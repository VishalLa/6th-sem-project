<template>
  <div class="charts">

    <!-- ── Row 1: Pie + Donut ── -->
    <div class="charts-row">

      <!-- Risk Category Pie -->
      <div class="chart-card">
        <div class="card-header">
          <span class="card-title">Risk Distribution</span>
          <span class="card-sub">Rings by category</span>
        </div>
        <div class="pie-wrap">
          <svg viewBox="0 0 220 220" class="pie-svg">
            <g transform="translate(110,110)">
              <template v-for="(slice, i) in pieSlices" :key="i">
                <path
                  :d="slice.d"
                  :fill="slice.color"
                  :opacity="hoveredSlice === i ? 1 : 0.82"
                  stroke="#07071a" stroke-width="2"
                  style="cursor:pointer;transition:opacity .2s,transform .2s"
                  :style="hoveredSlice === i ? { transform:'scale(1.06)', transformOrigin:'center' } : {}"
                  @mouseenter="hoveredSlice = i"
                  @mouseleave="hoveredSlice = null"
                />
              </template>
              <!-- Centre hole -->
              <circle r="52" fill="#0d0d2b" />
              <!-- Centre label -->
              <text text-anchor="middle" dy="-6" fill="#e2e8f0" font-size="22" font-family="Space Mono,monospace" font-weight="700">
                {{ store.totalRings }}
              </text>
              <text text-anchor="middle" dy="14" fill="#94a3b8" font-size="9" font-family="DM Sans,sans-serif">
                total rings
              </text>
            </g>
          </svg>
          <div class="pie-legend">
            <div v-for="(sl, i) in pieSlices" :key="i" class="pie-leg-item"
              :class="{ active: hoveredSlice === i }"
              @mouseenter="hoveredSlice = i" @mouseleave="hoveredSlice = null">
              <span class="pie-dot" :style="{ background: sl.color }" />
              <span class="pie-label">{{ sl.label }}</span>
              <span class="pie-val mono">{{ sl.count }}</span>
              <span class="pie-pct">{{ sl.pct }}%</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Risk Score Distribution — horizontal bar chart -->
      <div class="chart-card">
        <div class="card-header">
          <span class="card-title">Score Spread</span>
          <span class="card-sub">Rings per score bucket (0–100)</span>
        </div>
        <div class="bar-chart-wrap">
          <div v-for="bucket in scoreBuckets" :key="bucket.label" class="bar-row">
            <span class="bar-label mono">{{ bucket.label }}</span>
            <div class="bar-track">
              <div
                class="bar-fill"
                :style="{ width: bucket.pct + '%', background: bucket.color }"
              />
            </div>
            <span class="bar-count mono">{{ bucket.count }}</span>
          </div>
          <div v-if="!store.rings.length" class="no-data">No data yet</div>
        </div>
      </div>

    </div>

    <!-- ── Row 2: Pattern breakdown radar + line ── -->
    <div class="charts-row">

      <!-- Pattern type bar -->
      <div class="chart-card">
        <div class="card-header">
          <span class="card-title">Pattern Breakdown</span>
          <span class="card-sub">Rings per detected pattern</span>
        </div>
        <div class="pattern-bars">
          <div v-for="p in patternBars" :key="p.label" class="pat-row">
            <div class="pat-meta">
              <span class="pat-label">{{ p.label }}</span>
              <span class="mono pat-count">{{ p.count }}</span>
            </div>
            <div class="pat-track">
              <div class="pat-fill" :style="{ width: p.pct + '%', background: p.color }" />
            </div>
            <div class="pat-score-row">
              <span class="pat-score-label">Avg score</span>
              <span class="mono" :style="{ color: riskColor(p.avgScore) }">{{ p.avgScore }}</span>
            </div>
          </div>
          <div v-if="!patternBars.length" class="no-data">No data yet</div>
        </div>
      </div>

      <!-- Risk Score Line Chart (rings sorted by score) -->
      <div class="chart-card">
        <div class="card-header">
          <span class="card-title">Risk Score Profile</span>
          <span class="card-sub">All rings sorted by score (hover for details)</span>
        </div>
        <div class="line-wrap" ref="lineWrap">
          <svg :viewBox="`0 0 ${LINE_W} ${LINE_H}`" class="line-svg" preserveAspectRatio="xMidYMid meet">
            <!-- Grid lines -->
            <line v-for="y in [0,25,50,75,100]" :key="y"
              :x1="LINE_PAD" :y1="yScale(y)"
              :x2="LINE_W - LINE_PAD" :y2="yScale(y)"
              stroke="rgba(255,255,255,0.05)" stroke-width="1"
            />
            <!-- Y axis labels -->
            <text v-for="y in [0,25,50,75,100]" :key="'l'+y"
              :x="LINE_PAD - 6" :y="yScale(y) + 3"
              text-anchor="end" fill="#94a3b8" font-size="9" font-family="Space Mono,monospace">
              {{ y }}
            </text>

            <!-- Gradient fill under line -->
            <defs>
              <linearGradient id="lineGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#7c3aed" stop-opacity="0.35"/>
                <stop offset="100%" stop-color="#7c3aed" stop-opacity="0"/>
              </linearGradient>
            </defs>

            <!-- Area fill -->
            <path v-if="linePath" :d="areaPath" fill="url(#lineGrad)" />

            <!-- Line -->
            <path v-if="linePath" :d="linePath"
              fill="none" stroke="#a855f7" stroke-width="2"
              stroke-linejoin="round" stroke-linecap="round"
            />

            <!-- Dots -->
            <circle
              v-for="(pt, i) in linePoints" :key="i"
              :cx="pt.x" :cy="pt.y" r="4"
              :fill="riskColor(pt.score)"
              stroke="#07071a" stroke-width="1.5"
              style="cursor:pointer"
              @mouseenter="hoveredLine = i"
              @mouseleave="hoveredLine = null"
            />

            <!-- Hover tooltip -->
            <template v-if="hoveredLine !== null && linePoints[hoveredLine]">
              <rect
                :x="clamp(linePoints[hoveredLine].x - 55, LINE_PAD, LINE_W - LINE_PAD - 110)"
                :y="linePoints[hoveredLine].y - 46"
                width="110" height="38" rx="6"
                fill="#0d0d2b" stroke="rgba(124,58,237,.4)" stroke-width="1"
              />
              <text
                :x="clamp(linePoints[hoveredLine].x, LINE_PAD + 55, LINE_W - LINE_PAD - 55)"
                :y="linePoints[hoveredLine].y - 30"
                text-anchor="middle" fill="#c084fc" font-size="8.5" font-family="Space Mono,monospace" font-weight="700">
                {{ linePoints[hoveredLine].ringId }}
              </text>
              <text
                :x="clamp(linePoints[hoveredLine].x, LINE_PAD + 55, LINE_W - LINE_PAD - 55)"
                :y="linePoints[hoveredLine].y - 16"
                text-anchor="middle" font-size="8" font-family="DM Sans,sans-serif"
                :fill="riskColor(linePoints[hoveredLine].score)">
                Score: {{ linePoints[hoveredLine].score.toFixed(1) }}
              </text>
            </template>

            <!-- X axis label -->
            <text :x="LINE_W/2" :y="LINE_H - 2" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="DM Sans,sans-serif">
              Rings (sorted by risk score ↓)
            </text>
          </svg>
          <div v-if="!linePoints.length" class="no-data">No data yet</div>
        </div>
      </div>

    </div>

    <!-- ── Row 3: Member count distribution + Density scatter ── -->
    <div class="charts-row">

      <!-- Member count histogram -->
      <div class="chart-card">
        <div class="card-header">
          <span class="card-title">Ring Size Distribution</span>
          <span class="card-sub">Number of rings by member count</span>
        </div>
        <div class="bar-chart-wrap">
          <div v-for="b in memberBuckets" :key="b.label" class="bar-row">
            <span class="bar-label mono">{{ b.label }}</span>
            <div class="bar-track">
              <div class="bar-fill" :style="{ width: b.pct + '%', background: '#7c3aed' }" />
            </div>
            <span class="bar-count mono">{{ b.count }}</span>
          </div>
          <div v-if="!memberBuckets.length || !store.rings.length" class="no-data">No data yet</div>
        </div>
      </div>

      <!-- Density vs Risk Score scatter -->
      <div class="chart-card">
        <div class="card-header">
          <span class="card-title">Density vs Risk Score</span>
          <span class="card-sub">Each dot = one ring (hover for ID)</span>
        </div>
        <div class="line-wrap">
          <svg :viewBox="`0 0 ${LINE_W} ${LINE_H}`" class="line-svg" preserveAspectRatio="xMidYMid meet">
            <!-- Grid -->
            <line v-for="y in [0,25,50,75,100]" :key="'gy'+y"
              :x1="LINE_PAD" :y1="yScale(y)" :x2="LINE_W-LINE_PAD" :y2="yScale(y)"
              stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
            <line v-for="x in [0,0.25,0.5,0.75,1.0]" :key="'gx'+x"
              :x1="xScatter(x)" :y1="LINE_PAD" :x2="xScatter(x)" :y2="LINE_H-LINE_PAD-10"
              stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
            <!-- Axis labels -->
            <text v-for="y in [0,25,50,75,100]" :key="'ly'+y"
              :x="LINE_PAD-6" :y="yScale(y)+3"
              text-anchor="end" fill="#94a3b8" font-size="9" font-family="Space Mono,monospace">{{ y }}</text>
            <text v-for="x in [0,0.5,1.0]" :key="'lx'+x"
              :x="xScatter(x)" :y="LINE_H-LINE_PAD+2"
              text-anchor="middle" fill="#94a3b8" font-size="8" font-family="Space Mono,monospace">{{ x }}</text>
            <!-- Dots -->
            <circle
              v-for="(pt, i) in scatterPoints" :key="i"
              :cx="pt.x" :cy="pt.y"
              :r="3 + pt.members * 0.6"
              :fill="riskColor(pt.score)"
              fill-opacity="0.75"
              stroke="#07071a" stroke-width="1"
              style="cursor:pointer"
              @mouseenter="hoveredScatter = i"
              @mouseleave="hoveredScatter = null"
            />
            <!-- Hover tooltip -->
            <template v-if="hoveredScatter !== null && scatterPoints[hoveredScatter]">
              <rect
                :x="clamp(scatterPoints[hoveredScatter].x - 55, LINE_PAD, LINE_W-LINE_PAD-110)"
                :y="scatterPoints[hoveredScatter].y - 52"
                width="110" height="44" rx="6"
                fill="#0d0d2b" stroke="rgba(124,58,237,.4)" stroke-width="1"/>
              <text
                :x="clamp(scatterPoints[hoveredScatter].x, LINE_PAD+55, LINE_W-LINE_PAD-55)"
                :y="scatterPoints[hoveredScatter].y - 36"
                text-anchor="middle" fill="#c084fc" font-size="8" font-family="Space Mono,monospace" font-weight="700">
                {{ scatterPoints[hoveredScatter].ringId }}
              </text>
              <text
                :x="clamp(scatterPoints[hoveredScatter].x, LINE_PAD+55, LINE_W-LINE_PAD-55)"
                :y="scatterPoints[hoveredScatter].y - 23"
                text-anchor="middle" fill="#94a3b8" font-size="7.5" font-family="DM Sans,sans-serif">
                Score: {{ scatterPoints[hoveredScatter].score.toFixed(1) }}  Density: {{ scatterPoints[hoveredScatter].density.toFixed(2) }}
              </text>
              <text
                :x="clamp(scatterPoints[hoveredScatter].x, LINE_PAD+55, LINE_W-LINE_PAD-55)"
                :y="scatterPoints[hoveredScatter].y - 11"
                text-anchor="middle" fill="#94a3b8" font-size="7.5" font-family="DM Sans,sans-serif">
                Members: {{ scatterPoints[hoveredScatter].members }}
              </text>
            </template>
            <!-- Axis titles -->
            <text :x="LINE_W/2" :y="LINE_H-2" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="DM Sans,sans-serif">Ring Density →</text>
            <text x="10" :y="LINE_H/2" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="DM Sans,sans-serif"
              :transform="`rotate(-90, 10, ${LINE_H/2})`">Risk Score ↑</text>
          </svg>
          <div v-if="!scatterPoints.length" class="no-data">No data yet</div>
        </div>
      </div>

    </div>

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useResultsStore } from '@/stores/results'

const store = useResultsStore()

const hoveredSlice   = ref(null)
const hoveredLine    = ref(null)
const hoveredScatter = ref(null)

// ── chart dimensions ──────────────────────────────────────────────────
const LINE_W   = 480
const LINE_H   = 220
const LINE_PAD = 38

// ── helpers ───────────────────────────────────────────────────────────
function riskColor(score) {
  if (score >= 85) return '#ef4444'
  if (score >= 70) return '#f97316'
  if (score >= 50) return '#eab308'
  return '#22c55e'
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)) }

function yScale(score) {
  return LINE_PAD + (1 - score / 100) * (LINE_H - LINE_PAD - 18)
}
function xScatter(density) {
  return LINE_PAD + density * (LINE_W - LINE_PAD * 2)
}

// ── PIE slices ────────────────────────────────────────────────────────
const CAT_COLORS = { Critical: '#ef4444', High: '#f97316', Medium: '#eab308', Low: '#22c55e' }

const pieSlices = computed(() => {
  const cats = ['Critical', 'High', 'Medium', 'Low']
  const total = store.totalRings || 1
  let startAngle = -Math.PI / 2
  return cats.map(cat => {
    const count = store.rings.filter(r => r['Risk Category'] === cat).length
    const angle = (count / total) * 2 * Math.PI
    const endAngle = startAngle + angle
    const R = 88
    const x1 = Math.cos(startAngle) * R, y1 = Math.sin(startAngle) * R
    const x2 = Math.cos(endAngle)   * R, y2 = Math.sin(endAngle)   * R
    const large = angle > Math.PI ? 1 : 0
    const d = count > 0
      ? `M 0 0 L ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2} Z`
      : ''
    const pct = total > 0 ? Math.round((count / total) * 100) : 0
    startAngle = endAngle
    return { label: cat, count, color: CAT_COLORS[cat], d, pct }
  }).filter(s => s.count > 0)
})

// ── Score distribution buckets (0-20, 20-40, 40-60, 60-80, 80-100) ──
const scoreBuckets = computed(() => {
  const buckets = [
    { label: '80–100', min: 80, max: 100, color: '#ef4444' },
    { label: '60–80',  min: 60, max: 80,  color: '#f97316' },
    { label: '40–60',  min: 40, max: 60,  color: '#eab308' },
    { label: '20–40',  min: 20, max: 40,  color: '#22c55e' },
    { label: '0–20',   min: 0,  max: 20,  color: '#38bdf8' },
  ]
  const max = Math.max(...buckets.map(b => {
    return store.rings.filter(r => r['Risk Score'] >= b.min && r['Risk Score'] < (b.max === 100 ? 101 : b.max)).length
  }), 1)
  return buckets.map(b => {
    const count = store.rings.filter(r => {
      const s = r['Risk Score']
      return s >= b.min && (b.max === 100 ? s <= 100 : s < b.max)
    }).length
    return { ...b, count, pct: Math.round((count / max) * 100) }
  })
})

// ── Pattern bars ──────────────────────────────────────────────────────
const PATTERN_LABELS = {
  cycle_length_3: 'Cycle ×3',
  fan_in:         'Fan-In',
  fan_out:        'Fan-Out',
  layered_shell:  'Layered Shell'
}
const PATTERN_COLORS = {
  cycle_length_3: '#a855f7',
  fan_in:         '#38bdf8',
  fan_out:        '#f97316',
  layered_shell:  '#22c55e'
}

const patternBars = computed(() => {
  const pats = ['cycle_length_3', 'fan_in', 'fan_out', 'layered_shell']
  const maxCount = Math.max(...pats.map(p =>
    store.rings.filter(r => r['Pattern Type'] === p).length
  ), 1)

  return pats.map(p => {
    const rows     = store.rings.filter(r => r['Pattern Type'] === p)
    const count    = rows.length
    const avgScore = count
      ? Math.round(rows.reduce((s, r) => s + (r['Risk Score'] || 0), 0) / count)
      : 0
    return {
      label:    PATTERN_LABELS[p] || p,
      count,
      pct:      Math.round((count / maxCount) * 100),
      color:    PATTERN_COLORS[p],
      avgScore
    }
  }).filter(p => p.count > 0)
})

// ── Line chart: rings sorted by score ────────────────────────────────
const linePoints = computed(() => {
  const sorted = [...store.rings].sort((a, b) => b['Risk Score'] - a['Risk Score'])
  const n = sorted.length
  if (!n) return []
  const usableW = LINE_W - LINE_PAD * 2
  return sorted.map((r, i) => ({
    x: LINE_PAD + (n === 1 ? usableW / 2 : (i / (n - 1)) * usableW),
    y: yScale(r['Risk Score']),
    score:  r['Risk Score'],
    ringId: r['Ring ID']
  }))
})

const linePath = computed(() => {
  if (!linePoints.value.length) return ''
  return linePoints.value.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ')
})

const areaPath = computed(() => {
  if (!linePoints.value.length) return ''
  const pts = linePoints.value
  const bottom = yScale(0)
  return [
    `M ${pts[0].x} ${bottom}`,
    ...pts.map(p => `L ${p.x} ${p.y}`),
    `L ${pts[pts.length-1].x} ${bottom}`,
    'Z'
  ].join(' ')
})

// ── Member count buckets ──────────────────────────────────────────────
const memberBuckets = computed(() => {
  const buckets = [
    { label: '2',    min: 2,  max: 2  },
    { label: '3',    min: 3,  max: 3  },
    { label: '4–5',  min: 4,  max: 5  },
    { label: '6–10', min: 6,  max: 10 },
    { label: '11+',  min: 11, max: Infinity }
  ]
  const maxC = Math.max(...buckets.map(b =>
    store.rings.filter(r => r['Member Count'] >= b.min && r['Member Count'] <= b.max).length
  ), 1)
  return buckets.map((b, i) => {
    const count = store.rings.filter(r => r['Member Count'] >= b.min && r['Member Count'] <= b.max).length
    const colors = ['#7c3aed','#a855f7','#c084fc','#38bdf8','#22d3ee']
    return { ...b, count, pct: Math.round((count / maxC) * 100), color: colors[i] }
  }).filter(b => b.count > 0)
})

// ── Scatter: density vs risk score ───────────────────────────────────
const scatterPoints = computed(() =>
  store.rings.map(r => ({
    x:       xScatter(r['Ring Density'] ?? 0),
    y:       yScale(r['Risk Score']    ?? 0),
    score:   r['Risk Score'],
    density: r['Ring Density']  ?? 0,
    members: r['Member Count']  ?? 0,
    ringId:  r['Ring ID']
  }))
)
</script>

<style scoped>
.charts { display:flex; flex-direction:column; gap:20px; }

.charts-row {
  display:grid;
  grid-template-columns: repeat(auto-fit, minmax(340px, 1fr));
  gap:20px;
}

/* Card */
.chart-card {
  background:var(--surface); border:1px solid var(--border);
  border-radius:16px; padding:20px 22px; display:flex; flex-direction:column; gap:16px;
  transition:border-color .2s;
}
.chart-card:hover { border-color:rgba(124,58,237,.3); }

.card-header { display:flex; flex-direction:column; gap:3px; }
.card-title  { font-family:var(--font-mono); font-size:13px; font-weight:700; color:var(--text); }
.card-sub    { font-size:11px; color:var(--muted); }

/* ── Pie ── */
.pie-wrap {
  display:flex; align-items:center; gap:20px; flex-wrap:wrap;
  justify-content:center;
}
.pie-svg { width:180px; height:180px; flex-shrink:0; overflow:visible; }

.pie-legend { display:flex; flex-direction:column; gap:8px; }
.pie-leg-item {
  display:flex; align-items:center; gap:8px; font-size:12px;
  cursor:pointer; border-radius:6px; padding:3px 6px; transition:background .15s;
}
.pie-leg-item:hover, .pie-leg-item.active { background:var(--surface2); }
.pie-dot   { width:9px; height:9px; border-radius:50%; flex-shrink:0; }
.pie-label { color:var(--text); flex:1; font-weight:500; }
.pie-val   { color:var(--accent); font-size:12px; }
.pie-pct   { color:var(--muted); font-size:11px; min-width:32px; text-align:right; }

/* ── Horizontal bar charts ── */
.bar-chart-wrap { display:flex; flex-direction:column; gap:10px; }
.bar-row { display:flex; align-items:center; gap:10px; }
.bar-label { font-size:11px; color:var(--muted); min-width:44px; flex-shrink:0; text-align:right; }
.bar-track {
  flex:1; height:14px; background:rgba(255,255,255,.06);
  border-radius:7px; overflow:hidden;
}
.bar-fill { height:100%; border-radius:7px; transition:width .5s ease; }
.bar-count { font-size:11px; color:var(--accent); min-width:20px; }

/* ── Pattern bars ── */
.pattern-bars { display:flex; flex-direction:column; gap:14px; }
.pat-row { display:flex; flex-direction:column; gap:5px; }
.pat-meta { display:flex; justify-content:space-between; align-items:center; }
.pat-label { font-size:12px; font-weight:600; color:var(--text); }
.pat-count { font-size:12px; color:var(--accent); }
.pat-track { height:10px; background:rgba(255,255,255,.06); border-radius:5px; overflow:hidden; }
.pat-fill  { height:100%; border-radius:5px; transition:width .5s ease; }
.pat-score-row { display:flex; justify-content:flex-end; gap:6px; font-size:10px; }
.pat-score-label { color:var(--muted); }

/* ── Line / scatter SVG ── */
.line-wrap { position:relative; }
.line-svg  { width:100%; height:auto; display:block; }

/* ── No data ── */
.no-data {
  text-align:center; padding:40px 20px; color:var(--muted); font-size:13px;
}

@media(max-width:640px){
  .charts-row { grid-template-columns:1fr; }
  .pie-wrap   { flex-direction:column; align-items:center; }
}
</style>
