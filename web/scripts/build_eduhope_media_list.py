#!/usr/bin/env python3
"""Generate the owner's EduHope MEDIA LIST: every photo and recording to supply.

Reads the approved topic map and the authored demo lessons. One Listen & Match
question per topic (89 in total, above the book's suggested 10-15 per CEFR level),
following the book's progression: WORD -> PHRASE -> SITUATION -> DESCRIPTION ->
MEANING & INFERENCE. Photo option numbers are shuffled per question and the
suggested file names never reveal which photo is correct. No database writes.
"""
from pathlib import Path
import json
import random

ROOT = Path(__file__).resolve().parents[2] / 'web/seed-data/eduhope'

# (level, topic): (exact prompt to record, correct photo, [3 distinct alternatives])
LISTEN_MATCH = {
    (1, 1): ('Student.', 'A young adult with a backpack and books standing outside a university building', ['A doctor in a white coat in a clinic', 'A chef cooking in a kitchen', 'A bus driver at the wheel of a bus']),
    (1, 2): ('Goodbye.', 'Two friends waving goodbye to each other at a doorway', ['Two people shaking hands for the first time at a desk', 'A person sleeping on a sofa', 'A person reading a book alone']),
    (1, 3): ('Family.', 'Parents, grandparents and children sitting together on a sofa at home', ['A group of office colleagues around a meeting table', 'A football team on a pitch', 'A class of students facing a whiteboard']),
    (1, 4): ('Phone.', 'A smartphone lying on a table, screen dark', ['A laptop computer, closed', 'A wristwatch', 'A wallet']),
    (1, 5): ('Clock.', 'A round wall clock on a plain wall', ['A calendar hanging on a wall', 'A framed photograph on a wall', 'A mirror on a wall']),
    (1, 6): ('Birthday cake.', 'A birthday cake with lit candles on a table', ['A bowl of fruit on a table', 'A plate of rice and chicken', 'A cup of tea with a teapot']),
    (1, 7): ('Chair.', 'A single classroom chair, empty', ['A desk with nothing on it', 'A bookshelf full of books', 'A whiteboard on a wall']),
    (1, 8): ('Kitchen.', 'A clean home kitchen with a cooker, sink and cupboards', ['A bedroom with a made bed', 'A living room with a sofa and television', 'A bathroom with a sink and mirror']),
    (2, 1): ('Wake up.', 'A person stretching in bed next to a ringing alarm clock in the morning', ['A person eating lunch at a café', 'A person driving a car on a highway', 'A person studying at a library desk']),
    (2, 2): ('Coffee.', 'A cup of coffee on a café table', ['A glass of orange juice', 'A bottle of water', 'A cup of hot chocolate with cream']),
    (2, 3): ('Bag.', 'A shopping bag full of groceries on a counter', ['A suitcase standing on the floor', 'A school backpack', 'A cardboard box']),
    (2, 4): ('Turn left.', 'A person at a street corner pointing to their left', ['A person pointing straight ahead down a road', 'A person climbing stairs', 'A person crossing a pedestrian bridge']),
    (2, 5): ('Bus.', 'A city bus stopped at a bus stop', ['A taxi on a street', 'A bicycle parked on a pavement', 'A train at a platform']),
    (2, 6): ('Football.', 'Young people playing football in a park', ['Young people playing basketball indoors', 'A person swimming in a pool', 'A person running on a treadmill']),
    (2, 7): ('Rain.', 'Rain falling on a street with people holding umbrellas', ['A sunny beach with clear sky', 'Snow covering trees and a road', 'A windy field with bending grass']),
    (2, 8): ('Teacher.', 'A teacher standing at the front of a classroom explaining to students', ['A shop assistant behind a counter', 'A nurse checking a patient', 'A waiter carrying plates']),
    (3, 1): ('Went to the beach.', 'A group of friends walking on a beach at sunset', ['Friends sitting in a cinema', 'Friends studying together at a table', 'Friends shopping in a mall']),
    (3, 2): ('Book an appointment.', 'A person at a clinic reception desk talking to a receptionist with a calendar', ['A person paying at a supermarket checkout', 'A person boarding a plane', 'A person ordering at a fast-food counter']),
    (3, 3): ('Meet at the café.', 'Two friends greeting each other at the door of a café', ['Two friends meeting at a train station platform', 'Two friends at a gym', 'Two friends in a classroom']),
    (3, 4): ('Information desk.', 'A traveller asking a question at an information desk in a station', ['A person buying a snack from a vending machine', 'A person waiting alone on a bench', 'A person reading a newspaper']),
    (3, 5): ('Tall man with glasses.', 'A tall man wearing glasses standing next to shorter people', ['A short woman with long hair', 'A man with a beard and a hat, no glasses', 'A child with curly hair']),
    (3, 6): ('Playing the guitar.', 'A young person sitting and playing the guitar', ['A young person painting a picture', 'A young person cooking', 'A young person reading on a bench']),
    (3, 7): ('A sore throat.', 'A doctor checking a patient\'s throat with a small light', ['A doctor bandaging a patient\'s hand', 'A doctor listening to a patient\'s heart', 'A dentist examining teeth']),
    (3, 8): ('Come to my party.', 'A person handing an invitation card to a friend', ['A person returning a book to a library', 'A person paying a bill', 'A person posting a parcel']),
    (3, 9): ('Studying for an exam.', 'A student surrounded by notes and books studying late at a desk', ['A student playing a video game', 'A student sleeping in class', 'A student eating in a cafeteria']),
    (4, 1): ('Check in at the hotel.', 'A guest with a suitcase at a hotel reception desk receiving a key card', ['A guest swimming in a hotel pool', 'A guest eating breakfast at a buffet', 'A guest sleeping in a hotel room']),
    (4, 2): ('Waiting at the gate.', 'Passengers sitting and waiting at an airport departure gate', ['Passengers collecting bags at a baggage belt', 'Passengers walking through security', 'A pilot in a cockpit']),
    (4, 3): ('Buying a ticket.', 'A person buying a ticket from a ticket machine at a station', ['A person sitting on a moving train', 'A person waiting at a taxi rank', 'A person cycling to work']),
    (4, 4): ('The shirt is too small.', 'A customer at a shop counter holding up a small shirt to show the assistant', ['A customer trying on shoes', 'A customer paying for groceries', 'A customer choosing fruit at a market']),
    (4, 5): ('Opening a bank account.', 'A customer sitting at a bank desk signing forms with a bank employee', ['A person using a cash machine on the street', 'A person counting coins at home', 'A person shopping online on a laptop']),
    (4, 6): ('An apartment with a balcony.', 'An empty apartment living room with a door open onto a balcony', ['A house with a large garden', 'An office with many desks', 'A hotel corridor']),
    (4, 7): ('I am calling about my order.', 'A person on the phone at home looking at a delivery box', ['A person on the phone while running', 'A person on a video call in an office meeting', 'A person listening to music with headphones']),
    (4, 8): ('Our train is cancelled.', 'Travellers looking worried at a station departures board with crossed-out times (no readable text)', ['Travellers happily boarding a train', 'A person relaxing on a beach', 'A person buying souvenirs']),
    (4, 9): ('We visited an old city.', 'Tourists walking through narrow streets of an old stone city', ['Tourists on a modern shopping street', 'Tourists on a mountain hike', 'Tourists on a boat at sea']),
    (5, 1): ('She thinks online classes are useful.', 'A young woman smiling and speaking while pointing to a laptop showing an online class', ['A young woman frowning at a broken laptop', 'A young woman reading a printed book', 'A young woman walking to class']),
    (5, 2): ('They disagree, but they are listening to each other.', 'Two people in a calm discussion, one speaking and one listening attentively', ['Two people shouting angrily', 'Two people laughing together at a joke', 'Two people working silently side by side']),
    (5, 3): ('His laptop will not turn on.', 'A man pressing the power button of a laptop with a black screen, looking confused', ['A man typing quickly on a working laptop', 'A man charging his phone', 'A man buying a new laptop in a shop']),
    (5, 4): ('She is telling her friends about her first job.', 'A young woman talking enthusiastically to friends around a table', ['A young woman giving a lecture to a large hall', 'A young woman writing alone in a diary', 'A young woman on the phone in a car']),
    (5, 5): ('Why don\'t we take a break?', 'A small study group closing books and standing up to stretch', ['A study group starting a new exam', 'A study group arguing', 'A study group taking a photo']),
    (5, 6): ('He wants to study abroad next year.', 'A young man at home looking at a world map and university brochures (no readable text)', ['A young man packing for a beach holiday', 'A young man cooking dinner', 'A young man watching football on television']),
    (5, 7): ('The story ends with a surprise.', 'A group of children looking surprised while an adult reads them a story', ['Children playing football outside', 'Children sleeping', 'Children eating lunch']),
    (5, 8): ('They are watching a film together.', 'Friends on a sofa watching a film with popcorn', ['Friends at a live concert', 'Friends at a museum looking at paintings', 'Friends reading in a library']),
    (5, 9): ('She is sharing a video with her followers.', 'A young woman filming herself with a phone on a small tripod', ['A young woman reading a newspaper', 'A young woman sending a letter at the post office', 'A young woman talking on a landline phone']),
    (6, 1): ('He is waiting nervously for his interview.', 'A man in a suit sitting in a reception area holding a folder, looking nervous', ['A man relaxing at a café', 'A man leading a meeting confidently', 'A man jogging in a park']),
    (6, 2): ('She checks the reports every morning.', 'A woman at an office desk reviewing documents with coffee in the morning light', ['A woman presenting to a large audience', 'A woman on lunch break outside', 'A woman leaving the office at night']),
    (6, 3): ('The customer is complaining about cold food.', 'A diner pointing at a plate while speaking to a waiter, looking unhappy', ['A diner smiling and paying the bill', 'A waiter carrying a birthday cake', 'A chef tasting soup in a kitchen']),
    (6, 4): ('Some people have their cameras off.', 'A laptop screen showing a video meeting grid where several tiles show only initials (no readable text)', ['A laptop showing a film', 'A laptop showing a spreadsheet', 'A laptop with a blank screen']),
    (6, 5): ('Could you show me how this works?', 'A new employee watching as a colleague demonstrates a machine or software', ['An employee working alone at night', 'A manager giving a presentation', 'Colleagues celebrating with a cake']),
    (6, 6): ('Let\'s meet on Tuesday at ten.', 'A person on the phone writing an appointment in a paper diary', ['A person on the phone while cooking', 'A person texting while walking', 'A person reading emails']),
    (6, 7): ('He has started cycling to work to stay healthy.', 'A man in office clothes cycling on a city bike lane in the morning', ['A man driving a car in traffic', 'A man eating fast food', 'A man sleeping on a train']),
    (6, 8): ('Volunteers are cleaning the park.', 'A group of volunteers in gloves picking up litter in a park', ['A group having a picnic in a park', 'Gardeners being paid to cut grass', 'Children playing on swings']),
    (6, 9): ('Many young people cannot find affordable housing.', 'A young couple looking anxiously at apartment adverts on a phone in a café (no readable text)', ['A young couple moving into a large house', 'A young couple on holiday', 'A young couple at a wedding']),
    (7, 1): ('Everyone in the group is sharing an idea before they decide.', 'A seminar group around a table where several people are speaking with notes and sticky notes (no readable text)', ['One person giving a lecture to silent students', 'A group watching a film', 'A group eating dinner']),
    (7, 2): ('He is weighing both sides before giving his view.', 'A man looking thoughtfully at two sets of papers in each hand', ['A man signing a contract quickly', 'A man throwing papers away', 'A man sleeping at his desk']),
    (7, 3): ('Working from home saves time, but it can feel lonely.', 'A person working on a laptop alone at home, looking a little isolated', ['A person laughing with colleagues in an office', 'A person on a crowded train', 'A person on holiday by a pool']),
    (7, 4): ('She is presenting her project to a small audience.', 'A woman presenting slides to a small seated group (slides show only charts, no readable text)', ['A woman teaching a child to read', 'A woman shopping for clothes', 'A woman cooking for friends']),
    (7, 5): ('Fewer people are buying newspapers than before.', 'A nearly empty newspaper stand while people nearby read on phones', ['A busy newspaper stand with a queue', 'A library full of readers', 'A printing factory at full speed']),
    (7, 6): ('Plastic waste is polluting the beach.', 'A beach with plastic bottles and bags washed up on the sand', ['A clean beach with families', 'A forest with clean paths', 'A recycling centre with sorted bins']),
    (7, 7): ('The reporter is speaking outside a flooded building.', 'A television reporter with a microphone standing in front of a flooded street', ['A reporter in a studio', 'A reporter at a football match', 'A reporter at a fashion show']),
    (7, 8): ('In the future, deliveries might be made by drones.', 'A small drone carrying a parcel above a residential street', ['A delivery van stuck in traffic', 'A postman on a bicycle', 'A cargo ship at a port']),
    (7, 9): ('She is giving her colleague helpful suggestions about his report.', 'Two colleagues looking at a document together while one points kindly at a section', ['A manager shouting at an employee', 'Two colleagues ignoring each other', 'A colleague throwing a report in the bin']),
    (8, 1): ('Both sides are making compromises to reach an agreement.', 'Two small groups across a table shaking hands over documents after a discussion', ['Two groups arguing loudly', 'One person signing alone', 'A group celebrating a sports win']),
    (8, 2): ('The team is working together to fix a delay in the project.', 'A team standing around a planning board moving cards and timelines (no readable text)', ['A team at a party', 'One person working alone late', 'A team relaxing in a break room']),
    (8, 3): ('The manager is calmly telling an employee some difficult news.', 'A manager speaking gently to an upset employee in a private office', ['A manager congratulating an employee', 'Two employees chatting at a coffee machine', 'A manager presenting to a full room']),
    (8, 4): ('She is updating the team on what has been finished and what is still delayed.', 'A woman standing beside a progress chart with some bars complete and some short, speaking to a team (no readable text)', ['A woman greeting new clients at reception', 'A woman reading emails alone', 'A woman packing boxes']),
    (8, 5): ('He is explaining why the company chose the cheaper option.', 'A man presenting two product samples and pointing to one while colleagues listen', ['A man buying lunch', 'A man fixing a car', 'A man reading a novel']),
    (8, 6): ('Some schools focus on exams, while others focus on projects.', 'Split scene: one classroom silently taking a written exam, another with students building a model together', ['A single empty classroom', 'Students at a graduation ceremony', 'Students on a school trip to a museum']),
    (8, 7): ('She is convincing her friends to join a charity run.', 'A young woman holding a running bib and talking enthusiastically to hesitant friends (no readable text)', ['A young woman running alone in the rain', 'Friends watching a race on television', 'A young woman buying running shoes']),
    (8, 8): ('They realise they were talking about different meetings.', 'Two colleagues with calendars on their phones, looking at each other and laughing in sudden understanding', ['Two colleagues arguing angrily', 'Two colleagues eating lunch quietly', 'Two colleagues shaking hands at a first meeting']),
    (8, 9): ('He is exchanging contact details with someone he has just met at a conference.', 'Two professionals at a conference exhibition hall scanning a phone code to exchange details', ['A speaker giving a keynote', 'An empty conference hall', 'A person sleeping in a hotel room']),
    (9, 1): ('Although the plan is expensive, she argues that it will save money in the long term.', 'A woman presenting a chart where costs rise at first and then fall over time (no readable text)', ['A woman counting cash at a shop till', 'A woman shopping for luxury goods', 'A woman reading a menu']),
    (9, 2): ('The students are questioning the evidence behind the professor\'s claim.', 'University students raising hands and pointing at a projected chart during a seminar (no readable text)', ['Students sleeping in a lecture', 'Students taking photos at graduation', 'Students eating in a cafeteria']),
    (9, 3): ('The researcher is explaining an unexpected result in her study.', 'A researcher at a conference pointing at one data point that stands apart on a scatter chart (no readable text)', ['A researcher pouring liquid in a lab', 'A researcher reading in a library', 'A researcher on a field trip in a forest']),
    (9, 4): ('They are discussing whether it is fair to use AI to choose job candidates.', 'A diverse panel around a table looking at a laptop showing anonymous candidate profiles, with thoughtful expressions (no readable text)', ['A job interview with one candidate', 'A computer repair shop', 'A robot vacuum cleaning a floor']),
    (9, 5): ('The forecast suggests it may rain, but it is far from certain.', 'A person at a window holding an umbrella while the sky is half sunny and half cloudy', ['A person in a heavy storm', 'A person sunbathing under a clear sky', 'A person shovelling snow']),
    (9, 6): ('The data shows sales grew, but only in the summer months.', 'A bar chart with only a few tall bars in the middle and short bars elsewhere, being examined by two colleagues (no readable text)', ['A chart with bars rising steadily', 'A pie chart on a screen', 'A blank whiteboard']),
    (9, 7): ('She is making sure the quieter members of the group get a chance to speak.', 'A discussion leader gesturing towards a quiet participant who begins to speak while others listen', ['A leader speaking alone while others look at phones', 'A group shouting over each other', 'A group watching a video']),
    (9, 8): ('He adapts his greeting because his colleague comes from a different culture.', 'A businessman pausing and offering a respectful nod instead of a handshake to an international colleague', ['Two old friends hugging at an airport', 'A man waving at a bus', 'A man shaking hands with a robot']),
    (9, 9): ('The speaker pauses to consider a difficult question from the audience.', 'A speaker on stage thinking carefully while an audience member stands with a microphone', ['A speaker laughing with the audience', 'A speaker walking off stage', 'An empty stage with a microphone']),
    (10, 1): ('They need to deliver on time, stay within budget and keep the client satisfied.', 'A project team looking at a whiteboard sketch of a triangle with three icons: a clock, coins and a smiling face (no words)', ['A team celebrating a finished project with balloons', 'One person reading a contract', 'A team on a lunch break']),
    (10, 2): ('The chair is bringing the discussion back to the agenda.', 'A meeting chair raising a hand calmly while participants turn to face her', ['A meeting with everyone talking at once', 'An empty meeting room', 'A chair leaving the meeting early']),
    (10, 3): ('The speaker is addressing a large audience at a formal event.', 'A speaker at a podium in a large formal hall facing a seated audience', ['A small team meeting in an office', 'A teacher with five students', 'A person speaking on the phone']),
    (10, 4): ('He listens to the client\'s concern before responding with evidence.', 'A consultant listening carefully to a sceptical client, then showing a document with charts (no readable text)', ['A consultant ignoring a client', 'A salesperson leaving a shop', 'Two people celebrating a deal']),
    (10, 5): ('Three interviewers are asking her questions at the same time.', 'A candidate facing a panel of three interviewers at a long table', ['A candidate talking to one interviewer', 'A group interview with many candidates', 'A candidate filling in a form alone']),
    (10, 6): ('An experienced employee is guiding a new colleague through her first project.', 'An older colleague sitting beside a younger colleague, pointing at a screen and explaining patiently', ['A manager giving a speech to staff', 'A new employee working alone', 'Two colleagues arguing']),
    (10, 7): ('She is helping two colleagues resolve a disagreement.', 'A woman sitting between two colleagues who are listening to each other with calmer expressions', ['Two colleagues in an angry argument with no one else', 'A team party', 'A woman working alone']),
    (10, 8): ('The founder has three minutes to convince the investors.', 'A young founder presenting a prototype to a small panel of investors with a timer visible (no readable text)', ['A shop owner serving customers', 'Investors playing golf', 'A founder working alone in a garage at night']),
    (10, 9): ('She is answering questions about her organisation at an international fair.', 'A professional at an exhibition stand speaking with visitors from different countries', ['A tourist taking photos', 'A professional working from home', 'A shop assistant folding clothes']),
    (10, 10): ('After a long debate, he summarises the main points everyone agreed on.', 'A man standing at a whiteboard grouping notes into three clear clusters while the group nods (no readable text)', ['A man starting a new debate', 'A group leaving the room in disagreement', 'A man reading alone']),
}

RECORDING_GUIDELINES = [
    'Natural, clear speech at a normal conversational speed for the CEFR level (A1 slightly slower, never robotic). Record each line as a real conversation, not a reading.',
    'Quiet room with soft furnishings; no echo, fans, traffic, music or background voices.',
    'Microphone 15–20 cm from the mouth, with a pop filter; keep the same distance and level for every clip.',
    'Format: WAV, 44.1 kHz or 48 kHz, 16-bit or 24-bit, mono. MP3 at 192 kbps or higher is also accepted.',
    'Loudness about −16 LUFS (peaks below −1 dBFS); no clipping, no added effects or background music.',
    'Leave about 0.5 seconds of silence at the start and end of each file; one clip per file, named exactly as listed.',
    'Use different adult voices (female and male) where a dialogue has two speakers; clear international English accents.',
    'Listen & Match prompts are recorded alone, once, exactly as written — no introduction such as "Number one".',
]
PHOTO_GUIDELINES = [
    'Real, high-quality photographs of real people and places. No illustrations, cartoons or AI-looking images.',
    'Listen & Match photos must contain NO text: no readable signs, labels, captions, logos, brand names or screen text.',
    'Each question needs four photos that are clearly different. Only one may reasonably match the recording.',
    'Orientation: landscape 4:3, at least 1200 × 900 pixels; JPEG, PNG or WebP; under 5 MB each.',
    'Culturally appropriate for Arabic-speaking learners: modest clothing, respectful situations, no alcohol, no pork, no gambling, no religious symbols used as decoration.',
    'Show people of a range of ages and genders, including Arab and Middle Eastern settings where natural (university, home, city, workplace).',
    'Use only photos you own or have a licence for, with model releases for recognisable people. Keep the licence record.',
    'Level cover images may include more atmosphere, but still no text, so they work in both English and Arabic.',
]


def speaker_lines(dialogue):
    turns = [line.split(':', 1) for line in dialogue.split('\n') if ':' in line]
    return [(name.strip(), text.strip()) for name, text in turns]


def main():
    topic_map = json.loads((ROOT / 'topic-map.draft.json').read_text())
    lessons = json.loads((ROOT / 'teaching.json').read_text())['authored_demonstration_lessons']
    # Demo lessons keep their original logical keys; level N topic 1 holds each one.
    demo = {lesson['level']: lesson for lesson in lessons}
    shuffle = random.Random(20261013)
    items, lines = [], ['# EduHope Media List', '', 'Draft for the EduHope owner. Supply every file below; each lesson shows a clear placeholder until its file is uploaded.', '',
                        'Topic titles are the owner-approved draft map. Suggested file names never reveal the correct Listen & Match photo — the answer is listed here only.', '']
    for level in topic_map['levels']:
        number_level = level['level']
        lines += [f"## Level {number_level} · {level['cefr']} · {level['title']}", '',
                  f"**Level cover photo** — `L{number_level:02d}-cover.jpg` (landscape 16:9, at least 1920 × 1080): an atmospheric real photo for \"{level['title']}\", no text.", '']
        items.append({'level': number_level, 'kind': 'photo', 'use': 'level cover', 'file': f'L{number_level:02d}-cover.jpg'})
        for topic in level['topics']:
            n = topic['number']; prefix = f'L{number_level:02d}-T{n:02d}'
            lines += [f"### Topic {n}: {topic['title']}", '']
            lesson = demo.get(number_level) if n == 1 else None
            if lesson:
                lines += ['**Dialogue recording** (script approved for the demo lesson; record line by line):', '']
                for index, (speaker, text) in enumerate(speaker_lines(lesson['dialogue']), 1):
                    name = f'{prefix}-dialogue-{index:02d}-{speaker.lower()}.wav'
                    lines.append(f'- `{name}` — **{speaker}**: "{text}"')
                    items.append({'level': number_level, 'topic': n, 'kind': 'audio', 'use': 'dialogue line', 'speaker': speaker, 'script': text, 'file': name})
                lines += ['', '**Vocabulary audio** (word, then the example sentence, one file each):', '']
                for index, word in enumerate(lesson['vocabulary'], 1):
                    for part, script in (('word', word['word']), ('example', word['example'])):
                        name = f'{prefix}-vocab-{index:02d}-{part}.wav'
                        lines.append(f'- `{name}` — "{script}"')
                        items.append({'level': number_level, 'topic': n, 'kind': 'audio', 'use': f'vocabulary {part}', 'script': script, 'file': name})
                lines.append('')
            else:
                lines += [f'**Dialogue recording** — `{prefix}-dialogue-NN-speaker.wav`: *script to be written and approved before recording.*', '']
                items.append({'level': number_level, 'topic': n, 'kind': 'audio', 'use': 'dialogue', 'script': None, 'status': 'script pending', 'file': f'{prefix}-dialogue-NN-speaker.wav'})
            prompt, correct, others = LISTEN_MATCH[(number_level, n)]
            options = [correct] + others
            order = list(range(4)); shuffle.shuffle(order)
            answer = order.index(0) + 1
            lines += ['**Listen & Match** (4 photos, landscape 4:3, no text):', '',
                      f'- Audio `{prefix}-LM1-prompt.wav` — record exactly: "{prompt}"']
            items.append({'level': number_level, 'topic': n, 'kind': 'audio', 'use': 'listen & match prompt', 'script': prompt, 'file': f'{prefix}-LM1-prompt.wav'})
            for slot, source in enumerate(order, 1):
                name = f'{prefix}-LM1-photo-{slot}.jpg'
                lines.append(f'- Photo `{name}` — {options[source]}')
                items.append({'level': number_level, 'topic': n, 'kind': 'photo', 'use': 'listen & match option', 'shows': options[source], 'file': name, 'correct': source == 0})
            lines += [f'- Correct answer: photo {answer}', '']
    lines += ['## Recording guidelines', ''] + [f'- {rule}' for rule in RECORDING_GUIDELINES] + ['', '## Photo guidelines', ''] + [f'- {rule}' for rule in PHOTO_GUIDELINES] + ['']
    assert len(LISTEN_MATCH) == 89 and len({p for p, _, _ in LISTEN_MATCH.values()}) == 89
    (ROOT / 'media-list.md').write_text('\n'.join(lines))
    (ROOT / 'media-list.json').write_text(json.dumps({'status': 'Draft for owner', 'recording_guidelines': RECORDING_GUIDELINES,
                                                      'photo_guidelines': PHOTO_GUIDELINES, 'items': items}, ensure_ascii=False, indent=2) + '\n')
    photos = sum(item['kind'] == 'photo' for item in items); audio = sum(item['kind'] == 'audio' for item in items)
    pending = sum(item.get('status') == 'script pending' for item in items)
    print(f'Media list: {photos} photos, {audio} audio files ({pending} dialogues awaiting scripts). No database writes.')


if __name__ == '__main__':
    main()
