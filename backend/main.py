"""
GenAI SaaS — FastAPI Backend
Research Assistant with Auth, Rate Limiting, Streaming, Billing
"""

import os
import uuid
import json
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.db.models import (
    User, ResearchProject, ResearchResult, UsageLog,
    PlanType, PLAN_LIMITS, get_db, create_tables,
)
from backend.services.auth_service import (
    hash_password, verify_password, create_access_token,
    generate_api_key, get_current_user,
)
from backend.middleware.rate_limiter import check_rate_limit, get_usage_stats
from backend.services.ai_service import research_query, research_query_stream, summarize_results

# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ResearchAI SaaS API",
    description="Full-stack GenAI SaaS — Research Assistant with Auth, Billing, Streaming",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    create_tables()


# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class ProjectCreate(BaseModel):
    title: str
    description: Optional[str] = None


class ResearchRequest(BaseModel):
    query: str
    project_id: Optional[str] = None
    context: Optional[str] = None
    stream: bool = False
    groq_api_key: Optional[str] = None


class UpgradePlanRequest(BaseModel):
    plan: str  # "pro" or "enterprise"


# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.post("/api/auth/register", tags=["Auth"])
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        id=str(uuid.uuid4()),
        email=req.email,
        name=req.name,
        hashed_password=hash_password(req.password),
        plan=PlanType.FREE,
        api_key=generate_api_key(),
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name, "plan": user.plan},
    }


@app.post("/api/auth/login", tags=["Auth"])
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": user.id})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "name": user.name, "plan": user.plan},
    }


@app.get("/api/auth/me", tags=["Auth"])
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "plan": current_user.plan,
        "api_key": current_user.api_key,
        "created_at": current_user.created_at,
    }


# ─── Projects Routes ──────────────────────────────────────────────────────────

@app.get("/api/projects", tags=["Projects"])
def list_projects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    projects = db.query(ResearchProject).filter(
        ResearchProject.user_id == current_user.id
    ).order_by(ResearchProject.created_at.desc()).all()

    return [
        {
            "id": p.id, "title": p.title, "description": p.description,
            "status": p.status, "created_at": p.created_at,
            "result_count": len(p.results),
        }
        for p in projects
    ]


@app.post("/api/projects", tags=["Projects"])
def create_project(
    req: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Check project limit
    limit = PLAN_LIMITS[current_user.plan]["projects"]
    if limit != -1:
        count = db.query(ResearchProject).filter(ResearchProject.user_id == current_user.id).count()
        if count >= limit:
            raise HTTPException(
                status_code=403,
                detail=f"Project limit ({limit}) reached. Upgrade to create more.",
            )

    project = ResearchProject(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        title=req.title,
        description=req.description,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return {"id": project.id, "title": project.title, "created_at": project.created_at}


@app.delete("/api/projects/{project_id}", tags=["Projects"])
def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(ResearchProject).filter(
        ResearchProject.id == project_id,
        ResearchProject.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
    return {"deleted": True}


# ─── Research Routes ──────────────────────────────────────────────────────────

@app.post("/api/research", tags=["Research"])
async def run_research(
    req: ResearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Rate limit check
    check_rate_limit(current_user.id, current_user.plan)

    # Plan feature check
    plan_limits = PLAN_LIMITS[current_user.plan]
    if req.stream and not plan_limits["streaming"]:
        raise HTTPException(
            status_code=403,
            detail="Streaming is a Pro feature. Upgrade your plan.",
        )

    max_tokens = plan_limits["tokens_per_request"]

    # Streaming response
    if req.stream:
        async def stream_gen():
            async for chunk in research_query_stream(req.query, req.context, max_tokens):
                yield chunk

        return StreamingResponse(stream_gen(), media_type="text/event-stream")

    # Standard response
    result = await research_query(req.query, req.context, max_tokens, api_key=req.groq_api_key)

    # Save to DB if project specified
    if req.project_id:
        project = db.query(ResearchProject).filter(
            ResearchProject.id == req.project_id,
            ResearchProject.user_id == current_user.id,
        ).first()
        if project:
            research_result = ResearchResult(
                id=str(uuid.uuid4()),
                project_id=req.project_id,
                query=req.query,
                answer=result["answer"],
                sources=json.dumps(result["sources"]),
                tokens_used=result["tokens_used"],
                model_used=result["model"],
            )
            db.add(research_result)

    # Log usage
    log = UsageLog(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        endpoint="/api/research",
        tokens_used=result["tokens_used"],
        cost_usd=result["tokens_used"] * 0.000001,
    )
    db.add(log)
    db.commit()

    return result


@app.get("/api/research/{project_id}", tags=["Research"])
def get_project_results(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.query(ResearchProject).filter(
        ResearchProject.id == project_id,
        ResearchProject.user_id == current_user.id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return [
        {
            "id": r.id,
            "query": r.query,
            "answer": r.answer,
            "sources": json.loads(r.sources) if r.sources else [],
            "tokens_used": r.tokens_used,
            "created_at": r.created_at,
        }
        for r in project.results
    ]


# ─── Dashboard & Billing Routes ───────────────────────────────────────────────

@app.get("/api/dashboard", tags=["Dashboard"])
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan_limits = PLAN_LIMITS[current_user.plan]
    usage = get_usage_stats(current_user.id)
    projects = db.query(ResearchProject).filter(ResearchProject.user_id == current_user.id).count()
    total_queries = db.query(ResearchResult).join(ResearchProject).filter(
        ResearchProject.user_id == current_user.id
    ).count()

    return {
        "user": {"name": current_user.name, "email": current_user.email, "plan": current_user.plan},
        "usage": {
            "requests_today": usage["requests_today"],
            "requests_limit": plan_limits["requests_per_day"],
            "projects_used": projects,
            "projects_limit": plan_limits["projects"],
            "total_queries": total_queries,
        },
        "plan": {
            "name": current_user.plan,
            "limits": plan_limits,
        },
    }


@app.post("/api/billing/upgrade", tags=["Billing"])
def upgrade_plan(
    req: UpgradePlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # In production: integrate Stripe here
    valid_plans = {"pro": PlanType.PRO, "enterprise": PlanType.ENTERPRISE}
    if req.plan not in valid_plans:
        raise HTTPException(status_code=400, detail="Invalid plan")

    current_user.plan = valid_plans[req.plan]
    db.commit()

    return {
        "message": f"Plan upgraded to {req.plan}",
        "plan": current_user.plan,
        "limits": PLAN_LIMITS[current_user.plan],
    }


@app.get("/api/billing/plans", tags=["Billing"])
def get_plans():
    return {
        "plans": [
            {
                "name": "Free",
                "price_usd": 0,
                "requests_per_day": PLAN_LIMITS[PlanType.FREE]["requests_per_day"],
                "projects": PLAN_LIMITS[PlanType.FREE]["projects"],
                "streaming": PLAN_LIMITS[PlanType.FREE]["streaming"],
            },
            {
                "name": "Pro",
                "price_usd": 29,
                "requests_per_day": PLAN_LIMITS[PlanType.PRO]["requests_per_day"],
                "projects": PLAN_LIMITS[PlanType.PRO]["projects"],
                "streaming": PLAN_LIMITS[PlanType.PRO]["streaming"],
            },
            {
                "name": "Enterprise",
                "price_usd": 199,
                "requests_per_day": PLAN_LIMITS[PlanType.ENTERPRISE]["requests_per_day"],
                "projects": "Unlimited",
                "streaming": PLAN_LIMITS[PlanType.ENTERPRISE]["streaming"],
            },
        ]
    }


@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "version": "1.0.0", "timestamp": datetime.utcnow()}
