import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, UserSearch } from "lucide-react";
import { usePublicDoctors } from "../../lib/hooks";
import { consultsOn, matchesSearch, specialtiesOf } from "../../lib/doctors";
import { clinicDate, weekdayName, weekdayOf } from "../../lib/time";
import { DoctorCard } from "../../components/DoctorCard";
import { EmptyState, ErrorNote, Spinner } from "../../components/ui";

const WEEKDAYS = [0, 1, 2, 3, 4];

function FilterChips<T extends string | number | null>({ label, options, value, onChange }: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="filter-row" role="group" aria-label={label}>
      <span className="filter-label">{label}</span>
      <div className="filter-chips">
        {options.map((option) => (
          <button
            key={String(option.value)}
            type="button"
            className={`filter-chip ${option.value === value ? "is-selected" : ""}`}
            aria-pressed={option.value === value}
            onClick={() => onChange(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export function DoctorsPage() {
  const doctors = usePublicDoctors();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState(params.get("q") ?? "");
  const specialty = params.get("specialty");
  const day = params.get("day") === null ? null : Number(params.get("day"));
  const today = weekdayOf(clinicDate());

  const setFilter = (key: string, value: string | number | null) => {
    const next = new URLSearchParams(params);
    if (value === null) next.delete(key);
    else next.set(key, String(value));
    setParams(next, { replace: true });
  };

  const specialties = useMemo(() => specialtiesOf(doctors.data ?? []), [doctors.data]);
  const shown = (doctors.data ?? []).filter(
    (doctor) =>
      matchesSearch(doctor, query) &&
      (specialty === null || doctor.specialty === specialty) &&
      (day === null || consultsOn(doctor, day)),
  );

  return (
    <div className="container narrow-page">
      <div className="page-intro">
        <span className="eyebrow">Our doctors</span>
        <h1>Find a doctor</h1>
        <p className="muted">Search by name or specialty, or see who's consulting on a given day.</p>
      </div>

      <div className="doctor-filters card">
        <div className="input-icon">
          <Search size={16} />
          <input
            className="input"
            type="search"
            value={query}
            placeholder="e.g. paediatrician, Fernando, Tamil"
            aria-label="Search doctors"
            onChange={(event) => {
              setQuery(event.target.value);
              setFilter("q", event.target.value.trim() || null);
            }}
          />
        </div>
        {specialties.length > 1 && (
          <FilterChips
            label="Specialty"
            value={specialty}
            onChange={(value) => setFilter("specialty", value)}
            options={[{ value: null, label: "All" }, ...specialties.map((item) => ({ value: item, label: item }))]}
          />
        )}
        <FilterChips
          label="Consulting on"
          value={day}
          onChange={(value) => setFilter("day", value)}
          options={[
            { value: null, label: "Any day" },
            ...WEEKDAYS.map((weekday) => ({
              value: weekday,
              label: weekday === today ? "Today" : weekdayName(weekday).slice(0, 3),
            })),
          ]}
        />
      </div>

      {doctors.isLoading ? (
        <Spinner />
      ) : doctors.isError ? (
        <ErrorNote error={doctors.error} />
      ) : shown.length === 0 ? (
        <EmptyState
          icon={<UserSearch size={22} />}
          title="No doctors match"
          hint="Try another name or specialty, or clear the filters."
        />
      ) : (
        <>
          <p className="muted small results-count">
            {shown.length === doctors.data!.length ? `${shown.length} doctors` : `${shown.length} of ${doctors.data!.length} doctors`}
          </p>
          <div className="doctor-grid">
            {shown.map((doctor) => (
              <DoctorCard key={doctor.id} doctor={doctor} tone={doctors.data!.indexOf(doctor) % 6} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
