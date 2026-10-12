import type { DoctorProfile } from "../lib/api";
import { Field } from "./ui";

export type DoctorProfileForm = {
  specialty: string;
  qualifications: string;
  languages: string;
  bio: string;
  consultation_fee: string;
};

export const profileForm = (doctor: DoctorProfile): DoctorProfileForm => ({
  specialty: doctor.specialty ?? "",
  qualifications: doctor.qualifications ?? "",
  languages: doctor.languages ?? "",
  bio: doctor.bio ?? "",
  consultation_fee: doctor.consultation_fee === null ? "" : String(doctor.consultation_fee),
});

/** Blank fields are cleared on the server. */
export const profilePayload = (form: DoctorProfileForm): DoctorProfile => ({
  specialty: form.specialty.trim() || null,
  qualifications: form.qualifications.trim() || null,
  languages: form.languages.trim() || null,
  bio: form.bio.trim() || null,
  consultation_fee: form.consultation_fee.trim() === "" ? null : Number(form.consultation_fee),
});

/** The public profile patients see when choosing a doctor. */
export function DoctorProfileFields({ value, onChange }: {
  value: DoctorProfileForm;
  onChange: (value: DoctorProfileForm) => void;
}) {
  const set = (field: keyof DoctorProfileForm) => (event: { target: { value: string } }) =>
    onChange({ ...value, [field]: event.target.value });
  return (
    <>
      <div className="form-grid">
        <Field label="Specialty" hint="e.g. Consultant Paediatrician">
          <input className="input" value={value.specialty} maxLength={80} onChange={set("specialty")} />
        </Field>
        <Field label="Consultation fee (Rs.)" hint="Optional, paid at the clinic">
          <input className="input" type="number" min={0} max={1000000} value={value.consultation_fee} onChange={set("consultation_fee")} />
        </Field>
      </div>
      <Field label="Qualifications" hint="e.g. MBBS (Colombo), MD (Paediatrics)">
        <input className="input" value={value.qualifications} maxLength={200} onChange={set("qualifications")} />
      </Field>
      <Field label="Languages" hint="e.g. Sinhala, English">
        <input className="input" value={value.languages} maxLength={120} onChange={set("languages")} />
      </Field>
      <Field label="About" hint="One or two sentences patients will see. No contact details.">
        <textarea className="input" rows={3} value={value.bio} maxLength={500} onChange={set("bio")} />
      </Field>
    </>
  );
}
