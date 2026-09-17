create or replace function public.get_columns()
returns table(
  table_name text,
  column_name text,
  data_type text
)
language sql
security definer
as $$
  select 
    c.table_name::text,
    c.column_name::text,
    c.data_type::text
  from information_schema.columns c
  where c.table_schema = 'public'
  order by c.table_name, c.ordinal_position;
$$;

grant execute on function public.get_columns() to anon;
grant execute on function public.get_columns() to authenticated;

notify pgrst, 'reload schema';