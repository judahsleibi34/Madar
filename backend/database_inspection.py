from database import service_supabase
from rich.console import Console
from rich.table import Table

console = Console()


def get_table_names():
    response = service_supabase.rpc("get_tables").execute()
    return [table["table_name"] for table in response.data]


def show_tables():
    table_names = get_table_names()

    console.print("\n[bold cyan]Tables in Supabase[/bold cyan]")

    for table_name in table_names:
        console.print(f"- {table_name}")


def show_columns():
    columns = service_supabase.rpc("get_columns").execute()

    console.print("\n[bold cyan]Tables and columns[/bold cyan]")

    current_table = None

    for column in columns.data:
        table_name = column["table_name"]

        if table_name != current_table:
            current_table = table_name
            console.print(f"\n[bold yellow]--- {table_name} ---[/bold yellow]")

        console.print(f"- {column['column_name']} ({column['data_type']})")


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


def show_columns_and_values():
    show_columns()
    show_values(limit=5)


if __name__ == "__main__":
    show_columns_and_values()

