import { renderRichText } from "../../PageBuilder/core/PageBuilder.text";

export default function TextBlockRenderer({ content }) {
  const lines = String(content?.body ?? "").split("\n");
  let offset = 0;
  const nodes = [];
  for (const [index, line] of lines.entries()) {
    const start = offset; offset += line.length + 1;
    const ranges = (content?.ranges || []).filter((span) => span.end > start && span.start < start + line.length)
      .map((span) => ({ ...span, start: Math.max(0, span.start - start), end: Math.min(line.length, span.end - start) }));
    nodes.push({ format: content?.formats?.[index] || "p", text: renderRichText(line, ranges) });
  }
  const result = [];
  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    if (["bullet", "numbered"].includes(node.format)) {
      const items = [];
      const Tag = node.format === "bullet" ? "ul" : "ol";
      let cursor = index;
      while (cursor < nodes.length && nodes[cursor].format === node.format) {
        items.push(<li key={cursor}>{nodes[cursor].text}</li>); cursor += 1;
      }
      result.push(<Tag key={index}>{items}</Tag>); index = cursor - 1;
    } else {
      const Tag = ["h2", "h3"].includes(node.format) ? node.format : "p";
      result.push(<Tag key={index}>{node.text || <br />}</Tag>);
    }
  }
  return <div className="elearning-text-content">{result}</div>;
}
