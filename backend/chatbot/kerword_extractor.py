import re 
import logging 
from typing import List, Dict, Optional, Tuple 


from .domain_vocabulary import (
    COLUMN_ALIASES,
    SYNONYM_DICTIONARY,
    VALID_FILTER_VALUES,
    NUMERIC_COLUMNS,
    ALL_COLUMNS,
    HIGH_RISK_COUNTRY_PAIRS
)

logger = logging.getLogger(__name__)


PATTERNS = {
    "account_id": re.compile(r"\bacc\d{5}\b", re.IGNORECASE),
    "transaction_id": re.compile(r"\btxn\d{7}\b", re.IGNORECASE),
    "device_id": re.compile(r"\bdev-\d{4}\b", re.IGNORECASE),
    "amount_value": re.compile(r"\$?\d+(?:\.\d{1,2})?"),
    "country_code": re.compile(r"\b(sg|in|ae|ng|ca|uk|us)\b", re.IGNORECASE),
    "comparison_op": re.compile(r"(>=|<=|>|<|=|!=)"),
    "percentage": re.compile(r"\d+(?:\.\d+)?%"),
    "date_pattern": re.compile(
        r"\b(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|today|yesterday|last\s+\w+)\b",
        re.IGNORECASE,
    ),
    "top_n": re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE),
    "bottom_n": re.compile(r"\bbottom\s+(\d+)\b", re.IGNORECASE),
    "limit_n": re.compile(r"\b(?:first|show)\s+(\d+)\b", re.IGNORECASE),
    "range": re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)\b"),
}


class KeyWordExtractor:

    """
    Extracts important keywords from processed token lists,
    mapping them to column names and domain concepts.
    """

    def __init__(self):
        self._build_reverse_alias_map()
        logger.info("KeywordExtractor initialized.")

    
    def _build_reverse_alias_map(self):
        """Build alias → column mapping for fast lookup."""
        self._alias_to_column = {}

        for alias, col in COLUMN_ALIASES.items():
            self._alias_to_column[alias.lower()] = col

        for col in ALL_COLUMNS:
            self._alias_to_column[col.lower()] = col


    def extract_column_keywords(self, tokens: List[str], text: str) -> Dict[str, List[str]]:
        
        """
        Identify which columns are referenced in the query.

        Args:
            tokens: Preprocessed tokens
            text: Full cleaned text (for multi-word matching)

        Returns:
            Dict mapping found columns to their trigger phrases
        """

        found_columns: Dict[str, List[str]] = {}
        text_lower = text.lower()

        # Check multi-word aliases first (e.g., "sender country")
        for alias in sorted(self._alias_to_column.keys(), key=len, reverse=True):
            if alias in text_lower:
                col = self._alias_to_column[alias]

                if col not in found_columns:
                    found_columns[col] = []
                found_columns[col].append(alias)

        # Then check individual tokens
        for token in tokens:
            if token in self._alias_to_column:
                col = self._alias_to_column[token]

                if col not in found_columns:
                    found_columns[col] = [token]

        logger.debug(f"Extracted column keywords: {list(found_columns.keys())}")
        return found_columns
    

    def extract_filter_values(self, text: str) -> List[Dict]:
        
        """
        Extract filter conditions from text (e.g., country=SG, kyc=Verified).

        Args:
            text: Cleaned input text

        Returns:
            List of filter dicts: {column, operator, value}
        """

        filters = []
        text_lower = text.lower()

        # Check each column's valid values
        for column, valid_values in VALID_FILTER_VALUES.items():
            for value in valid_values:
                # Also check synonyms
                synonyms = SYNONYM_DICTIONARY.get(value.lower(), [value.lower()])

                for syn in synonyms:
                    if syn.lower() in text_lower:
                        filters.append({
                            "column": column,
                            "operator": "==",
                            "value": value,
                            "matched_text": syn,
                        })
                        break

        logger.debug(f"Extracted filters: {filters}")
        return filters


    def extract_numeric_conditions(self, text: str) -> List[Dict]:
        
        """
        Extract numeric conditions like 'amount > 500', 'age < 30'.

        Args:
            text: Cleaned input text

        Returns:
            List of condition dicts: {column, operator, value}
        """

        conditions = []
        text_lower = text.lower()

        # Map column mentions to numeric columns
        column_in_text = None

        for col in NUMERIC_COLUMNS:
            aliases = [k for k, v in COLUMN_ALIASES.items() if v == col]

            for alias in [col] + aliases:
                if alias in text_lower:
                    column_in_text = col
                    break

            if column_in_text:
                break

        if not column_in_text:
            column_in_text = "amount"  # Default

        # Find comparison operators and values
        op_match = PATTERNS["comparison_op"].search(text)
        amounts = PATTERNS["amount_value"].findall(text)

        if amounts:
            value = float(amounts[0].replace("$", ""))
            operator = op_match.group(1) if op_match else ">"
            conditions.append({
                "column": column_in_text,
                "operator": operator,
                "value": value,
            })

        # Range detection: "between 100 and 500"
        range_match = PATTERNS["range"].search(text)
        if range_match and "between" in text_lower:
            conditions.append({
                "column": column_in_text,
                "operator": "between",
                "value": (float(range_match.group(1)), float(range_match.group(2))),
            })

        logger.debug(f"Extracted numeric conditions: {conditions}")
        return conditions
    

    def extract_keywords(self, tokens: List[str], text: str) -> Dict:

        """
        Full keyword extraction pipeline.

        Args:
            tokens: Preprocessed token list
            text: Full cleaned text

        Returns:
            Dictionary with all extracted keyword categories
        """

        result = {
            "columns": self.extract_column_keywords(tokens, text),
            "filters": self.extract_filter_values(text),
            "numeric_conditions": self.extract_numeric_conditions(text),
            "entities": {},
        }
        return result



class NERModule:
    """
    Named Entity Recognition for transaction domain.
    Identifies specific entities: account IDs, transaction IDs, amounts, countries, etc.
    """

    def __init__(self):
        logger.info("NERModule initialized.")

    def extract(self, text: str) -> Dict:
        """
        Extract all named entities from text.

        Args:
            text: Raw or cleaned input text

        Returns:
            Dictionary mapping entity types to extracted values
        """
        entities = {}

        # Account IDs
        accounts = PATTERNS["account_id"].findall(text)
        if accounts:
            entities["account_ids"] = [a.upper() for a in accounts]

        # Transaction IDs
        txns = PATTERNS["transaction_id"].findall(text)
        if txns:
            entities["transaction_ids"] = [t.upper() for t in txns]

        # Device IDs
        devices = PATTERNS["device_id"].findall(text)
        if devices:
            entities["device_ids"] = [d.upper() for d in devices]

        # Amount values
        amounts = PATTERNS["amount_value"].findall(text)
        if amounts:
            entities["amounts"] = [float(a.replace("$", "")) for a in amounts if a.replace("$","").replace(".","").isdigit() or self._is_float(a.replace("$",""))]

        # Country codes
        countries = PATTERNS["country_code"].findall(text)
        if countries:
            entities["countries"] = [c.upper() for c in countries]

        # Top N
        top_n = PATTERNS["top_n"].search(text)
        if top_n:
            entities["top_n"] = int(top_n.group(1))

        # Bottom N
        bottom_n = PATTERNS["bottom_n"].search(text)
        if bottom_n:
            entities["bottom_n"] = int(bottom_n.group(1))

        # Limit N
        limit_n = PATTERNS["limit_n"].search(text)
        if limit_n:
            entities["limit"] = int(limit_n.group(1))

        # Date patterns
        dates = PATTERNS["date_pattern"].findall(text)
        if dates:
            entities["dates"] = dates

        # Percentages
        percentages = PATTERNS["percentage"].findall(text)
        if percentages:
            entities["percentages"] = [float(p.replace("%", "")) for p in percentages]

        logger.debug(f"NER extracted entities: {entities}")
        return entities
    

    def _is_float(self, s: str) -> bool:
        try:
            float(s)
            return True
        except ValueError:
            return False
