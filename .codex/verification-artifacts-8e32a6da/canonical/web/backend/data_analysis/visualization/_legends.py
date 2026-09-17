from ._deps import Line2D, Patch, math, pd, sns, to_hex


class LegendsMixin:
    def _legend_font_size(self, legend_font_size: int | None = None) -> int:
        return max(8, min(int(legend_font_size or 10), 11))

    def _legend_column_count(
        self,
        labels: list[str],
        rows_per_column: int = 12,
        max_columns: int = 4,
    ) -> int:
        if not labels:
            return 1

        return max(1, min(max_columns, math.ceil(len(labels) / rows_per_column)))

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
        bbox_to_anchor: tuple[float, float] = (0.82, 0.82),
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

            summaries.append(
                (series_name, stats, self._box_summary_color(index, color, palette))
            )

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

        column_count = self._legend_column_count(labels)

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

    def _add_bar_category_legend(
        self,
        axis,
        categories: pd.Series,
        horizontal: bool,
        legend_font_size: int | None,
        language: str,
    ) -> None:
        labels = [
            str(value)
            for value in pd.Series(categories).dropna().drop_duplicates().tolist()
        ]

        patches = list(axis.containers[0].patches) if axis.containers else list(axis.patches)
        patches = [
            patch
            for patch in patches
            if patch.get_width() or patch.get_height()
        ]

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
        column_count = self._legend_column_count(shown_labels)

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
        patches = [
            patch
            for patch in patches
            if patch.get_width() or patch.get_height()
        ]

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
            values = [
                str(value)
                for value in data[category_column].dropna().drop_duplicates().tolist()
            ]

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
        column_count = self._legend_column_count(labels)

        self._set_fixed_figure_legend(
            axis,
            handles=handles,
            labels=labels,
            legend_font_size=legend_font_size,
            language=language,
            ncol=column_count,
            columnspacing=1.1,
        )

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
