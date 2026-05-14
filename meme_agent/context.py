"""Per-run context shared between the agent loop, tools, and guardrails."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MemeContext:
    user_allows_disk_write: bool = False

    fetched_image_path: str | None = None
    fetched_image_url: str | None = None
    vision_runs: int = 0
    web_searches: int = 0
    web_search_hits: int = 0
    last_search_snippets: list[str] = field(default_factory=list)

    activity: list[str] = field(default_factory=list)
