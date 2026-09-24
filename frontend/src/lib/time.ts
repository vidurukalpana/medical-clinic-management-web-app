// All dates are shown in the clinic's timezone, matching the backend's CLINIC_TIMEZONE.
export const CLINIC_TZ: string = import.meta.env.VITE_CLINIC_TIMEZONE || "Asia/Colombo";

const WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
export const weekdayName = (weekday: number) => WEEKDAYS[weekday] ?? `Day ${weekday}`;

function parts(date: Date) {
  const values: Record<string, string> = {};
  for (const part of new Intl.DateTimeFormat("en-CA", {
    timeZone: CLINIC_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date)) {
    values[part.type] = part.value;
  }
  return values;
}

/** Clinic-local calendar date as YYYY-MM-DD. */
export function clinicDate(date: Date = new Date()): string {
  const p = parts(date);
  return `${p.year}-${p.month}-${p.day}`;
}

/** Offset of the clinic timezone at `date`, e.g. "+05:30". */
export function clinicOffset(date: Date = new Date()): string {
  const name =
    new Intl.DateTimeFormat("en-US", { timeZone: CLINIC_TZ, timeZoneName: "longOffset" })
      .formatToParts(date)
      .find((part) => part.type === "timeZoneName")?.value ?? "GMT";
  const match = name.match(/GMT([+-]\d{2}):?(\d{2})?/);
  return match ? `${match[1]}:${match[2] ?? "00"}` : "+00:00";
}

/** Converts a clinic-local "YYYY-MM-DDTHH:MM" value into an offset-aware ISO string. */
export function localInputToIso(value: string): string {
  const naive = new Date(`${value}:00Z`);
  return `${value}:00${clinicOffset(naive)}`;
}

/** Converts an ISO timestamp into a clinic-local "YYYY-MM-DDTHH:MM" input value. */
export function isoToLocalInput(iso: string): string {
  const p = parts(new Date(iso));
  return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`;
}

/** Adds days to a YYYY-MM-DD string. */
export function addDays(day: string, amount: number): string {
  const date = new Date(`${day}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + amount);
  return date.toISOString().slice(0, 10);
}

/** Monday = 0 … Sunday = 6, as in Python's date.weekday(). */
export function weekdayOf(day: string): number {
  return (new Date(`${day}T12:00:00Z`).getUTCDay() + 6) % 7;
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat("en-US", { timeZone: CLINIC_TZ, hour: "numeric", minute: "2-digit" }).format(
    new Date(iso),
  );
}

export function formatDateTime(iso: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: CLINIC_TZ,
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function formatDay(day: string, style: "long" | "short" = "long"): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "UTC",
    weekday: style === "long" ? "long" : "short",
    month: style === "long" ? "long" : "short",
    day: "numeric",
  }).format(new Date(`${day}T12:00:00Z`));
}

/** "09:00:00" → "9:00 AM" */
export function formatClock(value: string): string {
  const [h, m] = value.split(":").map(Number);
  const suffix = h >= 12 ? "PM" : "AM";
  return `${h % 12 || 12}:${String(m).padStart(2, "0")} ${suffix}`;
}

export function greeting(): string {
  const hour = Number(parts(new Date()).hour);
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}
