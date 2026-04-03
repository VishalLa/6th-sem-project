import re
import datetime 

import numpy as np
import pandas as pd
from datetime import datetime, date
from typing import Any

def validate_date_format(date_string: str) -> str:
    """Custom type validator for YYYY-MM-DD format."""
    if date_string is None:
        return 

    return datetime.strptime(date_string, '%Y-%m-%d').date()


def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert NumPy and Pandas types to Python native types.
    Safe for JSON serialization.
    
    Args:
        obj: Object to convert
        
    Returns:
        Converted object with Python native types
    """
    # None
    if obj is None:
        return None
    
    # NumPy types
    if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [convert_numpy_types(item) for item in obj.tolist()]
    
    # Pandas types
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient='records')
    if isinstance(obj, pd.Series):
        return obj.tolist()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    
    # Check for pandas NA (scalar values only)
    try:
        if isinstance(obj, (int, float, str, bool)) and pd.isna(obj):
            return None
    except (ValueError, TypeError):
        pass  # Not a scalar pandas value
    
    # DateTime
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    
    # Collections
    if isinstance(obj, dict):
        return {
            convert_numpy_types(key): convert_numpy_types(value) 
            for key, value in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [convert_numpy_types(item) for item in obj]
    if isinstance(obj, set):
        return [convert_numpy_types(item) for item in obj]
    
    # Default
    return obj


def to_json_serializable(obj: Any) -> Any:
    """
    Alternative simpler approach using JSON encoder.
    """
    class NumpyEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, pd.DataFrame):
                return obj.to_dict(orient='records')
            if isinstance(obj, pd.Series):
                return obj.tolist()
            if isinstance(obj, (datetime, date, pd.Timestamp)):
                return obj.isoformat()
            if isinstance(obj, set):
                return list(obj)
            return super().default(obj)
    
    # Convert via JSON encoding/decoding
    return json.loads(json.dumps(obj, cls=NumpyEncoder))

