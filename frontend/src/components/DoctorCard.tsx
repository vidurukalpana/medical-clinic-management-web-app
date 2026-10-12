import { Link } from "react-router-dom";
import { ArrowRight, CalendarDays, GraduationCap, Languages, Wallet } from "lucide-react";
import type { PublicDoctor } from "../lib/api";
import { describeWeek, formatFee } from "../lib/doctors";
import { Avatar } from "./ui";

/** A doctor's public profile with a link to book. */
export function DoctorCard({ doctor, tone }: { doctor: PublicDoctor; tone: number }) {
  const fee = formatFee(doctor.consultation_fee);
  return (
    <article className="doctor-card">
      <header className="doctor-card-head">
        <Avatar name={doctor.display_name} size={56} tone={tone} />
        <div>
          <h3>{doctor.display_name}</h3>
          <span className="doctor-specialty">{doctor.specialty ?? "Doctor"}</span>
        </div>
      </header>
      {doctor.bio && <p className="muted small">{doctor.bio}</p>}
      <ul className="doctor-facts">
        {doctor.qualifications && (
          <li>
            <GraduationCap size={15} /> {doctor.qualifications}
          </li>
        )}
        <li>
          <CalendarDays size={15} />{" "}
          {doctor.weekly_sessions.length ? describeWeek(doctor.weekly_sessions) : "No regular sessions yet"}
        </li>
        {doctor.languages && (
          <li>
            <Languages size={15} /> {doctor.languages}
          </li>
        )}
        {fee && (
          <li>
            <Wallet size={15} />
            <span>
              {fee} <span className="muted">· paid at the clinic</span>
            </span>
          </li>
        )}
      </ul>
      <footer className="doctor-card-foot">
        <span className="muted mono small">Reg. {doctor.registration_number}</span>
        <Link to={`/book?doctor=${doctor.id}`} className="btn btn-primary btn-sm">
          Book <ArrowRight size={15} />
        </Link>
      </footer>
    </article>
  );
}
