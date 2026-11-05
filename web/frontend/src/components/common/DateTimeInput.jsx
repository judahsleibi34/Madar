import { forwardRef, useEffect, useId, useImperativeHandle, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CalendarDays, ChevronLeft, ChevronRight, Clock3 } from "lucide-react";
import { useTranslation } from "react-i18next";
import "./DateTimeInput.css";

const pad = (value) => String(value).padStart(2, "0");
const dayValue = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
const types = new Set(["date", "time", "datetime-local"]);
const copy = {
  en: { date: "Choose date", time: "Choose time", "datetime-local": "Choose date and time", previous: "Previous month", next: "Next month", hour: "Hour (0–23)", minute: "Minute", clear: "Clear", today: "Today", done: "Done" },
  ar: { date: "اختر التاريخ", time: "اختر الوقت", "datetime-local": "اختر التاريخ والوقت", previous: "الشهر السابق", next: "الشهر التالي", hour: "الساعة (0–23)", minute: "الدقيقة", clear: "مسح", today: "اليوم", done: "تم" },
};

const DateTimeInput = forwardRef(function DateTimeInput({ type = "text", value, defaultValue, onChange, disabled, readOnly, pickerLabel, ...props }, forwardedRef) {
  const { i18n } = useTranslation();
  const locale = props.lang || i18n?.resolvedLanguage || "en";
  const rtl = locale.startsWith("ar");
  const text = copy[rtl ? "ar" : "en"];
  const [internal, setInternal] = useState(defaultValue ?? "");
  const selected = String(value ?? internal ?? "");
  const [open, setOpen] = useState(false);
  const [portalHost, setPortalHost] = useState(null);
  const [month, setMonth] = useState(() => new Date());
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const input = useRef(null);
  const root = useRef(null);
  const trigger = useRef(null);
  const popup = useRef(null);
  const popupId = useId();
  useImperativeHandle(forwardedRef, () => input.current);
  const temporal = types.has(type);
  const hasDate = type !== "time";
  const hasTime = type !== "date";
  const selectedDay = hasDate ? selected.slice(0, 10) : "";
  const time = (type === "time" ? selected : selected.slice(11)) || "09:00";
  const [hour, minute] = time.split(":");
  const today = dayValue(new Date());
  const start = new Date(month.getFullYear(), month.getMonth(), 1, 12);
  start.setDate(1 - start.getDay());
  const allowed = (next) => !next || (type === "time" && props.min && props.max && props.min > props.max
    ? next >= props.min || next <= props.max
    : (!props.min || next >= props.min) && (!props.max || next <= props.max));

  const emit = (next) => {
    if (disabled || readOnly || input.current?.matches(":disabled") || !allowed(next)) return;
    // Use the native setter so React observes the same change as direct entry.
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set.call(input.current, next);
    input.current.dispatchEvent(new Event("change", { bubbles: true }));
  };
  const close = () => { setOpen(false); trigger.current?.focus(); };

  useEffect(() => {
    if (!open) return undefined;
    const place = () => {
      const box = root.current?.getBoundingClientRect();
      if (!box) return;
      const width = Math.min(320, window.innerWidth - 24);
      const height = popup.current?.offsetHeight || 420;
      const top = box.bottom + 8 + height <= window.innerHeight ? box.bottom + 8 : Math.max(12, box.top - height - 8);
      setPosition({ top, left: Math.max(12, Math.min(rtl ? box.left : box.right - width, window.innerWidth - width - 12)) });
    };
    const popupElement = popup.current;
    popupElement?.showPopover?.();
    place();
    popup.current?.querySelector('[aria-pressed="true"], [data-picker-day], input')?.focus();
    const outside = (event) => {
      if (!root.current?.contains(event.target) && !popup.current?.contains(event.target)) setOpen(false);
    };
    const escape = (event) => { if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); setOpen(false); trigger.current?.focus(); } };
    const blur = (event) => {
      if (!root.current?.contains(event.target) && !popup.current?.contains(event.target)) setOpen(false);
    };
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    document.addEventListener("pointerdown", outside);
    document.addEventListener("focusin", blur);
    document.addEventListener("keydown", escape, true);
    return () => {
      if (popupElement?.hidePopover && popupElement.isConnected) popupElement.hidePopover();
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("focusin", blur);
      document.removeEventListener("keydown", escape, true);
    };
  }, [open, rtl]);

  const changeTime = (part, next, maximum) => {
    if (next === "" || !Number.isInteger(Number(next)) || Number(next) < 0 || Number(next) > maximum) return;
    const parts = time.split(":"); parts[part] = pad(Number(next));
    emit(type === "time" ? parts.join(":") : `${selectedDay || today}T${parts.join(":")}`);
  };
  const chooseDay = (day) => {
    let next = type === "date" ? day : `${day}T${time}`;
    if (props.min?.startsWith(day) && next < props.min) next = props.min;
    if (props.max?.startsWith(day) && next > props.max) next = props.max;
    emit(next);
  };
  const inputElement = <input {...props} ref={input} type={type} disabled={disabled} readOnly={readOnly} value={value === undefined ? undefined : value} defaultValue={value === undefined ? defaultValue : undefined} onChange={(event) => { setInternal(event.target.value); onChange?.(event); }} />;
  if (!temporal) return inputElement;

  return <span className="madar-date-input" ref={root}>
    {inputElement}
    <button type="button" className="madar-date-input-trigger" ref={trigger} disabled={disabled || readOnly} aria-label={pickerLabel || text[type]} aria-haspopup="dialog" aria-expanded={open} aria-controls={open ? popupId : undefined} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => {
      event.preventDefault();
      event.stopPropagation();
      if (input.current?.matches(":disabled")) return;
      if (!open) {
        setPortalHost(input.current?.closest("dialog[open]") || document.body);
        setMonth(selectedDay ? new Date(`${selectedDay}T12:00`) : new Date());
      }
      setOpen((current) => !current);
    }}>{hasDate ? <CalendarDays size={16} /> : <Clock3 size={16} />}</button>
    {open && !disabled && !readOnly && createPortal(<div id={popupId} className="madar-date-picker-popup" popover={typeof HTMLElement !== "undefined" && typeof HTMLElement.prototype.showPopover === "function" ? "manual" : undefined} data-madar-picker dir={rtl ? "rtl" : "ltr"} ref={popup} onPointerDown={(event) => event.stopPropagation()} onClick={(event) => event.stopPropagation()} role="dialog" aria-label={text[type]} style={position}>
      {hasDate && <><header><strong aria-live="polite">{month.toLocaleDateString(locale, { month: "long", year: "numeric" })}</strong><button type="button" aria-label={text.previous} onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))}><ChevronLeft size={16} /></button><button type="button" aria-label={text.next} onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))}><ChevronRight size={16} /></button></header>
      <div className="madar-date-picker-days">{Array.from({ length: 7 }, (_, index) => <span key={index}>{new Date(2026, 10, 1 + index).toLocaleDateString(locale, { weekday: "short" })}</span>)}
        {Array.from({ length: 42 }, (_, index) => {
          const date = new Date(start); date.setDate(start.getDate() + index); const day = dayValue(date);
          const outsideBounds = (props.min && day < props.min.slice(0, 10)) || (props.max && day > props.max.slice(0, 10));
          return <button type="button" key={day} data-picker-day={day} disabled={Boolean(outsideBounds)} aria-label={date.toLocaleDateString(locale, { weekday: "long", year: "numeric", month: "long", day: "numeric" })} aria-pressed={day === selectedDay} aria-current={day === today ? "date" : undefined} className={date.getMonth() !== month.getMonth() ? "is-outside" : ""} onClick={() => chooseDay(day)}>{date.getDate()}</button>;
        })}</div></>}
      {hasTime && <div className="madar-date-picker-time"><label>{text.hour}<input type="number" min="0" max="23" value={Number(hour)} onChange={(event) => changeTime(0, event.target.value, 23)} /></label><label>{text.minute}<input type="number" min="0" max="59" value={Number(minute)} onChange={(event) => changeTime(1, event.target.value, 59)} /></label></div>}
      <footer><button type="button" onClick={() => emit("")}>{text.clear}</button>{hasDate && <button type="button" disabled={!allowed(type === "date" ? today : `${today}T${time}`)} onClick={() => { setMonth(new Date()); chooseDay(today); }}>{text.today}</button>}<button type="button" className="is-done" onClick={close}>{text.done}</button></footer>
    </div>, portalHost || document.body)}
  </span>;
});
export default DateTimeInput;
