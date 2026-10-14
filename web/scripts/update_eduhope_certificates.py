#!/usr/bin/env python3
"""Give EduHope's certificate templates the book's exact names; dry-run by default.

Renames the five CEFR templates to "A1/A2/B1/B2/C1 English Speaking Certificate"
and creates the "Complete English Speaking Course Certificate" template. It does
not enable or assign certificates (an owner decision) and issues nothing.
Templates are saved through the owner API with revision checks; the current
designs are backed up first.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

LEVELS = ['A1', 'A2', 'B1', 'B2', 'C1']
COMPLETE = 'Complete English Speaking Course Certificate'


def cefr_design(level):
    # Certificate names are from the book document; the statement is owner-approval copy.
    return {'name': f'{level} English Speaking Certificate', 'title': f'{level} English Speaking Certificate', 'subtitle': f'CEFR {level}',
            'body': 'This certifies that {{learner_name}} has successfully completed the ' + level + ' Levels and the ' + level + ' Final Exam of {{course_name}}.',
            'issuer_name': 'EduHope'}


def complete_design():
    return {'name': COMPLETE, 'title': COMPLETE, 'subtitle': 'A1 – C1',
            'body': 'This certifies that {{learner_name}} has successfully completed all ten Levels of {{course_name}}.', 'issuer_name': 'EduHope'}


def main():
    from import_eduhope_seed import Importer, PACKAGE, PRODUCTION_API, PRODUCTION_ORIGIN, PRODUCTION_FOLDER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-tenant', type=int, required=True)
    parser.add_argument('--owner-email', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    importer = Importer(argparse.Namespace(target_tenant=args.target_tenant, owner_email=args.owner_email, destination='production', apply=args.apply,
                                           api=PRODUCTION_API, origin=PRODUCTION_ORIGIN, cookies=PRODUCTION_FOLDER / 'owner-cookies.json',
                                           local_env=None, media_root=PRODUCTION_FOLDER / 'assets', evidence=PRODUCTION_FOLDER / 'seed'))
    listing = importer.call('GET', '/elearning/certificate-templates')
    templates = {row['id']: row for row in listing.get('templates', listing.get('items', []))}
    plan = []
    for level in LEVELS:
        entry = importer.journal.get('credential.' + level)
        row = templates.get(entry['id']) if entry else None
        if row and row['design'].get('title') != cefr_design(level)['title']:
            plan.append(('rename', row, {**{k: v for k, v in row['design'].items() if k in ('signer_name', 'signer_title', 'logo_url', 'signature_url')}, **cefr_design(level)}))
    if not any(row['design'].get('title') == COMPLETE for row in templates.values()):
        plan.append(('create', None, complete_design()))
    print(json.dumps({'mode': 'apply' if args.apply else 'dry-run', 'changes': [{'action': action, 'from': (row or {}).get('design', {}).get('title'), 'to': design['title']} for action, row, design in plan]},
                     ensure_ascii=False, indent=2))
    if not args.apply or not plan:
        return
    backup = PACKAGE / 'backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-certificates')
    backup.mkdir(parents=True, exist_ok=True)
    (backup / 'certificate-templates.json').write_text(json.dumps(listing, ensure_ascii=False, indent=2))
    for action, row, design in plan:
        if action == 'rename':
            importer.call('PUT', f"/elearning/certificate-templates/{row['id']}", json={'design': design, 'expected_revision': row['revision'], 'status': row.get('status', 'active')})
        else:
            result = importer.call('POST', '/elearning/certificate-templates', json={'design': design, 'status': 'active'})
            importer.journal['credential.complete'] = {'id': result.get('saved_id')}; importer.checkpoint()
    print(f'Updated {len(plan)} templates; backup in {backup}')


if __name__ == '__main__':
    main()
