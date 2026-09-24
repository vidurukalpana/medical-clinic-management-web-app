import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, Trash2, CalendarOff, Clock3, Plane } from "lucide-react";
import { api, type Availability, type AvailabilityInput } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useStaffDoctors } from "../../lib/hooks";
import { formatClock, formatDateTime, isoToLocalInput, localInputToIso, weekdayName } from "../../lib/time";
import { Button, Card, EmptyState, ErrorNote, Field, Modal, PageHeader, Spinner } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { DoctorSelect } from "./QuickActions";

const WEEKDAYS = [0, 1, 2, 3, 4];

function minutesBetween(start: string, end: string) {
  const toMinutes = (value: string) => {
    const [h, m] = value.split(":").map(Number);
    return h * 60 + m;
  };
  return toMinutes(end) - toMinutes(start);
}

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
          slot_duration_minutes: editing.slot_duration_minutes,
          is_active: editing.is_active,
        }
      : { weekday: defaultWeekday, start_time: "09:00", end_time: "12:00", slot_duration_minutes: 10, is_active: true },
  );
  const mutation = useMutation({
    mutationFn: () =>
      editing ? api.replaceAvailability(doctorId, editing.id, form) : api.addAvailability(doctorId, form),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["availability", doctorId] });
      queryClient.invalidateQueries({ queryKey: ["slots"] });
      queryClient.invalidateQueries({ queryKey: ["booking-status"] });
      toast(editing ? "Session updated" : "Session added");
      onClose();
    },
  });
  const span = minutesBetween(form.start_time, form.end_time);
  const slots = span > 0 ? Math.floor(span / form.slot_duration_minutes) : 0;

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
        <Field label="Minutes per patient" hint={slots > 0 ? `${slots} appointment slots in this session` : "End must be after start"}>
          <input
            className="input"
            type="number"
            min={5}
            max={240}
            value={form.slot_duration_minutes}
            onChange={(event) => setForm({ ...form, slot_duration_minutes: Number(event.target.value) })}
            required
          />
        </Field>
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
      queryClient.invalidateQueries({ queryKey: ["slots"] });
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
      queryClient.invalidateQueries({ queryKey: ["slots"] });
      toast("Session removed");
    },
    onError: (error) => toast((error as Error).message, "error"),
  });
  const removeTimeOff = useMutation({
    mutationFn: (id: number) => api.deleteUnavailability(doctorId!, id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["unavailability", doctorId] });
      queryClient.invalidateQueries({ queryKey: ["slots"] });
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
                            {session.slot_duration_minutes} min slots ·{" "}
                            {Math.floor(minutesBetween(session.start_time, session.end_time) / session.slot_duration_minutes)} patients
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
