from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from data_analysis.core.analysis_i18n import (
    direction_for,
    has_arabic,
    normalize_language,
    normalize_symbols,
    report_title,
    translate,
)


@dataclass
class ReportBuilder:
    report_id: str
    domain: str
    title: str
    rows_used: int
    columns_used: list[str]
    summary: str = ""
    insights: list[str] = field(default_factory=list)
    kpis: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    charts: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    mappings: dict[str, Any] = field(default_factory=dict)
    language: str = "en"
    symbols: dict[str, str] = field(default_factory=normalize_symbols)

    def add_kpi(self, label: str, value: Any, unit: str | None = None) -> None:
        self.kpis.append({
            "label": translate(label, self.language),
            "value": json_safe(value),
            "unit": self._localized_unit(unit),
            "display_value": self._display_value(value, unit),
        })

    def add_table(self, title: str, rows: list[dict[str, Any]]) -> None:
        self.tables.append({"title": translate(title, self.language), "rows": json_safe(rows)})

    def add_chart(
        self,
        title: str,
        chart_type: str,
        data: list[dict[str, Any]],
        x: str | None = None,
        y: str | None = None,
    ) -> None:
        self.charts.append({
            "title": translate(title, self.language),
            "type": chart_type,
            "x": x,
            "y": y,
            "data": json_safe(data),
        })

    def set_summary(self, english: str, arabic: str | None = None) -> None:
        self.summary = arabic if self.language == "ar" and arabic else english

    def add_insight(self, english: str, arabic: str | None = None) -> None:
        self.insights.append(arabic if self.language == "ar" and arabic else english)

    def _localized_unit(self, unit: str | None) -> str | None:
        if unit == "%":
            return self.symbols.get("percent", "%")
        return unit

    def _display_value(self, value: Any, unit: str | None = None) -> str:
        safe_value = json_safe(value)
        if safe_value is None:
            return "-"
        if isinstance(safe_value, (int, float)):
            display = f"{safe_value:,.2f}" if isinstance(safe_value, float) and not safe_value.is_integer() else f"{safe_value:,}"
            display = display.replace(",", "TMP").replace(".", self.symbols.get("decimal_separator", ".")).replace("TMP", self.symbols.get("thousands_separator", ","))
        else:
            display = str(safe_value)
        localized_unit = self._localized_unit(unit)
        return f"{display}{localized_unit}" if localized_unit else display

    def to_dict(self) -> dict[str, Any]:
        summary = self.summary
        if self.language == "ar" and (not summary or not has_arabic(summary)):
            summary = f"طھظ… ط¥ظ†ط´ط§ط، طھظ‚ط±ظٹط± {self.title} ط¨ط§ط³طھط®ط¯ط§ظ… {self.rows_used:,} طµظپظˆظپ."
        insights = self.insights
        if self.language == "ar" and not any(has_arabic(item) for item in insights):
            insights = ["طھطھظˆظپط± ط§ظ„ظ†طھط§ط¦ط¬ ط§ظ„طھظپطµظٹظ„ظٹط© ظپظٹ ط§ظ„ظ…ط¤ط´ط±ط§طھ ظˆط§ظ„ط¬ط¯ط§ظˆظ„ ظˆط§ظ„ط±ط³ظˆظ… ط§ظ„ظ…ط±ظپظ‚ط©."] + insights

        return {
            "report_id": self.report_id,
            "domain": self.domain,
            "title": self.title,
            "summary": summary,
            "insights": insights,
            "kpis": self.kpis,
            "tables": self.tables,
            "charts": self.charts,
            "warnings": self.warnings,
            "metadata": {
                "rows_used": self.rows_used,
                "columns_used": self.columns_used,
                "mappings_used": self.mappings,
                "language": self.language,
                "direction": direction_for(self.language),
                "symbols": self.symbols,
            },
        }


class AnalysisBase:
    domain = "analysis"

    def __init__(self, df: pd.DataFrame, language: str = "en", symbols: dict[str, Any] | None = None) -> None:
        if df.empty:
            raise ValueError("DataFrame is empty")
        self.df = df.copy()
        self.language = normalize_language(language)
        self.symbols = normalize_symbols(symbols)
        self._numeric_cache: dict[str, pd.Series] = {}
        self._date_cache: dict[str, pd.Series] = {}
        self._group_cache: dict[tuple, pd.DataFrame] = {}
        self._value_counts_cache: dict[tuple, pd.DataFrame] = {}
        self._timeseries_cache: dict[tuple, tuple[pd.DataFrame, list[str]]] = {}
        self._column_profile_cache: dict[str, dict[str, dict[str, Any]]] = {}

    def report(self, report_id: str, title: str, mappings: dict[str, Any] | None = None) -> ReportBuilder:
        clean_mappings = {
            key: value
            for key, value in (mappings or {}).items()
            if key not in {"self", "report", "work", "result", "df"}
        }
        return ReportBuilder(
            report_id=report_id,
            domain=self.domain,
            title=report_title(report_id, title, self.language),
            rows_used=int(len(self.df)),
            columns_used=[str(column) for column in self.df.columns],
            mappings=clean_mappings,
            language=self.language,
            symbols=self.symbols,
        )

    def validate_columns(self, columns: list[str | None]) -> None:
        missing = [column for column in columns if column and column not in self.df.columns]
        if missing:
            raise ValueError(f"Columns not found: {missing}")

    def numeric(self, column: str) -> pd.Series:
        self.validate_columns([column])
        if column in self._numeric_cache:
            return self._numeric_cache[column].copy(deep=True)

        raw = self.df[column]
        if raw.dtype == "object" or str(raw.dtype).startswith("string"):
            cleaned = (
                raw.astype("string")
                .str.replace(",", "", regex=False)
                .str.replace(r"[$â‚¬آ£â‚ھ%]", "", regex=True)
                .str.strip()
            )
            values = pd.to_numeric(cleaned, errors="coerce")
        else:
            values = pd.to_numeric(raw, errors="coerce")
        if values.notna().sum() == 0:
            raise TypeError(f"Column '{column}' must contain numeric values")
        self._numeric_cache[column] = values.copy(deep=True)
        return values.copy(deep=True)

    def date(self, column: str) -> pd.Series:
        self.validate_columns([column])
        if column in self._date_cache:
            return self._date_cache[column].copy(deep=True)

        values = pd.to_datetime(self.df[column], errors="coerce")
        if values.notna().sum() == 0:
            raise TypeError(f"Column '{column}' must contain date values")
        self._date_cache[column] = values.copy(deep=True)
        return values.copy(deep=True)

    def safe_divide(self, numerator: float, denominator: float, warning: str | None = None, report: ReportBuilder | None = None) -> float | None:
        if denominator == 0 or pd.isna(denominator):
            if warning and report:
                report.warnings.append(warning)
            return None
        return float(numerator / denominator)

    def pct(self, numerator: float, denominator: float, warning: str | None = None, report: ReportBuilder | None = None) -> float | None:
        value = self.safe_divide(numerator, denominator, warning, report)
        return round(value * 100, 2) if value is not None else None

    def group_numeric(
        self,
        group_columns: str | list[str],
        numeric_columns: list[str],
        aggregations: list[str] | None = None,
    ) -> pd.DataFrame:
        group_list = [group_columns] if isinstance(group_columns, str) else group_columns
        self.validate_columns(group_list + numeric_columns)
        aggregations = aggregations or ["count", "sum", "mean", "median", "min", "max"]
        cache_key = (tuple(group_list), tuple(numeric_columns), tuple(aggregations))
        if cache_key in self._group_cache:
            return self._group_cache[cache_key].copy(deep=True)

        work = self.df[group_list].copy()
        for column in numeric_columns:
            work[column] = self.numeric(column)
        grouped = work.groupby(group_list, dropna=False)[numeric_columns].agg(aggregations)
        grouped.columns = ["_".join(col).strip() for col in grouped.columns.values]
        result = grouped.reset_index()
        self._group_cache[cache_key] = result.copy(deep=True)
        return result.copy(deep=True)

    def value_counts(self, column: str, limit: int | None = None) -> pd.DataFrame:
        self.validate_columns([column])
        cache_key = (column, limit)
        if cache_key in self._value_counts_cache:
            return self._value_counts_cache[cache_key].copy(deep=True)

        result = self.df[column].fillna("Missing").value_counts(dropna=False).reset_index()
        result.columns = [column, "count"]
        if limit:
            result = result.head(limit)
        total = result["count"].sum()
        result["percentage"] = result["count"].map(lambda value: round(float(value / total * 100), 2) if total else None)
        self._value_counts_cache[cache_key] = result.copy(deep=True)
        return result.copy(deep=True)

    def timeseries_sum(self, date_column: str, value_columns: list[str], bucket: str) -> tuple[pd.DataFrame, list[str]]:
        self.validate_columns([date_column] + value_columns)
        cache_key = (date_column, tuple(value_columns), bucket)
        if cache_key in self._timeseries_cache:
            cached_df, cached_warnings = self._timeseries_cache[cache_key]
            return cached_df.copy(deep=True), list(cached_warnings)

        warnings = []
        work = pd.DataFrame({"period_date": self.date(date_column)})
        invalid_dates = int(work["period_date"].isna().sum())
        if invalid_dates:
            warnings.append(f"{invalid_dates} rows had invalid dates and were excluded.")
        for column in value_columns:
            work[column] = self.numeric(column)
        work = work.dropna(subset=["period_date"])
        if bucket == "daily":
            work["period"] = work["period_date"].dt.date.astype(str)
        else:
            work["period"] = work["period_date"].dt.to_period("M").astype(str)
        result = work.groupby("period", dropna=False)[value_columns].sum().reset_index()
        self._timeseries_cache[cache_key] = (result.copy(deep=True), list(warnings))
        return result.copy(deep=True), list(warnings)

    def column_profile(self) -> dict[str, dict[str, Any]]:
        cache_key = "default"
        if cache_key in self._column_profile_cache:
            return {column: values.copy() for column, values in self._column_profile_cache[cache_key].items()}

        profiles = {}
        for column in self.df.columns:
            series = self.df[column]
            if series.dtype == "object" or str(series.dtype).startswith("string"):
                numeric_source = (
                    series.astype("string")
                    .str.replace(",", "", regex=False)
                    .str.replace(r"[$â‚¬آ£â‚ھ%]", "", regex=True)
                    .str.strip()
                )
            else:
                numeric_source = series
            numeric = pd.to_numeric(numeric_source, errors="coerce")
            dates = pd.to_datetime(series, errors="coerce")
            non_null = max(int(series.notna().sum()), 1)
            if numeric.notna().sum() / non_null >= 0.8:
                inferred = "number"
            elif dates.notna().sum() / non_null >= 0.8:
                inferred = "date"
            elif series.dropna().astype(str).str.contains(r",|;|\|").mean() > 0.25:
                inferred = "multi_choice"
            elif series.nunique(dropna=True) <= max(20, len(series) * 0.2):
                inferred = "category"
            else:
                inferred = "text"
            profiles[str(column)] = {
                "type": inferred,
                "missing": int(series.isna().sum()),
                "unique": int(series.nunique(dropna=True)),
                "sample": series.dropna().head(5).tolist(),
            }
        self._column_profile_cache[cache_key] = {column: values.copy() for column, values in profiles.items()}
        return {column: values.copy() for column, values in profiles.items()}


def json_safe(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return json_safe(value.to_dict(orient="records"))
    if isinstance(value, pd.Series):
        return json_safe(value.tolist())
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return json_safe(value.item())
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
