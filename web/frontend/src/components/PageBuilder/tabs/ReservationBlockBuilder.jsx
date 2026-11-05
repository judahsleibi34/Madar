import BookingFieldTranslations from "./BookingFieldTranslations";
import { getReservationLayout, getReservationLayoutStyle, getReservationStartColumn, normalizeReservationLayout } from "../blocks/reservationLayout";
import { viewports } from "../core/PageBuilder.constants";
import "../blocks/reservationLayout.css";
import { useReservationEditorI18n } from "../../../utils/reservationEditorI18n";
import { getReservationContent } from "../../../content/pageBuilder/reservationContent";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Baseline,
  Bold,
  CalendarDays,
  Highlighter,
  Move,
  Italic,
  List,
  ListOrdered,
  Plus,
  Redo2,
  Trash2,
  Underline,
  Undo2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  createReservationFormItem,
  getReservationTextStyle,
  localizeReservationFormItem,
  moveBookingComponent,
  normalizeReservationTextStyle,
  reservationFormItemLabels,
} from "../blocks/reservationForm";
import { pageBuilderFontFamilyOptions } from "../core/PageBuilder.theme";
import { normalizeTimeSlotsByDate } from "../blocks/reservationAvailability";

const BOOKING_COMPONENT_MIME = "application/x-madar-booking-component";
const toolboxTypes = ["heading", "paragraph", "divider", "availability", "text", "email", "phone", "checkbox", "radio", "button"];
const textComponentTypes = new Set(["heading", "paragraph"]);

const writeDragPayload = (event, payload) => {
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData(BOOKING_COMPONENT_MIME, JSON.stringify(payload));
};

const readDragPayload = (event) => {
  try {
    return JSON.parse(event.dataTransfer.getData(BOOKING_COMPONENT_MIME));
  } catch {
    return null;
  }
};

const getCanvasMovePreview = gesture => {
  const scrollDelta = gesture.scroller.scrollTop - gesture.scrollTop;
  const dx = gesture.clientX - gesture.x;
  const dy = gesture.clientY - gesture.y + scrollDelta;
  const centerY = gesture.clientY;
  const centerX = gesture.rect.left + gesture.rect.width / 2 + dx;
  const slots = [...gesture.page.querySelectorAll(":scope > .booking-canvas-component-slot")];
  let targetIndex = slots.length;
  for (let index = 0; index < slots.length; index++) {
    if (slots[index].dataset.componentId === gesture.id) continue;
    const rect = slots[index].querySelector("article").getBoundingClientRect();
    const middle = rect.top + rect.height / 2;
    const beforeInRow = gesture.direction === "rtl" ? centerX > rect.left + rect.width / 2 : centerX < rect.left + rect.width / 2;
    if (centerY < middle - 2 || (Math.abs(centerY - middle) <= 2 && beforeInRow)) { targetIndex = index; break; }
  }
  const sourceIndex = slots.findIndex(slot => slot.dataset.componentId === gesture.id);
  if (Math.abs(dy) < 6 || targetIndex === sourceIndex || targetIndex === sourceIndex + 1) targetIndex = null;
  return { id: gesture.id, dx, dy, targetIndex };
};

const getResizeGeometry = (node, columns) => {
  const page = node.closest(".booking-form-page");
  const article = node.closest("article");
  const style = getComputedStyle(page);
  const pageDirection = style.direction || page.dir || "ltr";
  const controlDirection = article.dir || pageDirection;
  const width = page.clientWidth - (parseFloat(style.paddingLeft) || 0) - (parseFloat(style.paddingRight) || 0);
  const step = Math.max(1, (width + 16) / 12);
  const frame = article.getBoundingClientRect();
  const bounds = page.getBoundingClientRect();
  const offset = pageDirection === "rtl" ? bounds.right - (parseFloat(style.paddingRight) || 0) - frame.right
    : frame.left - bounds.left - (parseFloat(style.paddingLeft) || 0);
  const start = Math.max(1, Math.min(13 - columns, Math.round(offset / step) + 1));
  const reverse = controlDirection !== pageDirection;
  return { step, start, reverse, direction: controlDirection, maxColumns: reverse ? start + columns - 1 : 13 - start, end: start + columns - 1 };
};

const renderPreviewText = (item, onTextChange) => {
  const textStyle = normalizeReservationTextStyle(item.textStyle);
  const style = getReservationTextStyle(item);
  const lines = String(item.text || "").split("\n").filter((line) => line.trim());
  const editing = {
    contentEditable: "plaintext-only",
    suppressContentEditableWarning: true,
    onBlur: event => {
      const value = event.currentTarget.innerText ?? event.currentTarget.textContent;
      if (value !== item.text) onTextChange(value);
    },
    onKeyDown: event => {
      if (!event.altKey) event.stopPropagation();
    },
  };
  if (textStyle.format === "bullets" || textStyle.format === "numbers") {
    const Tag = textStyle.format === "numbers" ? "ol" : "ul";
    return <Tag style={style} {...editing}>{lines.map((line, index) => <li key={`${item.id}_${index}`}>{line}</li>)}</Tag>;
  }
  const Tag = ["h1", "h2", "h3"].includes(textStyle.format)
    ? textStyle.format
    : item.type === "heading" ? "h3" : "p";
  return <Tag style={style} {...editing}>{item.text}</Tag>;
};

function BookingComponentPreview({ item, onTextChange, availableDates, timeSlots, timeSlotsByDate, lang }) {
  const content = getReservationContent(lang);
  if (item.type === "divider") return <div className="reservation-component-divider" role="separator" aria-orientation="horizontal" />;
  if (textComponentTypes.has(item.type)) return renderPreviewText(item, onTextChange);
  if (item.type === "availability") {
    const dates = Array.isArray(availableDates) ? availableDates : [];
    const times = normalizeTimeSlotsByDate(dates, timeSlots, timeSlotsByDate)[dates[0]] || [];
    return (
      <div className="booking-availability-preview">
        <strong>{item.label}</strong>
        {dates.length > 0 && times.length > 0 ? (
          <>
            <span><CalendarDays size={15} aria-hidden="true" /> {dates[0]}</span>
            <div>{times.slice(0, 4).map((time) => <button type="button" tabIndex={-1} key={time}>{time}</button>)}</div>
          </>
        ) : <small>{content.noSlots}</small>}
      </div>
    );
  }
  if (["text", "email", "phone"].includes(item.type)) {
    return <label>{item.label}{item.required ? " *" : ""}<input type={item.type === "text" ? "text" : item.type} disabled placeholder={item.placeholder || ""} />{item.type === "phone" && <small>{content.phoneHelper}</small>}</label>;
  }
  if (item.type === "checkbox" || item.type === "radio") {
    return (
      <fieldset>
        <legend>{item.label}{item.required ? " *" : ""}</legend>
        {(item.options || []).map((option, index) => (
          <label key={`${item.id}_${index}`}><input type={item.type} disabled /> <span>{item.optionLabels?.[option] || option}</span></label>
        ))}
      </fieldset>
    );
  }
  if (item.type === "button") return <button type="button" tabIndex={-1}>{item.label}</button>;
  return null;
}

const toolbarButtons = [
  { id: "bold", label: "Bold", icon: Bold },
  { id: "italic", label: "Italic", icon: Italic },
  { id: "underline", label: "Underline", icon: Underline },
  { id: "bullets", label: "Bullets", icon: List },
  { id: "numbers", label: "Numbers", icon: ListOrdered },
  { id: "left", label: "Align left", icon: AlignLeft },
  { id: "center", label: "Align center", icon: AlignCenter },
  { id: "right", label: "Align right", icon: AlignRight },
  { id: "justify", label: "Justify", icon: AlignJustify },
];

function BookingTextToolbar({ item, onUpdate, onUndo, onRedo, canUndo, canRedo }) {
  const { t } = useReservationEditorI18n();
  const style = normalizeReservationTextStyle(item.textStyle);
  const updateStyle = (updates) => onUpdate({ textStyle: { ...style, ...updates } });
  const applyAction = (action) => {
    if (action === "bold") updateStyle({ fontWeight: style.fontWeight === "700" ? "400" : "700" });
    else if (action === "italic") updateStyle({ fontStyle: style.fontStyle === "italic" ? "normal" : "italic" });
    else if (action === "underline") updateStyle({ textDecoration: style.textDecoration === "underline" ? "none" : "underline" });
    else if (action === "bullets" || action === "numbers") updateStyle({ format: style.format === action ? "text" : action });
    else updateStyle({ textAlign: action });
  };

  return (
    <div className="booking-text-toolbar" role="toolbar" aria-label={t("bookingEditor.bookingTextFormatting", { defaultValue: "Booking text formatting" })}>
      <select aria-label={t("bookingEditor.textStyle", { defaultValue: "Text style" })} value={style.format} onChange={(event) => updateStyle({ format: event.target.value })}>
        <option value="text">{t("bookingEditor.text", { defaultValue: "Text" })}</option>
        <option value="h1">H1</option>
        <option value="h2">H2</option>
        <option value="h3">H3</option>
        <option value="bullets">{t("bookingEditor.bullets", { defaultValue: "Bullets" })}</option>
        <option value="numbers">{t("bookingEditor.numbers", { defaultValue: "Numbers" })}</option>
      </select>
      <select aria-label={t("bookingEditor.fontFamily", { defaultValue: "Font family" })} value={style.fontFamily} onChange={(event) => updateStyle({ fontFamily: event.target.value })}>
        {pageBuilderFontFamilyOptions.map((font) => <option value={font} key={font}>{font}</option>)}
      </select>
      <label title={t("bookingEditor.textSize", { defaultValue: "Text size" })}><span>{t("bookingEditor.size", { defaultValue: "Size" })}</span><input aria-label={t("bookingEditor.textSize", { defaultValue: "Text size" })} type="number" min="8" max="256" value={style.fontSize} onChange={(event) => updateStyle({ fontSize: event.target.value })} /></label>
      <label title={t("bookingEditor.textOpacity", { defaultValue: "Text opacity" })}><span>{t("bookingEditor.opacity", { defaultValue: "Opacity" })}</span><input aria-label={t("bookingEditor.textOpacity", { defaultValue: "Text opacity" })} type="number" min="0" max="100" value={Math.round(style.opacity * 100)} onChange={(event) => updateStyle({ opacity: Number(event.target.value) / 100 })} /><span>%</span></label>
      <button type="button" aria-label={t("bookingEditor.undoFormatting", { defaultValue: "Undo formatting" })} title={t("bookingEditor.undo", { defaultValue: "Undo" })} disabled={!canUndo} onClick={onUndo}><Undo2 size={15} /></button>
      <button type="button" aria-label={t("bookingEditor.redoFormatting", { defaultValue: "Redo formatting" })} title={t("bookingEditor.redo", { defaultValue: "Redo" })} disabled={!canRedo} onClick={onRedo}><Redo2 size={15} /></button>
      {toolbarButtons.map(({ id, label, icon: Icon }) => {
        const active =
          (id === "bold" && style.fontWeight === "700") ||
          (id === "italic" && style.fontStyle === "italic") ||
          (id === "underline" && style.textDecoration === "underline") ||
          (["bullets", "numbers"].includes(id) && style.format === id) ||
          (["left", "center", "right", "justify"].includes(id) && style.textAlign === id);
        return <button type="button" className={active ? "is-active" : ""} aria-label={t(`bookingEditor.${id}`, { defaultValue: label })} title={t(`bookingEditor.${id}`, { defaultValue: label })} key={id} onClick={() => applyAction(id)}><Icon size={15} /></button>;
      })}
      <label className="booking-toolbar-color" title={t("bookingEditor.textColor", { defaultValue: "Text color" })}><Baseline size={15} /><input aria-label={t("bookingEditor.textColor", { defaultValue: "Text color" })} type="color" value={style.color || "#111827"} onChange={(event) => updateStyle({ color: event.target.value })} /></label>
      <label className="booking-toolbar-color" title={t("bookingEditor.backgroundColor", { defaultValue: "Background color" })}><Highlighter size={15} /><input aria-label={t("bookingEditor.textBackgroundColor", { defaultValue: "Text background color" })} type="color" value={style.backgroundColor || "#ffffff"} onChange={(event) => updateStyle({ backgroundColor: event.target.value })} /></label>
    </div>
  );
}

function BookingComponentInspector({ item, onUpdate, onDelete, onUndo, onRedo, canUndo, canRedo, contentLanguage, onContentLanguageChange }) {
  const { t, fieldLabel } = useReservationEditorI18n();
  const effectiveDirection = localizeReservationFormItem(item, contentLanguage).direction || "ltr";
  const updateOption = (index, value) => {
    onUpdate({ options: item.options.map((option, optionIndex) => optionIndex === index ? value : option) });
  };
  const updateDirection = (direction) => {
    if (contentLanguage === "ar") {
      onUpdate({ translations: { ...item.translations, ar: { ...item.translations?.ar, direction } } });
      return;
    }
    onUpdate({
      direction,
      translations: { ...item.translations, en: { ...item.translations?.en, direction } },
      ...(textComponentTypes.has(item.type)
        ? { textStyle: { ...normalizeReservationTextStyle(item.textStyle), textAlign: direction === "rtl" ? "right" : "left" } }
        : {}),
    });
  };

  return (
    <aside className="booking-component-inspector" aria-label={t("bookingEditor.selectedBookingComponentSettings", { defaultValue: "Selected booking component settings" })}>
      <div className="booking-component-inspector-heading">
        <div>
          <span>{t("bookingEditor.fieldSettings", { defaultValue: "Field settings" })}</span>
          <h4>{fieldLabel(item.type)}</h4>
        </div>
      </div>

      {textComponentTypes.has(item.type) && (
        <BookingTextToolbar item={item} onUpdate={onUpdate} onUndo={onUndo} onRedo={onRedo} canUndo={canUndo} canRedo={canRedo} />
      )}

      {textComponentTypes.has(item.type) ? (
        <label>
          {item.type === "heading" ? t("bookingEditor.headingText", { defaultValue: "Heading text" }) : t("bookingEditor.paragraphText", { defaultValue: "Paragraph text" })}
          {item.type === "paragraph" ? (
            <textarea value={item.text} onChange={(event) => onUpdate({ text: event.target.value })} />
          ) : (
            <input value={item.text} onChange={(event) => onUpdate({ text: event.target.value })} />
          )}
        </label>
      ) : item.type === "divider" ? null : (
        <label>
          {item.type === "button" ? t("bookingEditor.buttonLabel", { defaultValue: "Button label" }) : item.type === "availability" ? t("bookingEditor.sectionLabel", { defaultValue: "Section label" }) : t("bookingEditor.questionLabel", { defaultValue: "Question label" })}
          <input value={item.label} onChange={(event) => onUpdate({ label: event.target.value })} />
        </label>
      )}

      {textComponentTypes.has(item.type) && (
        <BookingFieldTranslations inline item={item} language={contentLanguage} onLanguageChange={onContentLanguageChange} onUpdate={onUpdate} />
      )}

      {["text", "email", "phone"].includes(item.type) && (
        <label>{t("bookingEditor.placeholder", { defaultValue: "Placeholder" })}<input value={item.placeholder || ""} onChange={(event) => onUpdate({ placeholder: event.target.value })} /></label>
      )}

      {(item.type === "checkbox" || item.type === "radio") && (
        <div className="booking-component-options">
          <span>{t("bookingEditor.choices", { defaultValue: "Choices" })}</span>
          {item.options.map((option, index) => (
            <div key={`${item.id}_option_${index}`}>
              <input value={option} onChange={(event) => updateOption(index, event.target.value)} />
              <button type="button" aria-label={t("bookingEditor.removeOption", { number: index + 1 })} disabled={item.options.length <= 1} onClick={() => onUpdate({ options: item.options.filter((_, optionIndex) => optionIndex !== index) })}><Trash2 size={13} /></button>
            </div>
          ))}
          <button type="button" onClick={() => onUpdate({ options: [...item.options, t("bookingEditor.option", { number: item.options.length + 1 })] })}><Plus size={13} />{t("bookingEditor.addChoice", { defaultValue: "Add choice" })}</button>
        </div>
      )}

      {["text", "email", "phone", "checkbox", "radio"].includes(item.type) && (
        <label className="booking-component-required"><input type="checkbox" checked={Boolean(item.required)} onChange={(event) => onUpdate({ required: event.target.checked })} />{t("bookingEditor.requiredAnswer", { defaultValue: "Required answer" })}</label>
      )}

      {item.type !== "divider" && <div className="booking-component-direction">
        <span>{t("bookingEditor.contentDirection", { defaultValue: "Content direction" })}</span>
        <div role="group" aria-label={t("bookingEditor.componentContentDirection", { defaultValue: "Component content direction" })}>
          <button type="button" className={effectiveDirection !== "rtl" ? "is-active" : ""} aria-pressed={effectiveDirection !== "rtl"} onClick={() => updateDirection("ltr")}>{t("bookingEditor.lTR", { defaultValue: "LTR" })}</button>
          <button type="button" className={effectiveDirection === "rtl" ? "is-active" : ""} aria-pressed={effectiveDirection === "rtl"} onClick={() => updateDirection("rtl")}>{t("bookingEditor.rTL", { defaultValue: "RTL" })}</button>
        </div>
      </div>}

      {!textComponentTypes.has(item.type) && item.type !== "divider" && <BookingFieldTranslations item={item} language={contentLanguage} onLanguageChange={onContentLanguageChange} onUpdate={onUpdate} />}
      <button type="button" className="booking-component-delete danger-button" onClick={onDelete}><Trash2 size={15} />{t("bookingEditor.removeField", { defaultValue: "Remove field" })}</button>
    </aside>
  );
}

export default function ReservationBlockBuilder({ items, onChange, availableDates = [], timeSlots = [], timeSlotsByDate, allowAvailability = false }) {
  const { t, direction, locale, fieldLabel } = useReservationEditorI18n();
  const [contentLanguage, setContentLanguage] = useState(locale);
  const [viewport, setViewport] = useState("desktop");
  const resizeGesture = useRef(null);
  const moveGesture = useRef(null);
  const [movePreview, setMovePreview] = useState(null);
  useEffect(() => () => {
    if (moveGesture.current) cancelAnimationFrame(moveGesture.current.frame);
    moveGesture.current = null;
  }, []);
  const visibleToolboxTypes = allowAvailability ? toolboxTypes : toolboxTypes.filter((type) => type !== "availability");
  const components = useMemo(() => (Array.isArray(items) ? items : []).filter((item) => item && reservationFormItemLabels[item.type]), [items]);
  const [selectedId, setSelectedId] = useState(components[0]?.id || "");
  const [activeDropIndex, setActiveDropIndex] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [historyById, setHistoryById] = useState(() => new Map());
  const [futureById, setFutureById] = useState(() => new Map());
  const effectiveSelectedId = components.some((item) => item.id === selectedId)
    ? selectedId
    : components[0]?.id || "";
  const selected = components.find((item) => item.id === effectiveSelectedId) || null;
  const hasButton = components.some((item) => item.type === "button");
  const hasAvailability = components.some((item) => item.type === "availability");

  const addComponent = (type, targetIndex = components.length) => {
    if ((type === "button" && hasButton) || (type === "availability" && hasAvailability)) return;
    const nextItem = createReservationFormItem(type);
    const defaults = { heading: "defaultHeading", paragraph: "defaultParagraph", availability: "defaultAvailability", text: "defaultQuestion", email: "defaultEmail", phone: "defaultPhone", checkbox: "defaultCheckbox", radio: "defaultRadio", button: "defaultSubmit" };
    nextItem.direction = direction;
    if (textComponentTypes.has(type)) {
      nextItem.text = t(`bookingEditor.${defaults[type]}`);
      nextItem.textStyle = { ...nextItem.textStyle, ...(direction === "rtl" ? { fontFamily: "IBM Plex Sans Arabic" } : {}), textAlign: direction === "rtl" ? "right" : "left" };
    } else if (type !== "divider") nextItem.label = t(`bookingEditor.${defaults[type]}`);
    if (type === "text") nextItem.placeholder = t("bookingEditor.defaultPlaceholder");
    if (nextItem.options) nextItem.options = nextItem.options.map((_, index) => t("bookingEditor.option", { number: index + 1 }));
    const next = [...components];
    next.splice(Math.max(0, Math.min(targetIndex, next.length)), 0, nextItem);
    onChange(next);
    setSelectedId(nextItem.id);
  };

  const dropAt = (event, targetIndex) => {
    event.preventDefault();
    event.stopPropagation();
    const payload = readDragPayload(event);
    setActiveDropIndex(null);
    setIsDragging(false);
    if (!payload) return;
    if (payload.kind === "toolbox") addComponent(payload.type, targetIndex);
    if (payload.kind === "component") {
      onChange(moveBookingComponent(components, payload.id, targetIndex));
      setSelectedId(payload.id);
    }
  };

  const moveOne = (id, direction) => {
    const index = components.findIndex(item => item.id === id);
    if (index < 0 || index + direction < 0 || index + direction >= components.length) return;
    onChange(moveBookingComponent(components, id, direction < 0 ? index - 1 : index + 2));
    setSelectedId(id);
  };

  const updateSelected = (updates, recordHistory = true, targetId = effectiveSelectedId) => {
    const current = components.find((item) => item.id === targetId);
    if (!current) return;
    if (current.type === "heading" && Object.hasOwn(updates, "text")) {
      updates = { ...updates, translations: { ...current.translations, ...updates.translations,
        en: { ...current.translations?.en, ...updates.translations?.en, text: updates.text } } };
    }
    if (recordHistory) {
      const history = historyById.get(targetId) || [];
      setHistoryById(new Map(historyById).set(targetId, [...history.slice(-49), current]));
      setFutureById(new Map(futureById).set(targetId, []));
    }
    onChange(components.map((item) => item.id === targetId ? { ...item, ...updates } : item));
  };

  const restoreSelected = (sourceMap, setSourceMap, targetMap, setTargetMap) => {
    const source = sourceMap.get(effectiveSelectedId) || [];
    const current = components.find((item) => item.id === effectiveSelectedId);
    if (!current || source.length === 0) return;
    const previous = source[source.length - 1];
    setSourceMap(new Map(sourceMap).set(effectiveSelectedId, source.slice(0, -1)));
    setTargetMap(new Map(targetMap).set(
      effectiveSelectedId,
      [...(targetMap.get(effectiveSelectedId) || []), current]
    ));
    onChange(components.map((item) => item.id === effectiveSelectedId ? previous : item));
  };

  const deleteSelected = () => {
    const index = components.findIndex((item) => item.id === effectiveSelectedId);
    const next = components.filter((item) => item.id !== effectiveSelectedId);
    onChange(next);
    setSelectedId(next[Math.min(index, next.length - 1)]?.id || "");
  };

  return (
    <div className="booking-element-builder" dir={direction}>
      <aside className="booking-component-toolbox" aria-label={t("bookingEditor.bookingComponentToolbox", { defaultValue: "Booking component toolbox" })}>
        <div className="booking-component-toolbox-heading"><h4>{t("bookingEditor.addFields", { defaultValue: "Add fields" })}</h4><p>{t("bookingEditor.clickAFieldToAddItOrDragItOntoYourForm", { defaultValue: "Click a field to add it, or drag it onto your form." })}</p></div>
        <div className="booking-component-toolbox-list section-component-palette">
          {visibleToolboxTypes.map((type) => (
            <button type="button" draggable={!((type === "button" && hasButton) || (type === "availability" && hasAvailability))} disabled={(type === "button" && hasButton) || (type === "availability" && hasAvailability)} key={type}
              onDragStart={(event) => { writeDragPayload(event, { kind: "toolbox", type }); setIsDragging(true); }}
              onDragEnd={() => { setIsDragging(false); setActiveDropIndex(null); }} onClick={() => addComponent(type)}>
              <strong>{fieldLabel(type)}</strong><small>{(type === "button" && hasButton) || (type === "availability" && hasAvailability) ? t("bookingEditor.alreadyAdded", { defaultValue: "Already added" }) : t("bookingEditor.clickOrDragToAdd", { defaultValue: "Click or drag to add" })}</small>
            </button>
          ))}
        </div>
      </aside>

      <section className="booking-element-stage" aria-label={t("bookingEditor.bookingElementCanvas", { defaultValue: "Booking element canvas" })}>
        <div className="booking-element-stage-heading"><div><strong>{t("bookingEditor.bookingForm", { defaultValue: "Booking form" })}</strong></div>
          <div className="booking-device-tabs" role="group" aria-label={t("bookingEditor.layoutDevice")}>
            {Object.keys(viewports).map(device => <button type="button" key={device} aria-pressed={viewport === device} onClick={() => setViewport(device)}>{t(`bookingEditor.devices.${device}`)}</button>)}
          </div>
          <label className="booking-preview-language">{t("bookingEditor.previewLanguage")}
          <select aria-label={t("bookingEditor.previewLanguage")} value={contentLanguage} onChange={event => setContentLanguage(event.target.value)}>
            <option value="en">English</option><option value="ar">العربية</option>
          </select>
        </label></div>
        <div className={`booking-element-canvas ${isDragging ? "is-dragging" : ""}`}>
          <div className="booking-form-page reservation-layout-grid" dir={contentLanguage === "ar" ? "rtl" : "ltr"} data-layout-viewport={viewport} style={viewport === "desktop" ? undefined : { maxWidth: viewports[viewport], marginInline: "auto" }}>
          {components.map((item, index) => (
            <div className={`booking-canvas-component-slot reservation-layout-item${movePreview?.targetIndex === index ? " is-pointer-drop-before" : ""}${movePreview?.targetIndex === components.length && index === components.length - 1 ? " is-pointer-drop-after" : ""}`} key={item.id} data-component-id={item.id} style={getReservationLayoutStyle(item)}>
              <div className={`booking-component-dropzone ${isDragging ? "is-visible" : ""} ${activeDropIndex === index ? "is-active" : ""}`} onDragEnter={(event) => { event.preventDefault(); setActiveDropIndex(index); }} onDragOver={(event) => event.preventDefault()} onDrop={(event) => dropAt(event, index)} />
              <article className={`booking-canvas-component is-${item.type} ${effectiveSelectedId === item.id ? "is-selected" : ""}${movePreview?.id === item.id ? " is-pointer-moving" : ""}`} tabIndex={0} aria-label={`${fieldLabel(item.type)} component`}
                dir={localizeReservationFormItem(item, contentLanguage).direction === "rtl" ? "rtl" : "ltr"}
                style={movePreview?.id === item.id ? { transform: `translate(${movePreview.dx}px, ${movePreview.dy}px)` } : undefined}
                onKeyDown={event => {
                  if (event.altKey && ["ArrowUp", "ArrowDown"].includes(event.key)) {
                    event.preventDefault(); event.stopPropagation(); moveOne(item.id, event.key === "ArrowUp" ? -1 : 1);
                  }
                }} onClick={() => setSelectedId(item.id)} onFocus={() => setSelectedId(item.id)}>
                <button type="button" className="booking-component-move-x direct-move-handle" aria-label={t("bookingEditor.moveHorizontally")} title={t("bookingEditor.moveHorizontally")}
                  onClick={event => event.stopPropagation()}
                  onPointerDown={event => {
                    event.preventDefault(); event.stopPropagation();
                    const page = event.currentTarget.closest(".booking-form-page");
                    const slot = event.currentTarget.closest(".booking-canvas-component-slot").getBoundingClientRect();
                    const rect = page.getBoundingClientRect();
                    const style = getComputedStyle(page);
                    const layoutDirection = style.direction;
                    const width = page.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
                    const step = (width + 16) / 12;
                    const offset = layoutDirection === "rtl" ? rect.right - parseFloat(style.paddingRight) - slot.right : slot.left - rect.left - parseFloat(style.paddingLeft);
                    const scroller = page.closest(".booking-element-canvas");
                    const gesture = { id: item.id, pointerId: event.pointerId, x: event.clientX, y: event.clientY, clientX: event.clientX, clientY: event.clientY,
                      page, scroller, scrollTop: scroller.scrollTop, rect: event.currentTarget.closest("article").getBoundingClientRect(), direction: layoutDirection,
                      start: Math.round(offset / step) + 1, step };
                    moveGesture.current = gesture;
                    event.currentTarget.setPointerCapture(event.pointerId); setSelectedId(item.id);
                    const animate = () => {
                      if (moveGesture.current !== gesture) return;
                      const bounds = scroller.getBoundingClientRect();
                      if (Math.hypot(gesture.clientX - gesture.x, gesture.clientY - gesture.y) > 4) {
                        if (gesture.clientY < bounds.top + 32) scroller.scrollTop -= 12;
                        else if (gesture.clientY > bounds.bottom - 32) scroller.scrollTop += 12;
                      }
                      const next = getCanvasMovePreview(gesture);
                      setMovePreview(previous => previous?.dx === next.dx && previous?.dy === next.dy && previous?.targetIndex === next.targetIndex ? previous : next);
                      gesture.frame = requestAnimationFrame(animate);
                    };
                    gesture.frame = requestAnimationFrame(animate);
                  }}
                  onPointerMove={event => {
                    const gesture = moveGesture.current;
                    if (!gesture || !event.currentTarget.hasPointerCapture(event.pointerId) || !event.buttons) return;
                    gesture.clientX = event.clientX; gesture.clientY = event.clientY;
                    setMovePreview(getCanvasMovePreview(gesture));
                  }}
                  onPointerUp={event => {
                    const gesture = moveGesture.current;
                    if (!gesture) return;
                    gesture.clientX = event.clientX; gesture.clientY = event.clientY;
                    const preview = getCanvasMovePreview(gesture);
                    cancelAnimationFrame(gesture.frame); moveGesture.current = null; setMovePreview(null);
                    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
                    const delta = (event.clientX - gesture.x) * (gesture.direction === "rtl" ? -1 : 1);
                    const layout = getReservationLayout(item, viewport);
                    const startColumn = Math.max(1, Math.min(13 - layout.columns, gesture.start + Math.round(delta / gesture.step)));
                    const horizontal = layout.columns < 12 && Math.round(delta / gesture.step) !== 0;
                    let next = preview.targetIndex === null ? components : moveBookingComponent(components, item.id, preview.targetIndex);
                    if (horizontal) next = next.map(component => component.id === item.id ? { ...component,
                      layout: normalizeReservationLayout({ ...component.layout, [viewport]: { ...layout, position: "custom", startColumn } }) } : component);
                    if (next !== components) onChange(next);
                  }}
                  onPointerCancel={() => { if (moveGesture.current) cancelAnimationFrame(moveGesture.current.frame); moveGesture.current = null; setMovePreview(null); }}
                  onKeyDown={event => {
                    if (event.key === "Escape" && moveGesture.current) {
                      event.preventDefault(); event.stopPropagation();
                      const gesture = moveGesture.current;
                      cancelAnimationFrame(gesture.frame); moveGesture.current = null; setMovePreview(null);
                      if (event.currentTarget.hasPointerCapture(gesture.pointerId)) event.currentTarget.releasePointerCapture(gesture.pointerId);
                      return;
                    }
                    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key) || event.altKey) return;
                    event.preventDefault(); event.stopPropagation();
                    const layout = getReservationLayout(item, viewport);
                    if (["ArrowUp", "ArrowDown"].includes(event.key)) {
                      moveOne(item.id, event.key === "ArrowUp" ? -1 : 1);
                      return;
                    }
                    if (layout.columns === 12) return;
                    const page = event.currentTarget.closest(".booking-form-page");
                    const layoutDirection = getComputedStyle(page).direction || page.dir || "ltr";
                    const delta = (event.key === "ArrowRight" ? 1 : -1) * (layoutDirection === "rtl" ? -1 : 1);
                    const startColumn = Math.max(1, Math.min(13 - layout.columns, (Number(getReservationStartColumn(layout)) || 1) + delta));
                    updateSelected({ layout: normalizeReservationLayout({ ...item.layout, [viewport]: { ...layout, position: "custom", startColumn } }) }, true, item.id);
                  }}><Move size={13} aria-hidden="true" /></button>
                <div className="booking-canvas-component-preview" dir={localizeReservationFormItem(item, contentLanguage).direction === "rtl" ? "rtl" : "ltr"}><BookingComponentPreview key={`${item.id}-${contentLanguage}`} item={localizeReservationFormItem(item, contentLanguage)} lang={contentLanguage}
                  onTextChange={text => updateSelected(contentLanguage === "ar" || (item.type !== "heading" && item.translations?.[contentLanguage]?.text)
                    ? { translations: { ...item.translations, [contentLanguage]: { ...item.translations?.[contentLanguage], text } } }
                    : { text }, true, item.id)}
                  availableDates={availableDates} timeSlots={timeSlots} timeSlotsByDate={timeSlotsByDate} /></div>
                <button type="button" className="booking-component-resize direct-resize-handle" aria-label={t("bookingEditor.resizeComponent")} title={t("bookingEditor.resizeComponent")}
                  onClick={event => event.stopPropagation()}
                  onPointerDown={event => {
                    event.preventDefault(); event.stopPropagation();
                    const article = event.currentTarget.closest("article");
                    const control = article.querySelector('.booking-canvas-component-preview > button, .booking-canvas-component-preview > label > input');
                    const columns = getReservationLayout(item, viewport).columns;
                    resizeGesture.current = { x: event.clientX, y: event.clientY, height: (control || article).getBoundingClientRect().height,
                      columns, ...getResizeGeometry(event.currentTarget, columns), changed: false };
                    event.currentTarget.setPointerCapture(event.pointerId); setSelectedId(item.id);
                  }}
                  onPointerMove={event => {
                    if (!event.currentTarget.hasPointerCapture(event.pointerId) || !event.buttons) return;
                    const gesture = resizeGesture.current;
                    if (!gesture) return;
                    const delta = (event.clientX - gesture.x) * (gesture.direction === "rtl" ? -1 : 1);
                    const columns = Math.max(1, Math.min(gesture.maxColumns, gesture.columns + Math.round(delta / gesture.step)));
                    const layout = getReservationLayout(item, viewport);
                    if (Math.abs(event.clientY - gesture.y) >= 2) gesture.movedY = true;
                    const contentHeight = gesture.movedY ? Math.max(32, Math.min(2000, Math.round(gesture.height + event.clientY - gesture.y))) : layout.contentHeight;
                    if (columns !== layout.columns || contentHeight !== layout.contentHeight) {
                      updateSelected({ layout: normalizeReservationLayout({ ...item.layout, [viewport]: { ...layout, columns,
                        ...(gesture.reverse ? { position: "custom", startColumn: gesture.end - columns + 1 } : {}),
                        ...(contentHeight ? { contentHeight } : {}) } }) }, !gesture.changed, item.id);
                      gesture.changed = true;
                    }
                  }}
                  onPointerUp={event => { resizeGesture.current = null; if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }}
                  onPointerCancel={() => { resizeGesture.current = null; }}
                  onKeyDown={event => {
                    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key) || event.altKey) return;
                    event.preventDefault(); event.stopPropagation();
                    const layout = getReservationLayout(item, viewport);
                    if (["ArrowUp", "ArrowDown"].includes(event.key)) {
                      const article = event.currentTarget.closest("article");
                      const control = article.querySelector('.booking-canvas-component-preview > button, .booking-canvas-component-preview > label > input');
                      const height = layout.contentHeight || (control || article).getBoundingClientRect().height || 40;
                      updateSelected({ layout: normalizeReservationLayout({ ...item.layout, [viewport]: { ...layout,
                        contentHeight: height + (event.key === "ArrowDown" ? 4 : -4) } }) }, true, item.id);
                      return;
                    }
                    const geometry = getResizeGeometry(event.currentTarget, layout.columns);
                    const delta = (event.key === "ArrowRight" ? 1 : -1) * (geometry.direction === "rtl" ? -1 : 1);
                    const columns = Math.max(1, Math.min(geometry.maxColumns, layout.columns + delta));
                    updateSelected({ layout: normalizeReservationLayout({ ...item.layout, [viewport]: { ...layout, columns,
                      ...(geometry.reverse ? { position: "custom", startColumn: geometry.end - columns + 1 } : {}) } }) }, true, item.id);
                  }} />
              </article>
            </div>
          ))}
          <div style={{ gridColumn: "1 / -1" }} className={`booking-component-dropzone is-last ${isDragging ? "is-visible" : ""} ${activeDropIndex === components.length ? "is-active" : ""}`} onDragEnter={(event) => { event.preventDefault(); setActiveDropIndex(components.length); }} onDragOver={(event) => event.preventDefault()} onDrop={(event) => dropAt(event, components.length)} />
          {components.length === 0 && !isDragging ? <div className="booking-element-empty-state"><strong>{t("bookingEditor.addYourFirstComponent", { defaultValue: "Add your first component" })}</strong><span>{t("bookingEditor.chooseAComponentAboveOrDragItHere", { defaultValue: "Choose a component above or drag it here." })}</span></div> : null}
          </div>
        </div>
      </section>

      {selected ? (
        <BookingComponentInspector item={selected} contentLanguage={contentLanguage} onContentLanguageChange={setContentLanguage} onUpdate={updateSelected} onDelete={deleteSelected}
          onUndo={() => restoreSelected(historyById, setHistoryById, futureById, setFutureById)}
          onRedo={() => restoreSelected(futureById, setFutureById, historyById, setHistoryById)}
          canUndo={(historyById.get(effectiveSelectedId) || []).length > 0}
          canRedo={(futureById.get(effectiveSelectedId) || []).length > 0} />
      ) : <aside className="booking-component-inspector is-empty"><strong>{t("bookingEditor.noComponentSelected", { defaultValue: "No component selected" })}</strong><p>{t("bookingEditor.dragAComponentOntoTheCanvasThenSelectItToEditItsContent", { defaultValue: "Drag a component onto the canvas, then select it to edit its content." })}</p></aside>}
    </div>
  );
}
