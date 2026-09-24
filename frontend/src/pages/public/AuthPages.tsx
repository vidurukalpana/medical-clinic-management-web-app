import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { LogIn, UserPlus, Lock, UserRound, HeartPulse, ShieldCheck, CalendarCheck2 } from "lucide-react";
import { api } from "../../lib/api";
import { homePathFor, useAuth } from "../../lib/auth";
import { Button, ErrorNote, Field } from "../../components/ui";
import { useToast } from "../../components/Toast";

function AuthShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="auth-page">
      <div className="auth-art">
        <div className="auth-art-inner">
          <HeartPulse size={40} />
          <h2>Care that runs on time.</h2>
          <ul>
            <li>
              <CalendarCheck2 size={18} /> Live queues and today's appointments at a glance
            </li>
            <li>
              <ShieldCheck size={18} /> Role-based access for doctors and administrators
            </li>
            <li>
              <UserRound size={18} /> Patients can keep all their bookings in one place
            </li>
          </ul>
        </div>
      </div>
      <div className="auth-form-wrap">
        <div className="auth-form card fade-in">
          <h1>{title}</h1>
          <p className="muted">{subtitle}</p>
          {children}
        </div>
      </div>
    </div>
  );
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const from = (location.state as { from?: string } | null)?.from;

  const mutation = useMutation({
    mutationFn: () => login(username.trim(), password),
    onSuccess: (signedIn) => {
      const target = from && (signedIn.role !== "patient" || !from.startsWith("/staff")) ? from : homePathFor(signedIn);
      navigate(target, { replace: true });
    },
  });

  if (user && !mutation.isPending) return <Navigate to={homePathFor(user)} replace />;

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to the staff portal or your patient account.">
      <form
        className="stack"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          mutation.mutate();
        }}
      >
        <Field label="Username">
          <div className="input-icon">
            <UserRound size={16} />
            <input
              className="input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              autoFocus
              required
            />
          </div>
        </Field>
        <Field label="Password">
          <div className="input-icon">
            <Lock size={16} />
            <input
              className="input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              minLength={8}
              required
            />
          </div>
        </Field>
        <ErrorNote error={mutation.error} />
        <Button type="submit" size="lg" loading={mutation.isPending} icon={<LogIn size={18} />}>
          Sign in
        </Button>
      </form>
      <p className="auth-switch muted">
        New patient? <Link to="/register">Create an account</Link> to keep your bookings together. You can also{" "}
        <Link to="/book">book without an account</Link>.
      </p>
    </AuthShell>
  );
}

export function RegisterPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  const mismatch = confirm.length > 0 && confirm !== password;
  const mutation = useMutation({
    mutationFn: async () => {
      await api.registerPatient(username.trim(), password);
      return login(username.trim(), password);
    },
    onSuccess: () => {
      toast("Account created. Welcome!");
      navigate("/my-bookings", { replace: true });
    },
  });

  if (user && !mutation.isPending) return <Navigate to={homePathFor(user)} replace />;

  return (
    <AuthShell title="Create a patient account" subtitle="Optional: keep every booking you make in one place.">
      <form
        className="stack"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          if (!mismatch) mutation.mutate();
        }}
      >
        <Field label="Username" hint="3–50 characters: letters, numbers, dots, dashes or underscores.">
          <input
            className="input"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            pattern="[a-zA-Z0-9_.\-]{3,50}"
            autoComplete="username"
            required
          />
        </Field>
        <Field label="Password" hint="At least 12 characters.">
          <input
            className="input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={12}
            maxLength={128}
            autoComplete="new-password"
            required
          />
        </Field>
        <Field label="Confirm password" error={mismatch ? "Passwords don't match." : undefined}>
          <input
            className="input"
            type="password"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            autoComplete="new-password"
            required
          />
        </Field>
        <ErrorNote error={mutation.error} />
        <Button type="submit" size="lg" loading={mutation.isPending} disabled={mismatch} icon={<UserPlus size={18} />}>
          Create account
        </Button>
      </form>
      <p className="auth-switch muted">
        Already registered? <Link to="/login">Sign in</Link>
      </p>
    </AuthShell>
  );
}
