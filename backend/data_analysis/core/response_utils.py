import math
from datetime import date, datetime
from typing import Any

import pandas as pd


def sanitize_for_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): sanitize_for_json(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(item) for item in value]

    if value is None:
        return None

    if isinstance(value, float):
        return value if math.isfinite(value) else None

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        return sanitize_for_json(value.item())

    return value


def dataframe_preview(df: pd.DataFrame, rows: int = 10) -> list[dict[str, Any]]:
    return sanitize_for_json(df.head(rows).to_dict(orient="records"))
