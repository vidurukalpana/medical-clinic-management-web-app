import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, Footprints, UserPlus } from "lucide-react";
import { api, type Gender, type Patient, type PatientInput } from "../../lib/api";
import { useStaffDoctors } from "../../lib/hooks";
import { clinicDate, formatDay, formatTime } from "../../lib/time";
import { PatientPicker } from "../../components/PatientPicker";
import { SlotPicker } from "../../components/SlotPicker";
import { Button, ErrorNote, Field, Modal } from "../../components/ui";
import { useToast } from "../../components/Toast";

const EMPTY_PATIENT: PatientInput = {
  full_name: "",
  date_of_birth: null,
  gender: "not_specified",
  phone: "",
  address: null,
  emergency_contact: null,
};

export function PatientForm({ initial, submitLabel, busy, error, onSubmit, onCancel }: {
  initial?: Partial<PatientInput>;
  submitLabel: string;
  busy?: boolean;
  error?: unknown;
  onSubmit: (data: PatientInput) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<PatientInput>({ ...EMPTY_PATIENT, ...initial });
  const set = <K extends keyof PatientInput>(key: K, value: PatientInput[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  return (
    <form
      className="stack"
      onSubmit={(event: FormEvent) => {
        event.preventDefault();
        onSubmit({
          ...form,
          full_name: form.full_name.trim(),
          phone: form.phone.trim(),
          address: form.address?.trim() || null,
          emergency_contact: form.emergency_contact?.trim() || null,
        });
      }}
    >
      <div className="form-grid">
        <Field label="Full name">
          <input
            className="input"
            value={form.full_name}
            onChange={(event) => set("full_name", event.target.value)}
            minLength={2}
            maxLength={150}
            required
            autoFocus
          />
        </Field>
        <Field label="Phone">
          <input
            className="input"
            value={form.phone}
            onChange={(event) => set("phone", event.target.value)}
            minLength={7}
            maxLength={30}
            inputMode="tel"
            required
          />
        </Field>
        <Field label="Date of birth" hint="Optional">
          <input
            className="input"
            type="date"
            max={clinicDate()}
            value={form.date_of_birth ?? ""}
            onChange={(event) => set("date_of_birth", event.target.value || null)}
          />
        </Field>
        <Field label="Gender">
          <select className="input" value={form.gender} onChange={(event) => set("gender", event.target.value as Gender)}>
            <option value="not_specified">Not specified</option>
            <option value="female">Female</option>
            <option value="male">Male</option>
            <option value="other">Other</option>
          </select>
        </Field>
      </div>
      <Field label="Address" hint="Optional">
        <textarea
          className="input"
          rows={2}
          value={form.address ?? ""}
          maxLength={1000}
          onChange={(event) => set("address", event.target.value)}
        />
      </Field>
      <Field label="Emergency contact" hint="Optional: name and phone">
        <input
          className="input"
          value={form.emergency_contact ?? ""}
          maxLength={200}
          onChange={(event) => set("emergency_contact", event.target.value)}
        />
      </Field>
      <ErrorNote error={error} />
      <div className="modal-foot-inline">
        <Button type="button" variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" loading={busy}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}

export function RegisterPatientModal({ open, onClose, onCreated }: {
  open: boolean;
  onClose: () => void;
  onCreated?: (patient: Patient) => void;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: api.createPatient,
    onSuccess: (patient) => {
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      toast(`${patient.full_name} registered · ${patient.medical_record_number}`);
      onCreated?.(patient);
      onClose();
    },
  });
  useEffect(() => {
    if (open) mutation.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);
  return (
    <Modal open={open} title="Register a patient" onClose={onClose} wide>
      {open && (
        <PatientForm
          submitLabel="Register patient"
          busy={mutation.isPending}
          error={mutation.error}
          onSubmit={(data) => mutation.mutate(data)}
          onCancel={onClose}
        />
      )}
    </Modal>
  );
}

export function DoctorSelect({ value, onChange, allowAll }: {
  value: number | null;
  onChange: (id: number | null) => void;
  allowAll?: boolean;
}) {
  const { doctors } = useStaffDoctors();
  useEffect(() => {
    if (!allowAll && value === null && doctors.length === 1) onChange(doctors[0].id);
  }, [allowAll, value, doctors, onChange]);
  return (
    <select
      className="input"
      value={value ?? ""}
      onChange={(event) => onChange(event.target.value ? Number(event.target.value) : null)}
    >
      {(allowAll || value === null) && <option value="">{allowAll ? "All doctors" : "Select a doctor…"}</option>}
      {doctors.map((doctor) => (
        <option key={doctor.id} value={doctor.id}>
          {doctor.display_name}
          {doctor.is_active ? "" : " (inactive)"}
        </option>
      ))}
    </select>
  );
}

export function BookAppointmentModal({ open, onClose, initialPatient }: {
  open: boolean;
  onClose: () => void;
  initialPatient?: Patient | null;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [doctorId, setDoctorId] = useState<number | null>(null);
  const [patient, setPatient] = useState<Patient | null>(initialPatient ?? null);
  const [day, setDay] = useState<string | null>(null);
  const [startAt, setStartAt] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setPatient(initialPatient ?? null);
      setStartAt(null);
    }
  }, [open, initialPatient]);

  const mutation = useMutation({
    mutationFn: () => api.createAppointment({ doctor_id: doctorId!, patient_id: patient!.id, start_at: startAt! }),
    onSuccess: (appointment) => {
      queryClient.invalidateQueries();
      toast(`Booked ${patient?.full_name} for ${formatDay(clinicDate(new Date(appointment.start_at)), "short")}, ${formatTime(appointment.start_at)}`);
      onClose();
    },
  });

  return (
    <Modal
      open={open}
      wide
      title="Book an appointment"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            icon={<CalendarPlus size={16} />}
            disabled={!doctorId || !patient || !startAt}
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Book {startAt ? formatTime(startAt) : ""}
          </Button>
        </>
      }
    >
      <div className="stack">
        <div className="form-grid">
          <Field label="Doctor">
            <DoctorSelect
              value={doctorId}
              onChange={(id) => {
                setDoctorId(id);
                setStartAt(null);
              }}
            />
          </Field>
          <Field label="Patient">
            <PatientPicker value={patient} onChange={setPatient} />
          </Field>
        </div>
        {doctorId && (
          <SlotPicker
            doctorId={doctorId}
            day={day}
            onDayChange={(next) => {
              setDay(next);
              setStartAt(null);
            }}
            value={startAt}
            onChange={(slot) => setStartAt(slot.start_at)}
          />
        )}
        <ErrorNote error={mutation.error} />
      </div>
    </Modal>
  );
}

export function WalkInModal({ open, onClose, initialPatient }: {
  open: boolean;
  onClose: () => void;
  initialPatient?: Patient | null;
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [doctorId, setDoctorId] = useState<number | null>(null);
  const [patient, setPatient] = useState<Patient | null>(initialPatient ?? null);

  useEffect(() => {
    if (open) setPatient(initialPatient ?? null);
  }, [open, initialPatient]);

  const mutation = useMutation({
    mutationFn: () => api.walkIn(doctorId!, patient!.id),
    onSuccess: (visit) => {
      queryClient.invalidateQueries();
      toast(`${patient?.full_name} added to the queue as #${visit.queue_number}${visit.start_at ? ` (${formatTime(visit.start_at)})` : ""}`);
      onClose();
    },
  });

  return (
    <Modal
      open={open}
      title="Add a walk-in"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            icon={<Footprints size={16} />}
            disabled={!doctorId || !patient}
            loading={mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            Add to queue
          </Button>
        </>
      }
    >
      <div className="stack">
        <p className="muted">The patient gets the doctor's next free slot today and joins the live queue.</p>
        <Field label="Doctor">
          <DoctorSelect value={doctorId} onChange={setDoctorId} />
        </Field>
        <Field label="Patient">
          <PatientPicker value={patient} onChange={setPatient} />
        </Field>
        <ErrorNote error={mutation.error} />
      </div>
    </Modal>
  );
}

export function QuickActionButtons() {
  const [modal, setModal] = useState<"register" | "book" | "walkin" | null>(null);
  const close = () => setModal(null);
  return (
    <>
      <div className="quick-actions">
        <button className="quick-action qa-teal" onClick={() => setModal("register")}>
          <span>
            <UserPlus size={20} />
          </span>
          <strong>Register patient</strong>
          <small>Create a medical record</small>
        </button>
        <button className="quick-action qa-violet" onClick={() => setModal("book")}>
          <span>
            <CalendarPlus size={20} />
          </span>
          <strong>Book appointment</strong>
          <small>Reserve a future slot</small>
        </button>
        <button className="quick-action qa-coral" onClick={() => setModal("walkin")}>
          <span>
            <Footprints size={20} />
          </span>
          <strong>Add walk-in</strong>
          <small>Queue for the next free slot</small>
        </button>
      </div>
      <RegisterPatientModal open={modal === "register"} onClose={close} />
      <BookAppointmentModal open={modal === "book"} onClose={close} />
      <WalkInModal open={modal === "walkin"} onClose={close} />
    </>
  );
}
