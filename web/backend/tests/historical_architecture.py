"""Explicit native-fixture loader for the superseded architecture history.

Never imported by runtime code. This does not grant operational admission.
"""
from pathlib import Path
from deployment.lib.migration_executor import Migration,MigrationManifest


def manifest(release,root,contract):
    rows=release.source_manifest(root)['migrations']
    return MigrationManifest(contract['candidate']['source_sha'],tuple(Migration(
        r['number'],Path(root)/'web/database/historical-architecture-146-150'/Path(r['path']).name,
        r['sha256'],r['from_schema'],r['to_schema'],r['compatibility']) for r in rows),coordinated=True)
