import re
import pandas as pd 
import networkx as nx 
from pathlib import Path
from .validation import InvalidColumnsError
from typing import DefaultDict


class Graph:

    COLUMN_PATTERNS = {
        "transaction_id": re.compile(r"(txn|trans|transaction).*(id|no|number|ref)?", re.I),
        "sender_id": re.compile(r"(sender|from|debitor|source|paid.{0,3}by)", re.I),
        "receiver_id": re.compile(r"(receiver|to|creditor|destination|beneficiary|paid.{0,3}to)", re.I),
        "amount": re.compile(r"(amount|amt|money|value|rs|inr|debit|credit)", re.I),
        "timestamp": re.compile(r"(date|time|timestamp|datetime|transaction.{0,3}date)", re.I),
    }

    REQUIRED_COLUMNS = ["transaction_id", "sender_id", "receiver_id", "amount", "timestamp"]

    """
    raw dataframe will be be recived from api call
    """

    def __init__(self, raw_dataframe: pd.DataFrame) -> None:
        self.dataframe = self._normalize_columns(df=raw_dataframe)
        self.structure_graph = nx.DiGraph()
        self.graph = nx.MultiDiGraph()
        self._build_graph()
        self._build_structure_graph()


    def _match_columns(self, df: pd.DataFrame):
        mapped_columns = {}

        for standard_col, pattern in self.COLUMN_PATTERNS.items():
            for real_col in df.columns:
                if pattern.search(real_col):
                    mapped_columns[standard_col] = real_col
                    break
            else:
                raise InvalidColumnsError(f"Missing column: {standard_col}")

        return mapped_columns
    

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        mapping = self._match_columns(df=df)

        df = df.rename(columns={v: k for k, v in mapping.items()})

        df = df[self.REQUIRED_COLUMNS].copy()

        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace("\ufeff", "", regex=False)
        )

        df["amount"] = (
            df["amount"]
            .astype(str)
            .str.replace(r"[₹,]", "", regex=True)
            .str.replace(r"(cr|dr)", "", regex=True, case=False)
            .str.strip()
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", dayfirst=True)

        df = df.reset_index(drop=True)

        return df
    
    def _build_graph(self):
        for _, row in self.dataframe.iterrows():
            self.graph.add_edge(
                row['sender_id'],
                row['receiver_id'],
                transaction_id=row['transaction_id'],
                amount=row['amount'],
                timestamp=row['timestamp']
            )

    def _build_structure_graph(self):
        self.structure_graph.add_edges_from(
            (u, v) for u, v in self.graph.edges()
        )
    