<template>
  <div class="table-wrap">

    <!-- Toolbar -->
    <div class="toolbar">
      <div class="search-box" :class="{ focused }">
        <SearchIcon />
        <input v-model="q" placeholder="Search rings, accounts, patterns…"
          @focus="focused=true" @blur="focused=false" />
        <button v-if="q" class="q-clear" @click="q=''">✕</button>
      </div>

      <div class="pills">
        <button v-for="cat in CATS" :key="cat"
          class="pill" :class="{ active: filter===cat }" :data-cat="cat"
          @click="filter=cat; page=1">
          {{ cat==='all' ? 'All' : cat }}
          <span v-if="cat!=='all'" class="pill-n">{{ countByCat(cat) }}</span>
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="scroll">
      <table>
        <thead>
          <tr>
            <th v-for="col in COLS" :key="col.key"
              :class="sortKey===col.key ? (sortDir===1?'asc':'desc') : ''"
              @click="doSort(col.key)">
              {{ col.label }}
              <span class="si">{{ sortKey===col.key ? (sortDir===1?'↑':'↓') : '↕' }}</span>
            </th>
          </tr>
        </thead>

        <tbody>
          <!-- Loading -->
          <tr v-if="store.loading">
            <td :colspan="COLS.length">
              <div class="tstate"><div class="spin" />Loading results…</div>
            </td>
          </tr>

          <!-- Error -->
          <tr v-else-if="store.error">
            <td :colspan="COLS.length">
              <div class="tstate err">{{ store.error }}</div>
            </td>
          </tr>

          <!-- No data at all -->
          <tr v-else-if="!store.rings.length">
            <td :colspan="COLS.length">
              <div class="tstate">No detection results yet — upload a CSV on the Home page.</div>
            </td>
          </tr>

          <!-- No match -->
          <tr v-else-if="!visible.length">
            <td :colspan="COLS.length">
              <div class="tstate">No rings match your filter.</div>
            </td>
          </tr>

          <!-- Data rows -->
          <tr v-else v-for="ring in paginated" :key="ring['Ring ID']" class="drow">
            <!-- Ring ID -->
            <td><span class="mono rid">{{ ring['Ring ID'] }}</span></td>

            <!-- Pattern (cycle_length_3 / fan_in / fan_out / layered_shell) -->
            <td><span class="pattern-chip">{{ fmtPattern(ring['Pattern Type']) }}</span></td>

            <!-- Members -->
            <td><span class="chip-num">{{ ring['Member Count'] }}</span></td>

            <!-- Risk Score with mini bar -->
            <td>
              <div class="score-cell">
                <span class="mono">{{ ring['Risk Score'] }}</span>
                <div class="bar-track">
                  <div class="bar-fill" :style="{ width: Math.min(ring['Risk Score'],100)+'%', background: riskColor(ring['Risk Score']) }" />
                </div>
              </div>
            </td>

            <!-- Category badge -->
            <td><span class="badge" :class="ring['Risk Category']">{{ ring['Risk Category'] }}</span></td>

            <!-- Avg / Max member score -->
            <td class="mono dim">{{ ring['Avg Member Score'] }}</td>
            <td class="mono dim">{{ ring['Max Member Score'] }}</td>

            <!-- Structural Complexity -->
            <td class="mono dim">{{ ring['Structural Complexity'] }}</td>

            <!-- Internal Edge Count -->
            <td class="mono dim">{{ ring['Internal Edge Count'] }}</td>

            <!-- Ring Density -->
            <td class="mono dim">{{ ring['Ring Density'] }}</td>

            <!-- Member IDs (truncated, full in title attr) -->
            <td>
              <span class="mids" :title="ring['Member Account IDs']">
                {{ ring['Member Account IDs'] }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="total > PAGE_SIZE" class="pagination">
      <button :disabled="page===1" @click="page--" class="pg-btn">←</button>
      <span class="pg-info">{{ page }} / {{ totalPages }} &nbsp;·&nbsp; {{ total }} rings</span>
      <button :disabled="page===totalPages" @click="page++" class="pg-btn">→</button>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, watch, defineComponent, h } from 'vue'
import { useResultsStore } from '@/stores/results'

const store = useResultsStore()

// ── columns — exact field names from engine.py summary_table() ──────
const COLS = [
  { key: 'Ring ID',               label: 'Ring ID'      },
  { key: 'Pattern Type',          label: 'Pattern'       },
  { key: 'Member Count',          label: 'Members'       },
  { key: 'Risk Score',            label: 'Risk Score'    },
  { key: 'Risk Category',         label: 'Category'      },
  { key: 'Avg Member Score',      label: 'Avg Score'     },
  { key: 'Max Member Score',      label: 'Max Score'     },
  { key: 'Structural Complexity', label: 'Complexity'    },
  { key: 'Internal Edge Count',   label: 'Edges'         },
  { key: 'Ring Density',          label: 'Density'       },
  { key: 'Member Account IDs',    label: 'Member IDs'    }
]

const CATS = ['all', 'Critical', 'High', 'Medium', 'Low']
const PAGE_SIZE = 20

const q       = ref('')
const filter  = ref('all')
const sortKey = ref('Risk Score')
const sortDir = ref(-1)   // default: highest score first
const page    = ref(1)
const focused = ref(false)

// Inline icon
const SearchIcon = defineComponent({
  render: () => h('svg', { viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':'2', style:'width:15px;height:15px;flex-shrink:0;stroke:var(--muted)' }, [
    h('circle', { cx:'11', cy:'11', r:'8' }),
    h('line',   { x1:'21', y1:'21', x2:'16.65', y2:'16.65' })
  ])
})

// ── filter + sort ───────────────────────────────────────────────────
const filtered = computed(() => {
  let list = [...store.rings]
  if (filter.value !== 'all')
    list = list.filter(r => r['Risk Category'] === filter.value)
  if (q.value) {
    const lq = q.value.toLowerCase()
    list = list.filter(r => JSON.stringify(r).toLowerCase().includes(lq))
  }
  if (sortKey.value) {
    list.sort((a, b) => {
      const va = a[sortKey.value], vb = b[sortKey.value]
      if (typeof va === 'number') return (va - vb) * sortDir.value
      return String(va ?? '').localeCompare(String(vb ?? '')) * sortDir.value
    })
  }
  return list
})

const total      = computed(() => filtered.value.length)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const paginated  = computed(() => {
  const s = (page.value - 1) * PAGE_SIZE
  return filtered.value.slice(s, s + PAGE_SIZE)
})
const visible = paginated  // alias for template

watch([q, filter], () => { page.value = 1 })

function doSort(key) {
  if (sortKey.value === key) sortDir.value *= -1
  else { sortKey.value = key; sortDir.value = 1 }
}

function countByCat(cat) {
  return store.rings.filter(r => r['Risk Category'] === cat).length
}

// Pattern type labels (backend returns snake_case)
const PATTERN_LABELS = {
  cycle_length_3: 'Cycle ×3',
  fan_in:         'Fan-In',
  fan_out:        'Fan-Out',
  layered_shell:  'Layered Shell'
}
function fmtPattern(p) { return PATTERN_LABELS[p] || p }

function riskColor(score) {
  if (score >= 85) return 'var(--critical)'
  if (score >= 70) return 'var(--high)'
  if (score >= 50) return 'var(--medium)'
  return 'var(--low)'
}
</script>

<style scoped>
.table-wrap {
  background:var(--surface); border:1px solid var(--border);
  border-radius:16px; overflow:hidden;
}

/* Toolbar */
.toolbar {
  display:flex; align-items:center; justify-content:space-between;
  flex-wrap:wrap; gap:12px; padding:16px 20px;
  border-bottom:1px solid var(--border);
}

.search-box {
  display:flex; align-items:center; gap:8px;
  background:var(--bg); border:1px solid var(--border);
  border-radius:10px; padding:8px 12px; transition:border-color .2s;
}
.search-box.focused { border-color:rgba(124,58,237,.5); }
.search-box input {
  background:none; border:none; outline:none; color:var(--text);
  font-size:13px; font-family:var(--font-sans); width:clamp(110px,18vw,240px);
}
.search-box input::placeholder { color:var(--muted); }
.q-clear { background:none; border:none; color:var(--muted); cursor:pointer; font-size:12px; }
.q-clear:hover { color:var(--text); }

.pills { display:flex; gap:6px; flex-wrap:wrap; }
.pill {
  display:flex; align-items:center; gap:5px;
  padding:5px 12px; border-radius:50px; font-size:12px; font-weight:500;
  border:1px solid var(--border); background:transparent; color:var(--muted);
  cursor:pointer; transition:all .2s; font-family:var(--font-sans);
}
.pill:hover { color:var(--text); background:var(--surface2); }
.pill.active[data-cat="all"]      { background:var(--purple);   border-color:var(--purple);   color:#fff; }
.pill.active[data-cat="Critical"] { background:var(--critical); border-color:var(--critical); color:#fff; }
.pill.active[data-cat="High"]     { background:var(--high);     border-color:var(--high);     color:#fff; }
.pill.active[data-cat="Medium"]   { background:var(--medium);   border-color:var(--medium);   color:#000; }
.pill.active[data-cat="Low"]      { background:var(--low);      border-color:var(--low);      color:#000; }
.pill-n { background:rgba(255,255,255,.15); border-radius:50px; padding:0 5px; font-size:10px; }

/* Table */
.scroll { overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:13px; min-width:1000px; }
thead tr { border-bottom:1px solid var(--border); }
th {
  padding:11px 14px; text-align:left; font-size:11px; font-weight:600;
  text-transform:uppercase; letter-spacing:.8px; color:var(--muted);
  white-space:nowrap; cursor:pointer; user-select:none; transition:color .2s;
}
th:hover { color:var(--text); }
th.asc .si, th.desc .si { color:var(--accent); }
.si { margin-left:4px; opacity:.4; }
th.asc .si, th.desc .si { opacity:1; }

tbody tr { border-bottom:1px solid var(--border); }
tbody tr:last-child { border-bottom:none; }
.drow { transition:background .15s; }
.drow:hover { background:var(--surface2); }
td { padding:11px 14px; }

.mono { font-family:var(--font-mono); }
.dim  { color:var(--muted); font-size:12px; }

/* Ring ID */
.rid { font-size:11px; color:var(--accent); }

/* Pattern chip */
.pattern-chip {
  display:inline-block;
  background:rgba(124,58,237,.12); border:1px solid rgba(124,58,237,.2);
  color:var(--accent); padding:2px 9px; border-radius:6px; font-size:11px; font-weight:600;
  font-family:var(--font-mono);
}

/* Member count chip */
.chip-num {
  display:inline-block;
  background:rgba(192,132,252,.1); border:1px solid rgba(192,132,252,.2);
  color:var(--accent); padding:2px 9px; border-radius:50px; font-size:12px;
  font-family:var(--font-mono);
}

/* Score bar */
.score-cell { display:flex; align-items:center; gap:8px; }
.bar-track { width:52px; height:4px; background:var(--border); border-radius:2px; overflow:hidden; }
.bar-fill  { height:100%; border-radius:2px; transition:width .3s; }

/* Badge */
.badge {
  display:inline-flex; align-items:center; gap:4px;
  padding:3px 10px; border-radius:50px; font-size:11px; font-weight:600;
}
.badge::before { content:''; width:5px; height:5px; border-radius:50%; background:currentColor; }
.badge.Critical { background:rgba(239,68,68,.15);  color:var(--critical); }
.badge.High     { background:rgba(249,115,22,.15); color:var(--high);     }
.badge.Medium   { background:rgba(234,179,8,.15);  color:var(--medium);   }
.badge.Low      { background:rgba(34,197,94,.15);  color:var(--low);      }

/* Member IDs */
.mids { display:block; max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:11px; color:var(--muted); }

/* Table states */
.tstate { display:flex; align-items:center; justify-content:center; gap:12px; padding:56px 20px; color:var(--muted); font-size:14px; }
.tstate.err { color:var(--critical); }
.spin { width:26px; height:26px; border:2px solid var(--border); border-top-color:var(--purple); border-radius:50%; animation:spin .8s linear infinite; }

/* Pagination */
.pagination {
  display:flex; align-items:center; justify-content:center; gap:14px;
  padding:14px; border-top:1px solid var(--border);
}
.pg-btn {
  background:var(--surface2); border:1px solid var(--border); color:var(--text);
  width:32px; height:32px; border-radius:8px; cursor:pointer; font-size:14px; transition:all .2s;
}
.pg-btn:hover:not(:disabled) { background:var(--purple); border-color:var(--purple); }
.pg-btn:disabled { opacity:.3; cursor:not-allowed; }
.pg-info { font-size:13px; color:var(--muted); }

@media(max-width:640px){
  .toolbar { flex-direction:column; align-items:flex-start; }
  .search-box input { width:160px; }
}
</style>
