from ._deps import Line2D, Patch, math, os, pd, plt, sns


class PlotHelpersMixin:
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
            boxprops={
                "facecolor": box_color,
                "edgecolor": "#303030",
                "linewidth": 1.3,
            },
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
            self._shape_text(
                (y_label or label) if is_horizontal else (x_label or "Variables"),
                language,
            ),
            fontsize=label_font_size,
            fontweight="bold",
            color="#111827",
            **font_options,
        )
        axis.set_ylabel(
            self._shape_text(
                (x_label or "Variables") if is_horizontal else (y_label or label),
                language,
            ),
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

        axis.grid(
            axis="x" if is_horizontal else "y",
            color="#111827",
            linewidth=0.65,
            alpha=0.16,
        )
        axis.tick_params(axis="both", labelsize=tick_font_size, colors="#111827")
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#d7dce5")
        axis.spines["bottom"].set_color("#d7dce5")

        self._format_line_axis_numbers(
            axis,
            numeric_values,
            "x" if is_horizontal else "y",
        )

        self._add_box_summary_legend(
            axis=axis,
            data=pd.DataFrame(
                {
                    "Series": [label] * len(numeric_values),
                    "Value": numeric_values,
                }
            ),
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
            colors = self._resize_palette(
                [str(item) for item in palette if item],
                panel_count,
            )
        elif color:
            colors = self._resize_palette([color], panel_count)
        else:
            colors = list(
                sns.color_palette(
                    palette or "viridis",
                    n_colors=panel_count,
                ).as_hex()
            )

        for axis, series_name, box_color in zip(axes, series_names, colors):
            values = pd.to_numeric(
                box_data.loc[
                    box_data[series_column] == series_name,
                    value_column,
                ],
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
                self._shape_text(
                    (y_label or "Value") if is_horizontal else (x_label or "Distribution"),
                    language,
                ),
                fontsize=label_font_size,
                fontweight="bold",
                color="#111827",
                **font_options,
            )
            axis.set_ylabel(
                self._shape_text(
                    (x_label or "Distribution") if is_horizontal else (y_label or "Value"),
                    language,
                ),
                fontsize=label_font_size,
                fontweight="bold",
                color="#111827",
                **font_options,
            )

            axis.grid(
                axis="x" if is_horizontal else "y",
                color="#111827",
                linewidth=0.65,
                alpha=0.16,
            )
            axis.tick_params(axis="both", labelsize=tick_font_size, colors="#111827")
            axis.spines["top"].set_visible(False)
            axis.spines["right"].set_visible(False)
            axis.spines["left"].set_color("#d7dce5")
            axis.spines["bottom"].set_color("#d7dce5")

            self._format_line_axis_numbers(
                axis,
                values,
                "x" if is_horizontal else "y",
            )

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
                target_axis.spines["right"].set_position(("axes", 1 + (0.08 * (index - 1))))
                secondary_axes.append(target_axis)
            elif index == 1:
                secondary_axes.append(target_axis)

            line = target_axis.plot(
                work[plot_x],
                work[plot_y],
                marker=marker,
                linewidth=2.6,
                color=line_color,
                linestyle=line_styles[index % len(line_styles)],
                label=label,
                zorder=5,
            )[0]

            if gradient:
                try:
                    baseline = float(pd.to_numeric(work[plot_y], errors="coerce").min())
                    target_axis.fill_between(
                        work[plot_x],
                        work[plot_y],
                        baseline,
                        color=line_color,
                        alpha=0.10,
                        zorder=1,
                    )
                except Exception:
                    pass

            target_axis.set_ylabel(
                self._shape_text(y_column, language),
                fontsize=label_font_size,
                fontweight="bold",
                color=line_color,
                **font_options,
            )
            target_axis.tick_params(axis="y", labelsize=tick_font_size, colors=line_color)
            target_axis.spines["right" if index else "left"].set_color(line_color)
            target_axis.grid(
                axis="y",
                color="#111827",
                linewidth=0.65,
                alpha=0.16 if index == 0 else 0.0,
            )
            self._format_line_axis_numbers(target_axis, work[plot_y], "y")
            lines.append(line)
            labels.append(label)

        axis.set_xlabel(
            self._shape_text(x_label or x_column, language),
            fontsize=label_font_size,
            fontweight="bold",
            color="#111827",
            **font_options,
        )
        axis.tick_params(axis="x", labelsize=tick_font_size, colors="#111827", rotation=rotation)
        axis.spines["top"].set_visible(False)
        axis.spines["bottom"].set_color("#d7dce5")

        for secondary_axis in secondary_axes:
            secondary_axis.spines["top"].set_visible(False)

        if title:
            axis.set_title(
                self._shape_text(title, language),
                fontsize=title_font_size,
                fontweight="bold",
                color="#111827",
                pad=20,
                **font_options,
            )

        axis._madar_fixed_legend_lane = "line"
        self._set_fixed_figure_legend(
            axis,
            handles=lines,
            labels=labels,
            legend_font_size=legend_font_size,
            language=language,
            bbox_to_anchor=(0.82, 0.84),
            ncol=1,
        )

        figure.tight_layout(rect=[0, 0, 0.76, 1])
        
    def _plot_pie(
        self,
        label_column: str,
        value_column: str,
        palette: str | list[str],
        language: str,
        gradient: bool = False,
        color: str | None = None,
    ) -> None:
        pie_data = self.df[[label_column, value_column]].copy()
        pie_data[value_column] = pd.to_numeric(pie_data[value_column], errors="coerce")
        pie_data = pie_data.dropna(subset=[label_column, value_column])

        if pie_data.empty:
            raise ValueError("Pie chart needs numeric values.")

        pie_data = (
            pie_data.groupby(label_column, dropna=False)[value_column]
            .sum()
            .reset_index()
        )
        pie_data = pie_data[pie_data[value_column] > 0]

        if pie_data.empty:
            raise ValueError("Pie chart needs positive numeric values.")

        labels = [
            self._shape_text(str(value), language)
            for value in pie_data[label_column].tolist()
        ]
        values = pie_data[value_column].tolist()

        if gradient:
            colors = self._gradient_colors(palette, len(values), color)
        elif isinstance(palette, list):
            colors = self._resize_palette([str(item) for item in palette if item], len(values))
        elif color:
            colors = self._resize_palette([color], len(values))
        else:
            colors = list(sns.color_palette(palette or "viridis", n_colors=len(values)).as_hex())

        axis = plt.gca()
        wedges, _texts, autotexts = axis.pie(
            values,
            labels=None,
            autopct="%1.1f%%",
            startangle=90,
            colors=colors,
            wedgeprops={
                "linewidth": 1,
                "edgecolor": "white",
            },
            textprops={
                "fontsize": 10,
                "color": "#111827",
            },
        )

        for autotext in autotexts:
            autotext.set_fontweight("bold")
            autotext.set_color("#111827")

        axis.axis("equal")

        legend_labels = [
            f"{label}: {self._format_summary_value(float(value))}"
            for label, value in zip(labels, values)
        ]

        axis._madar_fixed_legend_lane = "pie"
        self._set_fixed_figure_legend(
            axis,
            handles=wedges,
            labels=legend_labels,
            legend_font_size=10,
            language=language,
            bbox_to_anchor=(0.82, 0.84),
            ncol=1,
        )

        plt.tight_layout(rect=[0, 0, 0.78, 1])

    def _plot_heatmap(
        self,
        features: list[str] | None,
        palette: str | list[str],
        color: str | None = None,
    ) -> None:
        if features:
            missing_features = [
                feature
                for feature in features
                if feature not in self.df.columns
            ]
            if missing_features:
                raise ValueError(f"Columns not found: {missing_features}")

            heatmap_data = self.df[features].copy()
        else:
            heatmap_data = self.df.copy()

        numeric_data = heatmap_data.select_dtypes(include="number")

        if numeric_data.empty:
            raise ValueError("Heatmap requires at least one numeric column.")

        correlation = numeric_data.corr(numeric_only=True)

        if correlation.empty:
            raise ValueError("Heatmap could not compute correlations.")

        cmap = self._palette_cmap(palette, color)

        axis = sns.heatmap(
            correlation,
            annot=True,
            cmap=cmap,
            linewidths=0.8,
            linecolor="white",
            square=True,
            cbar_kws={"shrink": 0.78},
            fmt=".2f",
        )

        axis.set_xticklabels(
            [self._shape_text(label.get_text()) for label in axis.get_xticklabels()],
            rotation=45,
            ha="right",
        )
        axis.set_yticklabels(
            [self._shape_text(label.get_text()) for label in axis.get_yticklabels()],
            rotation=0,
        )

        plt.tight_layout()

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
        axis = plt.gca()
        font_options = {"fontfamily": font_family} if font_family else {}

        if title:
            axis.set_title(
                self._shape_text(title, language),
                fontsize=title_font_size,
                fontweight="bold",
                color="#111827",
                pad=20,
                **font_options,
            )

        axis.set_xlabel(
            self._shape_text(x_label, language) or "",
            fontsize=label_font_size,
            fontweight="bold",
            color="#111827",
            **font_options,
        )
        axis.set_ylabel(
            self._shape_text(y_label, language) or "",
            fontsize=label_font_size,
            fontweight="bold",
            color="#111827",
            **font_options,
        )

        axis.tick_params(axis="both", labelsize=tick_font_size, colors="#111827")

        for label in axis.get_xticklabels():
            label.set_rotation(rotation)
            label.set_horizontalalignment("right")
            label.set_color("#111827")
            if font_family:
                label.set_fontfamily(font_family)

        for label in axis.get_yticklabels():
            label.set_color("#111827")
            if font_family:
                label.set_fontfamily(font_family)

        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#d7dce5")
        axis.spines["bottom"].set_color("#d7dce5")

        legend = axis.get_legend()
        if legend:
            self._apply_legend_design(
                legend,
                legend_font_size=legend_font_size,
                font_family=font_family,
                language=language,
            )

        lane = getattr(axis, "_madar_fixed_legend_lane", None)
        if lane in {"bar", "scatter", "line", "stats", "pie"}:
            plt.tight_layout(rect=[0, 0, 0.78, 1])
        else:
            plt.tight_layout()

    def _save_plot(self, save_path: str) -> str:
        output_root = os.getenv("CHART_OUTPUT_DIR", "generated_charts")
        output_dir = os.path.abspath(output_root)
        os.makedirs(output_dir, exist_ok=True)

        requested_path = os.path.basename(save_path)
        if not requested_path:
            requested_path = "chart.png"

        if not requested_path.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".pdf")):
            requested_path = f"{requested_path}.png"

        output_path = os.path.join(output_dir, requested_path)

        plt.savefig(
            output_path,
            dpi=180,
            bbox_inches="tight",
            facecolor="white",
        )

        return output_path