import type { PublicDoctor, WeeklySession } from "./api";
import { formatClock } from "./time";

const SHORT_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** Weekly sessions in a line, e.g. "Mon, Wed · 5:00 PM" or "Mon 8:00 AM · Fri 2:00 PM". */
export function describeWeek(sessions: WeeklySession[]): string {
  const byTime = new Map<string, number[]>();
  for (const session of sessions) byTime.set(session.start_time, [...(byTime.get(session.start_time) ?? []), session.weekday]);
  return [...byTime.entries()]
    .map(([start, days]) => {
      const sorted = [...new Set(days)].sort();
      const label =
        sorted.length === 5 && sorted[0] === 0 && sorted[4] === 4 ? "Mon–Fri" : sorted.map((day) => SHORT_DAYS[day]).join(", ");
      return `${label} · ${formatClock(start)}`;
    })
    .join("  |  ");
}

export function formatFee(fee: number | null): string | null {
  return fee === null ? null : `Rs. ${fee.toLocaleString("en-US")}`;
}

export const consultsOn = (doctor: PublicDoctor, weekday: number) =>
  doctor.weekly_sessions.some((session) => session.weekday === weekday);

/** Case-insensitive match on name, specialty, qualifications and languages. */
export function matchesSearch(doctor: PublicDoctor, query: string): boolean {
  const text = [doctor.display_name, doctor.specialty, doctor.qualifications, doctor.languages]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
  return query
    .toLowerCase()
    .split(/\s+/)
    .filter(Boolean)
    .every((word) => text.includes(word));
}

export function specialtiesOf(doctors: PublicDoctor[]): string[] {
  return [...new Set(doctors.map((doctor) => doctor.specialty).filter((value): value is string => !!value))].sort();
}
