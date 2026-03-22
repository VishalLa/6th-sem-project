<template>
  <section class="page">
    <div class="header">
      <div>
        <h1 class="title">Metrics</h1>
        <p class="sub">
          <span v-if="lastLoaded">Last updated {{ lastLoaded }}</span>
          <span v-else>Transaction &amp; fraud ring analytics</span>
        </p>
      </div>
      <button class="btn-sec" @click="refresh" :disabled="refreshing">
        <span v-if="refreshing" class="spin-sm" />
        {{ refreshing ? 'Loading…' : '↺ Refresh' }}
      </button>
    </div>

    <!-- Loading skeleton -->
    <div v-if="refreshing" class="loading-state">
      <div class="spin-lg" />
      <p>Loading your data…</p>
    </div>

    <!-- No data at all -->
    <div v-else-if="!hasTxData && !hasRingData" class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
      <p>No data yet. Upload a CSV on the <RouterLink to="/" class="link">Home</RouterLink> page first.</p>
    </div>

    <template v-else>

      <!-- ── Upload info banner ── -->
      <div class="upload-banner" v-if="store.pipelineStats || hasTxData || hasRingData">
        <div class="banner-item">
          <span class="banner-icon">📁</span>
          <div>
            <p class="banner-val">{{ uploadInfo.filename }}</p>
            <p class="banner-key">Last uploaded file</p>
          </div>
        </div>
        <div class="banner-divider" />
        <div class="banner-item">
          <span class="banner-icon">🕐</span>
          <div>
            <p class="banner-val">{{ uploadInfo.time }}</p>
            <p class="banner-key">Upload time</p>
          </div>
        </div>
        <div class="banner-divider" />
        <div class="banner-item">
          <span class="banner-icon">⚡</span>
          <div>
            <p class="banner-val">
              {{ store.pipelineStats?.processing_time_seconds
                ? store.pipelineStats.processing_time_seconds + 's'
                : '—' }}
            </p>
            <p class="banner-key">Processing time</p>
          </div>
        </div>
        <div class="banner-divider" />
        <div class="banner-item">
          <span class="banner-icon">👤</span>
          <div>
            <p class="banner-val">
              {{ store.pipelineStats?.total_accounts_analyzed?.toLocaleString() || (hasTxData ? store.transactions.length.toLocaleString() : '—') }}
            </p>
            <p class="banner-key">Accounts analysed</p>
          </div>
        </div>
      </div>

      <!-- ── KPI row ── -->
      <div class="kpi-grid">
        <div class="kpi-card" v-if="hasTxData">
          <p class="kpi-label">Transactions</p>
          <p class="kpi-value">{{ m.count.toLocaleString() }}</p>
        </div>
        <div class="kpi-card" v-if="hasTxData">
          <p class="kpi-label">Total Volume</p>
          <p class="kpi-value">${{ fmtVolume(m.total) }}</p>
        </div>
        <div class="kpi-card" v-if="hasTxData">
          <p class="kpi-label">Avg Amount</p>
          <p class="kpi-value">${{ m.avg.toFixed(2) }}</p>
        </div>
        <div class="kpi-card" v-if="hasTxData">
          <p class="kpi-label">Max Amount</p>
          <p class="kpi-value">${{ m.max.toLocaleString() }}</p>
        </div>
        <div class="kpi-card" v-if="hasRingData">
          <p class="kpi-label">Fraud Rings</p>
          <p class="kpi-value" style="color:var(--critical)">{{ store.totalRings }}</p>
        </div>
        <div class="kpi-card" v-if="hasRingData">
          <p class="kpi-label">High + Critical</p>
          <p class="kpi-value" style="color:var(--high)">{{ store.criticalCount + store.highCount }}</p>
        </div>
        <div class="kpi-card" v-if="hasRingData">
          <p class="kpi-label">Avg Risk Score</p>
          <p class="kpi-value" style="color:var(--medium)">{{ store.avgScore }}</p>
        </div>
        <div class="kpi-card" v-if="store.pipelineStats?.suspicious_accounts_flagged">
          <p class="kpi-label">Flagged Accounts</p>
          <p class="kpi-value" style="color:var(--high)">
            {{ store.pipelineStats.suspicious_accounts_flagged.toLocaleString() }}
          </p>
        </div>
      </div>

      <!-- ── Charts ── -->
      <div class="charts-grid">

        <!-- Payment Methods -->
        <div class="chart-card" v-if="m?.methods && hasTxData">
          <p class="chart-title">Transactions by Payment Method</p>
          <div class="bar-chart">
            <div v-for="(val, key) in sortedMethods" :key="key" class="bar-row">
              <span class="bar-label">{{ key }}</span>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: pct(val, maxMethod) + '%', background: methodColor(key) }" />
              </div>
              <span class="bar-val">{{ val.toLocaleString() }}</span>
              <span class="bar-pct">{{ ((val / m.count) * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>

        <!-- KYC Status donut -->
        <div class="chart-card" v-if="m?.kyc && hasTxData">
          <p class="chart-title">KYC Status Distribution</p>
          <div class="donut-wrap">
            <svg viewBox="0 0 120 120" class="donut">
              <circle cx="60" cy="60" r="48" fill="none" stroke="rgba(255,255,255,.06)" stroke-width="16"/>
              <circle v-for="(seg, i) in kycSegments" :key="i"
                cx="60" cy="60" r="48" fill="none" :stroke="seg.color" stroke-width="16"
                :stroke-dasharray="`${seg.dash} ${seg.gap}`" :stroke-dashoffset="seg.offset"
                stroke-linecap="round" />
              <text x="60" y="56" text-anchor="middle" fill="var(--text)" font-size="15" font-weight="700">{{ m.count.toLocaleString() }}</text>
              <text x="60" y="70" text-anchor="middle" fill="var(--muted)" font-size="7">transactions</text>
            </svg>
            <div class="legend">
              <div v-for="seg in kycSegments" :key="seg.label" class="legend-row">
                <span class="dot" :style="{ background: seg.color }" />
                <span class="legend-label">{{ seg.label }}</span>
                <span class="legend-val">{{ seg.count.toLocaleString() }}</span>
                <span class="legend-pct">{{ ((seg.count / m.count) * 100).toFixed(1) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Sender Countries -->
        <div class="chart-card" v-if="m?.countries && hasTxData">
          <p class="chart-title">Top Sender Countries</p>
          <div class="bar-chart">
            <div v-for="(val, key) in topCountries" :key="key" class="bar-row">
              <span class="bar-label">{{ flagEmoji(key) }} {{ key }}</span>
              <div class="bar-track">
                <div class="bar-fill" style="background:var(--info)" :style="{ width: pct(val, maxCountry) + '%' }" />
              </div>
              <span class="bar-val">{{ val.toLocaleString() }}</span>
              <span class="bar-pct">{{ ((val / m.count) * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>

        <!-- Receiver Countries -->
        <div class="chart-card" v-if="receiverCountries && hasTxData">
          <p class="chart-title">Top Receiver Countries</p>
          <div class="bar-chart">
            <div v-for="(val, key) in receiverCountries" :key="key" class="bar-row">
              <span class="bar-label">{{ flagEmoji(key) }} {{ key }}</span>
              <div class="bar-track">
                <div class="bar-fill" style="background:var(--purple-light)" :style="{ width: pct(val, maxRecvCountry) + '%' }" />
              </div>
              <span class="bar-val">{{ val.toLocaleString() }}</span>
              <span class="bar-pct">{{ ((val / m.count) * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>

        <!-- Fraud Ring Risk categories -->
        <div class="chart-card" v-if="hasRingData">
          <p class="chart-title">Fraud Ring Risk Breakdown</p>
          <div class="risk-donut-wrap">
            <div class="risk-bars">
              <div v-for="cat in riskCats" :key="cat.label" class="risk-row">
                <div class="risk-left">
                  <span class="risk-dot" :style="{ background: `var(--${cat.color})` }" />
                  <span class="risk-label">{{ cat.label }}</span>
                </div>
                <div class="risk-track">
                  <div class="risk-fill"
                    :style="{ width: store.totalRings ? pct(cat.val, store.totalRings) + '%' : '0%',
                               background: `var(--${cat.color})` }" />
                </div>
                <span class="risk-val">{{ cat.val }}</span>
              </div>
            </div>
            <div class="ring-summary">
              <p class="ring-total">{{ store.totalRings }}</p>
              <p class="ring-label">total rings</p>
            </div>
          </div>
        </div>

        <!-- Amount distribution buckets -->
        <div class="chart-card" v-if="hasTxData">
          <p class="chart-title">Transaction Amount Ranges</p>
          <div class="bar-chart">
            <div v-for="bucket in amtBuckets" :key="bucket.label" class="bar-row">
              <span class="bar-label" style="font-size:11px">{{ bucket.label }}</span>
              <div class="bar-track">
                <div class="bar-fill" style="background:var(--accent)"
                  :style="{ width: pct(bucket.count, maxBucket) + '%' }" />
              </div>
              <span class="bar-val">{{ bucket.count.toLocaleString() }}</span>
              <span class="bar-pct">{{ ((bucket.count / m.count) * 100).toFixed(1) }}%</span>
            </div>
          </div>
        </div>

      </div>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useResultsStore } from '@/stores/results'
import { useAuthStore } from '@/stores/auth'
import { getMyTransactions, getMyFraudRings } from '@/services/api'

const store     = useResultsStore()
const auth      = useAuthStore()
const refreshing = ref(false)
const lastLoaded = ref('')

const hasTxData   = computed(() => store.transactions.length > 0)
const hasRingData = computed(() => store.totalRings > 0)
const m           = computed(() => store.txMetrics)

// Upload info derived from available data
const uploadInfo = computed(() => {
  const tx = store.transactions
  if (!tx.length) return { filename: '—', time: '—' }
  // Latest timestamp in the transactions
  const timestamps = tx.map(t => t.timestamp).filter(Boolean).sort()
  const latest = timestamps[timestamps.length - 1]
  const earliest = timestamps[0]
  return {
    filename: `${tx.length.toLocaleString()} transactions`,
    time: earliest ? new Date(earliest).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric'
    }) + ' – ' + new Date(latest).toLocaleDateString(undefined, {
      year: 'numeric', month: 'short', day: 'numeric'
    }) : '—',
  }
})

// Sorted methods (highest first)
const sortedMethods = computed(() => {
  if (!m.value) return {}
  return Object.fromEntries(Object.entries(m.value.methods).sort((a, b) => b[1] - a[1]))
})

const maxMethod   = computed(() => m.value ? Math.max(...Object.values(m.value.methods), 1) : 1)
const maxCountry  = computed(() => m.value ? Math.max(...Object.values(m.value.countries), 1) : 1)

const topCountries = computed(() => {
  if (!m.value) return {}
  return Object.fromEntries(Object.entries(m.value.countries).sort((a, b) => b[1] - a[1]).slice(0, 7))
})

// Receiver countries computed from raw transactions
const receiverCountriesRaw = computed(() => {
  const rc = {}
  store.transactions.forEach(t => {
    const c = t.receiver_country || '??'
    rc[c] = (rc[c] || 0) + 1
  })
  return Object.fromEntries(Object.entries(rc).sort((a, b) => b[1] - a[1]).slice(0, 7))
})
const receiverCountries = computed(() =>
  Object.keys(receiverCountriesRaw.value).length ? receiverCountriesRaw.value : null
)
const maxRecvCountry = computed(() =>
  receiverCountries.value ? Math.max(...Object.values(receiverCountries.value), 1) : 1
)

// Amount buckets
const amtBuckets = computed(() => {
  if (!store.transactions.length) return []
  const buckets = [
    { label: '$0–100',     min: 0,    max: 100,   count: 0 },
    { label: '$100–500',   min: 100,  max: 500,   count: 0 },
    { label: '$500–1K',    min: 500,  max: 1000,  count: 0 },
    { label: '$1K–5K',     min: 1000, max: 5000,  count: 0 },
    { label: '$5K+',       min: 5000, max: Infinity, count: 0 },
  ]
  store.transactions.forEach(t => {
    const a = Number(t.amount) || 0
    const b = buckets.find(b => a >= b.min && a < b.max)
    if (b) b.count++
  })
  return buckets.filter(b => b.count > 0)
})
const maxBucket = computed(() => Math.max(...amtBuckets.value.map(b => b.count), 1))

const METHOD_COLORS = { Crypto: '#a855f7', Wire: '#38bdf8', ACH: '#22c55e', P2P: '#f97316' }
function methodColor(k) { return METHOD_COLORS[k] || '#7c3aed' }

function pct(val, max) { return max ? Math.min(Math.round((val / max) * 100), 100) : 0 }

function fmtVolume(v) {
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + 'M'
  if (v >= 1_000)     return (v / 1_000).toFixed(1) + 'K'
  return v.toFixed(2)
}

function flagEmoji(code) {
  if (!code || code.length !== 2) return ''
  return String.fromCodePoint(...[...code.toUpperCase()].map(c => 0x1F1E6 + c.charCodeAt(0) - 65))
}

const KYC_COLORS = { Verified: '#22c55e', Pending: '#eab308', None: '#ef4444', nan: '#ef4444' }
const CIRC = 2 * Math.PI * 48

const kycSegments = computed(() => {
  if (!m.value) return []
  const entries = Object.entries(m.value.kyc)
  const total = entries.reduce((s, [, v]) => s + v, 0)
  let offset = -0.25 * CIRC
  return entries.map(([label, count]) => {
    const dash = (count / total) * CIRC - 2
    const seg = { label, count, color: KYC_COLORS[label] || '#94a3b8', dash, gap: CIRC - dash, offset }
    offset -= (count / total) * CIRC
    return seg
  })
})

const riskCats = computed(() => [
  { label: 'Critical', val: store.criticalCount, color: 'critical' },
  { label: 'High',     val: store.highCount,     color: 'high'     },
  { label: 'Medium',   val: store.mediumCount,   color: 'medium'   },
  { label: 'Low',      val: store.lowCount,      color: 'low'      },
])

async function refresh() {
  refreshing.value = true
  try {
    // Load BOTH transactions AND fraud rings in parallel
    const [txRes, ringsRes] = await Promise.all([
      getMyTransactions(1000, 0),
      getMyFraudRings(500, 0),
    ])
    const txList   = txRes.data?.transactions   || []
    const ringList = ringsRes.data?.fraud_rings || []

    if (txList.length)   store.setTransactions(txList)
    if (ringList.length) store.setFromDBRings(ringList)

    lastLoaded.value = new Date().toLocaleTimeString()
  } catch (e) {
    console.error('Metrics refresh failed:', e)
  } finally {
    refreshing.value = false
  }
}

onMounted(() => {
  // Load if either transactions OR rings are missing
  if (!hasTxData.value || !hasRingData.value) refresh()
  else lastLoaded.value = new Date().toLocaleTimeString()
})
</script>

<style scoped>
.page { min-height: 100vh; padding: 80px clamp(16px,4vw,48px) 60px; }

.header {
  display: flex; align-items: flex-start; justify-content: space-between;
  flex-wrap: wrap; gap: 16px; margin-bottom: 24px;
}
.title { font-family: var(--font-mono); font-size: clamp(20px,3vw,28px); font-weight: 700; margin-bottom: 4px; }
.sub   { color: var(--muted); font-size: 13px; }

.btn-sec {
  display: flex; align-items: center; gap: 6px;
  background: var(--surface); border: 1px solid var(--border);
  color: var(--muted); padding: 9px 18px; border-radius: 10px;
  font-size: 13px; font-weight: 600; cursor: pointer; transition: all .2s;
}
.btn-sec:hover:not(:disabled) { color: var(--text); border-color: var(--purple); }
.btn-sec:disabled { opacity: .4; cursor: not-allowed; }
.spin-sm { width: 13px; height: 13px; border: 2px solid rgba(255,255,255,.2); border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite; display: inline-block; }

.loading-state { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; height: 300px; color: var(--muted); }
.spin-lg { width: 40px; height: 40px; border: 3px solid var(--border); border-top-color: var(--purple); border-radius: 50%; animation: spin .8s linear infinite; }

.empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; height: 300px; color: var(--muted); text-align: center; font-size: 14px; }
.empty svg { width: 52px; height: 52px; stroke: rgba(124,58,237,.3); }
.link { color: var(--accent); text-decoration: underline; }

/* Upload info banner */
.upload-banner {
  display: flex; align-items: center; flex-wrap: wrap; gap: 0;
  background: rgba(124,58,237,.07); border: 1px solid rgba(124,58,237,.2);
  border-radius: 14px; padding: 16px 24px; margin-bottom: 24px;
}
.banner-item { display: flex; align-items: center; gap: 12px; padding: 4px 20px; flex: 1; min-width: 160px; }
.banner-icon { font-size: 20px; }
.banner-val { font-size: 14px; font-weight: 700; color: var(--text); }
.banner-key { font-size: 11px; color: var(--muted); margin-top: 2px; text-transform: uppercase; letter-spacing: .5px; }
.banner-divider { width: 1px; height: 40px; background: rgba(255,255,255,.08); flex-shrink: 0; }

/* KPI grid */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 24px; }
.kpi-card { background: var(--surface); border: 1px solid var(--border); border-radius: 14px; padding: 18px 20px; transition: all .2s; }
.kpi-card:hover { border-color: rgba(124,58,237,.3); transform: translateY(-2px); }
.kpi-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .8px; font-weight: 600; margin-bottom: 8px; }
.kpi-value { font-size: clamp(20px,2.5vw,28px); font-weight: 700; font-family: var(--font-mono); }

/* Charts grid */
.charts-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; }
.chart-card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 24px; }
.chart-title { font-size: 14px; font-weight: 700; margin-bottom: 20px; color: var(--text); }

/* Bar chart */
.bar-chart { display: flex; flex-direction: column; gap: 11px; }
.bar-row { display: grid; grid-template-columns: 72px 1fr 48px 44px; align-items: center; gap: 8px; }
.bar-label { font-size: 12px; font-weight: 600; color: var(--muted); text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.bar-track { height: 8px; background: rgba(255,255,255,.06); border-radius: 4px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 4px; transition: width .6s cubic-bezier(.4,0,.2,1); }
.bar-val { font-size: 12px; color: var(--text); font-family: var(--font-mono); text-align: right; }
.bar-pct { font-size: 11px; color: var(--muted); }

/* Donut */
.donut-wrap { display: flex; align-items: center; gap: 24px; }
.donut { width: 130px; height: 130px; flex-shrink: 0; transform: rotate(-90deg); }
.legend { display: flex; flex-direction: column; gap: 10px; flex: 1; }
.legend-row { display: grid; grid-template-columns: 10px 1fr auto auto; align-items: center; gap: 8px; font-size: 13px; }
.dot { width: 10px; height: 10px; border-radius: 50%; }
.legend-label { color: var(--muted); }
.legend-val { font-weight: 700; font-family: var(--font-mono); }
.legend-pct { font-size: 11px; color: var(--muted); width: 40px; text-align: right; }

/* Risk breakdown */
.risk-donut-wrap { display: flex; align-items: center; gap: 20px; }
.risk-bars { flex: 1; display: flex; flex-direction: column; gap: 12px; }
.risk-row { display: grid; grid-template-columns: 100px 1fr 36px; align-items: center; gap: 10px; }
.risk-left { display: flex; align-items: center; gap: 7px; }
.risk-dot { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
.risk-label { font-size: 12px; font-weight: 600; color: var(--muted); }
.risk-track { height: 10px; background: rgba(255,255,255,.06); border-radius: 5px; overflow: hidden; }
.risk-fill { height: 100%; border-radius: 5px; transition: width .6s cubic-bezier(.4,0,.2,1); }
.risk-val { font-size: 13px; font-weight: 700; font-family: var(--font-mono); text-align: right; }
.ring-summary { text-align: center; flex-shrink: 0; padding: 12px 16px; background: rgba(239,68,68,.07); border: 1px solid rgba(239,68,68,.15); border-radius: 12px; }
.ring-total { font-size: 28px; font-weight: 700; font-family: var(--font-mono); color: var(--critical); }
.ring-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; margin-top: 2px; }

@media (max-width: 600px) {
  .upload-banner { flex-direction: column; gap: 12px; }
  .banner-divider { width: 100%; height: 1px; }
  .banner-item { padding: 0; }
  .bar-row { grid-template-columns: 56px 1fr 44px; }
  .bar-pct { display: none; }
}
</style>
