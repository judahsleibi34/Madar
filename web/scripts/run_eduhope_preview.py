#!/usr/bin/env python3
"""Resume the retained local preview without migrations, import or resets."""
import argparse,json,os,socket,subprocess,time
from pathlib import Path
from urllib.parse import urlsplit
import psycopg
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[2]
PRIVATE=ROOT/'web/.eduhope-preview.local'
MARKER='madar-eduhope-local-preview-v1'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start',action='store_true');args=parser.parse_args()
    cfg=PRIVATE/'backend.env';values=dotenv_values(cfg);uri=urlsplit(values.get('SUPABASE_DB_URL',''))
    if values.get('APP_ENV')!='development' or uri.hostname!='127.0.0.1' or uri.port!=54322 or uri.path!='/madar_eduhope_preview_144':raise RuntimeError('Retained local144 configuration required')
    if cfg.stat().st_mode & 0o077 or PRIVATE.stat().st_mode & 0o077:raise RuntimeError('Private configuration must be0600 in0700 directory')
    with psycopg.connect(values['SUPABASE_DB_URL']) as db:
        db.execute('set transaction read only')
        assert db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0]==MARKER
        assert db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0]==144
    for name in ['auth','rest','storage','kong']:
        record=json.loads(subprocess.check_output(['docker','inspect','madar-eduhope-'+name]))[0]
        if record['Config']['Labels'].get('madar.preview')!='eduhope':raise RuntimeError('Unmarked provider service')
        if args.start and not record['State']['Running']:subprocess.run(['docker','start',record['Id']],check=True,stdout=subprocess.DEVNULL)
    commands={
        'backend':(8010,[str(ROOT/'web/backend/madar_env/bin/uvicorn'),'app:app','--host','127.0.0.1','--port','8010'],ROOT/'web/backend'),
        'frontend':(5180,['npm','run','dev','--','--host','127.0.0.1','--port','5180','--strictPort'],ROOT/'web/frontend'),
    }
    commands['notifications']=(8098,[str(ROOT/'web/backend/madar_env/bin/python'),'-m','workers.notification_worker'],ROOT/'web/backend')
    env={**os.environ, 'MADAR_ENV_FILE':str(cfg),'MADAR_ENV_OVERRIDE':'false','EMAIL_CHANNEL_ENABLED':'false','WEB_PUSH_ENABLED':'false','NOTIFICATION_WORKER_ENABLED':'true','NOTIFICATION_WORKER_HEALTH_HOST':'127.0.0.1','NOTIFICATION_WORKER_HEALTH_PORT':'8098','VITE_API_URL':'/api','VITE_DEV_PROXY_TARGET':'http://127.0.0.1:8010'}
    for name,(port,command,cwd) in commands.items():
        with socket.socket() as probe:busy=probe.connect_ex(('127.0.0.1',port))==0
        if not busy and args.start:
            log=PRIVATE/(name+'.log');fd=os.open(log,os.O_CREAT|os.O_APPEND|os.O_WRONLY,0o600)
            with os.fdopen(fd,'ab') as output:
                child=subprocess.Popen(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            (PRIVATE/(name+'.pid')).write_text(str(child.pid)+'\n')
        print(name+': '+('already listening' if busy else 'started' if args.start else 'stopped'))
    print('Public http://127.0.0.1:5180/academy/eduhope-local; credentials retained privately in '+str(PRIVATE))
    print('No migrations/import/production operation was performed.')
if __name__=='__main__':main()
