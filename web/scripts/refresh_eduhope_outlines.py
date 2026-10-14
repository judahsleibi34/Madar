#!/usr/bin/env python3
"""Owner decisions of 2026-10-13 for EduHope lessons; dry-run by default.

1. Unpublish the demo lessons whose content no longer matches their new titles
   (Level 4 topic 1 and Level 7 topic 1) until real content arrives.
2. Regenerate the 79 draft outline text blocks with the approved topic titles and
   their Level/CEFR. Outlines stay unpublished and "Draft — pending owner approval".
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_eduhope_seed import Importer, PACKAGE, PRODUCTION_API, PRODUCTION_ORIGIN, PRODUCTION_FOLDER  # noqa: E402
from rename_eduhope_topics import DRAFT, topic_places  # noqa: E402

UNPUBLISH = ['course.level-4.topic-1', 'course.level-7.topic-1']


def outline(title, level, cefr):
    return (f'{title} — Level {level} · {cefr}\n\n{DRAFT}\n\n'
            'Topic structure: real-life situation; short dialogue; listen; transcript; understand; useful expressions; '
            'vocabulary; Listen & Match with Pictures; communication practice; Speak Now.\n\n'
            'This topic is not published to learners. Its dialogue, audio and pictures will be added after the owner approves the script and media.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-tenant', type=int, required=True)
    parser.add_argument('--owner-email', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    importer = Importer(argparse.Namespace(target_tenant=args.target_tenant, owner_email=args.owner_email, destination='production', apply=args.apply,
                                           api=PRODUCTION_API, origin=PRODUCTION_ORIGIN, cookies=PRODUCTION_FOLDER / 'owner-cookies.json',
                                           local_env=None, media_root=PRODUCTION_FOLDER / 'assets', evidence=PRODUCTION_FOLDER / 'seed'))
    topic_map = json.loads((PACKAGE / 'topic-map.draft.json').read_text())
    cefr = {level['level']: level['cefr'] for level in topic_map['levels']}
    places, titles = topic_places(topic_map)
    course = importer.journal['course']['id']
    base = f'/elearning/courses/{course}'
    structure = importer.call('GET', base + '/structure')
    lessons = {row['id']: row for section in structure['sections'] for row in section['lessons']}
    unpublish = [lessons[importer.journal[key]['id']] for key in UNPUBLISH if lessons[importer.journal[key]['id']]['status'] == 'published']
    outlines = []
    for key, (level, number) in places.items():
        block = importer.journal.get('outline.' + key)
        if block:
            outlines.append((importer.journal[key]['id'], block['id'], titles[(level, number)], level))
    print(json.dumps({'mode': 'apply' if args.apply else 'dry-run', 'unpublish': [row['name'] for row in unpublish], 'outlines': len(outlines)},
                     ensure_ascii=False, indent=2))
    if not args.apply:
        return
    for lesson in unpublish:
        structure = importer.call('POST', base + '/structure/commands', json={'action': 'update_lesson', 'entity_id': lesson['id'], 'expected_revision': structure['revision'],
                                                                              'payload': {'name': lesson['name'], 'description': DRAFT, 'status': 'draft'}})
    for lesson_id, block_id, title, level in outlines:
        path = f'{base}/lessons/{lesson_id}/content'
        revision = importer.call('GET', path)['revision']
        importer.call('POST', path + '/commands', json={'action': 'update', 'entity_id': block_id, 'expected_revision': revision,
                                                        'payload': {'type': 'text', 'title': 'Editorial draft outline',
                                                                    'content': {'version': 1, 'body': outline(title, level, cefr[level])}}})
    print(f'Unpublished {len(unpublish)} demo lessons; regenerated {len(outlines)} draft outlines.')


if __name__ == '__main__':
    main()
