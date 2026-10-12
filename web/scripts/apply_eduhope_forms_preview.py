#!/usr/bin/env python3
"""Apply the approved unselected144 only to the marked isolated EduHope preview."""
from pathlib import Path
from urllib.parse import urlsplit
import argparse
import hashlib
import json
import subprocess
import sys
from dotenv import dotenv_values
import psycopg

ROOT=Path(__file__).resolve().parents[2]
FOLDER=Path('/tmp/madar-eduhope-preview')


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--apply144',action='store_true');args=parser.parse_args()
    if not args.apply144:print('Dry-run: marked local preview143 →144 only; verified143 backup and pinned executor.');return
    values=dotenv_values(FOLDER/'backend.env');uri=urlsplit(values['SUPABASE_DB_URL'])
    assert values['APP_ENV']=='development' and uri.hostname=='127.0.0.1' and uri.port==54322 and uri.path=='/madar_eduhope_preview_143'
    with psycopg.connect(values['SUPABASE_DB_URL']) as db:
        db.execute('set transaction read only')
        assert db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0]=='madar-eduhope-local-preview-v1'
        version=db.execute("select schema_version from application_schema_state where contract_key='core'").fetchone()[0]
        assert version in {143,144}
    sys.path.insert(0,str(ROOT/'web'));sys.path.insert(0,str(ROOT/'web/scripts'))
    from forms_review_candidate import validated_entries
    from deployment.lib.migration_executor import MigrationManifest,LockedMigrationExecutor
    validated_entries(ROOT)
    manifest=MigrationManifest.load(ROOT/'web/deployment/releases/migrations-143-144-forms.json',ROOT)
    assert [item.number for item in manifest.migrations]==[144] and not manifest.accepts_schema(141) and not manifest.accepts_schema(142)
    backup=FOLDER/'backup143';backup.mkdir(mode=0o700,exist_ok=True)
    dump=backup/'schema143.dump';digest_file=backup/'sha256.json'
    if version==143:
        if dump.exists():raise RuntimeError('A prior143 backup exists; inspect it instead of overwriting recovery evidence')
        data=subprocess.check_output(['docker','exec','supabase_db_web','pg_dump','-U','postgres','-Fc','madar_eduhope_preview_143'])
        dump.write_bytes(data);dump.chmod(0o600);digest_file.write_text(json.dumps({'schema':143,'database':'madar_eduhope_preview_143','sha256':hashlib.sha256(data).hexdigest()}));digest_file.chmod(0o600)
    def verify(_):
        expected=json.loads(digest_file.read_text())
        assert expected['schema']==143 and hashlib.sha256(dump.read_bytes()).hexdigest()==expected['sha256']
        subprocess.run(['docker','exec','-i','supabase_db_web','pg_restore','--list'],input=dump.read_bytes(),stdout=subprocess.PIPE,check=True)
    result=LockedMigrationExecutor(connection_factory=lambda:psycopg.connect(values['SUPABASE_DB_URL']),manifest=manifest,state_file=backup/'execution144.json',backup_dir=backup,backup_verifier=verify).run()
    assert result['migrations'][0]['number']==144
    values.update(SCHEMA_COMPATIBLE_MIN='143',SCHEMA_COMPATIBLE_MAX='144',SCHEMA_TARGET_VERSION='144')
    path=FOLDER/'backend.env';path.write_text('\n'.join(key+'='+value for key,value in values.items() if value is not None)+'\n');path.chmod(0o600)
    print('Marked local preview144 ready; verified143 backup retained. Existing application141 and production untouched. Restart only the verified preview backend to load its approved compatibility range.')


if __name__=='__main__':main()
