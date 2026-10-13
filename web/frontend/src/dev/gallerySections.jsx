// Sample data and extra sections for the dev-only EH component gallery.
// Existing EduHope (tenant 18) uploads, read through the dev proxy.
export const SAMPLE = {
  photo: "/uploads/tenant_18/builder_assets/6ad27da5369a45a3a4ba55420cf0f0c7.jpg",
  logo: "/uploads/tenant_18/builder_assets/8d0d8c9d7e44460abb21299b4e24e6ff.jpg",
  pictures: ["a2c73f1320d54c2f94c7ebfc81b9f579", "a5d42f39dab64e6198bd6a2d1d5a2b9b", "596e5ef0f480436983eca5726df66995", "b23cefc2c22e4e59a45ed8b5ee1a2939"].map(id => `/uploads/tenant_18/builder_assets/${id}.png`),
  dialogue: "Lina: Hello. Is this seat free?\nOmar: Yes, it is. Please sit here.\nLina: Thank you. My name is Lina. What is your name?\nOmar: I am Omar. I study engineering.",
};

// Each phase adds { id, title, render } entries here.
export const GALLERY_SECTIONS = [];

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
