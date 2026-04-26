<template>
  <div class="chat-view">
    <!-- Left: Conversation Panel -->
    <aside class="conv-panel">
      <div class="conv-header">
        <div class="conv-header-left">
          <div class="chat-avatar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
            </svg>
          </div>
          <div>
            <p class="conv-title">Data Assistant</p>
            <p class="conv-status">
              <span class="status-dot" :class="{ ready: chatReady }" />
              {{ chatReady ? 'Ready' : 'Initializing…' }}
            </p>
          </div>
        </div>
        <div class="conv-header-right">
          <button class="btn-icon" @click="clearChat" title="Clear conversation">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Messages -->
      <div class="conv-messages" ref="msgContainer">
        <!-- Welcome -->
        <div class="msg-row bot" v-if="messages.length === 0">
          <div class="msg-bubble bot welcome-bubble">
            <p>👋 Hi! I can answer questions about your transaction data.</p>
            <p style="margin-top:10px;font-size:12px;opacity:.7">Try one of these to get started:</p>
            <div class="starter-chips">
              <button v-for="s in starters" :key="s" class="chip" @click="sendText(s)">{{ s }}</button>
            </div>
          </div>
        </div>

        <template v-for="(msg, i) in messages" :key="i">
          <div class="msg-row" :class="msg.role">
            <div class="msg-bubble" :class="msg.role">
              <div class="msg-text" v-html="renderMd(msg.content)" />

              <div v-if="msg.confidence != null" class="msg-meta">
                <span class="conf-badge" :class="confClass(msg.confidence)">
                  {{ Math.round(msg.confidence * 100) }}% confidence
                </span>
              </div>

              <!-- Follow-up chips -->
              <div v-if="msg.followups?.length" class="followup-chips">
                <button v-for="(f, fi) in msg.followups.slice(0,4)" :key="fi"
                  class="chip" @click="sendText(f)">{{ f }}</button>
              </div>

              <!-- Table inline preview (3 rows) + expand button -->
              <div v-if="msg.tableRows?.length" class="table-inline-preview">
                <div class="table-preview-header">
                  <span class="table-preview-label">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px">
                      <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/>
                      <line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="9" x2="9" y2="21"/><line x1="15" y1="9" x2="15" y2="21"/>
                    </svg>
                    {{ msg.tableRows.length }} rows returned
                  </span>
                  <button class="btn-expand-table" @click="openTable(msg.tableRows, msg.content)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:12px;height:12px">
                      <polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/>
                      <line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
                    </svg>
                    View full table
                  </button>
                </div>
                <div class="table-scroll-mini">
                  <table>
                    <thead><tr>
                      <th v-for="h in Object.keys(msg.tableRows[0])" :key="h">{{ h }}</th>
                    </tr></thead>
                    <tbody>
                      <tr v-for="(row, ri) in msg.tableRows.slice(0, 3)" :key="ri">
                        <td v-for="h in Object.keys(msg.tableRows[0])" :key="h">{{ row[h] ?? '—' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p v-if="msg.tableRows.length > 3" class="table-more-hint">
                  +{{ msg.tableRows.length - 3 }} more rows — click "View full table" to explore
                </p>
              </div>
            </div>
          </div>
        </template>

        <!-- Typing indicator -->
        <div v-if="thinking" class="msg-row bot">
          <div class="msg-bubble bot typing">
            <span /><span /><span />
          </div>
        </div>
      </div>

      <!-- Input -->
      <div class="conv-input-row">
        <textarea
          v-model="inputText"
          class="conv-input"
          placeholder="Ask about your data…"
          rows="1"
          @keydown.enter.exact.prevent="send"
          @input="autoResize"
          ref="inputEl"
        />
        <button class="btn-send" @click="send" :disabled="thinking || !inputText.trim()">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </aside>

    <!-- Right: Data Table Panel -->
    <section class="table-panel" :class="{ 'has-data': activeTable.length > 0 }">
      <!-- Empty state -->
      <div v-if="activeTable.length === 0" class="table-empty">
        <div class="empty-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <line x1="3" y1="9" x2="21" y2="9"/>
            <line x1="3" y1="15" x2="21" y2="15"/>
            <line x1="9" y1="9" x2="9" y2="21"/>
            <line x1="15" y1="9" x2="15" y2="21"/>
          </svg>
        </div>
        <p class="empty-title">No data loaded yet</p>
        <p class="empty-sub">Ask a question that returns tabular data — it'll appear here for interactive exploration.</p>
        <div class="empty-examples">
          <span v-for="ex in tableExamples" :key="ex" class="ex-chip" @click="sendText(ex)">{{ ex }}</span>
        </div>
      </div>

      <!-- Table -->
      <template v-else>
        <div class="table-toolbar">
          <div class="table-toolbar-left">
            <p class="table-context">{{ activeTableContext }}</p>
            <span class="table-count">{{ filteredRows.length }} / {{ activeTable.length }} rows</span>
          </div>
          <div class="table-toolbar-right">
            <div class="search-box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px;flex-shrink:0">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
              <input v-model="tableSearch" placeholder="Search…" class="search-input" />
            </div>
            <button class="btn-export" @click="exportCSV" title="Export CSV">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px">
                <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
              CSV
            </button>
            <button class="btn-icon-sm" @click="clearTable" title="Clear table">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:13px;height:13px">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th v-for="col in tableColumns" :key="col"
                  @click="sortBy(col)" class="sortable-th"
                  :class="{ 'sort-active': sortCol === col }">
                  {{ col }}
                  <span class="sort-arrow">
                    {{ sortCol === col ? (sortDir === 'asc' ? '↑' : '↓') : '↕' }}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in paginatedRows" :key="ri"
                class="data-row"
                :class="{ 'row-highlight': isHighlighted(row) }">
                <td v-for="col in tableColumns" :key="col">
                  <span class="cell-val" :class="cellClass(col, row[col])">
                    {{ row[col] ?? '—' }}
                  </span>
                </td>
              </tr>
              <tr v-if="filteredRows.length === 0">
                <td :colspan="tableColumns.length" class="no-results">No rows match your search.</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Pagination -->
        <div class="table-pagination">
          <span class="pag-info">Page {{ page }} of {{ totalPages }}</span>
          <div class="pag-controls">
            <button class="pag-btn" @click="page = 1"          :disabled="page === 1">«</button>
            <button class="pag-btn" @click="page--"            :disabled="page === 1">‹</button>
            <button v-for="p in visiblePages" :key="p"
              class="pag-btn" :class="{ active: p === page }"
              @click="page = p">{{ p }}</button>
            <button class="pag-btn" @click="page++"            :disabled="page === totalPages">›</button>
            <button class="pag-btn" @click="page = totalPages" :disabled="page === totalPages">»</button>
          </div>
          <select class="pag-size" v-model="pageSize" @change="page = 1">
            <option :value="10">10 / page</option>
            <option :value="25">25 / page</option>
            <option :value="50">50 / page</option>
            <option :value="100">100 / page</option>
          </select>
        </div>
      </template>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { chatbotQuery, chatbotDatasetInfo } from "@/services/api"

// ── Chat state ────────────────────────────────────────────────────────────────
const chatReady   = ref(false)
const thinking    = ref(false)
const inputText   = ref('')
const messages    = ref([])
const msgContainer = ref(null)
const inputEl     = ref(null)
const sessionId   = `session_${Date.now()}`

const starters = [
  'How many transactions are there?',
  'Show high-risk transactions',
  'Group transactions by country',
  'What is the average transaction amount?',
]

const tableExamples = [
  'List transactions above $10,000',
  'Show suspicious patterns',
  'Group by sender country',
  'Find high-risk senders',
]

onMounted(async () => {
  try { await chatbotDatasetInfo(); chatReady.value = true } catch { chatReady.value = false }

  // Pick up table data forwarded from the floating sidebar
  try {
    const pending = sessionStorage.getItem('chatview_pending_table')
    if (pending) {
      const { rows, context } = JSON.parse(pending)
      sessionStorage.removeItem('chatview_pending_table')
      if (rows?.length) openTable(rows, context)
    }
  } catch { /* ignore */ }
})

function renderMd(text) {
  if (!text) return ''
  return text
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/_(.*?)_/g, '<em>$1</em>')
    .replace(/`(.*?)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br/>')
}

function confClass(c) {
  if (c >= 0.7) return 'high'
  if (c >= 0.4) return 'med'
  return 'low'
}

async function scrollDown() {
  await nextTick()
  if (msgContainer.value) msgContainer.value.scrollTop = msgContainer.value.scrollHeight
}

function autoResize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 140) + 'px'
}

async function send() {
  const q = inputText.value.trim()
  if (!q || thinking.value) return
  inputText.value = ''
  if (inputEl.value) inputEl.value.style.height = 'auto'

  messages.value.push({ role: 'user', content: q })
  await scrollDown()
  thinking.value = true

  try {
    const res  = await chatbotQuery(q, sessionId)
    const data = res.data
    const tableRows = data.table_data || []

    messages.value.push({
      role:       'bot',
      content:    data.answer || 'No answer returned.',
      confidence: data.confidence,
      followups:  data.followup_suggestions || [],
      tableRows,
    })

    // Auto-load table panel if data came back
    if (tableRows.length) openTable(tableRows, data.answer)
  } catch (e) {
    messages.value.push({ role: 'bot', content: `❌ Error: ${e.response?.data?.detail || e.message}` })
  } finally {
    thinking.value = false
    await scrollDown()
  }
}

function sendText(text) {
  inputText.value = text
  send()
}

function clearChat() {
  messages.value = []
  clearTable()
}

// ── Table state ───────────────────────────────────────────────────────────────
const activeTable        = ref([])
const activeTableContext = ref('')
const tableSearch        = ref('')
const sortCol            = ref('')
const sortDir            = ref('asc')
const page               = ref(1)
const pageSize           = ref(25)

const tableColumns = computed(() => {
  if (!activeTable.value.length) return []
  return Object.keys(activeTable.value[0])
})

const filteredRows = computed(() => {
  let rows = activeTable.value
  if (tableSearch.value.trim()) {
    const q = tableSearch.value.toLowerCase()
    rows = rows.filter(row =>
      Object.values(row).some(v => String(v ?? '').toLowerCase().includes(q))
    )
  }
  if (sortCol.value) {
    rows = [...rows].sort((a, b) => {
      const av = a[sortCol.value] ?? ''
      const bv = b[sortCol.value] ?? ''
      const an = parseFloat(av), bn = parseFloat(bv)
      const cmp = !isNaN(an) && !isNaN(bn) ? an - bn : String(av).localeCompare(String(bv))
      return sortDir.value === 'asc' ? cmp : -cmp
    })
  }
  return rows
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value)))

const paginatedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

const visiblePages = computed(() => {
  const total = totalPages.value
  const cur   = page.value
  const pages = []
  for (let p = Math.max(1, cur - 2); p <= Math.min(total, cur + 2); p++) pages.push(p)
  return pages
})

// Reset to page 1 on filter/sort change
watch([tableSearch, sortCol, sortDir], () => { page.value = 1 })

function sortBy(col) {
  if (sortCol.value === col) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortCol.value = col
    sortDir.value = 'asc'
  }
}

function openTable(rows, context = '') {
  activeTable.value        = rows
  activeTableContext.value = context ? context.replace(/<[^>]*>/g, '').slice(0, 120) : ''
  tableSearch.value        = ''
  sortCol.value            = ''
  page.value               = 1
}

function clearTable() {
  activeTable.value        = []
  activeTableContext.value = ''
  tableSearch.value        = ''
}

// Highlight rows with suspicious/high-risk keywords
const riskCols = ['risk', 'risk_score', 'risk_category', 'label', 'fraud', 'anomaly']
function isHighlighted(row) {
  return riskCols.some(c => {
    const v = String(row[c] ?? '').toLowerCase()
    return v.includes('critical') || v.includes('high') || v === 'true' || v === '1'
  })
}

function cellClass(col, val) {
  const c = col.toLowerCase(), v = String(val ?? '').toLowerCase()
  if (c.includes('risk') || c.includes('fraud') || c.includes('anomaly')) {
    if (v.includes('critical') || v === 'true' || v === '1') return 'val-critical'
    if (v.includes('high'))   return 'val-high'
    if (v.includes('medium')) return 'val-medium'
    if (v.includes('low'))    return 'val-low'
  }
  return ''
}

function exportCSV() {
  const cols = tableColumns.value
  const header = cols.join(',')
  const rows = filteredRows.value.map(r => cols.map(c => JSON.stringify(String(r[c] ?? ''))).join(','))
  const csv  = [header, ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url  = URL.createObjectURL(blob)
  const a    = Object.assign(document.createElement('a'), { href: url, download: 'query_results.csv' })
  document.body.appendChild(a); a.click()
  document.body.removeChild(a); URL.revokeObjectURL(url)
}
</script>

<style scoped>
/* ── Layout ──────────────────────────────────────────────────────────────── */
.chat-view {
  display: flex;
  height: calc(100vh - 64px);
  margin-top: 64px;
  overflow: hidden;
}

/* ── Conversation Panel ──────────────────────────────────────────────────── */
.conv-panel {
  width: 420px;
  min-width: 340px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg2);
  border-right: 1px solid var(--border);
  overflow: hidden;
}

.conv-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
  background: rgba(255,255,255,.02);
  flex-shrink: 0;
}
.conv-header-left { display: flex; align-items: center; gap: 12px; }
.conv-header-right { display: flex; align-items: center; gap: 8px; }

.chat-avatar {
  width: 40px; height: 40px; border-radius: 50%;
  background: linear-gradient(135deg, var(--purple), var(--purple-light));
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.chat-avatar svg { width: 20px; height: 20px; }
.conv-title  { font-size: 15px; font-weight: 700; }
.conv-status { font-size: 11px; color: var(--muted); display: flex; align-items: center; gap: 5px; margin-top: 2px; }
.status-dot  { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); transition: background .3s; flex-shrink: 0; }
.status-dot.ready { background: var(--low); animation: pulse 2s infinite; }

.conv-messages {
  flex: 1; overflow-y: auto;
  padding: 18px 16px;
  display: flex; flex-direction: column; gap: 14px;
}

.msg-row { display: flex; }
.msg-row.user { justify-content: flex-end; }
.msg-row.bot  { justify-content: flex-start; }

.msg-bubble {
  max-width: 90%; padding: 12px 16px;
  border-radius: 18px; font-size: 13px; line-height: 1.6;
}
.msg-bubble.user {
  background: linear-gradient(135deg, var(--purple), var(--purple-light));
  color: #fff; border-bottom-right-radius: 4px;
}
.msg-bubble.bot {
  background: var(--surface2); border: 1px solid var(--border);
  color: var(--text); border-bottom-left-radius: 4px;
}
.msg-bubble.bot :deep(code) {
  background: rgba(255,255,255,.08); padding: 1px 5px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 12px;
}
.msg-bubble.bot :deep(strong) { color: var(--accent); }

.welcome-bubble { background: linear-gradient(135deg, rgba(124,58,237,.12), rgba(168,85,247,.08)); border: 1px solid rgba(124,58,237,.2); }

/* Typing */
.typing { display: flex; align-items: center; gap: 5px; padding: 16px 20px; }
.typing span {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--muted); animation: bounce 1.2s infinite;
}
.typing span:nth-child(2) { animation-delay: .2s; }
.typing span:nth-child(3) { animation-delay: .4s; }

@keyframes bounce { 0%,80%,100%{ transform:translateY(0) } 40%{ transform:translateY(-7px) } }

.msg-meta { margin-top: 8px; }
.conf-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 6px; }
.conf-badge.high { background: rgba(34,197,94,.15);  color: var(--low); }
.conf-badge.med  { background: rgba(234,179,8,.15);  color: var(--medium); }
.conf-badge.low  { background: rgba(239,68,68,.15);  color: var(--critical); }

/* Follow-up chips */
.followup-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.starter-chips  { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.chip {
  background: rgba(124,58,237,.12); border: 1px solid rgba(124,58,237,.3);
  color: var(--accent); font-size: 11px; padding: 5px 11px; border-radius: 20px;
  cursor: pointer; transition: all .2s; text-align: left;
}
.chip:hover { background: rgba(124,58,237,.25); transform: translateY(-1px); }

/* Inline table preview */
.table-inline-preview {
  margin-top: 12px; border-radius: 10px; overflow: hidden;
  border: 1px solid rgba(124,58,237,.2); font-size: 11px;
}
.table-preview-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 7px 10px; background: rgba(124,58,237,.08);
  border-bottom: 1px solid rgba(124,58,237,.15);
}
.table-preview-label {
  display: flex; align-items: center; gap: 5px;
  color: var(--accent); font-weight: 600; font-size: 11px;
}
.btn-expand-table {
  display: flex; align-items: center; gap: 5px;
  background: var(--purple); border: none; color: #fff;
  font-size: 11px; padding: 4px 10px; border-radius: 6px;
  cursor: pointer; font-family: var(--font-sans); transition: all .2s;
}
.btn-expand-table:hover { background: var(--purple-light); }
.table-scroll-mini { overflow-x: auto; max-height: 120px; overflow-y: auto; }
.table-scroll-mini table { width: 100%; border-collapse: collapse; }
.table-scroll-mini th {
  padding: 5px 8px; background: rgba(255,255,255,.04);
  text-align: left; font-weight: 700; color: var(--muted);
  white-space: nowrap; position: sticky; top: 0;
}
.table-scroll-mini td {
  padding: 4px 8px; border-top: 1px solid rgba(255,255,255,.04);
  white-space: nowrap; max-width: 140px; overflow: hidden; text-overflow: ellipsis;
}
.table-more-hint {
  padding: 5px 10px; color: var(--muted); font-size: 10px;
  background: rgba(255,255,255,.02); border-top: 1px solid rgba(255,255,255,.04);
  text-align: center;
}

/* Input */
.conv-input-row {
  display: flex; align-items: flex-end; gap: 8px;
  padding: 14px 16px; border-top: 1px solid var(--border);
  flex-shrink: 0;
}
.conv-input {
  flex: 1; background: rgba(255,255,255,.05); border: 1px solid var(--border);
  color: var(--text); border-radius: 14px; padding: 11px 15px;
  font-size: 13px; font-family: var(--font-sans); resize: none;
  outline: none; transition: border-color .2s; line-height: 1.5;
  max-height: 140px; overflow-y: auto;
}
.conv-input:focus { border-color: var(--purple); }
.conv-input::placeholder { color: rgba(148,163,184,.4); }
.btn-send {
  width: 40px; height: 40px; border-radius: 12px; flex-shrink: 0;
  background: var(--purple); border: none; color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all .2s; box-shadow: 0 0 16px var(--purple-glow);
}
.btn-send svg { width: 15px; height: 15px; }
.btn-send:hover:not(:disabled) { background: var(--purple-light); }
.btn-send:disabled { opacity: .4; cursor: not-allowed; }

/* ── Table Panel ─────────────────────────────────────────────────────────── */
.table-panel {
  flex: 1; display: flex; flex-direction: column;
  overflow: hidden; background: var(--bg);
  transition: background .3s;
}
.table-panel.has-data { background: var(--bg); }

/* Empty state */
.table-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 14px; padding: 40px;
  color: var(--muted); text-align: center;
}
.empty-icon {
  width: 72px; height: 72px; border-radius: 20px;
  background: rgba(124,58,237,.08); border: 1px solid rgba(124,58,237,.15);
  display: flex; align-items: center; justify-content: center;
}
.empty-icon svg { width: 32px; height: 32px; color: var(--accent); }
.empty-title { font-size: 17px; font-weight: 700; color: var(--text); }
.empty-sub   { font-size: 13px; max-width: 360px; line-height: 1.6; }
.empty-examples { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 8px; }
.ex-chip {
  background: rgba(124,58,237,.1); border: 1px solid rgba(124,58,237,.2);
  color: var(--accent); font-size: 12px; padding: 6px 14px; border-radius: 20px;
  cursor: pointer; transition: all .2s;
}
.ex-chip:hover { background: rgba(124,58,237,.22); transform: translateY(-1px); }

/* Toolbar */
.table-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 20px; border-bottom: 1px solid var(--border);
  background: rgba(255,255,255,.02); flex-shrink: 0; gap: 12px; flex-wrap: wrap;
}
.table-toolbar-left { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.table-context {
  font-size: 12px; color: var(--muted); white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; max-width: 500px;
}
.table-count { font-size: 11px; color: var(--accent); font-weight: 600; }

.table-toolbar-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

.search-box {
  display: flex; align-items: center; gap: 8px;
  background: rgba(255,255,255,.05); border: 1px solid var(--border);
  border-radius: 10px; padding: 7px 12px;
  transition: border-color .2s;
}
.search-box:focus-within { border-color: var(--purple); }
.search-input {
  background: transparent; border: none; outline: none;
  color: var(--text); font-size: 13px; font-family: var(--font-sans);
  width: 180px;
}
.search-input::placeholder { color: rgba(148,163,184,.4); }

.btn-export {
  display: flex; align-items: center; gap: 6px;
  background: rgba(34,197,94,.1); border: 1px solid rgba(34,197,94,.2);
  color: var(--low); font-size: 12px; font-weight: 600; padding: 7px 14px;
  border-radius: 10px; cursor: pointer; transition: all .2s; font-family: var(--font-sans);
}
.btn-export:hover { background: rgba(34,197,94,.18); }

.btn-icon { background: transparent; border: 1px solid var(--border); color: var(--muted); border-radius: 8px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all .2s; }
.btn-icon:hover { color: var(--critical); border-color: var(--critical); }
.btn-icon-sm { background: transparent; border: 1px solid var(--border); color: var(--muted); border-radius: 8px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: all .2s; }
.btn-icon-sm:hover { color: var(--critical); border-color: var(--critical); }

/* Data table */
.table-container { flex: 1; overflow: auto; }

.data-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.data-table thead { position: sticky; top: 0; z-index: 2; }

.sortable-th {
  padding: 11px 14px;
  background: rgba(13,13,43,.95); backdrop-filter: blur(10px);
  text-align: left; font-weight: 700; font-size: 11px;
  color: var(--muted); white-space: nowrap;
  border-bottom: 1px solid var(--border);
  cursor: pointer; user-select: none; transition: color .15s;
}
.sortable-th:hover { color: var(--text); }
.sortable-th.sort-active { color: var(--accent); }
.sort-arrow { margin-left: 4px; font-size: 10px; opacity: .7; }

.data-row { transition: background .12s; }
.data-row:hover { background: rgba(255,255,255,.04); }
.data-row.row-highlight { background: rgba(239,68,68,.05); }
.data-row.row-highlight:hover { background: rgba(239,68,68,.09); }

.data-table td {
  padding: 9px 14px; border-bottom: 1px solid rgba(255,255,255,.04);
  white-space: nowrap; max-width: 220px; overflow: hidden; text-overflow: ellipsis;
}

.cell-val { font-size: 12px; }
.val-critical { color: var(--critical); font-weight: 700; }
.val-high     { color: var(--high);     font-weight: 600; }
.val-medium   { color: var(--medium);   font-weight: 600; }
.val-low      { color: var(--low); }

.no-results { text-align: center; padding: 32px; color: var(--muted); font-style: italic; }

/* Pagination */
.table-pagination {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 18px; border-top: 1px solid var(--border);
  background: rgba(255,255,255,.02); flex-shrink: 0; flex-wrap: wrap; gap: 8px;
}
.pag-info { font-size: 12px; color: var(--muted); }
.pag-controls { display: flex; align-items: center; gap: 4px; }
.pag-btn {
  width: 30px; height: 30px; border-radius: 8px; font-size: 12px;
  background: rgba(255,255,255,.04); border: 1px solid var(--border);
  color: var(--muted); cursor: pointer; transition: all .15s;
  display: flex; align-items: center; justify-content: center;
  font-family: var(--font-sans);
}
.pag-btn:hover:not(:disabled) { background: var(--surface2); color: var(--text); }
.pag-btn.active { background: var(--purple); border-color: var(--purple); color: #fff; }
.pag-btn:disabled { opacity: .3; cursor: not-allowed; }

.pag-size {
  background: rgba(255,255,255,.05); border: 1px solid var(--border);
  color: var(--muted); border-radius: 8px; padding: 5px 8px;
  font-size: 12px; font-family: var(--font-sans); cursor: pointer; outline: none;
}
.pag-size:focus { border-color: var(--purple); }

/* Responsive */
@media (max-width: 768px) {
  .chat-view { flex-direction: column; }
  .conv-panel { width: 100%; min-width: unset; height: 50vh; border-right: none; border-bottom: 1px solid var(--border); }
  .table-panel { height: 50vh; }
}

@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(1.4)} }
</style>
