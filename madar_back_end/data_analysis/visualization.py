import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Literal


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
        x: str | None = None,
        y: str | None = None,
        hue: str | None = None,
        title: str | None = None,
        x_label: str | None = None,
        y_label: str | None = None,
        palette: str | list[str] = "viridis",
        color: str | None = None,
        style: str = "whitegrid",
        figsize: tuple[int, int] = (10, 6),
        marker: str = "o",
        rotation: int = 45,
        save_path: str | None = None,
        show: bool = False
    ) -> str | None:
        sns.set_theme(style=style)

        plt.figure(figsize=figsize)

        if chart_type == "bar":
            self._validate_columns([x, y])
            sns.barplot(
                data=self.df,
                x=x,
                y=y,
                hue=hue,
                palette=palette,
                color=color
            )

        elif chart_type == "line":
            self._validate_columns([x, y])
            sns.lineplot(
                data=self.df,
                x=x,
                y=y,
                hue=hue,
                marker=marker,
                palette=palette,
                color=color
            )

        elif chart_type == "scatter":
            self._validate_columns([x, y])
            sns.scatterplot(
                data=self.df,
                x=x,
                y=y,
                hue=hue,
                palette=palette,
                color=color,
                s=90
            )

        elif chart_type == "histogram":
            self._validate_columns([x])
            sns.histplot(
                data=self.df,
                x=x,
                hue=hue,
                kde=True,
                palette=palette,
                color=color
            )

        elif chart_type == "box":
            self._validate_columns([x, y])
            sns.boxplot(
                data=self.df,
                x=x,
                y=y,
                hue=hue,
                palette=palette,
                color=color
            )

        elif chart_type == "violin":
            self._validate_columns([x, y])
            sns.violinplot(
                data=self.df,
                x=x,
                y=y,
                hue=hue,
                palette=palette,
                color=color
            )

        elif chart_type == "count":
            self._validate_columns([x])
            sns.countplot(
                data=self.df,
                x=x,
                hue=hue,
                palette=palette,
                color=color
            )

        elif chart_type == "pie":
            self._validate_columns([x, y])
            self._plot_pie(
                label_column=x,
                value_column=y,
                palette=palette
            )

        elif chart_type == "heatmap":
            self._plot_heatmap(
                palette=palette
            )

        else:
            raise ValueError(f"Unsupported chart type: {chart_type}")

        self._style_plot(
            title=title,
            x_label=x_label or x,
            y_label=y_label or y,
            rotation=rotation
        )

        if save_path:
            output_path = self._save_plot(save_path)
        else:
            output_path = None

        if show:
            plt.show()

        plt.close()

        return output_path

    def _plot_pie(
        self,
        label_column: str,
        value_column: str,
        palette: str | list[str]
    ) -> None:
        grouped = (
            self.df.groupby(label_column)[value_column]
            .sum()
            .sort_values(ascending=False)
        )

        colors = sns.color_palette(palette, len(grouped))

        plt.pie(
            grouped.values,
            labels=grouped.index,
            autopct="%1.1f%%",
            startangle=140,
            colors=colors,
            wedgeprops={"edgecolor": "white", "linewidth": 1}
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
        rotation: int
    ) -> None:
        if title:
            plt.title(title, fontsize=18, fontweight="bold", pad=20)

        if x_label:
            plt.xlabel(x_label, fontsize=12, fontweight="bold")

        if y_label:
            plt.ylabel(y_label, fontsize=12, fontweight="bold")

        plt.xticks(rotation=rotation)
        plt.yticks(rotation=0)
        plt.tight_layout()

        legend = plt.gca().get_legend()
        if legend:
            legend.set_title("")
            legend.get_frame().set_alpha(0.9)

    def _save_plot(self, save_path: str) -> str:
        path = Path(save_path)

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

