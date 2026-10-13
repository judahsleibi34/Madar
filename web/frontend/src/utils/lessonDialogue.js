// "Speaker: line" transcripts render as dialogue bubbles; anything else stays prose.
export function parseDialogue(transcript) {
  const lines = String(transcript || "").split("\n").map(line => line.trim()).filter(Boolean);
  const turns = lines.map(line => line.match(/^([^:]{1,40}):\s+(.+)$/));
  if (!lines.length || turns.some(turn => !turn)) return null;
  const speakers = [...new Set(turns.map(turn => turn[1]))];
  return turns.map(([, speaker, text]) => ({ speaker, text, side: speakers.indexOf(speaker) % 2 ? "end" : "start" }));
}
