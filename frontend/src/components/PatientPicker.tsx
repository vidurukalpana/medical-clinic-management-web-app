import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, UserRound, Check } from "lucide-react";
import { api, type Patient } from "../lib/api";
import { useDebounced } from "../lib/hooks";
import { Avatar, Spinner } from "./ui";

export function PatientPicker({ value, onChange }: { value: Patient | null; onChange: (patient: Patient) => void }) {
  const [text, setText] = useState("");
  const query = useDebounced(text.trim());
  const results = useQuery({
    queryKey: ["patients", query, 0, 6],
    queryFn: () => api.patients(query, 0, 6),
    enabled: query.length > 0,
  });

  return (
    <div className="patient-picker">
      {value && (
        <div className="picked">
          <Avatar name={value.full_name} size={34} />
          <div>
            <strong>{value.full_name}</strong>
            <span className="muted mono">{value.medical_record_number}</span>
          </div>
          <Check size={18} className="picked-check" />
        </div>
      )}
      <div className="input-icon">
        <Search size={16} />
        <input
          className="input"
          placeholder="Search by MRN, name or phone…"
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
      </div>
      {query && (
        <div className="picker-results">
          {results.isLoading ? (
            <Spinner label="Searching…" />
          ) : results.data?.items.length ? (
            results.data.items.map((patient) => (
              <button
                type="button"
                key={patient.id}
                className={`picker-row ${value?.id === patient.id ? "is-selected" : ""}`}
                onClick={() => {
                  onChange(patient);
                  setText("");
                }}
              >
                <Avatar name={patient.full_name} size={30} />
                <span className="picker-name">{patient.full_name}</span>
                <span className="muted mono">{patient.medical_record_number}</span>
                <span className="muted">{patient.phone}</span>
              </button>
            ))
          ) : (
            <div className="picker-none">
              <UserRound size={16} /> No matching patients. Register them first.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
