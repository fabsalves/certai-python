import { type ReactNode, useEffect } from "react";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  wide?: boolean;
}

export function Modal({ open, onClose, title, children, wide = false }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    document.documentElement.classList.add("modal-scroll-lock");
    return () => document.documentElement.classList.remove("modal-scroll-lock");
  }, [open]);

  if (!open) return null;

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div
        className={`modal card${wide ? " modal--wide" : ""}`}
        role="dialog"
        aria-modal
        aria-labelledby="modal-title"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal__head">
          <h2 id="modal-title">{title}</h2>
          <button type="button" className="modal__close" onClick={onClose} aria-label="Fechar">
            ×
          </button>
        </div>
        <div className="modal__body">{children}</div>
      </div>
    </div>
  );
}
