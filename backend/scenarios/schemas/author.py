"""Schema for Author from src/gitlab_queue/models/mr.py."""

from d42 import optional, schema

# Corresponds to dataclass Author:
# - id: int
# - name: str
# - username: str
# - avatar_url: str | None = None
AuthorSchema = schema.dict(
    {
        "id": schema.int.min(1).max(2_147_483_647),  # int32 positive
        "name": schema.str.len(1, 255),
        # Note: d42 doesn't support chaining .len().regex(), so we use regex only
        "username": schema.str.regex(r"^[a-zA-Z0-9_.-]{1,255}$"),
        optional("avatar_url"): schema.str.len(1, 2048),
    }
)

__all__ = ["AuthorSchema"]
