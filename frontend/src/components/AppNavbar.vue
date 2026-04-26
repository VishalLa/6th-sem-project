<template>
  <nav class="navbar">
    <RouterLink to="/" class="logo"><span>F</span>Matrix</RouterLink>

    <div class="nav-tabs">
      <RouterLink v-for="t in tabs" :key="t.to" :to="t.to" class="nav-tab"
        :class="{ active: route.path === t.to }">{{ t.label }}</RouterLink>
    </div>

    <div class="nav-right">
      <!-- Download dropdown -->
      <div class="dl-wrap" ref="dlWrap">
        <button class="btn-dl" @click="dlOpen = !dlOpen" :disabled="dlBusy">
          <span v-if="dlBusy" class="spin-sm" />
          <DownloadIcon v-else />
          Download
          <span class="chevron" :class="{ open: dlOpen }">▾</span>
        </button>

        <Transition name="dd">
          <div v-if="dlOpen" class="dl-dropdown">
            <p class="dd-heading">Export your data</p>

            <button class="dd-item" @click="exportRingsCSV">
              <span class="dd-icon">📋</span>
              <div>
                <p class="dd-label">Fraud Rings — CSV</p>
                <p class="dd-sub">{{ store.totalRings }} rings detected</p>
              </div>
            </button>

            <button class="dd-item" @click="exportRingsJSON">
              <span class="dd-icon">{ }</span>
              <div>
                <p class="dd-label">Fraud Rings — JSON</p>
                <p class="dd-sub">Full ring details</p>
              </div>
            </button>

            <button class="dd-item" @click="exportTransactionsCSV">
              <span class="dd-icon">💳</span>
              <div>
                <p class="dd-label">Transactions — CSV</p>
                <p class="dd-sub">{{ store.transactions.length.toLocaleString() }} records</p>
              </div>
            </button>

            <button class="dd-item" @click="exportFullReport">
              <span class="dd-icon">📦</span>
              <div>
                <p class="dd-label">Full Report — JSON</p>
                <p class="dd-sub">Rings + transactions + stats</p>
              </div>
            </button>

            <div class="dd-divider" />

            <button class="dd-item fetch-item" @click="fetchAndExport" :disabled="dlBusy">
              <span class="dd-icon">☁</span>
              <div>
                <p class="dd-label">Fetch latest from server</p>
                <p class="dd-sub">Refreshes data then downloads</p>
              </div>
            </button>

            <p v-if="dlMsg" class="dd-msg" :class="dlMsgType">{{ dlMsg }}</p>
          </div>
        </Transition>
      </div>

      <!-- User info + logout -->
      <div v-if="auth.user" class="user-info">
        <span class="user-name">{{ auth.user.first_name }}</span>
        <button class="btn-icon-sm" @click="doLogout" title="Sign out">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
      </div>
      <button class="hamburger" :class="{ open }" @click="open = !open">
        <span /><span /><span />
      </button>
    </div>
  </nav>

  <Transition name="mobile-slide">
    <div v-if="open" class="mobile-nav">
      <RouterLink v-for="t in tabs" :key="t.to" :to="t.to" class="m-tab"
        :class="{ active: route.path === t.to }" @click="open = false">{{ t.label }}</RouterLink>
      <button class="btn-dl w-full" @click="fetchAndExport; open = false">
        <DownloadIcon /> Download Report
      </button>
      <button v-if="auth.user" class="btn-logout-m" @click="doLogout">Sign Out</button>
    </div>
  </Transition>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, defineComponent, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getMyFraudRings, getMyTransactions } from '@/services/api'
import { useAuthStore }    from '@/stores/auth'
import { useResultsStore } from '@/stores/results'

const route  = useRoute()
const router = useRouter()
const auth   = useAuthStore()
const store  = useResultsStore()
const open   = ref(false)
const dlOpen = ref(false)
const dlBusy = ref(false)
const dlMsg  = ref('')
const dlMsgType = ref('ok')
const dlWrap = ref(null)

const tabs = [
  { to: '/',             label: 'Home'         },
  { to: '/batches',      label: '📁 Batches'   },
  { to: '/graph',        label: 'Graph'        },
  { to: '/summary',      label: 'Summary'      },
  { to: '/metrics',      label: 'Metrics'      },
  { to: '/transactions', label: 'Transactions' },
  { to: '/chat',         label: '✦ Chat'       },
]

const DownloadIcon = defineComponent({
  render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2', style: 'width:14px;height:14px' }, [
    h('path', { d: 'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4' }),
    h('polyline', { points: '7 10 12 15 17 10' }),
    h('line', { x1: '12', y1: '15', x2: '12', y2: '3' })
  ])
})

// Close dropdown when clicking outside
function onClickOutside(e) {
  if (dlWrap.value && !dlWrap.value.contains(e.target)) dlOpen.value = false
}
onMounted(()    => document.addEventListener('click', onClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', onClickOutside))

function doLogout() {
  auth.logout()
  router.replace('/auth')
}

function showMsg(msg, type = 'ok') {
  dlMsg.value = msg; dlMsgType.value = type
  setTimeout(() => { dlMsg.value = '' }, 3000)
}

// ── Export helpers ────────────────────────────────────────────────────────────
function triggerDownload(content, filename, mime) {
  const blob = new Blob([content], { type: mime })
  const url  = URL.createObjectURL(blob)
  const a    = Object.assign(document.createElement('a'), { href: url, download: filename })
  document.body.appendChild(a); a.click()
  document.body.removeChild(a); URL.revokeObjectURL(url)
}

function ringsToCSV(rings) {
  if (!rings.length) return ''
  const headers = [
    'Ring ID', 'Pattern Type', 'Member Count', 'Risk Score',
    'Risk Category', 'Member Account IDs', 'Created At'
  ]
  const rows = rings.map(r => headers.map(h => {
    const val = r[h] ?? r[h.toLowerCase().replace(/ /g, '_')] ?? ''
    return JSON.stringify(String(val))
  }).join(','))
  return [headers.join(','), ...rows].join('\n')
}

function txToCSV(txs) {
  if (!txs.length) return ''
  const headers = [
    'transaction_id', 'sender', 'receiver', 'amount', 'timestamp',
    'sender_country', 'receiver_country', 'sender_kyc', 'txn_method', 'device_id'
  ]
  const rows = txs.map(t => headers.map(h => JSON.stringify(String(t[h] ?? ''))).join(','))
  return [headers.join(','), ...rows].join('\n')
}

function exportRingsCSV() {
  if (!store.rings.length) { showMsg('No fraud rings loaded yet.', 'warn'); return }
  triggerDownload(ringsToCSV(store.rings), 'fraud_rings.csv', 'text/csv')
  showMsg(`✓ Exported ${store.rings.length} rings`)
  dlOpen.value = false
}

function exportRingsJSON() {
  if (!store.rings.length) { showMsg('No fraud rings loaded yet.', 'warn'); return }
  triggerDownload(JSON.stringify(store.rings, null, 2), 'fraud_rings.json', 'application/json')
  showMsg(`✓ Exported ${store.rings.length} rings`)
  dlOpen.value = false
}

function exportTransactionsCSV() {
  if (!store.transactions.length) { showMsg('No transactions loaded yet.', 'warn'); return }
  triggerDownload(txToCSV(store.transactions), 'transactions.csv', 'text/csv')
  showMsg(`✓ Exported ${store.transactions.length} transactions`)
  dlOpen.value = false
}

function exportFullReport() {
  if (!store.rings.length && !store.transactions.length) {
    showMsg('No data loaded yet.', 'warn'); return
  }
  const report = {
    exported_at: new Date().toISOString(),
    user: auth.user?.email_id,
    summary: {
      total_rings:        store.totalRings,
      total_transactions: store.transactions.length,
      avg_risk_score:     store.avgScore,
      critical:           store.criticalCount,
      high:               store.highCount,
      medium:             store.mediumCount,
      low:                store.lowCount,
    },
    fraud_rings:   store.rings,
    transactions:  store.transactions,
  }
  triggerDownload(JSON.stringify(report, null, 2), 'flowmatrix_full_report.json', 'application/json')
  showMsg('✓ Full report exported')
  dlOpen.value = false
}

// Fetch latest from server then auto-export full report
async function fetchAndExport() {
  dlBusy.value = true
  dlOpen.value = false
  try {
    const [ringsRes, txRes] = await Promise.all([
      getMyFraudRings(500, 0),
      getMyTransactions(1000, 0),
    ])
    const rings = ringsRes.data?.fraud_rings || []
    const txs   = txRes.data?.transactions   || []

    if (rings.length) store.setFromDBRings(rings)
    if (txs.length)   store.setTransactions(txs)

    if (!rings.length && !txs.length) {
      showMsg('No data on server yet. Upload a CSV first.', 'warn')
      dlOpen.value = true
      return
    }

    exportFullReport()
  } catch (e) {
    showMsg('Fetch failed: ' + (e.response?.data?.detail || e.message), 'err')
    dlOpen.value = true
  } finally {
    dlBusy.value = false
  }
}
</script>

<style scoped>
.navbar {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 clamp(16px,4vw,48px); height: 64px;
  background: rgba(7,7,26,.88); backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
}

.logo {
  display: flex; align-items: baseline; gap: 2px;
  font-family: var(--font-mono); font-size: clamp(16px,2vw,20px); font-weight: 700;
}
.logo span { color: var(--purple-light); font-size: 1.4em; line-height: 1; }

.nav-tabs {
  display: flex; gap: 2px;
  background: rgba(255,255,255,.04); border: 1px solid var(--border);
  border-radius: 50px; padding: 4px;
}
.nav-tab {
  padding: 6px 16px; border-radius: 50px; font-size: 13px; font-weight: 500;
  color: var(--muted); transition: all .2s; white-space: nowrap;
}
.nav-tab:hover { color: var(--text); background: var(--surface2); }
.nav-tab.active { background: var(--purple); color: #fff; box-shadow: 0 0 20px var(--purple-glow); }
.nav-tab[href$="/chat"], .nav-tab[href*="#/chat"] {
  color: var(--accent);
  border: 1px solid rgba(124,58,237,.3);
}
.nav-tab[href$="/chat"].active, .nav-tab[href*="#/chat"].active {
  background: linear-gradient(135deg, var(--purple), var(--purple-light));
  box-shadow: 0 0 24px var(--purple-glow);
  border-color: transparent;
  color: #fff;
}

.nav-right { display: flex; align-items: center; gap: 10px; }

/* Download dropdown */
.dl-wrap { position: relative; }

.btn-dl {
  display: flex; align-items: center; gap: 6px;
  background: var(--purple); color: #fff; border: none;
  padding: 8px 16px; border-radius: 50px; font-size: 13px; font-weight: 600;
  transition: all .2s; box-shadow: 0 0 20px var(--purple-glow); white-space: nowrap;
  cursor: pointer;
}
.btn-dl:hover:not(:disabled) { background: var(--purple-light); transform: translateY(-1px); }
.btn-dl:disabled { opacity: .5; cursor: not-allowed; }
.chevron { font-size: 10px; transition: transform .2s; }
.chevron.open { transform: rotate(180deg); }
.spin-sm { width: 12px; height: 12px; border: 2px solid rgba(255,255,255,.3); border-top-color: #fff; border-radius: 50%; animation: spin .7s linear infinite; display: inline-block; }

.dl-dropdown {
  position: absolute; top: calc(100% + 8px); right: 0; z-index: 200;
  width: 280px;
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: 16px; padding: 8px;
  box-shadow: 0 20px 60px rgba(0,0,0,.5), 0 0 30px rgba(124,58,237,.1);
}
.dd-heading {
  font-size: 11px; font-weight: 700; color: var(--muted);
  text-transform: uppercase; letter-spacing: .6px;
  padding: 6px 10px 8px;
}
.dd-item {
  display: flex; align-items: center; gap: 12px;
  width: 100%; padding: 10px 12px; border-radius: 10px;
  background: transparent; border: none; cursor: pointer;
  text-align: left; transition: background .15s;
}
.dd-item:hover:not(:disabled) { background: var(--surface2); }
.dd-item:disabled { opacity: .4; cursor: not-allowed; }
.dd-icon {
  font-size: 18px; width: 32px; height: 32px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  background: rgba(124,58,237,.12); border-radius: 8px;
  font-family: var(--font-mono); font-size: 12px; color: var(--accent);
}
.dd-label { font-size: 13px; font-weight: 600; color: var(--text); }
.dd-sub   { font-size: 11px; color: var(--muted); margin-top: 1px; }
.dd-divider { height: 1px; background: var(--border); margin: 6px 8px; }
.fetch-item .dd-icon { background: rgba(56,189,248,.1); color: var(--info); }
.dd-msg { font-size: 12px; padding: 6px 12px; border-radius: 8px; margin: 4px 2px 2px; }
.dd-msg.ok   { background: rgba(34,197,94,.1);  color: var(--low); }
.dd-msg.warn { background: rgba(234,179,8,.1);  color: var(--medium); }
.dd-msg.err  { background: rgba(239,68,68,.1);  color: var(--critical); }

/* Dropdown animation */
.dd-enter-active, .dd-leave-active { transition: all .18s cubic-bezier(.4,0,.2,1); }
.dd-enter-from, .dd-leave-to { opacity: 0; transform: translateY(-6px) scale(.98); }

.user-info { display: flex; align-items: center; gap: 8px; }
.user-name { font-size: 13px; font-weight: 600; color: var(--muted); }

.btn-icon-sm {
  width: 30px; height: 30px; border-radius: 8px;
  background: var(--surface); border: 1px solid var(--border);
  color: var(--muted); display: flex; align-items: center; justify-content: center;
  transition: all .2s; cursor: pointer;
}
.btn-icon-sm:hover { color: var(--critical); border-color: var(--critical); }

.hamburger { display: none; flex-direction: column; gap: 5px; background: none; border: none; padding: 4px; cursor: pointer; }
.hamburger span { display: block; width: 22px; height: 2px; background: var(--text); border-radius: 2px; transition: all .3s; }
.hamburger.open span:nth-child(1) { transform: translateY(7px) rotate(45deg); }
.hamburger.open span:nth-child(2) { opacity: 0; }
.hamburger.open span:nth-child(3) { transform: translateY(-7px) rotate(-45deg); }

.mobile-nav {
  position: fixed; top: 64px; left: 0; right: 0; z-index: 99;
  background: rgba(7,7,26,.97); backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border); padding: 12px 16px 20px;
  display: flex; flex-direction: column; gap: 6px;
}
.m-tab { padding: 12px 16px; border-radius: 12px; font-size: 15px; font-weight: 500; color: var(--muted); transition: all .2s; }
.m-tab:hover { color: var(--text); background: var(--surface2); }
.m-tab.active { background: var(--purple); color: #fff; }

.w-full { width: 100%; justify-content: center; margin-top: 8px; }

.btn-logout-m {
  margin-top: 8px; padding: 12px; border-radius: 12px;
  background: rgba(239,68,68,.1); border: 1px solid rgba(239,68,68,.2);
  color: var(--critical); font-size: 14px; font-weight: 600;
  cursor: pointer; transition: all .2s;
}
.btn-logout-m:hover { background: rgba(239,68,68,.2); }

.mobile-slide-enter-active, .mobile-slide-leave-active { transition: all .28s ease; }
.mobile-slide-enter-from, .mobile-slide-leave-to { opacity: 0; transform: translateY(-10px); }

@media (max-width: 900px) {
  .nav-tabs { display: none; }
  .hamburger { display: flex; }
  .btn-dl:not(.w-full) { display: none; }
  .user-info { display: none; }
}
</style>
