import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, UserPlus, Phone, Cake, MapPin, Contact, CalendarPlus, Footprints, Pencil, Users } from "lucide-react";
import { api, type Patient } from "../../lib/api";
import { useDebounced, useStaffDoctors } from "../../lib/hooks";
import { formatDateTime } from "../../lib/time";
import { Avatar, Button, Card, EmptyState, ErrorNote, Modal, PageHeader, Pagination, Spinner, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { BookAppointmentModal, PatientForm, RegisterPatientModal, WalkInModal } from "./QuickActions";

const LIMIT = 20;
const GENDER_LABEL = { female: "Female", male: "Male", other: "Other", not_specified: "Not specified" } as const;

function age(dob: string | null): string | null {
  if (!dob) return null;
  const birth = new Date(`${dob}T00:00:00`);
  const now = new Date();
  let years = now.getFullYear() - birth.getFullYear();
  if (now < new Date(now.getFullYear(), birth.getMonth(), birth.getDate())) years -= 1;
  return `${years} yrs`;
}

function PatientDetail({ patient, onClose }: { patient: Patient; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { names } = useStaffDoctors();
  const [editing, setEditing] = useState(false);
  const [modal, setModal] = useState<"book" | "walkin" | null>(null);
  const history = useQuery({
    queryKey: ["appointments", { patient_id: patient.id, limit: 100 }],
    queryFn: () => api.appointments({ patient_id: patient.id, limit: 100 }),
  });
  const update = useMutation({
    mutationFn: (data: Parameters<typeof api.updatePatient>[1]) => api.updatePatient(patient.id, data),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["patients"] });
      queryClient.setQueryData(["patient", updated.id], updated);
      toast("Patient details saved");
      setEditing(false);
      onClose();
    },
  });

  const recent = [...(history.data?.items ?? [])].reverse().slice(0, 5);

  return (
    <Modal open title={editing ? "Edit patient" : "Patient profile"} onClose={onClose} wide>
      {editing ? (
        <PatientForm
          initial={patient}
          submitLabel="Save changes"
          busy={update.isPending}
          error={update.error}
          onSubmit={(data) => update.mutate(data)}
          onCancel={() => setEditing(false)}
        />
      ) : (
        <div className="stack">
          <div className="profile-head">
            <Avatar name={patient.full_name} size={60} />
            <div>
              <h2>{patient.full_name}</h2>
              <span className="chip mono">{patient.medical_record_number}</span>
            </div>
            <Button variant="secondary" size="sm" icon={<Pencil size={14} />} onClick={() => setEditing(true)}>
              Edit
            </Button>
          </div>
          <div className="info-grid">
            <div>
              <Phone size={15} /> {patient.phone}
            </div>
            <div>
              <Cake size={15} /> {patient.date_of_birth ? `${patient.date_of_birth} (${age(patient.date_of_birth)})` : "Birth date not recorded"}
            </div>
            <div>
              <Users size={15} /> {GENDER_LABEL[patient.gender]}
            </div>
            <div>
              <Contact size={15} /> {patient.emergency_contact ?? "No emergency contact"}
            </div>
            <div className="span-2">
              <MapPin size={15} /> {patient.address ?? "No address"}
            </div>
          </div>
          <div className="row">
            <Button icon={<CalendarPlus size={16} />} onClick={() => setModal("book")}>
              Book appointment
            </Button>
            <Button variant="accent" icon={<Footprints size={16} />} onClick={() => setModal("walkin")}>
              Add walk-in
            </Button>
          </div>
          <div>
            <h4 className="list-title small-title">Recent appointments</h4>
            {history.isLoading ? (
              <Spinner />
            ) : recent.length ? (
              <ul className="mini-list">
                {recent.map((appointment) => (
                  <li key={appointment.id}>
                    <span>{formatDateTime(appointment.start_at)}</span>
                    <span className="muted">{names.get(appointment.doctor_id) ?? `Doctor #${appointment.doctor_id}`}</span>
                    <StatusBadge status={appointment.status} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">No appointments you can view yet.</p>
            )}
          </div>
        </div>
      )}
      <BookAppointmentModal open={modal === "book"} onClose={() => setModal(null)} initialPatient={patient} />
      <WalkInModal open={modal === "walkin"} onClose={() => setModal(null)} initialPatient={patient} />
    </Modal>
  );
}

export function PatientsPage() {
  const [text, setText] = useState("");
  const [offset, setOffset] = useState(0);
  const [registering, setRegistering] = useState(false);
  const [selected, setSelected] = useState<Patient | null>(null);
  const query = useDebounced(text.trim());
  const page = useQuery({
    queryKey: ["patients", query, offset, LIMIT],
    queryFn: () => api.patients(query, offset, LIMIT),
  });

  return (
    <div className="fade-in">
      <PageHeader
        title="Patients"
        subtitle={page.data ? `${page.data.total} records` : "Medical records"}
        actions={
          <Button icon={<UserPlus size={16} />} onClick={() => setRegistering(true)}>
            Register patient
          </Button>
        }
      />
      <div className="search-bar">
        <Search size={18} />
        <input
          className="input input-lg"
          placeholder="Search by medical record number, name or phone…"
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            setOffset(0);
          }}
          autoFocus
        />
      </div>

      {page.isLoading ? (
        <Spinner />
      ) : page.isError ? (
        <ErrorNote error={page.error} />
      ) : !page.data?.items.length ? (
        <EmptyState
          icon={<Users size={22} />}
          title={query ? "No patients match your search" : "No patients registered yet"}
          hint="Register a patient to create their medical record number."
        />
      ) : (
        <Card className="table-card">
          <div className="table-wrap">
            <table className="table table-hover">
              <thead>
                <tr>
                  <th>Patient</th>
                  <th>MRN</th>
                  <th>Phone</th>
                  <th>Age</th>
                  <th>Registered</th>
                </tr>
              </thead>
              <tbody>
                {page.data.items.map((patient) => (
                  <tr key={patient.id} onClick={() => setSelected(patient)} tabIndex={0} onKeyDown={(event) => event.key === "Enter" && setSelected(patient)}>
                    <td>
                      <span className="cell-person">
                        <Avatar name={patient.full_name} size={32} />
                        <strong>{patient.full_name}</strong>
                      </span>
                    </td>
                    <td className="mono">{patient.medical_record_number}</td>
                    <td>{patient.phone}</td>
                    <td className="muted">{age(patient.date_of_birth) ?? "—"}</td>
                    <td className="muted small">{new Date(patient.created_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination offset={offset} limit={LIMIT} total={page.data.total} onChange={setOffset} />
        </Card>
      )}

      <RegisterPatientModal open={registering} onClose={() => setRegistering(false)} onCreated={setSelected} />
      {selected && <PatientDetail key={selected.id} patient={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
