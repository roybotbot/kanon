"""Evidence crawler — fetch URLs, diff against baseline, detect meaningful changes.

Fetches evidence source URLs, strips HTML to text, compares against
stored baselines, and triggers drift detection when content changes
meaningfully.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

import httpx

from kanon.graph import KnowledgeGraph
from kanon.models.entities import Evidence


BASELINE_DIR_NAME = "evidence_baselines"


@dataclass
class CrawlResult:
    """Result of crawling a single evidence source."""

    evidence_id: str
    url: str
    status: str  # "unchanged", "changed", "new", "error", "no_url"
    diff_summary: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CrawlReport:
    """Result of crawling all evidence sources."""

    results: list[CrawlResult] = field(default_factory=list)
    changed: list[CrawlResult] = field(default_factory=list)
    unchanged: list[CrawlResult] = field(default_factory=list)
    errors: list[CrawlResult] = field(default_factory=list)
    new: list[CrawlResult] = field(default_factory=list)


def strip_html(html: str) -> str:
    """Extract meaningful text content from HTML.

    Strips tags, scripts, styles, nav elements, and normalizes whitespace.
    """
    # Remove script and style blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove nav, header, footer blocks
    text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<header[^>]*>.*?</header>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Remove all remaining tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Decode common HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def is_meaningful_change(old_text: str, new_text: str) -> tuple[bool, str]:
    """Determine if the difference between old and new text is meaningful.

    Filters out noise: whitespace-only changes, tiny edits (< 1% of content),
    date-only changes.

    Returns (is_meaningful, summary).
    """
    if old_text == new_text:
        return False, "No change"

    # Normalize for comparison
    old_norm = re.sub(r"\s+", " ", old_text).strip().lower()
    new_norm = re.sub(r"\s+", " ", new_text).strip().lower()

    if old_norm == new_norm:
        return False, "Whitespace-only change"

    # Calculate change magnitude
    old_words = set(old_norm.split())
    new_words = set(new_norm.split())
    added = new_words - old_words
    removed = old_words - new_words
    total = max(len(old_words), len(new_words), 1)
    change_ratio = (len(added) + len(removed)) / total

    if change_ratio < 0.01:
        return False, f"Trivial change ({change_ratio:.1%} of content)"

    # Check if only dates changed
    date_pattern = re.compile(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b")
    old_no_dates = date_pattern.sub("DATE", old_norm)
    new_no_dates = date_pattern.sub("DATE", new_norm)
    if old_no_dates == new_no_dates:
        return False, "Date-only change"

    # Build summary
    summary_parts = []
    if len(added) > 0:
        sample = list(added)[:10]
        summary_parts.append(f"{len(added)} words added")
    if len(removed) > 0:
        sample = list(removed)[:10]
        summary_parts.append(f"{len(removed)} words removed")
    summary_parts.append(f"{change_ratio:.1%} of content changed")

    return True, "; ".join(summary_parts)


def _get_baseline_dir(data_dir: Path) -> Path:
    """Get or create the baselines directory."""
    baseline_dir = data_dir / BASELINE_DIR_NAME
    baseline_dir.mkdir(exist_ok=True)
    return baseline_dir


def _load_baseline(baseline_dir: Path, evidence_id: str) -> Optional[str]:
    """Load stored baseline text for an evidence source."""
    path = baseline_dir / f"{evidence_id}.txt"
    if path.exists():
        return path.read_text()
    return None


def _save_baseline(baseline_dir: Path, evidence_id: str, text: str) -> None:
    """Save baseline text for an evidence source."""
    path = baseline_dir / f"{evidence_id}.txt"
    path.write_text(text)


def fetch_evidence(url: str, timeout: int = 30) -> str:
    """Fetch a URL and return stripped text content."""
    response = httpx.get(
        url,
        timeout=timeout,
        follow_redirects=True,
        headers={"User-Agent": "kanon-evidence-crawler/0.1"},
    )
    response.raise_for_status()
    return strip_html(response.text)


def crawl_evidence(
    graph: KnowledgeGraph,
    data_dir: Path,
    fetch_fn=None,
) -> CrawlReport:
    """Crawl all evidence sources and compare against stored baselines.

    Args:
        graph: The knowledge graph containing evidence entities.
        data_dir: Path to the data directory (baselines stored here).
        fetch_fn: Optional function to fetch URL content (for testing).
                  Signature: (url: str) -> str. Defaults to fetch_evidence.
    """
    if fetch_fn is None:
        fetch_fn = fetch_evidence

    baseline_dir = _get_baseline_dir(data_dir)
    report = CrawlReport()

    for entity in graph.entities.values():
        if not isinstance(entity, Evidence):
            continue

        if not entity.url:
            result = CrawlResult(
                evidence_id=entity.id,
                url="",
                status="no_url",
            )
            report.results.append(result)
            continue

        try:
            new_text = fetch_fn(entity.url)
        except Exception as e:
            result = CrawlResult(
                evidence_id=entity.id,
                url=entity.url,
                status="error",
                error=str(e),
            )
            report.results.append(result)
            report.errors.append(result)
            continue

        old_text = _load_baseline(baseline_dir, entity.id)

        if old_text is None:
            # First crawl — save baseline
            _save_baseline(baseline_dir, entity.id, new_text)
            result = CrawlResult(
                evidence_id=entity.id,
                url=entity.url,
                status="new",
                diff_summary="First crawl — baseline saved",
            )
            report.results.append(result)
            report.new.append(result)
            continue

        meaningful, summary = is_meaningful_change(old_text, new_text)

        if meaningful:
            _save_baseline(baseline_dir, entity.id, new_text)
            result = CrawlResult(
                evidence_id=entity.id,
                url=entity.url,
                status="changed",
                diff_summary=summary,
            )
            report.results.append(result)
            report.changed.append(result)
        else:
            result = CrawlResult(
                evidence_id=entity.id,
                url=entity.url,
                status="unchanged",
                diff_summary=summary,
            )
            report.results.append(result)
            report.unchanged.append(result)

    return report
