import { Link } from "react-router-dom";
import {
  CalendarPlus,
  CalendarX,
  ShieldCheck,
  Timer,
  ArrowRight,
  KeyRound,
  Stethoscope,
  HeartPulse,
} from "lucide-react";
import type { PublicDoctor } from "../../lib/api";
import { useNextAvailable, usePublicDoctors } from "../../lib/hooks";
import { addDays, clinicDate, formatDay, formatTime } from "../../lib/time";
import { Avatar, EmptyState, ErrorNote, Spinner } from "../../components/ui";

const STEPS = [
  { icon: Stethoscope, title: "Choose a doctor", text: "See who's in this week." },
  { icon: Timer, title: "Pick a time", text: "Whatever suits your day." },
  { icon: KeyRound, title: "Keep your code", text: "Change or cancel anytime." },
];

export function HomePage() {
  const doctors = usePublicDoctors();

  return (
    <>
      <section className="hero">
        <div className="hero-glow" />
        <div className="container hero-inner">
          <div className="hero-copy">
            <span className="eyebrow">
              <HeartPulse size={14} /> Care, right on time
            </span>
            <h1>
              Skip the waiting room.
              <br />
              <span className="gradient-text">See your doctor on time.</span>
            </h1>
            <p className="lead">Book in under a minute. We'll be ready when you arrive.</p>
            <div className="hero-cta">
              <Link to="/book" className="btn btn-accent btn-lg">
                <CalendarPlus size={18} /> Book an appointment
              </Link>
              <Link to="/manage" className="btn btn-secondary btn-lg">
                Manage a booking
              </Link>
            </div>
          </div>

          <HeroVisual doctors={doctors.data} />
        </div>
      </section>

      <section className="container section">
        <div className="section-head">
          <span className="eyebrow">How it works</span>
          <h2>Three simple steps</h2>
        </div>
        <div className="steps">
          {STEPS.map(({ icon: Icon, title, text }, index) => (
            <div key={title} className="step-card">
              <span className="step-index">0{index + 1}</span>
              <span className="step-icon">
                <Icon size={22} />
              </span>
              <h3>{title}</h3>
              <p className="muted">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="container section" id="doctors">
        <div className="section-head section-head-row">
          <div>
            <span className="eyebrow">Our doctors</span>
            <h2>Consulting this week</h2>
          </div>
          <Link to="/book" className="link-arrow">
            See all availability <ArrowRight size={16} />
          </Link>
        </div>
        {doctors.isLoading ? (
          <Spinner />
        ) : doctors.isError ? (
          <ErrorNote error={doctors.error} />
        ) : !doctors.data?.length ? (
          <EmptyState title="No doctors are taking bookings right now" hint="Please check back soon." />
        ) : (
          <div className="doctor-grid">
            {doctors.data.map((doctor, index) => (
              <article key={doctor.id} className="doctor-card">
                <Avatar name={doctor.display_name} size={64} tone={index % 6} />
                <div>
                  <h3>{doctor.display_name}</h3>
                  <span className="muted mono">Reg. {doctor.registration_number}</span>
                </div>
                <Link to={`/book?doctor=${doctor.id}`} className="btn btn-primary btn-sm">
                  Book with {doctor.display_name.split(" ")[0]} <ArrowRight size={15} />
                </Link>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="container section">
        <div className="cta-band">
          <div>
            <h2>Already booked?</h2>
            <p>Check, move or cancel your visit.</p>
          </div>
          <Link to="/manage" className="btn btn-lg btn-light">
            Manage my booking <ArrowRight size={18} />
          </Link>
        </div>
      </section>
    </>
  );
}

function dayLabel(day: string) {
  const today = clinicDate();
  if (day === today) return "Today";
  if (day === addDays(today, 1)) return "Tomorrow";
  return formatDay(day, "short");
}

/** Live preview of the soonest open appointment; never shows patient data. */
function HeroVisual({ doctors }: { doctors: PublicDoctor[] | undefined }) {
  const next = useNextAvailable(doctors);
  const found = next.data;

  return (
    <div className="hero-visual" aria-hidden>
      <div className="float-card float-card-main">
        {found ? (
          <>
            <div className="fc-head">
              <span className="fc-pill">Next available</span>
              <span className="muted mono">Reg. {found.doctor.registration_number}</span>
            </div>
            <div className="fc-doc">
              <Avatar name={found.doctor.display_name} size={44} tone={found.doctorIndex % 6} />
              <div>
                <strong>{found.doctor.display_name}</strong>
                <span className="muted">Registered doctor</span>
              </div>
            </div>
            <div className="fc-when">
              <div>
                <small>Date</small>
                <strong>{dayLabel(found.day)}</strong>
              </div>
              <div>
                <small>Time</small>
                <strong>{formatTime(found.slots[0].start_at)}</strong>
              </div>
            </div>
            <div className="fc-slots">
              {found.slots.slice(0, 6).map((slot, index) => (
                <span key={slot.start_at} className={index === 0 ? "on" : ""}>
                  {formatTime(slot.start_at).replace(/\s?[AP]M$/, "")}
                </span>
              ))}
            </div>
          </>
        ) : next.isPending || !doctors ? (
          <div className="fc-empty">
            <Spinner label="Finding the next open time…" />
          </div>
        ) : (
          <div className="fc-empty">
            <CalendarX size={28} />
            <strong>{next.isError ? "See open times on the booking page" : "Fully booked this week"}</strong>
            {!next.isError && <span className="muted">Please check back soon.</span>}
          </div>
        )}
      </div>
      {found && (
        <div className="float-card float-card-queue">
          <small>{dayLabel(found.day)}</small>
          <strong className="queue-num">{String(found.slots.length).padStart(2, "0")}</strong>
          <span className="muted">{found.slots.length === 1 ? "slot left" : "slots left"}</span>
        </div>
      )}
      <div className="float-card float-card-mini">
        <ShieldCheck size={18} />
        <span>Private booking code</span>
      </div>
    </div>
  );
}
