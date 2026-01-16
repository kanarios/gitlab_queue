"""Schemas for secret values."""

from d42 import schema

# General schema for secret strings
# Constraints: min 8 chars (security), max 256 (reasonable limit)
SecretValueSchema = schema.str.len(8, 256)

# GitLab Personal Access Token
# Format: glpat-XXXXXXXXXXXXXXXXXXXX (26+ chars)
GitLabTokenSchema = schema.str.regex(r"^glpat-[a-zA-Z0-9_-]{20,44}$")

# Webhook Secret
# Min 16 chars for security
WebhookSecretSchema = schema.str.len(16, 128)

# JWT Secret
# Min 64 chars per Settings validation
JWTSecretSchema = schema.str.len(64, 256)

__all__ = [
    "GitLabTokenSchema",
    "JWTSecretSchema",
    "SecretValueSchema",
    "WebhookSecretSchema",
]
