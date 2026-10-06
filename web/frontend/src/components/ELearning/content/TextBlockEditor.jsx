import { useId, useRef } from "react";
import { useTranslation } from "react-i18next";
import { replaceRichTextRangeStyle } from "../../PageBuilder/core/PageBuilder.text";
import TextBlockRenderer from "./TextBlockRenderer";

export default function TextBlockEditor({ value, onChange }) {
  const { t } = useTranslation("dashboard");
  const input = useRef(null);
  const bodyLabelId = useId();
  function style(property, setting) {
    const { selectionStart: start, selectionEnd: end } = input.current;
    if (end > start) onChange({ ...value, ranges: replaceRichTextRangeStyle(value.ranges, { field: "content", start, end }, property, setting) });
    input.current.focus(); input.current.setSelectionRange(start, end);
  }
  function format(format) {
    const start = input.current.selectionStart;
    const end = input.current.selectionEnd;
    const first = value.body.slice(0, start).split("\n").length - 1;
    const last = value.body.slice(0, end).split("\n").length - 1;
    const formats = value.body.split("\n").map((_, index) => index >= first && index <= last ? format : value.formats?.[index] || "p");
    onChange({ ...value, formats }); input.current.focus(); input.current.setSelectionRange(start, end);
  }
  function changeBody(body) {
    // Shift surviving ranges after an edit and drop spans touched by replacement.
    let start = 0;
    while (start < body.length && start < value.body.length && body[start] === value.body[start]) start += 1;
    let tail = 0;
    while (tail < body.length - start && tail < value.body.length - start && body[body.length - 1 - tail] === value.body[value.body.length - 1 - tail]) tail += 1;
    const oldEnd = value.body.length - tail, delta = body.length - value.body.length;
    const ranges = (value.ranges || []).flatMap((span) => span.end <= start ? [span] : span.start >= oldEnd ? [{ ...span, start: span.start + delta, end: span.end + delta }] : []);
    const oldLines = value.body.split("\n"), newLines = body.split("\n");
    const first = value.body.slice(0, start).split("\n").length - 1;
    const last = value.body.slice(0, oldEnd).split("\n").length - 1;
    const formats = [...(value.formats?.length ? value.formats : oldLines.map(() => "p"))];
    formats.splice(first, last - first + 1, ...Array.from({ length: newLines.length - oldLines.length + last - first + 1 }, () => value.formats?.[first] || "p"));
    onChange({ ...value, body, ranges, formats });
  }
  return <div className="elearning-text-editor">
    <p>{t("elearning.content.formatHelp")}</p>
    <div className="elearning-content-toolbar" role="group" aria-label={t("elearning.content.formatting")}>
      <button type="button" className="ecommerce-secondary-button" onClick={() => style("fontWeight", "700")}>{t("elearning.content.bold")}</button>
      <button type="button" className="ecommerce-secondary-button" onClick={() => style("fontStyle", "italic")}>{t("elearning.content.italic")}</button>
      <button type="button" className="ecommerce-secondary-button" onClick={() => style("textDecoration", "underline")}>{t("elearning.content.underline")}</button>
      <label>{t("elearning.content.lineFormat")}<select defaultValue="p" onChange={(event) => format(event.target.value)}>{["p", "h2", "h3", "bullet", "numbered"].map((name) => <option value={name} key={name}>{t(`elearning.content.formats.${name}`)}</option>)}</select></label>
    </div>
    <label><span id={bodyLabelId}>{t("elearning.content.body")}</span><textarea aria-labelledby={bodyLabelId} ref={input} required maxLength={50000} rows={10} value={value.body} onChange={(event) => changeBody(event.target.value)} /></label>
    <details><summary>{t("elearning.content.preview")}</summary><TextBlockRenderer content={value} /></details>
  </div>;
}
