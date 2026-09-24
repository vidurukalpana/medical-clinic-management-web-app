import { useEffect, useRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Loader2, X, Inbox } from "lucide-react";
import type { AppointmentStatus, VisitStatus } from "../lib/api";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "accent";

export function Button({
  variant = "primary",
  size,
  loading,
  icon,
  children,
  className = "",
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: "sm" | "lg";
  loading?: boolean;
  icon?: ReactNode;
}) {
  return (
    <button
      className={`btn btn-${variant} ${size ? `btn-${size}` : ""} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 size={16} className="spin" /> : icon}
      {children}
    </button>
  );
}

export function Spinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="spinner-wrap">
      <Loader2 className="spin" size={22} />
      <span>{label}</span>
    </div>
  );
}

export function EmptyState({ title, hint, icon }: { title: string; hint?: string; icon?: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon ?? <Inbox size={22} />}</div>
      <strong>{title}</strong>
      {hint && <p>{hint}</p>}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="alert alert-error">{error instanceof Error ? error.message : String(error)}</div>;
}

export function Card({ children, className = "", title, action }: {
  children: ReactNode;
  className?: string;
  title?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <header className="card-head">
          {title && <h3>{title}</h3>}
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function Field({ label, hint, children, error }: {
  label: string;
  hint?: string;
  children: ReactNode;
  error?: string;
}) {
  return (
    <label className="field">
      <span className="field-label">{label}</span>
      {children}
      {error ? <span className="field-error">{error}</span> : hint && <span className="field-hint">{hint}</span>}
    </label>
  );
}

export function Modal({ open, title, onClose, children, footer, wide }: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  wide?: boolean;
}) {
  const backdrop = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      // Only the top-most modal reacts when dialogs are stacked.
      const all = document.querySelectorAll(".modal-backdrop");
      if (event.key === "Escape" && all[all.length - 1] === backdrop.current) onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div ref={backdrop} className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <div className={`modal ${wide ? "modal-wide" : ""}`} role="dialog" aria-modal="true" aria-label={title}>
        <header className="modal-head">
          <h3>{title}</h3>
          <button className="icon-btn" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>
        <div className="modal-body">{children}</div>
        {footer && <footer className="modal-foot">{footer}</footer>}
      </div>
    </div>
  );
}

const STATUS_LABEL: Record<AppointmentStatus | VisitStatus, string> = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
  no_show: "No-show",
  waiting: "Waiting",
  in_progress: "In consultation",
};

export function StatusBadge({ status }: { status: AppointmentStatus | VisitStatus }) {
  return (
    <span className={`badge badge-${status}`}>
      <i className="dot" />
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

export function Avatar({ name, size = 40, tone }: { name: string; size?: number; tone?: number }) {
  const initials = name
    .replace(/^(dr\.?\s+)/i, "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase())
    .join("");
  const hue = tone ?? [...name].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 6;
  return (
    <span className={`avatar avatar-${hue}`} style={{ width: size, height: size, fontSize: size * 0.38 }}>
      {initials || "?"}
    </span>
  );
}

export function Pagination({ offset, limit, total, onChange }: {
  offset: number;
  limit: number;
  total: number;
  onChange: (offset: number) => void;
}) {
  if (total <= limit) return null;
  const page = Math.floor(offset / limit) + 1;
  const pages = Math.ceil(total / limit);
  return (
    <div className="pagination">
      <span>
        {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onChange(offset - limit)}>
        Previous
      </Button>
      <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onChange(offset + limit)}>
        Next
      </Button>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}
