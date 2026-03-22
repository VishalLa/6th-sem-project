<template>
  <section class="home">

    <div class="badge"><span class="bdot"/>&nbsp;Try FlowMatrix Now</div>

    <h1 class="hero-title">FL<span class="o">O</span>W-MAT<span class="r">R</span>IX</h1>

    <p class="hero-sub">
      Discover how graph-based technology is revolutionising financial crime detection.
      Are you ready to see what's hiding beneath the surface?
      The future of fraud prevention starts here.
    </p>

    <FileUpload v-model:files="files" class="uploader" />

    <button class="btn-detect" :disabled="loading || !files.length" @click="run">
      <span v-if="loading" class="bspin"/>
      <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="width:16px;height:16px">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </svg>
      {{ loading ? 'Detecting…' : 'Detect' }}
    </button>

    <Transition name="st">
      <p v-if="status.msg" class="status" :class="status.type">{{ status.msg }}</p>
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
import { useRouter } from 'vue-router'
import FileUpload from '@/components/FileUpload.vue'
import { uploadFiles } from '@/services/api'
import { useResultsStore } from '@/stores/results'

const router  = useRouter()
const store   = useResultsStore()
const files   = ref([])
const loading = ref(false)
const status  = reactive({ msg: '', type: '' })

function setStatus(msg, type) { status.msg = msg; status.type = type }

async function run() {
  if (!files.value.length) { setStatus('⚠ Select at least one CSV file.', 'err'); return }
  loading.value = true
  setStatus('Uploading and running detection pipeline…', 'info')
  try {
    const res = await uploadFiles(files.value)
    /*
      res.data shape:
      {
        "file.csv": {
          report:  { suspicious_accounts, fraud_rings, summary:{...} },
          summary: [ { "Ring ID", "Pattern Type", ... }, ... ],
          saved_to: "output/file_analysis.json"
        }
      }
    */
    store.setFromDetection(res.data)
    setStatus('✓ Detection complete! Redirecting to Summary…', 'ok')
    setTimeout(() => router.push('/summary'), 1100)
  } catch (e) {
    const detail = e.response?.data?.detail || e.message
    setStatus(`✗ ${detail}`, 'err')
    console.error(e)
  } finally {
    loading.value = false
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
  min-height:100vh; padding:80px clamp(16px,4vw,48px) 60px;
  display:flex; flex-direction:column; align-items:center;
  justify-content:center; text-align:center; gap:0;
}

.badge {
  display:inline-flex; align-items:center; gap:6px;
  background:rgba(124,58,237,.12); border:1px solid rgba(124,58,237,.3);
  color:var(--accent); font-size:12px; font-weight:600; letter-spacing:.5px;
  padding:6px 16px; border-radius:50px; margin-bottom:26px;
  animation:fadeUp .5s ease both;
}
.bdot { width:6px; height:6px; background:var(--accent); border-radius:50%; animation:pulse 2s infinite; }

.hero-title {
  font-family:var(--font-mono); font-size:clamp(40px,9vw,100px);
  font-weight:700; line-height:1; letter-spacing:clamp(-2px,-.3vw,-3px);
  margin-bottom:22px; animation:fadeUp .5s .08s ease both;
}
.o { color:var(--purple-light); }
.r { color:var(--accent); }

.hero-sub {
  max-width:560px; color:var(--muted); font-size:clamp(14px,1.8vw,16px);
  line-height:1.75; margin-bottom:36px; animation:fadeUp .5s .16s ease both;
}

.uploader { animation:fadeUp .5s .22s ease both; margin-bottom:20px; }

.btn-detect {
  display:flex; align-items:center; gap:10px;
  background:linear-gradient(135deg,var(--purple),var(--purple-light));
  color:#fff; border:none; padding:14px 52px; border-radius:50px;
  font-size:16px; font-weight:700; cursor:pointer; transition:all .3s;
  box-shadow:0 0 32px var(--purple-glow); margin-bottom:18px;
  animation:fadeUp .5s .28s ease both;
}
.btn-detect:hover:not(:disabled) { transform:translateY(-2px); box-shadow:0 0 50px var(--purple-glow); }
.btn-detect:disabled { opacity:.55; cursor:not-allowed; transform:none; }

.bspin {
  width:16px; height:16px; border:2px solid rgba(255,255,255,.3);
  border-top-color:#fff; border-radius:50%; animation:spin .7s linear infinite;
}

.status { font-size:13px; font-weight:500; min-height:20px; margin-bottom:14px; }
.status.ok   { color:var(--low); }
.status.err  { color:var(--critical); }
.status.info { color:var(--muted); }

.st-enter-active,.st-leave-active { transition:all .25s; }
.st-enter-from,.st-leave-to { opacity:0; transform:translateY(6px); }

.features {
  display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr));
  gap:16px; width:100%; max-width:760px; margin-top:44px;
  animation:fadeUp .5s .38s ease both;
}
.feat {
  background:var(--surface); border:1px solid var(--border);
  border-radius:16px; padding:24px 20px; text-align:left; transition:all .2s;
}
.feat:hover { border-color:rgba(124,58,237,.3); background:var(--surface2); transform:translateY(-2px); }
.feat-icon {
  width:40px; height:40px; background:rgba(124,58,237,.15);
  border-radius:10px; display:flex; align-items:center; justify-content:center; margin-bottom:12px;
}
.feat-icon :deep(svg) { width:20px; height:20px; stroke:var(--accent); }
.feat-title { font-size:14px; font-weight:700; margin-bottom:6px; }
.feat-desc  { font-size:13px; color:var(--muted); line-height:1.6; }

@media(max-width:480px){
  .features { grid-template-columns:1fr; }
  .btn-detect { padding:13px 36px; font-size:15px; }
}
</style>
