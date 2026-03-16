"""canon/visualize.py — Generate a self-contained interactive HTML graph visualization."""
from __future__ import annotations

import json
from pathlib import Path

from canon.graph import KnowledgeGraph

# ---------------------------------------------------------------------------
# Color scheme: entity type → (background, text)
# ---------------------------------------------------------------------------

_TYPE_COLORS: dict[str, tuple[str, str]] = {
    "Concept":           ("#1e3a5f", "#60a5fa"),
    "Capability":        ("#3b1f1f", "#f87171"),
    "Task":              ("#1f3b2d", "#4ade80"),
    "Audience":          ("#3b3b1f", "#facc15"),
    "Evidence":          ("#2d1f3b", "#c084fc"),
    "Asset":             ("#1f3b3b", "#22d3ee"),
    "Fact":              ("#1f2b3b", "#93c5fd"),
    "Constraint":        ("#3b2d1f", "#fb923c"),
    "LearningObjective": ("#2d3b1f", "#a3e635"),
}

_DEFAULT_COLORS = ("#1e1e1e", "#d1d5db")

# Layer assignment: lower number = higher on screen (top)
_TYPE_LAYER: dict[str, int] = {
    "Evidence":          1,
    "Fact":              2,
    "Concept":           3,
    "Capability":        4,
    "Task":              5,
    "LearningObjective": 5,
    "Audience":          6,
    "Asset":             7,
    "Constraint":        7,
}
_DEFAULT_LAYER = 8


def _entity_fields(entity) -> dict:
    """Return all fields of an entity as a plain dict (JSON-safe)."""
    data = {}
    for field_name in type(entity).model_fields:
        value = getattr(entity, field_name, None)
        if value is None:
            continue
        if hasattr(value, "isoformat"):
            data[field_name] = value.isoformat()
        elif hasattr(value, "model_dump"):
            data[field_name] = value.model_dump()
        else:
            data[field_name] = value
    return data


def generate_graph_html(graph: KnowledgeGraph, output_path: Path) -> Path:
    """Generate an interactive HTML visualization of the knowledge graph.

    Parameters
    ----------
    graph:
        A loaded :class:`~canon.graph.KnowledgeGraph` instance.
    output_path:
        Destination for the ``.html`` file.  Parent directories are created
        automatically.

    Returns
    -------
    Path
        The resolved path to the written file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Build node list
    # ------------------------------------------------------------------ #
    nodes: list[dict] = []
    node_index: dict[str, int] = {}

    for idx, (entity_id, entity) in enumerate(graph._entities.items()):
        type_name = type(entity).__name__
        bg, fg = _TYPE_COLORS.get(type_name, _DEFAULT_COLORS)
        label = getattr(entity, "name", entity_id)
        layer = _TYPE_LAYER.get(type_name, _DEFAULT_LAYER)

        nodes.append({
            "id": entity_id,
            "label": label,
            "type": type_name,
            "layer": layer,
            "bg": bg,
            "fg": fg,
            "fields": _entity_fields(entity),
        })
        node_index[entity_id] = idx

    # ------------------------------------------------------------------ #
    # Build edge list
    # ------------------------------------------------------------------ #
    edges: list[dict] = []
    seen_edges: set[tuple[str, str, str]] = set()

    for source_id, edge_list in graph._forward.items():
        for edge in edge_list:
            key = (edge.source_id, edge.relation, edge.target_id)
            if key in seen_edges:
                continue
            if edge.source_id not in node_index or edge.target_id not in node_index:
                continue
            seen_edges.add(key)
            edges.append({
                "source": node_index[edge.source_id],
                "target": node_index[edge.target_id],
                "relation": edge.relation,
            })

    # ------------------------------------------------------------------ #
    # Embed data + write HTML
    # ------------------------------------------------------------------ #
    nodes_json = json.dumps(nodes, default=str)
    edges_json = json.dumps(edges)

    # Build summary stats for the sidebar
    type_counts = {}
    concept_names_list = []
    for n in nodes:
        type_counts[n["type"]] = type_counts.get(n["type"], 0) + 1
        if n["type"] == "Concept":
            concept_names_list.append(n["label"])

    total_entities = len(nodes)
    evidence_count = type_counts.get("Evidence", 0)
    fact_count = type_counts.get("Fact", 0)
    asset_count = type_counts.get("Asset", 0)

    if len(concept_names_list) > 3:
        concept_names = ", ".join(concept_names_list[:3]) + f", and {len(concept_names_list) - 3} more"
    else:
        concept_names = ", ".join(concept_names_list) if concept_names_list else "none"

    html = _build_html(
        nodes_json, edges_json,
        total_entities=total_entities,
        concept_names=concept_names,
        evidence_count=evidence_count,
        fact_count=fact_count,
        asset_count=asset_count,
    )
    output_path.write_text(html, encoding="utf-8")
    return output_path.resolve()


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _build_html(
    nodes_json: str,
    edges_json: str,
    total_entities: int = 0,
    concept_names: str = "",
    evidence_count: int = 0,
    fact_count: int = 0,
    asset_count: int = 0,
) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Canon Knowledge Graph</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    background: #0a0a0a;
    color: #d1d5db;
    font-family: 'Segoe UI', system-ui, sans-serif;
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }}

  /* ---- type-group toolbar ---- */
  #type-toolbar {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 8px 12px;
    background: #111;
    border-bottom: 1px solid #1e1e1e;
    z-index: 20;
    flex-shrink: 0;
  }}

  #type-toolbar button {{
    border-radius: 6px;
    padding: 4px 10px;
    cursor: pointer;
    font-size: 11px;
    font-weight: 600;
    border: 1px solid transparent;
    transition: opacity 0.15s, filter 0.15s;
  }}

  #type-toolbar button.collapsed {{
    filter: brightness(0.45);
    border-style: dashed;
  }}

  /* ---- main layout ---- */
  #main {{
    display: flex;
    flex: 1;
    overflow: hidden;
  }}

  #canvas-wrap {{
    flex: 1;
    position: relative;
    overflow: hidden;
  }}

  canvas {{
    display: block;
    cursor: default;
  }}

  /* ---- overlay toolbar ---- */
  #overlay-toolbar {{
    position: absolute;
    top: 10px;
    left: 10px;
    display: flex;
    gap: 6px;
    z-index: 10;
  }}

  #overlay-toolbar button {{
    background: #181818;
    border: 1px solid #2a2a2a;
    color: #d1d5db;
    border-radius: 6px;
    padding: 5px 11px;
    cursor: pointer;
    font-size: 11px;
  }}
  #overlay-toolbar button:hover {{ background: #252525; }}

  /* ---- hint ---- */
  #hint {{
    position: absolute;
    bottom: 10px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0,0,0,0.65);
    border: 1px solid #222;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 11px;
    color: #6b7280;
    pointer-events: none;
    white-space: nowrap;
  }}

  /* ---- left sidebar ---- */
  #left-sidebar {{
    width: 280px;
    min-width: 280px;
    background: #111;
    border-right: 1px solid #1e1e1e;
    padding: 20px 16px;
    overflow-y: auto;
    flex-shrink: 0;
    font-size: 13px;
    line-height: 1.7;
  }}

  #left-sidebar h2 {{
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 12px;
  }}

  #left-sidebar p {{
    color: #9ca3af;
    margin-bottom: 10px;
  }}

  #left-sidebar .legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
    font-size: 12px;
  }}

  #left-sidebar .legend-swatch {{
    width: 14px;
    height: 14px;
    border-radius: 3px;
    flex-shrink: 0;
  }}

  #left-sidebar .legend-label {{
    color: #d1d5db;
  }}

  #left-sidebar .legend-desc {{
    color: #6b7280;
    font-size: 11px;
    margin-left: 22px;
    margin-bottom: 8px;
  }}

  #left-sidebar .flow-section {{
    margin-top: 16px;
    padding-top: 14px;
    border-top: 1px solid #1e1e1e;
  }}

  #left-sidebar .flow-arrow {{
    color: #4b5563;
    text-align: center;
    font-size: 11px;
    margin: 2px 0;
  }}

  #left-sidebar .flow-step {{
    text-align: center;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    margin: 2px 0;
  }}

  /* ---- detail panel ---- */
  #panel {{
    width: 300px;
    min-width: 260px;
    background: #111;
    border-left: 1px solid #1e1e1e;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: width 0.2s, min-width 0.2s;
    flex-shrink: 0;
  }}

  #panel.hidden {{ width: 0; min-width: 0; border-left: none; }}

  #panel-inner {{
    padding: 14px;
    overflow-y: auto;
    flex: 1;
    font-size: 12px;
    line-height: 1.6;
  }}

  #panel h2 {{
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 3px;
    word-break: break-word;
  }}

  #panel .type-badge {{
    display: inline-block;
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 999px;
    margin-bottom: 10px;
    font-weight: 700;
    letter-spacing: 0.04em;
  }}

  #panel .section-title {{
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6b7280;
    margin: 12px 0 5px;
    font-weight: 600;
  }}

  #panel .field-row {{
    display: flex;
    gap: 6px;
    margin-bottom: 3px;
    flex-wrap: wrap;
  }}

  #panel .field-key {{
    color: #6b7280;
    flex-shrink: 0;
    min-width: 72px;
  }}

  #panel .field-val {{
    color: #e5e7eb;
    word-break: break-word;
  }}

  #panel .conn-link {{
    display: block;
    padding: 3px 6px;
    margin-bottom: 3px;
    border-radius: 4px;
    cursor: pointer;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    transition: background 0.15s;
    word-break: break-word;
    font-size: 11px;
  }}
  #panel .conn-link:hover {{ background: #222; }}
  #panel .conn-link .rel-label {{
    font-size: 10px;
    color: #6b7280;
    margin-right: 4px;
  }}

  #panel-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 6px 10px 0;
    flex-shrink: 0;
  }}

  #close-panel {{
    background: none;
    border: none;
    color: #6b7280;
    cursor: pointer;
    font-size: 16px;
    padding: 4px 6px;
    line-height: 1;
    border-radius: 4px;
  }}
  #close-panel:hover {{ color: #d1d5db; background: #1e1e1e; }}
</style>
</head>
<body>

<!-- Type-group toggles toolbar -->
<div id="type-toolbar"></div>

<div id="main">
  <div id="left-sidebar">
    <h2>Canon Knowledge Graph</h2>
    <p>This graph contains <strong style="color:#fff;">{total_entities} entities</strong> representing training knowledge for the <strong style="color:#fff;">Claude/AI</strong> domain.</p>
    <p style="font-size:12px;">It covers {concept_names}, backed by {evidence_count} evidence source{"s" if evidence_count != 1 else ""} from Anthropic documentation. {fact_count} versioned facts track specific claims that can become stale. {asset_count} training asset{"s" if asset_count != 1 else ""} {"have" if asset_count != 1 else "has"} been generated from these knowledge objects.</p>

    <div class="flow-section">
      <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;font-weight:600;">Knowledge Flow</div>
      <div class="flow-step" style="background:#2d1f3b;color:#c084fc;">Evidence</div>
      <div class="flow-arrow">sources back</div>
      <div class="flow-step" style="background:#1f2b3b;color:#93c5fd;">Facts</div>
      <div class="flow-arrow">belong to</div>
      <div class="flow-step" style="background:#1e3a5f;color:#60a5fa;">Concepts</div>
      <div class="flow-arrow">support</div>
      <div class="flow-step" style="background:#3b1f1f;color:#f87171;">Capabilities</div>
      <div class="flow-arrow">enable</div>
      <div class="flow-step" style="background:#1f3b2d;color:#4ade80;">Tasks</div>
      <div class="flow-arrow">targeted at</div>
      <div class="flow-step" style="background:#3b3b1f;color:#facc15;">Audiences</div>
      <div class="flow-arrow">taught via</div>
      <div class="flow-step" style="background:#1f3b3b;color:#22d3ee;">Assets</div>
    </div>

    <div class="flow-section">
      <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;font-weight:600;">Entity Legend</div>

      <div class="legend-item"><div class="legend-swatch" style="background:#2d1f3b;"></div><span class="legend-label" style="color:#c084fc;">Evidence</span></div>
      <div class="legend-desc">Source documents backing factual claims</div>

      <div class="legend-item"><div class="legend-swatch" style="background:#1f2b3b;border-radius:1px;transform:rotate(45deg);width:12px;height:12px;"></div><span class="legend-label" style="color:#93c5fd;">Facts</span></div>
      <div class="legend-desc">Versioned claims that can become stale</div>

      <div class="legend-item"><div class="legend-swatch" style="background:#1e3a5f;border-radius:4px;"></div><span class="legend-label" style="color:#60a5fa;">Concepts</span></div>
      <div class="legend-desc">Ideas a learner must understand</div>

      <div class="legend-item"><div class="legend-swatch" style="background:#3b1f1f;border-radius:6px;"></div><span class="legend-label" style="color:#f87171;">Capabilities</span></div>
      <div class="legend-desc">What the system can do</div>

      <div class="legend-item"><div class="legend-swatch" style="background:#1f3b2d;"></div><span class="legend-label" style="color:#4ade80;">Tasks</span></div>
      <div class="legend-desc">Actions users perform</div>

      <div class="legend-item"><div class="legend-swatch" style="background:#3b3b1f;border-radius:50%;"></div><span class="legend-label" style="color:#facc15;">Audiences</span></div>
      <div class="legend-desc">Who the training targets</div>

      <div class="legend-item"><div class="legend-swatch" style="background:#1f3b3b;border:2px solid #22d3ee;width:12px;height:12px;"></div><span class="legend-label" style="color:#22d3ee;">Assets</span></div>
      <div class="legend-desc">Generated training materials</div>

      <div class="legend-item"><div class="legend-swatch" style="background:#3b2d1f;"></div><span class="legend-label" style="color:#fb923c;">Constraints</span></div>
      <div class="legend-desc">Rules training must respect</div>

      <div class="legend-item"><div class="legend-swatch" style="background:#2d3b1f;border:1px dashed #a3e635;width:12px;height:12px;"></div><span class="legend-label" style="color:#a3e635;">Learning Objectives</span></div>
      <div class="legend-desc">Measurable learner outcomes</div>
    </div>

    <div class="flow-section">
      <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;font-weight:600;">How to Use</div>
      <p style="font-size:11px;"><strong style="color:#d1d5db;">Click</strong> a node to highlight its trail and see details</p>
      <p style="font-size:11px;"><strong style="color:#d1d5db;">Scroll</strong> to zoom in and out</p>
      <p style="font-size:11px;"><strong style="color:#d1d5db;">Drag</strong> the canvas to pan</p>
      <p style="font-size:11px;"><strong style="color:#d1d5db;">Drag</strong> a node to reposition it</p>
      <p style="font-size:11px;"><strong style="color:#d1d5db;">Toggle</strong> entity types in the toolbar above</p>
    </div>
  </div>

  <div id="canvas-wrap">
    <canvas id="graph-canvas"></canvas>

    <div id="overlay-toolbar">
      <button id="btn-fit">Fit View</button>
      <button id="btn-reset-hl">Clear Selection</button>
      <button id="btn-reset-all">Reset View</button>
    </div>

    <div id="hint">Click node to explore trail · Scroll to zoom · Drag to pan · Double-click canvas to fit</div>
  </div>

  <div id="panel" class="hidden">
    <div id="panel-header">
      <span style="font-size:11px;color:#6b7280">Details</span>
      <button id="close-panel" title="Close">✕</button>
    </div>
    <div id="panel-inner"></div>
  </div>
</div>

<script>
// ============================================================
// DATA
// ============================================================
const RAW_NODES = {nodes_json};
const RAW_EDGES = {edges_json};

// ============================================================
// LAYER CONFIG
// ============================================================
const LAYER_ORDER = [
  "Evidence", "Fact", "Concept", "Capability",
  "Task", "LearningObjective", "Audience", "Asset", "Constraint"
];

// ============================================================
// CONSTANTS
// ============================================================
const NODE_H       = 40;
const NODE_MIN_W   = 120;
const NODE_MAX_W   = 250;
const FONT_SIZE    = 12;
const EDGE_FONT    = 10;
const LAYER_GAP    = 120;
const H_PADDING    = 40;   // horizontal padding between nodes in a row

// ============================================================
// CANVAS SETUP
// ============================================================
const canvas  = document.getElementById('graph-canvas');
const ctx     = canvas.getContext('2d');
const wrap    = document.getElementById('canvas-wrap');

let W = 0, H = 0;

function resize() {{
  W = wrap.clientWidth;
  H = wrap.clientHeight;
  canvas.width  = W * devicePixelRatio;
  canvas.height = H * devicePixelRatio;
  canvas.style.width  = W + 'px';
  canvas.style.height = H + 'px';
  ctx.scale(devicePixelRatio, devicePixelRatio);
  draw();
}}

window.addEventListener('resize', () => {{
  // Re-scale without recomputing layout
  const dpr = devicePixelRatio;
  W = wrap.clientWidth;
  H = wrap.clientHeight;
  canvas.width  = W * dpr;
  canvas.height = H * dpr;
  canvas.style.width  = W + 'px';
  canvas.style.height = H + 'px';
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  draw();
}});

// ============================================================
// STATE
// ============================================================
let px = [], py = [], pw = [];   // positions & widths (world-space)
let selectedIdx  = -1;           // clicked node
let trailNodes   = new Set();    // hop-1 nodes
let trailEdges   = new Set();    // hop-1 edges
let hop2Nodes    = new Set();    // hop-2 nodes (dimmer than hop-1)
let hop2Edges    = new Set();    // hop-2 edges

// Collapsed type groups
const collapsed = new Set();     // type names that are collapsed

// Viewport
let camX = 0, camY = 0, camZ = 1.0;

// Drag / pan
let dragging      = false;
let dragNode      = -1;
let dragStartX    = 0, dragStartY = 0;
let panStartX     = 0, panStartY = 0;
let panStartCamX  = 0, panStartCamY = 0;

// Nodes & edges after applying collapsed state
let NODES = [];
let EDGES = [];

// ============================================================
// MEASURE NODE WIDTH
// ============================================================
function measureNodeWidth(label) {{
  ctx.font = `${{FONT_SIZE}}px system-ui`;
  const tw = ctx.measureText(label).width;
  return Math.min(NODE_MAX_W, Math.max(NODE_MIN_W, tw + 28));
}}

// ============================================================
// BUILD EFFECTIVE NODES/EDGES (honouring collapsed groups)
// ============================================================
function buildEffective() {{
  NODES = [];
  EDGES = [];

  // Map from RAW_NODES index → NODES index
  const rawToEff = new Map();
  // Map from collapsed type name → NODES index of summary node
  const collapsedNodeIdx = new Map();

  for (let i = 0; i < RAW_NODES.length; i++) {{
    const n = RAW_NODES[i];
    if (collapsed.has(n.type)) {{
      if (!collapsedNodeIdx.has(n.type)) {{
        const count = RAW_NODES.filter(x => x.type === n.type).length;
        const label = `${{n.type}} (${{count}})`;
        const idx = NODES.length;
        NODES.push({{
          id:     '__collapsed__' + n.type,
          label,
          type:   n.type,
          layer:  n.layer,
          bg:     n.bg,
          fg:     n.fg,
          fields: {{}},
          isCollapsed: true,
        }});
        collapsedNodeIdx.set(n.type, idx);
      }}
      rawToEff.set(i, collapsedNodeIdx.get(n.type));
    }} else {{
      rawToEff.set(i, NODES.length);
      NODES.push({{ ...n, isCollapsed: false }});
    }}
  }}

  const seenEdge = new Set();
  for (const e of RAW_EDGES) {{
    const s = rawToEff.get(e.source);
    const t = rawToEff.get(e.target);
    if (s === undefined || t === undefined) continue;
    if (s === t) continue; // self-loop after collapse
    const key = `${{s}}/${{t}}/${{e.relation}}`;
    if (seenEdge.has(key)) continue;
    seenEdge.add(key);
    EDGES.push({{ source: s, target: t, relation: e.relation }});
  }}
}}

// ============================================================
// HIERARCHICAL LAYOUT
// ============================================================
function computeLayout() {{
  buildEffective();

  // Measure widths
  ctx.font = `${{FONT_SIZE}}px system-ui`;
  pw = NODES.map(n => measureNodeWidth(n.label));

  // Group by layer
  const byLayer = new Map();
  for (let i = 0; i < NODES.length; i++) {{
    const layer = NODES[i].layer ?? 9;
    if (!byLayer.has(layer)) byLayer.set(layer, []);
    byLayer.get(layer).push(i);
  }}

  const sortedLayers = [...byLayer.keys()].sort((a, b) => a - b);

  // Assign y positions
  const layerY = new Map();
  let y = 60;
  for (const layer of sortedLayers) {{
    layerY.set(layer, y);
    y += NODE_H + LAYER_GAP;
  }}

  // Assign x positions: center each layer
  px = new Array(NODES.length).fill(0);
  py = new Array(NODES.length).fill(0);

  for (const layer of sortedLayers) {{
    const indices = byLayer.get(layer);
    const thisY   = layerY.get(layer);

    // Total width of all nodes + gaps
    const totalW = indices.reduce((sum, i) => sum + pw[i], 0)
                   + H_PADDING * (indices.length - 1);
    let x = -totalW / 2;

    for (const i of indices) {{
      px[i] = x + pw[i] / 2;
      py[i] = thisY;
      x += pw[i] + H_PADDING;
    }}
  }}
}}

// ============================================================
// FIT VIEW
// ============================================================
function fitView() {{
  if (NODES.length === 0) {{ camX = 0; camY = 0; camZ = 1; return; }}

  let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
  for (let i = 0; i < NODES.length; i++) {{
    const hw = pw[i] / 2;
    const hh = NODE_H / 2;
    minX = Math.min(minX, px[i] - hw);
    maxX = Math.max(maxX, px[i] + hw);
    minY = Math.min(minY, py[i] - hh);
    maxY = Math.max(maxY, py[i] + hh);
  }}

  const padX = 60, padY = 60;
  const graphW = maxX - minX + padX * 2;
  const graphH = maxY - minY + padY * 2;
  camZ = Math.min(4, Math.max(0.1, Math.min(W / graphW, H / graphH)));
  camX = (minX + maxX) / 2;
  camY = (minY + maxY) / 2;
}}

// ============================================================
// TRAIL BFS
// ============================================================
function computeTrail(idx) {{
  trailNodes = new Set([idx]);
  trailEdges = new Set();
  hop2Nodes  = new Set();
  hop2Edges  = new Set();

  // Hop 1: direct connections
  for (let ei = 0; ei < EDGES.length; ei++) {{
    const e = EDGES[ei];
    if (e.source === idx && !trailNodes.has(e.target)) {{
      trailNodes.add(e.target);
      trailEdges.add(ei);
    }}
    if (e.target === idx && !trailNodes.has(e.source)) {{
      trailNodes.add(e.source);
      trailEdges.add(ei);
    }}
  }}

  // Hop 2: connections of hop-1 nodes
  for (const h1 of trailNodes) {{
    if (h1 === idx) continue;
    for (let ei = 0; ei < EDGES.length; ei++) {{
      const e = EDGES[ei];
      if (e.source === h1 && !trailNodes.has(e.target) && !hop2Nodes.has(e.target)) {{
        hop2Nodes.add(e.target);
        hop2Edges.add(ei);
      }}
      if (e.target === h1 && !trailNodes.has(e.source) && !hop2Nodes.has(e.source)) {{
        hop2Nodes.add(e.source);
        hop2Edges.add(ei);
      }}
    }}
  }}

  // Mark edges between trail nodes
  for (let ei = 0; ei < EDGES.length; ei++) {{
    if (trailNodes.has(EDGES[ei].source) && trailNodes.has(EDGES[ei].target)) {{
      trailEdges.add(ei);
    }}
  }}
}}

function clearTrail() {{
  selectedIdx = -1;
  trailNodes  = new Set();
  trailEdges  = new Set();
  hop2Nodes   = new Set();
  hop2Edges   = new Set();
}}

// ============================================================
// COORDINATE HELPERS
// ============================================================
function worldToScreen(wx, wy) {{
  return [
    W / 2 + (wx - camX) * camZ,
    H / 2 + (wy - camY) * camZ,
  ];
}}

function screenToWorld(sx, sy) {{
  return [
    (sx - W / 2) / camZ + camX,
    (sy - H / 2) / camZ + camY,
  ];
}}

function nodeAt(sx, sy) {{
  const [wx, wy] = screenToWorld(sx, sy);
  for (let i = NODES.length - 1; i >= 0; i--) {{
    const hw = pw[i] / 2, hh = NODE_H / 2;
    if (wx >= px[i] - hw && wx <= px[i] + hw &&
        wy >= py[i] - hh && wy <= py[i] + hh) {{
      return i;
    }}
  }}
  return -1;
}}

// ============================================================
// SHAPE DRAWING HELPERS
// ============================================================
function pathRoundRect(x, y, w, h, r) {{
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
}}

function pathHexagon(cx, cy, w, h) {{
  // Flat-top hexagon fitting within w x h
  const hw = w / 2, hh = h / 2;
  const inset = hh * 0.5;
  ctx.beginPath();
  ctx.moveTo(cx - hw + inset, cy - hh);
  ctx.lineTo(cx + hw - inset, cy - hh);
  ctx.lineTo(cx + hw, cy);
  ctx.lineTo(cx + hw - inset, cy + hh);
  ctx.lineTo(cx - hw + inset, cy + hh);
  ctx.lineTo(cx - hw, cy);
  ctx.closePath();
}}

function pathOctagon(cx, cy, w, h) {{
  const hw = w / 2, hh = h / 2;
  const cut = Math.min(hw, hh) * 0.28;
  ctx.beginPath();
  ctx.moveTo(cx - hw + cut, cy - hh);
  ctx.lineTo(cx + hw - cut, cy - hh);
  ctx.lineTo(cx + hw, cy - hh + cut);
  ctx.lineTo(cx + hw, cy + hh - cut);
  ctx.lineTo(cx + hw - cut, cy + hh);
  ctx.lineTo(cx - hw + cut, cy + hh);
  ctx.lineTo(cx - hw, cy + hh - cut);
  ctx.lineTo(cx - hw, cy - hh + cut);
  ctx.closePath();
}}

function pathEllipse(cx, cy, w, h) {{
  ctx.beginPath();
  ctx.ellipse(cx, cy, w / 2, h / 2, 0, 0, Math.PI * 2);
  ctx.closePath();
}}

function pathDocumentFold(x, y, w, h) {{
  // Rectangle with top-right corner folded
  const fold = Math.min(w, h) * 0.22;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + w - fold, y);
  ctx.lineTo(x + w, y + fold);
  ctx.lineTo(x + w, y + h);
  ctx.lineTo(x, y + h);
  ctx.closePath();
}}

function drawNodeShape(node, x, y, w, h, cx, cy) {{
  const r4 = 4, r8 = 8, r12 = 12;
  switch (node.type) {{
    case 'Concept':
      pathRoundRect(x, y, w, h, r8);
      break;
    case 'Fact':
      pathHexagon(cx, cy, w, h);
      break;
    case 'Capability':
      pathRoundRect(x, y, w, h, r12);
      break;
    case 'Task':
      pathRoundRect(x, y, w, h, r4);
      break;
    case 'Evidence':
      pathDocumentFold(x, y, w, h);
      break;
    case 'Audience':
      pathEllipse(cx, cy, w, h);
      break;
    case 'Constraint':
      pathOctagon(cx, cy, w, h);
      break;
    case 'LearningObjective':
      pathRoundRect(x, y, w, h, r8);
      break;
    case 'Asset':
      pathRoundRect(x, y, w, h, r4);
      break;
    default:
      pathRoundRect(x, y, w, h, r4);
  }}
}}

// ============================================================
// DRAW EXTRAS (fold line for Evidence, double border for Asset)
// ============================================================
function drawNodeExtras(node, x, y, w, h, cx, cy, color) {{
  if (node.type === 'Evidence') {{
    const fold = Math.min(w, h) * 0.22;
    ctx.beginPath();
    ctx.moveTo(x + w - fold, y);
    ctx.lineTo(x + w - fold, y + fold);
    ctx.lineTo(x + w, y + fold);
    ctx.strokeStyle = color + '88';
    ctx.lineWidth = 1;
    ctx.stroke();
  }}
  if (node.type === 'Asset') {{
    // Double border: inner rect inset by 3px
    const inset = 3;
    pathRoundRect(x + inset, y + inset, w - inset * 2, h - inset * 2, 2);
    ctx.strokeStyle = color + '55';
    ctx.lineWidth = 1;
    ctx.stroke();
  }}
  if (node.type === 'LearningObjective' && !node.isCollapsed) {{
    // Dashed border overlay
    pathRoundRect(x, y, w, h, 8);
    ctx.setLineDash([4, 3]);
    ctx.strokeStyle = color + 'cc';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash([]);
  }}
}}

// ============================================================
// EDGE ARROW
// ============================================================
function drawArrow(x1, y1, x2, y2, color, lineWidth) {{
  ctx.strokeStyle = color;
  ctx.lineWidth   = lineWidth;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();

  const angle  = Math.atan2(y2 - y1, x2 - x1);
  const aLen   = 9;
  const tipX   = x2;
  const tipY   = y2;
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(tipX, tipY);
  ctx.lineTo(tipX - Math.cos(angle - 0.38) * aLen, tipY - Math.sin(angle - 0.38) * aLen);
  ctx.lineTo(tipX - Math.cos(angle + 0.38) * aLen, tipY - Math.sin(angle + 0.38) * aLen);
  ctx.closePath();
  ctx.fill();
}}

// Get the intersection point of a line from (cx,cy) toward (tx,ty) with the node boundary
function edgeAnchor(ni, tx, ty) {{
  const cx = px[ni], cy = py[ni];
  const hw = pw[ni] / 2 + 3, hh = NODE_H / 2 + 3;
  const dx = tx - cx, dy = ty - cy;
  const dist = Math.sqrt(dx * dx + dy * dy);
  if (dist < 1) return [cx, cy];
  // Clamp to bounding box
  const sx = dx / dist, sy = dy / dist;
  let t = Infinity;
  if (Math.abs(sx) > 0.001) t = Math.min(t, (sx > 0 ? hw : -hw) / sx);
  if (Math.abs(sy) > 0.001) t = Math.min(t, (sy > 0 ? hh : -hh) / sy);
  return [cx + sx * t, cy + sy * t];
}}

// ============================================================
// MAIN DRAW
// ============================================================
function draw() {{
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#0a0a0a';
  ctx.fillRect(0, 0, W, H);

  if (NODES.length === 0) {{
    ctx.fillStyle = '#6b7280';
    ctx.font      = '16px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('No entities loaded', W / 2, H / 2);
    return;
  }}

  const hasTrail = trailNodes.size > 0;

  ctx.save();
  ctx.translate(W / 2 - camX * camZ, H / 2 - camY * camZ);
  ctx.scale(camZ, camZ);

  // ---- Draw edges ----
  for (let ei = 0; ei < EDGES.length; ei++) {{
    const e  = EDGES[ei];
    const si = e.source, ti = e.target;
    const onTrail = trailEdges.has(ei);
    const onHop2  = hop2Edges.has(ei);

    let alpha, edgeColor, lw;
    if (!hasTrail) {{
      alpha = 0.45; edgeColor = '#475569'; lw = 1.2;
    }} else if (onTrail) {{
      alpha = 0.9; edgeColor = '#94a3b8'; lw = 2.0;
    }} else if (onHop2) {{
      alpha = 0.35; edgeColor = '#475569'; lw = 1.0;
    }} else {{
      alpha = 0.1; edgeColor = '#1e293b'; lw = 0.6;
    }}

    ctx.globalAlpha = alpha;

    const [x1, y1] = edgeAnchor(si, px[ti], py[ti]);
    const [x2, y2] = edgeAnchor(ti, px[si], py[si]);
    drawArrow(x1, y1, x2, y2, edgeColor, lw);

    // Relation label at midpoint
    if (camZ > 0.45) {{
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2 - 5;
      ctx.font      = `${{EDGE_FONT}}px system-ui`;
      ctx.textAlign = 'center';
      ctx.fillStyle = onTrail ? '#94a3b8' : onHop2 ? '#64748b' : '#334155';
      ctx.fillText(e.relation, mx, my);
    }}
  }}

  // ---- Draw nodes ----
  for (let i = 0; i < NODES.length; i++) {{
    const node = NODES[i];
    const w  = pw[i], h = NODE_H;
    const cx = px[i], cy = py[i];
    const x  = cx - w / 2, y = cy - h / 2;

    const isSelected = i === selectedIdx;
    const onTrail    = trailNodes.has(i);
    const onHop2     = hop2Nodes.has(i);

    let alpha;
    if (!hasTrail)       alpha = 1.0;
    else if (isSelected) alpha = 1.0;
    else if (onTrail)    alpha = 0.9;
    else if (onHop2)     alpha = 0.5;
    else                 alpha = 0.18;

    ctx.globalAlpha = alpha;

    // Drop shadow — only on the clicked node, subtle on trail
    if (isSelected) {{
      ctx.shadowColor = node.fg;
      ctx.shadowBlur  = 10;
    }} else if (onTrail && hasTrail) {{
      ctx.shadowColor = node.fg;
      ctx.shadowBlur  = 3;
    }} else {{
      ctx.shadowBlur  = 0;
    }}

    // Fill shape
    drawNodeShape(node, x, y, w, h, cx, cy);
    ctx.fillStyle = node.bg;
    ctx.fill();

    // Border
    const borderColor = isSelected ? node.fg
                      : onTrail && hasTrail ? node.fg + 'bb'
                      : node.fg + '44';
    const borderWidth = isSelected ? 2.5 : (onTrail && hasTrail ? 1.5 : 1);
    ctx.strokeStyle = borderColor;
    ctx.lineWidth   = borderWidth;
    ctx.stroke();

    ctx.shadowBlur = 0;

    // Extras (fold line, double border, dashed)
    drawNodeExtras(node, x, y, w, h, cx, cy, node.fg);

    // Label
    ctx.fillStyle  = node.fg;
    ctx.font       = `${{FONT_SIZE}}px system-ui`;
    ctx.textAlign  = 'center';
    ctx.textBaseline = 'middle';

    let label = node.label;
    const maxW = w - 18;
    if (ctx.measureText(label).width > maxW) {{
      while (label.length > 1 && ctx.measureText(label + '…').width > maxW) {{
        label = label.slice(0, -1);
      }}
      label += '…';
    }}
    ctx.fillText(label, cx, cy);
    ctx.textBaseline = 'alphabetic';
  }}

  ctx.globalAlpha = 1;
  ctx.restore();
}}

// ============================================================
// DETAIL PANEL
// ============================================================
const panel      = document.getElementById('panel');
const panelInner = document.getElementById('panel-inner');
const closeBtn   = document.getElementById('close-panel');

function escHtml(s) {{
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}}

function formatValue(v) {{
  if (Array.isArray(v))                    return v.length ? v.join(', ') : '—';
  if (typeof v === 'object' && v !== null) return JSON.stringify(v);
  if (v === '' || v == null)               return '—';
  return String(v);
}}

function showPanel(idx) {{
  selectedIdx = idx;
  const node  = NODES[idx];

  const fwd = EDGES.filter(e => e.source === idx);
  const rev = EDGES.filter(e => e.target === idx);

  let html = `
    <h2 style="color:${{escHtml(node.fg)}}">${{escHtml(node.label)}}</h2>
    <span class="type-badge"
          style="background:${{escHtml(node.bg)}};color:${{escHtml(node.fg)}};border:1px solid ${{escHtml(node.fg)}}55">
      ${{escHtml(node.type)}}
    </span>
    <div class="field-row">
      <span class="field-key">id</span>
      <span class="field-val">${{escHtml(node.id)}}</span>
    </div>
  `;

  const skipFields = new Set(['id']);
  const fieldEntries = Object.entries(node.fields).filter(([k]) => !skipFields.has(k));
  if (fieldEntries.length) {{
    html += `<div class="section-title">Fields</div>`;
    for (const [k, v] of fieldEntries) {{
      html += `<div class="field-row">
        <span class="field-key">${{escHtml(k)}}</span>
        <span class="field-val">${{escHtml(formatValue(v))}}</span>
      </div>`;
    }}
  }}

  if (fwd.length) {{
    html += `<div class="section-title">Connects to (${{fwd.length}})</div>`;
    for (const e of fwd) {{
      const t = NODES[e.target];
      html += `<div class="conn-link" onclick="jumpTo(${{e.target}})"
                    style="color:${{escHtml(t.fg)}}">
        <span style="color:#6b7280;margin-right:4px;">\u2192</span><span class="rel-label">${{escHtml(e.relation)}}</span>${{escHtml(t.label)}}
      </div>`;
    }}
  }}

  if (rev.length) {{
    html += `<div class="section-title">Referenced by (${{rev.length}})</div>`;
    for (const e of rev) {{
      const s = NODES[e.source];
      html += `<div class="conn-link" onclick="jumpTo(${{e.source}})"
                    style="color:${{escHtml(s.fg)}}">
        <span style="color:#6b7280;margin-right:4px;">\u2190</span><span class="rel-label">${{escHtml(e.relation)}}</span>${{escHtml(s.label)}}
      </div>`;
    }}
  }}

  panelInner.innerHTML = html;
  panel.classList.remove('hidden');
}}

function jumpTo(idx) {{
  selectedIdx = idx;
  computeTrail(idx);
  camX = px[idx];
  camY = py[idx];
  showPanel(idx);
  draw();
}}

closeBtn.addEventListener('click', () => {{
  clearTrail();
  panel.classList.add('hidden');
  draw();
}});

document.getElementById('close-panel').addEventListener('click', () => {{
  clearTrail();
  panel.classList.add('hidden');
  draw();
}});

// ============================================================
// TYPE-GROUP TOOLBAR
// ============================================================
function buildTypeToolbar() {{
  const toolbar = document.getElementById('type-toolbar');
  const types   = [...new Set(RAW_NODES.map(n => n.type))];

  // Sort by layer order
  types.sort((a, b) => {{
    const la = LAYER_ORDER.indexOf(a), lb = LAYER_ORDER.indexOf(b);
    return (la === -1 ? 99 : la) - (lb === -1 ? 99 : lb);
  }});

  toolbar.innerHTML = '';
  for (const type of types) {{
    const count = RAW_NODES.filter(n => n.type === type).length;
    const n     = RAW_NODES.find(n => n.type === type);
    const btn   = document.createElement('button');
    btn.dataset.type = type;
    btn.textContent  = `${{type}} (${{count}})`;
    btn.style.background   = n.bg;
    btn.style.color        = n.fg;
    btn.style.borderColor  = n.fg + '55';
    if (collapsed.has(type)) btn.classList.add('collapsed');

    btn.addEventListener('click', () => {{
      if (collapsed.has(type)) {{
        collapsed.delete(type);
        btn.classList.remove('collapsed');
      }} else {{
        collapsed.add(type);
        btn.classList.add('collapsed');
      }}
      clearTrail();
      panel.classList.add('hidden');
      computeLayout();
      fitView();
      draw();
    }});
    toolbar.appendChild(btn);
  }}
}}

// ============================================================
// MOUSE / TOUCH EVENTS
// ============================================================
let dragOffsetX = 0, dragOffsetY = 0;  // offset from node center to click point
let nodeDragStarted = false;           // true once drag threshold is met

canvas.addEventListener('mousedown', e => {{
  const idx = nodeAt(e.offsetX, e.offsetY);
  if (idx !== -1) {{
    dragging         = true;
    dragNode         = idx;
    dragStartX       = e.offsetX;
    dragStartY       = e.offsetY;
    nodeDragStarted  = false;
    // Store offset from click to node center so node doesn't jump
    const [wx, wy] = screenToWorld(e.offsetX, e.offsetY);
    dragOffsetX = px[idx] - wx;
    dragOffsetY = py[idx] - wy;
  }} else {{
    dragging      = true;
    dragNode      = -1;
    panStartX     = e.offsetX;
    panStartY     = e.offsetY;
    panStartCamX  = camX;
    panStartCamY  = camY;
    canvas.style.cursor = 'grabbing';
  }}
}});

canvas.addEventListener('mousemove', e => {{
  if (!dragging) {{
    canvas.style.cursor = nodeAt(e.offsetX, e.offsetY) !== -1 ? 'pointer' : 'default';
    return;
  }}

  if (dragNode !== -1) {{
    const moved = Math.abs(e.offsetX - dragStartX) + Math.abs(e.offsetY - dragStartY);
    if (!nodeDragStarted && moved < 5) return;  // wait for drag threshold
    nodeDragStarted = true;
    canvas.style.cursor = 'grabbing';
    const [wx, wy] = screenToWorld(e.offsetX, e.offsetY);
    px[dragNode] = wx + dragOffsetX;
    py[dragNode] = wy + dragOffsetY;
    draw();
  }} else {{
    const dx = (e.offsetX - panStartX) / camZ;
    const dy = (e.offsetY - panStartY) / camZ;
    camX = panStartCamX - dx;
    camY = panStartCamY - dy;
    draw();
  }}
}});

canvas.addEventListener('mouseup', e => {{
  if (dragging && dragNode === -1) {{
    const moved = Math.abs(e.offsetX - panStartX) + Math.abs(e.offsetY - panStartY);
    if (moved < 5) {{
      // Click on canvas background
      clearTrail();
      panel.classList.add('hidden');
      draw();
    }}
  }} else if (dragging && dragNode !== -1 && !nodeDragStarted) {{
    // Click on node (no drag occurred)
    computeTrail(dragNode);
    showPanel(dragNode);
    draw();
  }}
  dragging = false;
  dragNode = -1;
  nodeDragStarted = false;
  canvas.style.cursor = 'default';
}});

canvas.addEventListener('mouseleave', () => {{
  dragging = false;
  dragNode = -1;
  canvas.style.cursor = 'default';
}});

canvas.addEventListener('wheel', e => {{
  e.preventDefault();
  const factor = e.deltaY < 0 ? 1.1 : 0.91;
  const [wx, wy] = screenToWorld(e.offsetX, e.offsetY);
  camZ = Math.max(0.08, Math.min(5.0, camZ * factor));
  camX = wx - (e.offsetX - W / 2) / camZ;
  camY = wy - (e.offsetY - H / 2) / camZ;
  draw();
}}, {{ passive: false }});

canvas.addEventListener('dblclick', e => {{
  const idx = nodeAt(e.offsetX, e.offsetY);
  if (idx === -1) {{
    fitView();
    draw();
  }}
}});

// ============================================================
// OVERLAY TOOLBAR BUTTONS
// ============================================================
document.getElementById('btn-fit').addEventListener('click', () => {{
  fitView();
  draw();
}});

document.getElementById('btn-reset-hl').addEventListener('click', () => {{
  clearTrail();
  panel.classList.add('hidden');
  draw();
}});

document.getElementById('btn-reset-all').addEventListener('click', () => {{
  // Clear selection
  clearTrail();
  panel.classList.add('hidden');
  // Expand all collapsed groups
  collapsed.clear();
  buildToolbar();
  rebuildVisibleGraph();
  // Reset layout to default positions
  assignPositions();
  fitView();
  draw();
}});

// ============================================================
// BOOTSTRAP
// ============================================================
// Initial size before first draw so measureNodeWidth has correct font
W = wrap.clientWidth  || window.innerWidth;
H = wrap.clientHeight || window.innerHeight;
canvas.width  = W * devicePixelRatio;
canvas.height = H * devicePixelRatio;
canvas.style.width  = W + 'px';
canvas.style.height = H + 'px';
ctx.scale(devicePixelRatio, devicePixelRatio);

computeLayout();
buildTypeToolbar();
fitView();
draw();

// Proper resize after fonts are loaded
requestAnimationFrame(() => {{
  W = wrap.clientWidth;
  H = wrap.clientHeight;
  canvas.width  = W * devicePixelRatio;
  canvas.height = H * devicePixelRatio;
  canvas.style.width  = W + 'px';
  canvas.style.height = H + 'px';
  ctx.scale(devicePixelRatio, devicePixelRatio);
  computeLayout();
  fitView();
  draw();
}});
</script>
</body>
</html>"""
