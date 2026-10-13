import { VocabularyCard, ExpressionCard, SpeakerTip, SituationCard } from "../components/ELearning/content/LessonCards";
import { ChooseBestResponse, SpeakNow } from "../components/ELearning/content/PracticeActivities";
import LessonStepTracker from "../components/ELearning/content/LessonStepTracker";
import { LESSON_STEPS, stepAnchor } from "../utils/lessonSteps";
import TopicRowsSample from "./TopicRowsSample";
// Sample data and extra sections for the dev-only EH component gallery.
// Existing EduHope (tenant 18) uploads, read through the dev proxy.
export const SAMPLE = {
  photo: "/uploads/tenant_18/builder_assets/6ad27da5369a45a3a4ba55420cf0f0c7.jpg",
  logo: "/uploads/tenant_18/builder_assets/8d0d8c9d7e44460abb21299b4e24e6ff.jpg",
  pictures: ["a2c73f1320d54c2f94c7ebfc81b9f579", "a5d42f39dab64e6198bd6a2d1d5a2b9b", "596e5ef0f480436983eca5726df66995", "b23cefc2c22e4e59a45ed8b5ee1a2939"].map(id => `/uploads/tenant_18/builder_assets/${id}.png`),
  dialogue: "Lina: Hello. Is this seat free?\nOmar: Yes, it is. Please sit here.\nLina: Thank you. My name is Lina. What is your name?\nOmar: I am Omar. I study engineering.",
};


// Lesson recordings are private to enrolled learners, so the gallery plays a
// generated one-second tone instead.
export function sampleToneUrl() {
  const rate = 8000, samples = rate, data = new DataView(new ArrayBuffer(44 + samples * 2));
  const text = (offset, value) => [...value].forEach((char, i) => data.setUint8(offset + i, char.charCodeAt(0)));
  text(0, "RIFF"); data.setUint32(4, 36 + samples * 2, true); text(8, "WAVEfmt "); data.setUint32(16, 16, true); data.setUint16(20, 1, true); data.setUint16(22, 1, true);
  data.setUint32(24, rate, true); data.setUint32(28, rate * 2, true); data.setUint16(32, 2, true); data.setUint16(34, 16, true); text(36, "data"); data.setUint32(40, samples * 2, true);
  for (let i = 0; i < samples; i += 1) data.setInt16(44 + i * 2, Math.sin(i / 4) * 8000, true);
  return URL.createObjectURL(new Blob([data], { type: "audio/wav" }));
}

const vocab = [{ word: "seat", meaning: "A place for one person to sit.", arabic: "مقعد", example: "Hello. Is this seat free?", pronunciation: "/siːt/", stress: "SEAT" },
  { word: "classmate", meaning: "A person in the same class as you.", arabic: "زميل في الصف", example: "This is my new classmate, Omar.", pronunciation: "", stress: "CLASS-mate" }];
const expressions = [{ expression: "Nice to meet you.", meaning: "A polite thing to say when you meet someone.", arabic: "سعيد بلقائك.", example: "Hi, I'm Lina. Nice to meet you." }];
const best = [{ id: "b1", type: "multiple_choice", prompt: "A new classmate asks: \"Is this seat free?\" What is the most natural response?", config: { options: [{ id: "x", label: "Yes, it is. Please sit here." }, { id: "y", label: "I have twenty years." }, { id: "z", label: "Seat is free." }] } }];
const speak = [{ id: "s1", type: "speaking_practice", prompt: "Introduce yourself to a new classmate and ask one question.", config: { max_duration_seconds: 60, max_size_bytes: 1048576 } }];

// Each phase adds { id, title, render } entries here.
export const GALLERY_SECTIONS = [
  { id: "cards", title: "EH / Lesson cards", render: () => <>
    <SituationCard text="You are meeting a new classmate at university." />
    <VocabularyCard items={vocab} />
    <ExpressionCard items={expressions} />
    <SpeakerTip tip="In English, we say our age with 'be', not 'have'." arabic="في الإنجليزية نعبّر عن العمر باستخدام الفعل be وليس have." avoid="I have 20 years." say="I am 20 years old." />
  </> },
  { id: "practice", title: "EH / Choose the Best Response · Speak Now", render: () => <>
    <ChooseBestResponse title="Choose the best response" questions={best} check={async (q, o) => ({ correct: o === "x" })} onFinish={() => {}} />
    <SpeakNow questions={speak} onFinish={() => {}} />
  </> },
  { id: "tracker", title: "EH / Lesson Step Tracker · Topic Lesson", render: () => <>
    <LessonStepTracker steps={LESSON_STEPS.slice(0, 8).map(step => ({ step }))} passedSteps={["situation", "listen"]} />
    <section id={stepAnchor("situation")} data-step="situation"><SituationCard text="You are meeting a new classmate at university." /></section>
  </> },
  { id: "topic-rows", title: "EH / Topic Row statuses", render: () => <TopicRowsSample /> },
];
