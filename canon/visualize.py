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


def _entity_fields(entity) -> dict:
    """Return all fields of an entity as a plain dict (JSON-safe)."""
    data = {}
    for field_name in type(entity).model_fields:
        value = getattr(entity, field_name, None)
        if value is None:
            continue
        # Convert non-serialisable types to strings
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

        nodes.append({
            "id": entity_id,
            "label": label,
            "type": type_name,
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

    html = _build_html(nodes_json, edges_json)
    output_path.write_text(html, encoding="utf-8")
    return output_path.resolve()


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

def _build_html(nodes_json: str, edges_json: str) -> str:
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
    height: 100vh;
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

  /* ---- detail panel ---- */
  #panel {{
    width: 320px;
    min-width: 280px;
    background: #111;
    border-left: 1px solid #222;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: width 0.2s;
  }}

  #panel.hidden {{ width: 0; min-width: 0; border-left: none; }}

  #panel-inner {{
    padding: 16px;
    overflow-y: auto;
    flex: 1;
    font-size: 13px;
    line-height: 1.6;
  }}

  #panel h2 {{
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 2px;
    word-break: break-word;
  }}

  #panel .type-badge {{
    display: inline-block;
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 999px;
    margin-bottom: 12px;
    font-weight: 600;
  }}

  #panel .section-title {{
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6b7280;
    margin: 14px 0 6px;
    font-weight: 600;
  }}

  #panel .field-row {{
    display: flex;
    gap: 6px;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }}

  #panel .field-key {{
    color: #6b7280;
    flex-shrink: 0;
    min-width: 80px;
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
  }}
  #panel .conn-link:hover {{ background: #222; }}
  #panel .conn-link .rel-label {{
    font-size: 10px;
    color: #6b7280;
    margin-right: 4px;
  }}

  #close-panel {{
    background: none;
    border: none;
    color: #6b7280;
    cursor: pointer;
    font-size: 18px;
    padding: 8px 12px;
    align-self: flex-end;
    line-height: 1;
  }}
  #close-panel:hover {{ color: #d1d5db; }}

  /* ---- toolbar ---- */
  #toolbar {{
    position: absolute;
    top: 12px;
    left: 12px;
    display: flex;
    gap: 8px;
    z-index: 10;
  }}

  #toolbar button {{
    background: #181818;
    border: 1px solid #2a2a2a;
    color: #d1d5db;
    border-radius: 6px;
    padding: 5px 12px;
    cursor: pointer;
    font-size: 12px;
  }}
  #toolbar button:hover {{ background: #222; }}

  /* ---- legend ---- */
  #legend {{
    position: absolute;
    bottom: 12px;
    left: 12px;
    background: rgba(17,17,17,0.9);
    border: 1px solid #222;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 11px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}

  #legend .leg-row {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  #legend .leg-dot {{
    width: 12px;
    height: 12px;
    border-radius: 3px;
    flex-shrink: 0;
  }}
</style>
</head>
<body>

<div id="canvas-wrap">
  <canvas id="graph-canvas"></canvas>

  <div id="toolbar">
    <button id="btn-reset">Reset View</button>
    <button id="btn-settle">Re-layout</button>
  </div>

  <div id="legend"></div>
</div>

<div id="panel" class="hidden">
  <button id="close-panel" title="Close">✕</button>
  <div id="panel-inner"></div>
</div>

<script>
// ============================================================
// DATA
// ============================================================
const NODES = {nodes_json};
const EDGES = {edges_json};

// ============================================================
// CONSTANTS
// ============================================================
const NODE_W = 140;
const NODE_H = 36;
const NODE_R = 6;       // corner radius
const FONT_SIZE = 12;
const EDGE_FONT = 10;
const REPEL_DIST = 260;
const REPEL_STRENGTH = 18000;
const ATTRACT_LEN = 180;
const ATTRACT_K = 0.04;
const DAMPING = 0.82;
const SETTLE_AFTER = 220;  // iterations before stopping

// ============================================================
// SETUP
// ============================================================
const canvas = document.getElementById('graph-canvas');
const ctx    = canvas.getContext('2d');
const wrap   = document.getElementById('canvas-wrap');

let W = 0, H = 0;

function resize() {{
  W = wrap.clientWidth;
  H = wrap.clientHeight;
  canvas.width  = W;
  canvas.height = H;
  draw();
}}

window.addEventListener('resize', resize);

// ============================================================
// STATE
// ============================================================
let vx = [], vy = [];         // velocities
let px = [], py = [];         // positions
let selectedIdx = -1;
let highlightIdx = -1;

// Viewport
let camX = 0, camY = 0, camZ = 1.0;

// Drag
let dragging = false;
let dragNode = -1;
let dragStartX = 0, dragStartY = 0;
let dragNodeStartX = 0, dragNodeStartY = 0;
let panStartX = 0, panStartY = 0;
let panStartCamX = 0, panStartCamY = 0;

// Animation
let iteration = 0;
let animating = true;
let rafId = null;

// ============================================================
// INIT POSITIONS — random spread
// ============================================================
function initPositions() {{
  const n = NODES.length;
  const cols = Math.ceil(Math.sqrt(n * 1.6));
  px = []; py = []; vx = []; vy = [];
  for (let i = 0; i < n; i++) {{
    // Spiral init for better convergence
    const angle = i * 2.399963;  // golden angle
    const r = Math.sqrt(i + 1) * 90;
    px.push(r * Math.cos(angle));
    py.push(r * Math.sin(angle));
    vx.push((Math.random() - 0.5) * 2);
    vy.push((Math.random() - 0.5) * 2);
  }}
  // Center camera
  camX = 0; camY = 0; camZ = 1.0;
}}

// ============================================================
// FORCE-DIRECTED LAYOUT
// ============================================================
function stepForces() {{
  const n = NODES.length;
  const fx = new Float64Array(n);
  const fy = new Float64Array(n);

  // Repulsion between all pairs
  for (let i = 0; i < n; i++) {{
    for (let j = i + 1; j < n; j++) {{
      let dx = px[i] - px[j];
      let dy = py[i] - py[j];
      let d2 = dx*dx + dy*dy;
      if (d2 < 1) d2 = 1;
      let d = Math.sqrt(d2);
      if (d < REPEL_DIST) {{
        const f = REPEL_STRENGTH / d2;
        fx[i] += (dx / d) * f;
        fy[i] += (dy / d) * f;
        fx[j] -= (dx / d) * f;
        fy[j] -= (dy / d) * f;
      }}
    }}
  }}

  // Attraction along edges
  for (const e of EDGES) {{
    const i = e.source, j = e.target;
    let dx = px[j] - px[i];
    let dy = py[j] - py[i];
    let d = Math.sqrt(dx*dx + dy*dy);
    if (d < 1) d = 1;
    const stretch = d - ATTRACT_LEN;
    const f = ATTRACT_K * stretch;
    fx[i] += (dx / d) * f;
    fy[i] += (dy / d) * f;
    fx[j] -= (dx / d) * f;
    fy[j] -= (dy / d) * f;
  }}

  // Weak centering gravity
  for (let i = 0; i < n; i++) {{
    fx[i] -= px[i] * 0.003;
    fy[i] -= py[i] * 0.003;
  }}

  // Integrate
  for (let i = 0; i < n; i++) {{
    vx[i] = (vx[i] + fx[i]) * DAMPING;
    vy[i] = (vy[i] + fy[i]) * DAMPING;
    px[i] += vx[i];
    py[i] += vy[i];
  }}

  iteration++;
  if (iteration >= SETTLE_AFTER) animating = false;
}}

// ============================================================
// COORDINATE HELPERS
// ============================================================
function worldToScreen(wx, wy) {{
  return [
    W/2 + (wx - camX) * camZ,
    H/2 + (wy - camY) * camZ
  ];
}}

function screenToWorld(sx, sy) {{
  return [
    (sx - W/2) / camZ + camX,
    (sy - H/2) / camZ + camY
  ];
}}

function nodeAt(sx, sy) {{
  const [wx, wy] = screenToWorld(sx, sy);
  for (let i = NODES.length - 1; i >= 0; i--) {{
    const hw = NODE_W / 2, hh = NODE_H / 2;
    if (wx >= px[i]-hw && wx <= px[i]+hw && wy >= py[i]-hh && wy <= py[i]+hh) return i;
  }}
  return -1;
}}

// ============================================================
// DRAWING
// ============================================================
function roundRect(x, y, w, h, r) {{
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

function draw() {{
  ctx.clearRect(0, 0, W, H);

  // Background
  ctx.fillStyle = '#0a0a0a';
  ctx.fillRect(0, 0, W, H);

  if (NODES.length === 0) {{
    ctx.fillStyle = '#6b7280';
    ctx.font = '16px system-ui';
    ctx.textAlign = 'center';
    ctx.fillText('No entities loaded', W/2, H/2);
    return;
  }}

  // ---- Draw edges ----
  ctx.save();
  ctx.translate(W/2 - camX * camZ, H/2 - camY * camZ);
  ctx.scale(camZ, camZ);

  for (const e of EDGES) {{
    const si = e.source, ti = e.target;
    const x1 = px[si], y1 = py[si];
    const x2 = px[ti], y2 = py[ti];

    // Dim if there's a selection and this edge isn't connected
    const connected = (si === selectedIdx || ti === selectedIdx ||
                       si === highlightIdx || ti === highlightIdx);
    const hasSelection = selectedIdx !== -1 || highlightIdx !== -1;
    ctx.globalAlpha = hasSelection ? (connected ? 0.9 : 0.15) : 0.5;

    ctx.strokeStyle = '#3a3a5c';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();

    // Arrowhead
    const angle = Math.atan2(y2 - y1, x2 - x1);
    const aLen = 8;
    const aWid = 4;
    const ax = x2 - Math.cos(angle) * (NODE_W / 2 + 4);
    const ay = y2 - Math.sin(angle) * (NODE_H / 2 + 4);
    ctx.fillStyle = '#3a3a5c';
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(ax - Math.cos(angle - 0.4) * aLen, ay - Math.sin(angle - 0.4) * aLen);
    ctx.lineTo(ax - Math.cos(angle + 0.4) * aLen, ay - Math.sin(angle + 0.4) * aLen);
    ctx.closePath();
    ctx.fill();

    // Relation label at midpoint
    if (camZ > 0.5) {{
      const mx = (x1 + x2) / 2;
      const my = (y1 + y2) / 2;
      ctx.font = `${{EDGE_FONT}}px system-ui`;
      ctx.textAlign = 'center';
      ctx.fillStyle = '#4b5563';
      ctx.fillText(e.relation, mx, my - 4);
    }}
  }}

  // ---- Draw nodes ----
  for (let i = 0; i < NODES.length; i++) {{
    const node = NODES[i];
    const x = px[i] - NODE_W / 2;
    const y = py[i] - NODE_H / 2;

    const isSelected  = i === selectedIdx;
    const isHighlight = i === highlightIdx;
    const hasSelection = selectedIdx !== -1 || highlightIdx !== -1;
    ctx.globalAlpha = hasSelection ? (isSelected || isHighlight ? 1.0 : 0.35) : 1.0;

    // Shadow / glow for selected
    if (isSelected || isHighlight) {{
      ctx.shadowColor = node.fg;
      ctx.shadowBlur  = 12;
    }} else {{
      ctx.shadowBlur = 0;
    }}

    roundRect(x, y, NODE_W, NODE_H, NODE_R);
    ctx.fillStyle = node.bg;
    ctx.fill();

    // Border
    ctx.strokeStyle = isSelected ? node.fg : (isHighlight ? node.fg + '88' : '#333');
    ctx.lineWidth   = isSelected ? 2 : 1;
    ctx.stroke();

    ctx.shadowBlur = 0;

    // Label
    ctx.fillStyle = node.fg;
    ctx.font = `${{FONT_SIZE}}px system-ui`;
    ctx.textAlign = 'center';

    // Truncate label if needed
    let label = node.label;
    const maxW = NODE_W - 14;
    if (ctx.measureText(label).width > maxW) {{
      while (label.length > 0 && ctx.measureText(label + '…').width > maxW) {{
        label = label.slice(0, -1);
      }}
      label += '…';
    }}

    ctx.fillText(label, px[i], py[i] + FONT_SIZE * 0.38);
  }}

  ctx.globalAlpha = 1;
  ctx.restore();
}}

// ============================================================
// ANIMATION LOOP
// ============================================================
function loop() {{
  if (animating) stepForces();
  draw();
  rafId = requestAnimationFrame(loop);
}}

// ============================================================
// DETAIL PANEL
// ============================================================
const panel     = document.getElementById('panel');
const panelInner = document.getElementById('panel-inner');
const closeBtn  = document.getElementById('close-panel');

function escHtml(s) {{
  return String(s)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}}

function formatValue(v) {{
  if (Array.isArray(v)) return v.length ? v.join(', ') : '—';
  if (typeof v === 'object' && v !== null) return JSON.stringify(v, null, 2);
  if (v === '' || v === null || v === undefined) return '—';
  return String(v);
}}

function showPanel(idx) {{
  const node = NODES[idx];
  selectedIdx = idx;

  // Build forward connections
  const fwd = EDGES.filter(e => e.source === idx);
  const rev = EDGES.filter(e => e.target === idx);

  const [bg, fg] = [node.bg, node.fg];

  // Exclude fields that are essentially ID lists (shown in connections)
  const skipFields = new Set(['id']);

  let html = `
    <h2 style="color:${{escHtml(fg)}}">${{escHtml(node.label)}}</h2>
    <span class="type-badge" style="background:${{escHtml(bg)}};color:${{escHtml(fg)}};border:1px solid ${{escHtml(fg)}}40">
      ${{escHtml(node.type)}}
    </span>
    <div class="field-row"><span class="field-key">id</span><span class="field-val">${{escHtml(node.id)}}</span></div>
  `;

  html += `<div class="section-title">Fields</div>`;
  for (const [k, v] of Object.entries(node.fields)) {{
    if (skipFields.has(k)) continue;
    html += `<div class="field-row">
      <span class="field-key">${{escHtml(k)}}</span>
      <span class="field-val">${{escHtml(formatValue(v))}}</span>
    </div>`;
  }}

  if (fwd.length) {{
    html += `<div class="section-title">Connects to (${{fwd.length}})</div>`;
    for (const e of fwd) {{
      const t = NODES[e.target];
      html += `<div class="conn-link" onclick="jumpTo(${{e.target}})" style="color:${{escHtml(t.fg)}}">
        <span class="rel-label">${{escHtml(e.relation)}}</span>${{escHtml(t.label)}}
        <span style="color:#6b7280;font-size:10px"> [${{escHtml(t.id)}}]</span>
      </div>`;
    }}
  }}

  if (rev.length) {{
    html += `<div class="section-title">Referenced by (${{rev.length}})</div>`;
    for (const e of rev) {{
      const s = NODES[e.source];
      html += `<div class="conn-link" onclick="jumpTo(${{e.source}})" style="color:${{escHtml(s.fg)}}">
        <span class="rel-label">${{escHtml(e.relation)}}</span>${{escHtml(s.label)}}
        <span style="color:#6b7280;font-size:10px"> [${{escHtml(s.id)}}]</span>
      </div>`;
    }}
  }}

  panelInner.innerHTML = html;
  panel.classList.remove('hidden');
  resize();
}}

function jumpTo(idx) {{
  highlightIdx = idx;
  // Pan camera to node
  camX = px[idx];
  camY = py[idx];
  draw();
  setTimeout(() => {{ highlightIdx = -1; draw(); }}, 1500);
}}

closeBtn.addEventListener('click', () => {{
  selectedIdx = -1;
  highlightIdx = -1;
  panel.classList.add('hidden');
  resize();
}});

// ============================================================
// LEGEND
// ============================================================
function buildLegend() {{
  const types = [...new Set(NODES.map(n => n.type))].sort();
  const legend = document.getElementById('legend');
  legend.innerHTML = types.map(t => {{
    const n = NODES.find(n => n.type === t);
    return `<div class="leg-row">
      <div class="leg-dot" style="background:${{n.bg}};border:1px solid ${{n.fg}}60"></div>
      <span style="color:${{n.fg}}">${{t}}</span>
    </div>`;
  }}).join('');
}}

// ============================================================
// MOUSE / TOUCH EVENTS
// ============================================================
let mouseX = 0, mouseY = 0;

canvas.addEventListener('mousedown', e => {{
  const idx = nodeAt(e.offsetX, e.offsetY);
  if (idx !== -1) {{
    dragging = true;
    dragNode = idx;
    dragStartX = e.offsetX;
    dragStartY = e.offsetY;
    dragNodeStartX = px[idx];
    dragNodeStartY = py[idx];
    canvas.style.cursor = 'grabbing';
  }} else {{
    dragging = true;
    dragNode = -1;
    panStartX = e.offsetX;
    panStartY = e.offsetY;
    panStartCamX = camX;
    panStartCamY = camY;
    canvas.style.cursor = 'grabbing';
  }}
}});

canvas.addEventListener('mousemove', e => {{
  mouseX = e.offsetX; mouseY = e.offsetY;

  if (!dragging) {{
    const idx = nodeAt(e.offsetX, e.offsetY);
    canvas.style.cursor = idx !== -1 ? 'pointer' : 'default';
    return;
  }}

  if (dragNode !== -1) {{
    const [wx, wy] = screenToWorld(e.offsetX, e.offsetY);
    px[dragNode] = wx;
    py[dragNode] = wy;
    vx[dragNode] = 0;
    vy[dragNode] = 0;
    if (!animating) draw();
  }} else {{
    const dx = (e.offsetX - panStartX) / camZ;
    const dy = (e.offsetY - panStartY) / camZ;
    camX = panStartCamX - dx;
    camY = panStartCamY - dy;
    if (!animating) draw();
  }}
}});

canvas.addEventListener('mouseup', e => {{
  if (dragging && dragNode === -1) {{
    const moved = Math.abs(e.offsetX - panStartX) + Math.abs(e.offsetY - panStartY);
    if (moved < 5) {{
      // Treat as click on canvas background
      selectedIdx = -1;
      highlightIdx = -1;
      draw();
    }}
  }} else if (dragging && dragNode !== -1) {{
    const moved = Math.abs(e.offsetX - dragStartX) + Math.abs(e.offsetY - dragStartY);
    if (moved < 5) {{
      // Treat as click on node
      showPanel(dragNode);
    }}
  }}
  dragging = false;
  dragNode = -1;
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
  camZ = Math.max(0.15, Math.min(4.0, camZ * factor));
  // Zoom toward cursor
  camX = wx - (e.offsetX - W/2) / camZ;
  camY = wy - (e.offsetY - H/2) / camZ;
  if (!animating) draw();
}}, {{ passive: false }});

// ============================================================
// TOOLBAR BUTTONS
// ============================================================
document.getElementById('btn-reset').addEventListener('click', () => {{
  camX = 0; camY = 0; camZ = 1.0;
  if (!animating) draw();
}});

document.getElementById('btn-settle').addEventListener('click', () => {{
  initPositions();
  iteration = 0;
  animating = true;
  selectedIdx = -1;
  highlightIdx = -1;
  panel.classList.add('hidden');
  resize();
}});

// ============================================================
// BOOTSTRAP
// ============================================================
initPositions();
buildLegend();
resize();
loop();
</script>
</body>
</html>"""
