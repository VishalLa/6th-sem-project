# FlowMatrix — Vue 3 Frontend

Complete Vue 3 frontend wired to the FlowMatrix FastAPI backend.

## Quick Start

```bash
npm install
npm run dev        # → http://localhost:5173
```

Backend must be running on `http://localhost:8000` (Vite proxies automatically).

## Project Structure

```
src/
├── components/
│   ├── AppNavbar.vue      # Responsive navbar + download handler
│   ├── FileUpload.vue     # Drag-drop (CSV only — matches backend validation)
│   ├── StatCards.vue      # Totals + pipeline stats (time, accounts analysed)
│   ├── SummaryTable.vue   # All 11 columns from engine.py summary_table()
│   └── GraphView.vue      # SVG graph with fan-in/fan-out/cycle topologies
├── views/
│   ├── HomeView.vue       # Upload → POST /input/files → store → redirect
│   ├── SummaryView.vue    # Summary table + CSV export
│   └── GraphView.vue      # Graph visualisation page
├── services/api.js        # uploadFiles / fetchFileList / downloadFile
├── stores/results.js      # Pinia: setFromDetection() parses backend response
└── router/index.js
```

## API ↔ Frontend Mapping

| Backend endpoint        | Frontend action                                   |
|-------------------------|---------------------------------------------------|
| `POST /input/files`     | HomeView → uploadFiles() → store.setFromDetection()|
| `GET /show/output/files`| Navbar Download button → fetchFileList()          |
| `GET /download/{name}`  | Navbar Download button → downloadFile(nameNoExt)  |

### Backend Response Shape (POST /input/files)

```json
{
  "file.csv": {
    "report": {
      "suspicious_accounts": [...],
      "fraud_rings": [
        { "ring_id": "RING_001", "pattern_type": "cycle_length_3",
          "member_accounts": ["A","B","C"], "risk_score": 82.4 }
      ],
      "summary": {
        "total_accounts_analyzed": 500,
        "suspicious_accounts_flagged": 42,
        "fraud_rings_detected": 7,
        "processing_time_seconds": 1.23
      }
    },
    "summary": [
      {
        "Ring ID": "RING_001",
        "Pattern Type": "cycle_length_3",
        "Member Count": 3,
        "Risk Score": 82.4,
        "Member Account IDs": "A, B, C",
        "Avg Member Score": 75.1,
        "Max Member Score": 90.2,
        "Structural Complexity": 6,
        "Internal Edge Count": 3,
        "Ring Density": 0.5,
        "Risk Category": "High"
      }
    ],
    "saved_to": "output/file_analysis.json"
  }
}
```

### Pattern Types (from engine.py)

| Backend value    | UI label       |
|------------------|----------------|
| `cycle_length_3` | Cycle ×3       |
| `fan_in`         | Fan-In         |
| `fan_out`        | Fan-Out        |
| `layered_shell`  | Layered Shell  |
