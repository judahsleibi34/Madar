from ._deps import LinearSegmentedColormap, colorsys, pd, sns, to_hex, to_rgb


class PaletteMixin:
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