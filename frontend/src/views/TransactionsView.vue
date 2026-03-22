<template>
  <section class="page">
    <div class="header">
      <div>
        <h1 class="title">Transactions</h1>
        <p class="sub">{{ store.transactions.length.toLocaleString() }} records loaded</p>
      </div>
      <button class="btn-sec" @click="load" :disabled="loading">
        <span v-if="loading" class="spin-sm" /> {{ loading ? 'Loading…' : '↺ Load' }}
      </button>
    </div>

    <!-- Filters -->
    <div class="filters" v-if="store.transactions.length">
      <input v-model="search" class="filter-input" placeholder="Search ID, account, country…" />
      <select v-model="filterKyc" class="filter-select">
        <option value="">All KYC</option>
        <option>Verified</option><option>Pending</option><option value="None">None</option>
      </select>
      <select v-model="filterMethod" class="filter-select">
        <option value="">All Methods</option>
        <option>Crypto</option><option>Wire</option><option>ACH</option><option>P2P</option>
      </select>
    </div>

    <div v-if="!store.transactions.length && !loading" class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
        <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
      </svg>
      <p>No transactions loaded. Upload a CSV on the <RouterLink to="/" class="link">Home</RouterLink> page.</p>
    </div>

    <div v-else class="table-wrap">
      <table class="tx-table">
        <thead>
          <tr>
            <th @click="sortBy('transaction_id')">TXN ID <SortIcon :col="'transaction_id'" :active="sort.col" :dir="sort.dir" /></th>
            <th @click="sortBy('amount')">Amount <SortIcon col="amount" :active="sort.col" :dir="sort.dir" /></th>
            <th @click="sortBy('sender_country')">From</th>
            <th @click="sortBy('receiver_country')">To</th>
            <th @click="sortBy('txn_method')">Method</th>
            <th @click="sortBy('sender_kyc')">KYC</th>
            <th @click="sortBy('timestamp')">Timestamp <SortIcon col="timestamp" :active="sort.col" :dir="sort.dir" /></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="tx in paginated" :key="tx.transaction_id">
            <td class="mono dim">{{ tx.transaction_id }}</td>
            <td class="mono"><span :class="amtClass(tx.amount)">${{ Number(tx.amount).toFixed(2) }}</span></td>
            <td><Flag :code="tx.sender_country" /> {{ tx.sender_country }}</td>
            <td><Flag :code="tx.receiver_country" /> {{ tx.receiver_country }}</td>
            <td><span class="badge" :class="tx.txn_method?.toLowerCase()">{{ tx.txn_method }}</span></td>
            <td><span class="kyc-badge" :class="(tx.sender_kyc || 'none').toLowerCase()">{{ tx.sender_kyc || 'None' }}</span></td>
            <td class="dim ts">{{ fmtDate(tx.timestamp) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div class="pagination" v-if="totalPages > 1">
        <button @click="page = Math.max(1, page - 1)" :disabled="page === 1">‹</button>
        <span>{{ page }} / {{ totalPages }}</span>
        <button @click="page = Math.min(totalPages, page + 1)" :disabled="page === totalPages">›</button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref, computed, onMounted, watch, defineComponent, h } from 'vue'
import { useResultsStore } from '@/stores/results'
import { getMyTransactions } from '@/services/api'

const store   = useResultsStore()
const loading = ref(false)
const search  = ref('')
const filterKyc    = ref('')
const filterMethod = ref('')
const page    = ref(1)
const PAGE_SIZE = 50
const sort    = ref({ col: 'timestamp', dir: 'desc' })

// Inline sort icon
const SortIcon = defineComponent({
  props: ['col', 'active', 'dir'],
  render(props) {
    if (props.col !== props.active) return null
    return h('span', { style: 'margin-left:4px;opacity:.6;font-size:10px' }, props.dir === 'asc' ? '▲' : '▼')
  }
})

// Inline flag emoji
const Flag = defineComponent({
  props: ['code'],
  render(props) {
    const code = props.code?.toUpperCase() || ''
    const flag = code.length === 2
      ? String.fromCodePoint(...[...code].map(c => 0x1F1E6 + c.charCodeAt(0) - 65))
      : ''
    return h('span', { style: 'margin-right:4px' }, flag)
  }
})

function fmtDate(ts) {
  if (!ts) return '—'
  try { return new Date(ts).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) }
  catch { return ts }
}

function amtClass(v) {
  const n = Number(v)
  if (n > 1000) return 'amt-high'
  if (n > 500)  return 'amt-med'
  return ''
}

function sortBy(col) {
  if (sort.value.col === col) sort.value.dir = sort.value.dir === 'asc' ? 'desc' : 'asc'
  else { sort.value.col = col; sort.value.dir = 'desc' }
  page.value = 1
}

const filtered = computed(() => {
  let txs = store.transactions
  const q = search.value.toLowerCase()
  if (q) txs = txs.filter(t =>
    (t.transaction_id || '').toLowerCase().includes(q) ||
    (t.sender || '').toLowerCase().includes(q) ||
    (t.receiver || '').toLowerCase().includes(q) ||
    (t.sender_country || '').toLowerCase().includes(q) ||
    (t.receiver_country || '').toLowerCase().includes(q)
  )
  if (filterKyc.value) {
    const v = filterKyc.value
    txs = txs.filter(t => (v === 'None' ? (!t.sender_kyc || t.sender_kyc === 'None') : t.sender_kyc === v))
  }
  if (filterMethod.value) txs = txs.filter(t => t.txn_method === filterMethod.value)
  // Sort
  const col = sort.value.col
  const dir = sort.value.dir === 'asc' ? 1 : -1
  return [...txs].sort((a, b) => {
    const av = a[col] ?? ''; const bv = b[col] ?? ''
    if (col === 'amount') return (Number(av) - Number(bv)) * dir
    return String(av).localeCompare(String(bv)) * dir
  })
})

watch([search, filterKyc, filterMethod], () => { page.value = 1 })

const totalPages = computed(() => Math.max(1, Math.ceil(filtered.value.length / PAGE_SIZE)))
const paginated  = computed(() => filtered.value.slice((page.value - 1) * PAGE_SIZE, page.value * PAGE_SIZE))

async function load() {
  loading.value = true
  try {
    const res = await getMyTransactions(500, 0)
    store.setTransactions(res.data.transactions || [])
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

onMounted(() => { if (!store.transactions.length) load() })
</script>

<style scoped>
.page { min-height: 100vh; padding: 80px clamp(16px,4vw,48px) 60px; }

.header { display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 16px; margin-bottom: 20px; }
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

.filters { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.filter-input, .filter-select {
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text); border-radius: 10px; padding: 8px 14px;
  font-size: 13px; outline: none; transition: border-color .2s;
  font-family: var(--font-sans);
}
.filter-input { flex: 1; min-width: 220px; }
.filter-input::placeholder { color: rgba(148,163,184,.4); }
.filter-input:focus, .filter-select:focus { border-color: var(--purple); }
.filter-select option { background: var(--bg2); }

.empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; height: 280px; color: var(--muted); text-align: center; font-size: 14px; }
.empty svg { width: 48px; height: 48px; stroke: rgba(124,58,237,.3); }
.link { color: var(--accent); text-decoration: underline; }

.table-wrap { overflow-x: auto; border-radius: 16px; border: 1px solid var(--border); }

.tx-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.tx-table thead tr { border-bottom: 1px solid var(--border); }
.tx-table th {
  padding: 12px 14px; font-size: 11px; font-weight: 700; text-transform: uppercase;
  letter-spacing: .6px; color: var(--muted); text-align: left; cursor: pointer;
  white-space: nowrap; user-select: none;
}
.tx-table th:hover { color: var(--text); }
.tx-table td { padding: 10px 14px; border-bottom: 1px solid rgba(255,255,255,.03); }
.tx-table tbody tr:hover { background: var(--surface2); }
.tx-table tbody tr:last-child td { border-bottom: none; }

.mono { font-family: var(--font-mono); }
.dim  { color: var(--muted); }
.ts   { font-size: 12px; white-space: nowrap; }

.amt-high { color: var(--critical); font-weight: 700; }
.amt-med  { color: var(--high); font-weight: 600; }

.badge {
  display: inline-block; padding: 3px 10px; border-radius: 6px;
  font-size: 11px; font-weight: 700; letter-spacing: .3px;
  background: rgba(124,58,237,.15); color: var(--accent);
}
.badge.crypto  { background: rgba(168,85,247,.15); color: #c084fc; }
.badge.wire    { background: rgba(56,189,248,.15);  color: var(--info); }
.badge.ach     { background: rgba(34,197,94,.15);   color: var(--low); }
.badge.p2p     { background: rgba(249,115,22,.15);  color: var(--high); }

.kyc-badge {
  display: inline-block; padding: 3px 10px; border-radius: 6px;
  font-size: 11px; font-weight: 700;
}
.kyc-badge.verified { background: rgba(34,197,94,.15);  color: var(--low); }
.kyc-badge.pending  { background: rgba(234,179,8,.15);  color: var(--medium); }
.kyc-badge.none     { background: rgba(239,68,68,.15);  color: var(--critical); }

.pagination {
  display: flex; align-items: center; justify-content: center; gap: 16px;
  padding: 14px; border-top: 1px solid var(--border);
  font-size: 13px; color: var(--muted);
}
.pagination button {
  background: var(--surface); border: 1px solid var(--border);
  color: var(--text); width: 32px; height: 32px; border-radius: 8px;
  font-size: 16px; transition: all .2s;
}
.pagination button:hover:not(:disabled) { border-color: var(--purple); color: var(--accent); }
.pagination button:disabled { opacity: .3; cursor: not-allowed; }
</style>
