#!/usr/bin/env python3
"""Import public EduHope content through canonical owner APIs; dry-run by default.

Apply currently requires the retained, marked local144 preview. Production
destination preparation is separate and grants no remote mutation authority.
"""
import argparse
import copy
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

import psycopg
from psycopg import sql
import requests
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[2]
PACKAGE=ROOT/'web/seed-data/eduhope'
MARKER='madar-eduhope-local-preview-v1'


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def resolve(value, mapping):
    if isinstance(value,dict):return {key:resolve(child,mapping) for key,child in value.items()}
    if isinstance(value,list):return [resolve(child,mapping) for child in value]
    if isinstance(value,str) and value.startswith('ref:'):
        if value[4:] not in mapping:raise ValueError('Unresolved logical reference: '+value)
        return mapping[value[4:]]
    return value


def website_fingerprint(schema):
    value=copy.deepcopy(schema);value.pop('seed_metadata',None)
    return fingerprint(value)


def private_json(path,value):
    path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as out:json.dump(value,out,ensure_ascii=False,indent=2)
    path.chmod(0o600)


class Importer:
    def __init__(self,args):
        self.args=args;self.env=dotenv_values(args.local_env)
        url=urlsplit(self.env['SUPABASE_DB_URL']);api=urlsplit(args.api)
        if self.env.get('APP_ENV')!='development' or url.hostname!='127.0.0.1' or url.port!=54322 or url.path!='/madar_eduhope_preview_144' or api.hostname!='127.0.0.1' or api.port!=8010:
            raise RuntimeError('Apply/read plan requires the retained isolated local144 context; remote destinations are not authorized')
        with psycopg.connect(self.env['SUPABASE_DB_URL']) as db:
            db.execute('set transaction read only')
            if db.execute("select shobj_description(oid,'pg_database') from pg_database where datname=current_database()").fetchone()[0]!=MARKER:raise RuntimeError('Preview marker mismatch')
            if db.execute("select schema_version from public.application_schema_state where contract_key='core'").fetchone()[0]!=144:raise RuntimeError('This content package requires compatible144; application141 is not a target')
        self.session=requests.Session()
        for key,value in json.loads(args.cookies.read_text()).items():self.session.cookies.set(key,value,domain='127.0.0.1',path='/')
        self.session.headers.update({'Origin':args.origin,'X-Madar-Builder-Contract':'cloud-draft-v1'})
        self.settings=self.call('GET','/elearning/settings')
        profile=self.settings['academy_management'];self.subdomain=profile['subdomain'];self.project=profile['landing_project']
        if not self.project or self.project['tenant_id']!=args.target_tenant or self.project['usage_profile']!='academy':raise RuntimeError('Explicit target tenant/project ownership does not match authorized session')
        self.pid=self.project['id'];self.state=copy.deepcopy(self.project['draft_schema']);self.journal=copy.deepcopy(self.state.get('seed_metadata',{}).get('resources',{}))
        self.audit=[];self.mapping={'routes.register':f'/academy/{self.subdomain}/login?register=1'}
        self.forms=json.loads((PACKAGE/'forms.json').read_text())['definitions'];self.course=json.loads((PACKAGE/'course.json').read_text())
        self.website=json.loads((PACKAGE/'website.json').read_text());self.media=json.loads((PACKAGE/'media.json').read_text())['assets']

    def call(self,method,path,**kwargs):
        if method!='GET' and not self.args.apply:raise RuntimeError('Dry-run mutation refused')
        self.session.headers['X-CSRF-Token']=self.session.cookies.get('madar_csrf_token','')
        response=self.session.request(method,self.args.api.rstrip('/')+path,timeout=60,**kwargs)
        if not response.ok:raise RuntimeError(f'{method} {path}: {response.status_code}: {response.text[:450]}')
        return response.json()

    def checkpoint(self):
        self.state.setdefault('seed_metadata',{}).update(logical_key='eduhope.website',package_version=1,resources=self.journal)
        result=self.call('PUT','/builder/projects/'+self.pid,json={'draft_schema':self.state,'expected_revision':self.project['draft_revision']})
        self.project=result.get('project',result)
        private_json(self.args.cookies,requests.utils.dict_from_cookiejar(self.session.cookies))

    def record(self,key,identifier,desired,live):
        self.journal[key]={'id':identifier,'input_hash':fingerprint(desired),'live_hash':fingerprint(live)}
        self.audit.append({'key':key,'id':identifier,'action':'created'});self.checkpoint()

    def backup(self):
        folder=self.args.evidence/'backup-before-import';folder.mkdir(mode=0o700,parents=True,exist_ok=True)
        dump=folder/'preview144.dump'
        if dump.exists():return
        data=subprocess.check_output(['docker','exec','supabase_db_web','pg_dump','-U','postgres','-Fc','madar_eduhope_preview_144'])
        fd=os.open(dump,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as out:out.write(data)
        listing=subprocess.check_output(['docker','exec','-i','supabase_db_web','pg_restore','--list'],input=data)
        if b'elearning_form_responses' not in listing or b'builder_projects' not in listing:raise RuntimeError('Recovery archive incomplete')
        private_json(folder/'manifest.json',{'database':'madar_eduhope_preview_144','schema':144,'sha256':hashlib.sha256(data).hexdigest(),'restore_listing_verified':True})

    def form_value(self,form):return {key:form[key] for key in ('name','status','schema')}

    def content_fingerprint(self):
        cid=self.journal['course']['id'];tenant=self.args.target_tenant
        roots={}
        with psycopg.connect(self.env['SUPABASE_DB_URL']) as db:
            db.execute('set transaction read only')
            for table in ('elearning_sections','elearning_lessons','elearning_content_blocks','elearning_assessment_placements'):
                rows=db.execute(sql.SQL("select to_jsonb(t)-'created_at'-'updated_at'-'created_by' from {} t where tenant_id=%s and course_id=%s order by id").format(sql.Identifier(table)),(tenant,cid)).fetchall()
                roots[table]=[row[0] for row in rows]
            for table in ('elearning_assessments','elearning_assessment_questions'):
                column='id' if table=='elearning_assessments' else 'assessment_id'
                rows=db.execute(sql.SQL("select to_jsonb(t)-'created_at'-'updated_at'-'created_by' from {} t where tenant_id=%s and {} in(select assessment_id from elearning_assessment_placements where tenant_id=%s and course_id=%s) order by id").format(sql.Identifier(table),sql.Identifier(column)),(tenant,tenant,cid)).fetchall()
                # Numeric values become Decimal in psycopg; JSON normalization
                # keeps this local protection deterministic without any writes.
                roots[table]=json.loads(json.dumps([row[0] for row in rows],default=str))
        return fingerprint(roots)

    def preflight(self):
        if not self.journal and not self.args.initialize_existing:raise RuntimeError('Initial import requires explicit --initialize-existing after reviewing the backed-up local project')
        if 'website' in self.journal and website_fingerprint(self.state)!=self.journal['website']['live_hash']:raise RuntimeError('Owner edited the website; reconciliation stops without overwriting their changes')
        expected=self.state.get('seed_metadata',{}).get('learning_content_hash')
        if expected and self.content_fingerprint()!=expected:raise RuntimeError('Owner learning content edit conflict; no mutations performed')
        library=self.call('GET','/elearning/forms')['items']
        for desired in self.forms:
            key=desired['key'];entry=self.journal.get(key)
            if entry:
                actual=self.call('GET','/elearning/forms/'+entry['id'])
                if fingerprint(self.form_value(actual))!=entry['live_hash']:raise RuntimeError('Owner Form edit conflict: '+key)
                if fingerprint(desired)!=entry['input_hash']:raise RuntimeError('Package revision requires explicit reconciliation: '+key)
            elif any(form['name']==desired['name'] for form in library):raise RuntimeError('Unmanaged Form name collision; inspect before adopting: '+key)
        if 'course' in self.journal:
            actual=self.call('GET','/elearning/courses/'+self.journal['course']['id'])['course']
            if fingerprint(self.course_value(actual))!=self.journal['course']['live_hash']:raise RuntimeError('Owner course metadata edit conflict')
        else:
            for row in self.call('GET','/elearning/courses')['courses']:
                if row['name']==self.course['title']:raise RuntimeError('Unmanaged course name collision; manual recovery/reconciliation required')
        if 'settings' in self.journal:
            keys=self.journal['settings'].get('managed_keys',list(json.loads((PACKAGE/'settings.json').read_text())['settings']))
            if fingerprint({key:self.settings['settings'].get(key) for key in keys})!=self.journal['settings']['live_hash']:raise RuntimeError('Owner settings edit conflict; no mutations performed')
        print(json.dumps({'mode':'apply' if self.args.apply else 'dry-run','tenant':self.args.target_tenant,'project':self.pid,'schema':144,'pages':len(self.website['pages']),'forms':len(self.forms),'levels':len(self.course['levels']),'topics':sum(len(level['topics']) for level in self.course['levels']),'existing_logical_resources':len(self.journal)},indent=2))

    @staticmethod
    def course_value(row):return {key:row.get(key) for key in ('name','description','cover_asset','status','access_type','catalog_visible')}

    def export_owner_website(self):
        """Explicit adoption of reviewed native edits; never an implicit rerun."""
        if not self.args.apply:
            raise RuntimeError('Owner export requires explicit --apply and --export-owner-website')
        if self.project['published_revision'] != self.project['draft_revision']:
            raise RuntimeError('Save and publish the reviewed owner edits before export')
        value=copy.deepcopy(self.state)
        value['seed_metadata']={'logical_key':'eduhope.website','package_version':1}
        reverse={entry['url']:'ref:'+key for key,entry in self.journal.items() if key.startswith('assets.') and entry.get('url')}
        reverse.update({entry['id']:'ref:'+key for key,entry in self.journal.items() if key.startswith('forms.')})
        reverse['/academy/'+self.subdomain+'/courses/'+self.journal['course']['id']]='ref:routes.course'
        reverse[self.mapping['routes.register']]='ref:routes.register'
        def portable(item):
            if isinstance(item,dict):return {key:portable(child) for key,child in item.items()}
            if isinstance(item,list):return [portable(child) for child in item]
            if isinstance(item,str):return reverse.get(item,item)
            return item
        value=portable(value)
        # Only presentation is exported: no definitions, submissions or journal.
        (PACKAGE/'website.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
        self.journal['website'].update(input_hash=fingerprint(value),live_hash=website_fingerprint(self.state))
        self.checkpoint()
        print('Reviewed published owner presentation exported; expected revision enforced.')

    def run(self):
        if self.args.capture_content_baseline:
            if not self.args.apply:raise RuntimeError('Content baseline requires explicit --apply')
            self.state.setdefault('seed_metadata',{})['learning_content_hash']=self.content_fingerprint()
            self.checkpoint();print('Reviewed course authoring baseline captured; no course records changed.');return
        if self.args.export_owner_website:
            self.export_owner_website();return
        self.preflight()
        if not self.args.apply:return
        self.backup()
        for asset in self.media:
            key='assets.'+asset['key']
            if key not in self.journal:
                path=PACKAGE/asset['package_file'] if asset.get('package_file') else self.args.media_root/asset['file']
                if asset.get('package_file') and not path.resolve().is_relative_to(PACKAGE.resolve()):raise RuntimeError('Package media path escapes its root')
                if not path.exists():
                    remote=urlsplit(asset.get('download_url',''))
                    if remote.scheme!='https' or remote.hostname!='images.pexels.com':raise RuntimeError('Missing portable media source')
                    response=requests.get(asset['download_url'],timeout=30);response.raise_for_status();data=response.content
                    if len(data)>5_000_000 or hashlib.sha256(data).hexdigest()!=asset['sha256']:raise RuntimeError('Remote source media digest/size mismatch')
                    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
                data=path.read_bytes()
                if hashlib.sha256(data).hexdigest()!=asset['sha256']:raise RuntimeError('Media digest mismatch: '+key)
                result=self.call('POST','/builder/assets/upload',files={'file':(asset['file'],data,mimetypes.guess_type(asset['file'])[0])})
                self.record(key,result['asset_id'],asset,{'url':result['asset_url'],'sha256':asset['sha256']})
                self.journal[key]['url']=result['asset_url'];self.checkpoint()
            self.mapping[key]=self.journal[key]['url']
        for desired in self.forms:
            key=desired['key']
            if key not in self.journal:
                schema=copy.deepcopy(desired['schema']);schema['metadata']={'logical_key':key,'content_package':'eduhope-v1'}
                actual=self.call('POST','/elearning/forms',json={'name':desired['name'],'status':desired['status'],'schema':schema})
                self.record(key,actual['id'],desired,self.form_value(actual))
            self.mapping[key]=self.journal[key]['id']
        settings=resolve(json.loads((PACKAGE/'settings.json').read_text())['settings'],self.mapping)
        current=self.call('GET','/elearning/settings')['settings']
        managed={key:current.get(key) for key in settings}
        entry=self.journal.get('settings')
        if entry and fingerprint(managed)!=entry['live_hash']:raise RuntimeError('Owner settings edit conflict; no overwrite')
        if not entry or fingerprint(settings)!=entry['input_hash']:
            result=self.call('PUT','/elearning/settings',json={**current,**settings})['settings']
            self.journal['settings']={'id':str(self.args.target_tenant),'input_hash':fingerprint(settings),'managed_keys':list(settings),'live_hash':fingerprint({key:result.get(key) for key in settings})};self.checkpoint()
        if 'course' not in self.journal:
            desired={'name':self.course['title'],'description':'Original provisional EduHope demonstration syllabus. The owner’s original 89-topic book map is pending. Draft lessons require editorial approval.','cover_asset':self.mapping['assets.hero.library'],'status':'draft','access_type':'paid','catalog_visible':True}
            actual=self.call('POST','/elearning/courses',json=desired)['course'];self.record('course',actual['id'],desired,self.course_value(actual))
        cid=self.journal['course']['id'];self.mapping['routes.course']=f'/academy/{self.subdomain}/courses/{cid}'
        actual=self.call('GET','/elearning/courses/'+cid)['course']
        if actual['status']=='draft' and not actual['catalog_visible']:
            # The canonical offering contract requires catalogue eligibility,
            # even for a draft plan; this does not publish the draft course.
            desired={**self.course_value(actual),'catalog_visible':True}
            actual=self.call('PUT','/elearning/courses/'+cid,json={**desired,'expected_revision':actual['revision']})['course']
            self.journal['course'].update(input_hash=fingerprint(desired),live_hash=fingerprint(self.course_value(actual)));self.checkpoint()
        for level in self.course['levels']:
            if level['key'] not in self.journal:
                before=self.call('GET',f'/elearning/courses/{cid}/structure');known={row['id'] for row in before['sections']}
                desired={'name':level['name'],'description':f"{level['cefr']} — provisional, owner-editable EduHope Level.",'status':'draft'}
                after=self.call('POST',f'/elearning/courses/{cid}/structure/commands',json={'action':'create_section','expected_revision':before['revision'],'payload':desired})
                actual=next(row for row in after['sections'] if row['id'] not in known);self.record(level['key'],actual['id'],desired,desired)
            sid=self.journal[level['key']]['id']
            for topic in level['topics']:
                if topic['key'] in self.journal:continue
                before=self.call('GET',f'/elearning/courses/{cid}/structure');known={row['id'] for section in before['sections'] for row in section['lessons']}
                desired={'name':topic['title'],'description':'Provisional original teaching content; not a reproduction of the owner’s unavailable topic map.','status':'draft','section_id':sid}
                after=self.call('POST',f'/elearning/courses/{cid}/structure/commands',json={'action':'create_lesson','expected_revision':before['revision'],'payload':desired})
                actual=next(row for section in after['sections'] for row in section['lessons'] if row['id'] not in known);self.record(topic['key'],actual['id'],desired,desired)
        if 'plan' not in self.journal:
            desired={'name':'EduHope English Conversation Course','description':'One-time course access. Official publication and live payments are pending.','status':'draft','billing_type':'one_time','amount':'30.00','currency':'USD','access_scope':'single_course','course_ids':[cid]}
            result=self.call('POST','/elearning/plans',json=desired);self.record('plan',result['saved_plan_id'],desired,desired)
        if self.args.learning:
            from eduhope_learning_import import seed_learning
            seed_learning(self)
        schema=resolve(self.website,self.mapping)
        # On rerun preserve the actual persisted page representation. Builder may
        # normalize it during an authorized edit; owner changes must reconcile.
        if 'website' not in self.journal:
            schema['seed_metadata']['resources']=self.journal;self.state=schema
            self.journal['website']={'id':self.pid,'input_hash':fingerprint(self.website),'live_hash':website_fingerprint(schema)};self.checkpoint()
        elif fingerprint(self.website)!=self.journal['website']['input_hash']:
            if not self.args.reconcile_package:raise RuntimeError('Website package changed; use explicit reconciliation after reviewing the dry-run')
            schema['seed_metadata']['resources']=self.journal;self.state=schema
            self.journal['website'].update(input_hash=fingerprint(self.website),live_hash=website_fingerprint(schema));self.checkpoint()
        if self.args.learning:
            self.state.setdefault('seed_metadata',{})['learning_content_hash']=self.content_fingerprint();self.checkpoint()
        if self.args.publish and self.project.get('published_revision')!=self.project['draft_revision']:
            self.call('POST','/builder/projects/'+self.pid+'/publish',json={'expected_revision':self.project['draft_revision'],'message':'EduHope local public website seed v1'})
        private_json(self.args.evidence/'import-report.json',{'package':'eduhope','version':1,'tenant':self.args.target_tenant,'project':self.pid,'schema':144,'resources':self.journal,'actions':self.audit,'public_url':self.args.origin+'/academy/'+self.subdomain,'editor_url':self.args.origin+'/e-learning/landing-page/projects/'+self.pid+'/pages','production_touched':False})
        print('Import complete. Created resources:',len(self.audit),'Public:',self.args.origin+'/academy/'+self.subdomain)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target-tenant',type=int,required=True);p.add_argument('--api',default='http://127.0.0.1:8010');p.add_argument('--origin',default='http://127.0.0.1:5180')
    p.add_argument('--local-env',type=Path,default=Path('/tmp/madar-eduhope-preview/backend.env'));p.add_argument('--cookies',type=Path,default=Path('/tmp/madar-eduhope-preview/owner-cookies.json'))
    p.add_argument('--media-root',type=Path,default=Path('/tmp/madar-eduhope-preview/assets'));p.add_argument('--evidence',type=Path,default=Path('/tmp/madar-eduhope-preview/seed'))
    p.add_argument('--apply',action='store_true');p.add_argument('--publish',action='store_true');p.add_argument('--initialize-existing',action='store_true');p.add_argument('--reconcile-package',action='store_true')
    p.add_argument('--capture-content-baseline',action='store_true',help='Explicitly adopt reviewed existing course authoring for owner-edit detection')
    p.add_argument('--export-owner-website',action='store_true',help='Explicitly adopt reviewed, published owner presentation into the public package')
    p.add_argument('--learning',action='store_true');p.add_argument('--publish-demo',action='store_true')
    Importer(p.parse_args()).run()


if __name__=='__main__':main()
