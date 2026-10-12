import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type BookingSession, type Doctor, type PublicDoctor } from "./api";
import { useAuth } from "./auth";
import { addDays, clinicDate } from "./time";

/**
 * Doctors the signed-in staff member may act for: administrators get every
 * profile (including inactive ones); doctors get only their own.
 */
export function useStaffDoctors() {
  const { user, isAdmin } = useAuth();
  const all = useQuery({ queryKey: ["admin-doctors"], queryFn: api.allDoctors, enabled: isAdmin });
  const doctors: Doctor[] = useMemo(() => {
    if (isAdmin) return all.data ?? [];
    return user?.doctor ? [user.doctor] : [];
  }, [isAdmin, all.data, user]);
  const names = useMemo(() => new Map(doctors.map((doctor) => [doctor.id, doctor.display_name])), [doctors]);
  return { doctors, names, isLoading: isAdmin && all.isLoading };
}

export function usePublicDoctors() {
  return useQuery({ queryKey: ["public-doctors"], queryFn: api.publicDoctors, staleTime: 60_000 });
}

export interface NextAvailable {
  doctor: PublicDoctor;
  doctorIndex: number;
  day: string;
  session: BookingSession;
}

/**
 * The earliest session with places left across all bookable doctors, searching
 * from today up to `days` ahead. Resolves to null when everyone is fully booked.
 */
export function useNextAvailable(doctors: PublicDoctor[] | undefined, days = 7) {
  return useQuery({
    queryKey: ["next-available", doctors?.map((doctor) => doctor.id), days],
    enabled: !!doctors?.length,
    staleTime: 60_000,
    queryFn: async (): Promise<NextAvailable | null> => {
      const today = clinicDate();
      for (let offset = 0; offset < days; offset++) {
        const day = addDays(today, offset);
        const results = await Promise.all(doctors!.map((doctor) => api.sessions(doctor.id, day)));
        let best: NextAvailable | null = null;
        for (const [doctorIndex, sessions] of results.entries()) {
          const session = sessions.find((item) => item.remaining_online > 0);
          if (session && (!best || Date.parse(session.start_at) < Date.parse(best.session.start_at)))
            best = { doctor: doctors![doctorIndex], doctorIndex, day, session };
        }
        if (best) return best;
      }
      return null;
    },
  });
}

/** A doctor's next session with a free place (counting every place), up to `days` ahead. */
export function useNextOpenSession(doctorId: number, days = 21) {
  return useQuery({
    queryKey: ["next-open-session", doctorId, days],
    staleTime: 30_000,
    queryFn: async (): Promise<BookingSession | null> => {
      const today = clinicDate();
      for (let offset = 0; offset < days; offset++) {
        const sessions = await api.sessions(doctorId, addDays(today, offset));
        const open = sessions.find((session) => session.remaining > 0);
        if (open) return open;
      }
      return null;
    },
  });
}

export function usePatientName(patientId: number) {
  const query = useQuery({
    queryKey: ["patient", patientId],
    queryFn: () => api.patient(patientId),
    staleTime: 60_000,
  });
  return query.data?.full_name;
}

export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
