import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useResultsStore = defineStore('results', () => {

  const rings         = ref([])
  const reportsByFile = ref({})
  const pipelineStats = ref(null)
  const loading       = ref(false)
  const error         = ref(null)

  const totalRings    = computed(() => rings.value.length)
  const criticalCount = computed(() => rings.value.filter(r => r['Risk Category'] === 'Critical').length)
  const highCount     = computed(() => rings.value.filter(r => r['Risk Category'] === 'High').length)
  const mediumCount   = computed(() => rings.value.filter(r => r['Risk Category'] === 'Medium').length)
  const lowCount      = computed(() => rings.value.filter(r => r['Risk Category'] === 'Low').length)
  const avgScore      = computed(() => {
    if (!rings.value.length) return '—'
    const avg = rings.value.reduce((s, r) => s + (Number(r['Risk Score']) || 0), 0) / rings.value.length
    return avg.toFixed(1)
  })

  const allFraudRings = computed(() =>
    Object.values(reportsByFile.value).flatMap(r => r.fraud_rings || [])
  )

  /**
   * Per-file unified graph data.
   * graphDataByFile[filename] = { nodes, edges, fraudRings, accountRingMap, ringMetaMap }
   */
  const graphDataByFile = computed(() => {
    const result = {}
    for (const [filename, report] of Object.entries(reportsByFile.value)) {
      const fraudRings = report.fraud_rings        || []
      const suspicious = report.suspicious_accounts || []

      // ring_id -> summary row
      const ringMetaMap = {}
      rings.value.filter(r => r._file === filename).forEach(r => {
        ringMetaMap[r['Ring ID']] = r
      })

      // account -> ring
      const accountRingMap = {}
      fraudRings.forEach(ring => {
        ring.member_accounts.forEach(acc => {
          accountRingMap[String(acc)] = ring
        })
      })

      // suspicious score lookup
      const suspScoreMap = {}
      suspicious.forEach(s => { suspScoreMap[String(s.account_id)] = s.suspicion_score })

      // nodes
      const nodeMap = {}
      const addNode = (id) => {
        const sid = String(id)
        if (!nodeMap[sid]) {
          nodeMap[sid] = {
            id:             sid,
            isSuspicious:   sid in suspScoreMap,
            suspicionScore: suspScoreMap[sid] ?? 0,
            ring:           accountRingMap[sid] ?? null
          }
        }
      }
      fraudRings.forEach(r => r.member_accounts.forEach(addNode))
      suspicious.forEach(s => addNode(s.account_id))

      // edges inferred from ring pattern
      const edges   = []
      const edgeSet = new Set()
      const addEdge = (src, dst, ring_id) => {
        const key = `${src}__${dst}`
        if (!edgeSet.has(key)) {
          edgeSet.add(key)
          edges.push({ src: String(src), dst: String(dst), ring_id })
        }
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
        nodes: Object.values(nodeMap),
        edges,
        fraudRings,
        suspiciousAccounts: suspicious,
        accountRingMap,
        ringMetaMap
      }
    }
    return result
  })

  function setFromDetection(responseData) {
    const summaryRows = []
    const reportsMap  = {}
    let   latestStats = null
    for (const [filename, payload] of Object.entries(responseData)) {
      if (Array.isArray(payload.summary)) {
        payload.summary.forEach(row => summaryRows.push({ ...row, _file: filename }))
      }
      if (payload.report) {
        reportsMap[filename] = payload.report
        latestStats          = payload.report.summary
      }
    }
    rings.value         = summaryRows
    reportsByFile.value = reportsMap
    pipelineStats.value = latestStats
    error.value         = null
  }

  function clear() {
    rings.value         = []
    reportsByFile.value = {}
    pipelineStats.value = null
    error.value         = null
  }

  return {
    rings, reportsByFile, pipelineStats,
    loading, error,
    totalRings, criticalCount, highCount, mediumCount, lowCount, avgScore,
    allFraudRings, graphDataByFile,
    setFromDetection, clear
  }
})
