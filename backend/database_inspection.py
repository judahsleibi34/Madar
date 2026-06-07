from collections import defaultdict

from database import service_supabase
from rich.console import Console
from rich.table import Table

console = Console()


def safe_execute(label, query_fn, default=None):
    try:
        response = query_fn()
        return getattr(response, "data", None) or default or []
    except Exception as error:
        console.print(f"[yellow]Could not load {label}: {type(error).__name__}[/yellow]")
        return default or []


def get_table_names():
    rows = safe_execute(
        "tables",
        lambda: service_supabase.rpc("get_tables").execute(),
    )
    return [table["table_name"] for table in rows if table.get("table_name")]


def get_columns():
    return safe_execute(
        "columns",
        lambda: service_supabase.rpc("get_columns").execute(),
    )


def get_table_constraints():
    return safe_execute(
        "table constraints",
        lambda: (
            service_supabase.table("information_schema.table_constraints")
            .select("table_name,constraint_name,constraint_type")
            .eq("table_schema", "public")
            .execute()
        ),
    )


def get_key_column_usage():
    return safe_execute(
        "key column usage",
        lambda: (
            service_supabase.table("information_schema.key_column_usage")
            .select("table_name,constraint_name,column_name,ordinal_position")
            .eq("table_schema", "public")
            .execute()
        ),
    )


def get_foreign_key_usage():
    return safe_execute(
        "foreign key usage",
        lambda: (
            service_supabase.table("information_schema.constraint_column_usage")
            .select("table_name,constraint_name,column_name")
            .eq("table_schema", "public")
            .execute()
        ),
    )


def get_check_constraints():
    return safe_execute(
        "check constraints",
        lambda: (
            service_supabase.table("information_schema.check_constraints")
            .select("constraint_name,check_clause")
            .eq("constraint_schema", "public")
            .execute()
        ),
    )


def get_indexes():
    return safe_execute(
        "indexes",
        lambda: (
            service_supabase.table("pg_indexes")
            .select("tablename,indexname,indexdef")
            .eq("schemaname", "public")
            .execute()
        ),
    )


def get_rls_status():
    return safe_execute(
        "RLS status",
        lambda: (
            service_supabase.table("pg_tables")
            .select("tablename,rowsecurity")
            .eq("schemaname", "public")
            .execute()
        ),
    )


def group_by(rows, key):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.get(key)].append(row)
    return grouped


def show_tables():
    table_names = get_table_names()
    rls_by_table = {
        row.get("tablename"): row.get("rowsecurity")
        for row in get_rls_status()
    }

    table = Table(title="Tables in Supabase", show_header=True, header_style="bold cyan")
    table.add_column("Table")
    table.add_column("RLS")

    for table_name in table_names:
        rls_value = rls_by_table.get(table_name)
        rls_text = "unknown" if rls_value is None else ("enabled" if rls_value else "disabled")
        table.add_row(table_name, rls_text)

    console.print(table)


def show_columns():
    columns_by_table = group_by(get_columns(), "table_name")

    console.print("\n[bold cyan]Columns[/bold cyan]")

    for table_name in get_table_names():
        table = Table(title=table_name, show_header=True, header_style="bold yellow")
        table.add_column("Column")
        table.add_column("Data type")

        for column in columns_by_table.get(table_name, []):
            table.add_row(
                str(column.get("column_name") or ""),
                str(column.get("data_type") or ""),
            )

        console.print(table)


def show_constraints():
    constraints = get_table_constraints()
    key_usage_by_constraint = group_by(get_key_column_usage(), "constraint_name")
    fk_usage_by_constraint = group_by(get_foreign_key_usage(), "constraint_name")
    checks_by_constraint = {
        row.get("constraint_name"): row.get("check_clause")
        for row in get_check_constraints()
    }

    table = Table(title="Constraints", show_header=True, header_style="bold cyan")
    table.add_column("Table")
    table.add_column("Type")
    table.add_column("Name")
    table.add_column("Columns")
    table.add_column("References / Check")

    for constraint in constraints:
        constraint_name = constraint.get("constraint_name")
        constraint_type = constraint.get("constraint_type")
        columns = ", ".join(
            str(row.get("column_name"))
            for row in sorted(
                key_usage_by_constraint.get(constraint_name, []),
                key=lambda row: row.get("ordinal_position") or 0,
            )
            if row.get("column_name")
        )

        reference = ""
        if constraint_type == "FOREIGN KEY":
            reference = "; ".join(
                f"{row.get('table_name')}.{row.get('column_name')}"
                for row in fk_usage_by_constraint.get(constraint_name, [])
            )
        elif constraint_type == "CHECK":
            reference = str(checks_by_constraint.get(constraint_name) or "")

        table.add_row(
            str(constraint.get("table_name") or ""),
            str(constraint_type or ""),
            str(constraint_name or ""),
            columns,
            reference,
        )

    console.print(table)


def show_indexes():
    table = Table(title="Indexes", show_header=True, header_style="bold cyan")
    table.add_column("Table")
    table.add_column("Index")
    table.add_column("Definition")

    for index in get_indexes():
        table.add_row(
            str(index.get("tablename") or ""),
            str(index.get("indexname") or ""),
            str(index.get("indexdef") or ""),
        )

    console.print(table)


def show_values(limit=5):
    table_names = get_table_names()

    console.print(f"\n[bold cyan]Table values, limit {limit} rows each[/bold cyan]")

    for table_name in table_names:
        console.print(f"\n[bold yellow]=== {table_name} ===[/bold yellow]")

        records = service_supabase.table(table_name).select("*").limit(limit).execute()

        if not records.data:
            console.print("[dim]No records found.[/dim]")
            continue

        table = Table(show_header=True, header_style="bold magenta")
        columns = list(records.data[0].keys())

        for column in columns:
            table.add_column(column)

        for record in records.data:
            table.add_row(*[str(record.get(column, "")) for column in columns])

        console.print(table)


def show_schema_summary(include_values=False):
    show_tables()
    show_columns()
    show_constraints()
    show_indexes()

    if include_values:
        show_values(limit=5)


if __name__ == "__main__":
    show_schema_summary(include_values=False)
