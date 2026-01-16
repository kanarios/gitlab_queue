"""Utilities for creating d42 schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from d42 import schema

if TYPE_CHECKING:
    from enum import StrEnum

    from d42.declaration.types._any_schema import AnySchema


def enum_schema(enum_class: type[StrEnum]) -> AnySchema:
    """Create d42 schema from StrEnum.

    Generates a schema that accepts any value from the enum.

    Args:
        enum_class: StrEnum class to create schema from.

    Returns:
        d42 schema validating enum values.

    Example:
        >>> from scenarios.library import MRState
        >>> MRStateSchema = enum_schema(MRState)
        >>> fake(MRStateSchema)  # -> "opened" or "closed" or "merged"
    """
    return schema.any(*[schema.str(value) for value in enum_class])


__all__ = ["enum_schema"]
