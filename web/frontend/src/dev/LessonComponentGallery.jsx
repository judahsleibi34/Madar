// Development-only gallery (localhost:5173/__eh-components): every EduHope
// lesson component in each state, with sample data, for visual checks in
// English and Arabic. Never bundled in production (see appMain.jsx).
import { useState } from "react";
import { useTranslation } from "react-i18next";
import LessonAudioPlayer from "../components/ELearning/content/LessonAudioPlayer";
import ListenMatchActivity, { ListenMatchResults } from "../components/ELearning/content/ListenMatchActivity";
import MediaSlot from "../components/ELearning/content/MediaSlot";
import { LearningExperienceContext } from "../components/ELearning/LearningExperienceContext";
import { GALLERY_SECTIONS, SAMPLE, sampleToneUrl } from "./gallerySections";

// EduHope's published builder theme (seed-data/eduhope/website.json).
const THEME = { "--theme-primary": "#002A60", "--theme-accent": "#088848", "--theme-surface": "#FFFFFF", "--theme-background": "#F6F7F4", "--theme-border": "#D9E3DF", "--theme-text": "#002A60", "--theme-text-soft": "#43576B", "--academy-accent": "#088848" };
const fakeUpload = (file, onProgress) => new Promise(resolve => {
  let value = 0; const timer = setInterval(() => { value += 20; onProgress?.(Math.min(value, 100)); if (value >= 100) { clearInterval(timer); resolve({ asset_id: "sample", asset_url: file.type.startsWith("image/") ? SAMPLE.photo : "" }); } }, 400);
});
const questions = [0, 1].map(n => ({ id: `q${n}`, type: "picture_listen", prompt: "Listen", config: { media: null, options: SAMPLE.pictures.map((url, i) => ({ id: `q${n}o${i}`, alt: `Picture ${i + 1}`, media: { url } })), correct_option_id: `q${n}o${n}` } }));

export default function LessonComponentGallery() {
  const { i18n } = useTranslation("dashboard");
  const [slot, setSlot] = useState({ id: "uploaded", url: SAMPLE.photo, filename: "L01-T01-LM1-photo-1.jpg" });
  const [tone] = useState(sampleToneUrl);
  const dir = i18n.dir();
  return <LearningExperienceContext.Provider value={{ lessonComponents: true }}>
    <main dir={dir} lang={i18n.language} style={{ ...THEME, background: "var(--theme-background)", color: "var(--theme-text)", minHeight: "100vh", padding: "24px 16px", fontFamily: "Inter, system-ui, sans-serif" }}>
      <header style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center", justifyContent: "space-between", maxWidth: 1100, margin: "0 auto 24px" }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>EH component gallery</h1>
        <button type="button" onClick={() => i18n.changeLanguage(i18n.language.startsWith("ar") ? "en" : "ar")} style={{ minHeight: 44, padding: "0 16px" }}>English | العربية</button>
      </header>
      <div style={{ display: "grid", gap: 28, maxWidth: 1100, margin: "0 auto" }}>
        <Section id="audio" title="EH / Audio Player">
          <LessonAudioPlayer src={tone} title="Listen to the conversation" transcript={SAMPLE.dialogue} />
          <LessonAudioPlayer title="Listen to the conversation" />
        </Section>
        <Section id="listen-match" title="EH / Listen & Match">
          <ListenMatchActivity questions={questions} check={async (q, o) => ({ correct: o === `${q}o${q.slice(1)}` })} onFinish={() => {}} />
          <ListenMatchResults correct={7} total={8} onRetry={() => {}} />
        </Section>
        <Section id="media-slot" title="EH / Media Slot">
          <MediaSlot kind="image" label="Photo 1" expectedName="L01-T01-LM1-photo-1.jpg" value={null} upload={fakeUpload} onChange={() => {}} />
          <MediaSlot kind="image" label="Photo 2" expectedName="L01-T01-LM1-photo-2.jpg" value={slot} upload={fakeUpload} onChange={setSlot} />
          <MediaSlot kind="audio" label="Dialogue recording" expectedName="L01-T01-dialogue.wav" value={null} upload={fakeUpload} onChange={() => {}} />
        </Section>
        {GALLERY_SECTIONS.map(({ id, title, render }) => <Section key={id} id={id} title={title}>{render()}</Section>)}
      </div>
    </main>
  </LearningExperienceContext.Provider>;
}

function Section({ id, title, children }) {
  return <section id={id} data-gallery-section style={{ display: "grid", gap: 14 }}><h2 style={{ margin: 0, fontSize: 18 }}>{title}</h2>{children}</section>;
}
