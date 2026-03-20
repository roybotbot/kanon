"""Tests for Experiment 04: Evidence Crawling.

Uses mock fetch functions to avoid hitting real URLs.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kanon.crawl import (
    CrawlReport,
    crawl_evidence,
    is_meaningful_change,
    strip_html,
)
from kanon.graph import KnowledgeGraph


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def crawl_graph(tmp_path):
    """Graph with evidence sources for crawl testing."""
    entities = {
        "concepts": [
            {
                "id": "tool_use",
                "name": "Tool Use",
                "description": "Tool use",
                "supports": [],
                "prerequisites": [],
            },
        ],
        "facts": [
            {
                "id": "max_tools",
                "claim": "Max tools",
                "value": "128",
                "status": "active",
                "concept": "tool_use",
                "evidence": ["tool_docs"],
                "effective_date": "2025-01-01",
                "recorded_date": "2025-01-01",
            },
        ],
        "evidence": [
            {
                "id": "tool_docs",
                "name": "Tool Use Docs",
                "url": "https://example.com/tool-use",
                "source_type": "documentation",
                "last_verified": "2025-06-01",
            },
            {
                "id": "models_page",
                "name": "Models Page",
                "url": "https://example.com/models",
                "source_type": "documentation",
                "last_verified": "2025-06-01",
            },
            {
                "id": "no_url_source",
                "name": "Internal Notes",
                "source_type": "internal_note",
                "last_verified": "2025-06-01",
            },
        ],
    }

    for entity_type, items in entities.items():
        entity_dir = tmp_path / entity_type
        entity_dir.mkdir()
        for item in items:
            (entity_dir / f"{item['id']}.yaml").write_text(
                yaml.dump(item, default_flow_style=False)
            )

    for subdir in ["tasks", "capabilities", "constraints", "objectives", "audiences", "assets"]:
        (tmp_path / subdir).mkdir(exist_ok=True)

    return KnowledgeGraph(data_dir=tmp_path), tmp_path


# ── strip_html ───────────────────────────────────────────────────────


class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_removes_scripts(self):
        html = "<p>Before</p><script>var x = 1;</script><p>After</p>"
        assert "var x" not in strip_html(html)
        assert "Before" in strip_html(html)
        assert "After" in strip_html(html)

    def test_removes_styles(self):
        html = "<style>.foo { color: red; }</style><p>Content</p>"
        assert "color" not in strip_html(html)
        assert "Content" in strip_html(html)

    def test_removes_nav(self):
        html = "<nav><a>Home</a><a>About</a></nav><main>Real content</main>"
        result = strip_html(html)
        assert "Home" not in result
        assert "Real content" in result

    def test_removes_footer(self):
        html = "<main>Content</main><footer>Copyright 2025</footer>"
        result = strip_html(html)
        assert "Copyright" not in result
        assert "Content" in result

    def test_decodes_entities(self):
        assert strip_html("&amp; &lt; &gt; &quot; &#39;") == '& < > " \''

    def test_normalizes_whitespace(self):
        html = "<p>  lots   of    spaces  </p>"
        assert strip_html(html) == "lots of spaces"


# ── is_meaningful_change ─────────────────────────────────────────────


class TestIsMeaningfulChange:
    def test_identical_is_not_meaningful(self):
        meaningful, _ = is_meaningful_change("hello world", "hello world")
        assert not meaningful

    def test_whitespace_only_not_meaningful(self):
        meaningful, summary = is_meaningful_change("hello  world", "hello world")
        assert not meaningful
        assert "hitespace" in summary

    def test_real_content_change_is_meaningful(self):
        old = "The maximum context window is 200,000 tokens for all plans."
        new = "The maximum context window is 500,000 tokens for Pro plans and 200,000 for Free plans."
        meaningful, summary = is_meaningful_change(old, new)
        assert meaningful
        assert "changed" in summary

    def test_trivial_change_not_meaningful(self):
        # Change 1 word in 300 unique words — well under 1% threshold
        words = [f"word{i}" for i in range(300)]
        old = " ".join(words)
        words[-1] = "changed299"
        new = " ".join(words)
        meaningful, summary = is_meaningful_change(old, new)
        assert not meaningful
        assert "rivial" in summary

    def test_date_only_change_not_meaningful(self):
        old = "Last updated 2025-01-15. The API supports tool use."
        new = "Last updated 2025-03-20. The API supports tool use."
        meaningful, summary = is_meaningful_change(old, new)
        assert not meaningful
        assert "date" in summary.lower()

    def test_substantial_addition_is_meaningful(self):
        old = "Tool use allows calling functions."
        new = "Tool use allows calling functions. You can define up to 128 tools per request. Each tool needs a name, description, and input schema."
        meaningful, _ = is_meaningful_change(old, new)
        assert meaningful


# ── crawl_evidence ───────────────────────────────────────────────────


class TestCrawlEvidence:
    def test_first_crawl_saves_baseline(self, crawl_graph):
        """First crawl should save baselines and report status 'new'."""
        g, tmp_path = crawl_graph

        def mock_fetch(url):
            return f"Content for {url}"

        report = crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)

        new_ids = {r.evidence_id for r in report.new}
        assert "tool_docs" in new_ids
        assert "models_page" in new_ids

        # Baselines should be saved
        baseline_dir = tmp_path / "evidence_baselines"
        assert (baseline_dir / "tool_docs.txt").exists()
        assert (baseline_dir / "models_page.txt").exists()

    def test_no_change_reports_unchanged(self, crawl_graph):
        """Second crawl with same content should report 'unchanged'."""
        g, tmp_path = crawl_graph

        def mock_fetch(url):
            return f"Content for {url}"

        # First crawl
        crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)
        # Second crawl — same content
        report = crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)

        unchanged_ids = {r.evidence_id for r in report.unchanged}
        assert "tool_docs" in unchanged_ids

    def test_meaningful_change_detected(self, crawl_graph):
        """Changed content should report 'changed'."""
        g, tmp_path = crawl_graph

        call_count = {"n": 0}

        def mock_fetch(url):
            call_count["n"] += 1
            if "tool-use" in url:
                if call_count["n"] <= 2:  # first crawl hits both URLs
                    return "Tool use supports up to 64 tools per request."
                else:
                    return "Tool use supports up to 128 tools per request. Each tool needs a name, description, and input schema defined in JSON Schema format."
            return "Stable content that does not change between crawls."

        # First crawl
        crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)
        # Second crawl — tool docs changed
        report = crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)

        changed_ids = {r.evidence_id for r in report.changed}
        assert "tool_docs" in changed_ids
        assert report.changed[0].diff_summary is not None

    def test_no_url_skipped(self, crawl_graph):
        """Evidence without URL should be skipped."""
        g, tmp_path = crawl_graph

        def mock_fetch(url):
            return "content"

        report = crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)
        no_url_ids = {r.evidence_id for r in report.results if r.status == "no_url"}
        assert "no_url_source" in no_url_ids

    def test_fetch_error_reported(self, crawl_graph):
        """Fetch errors should be reported, not crash."""
        g, tmp_path = crawl_graph

        def mock_fetch(url):
            if "tool-use" in url:
                raise httpx.HTTPStatusError("404", request=None, response=None)
            return "content"

        report = crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)
        error_ids = {r.evidence_id for r in report.errors}
        assert "tool_docs" in error_ids

    def test_whitespace_change_filtered(self, crawl_graph):
        """Whitespace-only changes should not trigger 'changed'."""
        g, tmp_path = crawl_graph

        call_count = {"n": 0}

        def mock_fetch(url):
            call_count["n"] += 1
            if call_count["n"] <= 2:
                return "Tool use allows calling external functions."
            return "Tool  use  allows  calling  external  functions."

        crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)
        report = crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)

        assert len(report.changed) == 0

    def test_baseline_updated_on_change(self, crawl_graph):
        """When content changes, baseline should be updated."""
        g, tmp_path = crawl_graph

        version = {"v": 1}

        def mock_fetch(url):
            if "tool-use" in url:
                if version["v"] == 1:
                    return "Version one content with many words to make it substantial enough."
                return "Version two content is completely different with new information about the API and tools."
            return "Stable content."

        crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)
        version["v"] = 2
        crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)

        baseline = (tmp_path / "evidence_baselines" / "tool_docs.txt").read_text()
        assert "Version two" in baseline


# ── Integration with drift ───────────────────────────────────────────


class TestCrawlDriftIntegration:
    def test_changed_evidence_triggers_drift(self, crawl_graph):
        """When crawl detects a change, drift detection finds affected facts."""
        from kanon.drift import detect_drift

        g, tmp_path = crawl_graph

        call_count = {"n": 0}

        def mock_fetch(url):
            call_count["n"] += 1
            if "tool-use" in url:
                if call_count["n"] <= 2:
                    return "Max tools is 64 per request in the current API version."
                return "Max tools is 128 per request in the current API version. New feature: tool streaming support added."
            return "Stable content."

        crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)
        report = crawl_evidence(g, tmp_path, fetch_fn=mock_fetch)

        # For each changed evidence, run drift
        for result in report.changed:
            drift_report = detect_drift(
                g,
                evidence_id=result.evidence_id,
                change_description=result.diff_summary or "Content changed",
            )
            # Should find the fact backed by this evidence
            stale_ids = {f.id for f in drift_report.stale_facts}
            assert "max_tools" in stale_ids
