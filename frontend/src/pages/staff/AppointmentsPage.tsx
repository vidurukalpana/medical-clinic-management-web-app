import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CalendarPlus, LogIn, UserX, XCircle, Filter } from "lucide-react";
import { api, type Appointment, type AppointmentStatus } from "../../lib/api";
import { usePatientName, useStaffDoctors } from "../../lib/hooks";
import { clinicDate, formatDay, formatTime, addDays } from "../../lib/time";
import { RescheduleModal } from "../../components/BookingPieces";
import { Button, Card, EmptyState, ErrorNote, Field, PageHeader, Pagination, Spinner, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { BookAppointmentModal, DoctorSelect } from "./QuickActions";

const LIMIT = 20;

function PatientCell({ id }: { id: number }) {
  const name = usePatientName(id);
  return <span>{name ?? <span className="muted">Patient #{id}</span>}</span>;
}

function RowActions({ appointment, onReschedule }: { appointment: Appointment; onReschedule: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const mutation = useMutation({
    mutationFn: (kind: "cancel" | "no-show" | "check-in"): Promise<unknown> =>
      kind === "cancel"
        ? api.cancelAppointment(appointment.id)
        : kind === "no-show"
          ? api.noShowAppointment(appointment.id)
          : api.checkIn(appointment.id),
    onSuccess: (_, kind) => {
      queryClient.invalidateQueries();
      toast(kind === "check-in" ? "Checked in to the queue" : kind === "cancel" ? "Appointment cancelled" : "Marked as no-show");
    },
    onError: (error) => toast((error as Error).message, "error"),
  });
  if (appointment.status !== "scheduled") return null;
  const now = Date.now();
  const ended = new Date(appointment.end_at).getTime() <= now;
  const today = clinicDate(new Date(appointment.start_at)) === clinicDate();
  const busy = (kind: string) => mutation.isPending && mutation.variables === kind;
  return (
    <div className="action-row">
      {today && (
        <Button size="sm" icon={<LogIn size={14} />} loading={busy("check-in")} onClick={() => mutation.mutate("check-in")}>
          Check in
        </Button>
      )}
      {!ended && (
        <Button size="sm" variant="secondary" icon={<CalendarClock size={14} />} onClick={onReschedule}>
          Move
        </Button>
      )}
      {ended && (
        <Button size="sm" variant="secondary" icon={<UserX size={14} />} loading={busy("no-show")} onClick={() => mutation.mutate("no-show")}>
          No-show
        </Button>
      )}
      <Button
        size="sm"
        variant="ghost"
        icon={<XCircle size={14} />}
        loading={busy("cancel")}
        onClick={() => window.confirm(`Cancel appointment #${appointment.id}?`) && mutation.mutate("cancel")}
      >
        Cancel
      </Button>
    </div>
  );
}

export function AppointmentsPage() {
  const { names } = useStaffDoctors();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [doctorId, setDoctorId] = useState<number | null>(null);
  const [status, setStatus] = useState<AppointmentStatus | "">("scheduled");
  const [dateFrom, setDateFrom] = useState(clinicDate());
  const [dateTo, setDateTo] = useState(addDays(clinicDate(), 14));
  const [offset, setOffset] = useState(0);
  const [moving, setMoving] = useState<Appointment | null>(null);
  const [booking, setBooking] = useState(false);

  const filters = { doctor_id: doctorId ?? undefined, status, date_from: dateFrom, date_to: dateTo, offset, limit: LIMIT };
  const page = useQuery({ queryKey: ["appointments", filters], queryFn: () => api.appointments(filters) });

  const reschedule = useMutation({
    mutationFn: (startAt: string) => api.rescheduleAppointment(moving!.id, startAt),
    onSuccess: () => {
      setMoving(null);
      queryClient.invalidateQueries();
      toast("Appointment moved");
    },
    onError: (error) => toast((error as Error).message, "error"),
  });

  const update = (fn: () => void) => {
    fn();
    setOffset(0);
  };

  // Group rows by clinic-local day for a calendar-like reading.
  const groups: [string, Appointment[]][] = [];
  for (const appointment of page.data?.items ?? []) {
    const day = clinicDate(new Date(appointment.start_at));
    const last = groups[groups.length - 1];
    if (last && last[0] === day) last[1].push(appointment);
    else groups.push([day, [appointment]]);
  }

  return (
    <div className="fade-in">
      <PageHeader
        title="Appointments"
        subtitle="Search, move, check in or close out bookings."
        actions={
          <Button icon={<CalendarPlus size={16} />} onClick={() => setBooking(true)}>
            New appointment
          </Button>
        }
      />

      <Card className="filters">
        <Filter size={16} className="muted" />
        <Field label="Doctor">
          <DoctorSelect value={doctorId} onChange={(id) => update(() => setDoctorId(id))} allowAll />
        </Field>
        <Field label="Status">
          <select
            className="input"
            value={status}
            onChange={(event) => update(() => setStatus(event.target.value as AppointmentStatus | ""))}
          >
            <option value="">Any status</option>
            <option value="scheduled">Scheduled</option>
            <option value="completed">Completed</option>
            <option value="cancelled">Cancelled</option>
            <option value="no_show">No-show</option>
          </select>
        </Field>
        <Field label="From">
          <input className="input" type="date" value={dateFrom} onChange={(event) => update(() => setDateFrom(event.target.value))} />
        </Field>
        <Field label="To">
          <input className="input" type="date" value={dateTo} onChange={(event) => update(() => setDateTo(event.target.value))} />
        </Field>
      </Card>

      {page.isLoading ? (
        <Spinner />
      ) : page.isError ? (
        <ErrorNote error={page.error} />
      ) : !page.data?.items.length ? (
        <EmptyState icon={<CalendarPlus size={22} />} title="No appointments match these filters" />
      ) : (
        <Card className="table-card">
          {groups.map(([day, items]) => (
            <div key={day} className="day-group">
              <div className="day-group-head">
                <strong>{formatDay(day)}</strong>
                <span className="muted small">{items.length} shown</span>
              </div>
              <div className="table-wrap">
                <table className="table">
                  <tbody>
                    {items.map((appointment) => (
                      <tr key={appointment.id}>
                        <td className="nowrap">
                          <strong>{formatTime(appointment.start_at)}</strong>
                          <span className="muted small"> – {formatTime(appointment.end_at)}</span>
                        </td>
                        <td>
                          <PatientCell id={appointment.patient_id} />
                        </td>
                        <td className="muted">{names.get(appointment.doctor_id) ?? `Doctor #${appointment.doctor_id}`}</td>
                        <td>
                          <StatusBadge status={appointment.status} />
                        </td>
                        <td className="muted mono small">#{appointment.id}</td>
                        <td className="align-right">
                          <RowActions appointment={appointment} onReschedule={() => setMoving(appointment)} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          <Pagination offset={offset} limit={LIMIT} total={page.data.total} onChange={setOffset} />
        </Card>
      )}

      {moving && (
        <RescheduleModal
          open
          doctorId={moving.doctor_id}
          onClose={() => setMoving(null)}
          busy={reschedule.isPending}
          onConfirm={(slot) => reschedule.mutate(slot.start_at)}
        />
      )}
      <BookAppointmentModal open={booking} onClose={() => setBooking(false)} />
    </div>
  );
}
