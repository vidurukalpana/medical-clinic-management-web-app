import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type Doctor } from "./api";
import { useAuth } from "./auth";

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
