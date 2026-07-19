# 🔬 ResearchAI — Full-Stack GenAI SaaS

A complete AI-powered research assistant SaaS with authentication, billing plans, and project management.

## ✨ Features

- JWT authentication (register, login, API keys)
- Free, Pro, and Enterprise plan tiers with rate limiting
- AI research assistant powered by Llama 3.3 70B via Groq
- Save research results to projects
- Usage dashboard with metrics
- Billing and plan upgrade flow

## 🏗️ Tech Stack

- FastAPI + SQLAlchemy + SQLite — Backend
- Llama 3.3 70B via Groq — AI responses
- JWT + bcrypt — Authentication
- Streamlit — Frontend

## 🚀 Run Locally

Terminal 1 - Backend:
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

Terminal 2 - Frontend:
streamlit run app.py

## ☁️ Deploy on Render.com

Backend: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
Frontend: streamlit run app.py --server.port $PORT --server.address 0.0.0.0
Environment variables: GROQ_API_KEY, API_BASE

## 🧪 Tests

pytest tests/ -v

---
Built with FastAPI + SQLite + Llama 3.3 70B + Streamlit
