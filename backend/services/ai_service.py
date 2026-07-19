"""
AI Research Assistant Service
Core LangGraph agent with streaming support.
Tools: web search simulation, summarization, citation extraction.
"""

import os
import json
import asyncio
from typing import AsyncGenerator, Optional
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

SYSTEM_PROMPT = """You are ResearchAI, an expert research assistant built into a SaaS platform.

Your job is to:
1. Thoroughly analyze research questions
2. Provide well-structured, cited answers
3. Break down complex topics clearly
4. Suggest related questions for deeper research
5. Always acknowledge uncertainty when present

Format your responses with:
- Clear headings using **bold**
- Bullet points for lists
- Source citations as [1], [2] etc.
- A "Related Questions" section at the end

Be comprehensive but concise. Lead with the most important information."""


def get_llm(max_tokens: int = 1000, stream: bool = False, api_key: str = None):
    key = api_key or GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
    if not key:
        raise ValueError("GROQ_API_KEY not set")
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0.2,
        max_tokens=max_tokens,
        api_key=key,
        streaming=stream,
    )


async def research_query(
    query: str,
    context: Optional[str] = None,
    max_tokens: int = 1000,
    api_key: str = None,
) -> dict:
    """Run a research query and return the full response"""
    llm = get_llm(max_tokens=max_tokens, api_key=api_key)

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    if context:
        messages.append(HumanMessage(content=f"Previous context:\n{context}\n\nNew question: {query}"))
    else:
        messages.append(HumanMessage(content=query))

    response = llm.invoke(messages)
    answer = response.content

    # Extract mock sources (in production, integrate real web search)
    sources = _extract_sources(query, answer)
    tokens_used = len(answer.split()) * 2  # rough estimate

    return {
        "answer": answer,
        "sources": sources,
        "tokens_used": tokens_used,
        "model": "llama-3.3-70b-versatile",
    }


async def research_query_stream(
    query: str,
    context: Optional[str] = None,
    max_tokens: int = 1000,
) -> AsyncGenerator[str, None]:
    """Stream a research query response token by token"""
    llm = get_llm(max_tokens=max_tokens, stream=True)

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    if context:
        messages.append(HumanMessage(content=f"Previous context:\n{context}\n\nNew question: {query}"))
    else:
        messages.append(HumanMessage(content=query))

    # Stream the response
    full_response = ""
    async for chunk in llm.astream(messages):
        token = chunk.content
        if token:
            full_response += token
            yield f"data: {json.dumps({'token': token, 'type': 'token'})}\n\n"
            await asyncio.sleep(0)  # yield control

    # Send final metadata
    sources = _extract_sources(query, full_response)
    yield f"data: {json.dumps({'type': 'done', 'sources': sources, 'tokens': len(full_response.split()) * 2})}\n\n"


def _extract_sources(query: str, answer: str) -> list:
    """
    In production: integrate Tavily/Serper/Exa for real web search.
    For demo: generate plausible source suggestions based on the topic.
    """
    query_lower = query.lower()
    base_sources = []

    # Topic-based source suggestions
    if any(k in query_lower for k in ["ai", "machine learning", "llm", "neural"]):
        base_sources = [
            {"title": "Attention Is All You Need", "url": "https://arxiv.org/abs/1706.03762", "type": "paper"},
            {"title": "Stanford AI Index Report", "url": "https://aiindex.stanford.edu", "type": "report"},
        ]
    elif any(k in query_lower for k in ["python", "programming", "code", "software"]):
        base_sources = [
            {"title": "Python Documentation", "url": "https://docs.python.org", "type": "docs"},
            {"title": "Stack Overflow", "url": "https://stackoverflow.com", "type": "forum"},
        ]
    elif any(k in query_lower for k in ["research", "study", "science"]):
        base_sources = [
            {"title": "Google Scholar", "url": "https://scholar.google.com", "type": "database"},
            {"title": "PubMed", "url": "https://pubmed.ncbi.nlm.nih.gov", "type": "database"},
        ]
    else:
        base_sources = [
            {"title": "Wikipedia", "url": "https://wikipedia.org", "type": "encyclopedia"},
            {"title": "ResearchGate", "url": "https://researchgate.net", "type": "database"},
        ]

    return base_sources


def summarize_results(results: list) -> str:
    """Summarize multiple research results into a cohesive report"""
    llm = get_llm(max_tokens=3000)
    content = "\n\n---\n\n".join(
        f"Query: {r.get('query', '')}\nAnswer: {r.get('answer', '')[:500]}"
        for r in results[:5]
    )
    response = llm.invoke([
        SystemMessage(content="You are a research summarizer. Create a cohesive executive summary."),
        HumanMessage(content=f"Summarize these research findings:\n\n{content}"),
    ])
    return response.content
