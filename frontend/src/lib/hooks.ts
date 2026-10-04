import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Doctor, type PublicDoctor, type Slot } from "./api";
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
  slots: Slot[];
}

/**
 * The earliest open slot across all bookable doctors, searching from today
 * up to `days` ahead. Resolves to null when everyone is fully booked.
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
        const results = await Promise.all(doctors!.map((doctor) => api.availableSlots(doctor.id, day)));
        let best: NextAvailable | null = null;
        for (const [doctorIndex, slots] of results.entries()) {
          const startsSooner = !best || Date.parse(slots[0]?.start_at) < Date.parse(best.slots[0].start_at);
          if (slots.length && startsSooner) best = { doctor: doctors![doctorIndex], doctorIndex, day, slots };
        }
        if (best) return best;
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
