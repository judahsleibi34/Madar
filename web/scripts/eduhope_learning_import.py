"""Canonical course content/media/assessment seed operations; no private learner data."""
import hashlib
import json
from pathlib import Path
import subprocess
from uuid import uuid5,NAMESPACE_URL

PACKAGE=Path(__file__).resolve().parents[1]/'seed-data/eduhope'

def uid(key):return str(uuid5(NAMESPACE_URL,'madar/eduhope/'+key))

def seed_learning(importer):
    I=importer;cid=I.journal['course']['id'];base='/elearning/courses/'+cid
    lessons=json.loads((PACKAGE/'teaching.json').read_text())['authored_demonstration_lessons']
    exams=json.loads((PACKAGE/'assessments.json').read_text())
    def text(lid,key,title,body):
        if key in I.journal:return
        path=base+'/lessons/'+lid+'/content';before=I.call('GET',path);known={b['id'] for b in before['blocks']}
        desired={'type':'text','title':title,'content':{'version':1,'body':body}}
        after=I.call('POST',path+'/commands',json={'action':'create','expected_revision':before['revision'],'payload':desired})
        actual=next(b for b in after['blocks'] if b['id'] not in known);I.record(key,actual['id'],desired,desired)
    def media(lid,key,filename,mime,data,provenance):
        if key in I.journal:return I.journal[key]['id']
        result=I.call('POST',base+'/lessons/'+lid+'/content/media/upload',files={'file':(filename,data,mime)})
        I.journal[key]={'id':result['asset_id'],'url':result['asset_url'],'source_sha256':hashlib.sha256(data).hexdigest(),'provenance':provenance}
        I.audit.append({'key':key,'id':result['asset_id'],'action':'uploaded'});I.checkpoint();return result['asset_id']
    def speech(lid,key,content,rate):
        if key in I.journal:return I.journal[key]['id']
        folder=I.args.media_root/'spoken';folder.mkdir(mode=0o700,parents=True,exist_ok=True);path=folder/(uid(key)+'.wav')
        subprocess.run(['espeak','-v','en','-s',str(rate),'-w',str(path),'--stdin'],input=content.encode(),check=True,stdout=subprocess.DEVNULL)
        return media(lid,key,path.name,'audio/wav',path.read_bytes(),{'generator':'espeak','voice':'en','rate':rate,'text':content,'temporary_original_demonstration':True})
    def assessment(lid,key,title,questions,mode='practice',status='published',section=None,details=None):
        if key in I.journal:return
        if lid:
            path=base+'/lessons/'+lid;revision=I.call('GET',path+'/content')['revision'];endpoint=path+'/assessments'
        else:
            revision=I.call('GET',base+'/structure')['revision'];endpoint=base+'/assessments'
        desired={'title':title,'instructions':'Original provisional teaching material. Follow each instruction. Subjective responses are reviewed by authorized staff; speaking practice has no automated score.','passing_score':70,'max_attempts':None if mode=='practice' else 5,'required_for_completion':mode=='practice','status':status,'activity_mode':mode,'practice_feedback':True,**(details or {})}
        payload={'expected_revision':revision,'assessment':desired,'questions':questions}
        if not lid:payload['section_id']=section
        result=I.call('POST',endpoint,json=payload);I.record(key,result['block_id'],{'assessment':desired,'questions':questions,'section':section},{'assessment':desired,'questions':questions})
    for lesson in lessons:
        lid=I.journal[lesson['key']]['id'];key='teaching.'+lesson['key']
        text(lid,key+'.intro','Purpose and learning approach',lesson['goal']+'\n\n'+lesson['arabic_support']+'\n\nOriginal provisional demonstration. The owner’s exact book topic map and final audio are pending.')
        audio=speech(lid,key+'.audio',lesson['dialogue'],lesson['audio_rate'])
        if key+'.listen' not in I.journal:
            path=base+'/lessons/'+lid+'/content';before=I.call('GET',path);known={b['id'] for b in before['blocks']};desired={'type':'audio','title':'Listen to the conversation','media_id':audio,'content':{'version':1,'caption':'Intelligible temporary narration; original dialogue, replaceable by the academy owner.','transcript':lesson['dialogue']}}
            after=I.call('POST',path+'/commands',json={'action':'create','expected_revision':before['revision'],'payload':desired});actual=next(b for b in after['blocks'] if b['id'] not in known);I.record(key+'.listen',actual['id'],desired,desired)
        qs=[]
        for index,item in enumerate(lesson['understanding']):
            options=[{'id':uid(key+':understand:'+str(index)+':'+str(n)),'label':label} for n,label in enumerate(item['choices'])]
            qs.append({'type':'multiple_choice','prompt':item['prompt'],'points':1,'config':{'options':options,'correct_option_id':options[item['correct']]['id']}})
        assessment(lid,key+'.understanding','Understand the conversation',qs)
        text(lid,key+'.expressions','Useful expressions','\n'.join(lesson['expressions'])+'\n\nChoose two expressions and adapt them to your own situation.')
        text(lid,key+'.vocabulary','Words and meanings','\n\n'.join(f"{v['word']} — {v['meaning']}\n{v['arabic']}\nExample: {v['example']}" for v in lesson['vocabulary']))
        target=lesson['picture'];other='bus' if target!='bus' else 'book';pictures=[]
        for image in [target,other]:
            mid=media(lid,'illustration.'+image,image+'.png','image/png',(PACKAGE/'illustrations'/ (image+'.png')).read_bytes(),{'original_vector':image+'.svg','creator':'Original Madar EduHope seed illustration','official_approval':False})
            pictures.append({'id':uid(key+':picture:'+image),'media_id':mid,'alt':{'book':'An open book','bus':'A bus','calendar':'A calendar with a date marked','meeting':'Two people sharing ideas in a discussion','interview':'A candidate answering questions at a desk','balance':'Two balanced pans on a scale','evidence':'A chart with data bars and a trend line'}[image]})
        cue={'book':'Choose the picture of a book.','bus':'Choose the picture of a bus.','calendar':'Choose the picture showing a marked date on a calendar.','meeting':'Choose the scene in which people are discussing their ideas together.','interview':'Choose the scene in which a candidate is answering questions in an interview.','balance':'Choose the image that represents balancing two different priorities.','evidence':'Choose the image that presents observations as data rather than a transport service.'}[target]
        prompt=speech(lid,key+'.picture-audio',cue,lesson['audio_rate'])
        assessment(lid,key+'.pictures','Listen and match with pictures',[{'type':'picture_listen','prompt':'Listen, then choose the corresponding image.','points':1,'config':{'media_id':prompt,'options':pictures,'correct_option_id':pictures[0]['id']}}])
        text(lid,key+'.communicate','Communication practice','Situations\n'+'\n'.join(lesson['communication_situations'])+'\n\nRespond in your own words\n'+'\n'.join(lesson['response_questions'])+'\n\nCompare your responses with the dialogue. Explain one reason for your choice.')
        assessment(lid,key+'.speaking','Speak now — private local practice',[{'type':'speaking_practice','prompt':challenge,'points':1,'config':{'rubric':'Unscored local speaking practice. Listen to your recording and reflect on intelligibility; no AI grading.','max_duration_seconds':120,'max_size_bytes':10485760}} for challenge in lesson['speaking_challenges']])
    # Preserve79 topic records as editable outlines, without pretending that
    # repeated generated prose is a completed educator-approved course.
    authored={lesson['key'] for lesson in lessons}
    for level in I.course['levels']:
        for topic in level['topics']:
            if topic['key'] in authored:continue
            lid=I.journal[topic['key']]['id'];text(lid,'outline.'+topic['key'],'Editorial draft outline',f"{topic['title']} — {level['cefr']}\n\nProvisional topic, pending the owner’s original book map.\nCommunication goal: apply this topic in university or everyday life.\n\nDraft authoring checklist: original dialogue; intelligible narration and transcript; comprehension; useful expressions; vocabulary with examples; picture listening; practical situations and response questions; unscored speaking challenge.\n\nThis topic is not published to learners. Adapt the sequence and content in the owner lesson editor before publication.")
    for bank in exams['level_reviews']+exams['cefr_finals']:
        section=I.journal['course.level-'+str(bank['section_number'])]['id'];details={field:bank[field] for field in ['pool_size','shuffle_questions','shuffle_options'] if field in bank}
        details['required_for_completion']=True
        assessment(None,bank['key'],bank['title'],bank['questions'],'graded','draft',section,details)
    for level,section_number in [('A1',2),('A2',4),('B1',6),('B2',8),('C1',10)]:
        key='credential.'+level
        if key not in I.journal:
            desired={'name':'EduHope '+level+' completion — provisional','title':level+' English communication','subtitle':'Independent CEFR-band course completion','body':'Awarded to {{learner_name}} for completing the configured '+level+' learning requirements in {{course_name}}.','issuer_name':'EduHope'}
            result=I.call('POST','/elearning/certificate-templates',json={'design':desired,'status':'active'});I.record(key,result['saved_id'],desired,desired)
            I.call('PUT','/elearning/programmes/courses/'+cid+'/cefr',json={'section_id':I.journal['course.level-'+str(section_number)]['id'],'level':level,'template_id':result['saved_id'],'enabled':False})
    # A separate small mixed exam demonstrates143 human review without
    # declaring unfinished official CEFR banks published or accredited.
    first=lessons[0];lid=I.journal[first['key']]['id']
    mixed=[{'type':'true_false','prompt':'In the conversation, Omar studies engineering.','points':1,'config':{'correct_answer':True}}, {'type':'written','prompt':'Introduce yourself to a new classmate and ask one relevant question.','points':4,'config':{'rubric':'Relevant introduction and intelligible question. Human reviewer awards0–4 points.','max_characters':1000}}, {'type':'speaking','prompt':'Introduce yourself aloud and ask where your classmate is from.','points':5,'config':{'rubric':'Relevant introduction and an intelligible question. Human reviewer awards0–5 points; do not penalize accent identity.','max_duration_seconds':60,'max_size_bytes':10485760}}]
    assessment(lid,'demo.mixed-exam','Local demonstration — written and speaking review',mixed,'graded','published',details={'required_for_completion':True})
    if I.args.publish_demo:
        structure=I.call('GET',base+'/structure')
        for lesson in lessons:
            sid=I.journal['course.level-'+str(lesson['level'])]['id'];lid=I.journal[lesson['key']]['id']
            section=next(s for s in structure['sections'] if s['id']==sid)
            if section['status']=='draft':structure=I.call('POST',base+'/structure/commands',json={'action':'update_section','entity_id':sid,'expected_revision':structure['revision'],'payload':{'name':section['name'],'description':section['description'],'status':'published'}})
            actual=next(row for s in structure['sections'] for row in s['lessons'] if row['id']==lid)
            if actual['status']=='draft':structure=I.call('POST',base+'/structure/commands',json={'action':'update_lesson','entity_id':lid,'expected_revision':structure['revision'],'payload':{'name':actual['name'],'description':'Original provisional demonstration; further educator/owner review required before official release.','status':'published'}})
        actual=I.call('GET',base)['course']
        if actual['status']=='draft':
            desired={**I.course_value(actual),'status':'published'};actual=I.call('PUT',base,json={**desired,'expected_revision':actual['revision']})['course']
            from import_eduhope_seed import fingerprint
            I.journal['course']['live_hash']=fingerprint(I.course_value(actual));I.checkpoint()
    print('Teaching imported:10 authored demonstration lessons;79 draft outlines;10 draft reviews;5 draft65-question finals;5 disabled CEFR configurations. Official publication requires educator review.')
