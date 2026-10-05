import { useEffect, useRef } from "react";
import { X } from "lucide-react";

export default function ELearningDialog({ title, children, onClose, busy = false, closeLabel, className = "" }) {
  const dialogRef = useRef(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    const previous = document.activeElement;
    if (dialog.showModal) dialog.showModal(); else dialog.setAttribute("open", "");
    return () => { dialog.close?.(); previous?.focus?.(); };
  }, []);
  return <dialog ref={dialogRef} className={`ecommerce-modal elearning-dialog ${className}`.trim()} aria-labelledby="elearning-dialog-title"
    onCancel={(event) => { event.preventDefault(); if (!busy) onClose(); }}>
    <header><h2 id="elearning-dialog-title">{title}</h2><button className="ecommerce-icon-button" type="button" aria-label={closeLabel} disabled={busy} onClick={onClose}><X size={20} /></button></header>
    {children}
  </dialog>;
}
