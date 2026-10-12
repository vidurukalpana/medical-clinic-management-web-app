import { useState, type ReactNode } from "react";
import { CalendarClock, Clock, Stethoscope } from "lucide-react";
import type { BookingSession, GuestBooking } from "../lib/api";
import { formatDay, formatTime, clinicDate } from "../lib/time";
import { SessionPicker } from "./SessionPicker";
import { Button, Modal, StatusBadge } from "./ui";

export function BookingTicket({ booking, doctorName, actions }: {
  booking: GuestBooking;
  doctorName?: string;
  actions?: ReactNode;
}) {
  const day = clinicDate(new Date(booking.start_at));
  const date = new Date(`${day}T12:00:00Z`);
  return (
    <article className={`ticket ticket-${booking.status}`}>
      <div className="ticket-date">
        <span>{date.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" })}</span>
        <strong>{date.getUTCDate()}</strong>
        <span>{date.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })}</span>
      </div>
      <div className="ticket-body">
        <div className="ticket-row">
          <StatusBadge status={booking.status} />
          <span className="muted mono">#{booking.id}</span>
        </div>
        <h4>
          <Stethoscope size={16} /> {doctorName ?? `Doctor #${booking.doctor_id}`}
          <span className="ticket-number">No. {booking.appointment_number}</span>
        </h4>
        <p className="muted">
          <Clock size={14} /> {formatDay(day)} · session starts {formatTime(booking.start_at)}
        </p>
        {actions && <div className="ticket-actions">{actions}</div>}
      </div>
    </article>
  );
}

export function RescheduleModal({ open, doctorId, onClose, onConfirm, busy }: {
  open: boolean;
  doctorId: number;
  onClose: () => void;
  onConfirm: (session: BookingSession) => void;
  busy?: boolean;
}) {
  const [day, setDay] = useState<string | null>(null);
  const [session, setSession] = useState<BookingSession | null>(null);
  return (
    <Modal
      open={open}
      wide
      title="Pick a new date"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Keep current booking
          </Button>
          <Button
            icon={<CalendarClock size={16} />}
            disabled={!session}
            loading={busy}
            onClick={() => session && onConfirm(session)}
          >
            {session ? `Move to ${formatDay(clinicDate(new Date(session.start_at)), "short")}` : "Choose a date"}
          </Button>
        </>
      }
    >
      <SessionPicker
        doctorId={doctorId}
        day={day}
        onDayChange={(next) => {
          setDay(next);
          setSession(null);
        }}
        value={session?.start_at ?? null}
        onChange={setSession}
      />
    </Modal>
  );
}

export const isUpcoming = (booking: GuestBooking) =>
  booking.status === "scheduled" && new Date(booking.end_at).getTime() > Date.now();
