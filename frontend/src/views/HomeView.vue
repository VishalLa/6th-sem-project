<template>
  <section class="home">

    <div class="badge"><span class="bdot"/>&nbsp;Try FlowMatrix Now</div>
    <h1 class="hero-title">FL<span class="o">O</span>W-MAT<span class="r">R</span>IX</h1>
    <p class="hero-sub">
      Upload your transaction CSV to instantly detect fraud rings, suspicious accounts,
      and money laundering patterns using graph analysis.
    </p>

    <!-- ── Upload card ── -->
    <div class="upload-card">

      <!-- Drop zone -->
      <div class="upload-area"
        :class="{ over: dragging, filled: !!file }"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
        @click="!file && inputRef?.click()"
      >
        <input ref="inputRef" type="file" accept=".csv" class="hidden" @change="onPick" />

        <template v-if="!file">
          <div class="dz-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </div>
          <p class="dz-title">Drop your CSV here</p>
          <p class="dz-hint">or <span class="dz-link" @click.stop="inputRef?.click()">browse files</span> · .csv only</p>
        </template>

        <template v-else>
          <div class="file-ready">
            <div class="file-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/>
                <polyline points="13 2 13 9 20 9"/>
              </svg>
            </div>
            <div class="file-info">
              <p class="file-name">{{ file.name }}</p>
              <p class="file-size">{{ fmtSize(file.size) }} · ready to process</p>
            </div>
            <button class="file-remove" @click.stop="file = null; result = null" title="Remove">✕</button>
          </div>
        </template>
      </div>

      <!-- Run button -->
      <button class="btn-detect" :disabled="loading || !file" @click="run">
        <span v-if="loading" class="bspin"/>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:16px;height:16px">
          <polygon points="5 3 19 12 5 21 5 3"/>
        </svg>
        {{ loading ? 'Running Pipeline…' : 'Detect & Analyse' }}
      </button>

      <!-- Progress steps during loading -->
      <Transition name="fade-up">
        <div v-if="loading" class="progress-steps">
          <div v-for="(step, i) in steps" :key="i" class="step" :class="stepClass(i)">
            <div class="step-dot">
              <span v-if="currentStep > i" class="check">✓</span>
              <span v-else-if="currentStep === i" class="spin-dot"/>
              <span v-else class="num">{{ i + 1 }}</span>
            </div>
            <span class="step-label">{{ step }}</span>
          </div>
        </div>
      </Transition>

      <!-- Error message -->
      <Transition name="fade-up">
        <p v-if="errorMsg" class="error-msg">{{ errorMsg }}</p>
      </Transition>
    </div>

    <!-- ── Result summary card (shown after successful detection) ── -->
    <Transition name="slide-up">
      <div v-if="result" class="result-card">
        <div class="result-header">
          <div class="result-title-row">
            <span class="result-check">✓</span>
            <div>
              <p class="result-title">Detection Complete</p>
              <p class="result-sub">{{ result.filename }} · processed {{ result.processedAt }}</p>
            </div>
          </div>
          <div class="result-nav-btns">
            <RouterLink to="/summary" class="btn-nav">
              View Summary →
            </RouterLink>
            <RouterLink to="/metrics" class="btn-nav secondary">
              Metrics →
            </RouterLink>
            <RouterLink to="/batches" class="btn-nav secondary">
              📁 Batches →
            </RouterLink>
          </div>
        </div>

        <!-- Stats grid -->
        <div class="result-stats">
          <div class="rs-item">
            <p class="rs-val">{{ result.transactions.toLocaleString() }}</p>
            <p class="rs-key">Transactions</p>
          </div>
          <div class="rs-item">
            <p class="rs-val">${{ fmtVolume(result.totalAmount) }}</p>
            <p class="rs-key">Total Volume</p>
          </div>
          <div class="rs-item">
            <p class="rs-val" :style="result.fraudRings > 0 ? 'color:var(--critical)' : 'color:var(--low)'">
              {{ result.fraudRings.toLocaleString() }}
            </p>
            <p class="rs-key">Fraud Rings</p>
          </div>
          <div class="rs-item" v-if="result.flaggedAccounts">
            <p class="rs-val" style="color:var(--high)">{{ result.flaggedAccounts.toLocaleString() }}</p>
            <p class="rs-key">Flagged Accounts</p>
          </div>
          <div class="rs-item" v-if="result.processingTime">
            <p class="rs-val">{{ result.processingTime }}s</p>
            <p class="rs-key">Processing Time</p>
          </div>
          <div class="rs-item" v-if="result.avgRiskScore">
            <p class="rs-val" style="color:var(--medium)">{{ result.avgRiskScore }}</p>
            <p class="rs-key">Avg Risk Score</p>
          </div>
        </div>

        <!-- Risk breakdown mini-bars -->
        <div class="result-risk" v-if="result.fraudRings > 0">
          <div class="risk-mini" v-for="cat in result.riskBreakdown" :key="cat.label">
            <span class="risk-dot" :style="{ background: `var(--${cat.color})` }"/>
            <span class="risk-label">{{ cat.label }}</span>
            <span class="risk-count" :style="{ color: `var(--${cat.color})` }">{{ cat.count }}</span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- Feature cards -->
    <div class="features">
      <div v-for="f in features" :key="f.title" class="feat">
        <div class="feat-icon" v-html="f.icon"/>
        <p class="feat-title">{{ f.title }}</p>
        <p class="feat-desc">{{ f.desc }}</p>
      </div>
    </div>

  </section>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { uploadFullPipeline, getMyFraudRings, getMyTransactions, getMyBatches } from '@/services/api'
import { useResultsStore } from '@/stores/results'

const store    = useResultsStore()
const file     = ref(null)
const inputRef = ref(null)
const dragging = ref(false)
const loading  = ref(false)
const errorMsg = ref('')
const result   = ref(null)
const currentStep = ref(-1)

const steps = [
  'Uploading CSV…',
  'Running fraud detection…',
  'Saving to database…',
  'Building embeddings…',
  'Loading results…',
]

function fmtSize(b) {
  if (b < 1024) return b + ' B'
  if (b < 1048576) return (b / 1024).toFixed(1) + ' KB'
  return (b / 1048576).toFixed(1) + ' MB'
}
function fmtVolume(v) {
  if (!v) return '0'
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(2) + 'M'
  if (v >= 1_000)     return (v / 1_000).toFixed(1) + 'K'
  return v.toFixed(2)
}

function onPick(e) { if (e.target.files[0]) { file.value = e.target.files[0]; result.value = null } }
function onDrop(e) {
  dragging.value = false
  const f = e.dataTransfer.files[0]
  if (f && f.name.endsWith('.csv')) { file.value = f; result.value = null }
  else errorMsg.value = '⚠ Please drop a .csv file.'
}

function startProgress() {
  currentStep.value = 0
  const delays = [0, 2500, 6000, 10000]
  delays.forEach((d, i) => setTimeout(() => { if (loading.value) currentStep.value = i }, d))
}
function stepClass(i) {
  if (currentStep.value > i)  return 'done'
  if (currentStep.value === i) return 'active'
  return 'pending'
}

async function run() {
  if (!file.value) return
  loading.value  = true
  errorMsg.value = ''
  result.value   = null
  currentStep.value = -1
  startProgress()

  const uploadedFileName = file.value.name

  try {
    const res  = await uploadFullPipeline(file.value)
    const data = res.data

    currentStep.value = 4

    // Normalise whatever shape the pipeline returned
    if (data) {
      const keys = Object.keys(data)
      const firstVal = data[keys[0]]
      if (firstVal && (firstVal.report || firstVal.summary)) store.setFromDetection(data)
      else if (data.fraud_rings_summary || data.detection_results) store.setFromFullPipeline(data)
      else if (data.results) store.setFromDetection(data.results)
    }

    // Always pull canonical data from DB
    const [ringsRes, txRes, batchesRes] = await Promise.all([
      getMyFraudRings(500, 0),
      getMyTransactions(1000, 0),
      getMyBatches(100, 0),
    ])
    const ringList = ringsRes.data?.fraud_rings || []
    const txList   = txRes.data?.transactions   || []

    if (ringList.length) store.setFromDBRings(ringList)
    if (txList.length)   store.setTransactions(txList)

    // Refresh batch list so /batches page is up to date
    store.setFromBatches(batchesRes.data?.batches || [])

    // Build result summary card
    const amounts  = txList.map(t => Number(t.amount) || 0)
    const total    = amounts.reduce((a, b) => a + b, 0)
    const ps       = store.pipelineStats

    result.value = {
      filename:        uploadedFileName,
      processedAt:     new Date().toLocaleString(),
      transactions:    txList.length  || ps?.total_accounts_analyzed || 0,
      totalAmount:     total,
      fraudRings:      ringList.length,
      flaggedAccounts: ps?.suspicious_accounts_flagged || 0,
      processingTime:  ps?.processing_time_seconds || null,
      avgRiskScore:    store.avgScore !== '—' ? store.avgScore : null,
      riskBreakdown: [
        { label: 'Critical', count: store.criticalCount, color: 'critical' },
        { label: 'High',     count: store.highCount,     color: 'high'     },
        { label: 'Medium',   count: store.mediumCount,   color: 'medium'   },
        { label: 'Low',      count: store.lowCount,      color: 'low'      },
      ].filter(c => c.count > 0),
    }

    loading.value = false

  } catch (e) {
    loading.value = false
    currentStep.value = -1
    errorMsg.value = `✗ ${e.response?.data?.detail || e.message}`
    console.error('Pipeline error:', e)
  }
}

const features = [
  {
    title: 'Cycle Detection',
    desc: 'Finds 3-node triangular transfer rings (A→B→C→A) — classic layering patterns.',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>`
  },
  {
    title: 'Smurfing / Fan Detection',
    desc: 'Flags accounts with abnormal fan-in or fan-out degree above threshold.',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><line x1="12" y1="7" x2="5" y2="17"/><line x1="12" y1="7" x2="19" y2="17"/></svg>`
  },
  {
    title: 'Layered Shell Analysis',
    desc: 'Uncovers multi-hop laundering chains passing through low-degree intermediaries.',
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`
  }
]
</script>

<style scoped>
.home {
  min-height: 100vh; padding: 80px clamp(16px,4vw,48px) 60px;
  display: flex; flex-direction: column; align-items: center;
  text-align: center; gap: 0;
}

.badge {
  display: inline-flex; align-items: center; gap: 6px;
  background: rgba(124,58,237,.12); border: 1px solid rgba(124,58,237,.3);
  color: var(--accent); font-size: 12px; font-weight: 600; letter-spacing: .5px;
  padding: 6px 16px; border-radius: 50px; margin-bottom: 26px;
  animation: fadeUp .5s ease both;
}
.bdot { width: 6px; height: 6px; background: var(--accent); border-radius: 50%; animation: pulse 2s infinite; }

.hero-title {
  font-family: var(--font-mono); font-size: clamp(40px,9vw,100px);
  font-weight: 700; line-height: 1; letter-spacing: clamp(-2px,-.3vw,-3px);
  margin-bottom: 22px; animation: fadeUp .5s .08s ease both;
}
.o { color: var(--purple-light); }
.r { color: var(--accent); }

.hero-sub {
  max-width: 560px; color: var(--muted); font-size: clamp(14px,1.8vw,16px);
  line-height: 1.75; margin-bottom: 36px; animation: fadeUp .5s .16s ease both;
}

/* Upload card */
.upload-card {
  width: 100%; max-width: 580px; display: flex; flex-direction: column;
  gap: 16px; animation: fadeUp .5s .22s ease both; margin-bottom: 12px;
}

.upload-area {
  background: var(--surface); border: 2px dashed rgba(124,58,237,.35);
  border-radius: 20px; padding: 36px 28px; cursor: pointer;
  transition: all .3s; text-align: center;
}
.upload-area:hover, .upload-area.over {
  border-color: var(--purple-light); background: rgba(124,58,237,.08);
  box-shadow: 0 0 32px var(--purple-glow);
}
.upload-area.filled { border-style: solid; border-color: rgba(124,58,237,.4); cursor: default; }
.hidden { display: none; }

.dz-icon {
  width: 52px; height: 52px; margin: 0 auto 14px;
  background: rgba(124,58,237,.2); border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
}
.dz-icon svg { width: 26px; height: 26px; stroke: var(--accent); }
.dz-title  { font-size: 15px; font-weight: 600; margin-bottom: 6px; }
.dz-hint   { font-size: 12px; color: var(--muted); }
.dz-link   { color: var(--accent); cursor: pointer; text-decoration: underline; }

.file-ready { display: flex; align-items: center; gap: 14px; text-align: left; }
.file-icon {
  width: 44px; height: 44px; flex-shrink: 0; border-radius: 10px;
  background: rgba(124,58,237,.15); display: flex; align-items: center; justify-content: center;
}
.file-icon svg { width: 22px; height: 22px; stroke: var(--accent); }
.file-info { flex: 1; min-width: 0; }
.file-name { font-size: 14px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-size { font-size: 12px; color: var(--muted); margin-top: 2px; }
.file-remove {
  background: rgba(239,68,68,.1); border: 1px solid rgba(239,68,68,.2);
  color: var(--critical); width: 28px; height: 28px; border-radius: 7px;
  font-size: 12px; flex-shrink: 0; transition: all .2s;
}
.file-remove:hover { background: rgba(239,68,68,.25); }

.btn-detect {
  display: flex; align-items: center; justify-content: center; gap: 10px;
  background: linear-gradient(135deg, var(--purple), var(--purple-light));
  color: #fff; border: none; padding: 15px 52px; border-radius: 50px;
  font-size: 16px; font-weight: 700; cursor: pointer; transition: all .3s;
  box-shadow: 0 0 32px var(--purple-glow); align-self: center;
}
.btn-detect:hover:not(:disabled) { transform: translateY(-2px); box-shadow: 0 0 50px var(--purple-glow); }
.btn-detect:disabled { opacity: .55; cursor: not-allowed; transform: none; }
.bspin { width: 16px; height: 16px; border: 2px solid rgba(255,255,255,.3); border-top-color: #fff; border-radius: 50%; animation: spin .7s linear infinite; }

/* Progress steps */
.progress-steps {
  display: flex; flex-direction: column; gap: 10px;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 14px; padding: 18px 22px; text-align: left;
}
.step { display: flex; align-items: center; gap: 12px; font-size: 13px; color: var(--muted); transition: all .3s; }
.step.active { color: var(--text); }
.step.done   { color: var(--low); }
.step-dot {
  width: 24px; height: 24px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(255,255,255,.05); border: 1px solid var(--border); font-size: 11px;
}
.step.active .step-dot { border-color: var(--purple); background: rgba(124,58,237,.15); }
.step.done   .step-dot { border-color: var(--low);    background: rgba(34,197,94,.15);  color: var(--low); }
.check    { font-size: 11px; font-weight: 700; }
.spin-dot { width: 10px; height: 10px; border: 2px solid rgba(124,58,237,.3); border-top-color: var(--purple); border-radius: 50%; animation: spin .7s linear infinite; }
.num      { font-size: 11px; color: var(--muted); }

.error-msg { color: var(--critical); font-size: 13px; font-weight: 500; }

/* Result card */
.result-card {
  width: 100%; max-width: 700px; margin-bottom: 20px;
  background: var(--surface); border: 1px solid rgba(34,197,94,.25);
  border-radius: 20px; overflow: hidden;
  box-shadow: 0 0 40px rgba(34,197,94,.08);
}
.result-header {
  display: flex; align-items: center; justify-content: space-between;
  flex-wrap: wrap; gap: 14px;
  padding: 20px 24px; border-bottom: 1px solid var(--border);
  background: rgba(34,197,94,.05);
}
.result-title-row { display: flex; align-items: center; gap: 14px; }
.result-check {
  width: 36px; height: 36px; border-radius: 50%; flex-shrink: 0;
  background: rgba(34,197,94,.15); border: 1px solid rgba(34,197,94,.3);
  color: var(--low); font-size: 16px; display: flex; align-items: center; justify-content: center;
}
.result-title { font-size: 15px; font-weight: 700; }
.result-sub   { font-size: 12px; color: var(--muted); margin-top: 2px; }
.result-nav-btns { display: flex; gap: 8px; }
.btn-nav {
  padding: 8px 18px; border-radius: 10px; font-size: 13px; font-weight: 600;
  background: var(--purple); color: #fff; border: none; cursor: pointer;
  transition: all .2s; box-shadow: 0 0 16px var(--purple-glow);
}
.btn-nav:hover { background: var(--purple-light); }
.btn-nav.secondary { background: var(--surface2); border: 1px solid var(--border); color: var(--muted); box-shadow: none; }
.btn-nav.secondary:hover { color: var(--text); border-color: var(--purple); }

/* Result stats grid */
.result-stats {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 0; padding: 0;
}
.rs-item {
  padding: 18px 20px; border-right: 1px solid var(--border); text-align: center;
}
.rs-item:last-child { border-right: none; }
.rs-val { font-size: clamp(18px,2vw,24px); font-weight: 700; font-family: var(--font-mono); }
.rs-key { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .5px; margin-top: 4px; }

/* Risk breakdown row */
.result-risk {
  display: flex; align-items: center; gap: 20px; flex-wrap: wrap;
  padding: 14px 24px; background: rgba(239,68,68,.04);
  border-top: 1px solid var(--border);
}
.risk-mini  { display: flex; align-items: center; gap: 7px; font-size: 13px; }
.risk-dot   { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.risk-label { color: var(--muted); }
.risk-count { font-weight: 700; font-family: var(--font-mono); }

/* Features */
.features {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr));
  gap: 16px; width: 100%; max-width: 760px; margin-top: 40px;
  animation: fadeUp .5s .38s ease both;
}
.feat {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 16px; padding: 24px 20px; text-align: left; transition: all .2s;
}
.feat:hover { border-color: rgba(124,58,237,.3); background: var(--surface2); transform: translateY(-2px); }
.feat-icon {
  width: 40px; height: 40px; background: rgba(124,58,237,.15);
  border-radius: 10px; display: flex; align-items: center; justify-content: center; margin-bottom: 12px;
}
.feat-icon :deep(svg) { width: 20px; height: 20px; stroke: var(--accent); }
.feat-title { font-size: 14px; font-weight: 700; margin-bottom: 6px; }
.feat-desc  { font-size: 13px; color: var(--muted); line-height: 1.6; }

/* Transitions */
.fade-up-enter-active, .fade-up-leave-active { transition: all .3s ease; }
.fade-up-enter-from,  .fade-up-leave-to      { opacity: 0; transform: translateY(8px); }

.slide-up-enter-active { transition: all .4s cubic-bezier(.4,0,.2,1); }
.slide-up-leave-active { transition: all .25s ease; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(20px); }

@media(max-width:480px) {
  .features { grid-template-columns: 1fr; }
  .btn-detect { padding: 13px 36px; font-size: 15px; }
  .result-stats { grid-template-columns: repeat(2, 1fr); }
  .rs-item { border-bottom: 1px solid var(--border); }
}
</style>
