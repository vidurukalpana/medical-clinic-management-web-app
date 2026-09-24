import { useEffect, useMemo, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight, Sun, Sunrise, Moon, CalendarX } from "lucide-react";
import { api, type Slot } from "../lib/api";
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
  const remaining = status.data?.remaining_slots;
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
        {status.isLoading ? "…" : status.isError ? "—" : full ? "Full" : `${remaining} open`}
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

function bucket(slot: Slot) {
  const hour = Number(
    new Intl.DateTimeFormat("en-US", {
      timeZone: CLINIC_TZ,
      hour: "numeric",
      hourCycle: "h23",
    }).format(new Date(slot.start_at)),
  );
  return hour < 12 ? "Morning" : hour < 17 ? "Afternoon" : "Evening";
}

const BUCKET_ICON = { Morning: Sunrise, Afternoon: Sun, Evening: Moon } as const;

export function SlotGrid({ doctorId, day, value, onChange }: {
  doctorId: number;
  day: string;
  value: string | null;
  onChange: (slot: Slot) => void;
}) {
  const slots = useQuery({
    queryKey: ["slots", doctorId, day],
    queryFn: () => api.availableSlots(doctorId, day),
    staleTime: 15_000,
  });

  const groups = useMemo(() => {
    const result: Record<string, Slot[]> = {};
    for (const slot of slots.data ?? []) (result[bucket(slot)] ??= []).push(slot);
    return result;
  }, [slots.data]);

  if (slots.isLoading) return <Spinner label="Finding open times…" />;
  if (slots.isError) return <ErrorNote error={slots.error} />;
  if (!slots.data?.length)
    return (
      <EmptyState
        icon={<CalendarX size={22} />}
        title="No open times on this day"
        hint="The doctor may be fully booked or not consulting. Try another date."
      />
    );

  return (
    <div className="slot-groups">
      {(["Morning", "Afternoon", "Evening"] as const)
        .filter((name) => groups[name])
        .map((name) => {
          const Icon = BUCKET_ICON[name];
          return (
            <div key={name} className="slot-group">
              <div className="slot-group-title">
                <Icon size={15} /> {name} <span className="muted">· {groups[name].length}</span>
              </div>
              <div className="slot-grid">
                {groups[name].map((slot) => (
                  <button
                    type="button"
                    key={slot.start_at}
                    className={`slot ${value === slot.start_at ? "is-selected" : ""}`}
                    onClick={() => onChange(slot)}
                  >
                    {formatTime(slot.start_at)}
                  </button>
                ))}
              </div>
            </div>
          );
        })}
    </div>
  );
}

/** Day strip + slot grid, used for booking and rescheduling. */
export function SlotPicker({ doctorId, day, onDayChange, value, onChange }: {
  doctorId: number;
  day: string | null;
  onDayChange: (day: string) => void;
  value: string | null;
  onChange: (slot: Slot) => void;
}) {
  const days = useMemo(() => upcomingClinicDays(), []);
  useEffect(() => {
    if (!day) onDayChange(days[0]);
  }, [day, days, onDayChange]);
  return (
    <div className="slot-picker">
      <DayStrip doctorId={doctorId} value={day} onChange={onDayChange} />
      {day && <SlotGrid doctorId={doctorId} day={day} value={value} onChange={onChange} />}
    </div>
  );
}
