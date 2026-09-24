import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Power, UserPlus, KeyRound, Stethoscope, ShieldCheck, UserRound } from "lucide-react";
import { api, type Doctor, type DoctorProfileInput, type Role, type User } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { Avatar, Button, Card, EmptyState, ErrorNote, Field, Modal, PageHeader, Pagination, Spinner } from "../../components/ui";
import { useToast } from "../../components/Toast";

const ROLE_META: Record<Role, { label: string; icon: typeof ShieldCheck }> = {
  administrator: { label: "Administrator", icon: ShieldCheck },
  doctor: { label: "Doctor", icon: Stethoscope },
  patient: { label: "Patient", icon: UserRound },
};

function DoctorEditModal({ doctor, onClose }: { doctor: Doctor; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    display_name: doctor.display_name,
    registration_number: doctor.registration_number,
    phone: doctor.phone ?? "",
  });
  const mutation = useMutation({
    mutationFn: () =>
      api.updateDoctor(doctor.id, {
        display_name: form.display_name.trim(),
        registration_number: form.registration_number.trim(),
        phone: form.phone.trim() || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin-doctors"] });
      queryClient.invalidateQueries({ queryKey: ["public-doctors"] });
      toast("Doctor profile saved");
      onClose();
    },
  });
  return (
    <Modal open title="Edit doctor profile" onClose={onClose}>
      <form
        className="stack"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <Field label="Display name">
          <input className="input" value={form.display_name} minLength={2} maxLength={100} required onChange={(event) => setForm({ ...form, display_name: event.target.value })} />
        </Field>
        <Field label="Registration number">
          <input className="input mono" value={form.registration_number} minLength={2} maxLength={50} required onChange={(event) => setForm({ ...form, registration_number: event.target.value })} />
        </Field>
        <Field label="Phone" hint="Staff only, never shown publicly">
          <input className="input" value={form.phone} maxLength={30} onChange={(event) => setForm({ ...form, phone: event.target.value })} />
        </Field>
        <ErrorNote error={mutation.error} />
        <div className="modal-foot-inline">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" loading={mutation.isPending}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  );
}

export function DoctorsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Doctor | null>(null);
  const doctors = useQuery({ queryKey: ["admin-doctors"], queryFn: api.allDoctors });
  const toggle = useMutation({
    mutationFn: (doctor: Doctor) => api.updateDoctor(doctor.id, { is_active: !doctor.is_active }),
    onSuccess: (doctor) => {
      queryClient.invalidateQueries({ queryKey: ["admin-doctors"] });
      queryClient.invalidateQueries({ queryKey: ["public-doctors"] });
      toast(`${doctor.display_name} is now ${doctor.is_active ? "taking bookings" : "hidden from booking"}`);
    },
    onError: (error) => toast((error as Error).message, "error"),
  });

  return (
    <div className="fade-in">
      <PageHeader title="Doctors" subtitle="Public profiles and booking visibility. Create new doctors from Accounts." />
      {doctors.isLoading ? (
        <Spinner />
      ) : doctors.isError ? (
        <ErrorNote error={doctors.error} />
      ) : !doctors.data?.length ? (
        <EmptyState title="No doctor profiles" />
      ) : (
        <div className="doctor-admin-grid">
          {doctors.data.map((doctor, index) => (
            <Card key={doctor.id} className={`doctor-admin ${doctor.is_active ? "" : "is-inactive"}`}>
              <div className="doctor-admin-head">
                <Avatar name={doctor.display_name} size={52} tone={index % 6} />
                <div>
                  <h3>{doctor.display_name}</h3>
                  <span className="muted mono small">Reg. {doctor.registration_number}</span>
                </div>
                <span className={`chip ${doctor.is_active ? "chip-green" : ""}`}>{doctor.is_active ? "Active" : "Inactive"}</span>
              </div>
              <p className="muted small">{doctor.phone ?? "No phone on file"}</p>
              <div className="row">
                <Button variant="secondary" size="sm" icon={<Pencil size={14} />} onClick={() => setEditing(doctor)}>
                  Edit
                </Button>
                <Button
                  variant={doctor.is_active ? "ghost" : "primary"}
                  size="sm"
                  icon={<Power size={14} />}
                  loading={toggle.isPending && toggle.variables?.id === doctor.id}
                  onClick={() => toggle.mutate(doctor)}
                >
                  {doctor.is_active ? "Deactivate" : "Activate"}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
      {editing && <DoctorEditModal doctor={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function DoctorProfileFields({ value, onChange, optional }: {
  value: DoctorProfileInput;
  onChange: (value: DoctorProfileInput) => void;
  optional?: boolean;
}) {
  return (
    <div className="form-grid nested-fields">
      <Field label="Doctor display name">
        <input className="input" value={value.display_name} minLength={2} maxLength={100} required={!optional} onChange={(event) => onChange({ ...value, display_name: event.target.value })} />
      </Field>
      <Field label="Registration number">
        <input className="input mono" value={value.registration_number} minLength={2} maxLength={50} required={!optional || Boolean(value.display_name)} onChange={(event) => onChange({ ...value, registration_number: event.target.value })} />
      </Field>
      <Field label="Phone" hint="Optional">
        <input className="input" value={value.phone ?? ""} maxLength={30} onChange={(event) => onChange({ ...value, phone: event.target.value })} />
      </Field>
    </div>
  );
}

const EMPTY_PROFILE: DoctorProfileInput = { display_name: "", registration_number: "", phone: "" };
const cleanProfile = (profile: DoctorProfileInput): DoctorProfileInput => ({
  display_name: profile.display_name.trim(),
  registration_number: profile.registration_number.trim(),
  phone: profile.phone?.trim() || null,
});

function CreateUserModal({ onClose }: { onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("doctor");
  const [profile, setProfile] = useState<DoctorProfileInput>(EMPTY_PROFILE);
  const mutation = useMutation({
    mutationFn: () =>
      api.createUser({
        username: username.trim(),
        password,
        role,
        is_active: true,
        ...(role === "doctor" ? { doctor: cleanProfile(profile) } : {}),
      }),
    onSuccess: (user) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-doctors"] });
      queryClient.invalidateQueries({ queryKey: ["public-doctors"] });
      toast(`Account ${user.username} created`);
      onClose();
    },
  });
  return (
    <Modal open title="Create account" onClose={onClose} wide>
      <form
        className="stack"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <div className="segmented">
          {(Object.keys(ROLE_META) as Role[]).map((value) => {
            const Icon = ROLE_META[value].icon;
            return (
              <button type="button" key={value} className={role === value ? "is-selected" : ""} onClick={() => setRole(value)}>
                <Icon size={16} /> {ROLE_META[value].label}
              </button>
            );
          })}
        </div>
        <div className="form-grid">
          <Field label="Username">
            <input className="input" value={username} pattern="[a-zA-Z0-9_.\-]{3,50}" required onChange={(event) => setUsername(event.target.value)} autoComplete="off" />
          </Field>
          <Field label="Initial password" hint="12–128 characters">
            <input className="input" type="password" value={password} minLength={12} maxLength={128} required onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" />
          </Field>
        </div>
        {role === "doctor" && <DoctorProfileFields value={profile} onChange={setProfile} />}
        <ErrorNote error={mutation.error} />
        <div className="modal-foot-inline">
          <Button type="button" variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" icon={<UserPlus size={16} />} loading={mutation.isPending}>
            Create account
          </Button>
        </div>
      </form>
    </Modal>
  );
}

function EditUserModal({ user, onClose }: { user: User; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [role, setRole] = useState<Role>(user.role);
  const [profile, setProfile] = useState<DoctorProfileInput>(EMPTY_PROFILE);
  const [password, setPassword] = useState("");
  const needsProfile = role === "doctor" && user.role !== "doctor";

  const save = useMutation({
    mutationFn: () =>
      api.updateUser(user.id, { role, ...(needsProfile && profile.display_name ? { doctor: cleanProfile(profile) } : {}) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-doctors"] });
      toast("Role updated. Their sessions were signed out.");
      onClose();
    },
  });
  const reset = useMutation({
    mutationFn: () => api.resetPassword(user.id, password),
    onSuccess: () => {
      setPassword("");
      toast(`Password reset for ${user.username}`);
    },
  });

  return (
    <Modal open title={`Manage ${user.username}`} onClose={onClose} wide>
      <div className="stack">
        <form
          className="stack"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            save.mutate();
          }}
        >
          <h4 className="small-title">Role</h4>
          <div className="segmented">
            {(Object.keys(ROLE_META) as Role[]).map((value) => {
              const Icon = ROLE_META[value].icon;
              return (
                <button type="button" key={value} className={role === value ? "is-selected" : ""} onClick={() => setRole(value)}>
                  <Icon size={16} /> {ROLE_META[value].label}
                </button>
              );
            })}
          </div>
          {needsProfile && (
            <>
              <p className="muted small">
                If this account had a doctor profile before, leave these blank and it'll be reactivated. Otherwise fill them in.
              </p>
              <DoctorProfileFields value={profile} onChange={setProfile} optional />
            </>
          )}
          <ErrorNote error={save.error} />
          <div className="modal-foot-inline">
            <Button type="submit" disabled={role === user.role} loading={save.isPending}>
              Save role
            </Button>
          </div>
        </form>
        <hr className="divider" />
        <form
          className="stack"
          onSubmit={(event: FormEvent) => {
            event.preventDefault();
            reset.mutate();
          }}
        >
          <h4 className="small-title">Reset password</h4>
          <Field label="New password" hint="At least 12 characters. All of their active sessions will be signed out.">
            <input className="input" type="password" value={password} minLength={12} maxLength={128} required onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" />
          </Field>
          <ErrorNote error={reset.error} />
          <div className="modal-foot-inline">
            <Button type="submit" variant="secondary" icon={<KeyRound size={16} />} loading={reset.isPending}>
              Reset password
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
}

const LIMIT = 20;

export function UsersPage() {
  const { user: me } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [role, setRole] = useState<Role | "">("");
  const [offset, setOffset] = useState(0);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<User | null>(null);
  const users = useQuery({
    queryKey: ["users", role, offset],
    queryFn: () => api.users({ role, offset, limit: LIMIT }),
  });
  const toggle = useMutation({
    mutationFn: (user: User) => api.updateUser(user.id, { is_active: !user.is_active }),
    onSuccess: (user) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      queryClient.invalidateQueries({ queryKey: ["admin-doctors"] });
      toast(`${user.username} ${user.is_active ? "enabled" : "disabled"}`);
    },
    onError: (error) => toast((error as Error).message, "error"),
  });

  return (
    <div className="fade-in">
      <PageHeader
        title="Accounts"
        subtitle="Sign-in accounts for administrators, doctors and patients."
        actions={
          <Button icon={<UserPlus size={16} />} onClick={() => setCreating(true)}>
            New account
          </Button>
        }
      />
      <div className="tabs">
        {(["", "administrator", "doctor", "patient"] as const).map((value) => (
          <button
            key={value || "all"}
            className={role === value ? "is-selected" : ""}
            onClick={() => {
              setRole(value);
              setOffset(0);
            }}
          >
            {value ? ROLE_META[value].label + "s" : "All"}
          </button>
        ))}
      </div>
      {users.isLoading ? (
        <Spinner />
      ) : users.isError ? (
        <ErrorNote error={users.error} />
      ) : !users.data?.items.length ? (
        <EmptyState title="No accounts here" />
      ) : (
        <Card className="table-card">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {users.data.items.map((user) => {
                  const Icon = ROLE_META[user.role].icon;
                  return (
                    <tr key={user.id}>
                      <td>
                        <span className="cell-person">
                          <Avatar name={user.username} size={30} />
                          <strong>{user.username}</strong>
                          {user.id === me?.id && <span className="chip">You</span>}
                        </span>
                      </td>
                      <td>
                        <span className={`role-pill role-${user.role}`}>
                          <Icon size={14} /> {ROLE_META[user.role].label}
                        </span>
                      </td>
                      <td>
                        <span className={`chip ${user.is_active ? "chip-green" : ""}`}>{user.is_active ? "Active" : "Disabled"}</span>
                      </td>
                      <td className="align-right">
                        <div className="action-row">
                          <Button size="sm" variant="secondary" icon={<Pencil size={14} />} onClick={() => setEditing(user)}>
                            Manage
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            icon={<Power size={14} />}
                            disabled={user.id === me?.id}
                            loading={toggle.isPending && toggle.variables?.id === user.id}
                            onClick={() => toggle.mutate(user)}
                          >
                            {user.is_active ? "Disable" : "Enable"}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <Pagination offset={offset} limit={LIMIT} total={users.data.total} onChange={setOffset} />
        </Card>
      )}
      {creating && <CreateUserModal onClose={() => setCreating(false)} />}
      {editing && <EditUserModal user={editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
