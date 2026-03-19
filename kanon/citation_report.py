"""Render citation reports as markdown and HTML for review."""
from __future__ import annotations

from pathlib import Path

from kanon.citations import CitationReport, extract_citations, validate_citations, strip_citations, CITATION_PATTERN
from kanon.graph import KnowledgeGraph
from kanon.models.entities import Fact

import re


def render_citation_markdown(
    content: str,
    report: CitationReport,
    asset_name: str,
) -> str:
    """Render a markdown report with citations visible and a validation summary."""
    lines: list[str] = []

    lines.append(f"# Citation Report: {asset_name}")
    lines.append("")
    lines.append(f"**Total citations:** {report.total_citations}")
    lines.append(f"**Valid:** {len(report.valid)}")
    if report.missing_from_graph:
        lines.append(f"**Missing from graph:** {', '.join(report.missing_from_graph)}")
    if report.superseded:
        lines.append(f"**Superseded:** {', '.join(report.superseded)}")
    if report.retracted:
        lines.append(f"**Retracted:** {', '.join(report.retracted)}")
    lines.append(f"**Validation:** {'✅ PASS' if report.is_valid else '❌ FAIL'}")
    if report.failures:
        lines.append("")
        lines.append("### Failures")
        for f in report.failures:
            lines.append(f"- {f}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Generated Content (citations visible)")
    lines.append("")
    lines.append(content)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Clean Content (citations stripped)")
    lines.append("")
    lines.append(strip_citations(content))

    return "\n".join(lines)


def render_citation_html(
    content: str,
    report: CitationReport,
    graph: KnowledgeGraph,
    asset_name: str,
) -> str:
    """Render a self-contained HTML report with inline-highlighted citations."""

    # Build fact lookup for tooltips
    fact_info: dict[str, dict] = {}
    for fid in report.valid:
        entity = graph.get(fid)
        if isinstance(entity, Fact):
            fact_info[fid] = {
                "claim": entity.claim,
                "value": entity.value,
                "status": entity.status,
                "css_class": "citation-valid",
            }
    for fid in report.superseded:
        entity = graph.get(fid)
        if isinstance(entity, Fact):
            fact_info[fid] = {
                "claim": entity.claim,
                "value": entity.value,
                "status": "superseded",
                "css_class": "citation-superseded",
            }
    for fid in report.retracted:
        entity = graph.get(fid)
        if isinstance(entity, Fact):
            fact_info[fid] = {
                "claim": entity.claim,
                "value": entity.value,
                "status": "retracted",
                "css_class": "citation-retracted",
            }
    for fid in report.missing_from_graph:
        fact_info[fid] = {
            "claim": "Unknown",
            "value": "Not found in graph",
            "status": "missing",
            "css_class": "citation-missing",
        }

    # Convert markdown content to HTML with highlighted citations
    import html as html_mod

    def replace_citation(match: re.Match) -> str:
        fid = match.group(1)
        info = fact_info.get(fid, {
            "claim": "Unknown",
            "value": "Unknown",
            "status": "unknown",
            "css_class": "citation-missing",
        })
        tooltip = html_mod.escape(f"{info['claim']}: {info['value']} [{info['status']}]")
        css = info["css_class"]
        return f'<span class="citation {css}" title="{tooltip}">{{{{fact:{fid}}}}}</span>'

    highlighted = html_mod.escape(content)
    # Re-apply citation highlighting on escaped content
    highlighted = re.sub(
        r"\{\{fact:([a-zA-Z0-9_]+)\}\}",
        lambda m: replace_citation(m),
        highlighted,
    )
    # Convert markdown-ish formatting
    highlighted = highlighted.replace("\n\n", "</p><p>")
    highlighted = highlighted.replace("\n", "<br>")
    highlighted = f"<p>{highlighted}</p>"

    # Validation summary
    status_class = "pass" if report.is_valid else "fail"
    status_text = "✅ PASS — all citations reference active facts" if report.is_valid else "❌ FAIL — issues found"

    failures_html = ""
    if report.failures:
        items = "".join(f"<li>{html_mod.escape(f)}</li>" for f in report.failures)
        failures_html = f'<ul class="failures">{items}</ul>'

    # Fact legend
    legend_rows = ""
    all_ids = report.valid + report.superseded + report.retracted + report.missing_from_graph
    seen: set[str] = set()
    for fid in all_ids:
        if fid in seen:
            continue
        seen.add(fid)
        info = fact_info.get(fid, {"claim": "?", "value": "?", "status": "?", "css_class": "citation-missing"})
        legend_rows += (
            f'<tr class="{info["css_class"]}">'
            f'<td><code>{{{{fact:{fid}}}}}</code></td>'
            f'<td>{html_mod.escape(info["claim"])}</td>'
            f'<td>{html_mod.escape(info["value"])}</td>'
            f'<td>{info["status"]}</td>'
            f'</tr>'
        )

    clean_content = strip_citations(content)
    clean_escaped = html_mod.escape(clean_content)
    clean_escaped = clean_escaped.replace("\n\n", "</p><p>")
    clean_escaped = clean_escaped.replace("\n", "<br>")
    clean_escaped = f"<p>{clean_escaped}</p>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Citation Report: {html_mod.escape(asset_name)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; padding: 2rem; line-height: 1.6; }}
  h1 {{ color: #fff; margin-bottom: 0.5rem; }}
  h2 {{ color: #ccc; margin: 2rem 0 1rem; border-bottom: 1px solid #333; padding-bottom: 0.5rem; }}
  h3 {{ color: #aaa; margin: 1.5rem 0 0.5rem; }}

  .summary {{ background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; }}
  .summary .stat {{ display: inline-block; margin-right: 2rem; }}
  .summary .stat .label {{ color: #888; font-size: 0.85rem; }}
  .summary .stat .value {{ font-size: 1.2rem; font-weight: bold; }}

  .status {{ padding: 0.75rem 1rem; border-radius: 6px; margin: 1rem 0; font-weight: bold; }}
  .status.pass {{ background: #052e16; border: 1px solid #166534; color: #4ade80; }}
  .status.fail {{ background: #450a0a; border: 1px solid #991b1b; color: #f87171; }}

  .failures {{ margin: 0.5rem 0 0 1.5rem; }}
  .failures li {{ color: #f87171; margin: 0.25rem 0; }}

  .legend {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
  .legend th {{ text-align: left; padding: 0.5rem; border-bottom: 2px solid #333; color: #888; font-size: 0.85rem; text-transform: uppercase; }}
  .legend td {{ padding: 0.5rem; border-bottom: 1px solid #222; }}
  .legend code {{ background: #222; padding: 0.15rem 0.4rem; border-radius: 3px; font-size: 0.85rem; }}
  .legend .citation-valid td {{ color: #4ade80; }}
  .legend .citation-superseded td {{ color: #fbbf24; }}
  .legend .citation-retracted td {{ color: #f87171; }}
  .legend .citation-missing td {{ color: #f87171; }}

  .content {{ background: #111; border: 1px solid #333; border-radius: 8px; padding: 1.5rem; margin: 1rem 0; white-space: pre-wrap; font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.9rem; }}

  .citation {{ padding: 0.1rem 0.4rem; border-radius: 3px; font-family: 'SF Mono', 'Fira Code', monospace; font-size: 0.8rem; cursor: help; }}
  .citation-valid {{ background: #052e16; color: #4ade80; border: 1px solid #166534; }}
  .citation-superseded {{ background: #451a03; color: #fbbf24; border: 1px solid #92400e; }}
  .citation-retracted {{ background: #450a0a; color: #f87171; border: 1px solid #991b1b; }}
  .citation-missing {{ background: #450a0a; color: #f87171; border: 1px solid #991b1b; }}

  .tabs {{ display: flex; gap: 0; margin-top: 2rem; }}
  .tab {{ padding: 0.75rem 1.5rem; background: #1a1a1a; border: 1px solid #333; border-bottom: none; cursor: pointer; color: #888; border-radius: 6px 6px 0 0; }}
  .tab.active {{ background: #111; color: #fff; border-color: #333; }}
  .tab-content {{ display: none; }}
  .tab-content.active {{ display: block; }}
</style>
</head>
<body>

<h1>Citation Report</h1>
<h3>{html_mod.escape(asset_name)}</h3>

<div class="summary">
  <span class="stat"><span class="label">Citations</span><br><span class="value">{report.total_citations}</span></span>
  <span class="stat"><span class="label">Valid</span><br><span class="value" style="color:#4ade80">{len(report.valid)}</span></span>
  <span class="stat"><span class="label">Superseded</span><br><span class="value" style="color:#fbbf24">{len(report.superseded)}</span></span>
  <span class="stat"><span class="label">Retracted</span><br><span class="value" style="color:#f87171">{len(report.retracted)}</span></span>
  <span class="stat"><span class="label">Missing</span><br><span class="value" style="color:#f87171">{len(report.missing_from_graph)}</span></span>
</div>

<div class="status {status_class}">{status_text}</div>
{failures_html}

<h2>Fact Legend</h2>
<table class="legend">
  <thead><tr><th>Citation Tag</th><th>Claim</th><th>Value</th><th>Status</th></tr></thead>
  <tbody>{legend_rows}</tbody>
</table>

<div class="tabs">
  <div class="tab active" onclick="switchTab('cited')">With Citations</div>
  <div class="tab" onclick="switchTab('clean')">Clean</div>
</div>

<div id="tab-cited" class="tab-content active">
  <div class="content">{highlighted}</div>
</div>

<div id="tab-clean" class="tab-content">
  <div class="content">{clean_escaped}</div>
</div>

<script>
function switchTab(name) {{
  document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  event.target.classList.add('active');
}}
</script>

</body>
</html>"""
