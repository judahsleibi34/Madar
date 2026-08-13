import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Baseline,
  Bold,
  CalendarDays,
  Highlighter,
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
  normalizeReservationTextStyle,
  reservationFormItemLabels,
} from "../blocks/reservationForm";
import { pageBuilderFontFamilyOptions } from "../core/PageBuilder.theme";
import { normalizeTimeSlotsByDate } from "../blocks/reservationAvailability";

const BOOKING_COMPONENT_MIME = "application/x-madar-booking-component";
const toolboxTypes = ["heading", "paragraph", "availability", "text", "checkbox", "radio", "button"];
const textComponentTypes = new Set(["heading", "paragraph"]);

export const moveBookingComponent = (items, sourceId, targetIndex) => {
  const current = Array.isArray(items) ? [...items] : [];
  const sourceIndex = current.findIndex((item) => item.id === sourceId);
  if (sourceIndex < 0) return current;
  const [moved] = current.splice(sourceIndex, 1);
  const adjustedIndex = sourceIndex < targetIndex ? targetIndex - 1 : targetIndex;
  current.splice(Math.max(0, Math.min(adjustedIndex, current.length)), 0, moved);
  return current;
};

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

const renderPreviewText = (item) => {
  const textStyle = normalizeReservationTextStyle(item.textStyle);
  const style = getReservationTextStyle(item);
  const lines = String(item.text || "").split("\n").filter((line) => line.trim());
  if (textStyle.format === "bullets" || textStyle.format === "numbers") {
    const Tag = textStyle.format === "numbers" ? "ol" : "ul";
    return <Tag style={style}>{lines.map((line, index) => <li key={`${item.id}_${index}`}>{line}</li>)}</Tag>;
  }
  const Tag = ["h1", "h2", "h3"].includes(textStyle.format)
    ? textStyle.format
    : item.type === "heading" ? "h3" : "p";
  return <Tag style={style}>{item.text}</Tag>;
};

function BookingComponentPreview({ item, availableDates, timeSlots, timeSlotsByDate }) {
  if (textComponentTypes.has(item.type)) return renderPreviewText(item);
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
        ) : <small>No availability entered yet.</small>}
      </div>
    );
  }
  if (item.type === "text") {
    return <label>{item.label}{item.required ? " *" : ""}<input disabled placeholder={item.placeholder || ""} /></label>;
  }
  if (item.type === "checkbox" || item.type === "radio") {
    return (
      <fieldset>
        <legend>{item.label}{item.required ? " *" : ""}</legend>
        {(item.options || []).map((option, index) => (
          <label key={`${item.id}_${index}`}><input type={item.type} disabled /> <span>{option}</span></label>
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
    <div className="booking-text-toolbar" role="toolbar" aria-label="Booking text formatting">
      <select aria-label="Text style" value={style.format} onChange={(event) => updateStyle({ format: event.target.value })}>
        <option value="text">Text</option>
        <option value="h1">H1</option>
        <option value="h2">H2</option>
        <option value="h3">H3</option>
        <option value="bullets">Bullets</option>
        <option value="numbers">Numbers</option>
      </select>
      <select aria-label="Font family" value={style.fontFamily} onChange={(event) => updateStyle({ fontFamily: event.target.value })}>
        {pageBuilderFontFamilyOptions.map((font) => <option value={font} key={font}>{font}</option>)}
      </select>
      <label title="Text size"><span>Size</span><input aria-label="Text size" type="number" min="8" max="256" value={style.fontSize} onChange={(event) => updateStyle({ fontSize: event.target.value })} /></label>
      <label title="Text opacity"><span>Opacity</span><input aria-label="Text opacity" type="number" min="0" max="100" value={Math.round(style.opacity * 100)} onChange={(event) => updateStyle({ opacity: Number(event.target.value) / 100 })} /><span>%</span></label>
      <button type="button" aria-label="Undo formatting" title="Undo" disabled={!canUndo} onClick={onUndo}><Undo2 size={15} /></button>
      <button type="button" aria-label="Redo formatting" title="Redo" disabled={!canRedo} onClick={onRedo}><Redo2 size={15} /></button>
      {toolbarButtons.map(({ id, label, icon: Icon }) => {
        const active =
          (id === "bold" && style.fontWeight === "700") ||
          (id === "italic" && style.fontStyle === "italic") ||
          (id === "underline" && style.textDecoration === "underline") ||
          (["bullets", "numbers"].includes(id) && style.format === id) ||
          (["left", "center", "right", "justify"].includes(id) && style.textAlign === id);
        return <button type="button" className={active ? "is-active" : ""} aria-label={label} title={label} key={id} onClick={() => applyAction(id)}><Icon size={15} /></button>;
      })}
      <label className="booking-toolbar-color" title="Text color"><Baseline size={15} /><input aria-label="Text color" type="color" value={style.color || "#111827"} onChange={(event) => updateStyle({ color: event.target.value })} /></label>
      <label className="booking-toolbar-color" title="Background color"><Highlighter size={15} /><input aria-label="Text background color" type="color" value={style.backgroundColor || "#ffffff"} onChange={(event) => updateStyle({ backgroundColor: event.target.value })} /></label>
    </div>
  );
}

function BookingComponentInspector({ item, onUpdate, onDelete, onUndo, onRedo, canUndo, canRedo }) {
  const updateOption = (index, value) => {
    onUpdate({ options: item.options.map((option, optionIndex) => optionIndex === index ? value : option) });
  };
  const updateDirection = (direction) => {
    onUpdate({
      direction,
      ...(textComponentTypes.has(item.type)
        ? { textStyle: { ...normalizeReservationTextStyle(item.textStyle), textAlign: direction === "rtl" ? "right" : "left" } }
        : {}),
    });
  };

  return (
    <aside className="booking-component-inspector" aria-label="Selected booking component settings">
      <div className="booking-component-inspector-heading">
        <div>
          <span>Component settings</span>
          <h4>{reservationFormItemLabels[item.type]}</h4>
        </div>
      </div>

      {textComponentTypes.has(item.type) && (
        <BookingTextToolbar item={item} onUpdate={onUpdate} onUndo={onUndo} onRedo={onRedo} canUndo={canUndo} canRedo={canRedo} />
      )}

      {textComponentTypes.has(item.type) ? (
        <label>
          {item.type === "heading" ? "Heading text" : "Paragraph text"}
          {item.type === "paragraph" ? (
            <textarea value={item.text} onChange={(event) => onUpdate({ text: event.target.value })} />
          ) : (
            <input value={item.text} onChange={(event) => onUpdate({ text: event.target.value })} />
          )}
        </label>
      ) : (
        <label>
          {item.type === "button" ? "Button label" : item.type === "availability" ? "Section label" : "Question label"}
          <input value={item.label} onChange={(event) => onUpdate({ label: event.target.value })} />
        </label>
      )}

      {item.type === "text" && (
        <label>Placeholder<input value={item.placeholder || ""} onChange={(event) => onUpdate({ placeholder: event.target.value })} /></label>
      )}

      {(item.type === "checkbox" || item.type === "radio") && (
        <div className="booking-component-options">
          <span>Choices</span>
          {item.options.map((option, index) => (
            <div key={`${item.id}_option_${index}`}>
              <input value={option} onChange={(event) => updateOption(index, event.target.value)} />
              <button type="button" aria-label={`Remove option ${index + 1}`} disabled={item.options.length <= 1} onClick={() => onUpdate({ options: item.options.filter((_, optionIndex) => optionIndex !== index) })}><Trash2 size={13} /></button>
            </div>
          ))}
          <button type="button" onClick={() => onUpdate({ options: [...item.options, `Option ${item.options.length + 1}`] })}><Plus size={13} /> Add choice</button>
        </div>
      )}

      {["text", "checkbox", "radio"].includes(item.type) && (
        <label className="booking-component-required"><input type="checkbox" checked={Boolean(item.required)} onChange={(event) => onUpdate({ required: event.target.checked })} />Required answer</label>
      )}

      <div className="booking-component-direction">
        <span>Content direction</span>
        <div role="group" aria-label="Component content direction">
          <button type="button" className={item.direction !== "rtl" ? "is-active" : ""} aria-pressed={item.direction !== "rtl"} onClick={() => updateDirection("ltr")}>LTR</button>
          <button type="button" className={item.direction === "rtl" ? "is-active" : ""} aria-pressed={item.direction === "rtl"} onClick={() => updateDirection("rtl")}>RTL</button>
        </div>
      </div>

      <button type="button" className="booking-component-delete danger-button" onClick={onDelete}><Trash2 size={15} /> Delete component</button>
    </aside>
  );
}

export default function ReservationBlockBuilder({ items, onChange, availableDates = [], timeSlots = [], timeSlotsByDate, allowAvailability = false }) {
  const visibleToolboxTypes = allowAvailability ? toolboxTypes : toolboxTypes.filter((type) => type !== "availability");
  const components = useMemo(() => (Array.isArray(items) ? items : []).filter((item) => item && reservationFormItemLabels[item.type]), [items]);
  const [selectedId, setSelectedId] = useState(components[0]?.id || "");
  const [activeDropIndex, setActiveDropIndex] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const historyRef = useRef(new Map());
  const futureRef = useRef(new Map());
  const selected = components.find((item) => item.id === selectedId) || null;
  const hasButton = components.some((item) => item.type === "button");
  const hasAvailability = components.some((item) => item.type === "availability");

  useEffect(() => {
    if (!selectedId && components.length > 0) setSelectedId(components[0].id);
    else if (selectedId && components.length > 0 && !components.some((item) => item.id === selectedId)) setSelectedId(components[0].id);
  }, [components, selectedId]);

  const addComponent = (type, targetIndex = components.length) => {
    if ((type === "button" && hasButton) || (type === "availability" && hasAvailability)) return;
    const nextItem = createReservationFormItem(type);
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

  const updateSelected = (updates, recordHistory = true) => {
    const current = components.find((item) => item.id === selectedId);
    if (!current) return;
    if (recordHistory) {
      const history = historyRef.current.get(selectedId) || [];
      historyRef.current.set(selectedId, [...history.slice(-49), current]);
      futureRef.current.set(selectedId, []);
    }
    onChange(components.map((item) => item.id === selectedId ? { ...item, ...updates } : item));
  };

  const restoreSelected = (sourceRef, targetRef) => {
    const source = sourceRef.current.get(selectedId) || [];
    const current = components.find((item) => item.id === selectedId);
    if (!current || source.length === 0) return;
    const previous = source[source.length - 1];
    sourceRef.current.set(selectedId, source.slice(0, -1));
    targetRef.current.set(selectedId, [...(targetRef.current.get(selectedId) || []), current]);
    onChange(components.map((item) => item.id === selectedId ? previous : item));
  };

  const deleteSelected = () => {
    const index = components.findIndex((item) => item.id === selectedId);
    const next = components.filter((item) => item.id !== selectedId);
    onChange(next);
    setSelectedId(next[Math.min(index, next.length - 1)]?.id || "");
  };

  return (
    <div className="booking-element-builder">
      <aside className="booking-component-toolbox" aria-label="Booking component toolbox">
        <div className="booking-component-toolbox-heading"><strong>Components</strong><p>Drag a component onto the booking element.</p></div>
        <div className="booking-component-toolbox-list section-component-palette">
          {visibleToolboxTypes.map((type) => (
            <button type="button" draggable={!((type === "button" && hasButton) || (type === "availability" && hasAvailability))} disabled={(type === "button" && hasButton) || (type === "availability" && hasAvailability)} key={type}
              onDragStart={(event) => { writeDragPayload(event, { kind: "toolbox", type }); setIsDragging(true); }}
              onDragEnd={() => { setIsDragging(false); setActiveDropIndex(null); }} onClick={() => addComponent(type)}>
              <strong>{reservationFormItemLabels[type]}</strong><small>{(type === "button" && hasButton) || (type === "availability" && hasAvailability) ? "Already added" : "Drag into booking element"}</small>
            </button>
          ))}
        </div>
      </aside>

      <section className="booking-element-stage" aria-label="Booking element canvas">
        <div className="booking-element-stage-heading"><div><strong>Booking element</strong></div><small>Select an item to edit it</small></div>
        <div className={`booking-element-canvas ${isDragging ? "is-dragging" : ""}`}>
          {components.map((item, index) => (
            <div className="booking-canvas-component-slot" key={item.id}>
              <div className={`booking-component-dropzone ${isDragging ? "is-visible" : ""} ${activeDropIndex === index ? "is-active" : ""}`} onDragEnter={(event) => { event.preventDefault(); setActiveDropIndex(index); }} onDragOver={(event) => event.preventDefault()} onDrop={(event) => dropAt(event, index)} />
              <article className={`booking-canvas-component is-${item.type} ${selectedId === item.id ? "is-selected" : ""}`} draggable tabIndex={0} aria-label={`${reservationFormItemLabels[item.type]} component`}
                onDragStart={(event) => { writeDragPayload(event, { kind: "component", id: item.id }); setIsDragging(true); }} onDragEnd={() => { setIsDragging(false); setActiveDropIndex(null); }} onClick={() => setSelectedId(item.id)} onFocus={() => setSelectedId(item.id)}>
                <div className="booking-canvas-component-preview" dir={item.direction === "rtl" ? "rtl" : "ltr"}><BookingComponentPreview item={item} availableDates={availableDates} timeSlots={timeSlots} timeSlotsByDate={timeSlotsByDate} /></div>
              </article>
            </div>
          ))}
          <div className={`booking-component-dropzone is-last ${isDragging ? "is-visible" : ""} ${activeDropIndex === components.length ? "is-active" : ""}`} onDragEnter={(event) => { event.preventDefault(); setActiveDropIndex(components.length); }} onDragOver={(event) => event.preventDefault()} onDrop={(event) => dropAt(event, components.length)} />
          {components.length === 0 && !isDragging ? <div className="booking-element-empty-state"><strong>Add your first component</strong><span>Choose a component above or drag it here.</span></div> : null}
        </div>
      </section>

      {selected ? (
        <BookingComponentInspector item={selected} onUpdate={updateSelected} onDelete={deleteSelected}
          onUndo={() => restoreSelected(historyRef, futureRef)} onRedo={() => restoreSelected(futureRef, historyRef)}
          canUndo={(historyRef.current.get(selectedId) || []).length > 0} canRedo={(futureRef.current.get(selectedId) || []).length > 0} />
      ) : <aside className="booking-component-inspector is-empty"><strong>No component selected</strong><p>Drag a component onto the canvas, then select it to edit its content.</p></aside>}
    </div>
  );
}