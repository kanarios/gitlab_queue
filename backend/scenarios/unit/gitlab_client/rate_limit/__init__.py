"""Test scenarios for GitLabClient rate limiting.

Tests rate limit handling including:
- RateLimitState properties and calculations
- Retry-After header parsing
- 429 error handling
- Adaptive throttling behavior
"""
