from ._deps import FuncFormatter, arabic_reshaper, get_display, pd


class FormattingMixin:
    def _normalize_columns(self, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        return [str(value)] if value else []

    def _axis_label(self, columns: list[str]) -> str | None:
        if not columns:
            return None
        if len(columns) == 1:
            return columns[0]
        return " / ".join(columns)

    def _has_arabic(self, value: str | None) -> bool:
        return any("\u0600" <= char <= "\u06ff" for char in str(value or ""))

    def _shape_text(self, value: str | None, language: str = "en") -> str | None:
        if value is None:
            return None

        text = str(value)
        if language != "ar" and not self._has_arabic(text):
            return text

        if arabic_reshaper is None or get_display is None:
            return text

        return get_display(arabic_reshaper.reshape(text))

    def _format_compact_tick(self, value: float, _position: int | None = None) -> str:
        abs_value = abs(value)
        if abs_value >= 1_000_000_000_000:
            return f"{value / 1_000_000_000_000:.2f}T"
        if abs_value >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if abs_value >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        if abs_value >= 1_000:
            return f"{value / 1_000:.1f}K"
        return f"{value:g}"

    def _format_line_axis_numbers(self, axis, values: pd.Series, axis_name: str = "y") -> None:
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty:
            return

        max_abs = float(numeric_values.abs().max())
        if max_abs >= 1_000_000:
            target_axis = axis.xaxis if axis_name == "x" else axis.yaxis
            target_axis.set_major_formatter(FuncFormatter(self._format_compact_tick))
            target_axis.offsetText.set_visible(False)

    def _format_summary_value(self, value: float) -> str:
        if abs(value) >= 100:
            return f"{value:,.1f}"
        if abs(value) >= 10:
            return f"{value:,.2f}"
        return f"{value:,.3f}"