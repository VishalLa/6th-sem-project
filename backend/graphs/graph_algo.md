# Fraud Detection Engine - Technical Overview

## What It Does
A graph-based fraud detection system that analyzes financial transaction networks to identify suspicious patterns using 10 detection algorithms, multi-dimensional scoring, and machine learning metrics.

---

## Core Architecture

### Input → Graph → Detection → Scoring → Output

1. **Input**: Transaction CSV with columns like sender, receiver, amount, timestamp, country, KYC status, device_id
2. **Graph Construction**: Builds NetworkX graphs (MultiDiGraph for transactions, DiGraph for account structure)
3. **Pattern Detection**: Runs 10 algorithms to find fraud patterns
4. **Scoring**: Combines 6 dimensions (structural, behavioral, statistical, network, contextual, legitimate)
5. **Output**: Suspicious accounts, fraud rings, and performance metrics

---

## 10 Detection Algorithms

### 1. **Cycle Detection** (Dynamic Length 3-6)

**What**: Finds circular money flows (A → B → C → A)

**Why**: Money laundering often involves cycles to obscure origin

**How**: 
- Length 3: Optimized triangle detection O(V × deg²)
- Length 4-6: BFS-based cycle finding

**Example**: Company A pays B, B pays C, C pays back A

### 2. **Smurfing Detection** (Fan-in/Fan-out)

**What**: Detects accounts with many incoming (fan-in) or outgoing (fan-out) connections

**Why**: Structuring and money mule operations use hub accounts

**How**: Counts in-degree and out-degree; flags if ≥ threshold (default: 8)

**Example**: Account receives from 50 sources in one day (consolidation)

### 3. **Layered Shells Detection**

**What**: Finds intermediary accounts acting as pass-throughs

**Why**: Layering phase of money laundering uses shell accounts

**How**: Identifies nodes with low out-degree (≤2) between source and destination

**Example**: A → Shell → B (Shell only forwards money, minimal activity)

### 4. **Cross-Border Chains**

**What**: Tracks transactions spanning multiple countries

**Why**: International laundering exploits jurisdictional gaps

**How**: Aggregates unique countries per account from sender_country/receiver_country

**Example**: Account transacts across US → SG → AE → UK (4 countries)

### 5. **Unverified KYC Clusters**

**What**: Groups of unverified accounts transacting together

**Why**: Fraud rings often use fake/incomplete identities

**How**: Finds connected components in subgraph of unverified accounts (status: Pending/None/Unknown)

**Example**: 8 unverified accounts forming a connected network

### 6. **Round Amount Patterns**

**What**: Accounts frequently using round numbers (e.g., $10,000 vs $9,847.23)

**Why**: Legitimate business rarely uses exact round amounts

**How**: Calculates ratio of round_amount transactions; flags if ≥70%

**Example**: 15 out of 20 transactions are round amounts (75%)

### 7. **Device Sharing**

**What**: Multiple accounts using same device/IP

**Why**: Identity fraud, account farms, coordinated attacks

**How**: Groups accounts by device_id; flags if ≥3 accounts per device

**Example**: 10 accounts all using device DEV-5033

### 8. **New Account Bursts**

**What**: Newly created accounts with high activity

**Why**: "Bust-out" fraud, test accounts before larger fraud

**How**: Checks sender_acct_age ≤30 days AND transaction_count ≥10

**Example**: Account opened 5 days ago, already 50 transactions

### 9. **Velocity Spikes**

**What**: Abnormally fast transaction sequences

**Why**: Automated fraud, bot attacks

**How**: Calculates average velocity_mins (time between transactions); flags if ≤5 minutes

**Example**: 20 transactions in 30 minutes (avg 1.5 min gap)

### 10. **Rapid Movement**

**What**: Money moving quickly through multiple accounts

**Why**: Quick laundering to avoid detection

**How**: Tracks transaction chains within time window (default: 24 hours)

**Example**: A → B (time 0) → B → C (time +2hr) → C → D (time +5hr)

---

## Scoring System

### Multi-Dimensional Score (0-100)

**Formula:**
```
Raw = 0.30×Structural + 0.20×Behavioral + 0.10×Statistical + 
      0.10×Network + 0.20×Contextual - 0.20×Legitimate

Final Score = 100 / (1 + exp(-5 × Raw))  # Sigmoid scaling
```

### 6 Scoring Dimensions:

**1. Structural (30%)**
- Pattern membership weight
- Cycles: +1.0, Smurfing: +0.7, Shells: +0.8
- Captures direct fraud pattern involvement

**2. Behavioral (20%)**
- Transaction activity: (in_degree + out_degree) / 20
- Higher activity = higher suspicion (capped at 1.0)
- Identifies unusually active accounts

**3. Statistical (10%)**
- Degree z-score: |degree - mean| / std_dev
- Outlier detection via standard deviation
- Finds accounts behaving differently from norm

**4. Network (10%)**
- Sparse matrix propagation of neighbor scores
- "Guilt by association" principle
- If your neighbors are suspicious, you might be too

**5. Contextual (20%)**
- New patterns from additional columns
- Cross-border: +0.6, KYC: +0.8, Round amounts: +0.5
- Device sharing: +0.7, New bursts: +0.6, Velocity: +0.7, Rapid: +0.8

**6. Legitimate (-20%)**
- Dampening for established accounts
- High in_degree (>50) AND high out_degree (>50): -0.5
- Reduces false positives for legitimate businesses

### Risk Levels:
- **0-40**: Low (legitimate)
- **40-70**: Medium (investigate)
- **70-100**: High (likely fraud)

---

## Fraud Ring Formation

**Purpose**: Groups suspicious accounts into organized fraud rings

**Algorithm:**
1. Collect all group-based patterns (cycles, shells, KYC clusters, rapid movement)
2. For each group, check if members overlap with existing rings (skip if overlap)
3. Calculate ring risk score:
```
   Risk = min(100, 
     0.5 × Avg_Member_Score + 
     0.3 × Size × 5 + 
     0.2 × Max_Member_Score
   )
```
4. Assign unique ring_id (RING_001, RING_002, etc.)

**Why Groups Matter**: Organized fraud is network-based, not individual

---

## Performance Metrics (with Ground Truth)

### Confusion Matrix
```
                Predicted
                Fraud    Legit
Actual  Fraud   TP       FN
        Legit   FP       TN
```

### Key Metrics:

**Precision** = TP / (TP + FP)
- Of flagged accounts, how many are actually fraud?
- High precision = fewer false alarms

**Recall** = TP / (TP + FN)
- Of actual fraud, how many did we catch?
- High recall = fewer missed frauds

**F1 Score** = 2 × (Precision × Recall) / (Precision + Recall)
- Harmonic mean balancing precision and recall
- Best single metric for imbalanced data

**AUC-ROC**: Area under ROC curve (0.5=random, 1.0=perfect)

**MCC** (Matthews Correlation Coefficient): Balanced metric for imbalanced datasets
- Range: -1 (total disagreement) to +1 (perfect)
- More reliable than accuracy when fraud rate is low (<1%)

### Adaptive Threshold
```
Threshold = Mean(scores) + 1.0 × StdDev(scores)
```
Automatically adjusts to data distribution; can be optimized to maximize F1

---

## Why These Algorithms Work

### Graph-Based Approach
- **Financial networks are graphs**: Accounts = nodes, Transactions = edges
- **Fraud leaves structural patterns**: Cycles, hubs, chains visible in graph topology
- **Fast computation**: Sparse matrices, optimized algorithms (O(V×deg²) for triangles)

### Multi-Dimensional Scoring
- **No single signal catches all fraud**: Combines 6 independent dimensions
- **Weighted by importance**: Structural (30%) heaviest, network propagation (10%) lightest
- **Sigmoid normalization**: Converts raw scores to 0-100 scale with smooth transitions

### Why Each Pattern Matters
- **Cycles**: Money laundering classic (placement → layering → integration)
- **Smurfing**: Avoids transaction reporting limits ($10k in US)
- **Shells**: Obscures beneficial ownership
- **Cross-border**: Exploits different regulatory regimes
- **KYC clusters**: Identity fraud networks
- **Round amounts**: Unusual in legitimate business (invoices are rarely exact)
- **Device sharing**: Account farms, identity theft
- **New bursts**: Test accounts before major fraud
- **Velocity**: Bots move faster than humans
- **Rapid movement**: Quick extraction before detection

### Machine Learning Integration
- Uses scikit-learn metrics (not ML model itself)
- Graph algorithms + rule-based scoring + statistical analysis
- Supervised evaluation (if labels provided), unsupervised detection (no labels needed)

---

## Performance Characteristics

**Time Complexity:**
- Cycle detection: O(V × deg²) for length 3, O(V × deg^k) for length k
- Smurfing: O(V)
- Other detections: O(E) to O(V×E) where V=accounts, E=transactions

**Space Complexity:**
- Sparse adjacency matrix: O(E)
- Pre-cached successors/predecessors: O(V + E)
- Total: O(V + E) - linear in graph size

**Scalability:**
- Optimized for 10k-1M transactions
- Sparse matrix operations for large networks
- Configurable thresholds to control detection sensitivity

---

## Usage Pattern
```python
# 1. Build graph
graph = Graph(transaction_dataframe)

# 2. Initialize engine
engine = MainEngine(graph, cycle_length=3, ground_truth_labels=labels)

# 3. Run pipeline
results = engine.run_full_pipeline(compute_metrics=True)

# 4. Access results
results['suspicious_accounts']  # List of flagged accounts with reasons
results['fraud_rings']          # Grouped fraud networks
results['account_scores']       # All scores (0-100)
results['performance_metrics']  # Precision, recall, F1, AUC-ROC (if labels)
```

**Output Example:**
```python
{
  "account_id": "ACC_12345",
  "suspicion_score": 85.3,
  "risk_level": "HIGH",
  "reasons": [
    "cycle_member(length=3,deg=12)",
    "cross_border_chain(countries=4)",
    "device_sharing(device=DEV-5033,accounts=8)"
  ],
  "detected_patterns": ["cycle_3", "cross_border_chain", "device_sharing"],
  "ring_id": "RING_003"
}
```

---

## Key Innovations

1. **Dynamic cycle detection**: Configurable 3-6 node cycles (not just triangles)
2. **Contextual scoring**: Leverages all transaction metadata (country, KYC, device, velocity)
3. **Legitimate dampening**: Reduces false positives for high-volume accounts
4. **Fraud ring formation**: Groups accounts, not just individual flags
5. **Comprehensive metrics**: F1, MCC, AUC-ROC for robust evaluation
6. **Reason generation**: Explainable AI - each flag has detailed justification
7. **Adaptive thresholding**: Automatically adjusts to data distribution

---

**Version**: 1.0  
**Optimized for**: Financial transaction networks, anti-money laundering (AML), fraud detection
