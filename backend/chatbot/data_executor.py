import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple

from .domain_vocabulary import (
    FRAUD_INDICATORS, 
    HIGH_RISK_COUNTRY_PAIRS, 
    NUMERIC_COLUMNS
)


logger = logging.getLogger(__name__)

FRAUD_VELOCITY_THRESHOLD = 5      # minutes
FRAUD_AMOUNT_THRESHOLD = 500      # USD
FRAUD_NEW_ACCOUNT_DAYS = 30       # days


class DataExecutor:
    """
    Executes query specs against a loaded pandas DataFrame.
    Returns results and metadata for answer construction.
    """

    def __init__(self, df: pd.DataFrame):
        """
        Args:
            df: The loaded transactions DataFrame
        """
        self.df = df.copy()
        self._preprocess_dataframe()
        logger.info(f"DataExecutor initialized with {len(self.df)} rows.")


    def _preprocess_dataframe(self):
        """Preprocess the dataframe: parse timestamps, normalize strings."""

        if "timestamp" in self.df.columns:
            self.df["timestamp"] = pd.to_datetime(self.df["timestamp"], errors="coerce")

        # Normalize string columns
        str_cols = ["sender_kyc", "txn_method", "sender_country", "receiver_country"]
        for col in str_cols:
            if col in self.df.columns:
                self.df[col] = self.df[col].astype(str).str.strip()

        # Ensure is_round_amount is boolean
        if "is_round_amount" in self.df.columns:
            self.df["is_round_amount"] = self.df["is_round_amount"].astype(str).str.lower().isin(["true", "1", "yes"])

        logger.debug("DataFrame preprocessing complete.")


    def execute(self, query_spec: Dict) -> Dict:
        """
        Route and execute a query spec.

        Args:
            query_spec: Analyzed query specification

        Returns:
            Result dict with: data (DataFrame or scalar), metadata, operation
        """
        operation = query_spec.get("operation_type", "SELECT")
        logger.info(f"Executing operation: {operation}")

        try:
            if operation == "FRAUD_DETECT":
                return self.execute_fraud_detection(query_spec)
            elif operation == "GROUP_BY":
                return self.execute_group_by(query_spec)
            elif operation in ("AGGREGATE", "CALCULATE"):
                return self.execute_aggregation(query_spec)
            elif operation == "COUNT":
                return self.execute_count(query_spec)
            elif operation in ("SORT", "SELECT", "FILTER", "COMPARE"):
                return self.execute_ranking(query_spec)
            else:
                return self.execute_ranking(query_spec)

        except Exception as e:
            logger.error(f"Execution error for op={operation}: {e}", exc_info=True)
            return {
                "data": None,
                "metadata": {"error": str(e)},
                "operation": operation,
                "success": False,
            }
        

    def _apply_filters(self, df: pd.DataFrame, query_spec: Dict) -> pd.DataFrame:
        """
        Apply filter conditions and numeric conditions to a DataFrame.
        IMPROVED: Better handling of conflicting filters.

        Args:
            df: Input DataFrame
            query_spec: Query spec with filters and numeric_conditions

        Returns:
            Filtered DataFrame
        """
        # Group filters by column to detect conflicts
        filters_by_column = {}
        for f in query_spec.get("filters", []):
            col = f.get("column")
            if col not in filters_by_column:
                filters_by_column[col] = []
            filters_by_column[col].append(f)
        
        # Apply filters, using OR logic for same column with different values
        for col, col_filters in filters_by_column.items():
            if col not in df.columns:
                continue
            
            try:
                if len(col_filters) == 1:
                    f = col_filters[0]
                    op = f.get("operator", "==")
                    val = f.get("value")

                    # Special case: filtering for None/null KYC (or any column)
                    # The raw data may store actual NaN/None, which .astype(str) turns
                    # into the string "nan" or "none". Match both.
                    if op == "==" and str(val).lower() in ("none", "null", "nan", ""):
                        df = df[
                            df[col].isna()
                            | df[col].astype(str).str.lower().isin(["none", "null", "nan", ""])
                        ]
                    elif op == "==":
                        df = df[df[col].astype(str).str.lower() == str(val).lower()]
                    elif op == "!=":
                        df = df[df[col].astype(str).str.lower() != str(val).lower()]
                else:
                    # Multiple filters on same column — OR logic
                    values = [f.get("value") for f in col_filters]
                    none_vals = {str(v).lower() for v in values if str(v).lower() in ("none", "null", "nan", "")}
                    normal_vals = [str(v).lower() for v in values if str(v).lower() not in ("none", "null", "nan", "")]

                    if none_vals and normal_vals:
                        df = df[
                            df[col].isna()
                            | df[col].astype(str).str.lower().isin(["none", "null", "nan", ""] + normal_vals)
                        ]
                    elif none_vals:
                        df = df[
                            df[col].isna()
                            | df[col].astype(str).str.lower().isin(["none", "null", "nan", ""])
                        ]
                    else:
                        df = df[df[col].astype(str).str.lower().isin(normal_vals)]
                    logger.debug(f"Applied OR filter for {col}: {values}")
                    
            except Exception as e:
                logger.warning(f"Filter error on col={col}: {e}")

        # Apply numeric conditions
        for cond in query_spec.get("numeric_conditions", []):
            col = cond.get("column")
            op = cond.get("operator", ">")
            val = cond.get("value")

            if col not in df.columns:
                continue

            try:
                numeric_col = pd.to_numeric(df[col], errors="coerce")
                if op == ">":
                    df = df[numeric_col > float(val)]
                elif op == ">=":
                    df = df[numeric_col >= float(val)]
                elif op == "<":
                    df = df[numeric_col < float(val)]
                elif op == "<=":
                    df = df[numeric_col <= float(val)]
                elif op == "==" or op == "=":
                    df = df[numeric_col == float(val)]
                elif op == "between" and isinstance(val, tuple):
                    df = df[(numeric_col >= val[0]) & (numeric_col <= val[1])]
            except Exception as e:
                logger.warning(f"Numeric condition error on col={col}: {e}")

        # Entity-based filters (specific account/country IDs)
        entities = query_spec.get("entities", {})

        if "account_ids" in entities:
            acct_ids = [a.upper() for a in entities["account_ids"]]
            df = df[df["sender"].isin(acct_ids) | df["receiver"].isin(acct_ids)]

        if "transaction_ids" in entities:
            txn_ids = [t.upper() for t in entities["transaction_ids"]]
            df = df[df["transaction_id"].isin(txn_ids)]

        if "countries" in entities and "sender_country" in df.columns:
            countries = [c.upper() for c in entities["countries"]]
            df = df[df["sender_country"].isin(countries) | df["receiver_country"].isin(countries)]

        return df
    

    def execute_count(self, query_spec: Dict) -> Dict:
        """
        Execute a COUNT operation.
        FIXED: This method was missing!
        """
        df = self._apply_filters(self.df, query_spec)
        
        count = len(df)
        
        return {
            "data": {"count": count},
            "metadata": {
                "count": count,
                "operation": "COUNT",
                "total_records": len(self.df),
            },
            "operation": "COUNT",
            "success": True,
        }


    def execute_ranking(self, query_spec: Dict) -> Dict:
        """Execute a SELECT/SORT/FILTER operation."""
        df = self._apply_filters(self.df, query_spec)

        # Sort
        target_col = query_spec.get("target_column", "amount")
        sort_dir = query_spec.get("sort_direction", "DESC")

        if target_col in df.columns and target_col in NUMERIC_COLUMNS:
            df = df.sort_values(
                by=target_col,
                ascending=(sort_dir == "ASC"),
                na_position="last",
            )
        elif "timestamp" in df.columns:
            df = df.sort_values(by="timestamp", ascending=False)

        # Limit - IMPROVED: Check for explicit limit in entities
        entities = query_spec.get("entities", {})
        
        # Get limit from various sources
        limit = None
        if "top_n" in entities:
            limit = entities["top_n"]
        elif "limit" in entities:
            limit = entities["limit"]
        elif "bottom_n" in entities:
            limit = entities["bottom_n"]
        
        # If no explicit limit and operation is SELECT (not COUNT), use reasonable default
        # But if user says "how many", don't limit
        if limit is None:
            # Check if this is a "show all" type query
            raw_query = query_spec.get("raw_query", "").lower()
            if any(phrase in raw_query for phrase in ["how many", "count", "total number"]):
                # Don't limit for count queries
                limit = len(df)
            else:
                # Default limit for display
                limit = 100
        
        was_limited = limit is not None and len(df) > 0 and limit < len(df)
        df = df.head(int(limit)) if limit else df

        return {
            "data": df,
            "metadata": {
                "count": len(df),
                "operation": "SELECT",
                "columns": list(df.columns),
                "limited": was_limited,
            },
            "operation": "SELECT",
            "success": True,
        }


    def execute_group_by(self, query_spec: Dict) -> Dict:
        """
        Execute a GROUP_BY aggregation.
        IMPROVED: Better column detection and aggregation handling.
        """
        df = self._apply_filters(self.df, query_spec)
        group_col = query_spec.get("group_column")

        # IMPROVED: Better fallback logic
        if not group_col or group_col not in df.columns:
            # Try to infer from referenced columns
            referenced = query_spec.get("referenced_columns", [])
            categorical_cols = ["sender_country", "receiver_country", "txn_method", "sender_kyc"]
            
            for col in referenced:
                if col in categorical_cols and col in df.columns:
                    group_col = col
                    break
            
            if not group_col:
                group_col = "txn_method"  # Final fallback
            
            logger.info(f"Inferred group column: {group_col}")

        aggregation = query_spec.get("aggregation", "COUNT")
        target_col = query_spec.get("target_column", "amount")

        if aggregation == "COUNT" or target_col not in NUMERIC_COLUMNS:
            result = df.groupby(group_col).size().reset_index(name="count")
            result = result.sort_values("count", ascending=False)
            agg_col = "count"
        else:
            agg_map = {"SUM": "sum", "AVG": "mean", "MAX": "max", "MIN": "min", "COUNT": "count"}
            agg_func = agg_map.get(aggregation, "sum")
            result = df.groupby(group_col)[target_col].agg(agg_func).reset_index()
            result.columns = [group_col, f"{agg_func}_{target_col}"]
            agg_col = f"{agg_func}_{target_col}"
            result = result.sort_values(agg_col, ascending=False)

        return {
            "data": result,
            "metadata": {
                "count": len(result),
                "operation": "GROUP_BY",
                "group_column": group_col,
                "aggregation": aggregation,
                "columns": list(result.columns),
            },
            "operation": "GROUP_BY",
            "success": True,
        }
    

    def execute_aggregation(self, query_spec: Dict) -> Dict:
        """
        Execute a scalar aggregation (AVG, SUM, MAX, MIN).
        IMPROVED: Better target column detection.
        """
        df = self._apply_filters(self.df, query_spec)
        target_col = query_spec.get("target_column", "amount")
        aggregation = query_spec.get("aggregation", "SUM")

        if target_col not in df.columns:
            target_col = "amount"

        # Handle special columns that might not be in NUMERIC_COLUMNS
        if target_col not in df.columns:
            # Try to find a numeric column
            for col in NUMERIC_COLUMNS:
                if col in df.columns:
                    target_col = col
                    break

        numeric_col = pd.to_numeric(df[target_col], errors="coerce").dropna()

        agg_map = {
            "SUM": ("sum", numeric_col.sum()),
            "AVG": ("average", numeric_col.mean()),
            "MAX": ("maximum", numeric_col.max()),
            "MIN": ("minimum", numeric_col.min()),
            "COUNT": ("count", len(df)),
        }

        label, value = agg_map.get(aggregation, ("sum", numeric_col.sum()))

        return {
            "data": {"label": label, "column": target_col, "value": round(float(value), 4)},
            "metadata": {
                "count": len(df),
                "operation": "AGGREGATE",
                "aggregation": aggregation,
                "column": target_col,
            },
            "operation": "AGGREGATE",
            "success": True,
        }
    

    def execute_fraud_detection(self, query_spec: Dict) -> Dict:
        """
        Identify potentially fraudulent transactions using rule-based signals.
        IMPROVED: Better error handling.
        """
        df = self._apply_filters(self.df, query_spec)
        
        flagged_df = df.copy()
        flagged_df["risk_flags"] = ""
        flagged_df["risk_score"] = 0

        for idx, row in flagged_df.iterrows():
            flags = []
            score = 0

            # Unverified KYC
            kyc = str(row.get("sender_kyc", "")).strip().lower()
            if kyc in ("none", "nan", ""):
                flags.append("No KYC")
                score += 3
            elif kyc == "pending":
                flags.append("Pending KYC")
                score += 1

            # Round amount
            if row.get("is_round_amount", False):
                flags.append("Round Amount")
                score += 1

            # High amount
            try:
                amt = float(row.get("amount", 0))
                if amt > FRAUD_AMOUNT_THRESHOLD:
                    flags.append(f"High Amount (${amt:.2f})")
                    score += 2
            except (ValueError, TypeError):
                pass

            # New account
            try:
                acct_age = float(row.get("sender_acct_age", 999))
                if acct_age < FRAUD_NEW_ACCOUNT_DAYS:
                    flags.append(f"New Account ({int(acct_age)}d)")
                    score += 2
            except (ValueError, TypeError):
                pass

            # High velocity
            try:
                vel = row.get("velocity_mins", None)
                if vel is not None and not pd.isna(vel):
                    vel_f = float(vel)
                    if vel_f < FRAUD_VELOCITY_THRESHOLD:
                        flags.append(f"High Velocity ({vel_f:.1f}min)")
                        score += 2
            except (ValueError, TypeError):
                pass

            # High-risk country pair
            sc = str(row.get("sender_country", "")).upper()
            rc = str(row.get("receiver_country", "")).upper()
            if (sc, rc) in HIGH_RISK_COUNTRY_PAIRS:
                flags.append(f"High-Risk Route ({sc}→{rc})")
                score += 2

            flagged_df.at[idx, "risk_flags"] = " | ".join(flags)
            flagged_df.at[idx, "risk_score"] = score

        # Filter to only flagged rows
        result = flagged_df[flagged_df["risk_score"] > 0].sort_values(
            "risk_score", ascending=False
        )

        return {
            "data": result,
            "metadata": {
                "count": len(result),
                "total_checked": len(df),
                "operation": "FRAUD_DETECT",
                "columns": list(result.columns),
            },
            "operation": "FRAUD_DETECT",
            "success": True,
        }
    