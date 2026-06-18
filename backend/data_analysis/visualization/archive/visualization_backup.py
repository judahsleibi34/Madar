import pandas as pd
import seaborn as sns
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, to_hex, to_rgb
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
import colorsys
import math
import os
import re
import warnings
from pathlib import Path
from typing import Literal

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:
    arabic_reshaper = None
    get_display = None

try:
    import pygwalker as pyg
except Exception:
    pyg = None


class DataVisualization:
    def __init__(self, df: pd.DataFrame) -> None:
        if df.empty:
            raise ValueError("DataFrame is empty")

        self.df = df.copy()

    def plot(
        self,
        chart_type: Literal[
            "bar",
            "line",
            "scatter",
            "histogram",
            "box",
            "violin",
            "count",
            "pie",
            "heatmap"
        ],
        x: str | list[str] | None = None,
        y: str | list[str] | None = None,
        hue: str | None = None,
        title: str | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        palette: str | list[str] = "viridis",
        color: str | None = None,
        font_family: str | None = None,
        title_font_size: int = 18,
        label_font_size: int = 12,
        tick_font_size: int = 10,
        legend_font_size: int = 10,
        series_count: int | None = None,
        features: list[str] | None = None,
        language: str = "en",
        orientation: str = "vertical",
        style: str = "whitegrid",
        figsize: tuple[int, int] = (10, 6),
        marker: str = "o",
        rotation: int = 45,
        gradient: bool = False,
        save_path: str | None = None,
        show: bool = False
    ) -> str | None:
        sns.set_theme(
            style=style,
            rc={
                "axes.facecolor": "#ffffff",
                "figure.facecolor": "#ffffff",
                "axes.edgecolor": "#d9dee8",
                "grid.color": "#e6eaf0",
                "grid.linewidth": 0.9,
            },
        )

        plt.figure(figsize=figsize)
        plot_already_styled = False
        x_columns = self._normalize_columns(x)
        y_columns = self._normalize_columns(y)
        hue = hue or None

        if chart_type == "bar":
            self._require_columns(x_columns, "X axis")
            self._require_columns(y_columns, "Y axis")
            self._validate_columns([*x_columns, *y_columns, hue])
            data, plot_x, plot_y, plot_hue = self._comparison_frame(x_columns, y_columns, hue)
            data, plot_x, plot_y, plot_hue, counted_relation = self._bar_relation_frame(
                data,
                plot_x,
                plot_y,
                plot_hue,
            )
            data = data.copy()
            bar_category_column = f"{plot_x}__bar_category"
            data[bar_category_column] = data[plot_x].map(
                lambda value: "" if pd.isna(value) else str(value)
            )
            plot_color = self._resolve_color(color, plot_hue)
            plot_palette = self._resolve_palette(palette, data, plot_hue, series_count, plot_color)
            is_horizontal = str(orientation).lower() == "horizontal"
            axis = sns.barplot(
                data=data,
                x=plot_y if is_horizontal else bar_category_column,
                y=bar_category_column if is_horizontal else plot_y,
                hue=plot_hue,
                palette=plot_palette if plot_hue else None,
                color=plot_color or (None if plot_hue else self._first_palette_color(palette)),
                errorbar=None,
                saturation=0.92,
                width=0.78,
            )
            if gradient and not plot_hue:
                self._apply_bar_gradient(
                    axis=axis,
                    palette=palette,
                    color=plot_color,
                    horizontal=is_horizontal,
                )
            elif not plot_hue and plot_palette:
                self._apply_bar_palette(axis, plot_palette, horizontal=is_horizontal)
            if counted_relation:
                if is_horizontal:
                    x_label = x_label or "Count"
                    y_label = y_label or self._axis_label(x_columns)
                else:
                    y_label = y_label or "Count"
            elif is_horizontal:
                x_label = x_label or self._axis_label(y_columns)
                y_label = y_label or self._axis_label(x_columns)
            if not plot_hue:
                self._add_bar_category_legend(
                    axis=axis,
                    categories=data[plot_x],
                    horizontal=is_horizontal,
                    legend_font_size=legend_font_size,
                    language=language,
                )

        elif chart_type == "line":
            self._require_columns(x_columns, "X axis")
            self._require_columns(y_columns, "Y axis")
            self._validate_columns([*x_columns, *y_columns, hue])
            if len(x_columns) == 1 and len(y_columns) > 1 and not hue:
                self._plot_multi_line_axes(
                    x_column=x_columns[0],
                    y_columns=y_columns,
                    palette=palette,
                    color=color,
                    title=title,
                    x_label=x_label,
                    font_family=font_family,
                    title_font_size=title_font_size,
                    label_font_size=label_font_size,
                    tick_font_size=tick_font_size,
                    legend_font_size=legend_font_size,
                    language=language,
                    marker=marker,
                    rotation=rotation,
                    gradient=gradient,
                    figsize=figsize,
                )
                plot_already_styled = True
            else:
                data, plot_x, plot_y, plot_hue = self._comparison_frame(x_columns, y_columns, hue)
                data, plot_x, plot_y = self._prepare_line_frame(data, plot_x, plot_y)
                plot_color = self._resolve_color(color, plot_hue)
                plot_palette = self._resolve_palette(palette, data, plot_hue, series_count, plot_color)
                axis = sns.lineplot(
                    data=data,
                    x=plot_x,
                    y=plot_y,
                    hue=plot_hue,
                    marker=marker,
                    palette=plot_palette,
                    color=plot_color or (None if plot_hue else self._first_palette_color(palette)),
                    errorbar=None,
                    linewidth=2.6,
                )
                if gradient:
                    self._apply_line_gradient_fill(axis)
                self._ensure_line_legend(
                    axis=axis,
                    y_columns=y_columns,
                    has_hue=bool(plot_hue),
                    language=language,
                    legend_font_size=legend_font_size,
                )

        elif chart_type == "scatter":
            self._require_columns(x_columns, "X axis")
            self._require_columns(y_columns, "Y axis")
            self._validate_columns([*x_columns, *y_columns, hue])
            data, plot_x, plot_y, plot_hue = self._comparison_frame(x_columns, y_columns, hue)
            data, plot_x, plot_y, scatter_category_axes = self._prepare_scatter_frame(data, plot_x, plot_y)
            plot_color = self._resolve_color(color, plot_hue)
            plot_palette = self._resolve_palette(palette, data, plot_hue, series_count, plot_color)
            scatter_hue = plot_y if gradient and not plot_hue and "y" not in scatter_category_axes else plot_hue
            scatter_palette = palette if gradient and not plot_hue else plot_palette
            axis = sns.scatterplot(
                data=data,
                x=plot_x,
                y=plot_y,
                hue=scatter_hue,
                palette=scatter_palette if scatter_hue else None,
                color=plot_color or (None if scatter_hue else self._first_palette_color(palette)),
                s=86,
                alpha=0.86,
                edgecolor="white",
                linewidth=0.7,
            )
            if gradient and not plot_hue:
                legend = axis.get_legend()
                if legend:
                    legend.remove()
            if plot_hue:
                self._add_scatter_category_legend(
                    axis=axis,
                    data=data,
                    category_column=plot_hue,
                    legend_font_size=legend_font_size,
                    language=language,
                )
            elif gradient and "y" not in scatter_category_axes:
                self._add_scatter_category_legend(
                    axis=axis,
                    data=data,
                    category_column=plot_y,
                    legend_font_size=legend_font_size,
                    language=language,
                )
            self._apply_scatter_category_axes(axis, scatter_category_axes, language)
            if "x" not in scatter_category_axes:
                self._format_line_axis_numbers(axis, data[plot_x], "x")
            if "y" not in scatter_category_axes:
                self._format_line_axis_numbers(axis, data[plot_y], "y")

        elif chart_type == "histogram":
            self._require_exactly_one(x_columns, "Histogram X axis")
            plot_x = x_columns[0] if x_columns else None
            self._validate_columns([plot_x, hue])
            histogram_data = self.df
            histogram_x = plot_x
            if plot_x and not pd.api.types.is_numeric_dtype(histogram_data[plot_x]):
                numeric_values = pd.to_numeric(histogram_data[plot_x], errors="coerce")
                if numeric_values.notna().sum() < 2:
                    raise ValueError("Histogram requires a numeric column")
                histogram_data = histogram_data.copy()
                histogram_x = f"{plot_x}__numeric"
                histogram_data[histogram_x] = numeric_values
            plot_color = self._resolve_color(color, hue)
            plot_palette = self._resolve_palette(palette, histogram_data, hue, series_count, plot_color)
            axis = sns.histplot(
                data=histogram_data,
                x=histogram_x,
                hue=hue,
                kde=True,
                palette=plot_palette if hue else None,
                color=plot_color or (None if hue else self._first_palette_color(palette)),
                edgecolor="white",
                linewidth=1,
                alpha=0.78,
            )
            if gradient and not hue:
                self._apply_histogram_gradient(axis, palette, plot_color)
            self._style_histogram(axis)
            self._add_histogram_summary_lines(
                axis=axis,
                values=histogram_data[histogram_x],
                color=plot_color,
                palette=palette,
                language=language,
                legend_font_size=legend_font_size,
            )

        elif chart_type == "box":
            self._require_exactly_one(x_columns, "Box X axis")
            self._require_columns(y_columns, "Box Y axis")
            plot_x = x_columns[0] if x_columns else None
            is_horizontal = str(orientation).lower() == "horizontal"
            if plot_x in y_columns:
                raise ValueError("Box chart needs different X and Y columns. Remove the X axis column from Y variables.")
            self._validate_columns([plot_x, *y_columns, hue])
            box_width = 0.62

            if len(y_columns) > 1:
                if hue:
                    raise ValueError("Box 1:M comparisons cannot also use group color. Remove grouping or use one Y variable.")

                box_data = self.df[[plot_x, *y_columns]].melt(
                    id_vars=[plot_x],
                    value_vars=y_columns,
                    var_name="Series",
                    value_name="Value",
                )
                box_data["Value"] = pd.to_numeric(box_data["Value"], errors="coerce")
                box_data = box_data.dropna(subset=[plot_x, "Value"])
                if box_data.empty:
                    raise ValueError("Box chart needs numeric values in at least one selected Y variable.")

                has_useful_x_groups = self._box_grouping_is_useful(
                    box_data,
                    plot_x,
                    "Series",
                )
                if has_useful_x_groups:
                    box_x = plot_x
                    box_hue = "Series"
                else:
                    if self._box_series_scales_need_panels(box_data, "Series", "Value"):
                        self._plot_multi_box_panels(
                            box_data=box_data,
                            series_column="Series",
                            value_column="Value",
                            palette=palette,
                            color=color,
                            title=title,
                            x_label=x_label,
                            y_label=y_label,
                            font_family=font_family,
                            title_font_size=title_font_size,
                            label_font_size=label_font_size,
                            tick_font_size=tick_font_size,
                            legend_font_size=legend_font_size,
                            orientation=orientation,
                            language=language,
                            gradient=gradient,
                        )
                        plot_already_styled = True
                        box_x = None
                        plot_hue = None
                    else:
                        box_x = "Series"
                        box_hue = None
                        if not x_label:
                            x_label = "Variables"

                if not plot_already_styled:
                    plot_hue = box_hue

                plot_y = "Value"
                box_series_count = len(y_columns)
                if not y_label:
                    y_label = "Value"
            else:
                plot_y = y_columns[0] if y_columns else None
                box_columns = [plot_x, plot_y, hue] if hue else [plot_x, plot_y]
                box_data = self.df[box_columns].copy()
                box_data[plot_y] = pd.to_numeric(box_data[plot_y], errors="coerce")
                box_data = box_data.dropna(subset=[plot_x, plot_y])
                if box_data.empty:
                    raise ValueError("Box chart needs numeric values in the selected Y variable.")
                if self._box_grouping_is_useful(box_data, plot_x):
                    box_x = plot_x
                    box_hue = hue
                else:
                    box_data = box_data.rename(columns={plot_y: "Value"})
                    box_data["Series"] = plot_y
                    self._plot_single_box_distribution(
                        values=box_data["Value"],
                        label=plot_y,
                        palette=palette,
                        color=color,
                        title=title,
                        x_label=x_label or "Variables",
                        y_label=y_label or y_columns[0],
                        font_family=font_family,
                        title_font_size=title_font_size,
                        label_font_size=label_font_size,
                        tick_font_size=tick_font_size,
                        legend_font_size=legend_font_size,
                        orientation=orientation,
                        language=language,
                        gradient=gradient,
                    )
                    plot_already_styled = True
                    box_x = None
                    box_hue = None
                    plot_hue = None
                plot_hue = box_hue
                box_series_count = (
                    int(box_data[box_x].dropna().nunique())
                    if box_x and box_x in box_data.columns
                    else series_count
                )

            if not plot_already_styled:
                plot_color = self._resolve_color(color, plot_hue)
                plot_palette = self._resolve_palette(palette, box_data, plot_hue, box_series_count, plot_color)
                box_group_palette = (
                    plot_palette
                    if plot_hue or (box_x and box_x in box_data.columns)
                    else None
                )
                box_plot_hue = plot_hue or (box_x if box_group_palette and box_x in box_data.columns else None)
                axis = sns.boxplot(
                    data=box_data,
                    x=plot_y if is_horizontal else box_x,
                    y=box_x if is_horizontal else plot_y,
                    hue=box_plot_hue,
                    palette=box_group_palette,
                    color=plot_color or (None if box_group_palette else self._first_palette_color(palette)),
                    width=box_width,
                    linewidth=1.3,
                    fliersize=4,
                    legend=False,
                )
                if gradient:
                    self._apply_box_gradient(axis, palette, plot_color)
                summary_series_column = (
                    plot_hue
                    if plot_hue
                    else box_x
                    if box_x and box_x in box_data.columns
                    else "Series"
                    if "Series" in box_data.columns
                    else None
                )
                self._add_box_summary_legend(
                    axis=axis,
                    data=box_data,
                    value_column=plot_y,
                    series_column=summary_series_column,
                    default_label=self._axis_label(y_columns),
                    color=plot_color,
                    palette=plot_palette or palette,
                    value_axis="x" if is_horizontal else "y",
                    legend_font_size=legend_font_size,
                    language=language,
                )
                self._format_line_axis_numbers(
                    axis,
                    box_data[plot_y],
                    "x" if is_horizontal else "y",
                )
                if is_horizontal:
                    x_label = x_label or self._axis_label(y_columns)
                    y_label = y_label or (box_x if box_x else self._axis_label(x_columns))

        elif chart_type == "violin":
            self._require_exactly_one(x_columns, "Violin X axis")
            self._require_exactly_one(y_columns, "Violin Y axis")
            plot_x = x_columns[0] if x_columns else None
            plot_y = y_columns[0] if y_columns else None
            is_horizontal = str(orientation).lower() == "horizontal"
            self._validate_columns([plot_x, plot_y, hue])
            plot_color = self._resolve_color(color, hue)
            plot_palette = self._resolve_palette(palette, self.df, hue, series_count, plot_color)
            axis = sns.violinplot(
                data=self.df,
                x=plot_y if is_horizontal else plot_x,
                y=plot_x if is_horizontal else plot_y,
                hue=hue,
                palette=plot_palette,
                color=plot_color or (None if hue else self._first_palette_color(palette)),
                inner="quartile",
                linewidth=1.2,
                cut=0,
            )
            if gradient:
                self._apply_violin_gradient(axis, palette, plot_color)
            if is_horizontal:
                x_label = x_label or self._axis_label(y_columns)
                y_label = y_label or self._axis_label(x_columns)
            self._format_line_axis_numbers(
                axis,
                self.df[plot_y],
                "x" if is_horizontal else "y",
            )
            self._add_box_summary_legend(
                axis=axis,
                data=self.df,
                value_column=plot_y,
                series_column=hue if hue else plot_x,
                default_label=plot_y,
                value_axis="x" if is_horizontal else "y",
                color=plot_color,
                palette=palette,
                legend_font_size=legend_font_size,
                language=language,
            )

        elif chart_type == "count":
            self._require_exactly_one(x_columns, "Count X axis")
            plot_x = x_columns[0] if x_columns else None
            self._validate_columns([plot_x, hue])
            plot_color = self._resolve_color(color, hue)
            plot_palette = self._resolve_palette(palette, self.df, hue, series_count, plot_color)
            axis = sns.countplot(
                data=self.df,
                x=plot_x,
                hue=hue,
                palette=plot_palette if hue else None,
                color=plot_color or (None if hue else self._first_palette_color(palette)),
                saturation=0.92,
                width=0.78,
            )
            if gradient:
                self._apply_bar_gradient(
                    axis=axis,
                    palette=palette,
                    color=plot_color,
                    horizontal=False,
                    by_position=True,
                )
            elif not hue and plot_palette:
                self._apply_bar_palette(axis, plot_palette, horizontal=False)
            group_items = []
            if hue:
                handles, labels = axis.get_legend_handles_labels()
                for handle, label in zip(handles, labels):
                    facecolor = None
                    if hasattr(handle, "get_facecolor"):
                        raw_color = handle.get_facecolor()
                        if isinstance(raw_color, (list, tuple)) and len(raw_color) and hasattr(raw_color[0], "__iter__"):
                            raw_color = raw_color[0]
                        facecolor = to_hex(raw_color)
                    group_items.append((label, facecolor or "#6b7280"))
                existing_legend = axis.get_legend()
                if existing_legend:
                    existing_legend.remove()
            if not y_label:
                y_label = "Number of records"
            self._add_count_frequency_legend(
                axis=axis,
                has_grouping=bool(hue),
                group_items=group_items,
                category_items=[] if hue else self._bar_patch_legend_items(axis),
                legend_font_size=legend_font_size,
                language=language,
            )

        elif chart_type == "pie":
            self._require_exactly_one(x_columns, "Pie label column")
            self._require_exactly_one(y_columns, "Pie value column")
            plot_x = x_columns[0] if x_columns else None
            plot_y = y_columns[0] if y_columns else None
            self._validate_columns([plot_x, plot_y])
            self._plot_pie(
                label_column=plot_x,
                value_column=plot_y,
                palette=palette,
                language=language,
                gradient=gradient,
                color=color,
            )

        elif chart_type == "heatmap":
            self._plot_heatmap(
                features=features,
                palette=palette,
                color=color if gradient else None,
            )

        else:
            raise ValueError(f"Unsupported chart type: {chart_type}")

        if not plot_already_styled:
            axis_labels_disabled = chart_type in {"pie", "heatmap"}
            self._style_plot(
                title=title,
                x_label="" if axis_labels_disabled else x_label or self._axis_label(x_columns),
                y_label="" if axis_labels_disabled else y_label or self._axis_label(y_columns),
                rotation=rotation,
                font_family=font_family,
                title_font_size=title_font_size,
                label_font_size=label_font_size,
                tick_font_size=tick_font_size,
                legend_font_size=legend_font_size,
                language=language,
            )

        if save_path:
            output_path = self._save_plot(save_path)
        else:
            output_path = None

        if show:
            plt.show()

        plt.close()

        return output_path

    def explorer(self, save_path: str | None = None) -> str | None:
        if pyg is None:
            raise RuntimeError(
                "PyGWalker is not installed in the backend environment."
            )

        output_root = Path(os.getenv("CHART_OUTPUT_DIR", "generated_charts")).resolve()
        requested = Path(save_path or f"pygwalker-{pd.Timestamp.utcnow().timestamp():.0f}.html")
        path = (output_root / requested.name).resolve()

        if path.suffix.lower() != ".html":
            path = path.with_suffix(".html")

        path.parent.mkdir(parents=True, exist_ok=True)
        html = pyg.to_html(self.df)
        path.write_text(html, encoding="utf-8")
        return str(path)

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

        raise ValueError("Multi-axis comparisons require one X with many Y values, or matching X/Y list lengths")

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

    def _box_grouping_is_useful(
        self,
        data: pd.DataFrame,
        x_column: str,
        series_column: str | None = None,
    ) -> bool:
        if x_column not in data.columns:
            return False

        unique_count = int(data[x_column].dropna().nunique())
        if unique_count < 2 or unique_count > 18:
            return False

        group_columns = [x_column]
        if series_column and series_column in data.columns:
            group_columns.append(series_column)

        group_sizes = data.groupby(group_columns, dropna=False).size()
        if group_sizes.empty:
            return False

        return bool((group_sizes >= 2).mean() >= 0.6)

    def _box_series_scales_need_panels(
        self,
        data: pd.DataFrame,
        series_column: str,
        value_column: str,
    ) -> bool:
        ranges = []
        for _series_name, group in data.groupby(series_column, dropna=False):
            values = pd.to_numeric(group[value_column], errors="coerce").dropna()
            if values.empty:
                continue
            low = float(values.quantile(0.25))
            high = float(values.quantile(0.75))
            spread = max(abs(high - low), abs(float(values.median())), 1.0)
            ranges.append(spread)

        if len(ranges) < 2:
            return False

        return max(ranges) / max(min(ranges), 1.0) >= 25

    def _box_summary_stats(self, values: pd.Series) -> dict[str, float | int] | None:
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty:
            return None

        q1 = float(numeric_values.quantile(0.25))
        q3 = float(numeric_values.quantile(0.75))
        iqr = q3 - q1
        lower_fence = q1 - 1.5 * iqr
        upper_fence = q3 + 1.5 * iqr
        outlier_count = int(((numeric_values < lower_fence) | (numeric_values > upper_fence)).sum())
        return {
            "count": int(numeric_values.count()),
            "mean": float(numeric_values.mean()),
            "q1": q1,
            "median": float(numeric_values.median()),
            "q3": q3,
            "iqr": iqr,
            "min": float(numeric_values.min()),
            "max": float(numeric_values.max()),
            "outliers": outlier_count,
        }

    def _box_summary_color(
        self,
        index: int,
        color: str | None,
        palette: str | list[str] | None,
    ) -> str:
        if color:
            return color

        if isinstance(palette, list) and palette:
            return str(palette[index % len(palette)])

        try:
            return sns.color_palette(palette or "viridis", n_colors=index + 1).as_hex()[index]
        except Exception:
            return self._first_palette_color(palette)

    def _legend_font_size(self, legend_font_size: int | None = None) -> int:
        return max(8, min(int(legend_font_size or 10), 11))

    def _apply_legend_design(
        self,
        legend,
        legend_font_size: int | None = None,
        font_family: str | None = None,
        language: str = "en",
    ) -> None:
        if not legend:
            return

        legend.set_title("")
        legend.set_frame_on(True)
        frame = legend.get_frame()
        frame.set_facecolor("#ffffff")
        frame.set_edgecolor("#d7dce5")
        frame.set_linewidth(1)
        frame.set_alpha(0.96)
        try:
            frame.set_boxstyle("round,pad=0.35,rounding_size=0.12")
        except Exception:
            pass

        for text in legend.get_texts():
            text.set_text(self._shape_text(text.get_text(), language))
            text.set_color("#30343b")
            text.set_fontsize(self._legend_font_size(legend_font_size))
            if font_family:
                text.set_fontfamily(font_family)

    def _legend_pairs(self, axis) -> list[tuple[object, str]]:
        handles, labels = axis.get_legend_handles_labels()
        pairs = []
        for handle, label in zip(handles, labels):
            if label and not str(label).startswith("_"):
                pairs.append((handle, str(label)))
        return pairs

    def _set_chart_legend(
        self,
        axis,
        handles: list,
        labels: list[str],
        legend_font_size: int | None = None,
        language: str = "en",
        loc: str = "upper left",
        bbox_to_anchor: tuple[float, float] | None = (1.01, 1),
        **kwargs,
    ):
        if not handles or not labels:
            return None

        legend = axis.legend(
            handles=handles,
            labels=[self._shape_text(label, language) for label in labels],
            title="",
            loc=loc,
            bbox_to_anchor=bbox_to_anchor,
            borderaxespad=0,
            frameon=True,
            fontsize=self._legend_font_size(legend_font_size),
            handlelength=2.1,
            handletextpad=0.8,
            labelspacing=0.65,
            **kwargs,
        )
        self._apply_legend_design(legend, legend_font_size, language=language)
        return legend

    def _set_fixed_figure_legend(
        self,
        axis,
        handles: list,
        labels: list[str],
        legend_font_size: int | None = None,
        language: str = "en",
        loc: str = "upper left",
        bbox_to_anchor: tuple[float, float] = (0.76, 0.82),
        **kwargs,
    ):
        if not handles or not labels:
            return None

        legend = axis.figure.legend(
            handles=handles,
            labels=[self._shape_text(label, language) for label in labels],
            title="",
            loc=loc,
            bbox_to_anchor=bbox_to_anchor,
            bbox_transform=axis.figure.transFigure,
            borderaxespad=0,
            frameon=True,
            fontsize=self._legend_font_size(legend_font_size),
            handlelength=2.1,
            handletextpad=0.8,
            labelspacing=0.65,
            **kwargs,
        )
        legend.set_zorder(30)
        self._apply_legend_design(legend, legend_font_size, language=language)
        return legend

    def _numeric_summary_values(self, values: pd.Series) -> tuple[float, float] | None:
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty:
            return None
        return float(numeric_values.mean()), float(numeric_values.median())

    def _stat_summary_labels(self, stats: dict[str, float | int], prefix: str = "") -> list[str]:
        return [
            f"{prefix}Min: {self._format_summary_value(float(stats['min']))}",
            f"{prefix}Q1: {self._format_summary_value(float(stats['q1']))}",
            f"{prefix}Median: {self._format_summary_value(float(stats['median']))}",
            f"{prefix}Mean: {self._format_summary_value(float(stats['mean']))}",
            f"{prefix}Q3: {self._format_summary_value(float(stats['q3']))}",
            f"{prefix}Max: {self._format_summary_value(float(stats['max']))}",
        ]

    def _transparent_legend_handles(self, count: int) -> list[Line2D]:
        return [
            Line2D(
                [0],
                [0],
                marker="s",
                color="none",
                markerfacecolor=(1, 1, 1, 0),
                markeredgecolor=(1, 1, 1, 0),
                markersize=7,
            )
            for _index in range(count)
        ]

    def _stat_summary_handles(self, color: str, count: int) -> list[Line2D]:
        return [
            Line2D(
                [0],
                [0],
                marker="s",
                color="none",
                markerfacecolor=color,
                markeredgecolor="white",
                markersize=7,
            )
            for _index in range(count)
        ]

    def _add_numeric_summary_legend(
        self,
        axis,
        values: pd.Series,
        value_axis: str,
        color: str | None,
        palette: str | list[str] | None,
        language: str,
        legend_font_size: int | None = None,
        include_existing: bool = False,
    ) -> None:
        stats = self._box_summary_stats(values)
        if not stats:
            return

        existing_pairs = self._legend_pairs(axis) if include_existing else []
        existing_handles = [handle for handle, _label in existing_pairs]
        existing_labels = [label for _handle, label in existing_pairs]
        summary_color = color or self._first_palette_color(palette)
        summary_labels = self._stat_summary_labels(stats)
        summary_handles = self._stat_summary_handles(summary_color, len(summary_labels))

        axis._madar_fixed_legend_lane = "stats"

        self._set_fixed_figure_legend(
            axis,
            [*existing_handles, *summary_handles],
            [*existing_labels, *summary_labels],
            legend_font_size=legend_font_size,
            language=language,
            bbox_to_anchor=(0.88, 0.82),
            ncol=1,
        )

    def _add_box_summary_legend(
        self,
        axis,
        data: pd.DataFrame,
        value_column: str,
        series_column: str | None,
        default_label: str,
        color: str | None,
        palette: str | list[str] | None,
        value_axis: str,
        legend_font_size: int,
        language: str,
    ) -> None:
        if value_column not in data.columns:
            return

        if series_column and series_column in data.columns:
            grouped_series = [
                (str(series_name), group[value_column])
                for series_name, group in data.groupby(series_column, dropna=False, sort=False)
            ]
        else:
            grouped_series = [(default_label, data[value_column])]

        summaries = []
        for index, (series_name, values) in enumerate(grouped_series):
            stats = self._box_summary_stats(values)
            if not stats:
                continue
            summaries.append((series_name, stats, self._box_summary_color(index, color, palette)))

        if not summaries:
            return

        existing_legend = axis.get_legend()
        if existing_legend:
            existing_legend.remove()

        handles = []
        labels = []
        max_items = 3
        for series_name, stats, summary_color in summaries[:max_items]:
            if len(summaries) > 1:
                labels.append(str(series_name))
                handles.append(Patch(facecolor=summary_color, edgecolor="none"))
                stat_labels = self._stat_summary_labels(stats, "  ")
                labels.extend(stat_labels)
                handles.extend(self._transparent_legend_handles(len(stat_labels)))
                continue

            stat_labels = self._stat_summary_labels(stats)
            labels.extend(stat_labels)
            handles.extend(self._stat_summary_handles(summary_color, len(stat_labels)))

        if len(summaries) > max_items:
            labels.append(f"+ {len(summaries) - max_items} more series")
            handles.append(
                Line2D(
                    [0],
                    [0],
                    marker="s",
                    color="none",
                    markerfacecolor="#6b7280",
                    markeredgecolor="white",
                    markersize=7,
                )
            )

        axis._madar_fixed_legend_lane = "stats"

        self._set_fixed_figure_legend(
            axis,
            handles,
            labels,
            legend_font_size=legend_font_size,
            language=language,
            bbox_to_anchor=(0.88, 0.82),
            ncol=1,
        )

    def _add_violin_quartile_legend(
        self,
        axis,
        values: pd.Series,
        value_axis: str,
        color: str | None,
        palette: str | list[str] | None,
        legend_font_size: int,
        language: str,
    ) -> None:
        existing_legend = axis.get_legend()
        if existing_legend:
            existing_legend.remove()

        self._add_numeric_summary_legend(
            axis=axis,
            values=values,
            value_axis=value_axis,
            color=color,
            palette=palette,
            language=language,
            legend_font_size=legend_font_size,
        )

    def _add_count_frequency_legend(
        self,
        axis,
        has_grouping: bool,
        group_items: list[tuple[str, str]],
        category_items: list[tuple[str, str]],
        legend_font_size: int,
        language: str,
    ) -> None:
        legend_items = group_items if has_grouping else category_items
        if legend_items:
            handles = [
                Patch(facecolor=item_color or "#6b7280", edgecolor="none")
                for _label, item_color in legend_items
            ]
            labels = [str(label) for label, _item_color in legend_items]
        else:
            handles = [
                Patch(facecolor="#7f1d1d", edgecolor="none"),
                Patch(facecolor="#1f4e79", edgecolor="none"),
            ]
            labels = ["Metric: category count", "Height: records"]

        column_count = max(1, math.ceil(len(labels) / 12))

        axis._madar_fixed_legend_lane = "bar"
        self._set_fixed_figure_legend(
            axis,
            handles=handles,
            labels=labels,
            legend_font_size=legend_font_size,
            language=language,
            ncol=column_count,
            columnspacing=1.1,
        )

    def _plot_single_box_distribution(
        self,
        values: pd.Series,
        label: str,
        palette: str | list[str],
        color: str | None,
        title: str | None,
        x_label: str | None,
        y_label: str | None,
        font_family: str | None,
        title_font_size: int,
        label_font_size: int,
        tick_font_size: int,
        legend_font_size: int,
        orientation: str,
        language: str,
        gradient: bool = False,
    ) -> None:
        numeric_values = pd.to_numeric(values, errors="coerce").dropna()
        if numeric_values.empty:
            raise ValueError("Box chart needs numeric values in the selected Y variable.")

        axis = plt.gca()
        font_options = {"fontfamily": font_family} if font_family else {}
        box_color = color or self._first_palette_color(palette)
        if gradient:
            box_color = self._gradient_colors(palette, 1, color)[0]
        is_horizontal = str(orientation).lower() == "horizontal"

        axis.boxplot(
            [numeric_values],
            positions=[1],
            widths=0.14,
            vert=not is_horizontal,
            patch_artist=True,
            labels=[self._shape_text(label, language)],
            boxprops={"facecolor": box_color, "edgecolor": "#303030", "linewidth": 1.3},
            medianprops={"color": "#303030", "linewidth": 1.4},
            whiskerprops={"color": "#303030", "linewidth": 1.2},
            capprops={"color": "#303030", "linewidth": 1.2},
            flierprops={
                "marker": "o",
                "markerfacecolor": "white",
                "markeredgecolor": "#303030",
                "markersize": 4,
                "alpha": 0.9,
            },
        )
        if is_horizontal:
            axis.set_ylim(0.35, 1.65)
        else:
            axis.set_xlim(0.35, 1.65)
        axis.set_xlabel(
            self._shape_text((y_label or label) if is_horizontal else (x_label or "Variables"), language),
            fontsize=label_font_size,
            fontweight="bold",
            color="#111827",
            **font_options,
        )
        axis.set_ylabel(
            self._shape_text((x_label or "Variables") if is_horizontal else (y_label or label), language),
            fontsize=label_font_size,
            fontweight="bold",
            color="#111827",
            **font_options,
        )
        if title:
            axis.set_title(
                self._shape_text(title, language),
                fontsize=title_font_size,
                fontweight="bold",
                color="#111827",
                pad=20,
                **font_options,
            )

        axis.grid(axis="x" if is_horizontal else "y", color="#111827", linewidth=0.65, alpha=0.16)
        axis.tick_params(axis="both", labelsize=tick_font_size, colors="#111827")
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#d7dce5")
        axis.spines["bottom"].set_color("#d7dce5")
        self._format_line_axis_numbers(axis, numeric_values, "x" if is_horizontal else "y")
        self._add_box_summary_legend(
            axis=axis,
            data=pd.DataFrame({"Series": [label] * len(numeric_values), "Value": numeric_values}),
            value_column="Value",
            series_column="Series",
            default_label=label,
            color=box_color,
            palette=palette,
            value_axis="x" if is_horizontal else "y",
            legend_font_size=legend_font_size,
            language=language,
        )
        plt.tight_layout(rect=[0, 0, 0.82, 1])

    def _plot_multi_box_panels(
        self,
        box_data: pd.DataFrame,
        series_column: str,
        value_column: str,
        palette: str | list[str],
        color: str | None,
        title: str | None,
        x_label: str | None,
        y_label: str | None,
        font_family: str | None,
        title_font_size: int,
        label_font_size: int,
        tick_font_size: int,
        legend_font_size: int,
        orientation: str,
        language: str,
        gradient: bool = False,
    ) -> None:
        series_names = list(box_data[series_column].dropna().unique())
        if not series_names:
            raise ValueError("Box chart needs numeric values in at least one selected Y variable.")

        panel_count = len(series_names)
        plt.clf()
        figure, axes = plt.subplots(
            1,
            panel_count,
            figsize=(max(10, 3.6 * panel_count), 6),
            squeeze=False,
        )
        axes = list(axes.flat)
        font_options = {"fontfamily": font_family} if font_family else {}
        is_horizontal = str(orientation).lower() == "horizontal"

        if gradient:
            colors = self._gradient_colors(palette, panel_count, color)
        elif isinstance(palette, list):
            colors = self._resize_palette([str(item) for item in palette if item], panel_count)
        elif color:
            colors = self._resize_palette([color], panel_count)
        else:
            colors = list(sns.color_palette(palette or "viridis", n_colors=panel_count).as_hex())

        for axis, series_name, box_color in zip(axes, series_names, colors):
            values = pd.to_numeric(
                box_data.loc[box_data[series_column] == series_name, value_column],
                errors="coerce",
            ).dropna()
            if values.empty:
                continue

            sns.boxplot(
                x=values if is_horizontal else None,
                y=None if is_horizontal else values,
                ax=axis,
                color=box_color,
                width=0.45,
                linewidth=1.3,
                fliersize=4,
            )
            axis.set_title(
                self._shape_text(str(series_name), language),
                fontsize=label_font_size,
                fontweight="bold",
                color="#111827",
                **font_options,
            )
            axis.set_xlabel(
                self._shape_text((y_label or "Value") if is_horizontal else (x_label or "Distribution"), language),
                fontsize=label_font_size,
                fontweight="bold",
                color="#111827",
                **font_options,
            )
            axis.set_ylabel(
                self._shape_text((x_label or "Distribution") if is_horizontal else (y_label or "Value"), language),
                fontsize=label_font_size,
                fontweight="bold",
                color="#111827",
                **font_options,
            )
            axis.grid(axis="x" if is_horizontal else "y", color="#111827", linewidth=0.65, alpha=0.16)
            axis.tick_params(axis="both", labelsize=tick_font_size, colors="#111827")
            axis.spines["top"].set_visible(False)
            axis.spines["right"].set_visible(False)
            axis.spines["left"].set_color("#d7dce5")
            axis.spines["bottom"].set_color("#d7dce5")
            self._format_line_axis_numbers(axis, values, "x" if is_horizontal else "y")

        self._add_box_summary_legend(
            axis=axes[-1],
            data=box_data,
            value_column=value_column,
            series_column=series_column,
            default_label=value_column,
            color=color,
            palette=colors,
            value_axis="x" if is_horizontal else "y",
            legend_font_size=legend_font_size,
            language=language,
        )

        if title:
            figure.suptitle(
                self._shape_text(title, language),
                fontsize=title_font_size,
                fontweight="bold",
                color="#111827",
                y=0.98,
                **font_options,
            )

        figure.tight_layout(rect=[0, 0, 0.8, 0.92 if title else 1])

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

    def _require_columns(self, columns: list[str], label: str) -> None:
        if not columns:
            raise ValueError(f"{label} requires at least one column")

    def _require_exactly_one(self, columns: list[str], label: str) -> None:
        if len(columns) != 1:
            raise ValueError(f"{label} requires exactly one column")

    def _series_count(
        self,
        data: pd.DataFrame | None,
        hue: str | None,
        fallback: int | None,
    ) -> int:
        if hue and data is not None and hue in data.columns:
            count = int(data[hue].dropna().nunique())
            if count > 0:
                return count

        if fallback:
            return max(1, int(fallback))

        return 1

    def _resize_palette(self, colors: list[str], count: int) -> list[str]:
        if not colors:
            return list(sns.color_palette("viridis", n_colors=count).as_hex())
        if len(colors) == count:
            return colors
        if len(colors) > count:
            return colors[:count]

        return [colors[index % len(colors)] for index in range(count)]

    def _resolve_palette(
        self,
        palette: str | list[str] | None,
        data: pd.DataFrame | None,
        hue: str | None,
        series_count: int | None,
        color: str | None = None,
    ) -> str | list[str] | None:
        if color and not hue:
            return None

        count = self._series_count(data, hue, series_count)

        if isinstance(palette, list):
            colors = [str(color) for color in palette if color]
            return self._resize_palette(colors, count)

        palette_name = palette or "viridis"
        if hue or count > 1:
            return list(sns.color_palette(palette_name, n_colors=count).as_hex())

        return None

    def _resolve_color(self, color: str | None, hue: str | None) -> str | None:
        if hue:
            return None
        return color or None

    def _palette_cmap(
        self,
        palette: str | list[str] | None,
        color: str | None = None,
    ):
        if isinstance(palette, list) and palette:
            return LinearSegmentedColormap.from_list(
                "madar_gradient",
                [str(item) for item in palette if item],
            )

        if color:
            return LinearSegmentedColormap.from_list(
                "madar_single_gradient",
                ["#e8eef8", str(color)],
            )

        try:
            return sns.color_palette(palette or "crest", as_cmap=True)
        except Exception:
            return sns.color_palette("crest", as_cmap=True)

    def _first_palette_color(self, palette: str | list[str] | None) -> str:
        if isinstance(palette, list):
            colors = [str(color) for color in palette if color]
            if colors:
                return colors[0]

        try:
            return sns.color_palette(palette or "viridis", n_colors=1).as_hex()[0]
        except Exception:
            return sns.color_palette("viridis", n_colors=1).as_hex()[0]

    def _gradient_colors(
        self,
        palette: str | list[str] | None,
        count: int,
        color: str | None = None,
    ) -> list:
        safe_count = max(1, int(count or 1))
        cmap = self._palette_cmap(palette, color)
        if safe_count == 1:
            return [cmap(0.62)]
        return [cmap(index / (safe_count - 1)) for index in range(safe_count)]

    def _style_histogram(self, axis) -> None:
        for patch in axis.patches:
            patch.set_edgecolor("white")
            patch.set_linewidth(1)
            patch.set_alpha(0.78)

        for line in axis.lines:
            line.set_linewidth(2.5)
            line.set_alpha(0.95)

    def _apply_histogram_gradient(
        self,
        axis,
        palette: str | list[str] | None,
        color: str | None,
    ) -> None:
        patches = [patch for patch in axis.patches if patch.get_height()]
        if not patches:
            return

        values = [patch.get_x() + patch.get_width() / 2 for patch in patches]
        low = min(values)
        high = max(values)
        span = high - low or 1
        cmap = self._palette_cmap(palette, color)

        for patch, value in zip(patches, values):
            patch.set_facecolor(cmap(1 - ((value - low) / span)))
            patch.set_edgecolor("white")
            patch.set_linewidth(1)
            patch.set_alpha(0.86)

        for line in axis.lines:
            line.set_color(cmap(0.85))
            line.set_linewidth(2.6)

    def _histogram_summary_colors(
        self,
        color: str | None,
        palette: str | list[str] | None,
    ) -> tuple[str, str]:
        base_color = color or self._first_palette_color(palette)

        try:
            red, green, blue = to_rgb(base_color)
            hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)
        except ValueError:
            red, green, blue = to_rgb("#4f46e5")
            hue, saturation, value = colorsys.rgb_to_hsv(red, green, blue)

        mean_hue = (hue + 0.5) % 1
        mean_saturation = min(0.82, max(0.52, saturation + 0.16))
        mean_value = min(0.74, max(0.42, value * 0.82))
        mean_color = to_hex(colorsys.hsv_to_rgb(mean_hue, mean_saturation, mean_value))

        median_hue = (hue + 0.08) % 1
        median_saturation = min(0.72, max(0.38, saturation * 0.86))
        median_value = min(0.88, max(0.48, value * 1.06))
        median_color = to_hex(colorsys.hsv_to_rgb(median_hue, median_saturation, median_value))

        return mean_color, median_color

    def _format_summary_value(self, value: float) -> str:
        if abs(value) >= 100:
            return f"{value:,.1f}"
        if abs(value) >= 10:
            return f"{value:,.2f}"
        return f"{value:,.3f}"

    def _add_histogram_summary_lines(
        self,
        axis,
        values: pd.Series,
        color: str | None,
        palette: str | list[str] | None,
        language: str,
        legend_font_size: int | None = None,
    ) -> None:
        stats = self._box_summary_stats(values)
        if not stats:
            return

        existing_pairs = self._legend_pairs(axis)
        existing_handles = [handle for handle, _label in existing_pairs]
        existing_labels = [label for _handle, label in existing_pairs]
        summary_color = color or self._first_palette_color(palette)
        summary_labels = self._stat_summary_labels(stats)
        summary_handles = self._stat_summary_handles(summary_color, len(summary_labels))

        axis._madar_fixed_legend_lane = "stats"

        self._set_fixed_figure_legend(
            axis,
            [*existing_handles, *summary_handles],
            [*existing_labels, *summary_labels],
            language=language,
            legend_font_size=legend_font_size,
            bbox_to_anchor=(0.88, 0.82),
            ncol=1,
        )

    def _apply_bar_gradient(
        self,
        axis,
        palette: str | list[str] | None,
        color: str | None,
        horizontal: bool = False,
        by_position: bool = False,
    ) -> None:
        patches = [patch for patch in axis.patches if patch.get_width() or patch.get_height()]
        if not patches:
            return

        if by_position:
            values = [
                patch.get_y() + patch.get_height() / 2 if horizontal else patch.get_x() + patch.get_width() / 2
                for patch in patches
            ]
        else:
            values = [
                patch.get_width() if horizontal else patch.get_height()
                for patch in patches
            ]
        low = min(values)
        high = max(values)
        span = high - low or 1
        cmap = self._palette_cmap(palette, color)

        for patch, value in zip(patches, values):
            patch.set_facecolor(cmap((value - low) / span))
            patch.set_edgecolor("none")
            patch.set_alpha(0.96)

    def _apply_box_gradient(
        self,
        axis,
        palette: str | list[str] | None,
        color: str | None,
    ) -> None:
        patches = [patch for patch in axis.patches if hasattr(patch, "set_facecolor")]
        if not patches:
            return

        colors = self._gradient_colors(palette, len(patches), color)
        for patch, item_color in zip(patches, colors):
            patch.set_facecolor(item_color)
            patch.set_alpha(0.9)

    def _apply_violin_gradient(
        self,
        axis,
        palette: str | list[str] | None,
        color: str | None,
    ) -> None:
        bodies = [
            collection
            for collection in axis.collections
            if hasattr(collection, "get_paths") and collection.get_paths()
        ]
        if not bodies:
            return

        colors = self._gradient_colors(palette, len(bodies), color)
        for body, item_color in zip(bodies, colors):
            body.set_facecolor(item_color)
            body.set_alpha(0.82)
            body.set_edgecolor("#30343b")

    def _apply_bar_palette(
        self,
        axis,
        palette: str | list[str],
        horizontal: bool = False,
    ) -> None:
        patches = [patch for patch in axis.patches if patch.get_width() or patch.get_height()]
        if not patches:
            return

        if isinstance(palette, str):
            colors = list(sns.color_palette(palette or "viridis", n_colors=len(patches)).as_hex())
        else:
            colors = self._resize_palette([str(color) for color in palette if color], len(patches))

        for patch, color in zip(patches, colors):
            patch.set_facecolor(color)
            patch.set_edgecolor("none")
            patch.set_alpha(0.96)

    def _add_bar_category_legend(
        self,
        axis,
        categories: pd.Series,
        horizontal: bool,
        legend_font_size: int | None,
        language: str,
    ) -> None:
        labels = [str(value) for value in pd.Series(categories).dropna().drop_duplicates().tolist()]
        patches = list(axis.containers[0].patches) if axis.containers else list(axis.patches)
        patches = [patch for patch in patches if patch.get_width() or patch.get_height()]
        if len(labels) < 2 or not patches:
            return

        shown_labels = labels
        shown_patches = patches[: len(shown_labels)]
        handles = [
            Patch(facecolor=patch.get_facecolor(), edgecolor="none", label=label)
            for label, patch in zip(shown_labels, shown_patches)
        ]
        if not handles:
            return

        axis._madar_fixed_legend_lane = "bar"
        column_count = max(1, math.ceil(len(shown_labels) / 12))
        self._set_fixed_figure_legend(
            axis,
            handles=handles,
            labels=shown_labels,
            legend_font_size=legend_font_size,
            language=language,
            ncol=column_count,
            columnspacing=1.1,
        )

    def _bar_patch_legend_items(self, axis) -> list[tuple[str, str]]:
        labels = [
            label.get_text()
            for label in axis.get_xticklabels()
            if str(label.get_text()).strip()
        ]
        patches = list(axis.containers[0].patches) if axis.containers else list(axis.patches)
        patches = [patch for patch in patches if patch.get_width() or patch.get_height()]

        items = []
        seen = set()
        for label, patch in zip(labels, patches):
            clean_label = str(label).strip()
            if not clean_label or clean_label in seen:
                continue
            seen.add(clean_label)
            items.append((clean_label, to_hex(patch.get_facecolor())))
        return items

    def _add_scatter_category_legend(
        self,
        axis,
        data: pd.DataFrame,
        category_column: str,
        legend_font_size: int | None,
        language: str,
    ) -> None:
        existing_legend = axis.get_legend()
        existing_pairs = self._legend_pairs(axis)
        if existing_legend:
            existing_legend.remove()

        handles = []
        labels = []
        for handle, label in existing_pairs:
            if label and label not in labels:
                handles.append(handle)
                labels.append(label)

        if not handles and category_column in data.columns:
            values = [str(value) for value in data[category_column].dropna().drop_duplicates().tolist()]
            if len(values) > 1:
                colors = sns.color_palette("viridis", n_colors=min(len(values), 30)).as_hex()
                for label, item_color in zip(values[:30], colors):
                    handles.append(
                        Line2D(
                            [0],
                            [0],
                            marker="o",
                            color="none",
                            markerfacecolor=item_color,
                            markeredgecolor="white",
                            markersize=8,
                            label=label,
                        )
                    )
                    labels.append(label)
                if len(values) > 30:
                    handles.append(
                        Line2D(
                            [0],
                            [0],
                            marker="o",
                            color="none",
                            markerfacecolor="#6b7280",
                            markeredgecolor="white",
                            markersize=8,
                            label=f"+ {len(values) - 30} more",
                        )
                    )
                    labels.append(f"+ {len(values) - 30} more")

        if not handles:
            return

        axis._madar_fixed_legend_lane = "scatter"
        column_count = max(1, min(3, math.ceil(len(labels) / 12)))
        self._set_fixed_figure_legend(
            axis,
            handles=handles,
            labels=labels,
            legend_font_size=legend_font_size,
            language=language,
            ncol=column_count,
            columnspacing=1.1,
        )

    def _apply_line_gradient_fill(self, axis) -> None:
        data_lines = [line for line in axis.lines if not line.get_label().startswith("_")]

        if len(data_lines) > 1:
            for line in data_lines:
                line.set_linewidth(2.8)
                line.set_alpha(0.96)
                line.set_zorder(5)
            return

        for line in data_lines:
            x_data = line.get_xdata()
            y_data = line.get_ydata()
            if len(x_data) < 2 or len(y_data) < 2:
                continue

            try:
                baseline = min(y_data)
                color = line.get_color()
                axis.fill_between(
                    x_data,
                    y_data,
                    baseline,
                    color=color,
                    alpha=0.14,
                    zorder=1,
                )
                line.set_linewidth(2.8)
                line.set_zorder(5)
            except Exception:
                continue

    def _ensure_line_legend(
        self,
        axis,
        y_columns: list[str],
        has_hue: bool,
        language: str,
        legend_font_size: int | None = None,
    ) -> None:
        legend = axis.get_legend()
        if legend:
            legend.remove()

        if has_hue:
            handles, labels = axis.get_legend_handles_labels()
            visible_pairs = [
                (handle, label)
                for handle, label in zip(handles, labels)
                if label and not str(label).startswith("_")
            ]
            if visible_pairs:
                handles, labels = zip(*visible_pairs)
                axis._madar_fixed_legend_lane = "line"
                self._set_fixed_figure_legend(
                    axis,
                    list(handles),
                    list(labels),
                    language=language,
                    legend_font_size=legend_font_size,
                )
            return

        label = self._axis_label(y_columns) or "Value"
        data_lines = [
            line
            for line in axis.lines
            if len(line.get_xdata()) >= 2 and len(line.get_ydata()) >= 2
        ]
        if not data_lines:
            return

        data_lines[0].set_label(self._shape_text(label, language))
        axis._madar_fixed_legend_lane = "line"
        self._set_fixed_figure_legend(
            axis,
            handles=[data_lines[0]],
            labels=[self._shape_text(label, language)],
            language=language,
            legend_font_size=legend_font_size,
        )

    def _plot_multi_line_axes(
        self,
        x_column: str,
        y_columns: list[str],
        palette: str | list[str],
        color: str | None,
        title: str | None,
        x_label: str | None,
        font_family: str | None,
        title_font_size: int,
        label_font_size: int,
        tick_font_size: int,
        legend_font_size: int,
        language: str,
        marker: str,
        rotation: int,
        gradient: bool,
        figsize: tuple[int, int],
    ) -> None:
        series_count = len(y_columns)
        if series_count < 2:
            raise ValueError("Compare trends needs at least two Y variables.")

        axis = plt.gca()
        figure = axis.figure
        font_options = {"fontfamily": font_family} if font_family else {}

        if isinstance(palette, list):
            colors = self._resize_palette([str(item) for item in palette if item], series_count)
        elif color:
            colors = self._resize_palette([color], series_count)
        else:
            colors = list(sns.color_palette(palette or "viridis", n_colors=series_count).as_hex())

        lines = []
        labels = []
        secondary_axes = []
        line_styles = ["-", "--", "-.", ":"]

        for index, (y_column, line_color) in enumerate(zip(y_columns, colors)):
            source_columns = [x_column] if y_column == x_column else [x_column, y_column]
            work, plot_x, plot_y = self._prepare_line_frame(
                self.df[source_columns].copy(),
                x_column,
                y_column,
            )
            label = self._shape_text(y_column, language)
            target_axis = axis if index == 0 else axis.twinx()

            if index > 1:
                target_axis.spines["right"].set_position(("axes", 1 + (0.09 * (index - 1))))
            if index > 0:
                secondary_axes.append(target_axis)

            line = target_axis.plot(
                work[plot_x],
                work[plot_y],
                marker=marker,
                color=line_color,
                linestyle=line_styles[index % len(line_styles)],
                linewidth=2.7,
                label=label,
                zorder=6 + index,
            )[0]
            lines.append(line)
            labels.append(label)

            if gradient:
                try:
                    target_axis.fill_between(
                        work[plot_x],
                        work[plot_y],
                        work[plot_y].min(),
                        color=line_color,
                        alpha=0.12,
                        zorder=1,
                    )
                except Exception:
                    pass

            target_axis.set_ylabel(
                label,
                color="#111827",
                fontsize=label_font_size,
                fontweight="bold",
                labelpad=14 if index == 0 else 22 + (8 * (index - 1)),
                **font_options,
            )
            target_axis.tick_params(
                axis="y",
                labelsize=tick_font_size,
                colors="#111827",
                pad=6 if index == 0 else 10,
            )
            target_axis.patch.set_visible(False)
            target_axis.spines["top"].set_visible(False)
            target_axis.spines["right"].set_color("#111827" if index > 0 else "#d7dce5")
            target_axis.spines["left"].set_color("#111827" if index == 0 else "#d7dce5")
            target_axis.margins(x=0.02, y=0.14)
            self._format_line_axis_numbers(target_axis, work[plot_y])

        axis.set_xlabel(
            self._shape_text(x_label or x_column, language),
            color="#111827",
            fontsize=label_font_size,
            fontweight="bold",
            **font_options,
        )
        axis.spines["top"].set_visible(False)
        axis.spines["bottom"].set_color("#111827")
        axis.grid(axis="both", color="#111827", linewidth=0.65, alpha=0.18)
        axis.set_axisbelow(True)
        axis.tick_params(axis="x", colors="#111827", labelsize=tick_font_size)

        for tick_label in axis.get_xticklabels():
            tick_label.set_rotation(rotation)
            tick_label.set_ha("right" if rotation else "center")
            tick_label.set_rotation_mode("anchor")
            tick_label.set_fontsize(tick_font_size)
            tick_label.set_color("#111827")
            if font_family:
                tick_label.set_fontfamily(font_family)

        if title:
            figure.suptitle(
                self._shape_text(title, language),
                fontsize=title_font_size,
                fontweight="bold",
                y=0.985,
                **font_options,
            )

        axis._madar_fixed_legend_lane = "line"
        self._set_fixed_figure_legend(
            axis,
            lines,
            labels,
            ncol=min(len(lines), 4),
            columnspacing=1.4,
            legend_font_size=legend_font_size,
            language=language,
        )

        right_margin = max(0.78, min(0.82, 0.9 - (0.04 * max(0, len(secondary_axes) - 1))))
        top_margin = 0.9 if title else 0.94
        plt.tight_layout(rect=[0.02, 0.02, right_margin, top_margin])

    def _plot_pie(
        self,
        label_column: str,
        value_column: str,
        palette: str | list[str],
        language: str = "en",
        gradient: bool = False,
        color: str | None = None,
    ) -> None:
        grouped = (
            self.df.groupby(label_column)[value_column]
            .sum()
            .sort_values(ascending=False)
        )

        colors = self._gradient_colors(palette, len(grouped), color) if gradient else (
            self._resize_palette([str(color) for color in palette if color], len(grouped))
            if isinstance(palette, list)
            else sns.color_palette(palette or "viridis", len(grouped))
        )

        total = grouped.sum()
        explode = [0.018] * len(grouped)
        wedges, _ = plt.pie(
            grouped.values,
            labels=None,
            startangle=140,
            colors=colors,
            explode=explode,
            wedgeprops={"edgecolor": "white", "linewidth": 1.2}
        )

        labels = [
            f"{self._shape_text(label, language)} ({value / total:.1%})"
            for label, value in grouped.items()
        ]
        legend = plt.legend(
            handles=wedges,
            labels=labels,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            frameon=True,
        )
        self._apply_legend_design(legend, language=language)
        plt.axis("equal")

    def _plot_heatmap(
        self,
        features: list[str] | None,
        palette: str | list[str],
        color: str | None = None,
    ) -> None:
        selected_features = self._normalize_columns(features)
        if selected_features:
            self._validate_columns(selected_features)
            numeric_df = self.df[selected_features].apply(pd.to_numeric, errors="coerce")
            numeric_df = numeric_df.dropna(axis=1, how="all")
        else:
            numeric_df = self.df.select_dtypes(include="number")

        if numeric_df.empty:
            raise ValueError("Heatmap requires numeric columns")

        if len(numeric_df.columns) < 2:
            raise ValueError("Heatmap requires at least two numeric columns")

        correlation = numeric_df.corr()

        sns.heatmap(
            correlation,
            annot=True,
            cmap=self._palette_cmap(palette, color),
            linewidths=0.5,
            fmt=".2f"
        )

    def _style_plot(
        self,
        title: str | None,
        x_label: str | None,
        y_label: str | None,
        rotation: int,
        font_family: str | None,
        title_font_size: int,
        label_font_size: int,
        tick_font_size: int,
        legend_font_size: int,
        language: str,
    ) -> None:
        font_options = {"fontfamily": font_family} if font_family else {}
        axis = plt.gca()

        if title:
            plt.title(
                self._shape_text(title, language),
                fontsize=title_font_size,
                fontweight="bold",
                pad=20,
                **font_options
            )

        if x_label:
            plt.xlabel(
                self._shape_text(x_label, language),
                fontsize=label_font_size,
                fontweight="bold",
                **font_options
            )

        if y_label:
            plt.ylabel(
                self._shape_text(y_label, language),
                fontsize=label_font_size,
                fontweight="bold",
                **font_options
            )

        x_tick_count = len(axis.get_xticklabels())
        next_rotation = rotation
        if x_tick_count > 18:
            next_rotation = 65
            tick_font_size = max(8, tick_font_size - 1)
        elif x_tick_count > 8:
            next_rotation = max(rotation, 40)

        plt.xticks(rotation=next_rotation, fontsize=tick_font_size, **font_options)
        plt.yticks(rotation=0, fontsize=tick_font_size, **font_options)

        axis.set_xticks(
            axis.get_xticks(),
            labels=[self._shape_text(label.get_text(), language) for label in axis.get_xticklabels()],
            rotation=next_rotation,
            fontsize=tick_font_size,
            **font_options
        )
        axis.set_yticks(
            axis.get_yticks(),
            labels=[self._shape_text(label.get_text(), language) for label in axis.get_yticklabels()],
            rotation=0,
            fontsize=tick_font_size,
            **font_options
        )

        for label in axis.get_xticklabels():
            label.set_ha("right" if next_rotation else "center")
            label.set_rotation_mode("anchor")

        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#d7dce5")
        axis.spines["bottom"].set_color("#d7dce5")
        axis.grid(axis="y", color="#e8edf4", linewidth=1)
        axis.set_axisbelow(True)
        axis.margins(x=0.02, y=0.08)

        legend = plt.gca().get_legend()
        has_side_table = bool(getattr(axis, "tables", None)) or bool(
            getattr(axis, "_madar_side_summary", False)
        )
        fixed_legend_lane = getattr(axis, "_madar_fixed_legend_lane", "")
        legend_right_edge = 0.88
        if legend:
            legend_right_edge = 0.78 if len(legend.get_texts()) > 4 else 0.88
            self._apply_legend_design(
                legend,
                legend_font_size=legend_font_size,
                font_family=font_family,
                language=language,
            )

        if has_side_table:
            axis.set_position([0.12, 0.16, 0.58, 0.68])
        elif fixed_legend_lane == "bar":
            plt.tight_layout(rect=[0, 0, 0.72, 1])
        elif fixed_legend_lane == "stats":
            plt.tight_layout(rect=[0, 0, 0.74, 1])
        elif fixed_legend_lane in {"line", "scatter"}:
            plt.tight_layout(rect=[0, 0, 0.82, 1])
        else:
            plt.tight_layout(rect=[0, 0, legend_right_edge, 1] if legend else None)

    def _save_plot(self, save_path: str) -> str:
        output_root = Path(os.getenv("CHART_OUTPUT_DIR", "generated_charts")).resolve()
        requested = Path(save_path)
        path = (output_root / requested.name).resolve()

        if path.suffix.lower() not in [".png", ".jpg", ".jpeg", ".svg", ".pdf"]:
            raise ValueError("save_path must end with .png, .jpg, .jpeg, .svg, or .pdf")

        path.parent.mkdir(parents=True, exist_ok=True)

        plt.savefig(
            path,
            dpi=300,
            bbox_inches="tight",
            facecolor="white"
        )

        return str(path)

    def _validate_columns(self, columns: list[str | None]) -> None:
        missing_columns = [
            column
            for column in columns
            if column is not None and column not in self.df.columns
        ]

        if missing_columns:
            raise ValueError(f"Columns not found: {missing_columns}")
