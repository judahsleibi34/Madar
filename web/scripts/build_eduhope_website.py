#!/usr/bin/env python3
"""Rebuild the EduHope public website from the owner's two source documents.

Copy is taken word for word from "website prompt" and "The book project. 30"
wherever they provide it; OWN_COPY lists every sentence written here instead,
for owner approval. Sections use the flow (rows/columns) layout so every page
stacks at phone, tablet and desktop widths. Theme, logo and Form references are
kept from the existing package. No database writes.
"""
from pathlib import Path
import copy
import json

ROOT = Path(__file__).resolve().parents[2] / 'web/seed-data/eduhope'
SERIAL = 0
NAVY, GREEN, GREEN_DARK, SOFT = '#002A60', '#088848', '#006C39', '#F6F7F4'
# Terms & Privacy stay out of the published site until the owner approves their text;
# their drafts are written to legal-drafts.json instead.
PUBLISH_LEGAL = False
# Domains whose sign-ups must confirm their email (PAU; confirm with the owner).
VERIFIED_EMAIL_DOMAINS = ['paluniv.edu.ps']
# Sentences not supplied by either document (reported for approval).
OWN_COPY = []


def identity(prefix):
    global SERIAL
    SERIAL += 1
    return f'eduhope-v2-{prefix}-{SERIAL}'


def own(en):
    OWN_COPY.append(en)
    return en


def text(kind, en, ar, **extra):
    styles = {'color': NAVY, 'width': '100%', 'textAlign': 'start', 'lineHeight': '1.7', 'fontSize': '17px'}
    styles.update(extra.pop('styles', {}))
    element = {'id': identity(kind), 'type': kind, 'name': kind, 'content': en, 'styles': styles,
               'action': extra.pop('action', {'type': 'none'}), **extra,
               'localized': {'content': {'en': en, 'ar': ar}}}
    if kind == 'list':
        # Flow lists grow with their items (a fixed height clips them).
        element['styles'].update(height='auto', minHeight='0', flexShrink='0', alignSelf='stretch', backgroundColor='transparent', padding='0')
        element['listTitle'] = ''
        element['listItems'] = en.split('\n')
        element['listStyle'] = extra.get('listStyle', 'disc')
        element['localized']['listItems'] = {'en': en.split('\n'), 'ar': ar.split('\n')}
    return element


def heading(en, ar, tag='h2'):
    size = {'h1': '44px', 'h2': '32px', 'h3': '22px'}[tag]
    return text('heading', en, ar, headingTag=tag, styles={'fontWeight': '750', 'fontSize': size, 'lineHeight': '1.25'})


def paragraph(en, ar):
    return text('text', en, ar)


def bullets(en_items, ar_items, numbered=False):
    # Builder list elements use size containment (fixed height only), so each
    # item is its own text line, which grows naturally at every width.
    marks = [f'{n}.' for n in range(1, len(en_items) + 1)] if numbered else ['•'] * len(en_items)
    return [text('text', f'{mark} {en}', f'{mark} {ar}', styles={'paddingInlineStart': '8px'}) for mark, en, ar in zip(marks, en_items, ar_items)]


def button(en, ar, destination, secondary=False):
    action = {'type': 'openUrl', 'url': destination} if destination.startswith('ref:') else {'type': 'goToPage', 'pageId': 'eduhope-page-' + destination}
    colors = ({'backgroundColor': '#FFFFFF', 'textColor': GREEN, 'hoverBackgroundColor': SOFT, 'hoverTextColor': GREEN_DARK}
              if secondary else {'backgroundColor': GREEN, 'textColor': '#FFFFFF', 'hoverBackgroundColor': GREEN_DARK, 'hoverTextColor': '#FFFFFF'})
    return text('button', en, ar, action=action, **colors,
                styles={'width': 'auto', 'borderRadius': '999px', 'fontWeight': '700', 'fontSize': '16px', 'minHeight': '48px',
                        **({'border': f'1px solid {GREEN}'} if secondary else {})})


def form_block(key):
    return {'id': identity('form'), 'type': 'academyForm', 'name': 'Learning form placement', 'content': '',
            'styles': {'width': '100%'}, 'academy': {'formId': 'ref:forms.' + key}, 'action': {'type': 'none'}}


def section(name, elements, background='#FFFFFF', columns=None):
    def flat(items):
        out = []
        for item in items:
            out.extend(flat(item) if isinstance(item, list) else [item])
        return out
    groups = [flat(group) for group in (columns or [elements])]
    return {'id': identity('section'), 'name': name,
            'layout': {'width': 'full', 'paddingY': 'large', 'background': background},
            'rows': [{'id': identity('row'), 'layout': {'columns': len(groups), 'align': 'start', 'gap': 'large'},
                      'columns': [{'id': identity('column'), 'elements': items} for items in groups]}]}


LEVELS = [('Beginner Foundations', 'الأساسيات للمبتدئين', 'A1'), ('Beginner Communication', 'التواصل للمبتدئين', 'A1'),
          ('Elementary Communication', 'التواصل الأولي', 'A2'), ('Elementary Real-Life English', 'الإنجليزية الواقعية الأولية', 'A2'),
          ('Intermediate Communication', 'التواصل المتوسط', 'B1'), ('Intermediate Real-Life English', 'الإنجليزية الواقعية المتوسطة', 'B1'),
          ('Upper-Intermediate Communication', 'التواصل فوق المتوسط', 'B2'), ('Advanced Everyday Communication', 'التواصل اليومي المتقدم', 'B2'),
          ('Advanced Communication', 'التواصل المتقدم', 'C1'), ('Advanced Fluency and Professional Communication', 'الطلاقة المتقدمة والتواصل المهني', 'C1')]
CERTIFICATES = ['A1 English Speaking Certificate', 'A2 English Speaking Certificate', 'B1 English Speaking Certificate',
                'B2 English Speaking Certificate', 'C1 English Speaking Certificate', 'Complete English Speaking Course Certificate']
CERTIFICATES_AR = ['شهادة A1 في التحدّث باللغة الإنجليزية', 'شهادة A2 في التحدّث باللغة الإنجليزية', 'شهادة B1 في التحدّث باللغة الإنجليزية',
                   'شهادة B2 في التحدّث باللغة الإنجليزية', 'شهادة C1 في التحدّث باللغة الإنجليزية', 'شهادة إتمام دورة التحدّث باللغة الإنجليزية كاملة']
HOW_STEPS = ['Create an account.', 'Purchase the English course.', 'Start learning through 10 course levels.',
             'Receive a referral link after purchasing the course.', 'Share the course with others.', 'Earn eligible referral rewards.',
             'Make 4 successful course sales to become eligible to apply for Tuition Support.',
             'Apply for an Exchange Programme while studying with EduHope.']
HOW_STEPS_AR = ['أنشئ حساباً.', 'اشترِ دورة اللغة الإنجليزية.', 'ابدأ التعلّم عبر 10 مستويات دراسية.',
                'احصل على رابط إحالة بعد شراء الدورة.', 'شارك الدورة مع الآخرين.', 'اكسب مكافآت الإحالة المؤهلة.',
                'حقّق 4 مبيعات ناجحة للدورة لتصبح مؤهلاً للتقديم على دعم الرسوم الجامعية.',
                'قدّم طلباً للمشاركة في برنامج تبادل أثناء دراستك مع EduHope.']
AFFILIATE_NOTE = ("If you would like to promote EduHope without purchasing the course, you can apply to become an Affiliate.",
                  "إذا رغبت في التعريف بـ EduHope دون شراء الدورة، يمكنك التقديم لتصبح مسوّقاً بالعمولة.")
EXCHANGE_LINE = ("Active EduHope learners can apply for available exchange opportunities, subject to programme requirements.",
                 "يمكن لمتعلّمي EduHope النشطين التقديم على فرص التبادل المتاحة، وفقاً لمتطلبات البرنامج.")
TUITION_LOCKED = ("Make 4 successful course sales through your EduHope referral link to become eligible to apply for Tuition Support.",
                  "حقّق 4 مبيعات ناجحة للدورة عبر رابط إحالتك في EduHope لتصبح مؤهلاً للتقديم على دعم الرسوم الجامعية.")
LEVEL4 = ("Completing Level 4 is not a Tuition Support eligibility requirement.",
          "إكمال المستوى الرابع ليس شرطاً للأهلية لدعم الرسوم الجامعية.")


def home():
    welcome = ("EduHope is an online English-learning platform that combines practical English education with opportunities for students to learn, share, earn eligible referral rewards, apply for tuition support, and participate in exchange programmes.",
               "EduHope منصّة إلكترونية لتعلّم اللغة الإنجليزية تجمع بين التعليم العملي للغة الإنجليزية وفرص تتيح للطلاب التعلّم والمشاركة وكسب مكافآت الإحالة المؤهلة والتقديم على دعم الرسوم الجامعية والمشاركة في برامج التبادل.")
    hero = text('card', 'Your Gateway to Success. Learn. Grow. Give Back.', 'بوابتك إلى النجاح. تعلّم. تطوّر. ردّ الجميل.',
                variant='educationHero', imageUrl='ref:assets.hero.library', alt='Adult learners studying together in a library',
                description='Learn English, build your confidence, create opportunities, and help create opportunities for other learners.',
                primaryLabel='Start Learning', secondaryLabel='How It Works', focalX=60, focalY=50,
                action={'type': 'goToPage', 'pageId': 'eduhope-page-course'}, secondaryAction={'type': 'goToPage', 'pageId': 'eduhope-page-how-it-works'},
                styles={'borderRadius': '24px'})
    hero['localized'].update(description={'en': hero['description'], 'ar': 'تعلّم الإنجليزية، وابنِ ثقتك بنفسك، واصنع الفرص، وساعد في صنع الفرص لمتعلّمين آخرين.'},
                             primaryLabel={'en': 'Start Learning', 'ar': 'ابدأ التعلّم'}, secondaryLabel={'en': 'How It Works', 'ar': 'كيف يعمل'},
                             alt={'en': hero['alt'], 'ar': 'متعلّمون بالغون يدرسون معاً في مكتبة'})
    focus = ['Practical communication', 'Speaking', 'Listening', 'Vocabulary', 'Pronunciation', 'Real-life English',
             'Academic communication', 'Professional communication', 'Confidence building']
    focus_ar = ['التواصل العملي', 'التحدّث', 'الاستماع', 'المفردات', 'النطق', 'الإنجليزية في الحياة الواقعية',
                'التواصل الأكاديمي', 'التواصل المهني', 'بناء الثقة']
    return [section('Hero', [hero]),
            section('A. Welcome to EduHope', [heading('Welcome to EduHope', 'مرحباً بك في EduHope'), paragraph(*welcome)], SOFT),
            section('B. Learn English with Confidence', [heading('Learn English with Confidence', 'تعلّم الإنجليزية بثقة'),
                    paragraph('The course focuses on:', 'تركّز الدورة على:'), bullets(focus, focus_ar)]),
            section('C. How EduHope Works', [heading('How EduHope Works', 'كيف تعمل EduHope'), bullets(HOW_STEPS, HOW_STEPS_AR, True),
                    paragraph(*AFFILIATE_NOTE), button('Become an Affiliate', 'كن مسوّقاً بالعمولة', 'affiliate', True)], SOFT),
            section('D and E. Programmes', [], columns=[
                [heading('Tuition Support', 'دعم الرسوم الجامعية', 'h3'), paragraph(*TUITION_LOCKED), paragraph(*LEVEL4),
                 button('Learn About Tuition Support', 'تعرّف على دعم الرسوم الجامعية', 'tuition-support')],
                [heading('Exchange Programme', 'برنامج التبادل', 'h3'), paragraph(*EXCHANGE_LINE),
                 button('Explore Exchange Opportunities', 'استكشف فرص التبادل', 'exchange')]]),
            section('F. Join EduHope', [heading('Join EduHope', 'انضم إلى EduHope'),
                    paragraph(own('Create an account and begin your learning journey.'), 'أنشئ حساباً وابدأ رحلتك في التعلّم.'),
                    button('Register Now', 'سجّل الآن', 'ref:routes.register'), button('Explore the Course', 'استكشف الدورة', 'course', True)], SOFT)]


def course():
    areas = ['Speaking', 'Listening', 'Everyday Conversations', 'Vocabulary Development', 'Useful Expressions', 'Pronunciation',
             'Everyday English', 'Academic English', 'Professional Communication', 'Confidence Building']
    areas_ar = ['التحدّث', 'الاستماع', 'المحادثات اليومية', 'تطوير المفردات', 'العبارات المفيدة', 'النطق',
                'الإنجليزية اليومية', 'الإنجليزية الأكاديمية', 'التواصل المهني', 'بناء الثقة']
    features = ['One complete English course.', '10 course levels.', 'Lifetime access after successful purchase.', 'Student progress tracking.',
                'Level completion tracking.', 'Clear progress indicators.', 'Continue Learning button.',
                'Course access activated only after confirmed successful payment.']
    features_ar = ['دورة إنجليزية واحدة كاملة.', '10 مستويات دراسية.', 'وصول مدى الحياة بعد الشراء الناجح.', 'متابعة تقدّم الطالب.',
                   'متابعة إكمال المستويات.', 'مؤشرات تقدّم واضحة.', 'زر «تابع التعلّم».', 'تفعيل الوصول إلى الدورة فقط بعد تأكيد نجاح الدفع.']
    levels = [f'Level {n} — {en} ({cefr})' for n, (en, _, cefr) in enumerate(LEVELS, 1)]
    levels_ar = [f'المستوى {n} — {ar} ({cefr})' for n, (_, ar, cefr) in enumerate(LEVELS, 1)]
    topic_steps = ['Topic title', 'Real-life situation', 'Short dialogue', 'Listen', 'Transcript', 'Understand', 'Useful expressions',
                   'Vocabulary', 'Listen & Match with Pictures', 'Communication practice', 'Speak Now']
    topic_steps_ar = ['عنوان الموضوع', 'موقف من الحياة الواقعية', 'حوار قصير', 'استمع', 'النص المكتوب', 'افهم', 'عبارات مفيدة',
                      'المفردات', 'استمع وطابق مع الصور', 'تدريب على التواصل', 'تحدّث الآن']
    return [section('Course introduction', [heading('EduHope English Conversation Course', 'دورة EduHope للمحادثة باللغة الإنجليزية', 'h1'),
                    paragraph('Learn English in real-life situations.', 'تعلّم الإنجليزية من خلال مواقف الحياة الواقعية.'),
                    heading('$30 USD', '30 دولاراً أمريكياً', 'h2'),
                    paragraph(own('One-time payment.') + ' The course consists of one complete programme divided into 10 course levels.',
                              'دفعة واحدة. تتكوّن الدورة من برنامج واحد كامل مقسّم إلى 10 مستويات دراسية.'),
                    button('Enroll Now', 'سجّل في الدورة الآن', 'ref:routes.course'),
                    paragraph('Course access activated only after confirmed successful payment. A student receives a referral link after successfully purchasing the English course.',
                              'يُفعَّل الوصول إلى الدورة فقط بعد تأكيد نجاح الدفع. يحصل الطالب على رابط إحالة بعد شراء دورة اللغة الإنجليزية بنجاح.')]),
            section('Core principle', [heading('Students should not only learn English. They should use English.',
                                               'لا يكفي أن يتعلّم الطلاب الإنجليزية، بل عليهم أن يستخدموها.'),
                    paragraph('LISTEN → SEE → UNDERSTAND → MATCH → PRACTICE → SPEAK → COMMUNICATE',
                              'استمع ← شاهد ← افهم ← طابق ← تدرّب ← تحدّث ← تواصل')], SOFT),
            section('Areas and features', [], columns=[
                [heading('Course Areas', 'مجالات الدورة', 'h3'), bullets(areas, areas_ar)],
                [heading('Course Features', 'مزايا الدورة', 'h3'), bullets(features, features_ar)]]),
            section('Levels', [heading('10 Levels', '10 مستويات'), bullets(levels, levels_ar, True),
                    paragraph('The original course contains 89 topics.', 'تحتوي الدورة الأصلية على 89 موضوعاً.')], SOFT),
            section('Topic structure', [heading('Every topic follows a consistent structure', 'يتبع كل موضوع بنية ثابتة'),
                    bullets(topic_steps, topic_steps_ar, True)]),
            section('Exams and certificates', [heading('Exams and certificates', 'الامتحانات والشهادات'),
                    paragraph('Five final exams: A1, A2, B1, B2 and C1. The required passing score is 70%. Students must be allowed to retake final exams; retakes use new questions.',
                              'خمسة امتحانات نهائية: A1 وA2 وB1 وB2 وC1. درجة النجاح المطلوبة 70%. يُسمح للطلاب بإعادة الامتحانات النهائية، وتُستخدم أسئلة جديدة عند الإعادة.'),
                    bullets(CERTIFICATES, CERTIFICATES_AR),
                    paragraph('Students do not need to complete the entire course to receive a level certificate.',
                              'لا يحتاج الطلاب إلى إكمال الدورة كاملة للحصول على شهادة المستوى.')], SOFT)]


def how_it_works():
    return [section('How It Works', [heading('How It Works', 'كيف يعمل', 'h1')]),
            section('Learn and Share', [], SOFT, columns=[
                [heading('🎓 Learn', '🎓 تعلّم', 'h3'),
                 paragraph('Improve your English-speaking skills through our practical 10-level course, designed to help you communicate confidently in real-life situations.',
                           'طوّر مهاراتك في التحدّث بالإنجليزية من خلال دورتنا العملية ذات المستويات العشرة، المصمّمة لتساعدك على التواصل بثقة في مواقف الحياة الواقعية.')],
                [heading('🔗 Share', '🔗 شارك', 'h3'),
                 paragraph('Enjoy the course and share it with others. Earn a $10 reward for every eligible course purchase made through your personal link.',
                           'استمتع بالدورة وشاركها مع الآخرين. اكسب مكافأة قدرها 10 دولارات عن كل عملية شراء مؤهلة للدورة تتم عبر رابطك الشخصي.')]]),
            section('Steps', [heading('How EduHope Works', 'كيف تعمل EduHope'), bullets(HOW_STEPS, HOW_STEPS_AR, True), paragraph(*LEVEL4),
                    button('Explore the Course', 'استكشف الدورة', 'course'), paragraph(*AFFILIATE_NOTE),
                    button('Become an Affiliate', 'كن مسوّقاً بالعمولة', 'affiliate', True)])]


def affiliate():
    rules = ['An affiliate does not have to purchase the English course.', 'After approval, they receive a unique affiliate referral link.',
             '$10 for each eligible direct course sale.', 'Only direct referrals count.',
             'Rewards are subject to verification and the Referral Programme Terms & Conditions.', 'Earnings are not guaranteed.']
    rules_ar = ['لا يلزم المسوّق بالعمولة شراء دورة اللغة الإنجليزية.', 'بعد الموافقة، يحصل على رابط إحالة فريد خاص بالمسوّق.',
                '10 دولارات عن كل عملية بيع مباشرة مؤهلة للدورة.', 'تُحتسب الإحالات المباشرة فقط.',
                'تخضع المكافآت للتحقّق ولشروط وأحكام برنامج الإحالة.', 'الأرباح غير مضمونة.']
    return [section('Become an Affiliate', [heading('Become an Affiliate', 'كن مسوّقاً بالعمولة', 'h1'),
                    paragraph('This page is for users who want to promote EduHope without purchasing the English course.',
                              'هذه الصفحة مخصّصة للمستخدمين الذين يرغبون في التعريف بـ EduHope دون شراء دورة اللغة الإنجليزية.'),
                    bullets(rules, rules_ar)]),
            section('Affiliate Application', [heading('Affiliate Application', 'طلب الانضمام كمسوّق بالعمولة'), form_block('affiliate')], SOFT)]


def about():
    paras = [("EduHope combines practical English language education with opportunity and hope.",
              "تجمع EduHope بين التعليم العملي للغة الإنجليزية والفرصة والأمل."),
             ("Our primary mission is to make English learning accessible, practical, and meaningful. EduHope helps learners develop real-life English communication skills, improve their confidence, and use English in everyday, academic, and professional situations.",
              "مهمّتنا الأساسية أن نجعل تعلّم الإنجليزية متاحاً وعملياً وذا معنى. تساعد EduHope المتعلّمين على تطوير مهارات التواصل بالإنجليزية في الحياة الواقعية، وتعزيز ثقتهم بأنفسهم، واستخدام الإنجليزية في المواقف اليومية والأكاديمية والمهنية."),
             ("Beyond language learning, EduHope aims to create opportunities for learners to grow, share, and contribute to their communities.",
              "وإلى جانب تعلّم اللغة، تسعى EduHope إلى توفير فرص للمتعلّمين كي ينموا ويشاركوا ويُسهموا في مجتمعاتهم."),
             ("Through our referral programme, eligible learners and approved affiliates can help introduce others to EduHope and earn rewards for successful course sales.",
              "ومن خلال برنامج الإحالة، يستطيع المتعلّمون المؤهلون والمسوّقون المعتمدون تعريف الآخرين بـ EduHope وكسب مكافآت عن مبيعات الدورة الناجحة."),
             ("Through our Tuition Support initiative, a portion of eligible course sales will be allocated to supporting students facing financial difficulties with their university tuition fees.",
              "ومن خلال مبادرة دعم الرسوم الجامعية، سيُخصَّص جزء من مبيعات الدورة المؤهلة لدعم الطلاب الذين يواجهون صعوبات مالية في سداد رسومهم الجامعية."),
             ("We also aim to connect learning with wider opportunities through exchange programmes.",
              "كما نسعى إلى ربط التعلّم بفرص أوسع من خلال برامج التبادل.")]
    return [section('About EduHope', [heading('About EduHope', 'عن EduHope', 'h1')] + [paragraph(*p) for p in paras]),
            section('Philosophy', [paragraph('EduHope is built around one simple idea:', 'تقوم EduHope على فكرة واحدة بسيطة:'),
                    heading('Learn. Grow. Give Back.', 'تعلّم. تطوّر. ردّ الجميل.'),
                    paragraph("EduHope is not only about learning English. It is about helping learners grow, creating opportunities, and making education more accessible to those who need support.",
                              "EduHope ليست مجرد تعلّم للغة الإنجليزية، بل هي مساعدة المتعلّمين على النمو، وصنع الفرص، وجعل التعليم أكثر إتاحة لمن يحتاجون إلى الدعم.")], SOFT)]


def tuition():
    description = ("At EduHope, we believe that learning is not only about helping individual learners—it is also about creating opportunities for others to learn and succeed. We believe that education is a right for everyone, and every learner should have the opportunity to pursue their education regardless of their financial circumstances. Through EduHope, a portion of eligible course sales will be allocated to support students who are facing financial difficulties and need assistance with their university tuition fees. In this way, every learner who chooses to learn with EduHope can also help create an opportunity for another student.",
                   "نؤمن في EduHope بأن التعلّم لا يقتصر على مساعدة المتعلّم الفرد، بل يشمل أيضاً صنع فرص تتيح للآخرين أن يتعلّموا وينجحوا. ونؤمن بأن التعليم حقّ للجميع، وأن لكل متعلّم الحق في مواصلة تعليمه بصرف النظر عن ظروفه المالية. ومن خلال EduHope، سيُخصَّص جزء من مبيعات الدورة المؤهلة لدعم الطلاب الذين يواجهون صعوبات مالية ويحتاجون إلى المساعدة في سداد رسومهم الجامعية. وبهذا يستطيع كل متعلّم يختار التعلّم مع EduHope أن يُسهم أيضاً في صنع فرصة لطالب آخر.")
    excluded = ['Failed payments.', 'Cancelled purchases.', 'Refunded purchases.', 'Duplicate purchases.', 'Self-referrals.',
                'Fraudulent purchases.', 'Invalid referral transactions.']
    excluded_ar = ['المدفوعات الفاشلة.', 'عمليات الشراء الملغاة.', 'عمليات الشراء المستردّة.', 'عمليات الشراء المكرّرة.', 'الإحالات الذاتية.',
                   'عمليات الشراء الاحتيالية.', 'معاملات الإحالة غير الصالحة.']
    return [section('Tuition Support', [heading('Tuition Support', 'دعم الرسوم الجامعية', 'h1'), paragraph(*description),
                    heading('Learn. Grow. Give Back.', 'تعلّم. تطوّر. ردّ الجميل.', 'h3')]),
            section('Eligibility', [heading('Tuition Support Eligibility', 'الأهلية لدعم الرسوم الجامعية'),
                    paragraph('The student must make 4 successful course sales through their own EduHope referral link. After reaching 4 eligible sales, the student becomes eligible to apply for Tuition Support.',
                              'يجب أن يحقّق الطالب 4 مبيعات ناجحة للدورة عبر رابط الإحالة الخاص به في EduHope. وبعد بلوغ 4 مبيعات مؤهلة، يصبح الطالب مؤهلاً للتقديم على دعم الرسوم الجامعية.'),
                    paragraph(*LEVEL4),
                    paragraph('Only valid and verified purchases count. The system must not count:', 'تُحتسب عمليات الشراء الصحيحة والموثّقة فقط. ولا تُحتسب:'),
                    bullets(excluded, excluded_ar),
                    paragraph('Submitting an application does not guarantee financial assistance.', 'تقديم الطلب لا يضمن الحصول على مساعدة مالية.')], SOFT),
            section('Application', [heading('Tuition Support Application', 'طلب دعم الرسوم الجامعية'), form_block('tuition')])]


def exchange():
    return [section('Exchange Programme', [heading('Exchange Programme', 'برنامج التبادل', 'h1'), paragraph(*EXCHANGE_LINE),
                    paragraph('Exchange Programme eligibility is separate from Tuition Support. Students do not need:',
                              'الأهلية لبرنامج التبادل منفصلة عن دعم الرسوم الجامعية. لا يحتاج الطلاب إلى:'),
                    bullets(['4 referral sales.', 'Tuition Support eligibility.', 'Tuition Support approval.'],
                            ['4 مبيعات إحالة.', 'الأهلية لدعم الرسوم الجامعية.', 'الموافقة على دعم الرسوم الجامعية.']),
                    paragraph('The student must simply be an active EduHope learner and meet the specific programme requirements.',
                              'يكفي أن يكون الطالب متعلّماً نشطاً في EduHope وأن يستوفي متطلبات البرنامج المحدّدة.')]),
            section('Application', [heading('Exchange Application Form', 'نموذج طلب برنامج التبادل'), form_block('exchange')], SOFT)]


def faq():
    qa = [("What is EduHope?", "ما هي EduHope؟",
           "EduHope is an online English-learning platform that combines practical English education with referral opportunities, Tuition Support, and Exchange Programme opportunities.",
           "EduHope منصّة إلكترونية لتعلّم اللغة الإنجليزية تجمع بين التعليم العملي للغة الإنجليزية وفرص الإحالة ودعم الرسوم الجامعية وفرص برنامج التبادل."),
          ("How much does the English course cost?", "كم تكلفة دورة اللغة الإنجليزية؟",
           "The EduHope English Conversation Course costs $30 USD. The price can be changed by Admin.",
           "تبلغ تكلفة دورة EduHope للمحادثة باللغة الإنجليزية 30 دولاراً أمريكياً. ويمكن للإدارة تغيير السعر."),
          ("How many levels are in the course?", "كم عدد المستويات في الدورة؟", "The course contains 10 levels.", "تحتوي الدورة على 10 مستويات."),
          ("What does the course include?", "ماذا تتضمّن الدورة؟",
           "The course focuses on practical English communication, speaking, listening, vocabulary, pronunciation, useful expressions, everyday English, academic English, and professional communication.",
           "تركّز الدورة على التواصل العملي بالإنجليزية والتحدّث والاستماع والمفردات والنطق والعبارات المفيدة والإنجليزية اليومية والإنجليزية الأكاديمية والتواصل المهني."),
          ("Do I receive a referral link when I register?", "هل أحصل على رابط إحالة عند التسجيل؟",
           "No. A student receives a referral link after successfully purchasing the English course. A user who has not purchased the course can apply to become an Affiliate.",
           "لا. يحصل الطالب على رابط إحالة بعد شراء دورة اللغة الإنجليزية بنجاح. ويمكن للمستخدم الذي لم يشترِ الدورة التقديم ليصبح مسوّقاً بالعمولة."),
          ("How much is the referral reward?", "كم تبلغ مكافأة الإحالة؟",
           "The current reward is $10 for each eligible direct course sale. Rewards are subject to verification and the Referral Programme Terms & Conditions. Earnings are not guaranteed.",
           "المكافأة الحالية 10 دولارات عن كل عملية بيع مباشرة مؤهلة للدورة. تخضع المكافآت للتحقّق ولشروط وأحكام برنامج الإحالة. الأرباح غير مضمونة."),
          ("How can I become eligible for Tuition Support?", "كيف أصبح مؤهلاً لدعم الرسوم الجامعية؟",
           "You must make 4 successful course sales through your EduHope referral link.", "يجب أن تحقّق 4 مبيعات ناجحة للدورة عبر رابط إحالتك في EduHope."),
          ("Do I need to complete Level 4?", "هل أحتاج إلى إكمال المستوى الرابع؟",
           "No. Completing Level 4 is not a Tuition Support requirement. Tuition Support eligibility is based on making 4 successful course sales through your referral link.",
           "لا. إكمال المستوى الرابع ليس شرطاً لدعم الرسوم الجامعية. تعتمد الأهلية لدعم الرسوم الجامعية على تحقيق 4 مبيعات ناجحة للدورة عبر رابط إحالتك."),
          ("Does reaching 4 sales guarantee Tuition Support?", "هل يضمن بلوغ 4 مبيعات الحصول على دعم الرسوم الجامعية؟",
           "No. Reaching 4 successful sales makes you eligible to apply. The application is reviewed and financial assistance is not guaranteed.",
           "لا. بلوغ 4 مبيعات ناجحة يجعلك مؤهلاً للتقديم. يخضع الطلب للمراجعة، والمساعدة المالية غير مضمونة."),
          ("Can I apply for an Exchange Programme without making 4 sales?", "هل يمكنني التقديم على برنامج تبادل دون تحقيق 4 مبيعات؟",
           "Yes. Active EduHope learners can apply for available Exchange Programmes, subject to programme requirements.",
           "نعم. يمكن لمتعلّمي EduHope النشطين التقديم على برامج التبادل المتاحة، وفقاً لمتطلبات البرنامج."),
          ("Can I become an Affiliate without purchasing the course?", "هل يمكنني أن أصبح مسوّقاً بالعمولة دون شراء الدورة؟",
           "Yes. You can apply through the Become an Affiliate page.", "نعم. يمكنك التقديم عبر صفحة «كن مسوّقاً بالعمولة»."),
          ("When can I withdraw rewards?", "متى يمكنني سحب المكافآت؟",
           "You can request a withdrawal when your available balance reaches the minimum withdrawal amount configured by EduHope. Pending rewards cannot be withdrawn.",
           "يمكنك طلب السحب عندما يبلغ رصيدك المتاح الحد الأدنى للسحب الذي تحدّده EduHope. لا يمكن سحب المكافآت المعلّقة."),
          ("How can I contact EduHope?", "كيف يمكنني التواصل مع EduHope؟",
           "Use the Contact page to send a message to the EduHope team.", "استخدم صفحة «تواصل معنا» لإرسال رسالة إلى فريق EduHope.")]
    return [section('FAQ', [heading('Frequently Asked Questions', 'الأسئلة الشائعة', 'h1')])] + [
        section(f'FAQ {i}', [heading(q, qa_ar, 'h3'), paragraph(a, a_ar)], SOFT if i % 2 else '#FFFFFF')
        for i, (q, qa_ar, a, a_ar) in enumerate(qa, 1)]


def contact():
    return [section('Contact', [heading('Contact', 'تواصل معنا', 'h1'),
                    paragraph('Use the Contact page to send a message to the EduHope team.', 'استخدم صفحة «تواصل معنا» لإرسال رسالة إلى فريق EduHope.'),
                    form_block('contact')])]


DRAFT = (own('Draft for owner approval. This text summarises the EduHope programme rules and is not final legal advice.'),
         'مسودة بانتظار اعتماد المالك. يلخّص هذا النص قواعد برامج EduHope وليس صيغة قانونية نهائية.')


def terms():
    blocks = [
        ('Course Purchase', 'شراء الدورة',
         ['The EduHope English Conversation Course costs $30 USD as a one-time payment. The price can be changed by Admin.',
          'Course access is activated only after confirmed successful payment and gives lifetime access to one complete course of 10 levels.',
          'Payment is verified by the backend; a success message shown in the browser alone does not activate the course.'],
         ['تبلغ تكلفة دورة EduHope للمحادثة باللغة الإنجليزية 30 دولاراً أمريكياً تُدفع مرة واحدة. ويمكن للإدارة تغيير السعر.',
          'يُفعَّل الوصول إلى الدورة فقط بعد تأكيد نجاح الدفع، ويمنح وصولاً مدى الحياة إلى دورة واحدة كاملة من 10 مستويات.',
          'يتحقّق النظام من الدفع؛ ولا تكفي رسالة نجاح تظهر في المتصفح وحدها لتفعيل الدورة.']),
        ('Referral Programme', 'برنامج الإحالة',
         ['A student receives a referral link only after successfully purchasing the course.',
          'The reward is $10 for each eligible direct course sale. Only direct referrals count; there are no multi-level, downline, second-level or indirect rewards.',
          'Failed, cancelled, refunded, duplicate, self-referral and fraudulent purchases do not count. Rewards start as Pending and become Available after verification.',
          'Referral rewards are based on eligible successful sales. Earnings are not guaranteed.'],
         ['يحصل الطالب على رابط إحالة فقط بعد شراء الدورة بنجاح.',
          'المكافأة 10 دولارات عن كل عملية بيع مباشرة مؤهلة للدورة. تُحتسب الإحالات المباشرة فقط؛ ولا توجد مكافآت متعدّدة المستويات أو من المستوى الثاني أو غير مباشرة.',
          'لا تُحتسب عمليات الشراء الفاشلة أو الملغاة أو المستردّة أو المكرّرة أو الإحالات الذاتية أو الاحتيالية. تبدأ المكافآت بحالة «معلّقة» وتصبح «متاحة» بعد التحقّق.',
          'تعتمد مكافآت الإحالة على المبيعات الناجحة المؤهلة. الأرباح غير مضمونة.']),
        ('Affiliate Programme', 'برنامج المسوّقين بالعمولة',
         ['An affiliate does not have to purchase the English course. Applications are reviewed by Admin, who can approve, reject, suspend or reactivate affiliates.',
          'Approved affiliates receive a unique referral link and follow the same reward and withdrawal rules.'],
         ['لا يلزم المسوّق بالعمولة شراء دورة اللغة الإنجليزية. تراجع الإدارة الطلبات، ويمكنها الموافقة عليها أو رفضها أو تعليق المسوّقين أو إعادة تفعيلهم.',
          'يحصل المسوّقون المعتمدون على رابط إحالة فريد ويخضعون لقواعد المكافآت والسحب نفسها.']),
        ('Tuition Support', 'دعم الرسوم الجامعية',
         ['Eligibility to apply requires 4 successful, verified course sales through your own referral link. Completing Level 4 or any level is not a requirement.',
          'If a counted purchase is later refunded or invalidated, the eligible sales count is updated.',
          'Submitting an application does not guarantee financial assistance.'],
         ['تتطلّب الأهلية للتقديم 4 مبيعات ناجحة وموثّقة للدورة عبر رابط إحالتك. إكمال المستوى الرابع أو أي مستوى آخر ليس شرطاً.',
          'إذا استُردّت عملية شراء محتسبة أو أُلغيت صلاحيتها لاحقاً، يُحدَّث عدد المبيعات المؤهلة.',
          'تقديم الطلب لا يضمن الحصول على مساعدة مالية.']),
        ('Exchange Programme', 'برنامج التبادل',
         ['Active EduHope learners can apply for available exchange opportunities, subject to programme requirements. 4 referral sales are not required.',
          'Applications are reviewed by Admin and receive one of these statuses: Submitted, Under Review, Approved or Not Approved.'],
         ['يمكن لمتعلّمي EduHope النشطين التقديم على فرص التبادل المتاحة وفقاً لمتطلبات البرنامج. لا تُشترط 4 مبيعات إحالة.',
          'تراجع الإدارة الطلبات، ويحصل كل طلب على إحدى الحالات التالية: مُقدَّم، قيد المراجعة، مقبول، غير مقبول.']),
        ('Withdrawals', 'السحوبات',
         ['Only Available Balance can be withdrawn, and only once it reaches the minimum withdrawal amount set by Admin. Pending rewards cannot be withdrawn.',
          'You must confirm that the payment information you provide is correct and belongs to you. Users cannot manually edit their wallet.'],
         ['يمكن سحب الرصيد المتاح فقط، وذلك بعد أن يبلغ الحد الأدنى للسحب الذي تحدّده الإدارة. لا يمكن سحب المكافآت المعلّقة.',
          'يجب أن تؤكّد أن معلومات الدفع التي تقدّمها صحيحة وتعود إليك. لا يمكن للمستخدمين تعديل محافظهم يدوياً.'])]
    return [section('Terms & Conditions', [heading('Terms & Conditions', 'الشروط والأحكام', 'h1'), paragraph(*DRAFT)])] + [
        section(en, [heading(en, ar, 'h3'), bullets(items, items_ar)], SOFT if i % 2 else '#FFFFFF')
        for i, (en, ar, items, items_ar) in enumerate(blocks, 1)]


def privacy():
    collected = [own('Account details: full name, email address, country and university (if provided).'),
                 own('Course purchases, payment status and course progress.'),
                 own('Referral, reward, wallet and withdrawal records.'),
                 own('Affiliate, Tuition Support and Exchange Programme applications, including any supporting documents you upload.'),
                 own('Messages you send through the Contact page.')]
    collected_ar = ['بيانات الحساب: الاسم الكامل والبريد الإلكتروني والدولة والجامعة (إن وُجدت).',
                    'عمليات شراء الدورة وحالة الدفع والتقدّم في الدورة.',
                    'سجلات الإحالة والمكافآت والمحفظة والسحوبات.',
                    'طلبات برنامج المسوّقين بالعمولة ودعم الرسوم الجامعية وبرنامج التبادل، بما في ذلك أي مستندات داعمة ترفعها.',
                    'الرسائل التي ترسلها عبر صفحة «تواصل معنا».']
    use = [own('To provide course access and track your progress.'), own('To verify payments, referral sales, rewards and withdrawals.'),
           own('To review your applications.'), own('To send in-dashboard notifications and answer your messages.')]
    use_ar = ['لتوفير الوصول إلى الدورة ومتابعة تقدّمك.', 'للتحقّق من المدفوعات ومبيعات الإحالة والمكافآت والسحوبات.',
              'لمراجعة طلباتك.', 'لإرسال الإشعارات داخل لوحة التحكم والرد على رسائلك.']
    return [section('Privacy Policy', [heading('Privacy Policy', 'سياسة الخصوصية', 'h1'), paragraph(*DRAFT)]),
            section('What we collect', [heading(own('What we collect'), 'ما البيانات التي نجمعها', 'h3'), bullets(collected, collected_ar)], SOFT),
            section('How we use it', [heading(own('How we use it'), 'كيف نستخدمها', 'h3'), bullets(use, use_ar)]),
            section('Access', [heading(own('Who can see it'), 'من يمكنه الاطّلاع عليها', 'h3'),
                    paragraph(own('Applications, supporting documents and contact messages are private and available only to authorized EduHope administrators. Wallet balances and payment status can only be changed by secure backend processes.'),
                              'الطلبات والمستندات الداعمة ورسائل التواصل خاصة ومتاحة فقط لمسؤولي EduHope المخوّلين. ولا يمكن تغيير أرصدة المحافظ وحالة الدفع إلا من خلال عمليات آمنة في النظام.'),
                    paragraph(own('To ask about your data, use the Contact page to send a message to the EduHope team.'),
                              'للاستفسار عن بياناتك، استخدم صفحة «تواصل معنا» لإرسال رسالة إلى فريق EduHope.')], SOFT)]


# key, slug, English name, Arabic name, shown in the header menu, builder
PAGES = [('home', '/', 'Home', 'الرئيسية', True, home), ('course', '/course', 'Course', 'الدورة', True, course),
         ('how-it-works', '/how-it-works', 'How It Works', 'كيف يعمل', True, how_it_works),
         ('affiliate', '/become-an-affiliate', 'Become an Affiliate', 'كن مسوّقاً بالعمولة', True, affiliate),
         ('about', '/about', 'About EduHope', 'عن EduHope', True, about),
         ('tuition-support', '/tuition-support', 'Tuition Support', 'دعم الرسوم الجامعية', True, tuition),
         ('exchange', '/exchange', 'Exchange Programme', 'برنامج التبادل', False, exchange),
         ('faq', '/faq', 'FAQ', 'الأسئلة الشائعة', True, faq), ('contact', '/contact', 'Contact', 'تواصل معنا', True, contact),
         ('terms', '/terms', 'Terms & Conditions', 'الشروط والأحكام', False, terms),
         ('privacy', '/privacy', 'Privacy Policy', 'سياسة الخصوصية', False, privacy)]
DESCRIPTION = ('EduHope is an online English-learning platform that combines practical English education with opportunities for students to learn, share, earn eligible referral rewards, apply for tuition support, and participate in exchange programmes.',
               'EduHope منصّة إلكترونية لتعلّم اللغة الإنجليزية تجمع بين التعليم العملي للغة الإنجليزية وفرص تتيح للطلاب التعلّم والمشاركة وكسب مكافآت الإحالة المؤهلة والتقديم على دعم الرسوم الجامعية والمشاركة في برامج التبادل.')


def main():
    current = json.loads((ROOT / 'website.json').read_text())
    project = copy.deepcopy(current)
    specs = [spec for spec in PAGES if PUBLISH_LEGAL or spec[0] not in {'terms', 'privacy'}]
    drafts = [spec for spec in PAGES if spec not in specs]
    project['pages'] = [{'id': 'eduhope-page-' + key, 'name': en, 'slug': slug, 'order': order, 'access': 'public', 'pageType': 'main',
                         'isDefault': key == 'home', 'navigationLabel': en, 'showInNavigation': nav, 'sections': build(),
                         'localized': {'name': {'en': en, 'ar': ar}, 'navigationLabel': {'en': en, 'ar': ar}},
                         'seo': {'title': f'{en} | EduHope', 'description': DESCRIPTION[0],
                                 'localized': {'title': {'en': f'{en} | EduHope', 'ar': f'{ar} | EduHope'},
                                               'description': {'en': DESCRIPTION[0], 'ar': DESCRIPTION[1]}}}}
                        for order, (key, slug, en, ar, nav, build) in enumerate(specs)]
    legal = [(key, slug, en, ar, build()) for key, slug, en, ar, _, build in drafts]
    chrome = project['siteChrome']
    chrome.update(brand='', description='EduHope — Learn English. Build confidence. Create opportunities.', rights='All rights reserved.',
                  footerShopTitle='Explore', footerHelpTitle='More information', footerLanguageLabel='English | العربية',
                  footerShopLinks='\n'.join('eduhope-page-' + k for k in ('home', 'course', 'how-it-works', 'affiliate', 'about')),
                  footerHelpLinks='\n'.join('eduhope-page-' + k for k in ('tuition-support', 'faq', 'contact', 'privacy', 'terms')
                                             if PUBLISH_LEGAL or k not in {'privacy', 'terms'}))
    chrome['localized'] = {'description': {'ar': 'EduHope — تعلّم الإنجليزية. ابنِ ثقتك. اصنع الفرص.'}, 'rights': {'ar': 'جميع الحقوق محفوظة.'},
                           'footerShopTitle': {'ar': 'استكشف'}, 'footerHelpTitle': {'ar': 'معلومات إضافية'}}
    # Tenant-owned registration profile read by the academy sign-up form.
    # Terms acceptance is required once the approved Terms & Privacy pages are published.
    project['academyRegistration'] = {'fields': ['country', 'university'], 'requireTerms': PUBLISH_LEGAL,
                                      'termsPageId': 'eduhope-page-terms', 'privacyPageId': 'eduhope-page-privacy',
                                      'verifiedEmailDomains': VERIFIED_EMAIL_DOMAINS}
    project['academyChrome'] = {'signUpLabel': {'en': 'Register', 'ar': 'التسجيل'}, 'languageSwitcher': 'text'}
    (ROOT / 'website.json').write_text(json.dumps(project, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'legal-drafts.json').write_text(json.dumps([{'key': k, 'slug': sl, 'name': {'en': en, 'ar': ar}, 'sections': sec} for k, sl, en, ar, sec in legal], ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'own-copy.json').write_text(json.dumps(sorted(set(OWN_COPY)), ensure_ascii=False, indent=2) + '\n')
    print(f'Rebuilt {len(project["pages"])} pages; {len(set(OWN_COPY))} owner-approval sentences listed in own-copy.json. No database writes.')


if __name__ == '__main__':
    main()
