# FlowMatrix Frontend

## Quick Start (3 commands)

```bash
cd frontend
npm install
npm run dev
```

App runs at http://localhost:5173

## Requirements
- Node.js 18+ (check with: node --version)
- Backend running at http://127.0.0.1:8000

## What's in this build

### Pages
| Route | What it does |
|---|---|
| `/#/auth` | Login & Register |
| `/#/` | Home — upload CSV, run detection |
| `/#/summary` | Fraud ring summary table |
| `/#/graph` | Interactive fraud graph |
| `/#/metrics` | Charts: KYC, payment methods, countries, risk |
| `/#/transactions` | Transaction table with search & filters |

### Features
- JWT auth (token saved to localStorage, auto-attached to all requests)
- Closable chat assistant (bottom-right button) — asks questions about your data
- All detection/upload routes preserved from original

## Build for production
```bash
npm run build
```
Output goes to `dist/` folder.
