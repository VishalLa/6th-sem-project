from .build_graph import Graph

import time
import networkx as nx
from collections import defaultdict, deque
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics import (
    precision_recall_curve,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
)


def normalize_array(arr: np.ndarray) -> np.ndarray:
    max_val = arr.max()
    return arr / max_val if max_val > 0 else np.zeros_like(arr)


def _risk_level(score: float) -> str:
    if score >= 70:  return "HIGH"
    if score >= 40:  return "MED"
    return "LOW"


_PATTERN_CLEAN = {
    "cycle_length_3": "cycle",
    "fan_in":         "fan_in",
    "fan_out":        "fan_out",
    "layered_shell":  "layered_shell",
    "cycle":          "cycle",
}

class MainEngine:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.nx_graph: nx.MultiDiGraph = graph.graph
        self._sg: nx.DiGraph = graph.structure_graph 

        # Account index 
        self._accounts: list = list(self._sg.nodes())
        self._acc_idx:  dict = {a: i for i, a in enumerate(self._accounts)}
        n = len(self._accounts)

        # Degree vectors (used in scoring + stats) 
        self._in_deg  = np.array([self._sg.in_degree(a)  for a in self._accounts], dtype=np.float32)
        self._out_deg = np.array([self._sg.out_degree(a) for a in self._accounts], dtype=np.float32)
        self._degrees = self._in_deg + self._out_deg           # total degree

        # Sparse adjacency for network risk (O(edges) multiply)
        rows, cols = [], []
        for u, v in self._sg.edges():
            if u in self._acc_idx and v in self._acc_idx:
                ui, vi = self._acc_idx[u], self._acc_idx[v]
                rows += [ui, vi]
                cols += [vi, ui]
        self._adj = csr_matrix(
            (np.ones(len(rows), dtype=np.float32), (rows, cols)),
            shape=(n, n)
        )

        # Pre-cache successor/predecessor lists 
        self._successors:   dict = {nd: list(self._sg.successors(nd))   for nd in self._sg.nodes()}
        self._predecessors: dict = {nd: list(self._sg.predecessors(nd)) for nd in self._sg.nodes()}
        self._degree_map:   dict = dict(self._sg.degree())

        # DataFrame (only needed for smurfing timestamp windows)
        df = graph.dataframe[
            ["transaction_id", "sender_id", "receiver_id", "amount", "timestamp"]
        ].copy()
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)
        df["ts_ns"] = df["timestamp"].values.astype(np.int64)
        self._df = df

        #  Pre-aggregated stats for behavioral/legitimate scoring 
        self._s_count   = df.groupby("sender_id").size()
        self._r_count   = df.groupby("receiver_id").size()
        self._s_span    = df.groupby("sender_id")["ts_ns"].agg(["min", "max"])
        self._r_span    = df.groupby("receiver_id")["ts_ns"].agg(["min", "max"])
        self._uniq_recv = df.groupby("sender_id")["receiver_id"].nunique()
        self._s_amount  = df.groupby("sender_id")["amount"].agg(["mean", "std"])
        self._r_amount  = df.groupby("receiver_id")["amount"].agg(["mean", "std"])

    # ─────────────────────────────────────────────────────────────────
    # 1. CYCLE DETECTION
    #    Logic: explicit 3-node triangle check on the graph.
    #    Faster than all_simple_paths for triangles — O(V × avg_degree²).
    #    Kept pure graph — no DataFrame involved.
    # ─────────────────────────────────────────────────────────────────
    def detect_cycles(self) -> list[dict]:
        cycles = []
        G      = self._sg
        succs  = self._successors

        for u in G.nodes:
            for v in succs.get(u, []):
                if v == u:
                    continue
                for w in succs.get(v, []):
                    if w == u or w == v:
                        continue

                    if G.has_edge(w, u):
                        cycles.append({
                            "accounts": [u, v, w],
                            "pattern":  "cycle_length_3"
                        })

        return cycles

    # ─────────────────────────────────────────────────────────────────
    # 2. SMURFING DETECTION
    #    Logic: in_degree / out_degree threshold on graph.
    #    No DataFrame scanning needed — pure graph structural check.
    #    Much faster than sliding timestamp windows for large datasets.
    # ─────────────────────────────────────────────────────────────────
    def detect_smurfing(self, threshold: int = 8) -> list[dict]:
        suspicious = []
        G          = self._sg

        for node in G.nodes:
            in_d  = G.in_degree(node)
            out_d = G.out_degree(node)

            if in_d >= threshold:
                suspicious.append({"account": node, "pattern": "fan_in"})
            if out_d >= threshold:
                suspicious.append({"account": node, "pattern": "fan_out"})

        return suspicious

    # ─────────────────────────────────────────────────────────────────
    # 3. LAYERED SHELL DETECTION
    #    Logic: node → low-out-degree neighbour → next hop.
    #    Kept as constrained iterative DFS with dedup and hard cap to
    #    prevent path explosion on dense graphs.
    # ─────────────────────────────────────────────────────────────────
    def detect_layered_shells(self) -> list[dict]:
        suspicious_chains = []
        G         = self._sg
        succs     = self._successors
        seen_sets = set()
        MAX_PATHS = 500

        for node in G.nodes:
            for neighbor in succs.get(node, []):
                # Shell intermediate must have low out-degree (≤ 2)
                if G.out_degree(neighbor) > 2:
                    continue
                count = 0
                for next_node in succs.get(neighbor, []):
                    if next_node == node or count >= MAX_PATHS:
                        continue
                    path = [node, neighbor, next_node]
                    key  = frozenset(path)
                    if key not in seen_sets:
                        seen_sets.add(key)
                        suspicious_chains.append({
                            "accounts": path,
                            "pattern":  "layered_shell"
                        })
                        count += 1

        return suspicious_chains

    # ─────────────────────────────────────────────────────────────────
    # 4. ADAPTIVE THRESHOLD
    # ─────────────────────────────────────────────────────────────────
    def adaptive_threshold(self, scores: dict) -> float:
        v = np.fromiter(scores.values(), dtype=np.float32)
        return float(v.mean() + 1.0 * v.std())

    # ─────────────────────────────────────────────────────────────────
    # 5. COMPUTE SCORES
    #    Logic  — structural / behavioral / statistical /
    #    legitimate — all ported to vectorized numpy arrays.
    #    Network risk uses sparse matrix multiply (O(edges), not O(V×k)).
    # ─────────────────────────────────────────────────────────────────
    def compute_scores(
        self, cycles: list, smurfing: list, shells: list
    ) -> dict:
        n       = len(self._accounts)
        idx_map = self._acc_idx
        G       = self._sg

        structural  = np.zeros(n, dtype=np.float32)
        behavioral  = np.zeros(n, dtype=np.float32)
        statistical = np.zeros(n, dtype=np.float32)
        legitimate  = np.zeros(n, dtype=np.float32)


        cycle_members  = {a for c in cycles for a in c["accounts"]}
        smurf_accounts = {s["account"] for s in smurfing}
        shell_members  = {a for sh in shells for a in sh["accounts"]}

        for i, acc in enumerate(self._accounts):
            score = 0.0
            if acc in cycle_members:  score += 1.0
            if acc in smurf_accounts: score += 0.7
            if acc in shell_members:  score += 0.8
            structural[i] = min(1.0, score)

        # BEHAVIORAL: (in_deg + out_deg) / 20, capped at 1 
        behavioral = np.minimum(1.0, (self._in_deg + self._out_deg) / 20.0)

        # NETWORK: sparse neighbour structural score propagation 
        network = normalize_array(self._adj.dot(structural))

        # STATISTICAL: z-score of degree, capped at 1 
        mean_deg    = self._degrees.mean()
        std_deg     = float(self._degrees.std()) or 1.0
        z_scores    = np.abs(self._degrees - mean_deg) / std_deg
        statistical = np.minimum(1.0, z_scores / 3.0)

        # LEGITIMATE DAMPENING: heavy balanced traders 
        # high in + out degree → established account, reduce suspicion
        legitimate = np.where(
            (self._in_deg > 50) & (self._out_deg > 50),
            0.5,
            0.0
        ).astype(np.float32)

        # FINAL SCORE (formula, vectorized sigmoid) 
        raw = (
            0.35 * structural  +
            0.25 * behavioral  +
            0.15 * statistical +
            0.10 * network     -
            0.25 * legitimate
        ).astype(np.float64)

        # Sigmoid scaled by 5 (matches: 100 / (1 + exp(-5*raw)))
        final = np.round(100.0 / (1.0 + np.exp(-5.0 * raw)), 2)

        return {acc: float(final[i]) for i, acc in enumerate(self._accounts)}

    # ─────────────────────────────────────────────────────────────────
    # 6. BUILD FRAUD RINGS
    #    Logic: cycle + shell members form rings,
    #    skip if any member already used (no overlap).
    # ─────────────────────────────────────────────────────────────────
    def build_fraud_rings(
        self,
        cycles:  list,
        smurfing: list,
        shells:  list,
        scores:  dict
    ) -> list[dict]:
        rings   = []
        ring_id = 1
        used    = set()

        for group in cycles + shells:
            members = set(group["accounts"])
            if members & used:          # skip overlapping groups
                continue
            used.update(members)

            member_scores = [scores.get(m, 0) for m in members]
            avg_score     = float(np.mean(member_scores))
            max_score     = float(max(member_scores))
            size_factor   = len(members)

            risk = round(min(100.0,
                0.5 * avg_score +
                0.3 * size_factor * 5 +
                0.2 * max_score
            ), 2)

            rings.append({
                "ring_id":         f"RING_{str(ring_id).zfill(3)}",
                "pattern_type":    group["pattern"],
                "member_accounts": list(members),
                "risk_score":      risk
            })
            ring_id += 1

        return rings

    def summary_table(self, fraud_rings: list, account_scores: dict) -> pd.DataFrame:
        if not fraud_rings:
            return pd.DataFrame()

        rows = []
        for ring in fraud_rings:
            members    = ring["member_accounts"]
            member_set = set(members)
            mc         = len(members)

            # Count internal edges using graph (no DataFrame) 
            internal_edges = sum(
                1 for u in members
                for v in self._successors.get(u, [])
                if v in member_set
            )

            max_edges = mc * (mc - 1) if mc > 1 else 1
            density   = round(internal_edges / max_edges, 3)
            s_vals    = [account_scores.get(m, 0) for m in members]
            risk      = ring["risk_score"]

            rows.append({
                "Ring ID":               ring["ring_id"],
                "Pattern Type":          ring["pattern_type"],
                "Member Count":          mc,
                "Risk Score":            risk,
                "Member Account IDs":    ", ".join(sorted(str(m) for m in members)),
                "Avg Member Score":      round(float(np.mean(s_vals)), 2),
                "Max Member Score":      round(float(max(s_vals)), 2),
                "Structural Complexity": mc + internal_edges,
                "Internal Edge Count":   internal_edges,
                "Ring Density":          density,
                "Risk Category": (
                    "Critical" if risk >= 85 else
                    "High"     if risk >= 70 else
                    "Medium"   if risk >= 50 else "Low"
                )
            })

        return (
            pd.DataFrame(rows)
            .sort_values("Risk Score", ascending=False)
            .reset_index(drop=True)
        )
    
    

    def _build_reasons(
        self,
        acc:      str,
        score:    float,
        meta:     dict,
        smurfing: list,
    ) -> list[str]:
        reasons = []
        G       = self._sg

        total_tx = int(
            self._s_count.get(acc, 0) + self._r_count.get(acc, 0)
        )

        # Activity gate
        penalty = 0.2 if total_tx < 5 else 0.0
        if penalty:
            reasons.append(f"activity_gate(total_tx={total_tx},penalty={penalty})")

        patterns = meta.get("patterns", set())

        # Cycle centrality
        if "cycle_length_3" in patterns or "cycle" in patterns:
            deg  = G.degree(acc)
            # count how many cycles this node appears in (approx via neighbours)
            size = deg + 1
            reasons.append(f"cycle_centrality(deg={deg},size={size})")

        # Fan-in intensity
        if "fan_in" in patterns:
            in_d = G.in_degree(acc)
            reasons.append(f"fan_in_intensity(in={in_d})")

        # Fan-out intensity
        if "fan_out" in patterns:
            out_d = G.out_degree(acc)
            reasons.append(f"fan_out_intensity(out={out_d})")

        # Layered shell
        if "layered_shell" in patterns:
            reasons.append("layered_shell_member")

        # Low activity cap
        if total_tx < 5:
            cap = round(score, 1)
            reasons.append(f"low_activity_cap(total_tx={total_tx},score_cap={cap})")

        return reasons


    def run_full_pipeline(self) -> dict:
        t0 = time.perf_counter()

        cycles    = self.detect_cycles()
        smurfing  = self.detect_smurfing()
        shells    = self.detect_layered_shells()
        scores    = self.compute_scores(cycles, smurfing, shells)
        threshold = self.adaptive_threshold(scores)
        rings     = self.build_fraud_rings(cycles, smurfing, shells, scores)


        account_meta: dict = defaultdict(lambda: {"patterns": set(), "ring_id": None})
        for c  in cycles:   [account_meta[a]["patterns"].add(c["pattern"])  for a in c["accounts"]]
        for s  in smurfing:  account_meta[s["account"]]["patterns"].add(s["pattern"])
        for sh in shells:   [account_meta[a]["patterns"].add(sh["pattern"]) for a in sh["accounts"]]
        for r  in rings:    [account_meta[a].__setitem__("ring_id", r["ring_id"]) for a in r["member_accounts"]]

        suspicious = []
        for acc, score in scores.items():
            if score < threshold:
                continue
            meta     = account_meta[acc]
            patterns = meta["patterns"]
            reasons  = self._build_reasons(acc, score, meta, smurfing)

            suspicious.append({
                "account_id":        acc,
                "suspicion_score":   score,
                "risk_level":        _risk_level(score),   # ← added
                "reasons":           reasons,               # ← added
                "detected_patterns": [_PATTERN_CLEAN.get(p, p) for p in patterns],
                "ring_id":           meta["ring_id"],
            })


        return {
            "suspicious_accounts": suspicious,
            "fraud_rings":         rings,
            "account_scores":      scores,
            "summary": {
                "total_accounts_analyzed":     len(self._accounts),
                "suspicious_accounts_flagged": len(suspicious),
                "fraud_rings_detected":        len(rings),
                "processing_time_seconds":     round(time.perf_counter() - t0, 3),
            }
        }
    