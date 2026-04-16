"""Pilot validation of tool inputs before execution (fail-fast, narrow scope)."""

from __future__ import annotations

from typing import Any


def _extract_nested_params(params: dict[str, Any]) -> dict[str, Any]:
    """Extract nested params from 'arguments', 'input', or 'params' wrappers."""
    if not isinstance(params, dict):
        return {}
    # Check for wrapped params (common in some LLM outputs)
    for wrapper_key in ("arguments", "input", "params"):
        wrapped = params.get(wrapper_key)
        if isinstance(wrapped, dict):
            # Merge outer params with wrapped params (wrapped takes precedence)
            merged = dict(params)
            merged.update(wrapped)
            # Remove the wrapper key
            merged.pop(wrapper_key, None)
            return merged
    return params


def _get_str_param(params: dict[str, Any], *keys: str) -> str | None:
    """Get first non-empty string value for any of the given keys."""
    for k in keys:
        v = params.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def pilot_validate_tool_input(tool_name: str, params: dict[str, Any]) -> str | None:
    """Return an error message if input is invalid; otherwise None.

    Only ``bash`` and ``write`` are validated here; other tools unchanged.
    """
    # Unwrap nested params for consistent validation
    params = _extract_nested_params(params)

    if tool_name == "bash":
        cmd = _get_str_param(params, "command")
        if not cmd:
            return "Invalid input for bash: 'command' must be a non-empty string."
        return None

    if tool_name == "write":
        fp = _get_str_param(params, "file_path", "filePath", "path", "filename")
        if not fp:
            return "Invalid input for write: 'file_path' must be a non-empty string."

        # Handle content: check various possible keys
        content = _get_str_param(params, "content", "text")
        if content is None and "content" not in params and "text" not in params:
            return "Invalid input for write: 'content' is required."
        # Content can be empty string, but if provided must be string
        if params.get("content") is not None and not isinstance(params.get("content"), str):
            return "Invalid input for write: 'content' must be a string."
        return None

    return None


__all__ = ["pilot_validate_tool_input"]
