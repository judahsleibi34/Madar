begin;

alter table public.ecommerce_product_options
  add column display_type text not null default 'text',
  add constraint ecommerce_product_options_display_type_check
    check (display_type in ('text','color'));

alter table public.ecommerce_product_option_values
  add column color_hex text,
  add constraint ecommerce_product_option_values_color_hex_check
    check (color_hex is null or color_hex ~ '^#[0-9A-Fa-f]{6}$');

-- Extends the proven aggregate transaction instead of duplicating its identity,
-- SKU, archival, inventory, and publication invariants.
create or replace function public.save_ecommerce_product_aggregate_v2_safe(
  p_tenant_id integer,p_product_id uuid,p_attributes jsonb,p_options jsonb,p_variants jsonb
) returns jsonb language plpgsql security definer set search_path=public as $$
declare v_option jsonb; v_value jsonb; v_option_id uuid; v_display_type text;
begin
  perform public.save_ecommerce_product_aggregate_safe(
    p_tenant_id,p_product_id,p_attributes,p_options,p_variants
  );

  for v_option in select * from jsonb_array_elements(p_options) loop
    v_option_id := (v_option->>'id')::uuid;
    v_display_type := coalesce(nullif(v_option->>'display_type',''),'text');
    if v_display_type not in ('text','color') then
      raise exception using errcode='P0001',message='ecommerce_option_display_type_invalid';
    end if;

    update public.ecommerce_product_options
       set display_type=v_display_type
     where id=v_option_id and tenant_id=p_tenant_id and product_id=p_product_id;
    if not found then
      raise exception using errcode='P0001',message='ecommerce_option_presentation_target_invalid';
    end if;

    for v_value in select * from jsonb_array_elements(v_option->'values') loop
      if v_display_type='color' and coalesce((v_value->>'active')::boolean,true)
         and coalesce(v_value->>'color_hex','') !~ '^#[0-9A-Fa-f]{6}$' then
        raise exception using errcode='P0001',message='ecommerce_color_swatch_required';
      end if;
      if v_display_type='text' and nullif(v_value->>'color_hex','') is not null then
        raise exception using errcode='P0001',message='ecommerce_text_value_swatch_invalid';
      end if;
      update public.ecommerce_product_option_values
         set color_hex=case when v_display_type='color' then upper(v_value->>'color_hex') else null end
       where id=(v_value->>'id')::uuid
         and option_id=v_option_id
         and tenant_id=p_tenant_id
         and product_id=p_product_id;
      if not found then
        raise exception using errcode='P0001',message='ecommerce_value_presentation_target_invalid';
      end if;
    end loop;
  end loop;
  return jsonb_build_object('product_id',p_product_id,'saved',true);
end $$;

revoke all on function public.save_ecommerce_product_aggregate_v2_safe(integer,uuid,jsonb,jsonb,jsonb) from public,anon,authenticated;
grant execute on function public.save_ecommerce_product_aggregate_v2_safe(integer,uuid,jsonb,jsonb,jsonb) to service_role;

do $$ declare v_schema_version public.application_schema_state.schema_version%TYPE; begin
  select schema_version into v_schema_version from public.application_schema_state where contract_key = 'core' for update;
  if v_schema_version is null then raise exception using errcode='P0001',message='migration_099_schema_state_missing'; end if;
  if v_schema_version<>98 then raise exception using errcode='P0001',message=format('migration_099_expected_schema_98_got_%s',v_schema_version); end if;
  update public.application_schema_state set schema_version=99,applied_at=now() where contract_key = 'core';
end $$;

notify pgrst,'reload schema';
commit;
