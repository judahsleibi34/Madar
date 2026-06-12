import pandas as pd
import seaborn as sns
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch
import os
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
            plot_color = self._resolve_color(color, plot_hue)
            plot_palette = self._resolve_palette(palette, data, plot_hue, series_count, plot_color)
            is_horizontal = str(orientation).lower() == "horizontal"
            axis = sns.barplot(
                data=data,
                x=plot_y if is_horizontal else plot_x,
                y=plot_x if is_horizontal else plot_y,
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

        elif chart_type == "line":
            self._require_columns(x_columns, "X axis")
            self._require_columns(y_columns, "Y axis")
            self._validate_columns([*x_columns, *y_columns, hue])
            data, plot_x, plot_y, plot_hue = self._comparison_frame(x_columns, y_columns, hue)
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

        elif chart_type == "scatter":
            self._require_columns(x_columns, "X axis")
            self._require_columns(y_columns, "Y axis")
            self._validate_columns([*x_columns, *y_columns, hue])
            data, plot_x, plot_y, plot_hue = self._comparison_frame(x_columns, y_columns, hue)
            plot_color = self._resolve_color(color, plot_hue)
            plot_palette = self._resolve_palette(palette, data, plot_hue, series_count, plot_color)
            scatter_hue = plot_y if gradient and not plot_hue else plot_hue
            scatter_palette = palette if gradient and not plot_hue else plot_palette
            axis = sns.scatterplot(
                data=data,
                x=plot_x,
                y=plot_y,
                hue=scatter_hue,
                palette=scatter_palette,
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

        elif chart_type == "box":
            self._require_exactly_one(x_columns, "Box X axis")
            self._require_exactly_one(y_columns, "Box Y axis")
            plot_x = x_columns[0] if x_columns else None
            plot_y = y_columns[0] if y_columns else None
            self._validate_columns([plot_x, plot_y, hue])
            plot_color = self._resolve_color(color, hue)
            plot_palette = self._resolve_palette(palette, self.df, hue, series_count, plot_color)
            sns.boxplot(
                data=self.df,
                x=plot_x,
                y=plot_y,
                hue=hue,
                palette=plot_palette,
                color=plot_color or (None if hue else self._first_palette_color(palette)),
                width=0.62,
                linewidth=1.3,
                fliersize=4,
            )

        elif chart_type == "violin":
            self._require_exactly_one(x_columns, "Violin X axis")
            self._require_exactly_one(y_columns, "Violin Y axis")
            plot_x = x_columns[0] if x_columns else None
            plot_y = y_columns[0] if y_columns else None
            self._validate_columns([plot_x, plot_y, hue])
            plot_color = self._resolve_color(color, hue)
            plot_palette = self._resolve_palette(palette, self.df, hue, series_count, plot_color)
            sns.violinplot(
                data=self.df,
                x=plot_x,
                y=plot_y,
                hue=hue,
                palette=plot_palette,
                color=plot_color or (None if hue else self._first_palette_color(palette)),
                inner="quartile",
                linewidth=1.2,
                cut=0,
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
            if not hue and plot_palette:
                self._apply_bar_palette(axis, plot_palette, horizontal=False)

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
            )

        elif chart_type == "heatmap":
            self._plot_heatmap(
                palette=palette
            )

        else:
            raise ValueError(f"Unsupported chart type: {chart_type}")

        self._style_plot(
            title=title,
            x_label=x_label or self._axis_label(x_columns),
            y_label=y_label or self._axis_label(y_columns),
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

        values = [patch.get_height() for patch in patches]
        low = min(values)
        high = max(values)
        span = high - low or 1
        cmap = self._palette_cmap(palette, color)

        for patch, value in zip(patches, values):
            patch.set_facecolor(cmap((value - low) / span))
            patch.set_edgecolor("white")
            patch.set_linewidth(1)
            patch.set_alpha(0.86)

        for line in axis.lines:
            line.set_color(cmap(0.85))
            line.set_linewidth(2.6)

    def _apply_bar_gradient(
        self,
        axis,
        palette: str | list[str] | None,
        color: str | None,
        horizontal: bool = False,
    ) -> None:
        patches = [patch for patch in axis.patches if patch.get_width() or patch.get_height()]
        if not patches:
            return

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

        tick_labels = axis.get_yticklabels() if horizontal else axis.get_xticklabels()
        labels = [label.get_text() for label in tick_labels if label.get_text()]
        if 1 < len(labels) <= 12 and len(labels) == len(colors):
            handles = [
                Patch(facecolor=color, edgecolor="none", label=label)
                for label, color in zip(labels, colors)
            ]
            axis.legend(
                handles=handles,
                title="",
                loc="upper left",
                bbox_to_anchor=(1.01, 1),
                borderaxespad=0,
                frameon=True,
            )

    def _apply_line_gradient_fill(self, axis) -> None:
        for line in axis.lines:
            x_data = line.get_xdata()
            y_data = line.get_ydata()
            if len(x_data) < 2 or len(y_data) < 2:
                continue

            try:
                baseline = min(y_data)
                color = line.get_color()
                axis.fill_between(x_data, y_data, baseline, color=color, alpha=0.16)
                axis.plot(x_data, y_data, color=color, linewidth=2.8)
            except Exception:
                continue

    def _plot_pie(
        self,
        label_column: str,
        value_column: str,
        palette: str | list[str],
        language: str = "en",
    ) -> None:
        grouped = (
            self.df.groupby(label_column)[value_column]
            .sum()
            .sort_values(ascending=False)
        )

        colors = (
            self._resize_palette([str(color) for color in palette if color], len(grouped))
            if isinstance(palette, list)
            else sns.color_palette(palette or "viridis", len(grouped))
        )

        total = grouped.sum()
        explode = [0.018] * len(grouped)
        wedges, _, autotexts = plt.pie(
            grouped.values,
            labels=None,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            pctdistance=0.72,
            explode=explode,
            wedgeprops={"edgecolor": "white", "linewidth": 1.2}
        )

        for text in autotexts:
            text.set_fontweight("bold")
            text.set_color("#1f2933")

        labels = [
            f"{self._shape_text(label, language)} ({value / total:.1%})"
            for label, value in grouped.items()
        ]
        plt.legend(
            wedges,
            labels,
            loc="center left",
            bbox_to_anchor=(1.02, 0.5),
            frameon=True,
        )
        plt.axis("equal")

    def _plot_heatmap(
        self,
        palette: str | list[str]
    ) -> None:
        numeric_df = self.df.select_dtypes(include="number")

        if numeric_df.empty:
            raise ValueError("Heatmap requires numeric columns")

        correlation = numeric_df.corr()

        sns.heatmap(
            correlation,
            annot=True,
            cmap=palette if isinstance(palette, str) else "viridis",
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
        if legend:
            legend.set_title("")
            legend.get_frame().set_alpha(0.95)
            legend.get_frame().set_edgecolor("#d7dce5")
            legend.get_frame().set_linewidth(0.8)
            for text in legend.get_texts():
                text.set_text(self._shape_text(text.get_text(), language))
                text.set_fontsize(legend_font_size)
                if font_family:
                    text.set_fontfamily(font_family)

        plt.tight_layout(rect=[0, 0, 0.88, 1] if legend else None)

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
