"""
Rate limiting middleware — enforces per-plan request limits.
Uses in-memory counters (swap for Redis in production).
"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException, status
from backend.db.models import PLAN_LIMITS, PlanType

# In-memory rate limit store: {user_id: [(timestamp, count)]}
_request_counts: dict = defaultdict(list)


def check_rate_limit(user_id: str, plan: PlanType):
    """Check if user has exceeded their daily request limit"""
    limit = PLAN_LIMITS[plan]["requests_per_day"]
    now = time.time()
    day_ago = now - 86400  # 24 hours

    # Clean up old entries
    _request_counts[user_id] = [
        (ts, c) for ts, c in _request_counts[user_id] if ts > day_ago
    ]

    # Count today's requests
    total = sum(c for _, c in _request_counts[user_id])

    if total >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily limit of {limit} requests reached. Upgrade your plan for more.",
            headers={"X-RateLimit-Limit": str(limit), "X-RateLimit-Remaining": "0"},
        )

    # Record this request
    _request_counts[user_id].append((now, 1))
    return limit - total - 1  # remaining


def get_usage_stats(user_id: str) -> dict:
    """Get usage stats for a user"""
    now = time.time()
    day_ago = now - 86400
    _request_counts[user_id] = [
        (ts, c) for ts, c in _request_counts[user_id] if ts > day_ago
    ]
    used = sum(c for _, c in _request_counts[user_id])
    return {"requests_today": used}
