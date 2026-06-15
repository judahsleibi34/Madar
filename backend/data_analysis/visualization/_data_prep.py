from ._deps import math, pd, re, warnings


class DataPreparationMixin:
    def _comparison_frame(
        self,
        x_columns: list[str],
        y_columns: list[str],
        hue: str | None,
    ) -> tuple[pd.DataFrame, str, str, str | None]:
        if len(x_columns) == 1 and len(y_columns) <= 1:
            return self.df, x_columns[0], y_columns[0], hue

        if len(x_columns) == 1 and len(y_columns) > 1:
            melted = self.df.melt(
                id_vars=[x_columns[0]],
                value_vars=y_columns,
                var_name="Series",
                value_name="Value",
            )
            return melted, x_columns[0], "Value", "Series"

        if len(x_columns) == len(y_columns) and y_columns:
            frames = []
            for x_column, y_column in zip(x_columns, y_columns):
                frame = self.df[[x_column, y_column]].copy()
                frame = frame.rename(columns={x_column: "X", y_column: "Value"})
                frame["Series"] = f"{y_column} by {x_column}"
                frames.append(frame)

            return pd.concat(frames, ignore_index=True), "X", "Value", "Series"

        raise ValueError(
            "Multi-axis comparisons require one X with many Y values, or matching X/Y list lengths"
        )

    def _bar_relation_frame(
        self,
        data: pd.DataFrame,
        plot_x: str,
        plot_y: str,
        plot_hue: str | None,
    ) -> tuple[pd.DataFrame, str, str, str | None, bool]:
        if (
            plot_x in data.columns
            and plot_y in data.columns
            and not pd.api.types.is_numeric_dtype(data[plot_y])
        ):
            work = data[[plot_x, plot_y]].dropna().copy()
            work[plot_x] = work[plot_x].astype(str)
            work[plot_y] = work[plot_y].astype(str)
            counted = (
                work.groupby([plot_x, plot_y], dropna=False)
                .size()
                .reset_index(name="Count")
            )
            return counted, plot_x, "Count", plot_y, True

        return data, plot_x, plot_y, plot_hue, False

    def _prepare_line_frame(
        self,
        data: pd.DataFrame,
        plot_x: str,
        plot_y: str,
    ) -> tuple[pd.DataFrame, str, str]:
        if plot_y not in data.columns:
            raise ValueError("Line chart needs a numeric Y column.")

        work = data.copy()
        numeric_y = pd.to_numeric(work[plot_y], errors="coerce")

        if numeric_y.notna().sum() < 2:
            raise ValueError("Line chart needs at least two numeric Y values.")

        work[plot_y] = numeric_y

        if plot_x in work.columns and not pd.api.types.is_numeric_dtype(work[plot_x]):
            parsed_x = self._maybe_parse_datetime_x(work[plot_x], plot_x)
            if parsed_x.notna().sum() >= 2:
                work[plot_x] = parsed_x

        work = work.dropna(subset=[plot_x, plot_y])
        if len(work) < 2:
            raise ValueError("Line chart needs at least two complete X/Y rows.")

        if work[plot_x].duplicated().any():
            work = (
                work.groupby(plot_x, sort=False, as_index=False)[plot_y]
                .mean()
                .dropna(subset=[plot_x, plot_y])
            )

        if pd.api.types.is_numeric_dtype(work[plot_x]) or pd.api.types.is_datetime64_any_dtype(work[plot_x]):
            work = work.sort_values(plot_x)

        if len(work) < 2:
            raise ValueError("Line chart needs at least two X values after grouping duplicate X labels.")

        return work, plot_x, plot_y

    def _prepare_scatter_frame(
        self,
        data: pd.DataFrame,
        plot_x: str,
        plot_y: str,
    ) -> tuple[pd.DataFrame, str, str, dict[str, dict[str, list]]]:
        work = data.copy()
        category_axes: dict[str, dict[str, list]] = {}

        for axis_name, column in [("x", plot_x), ("y", plot_y)]:
            if column not in work.columns:
                continue

            if self._is_identifier_like_column(column, work[column]) or self._scatter_axis_contains_identifier_series(work, column):
                labels = work[column].map(lambda value: "" if pd.isna(value) else str(value))
                codes, uniques = pd.factorize(labels, sort=False)
                if len(uniques) < 2:
                    continue

                category_column = f"{column}__scatter_category_{axis_name}"
                work[category_column] = codes.astype(float)
                category_axes[axis_name] = {
                    "positions": list(range(len(uniques))),
                    "labels": [str(value) for value in uniques],
                }

                if axis_name == "x":
                    plot_x = category_column
                else:
                    plot_y = category_column
                continue

            numeric_values = pd.to_numeric(work[column], errors="coerce")
            if numeric_values.notna().sum() < 2:
                continue

            numeric_column = f"{column}__scatter_numeric_{axis_name}"
            work[numeric_column] = numeric_values

            if axis_name == "x":
                plot_x = numeric_column
            else:
                plot_y = numeric_column

        work = work.dropna(subset=[plot_x, plot_y])
        if work.empty:
            raise ValueError("Scatter chart needs at least one complete X/Y pair.")

        return work, plot_x, plot_y, category_axes

    def _is_identifier_like_column(self, column_name: str, values: pd.Series) -> bool:
        lowered_name = str(column_name).lower()
        identifier_tokens = [
            "phone",
            "mobile",
            "tel",
            "whatsapp",
            "contact",
            "id",
            "رقم",
            "هاتف",
            "الهاتف",
            "جوال",
        ]

        if any(token in lowered_name for token in identifier_tokens):
            return True

        return self._has_identifier_like_values(values, minimum_ratio=0.7)

    def _scatter_axis_contains_identifier_series(self, data: pd.DataFrame, value_column: str) -> bool:
        if "Series" not in data.columns or value_column not in data.columns:
            return False

        for series_name, series_frame in data.groupby("Series", sort=False):
            if self._is_identifier_like_column(str(series_name), series_frame[value_column]):
                return True
            if self._has_identifier_like_values(series_frame[value_column], minimum_ratio=0.5):
                return True

        return False

    def _has_identifier_like_values(self, values: pd.Series, minimum_ratio: float = 0.7) -> bool:
        text_values = values.dropna().astype(str).str.strip()
        if text_values.empty:
            return False

        sample = text_values.head(50)
        digit_lengths = sample.map(lambda value: len(re.sub(r"\D", "", value)))
        has_identifier_shape = sample.str.match(r"^\+?[\d\s().-]{7,}$").mean() >= minimum_ratio

        return bool(has_identifier_shape and digit_lengths.median() >= 7)

    def _apply_scatter_category_axes(
        self,
        axis,
        category_axes: dict[str, dict[str, list]],
        language: str,
    ) -> None:
        for axis_name, metadata in category_axes.items():
            positions = list(metadata.get("positions", []))
            labels = list(metadata.get("labels", []))

            if not positions or not labels:
                continue

            max_ticks = 16
            if len(positions) > max_ticks:
                step = max(1, math.ceil(len(positions) / max_ticks))
                selected_indexes = list(range(0, len(positions), step))
                if selected_indexes[-1] != len(positions) - 1:
                    selected_indexes.append(len(positions) - 1)
            else:
                selected_indexes = list(range(len(positions)))

            shown_positions = [positions[index] for index in selected_indexes]
            shown_labels = [self._shape_text(labels[index], language) for index in selected_indexes]

            if axis_name == "x":
                axis.set_xticks(shown_positions)
                axis.set_xticklabels(shown_labels)
            else:
                axis.set_yticks(shown_positions)
                axis.set_yticklabels(shown_labels)

    def _maybe_parse_datetime_x(self, values: pd.Series, column_name: str) -> pd.Series:
        lowered_name = str(column_name).lower()

        if not any(token in lowered_name for token in ["date", "time", "timestamp"]):
            return pd.Series(pd.NaT, index=values.index)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                return pd.to_datetime(values, errors="coerce", format="mixed")
        except TypeError:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                return pd.to_datetime(values, errors="coerce")