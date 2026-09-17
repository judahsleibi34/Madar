#!/usr/bin/env python3
"""Authenticated checkout/COD/inventory/loyalty proof on a disposable local DB."""
from pathlib import Path
import os
import subprocess
import time
import uuid

WEB = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = 'postgres:17-alpine@sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73'

def main() -> None:
    name = 'madar-checkout-synthetic-' + uuid.uuid4().hex[:12]
    created = False
    try:
        result = subprocess.run(['docker','run','--detach','--name',name,
            '--label','madar.rehearsal=authenticated-checkout','--network','none',
            '--tmpfs','/var/lib/postgresql/data:rw,noexec,nosuid,size=1g',
            '--env','POSTGRES_HOST_AUTH_METHOD=trust',POSTGRES_IMAGE],capture_output=True,text=True)
        if result.returncode:raise RuntimeError('disposable_checkout_database_start_failed')
        created = True
        for _ in range(60):
            if subprocess.run(['docker','exec',name,'pg_isready','-U','postgres'],capture_output=True).returncode == 0:break
            time.sleep(1)
        else:raise RuntimeError('disposable_checkout_database_not_ready')
        args = ['docker','run','--rm','--network','container:'+name]
        values = {'APP_ENV':'test','SUPABASE_URL':'http://127.0.0.1:54321',
            'SUPABASE_ANON_KEY':'madar-ci-placeholder-anon-not-a-secret',
            'SUPABASE_SERVICE_KEY':'madar-ci-placeholder-service-not-a-secret',
            'PYGWALKER_TELEMETRY_ENABLED':'false',
            'MADAR_CHECKOUT_TEST_DATABASE_URL':'postgresql://postgres@127.0.0.1:5432/postgres'}
        for key,value in values.items():args += ['--env',key+'='+value]
        args += ['--volume',str(WEB/'database')+':/database:ro',
            os.getenv('BACKEND_TEST_IMAGE','madar-backend-test'),'python','-m','unittest',
            'tests.test_authenticated_checkout','-v']
        result = subprocess.run(args,capture_output=True,text=True)
        for line in result.stderr.splitlines():
            if line.startswith(('Ran ','FAILED','OK','FAIL:','ERROR:')):print(line)
        if result.returncode:raise RuntimeError('authenticated_checkout_rehearsal_failed')
        print('Authenticated checkout/COD/inventory/loyalty replay rehearsal PASS')
    finally:
        if created:
            result = subprocess.run(['docker','rm','--force',name],capture_output=True)
            if result.returncode:raise RuntimeError('disposable_checkout_database_cleanup_failed')

if __name__ == '__main__':main()
