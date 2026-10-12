import { useEffect, useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Sun, Sunrise, Moon, CalendarX } from "lucide-react";
import { api, type BookingSession } from "../lib/api";
import { addDays, CLINIC_TZ, clinicDate, formatTime, weekdayOf } from "../lib/time";
import { EmptyState, ErrorNote, Spinner } from "./ui";

const DAYS_AHEAD = 21;

/** Upcoming clinic weekdays (availability can only be defined Monday–Friday). */
export function upcomingClinicDays(count = DAYS_AHEAD): string[] {
  const days: string[] = [];
  let day = clinicDate();
  while (days.length < count) {
    if (weekdayOf(day) < 5) days.push(day);
    day = addDays(day, 1);
  }
  return days;
}

function DayChip({ doctorId, day, selected, onSelect }: {
  doctorId: number;
  day: string;
  selected: boolean;
  onSelect: () => void;
}) {
  const status = useQuery({
    queryKey: ["booking-status", doctorId, day],
    queryFn: () => api.bookingStatus(doctorId, day),
    staleTime: 30_000,
  });
  const date = new Date(`${day}T12:00:00Z`);
  const remaining = status.data?.remaining_places;
  const full = status.data?.is_fully_booked;
  return (
    <button
      type="button"
      className={`day-chip ${selected ? "is-selected" : ""} ${full || status.isError ? "is-full" : ""}`}
      onClick={onSelect}
      aria-pressed={selected}
    >
      <span className="day-chip-wd">{date.toLocaleDateString("en-US", { weekday: "short", timeZone: "UTC" })}</span>
      <span className="day-chip-num">{date.getUTCDate()}</span>
      <span className="day-chip-mo">{date.toLocaleDateString("en-US", { month: "short", timeZone: "UTC" })}</span>
      <span className="day-chip-meta">
        {status.isLoading ? "…" : status.isError ? "—" : full ? "Full" : `${remaining} left`}
      </span>
    </button>
  );
}

export function DayStrip({ doctorId, value, onChange }: {
  doctorId: number;
  value: string | null;
  onChange: (day: string) => void;
}) {
  const days = useMemo(() => upcomingClinicDays(), []);
  const scroller = useRef<HTMLDivElement>(null);
  const scroll = (direction: number) =>
    scroller.current?.scrollBy({ left: direction * scroller.current.clientWidth * 0.8, behavior: "smooth" });

  return (
    <div className="day-strip">
      <button type="button" className="icon-btn day-strip-nav" onClick={() => scroll(-1)} aria-label="Earlier days">
        <ChevronLeft size={18} />
      </button>
      <div className="day-strip-scroll" ref={scroller}>
        {days.map((day) => (
          <DayChip key={day} doctorId={doctorId} day={day} selected={day === value} onSelect={() => onChange(day)} />
        ))}
      </div>
      <button type="button" className="icon-btn day-strip-nav" onClick={() => scroll(1)} aria-label="Later days">
        <ChevronRight size={18} />
      </button>
    </div>
  );
}

function bucket(session: BookingSession) {
  const hour = Number(
    new Intl.DateTimeFormat("en-US", {
      timeZone: CLINIC_TZ,
      hour: "numeric",
      hourCycle: "h23",
    }).format(new Date(session.start_at)),
  );
  return hour < 12 ? "Morning" : hour < 17 ? "Afternoon" : "Evening";
}

const BUCKET_ICON = { Morning: Sunrise, Afternoon: Sun, Evening: Moon } as const;

export function SessionList({ doctorId, day, value, onChange }: {
  doctorId: number;
  day: string;
  value: string | null;
  onChange: (session: BookingSession) => void;
}) {
  const sessions = useQuery({
    queryKey: ["sessions", doctorId, day],
    queryFn: () => api.sessions(doctorId, day),
    staleTime: 15_000,
  });
  const open = sessions.data?.filter((session) => session.remaining > 0) ?? [];

  // With one open session the date is enough, so choose it for the patient.
  const onlyOpen = open.length === 1 ? open[0] : null;
  useEffect(() => {
    if (!value && onlyOpen) onChange(onlyOpen);
  }, [value, onlyOpen, onChange]);

  if (sessions.isLoading) return <Spinner label="Checking sessions…" />;
  if (sessions.isError) return <ErrorNote error={sessions.error} />;
  if (!sessions.data?.length)
    return (
      <EmptyState
        icon={<CalendarX size={22} />}
        title="No sessions on this day"
        hint="The doctor isn't consulting then. Try another date."
      />
    );

  return (
    <div className="session-list">
      {sessions.data.map((session) => {
        const name = bucket(session);
        const Icon = BUCKET_ICON[name];
        const full = session.remaining === 0;
        return (
          <button
            type="button"
            key={session.start_at}
            className={`session-option ${value === session.start_at ? "is-selected" : ""}`}
            onClick={() => onChange(session)}
            disabled={full}
            aria-pressed={value === session.start_at}
          >
            <Icon size={18} />
            <span className="session-option-text">
              <strong>
                {formatTime(session.start_at)} – {formatTime(session.end_at)}
              </strong>
              <small>{name} session</small>
            </span>
            <span className="session-option-meta">{full ? "Full" : `${session.remaining} left`}</span>
          </button>
        );
      })}
      <p className="muted small">Patients are seen in number order. You'll get your number when you book.</p>
    </div>
  );
}

/** Day strip + that day's sessions, used for booking and rescheduling. */
export function SessionPicker({ doctorId, day, onDayChange, value, onChange }: {
  doctorId: number;
  day: string | null;
  onDayChange: (day: string) => void;
  value: string | null;
  onChange: (session: BookingSession) => void;
}) {
  const days = useMemo(() => upcomingClinicDays(), []);
  useEffect(() => {
    if (!day) onDayChange(days[0]);
  }, [day, days, onDayChange]);
  return (
    <div className="session-picker">
      <DayStrip doctorId={doctorId} value={day} onChange={onDayChange} />
      {day && <SessionList doctorId={doctorId} day={day} value={value} onChange={onChange} />}
    </div>
  );
}
