<template>
  <div class="stats-grid">
    <div v-for="card in cards" :key="card.label" class="stat-card">
      <p class="label">{{ card.label }}</p>
      <p class="value mono" :style="card.color ? { color: `var(--${card.color})` } : {}">
        {{ card.value }}
      </p>
    </div>
  </div>

  <!-- Pipeline stats (from last detection run) -->
  <div v-if="store.pipelineStats" class="pipeline-bar">
    <span>
      <b>{{ store.pipelineStats.total_accounts_analyzed }}</b> accounts analysed
    </span>
    <span class="sep">·</span>
    <span>
      <b>{{ store.pipelineStats.suspicious_accounts_flagged }}</b> flagged
    </span>
    <span class="sep">·</span>
    <span>
      Processed in <b>{{ store.pipelineStats.processing_time_seconds }}s</b>
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useResultsStore } from '@/stores/results'

const store = useResultsStore()

const cards = computed(() => [
  { label: 'Total Rings',  value: store.totalRings    || '—'  },
  { label: 'Critical',     value: store.criticalCount || '0',  color: 'critical' },
  { label: 'High Risk',    value: store.highCount     || '0',  color: 'high'     },
  { label: 'Medium',       value: store.mediumCount   || '0',  color: 'medium'   },
  { label: 'Low Risk',     value: store.lowCount      || '0',  color: 'low'      },
  { label: 'Avg Score',    value: store.avgScore      || '—'  }
])
</script>

<style scoped>
.stats-grid {
  display:grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap:12px; margin-bottom:16px;
}
.stat-card {
  background:var(--surface); border:1px solid var(--border);
  border-radius:14px; padding:16px 18px; transition:all .2s;
}
.stat-card:hover { border-color:rgba(124,58,237,.3); background:var(--surface2); }
.label { font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.8px; font-weight:600; margin-bottom:8px; }
.value { font-size:clamp(22px,3vw,28px); font-weight:700; line-height:1; }

.pipeline-bar {
  display:flex; align-items:center; gap:10px; flex-wrap:wrap;
  background:rgba(56,189,248,.07); border:1px solid rgba(56,189,248,.15);
  border-radius:10px; padding:10px 16px; font-size:13px; color:var(--muted);
  margin-bottom:20px;
}
.pipeline-bar b { color:var(--info); }
.sep { opacity:.3; }
</style>
