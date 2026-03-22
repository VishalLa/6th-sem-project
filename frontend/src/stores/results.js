import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useResultsStore = defineStore('results', () => {

  const rings         = ref([])
  const reportsByFile = ref({})
  const pipelineStats = ref(null)
  const loading       = ref(false)
  const error         = ref(null)
  const transactions  = ref([])

  // ── Computed ─────────────────────────────────────────────────────────────
  const totalRings    = computed(() => rings.value.length)
  const criticalCount = computed(() => rings.value.filter(r => cat(r) === 'Critical').length)
  const highCount     = computed(() => rings.value.filter(r => cat(r) === 'High').length)
  const mediumCount   = computed(() => rings.value.filter(r => cat(r) === 'Medium').length)
  const lowCount      = computed(() => rings.value.filter(r => cat(r) === 'Low').length)
  const avgScore      = computed(() => {
    if (!rings.value.length) return '—'
    const avg = rings.value.reduce((s, r) => s + (Number(score(r)) || 0), 0) / rings.value.length
    return avg.toFixed(1)
  })

  // Helpers to read either title-case (CSV) or snake_case (DB) field names
  function cat(r)   { return r['Risk Category']  ?? r.risk_category  ?? '' }
  function score(r) { return r['Risk Score']      ?? r.risk_score     ?? 0  }

  const allFraudRings = computed(() =>
    Object.values(reportsByFile.value).flatMap(r => r.fraud_rings || [])
  )

  const txMetrics = computed(() => {
    const txs = transactions.value
    if (!txs.length) return null
    const amounts  = txs.map(t => Number(t.amount) || 0)
    const total    = amounts.reduce((a, b) => a + b, 0)
    const avg      = total / amounts.length
    const max      = Math.max(...amounts)
    const kyc      = {}
    const methods  = {}
    const countries = {}
    txs.forEach(t => {
      const k = t.sender_kyc || 'None';      kyc[k]         = (kyc[k]         || 0) + 1
      const m = t.txn_method  || 'Unknown';  methods[m]     = (methods[m]     || 0) + 1
      const c = t.sender_country || '??';    countries[c]   = (countries[c]   || 0) + 1
    })
    return { count: txs.length, total, avg, max, kyc, methods, countries }
  })

  // ── Graph data ────────────────────────────────────────────────────────────
  const graphDataByFile = computed(() => {
    const result = {}
    for (const [filename, report] of Object.entries(reportsByFile.value)) {
      const fraudRings = report.fraud_rings         || []
      const suspicious = report.suspicious_accounts || []

      const ringMetaMap = {}
      rings.value.filter(r => r._file === filename).forEach(r => {
        ringMetaMap[r['Ring ID'] || r.ring_id] = r
      })

      const accountRingMap = {}
      fraudRings.forEach(ring => {
        ring.member_accounts.forEach(acc => { accountRingMap[String(acc)] = ring })
      })

      const suspScoreMap = {}
      suspicious.forEach(s => { suspScoreMap[String(s.account_id)] = s.suspicion_score })

      const nodeMap = {}
      const addNode = id => {
        const sid = String(id)
        if (!nodeMap[sid]) nodeMap[sid] = {
          id: sid, isSuspicious: sid in suspScoreMap,
          suspicionScore: suspScoreMap[sid] ?? 0, ring: accountRingMap[sid] ?? null
        }
      }
      fraudRings.forEach(r => r.member_accounts.forEach(addNode))
      suspicious.forEach(s => addNode(s.account_id))

      const edges = []; const edgeSet = new Set()
      const addEdge = (src, dst, ring_id) => {
        const key = `${src}__${dst}`
        if (!edgeSet.has(key)) { edgeSet.add(key); edges.push({ src: String(src), dst: String(dst), ring_id }) }
      }
      fraudRings.forEach(ring => {
        const members = ring.member_accounts.map(String)
        const n = members.length
        if (ring.pattern_type === 'fan_in') {
          for (let i = 1; i < n; i++) addEdge(members[i], members[0], ring.ring_id)
        } else if (ring.pattern_type === 'fan_out') {
          for (let i = 1; i < n; i++) addEdge(members[0], members[i], ring.ring_id)
        } else {
          for (let i = 0; i < n; i++) addEdge(members[i], members[(i+1)%n], ring.ring_id)
          if (n >= 3) addEdge(members[0], members[Math.floor(n/2)], ring.ring_id)
        }
      })

      result[filename] = {
        nodes: Object.values(nodeMap), edges, fraudRings,
        suspiciousAccounts: suspicious, accountRingMap, ringMetaMap
      }
    }
    return result
  })

  // ── Setters ───────────────────────────────────────────────────────────────

  // Old /upload/detect shape: { "file.csv": { report, summary[] } }
  function setFromDetection(responseData) {
    const summaryRows = []; const reportsMap = {}; let latestStats = null
    for (const [filename, payload] of Object.entries(responseData)) {
      if (Array.isArray(payload.summary)) {
        payload.summary.forEach(row => summaryRows.push({ ...row, _file: filename }))
      }
      if (payload.report) { reportsMap[filename] = payload.report; latestStats = payload.report.summary }
    }
    rings.value = summaryRows; reportsByFile.value = reportsMap
    pipelineStats.value = latestStats; error.value = null
  }

  // New /upload/full-pipeline shape: { fraud_rings_summary, detection_results, summary }
  function setFromFullPipeline(data) {
    if (data.fraud_rings_summary?.length) {
      rings.value = data.fraud_rings_summary.map(r => ({ ...r, _file: 'pipeline' }))
    }
    if (data.detection_results) {
      reportsByFile.value = { pipeline: data.detection_results }
    }
    if (data.summary) pipelineStats.value = data.summary
    error.value = null
  }

  // DB rings from /my-fraud-rings — normalize to title-case fields so
  // SummaryTable, StatCards, GraphView all work without changes
  function setFromDBRings(dbRings) {
    if (!dbRings?.length) return

    // Map DB snake_case → CSV Title Case (what all existing components expect)
    const normalized = dbRings.map(r => ({
      'Ring ID':               r.ring_id              ?? r['Ring ID'],
      'Pattern Type':          r.pattern_type         ?? r['Pattern Type'],
      'Member Count':          r.member_count         ?? r['Member Count'],
      'Risk Score':            r.risk_score           ?? r['Risk Score'],
      'Risk Category':         r.risk_category        ?? r['Risk Category'],
      'Avg Member Score':      r.avg_member_score     ?? r['Avg Member Score'],
      'Max Member Score':      r.max_member_score     ?? r['Max Member Score'],
      'Structural Complexity': r.structural_complexity ?? r['Structural Complexity'],
      'Internal Edge Count':   r.internal_edge_count  ?? r['Internal Edge Count'],
      'Ring Density':          r.ring_density         ?? r['Ring Density'],
      'Member Account IDs':    r.member_accounts
                                 ? (Array.isArray(r.member_accounts) ? r.member_accounts.join(', ') : r.member_accounts)
                                 : (r['Member Account IDs'] ?? ''),
      _file: 'db',
      // keep original for graph rendering
      _raw: r,
    }))

    rings.value = normalized

    // Also build a synthetic reportsByFile so GraphView gets data
    // Reconstruct fraud_rings array in the format GraphView expects
    const fraudRings = dbRings.map(r => ({
      ring_id:         r.ring_id,
      pattern_type:    r.pattern_type,
      risk_score:      r.risk_score,
      member_accounts: Array.isArray(r.member_accounts)
        ? r.member_accounts
        : String(r.member_accounts || '').split(',').map(s => s.trim()).filter(Boolean),
    }))

    reportsByFile.value = {
      db: {
        fraud_rings: fraudRings,
        suspicious_accounts: [],
        summary: {
          total_accounts_analyzed: dbRings.reduce((s, r) => s + (r.member_count || 0), 0),
          suspicious_accounts_flagged: dbRings.length,
          fraud_rings_detected: dbRings.length,
          processing_time_seconds: 0,
        }
      }
    }

    pipelineStats.value = reportsByFile.value.db.summary
    error.value = null
  }

  function setTransactions(txList) {
    transactions.value = txList || []
  }

  function clear() {
    rings.value = []; reportsByFile.value = {}; pipelineStats.value = null
    error.value = null; transactions.value = []
  }

  return {
    rings, reportsByFile, pipelineStats, loading, error, transactions,
    totalRings, criticalCount, highCount, mediumCount, lowCount, avgScore,
    allFraudRings, graphDataByFile, txMetrics,
    setFromDetection, setFromFullPipeline, setFromDBRings, setTransactions, clear
  }
})
