import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { CalendarCheck, CalendarClock, Clock, QrCode, Radio, Stethoscope } from "lucide-react";
import type { BookingSession, GuestBooking } from "../lib/api";
import { useNextOpenSession } from "../lib/hooks";
import { formatDay, formatTime, clinicDate, liveQueueLink } from "../lib/time";
import { SessionPicker } from "./SessionPicker";
import { CheckInQr } from "./CheckInQr";
import { Button, Modal, StatusBadge } from "./ui";

export function BookingTicket({ booking, doctorName, actions }: {
  booking: GuestBooking;
  doctorName?: string;
  actions?: ReactNode;
}) {
  const [showQr, setShowQr] = useState(false);
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
        {needsNewDate(booking) && (
          <p className="ticket-note">We're sorry, the clinic had to cancel this session. Please move your booking to another date.</p>
        )}
        {isUpcoming(booking) && (
          <button type="button" className="link-arrow small ticket-qr-toggle" onClick={() => setShowQr((value) => !value)}>
            <QrCode size={14} /> {showQr ? "Hide check-in QR" : "Show check-in QR"}
          </button>
        )}
        {showQr && isUpcoming(booking) && <CheckInQr code={booking.checkin_code} size={150} />}
        {booking.status === "scheduled" && day === clinicDate() && (
          <Link to={liveQueueLink(booking)} className="link-arrow small">
            <Radio size={14} /> See where the queue is
          </Link>
        )}
        {actions && <div className="ticket-actions">{actions}</div>}
      </div>
    </article>
  );
}

export function RescheduleModal({ open, doctorId, onClose, onConfirm, busy, allPlaces = false }: {
  open: boolean;
  doctorId: number;
  onClose: () => void;
  onConfirm: (session: BookingSession) => void;
  busy?: boolean;
  /** Staff, or a patient whose session the clinic cancelled, may use places kept for walk-ins. */
  allPlaces?: boolean;
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
        allPlaces={allPlaces}
      />
    </Modal>
  );
}

export const isUpcoming = (booking: GuestBooking) =>
  booking.status === "scheduled" && new Date(booking.end_at).getTime() > Date.now();

/** The clinic cancelled this booking's session within the last week, so the patient should pick a new one. */
export const needsNewDate = (booking: GuestBooking) =>
  booking.status === "cancelled" &&
  booking.cancelled_by_clinic &&
  new Date(booking.end_at).getTime() > Date.now() - 7 * 24 * 3600_000;

/** One tap to the doctor's next open session, or a free choice of date. */
export function MoveCancelledBooking({ booking, onMove, onChooseDate, busy }: {
  booking: GuestBooking;
  onMove: (startAt: string) => void;
  onChooseDate: () => void;
  busy?: boolean;
}) {
  const next = useNextOpenSession(booking.doctor_id);
  return (
    <>
      {next.data && (
        <Button size="sm" icon={<CalendarCheck size={15} />} loading={busy} onClick={() => onMove(next.data!.start_at)}>
          Move to {formatDay(clinicDate(new Date(next.data.start_at)), "short")}, {formatTime(next.data.start_at)}
        </Button>
      )}
      <Button variant="secondary" size="sm" icon={<CalendarClock size={15} />} onClick={onChooseDate}>
        Choose another date
      </Button>
    </>
  );
}
