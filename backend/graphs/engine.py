from .build_graph import Graph

import time
import networkx as nx
from collections import defaultdict, deque, Counter
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics import (
    precision_recall_curve,
    precision_score,
    recall_score,
    f1_score,
    accuracy_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)
from typing import Optional



# System Components
"""
┌─────────────────────────────────────────────────────────────┐
│                     Input Data Layer                        │
│  (CSV with transaction_id, sender, receiver, amount, etc.)  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Graph Construction                        │
│  - Column normalization                                     │
│  - MultiDiGraph (transaction-level)                         │
│  - DiGraph (account-level structure)                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Pattern Detection                         │
│  - Cycles (3-6 nodes)        - Device Sharing               │
│  - Smurfing (fan-in/out)     - New Account Bursts           │
│  - Layered Shells            - Velocity Spikes              │
│  - Cross-border Chains       - Rapid Movement               │
│  - KYC Clusters              - Round Amounts                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Scoring Engine                           │
│  - Structural (30%)          - Network (10%)                │
│  - Behavioral (20%)          - Contextual (20%)             │
│  - Statistical (10%)         - Legitimate (-20%)            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  Fraud Ring Formation                       │
│  - Group connected suspicious accounts                      │
│  - Calculate ring risk scores                               │
│  - Assign ring IDs                                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 Performance Evaluation                      │
│  - Metrics (if ground truth provided)                       │
│  - Summary statistics                                       │
│  - Exportable results                                       │
└─────────────────────────────────────────────────────────────┘
"""


def normalize_array(arr: np.ndarray) -> np.ndarray:
    """
    Normalizes a NumPy array by scaling its values between 0 and 1.
    
    Args:
        arr (np.ndarray): The input array to normalize.
        
    Returns:
        np.ndarray: The normalized array. Returns an array of zeros if the max value is 0.
    """
    max_val = arr.max()
    return arr / max_val if max_val > 0 else np.zeros_like(arr)


def _risk_level(score: float) -> str:
    """
    Categorizes a numeric risk score into a human-readable string level.
    
    Args:
        score (float): The calculated suspicion score (0 to 100).
        
    Returns:
        str: "HIGH" (>= 70), "MED" (>= 40), or "LOW" (< 40).
    """
    if score >= 70:  return "HIGH"
    if score >= 40:  return "MED"
    return "LOW"


def adaptive_threshold(scores: dict) -> float:
    """
    Calculates a dynamic threshold for flagging accounts based on score distribution.
    The threshold is set to the mean score plus one standard deviation.
    
    Args:
        scores (dict): Dictionary mapping account IDs to their risk scores.
        
    Returns:
        float: The calculated threshold score.
    """
    v = np.fromiter(scores.values(), dtype=np.float32)
    return float(v.mean() + 1.0 * v.std())


_PATTERN_CLEAN = {
    "cycle_length_3":           "cycle_3",
    "cycle_length_4":           "cycle_4",
    "cycle_length_5":           "cycle_5",
    "cycle_length_6":           "cycle_6",
    "cycle_length_7":           "cycle_7",
    "cycle_length_8":           "cycle_8",
    "fan_in":                   "fan_in",
    "fan_out":                  "fan_out",
    "layered_shell":            "layered_shell",
    "cycle":                    "cycle",
    "rapid_movement":           "rapid_movement",
    "cross_border_chain":       "cross_border_chain",
    "unverified_kyc_cluster":   "unverified_kyc",
    "round_amount_pattern":     "round_amounts",
    "device_sharing":           "device_sharing",
    "new_account_burst":        "new_account_burst",
    "velocity_spike":           "velocity_spike",
}



class MainEngine:

    """
    The core analysis engine responsible for detecting money mule patterns, 
    evaluating risk scores, and generating fraud rings from transaction graph data.
    """

    def __init__(
        self, 
        graph: Graph, 
        cycle_length: int = 3, 
        ground_truth_labels: Optional[dict] = None
    ) -> None:
        
        """
        Initializes the MainEngine and pre-computes necessary network and dataframe statistics.
        
        Args:
            graph (Graph): The constructed Graph object containing the MultiDiGraph, DiGraph, and dataframe.
            cycle_length (int, optional): The maximum length of circular transactions to look for. Defaults to 3. (Max: 6).
            ground_truth_labels (dict, optional): Dictionary of true account labels for evaluation metrics. Defaults to None.
        """
        
        self.graph = graph
        self.nx_graph: nx.MultiDiGraph = graph.graph
        self._sg: nx.DiGraph = graph.structure_graph 
        self.cycle_length = max(3, min(cycle_length, 6))
        self.ground_truth = ground_truth_labels


        # Account index 
        self._accounts: list = list(self._sg.nodes())
        self._acc_idx:  dict = {a: i for i, a in enumerate(self._accounts)}
        n = len(self._accounts)

        # Degree vectors (used in scoring + stats) 
        self._in_deg  = np.array([self._sg.in_degree(a)  for a in self._accounts], dtype=np.float32)
        self._out_deg = np.array([self._sg.out_degree(a) for a in self._accounts], dtype=np.float32)
        self._degrees = self._in_deg + self._out_deg          # total degree

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
        self._successors:   dict = {nd: list(self._sg.successors(nd)) for nd in self._sg.nodes()}
        self._predecessors: dict = {nd: list(self._sg.predecessors(nd)) for nd in self._sg.nodes()}
        self._degree_map:   dict = dict(self._sg.degree())

        # DataFrame (only needed for smurfing timestamp windows)
        df = graph.dataframe.copy()

        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)

        df["ts_ns"] = df["timestamp"].values.astype(np.int64)
        self._df = df

        #  Pre-aggregated stats for behavioral/legitimate scoring 
        self._s_count = df.groupby("sender").size()
        self._r_count = df.groupby("receiver").size()
        self._s_span = df.groupby("sender")["ts_ns"].agg(["min", "max"])
        self._r_span = df.groupby("receiver")["ts_ns"].agg(["min", "max"])

        self._uniq_recv = df.groupby("sender")["receiver"].nunique()

        self._s_amount  = df.groupby("sender")["amount"].agg(["mean", "std"])
        self._r_amount  = df.groupby("receiver")["amount"].agg(["mean", "std"])

        self._s_countries = df.groupby("sender")["sender_country"].unique()
        self._r_countries = df.groupby("receiver")["receiver_country"].unique()

        self._s_devices = df.groupby("sender")["device_id"].unique()

        self._s_kyc = df.groupby("sender")["sender_kyc"].agg(lambda x: x.mode()[0] if len(x.mode()) > 0 else "Unknown")
        self._txn_methods = df.groupby("sender")["txn_method"].unique()

        self._round_amounts = df.groupby("sender")["is_round_amount"].sum()
        self._acct_ages = df.groupby("sender")["sender_acct_age"].first()
        self._velocities = df.groupby("sender")["velocity_mins"].mean()


    def detect_cycles(self, max_length: int = 8) -> list[dict]:

        """
        Detects circular transactions where money returns to the original sender.
        Finds ALL cycles from length 3 up to max_length.
        
        Args:
            max_length (int, optional): Max nodes in the cycle. Uses self.cycle_length if None.
            
        Returns:
            list[dict]: List of detected cycles with 'accounts' and 'pattern' type.
                        Contains cycles of ALL lengths from 3 to max_length.
        """

        if max_length is None:
            max_length = self.cycle_length

        max_length = min(max_length, 8)
        
        cycles = []
        
        if max_length >= 3:
            cycles.extend(self._detect_cycles_length_3())
        
        if max_length > 3:
            cycles.extend(self._detect_cycles_general(max_length))
        
        return cycles
    

    def _detect_cycles_length_3(self) -> list[dict]:

        """
        Fast, hardcoded triangle (A -> B -> C -> A) detection algorithm.
        
        Returns:
            list[dict]: List of cycles of length 3.
        """

        cycles = []
        G = self._sg
        succs = self._successors
        seen_cycles = set()
        
        for u in G.nodes:
            for v in succs.get(u, []):

                if v == u:
                    continue

                for w in succs.get(v, []):

                    if w == u or w == v:
                        continue

                    if G.has_edge(w, u):
                        # Use sorted tuple to avoid duplicates
                        cycle_key = tuple(sorted([u, v, w]))
                        if cycle_key not in seen_cycles:
                            seen_cycles.add(cycle_key)
                            cycles.append({
                                "accounts": [u, v, w],
                                "pattern": "cycle_length_3"
                            })
        return cycles
    

    def _detect_cycles_general(self, max_length: int) -> list[dict]:
        
        """
        General cycle detection using Breadth-First Search for cycle lengths 4 to max_length.
        Finds ALL cycles from length 4 up to max_length (avoids duplicating length-3 cycles).
        Args:
            max_length (int): Maximum depth of the cycle search.
            
        Returns:
            list[dict]: List of cycles found.
        """

        cycles = []
        G = self._sg
        seen_cycles = set()
        
        for start_node in G.nodes:
            # BFS to find cycles
            queue = deque([(start_node, [start_node])])
            
            while queue:
                node, path = queue.popleft()
                
                if len(path) > max_length:
                    continue
                
                for neighbor in self._successors.get(node, []):

                    if neighbor == start_node and len(path) >= 3:
                        # Found a cycle
                        cycle_key = tuple(sorted(path))
                        if cycle_key not in seen_cycles:
                            seen_cycles.add(cycle_key)
                            cycles.append({
                                "accounts": path,
                                "pattern": f"cycle_length_{len(path)}"
                            })

                    elif neighbor not in path and len(path) < max_length:
                        queue.append((neighbor, path + [neighbor]))
        
        return cycles


    def detect_smurfing(self, threshold: int = 8) -> list[dict]:

        """
        Detects smurfing behavior: "fan-in" (many accounts sending to one) 
        and "fan-out" (one account sending to many).
        
        Args:
            threshold (int): Minimum number of unique connections to trigger detection.
            
        Returns:
            list[dict]: List of flagged accounts and their pattern ('fan_in' or 'fan_out').
        """

        suspicious = []
        G = self._sg

        for node in G.nodes:
            in_d  = G.in_degree(node)
            out_d = G.out_degree(node)

            if in_d >= threshold:
                suspicious.append({"account": node, "pattern": "fan_in"})

            if out_d >= threshold:
                suspicious.append({"account": node, "pattern": "fan_out"})

        return suspicious


    def detect_layered_shells(self) -> list[dict]:

        """
        Detects 'layered shell' structures where an account acts as a strict middleman
        (receives funds and forwards them, keeping little to nothing, with low out-degree).
        
        Returns:
            list[dict]: List of flagged transaction chains (A -> B -> C).
        """

        suspicious_chains = []
        G = self._sg
        succs = self._successors
        seen_sets = set()
        MAX_PATHS = 500

        for node in G.nodes:
            for neighbor in succs.get(node, []):

                if G.out_degree(neighbor) > 2:
                    continue
                count = 0

                for next_node in succs.get(neighbor, []):
                    if next_node == node or count >= MAX_PATHS:
                        continue

                    path = [node, neighbor, next_node]
                    key = frozenset(path)

                    if key not in seen_sets:
                        seen_sets.add(key)
                        suspicious_chains.append({
                            "accounts": path,
                            "pattern": "layered_shell"
                        })

                        count += 1

        return suspicious_chains
    

    def detect_cross_border_chains(self, min_countries: int = 3) -> list[dict]:

        """
        Detects accounts involved in transferring funds across multiple different countries.
        
        Args:
            min_countries (int): Minimum number of unique countries in the transfer chain.
            
        Returns:
            list[dict]: List of accounts, the pattern, and the countries involved.
        """

        suspicious = []
        df = self._df
        
        # Group by sender to find cross-border patterns
        for sender in df["sender"].unique():
            sender_txns = df[df["sender"] == sender]
            
            # Get unique countries involved
            countries = set()
            if sender in self._s_countries:
                countries.update(self._s_countries[sender])
            if sender in self._r_countries:
                countries.update(self._r_countries[sender])
            
            # Check receivers' countries
            for receiver in sender_txns["receiver"].unique():
                if receiver in self._s_countries:
                    countries.update(self._s_countries[receiver])
                if receiver in self._r_countries:
                    countries.update(self._r_countries[receiver])
            
            if len(countries) >= min_countries:
                suspicious.append({
                    "account": sender,
                    "pattern": "cross_border_chain",
                    "countries_count": len(countries),
                    "countries": list(countries)
                })
        
        return suspicious
    

    def detect_unverified_kyc_clusters(self, min_cluster_size: int = 3) -> list[dict]:

        """
        Detects interconnected networks (subgraphs) of users with unverified KYC status.
        
        Args:
            min_cluster_size (int): Minimum number of connected unverified accounts to flag.
            
        Returns:
            list[dict]: List of unverified clusters containing member accounts.
        """

        suspicious = []
        df = self._df
        
        # Find unverified or pending KYC accounts
        unverified_accounts = set()

        for acc in self._accounts:
            kyc_status = self._s_kyc.get(acc, "Unknown")

            if kyc_status in ["Pending", "None", "Unknown", None]:
                unverified_accounts.add(acc)
        
        # Find connected components among unverified accounts
        unverified_subgraph = self._sg.subgraph(unverified_accounts)
        
        for component in nx.weakly_connected_components(unverified_subgraph):

            if len(component) >= min_cluster_size:
                suspicious.append({
                    "accounts": list(component),
                    "pattern": "unverified_kyc_cluster",
                    "cluster_size": len(component)
                })
        
        return suspicious
    

    def detect_round_amount_patterns(self, threshold_ratio: float = 0.7) -> list[dict]:

        """
        Identifies accounts that have a high ratio of sending 'round' amounts (e.g. $500.00 vs $542.11).
        
        Args:
            threshold_ratio (float): Ratio of round transactions to total transactions to trigger flag.
            
        Returns:
            list[dict]: List of flagged accounts, their ratios, and total transactions.
        """

        suspicious = []
        df = self._df
        
        for sender in df["sender"].unique():
            sender_txns = df[df["sender"] == sender]
            total_txns = len(sender_txns)
            
            if total_txns < 3:  # Need minimum transactions
                continue
            
            round_count = self._round_amounts.get(sender, 0)
            round_ratio = round_count / total_txns
            
            if round_ratio >= threshold_ratio:
                suspicious.append({
                    "account": sender,
                    "pattern": "round_amount_pattern",
                    "round_ratio": round(round_ratio, 2),
                    "total_txns": total_txns,
                    "round_txns": int(round_count)
                })
        
        return suspicious
    

    def detect_device_sharing(self, min_accounts: int = 3) -> list[dict]:

        """
        Detects multiple distinct accounts operating from the same device_id/IP address.
        
        Args:
            min_accounts (int): Minimum accounts tied to a single device to flag.
            
        Returns:
            list[dict]: List of flagged devices and the associated accounts.
        """

        suspicious = []
        df = self._df
        
        # Group by device_id
        device_accounts = defaultdict(set)
        
        for sender in df["sender"].unique():
            if sender in self._s_devices:
                devices = self._s_devices[sender]

                for device in devices:
                    if pd.notna(device):
                        device_accounts[device].add(sender)
        
        for device, accounts in device_accounts.items():
            if len(accounts) >= min_accounts:
                suspicious.append({
                    "device_id": device,
                    "accounts": list(accounts),
                    "pattern": "device_sharing",
                    "account_count": len(accounts)
                })
        
        return suspicious
    

    def detect_new_account_bursts(self, max_age_days: int = 30, min_txns: int = 10) -> list[dict]:

        """
        Detects newly created accounts executing a high volume of transactions immediately.
        
        Args:
            max_age_days (int): Definition of a 'new' account.
            min_txns (int): Minimum transactions needed to constitute a 'burst'.
            
        Returns:
            list[dict]: List of flagged accounts.
        """

        suspicious = []
        
        for sender in self._accounts:
            acct_age = self._acct_ages.get(sender, None)
            if acct_age is None or pd.isna(acct_age):
                continue
            
            if acct_age <= max_age_days:
                txn_count = self._s_count.get(sender, 0)
                if txn_count >= min_txns:
                    suspicious.append({
                        "account": sender,
                        "pattern": "new_account_burst",
                        "account_age_days": int(acct_age),
                        "transaction_count": int(txn_count)
                    })
        
        return suspicious
    

    def detect_velocity_spikes(self, threshold_mins: float = 5.0) -> list[dict]:

        """
        Detects accounts that move money out almost immediately after receiving it (Velocity).
        
        Args:
            threshold_mins (float): Maximum allowed average minutes between receiving and sending.
            
        Returns:
            list[dict]: Flagged accounts and their average velocity.
        """

        suspicious = []
        
        for sender in self._accounts:

            avg_velocity = self._velocities.get(sender, None)
            if avg_velocity is None or pd.isna(avg_velocity):
                continue
            
            if avg_velocity <= threshold_mins:
                txn_count = self._s_count.get(sender, 0)

                if txn_count >= 5:  # Need multiple transactions
                    suspicious.append({
                        "account": sender,
                        "pattern": "velocity_spike",
                        "avg_velocity_mins": round(float(avg_velocity), 2),
                        "transaction_count": int(txn_count)
                    })
        
        return suspicious
    

    def detect_rapid_movement(self, time_window_hours: int = 24) -> list[dict]:

        """
        Detects temporal chains (A sends to B, B immediately sends to C) within a tight time window.
        
        Args:
            time_window_hours (int): Hour window for the A -> B -> C sequence to execute.
            
        Returns:
            list[dict]: Chains of accounts exhibiting rapid temporal movement.
        """

        suspicious = []
        df = self._df
        time_window_ns = time_window_hours * 3600 * 1e9
        seen_chains = set()
        
        # Find chains of transactions within time window
        for idx, row in df.iterrows():
            sender = row["sender"]
            receiver = row["receiver"]
            timestamp = row["ts_ns"]
            
            # Check if receiver quickly sends to another account
            receiver_txns: pd.DataFrame = df[
                (df["sender"] == receiver) & 
                (df["ts_ns"] >= timestamp) & 
                (df["ts_ns"] <= timestamp + time_window_ns)
            ]
            
            if len(receiver_txns) > 0:
                for _, next_txn in receiver_txns.iterrows():

                    time_diff_hours = (next_txn["ts_ns"] - timestamp) / (3600 * 1e9)
                    chain_key = tuple(sorted([sender, receiver, next_txn["receiver"]]))
                    
                    if chain_key not in seen_chains:
                        seen_chains.add(chain_key)
                        suspicious.append({
                            "accounts": [sender, receiver, next_txn["receiver"]],
                            "pattern": "rapid_movement",
                            "time_diff_hours": round(float(time_diff_hours), 2)
                        })
        
        return suspicious


    def compute_scores(
        self,
        cycles: list,
        smurfing: list,
        shells: list,
        cross_border: list = None,
        kyc_clusters: list = None,
        round_amounts: list = None,
        device_sharing: list = None,
        new_bursts: list = None,
        velocity_spikes: list = None,
        rapid_movement: list = None
    ) -> dict:
        
        """
        Aggregates the detected patterns, structural data, and behavioural features 
        into a singular machine-learning-style risk score for each account.
        
        Args:
            cycles, smurfing, shells, cross_border, kyc_clusters, round_amounts, 
            device_sharing, new_bursts, velocity_spikes, rapid_movement (list): Output from the detect_* functions.
            
        Returns:
            dict: Dictionary mapping account IDs to their final suspicion score (0.0 to 100.0).
        """

        n = len(self._accounts)
        idx_map = self._acc_idx
        G = self._sg

        structural = np.zeros(n, dtype=np.float32)
        behavioral = np.zeros(n, dtype=np.float32)
        statistical = np.zeros(n, dtype=np.float32)
        legitimate = np.zeros(n, dtype=np.float32)
        contextual = np.zeros(n, dtype=np.float32)  # New: for cross-border, KYC, etc.

        # Collect all pattern members
        cycle_members = {a for c in cycles for a in c["accounts"]}
        smurf_accounts = {s["account"] for s in smurfing}
        shell_members = {a for sh in shells for a in sh["accounts"]}
        
        cross_border_accounts = set()
        if cross_border:
            cross_border_accounts = {cb["account"] for cb in cross_border}
        
        kyc_cluster_members = set()
        if kyc_clusters:
            kyc_cluster_members = {a for kc in kyc_clusters for a in kc["accounts"]}
        
        round_amt_accounts = set()
        if round_amounts:
            round_amt_accounts = {ra["account"] for ra in round_amounts}
        
        device_share_accounts = set()
        if device_sharing:
            device_share_accounts = {a for ds in device_sharing for a in ds["accounts"]}
        
        new_burst_accounts = set()
        if new_bursts:
            new_burst_accounts = {nb["account"] for nb in new_bursts}
        
        velocity_spike_accounts = set()
        if velocity_spikes:
            velocity_spike_accounts = {vs["account"] for vs in velocity_spikes}
        
        rapid_movement_accounts = set()
        if rapid_movement:
            rapid_movement_accounts = {a for rm in rapid_movement for a in rm["accounts"]}

        # STRUCTURAL: traditional patterns
        for i, acc in enumerate(self._accounts):
            score = 0.0
            if acc in cycle_members:  score += 1.0
            if acc in smurf_accounts: score += 0.7
            if acc in shell_members:  score += 0.8
            structural[i] = min(1.0, score)

        # BEHAVIORAL: degree-based
        behavioral = np.minimum(1.0, (self._in_deg + self._out_deg) / 20.0)

        # NETWORK: sparse neighbour propagation
        network = normalize_array(self._adj.dot(structural))

        # STATISTICAL: z-score of degree
        mean_deg = self._degrees.mean()
        std_deg = float(self._degrees.std()) or 1.0
        z_scores = np.abs(self._degrees - mean_deg) / std_deg
        statistical = np.minimum(1.0, z_scores / 3.0)

        # CONTEXTUAL: new patterns based on additional columns
        for i, acc in enumerate(self._accounts):
            ctx_score = 0.0
            if acc in cross_border_accounts: ctx_score += 0.6
            if acc in kyc_cluster_members: ctx_score += 0.8
            if acc in round_amt_accounts: ctx_score += 0.5
            if acc in device_share_accounts: ctx_score += 0.7
            if acc in new_burst_accounts: ctx_score += 0.6
            if acc in velocity_spike_accounts: ctx_score += 0.7
            if acc in rapid_movement_accounts: ctx_score += 0.8
            contextual[i] = min(1.0, ctx_score)

        # LEGITIMATE: dampening for established accounts
        legitimate = np.where(
            (self._in_deg > 50) & (self._out_deg > 50),
            0.5,
            0.0
        ).astype(np.float32)

        # FINAL SCORE (updated formula with contextual)
        raw = (
            0.30 * structural +
            0.20 * behavioral +
            0.10 * statistical +
            0.10 * network +
            0.20 * contextual -
            0.20 * legitimate
        ).astype(np.float64)

        # Sigmoid scaling
        final = np.round(100.0 / (1.0 + np.exp(-5.0 * raw)), 2)

        return {acc: float(final[i]) for i, acc in enumerate(self._accounts)}
    

    def evaluate_metrics(
        self, 
        account_scores: dict, 
        threshold: float,
        ground_truth: Optional[dict] = None
    ) -> dict:
        """
        Evaluate model performance metrics if ground truth is available.
        
        Args:
            account_scores: Dictionary of {account_id: suspicion_score}
            threshold: Threshold for classifying accounts as suspicious
            ground_truth: Dictionary of {account_id: label} where 1=fraud, 0=legitimate
                         If None, uses self.ground_truth
        
        Returns:
            Dictionary containing various performance metrics
        """
        if ground_truth is None:
            ground_truth = self.ground_truth
        
        if ground_truth is None:
            return {
                "error": "No ground truth labels provided. Cannot compute metrics.",
                "metrics_available": False
            }
        
        # Align scores and labels
        accounts = [acc for acc in account_scores.keys() if acc in ground_truth]
        
        if len(accounts) == 0:
            return {
                "error": "No overlap between scored accounts and ground truth labels.",
                "metrics_available": False
            }
        
        y_true = np.array([ground_truth[acc] for acc in accounts])
        y_scores = np.array([account_scores[acc] for acc in accounts])
        y_pred = (y_scores >= threshold).astype(int)
        
        # Basic metrics
        precision = precision_score(y_true, y_pred, zero_division=0)
        recall = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        accuracy = accuracy_score(y_true, y_pred)
        
        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        
        # Specificity (True Negative Rate)
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        
        # False Positive Rate
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        
        # False Negative Rate
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        
        # AUC-ROC (if we have both classes)
        try:
            if len(np.unique(y_true)) > 1:
                auc_roc = roc_auc_score(y_true, y_scores)
            else:
                auc_roc = None
        except:
            auc_roc = None
        
        # Precision-Recall curve analysis
        precisions, recalls, pr_thresholds = precision_recall_curve(y_true, y_scores)
        
        # Find optimal threshold (max F1)
        f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
        optimal_idx = np.argmax(f1_scores)
        optimal_threshold = pr_thresholds[optimal_idx] if optimal_idx < len(pr_thresholds) else threshold
        optimal_f1 = f1_scores[optimal_idx]
        
        # Matthews Correlation Coefficient
        mcc_numerator = (tp * tn) - (fp * fn)
        mcc_denominator = np.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
        mcc = mcc_numerator / mcc_denominator if mcc_denominator > 0 else 0.0
        
        metrics = {
            "metrics_available": True,
            "threshold_used": round(float(threshold), 2),
            "sample_size": len(accounts),
            "true_fraud_count": int(y_true.sum()),
            "predicted_fraud_count": int(y_pred.sum()),
            
            # Primary metrics
            "accuracy": round(float(accuracy), 4),
            "precision": round(float(precision), 4),
            "recall": round(float(recall), 4),
            "f1_score": round(float(f1), 4),
            "specificity": round(float(specificity), 4),
            
            # Confusion matrix
            "confusion_matrix": {
                "true_negatives": int(tn),
                "false_positives": int(fp),
                "false_negatives": int(fn),
                "true_positives": int(tp)
            },
            
            # Error rates
            "false_positive_rate": round(float(fpr), 4),
            "false_negative_rate": round(float(fnr), 4),
            
            # Advanced metrics
            "matthews_correlation_coefficient": round(float(mcc), 4),
            "auc_roc": round(float(auc_roc), 4) if auc_roc is not None else None,
            
            # Optimal threshold
            "optimal_threshold": round(float(optimal_threshold), 2),
            "optimal_f1_score": round(float(optimal_f1), 4),
            
            # Score distribution
            "score_statistics": {
                "mean": round(float(y_scores.mean()), 2),
                "std": round(float(y_scores.std()), 2),
                "min": round(float(y_scores.min()), 2),
                "max": round(float(y_scores.max()), 2),
                "median": round(float(np.median(y_scores)), 2),
            }
        }
        
        return metrics


    def build_fraud_rings(
        self,
        cycles: list,
        smurfing: list,
        shells: list,
        cross_border: list,
        kyc_clusters: list,
        rapid_movement: list,
        scores: dict
    ) -> list[dict]:
        
        """
        Collapses individual flagged accounts into unified 'Fraud Rings' based on their 
        graph connectivity and shared detection patterns.
        
        Args:
            cycles, smurfing, shells, cross_border, kyc_clusters, rapid_movement (list): Pattern outputs.
            scores (dict): Computed final risk scores.
            
        Returns:
            list[dict]: List of fraud rings containing ring_id, pattern type, members, and ring risk score.
        """

        rings = []
        ring_id = 1
        used = set()

        # Combine all group-based patterns
        all_groups = cycles + shells + kyc_clusters + rapid_movement
        
        for group in all_groups:
            members = set(group["accounts"])
            if members & used:
                continue
            used.update(members)

            member_scores = [scores.get(m, 0) for m in members]
            avg_score = float(np.mean(member_scores))
            max_score = float(max(member_scores))
            size_factor = len(members)

            risk = round(min(100.0,
                0.5 * avg_score +
                0.3 * size_factor * 5 +
                0.2 * max_score
            ), 2)

            rings.append({
                "ring_id": f"RING_{str(ring_id).zfill(3)}",
                "pattern_type": group["pattern"],
                "member_accounts": list(members),
                "risk_score": risk
            })
            ring_id += 1

        return rings
    

    def summary_table(self, fraud_rings: list, account_scores: dict) -> pd.DataFrame:
        
        """
        Generates a Pandas DataFrame summarising the detected fraud rings, ordered by severity.
        
        Args:
            fraud_rings (list): The list of generated fraud rings.
            account_scores (dict): Dictionary mapping accounts to their scores.
            
        Returns:
            pd.DataFrame: Formatted summary DataFrame.
        """

        if not fraud_rings:
            return pd.DataFrame()

        rows = []
        for ring in fraud_rings:
            members = ring["member_accounts"]
            member_set = set(members)
            mc = len(members)

            internal_edges = sum(
                1 for u in members
                for v in self._successors.get(u, [])
                if v in member_set
            )

            max_edges = mc * (mc - 1) if mc > 1 else 1
            density = round(internal_edges / max_edges, 3)
            s_vals = [account_scores.get(m, 0) for m in members]
            risk = ring["risk_score"]

            rows.append({
                "Ring ID": ring["ring_id"],
                "Pattern Type": ring["pattern_type"],
                "Member Count": mc,
                "Risk Score": risk,
                "Member Account IDs": ", ".join(sorted(str(m) for m in members)),
                "Avg Member Score": round(float(np.mean(s_vals)), 2),
                "Max Member Score": round(float(max(s_vals)), 2),
                "Structural Complexity": mc + internal_edges,
                "Internal Edge Count": internal_edges,
                "Ring Density": density,
                "Risk Category": (
                    "Critical" if risk >= 85 else
                    "High" if risk >= 70 else
                    "Medium" if risk >= 50 else "Low"
                )
            })

        return (
            pd.DataFrame(rows)
            .sort_values("Risk Score", ascending=False)
            .reset_index(drop=True)
        )
    

    def _build_reasons(
        self,
        acc: str,
        score: float,
        meta: dict,
        smurfing: list,
        cross_border: list,
        round_amounts: list,
        device_sharing: list,
        new_bursts: list,
        velocity_spikes: list
    ) -> list[str]:
        
        """
        Compiles a list of human-readable justification strings explaining WHY 
        a specific account received its risk score based on triggered patterns.
        
        Args:
            acc, score, meta: Basic account info.
            smurfing ... velocity_spikes (list): Raw pattern data outputs.
            
        Returns:
            list[str]: List of explanation tags (e.g. ['activity_gate(total_tx=4,penalty=0.2)', 'velocity_spike(avg=3.2mins)']).
        """

        reasons = []
        G = self._sg

        total_tx = int(
            self._s_count.get(acc, 0) + self._r_count.get(acc, 0)
        )

        # Activity gate
        penalty = 0.2 if total_tx < 5 else 0.0
        if penalty:
            reasons.append(f"activity_gate(total_tx={total_tx},penalty={penalty})")

        patterns = meta.get("patterns", set())

        # Cycle patterns
        for pattern in patterns:
            if "cycle_length" in pattern:
                deg = G.degree(acc)
                cycle_len = pattern.split("_")[-1]
                reasons.append(f"cycle_member(length={cycle_len},deg={deg})")

        # Fan patterns
        if "fan_in" in patterns:
            in_d = G.in_degree(acc)
            reasons.append(f"fan_in_intensity(in={in_d})")

        if "fan_out" in patterns:
            out_d = G.out_degree(acc)
            reasons.append(f"fan_out_intensity(out={out_d})")

        # Layered shell
        if "layered_shell" in patterns:
            reasons.append("layered_shell_member")

        # Cross-border
        if "cross_border_chain" in patterns:
            cb_info = next((cb for cb in cross_border if cb["account"] == acc), None)
            if cb_info:
                reasons.append(f"cross_border_chain(countries={cb_info['countries_count']})")

        # KYC cluster
        if "unverified_kyc_cluster" in patterns:
            kyc_status = self._s_kyc.get(acc, "Unknown")
            reasons.append(f"unverified_kyc(status={kyc_status})")

        # Round amounts
        if "round_amount_pattern" in patterns:
            ra_info = next((ra for ra in round_amounts if ra["account"] == acc), None)
            if ra_info:
                reasons.append(f"round_amounts(ratio={ra_info['round_ratio']})")

        # Device sharing
        if "device_sharing" in patterns:
            ds_info = next((ds for ds in device_sharing if acc in ds["accounts"]), None)
            if ds_info:
                reasons.append(f"device_sharing(device={ds_info['device_id']},accounts={ds_info['account_count']})")

        # New account burst
        if "new_account_burst" in patterns:
            nb_info = next((nb for nb in new_bursts if nb["account"] == acc), None)
            if nb_info:
                reasons.append(f"new_account_burst(age={nb_info['account_age_days']}days,txns={nb_info['transaction_count']})")

        # Velocity spike
        if "velocity_spike" in patterns:
            vs_info = next((vs for vs in velocity_spikes if vs["account"] == acc), None)
            if vs_info:
                reasons.append(f"velocity_spike(avg={vs_info['avg_velocity_mins']}mins)")

        # Rapid movement
        if "rapid_movement" in patterns:
            reasons.append("rapid_movement_chain")

        # Low activity cap
        if total_tx < 5:
            cap = round(score, 1)
            reasons.append(f"low_activity_cap(total_tx={total_tx},score_cap={cap})")

        return reasons
    

    def metrics_summary_table(self, metrics: dict) -> pd.DataFrame:
        """
        Create a formatted table of performance metrics.
        
        Args:
            metrics: Dictionary returned from evaluate_metrics()
        
        Returns:
            DataFrame with metric names and values
        """
        if not metrics.get("metrics_available", False):
            return pd.DataFrame({"Error": [metrics.get("error", "No metrics available")]})
        
        rows = [
            {"Metric": "Sample Size", "Value": metrics["sample_size"]},
            {"Metric": "True Fraud Count", "Value": metrics["true_fraud_count"]},
            {"Metric": "Predicted Fraud Count", "Value": metrics["predicted_fraud_count"]},
            {"Metric": "Threshold Used", "Value": metrics["threshold_used"]},
            {"Metric": "", "Value": ""},  # Separator
            {"Metric": "Accuracy", "Value": metrics["accuracy"]},
            {"Metric": "Precision", "Value": metrics["precision"]},
            {"Metric": "Recall", "Value": metrics["recall"]},
            {"Metric": "F1 Score", "Value": metrics["f1_score"]},
            {"Metric": "Specificity", "Value": metrics["specificity"]},
            {"Metric": "", "Value": ""},  # Separator
            {"Metric": "False Positive Rate", "Value": metrics["false_positive_rate"]},
            {"Metric": "False Negative Rate", "Value": metrics["false_negative_rate"]},
            {"Metric": "Matthews Correlation Coef", "Value": metrics["matthews_correlation_coefficient"]},
            {"Metric": "AUC-ROC", "Value": metrics["auc_roc"] if metrics["auc_roc"] else "N/A"},
            {"Metric": "", "Value": ""},  # Separator
            {"Metric": "Optimal Threshold", "Value": metrics["optimal_threshold"]},
            {"Metric": "Optimal F1 Score", "Value": metrics["optimal_f1_score"]},
            {"Metric": "", "Value": ""},  # Separator
            {"Metric": "True Positives", "Value": metrics["confusion_matrix"]["true_positives"]},
            {"Metric": "True Negatives", "Value": metrics["confusion_matrix"]["true_negatives"]},
            {"Metric": "False Positives", "Value": metrics["confusion_matrix"]["false_positives"]},
            {"Metric": "False Negatives", "Value": metrics["confusion_matrix"]["false_negatives"]},
        ]
        
        return pd.DataFrame(rows)
    

    def run_full_pipeline(self, compute_metrics: bool = True) -> dict:
        """
        Orchestrates the entire execution: runs all pattern detection logic, 
        computes final scores, maps patterns to accounts, builds rings, and packages the results.
        
        Args:
            compute_metrics (bool, optional): If True and ground truth is available, computes performance. Defaults to True.
        
        Returns:
            dict: The ultimate results payload containing suspicious_accounts, fraud_rings, account_scores, 
                  pattern_detections breakdown, run summary, and performance metrics (if requested).
        """
        t0 = time.perf_counter()

        # Run all detection methods
        cycles = self.detect_cycles(max_length=8)
        smurfing = self.detect_smurfing()
        shells = self.detect_layered_shells()
        cross_border = self.detect_cross_border_chains()
        kyc_clusters = self.detect_unverified_kyc_clusters()
        round_amounts = self.detect_round_amount_patterns()
        device_sharing = self.detect_device_sharing()
        new_bursts = self.detect_new_account_bursts()
        velocity_spikes = self.detect_velocity_spikes()
        rapid_movement = self.detect_rapid_movement()

        # Compute scores with all patterns
        scores = self.compute_scores(
            cycles, smurfing, shells, cross_border, kyc_clusters,
            round_amounts, device_sharing, new_bursts, velocity_spikes, rapid_movement
        )
        
        threshold = adaptive_threshold(scores)
        rings = self.build_fraud_rings(
            cycles, smurfing, shells, cross_border, kyc_clusters, rapid_movement, scores
        )

        # Build account metadata
        account_meta: dict = defaultdict(lambda: {"patterns": set(), "ring_id": None})
        
        for c in cycles:
            [account_meta[a]["patterns"].add(c["pattern"]) for a in c["accounts"]]
        for s in smurfing:
            account_meta[s["account"]]["patterns"].add(s["pattern"])
        for sh in shells:
            [account_meta[a]["patterns"].add(sh["pattern"]) for a in sh["accounts"]]
        for cb in cross_border:
            account_meta[cb["account"]]["patterns"].add(cb["pattern"])
        for kc in kyc_clusters:
            [account_meta[a]["patterns"].add(kc["pattern"]) for a in kc["accounts"]]
        for ra in round_amounts:
            account_meta[ra["account"]]["patterns"].add(ra["pattern"])
        for ds in device_sharing:
            [account_meta[a]["patterns"].add(ds["pattern"]) for a in ds["accounts"]]
        for nb in new_bursts:
            account_meta[nb["account"]]["patterns"].add(nb["pattern"])
        for vs in velocity_spikes:
            account_meta[vs["account"]]["patterns"].add(vs["pattern"])
        for rm in rapid_movement:
            [account_meta[a]["patterns"].add(rm["pattern"]) for a in rm["accounts"]]
        for r in rings:
            [account_meta[a].__setitem__("ring_id", r["ring_id"]) for a in r["member_accounts"]]

        # Build suspicious accounts list
        suspicious = []
        for acc, score in scores.items():
            if score < threshold:
                continue
            meta = account_meta[acc]
            patterns = meta["patterns"]
            reasons = self._build_reasons(
                acc, score, meta, smurfing, cross_border, round_amounts,
                device_sharing, new_bursts, velocity_spikes
            )

            suspicious.append({
                "account_id": acc,
                "suspicion_score": score,
                "risk_level": _risk_level(score),
                "reasons": reasons,
                "detected_patterns": [_PATTERN_CLEAN.get(p, p) for p in patterns],
                "ring_id": meta["ring_id"],
            })

        # Compute performance metrics if requested and ground truth available
        performance_metrics = None
        if compute_metrics:
            performance_metrics = self.evaluate_metrics(scores, threshold)

        result = {
            "suspicious_accounts": suspicious,
            "fraud_rings": rings,
            "account_scores": scores,
            "pattern_detections": {
                "cycles": len(cycles),
                "smurfing": len(smurfing),
                "shells": len(shells),
                "cross_border": len(cross_border),
                "kyc_clusters": len(kyc_clusters),
                "round_amounts": len(round_amounts),
                "device_sharing": len(device_sharing),
                "new_bursts": len(new_bursts),
                "velocity_spikes": len(velocity_spikes),
                "rapid_movement": len(rapid_movement),
            },
            "summary": {
                "total_accounts_analyzed": len(self._accounts),
                "suspicious_accounts_flagged": len(suspicious),
                "fraud_rings_detected": len(rings),
                "threshold_used": round(threshold, 2),
                "processing_time_seconds": round(time.perf_counter() - t0, 3),
            }
        }
        
        # Add metrics if available
        if performance_metrics:
            result["performance_metrics"] = performance_metrics
        
        return result

