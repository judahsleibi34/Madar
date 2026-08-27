import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, Heart, Images, RotateCcw, X } from "lucide-react";

import { getResponsiveMediaProps } from "../../../utils/media";
import { parsePhotoProofingContent } from "../core/PageBuilder.uploadHandlers";
import "./PhotoProofingBlock.css";

const SWIPE_THRESHOLD = 90;
const EXIT_DELAY_MS = 220;

function DecisionSummary({ decisions }) {
  const values = Object.values(decisions);
  const liked = values.filter((value) => value === "liked").length;
  const rejected = values.filter((value) => value === "rejected").length;
  const favorites = values.filter((value) => value === "favorite").length;
  return (
    <div className="photo-proofing-summary-counts">
      <span><Check size={15} />{liked} kept</span>
      <span><Heart size={15} />{favorites} favorites</span>
      <span><X size={15} />{rejected} passed</span>
    </div>
  );
}

export default function PhotoProofingBlock({ content, settings = {}, disabled = false }) {
  const photos = useMemo(
    () => parsePhotoProofingContent(content).map((photo, index) => ({
      ...photo,
      id: `proof-${index + 1}`,
      description: index === 0 ? settings.description || photo.description : "",
      imageSource: photo.image,
      imageProps: getResponsiveMediaProps(photo.image, {
        sizes: "(max-width: 720px) 94vw, 76vw",
      }),
    })),
    [content, settings.description]
  );
  const [open, setOpen] = useState(false);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [decisions, setDecisions] = useState({});
  const [history, setHistory] = useState([]);
  const [dragX, setDragX] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [exitDirection, setExitDirection] = useState("");
  const dragStartRef = useRef(null);

  const title = settings.title || "Choose your photos";
  const description = settings.description || "Drag right to keep a photo or left to pass.";
  const buttonText = settings.buttonText || "Start selecting";
  const currentPhoto = photos[currentIndex];
  const reviewedCount = Object.keys(decisions).length;

  useEffect(() => {
    if (!open) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === "Escape") setOpen(false);
      if (event.key === "ArrowRight") commitDecision("liked");
      if (event.key === "ArrowLeft") commitDecision("rejected");
      if (event.key.toLowerCase() === "f") commitDecision("favorite");
    };
    window.addEventListener("keydown", handleKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  });

  const nextPhotoIndex = (fromIndex, nextDecisions) => {
    for (let index = fromIndex + 1; index < photos.length; index += 1) {
      if (!nextDecisions[photos[index].id]) return index;
    }
    return photos.length;
  };

  function commitDecision(decision) {
    if (!currentPhoto || exitDirection) return;
    const previous = decisions[currentPhoto.id];
    const nextDecisions = { ...decisions, [currentPhoto.id]: decision };
    setHistory((items) => [...items, { index: currentIndex, photoId: currentPhoto.id, previous }]);
    setDecisions(nextDecisions);
    setExitDirection(decision === "rejected" ? "left" : "right");
    window.setTimeout(() => {
      setCurrentIndex(nextPhotoIndex(currentIndex, nextDecisions));
      setDragX(0);
      setExitDirection("");
    }, EXIT_DELAY_MS);
  }

  const undoDecision = () => {
    const last = history.at(-1);
    if (!last || exitDirection) return;
    setHistory((items) => items.slice(0, -1));
    setDecisions((items) => {
      const next = { ...items };
      if (last.previous) next[last.photoId] = last.previous;
      else delete next[last.photoId];
      return next;
    });
    setCurrentIndex(last.index);
    setDragX(0);
  };

  const handlePointerDown = (event) => {
    if (!currentPhoto || exitDirection) return;
    dragStartRef.current = { pointerId: event.pointerId, x: event.clientX };
    event.currentTarget.setPointerCapture(event.pointerId);
    setDragging(true);
  };

  const handlePointerMove = (event) => {
    if (dragStartRef.current?.pointerId !== event.pointerId) return;
    setDragX(event.clientX - dragStartRef.current.x);
  };

  const handlePointerEnd = (event) => {
    if (dragStartRef.current?.pointerId !== event.pointerId) return;
    const distance = event.clientX - dragStartRef.current.x;
    dragStartRef.current = null;
    setDragging(false);
    if (distance >= SWIPE_THRESHOLD) commitDecision("liked");
    else if (distance <= -SWIPE_THRESHOLD) commitDecision("rejected");
    else setDragX(0);
  };

  const restart = () => {
    setCurrentIndex(0);
    setDecisions({});
    setHistory([]);
    setDragX(0);
    setExitDirection("");
  };

  const launcher = (
    <div className="photo-proofing-launcher">
      <div className="photo-proofing-launcher-collage" aria-hidden="true">
        {photos.slice(0, 3).map((photo, index) => (
          <img key={photo.id} {...getResponsiveMediaProps(photo.imageSource, { widths: [320, 480, 768], fallbackWidth: 480, sizes: "30vw" })} alt="" loading="lazy" decoding="async" style={{ "--proof-preview-index": index }} />
        ))}
        {photos.length === 0 && <span><Images size={34} /></span>}
      </div>
      <div className="photo-proofing-launcher-copy">
        <span className="photo-proofing-kicker"><Images size={15} /> Client photo selection</span>
        <h3>{title}</h3>
        <p>{description}</p>
        <div><strong>{photos.length}</strong><span>photos ready to review</span></div>
      </div>
      <button type="button" disabled={disabled || photos.length === 0} onClick={() => setOpen(true)}>{buttonText}</button>
    </div>
  );

  if (!open || typeof document === "undefined") return launcher;

  const cardStyle = {
    transform: exitDirection
      ? `translateX(${exitDirection === "right" ? "120vw" : "-120vw"}) rotate(${exitDirection === "right" ? 18 : -18}deg)`
      : `translateX(${dragX}px) rotate(${dragX / 24}deg)`,
    transition: dragging ? "none" : "transform 220ms cubic-bezier(.2,.8,.2,1)",
  };
  const likeStrength = Math.min(1, Math.max(0, dragX / SWIPE_THRESHOLD));
  const rejectStrength = Math.min(1, Math.max(0, -dragX / SWIPE_THRESHOLD));

  const modal = (
    <div className="photo-proofing-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setOpen(false); }}>
      <section className="photo-proofing-modal" role="dialog" aria-modal="true" aria-labelledby="photo-proofing-title">
        <header className="photo-proofing-modal-header">
          <div>
            <span>Client proofing</span>
            <h2 id="photo-proofing-title">{title}</h2>
          </div>
          <div className="photo-proofing-progress-copy"><strong>{Math.min(currentIndex + 1, photos.length)}</strong><span>of {photos.length}</span></div>
          <button type="button" onClick={() => setOpen(false)} aria-label="Close photo selection"><X size={20} /></button>
        </header>
        <div className="photo-proofing-progress"><i style={{ width: `${photos.length ? reviewedCount / photos.length * 100 : 0}%` }} /></div>

        {currentPhoto ? (
          <>
            <div className="photo-proofing-stage">
              <div className="photo-proofing-stack-card is-back" />
              <article
                className={`photo-proofing-card${dragging ? " is-dragging" : ""}`}
                style={cardStyle}
                onPointerDown={handlePointerDown}
                onPointerMove={handlePointerMove}
                onPointerUp={handlePointerEnd}
                onPointerCancel={handlePointerEnd}
              >
                <img {...currentPhoto.imageProps} alt={currentPhoto.title} decoding="async" draggable="false" />
                <span className="photo-proofing-decision is-reject" style={{ opacity: rejectStrength }}>PASS</span>
                <span className="photo-proofing-decision is-like" style={{ opacity: likeStrength }}>KEEP</span>
                <footer><strong>{currentPhoto.title}</strong>{currentPhoto.description && <span>{currentPhoto.description}</span>}</footer>
              </article>
            </div>
            <p className="photo-proofing-drag-hint"><span>← Drag left to pass</span><span>Drag right to keep →</span></p>
            <div className="photo-proofing-actions">
              <button type="button" className="is-reject" onClick={() => commitDecision("rejected")} aria-label="Pass this photo"><X size={22} /></button>
              <button type="button" className="is-undo" onClick={undoDecision} disabled={history.length === 0} aria-label="Undo last choice"><RotateCcw size={19} /></button>
              <button type="button" className="is-favorite" onClick={() => commitDecision("favorite")} aria-label="Favorite this photo"><Heart size={21} /></button>
              <button type="button" className="is-like" onClick={() => commitDecision("liked")} aria-label="Keep this photo"><Check size={23} /></button>
            </div>
          </>
        ) : (
          <div className="photo-proofing-complete">
            <span><Check size={30} /></span>
            <h3>Selection complete</h3>
            <p>Your choices are ready for a final review.</p>
            <DecisionSummary decisions={decisions} />
            <div><button type="button" onClick={undoDecision} disabled={history.length === 0}>Review last photo</button><button type="button" className="is-primary" onClick={() => setOpen(false)}>Submit selection</button></div>
            <button type="button" className="photo-proofing-start-over" onClick={restart}>Start over</button>
          </div>
        )}
        {currentPhoto && <small className="photo-proofing-shortcuts">Keyboard: ← pass · → keep · F favorite</small>}
      </section>
    </div>
  );

  return <>{launcher}{createPortal(modal, document.body)}</>;
}
