import pandas as pd


class NgoMealAnalysis:
    def __init__(self, df: pd.DataFrame) -> None:
        if df.empty:
            raise ValueError("DataFrame is empty")

        self.df = df.copy()

    def indicator_progress(
        self,
        indicator_column: str,
        actual_column: str,
        target_column: str,
        group_column: str | None = None
    ) -> dict | list[dict]:
        self._validate_columns_exist([indicator_column, actual_column, target_column])
        self._validate_numeric_columns([actual_column, target_column])

        df = self.df.copy()

        if group_column:
            self._validate_columns_exist([group_column])

            grouped = (
                df.groupby([group_column, indicator_column])
                .agg({
                    actual_column: "sum",
                    target_column: "sum"
                })
                .reset_index()
            )

            grouped["achievement_percentage"] = grouped.apply(
                lambda row: (row[actual_column] / row[target_column]) * 100
                if row[target_column] != 0 else None,
                axis=1
            )

            return grouped.to_dict(orient="records")

        grouped = (
            df.groupby(indicator_column)
            .agg({
                actual_column: "sum",
                target_column: "sum"
            })
            .reset_index()
        )

        grouped["achievement_percentage"] = grouped.apply(
            lambda row: (row[actual_column] / row[target_column]) * 100
            if row[target_column] != 0 else None,
            axis=1
        )

        return grouped.to_dict(orient="records")

    def target_achievement(
        self,
        actual_column: str,
        target_column: str
    ) -> dict:
        self._validate_columns_exist([actual_column, target_column])
        self._validate_numeric_columns([actual_column, target_column])

        actual = self.df[actual_column].sum()
        target = self.df[target_column].sum()

        return {
            "actual": float(actual),
            "target": float(target),
            "gap": float(target - actual),
            "achievement_percentage": round(float((actual / target) * 100), 2)
            if target != 0 else None
        }

    def beneficiary_summary(
        self,
        beneficiary_column: str,
        group_columns: list[str] | None = None
    ) -> dict | list[dict]:
        self._validate_columns_exist([beneficiary_column])
        self._validate_numeric_columns([beneficiary_column])

        if group_columns:
            self._validate_columns_exist(group_columns)

            result = (
                self.df.groupby(group_columns)[beneficiary_column]
                .sum()
                .reset_index(name="total_beneficiaries")
            )

            return result.to_dict(orient="records")

        return {
            "total_beneficiaries": float(self.df[beneficiary_column].sum()),
            "average_beneficiaries": float(self.df[beneficiary_column].mean()),
            "max_beneficiaries": float(self.df[beneficiary_column].max()),
            "min_beneficiaries": float(self.df[beneficiary_column].min())
        }

    def disaggregation_summary(
        self,
        value_column: str,
        disaggregation_columns: list[str]
    ) -> list[dict]:
        self._validate_columns_exist([value_column] + disaggregation_columns)
        self._validate_numeric_columns([value_column])

        result = (
            self.df.groupby(disaggregation_columns)[value_column]
            .sum()
            .reset_index(name="total")
        )

        return result.to_dict(orient="records")

    def baseline_endline_change(
        self,
        group_column: str,
        baseline_column: str,
        endline_column: str
    ) -> list[dict]:
        self._validate_columns_exist([group_column, baseline_column, endline_column])
        self._validate_numeric_columns([baseline_column, endline_column])

        df = self.df.copy()

        result = (
            df.groupby(group_column)
            .agg({
                baseline_column: "mean",
                endline_column: "mean"
            })
            .reset_index()
        )

        result["absolute_change"] = result[endline_column] - result[baseline_column]
        result["percentage_change"] = result.apply(
            lambda row: ((row[endline_column] - row[baseline_column]) / row[baseline_column]) * 100
            if row[baseline_column] != 0 else None,
            axis=1
        )

        return result.to_dict(orient="records")

    def activity_completion_rate(
        self,
        completed_column: str,
        planned_column: str,
        group_column: str | None = None
    ) -> dict | list[dict]:
        self._validate_columns_exist([completed_column, planned_column])
        self._validate_numeric_columns([completed_column, planned_column])

        if group_column:
            self._validate_columns_exist([group_column])

            result = (
                self.df.groupby(group_column)
                .agg({
                    completed_column: "sum",
                    planned_column: "sum"
                })
                .reset_index()
            )

            result["completion_rate_percentage"] = result.apply(
                lambda row: (row[completed_column] / row[planned_column]) * 100
                if row[planned_column] != 0 else None,
                axis=1
            )

            return result.to_dict(orient="records")

        completed = self.df[completed_column].sum()
        planned = self.df[planned_column].sum()

        return {
            "completed": float(completed),
            "planned": float(planned),
            "completion_rate_percentage": round(float((completed / planned) * 100), 2)
            if planned != 0 else None
        }

    def survey_question_summary(
        self,
        question_column: str,
        response_column: str
    ) -> list[dict]:
        self._validate_columns_exist([question_column, response_column])

        result = (
            self.df.groupby([question_column, response_column])
            .size()
            .reset_index(name="count")
        )

        totals = (
            result.groupby(question_column)["count"]
            .transform("sum")
        )

        result["percentage"] = round((result["count"] / totals) * 100, 2)

        return result.to_dict(orient="records")

    def location_summary(
        self,
        location_column: str,
        value_columns: list[str]
    ) -> list[dict]:
        self._validate_columns_exist([location_column] + value_columns)
        self._validate_numeric_columns(value_columns)

        result = (
            self.df.groupby(location_column)[value_columns]
            .sum()
            .reset_index()
        )

        return result.to_dict(orient="records")

    def partner_summary(
        self,
        partner_column: str,
        value_columns: list[str]
    ) -> list[dict]:
        self._validate_columns_exist([partner_column] + value_columns)
        self._validate_numeric_columns(value_columns)

        result = (
            self.df.groupby(partner_column)[value_columns]
            .sum()
            .reset_index()
        )

        return result.to_dict(orient="records")

    def vulnerability_summary(
        self,
        vulnerability_column: str,
        beneficiary_column: str
    ) -> list[dict]:
        self._validate_columns_exist([vulnerability_column, beneficiary_column])
        self._validate_numeric_columns([beneficiary_column])

        result = (
            self.df.groupby(vulnerability_column)[beneficiary_column]
            .sum()
            .sort_values(ascending=False)
            .reset_index(name="total_beneficiaries")
        )

        return result.to_dict(orient="records")

    def complaint_feedback_summary(
        self,
        channel_column: str,
        status_column: str
    ) -> list[dict]:
        self._validate_columns_exist([channel_column, status_column])

        result = (
            self.df.groupby([channel_column, status_column])
            .size()
            .reset_index(name="count")
        )

        return result.to_dict(orient="records")

    def case_status_summary(
        self,
        status_column: str,
        group_column: str | None = None
    ) -> list[dict]:
        self._validate_columns_exist([status_column])

        if group_column:
            self._validate_columns_exist([group_column])

            result = (
                self.df.groupby([group_column, status_column])
                .size()
                .reset_index(name="count")
            )

            return result.to_dict(orient="records")

        result = (
            self.df[status_column]
            .value_counts(dropna=False)
            .reset_index()
        )

        result.columns = [status_column, "count"]

        return result.to_dict(orient="records")

    def attendance_rate(
        self,
        attended_column: str,
        registered_column: str,
        group_column: str | None = None
    ) -> dict | list[dict]:
        self._validate_columns_exist([attended_column, registered_column])
        self._validate_numeric_columns([attended_column, registered_column])

        if group_column:
            self._validate_columns_exist([group_column])

            result = (
                self.df.groupby(group_column)
                .agg({
                    attended_column: "sum",
                    registered_column: "sum"
                })
                .reset_index()
            )

            result["attendance_rate_percentage"] = result.apply(
                lambda row: (row[attended_column] / row[registered_column]) * 100
                if row[registered_column] != 0 else None,
                axis=1
            )

            return result.to_dict(orient="records")

        attended = self.df[attended_column].sum()
        registered = self.df[registered_column].sum()

        return {
            "attended": float(attended),
            "registered": float(registered),
            "attendance_rate_percentage": round(float((attended / registered) * 100), 2)
            if registered != 0 else None
        }

    def _validate_columns_exist(self, columns: list[str]) -> None:
        missing_columns = [
            column for column in columns
            if column not in self.df.columns
        ]

        if missing_columns:
            raise ValueError(f"Columns not found: {missing_columns}")

    def _validate_numeric_columns(self, columns: list[str]) -> None:
        for column in columns:
            if not pd.api.types.is_numeric_dtype(self.df[column]):
                raise TypeError(f"Column '{column}' must be numeric")

