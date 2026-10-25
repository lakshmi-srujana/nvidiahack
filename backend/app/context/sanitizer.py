from __future__ import annotations

import re
from datetime import datetime, timezone
from hashlib import sha256
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class EvidenceItem(BaseModel):
    """Untrusted, bounded web evidence; it deliberately has no policy fields."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    evidence_id: str
    url: HttpUrl
    domain: str
    title: str = Field(max_length=300)
    excerpt: str = Field(max_length=5000)
    retrieved_at: datetime
    published_at: datetime | None = None
    score: float | None = None
    provider: str = "tavily"
    trust: str = "UNTRUSTED_WEB"
    flagged: bool = False


_INSTRUCTION_MARKERS = (
    "system:",
    "developer:",
    "ignore previous",
    "<|",
    "```",
    "safety_policy",
    "certificate",
    "</context>",
)
_CONTROL_PATTERN = re.compile(
    "|".join(re.escape(marker) for marker in _INSTRUCTION_MARKERS), re.IGNORECASE
)


def sanitize_evidence(results: list[dict[str, object]], char_limit: int = 1200) -> list[EvidenceItem]:
    """Normalizes data, removes prompt-control markers, and preserves provenance.

    This is defense in depth: evidence is additionally placed in a separately
    labelled untrusted prompt block and is never merged with policy DTOs.
    """
    safe: list[EvidenceItem] = []
    seen: set[str] = set()
    for result in results:
        raw_url = str(result.get("url", "")).strip()
        parsed = urlparse(raw_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or raw_url in seen:
            continue
        seen.add(raw_url)
        raw = " ".join(str(result.get("content", result.get("excerpt", ""))).split())[
            :char_limit
        ]
        raw, redactions = _CONTROL_PATTERN.subn("[redacted-control-marker]", raw)
        title = " ".join(str(result.get("title", "")).split())[:300]
        title, title_redactions = _CONTROL_PATTERN.subn("[redacted-control-marker]", title)
        published_at = result.get("published_date") or result.get("published_at")
        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except ValueError:
                published_at = None
        elif not isinstance(published_at, datetime):
            published_at = None
        score = result.get("score")
        if not isinstance(score, (int, float)):
            score = None
        digest = sha256(raw_url.encode()).hexdigest()[:16]
        safe.append(
            EvidenceItem(
                evidence_id=f"web-{digest}",
                url=raw_url,
                domain=parsed.netloc.lower(),
                title=title,
                excerpt=raw,
                retrieved_at=datetime.now(timezone.utc),
                published_at=published_at,
                score=float(score) if score is not None else None,
                flagged=(redactions + title_redactions) > 0,
            )
        )
    return safe
