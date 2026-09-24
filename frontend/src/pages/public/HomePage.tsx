import { Link } from "react-router-dom";
import {
  CalendarPlus,
  ShieldCheck,
  Timer,
  UserRoundCheck,
  ArrowRight,
  KeyRound,
  Sparkles,
  BadgeCheck,
  Stethoscope,
} from "lucide-react";
import { usePublicDoctors } from "../../lib/hooks";
import { Avatar, EmptyState, ErrorNote, Spinner } from "../../components/ui";

const STEPS = [
  { icon: Stethoscope, title: "Choose your doctor", text: "See who's consulting and how many slots remain each day." },
  { icon: Timer, title: "Pick a time that suits you", text: "Live availability, so you never book a slot that's already taken." },
  { icon: KeyRound, title: "Keep your private code", text: "Use it to check, move or cancel your visit. You don't need an account." },
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
              <Sparkles size={14} /> Same-week appointments available
            </span>
            <h1>
              Skip the waiting room.
              <br />
              <span className="gradient-text">See your doctor on time.</span>
            </h1>
            <p className="lead">
              Book a consultation in under a minute with just your name and phone number. Arrive at your slot and
              we'll take it from there.
            </p>
            <div className="hero-cta">
              <Link to="/book" className="btn btn-accent btn-lg">
                <CalendarPlus size={18} /> Book an appointment
              </Link>
              <Link to="/manage" className="btn btn-secondary btn-lg">
                Manage a booking
              </Link>
            </div>
            <ul className="hero-trust">
              <li>
                <UserRoundCheck size={16} /> No account needed
              </li>
              <li>
                <ShieldCheck size={16} /> No medical details online
              </li>
              <li>
                <BadgeCheck size={16} /> Registered doctors
              </li>
            </ul>
          </div>

          <div className="hero-visual" aria-hidden>
            <div className="float-card float-card-main">
              <div className="fc-head">
                <span className="fc-pill">Confirmed</span>
                <span className="muted mono">#1042</span>
              </div>
              <div className="fc-doc">
                <Avatar name="Doctor One" size={44} tone={0} />
                <div>
                  <strong>Doctor One</strong>
                  <span className="muted">General consultation</span>
                </div>
              </div>
              <div className="fc-when">
                <div>
                  <small>Date</small>
                  <strong>Tue, 14 Oct</strong>
                </div>
                <div>
                  <small>Time</small>
                  <strong>9:20 AM</strong>
                </div>
              </div>
              <div className="fc-slots">
                {["9:00", "9:10", "9:20", "9:30", "9:40", "9:50"].map((time, index) => (
                  <span key={time} className={index === 2 ? "on" : index === 0 || index === 4 ? "off" : ""}>
                    {time}
                  </span>
                ))}
              </div>
            </div>
            <div className="float-card float-card-queue">
              <small>Now serving</small>
              <strong className="queue-num">07</strong>
              <span className="muted">3 patients ahead</span>
            </div>
            <div className="float-card float-card-mini">
              <ShieldCheck size={18} />
              <span>Private booking code</span>
            </div>
          </div>
        </div>
      </section>

      <section className="container section">
        <div className="section-head">
          <span className="eyebrow">How it works</span>
          <h2>Three steps, no paperwork</h2>
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
            <p>Use your booking number and private code to check, move or cancel your visit.</p>
          </div>
          <Link to="/manage" className="btn btn-lg btn-light">
            Manage my booking <ArrowRight size={18} />
          </Link>
        </div>
      </section>
    </>
  );
}
