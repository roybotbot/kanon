"""Anthropic API authentication.

Supports two methods:
1. OAuth token from pi's auth store (~/.pi/agent/auth.json)
2. ANTHROPIC_API_KEY environment variable

OAuth tokens use Bearer auth; API keys use x-api-key header.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

PI_AUTH_PATH = Path.home() / ".pi" / "agent" / "auth.json"
API_BASE = "https://api.anthropic.com"


@dataclass
class AnthropicCredential:
    token: str
    is_oauth: bool

    def auth_headers(self) -> dict[str, str]:
        if self.is_oauth:
            return {
                "Authorization": f"Bearer {self.token}",
                "anthropic-beta": "claude-code-20250219,oauth-2025-04-20",
            }
        return {"x-api-key": self.token}

    def wrap_system_prompt(self, system_prompt: str) -> str | list[dict]:
        """Wrap system prompt for API compatibility.

        OAuth tokens require the Claude Code identity prefix and array format.
        API keys use the system prompt as-is (string).
        """
        if self.is_oauth:
            return [
                {
                    "type": "text",
                    "text": "You are Claude Code, Anthropic's official CLI for Claude.",
                },
                {"type": "text", "text": system_prompt},
            ]
        return system_prompt


def get_credential() -> Optional[AnthropicCredential]:
    """Resolve an Anthropic credential, checking OAuth first, then env var."""
    # 1. Try pi's OAuth token
    if PI_AUTH_PATH.exists():
        try:
            data = json.loads(PI_AUTH_PATH.read_text())
            anthropic = data.get("anthropic", {})
            if anthropic.get("type") == "oauth" and anthropic.get("access"):
                return AnthropicCredential(
                    token=anthropic["access"],
                    is_oauth=True,
                )
        except (json.JSONDecodeError, KeyError):
            pass

    # 2. Fall back to environment variable
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        return AnthropicCredential(token=api_key, is_oauth=False)

    return None
