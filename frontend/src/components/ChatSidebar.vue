<template>
  <!-- Toggle button (always visible) -->
  <button class="chat-toggle" @click="open = !open" :class="{ pulsing: !open && hasUnread }" title="Ask about your data">
    <svg v-if="!open" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
    </svg>
    <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
    <span v-if="!open && hasUnread" class="unread-dot" />
  </button>

  <!-- Sidebar panel -->
  <Transition name="chat-slide">
    <div v-if="open" class="chat-panel">
      <div class="chat-header">
        <div class="chat-header-left">
          <div class="chat-avatar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
            </svg>
          </div>
          <div class="chat-title-wrap">
            <p class="chat-title">Data Assistant</p>
            <div style="display:flex; align-items:center; gap:6px; margin-top:2px;">
              <span class="status-dot" :class="{ ready: chatReady }" />
              <select v-if="batches.length > 0" v-model="selectedBatch" class="batch-select" @change="onBatchChange">
                <option value="">Latest Upload</option>
                <option v-for="b in batches" :key="b.batch_id" :value="b.batch_id">
                  {{ b.original_filename || b.batch_id.slice(0,8) }}
                </option>
              </select>
              <span v-else class="chat-status" style="margin:0;">
                {{ chatReady ? 'Ready' : 'Initializing…' }}
              </span>
            </div>
          </div>
        </div>
        <button class="btn-icon" @click="clearChat" title="Clear chat">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:15px;height:15px">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/>
          </svg>
        </button>
      </div>

      <!-- Messages -->
      <div class="chat-messages" ref="msgContainer">
        <!-- Welcome message -->
        <div class="msg-row bot" v-if="messages.length === 0">
          <div class="msg-bubble bot">
            <p>👋 Hi! I can answer questions about your transaction data.</p>
            <p style="margin-top:8px;font-size:12px;opacity:.7">Try: <em>"How many transactions are there?"</em> or <em>"Show suspicious patterns"</em></p>
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
                <button v-for="(f, fi) in msg.followups.slice(0,3)" :key="fi"
                  class="chip" @click="sendFollowup(f)">{{ f }}</button>
              </div>
              <!-- Table preview -->
              <div v-if="msg.tableRows?.length" class="table-preview">
                <div class="table-preview-bar">
                  <span class="tbl-label">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:10px;height:10px">
                      <rect x="3" y="3" width="18" height="18" rx="2"/>
                      <line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/>
                      <line x1="9" y1="9" x2="9" y2="21"/><line x1="15" y1="9" x2="15" y2="21"/>
                    </svg>
                    {{ msg.tableRows.length }} rows
                  </span>
                  <button class="btn-open-chat" @click="openInChatTab(msg.tableRows, msg.content)">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:10px;height:10px">
                      <polyline points="15 3 21 3 21 9"/><line x1="21" y1="3" x2="14" y2="10"/>
                      <path d="M10 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-6"/>
                    </svg>
                    Open in Chat tab
                  </button>
                </div>
                <table>
                  <thead><tr>
                    <th v-for="h in Object.keys(msg.tableRows[0])" :key="h">{{ h }}</th>
                  </tr></thead>
                  <tbody>
                    <tr v-for="(row, ri) in msg.tableRows.slice(0,5)" :key="ri">
                      <td v-for="h in Object.keys(msg.tableRows[0])" :key="h">{{ row[h] ?? '—' }}</td>
                    </tr>
                  </tbody>
                </table>
                <p v-if="msg.tableRows.length > 5" class="table-more">+{{ msg.tableRows.length - 5 }} more rows</p>
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
      <div class="chat-input-row">
        <textarea
          v-model="inputText"
          class="chat-input"
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
    </div>
  </Transition>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { chatbotQuery, chatbotDatasetInfo, getMyBatches } from '@/services/api'

const router     = useRouter()

const open       = ref(false)
const chatReady  = ref(false)
const thinking   = ref(false)
const hasUnread  = ref(false)
const inputText  = ref('')
const messages   = ref([])
const msgContainer = ref(null)
const inputEl    = ref(null)
const sessionId  = `session_${Date.now()}`

const batches = ref([])
const selectedBatch = ref('')

// Check health on mount
onMounted(async () => {
  try {
    const res = await getMyBatches(100, 0)
    batches.value = res.data?.batches || []
  } catch (e) {
    console.error('Failed to fetch batches', e)
  }
  try { await chatbotDatasetInfo(selectedBatch.value || null); chatReady.value = true } catch { chatReady.value = false }
})

async function onBatchChange() {
  chatReady.value = false
  messages.value = []
  try {
    await chatbotDatasetInfo(selectedBatch.value || null)
    chatReady.value = true
  } catch {
    chatReady.value = false
  }
}

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
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

async function send() {
  const q = inputText.value.trim()
  if (!q || thinking.value) return
  inputText.value = ''
  if (inputEl.value) { inputEl.value.style.height = 'auto' }

  messages.value.push({ role: 'user', content: q })
  await scrollDown()
  thinking.value = true

  try {
    const res  = await chatbotQuery(q, sessionId, selectedBatch.value || null)
    const data = res.data
    messages.value.push({
      role:       'bot',
      content:    data.answer || 'No answer returned.',
      confidence: data.confidence,
      followups:  data.followup_suggestions || [],
      tableRows:  data.table_data || [],
    })
    hasUnread.value = !open.value
  } catch (e) {
    messages.value.push({ role: 'bot', content: `❌ Error: ${e.response?.data?.detail || e.message}` })
  } finally {
    thinking.value = false
    await scrollDown()
  }
}

function sendFollowup(text) {
  inputText.value = text
  send()
}

function openInChatTab(rows, context) {
  // Store pending table data in sessionStorage so ChatView can pick it up
  sessionStorage.setItem('chatview_pending_table', JSON.stringify({ rows, context: context || '' }))
  open.value = false
  router.push('/chat')
}

function clearChat() {
  messages.value = []
  hasUnread.value = false
}
</script>

<style scoped>
/* Toggle button */
.chat-toggle {
  position: fixed; bottom: 24px; right: 24px; z-index: 200;
  width: 52px; height: 52px; border-radius: 50%;
  background: linear-gradient(135deg, var(--purple), var(--purple-light));
  border: none; color: #fff; display: flex; align-items: center; justify-content: center;
  box-shadow: 0 0 32px var(--purple-glow); cursor: pointer; transition: all .3s;
}
.chat-toggle svg { width: 22px; height: 22px; }
.chat-toggle:hover { transform: scale(1.08); box-shadow: 0 0 50px var(--purple-glow); }
.chat-toggle.pulsing { animation: pulse-btn 2s infinite; }
.unread-dot {
  position: absolute; top: 6px; right: 6px; width: 10px; height: 10px;
  background: var(--critical); border-radius: 50%; border: 2px solid var(--bg);
}

/* Panel */
.chat-panel {
  position: fixed; bottom: 88px; right: 24px; z-index: 199;
  width: min(560px, calc(100vw - 32px)); height: min(78vh, calc(100vh - 110px));
  background: var(--bg2); border: 1px solid var(--border);
  border-radius: 20px; display: flex; flex-direction: column;
  box-shadow: 0 24px 80px rgba(0,0,0,.5), 0 0 40px rgba(124,58,237,.15);
  overflow: hidden;
}

/* Header */
.chat-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 18px; border-bottom: 1px solid var(--border);
  background: rgba(255,255,255,.02);
}
.chat-header-left { display: flex; align-items: center; gap: 12px; }
.chat-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, var(--purple), var(--purple-light));
  display: flex; align-items: center; justify-content: center;
}
.chat-avatar svg { width: 18px; height: 18px; }
.chat-title  { font-size: 14px; font-weight: 700; }
.chat-status { font-size: 11px; color: var(--muted); }
.status-dot  { width: 6px; height: 6px; border-radius: 50%; background: var(--muted); transition: background .3s; display: inline-block;}
.status-dot.ready { background: var(--low); animation: pulse 2s infinite; }

.batch-select {
  background: rgba(255,255,255,.05); border: 1px solid var(--border);
  color: var(--text); border-radius: 4px; padding: 2px 4px;
  font-size: 10px; font-family: var(--font-sans); cursor: pointer; outline: none; max-width: 130px; text-overflow: ellipsis; white-space: nowrap; overflow: hidden;
}
.batch-select:focus { border-color: var(--purple); }
.batch-select option {
  background: #1e1e2e; /* solid dark background for the dropdown menu */
  color: #fff;
}

.btn-icon {
  background: transparent; border: 1px solid var(--border);
  color: var(--muted); border-radius: 8px; width: 30px; height: 30px;
  display: flex; align-items: center; justify-content: center;
  transition: all .2s; cursor: pointer;
}
.btn-icon:hover { color: var(--critical); border-color: var(--critical); }

/* Messages */
.chat-messages {
  flex: 1; overflow-y: auto; padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
}

.msg-row { display: flex; }
.msg-row.user { justify-content: flex-end; }
.msg-row.bot  { justify-content: flex-start; }

.msg-bubble {
  max-width: 85%; padding: 10px 14px; border-radius: 16px; font-size: 13px; line-height: 1.5;
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

/* Typing */
.typing { display: flex; align-items: center; gap: 4px; padding: 14px 18px; }
.typing span {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--muted); animation: bounce 1.2s infinite;
}
.typing span:nth-child(2) { animation-delay: .2s; }
.typing span:nth-child(3) { animation-delay: .4s; }

@keyframes bounce { 0%,80%,100%{ transform:translateY(0) } 40%{ transform:translateY(-6px) } }

.msg-meta { margin-top: 6px; }
.conf-badge {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 6px;
}
.conf-badge.high { background: rgba(34,197,94,.15);  color: var(--low); }
.conf-badge.med  { background: rgba(234,179,8,.15);  color: var(--medium); }
.conf-badge.low  { background: rgba(239,68,68,.15);  color: var(--critical); }

/* Follow-up chips */
.followup-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.chip {
  background: rgba(124,58,237,.12); border: 1px solid rgba(124,58,237,.25);
  color: var(--accent); font-size: 11px; padding: 4px 10px; border-radius: 20px;
  cursor: pointer; transition: all .2s; text-align: left;
}
.chip:hover { background: rgba(124,58,237,.25); }

/* Table preview */
.table-preview {
  margin-top: 10px; border-radius: 8px; overflow: hidden;
  border: 1px solid rgba(255,255,255,.06); font-size: 11px;
}
.table-preview-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 5px 8px; background: rgba(124,58,237,.08);
  border-bottom: 1px solid rgba(124,58,237,.15);
}
.tbl-label {
  display: flex; align-items: center; gap: 4px;
  color: var(--accent); font-weight: 600; font-size: 10px;
}
.btn-open-chat {
  display: flex; align-items: center; gap: 4px;
  background: var(--purple); border: none; color: #fff;
  font-size: 10px; padding: 3px 8px; border-radius: 5px;
  cursor: pointer; font-family: var(--font-sans); transition: all .2s;
}
.btn-open-chat:hover { background: var(--purple-light); }
.table-preview table { width: 100%; border-collapse: collapse; }
.table-preview th {
  padding: 6px 8px; background: rgba(255,255,255,.05);
  text-align: left; font-weight: 700; color: var(--muted);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 120px;
}
.table-preview td {
  padding: 5px 8px; border-top: 1px solid rgba(255,255,255,.03);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 120px;
}
.table-more {
  padding: 6px 8px; color: var(--muted); text-align: center;
  background: rgba(255,255,255,.03); border-top: 1px solid rgba(255,255,255,.04);
}

/* Input row */
.chat-input-row {
  display: flex; align-items: flex-end; gap: 8px;
  padding: 12px 14px; border-top: 1px solid var(--border);
}
.chat-input {
  flex: 1; background: rgba(255,255,255,.05); border: 1px solid var(--border);
  color: var(--text); border-radius: 12px; padding: 10px 14px;
  font-size: 13px; font-family: var(--font-sans); resize: none;
  outline: none; transition: border-color .2s; line-height: 1.4;
  max-height: 120px; overflow-y: auto;
}
.chat-input:focus { border-color: var(--purple); }
.chat-input::placeholder { color: rgba(148,163,184,.4); }

.btn-send {
  width: 38px; height: 38px; border-radius: 12px; flex-shrink: 0;
  background: var(--purple); border: none; color: #fff;
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all .2s; box-shadow: 0 0 16px var(--purple-glow);
}
.btn-send svg { width: 15px; height: 15px; }
.btn-send:hover:not(:disabled) { background: var(--purple-light); }
.btn-send:disabled { opacity: .4; cursor: not-allowed; }

/* Slide animation */
.chat-slide-enter-active, .chat-slide-leave-active { transition: all .28s cubic-bezier(.4,0,.2,1); }
.chat-slide-enter-from, .chat-slide-leave-to { opacity: 0; transform: translateY(20px) scale(.97); }

@keyframes pulse-btn { 0%,100%{ box-shadow:0 0 32px var(--purple-glow) } 50%{ box-shadow:0 0 60px var(--purple-glow) } }
</style>
