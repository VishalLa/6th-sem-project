<template>
  <div
    class="dropzone"
    :class="{ over: dragging, filled: files.length }"
    @dragover.prevent="dragging=true"
    @dragleave.prevent="dragging=false"
    @drop.prevent="onDrop"
    @click="inputRef?.click()"
  >
    <input ref="inputRef" type="file" multiple accept=".csv"
      class="hidden" @change="onPick" />

    <!-- Empty state -->
    <template v-if="!files.length">
      <div class="dz-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="16 16 12 12 8 16"/>
          <line x1="12" y1="12" x2="12" y2="21"/>
          <path d="M20.39 18.39A5 5 0 0018 9h-1.26A8 8 0 103 16.3"/>
        </svg>
      </div>
      <p class="dz-title">Drag &amp; drop CSV files here</p>
      <p class="dz-hint">Only .csv files are accepted by the backend</p>
    </template>

    <!-- File list -->
    <template v-else>
      <div class="flist-header">
        <span class="flist-count">{{ files.length }} file{{ files.length > 1 ? 's' : '' }} ready</span>
        <button class="flist-clear" @click.stop="clear">✕ Clear</button>
      </div>
      <div class="flist" @click.stop>
        <div v-for="(f,i) in files" :key="i" class="fitem">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z"/>
            <polyline points="13 2 13 9 20 9"/>
          </svg>
          <span class="fname">{{ f.name }}</span>
          <span class="fsize">{{ fmt(f.size) }}</span>
        </div>
      </div>
      <p class="dz-hint" style="margin-top:8px">Click to add more files</p>
    </template>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const emit = defineEmits(['update:files'])
const inputRef = ref(null)
const dragging = ref(false)
const files    = ref([])

function onPick(e) { add(Array.from(e.target.files)) }
function onDrop(e) { dragging.value=false; add(Array.from(e.dataTransfer.files)) }

function add(incoming) {
  const valid = incoming.filter(f => f.name.toLowerCase().endsWith('.csv'))
  const names = new Set(files.value.map(f => f.name))
  valid.forEach(f => { if (!names.has(f.name)) files.value.push(f) })
  emit('update:files', files.value)
}

function clear() {
  files.value = []
  if (inputRef.value) inputRef.value.value = ''
  emit('update:files', [])
}

function fmt(b) {
  if (b < 1024) return b + ' B'
  if (b < 1024*1024) return (b/1024).toFixed(1) + ' KB'
  return (b/1024/1024).toFixed(1) + ' MB'
}
</script>

<style scoped>
.dropzone {
  width:100%; max-width:580px;
  background:var(--surface); border:2px dashed rgba(124,58,237,.35);
  border-radius:20px; padding:36px 28px;
  cursor:pointer; transition:all .3s; text-align:center; position:relative;
}
.dropzone:hover,.dropzone.over {
  border-color:var(--purple-light); background:rgba(124,58,237,.08);
  box-shadow:0 0 32px var(--purple-glow);
}
.dropzone.filled { border-style:solid; border-color:rgba(124,58,237,.4); }

.hidden { display:none; }

.dz-icon {
  width:50px; height:50px; margin:0 auto 14px;
  background:rgba(124,58,237,.2); border-radius:14px;
  display:flex; align-items:center; justify-content:center;
}
.dz-icon svg { width:26px; height:26px; stroke:var(--accent); }
.dz-title { font-size:15px; font-weight:600; margin-bottom:6px; }
.dz-hint  { font-size:12px; color:var(--muted); }

/* File list */
.flist-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
.flist-count  { font-size:13px; font-weight:600; color:var(--accent); }
.flist-clear  {
  background:rgba(239,68,68,.1); border:1px solid rgba(239,68,68,.25);
  color:var(--critical); padding:3px 10px; border-radius:6px; font-size:12px; cursor:pointer; transition:all .2s;
}
.flist-clear:hover { background:rgba(239,68,68,.2); }

.flist { display:flex; flex-direction:column; gap:6px; max-height:160px; overflow-y:auto; text-align:left; }

.fitem {
  display:flex; align-items:center; gap:8px;
  background:rgba(124,58,237,.1); border:1px solid rgba(124,58,237,.2);
  border-radius:8px; padding:7px 10px; font-size:12px;
}
.fitem svg { width:13px; height:13px; stroke:var(--accent); flex-shrink:0; }
.fname { flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.fsize { color:var(--muted); flex-shrink:0; }
</style>
