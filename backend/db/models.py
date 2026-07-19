"""
Database models for GenAI SaaS
Tables: users, sessions, research_projects, research_results, usage_logs
"""

from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, Float,
    DateTime, Boolean, Text, ForeignKey, Enum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import enum
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./saas.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class PlanType(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    plan = Column(Enum(PlanType), default=PlanType.FREE)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    api_key = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    projects = relationship("ResearchProject", back_populates="user", cascade="all, delete-orphan")
    usage_logs = relationship("UsageLog", back_populates="user", cascade="all, delete-orphan")


class ResearchProject(Base):
    __tablename__ = "research_projects"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="projects")
    results = relationship("ResearchResult", back_populates="project", cascade="all, delete-orphan")


class ResearchResult(Base):
    __tablename__ = "research_results"

    id = Column(String, primary_key=True)
    project_id = Column(String, ForeignKey("research_projects.id"), nullable=False)
    query = Column(Text, nullable=False)
    answer = Column(Text)
    sources = Column(Text)          # JSON string of sources
    tokens_used = Column(Integer, default=0)
    model_used = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("ResearchProject", back_populates="results")


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    endpoint = Column(String)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="usage_logs")


# Plan limits
PLAN_LIMITS = {
    PlanType.FREE: {
        "requests_per_day": 10,
        "tokens_per_request": 1000,
        "projects": 3,
        "streaming": False,
    },
    PlanType.PRO: {
        "requests_per_day": 100,
        "tokens_per_request": 2000,
        "projects": 20,
        "streaming": True,
    },
    PlanType.ENTERPRISE: {
        "requests_per_day": 10000,
        "tokens_per_request": 4000,
        "projects": -1,  # unlimited
        "streaming": True,
    },
}


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    Base.metadata.create_all(bind=engine)
