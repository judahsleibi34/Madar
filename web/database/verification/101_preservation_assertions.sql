do $$ begin
  if exists(select 1 from public.ecommerce_product_options where display_type <> 'text')
     or exists(select 1 from public.ecommerce_product_option_values where color_hex is not null) then raise exception '101_legacy_defaults_invalid'; end if;
  perform public.record_public_site_visit_safe(961,'website');
  perform public.record_public_site_visit_safe(961,'website');
  perform public.record_public_site_visit_safe(961,'store');
  if not exists(select 1 from public.site_visit_counters where tenant_id=961 and website_visits=19 and store_visits=10) then raise exception '098_counter_wrong'; end if;
  begin
    perform public.record_public_site_visit_safe(961,'invalid');
    raise exception '098_invalid_surface_allowed';
  exception when sqlstate 'P0001' then
    if sqlerrm <> 'site_visit_surface_invalid' then raise; end if;
  end;
  begin
    update public.ecommerce_product_option_values set color_hex='bad';
    raise exception '101_invalid_hex_allowed';
  exception when check_violation then null; end;
end $$;

do $$ declare attrs jsonb; opts jsonb; variants jsonb; before_variants jsonb; after_variants jsonb; begin
  select coalesce(jsonb_agg(to_jsonb(a) order by id),'[]') into attrs from public.ecommerce_product_attributes a where tenant_id=961;
  select jsonb_agg(to_jsonb(o) || jsonb_build_object('client_id',o.id,'display_type','color','values',
    (select jsonb_agg(to_jsonb(v) || jsonb_build_object('color_hex','#aabbcc') order by id) from public.ecommerce_product_option_values v where v.option_id=o.id)))
    into opts from public.ecommerce_product_options o where tenant_id=961;
  select jsonb_agg(to_jsonb(v) || jsonb_build_object('option_value_ids',
    (select jsonb_agg(option_value_id order by option_value_id) from public.ecommerce_variant_option_values l where l.variant_id=v.id)) order by id)
    into variants from public.ecommerce_product_variants v where tenant_id=961;
  select jsonb_agg(to_jsonb(v)-'updated_at' order by id) into before_variants from public.ecommerce_product_variants v where tenant_id=961;
  perform public.save_ecommerce_product_aggregate_v2_safe(961,'96100000-0000-0000-0000-000000000002',attrs,opts,variants);
  if exists(select 1 from public.ecommerce_product_options where tenant_id=961 and display_type<>'color')
    or exists(select 1 from public.ecommerce_product_option_values where tenant_id=961 and color_hex is distinct from '#AABBCC') then raise exception '101_color_save_wrong'; end if;
  select jsonb_agg(to_jsonb(v)-'updated_at' order by id) into after_variants from public.ecommerce_product_variants v where tenant_id=961;
  if before_variants is distinct from after_variants then raise exception '101_save_changed_variant_commercial_fields'; end if;
  begin
    perform public.save_ecommerce_product_aggregate_v2_safe(961,'96100000-0000-0000-0000-000000000002',attrs,jsonb_set(opts,'{0,values,0,color_hex}','"bad"'),variants);
    raise exception '101_bad_swatch_allowed';
  exception when sqlstate 'P0001' then if sqlerrm<>'ecommerce_color_swatch_required' then raise; end if; end;
  if exists(select 1 from public.ecommerce_product_option_values where tenant_id=961 and color_hex is distinct from '#AABBCC') then raise exception '101_invalid_save_not_atomic'; end if;
end $$;
