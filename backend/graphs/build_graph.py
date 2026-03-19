import re
import pandas as pd 
import networkx as nx 
from .validation import InvalidColumnsError


class Graph:
   
    COLUMN_PATTERNS = {
        "transaction_id": re.compile(r"(txn|trans|transaction).*(id|no|number|ref)", re.I),
        "sender": re.compile(r"(sender|from|debitor|source|paid.{0,3}by|sender_id|payer)", re.I),
        "receiver": re.compile(r"(receiver|to|creditor|destination|beneficiary|paid.{0,3}to|receiver_id|payee)", re.I),
        "amount": re.compile(r"(amount|amt|money|value|rs|inr|debit|credit|sum|total)", re.I),
        "timestamp": re.compile(r"(date|time|timestamp|datetime|transaction.{0,3}date|txn.{0,3}date|when)", re.I),
        "sender_country": re.compile(r"(sender.{0,3}country|origin.{0,3}country|sender.{0,3}loc|from.{0,3}country|source.{0,3}country)", re.I),
        "receiver_country": re.compile(r"(receiver.{0,3}country|dest.{0,3}country|receiver.{0,3}loc|to.{0,3}country|destination.{0,3}country)", re.I),
        "sender_kyc": re.compile(r"(sender.{0,3}kyc|from.{0,3}kyc|kyc.{0,3}status|verified|verification|kyc)", re.I),
        "txn_method": re.compile(r"(txn.{0,3}method|transaction.{0,3}method|payment.{0,3}method|type|method|channel|mode)", re.I),
        "device_id": re.compile(r"(device|device.{0,3}id|dev.{0,3}id|ip|ip.{0,3}address|machine.{0,3}id)", re.I),
        "sender_acct_age": re.compile(r"(sender.{0,3}acct.{0,3}age|sender.{0,3}account.{0,3}age|account.{0,3}age|acct.{0,3}age|age)", re.I),
        "velocity_mins": re.compile(r"(velocity|velocity.{0,3}mins|time.{0,3}gap|time.{0,3}diff|gap.{0,3}mins)", re.I),
        "is_round_amount": re.compile(r"(is.{0,3}round|round|round.{0,3}amount|is.{0,3}round.{0,3}amt)", re.I),
    }

    def __init__(self, raw_dataframe: pd.DataFrame) -> None:
        self.graph = nx.MultiDiGraph()
        self.structure_graph = nx.DiGraph()
        self.dataframe = self._normalize_columns(df=raw_dataframe)
        
        self._build_graph()
        self._build_structure_graph()


    def _match_columns(self, df: pd.DataFrame):
        mapped_columns = {}
        missing_columns = []

        for standard_col, pattern in self.COLUMN_PATTERNS.items():
            matched = False

            for real_col in df.columns:
                if pattern.search(real_col):
                    mapped_columns[standard_col] = real_col
                    matched = True
                    break
            
            if not matched:
                missing_columns.append(standard_col)
        
        if missing_columns:
            raise InvalidColumnsError(
                f"Missing required columns: {', '.join(missing_columns)}. "
                f"Available columns: {', '.join(df.columns)}"
            )
                
        return mapped_columns
    
    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        mapping = self._match_columns(df=df)

        # Rename columns based on mapping
        df = df.rename(columns={v: k for k, v in mapping.items()})

        required_columns = list(self.COLUMN_PATTERNS.keys())
        df = df[required_columns].copy()

        # Clean amount column
        df["amount"] = (
            df["amount"]
            .astype(str)
            .str.replace(r"[₹,$£€,]", "", regex=True)
            .str.replace(r"(cr|dr)", "", regex=True, case=False)
            .str.strip()
        )
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")

        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", dayfirst=True)

        df["velocity_mins"] = pd.to_numeric(df["velocity_mins"], errors="coerce")
        df["sender_acct_age"] = pd.to_numeric(df["sender_acct_age"], errors="coerce")
        
        # Convert boolean column - handle various representations
        if df["is_round_amount"].dtype == 'object':
            df["is_round_amount"] = df["is_round_amount"].map({
                'True': True, 'true': True, 'TRUE': True, '1': True, 1: True,
                'False': False, 'false': False, 'FALSE': False, '0': False, 0: False,
                'Yes': True, 'yes': True, 'No': False, 'no': False
            })
        else:
            df["is_round_amount"] = df["is_round_amount"].astype(bool)

        df = df.reset_index(drop=True)
        return df
    
    
    def _build_graph(self):
        for _, row in self.dataframe.iterrows():
            edge_attrs = row.dropna().to_dict()
            
            sender = edge_attrs.pop('sender')
            receiver = edge_attrs.pop('receiver')

            self.graph.add_edge(sender, receiver, **edge_attrs)
            

    def _build_structure_graph(self):
        self.structure_graph.add_edges_from(
            (u, v) for u, v in self.graph.edges()
        )
