"""
Domain Vocabulary for Fraud Detection Chatbot.
Defines all domain-specific terms, synonyms, column mappings, and intent keywords.
IMPROVED: Added better aliases for common queries and risk_score support.
"""

from typing import Dict, List, Set


# COLUMN MAPPINGS: natural language → actual CSV column names
COLUMN_ALIASES: Dict[str, str] = {
    # transaction_id
    "transaction id": "transaction_id",
    "transaction": "transaction_id",
    "txn id": "transaction_id",
    "txn": "transaction_id",
    "id": "transaction_id",
    "tx id": "transaction_id",
    "tx": "transaction_id",

    # sender
    "sender": "sender",
    "from": "sender",
    "source account": "sender",
    "payer": "sender",
    "originator": "sender",
    "sending account": "sender",

    # receiver
    "receiver": "receiver",
    "recipient": "receiver",
    "to": "receiver",
    "destination account": "receiver",
    "payee": "receiver",
    "beneficiary": "receiver",
    "receiving account": "receiver",

    # amount
    "amount": "amount",
    "value": "amount",
    "sum": "amount",
    "total": "amount",
    "money": "amount",
    "payment": "amount",
    "transfer amount": "amount",
    "transaction amount": "amount",
    "price": "amount",
    "cost": "amount",
    "dollar": "amount",
    "dollars": "amount",
    "usd": "amount",

    # timestamp
    "timestamp": "timestamp",
    "time": "timestamp",
    "date": "timestamp",
    "when": "timestamp",
    "datetime": "timestamp",
    "transaction time": "timestamp",
    "transaction date": "timestamp",
    "created at": "timestamp",

    # sender_country
    "sender country": "sender_country",
    "from country": "sender_country",
    "origin country": "sender_country",
    "source country": "sender_country",
    "sending country": "sender_country",

    # receiver_country
    "receiver country": "receiver_country",
    "to country": "receiver_country",
    "destination country": "receiver_country",
    "receiving country": "receiver_country",
    "beneficiary country": "receiver_country",

    # sender_kyc
    "kyc": "sender_kyc",
    "sender kyc": "sender_kyc",
    "kyc status": "sender_kyc",
    "verification": "sender_kyc",
    "verified": "sender_kyc",
    "kyc verified": "sender_kyc",

    # txn_method
    "method": "txn_method",
    "txn method": "txn_method",
    "transaction method": "txn_method",
    "payment method": "txn_method",
    "channel": "txn_method",
    "type": "txn_method",
    "mode": "txn_method",

    # device_id
    "device": "device_id",
    "device id": "device_id",
    "device identifier": "device_id",

    # sender_acct_age
    "account age": "sender_acct_age",
    "sender account age": "sender_acct_age",
    "acct age": "sender_acct_age",
    "age": "sender_acct_age",
    "account tenure": "sender_acct_age",
    "how old": "sender_acct_age",

    # velocity_mins
    "velocity": "velocity_mins",
    "velocity minutes": "velocity_mins",
    "transaction velocity": "velocity_mins",
    "velocity mins": "velocity_mins",
    "speed": "velocity_mins",
    "frequency": "velocity_mins",

    # is_round_amount
    "round amount": "is_round_amount",
    "round": "is_round_amount",
    "is round": "is_round_amount",
    "round number": "is_round_amount",
    "rounded": "is_round_amount",
    
    # ADDED: risk_score support (will be computed dynamically)
    "risk score": "risk_score",
    "risk": "risk_score",
    "score": "risk_score",
    "risk level": "risk_score",
    "risk rating": "risk_score",
}


# SYNONYM DICTIONARY: synonyms for value matching
SYNONYM_DICTIONARY: Dict[str, List[str]] = {
    # KYC status
    "verified": ["verified", "kyc verified", "cleared", "approved", "confirmed", "complete"],
    "pending": ["pending", "under review", "in progress", "awaiting", "incomplete"],
    "none": [
        "none", "unverified", "no kyc", "not verified", "unknown",
        "missing kyc", "no verification", "kyc none", "no kyc status",
    ],

    # Transaction methods
    "crypto": [
        "crypto", "cryptocurrency", "bitcoin", "btc", "digital currency", "blockchain",
        "eth", "ethereum", "digital asset",
    ],
    "wire": ["wire", "wire transfer", "bank wire", "swift", "international transfer", "telegraphic"],
    "ach": ["ach", "automated clearing house", "bank transfer", "direct deposit", "eft"],
    "p2p": ["p2p", "peer to peer", "person to person", "direct transfer", "person-to-person"],

    # Countries
    "sg": ["sg", "singapore"],
    "in": ["in", "india"],
    "ae": ["ae", "uae", "dubai", "united arab emirates"],
    "ng": ["ng", "nigeria", "nigerian"],
    "ca": ["ca", "canada", "canadian"],
    "uk": ["uk", "united kingdom", "britain", "england", "gb"],
    "us": ["us", "usa", "united states", "america", "american"],

    # Amount descriptors
    "high": ["high", "large", "big", "significant", "major", "substantial", "above"],
    "low": ["low", "small", "minor", "tiny", "minimal", "below"],
    "round": ["round", "even", "whole", "exact", "rounded"],

    # Time periods
    "today": ["today", "now", "current day"],
    "recent": ["recent", "latest", "new", "last", "newest"],
    "old": ["old", "earliest", "first", "oldest", "ancient"],
}


# INTENT KEYWORDS: maps keywords → intent types
INTENT_KEYWORDS: Dict[str, List[str]] = {
    "show": [
        "show", "display", "list", "get", "fetch", "find", "give me",
        "tell me", "what are", "which", "view", "see", "look at", "retrieve",
        "pull", "lookup", "search", "give", "provide", "return",
        "what transactions", "show me", "list all", "get me", "i want",
        "let me see", "bring up", "identify", "highlight",
    ],
    "count": [
        "count", "how many", "number of", "total number", "tally",
        "how much", "quantity", "how often",
        "total count", "count of", "how frequent", "volume", "occurrences",
        "instances", "number", "amount of records", "how large",
    ],
    "aggregate": [
        "average", "avg", "mean", "sum", "total", "max", "maximum",
        "min", "minimum", "median", "top", "bottom", "highest", "lowest",
        "aggregate", "summarize", "overall", "combined", "cumulative",
        "total amount", "grand total", "what is the total", "what's the total",
        "what is the average", "what's the average", "what is the sum",
    ],
    "filter": [
        "where", "with", "having", "that have", "containing", "only",
        "filter", "matching", "equals", "is", "are", "from", "by", "between",
        "above", "below", "over", "under", "greater", "less",
        "using", "via", "through", "sent from", "received by", "involve",
        "within", "excluding", "include", "without", "except", "specifically",
        "limited to", "restrict", "narrow", "whose", "that are",
    ],
    "sort": [
        "sort", "order", "rank", "arrange", "ascending", "descending",
        "highest to lowest", "lowest to highest", "ranked", "top", "bottom",
        "sorted by", "ordered by", "ranked by", "in order of",
        "by highest", "by lowest", "by most", "by least",
    ],
    "group": [
        "group by", "grouped by", "per", "by country", "by method",
        "categorize", "breakdown", "split by", "each", "per group",
        "by type", "by channel", "by kyc", "by payment", "by sender",
        "by receiver", "by status", "segment", "partition", "organize by",
        "distribute by", "classify by", "separate by",
    ],
    "compare": [
        "compare", "vs", "versus", "difference", "between", "contrast",
        "more than", "less than", "greater", "higher", "lower",
        "relative to", "compared to", "against", "side by side", "ratio of",
    ],
    "fraud": [
        "fraud", "suspicious", "anomaly", "risk", "flagged", "alert",
        "detect", "unusual", "abnormal", "outlier", "high risk",
        "high-risk", "risky", "dangerous", "problematic",
        "fraud detection", "suspect", "bad actor", "money laundering",
        "aml", "kyc none", "unverified", "at risk", "marked", "suspicious activity",
        "flag", "red flag", "questionable", "irregular", "illicit",
    ],
    "navigate": [
        "go to", "navigate", "open", "jump to", "show page", "chart",
        "dashboard", "graph", "visualize", "plot",
    ],
    "math": [
        "calculate", "compute", "growth rate", "percentage", "ratio",
        "rate", "increase", "decrease", "change", "percent", "multiply", "divide",
        "proportion", "share", "fraction", "breakdown percentage",
    ],
    "help": [
        "help", "what can you do", "how do i", "explain", "what is",
        "describe", "guide", "tutorial", "capabilities",
        "how to", "what can", "tell me about", "instructions", "usage",
    ],
}


# DOMAIN TERMS: all valid domain-specific tokens
DOMAIN_TERMS: Set[str] = {
    # Columns
    "transaction_id", "sender", "receiver", "amount", "timestamp",
    "sender_country", "receiver_country", "sender_kyc", "txn_method",
    "device_id", "sender_acct_age", "velocity_mins", "is_round_amount",
    "risk_score", "risk_flags",  # ADDED
    # Methods
    "crypto", "wire", "ach", "p2p",
    # KYC
    "verified", "pending", "none",
    # Countries
    "sg", "in", "ae", "ng", "ca", "uk", "us",
    # Concepts
    "fraud", "transaction", "payment", "transfer", "account",
    "velocity", "kyc", "device", "country", "amount",
    "suspicious", "high-risk", "risky",  # ADDED
}

# Numeric column names - ADDED risk_score
NUMERIC_COLUMNS: List[str] = ["amount", "sender_acct_age", "velocity_mins", "risk_score"]

# Categorical column names
CATEGORICAL_COLUMNS: List[str] = [
    "sender", "receiver", "sender_country", "receiver_country",
    "sender_kyc", "txn_method", "device_id", "is_round_amount"
]

# All column names - ADDED risk_score and risk_flags
ALL_COLUMNS: List[str] = [
    "transaction_id", "sender", "receiver", "amount", "timestamp",
    "sender_country", "receiver_country", "sender_kyc", "txn_method",
    "device_id", "sender_acct_age", "velocity_mins", "is_round_amount",
    "risk_score", "risk_flags"
]

# Valid filter values per column
VALID_FILTER_VALUES: Dict[str, List[str]] = {
    "sender_kyc": ["Verified", "Pending", "None"],
    "txn_method": ["Crypto", "Wire", "ACH", "P2P"],
    "sender_country": ["SG", "IN", "AE", "NG", "CA", "UK", "US"],
    "receiver_country": ["SG", "IN", "AE", "NG", "CA", "UK", "US"],
    "is_round_amount": ["True", "False"],
}

# Fraud risk indicators
FRAUD_INDICATORS: Dict[str, str] = {
    "unverified_kyc": "Sender KYC is None or Pending",
    "high_velocity": "Transaction velocity is very low (< 5 mins since last txn)",
    "round_amount": "Amount is a round number (potential structuring)",
    "cross_border_high_risk": "Cross-border transaction involving high-risk country pairs",
    "new_account": "Sender account age < 30 days",
    "large_amount": "Amount > 500 USD",
}

# High-risk country pairs for fraud detection
HIGH_RISK_COUNTRY_PAIRS: List[tuple] = [
    ("NG", "SG"), ("NG", "UK"), ("NG", "US"), ("NG", "CA"),
    ("SG", "NG"), ("AE", "NG"),
]
