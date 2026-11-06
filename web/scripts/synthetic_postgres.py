"""Identity checks for disposable synthetic PostgreSQL rehearsals (no authority)."""
import argparse
import json
import re
import subprocess
import uuid

OWNER_LABEL = 'madar.rehearsal.owner'


def docker(*args):
    return subprocess.run(['docker', *args], check=True, capture_output=True, text=True).stdout


def observe(name, owner, purpose, image):
    if str(uuid.UUID(owner)) != owner or name != 'madar-synthetic-' + owner:
        raise ValueError('synthetic_postgres_scope_invalid')
    # Missing containers are idempotent cleanup, but daemon failures must surface.
    ids = docker('container', 'ls', '-aq', '--no-trunc', '--filter', 'name=^/' + name + '$').split()
    if not ids:
        return None
    if len(ids) != 1 or not re.fullmatch('[0-9a-f]{64}', ids[0]):
        raise ValueError('synthetic_postgres_identity_ambiguous')
    records = json.loads(docker('container', 'inspect', ids[0]))
    if len(records) != 1:
        raise ValueError('synthetic_postgres_identity_ambiguous')
    record = records[0]
    labels = record['Config'].get('Labels') or {}
    if (record['Id'] != ids[0] or record['Name'] != '/' + name
            or record['Config']['Image'] != image
            or labels.get(OWNER_LABEL) != owner
            or labels.get('madar.rehearsal') != purpose):
        raise ValueError('synthetic_postgres_ownership_refused')
    return record


def port(record):
    if not record or not record['State']['Running']:
        raise ValueError('synthetic_postgres_not_running')
    bindings = record['NetworkSettings']['Ports'].get('5432/tcp')
    if (not isinstance(bindings, list) or len(bindings) != 1
            or bindings[0]['HostIp'] != '127.0.0.1'
            or not re.fullmatch('[1-9][0-9]{0,4}', bindings[0]['HostPort'])
            or not 1 <= int(bindings[0]['HostPort']) <= 65535):
        raise ValueError('synthetic_postgres_loopback_binding_invalid')
    return bindings[0]['HostPort']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('identity', 'port', 'cleanup'))
    for key in ('name', 'owner', 'purpose', 'image'):
        parser.add_argument(key)
    args = parser.parse_args()
    record = observe(args.name, args.owner, args.purpose, args.image)
    if args.action == 'cleanup':
        if record:
            # Delete only the authenticated immutable ID, never a reusable name.
            docker('container', 'rm', '-f', record['Id'])
    elif args.action == 'port':
        print(port(record))
    elif record:
        print(record['Id'])
    else:
        raise ValueError('synthetic_postgres_missing')


if __name__ == '__main__':
    main()
