<template>
  <section class="page">
    <div class="header">
      <div>
        <h1 class="title">Transaction Graph</h1>
        <p class="sub">Full account network — ring clusters highlighted · click to inspect</p>
      </div>
    </div>

    <div v-if="!hasData" class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.1">
        <circle cx="12" cy="5" r="2"/>
        <circle cx="5"  cy="19" r="2"/>
        <circle cx="19" cy="19" r="2"/>
        <line x1="12" y1="7"  x2="5"  y2="17"/>
        <line x1="12" y1="7"  x2="19" y2="17"/>
        <line x1="7"  y1="19" x2="17" y2="19"/>
      </svg>
      <p>No data yet — upload a CSV on the <RouterLink to="/" class="link">Home</RouterLink> page first.</p>
    </div>

    <GraphViewComponent v-else />
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useResultsStore }  from '@/stores/results'
import GraphViewComponent   from '@/components/GraphView.vue'

const store   = useResultsStore()
const hasData = computed(() => Object.keys(store.graphDataByFile).length > 0)
</script>

<style scoped>
.page  { min-height:100vh; padding:80px clamp(16px,4vw,48px) 48px; }
.header { display:flex; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; gap:16px; margin-bottom:24px; }
.title  { font-family:var(--font-mono); font-size:clamp(20px,3vw,28px); font-weight:700; margin-bottom:4px; }
.sub    { color:var(--muted); font-size:13px; }
.empty  {
  display:flex; flex-direction:column; align-items:center;
  justify-content:center; gap:16px; height:400px;
  color:var(--muted); text-align:center; font-size:14px; line-height:1.7;
}
.empty svg { width:72px; height:72px; stroke:rgba(124,58,237,.3); }
.link { color:var(--accent); text-decoration:underline; }
</style>
