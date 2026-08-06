import { type ReactNode, useEffect, useRef } from "react";
import { createPortal } from "react-dom";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  wide?: boolean;
  className?: string;
}

export function Modal({
  open,
  onClose,
  title,
  children,
  wide = false,
  className = "",
}: ModalProps) {
  const pointerDownOnBackdrop = useRef(false);

  useEffect(() => {
    if (!open) return;
    document.documentElement.classList.add("modal-scroll-lock");
    return () => document.documentElement.classList.remove("modal-scroll-lock");
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      className="modal-backdrop"
      role="presentation"
      onPointerDown={(e) => {
        pointerDownOnBackdrop.current = e.target === e.currentTarget;
      }}
      onClick={(e) => {
        if (pointerDownOnBackdrop.current && e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        className={`modal card${wide ? " modal--wide" : ""}${className ? ` ${className}` : ""}`}
        role="dialog"
        aria-modal
        aria-labelledby="modal-title"
      >
        <div className="modal__head">
          <h2 id="modal-title">{title}</h2>
          <button type="button" className="modal__close" onClick={onClose} aria-label="Fechar">
            ×
          </button>
        </div>
        <div className="modal__body">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
