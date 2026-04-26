<template>
  <section class="page">

    <!-- ── Header ── -->
    <div class="header">
      <div>
        <h1 class="title">Upload Batches</h1>
        <p class="sub">{{ store.batches.length }} batch{{ store.batches.length !== 1 ? 'es' : '' }} · manage your uploaded files</p>
      </div>
      <button class="btn-sec" @click="loadBatches" :disabled="loading">
        <span v-if="loading" class="spin-sm" />
        {{ loading ? 'Loading…' : '↺ Refresh' }}
      </button>
    </div>

    <!-- ── Loading ── -->
    <div v-if="loading" class="loading-state">
      <div class="spin-lg" />
      <p>Fetching your batches…</p>
    </div>

    <!-- ── Empty ── -->
    <div v-else-if="!store.batches.length" class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/>
      </svg>
      <p>No uploads yet. Go to the <RouterLink to="/" class="link">Home</RouterLink> page to upload a CSV.</p>
    </div>

    <!-- ── Batches table ── -->
    <template v-else>
      <div class="table-wrap">
        <table class="batch-table">
          <thead>
            <tr>
              <th>Batch ID</th>
              <th>Uploaded</th>
              <th>Transactions</th>
              <th>Fraud Rings</th>
              <th class="actions-col">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="b in store.batches"
              :key="b.batch_id"
              :class="{ active: store.activeBatchId === b.batch_id }"
              @click="selectBatch(b.batch_id)"
            >
              <td class="mono dim id-cell">
                <span class="id-dot" :class="store.activeBatchId === b.batch_id ? 'active' : ''" />
                {{ b.batch_id.slice(0, 8) }}…
              </td>
              <td class="dim">{{ fmtDate(b.uploaded_at) }}</td>
              <td class="mono">{{ (b.transaction_count ?? '—').toLocaleString() }}</td>
              <td>
                <span v-if="b.fraud_ring_count > 0" class="ring-badge danger">{{ b.fraud_ring_count }}</span>
                <span v-else class="ring-badge safe">0</span>
              </td>
              <td class="actions-cell" @click.stop>
                <button class="icon-btn" title="Load into Charts" @click="loadIntoCharts(b.batch_id)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
                </button>
                <button class="icon-btn" title="Download JSON" @click="dlJson(b.batch_id)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                </button>
                <button class="icon-btn" title="Download CSV" @click="dlCsv(b.batch_id)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="9" x2="9" y2="21"/></svg>
                </button>
                <button class="icon-btn danger" title="Delete Batch" @click="confirmDelete(b.batch_id)">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4h6v2"/></svg>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── Per-batch detail panel ── -->
      <Transition name="slide-up">
        <div v-if="store.activeBatchId && detail" class="detail-panel">

          <div class="detail-header">
            <div>
              <p class="detail-title">Batch Details</p>
              <p class="detail-sub mono">{{ store.activeBatchId }}</p>
            </div>
            <div class="detail-actions">
              <button class="btn-sec" @click="loadIntoCharts(store.activeBatchId)">
                📊 Load into Charts
              </button>
              <RouterLink to="/metrics" class="btn-nav">View Metrics →</RouterLink>
            </div>
          </div>

          <!-- Fraud Rings tab -->
          <div v-if="detail.rings.length" class="detail-section">
            <p class="section-label">Fraud Rings ({{ detail.rings.length }})</p>
            <div class="mini-table-wrap">
              <table class="mini-table">
                <thead>
                  <tr><th>Ring ID</th><th>Pattern</th><th>Members</th><th>Risk Score</th><th>Category</th></tr>
                </thead>
                <tbody>
                  <tr v-for="r in detail.rings" :key="r.ring_id">
                    <td class="mono dim">{{ r.ring_id }}</td>
                    <td><span class="pattern-tag">{{ r.pattern_type }}</span></td>
                    <td class="mono">{{ r.member_count }}</td>
                    <td class="mono" :style="riskColor(r.risk_score)">{{ Number(r.risk_score).toFixed(1) }}</td>
                    <td><span class="risk-badge" :class="r.risk_category?.toLowerCase()">{{ r.risk_category }}</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
          <div v-else class="no-data-row">No fraud rings detected in this batch.</div>

          <!-- Transactions preview -->
          <div v-if="detail.transactions.length" class="detail-section">
            <p class="section-label">Transactions preview (first {{ detail.transactions.length }})</p>
            <div class="mini-table-wrap">
              <table class="mini-table">
                <thead>
                  <tr><th>TXN ID</th><th>Sender</th><th>Receiver</th><th>Amount</th><th>Timestamp</th></tr>
                </thead>
                <tbody>
                  <tr v-for="t in detail.transactions" :key="t.transaction_id">
                    <td class="mono dim">{{ t.transaction_id }}</td>
                    <td class="mono">{{ t.sender }}</td>
                    <td class="mono">{{ t.receiver }}</td>
                    <td class="mono">${{ Number(t.amount).toFixed(2) }}</td>
                    <td class="dim">{{ fmtDate(t.timestamp) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </Transition>
    </template>

    <!-- ── Delete confirmation modal ── -->
    <Transition name="fade">
      <div v-if="deleteModal.show" class="modal-backdrop" @click.self="deleteModal.show = false">
        <div class="modal">
          <div class="modal-icon">🗑</div>
          <p class="modal-title">Delete Batch?</p>
          <p class="modal-body">
            This will permanently remove all transactions, fraud rings, JSON report, and FAISS index
            for batch <code>{{ deleteModal.batchId?.slice(0, 8) }}…</code>. This cannot be undone.
          </p>
          <div class="modal-actions">
            <button class="btn-cancel" @click="deleteModal.show = false">Cancel</button>
            <button class="btn-danger" :disabled="deleteModal.loading" @click="doDelete">
              <span v-if="deleteModal.loading" class="spin-sm" /> Delete
            </button>
          </div>
          <p v-if="deleteModal.error" class="modal-error">{{ deleteModal.error }}</p>
        </div>
      </div>
    </Transition>

    <!-- ── Toast notification ── -->
    <Transition name="toast">
      <div v-if="toast.show" class="toast" :class="toast.type">{{ toast.msg }}</div>
    </Transition>

  </section>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useResultsStore } from '@/stores/results'
import {
  getMyBatches,
  getBatchTransactions,
  getBatchFraudRings,
  downloadBatchJson,
  downloadBatchCsv,
  deleteBatch,
  getMyFraudRings,
  getMyTransactions,
} from '@/services/api'

const store   = useResultsStore()
const loading = ref(false)
const detail  = ref(null)
const detailLoading = ref(false)

const deleteModal = reactive({ show: false, batchId: null, loading: false, error: '' })
const toast       = reactive({ show: false, msg: '', type: 'success' })

// ── Helpers ────────────────────────────────────────────────────────────────
function fmtDate(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) }
  catch { return ts }
}

function riskColor(score) {
  const s = Number(score)
  if (s >= 75) return 'color: var(--critical)'
  if (s >= 50) return 'color: var(--high)'
  if (s >= 25) return 'color: var(--medium)'
  return 'color: var(--low)'
}

function showToast(msg, type = 'success') {
  toast.msg = msg; toast.type = type; toast.show = true
  setTimeout(() => { toast.show = false }, 3200)
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a   = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

// ── Data loading ───────────────────────────────────────────────────────────
async function loadBatches() {
  loading.value = true
  try {
    const res = await getMyBatches(100, 0)
    store.setFromBatches(res.data?.batches || [])
    if (store.batches.length && !store.activeBatchId) {
      selectBatch(store.batches[0].batch_id)
    }
  } catch (e) {
    showToast('Failed to load batches: ' + (e.response?.data?.detail || e.message), 'error')
  } finally {
    loading.value = false
  }
}

async function selectBatch(batchId) {
  store.setActiveBatch(batchId)
  detail.value = null
  detailLoading.value = true
  try {
    const [ringsRes, txRes] = await Promise.all([
      getBatchFraudRings(batchId, 50, 0),
      getBatchTransactions(batchId, 20, 0),
    ])
    detail.value = {
      rings:        ringsRes.data?.fraud_rings   || [],
      transactions: txRes.data?.transactions     || [],
    }
  } catch (e) {
    showToast('Could not load batch details.', 'error')
    detail.value = { rings: [], transactions: [] }
  } finally {
    detailLoading.value = false
  }
}

// ── Actions ────────────────────────────────────────────────────────────────
async function loadIntoCharts(batchId) {
  try {
    const [ringsRes, txRes] = await Promise.all([
      getBatchFraudRings(batchId, 500, 0),
      getBatchTransactions(batchId, 1000, 0),
    ])
    const rings = ringsRes.data?.fraud_rings   || []
    const txs   = txRes.data?.transactions     || []
    if (rings.length) store.setFromDBRings(rings)
    if (txs.length)   store.setTransactions(txs)
    showToast(`Batch loaded into charts — ${rings.length} rings, ${txs.length} transactions`)
  } catch (e) {
    showToast('Failed to load batch data: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

async function dlJson(batchId) {
  try {
    const res = await downloadBatchJson(batchId)
    triggerDownload(res.data, `batch_${batchId.slice(0,8)}_report.json`)
    showToast('JSON report downloaded')
  } catch (e) {
    showToast('Download failed: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

async function dlCsv(batchId) {
  try {
    const res = await downloadBatchCsv(batchId)
    triggerDownload(res.data, `batch_${batchId.slice(0,8)}_summary.csv`)
    showToast('CSV downloaded')
  } catch (e) {
    showToast('Download failed: ' + (e.response?.data?.detail || e.message), 'error')
  }
}

function confirmDelete(batchId) {
  deleteModal.batchId = batchId
  deleteModal.error   = ''
  deleteModal.show    = true
}

async function doDelete() {
  deleteModal.loading = true
  deleteModal.error   = ''
  try {
    await deleteBatch(deleteModal.batchId)
    store.removeBatch(deleteModal.batchId)
    if (detail.value && store.activeBatchId === deleteModal.batchId) detail.value = null
    deleteModal.show = false
    showToast('Batch deleted successfully')
    // Reload batches to get fresh list
    await loadBatches()
  } catch (e) {
    deleteModal.error = e.response?.data?.detail || e.message
  } finally {
    deleteModal.loading = false
  }
}

onMounted(() => {
  if (!store.batches.length) loadBatches()
  else if (store.activeBatchId && !detail.value) selectBatch(store.activeBatchId)
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
.btn-nav {
  padding: 9px 18px; border-radius: 10px; font-size: 13px; font-weight: 600;
  background: var(--purple); color: #fff; transition: all .2s;
  box-shadow: 0 0 16px var(--purple-glow);
}
.btn-nav:hover { background: var(--purple-light); }
.spin-sm { width: 13px; height: 13px; border: 2px solid rgba(255,255,255,.2); border-top-color: var(--accent); border-radius: 50%; animation: spin .7s linear infinite; display: inline-block; }

.loading-state { display: flex; flex-direction: column; align-items: center; gap: 16px; height: 280px; justify-content: center; color: var(--muted); }
.spin-lg { width: 40px; height: 40px; border: 3px solid var(--border); border-top-color: var(--purple); border-radius: 50%; animation: spin .8s linear infinite; }

.empty { display: flex; flex-direction: column; align-items: center; gap: 16px; height: 280px; justify-content: center; color: var(--muted); text-align: center; font-size: 14px; }
.empty svg { width: 52px; height: 52px; stroke: rgba(124,58,237,.3); }
.link { color: var(--accent); text-decoration: underline; }

/* ── Batches Table ── */
.table-wrap { overflow-x: auto; border-radius: 16px; border: 1px solid var(--border); margin-bottom: 24px; }
.batch-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.batch-table thead tr { border-bottom: 1px solid var(--border); }
.batch-table th {
  padding: 12px 16px; font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .6px; color: var(--muted); text-align: left; white-space: nowrap;
}
.batch-table td { padding: 12px 16px; border-bottom: 1px solid rgba(255,255,255,.03); vertical-align: middle; }
.batch-table tbody tr { cursor: pointer; transition: background .15s; }
.batch-table tbody tr:hover { background: var(--surface2); }
.batch-table tbody tr.active { background: rgba(124,58,237,.07); border-left: 3px solid var(--purple); }
.batch-table tbody tr:last-child td { border-bottom: none; }
.actions-col { text-align: right; width: 160px; }
.actions-cell { text-align: right; }

.id-cell { display: flex; align-items: center; gap: 8px; }
.id-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--border); flex-shrink: 0; transition: background .2s; }
.id-dot.active { background: var(--purple-light); box-shadow: 0 0 8px var(--purple-glow); }

.ring-badge {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 26px; padding: 2px 8px; border-radius: 20px; font-size: 12px; font-weight: 700; font-family: var(--font-mono);
}
.ring-badge.danger { background: rgba(239,68,68,.15); color: var(--critical); }
.ring-badge.safe   { background: rgba(34,197,94,.1);  color: var(--low); }

.icon-btn {
  display: inline-flex; align-items: center; justify-content: center;
  width: 32px; height: 32px; border-radius: 8px;
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--muted); cursor: pointer; transition: all .2s; margin-left: 4px;
}
.icon-btn svg { width: 14px; height: 14px; }
.icon-btn:hover { color: var(--text); border-color: var(--purple); }
.icon-btn.danger:hover { color: var(--critical); border-color: rgba(239,68,68,.4); background: rgba(239,68,68,.08); }

/* ── Detail Panel ── */
.detail-panel {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 20px; overflow: hidden; margin-bottom: 32px;
}
.detail-header {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px;
  padding: 20px 24px; border-bottom: 1px solid var(--border);
  background: rgba(124,58,237,.05);
}
.detail-title { font-size: 15px; font-weight: 700; }
.detail-sub   { font-size: 11px; color: var(--muted); margin-top: 2px; }
.detail-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

.detail-section { padding: 20px 24px; border-bottom: 1px solid var(--border); }
.detail-section:last-child { border-bottom: none; }
.section-label { font-size: 12px; font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: .6px; margin-bottom: 14px; }

.no-data-row { padding: 20px 24px; color: var(--muted); font-size: 13px; }

.mini-table-wrap { overflow-x: auto; border-radius: 10px; border: 1px solid rgba(255,255,255,.06); }
.mini-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.mini-table th { padding: 8px 12px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; color: var(--muted); text-align: left; border-bottom: 1px solid rgba(255,255,255,.06); }
.mini-table td { padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,.03); }
.mini-table tbody tr:last-child td { border-bottom: none; }
.mini-table tbody tr:hover { background: rgba(255,255,255,.02); }

.pattern-tag {
  display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 11px;
  background: rgba(124,58,237,.12); color: var(--accent); font-weight: 600;
}
.risk-badge {
  display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700;
}
.risk-badge.high     { background: rgba(249,115,22,.15); color: var(--high); }
.risk-badge.critical { background: rgba(239,68,68,.15);  color: var(--critical); }
.risk-badge.medium   { background: rgba(234,179,8,.15);  color: var(--medium); }
.risk-badge.low      { background: rgba(34,197,94,.15);  color: var(--low); }

/* ── Delete Modal ── */
.modal-backdrop {
  position: fixed; inset: 0; background: rgba(0,0,0,.65);
  display: flex; align-items: center; justify-content: center; z-index: 1000;
  backdrop-filter: blur(4px);
}
.modal {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 20px; padding: 32px; max-width: 420px; width: 90%; text-align: center;
  box-shadow: 0 24px 60px rgba(0,0,0,.5);
}
.modal-icon { font-size: 36px; margin-bottom: 12px; }
.modal-title { font-size: 18px; font-weight: 700; margin-bottom: 10px; }
.modal-body  { font-size: 13px; color: var(--muted); line-height: 1.7; margin-bottom: 24px; }
.modal-body code { background: rgba(255,255,255,.07); padding: 1px 6px; border-radius: 5px; font-family: var(--font-mono); color: var(--text); }
.modal-actions { display: flex; gap: 10px; justify-content: center; }
.btn-cancel {
  padding: 10px 24px; border-radius: 10px; border: 1px solid var(--border);
  background: var(--surface); color: var(--muted); font-size: 14px; font-weight: 600; cursor: pointer; transition: all .2s;
}
.btn-cancel:hover { color: var(--text); border-color: var(--purple); }
.btn-danger {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 24px; border-radius: 10px; border: none;
  background: rgba(239,68,68,.9); color: #fff; font-size: 14px; font-weight: 700; cursor: pointer; transition: all .2s;
}
.btn-danger:hover:not(:disabled) { background: #ef4444; box-shadow: 0 0 20px rgba(239,68,68,.4); }
.btn-danger:disabled { opacity: .5; cursor: not-allowed; }
.modal-error { color: var(--critical); font-size: 12px; margin-top: 12px; }

/* ── Toast ── */
.toast {
  position: fixed; bottom: 28px; right: 28px; z-index: 2000;
  padding: 12px 20px; border-radius: 12px; font-size: 13px; font-weight: 600;
  box-shadow: 0 8px 32px rgba(0,0,0,.4); pointer-events: none;
}
.toast.success { background: rgba(34,197,94,.15); border: 1px solid rgba(34,197,94,.3); color: var(--low); }
.toast.error   { background: rgba(239,68,68,.15); border: 1px solid rgba(239,68,68,.3); color: var(--critical); }

/* ── Transitions ── */
.slide-up-enter-active { transition: all .35s cubic-bezier(.4,0,.2,1); }
.slide-up-leave-active { transition: all .2s ease; }
.slide-up-enter-from, .slide-up-leave-to { opacity: 0; transform: translateY(16px); }

.fade-enter-active, .fade-leave-active { transition: opacity .2s; }
.fade-enter-from, .fade-leave-to       { opacity: 0; }

.toast-enter-active { transition: all .3s cubic-bezier(.4,0,.2,1); }
.toast-leave-active { transition: all .25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(16px); }

.mono { font-family: var(--font-mono); }
.dim  { color: var(--muted); }
</style>
