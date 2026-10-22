"""Source-only reconciliation checks; no controller registration or authority."""
import hashlib
import json
from pathlib import Path


def validated_entries(root):
    root=Path(root)
    lock=json.loads((root/'web/deployment/migration-history-reconciliation.json').read_bytes())
    for path,checksum in (lock['published_main']|lock['historical']).items():
        source=root/path
        if (not path.startswith(('web/database/migrations/','web/supabase/migrations/',
                'web/database/historical-architecture-146-150/','web/supabase/historical-architecture-146-150/'))
                or not source.resolve().is_relative_to(root.resolve())
                or source.resolve()!=source.absolute() or source.is_symlink()
                or hashlib.sha256(source.read_bytes()).hexdigest()!=checksum):
            raise ValueError('reconciled_published_history_changed: '+path)
    manifest=root/'web/deployment/releases/migrations-157-160-reconciled.json'
    if hashlib.sha256(manifest.read_bytes()).hexdigest()!=lock['forward_manifest_sha256']:
        raise ValueError('reconciled_forward_manifest_changed')
    raw=json.loads(manifest.read_bytes())
    if (raw['execution_status']!='blocked_pending_protected_controller_reconciliation'
            or [r['number'] for r in raw['migrations']]!=[157,158,159,160]):
        raise ValueError('reconciled_forward_contract_changed')
    for row in raw['migrations']:
        path=root/row['path'];mirror=root/'web/supabase/migrations'/path.name
        if (row['from_schema']!=row['number']-1 or row['to_schema']!=row['number']
                or path.is_symlink() or mirror.is_symlink()
                or path.read_bytes()!=mirror.read_bytes()
                or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']):
            raise ValueError('reconciled_forward_sql_changed')
    return raw['migrations']


if __name__=='__main__':
    validated_entries(Path(__file__).resolve().parents[2])
    print('Published main, historical architecture and reconciled157–160 checksums PASS; execution remains blocked')
