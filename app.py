"""
ResearchAI SaaS — Clean Streamlit UI
FastAPI backend + Llama 3 + JWT Auth
"""

import os
import json
import requests
import streamlit as st

st.set_page_config(
    page_title="ResearchAI",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

# ── Session state ──────────────────────────────────────────────────────────────
for k, v in [("token", None), ("user", None), ("page", "home"), ("qa_history", []), ("groq_key", "")]:
    if k not in st.session_state:
        st.session_state[k] = v

# ── API helpers ────────────────────────────────────────────────────────────────
def api_headers():
    return {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}

def api_get(path):
    try:
        r = requests.get(f"{API_BASE}{path}", headers=api_headers(), timeout=30)
        return r.json() if r.ok else None
    except:
        return None

def api_post(path, data):
    try:
        r = requests.post(f"{API_BASE}{path}", json=data, headers=api_headers(), timeout=60)
        return r.json(), r.ok
    except Exception as e:
        return {"detail": str(e)}, False

def api_delete(path):
    try:
        r = requests.delete(f"{API_BASE}{path}", headers=api_headers(), timeout=10)
        return r.ok
    except:
        return False

def nav(page):
    st.session_state.page = page
    st.rerun()

# ════════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ════════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 🔬 ResearchAI")
    st.markdown("---")

    groq_key = st.text_input("Groq API Key", type="password", placeholder="gsk_...",
                              help="Get your free key at console.groq.com")
    if groq_key:
        os.environ["GROQ_API_KEY"] = groq_key
        st.session_state.groq_key = groq_key
        st.success("✅ Key set")
    elif os.getenv("GROQ_API_KEY"):
        st.success("✅ Key loaded")
    else:
        st.warning("⚠️ Add Groq API key")
    st.markdown("---")

    if st.session_state.user:
        user = st.session_state.user
        plan = user.get("plan", "free")
        plan_colors = {"free": "🔵", "pro": "🟣", "enterprise": "🟢"}
        st.markdown(f"**{user.get('name', 'User')}**")
        st.markdown(f"{plan_colors.get(plan, '🔵')} {plan.upper()} Plan")
        st.markdown(f"✉️ {user.get('email', '')}")
        st.markdown("---")

        if st.button("🏠 Dashboard", use_container_width=True):
            nav("home")
        if st.button("🔬 Research", use_container_width=True):
            nav("research")
        if st.button("📁 Projects", use_container_width=True):
            nav("projects")
        if st.button("💳 Billing", use_container_width=True):
            nav("billing")
        if st.button("🔑 API Keys", use_container_width=True):
            nav("apikeys")

        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.token = None
            st.session_state.user = None
            st.session_state.page = "home"
            st.rerun()
    else:
        st.info("Sign in to get started")
        if st.button("🔐 Login / Register", use_container_width=True):
            nav("login")

    st.markdown("---")
    st.caption("FastAPI · SQLite · Llama 3 · Streamlit")

# ════════════════════════════════════════════════════════════════════════════════
# AUTH
# ════════════════════════════════════════════════════════════════════════════════
if not st.session_state.user:
    if st.session_state.page == "login":
        st.title("🔬 ResearchAI")
        st.markdown("Your AI-powered research assistant")
        st.markdown("---")

        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])

        with tab1:
            email = st.text_input("Email", placeholder="you@example.com", key="l_email")
            password = st.text_input("Password", type="password", key="l_pass")
            if st.button("Login →", use_container_width=True, key="do_login"):
                result, ok = api_post("/api/auth/login", {"email": email, "password": password})
                if ok:
                    st.session_state.token = result["access_token"]
                    st.session_state.user = result["user"]
                    nav("home")
                else:
                    st.error(result.get("detail", "Login failed"))

        with tab2:
            name = st.text_input("Full name", placeholder="Rohan Vishwanath", key="r_name")
            email2 = st.text_input("Email", placeholder="you@example.com", key="r_email")
            password2 = st.text_input("Password", type="password", key="r_pass")
            if st.button("Create Account →", use_container_width=True, key="do_register"):
                result, ok = api_post("/api/auth/register", {"name": name, "email": email2, "password": password2})
                if ok:
                    st.session_state.token = result["access_token"]
                    st.session_state.user = result["user"]
                    nav("home")
                else:
                    st.error(result.get("detail", "Registration failed"))
    else:
        st.title("🔬 ResearchAI")
        st.markdown("### Your AI-powered research assistant")
        st.markdown("Ask any question, get grounded answers powered by Llama 3.")
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("🧠 **Deep Research**\n\nAsk complex questions and get thorough answers with citations")
        with col2:
            st.info("⚡ **Streaming**\n\nWatch answers generate in real-time (Pro plan)")
        with col3:
            st.info("📁 **Projects**\n\nOrganize research into projects and save results")
        st.markdown("---")
        if st.button("🚀 Get Started Free", use_container_width=True):
            nav("login")
    st.stop()

# ════════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":
    st.title(f"👋 Welcome, {st.session_state.user.get('name', 'User').split()[0]}!")
    dash = api_get("/api/dashboard") or {}
    usage = dash.get("usage", {})

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Requests Today", usage.get("requests_today", 0))
    col2.metric("Daily Limit", usage.get("requests_limit", 10))
    col3.metric("Projects", usage.get("projects_used", 0))
    col4.metric("Total Queries", usage.get("total_queries", 0))

    st.markdown("---")
    used = usage.get("requests_today", 0)
    limit = usage.get("requests_limit", 10)
    pct = min(used / max(limit, 1), 1.0)
    st.markdown(f"**Usage today:** {used}/{limit} requests")
    st.progress(pct)

    if pct > 0.8:
        st.warning("⚠️ Approaching daily limit. Consider upgrading!")
        if st.button("⬆️ Upgrade Plan"):
            nav("billing")

    st.markdown("---")
    st.markdown("### ⚡ Quick Research")
    q = st.text_input("Ask anything", placeholder="What would you like to research?")
    if st.button("🔬 Research", use_container_width=True):
        if q.strip():
            with st.spinner("Researching..."):
                result, ok = api_post("/api/research", {"query": q, "groq_api_key": st.session_state.groq_key or os.getenv("GROQ_API_KEY", "")})
                if ok:
                    st.session_state.qa_history.insert(0, {
                        "question": q,
                        "answer": result.get("answer", ""),
                        "sources": result.get("sources", []),
                    })
                    st.rerun()
                else:
                    st.error(result.get("detail", "Research failed"))

    if st.session_state.qa_history:
        st.markdown("### 📝 Recent Answers")
        for qa in st.session_state.qa_history[:3]:
            with st.expander(f"❓ {qa['question'][:80]}..."):
                st.markdown(qa["answer"])
                if qa.get("sources"):
                    for s in qa["sources"]:
                        st.caption(f"🔗 [{s['title']}]({s['url']})")

# ════════════════════════════════════════════════════════════════════════════════
# RESEARCH
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "research":
    st.title("🔬 Research Assistant")
    projects = api_get("/api/projects") or []
    proj_map = {"None": None} | {p["title"]: p["id"] for p in projects}

    with st.form("research_form"):
        query = st.text_area("Your research question", height=120,
                             placeholder="Ask anything in detail...")
        proj = st.selectbox("Save to project", list(proj_map.keys()))
        submitted = st.form_submit_button("🔬 Research", use_container_width=True)

    if submitted and query.strip():
        with st.spinner("🤖 Researching..."):
            result, ok = api_post("/api/research", {"query": query, "project_id": proj_map.get(proj), "groq_api_key": st.session_state.groq_key or os.getenv("GROQ_API_KEY", "")})
            if ok:
                st.session_state.qa_history.insert(0, {
                    "question": query,
                    "answer": result.get("answer", ""),
                    "sources": result.get("sources", []),
                })
                st.success("✅ Done!")
                st.markdown("### 📝 Answer")
                st.markdown(result.get("answer", ""))
                if result.get("sources"):
                    st.markdown("**Sources:**")
                    for s in result["sources"]:
                        st.markdown(f"- 🔗 [{s['title']}]({s['url']})")
            else:
                st.error(result.get("detail", "Failed"))

    if st.session_state.qa_history:
        st.markdown("---")
        st.markdown("### 📚 History")
        for qa in st.session_state.qa_history:
            with st.expander(f"❓ {qa['question'][:80]}..."):
                st.markdown(qa["answer"])
                for s in qa.get("sources", []):
                    st.caption(f"🔗 [{s['title']}]({s['url']})")

# ════════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "projects":
    st.title("📁 Research Projects")

    with st.expander("➕ Create New Project"):
        with st.form("new_project"):
            title = st.text_input("Project title")
            desc = st.text_area("Description", height=80)
            if st.form_submit_button("Create"):
                result, ok = api_post("/api/projects", {"title": title, "description": desc})
                if ok:
                    st.success(f"✅ '{title}' created!")
                    st.rerun()
                else:
                    st.error(result.get("detail", "Failed"))

    projects = api_get("/api/projects") or []
    if projects:
        for p in projects:
            with st.expander(f"📁 {p['title']} — {p['result_count']} queries"):
                st.caption(p.get("description", "No description"))
                st.caption(f"Created: {str(p['created_at'])[:10]}")
                if st.button("🗑️ Delete", key=f"del_{p['id']}"):
                    if api_delete(f"/api/projects/{p['id']}"):
                        st.rerun()
                results = api_get(f"/api/research/{p['id']}") or []
                for r in results[:3]:
                    st.markdown(f"**Q:** {r['query'][:80]}...")
                    st.markdown(f"**A:** {r['answer'][:200]}...")
                    st.divider()
    else:
        st.info("No projects yet. Create one above!")

# ════════════════════════════════════════════════════════════════════════════════
# BILLING
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "billing":
    st.title("💳 Plans & Billing")
    plans_data = api_get("/api/billing/plans")
    current = st.session_state.user.get("plan", "free")

    if plans_data:
        cols = st.columns(3)
        for i, plan in enumerate(plans_data["plans"]):
            pk = plan["name"].lower()
            with cols[i]:
                is_current = pk == current
                if is_current:
                    st.success(f"✅ **{plan['name']}** (Current)")
                else:
                    st.info(f"**{plan['name']}**")
                st.metric("Price", f"${plan['price_usd']}/mo")
                st.write(f"🔬 {plan['requests_per_day']} req/day")
                st.write(f"📁 {plan['projects']} projects")
                st.write(f"⚡ Streaming: {'✅' if plan['streaming'] else '❌'}")
                if not is_current and pk != "free":
                    if st.button(f"Upgrade to {plan['name']}", key=f"up_{pk}", use_container_width=True):
                        result, ok = api_post("/api/billing/upgrade", {"plan": pk})
                        if ok:
                            st.session_state.user["plan"] = pk
                            st.success(f"✅ Upgraded to {plan['name']}!")
                            st.rerun()

    st.info("💡 Payments via Stripe in production. Upgrade is simulated here.")

# ════════════════════════════════════════════════════════════════════════════════
# API KEYS
# ════════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "apikeys":
    st.title("🔑 API Keys")
    me = api_get("/api/auth/me")
    if me:
        st.markdown("### Your API Key")
        st.code(me.get("api_key", ""), language="text")
        st.caption("Use as Bearer token in API calls")

        st.markdown("### Quick Start")
        st.code(f"""import requests

headers = {{"Authorization": "Bearer {me.get('api_key', 'YOUR_KEY')}"}}
r = requests.post("{API_BASE}/api/research",
    headers=headers,
    json={{"query": "What is LangGraph?"}})
print(r.json())""", language="python")

        st.markdown(f"### [View API Docs →]({API_BASE}/docs)")
