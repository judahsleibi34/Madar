import { createElement, useEffect, useRef, useState } from "react";
import { CalendarDays, ChevronRight, FileText, Image, LayoutTemplate, List, Minus, MousePointer2, Play, Plus, Type, X } from "lucide-react";

const descriptions = {
  heading: "Introduce a section with a clear, editable title.",
  educationHero: "Welcome visitors with a large photograph, headline, and call to action.",
  text: "Add paragraphs, descriptions, and supporting copy.",
  button: "Guide visitors to a page, link, or connected action.",
  imageButton: "Turn an image into a clickable link or action.",
  imageCardButton: "Combine a photograph, title, and link in an editorial card.",
  image: "Display a photograph or illustration with adjustable sizing.",
  video: "Place a video player on your page.",
  document: "Let visitors view a document directly on the page.",
  photoProofing: "Share a photo gallery where clients can review and select images.",
  card: "Group an image, heading, and description in one content card.",
  carousel: "Present a collection of cards in a sliding carousel.",
  logoSlider: "Show a scrolling collection of client or partner logos.",
  list: "Organize related information into a readable list.",
  divider: "Separate content with a decorative divider.",
  thinDivider: "Add a simple horizontal line between sections.",
  embed: "Include external content using an embed.",
  metric: "Highlight a key number with a supporting label.",
  loginBlock: "Allow site members to sign in to their account.",
  registrationBlock: "Let new visitors create a site member account.",
  formBlock: "Connect a form so visitors can submit information.",
  reservationRequest: "Let visitors request a preferred date and time.",
  reservationFixedSlots: "Let visitors choose from available booking slots.",
  academyFeaturedCourses: "Highlight selected courses from your Academy catalog.",
  academyCourseCollection: "Help learners browse a collection of Academy courses.",
  academyPlans: "Present Academy plans and pricing options.",
  academyForm: "Connect an Academy form to collect learner information.",
  academyContact: "Display Academy contact information and ways to get in touch.",
  academyExchangeOpportunities: "Show available Academy exchange opportunities.",
  academyProgrammeInfo: "Introduce Academy programmes and their details.",
  academyInstructors: "Introduce the people teaching at your Academy.",
  academyContinueLearning: "Help signed-in learners return to their courses.",
};

const iconFor = (item) => {
  const type = item.type || item.id;
  if (item.group === "Bookings") return CalendarDays;
  if (["heading", "text"].includes(type)) return Type;
  if (["image", "imageButton", "imageCardButton", "photoProofing", "educationHero", "logoSlider"].includes(type)) return Image;
  if (type === "video") return Play;
  if (["divider", "thinDivider"].includes(type)) return Minus;
  if (type === "button") return MousePointer2;
  if (type === "list") return List;
  if (["document", "formBlock", "academyForm", "loginBlock", "registrationBlock"].includes(type)) return FileText;
  return LayoutTemplate;
};

function ComponentIcon({ item, ...props }) {
  return createElement(iconFor(item), props);
}

function ComponentExample({ item }) {
  const type = item.type || item.id;
  const isForm = ["formBlock", "academyForm", "loginBlock", "registrationBlock"].includes(type);
  return (
    <div className={`component-example component-example-${type}`} aria-hidden="true">
      {type === "heading" ? <strong className="component-example-title">A beautiful headline</strong>
        : type === "text" ? <p>Tell your story with clear, thoughtful words. Add a little detail to help your visitors discover more.</p>
        : type === "button" ? <span className="component-example-button">Discover more <ChevronRight size={14} /></span>
        : ["divider", "thinDivider"].includes(type) ? <hr />
        : type === "metric" ? <div><strong className="component-example-title">1,240</strong><p>Happy customers</p></div>
        : type === "list" ? <ul><li>A thoughtful first detail</li><li>Something worth discovering</li><li>One more reason to explore</li></ul>
        : isForm ? <div className="component-example-form"><strong>Your next step starts here</strong><span /><span /><span className="component-example-button">Continue</span></div>
        : item.group === "Bookings" ? <div className="component-example-booking"><CalendarDays size={32} /><strong>{item.label}</strong><div><span>09:00</span><span>11:00</span><span>14:00</span></div></div>
        : <div className="component-example-card"><div className="component-example-media"><ComponentIcon item={item} size={40} strokeWidth={1.25} /></div>{!["image", "video", "embed", "document"].includes(type) && <><strong>Something worth discovering</strong><p>A little detail brings your content to life.</p></>}</div>}
    </div>
  );
}

export default function PageBuilderComponentLibrary({ groups, items, selectedKey, onInspect, onDragStart }) {
  const [query, setQuery] = useState("");
  const filtered = items.filter((item) => `${item.label} ${item.group} ${descriptions[item.type || item.id] || ""}`.toLowerCase().includes(query.trim().toLowerCase()));
  return (
    <section className="builder-panel component-library">
      <h2>Components</h2>
      <p className="panel-help">Choose a component to explore, or drag it onto your page.</p>
      <label className="component-library-search"><input type="search" aria-label="Search components" placeholder="Search components…" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      <div className="component-library-list">
        {groups.map((group) => {
          const entries = filtered.filter((item) => item.group === group);
          if (!entries.length) return null;
          return <section className="component-library-group" key={group} aria-label={group}>
            <h3>{group}</h3>
            {entries.map((item) => {
              return <button type="button" key={item.key} className="component-library-row" draggable aria-label={`Preview ${item.label}`} aria-expanded={selectedKey === item.key} aria-controls={selectedKey === item.key ? "component-details" : undefined} onDragStart={(event) => onDragStart(event, item)} onClick={(event) => onInspect(item, event.currentTarget)}>
                <span className="component-library-icon"><ComponentIcon item={item} size={20} strokeWidth={1.6} aria-hidden="true" /></span>
                <span className="component-library-label"><strong>{item.label}</strong><small>{item.helper || descriptions[item.type || item.id]}</small></span>
                <ChevronRight size={14} aria-hidden="true" />
              </button>;
            })}
          </section>;
        })}
        {!filtered.length && <p className="panel-help">No components found. Try a different search.</p>}
      </div>
    </section>
  );
}

export function PageBuilderComponentDetails({ item, onClose, onAdd, onDragStart }) {
  const closeRef = useRef(null);
  const dragTimerRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const startDrag = (event) => {
    onDragStart(event, item);
    // Let the browser capture the native drag image before hiding the panel.
    // Keep the source mounted throughout the drag so Chromium does not cancel it.
    window.clearTimeout(dragTimerRef.current);
    dragTimerRef.current = window.setTimeout(() => setDragging(true), 0);
  };
  const endDrag = () => {
    window.clearTimeout(dragTimerRef.current);
    setDragging(false);
    onClose();
  };
  useEffect(() => () => window.clearTimeout(dragTimerRef.current), []);
  useEffect(() => {
    closeRef.current?.focus();
    const onKeyDown = (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);
  return (
    <section id="component-details" className={`component-details${dragging ? " is-dragging" : ""}`} role="region" aria-label={`${item.label} component details`}>
      <header><span>Component preview</span><button ref={closeRef} type="button" className="component-details-close" aria-label="Close component details" onClick={onClose}><X size={18} /></button></header>
      <div className="component-details-body">
        <span className="component-details-category">{item.group}</span>
        <h2>{item.label}</h2>
        <p>{descriptions[item.type || item.id] || "Add this component to your page and customize its content in the inspector."}</p>
        {item.helper && <p>{item.helper}{!item.isStarter ? ". Uses your saved booking configuration." : "."}</p>}
        <div className="component-details-preview" draggable onDragStart={startDrag} onDragEnd={endDrag}><ComponentExample item={item} /><span>Drag this preview onto the canvas · customize after adding</span></div>
      </div>
      <footer><button type="button" className="primary-action component-details-add" draggable onDragStart={startDrag} onDragEnd={endDrag} onClick={() => onAdd(item)}><Plus size={17} aria-hidden="true" />Add to page</button><p>Or drag the preview or this button onto the canvas.</p></footer>
    </section>
  );
}
