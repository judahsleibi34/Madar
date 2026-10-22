\set ON_ERROR_STOP on

do $$
declare v_reservation uuid := '15400000-0000-4000-8000-000000000001';
declare v_object uuid; v_replay uuid; v_dataset uuid; v_version integer;
begin
  if not exists(select 1 from public.storage_objects where storage_backend='local_private') then
    raise exception 'legacy local storage rows were not preserved';
  end if;
  insert into public.storage_reservations(id,tenant_id,user_id,category,bytes,status)
  values(v_reservation,1,7,'dataset',19,'reserved');
  perform public.prepare_immutable_storage154(
    v_reservation,'madar-data-immutable',
    'tenant_1/dataset/15400000-0000-4000-8000-000000000001/'||repeat('a',64)||'.csv',
    19,repeat('a',64));
  perform public.prepare_immutable_storage154(
    v_reservation,'madar-data-immutable',
    'tenant_1/dataset/15400000-0000-4000-8000-000000000001/'||repeat('a',64)||'.csv',
    19,repeat('a',64));
  perform public.verify_immutable_storage154(v_reservation);
  v_object := public.finish_immutable_storage154(
    v_reservation,'tenant_1/user_7/shared-checkpoint.csv',null);
  v_replay := public.finish_immutable_storage154(
    v_reservation,'tenant_1/user_7/shared-checkpoint.csv',null);
  if v_object is null or v_object<>v_replay then
    raise exception 'immutable finish replay was not idempotent';
  end if;
  if not exists(select 1 from public.storage_objects where id=v_object
    and storage_backend='supabase_private' and storage_bucket='madar-data-immutable'
    and verified_size_bytes=size_bytes and verified_sha256=sha256
    and integrity_verified_at is not null) then
    raise exception 'verified provider evidence was not persisted';
  end if;
  insert into public.data_dataset_record_changes(
    tenant_id,project_id,source_id,source_resource_id,dataset_id,committed_revision,
    ingestion_run_id,storage_object_id,row_ordinal,source_record_id,operation,outcome,
    source_order,source_event_id,content_hash,schema_fingerprint
  ) select tenant_id,project_id,source_id,source_resource_id,dataset_id,9999,
    ingestion_run_id,v_object,9999,'shared-storage-proof','upsert','duplicate',
    null,null,content_hash,schema_fingerprint
  from public.data_dataset_record_changes order by id limit 1;
  if not exists(select 1 from public.data_dataset_record_changes
    where storage_object_id=v_object and committed_revision=9999) then
    raise exception 'verified shared history object was rejected';
  end if;
  begin
    insert into public.data_dataset_record_changes(
      tenant_id,project_id,source_id,source_resource_id,dataset_id,committed_revision,
      ingestion_run_id,storage_object_id,row_ordinal,source_record_id,operation,outcome,
      source_order,source_event_id,content_hash,schema_fingerprint
    ) select tenant_id,project_id,source_id,source_resource_id,dataset_id,10000,
      ingestion_run_id,'55555555-5555-4555-8555-555555555551',9998,
      'local-storage-proof','upsert','duplicate',null,null,content_hash,schema_fingerprint
    from public.data_dataset_record_changes order by id limit 1;
    raise exception 'unverified local incremental history was accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm<>'incremental_history_storage_not_verified' then raise; end if;
  end;
  select dataset_id into v_dataset from public.data_source_resources
  where resource_key='benchmark';
  select coalesce(max(version_number),0)+1 into v_version
  from public.data_dataset_versions where dataset_id=v_dataset;
  insert into public.data_dataset_versions(
    tenant_id,dataset_id,version_number,storage_object_id,created_by_user_id,
    version_kind,original_filename,content_type,file_extension,size_bytes,content_hash
  ) values(1,v_dataset,v_version,v_object,7,'checkpoint','shared.csv','text/csv','.csv',19,repeat('a',64));
  begin
    update public.storage_objects set status='deleted' where id=v_object;
    raise exception 'referenced shared checkpoint was released';
  exception when sqlstate 'P0001' then
    if sqlerrm not in ('incremental_history_storage_referenced','dataset_version_storage_referenced') then raise; end if;
  end;
  begin
    insert into public.data_dataset_versions(
      tenant_id,dataset_id,version_number,storage_object_id,created_by_user_id,
      version_kind,original_filename,content_type,file_extension,size_bytes,content_hash
    ) values(1,v_dataset,v_version+1,'55555555-5555-4555-8555-555555555551',7,
      'checkpoint','local.csv','text/csv','.csv',18,repeat('a',64));
    raise exception 'unverified local checkpoint was accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm<>'checkpoint_storage_not_verified' then raise; end if;
  end;
  insert into public.storage_reservations(id,tenant_id,user_id,category,bytes,status)
  values('15400000-0000-4000-8000-000000000002',1,7,'dataset',19,'reserved');
  begin
    perform public.prepare_immutable_storage154(
      '15400000-0000-4000-8000-000000000002','madar-data-immutable',
      'tenant_2/dataset/15400000-0000-4000-8000-000000000002/'||repeat('a',64)||'.csv',
      19,repeat('a',64));
    raise exception 'cross-tenant provider identity was accepted';
  exception when sqlstate 'P0001' then
    if sqlerrm<>'immutable_storage_identity_invalid' then raise; end if;
  end;
end;
$$;

select 'migration_154_shared_immutable_storage_passed' as result;
