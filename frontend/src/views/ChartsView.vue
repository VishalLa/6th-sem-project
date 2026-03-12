<template>
  <section class="page">
    <div class="header">
      <div>
        <h1 class="title">Analytics</h1>
        <p class="sub">Risk distribution, score profiles, pattern breakdown and density scatter</p>
      </div>
    </div>

    <div v-if="!store.rings.length" class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.1">
        <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/>
        <line x1="6"  y1="20" x2="6"  y2="14"/>
      </svg>
      <p>No data — run detection on the <RouterLink to="/" class="link">Home</RouterLink> page first.</p>
    </div>

    <ChartsView v-else />
  </section>
</template>

<script setup>
import { useResultsStore } from '@/stores/results'
import ChartsView from '@/components/ChartsView.vue'
const store = useResultsStore()
</script>

<style scoped>
.page   { min-height:100vh; padding:80px clamp(16px,4vw,48px) 48px; }
.header { display:flex; align-items:flex-start; justify-content:space-between; flex-wrap:wrap; gap:16px; margin-bottom:24px; }
.title  { font-family:var(--font-mono); font-size:clamp(20px,3vw,28px); font-weight:700; margin-bottom:4px; }
.sub    { color:var(--muted); font-size:13px; }
.empty  {
  display:flex; flex-direction:column; align-items:center;
  justify-content:center; gap:16px; height:300px;
  color:var(--muted); text-align:center; font-size:14px;
}
.empty svg { width:60px; height:60px; stroke:rgba(124,58,237,.3); }
.link { color:var(--accent); text-decoration:underline; }
</style>
