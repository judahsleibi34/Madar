#!/usr/bin/env python3
"""Apply the owner-approved draft topic map to EduHope lesson names; dry-run by default.

Uses the importer's verified owner session and journal (tenant, owner email and
schema checks included). Only lesson names and descriptions change; publication
status, content and order are left as they are. Every topic is labelled
"Draft — pending owner approval" and stays editable in the owner area.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from import_eduhope_seed import Importer, PACKAGE, PRODUCTION_API, PRODUCTION_ORIGIN, PRODUCTION_FOLDER  # noqa: E402

DRAFT = 'Draft — pending owner approval.'
# The imported course has 9 topics per Level and 8 in Level 10; the approved map
# has 8, 8, 9 x 7, 10. The last (draft, unpublished) topic of Levels 1 and 2
# moves to Level 10 as topics 9 and 10; everything else keeps its place.
MOVED = {'course.level-1.topic-9': (10, 9), 'course.level-2.topic-9': (10, 10)}


def topic_places(topic_map):
    """Journal topic key -> (level, number) in the approved map, plus titles."""
    places = {}
    for level in range(1, 11):
        for number in range(1, 10 if level < 10 else 9):
            key = f'course.level-{level}.topic-{number}'
            places[key] = MOVED.get(key, (level, number))
    titles = {(level['level'], topic['number']): topic['title'] for level in topic_map['levels'] for topic in level['topics']}
    if sorted(places.values()) != sorted(titles):
        raise RuntimeError('Topic positions do not match the approved map')
    return places, titles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-tenant', type=int, required=True)
    parser.add_argument('--owner-email', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    importer_args = argparse.Namespace(target_tenant=args.target_tenant, owner_email=args.owner_email, destination='production', apply=args.apply,
                                       api=PRODUCTION_API, origin=PRODUCTION_ORIGIN, cookies=PRODUCTION_FOLDER / 'owner-cookies.json',
                                       local_env=None, media_root=PRODUCTION_FOLDER / 'assets', evidence=PRODUCTION_FOLDER / 'seed')
    importer = Importer(importer_args)
    topic_map = json.loads((PACKAGE / 'topic-map.draft.json').read_text())
    places, titles = topic_places(topic_map)
    course = importer.journal['course']['id']
    base = f'/elearning/courses/{course}/structure'
    structure = importer.call('GET', base)
    lessons = {row['id']: {**row, 'section_id': section['id']} for section in structure['sections'] for row in section['lessons']}
    level_sections = {level: importer.journal[f'course.level-{level}']['id'] for level in range(1, 11)}
    changes = []
    for key, (level, number) in places.items():
        lesson = lessons.get((importer.journal.get(key) or {}).get('id'))
        if not lesson:
            raise RuntimeError('Topic missing from the live course: ' + key)
        if key in MOVED and lesson['status'] != 'draft':
            raise RuntimeError('Only unpublished draft topics are moved: ' + key)
        title, section = titles[(level, number)], level_sections[level]
        if lesson['name'] != title or (lesson.get('description') or '') != DRAFT or lesson['section_id'] != section:
            changes.append((key, lesson, title, section))
    print(json.dumps({'mode': 'apply' if args.apply else 'dry-run', 'topics': len(places), 'to_update': len(changes),
                      'moves': [{'topic': key, 'to': f'Level {places[key][0]} topic {places[key][1]}'} for key in MOVED],
                      'sample': [{'from': lesson['name'], 'to': title} for _, lesson, title, _ in changes[:5]]}, ensure_ascii=False, indent=2))
    if not args.apply:
        return
    for key in MOVED:
        lesson = lessons[importer.journal[key]['id']]
        if lesson['section_id'] != level_sections[10]:
            structure = importer.call('POST', base + '/commands', json={'action': 'move_lesson', 'entity_id': lesson['id'],
                                                                         'expected_revision': structure['revision'], 'payload': {'section_id': level_sections[10]}})
    for key, lesson, title, _ in changes:
        payload = {'name': title, 'description': DRAFT, 'status': lesson['status']}
        structure = importer.call('POST', base + '/commands', json={'action': 'update_lesson', 'entity_id': lesson['id'],
                                                                     'expected_revision': structure['revision'], 'payload': payload})
    print(f'Renamed {len(changes)} topics; statuses unchanged.')


if __name__ == '__main__':
    main()
