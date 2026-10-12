#!/usr/bin/env python3
"""Original provisional89-topic syllabus; owner topic map/audio/educator review pending."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[2]/'web/seed-data/eduhope'
PARTS=[
 ('A1','Beginner Foundations',['Meeting a new classmate','Introducing yourself','Names and spelling','Countries and languages','Numbers and contact details','People in your family','Everyday study objects','Classroom questions','Places on campus']),
 ('A1','Beginner Communication',['Daily routines','Telling the time','Ordering a simple meal','Buying everyday items','Getting around town','Asking for directions','Likes and preferences','Making a simple invitation','Describing your room']),
 ('A2','Elementary Communication',['Talking about last weekend','Planning a study session','Making an appointment','Finding information online','Asking about a timetable','Describing a person','Shopping for clothing','Comparing everyday choices','Talking about health']),
 ('A2','Elementary Real-Life English',['Booking a journey','At a service desk','Explaining a simple problem','University clubs and activities','Talking about experiences','Finding a place to live','Requesting help politely','Making and changing plans','Giving practical instructions']),
 ('B1','Intermediate Communication',['Giving an opinion respectfully','Explaining a missed deadline','Discussing study habits','Describing an important experience','Making a group decision','Responding to unexpected changes','Talking about future goals','Making a recommendation','Explaining a process']),
 ('B1','Intermediate Real-Life English',['Preparing for a job interview','Resolving a misunderstanding','Communicating in an online meeting','Planning a community activity','Asking about study opportunities','Evaluating information sources','Giving constructive feedback','Negotiating a practical arrangement','Presenting a short proposal']),
 ('B2','Upper-Intermediate Communication',['Balancing different viewpoints','Discussing professional priorities','Handling a difficult conversation','Interpreting a detailed explanation','Clarifying assumptions','Supporting an argument with examples','Managing an international meeting','Giving a persuasive presentation','Summarizing competing proposals']),
 ('B2','Advanced Everyday Communication',['Negotiating a shared outcome','Responding to a service complaint','Discussing technology responsibly','Explaining uncertainty','Communicating across cultures','Proposing improvements at work','Handling detailed travel problems','Discussing ethical choices','Adapting tone to an audience']),
 ('C1','Advanced Communication',['Developing a nuanced argument','Evaluating academic claims','Synthesizing information','Challenging a conclusion diplomatically','Explaining implications','Leading a complex discussion','Presenting an evidence-based position','Managing disagreement constructively','Interpreting implied meaning']),
 ('C1','Advanced Fluency and Professional Communication',['Negotiating with multiple constraints','Communicating a strategic recommendation','Presenting research to a broad audience','Responding to challenging questions','Discussing policy trade-offs','Building consensus professionally','Reflecting on communication choices','Planning continued independent learning']),
]
CONTEXTS=['a university class in Bethlehem','a study group in Ramallah','a campus library','a team project','a conversation with a new colleague','a student society meeting','an international online meeting','a careers workshop','a community learning session']


def topic(part,index,name,level):
    return {'key':f'course.level-{part}.topic-{index+1}','title':name,'cefr':level,'status':'draft','provisional':True,'owner_original_topic':False,'teaching_ref':'teaching.json' if index==0 else None,'editorial_status':'authored_demonstration' if index==0 else 'outline_requires_authoring','original_owner_material_required':True}


def main():
    levels=[]
    for number,(cefr,name,titles) in enumerate(PARTS,1):
        levels.append({'key':f'course.level-{number}','number':number,'name':f'Level {number} — {name}','cefr':cefr,'status':'draft','topics':[topic(number,index,title,cefr) for index,title in enumerate(titles)],'review':{'title':f'Level {number} review','passing_score':70,'max_attempts':3,'status':'draft','provisional':True}})
    assert len(levels)==10 and sum(len(level['topics']) for level in levels)==89
    value={'version':1,'logical_key':'eduhope.course','title':'EduHope English Conversation Course','price':{'amount':'30.00','currency':'USD','billing_type':'one_time'},'access_type':'paid','status':'draft','provisional':True,'owner_original_topic_map_missing':True,'levels':levels,'assessments_ref':'assessments.json','teaching_ref':'teaching.json','publish_policy':'Official material remains Draft pending owner topic-map and educator review. Explicit local demonstration publication is separate.'}
    (ROOT/'course.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print('Generated10 Levels and89 provisional topic records. Authored teaching and exam banks are separate inputs; no database writes.')


if __name__=='__main__':main()
