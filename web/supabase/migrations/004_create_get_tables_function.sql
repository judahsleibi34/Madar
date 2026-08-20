create or replace function get_tables()
returns table(table_name text)
language sql
security definer
as $$
  select tables.table_name::text
  from information_schema.tables
  where table_schema = 'public'
  order by tables.table_name;
$$;