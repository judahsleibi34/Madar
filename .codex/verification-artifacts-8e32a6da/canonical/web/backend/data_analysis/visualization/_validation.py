class ValidationMixin:
    def _require_columns(self, columns: list[str], label: str) -> None:
        if not columns:
            raise ValueError(f"{label} requires at least one column")

    def _require_exactly_one(self, columns: list[str], label: str) -> None:
        if len(columns) != 1:
            raise ValueError(f"{label} requires exactly one column")

    def _validate_columns(self, columns: list[str | None]) -> None:
        missing_columns = [
            column
            for column in columns
            if column is not None and column not in self.df.columns
        ]

        if missing_columns:
            raise ValueError(f"Columns not found: {missing_columns}")
