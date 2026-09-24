// Thin typed client for the FastAPI backend. Types mirror app/schemas/*.py.

export type Role = "patient" | "administrator" | "doctor";
export type AppointmentStatus = "scheduled" | "completed" | "cancelled" | "no_show";
export type VisitStatus = "waiting" | "in_progress" | "completed" | "cancelled";
export type Gender = "female" | "male" | "other" | "not_specified";

export interface Doctor {
  id: number;
  user_id: number;
  display_name: string;
  registration_number: string;
  phone: string | null;
  is_active: boolean;
}
export interface PublicDoctor {
  id: number;
  display_name: string;
  registration_number: string;
}
export interface User {
  id: number;
  username: string;
  role: Role;
  is_active: boolean;
}
export interface AuthUser extends User {
  doctor: Doctor | null;
}
export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: AuthUser;
}
export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}
export interface Slot {
  start_at: string;
  end_at: string;
}
export interface BookingStatus {
  remaining_slots: number;
  is_fully_booked: boolean;
}
export interface Appointment extends Slot {
  id: number;
  doctor_id: number;
  patient_id: number;
  status: AppointmentStatus;
}
export interface GuestBooking extends Slot {
  id: number;
  doctor_id: number;
  status: AppointmentStatus;
}
export interface GuestBookingConfirmation extends GuestBooking {
  management_token: string;
}
export interface Patient {
  id: number;
  medical_record_number: string;
  full_name: string;
  date_of_birth: string | null;
  gender: Gender;
  phone: string;
  address: string | null;
  emergency_contact: string | null;
  created_at: string;
  updated_at: string;
}
export type PatientInput = {
  full_name: string;
  date_of_birth: string | null;
  gender: Gender;
  phone: string;
  address: string | null;
  emergency_contact: string | null;
};
export interface Visit {
  id: number;
  appointment_id: number | null;
  doctor_id: number;
  patient_id: number;
  visit_date: string;
  queue_number: number;
  start_at: string | null;
  end_at: string | null;
  status: VisitStatus;
}
export interface DashboardAction {
  label: string;
  method: "POST" | "PUT" | "PATCH";
  path: string;
  body: Record<string, string | number>;
}
export interface DashboardAppointment extends Appointment {
  patient_name: string;
  doctor_name: string;
  visit_id: number | null;
  actions: DashboardAction[];
}
export interface DashboardVisit extends Visit {
  patient_name: string;
  actions: DashboardAction[];
}
export interface DoctorQueue {
  doctor_id: number;
  doctor_name: string;
  is_active: boolean;
  waiting_count: number;
  in_progress_count: number;
  patients: DashboardVisit[];
}
export interface Dashboard {
  day: string;
  timezone: string;
  generated_at: string;
  summary: {
    appointments: number;
    scheduled: number;
    waiting: number;
    in_progress: number;
    completed: number;
    cancelled: number;
    no_show: number;
  };
  appointments: DashboardAppointment[];
  doctor_queues: DoctorQueue[];
}
export interface Availability {
  id: number;
  doctor_id: number;
  weekday: number;
  start_time: string;
  end_time: string;
  slot_duration_minutes: number;
  is_active: boolean;
}
export type AvailabilityInput = Omit<Availability, "id" | "doctor_id">;
export interface Unavailability {
  id: number;
  doctor_id: number;
  start_at: string;
  end_at: string;
  reason: string | null;
}
export type UnavailabilityInput = Omit<Unavailability, "id" | "doctor_id">;
export interface DoctorProfileInput {
  display_name: string;
  registration_number: string;
  phone?: string | null;
}

const TOKEN_KEY = "careflow.token";

export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string | null) {
    try {
      if (token) localStorage.setItem(TOKEN_KEY, token);
      else localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* storage unavailable: session lasts for this tab only */
    }
  },
};

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(handler: (() => void) | null) {
  onUnauthorized = handler;
}

function describeError(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI 422 validation errors.
    return detail
      .map((item: { loc?: (string | number)[]; msg?: string }) => {
        const field = item.loc?.filter((part) => part !== "body").join(".");
        const msg = (item.msg ?? "Invalid value").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join(" · ");
  }
  return status >= 500 ? "The server hit an unexpected error." : `Request failed (${status}).`;
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
  headers?: Record<string, string>;
  auth?: boolean;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, headers = {}, auth = true } = options;
  let url = path.startsWith("/api") ? path : `/api${path}`;
  if (query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
    }
    const qs = params.toString();
    if (qs) url += `?${qs}`;
  }
  const token = tokenStore.get();
  const finalHeaders: Record<string, string> = { Accept: "application/json", ...headers };
  if (body !== undefined) finalHeaders["Content-Type"] = "application/json";
  if (auth && token) finalHeaders.Authorization = `Bearer ${token}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers: finalHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Cannot reach the clinic server. Is the backend running?");
  }

  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && auth && token && !headers["X-Booking-Token"]) onUnauthorized?.();
    throw new ApiError(response.status, describeError(data?.detail, response.status));
  }
  return data as T;
}

export const api = {
  // Auth
  login: (username: string, password: string) =>
    request<LoginResponse>("/auth/login", { method: "POST", body: { username, password }, auth: false }),
  logout: () => request<void>("/auth/logout", { method: "POST" }),
  me: () => request<AuthUser>("/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    request<void>("/auth/password", { method: "PUT", body: { current_password, new_password } }),
  registerPatient: (username: string, password: string) =>
    request<AuthUser>("/auth/register-patient", { method: "POST", body: { username, password }, auth: false }),

  // Doctors
  publicDoctors: () => request<PublicDoctor[]>("/doctors", { auth: false }),
  allDoctors: () => request<Doctor[]>("/admin/doctors"),
  myDoctorProfile: () => request<Doctor>("/doctors/me"),
  updateMyDoctorProfile: (body: { display_name?: string; phone?: string | null }) =>
    request<Doctor>("/doctors/me", { method: "PATCH", body }),
  updateDoctor: (id: number, body: Partial<Omit<Doctor, "id" | "user_id">>) =>
    request<Doctor>(`/doctors/${id}`, { method: "PATCH", body }),

  // Slots
  availableSlots: (doctorId: number, day: string) =>
    request<Slot[]>(`/doctors/${doctorId}/available-slots`, { query: { day }, auth: false }),
  bookingStatus: (doctorId: number, day: string) =>
    request<BookingStatus>(`/doctors/${doctorId}/booking-status`, { query: { day }, auth: false }),

  // Guest booking (a signed-in patient's token links the booking to the account)
  bookAsGuest: (body: { doctor_id: number; start_at: string; full_name: string; phone: string }) =>
    request<GuestBookingConfirmation>("/guest/appointments", { method: "POST", body }),
  guestBooking: (id: number, token: string) =>
    request<GuestBooking>(`/guest/appointments/${id}`, { headers: { "X-Booking-Token": token }, auth: false }),
  guestCancel: (id: number, token: string) =>
    request<GuestBooking>(`/guest/appointments/${id}/cancel`, {
      method: "PUT",
      headers: { "X-Booking-Token": token },
      auth: false,
    }),
  guestReschedule: (id: number, token: string, start_at: string) =>
    request<GuestBooking>(`/guest/appointments/${id}/reschedule`, {
      method: "PUT",
      body: { start_at },
      headers: { "X-Booking-Token": token },
      auth: false,
    }),

  // Patient account
  myAppointments: () => request<GuestBooking[]>("/my/appointments"),
  myCancel: (id: number) => request<GuestBooking>(`/my/appointments/${id}/cancel`, { method: "PUT" }),
  myReschedule: (id: number, start_at: string) =>
    request<GuestBooking>(`/my/appointments/${id}/reschedule`, { method: "PUT", body: { start_at } }),

  // Staff: dashboard, appointments, visits
  dashboard: (doctorId?: number) => request<Dashboard>("/dashboard", { query: { doctor_id: doctorId } }),
  runAction: (action: DashboardAction) =>
    request<unknown>(action.path, { method: action.method, body: action.body ?? {} }),
  appointments: (query: {
    doctor_id?: number;
    patient_id?: number;
    status?: AppointmentStatus | "";
    date_from?: string;
    date_to?: string;
    offset?: number;
    limit?: number;
  }) => request<Page<Appointment>>("/appointments", { query }),
  createAppointment: (body: { doctor_id: number; patient_id: number; start_at: string }) =>
    request<Appointment>("/appointments", { method: "POST", body }),
  cancelAppointment: (id: number) => request<Appointment>(`/appointments/${id}/cancel`, { method: "PUT" }),
  rescheduleAppointment: (id: number, start_at: string) =>
    request<Appointment>(`/appointments/${id}/reschedule`, { method: "PUT", body: { start_at } }),
  noShowAppointment: (id: number) => request<Appointment>(`/appointments/${id}/no-show`, { method: "PUT" }),
  checkIn: (id: number) => request<Visit>(`/appointments/${id}/check-in`, { method: "POST", body: {} }),
  walkIn: (doctor_id: number, patient_id: number) =>
    request<Visit>("/visits/walk-in", { method: "POST", body: { doctor_id, patient_id } }),

  // Patients
  patients: (query: string, offset = 0, limit = 20) =>
    request<Page<Patient>>("/patients", { query: { query, offset, limit } }),
  patient: (id: number) => request<Patient>(`/patients/${id}`),
  createPatient: (body: PatientInput) => request<Patient>("/patients", { method: "POST", body }),
  updatePatient: (id: number, body: Partial<PatientInput>) =>
    request<Patient>(`/patients/${id}`, { method: "PATCH", body }),

  // Scheduling
  availability: (doctorId: number) => request<Availability[]>(`/doctors/${doctorId}/availability`),
  addAvailability: (doctorId: number, body: AvailabilityInput) =>
    request<Availability>(`/doctors/${doctorId}/availability`, { method: "POST", body }),
  replaceAvailability: (doctorId: number, id: number, body: AvailabilityInput) =>
    request<Availability>(`/doctors/${doctorId}/availability/${id}`, { method: "PUT", body }),
  deleteAvailability: (doctorId: number, id: number) =>
    request<void>(`/doctors/${doctorId}/availability/${id}`, { method: "DELETE" }),
  unavailability: (doctorId: number) => request<Unavailability[]>(`/doctors/${doctorId}/unavailability`),
  addUnavailability: (doctorId: number, body: UnavailabilityInput) =>
    request<Unavailability>(`/doctors/${doctorId}/unavailability`, { method: "POST", body }),
  deleteUnavailability: (doctorId: number, id: number) =>
    request<void>(`/doctors/${doctorId}/unavailability/${id}`, { method: "DELETE" }),

  // Administration
  users: (query: { role?: Role | ""; is_active?: boolean | ""; offset?: number; limit?: number }) =>
    request<Page<User>>("/admin/users", { query }),
  createUser: (body: {
    username: string;
    password: string;
    role: Role;
    is_active: boolean;
    doctor?: DoctorProfileInput;
  }) => request<AuthUser>("/admin/users", { method: "POST", body }),
  updateUser: (id: number, body: { role?: Role; is_active?: boolean; doctor?: DoctorProfileInput }) =>
    request<AuthUser>(`/admin/users/${id}`, { method: "PATCH", body }),
  resetPassword: (id: number, new_password: string) =>
    request<void>(`/admin/users/${id}/password`, { method: "PUT", body: { new_password } }),
};
