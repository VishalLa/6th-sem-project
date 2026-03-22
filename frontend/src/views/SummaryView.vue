<template>
  <section class="page">

    <div class="header">
      <div>
        <h1 class="title">Fraud Ring Summary</h1>
        <p class="sub">
          <template v-if="store.totalRings">
            <span class="mono accent">{{ store.totalRings }}</span>
            ring{{ store.totalRings !== 1 ? 's' : '' }} detected
          </template>
          <template v-else>No results yet</template>
        </p>
      </div>
      <div class="header-actions">
        <button class="btn-sec" @click="reload" :disabled="refreshing">
          <span v-if="refreshing" class="spin-sm"/>
          {{ refreshing ? 'Loading…' : '↺ Reload' }}
        </button>
        <button class="btn-sec" @click="exportCSV" :disabled="!store.rings.length">
          ↓ Export CSV
        </button>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="refreshing" class="loading-state">
      <div class="spin-lg"/>
      <p>Loading results from database…</p>
    </div>

    <!-- No data -->
    <div v-else-if="!store.rings.length" class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2">
        <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/>
        <polyline points="13 2 13 9 20 9"/>
      </svg>
      <p>No results yet. Upload a CSV file on the <RouterLink to="/" class="link">Home</RouterLink> page and run detection.</p>
    </div>

    <template v-else>
      <StatCards />
      <SummaryTable />
    </template>

  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useResultsStore } from '@/stores/results'
import { getMyFraudRings } from '@/services/api'
import StatCards    from '@/components/StatCards.vue'
import SummaryTable from '@/components/SummaryTable.vue'

const store     = useResultsStore()
const refreshing = ref(false)

async function reload() {
  refreshing.value = true
  try {
    const res = await getMyFraudRings(500, 0)
    const rings = res.data?.fraud_rings || []
    if (rings.length) store.setFromDBRings(rings)
  } catch (e) { console.error('Reload failed:', e) }
  finally { refreshing.value = false }
}

// Auto-load on first visit if store is empty
onMounted(() => { if (!store.rings.length) reload() })

function exportCSV() {
  if (!store.rings.length) return
  const headers = [
    'Ring ID','Pattern Type','Member Count','Risk Score','Risk Category',
    'Avg Member Score','Max Member Score','Structural Complexity',
    'Internal Edge Count','Ring Density','Member Account IDs'
  ]
  const rows = store.rings.map(r =>
    headers.map(h => JSON.stringify(r[h] ?? '')).join(',')
  )
  const csv  = [headers.join(','), ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = Object.assign(document.createElement('a'), { href: url, download: 'flowmatrix_results.csv' })
  document.body.appendChild(a); a.click()
  document.body.removeChild(a); URL.revokeObjectURL(url)
}
</script>

<style scoped>
.page { min-height:100vh; padding:80px clamp(16px,4vw,48px) 48px; }

.header {
  display:flex; align-items:flex-start; justify-content:space-between;
  flex-wrap:wrap; gap:16px; margin-bottom:24px;
}
.title { font-family:var(--font-mono); font-size:clamp(20px,3vw,28px); font-weight:700; margin-bottom:4px; }
.sub   { color:var(--muted); font-size:13px; }
.accent { color:var(--accent); }

.header-actions { display:flex; gap:10px; flex-wrap:wrap; }

.btn-sec {
  display:flex; align-items:center; gap:6px;
  background:var(--surface); border:1px solid var(--border);
  color:var(--muted); padding:9px 18px; border-radius:10px;
  font-size:13px; font-weight:600; cursor:pointer; transition:all .2s;
  font-family:var(--font-sans);
}
.btn-sec:hover:not(:disabled) { color:var(--text); border-color:var(--purple); }
.btn-sec:disabled { opacity:.4; cursor:not-allowed; }

.spin-sm {
  width:13px; height:13px; border:2px solid rgba(255,255,255,.2);
  border-top-color:var(--accent); border-radius:50%; animation:spin .7s linear infinite; display:inline-block;
}

.loading-state {
  display:flex; flex-direction:column; align-items:center;
  justify-content:center; gap:16px; height:300px; color:var(--muted);
}
.spin-lg {
  width:40px; height:40px; border:3px solid var(--border);
  border-top-color:var(--purple); border-radius:50%; animation:spin .8s linear infinite;
}

.empty {
  display:flex; flex-direction:column; align-items:center;
  justify-content:center; gap:16px; height:300px;
  color:var(--muted); text-align:center; font-size:14px;
}
.empty svg { width:52px; height:52px; stroke:rgba(124,58,237,.3); }
.link { color:var(--accent); text-decoration:underline; }
</style>
