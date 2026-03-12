<template>
  <div class="gv">

    <!-- File selector if multiple files -->
    <div v-if="fileNames.length > 1" class="file-tabs">
      <button
        v-for="f in fileNames" :key="f"
        class="ftab" :class="{ active: activeFile === f }"
        @click="activeFile = f; nextTick(drawGraph)"
      >{{ f }}</button>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="toolbar-left">
        <span class="graph-meta" v-if="gd">
          <span class="mono accent">{{ gd.nodes.length }}</span> accounts ·
          <span class="mono accent">{{ gd.edges.length }}</span> transactions ·
          <span class="mono accent">{{ gd.fraudRings.length }}</span> rings
        </span>
      </div>
      <div class="toolbar-right">
        <div class="layout-toggle">
          <button v-for="l in LAYOUTS" :key="l.v"
            class="lt-btn" :class="{ active: layout === l.v }"
            @click="layout = l.v; nextTick(drawGraph)">{{ l.label }}</button>
        </div>
        <button class="btn-rerun" @click="nextTick(drawGraph)">↺ Re-run</button>
      </div>
    </div>

    <!-- Legend -->
    <div class="legend">
      <div class="lg-item"><div class="lg-dot ring-dot"/>Ring member (highlighted)</div>
      <div class="lg-item"><div class="lg-dot susp-dot"/>Suspicious account</div>
      <div class="lg-item"><div class="lg-dot norm-dot"/>Other account</div>
      <div class="lg-item"><div class="lg-edge ring-edge"/>Ring edge</div>
      <div class="lg-item"><span class="lg-hint">Click a highlighted ring cluster to see details</span></div>
    </div>

    <!-- Main canvas -->
    <div class="canvas-wrap">
      <svg ref="svgEl" class="main-svg"
        @mousedown="onPanStart"
        @mousemove="onPanMove"
        @mouseup="onPanEnd"
        @mouseleave="onPanEnd"
        @wheel.prevent="onWheel"
        @touchstart.prevent="onTouchStart"
        @touchmove.prevent="onTouchMove"
        @touchend="onTouchEnd"
      />

      <!-- Ring info sidebar (slides in on click) -->
      <Transition name="sidebar">
        <div v-if="selectedRing" class="ring-sidebar">
          <button class="sidebar-close" @click="selectedRing = null">✕</button>
          <div class="sb-header">
            <span class="mono sb-id">{{ selectedRing.ring_id }}</span>
            <span class="badge" :class="riskCat(selectedRing.risk_score)">
              {{ riskCat(selectedRing.risk_score) }}
            </span>
          </div>

          <div class="sb-score-bar">
            <span class="sb-score-label">Risk Score</span>
            <div class="sb-bar-wrap">
              <div class="sb-bar-track">
                <div class="sb-bar-fill" :style="{
                  width: Math.min(selectedRing.risk_score, 100) + '%',
                  background: riskColor(selectedRing.risk_score)
                }"/>
              </div>
              <span class="mono sb-score-val" :style="{ color: riskColor(selectedRing.risk_score) }">
                {{ selectedRing.risk_score.toFixed(1) }}
              </span>
            </div>
          </div>

          <div class="sb-rows">
            <div class="sb-row"><span>Pattern</span><span>{{ fmtPat(selectedRing.pattern_type) }}</span></div>
            <div class="sb-row"><span>Members</span><span>{{ selectedRing.member_accounts.length }}</span></div>
            <template v-if="selectedMeta">
              <div class="sb-row"><span>Avg Score</span><span class="mono">{{ selectedMeta['Avg Member Score'] }}</span></div>
              <div class="sb-row"><span>Max Score</span><span class="mono">{{ selectedMeta['Max Member Score'] }}</span></div>
              <div class="sb-row"><span>Density</span><span class="mono">{{ selectedMeta['Ring Density'] }}</span></div>
              <div class="sb-row"><span>Edges</span><span class="mono">{{ selectedMeta['Internal Edge Count'] }}</span></div>
              <div class="sb-row"><span>Complexity</span><span class="mono">{{ selectedMeta['Structural Complexity'] }}</span></div>
            </template>
          </div>

          <div class="sb-members">
            <p class="sb-members-label">Member Accounts</p>
            <div class="sb-chips">
              <span v-for="m in selectedRing.member_accounts" :key="m" class="sb-chip mono">{{ m }}</span>
            </div>
          </div>
        </div>
      </Transition>

      <!-- Zoom hint -->
      <div class="zoom-hint">Scroll to zoom · Drag to pan · Click a ring to inspect</div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useResultsStore } from '@/stores/results'

const store = useResultsStore()

// ── state ────────────────────────────────────────────────────────────
const svgEl        = ref(null)
const activeFile   = ref('')
const layout       = ref('force')
const selectedRing = ref(null)

// pan / zoom
let transform    = { x: 0, y: 0, k: 1 }
let isPanning    = false
let panStart     = { x: 0, y: 0 }
let touchDist    = 0

const LAYOUTS = [
  { v: 'force', label: 'Force' },
  { v: 'grid',  label: 'Grid'  }
]

const PATTERN_LABELS = {
  cycle_length_3: 'Cycle ×3',
  fan_in:         'Fan-In',
  fan_out:        'Fan-Out',
  layered_shell:  'Layered Shell'
}
function fmtPat(p) { return PATTERN_LABELS[p] || p }

// ── data ─────────────────────────────────────────────────────────────
const fileNames = computed(() => Object.keys(store.graphDataByFile))

const gd = computed(() => {
  if (!activeFile.value) return null
  return store.graphDataByFile[activeFile.value] ?? null
})

const selectedMeta = computed(() => {
  if (!selectedRing.value || !gd.value) return null
  return gd.value.ringMetaMap[selectedRing.value.ring_id] ?? null
})

// ── watchers ─────────────────────────────────────────────────────────
watch(fileNames, (names) => {
  if (names.length && !activeFile.value) {
    activeFile.value = names[0]
    nextTick(drawGraph)
  }
}, { immediate: true })

onMounted(() => {
  if (fileNames.value.length) {
    activeFile.value = fileNames.value[0]
    nextTick(drawGraph)
  }
})

// ── helpers ───────────────────────────────────────────────────────────
function riskColor(score) {
  if (score >= 85) return '#ef4444'
  if (score >= 70) return '#f97316'
  if (score >= 50) return '#eab308'
  return '#22c55e'
}
function riskCat(score) {
  if (score >= 85) return 'Critical'
  if (score >= 70) return 'High'
  if (score >= 50) return 'Medium'
  return 'Low'
}
function ringColor(ring) { return riskColor(ring.risk_score) }

// ── GRAPH DRAW ────────────────────────────────────────────────────────
function drawGraph() {
  const svg  = svgEl.value
  const data = gd.value
  if (!svg || !data || !data.nodes.length) return

  svg.innerHTML = ''
  transform = { x: 0, y: 0, k: 1 }

  const W  = svg.clientWidth  || 900
  const H  = svg.clientHeight || 620
  const ns = 'http://www.w3.org/2000/svg'

  const nodes = data.nodes
  const edges = data.edges
  const n     = nodes.length

  // ── positions ──
  const pos = computePositions(nodes, edges, W, H)
  // id → position
  const posMap = {}
  nodes.forEach((nd, i) => { posMap[nd.id] = pos[i] })

  // ── ring → color ──
  const ringColorMap = {}
  data.fraudRings.forEach(r => { ringColorMap[r.ring_id] = ringColor(r) })

  // ── SVG defs ──
  const defs = document.createElementNS(ns, 'defs')
  defs.innerHTML = `
    <filter id="UG_glow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="5" result="cb"/>
      <feMerge><feMergeNode in="cb"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="UG_glow_sm" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="2.5" result="cb"/>
      <feMerge><feMergeNode in="cb"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <marker id="UG_arr_ring" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="rgba(192,132,252,.7)"/>
    </marker>
    <marker id="UG_arr_norm" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
      <path d="M0,0 L0,6 L8,3 z" fill="rgba(255,255,255,.15)"/>
    </marker>
  `
  svg.appendChild(defs)

  // ── root group (transformed for pan/zoom) ──
  const root = document.createElementNS(ns, 'g')
  root.setAttribute('id', 'ug-root')
  svg.appendChild(root)

  // ── ring convex hull backgrounds ──
  data.fraudRings.forEach(ring => {
    const col     = ringColorMap[ring.ring_id]
    const members = ring.member_accounts.map(String)
    const pts     = members.map(id => posMap[id]).filter(Boolean)
    if (pts.length < 2) return

    // Convex hull (Graham scan)
    const hull = convexHull(pts)
    if (hull.length < 2) return

    const padded = padHull(hull, 28)

    const poly = document.createElementNS(ns, 'polygon')
    poly.setAttribute('points', padded.map(p => `${p.x},${p.y}`).join(' '))
    poly.setAttribute('fill',   hexToRgba(col, 0.10))
    poly.setAttribute('stroke', hexToRgba(col, 0.55))
    poly.setAttribute('stroke-width', '1.8')
    poly.setAttribute('stroke-dasharray', '5,3')
    poly.setAttribute('filter', 'url(#UG_glow_sm)')
    poly.setAttribute('cursor', 'pointer')
    poly.setAttribute('data-ring', ring.ring_id)

    poly.addEventListener('click', (e) => {
      e.stopPropagation()
      selectedRing.value = ring
      highlightRing(ring.ring_id, root)
    })
    root.appendChild(poly)
  })

  // ── edges ──
  const edgeGroup = document.createElementNS(ns, 'g')
  edges.forEach(edge => {
    const sp = posMap[edge.src], dp = posMap[edge.dst]
    if (!sp || !dp) return

    const isRingEdge = !!edge.ring_id
    const col        = isRingEdge ? (ringColorMap[edge.ring_id] || '#a855f7') : null

    const line = document.createElementNS(ns, 'line')
    line.setAttribute('x1', sp.x); line.setAttribute('y1', sp.y)
    line.setAttribute('x2', dp.x); line.setAttribute('y2', dp.y)
    line.setAttribute('stroke',       isRingEdge ? hexToRgba(col, 0.75) : 'rgba(255,255,255,0.08)')
    line.setAttribute('stroke-width', isRingEdge ? '1.8' : '0.8')
    line.setAttribute('marker-end',   isRingEdge ? 'url(#UG_arr_ring)' : 'url(#UG_arr_norm)')
    if (edge.ring_id) line.setAttribute('data-ring-edge', edge.ring_id)
    edgeGroup.appendChild(line)
  })
  root.appendChild(edgeGroup)

  // ── nodes ──
  const nodeGroup = document.createElementNS(ns, 'g')
  nodes.forEach((nd, i) => {
    const p   = pos[i]
    const col = nd.ring
      ? ringColorMap[nd.ring.ring_id]
      : nd.isSuspicious ? '#f97316' : '#64748b'

    const g = document.createElementNS(ns, 'g')
    g.setAttribute('cursor', nd.ring ? 'pointer' : 'default')
    if (nd.ring) g.setAttribute('data-ring-node', nd.ring.ring_id)

    // glow halo for ring members
    if (nd.ring) {
      const halo = document.createElementNS(ns, 'circle')
      halo.setAttribute('cx', p.x); halo.setAttribute('cy', p.y)
      halo.setAttribute('r', 20)
      halo.setAttribute('fill', hexToRgba(col, 0.18))
      g.appendChild(halo)
    }

    const r    = nd.ring ? 14 : nd.isSuspicious ? 10 : 7
    const circ = document.createElementNS(ns, 'circle')
    circ.setAttribute('cx', p.x); circ.setAttribute('cy', p.y); circ.setAttribute('r', r)
    circ.setAttribute('fill',         nd.ring ? '#0d0d2b' : nd.isSuspicious ? 'rgba(249,115,22,.15)' : 'rgba(100,116,139,.12)')
    circ.setAttribute('stroke',       col)
    circ.setAttribute('stroke-width', nd.ring ? '2.2' : nd.isSuspicious ? '1.4' : '0.8')
    if (nd.ring) circ.setAttribute('filter', 'url(#UG_glow_sm)')
    g.appendChild(circ)

    // label only for ring members (larger)
    if (nd.ring) {
      const lbl = document.createElementNS(ns, 'text')
      lbl.setAttribute('x', p.x); lbl.setAttribute('y', p.y + 1)
      lbl.setAttribute('text-anchor', 'middle'); lbl.setAttribute('dominant-baseline', 'middle')
      lbl.setAttribute('fill', col); lbl.setAttribute('font-size', '6')
      lbl.setAttribute('font-family', 'Space Mono,monospace'); lbl.setAttribute('font-weight', '700')
      lbl.textContent = String(nd.id).slice(-5)
      g.appendChild(lbl)

      const sub = document.createElementNS(ns, 'text')
      sub.setAttribute('x', p.x); sub.setAttribute('y', p.y + 26)
      sub.setAttribute('text-anchor', 'middle')
      sub.setAttribute('fill', 'rgba(226,232,240,.55)'); sub.setAttribute('font-size', '7')
      sub.setAttribute('font-family', 'DM Sans,sans-serif')
      sub.textContent = String(nd.id)
      g.appendChild(sub)
    }

    // click: select ring
    if (nd.ring) {
      g.addEventListener('click', (e) => {
        e.stopPropagation()
        selectedRing.value = nd.ring
        highlightRing(nd.ring.ring_id, root)
      })
    }

    // hover tooltip for suspicious non-ring nodes
    if (nd.isSuspicious && !nd.ring) {
      g.addEventListener('mouseenter', () => showTooltip(svg, p, nd))
      g.addEventListener('mouseleave', () => hideTooltip(svg))
    }

    nodeGroup.appendChild(g)
  })
  root.appendChild(nodeGroup)

  // Clear selection on background click
  svg.addEventListener('click', () => {
    selectedRing.value = null
    clearHighlight(root)
  })

  applyTransform(root)
}

// ── highlight / dim ────────────────────────────────────────────────
function highlightRing(ringId, root) {
  clearHighlight(root)
  // Dim all edges
  root.querySelectorAll('line').forEach(l => {
    l.setAttribute('opacity', l.getAttribute('data-ring-edge') === ringId ? '1' : '0.08')
    if (l.getAttribute('data-ring-edge') === ringId) {
      l.setAttribute('stroke-width', '2.5')
    }
  })
  // Dim all node groups
  root.querySelectorAll('g[data-ring-node]').forEach(g => {
    g.setAttribute('opacity', g.getAttribute('data-ring-node') === ringId ? '1' : '0.15')
  })
  // Bright hull
  root.querySelectorAll('polygon[data-ring]').forEach(p => {
    if (p.getAttribute('data-ring') === ringId) {
      p.setAttribute('fill-opacity', '0.22')
      p.setAttribute('stroke-width', '2.5')
      p.removeAttribute('stroke-dasharray')
    } else {
      p.setAttribute('opacity', '0.08')
    }
  })
}

function clearHighlight(root) {
  root.querySelectorAll('line').forEach(l => {
    l.setAttribute('opacity', '1')
    const isRing = l.getAttribute('data-ring-edge')
    l.setAttribute('stroke-width', isRing ? '1.8' : '0.8')
  })
  root.querySelectorAll('g[data-ring-node]').forEach(g => g.setAttribute('opacity', '1'))
  root.querySelectorAll('polygon[data-ring]').forEach(p => {
    p.setAttribute('opacity', '1')
    p.setAttribute('fill-opacity', '1')
    p.setAttribute('stroke-width', '1.8')
    p.setAttribute('stroke-dasharray', '5,3')
  })
}

// ── tooltip (non-ring suspicious nodes) ───────────────────────────
function showTooltip(svg, p, nd) {
  const ns  = 'http://www.w3.org/2000/svg'
  let   tip = svg.getElementById('ug-tooltip')
  if (!tip) {
    tip = document.createElementNS(ns, 'g')
    tip.setAttribute('id', 'ug-tooltip')
    svg.appendChild(tip)
  }
  tip.innerHTML = ''
  const rect = document.createElementNS(ns, 'rect')
  rect.setAttribute('x', p.x + 14); rect.setAttribute('y', p.y - 20)
  rect.setAttribute('width', '110'); rect.setAttribute('height', '36')
  rect.setAttribute('rx', '6'); rect.setAttribute('fill', '#0d0d2b')
  rect.setAttribute('stroke', 'rgba(255,255,255,.1)'); rect.setAttribute('stroke-width', '1')
  const t1 = document.createElementNS(ns, 'text')
  t1.setAttribute('x', p.x + 20); t1.setAttribute('y', p.y - 4)
  t1.setAttribute('fill', '#e2e8f0'); t1.setAttribute('font-size', '9')
  t1.setAttribute('font-family', 'Space Mono,monospace'); t1.textContent = nd.id
  const t2 = document.createElementNS(ns, 'text')
  t2.setAttribute('x', p.x + 20); t2.setAttribute('y', p.y + 9)
  t2.setAttribute('fill', '#f97316'); t2.setAttribute('font-size', '8')
  t2.setAttribute('font-family', 'DM Sans,sans-serif')
  t2.textContent = `Score: ${nd.suspicionScore?.toFixed(1) ?? '—'}`
  tip.appendChild(rect); tip.appendChild(t1); tip.appendChild(t2)
}

function hideTooltip(svg) {
  const tip = svg.getElementById('ug-tooltip')
  if (tip) tip.remove()
}

// ── pan / zoom ────────────────────────────────────────────────────
function applyTransform(root) {
  root.setAttribute('transform', `translate(${transform.x},${transform.y}) scale(${transform.k})`)
}

function onPanStart(e) {
  if (e.button !== 0) return
  isPanning = true
  panStart  = { x: e.clientX - transform.x, y: e.clientY - transform.y }
  svgEl.value.style.cursor = 'grabbing'
}
function onPanMove(e) {
  if (!isPanning) return
  transform.x = e.clientX - panStart.x
  transform.y = e.clientY - panStart.y
  const root = svgEl.value?.getElementById('ug-root')
  if (root) applyTransform(root)
}
function onPanEnd() {
  isPanning = false
  if (svgEl.value) svgEl.value.style.cursor = 'grab'
}
function onWheel(e) {
  const factor = e.deltaY < 0 ? 1.12 : 0.89
  const svg    = svgEl.value
  if (!svg) return
  const rect   = svg.getBoundingClientRect()
  const mx     = e.clientX - rect.left
  const my     = e.clientY - rect.top
  transform.x  = mx - factor * (mx - transform.x)
  transform.y  = my - factor * (my - transform.y)
  transform.k  = Math.max(0.15, Math.min(6, transform.k * factor))
  const root   = svg.getElementById('ug-root')
  if (root) applyTransform(root)
}

function onTouchStart(e) {
  if (e.touches.length === 2) {
    touchDist = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY)
  } else {
    isPanning = true
    panStart  = { x: e.touches[0].clientX - transform.x, y: e.touches[0].clientY - transform.y }
  }
}
function onTouchMove(e) {
  if (e.touches.length === 2) {
    const d = Math.hypot(e.touches[0].clientX - e.touches[1].clientX, e.touches[0].clientY - e.touches[1].clientY)
    const f = d / touchDist; touchDist = d
    transform.k = Math.max(0.15, Math.min(6, transform.k * f))
    const root = svgEl.value?.getElementById('ug-root')
    if (root) applyTransform(root)
  } else if (isPanning) {
    transform.x = e.touches[0].clientX - panStart.x
    transform.y = e.touches[0].clientY - panStart.y
    const root = svgEl.value?.getElementById('ug-root')
    if (root) applyTransform(root)
  }
}
function onTouchEnd() { isPanning = false }

// ── LAYOUT ────────────────────────────────────────────────────────
function computePositions(nodes, edges, W, H) {
  const n = nodes.length
  if (!n) return []

  if (layout.value === 'grid') {
    const cols = Math.ceil(Math.sqrt(n))
    const rows = Math.ceil(n / cols)
    const cW   = (W - 80) / cols
    const cH   = (H - 80) / rows
    return nodes.map((_, i) => ({
      x: 40 + cW * (i % cols + 0.5),
      y: 40 + cH * (Math.floor(i / cols) + 0.5)
    }))
  }

  // Force-directed
  const pos    = nodes.map(() => ({
    x: W * 0.1 + Math.random() * W * 0.8,
    y: H * 0.1 + Math.random() * H * 0.8,
    vx: 0, vy: 0
  }))
  const idxMap = {}
  nodes.forEach((nd, i) => { idxMap[nd.id] = i })

  // Group same-ring nodes close together by adding initial cluster seed
  const ringGroups = {}
  nodes.forEach((nd, i) => {
    if (nd.ring) {
      if (!ringGroups[nd.ring.ring_id]) ringGroups[nd.ring.ring_id] = { cx: Math.random()*W*0.6+W*0.2, cy: Math.random()*H*0.6+H*0.2 }
      const seed = ringGroups[nd.ring.ring_id]
      pos[i].x = seed.cx + (Math.random()-0.5)*60
      pos[i].y = seed.cy + (Math.random()-0.5)*60
    }
  })

  const K_REPEL   = 1800
  const K_ATTRACT = 0.04
  const K_RING    = 0.18   // stronger pull for same-ring members
  const IDEAL     = 90
  const IDEAL_RING = 55

  for (let it = 0; it < 300; it++) {
    // Repulsion
    for (let i = 0; i < n; i++) {
      for (let j = i+1; j < n; j++) {
        const dx = pos[j].x - pos[i].x, dy = pos[j].y - pos[i].y
        const d  = Math.max(Math.sqrt(dx*dx+dy*dy), 0.1)
        const f  = K_REPEL / (d*d)
        pos[i].vx -= (dx/d)*f; pos[i].vy -= (dy/d)*f
        pos[j].vx += (dx/d)*f; pos[j].vy += (dy/d)*f
      }
    }
    // Edge attraction
    edges.forEach(e => {
      const ai = idxMap[e.src], bi = idxMap[e.dst]
      if (ai == null || bi == null) return
      const sameRing = e.ring_id && nodes[ai].ring?.ring_id === nodes[bi].ring?.ring_id
      const ideal    = sameRing ? IDEAL_RING : IDEAL
      const k        = sameRing ? K_RING : K_ATTRACT
      const dx = pos[bi].x - pos[ai].x, dy = pos[bi].y - pos[ai].y
      const d  = Math.max(Math.sqrt(dx*dx+dy*dy), 0.1)
      const f  = (d - ideal) * k
      pos[ai].vx += (dx/d)*f; pos[ai].vy += (dy/d)*f
      pos[bi].vx -= (dx/d)*f; pos[bi].vy -= (dy/d)*f
    })
    // Gravity
    pos.forEach(p => {
      p.vx += (W/2 - p.x) * 0.01
      p.vy += (H/2 - p.y) * 0.01
    })
    // Integrate
    pos.forEach(p => {
      p.x += p.vx * 0.3; p.y += p.vy * 0.3
      p.vx *= 0.82;      p.vy *= 0.82
      p.x = Math.max(30, Math.min(W-30, p.x))
      p.y = Math.max(30, Math.min(H-30, p.y))
    })
  }
  return pos
}

// ── CONVEX HULL (Graham scan) ─────────────────────────────────────
function convexHull(pts) {
  if (pts.length < 3) return pts
  const sorted = [...pts].sort((a, b) => a.x !== b.x ? a.x - b.x : a.y - b.y)
  const cross   = (o, a, b) => (a.x-o.x)*(b.y-o.y) - (a.y-o.y)*(b.x-o.x)
  const lower   = []
  for (const p of sorted) {
    while (lower.length >= 2 && cross(lower[lower.length-2], lower[lower.length-1], p) <= 0) lower.pop()
    lower.push(p)
  }
  const upper = []
  for (let i = sorted.length-1; i >= 0; i--) {
    const p = sorted[i]
    while (upper.length >= 2 && cross(upper[upper.length-2], upper[upper.length-1], p) <= 0) upper.pop()
    upper.push(p)
  }
  upper.pop(); lower.pop()
  return lower.concat(upper)
}

function padHull(hull, pad) {
  const cx = hull.reduce((s, p) => s + p.x, 0) / hull.length
  const cy = hull.reduce((s, p) => s + p.y, 0) / hull.length
  return hull.map(p => {
    const dx = p.x - cx, dy = p.y - cy
    const d  = Math.max(Math.sqrt(dx*dx+dy*dy), 0.1)
    return { x: p.x + (dx/d)*pad, y: p.y + (dy/d)*pad }
  })
}

function hexToRgba(hex, alpha) {
  // supports CSS var() strings — fall back to purple
  if (!hex || hex.startsWith('var(')) return `rgba(124,58,237,${alpha})`
  const r = parseInt(hex.slice(1,3),16)
  const g = parseInt(hex.slice(3,5),16)
  const b = parseInt(hex.slice(5,7),16)
  return `rgba(${r},${g},${b},${alpha})`
}
</script>

<style scoped>
.gv { display:flex; flex-direction:column; gap:14px; }

/* File tabs */
.file-tabs { display:flex; gap:6px; flex-wrap:wrap; }
.ftab {
  padding:6px 16px; border-radius:8px; font-size:12px; font-weight:600;
  border:1px solid var(--border); background:transparent; color:var(--muted);
  cursor:pointer; transition:all .2s; font-family:var(--font-sans);
}
.ftab:hover { color:var(--text); background:var(--surface2); }
.ftab.active { background:var(--purple); border-color:var(--purple); color:#fff; }

/* Toolbar */
.toolbar {
  display:flex; align-items:center; justify-content:space-between;
  flex-wrap:wrap; gap:10px;
}
.toolbar-left, .toolbar-right { display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
.graph-meta { font-size:13px; color:var(--muted); }
.accent { color:var(--accent); }

.layout-toggle {
  display:flex; background:var(--surface); border:1px solid var(--border);
  border-radius:10px; overflow:hidden;
}
.lt-btn {
  padding:7px 14px; font-size:12px; font-weight:600;
  background:transparent; border:none; color:var(--muted);
  cursor:pointer; transition:all .2s; font-family:var(--font-sans); white-space:nowrap;
}
.lt-btn:hover { color:var(--text); }
.lt-btn.active { background:var(--purple); color:#fff; }

.btn-rerun {
  background:var(--surface); border:1px solid var(--border);
  color:var(--muted); padding:7px 14px; border-radius:10px;
  font-size:12px; font-weight:600; cursor:pointer; transition:all .2s; font-family:var(--font-sans);
}
.btn-rerun:hover { color:var(--accent); border-color:var(--purple); }

/* Legend */
.legend { display:flex; gap:16px; flex-wrap:wrap; font-size:12px; color:var(--muted); align-items:center; }
.lg-item { display:flex; align-items:center; gap:6px; }
.lg-dot  { width:9px; height:9px; border-radius:50%; flex-shrink:0; border:1.5px solid currentColor; }
.ring-dot { background:rgba(124,58,237,.2); border-color:#a855f7; }
.susp-dot { background:rgba(249,115,22,.2); border-color:#f97316; }
.norm-dot { background:rgba(100,116,139,.2); border-color:#64748b; }
.lg-edge  { width:22px; height:2px; }
.ring-edge { background:rgba(192,132,252,.7); }
.lg-hint { font-size:11px; color:rgba(148,163,184,.6); font-style:italic; }

/* Canvas */
.canvas-wrap {
  position:relative;
  background:var(--surface); border:1px solid var(--border);
  border-radius:18px; overflow:hidden;
  height: clamp(460px, 68vh, 820px);
}
.main-svg {
  width:100%; height:100%;
  cursor:grab;
  display:block;
}

/* Zoom hint */
.zoom-hint {
  position:absolute; bottom:12px; left:50%; transform:translateX(-50%);
  font-size:11px; color:rgba(148,163,184,.45);
  background:rgba(7,7,26,.7); padding:4px 12px; border-radius:20px;
  pointer-events:none; white-space:nowrap;
}

/* Ring info sidebar */
.ring-sidebar {
  position:absolute; top:16px; right:16px;
  width: clamp(220px, 26vw, 300px);
  background:rgba(7,7,26,.96); border:1px solid rgba(124,58,237,.3);
  border-radius:16px; padding:18px 20px;
  backdrop-filter:blur(20px);
  box-shadow:0 0 40px rgba(124,58,237,.15);
  overflow-y:auto; max-height:calc(100% - 32px);
}

.sidebar-close {
  position:absolute; top:12px; right:14px;
  background:var(--surface2); border:1px solid var(--border);
  color:var(--muted); width:24px; height:24px; border-radius:6px;
  font-size:12px; cursor:pointer; display:flex; align-items:center; justify-content:center;
  transition:all .2s;
}
.sidebar-close:hover { color:var(--text); background:var(--surface); }

.sb-header { display:flex; align-items:center; gap:10px; margin-bottom:16px; flex-wrap:wrap; padding-right:28px; }
.sb-id { font-size:14px; font-weight:700; color:var(--accent); }

.badge {
  display:inline-flex; align-items:center; gap:4px;
  padding:3px 10px; border-radius:50px; font-size:11px; font-weight:600;
}
.badge::before { content:''; width:5px; height:5px; border-radius:50%; background:currentColor; }
.badge.Critical { background:rgba(239,68,68,.15);  color:#ef4444; }
.badge.High     { background:rgba(249,115,22,.15); color:#f97316; }
.badge.Medium   { background:rgba(234,179,8,.15);  color:#eab308; }
.badge.Low      { background:rgba(34,197,94,.15);  color:#22c55e; }

.sb-score-bar { margin-bottom:16px; }
.sb-score-label { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.7px; font-weight:600; display:block; margin-bottom:6px; }
.sb-bar-wrap { display:flex; align-items:center; gap:10px; }
.sb-bar-track { flex:1; height:6px; background:var(--border); border-radius:3px; overflow:hidden; }
.sb-bar-fill  { height:100%; border-radius:3px; transition:width .4s; }
.sb-score-val { font-size:13px; font-weight:700; flex-shrink:0; }

.sb-rows { display:flex; flex-direction:column; gap:8px; margin-bottom:16px; padding-bottom:16px; border-bottom:1px solid var(--border); }
.sb-row  { display:flex; justify-content:space-between; align-items:center; gap:12px; font-size:12px; }
.sb-row span:first-child { color:var(--muted); }
.sb-row span:last-child  { font-weight:600; }

.sb-members { }
.sb-members-label { font-size:10px; color:var(--muted); text-transform:uppercase; letter-spacing:.7px; font-weight:600; margin-bottom:8px; }
.sb-chips { display:flex; flex-wrap:wrap; gap:5px; }
.sb-chip {
  font-size:10px; background:rgba(124,58,237,.12); border:1px solid rgba(124,58,237,.25);
  color:var(--accent); padding:3px 7px; border-radius:5px;
}

/* Sidebar transition */
.sidebar-enter-active, .sidebar-leave-active { transition:all .25s ease; }
.sidebar-enter-from, .sidebar-leave-to { opacity:0; transform:translateX(16px); }

@media(max-width:768px){
  .ring-sidebar { width:calc(100% - 32px); top:auto; bottom:16px; right:16px; left:16px; max-height:45%; }
  .canvas-wrap { height:clamp(380px,55vh,600px); }
}
@media(max-width:480px){
  .toolbar { flex-direction:column; align-items:flex-start; }
  .legend { gap:10px; }
}
</style>
