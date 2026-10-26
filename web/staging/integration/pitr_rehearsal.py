#!/usr/bin/env python3
"""Tiny physical/WAL recovery drill: owned synthetic, network-none PostgreSQL only."""
import argparse
import os
import subprocess
import json
from pathlib import Path
import re
import secrets
import shutil
import time

import manage

IMAGE='postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'
MARKER='madar-pitr-synthetic-20261017'
SCOPE_LABEL='com.madar.rehearsal.scope'


def remove_container(name,scope):
    rows=json.loads(manage.docker('inspect',name))
    if (len(rows)!=1 or rows[0]['Name']!='/'+name
            or rows[0]['Config']['Labels'].get(SCOPE_LABEL)!=scope
            or rows[0]['Config']['Labels'].get('com.madar.staging.owner')!=manage.OWNER):
        raise RuntimeError('Refusing unowned PITR cleanup')
    manage.docker('rm','--force',name)


def main(mode):
    manage.require_staging_host()
    if mode=='INSPECT':
        print(json.dumps({'mode':mode,'image':IMAGE,'network':'none','production_modified':False}));return
    available=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
    if available<1400*1024 or shutil.disk_usage(Path.home()).free<2*1024**3:
        raise RuntimeError('PITR headroom insufficient')
    scope='madar-pitr-'+secrets.token_hex(6)
    previous=manage.RUNTIME;runtime=Path.home()/scope;runtime.mkdir(mode=0o700)
    manage.RUNTIME=runtime
    names=[];volumes=[];started=time.monotonic()
    labels=['--label',SCOPE_LABEL+'='+scope,'--label','com.madar.staging.owner='+manage.OWNER]
    def volume(kind):
        name=scope+'-'+kind
        manage.docker('volume','create',*labels,name);volumes.append(name)
        return name
    data,archive,backup,recovered,missing,corrupt,incomplete,badarchive=[volume(n) for n in ('data','wal','base','recovered','missing','corrupt','incomplete','badwal')]
    def helper(script,mounts):
        args=['run','--rm','--network=none','--memory=128m','--cpus=0.5','--pids-limit=64',*labels]
        for name,destination,writable in mounts:
            metadata=json.loads(manage.docker('volume','inspect',name))[0]
            if metadata.get('Labels',{}).get(SCOPE_LABEL)!=scope:raise RuntimeError('PITR volume ownership changed')
            args+=['--volume',name+':'+destination+('' if writable else ':ro')]
        return manage.docker(*args,'--entrypoint','sh',IMAGE,'-ec',script)
    def start(kind,vol,archive_vol,*,target=None):
        name=scope+'-'+kind
        args=['run','--detach','--name',name,'--network=none','--memory=384m','--cpus=0.5','--pids-limit=128',
              '--security-opt','no-new-privileges:true','--cap-drop=ALL','--user=70:70','--read-only',*labels,
              '--log-opt','max-size=2m','--log-opt','max-file=2',
              '--tmpfs','/tmp:rw,nosuid,nodev,size=32m,uid=70,gid=70',
              '--tmpfs','/var/run/postgresql:rw,nosuid,nodev,size=8m,uid=70,gid=70',
              '--volume',vol+':/var/lib/postgresql/data','--volume',archive_vol+':/archive'+(':ro' if target else ''),
              '--env','POSTGRES_HOST_AUTH_METHOD=trust']
        if target is None:args+=['--volume',backup+':/backup']
        args += [IMAGE,'postgres','-c','shared_buffers=32MB','-c','max_connections=16','-c','max_wal_size=64MB']
        if target:
            args+=['-c','archive_mode=off','-c','restore_command=cp /archive/%f %p','-c','recovery_target_name='+target,
                   '-c','recovery_target_action=pause','-c','recovery_target_timeline=current']
        else:args+=['-c','wal_level=replica','-c','archive_mode=on','-c','archive_timeout=60',
                    '-c','archive_command=test ! -f /archive/%f && cp %p /archive/%f']
        manage.docker(*args);names.append(name);return name
    def sql(name,statement):
        row=json.loads(manage.docker('inspect',name))[0]
        if row.get('Config',{}).get('Labels',{}).get(SCOPE_LABEL)!=scope:raise RuntimeError('PITR database ownership changed')
        return manage.docker('exec',name,'psql','-h','127.0.0.1','-U','postgres','-d','postgres','-XqAt','-v','ON_ERROR_STOP=1','-c',statement).decode().strip()
    def wait_ready(name):
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            try:
                if sql(name,'select 1;')=='1':return
            except RuntimeError:pass
            time.sleep(0.5)
        raise RuntimeError('Owned PITR instance unavailable')
    def clone(destination):
        helper('cp -a /backup/base/. /data/; touch /data/recovery.signal; chown -R 70:70 /data',[(backup,'/backup',False),(destination,'/data',True)])
    try:
        helper('chown 70:70 /data /archive /backup',[(data,'/data',True),(archive,'/archive',True),(backup,'/backup',True)])
        source=start('source',data,archive);wait_ready(source)
        sql(source,"comment on database postgres is '"+MARKER+"'; create table pitr_probe(id integer primary key); insert into pitr_probe values(1);")
        if sql(source,"select shobj_description(oid,'pg_database') from pg_database where datname='postgres';")!=MARKER:raise RuntimeError('PITR marker mismatch')
        system=sql(source,'select system_identifier from pg_control_system();')
        manage.docker('exec',source,'pg_basebackup','-h','127.0.0.1','-U','postgres','-D','/backup/base','-X','stream','-c','fast',timeout=120)
        verified=manage.docker('exec',source,'pg_verifybackup','/backup/base').decode()
        if 'backup successfully verified' not in verified:raise RuntimeError('Base backup verification missing')
        # Force the target record into a segment not bundled with the base backup.
        sql(source,'select pg_switch_wal();')
        sql(source,'insert into pitr_probe values(2);')
        target='madar_target_'+secrets.token_hex(8)
        lsn=sql(source,"select pg_create_restore_point('"+target+"')::text;")
        if not re.fullmatch('[0-9A-F]+/[0-9A-F]+',lsn):raise RuntimeError('PITR target LSN invalid')
        wal=sql(source,"select pg_walfile_name('"+lsn+"'::pg_lsn);")
        if not re.fullmatch('[0-9A-F]{24}',wal):raise RuntimeError('PITR archive identity invalid')
        sql(source,'select pg_switch_wal();')
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            try:manage.docker('exec',source,'test','-f','/archive/'+wal);break
            except RuntimeError:time.sleep(0.5)
        else:raise RuntimeError('Required target WAL not archived')
        sql(source,'insert into pitr_probe values(3); delete from pitr_probe where id=1;')
        if sql(source,'select array_agg(id order by id)::text from pitr_probe;')!='{2,3}':raise RuntimeError('Synthetic post-target change not established')
        clone(recovered);good=start('recovered',recovered,archive,target=target);wait_ready(good)
        state=json.loads(sql(good,"select json_build_object('recovery',pg_is_in_recovery(),'pause',pg_get_wal_replay_pause_state(),'rows',(select array_agg(id order by id) from pitr_probe));"))
        if state!={'recovery':True,'pause':'paused','rows':[1,2]}:raise RuntimeError('Named-target PITR did not restore exact pre-delete rows')
        if sql(good,'select system_identifier from pg_control_system();')!=system:raise RuntimeError('Physical restore lineage differs')
        remove_container(good,scope);names.remove(good)
        failures={}
        # Independent copies: never corrupt the real base or WAL archive.
        helper('cp -a /backup/base/. /data/; rm /data/PG_VERSION',[(backup,'/backup',False),(incomplete,'/data',True)])
        try:
            helper('pg_verifybackup /data',[(incomplete,'/data',False)])
        except RuntimeError:
            if 'PG_VERSION' not in (runtime/'last-command-error.log').read_text():raise
            failures['incomplete_base_backup_rejected']=True
        else:raise RuntimeError('Incomplete base backup incorrectly accepted')
        helper('cp -a /archive/. /bad/; chown -R 70:70 /bad; dd if=/dev/zero of=/bad/'+wal+' bs=1048576 count=16',[(archive,'/archive',False),(badarchive,'/bad',True)])
        empty=volume('emptywal');helper('chown 70:70 /empty',[(empty,'/empty',True)])
        for kind,destination,wal_volume in (('missing',missing,empty),('corrupt',corrupt,badarchive)):
            clone(destination);name=start(kind,destination,wal_volume,target=target)
            accepted=False;writable=False;deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                row=json.loads(manage.docker('inspect',name))[0]
                if not row['State']['Running']:break
                try:
                    result=json.loads(sql(name,"select json_build_object('recovery',pg_is_in_recovery(),'pause',pg_get_wal_replay_pause_state());"))
                    if result.get('recovery') is False:writable=True;break
                    if result.get('pause')=='paused':accepted=True;break
                except RuntimeError:pass
                time.sleep(0.5)
            result=subprocess.run(manage.DOCKER+['logs','--tail','50',name],capture_output=True,timeout=10,
                env={'PATH':os.defpath,'HOME':str(Path.home())})
            if result.returncode:raise RuntimeError('PITR diagnostic transport failed')
            log=(result.stdout+result.stderr).decode(errors='replace')
            if row['State'].get('OOMKilled') or not any(text in log for text in (
                    'recovery ended before configured recovery target was reached','invalid magic number',
                    'incorrect checksum','could not restore file')):
                raise RuntimeError('PITR negative probe failed for an unverified reason')
            manage.private_write(kind+'-recovery.log',log)
            # Docker logs may place stderr outside stdout; database acceptance
            # itself is the invariant, not a synthetic log success message.
            if accepted or writable:raise RuntimeError('Invalid archive reached a recovery acceptance/writable state')
            failures[kind+'_archive_cannot_accept_target']=True
            remove_container(name,scope);names.remove(name)
        report={'scope':'isolated synthetic physical base backup and named-target WAL recovery',
            'source_system_identifier':system,'target_lsn':lsn,'required_wal':wal,'base_backup_verified':True,
            'target_rows':[1,2],'source_rows_after_delete':[2,3],'target_recovery_paused':True,
            'failures':failures,'elapsed_seconds':round(time.monotonic()-started,3),
            'retained_volumes':volumes,'production_modified':False,
            'limitations':['same VM','not production WAL configuration','not continuous off-host archiving','not PITR application/Auth/Storage acceptance','no promotion/HA/quorum/RPO/RTO claim']}
        manage.private_write('result.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report,sort_keys=True))
    finally:
        for name in names:remove_container(name,scope)
        manage.RUNTIME=previous


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('INSPECT','REHEARSE'),nargs='?',default='INSPECT')
    main(parser.parse_args().mode)
