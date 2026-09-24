import { useState, type ReactNode } from "react";
import { CalendarClock, Clock, Stethoscope } from "lucide-react";
import type { GuestBooking, Slot } from "../lib/api";
import { formatDay, formatTime, clinicDate } from "../lib/time";
import { SlotPicker } from "./SlotPicker";
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
        </h4>
        <p className="muted">
          <Clock size={14} /> {formatDay(day)} · {formatTime(booking.start_at)} – {formatTime(booking.end_at)}
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
  onConfirm: (slot: Slot) => void;
  busy?: boolean;
}) {
  const [day, setDay] = useState<string | null>(null);
  const [slot, setSlot] = useState<Slot | null>(null);
  return (
    <Modal
      open={open}
      wide
      title="Pick a new time"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Keep current time
          </Button>
          <Button
            icon={<CalendarClock size={16} />}
            disabled={!slot}
            loading={busy}
            onClick={() => slot && onConfirm(slot)}
          >
            {slot ? `Move to ${formatTime(slot.start_at)}` : "Choose a time"}
          </Button>
        </>
      }
    >
      <SlotPicker
        doctorId={doctorId}
        day={day}
        onDayChange={(next) => {
          setDay(next);
          setSlot(null);
        }}
        value={slot?.start_at ?? null}
        onChange={setSlot}
      />
    </Modal>
  );
}

export const isUpcoming = (booking: GuestBooking) =>
  booking.status === "scheduled" && new Date(booking.end_at).getTime() > Date.now();
