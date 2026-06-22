from ._deps import Literal, Path, os, pd, plt, pyg, sns

from ._validation import ValidationMixin
from ._formatting import FormattingMixin
from ._palette import PaletteMixin
from ._data_prep import DataPreparationMixin
from ._effects import EffectsMixin
from ._legends import LegendsMixin
from ._plot_helpers import PlotHelpersMixin
from ._stats import StatsMixin


class DataVisualization(
    ValidationMixin,
    FormattingMixin,
    PaletteMixin,
    DataPreparationMixin,
    StatsMixin,
    LegendsMixin,
    EffectsMixin,
    PlotHelpersMixin,
):
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
            single_repeated_palette = (
                isinstance(plot_palette, list)
                and len({str(item).lower() for item in plot_palette if item}) <= 1
                and not plot_hue
                and not plot_color
            )
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
            elif not plot_hue and not plot_color:
                self._apply_bar_palette(
                    axis,
                    palette if single_repeated_palette else plot_palette or palette,
                    horizontal=is_horizontal,
                )
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
                # data=histogram_data,
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
            single_repeated_palette = (
                isinstance(plot_palette, list)
                and len({str(item).lower() for item in plot_palette if item}) <= 1
                and not hue
                and not plot_color
            )
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
            elif not hue and not plot_color:
                self._apply_bar_palette(
                    axis,
                    palette if single_repeated_palette else plot_palette or palette,
                    horizontal=False,
                )
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
