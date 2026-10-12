import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, CalendarOff, CalendarX2, Clock3, Phone, Plane } from "lucide-react";
import { api, type Availability, type AvailabilityInput, type BookingSession, type SessionCancellation } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useStaffDoctors } from "../../lib/hooks";
import { clinicDate, formatClock, formatDateTime, formatDay, formatTime, isoToLocalInput, localInputToIso, weekdayName } from "../../lib/time";
import { Button, Card, EmptyState, ErrorNote, Field, Modal, PageHeader, Spinner } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { DoctorSelect } from "./QuickActions";

const WEEKDAYS = [0, 1, 2, 3, 4];

function AvailabilityModal({ doctorId, editing, defaultWeekday, onClose }: {
  doctorId: number;
  editing: Availability | null;
  defaultWeekday: number;
  onClose: () => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<AvailabilityInput>(
    editing
      ? {
          weekday: editing.weekday,
          start_time: editing.start_time.slice(0, 5),
          end_time: editing.end_time.slice(0, 5),
          max_patients: editing.max_patients,
          reserved_places: editing.reserved_places,
          is_active: editing.is_active,
        }
      : { weekday: defaultWeekday, start_time: "09:00", end_time: "12:00", max_patients: 20, reserved_places: 0, is_active: true },
  );
  const mutation = useMutation({
    mutationFn: () =>
      editing ? api.replaceAvailability(doctorId, editing.id, form) : api.addAvailability(doctorId, form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["availability", doctorId] });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      queryClient.invalidateQueries({ queryKey: ["booking-status"] });
      toast(editing ? "Session updated" : "Session added");
      onClose();
    },
  });

  return (
    <Modal open title={editing ? "Edit consulting session" : "Add consulting session"} onClose={onClose}>
      <form
        className="stack"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <Field label="Weekday">
          <select
            className="input"
            value={form.weekday}
            onChange={(event) => setForm({ ...form, weekday: Number(event.target.value) })}
          >
            {WEEKDAYS.map((day) => (
              <option key={day} value={day}>
                {weekdayName(day)}
              </option>
            ))}
          </select>
        </Field>
        <div className="form-grid">
          <Field label="Starts">
            <input
              className="input"
              type="time"
              value={form.start_time}
              onChange={(event) => setForm({ ...form, start_time: event.target.value })}
              required
            />
          </Field>
          <Field label="Ends">
            <input
              className="input"
              type="time"
              value={form.end_time}
              onChange={(event) => setForm({ ...form, end_time: event.target.value })}
              required
            />
          </Field>
        </div>
        <div className="form-grid">
          <Field
            label="Patients per session"
            hint={form.end_time > form.start_time ? "Seen in number order: 1, 2, 3…" : "End must be after start"}
          >
            <input
              className="input"
              type="number"
              min={1}
              max={200}
              value={form.max_patients}
              onChange={(event) => setForm({ ...form, max_patients: Number(event.target.value) })}
              required
            />
          </Field>
          <Field
            label="Kept for walk-ins"
            hint={`Online booking can take ${Math.max(form.max_patients - form.reserved_places, 0)} of ${form.max_patients}`}
          >
            <input
              className="input"
              type="number"
              min={0}
              max={form.max_patients}
              value={form.reserved_places}
              onChange={(event) => setForm({ ...form, reserved_places: Number(event.target.value) })}
              required
            />
          </Field>
        </div>
        <label className="check">
          <input
            type="checkbox"
            checked={form.is_active}
            onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
          />
          <span>Open for booking</span>
        </label>
        <ErrorNote error={mutation.error} />
        <div className="modal-foot-inline">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={mutation.isPending}>
            {editing ? "Save session" : "Add session"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

/** One-off cancellation: closes a session on a date and cancels its bookings so patients can move them. */
function CancelSessionCard({ doctorId }: { doctorId: number }) {
  const queryClient = useQueryClient();
  const [day, setDay] = useState(clinicDate());
  const [confirming, setConfirming] = useState<BookingSession | null>(null);
  const [reason, setReason] = useState("");
  const [result, setResult] = useState<SessionCancellation | null>(null);
  const sessions = useQuery({
    queryKey: ["sessions", doctorId, day],
    queryFn: () => api.sessions(doctorId, day),
    enabled: !!day,
  });
  const mutation = useMutation({
    mutationFn: (session: BookingSession) => api.cancelSession(doctorId, session.start_at, reason.trim() || null),
    onSuccess: (cancellation) => {
      queryClient.invalidateQueries();
      setConfirming(null);
      setReason("");
      setResult(cancellation);
    },
  });
  const booked = (session: BookingSession) => session.max_patients - session.remaining;

  return (
    <Card title={<><CalendarX2 size={18} /> Cancel a session</>} className="mt">
      <p className="muted small">
        For a one-off change, such as the doctor being unwell. Booked patients see the cancellation and can move to
        another date. Please call them too.
      </p>
      <div className="cancel-session">
        <Field label="Date">
          <input className="input" type="date" value={day} min={clinicDate()} onChange={(event) => setDay(event.target.value)} />
        </Field>
        <div className="cancel-session-list">
          {sessions.isLoading ? (
            <Spinner />
          ) : sessions.isError ? (
            <ErrorNote error={sessions.error} />
          ) : !sessions.data?.length ? (
            <p className="muted small">No open sessions on this date.</p>
          ) : (
            sessions.data.map((session) => (
              <div key={session.start_at} className="cancel-session-item">
                <span>
                  <strong>
                    {formatTime(session.start_at)} – {formatTime(session.end_at)}
                  </strong>
                  <span className="muted small"> · {booked(session)} booked</span>
                </span>
                <Button size="sm" variant="danger" onClick={() => setConfirming(session)}>
                  Cancel session
                </Button>
              </div>
            ))
          )}
        </div>
      </div>

      {confirming && (
        <Modal open title="Cancel this session?" onClose={() => setConfirming(null)}>
          <div className="stack">
            <p>
              {formatDay(day)}, {formatTime(confirming.start_at)} – {formatTime(confirming.end_at)}.{" "}
              {booked(confirming) > 0
                ? `${booked(confirming)} booked patients will be cancelled and asked to choose another date.`
                : "No one is booked yet."}
            </p>
            <Field label="Reason" hint="Optional, visible to staff only">
              <input className="input" value={reason} maxLength={255} onChange={(event) => setReason(event.target.value)} placeholder="Doctor unwell…" />
            </Field>
            <ErrorNote error={mutation.error} />
            <div className="modal-foot-inline">
              <Button type="button" variant="ghost" onClick={() => setConfirming(null)}>
                Keep session
              </Button>
              <Button variant="danger" loading={mutation.isPending} onClick={() => mutation.mutate(confirming)}>
                Cancel session
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {result && (
        <Modal open title="Session cancelled" onClose={() => setResult(null)}>
          <div className="stack">
            {result.affected.length === 0 ? (
              <p>No one was booked, so there's no one to contact.</p>
            ) : (
              <>
                <p>Please let these patients know. They can also move their booking online.</p>
                <ul className="affected-list">
                  {result.affected.map((item) => (
                    <li key={item.appointment_id}>
                      <span className="queue-num-sm">No. {item.appointment_number}</span>
                      <strong>{item.patient_name}</strong>
                      <a href={`tel:${item.phone.replace(/[^+0-9]/g, "")}`} className="muted">
                        <Phone size={14} /> {item.phone}
                      </a>
                    </li>
                  ))}
                </ul>
              </>
            )}
            <div className="modal-foot-inline">
              <Button onClick={() => setResult(null)}>Done</Button>
            </div>
          </div>
        </Modal>
      )}
    </Card>
  );
}

function TimeOffForm({ doctorId }: { doctorId: number }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const now = isoToLocalInput(new Date().toISOString());
  const [start, setStart] = useState(`${now.slice(0, 10)}T08:00`);
  const [end, setEnd] = useState(`${now.slice(0, 10)}T17:00`);
  const [reason, setReason] = useState("");
  const mutation = useMutation({
    mutationFn: () =>
      api.addUnavailability(doctorId, {
        start_at: localInputToIso(start),
        end_at: localInputToIso(end),
        reason: reason.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["unavailability", doctorId] });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      queryClient.invalidateQueries({ queryKey: ["booking-status"] });
      setReason("");
      toast("Time off added");
    },
  });
  return (
    <form
      className="timeoff-form"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <Field label="From">
        <input className="input" type="datetime-local" value={start} onChange={(event) => setStart(event.target.value)} required />
      </Field>
      <Field label="Until">
        <input className="input" type="datetime-local" value={end} onChange={(event) => setEnd(event.target.value)} required />
      </Field>
      <Field label="Reason" hint="Optional, visible to staff only">
        <input className="input" value={reason} maxLength={255} onChange={(event) => setReason(event.target.value)} placeholder="Conference, leave…" />
      </Field>
      <Button type="submit" icon={<Plus size={16} />} loading={mutation.isPending}>
        Block time
      </Button>
      <div className="span-all">
        <ErrorNote error={mutation.error} />
      </div>
    </form>
  );
}

export function SchedulePage() {
  const { user, isAdmin } = useAuth();
  const { doctors } = useStaffDoctors();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [chosen, setChosen] = useState<number | null>(null);
  const doctorId = chosen ?? (isAdmin ? doctors[0]?.id ?? null : user?.doctor?.id ?? null);
  const [modal, setModal] = useState<{ editing: Availability | null; weekday: number } | null>(null);

  const availability = useQuery({
    queryKey: ["availability", doctorId],
    queryFn: () => api.availability(doctorId!),
    enabled: doctorId !== null,
  });
  const timeOff = useQuery({
    queryKey: ["unavailability", doctorId],
    queryFn: () => api.unavailability(doctorId!),
    enabled: doctorId !== null,
  });

  const removeSession = useMutation({
    mutationFn: (id: number) => api.deleteAvailability(doctorId!, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["availability", doctorId] });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      toast("Session removed");
    },
    onError: (error) => toast((error as Error).message, "error"),
  });
  const removeTimeOff = useMutation({
    mutationFn: (id: number) => api.deleteUnavailability(doctorId!, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["unavailability", doctorId] });
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      toast("Time off removed");
    },
    onError: (error) => toast((error as Error).message, "error"),
  });

  const upcomingTimeOff = (timeOff.data ?? []).filter((item) => new Date(item.end_at).getTime() > Date.now());

  return (
    <div className="fade-in">
      <PageHeader
        title="Schedule"
        subtitle="Weekly consulting sessions and time off. Changes that would strand booked patients are rejected."
        actions={
          isAdmin ? (
            <div className="dash-filter">
              <DoctorSelect value={doctorId} onChange={setChosen} />
            </div>
          ) : undefined
        }
      />

      {doctorId === null ? (
        <EmptyState title="No doctor profile to schedule" />
      ) : (
        <>
          <Card title={<><Clock3 size={18} /> Weekly sessions</>}>
            {availability.isLoading ? (
              <Spinner />
            ) : availability.isError ? (
              <ErrorNote error={availability.error} />
            ) : (
              <div className="week-grid">
                {WEEKDAYS.map((day) => {
                  const sessions = (availability.data ?? [])
                    .filter((item) => item.weekday === day)
                    .sort((a, b) => a.start_time.localeCompare(b.start_time));
                  return (
                    <div key={day} className="week-col">
                      <div className="week-col-head">
                        <strong>{weekdayName(day)}</strong>
                        <button className="icon-btn" aria-label={`Add session on ${weekdayName(day)}`} onClick={() => setModal({ editing: null, weekday: day })}>
                          <Plus size={16} />
                        </button>
                      </div>
                      {sessions.length === 0 && <span className="week-empty">Not consulting</span>}
                      {sessions.map((session) => (
                        <div key={session.id} className={`session ${session.is_active ? "" : "is-paused"}`}>
                          <strong>
                            {formatClock(session.start_time)} – {formatClock(session.end_time)}
                          </strong>
                          <span className="small">
                            Up to {session.max_patients} patients
                            {session.reserved_places > 0 && ` · ${session.reserved_places} kept for walk-ins`}
                          </span>
                          {!session.is_active && <span className="chip">Paused</span>}
                          <div className="session-tools">
                            <button className="icon-btn" aria-label="Edit session" onClick={() => setModal({ editing: session, weekday: day })}>
                              <Pencil size={14} />
                            </button>
                            <button
                              className="icon-btn"
                              aria-label="Remove session"
                              onClick={() => window.confirm("Remove this session?") && removeSession.mutate(session.id)}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          <CancelSessionCard doctorId={doctorId} />

          <Card title={<><Plane size={18} /> Time off</>} className="mt">
            <TimeOffForm doctorId={doctorId} />
            {timeOff.isLoading ? (
              <Spinner />
            ) : upcomingTimeOff.length ? (
              <ul className="timeoff-list">
                {upcomingTimeOff.map((item) => (
                  <li key={item.id}>
                    <CalendarOff size={16} />
                    <span>
                      <strong>
                        {formatDateTime(item.start_at)} → {formatDateTime(item.end_at)}
                      </strong>
                      {item.reason && <span className="muted"> · {item.reason}</span>}
                    </span>
                    <button
                      className="icon-btn"
                      aria-label="Remove time off"
                      onClick={() => window.confirm("Remove this time off?") && removeTimeOff.mutate(item.id)}
                    >
                      <Trash2 size={15} />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No upcoming time off.</p>
            )}
          </Card>
        </>
      )}

      {modal && doctorId !== null && (
        <AvailabilityModal
          doctorId={doctorId}
          editing={modal.editing}
          defaultWeekday={modal.weekday}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}
