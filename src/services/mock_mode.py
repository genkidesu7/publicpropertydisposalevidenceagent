"""AgentCore Platform v1.0"""

# Shared mock-mode flag resolution — single source of truth for every service.
# See .claude/rules/implementation_rule.md Rule 1: the scaffold deploy-stg CI
# job sets STG_MOCK_MODE on the uvicorn process, never USE_MOCK. A helper that
# only checks USE_MOCK silently fails to activate mock mode in that job.

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

_env: dict[str, str | None] = dotenv_values(Path(__file__).parent.parent.parent / ".env")

_TRUE_VALUES = ("1", "true", "yes")


def _get_flag(key: str) -> str:
    """OS env takes precedence over .env file."""
    return os.environ.get(key) or _env.get(key) or ""


def mock_mode_enabled() -> bool:
    """Resolve mock mode under either accepted alias.

    Canonical: USE_MOCK (what tests set).
    CI alias: STG_MOCK_MODE (what deploy-stg actually sets).
    """
    return _get_flag("USE_MOCK").lower() in _TRUE_VALUES or _get_flag("STG_MOCK_MODE").lower() in _TRUE_VALUES
