#!/usr/bin/env python3
"""Seed/reset only the isolated local Docker test tenant. Never uses web/.env."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5
from dotenv import dotenv_values
import psycopg
from elearning_demo_data import COURSES, MARKER, PROGRESS_TARGETS

WEB = Path(__file__).resolve().parents[1]
NAMESPACE = uuid5(NAMESPACE_URL, "madar:development:elearning-demo:v1")


def stable_id(tenant, key):
    return uuid5(NAMESPACE, f"{tenant}:{key}")


def local_configuration():
    if os.getenv("APP_ENV", "").lower() in {"prod", "production"}:
        raise RuntimeError("Development seed refuses production APP_ENV")
    values = dotenv_values(WEB / ".env.database.local")
    db, api = urlsplit(values.get("SUPABASE_DB_URL", "")), urlsplit(values.get("SUPABASE_URL", ""))
    if values.get("APP_ENV") != "development" or db.hostname != "127.0.0.1" or db.port != 54322 or db.path != "/postgres" or api.hostname != "127.0.0.1" or api.port != 54321:
        raise RuntimeError("Requires the generated local Docker environment on ports 54321/54322")
    endpoint = subprocess.run(["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"], capture_output=True, text=True, check=True).stdout.strip()
    if not endpoint.startswith("unix://") or (os.getenv("DOCKER_HOST") and not os.getenv("DOCKER_HOST").startswith("unix://")):
        raise RuntimeError("Refusing remote Docker")
    inspected = subprocess.run(["docker", "inspect", "supabase_db_web"], capture_output=True, text=True, check=True)
    container = json.loads(inspected.stdout)[0]
    bindings = container["NetworkSettings"]["Ports"].get("5432/tcp") or []
    if not container["State"]["Running"] or not any(port["HostPort"] == "54322" for port in bindings):
        raise RuntimeError("Local Supabase Docker database is not running on the expected port")
    if not values.get("MADAR_TEST_EMAIL"):
        raise RuntimeError("Configure the current local test account first")
    return values


def resolve_owner(db, email):
    row = db.execute("select u.tenant_id,u.id from public.users u join public.tenant_memberships m on(m.tenant_id,m.user_id,m.auth_id)=(u.tenant_id,u.id,u.auth_id) join public.tenants t on t.tenant_id=u.tenant_id and t.lifecycle_state='active' where lower(u.email)=lower(%s) and u.account_status='active' and m.status='active' and m.role in ('owner','admin')", (email,)).fetchone()
    if not row: raise RuntimeError("Local test account needs an active owner/admin membership")
    if db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0] not in {121, 122, 123, 124}:
        raise RuntimeError("Apply the verified local schema 121, 122, 123 or 124 before seeding")
    return row


def expected_ids(tenant):
    courses, sections, lessons = set(), set(), set()
    for key, _name, _status, _access, _description, parts, _count in COURSES:
        courses.add(stable_id(tenant, key))
        for index, (_section, names) in enumerate(parts):
            sections.add(stable_id(tenant, f"{key}/section/{index}"))
            for position in range(len(names)): lessons.add(stable_id(tenant, f"{key}/section/{index}/lesson/{position}"))
    return courses, sections, lessons


def validate_owned_seed(db, tenant, owner):
    course_ids, section_ids, lesson_ids = expected_ids(tenant)
    for table, ids, parent in (("elearning_courses", course_ids, None), ("elearning_sections", section_ids, course_ids), ("elearning_lessons", lesson_ids, course_ids)):
        # Table names come only from the fixed tuple above, never CLI input.
        rows = db.execute(f"select id,tenant_id,created_by,description from public.{table} where id=any(%s)" + (" or course_id=any(%s)" if parent else ""), (list(ids), list(parent)) if parent else (list(ids),)).fetchall()
        for identity, row_tenant, creator, description in rows:
            if identity not in ids or row_tenant != tenant or creator != owner or not description.startswith(MARKER):
                raise RuntimeError("Seed ID collision or non-seed course content found; refusing overwrite/cleanup")
    learner_ids = [stable_id(tenant, f"learner/{i:02}") for i in range(1,31)]
    rows = db.execute("select id,tenant_id,created_by,email from public.elearning_learners where id=any(%s)", (learner_ids,)).fetchall()
    for identity, scope, creator, email in rows:
        index = learner_ids.index(identity) + 1
        if scope != tenant or creator != owner or email != f"learner{index:02}.tenant{tenant}@madar-demo.invalid":
            raise RuntimeError("Seed learner collision; refusing overwrite/cleanup")
    expected_enrollments = {stable_id(tenant, f"{key}/enrollment/{i:02}") for key,*rest in COURSES for i in range(1,rest[-1]+1)}
    rows = db.execute("select id,tenant_id,created_by from public.elearning_enrollments where course_id=any(%s) or learner_id=any(%s) or id=any(%s)", (list(course_ids),learner_ids,list(expected_enrollments))).fetchall()
    if any(identity not in expected_enrollments or scope != tenant or creator != owner for identity,scope,creator in rows):
        raise RuntimeError("Non-seed enrollments found; refusing overwrite/cleanup")
    return list(course_ids), learner_ids, list(expected_enrollments)


def cleanup(db, tenant, owner):
    courses, learners, enrollments = validate_owned_seed(db, tenant, owner)
    db.execute("delete from public.elearning_lesson_completions where tenant_id=%s and enrollment_id=any(%s)", (tenant,enrollments))
    db.execute("delete from public.elearning_enrollments where tenant_id=%s and id=any(%s)", (tenant,enrollments))
    db.execute("delete from public.elearning_lessons where tenant_id=%s and course_id=any(%s)", (tenant,courses))
    db.execute("delete from public.elearning_sections where tenant_id=%s and course_id=any(%s)", (tenant,courses))
    db.execute("delete from public.elearning_courses where tenant_id=%s and id=any(%s)", (tenant,courses))
    db.execute("delete from public.elearning_learners where tenant_id=%s and id=any(%s)", (tenant,learners))


def seed(db, tenant, owner):
    courses, _learners, _enrollments = validate_owned_seed(db, tenant, owner)
    # Serialize against structure/participation mutations and all seed invocations.
    db.execute("select id from public.elearning_courses where tenant_id=%s and id=any(%s) order by id for update", (tenant,courses))
    for i in range(1,31):
        db.execute("insert into public.elearning_learners(id,tenant_id,name,email,created_by) values(%s,%s,%s,%s,%s) on conflict(id) do update set name=excluded.name,status='active',revision=elearning_learners.revision+1", (stable_id(tenant,f"learner/{i:02}"),tenant,f"Test Learner {i:02}",f"learner{i:02}.tenant{tenant}@madar-demo.invalid",owner))
    for key,name,status,access,description,parts,count in COURSES:
        course = stable_id(tenant,key)
        db.execute("insert into public.elearning_courses(id,tenant_id,name,description,status,access_type,created_by) values(%s,%s,%s,%s,%s,%s,%s) on conflict(id) do update set name=excluded.name,description=excluded.description,status=excluded.status,access_type=excluded.access_type,revision=elearning_courses.revision+1,structure_revision=elearning_courses.structure_revision+1", (course,tenant,name,f"{MARKER} {description}",status,access,owner))
        ordered = []
        for index,(section_name,names) in enumerate(parts):
            section = stable_id(tenant,f"{key}/section/{index}")
            section_status = 'draft' if status == 'draft' and index >= 2 else 'published'
            db.execute("insert into public.elearning_sections(id,tenant_id,course_id,name,description,status,position,created_by) values(%s,%s,%s,%s,%s,%s,%s,%s) on conflict(id) do update set name=excluded.name,description=excluded.description,status=excluded.status,position=excluded.position,archived_at=null", (section,tenant,course,section_name,f"{MARKER} Practice skills in {section_name.lower()}.",section_status,index,owner))
            for position,lesson_name in enumerate(names):
                lesson = stable_id(tenant,f"{key}/section/{index}/lesson/{position}")
                lesson_status = 'draft' if status=='draft' and (section_status=='draft' or position==len(names)-1) else 'published'
                db.execute("insert into public.elearning_lessons(id,tenant_id,course_id,section_id,name,description,status,position,created_by) values(%s,%s,%s,%s,%s,%s,%s,%s,%s) on conflict(id) do update set section_id=excluded.section_id,name=excluded.name,description=excluded.description,status=excluded.status,position=excluded.position,archived_at=null", (lesson,tenant,course,section,lesson_name,f"{MARKER} Guided practice: {lesson_name.lower()}. Summary only; content has not been built.",lesson_status,position,owner))
                if lesson_status=='published' and section_status=='published' and status=='published': ordered.append(lesson)
        for index in range(1,count+1):
            # Overlapping ranges cover all thirty learners while preserving exact per-course counts.
            offset = {'english':0,'marketing':12,'safety':6}[key]
            learner_number = (index-1+offset)%30+1
            enrollment = stable_id(tenant,f"{key}/enrollment/{index:02}")
            learner = stable_id(tenant,f"learner/{learner_number:02}")
            source = 'free' if access=='free' else 'manual'
            db.execute("insert into public.elearning_enrollments(id,tenant_id,course_id,learner_id,access_source,created_by) values(%s,%s,%s,%s,%s,%s) on conflict(id) do update set status='active',access_source=excluded.access_source", (enrollment,tenant,course,learner,source,owner))
            db.execute("select public.manage_elearning_participation(%s,%s,%s,'enroll',%s::jsonb)", (tenant,course,owner,json.dumps({"learner_id":str(learner),"access_source":source})))
            db.execute("delete from public.elearning_lesson_completions where tenant_id=%s and enrollment_id=%s", (tenant,enrollment))
            completed = round(len(ordered)*PROGRESS_TARGETS[(index-1)%len(PROGRESS_TARGETS)]/100)
            # Sequential completion produces deliberately uneven section progress.
            for lesson in ordered[:completed]:
                db.execute("select public.manage_elearning_participation(%s,%s,%s,'complete_lesson',%s::jsonb)", (tenant,course,owner,json.dumps({'enrollment_id':str(enrollment),'lesson_id':str(lesson)})))
    verify(db, tenant)


def verify(db, tenant):
    summary = []
    for key,name,status,access,parts_description,parts,count in COURSES:
        course = stable_id(tenant,key)
        structure = db.execute("select public.get_elearning_structure(%s,%s)", (tenant,course)).fetchone()[0]
        progress = db.execute("select public.get_elearning_progress(%s,%s)", (tenant,course)).fetchone()[0]
        assert structure['section_count']==len(parts) and structure['lesson_count']==sum(len(names) for _,names in parts)
        assert progress['learner_count']==count
        for enrollment in progress['enrollments']:
            assert sum(part['completed_lessons'] for part in enrollment['sections'])==enrollment['completed_lessons']
            assert enrollment['completed_lessons']<=enrollment['total_lessons']
        summary.append({'name':name,'status':status,'access_type':access,'sections':structure['section_count'],'lessons':structure['lesson_count'],'learners':count,'average_progress':progress['average_progress']})
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cleanup',action='store_true',help='Remove only this seed; refuses courses with non-seed content')
    parser.add_argument('--verify',action='store_true',help='Read and validate the seeded records without changing them')
    args=parser.parse_args()
    config=local_configuration()
    with psycopg.connect(config['SUPABASE_DB_URL']) as db:
        tenant,owner=resolve_owner(db,config['MADAR_TEST_EMAIL'])
        db.execute('select pg_advisory_xact_lock(%s,%s)', (120,tenant))
        db.execute('select id from public.elearning_courses where tenant_id=%s and id=any(%s) order by id for update', (tenant,list(expected_ids(tenant)[0])))
        if args.cleanup:
            cleanup(db,tenant,owner)
            print(f'Removed only E-Learning demo records for local tenant {tenant}.')
        else:
            if not args.verify: seed(db,tenant,owner)
            print(json.dumps({'tenant_id':tenant,'courses':verify(db,tenant),'note':'Draft Leadership is intentionally unenrolled. Paid/private enrollments are manual assignments, not payments.'},indent=2))


if __name__=='__main__':
    try: main()
    except (RuntimeError,psycopg.Error,subprocess.SubprocessError,ValueError,AssertionError):
        print('Development seed failed safely; transaction rolled back. Check the local database, owner membership and seed ownership markers.',file=sys.stderr)
        sys.exit(1)
