#!/usr/bin/env python3
"""Turn the demo lessons' plain vocabulary/expression text into structured EH cards.

Dry-run by default. With --apply it updates only the existing "Useful expressions"
and "Words and meanings" text blocks of the authored demo lessons on the given
tenant, using teaching.json's structured data; the plain-text body is kept as the
fallback. Back up the lesson content first (--backup-dir) — this is lesson
content, so run it only with the owner's approval.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_eduhope_seed import Importer, PACKAGE, PRODUCTION_API, PRODUCTION_ORIGIN, PRODUCTION_FOLDER  # noqa: E402


def components(lesson):
    vocabulary = {'kind': 'vocabulary', 'items': [{'word': v['word'], 'meaning': v['meaning'], 'arabic': v.get('arabic', ''), 'example': v.get('example', ''),
                                                   'pronunciation': '', 'stress': ''} for v in lesson['vocabulary']]}
    expressions = {'kind': 'expressions', 'items': [{'expression': e, 'meaning': '', 'arabic': '', 'example': ''} for e in lesson['expressions']]}
    return {'vocabulary': vocabulary, 'expressions': expressions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-tenant', type=int, required=True)
    parser.add_argument('--owner-email', required=True)
    parser.add_argument('--backup-dir', type=Path, default=PACKAGE / 'backups' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    importer = Importer(argparse.Namespace(target_tenant=args.target_tenant, owner_email=args.owner_email, destination='production', apply=args.apply,
                                           api=PRODUCTION_API, origin=PRODUCTION_ORIGIN, cookies=PRODUCTION_FOLDER / 'owner-cookies.json',
                                           local_env=None, media_root=PRODUCTION_FOLDER / 'assets', evidence=PRODUCTION_FOLDER / 'seed'))
    lessons = json.loads((PACKAGE / 'teaching.json').read_text())['authored_demonstration_lessons']
    course = importer.journal['course']['id']
    plan = []
    for lesson in lessons:
        lesson_id = importer.journal[lesson['key']]['id']
        for part, block_key in (('expressions', f"teaching.{lesson['key']}.expressions"), ('vocabulary', f"teaching.{lesson['key']}.vocabulary")):
            if block_key in importer.journal:
                plan.append((lesson_id, importer.journal[block_key]['id'], components(lesson)[part], lesson['title']))
    print(json.dumps({'mode': 'apply' if args.apply else 'dry-run', 'blocks': len(plan), 'backup_dir': str(args.backup_dir)}, indent=2))
    if not args.apply:
        return
    args.backup_dir.mkdir(parents=True, exist_ok=True)
    for lesson_id, block_id, component, _ in plan:
        path = f'/elearning/courses/{course}/lessons/{lesson_id}/content'
        content = importer.call('GET', path)
        (args.backup_dir / f'lesson-{lesson_id}.json').write_text(json.dumps(content, ensure_ascii=False, indent=2))
        block = next(item for item in content['blocks'] if item['id'] == block_id)
        importer.call('POST', path + '/commands', json={'action': 'update', 'entity_id': block_id, 'expected_revision': content['revision'],
                                                        'payload': {'type': 'text', 'title': block.get('title') or '', 'content': {**block['content'], 'component': component}}})
    print(f'Converted {len(plan)} blocks; backups in {args.backup_dir}')


if __name__ == '__main__':
    main()
