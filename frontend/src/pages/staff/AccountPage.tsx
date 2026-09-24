import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { KeyRound, Save } from "lucide-react";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { Avatar, Button, Card, ErrorNote, Field, PageHeader } from "../../components/ui";
import { useToast } from "../../components/Toast";

export function ChangePasswordCard() {
  const { clear } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const mismatch = confirm.length > 0 && next !== confirm;
  const mutation = useMutation({
    mutationFn: () => api.changePassword(current, next),
    onSuccess: () => {
      // The backend revokes every session after a password change.
      clear();
      toast("Password changed. Please sign in again.");
      navigate("/login");
    },
  });
  return (
    <Card title={<><KeyRound size={18} /> Change password</>}>
      <form
        className="stack"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          if (!mismatch) mutation.mutate();
        }}
      >
        <Field label="Current password">
          <input className="input" type="password" value={current} minLength={8} required autoComplete="current-password" onChange={(event) => setCurrent(event.target.value)} />
        </Field>
        <div className="form-grid">
          <Field label="New password" hint="At least 12 characters">
            <input className="input" type="password" value={next} minLength={12} maxLength={128} required autoComplete="new-password" onChange={(event) => setNext(event.target.value)} />
          </Field>
          <Field label="Confirm new password" error={mismatch ? "Passwords don't match." : undefined}>
            <input className="input" type="password" value={confirm} required autoComplete="new-password" onChange={(event) => setConfirm(event.target.value)} />
          </Field>
        </div>
        <ErrorNote error={mutation.error} />
        <div>
          <Button type="submit" loading={mutation.isPending} disabled={mismatch}>
            Update password
          </Button>
        </div>
      </form>
    </Card>
  );
}

function DoctorProfileCard() {
  const { user, refreshUser } = useAuth();
  const toast = useToast();
  const doctor = user!.doctor!;
  const [displayName, setDisplayName] = useState(doctor.display_name);
  const [phone, setPhone] = useState(doctor.phone ?? "");
  const mutation = useMutation({
    mutationFn: () => api.updateMyDoctorProfile({ display_name: displayName.trim(), phone: phone.trim() || null }),
    onSuccess: async () => {
      await refreshUser();
      toast("Profile saved");
    },
  });
  return (
    <Card title="Doctor profile">
      <form
        className="stack"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <div className="form-grid">
          <Field label="Display name" hint="Shown to patients when they book">
            <input className="input" value={displayName} minLength={2} maxLength={100} required onChange={(event) => setDisplayName(event.target.value)} />
          </Field>
          <Field label="Phone" hint="Staff only">
            <input className="input" value={phone} maxLength={30} onChange={(event) => setPhone(event.target.value)} />
          </Field>
        </div>
        <Field label="Registration number" hint="Only an administrator can change this">
          <input className="input mono" value={doctor.registration_number} disabled />
        </Field>
        <ErrorNote error={mutation.error} />
        <div>
          <Button type="submit" icon={<Save size={16} />} loading={mutation.isPending}>
            Save profile
          </Button>
        </div>
      </form>
    </Card>
  );
}

export function AccountPage() {
  const { user } = useAuth();
  if (!user) return null;
  const name = user.doctor?.display_name ?? user.username;
  return (
    <div className="fade-in account-page">
      <PageHeader title="Account" />
      <Card className="account-hero">
        <Avatar name={name} size={64} />
        <div>
          <h2>{name}</h2>
          <span className="muted">
            @{user.username} · {user.role === "administrator" ? "Administrator" : "Doctor"}
          </span>
        </div>
      </Card>
      {user.doctor && <DoctorProfileCard />}
      <ChangePasswordCard />
    </div>
  );
}
