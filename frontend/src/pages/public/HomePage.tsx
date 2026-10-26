import { Link } from "react-router-dom";
import {
  CalendarDays,
  CalendarPlus,
  CalendarX,
  ShieldCheck,
  ArrowRight,
  KeyRound,
  Stethoscope,
} from "lucide-react";
import type { PublicDoctor } from "../../lib/api";
import { useNextAvailable, usePublicDoctors } from "../../lib/hooks";
import { addDays, clinicDate, formatDay, formatTime } from "../../lib/time";
import { Avatar, EmptyState, ErrorNote, Spinner } from "../../components/ui";
import { DoctorCard } from "../../components/DoctorCard";

const HOME_DOCTORS = 3;

const STEPS = [
  { icon: Stethoscope, title: "Choose a doctor", text: "Search by name or specialty." },
  { icon: CalendarDays, title: "Pick a day", text: "You'll get your number right away." },
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
            <h1>
              Skip the waiting room.
              <br />
              <span className="gradient-text">See your doctor on time.</span>
            </h1>
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
          <span className="eyebrow">How booking works</span>
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
          <Link to="/doctors" className="link-arrow">
            {doctors.data && doctors.data.length > HOME_DOCTORS ? `See all ${doctors.data.length} doctors` : "Find a doctor"}{" "}
            <ArrowRight size={16} />
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
            {doctors.data.slice(0, HOME_DOCTORS).map((doctor, index) => (
              <DoctorCard key={doctor.id} doctor={doctor} tone={index % 6} />
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

/** Live preview of the soonest session with places left; never shows patient data. */
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
                <span className="muted">{found.doctor.specialty ?? "Registered doctor"}</span>
              </div>
            </div>
            <div className="fc-when">
              <div>
                <small>Date</small>
                <strong>{dayLabel(found.day)}</strong>
              </div>
              <div>
                <small>Starts</small>
                <strong>{formatTime(found.session.start_at)}</strong>
              </div>
            </div>
          </>
        ) : next.isPending || !doctors ? (
          <div className="fc-empty">
            <Spinner label="Finding the next open session…" />
          </div>
        ) : (
          <div className="fc-empty">
            <CalendarX size={28} />
            <strong>{next.isError ? "See open sessions on the booking page" : "Fully booked this week"}</strong>
            {!next.isError && <span className="muted">Please check back soon.</span>}
          </div>
        )}
      </div>
      {found && (
        <div className="float-card float-card-queue">
          <small>{dayLabel(found.day)}</small>
          <strong className="queue-num">{String(found.session.remaining_online).padStart(2, "0")}</strong>
          <span className="muted">{found.session.remaining_online === 1 ? "place left" : "places left"}</span>
        </div>
      )}
      <div className="float-card float-card-mini">
        <ShieldCheck size={18} />
        <span>Private booking code</span>
      </div>
    </div>
  );
}
