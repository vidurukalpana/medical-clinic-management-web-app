import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CalendarX } from "lucide-react";
import { api, type LiveSession } from "../../lib/api";
import { usePublicDoctors } from "../../lib/hooks";
import { formatDay, formatTime } from "../../lib/time";
import { Avatar, EmptyState, ErrorNote, Spinner } from "../../components/ui";

const REFRESH_MS = 20_000;

const STATUS_LABEL: Record<LiveSession["status"], string> = {
  not_started: "Not started",
  in_progress: "In session",
  ended: "Ended",
  unavailable: "Cancelled",
};

function YourPlace({ session, number }: { session: LiveSession; number: number }) {
  if (session.now_serving === number) return <p className="live-you is-now">No. {number} · It's your turn now.</p>;
  if (!session.numbers_to_see.includes(number))
    return <p className="live-you">We can't find No. {number} in the waiting list. Please check with reception.</p>;
  const ahead = session.numbers_to_see.filter((item) => item < number).length;
  return (
    <p className="live-you">
      No. {number} · {ahead === 0 ? "You're next." : `${ahead} ahead of you.`}
    </p>
  );
}

function LiveCard({ session, tone, yourNumber }: { session: LiveSession; tone: number; yourNumber: number | null }) {
  const waiting = session.numbers_to_see.length;
  const open = session.status === "not_started" || session.status === "in_progress";
  return (
    <article className={`live-card card ${yourNumber ? "is-yours" : ""} status-${session.status}`}>
      <header className="live-card-head">
        <Avatar name={session.doctor_name} size={42} tone={tone} />
        <div>
          <strong>{session.doctor_name}</strong>
          <span className="muted small">
            {formatTime(session.start_at)} – {formatTime(session.end_at)} session
          </span>
        </div>
        <span className={`chip ${session.status === "in_progress" ? "chip-green" : ""}`}>
          {session.status === "in_progress" && <span className="live-dot" />} {STATUS_LABEL[session.status]}
        </span>
      </header>

      {session.status === "in_progress" ? (
        <div className="live-now">
          <small>{session.now_serving ? "Now seeing" : "Between patients"}</small>
          <strong className="queue-num">
            {session.now_serving ? `No. ${session.now_serving}` : "—"}
          </strong>
        </div>
      ) : (
        <p className="live-note">
          {session.status === "not_started"
            ? `Starts at ${formatTime(session.start_at)}.`
            : session.status === "ended"
              ? session.doctor_left_at
                ? `This session has ended. The doctor left at ${formatTime(session.doctor_left_at)}.`
                : "This session has ended."
              : "This session is cancelled. If you had a booking, you can move it to another date from Manage booking."}
        </p>
      )}

      {open && (
        <p className="muted small">
          {session.doctor_arrived_at ? `Doctor arrived at ${formatTime(session.doctor_arrived_at)} · ` : ""}
          {waiting === 0 ? "No one waiting." : `${waiting} still to be seen`}
        </p>
      )}
      {yourNumber && open && <YourPlace session={session} number={yourNumber} />}
    </article>
  );
}

export function LivePage() {
  const [params] = useSearchParams();
  const doctorId = Number(params.get("doctor")) || null;
  const startAt = params.get("at");
  const yourNumber = Number(params.get("number")) || null;
  const live = useQuery({ queryKey: ["live-queue"], queryFn: api.liveQueue, refetchInterval: REFRESH_MS });

  const isYours = (session: LiveSession) =>
    session.doctor_id === doctorId && !!startAt && Date.parse(session.start_at) === Date.parse(startAt);
  // Match each doctor's avatar colour on the other public pages.
  const doctors = usePublicDoctors();
  const toneOf = (doctorId: number) => Math.max(doctors.data?.findIndex((doctor) => doctor.id === doctorId) ?? 0, 0) % 6;

  return (
    <div className="container narrow-page">
      <div className="page-intro">
        <span className="eyebrow">
          <span className="live-dot" /> Live queue
        </span>
        <h1>Who's being seen now</h1>
        <p className="muted">
          {live.data ? `${formatDay(live.data.day)}. ` : ""}Updates every 20 seconds. We show numbers only, never names.
        </p>
      </div>

      {live.isLoading ? (
        <Spinner />
      ) : live.isError ? (
        <ErrorNote error={live.error} />
      ) : !live.data?.sessions.length ? (
        <EmptyState
          icon={<CalendarX size={22} />}
          title="No sessions today"
          hint="Please check back on a consulting day."
        />
      ) : (
        <div className="live-grid">
          {live.data.sessions.map((session) => (
            <LiveCard
              key={`${session.doctor_id}-${session.start_at}`}
              session={session}
              tone={toneOf(session.doctor_id)}
              yourNumber={isYours(session) ? yourNumber : null}
            />
          ))}
        </div>
      )}

      <p className="muted small live-foot">
        Numbers are seen in order, but someone who arrives late may be seen when they arrive.{" "}
        <Link to="/manage">Find your booking</Link>
      </p>
    </div>
  );
}
