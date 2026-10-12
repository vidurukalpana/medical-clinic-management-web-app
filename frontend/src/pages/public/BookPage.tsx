import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Copy,
  KeyRound,
  Phone,
  Stethoscope,
  UserRound,
  CalendarDays,
  Clock,
  Download,
  Search,
} from "lucide-react";
import { api, type BookingSession, type GuestBookingConfirmation, type PublicDoctor } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { usePublicDoctors } from "../../lib/hooks";
import { describeWeek, matchesSearch } from "../../lib/doctors";
import { saveBooking } from "../../lib/savedBookings";
import { clinicDate, formatDay, formatTime, liveQueueLink } from "../../lib/time";
import { SessionPicker } from "../../components/SessionPicker";
import { CheckInQr } from "../../components/CheckInQr";
import { formatCheckinCode } from "../../lib/checkin";
import { Avatar, Button, EmptyState, ErrorNote, Field, Spinner } from "../../components/ui";
import { useToast } from "../../components/Toast";

const STEPS = ["Doctor", "Date", "Your details"];
const PHONE_PATTERN = /^\+?[0-9][0-9 ()-]{5,28}[0-9]$/;

function Stepper({ step }: { step: number }) {
  return (
    <ol className="stepper">
      {STEPS.map((label, index) => (
        <li key={label} className={index < step ? "is-done" : index === step ? "is-current" : ""}>
          <span className="stepper-dot">{index < step ? <Check size={14} /> : index + 1}</span>
          <span className="stepper-label">{label}</span>
        </li>
      ))}
    </ol>
  );
}

export function BookPage() {
  const [params] = useSearchParams();
  const doctors = usePublicDoctors();
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();

  const preselected = Number(params.get("doctor")) || null;
  const [doctorId, setDoctorId] = useState<number | null>(preselected);
  const [step, setStep] = useState(preselected ? 1 : 0);
  const [day, setDay] = useState<string | null>(null);
  const [session, setSession] = useState<BookingSession | null>(null);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [remember, setRemember] = useState(false);
  const [confirmation, setConfirmation] = useState<GuestBookingConfirmation | null>(null);
  const [doctorQuery, setDoctorQuery] = useState("");

  const doctor = doctors.data?.find((item) => item.id === doctorId) ?? null;

  const book = useMutation({
    mutationFn: () =>
      api.bookAsGuest({ doctor_id: doctorId!, start_at: session!.start_at, full_name: fullName.trim(), phone: phone.trim() }),
    onSuccess: (result) => {
      setConfirmation(result);
      if (remember) {
        saveBooking({
          id: result.id,
          token: result.management_token,
          label: `${doctor?.display_name ?? "Doctor"} · ${formatDay(clinicDate(new Date(result.start_at)), "short")}`,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      queryClient.invalidateQueries({ queryKey: ["booking-status"] });
      queryClient.invalidateQueries({ queryKey: ["my-appointments"] });
    },
    onError: (error) => {
      // A 409 means the session filled up meanwhile; send the user back to choose again.
      if ((error as { status?: number }).status === 409) {
        setSession(null);
        setStep(1);
        queryClient.invalidateQueries({ queryKey: ["sessions"] });
        queryClient.invalidateQueries({ queryKey: ["booking-status"] });
        toast("That session just filled up. Please pick another date.", "error");
      }
    },
  });

  const phoneValid = PHONE_PATTERN.test(phone.trim());
  const nameValid = fullName.trim().length >= 2;

  if (confirmation) return <Confirmation booking={confirmation} doctor={doctor} remembered={remember} />;

  return (
    <div className="container book-page">
      <div className="book-head">
        <span className="eyebrow">Book a visit</span>
        <h1>Reserve your consultation</h1>
        <Stepper step={step} />
      </div>

      <div className="book-layout">
        <div className="book-main card">
          {step === 0 && (
            <div className="fade-in">
              <h2 className="step-title">Who would you like to see?</h2>
              {doctors.isLoading ? (
                <Spinner />
              ) : doctors.isError ? (
                <ErrorNote error={doctors.error} />
              ) : !doctors.data?.length ? (
                <EmptyState title="No doctors are available for booking" />
              ) : (
                <div className="choice-list">
                  {doctors.data.length > 4 && (
                    <div className="input-icon">
                      <Search size={16} />
                      <input
                        className="input"
                        type="search"
                        value={doctorQuery}
                        placeholder="Search by name or specialty"
                        aria-label="Search doctors"
                        onChange={(event) => setDoctorQuery(event.target.value)}
                      />
                    </div>
                  )}
                  {doctors.data.filter((item) => matchesSearch(item, doctorQuery)).length === 0 && (
                    <EmptyState title="No doctors match" hint="Try another name or specialty." />
                  )}
                  {doctors.data.map((item, index) => !matchesSearch(item, doctorQuery) ? null : (
                    <button
                      type="button"
                      key={item.id}
                      className={`choice ${doctorId === item.id ? "is-selected" : ""}`}
                      onClick={() => {
                        setDoctorId(item.id);
                        setSession(null);
                        setDay(null);
                        setStep(1);
                      }}
                    >
                      <Avatar name={item.display_name} size={48} tone={index % 6} />
                      <span className="choice-text">
                        <strong>{item.display_name}</strong>
                        <span className="doctor-specialty">{item.specialty ?? "Doctor"}</span>
                        {item.weekly_sessions.length > 0 && (
                          <span className="muted small">{describeWeek(item.weekly_sessions)}</span>
                        )}
                      </span>
                      <ArrowRight size={18} className="choice-arrow" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {step === 1 && doctorId && (
            <div className="fade-in">
              <h2 className="step-title">Which day suits you?</h2>
              <SessionPicker
                doctorId={doctorId}
                day={day}
                onDayChange={(next) => {
                  setDay(next);
                  setSession(null);
                }}
                value={session?.start_at ?? null}
                onChange={setSession}
              />
              <div className="step-nav">
                <Button variant="ghost" icon={<ArrowLeft size={16} />} onClick={() => setStep(0)}>
                  Change doctor
                </Button>
                <Button disabled={!session} onClick={() => setStep(2)}>
                  Continue <ArrowRight size={16} />
                </Button>
              </div>
            </div>
          )}

          {step === 2 && (
            <form
              className="fade-in"
              onSubmit={(event: FormEvent) => {
                event.preventDefault();
                if (nameValid && phoneValid) book.mutate();
              }}
            >
              <h2 className="step-title">Just two details</h2>
              <p className="muted">Please don't include medical details.</p>
              <div className="form-grid">
                <Field label="Full name">
                  <div className="input-icon">
                    <UserRound size={16} />
                    <input
                      className="input"
                      value={fullName}
                      onChange={(event) => setFullName(event.target.value)}
                      placeholder="e.g. Nimal Perera"
                      autoComplete="name"
                      maxLength={150}
                      required
                    />
                  </div>
                </Field>
                <Field
                  label="Phone number"
                  error={phone && !phoneValid ? "Enter a valid phone number, e.g. +94 77 123 4567" : undefined}
                >
                  <div className="input-icon">
                    <Phone size={16} />
                    <input
                      className="input"
                      value={phone}
                      onChange={(event) => setPhone(event.target.value)}
                      placeholder="+94 77 123 4567"
                      autoComplete="tel"
                      inputMode="tel"
                      required
                    />
                  </div>
                </Field>
              </div>
              <label className="check">
                <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} />
                <span>Remember on this device</span>
              </label>
              {user?.role === "patient" && (
                <div className="alert alert-info">
                  Signed in as <b>{user.username}</b>. This booking will also appear under My bookings.
                </div>
              )}
              <ErrorNote error={book.error} />
              <div className="step-nav">
                <Button type="button" variant="ghost" icon={<ArrowLeft size={16} />} onClick={() => setStep(1)}>
                  Back
                </Button>
                <Button type="submit" variant="accent" loading={book.isPending} disabled={!nameValid || !phoneValid}>
                  Confirm booking
                </Button>
              </div>
            </form>
          )}
        </div>

        <aside className="book-summary card">
          <h3>Your visit</h3>
          <SummaryRow icon={<Stethoscope size={16} />} label="Doctor" value={doctor?.display_name} />
          <SummaryRow icon={<CalendarDays size={16} />} label="Date" value={day ? formatDay(day) : undefined} />
          <SummaryRow
            icon={<Clock size={16} />}
            label="Session"
            value={session ? `${formatTime(session.start_at)} – ${formatTime(session.end_at)}` : undefined}
          />
        </aside>
      </div>
    </div>
  );
}

function SummaryRow({ icon, label, value }: { icon: ReactNode; label: string; value?: string }) {
  return (
    <div className={`summary-row ${value ? "" : "is-empty"}`}>
      <span className="summary-icon">{icon}</span>
      <span>
        <small>{label}</small>
        <strong>{value ?? "Not selected"}</strong>
      </span>
    </div>
  );
}

function Confirmation({ booking, doctor, remembered }: {
  booking: GuestBookingConfirmation;
  doctor: PublicDoctor | null;
  remembered: boolean;
}) {
  const toast = useToast();
  const [copied, setCopied] = useState(false);
  const day = clinicDate(new Date(booking.start_at));

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(booking.management_token);
      setCopied(true);
      toast("Private code copied");
    } catch {
      toast("Couldn't copy automatically. Select the code and copy it.", "error");
    }
  };

  const download = () => {
    const text = [
      "CareFlow Clinic booking",
      `Booking ID: ${booking.id}`,
      `Your number: ${booking.appointment_number}`,
      `Doctor: ${doctor?.display_name ?? booking.doctor_id}`,
      `When: ${formatDay(day)}, session starts ${formatTime(booking.start_at)}`,
      `Check-in code (show at reception): ${formatCheckinCode(booking.checkin_code)}`,
      `Private code: ${booking.management_token}`,
      "",
      "Keep this code private. It lets anyone view, move or cancel this booking.",
    ].join("\n");
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    const link = Object.assign(document.createElement("a"), { href: url, download: `booking-${booking.id}.txt` });
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="container confirm-page fade-in">
      <div className="confirm-card card">
        <div className="confirm-burst">
          <CheckCircle2 size={44} />
        </div>
        <h1>You're booked!</h1>
        <p className="lead">
          {doctor?.display_name} · <b>{formatDay(day)}</b>
        </p>

        <div className="confirm-grid">
          <div className="confirm-stat confirm-stat-number">
            <small>Your number</small>
            <strong>{booking.appointment_number}</strong>
          </div>
          <div className="confirm-stat">
            <small>Session starts</small>
            <strong>{formatTime(booking.start_at)}</strong>
          </div>
          <div className="confirm-stat">
            <small>Booking ID</small>
            <strong className="mono">#{booking.id}</strong>
          </div>
        </div>
        <p className="muted small">Patients are seen in number order. Please arrive a little before the session starts.</p>

        <CheckInQr code={booking.checkin_code} />

        <div className="token-box">
          <div className="token-head">
            <KeyRound size={16} /> Your private code
            <span className="muted">We show it only once</span>
          </div>
          <code className="token">{booking.management_token}</code>
          <div className="token-actions">
            <Button variant="secondary" size="sm" icon={copied ? <Check size={15} /> : <Copy size={15} />} onClick={copy}>
              {copied ? "Copied" : "Copy code"}
            </Button>
            <Button variant="secondary" size="sm" icon={<Download size={15} />} onClick={download}>
              Save as file
            </Button>
          </div>
          <p className="muted small">
            {remembered ? "Saved on this device." : "Keep this code safe. It can't be recovered."}
          </p>
        </div>

        <div className="confirm-actions">
          <Link to={`/manage?id=${booking.id}`} className="btn btn-primary">
            Manage this booking
          </Link>
          {day === clinicDate() && (
            <Link to={liveQueueLink(booking)} className="btn btn-secondary">
              See live queue
            </Link>
          )}
          <Link to="/" className="btn btn-ghost">
            Back to home
          </Link>
        </div>
      </div>
    </div>
  );
}
