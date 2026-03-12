<template>
  <nav class="navbar">
    <RouterLink to="/" class="logo"><span>F</span>Matrix</RouterLink>

    <div class="nav-tabs">
      <RouterLink v-for="t in tabs" :key="t.to" :to="t.to" class="nav-tab"
        :class="{ active: route.path === t.to }">{{ t.label }}</RouterLink>
    </div>

    <div class="nav-right">
      <button class="btn-dl" @click="handleDownload" title="Download JSON reports">
        <DownloadIcon /> Download
      </button>
      <button class="hamburger" :class="{ open: open }" @click="open = !open">
        <span /><span /><span />
      </button>
    </div>
  </nav>

  <Transition name="mobile-slide">
    <div v-if="open" class="mobile-nav">
      <RouterLink v-for="t in tabs" :key="t.to" :to="t.to" class="m-tab"
        :class="{ active: route.path === t.to }" @click="open=false">{{ t.label }}</RouterLink>
      <button class="btn-dl w-full" @click="handleDownload; open=false">
        <DownloadIcon /> Download Reports
      </button>
    </div>
  </Transition>
</template>

<script setup>
import { ref, defineComponent, h } from 'vue'
import { useRoute } from 'vue-router'
import { fetchFileList, downloadFile } from '@/services/api'

const route = useRoute()
const open  = ref(false)

const tabs = [
  { to: '/',        label: 'Home' },
  { to: '/graph',   label: 'Graph' },
  { to: '/summary', label: 'Summary Table' },
]

// Inline icon component
const DownloadIcon = defineComponent({
  render: () => h('svg', { viewBox:'0 0 24 24', fill:'none', stroke:'currentColor', 'stroke-width':'2', style:'width:14px;height:14px' }, [
    h('path', { d:'M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4' }),
    h('polyline', { points:'7 10 12 15 17 10' }),
    h('line', { x1:'12', y1:'15', x2:'12', y2:'3' })
  ])
})

async function handleDownload() {
  try {
    const res   = await fetchFileList()
    const files = res.data?.files ?? []

    if (!files.length) { alert('No output files found. Run detection first.'); return }

    for (const f of files) {
      // backend appends .json itself — strip it from name before calling /download/
      const nameNoExt = f.name.replace(/\.json$/, '')
      const r   = await downloadFile(nameNoExt)
      const url = URL.createObjectURL(new Blob([r.data], { type: 'application/json' }))
      const a   = Object.assign(document.createElement('a'), { href: url, download: f.name })
      document.body.appendChild(a); a.click()
      document.body.removeChild(a); URL.revokeObjectURL(url)
    }
  } catch (e) {
    console.error('Download failed', e)
    alert('Download failed — is the backend running?')
  }
}
</script>

<style scoped>
.navbar {
  position:fixed; top:0; left:0; right:0; z-index:100;
  display:flex; align-items:center; justify-content:space-between;
  padding: 0 clamp(16px,4vw,48px); height:64px;
  background: rgba(7,7,26,.88); backdrop-filter:blur(20px);
  border-bottom: 1px solid var(--border);
}

.logo {
  display:flex; align-items:baseline; gap:2px;
  font-family:var(--font-mono); font-size:clamp(16px,2vw,20px); font-weight:700;
}
.logo span { color:var(--purple-light); font-size:1.4em; line-height:1; }

.nav-tabs {
  display:flex; gap:4px;
  background:rgba(255,255,255,.04); border:1px solid var(--border);
  border-radius:50px; padding:4px;
}
.nav-tab {
  padding:6px 20px; border-radius:50px; font-size:14px; font-weight:500;
  color:var(--muted); transition:all .2s; white-space:nowrap;
}
.nav-tab:hover { color:var(--text); background:var(--surface2); }
.nav-tab.active { background:var(--purple); color:#fff; box-shadow:0 0 20px var(--purple-glow); }

.nav-right { display:flex; align-items:center; gap:10px; }

.btn-dl {
  display:flex; align-items:center; gap:6px;
  background:var(--purple); color:#fff; border:none;
  padding:8px 20px; border-radius:50px; font-size:14px; font-weight:600;
  transition:all .2s; box-shadow:0 0 20px var(--purple-glow); white-space:nowrap;
}
.btn-dl:hover { background:var(--purple-light); transform:translateY(-1px); }
.w-full { width:100%; justify-content:center; margin-top:8px; }

.hamburger { display:none; flex-direction:column; gap:5px; background:none; border:none; padding:4px; }
.hamburger span { display:block; width:22px; height:2px; background:var(--text); border-radius:2px; transition:all .3s; }
.hamburger.open span:nth-child(1) { transform:translateY(7px) rotate(45deg); }
.hamburger.open span:nth-child(2) { opacity:0; }
.hamburger.open span:nth-child(3) { transform:translateY(-7px) rotate(-45deg); }

.mobile-nav {
  position:fixed; top:64px; left:0; right:0; z-index:99;
  background:rgba(7,7,26,.97); backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border); padding:12px 16px 20px;
  display:flex; flex-direction:column; gap:6px;
}
.m-tab {
  padding:12px 16px; border-radius:12px; font-size:15px; font-weight:500; color:var(--muted); transition:all .2s;
}
.m-tab:hover { color:var(--text); background:var(--surface2); }
.m-tab.active { background:var(--purple); color:#fff; }

.mobile-slide-enter-active,.mobile-slide-leave-active { transition:all .28s ease; }
.mobile-slide-enter-from,.mobile-slide-leave-to { opacity:0; transform:translateY(-10px); }

@media(max-width:768px){
  .nav-tabs { display:none; }
  .hamburger { display:flex; }
  .btn-dl:not(.w-full) { display:none; }
}
</style>
