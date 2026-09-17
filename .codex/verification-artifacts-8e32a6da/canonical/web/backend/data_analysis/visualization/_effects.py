from ._deps import pd, plt, sns, to_hex


class EffectsMixin:
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