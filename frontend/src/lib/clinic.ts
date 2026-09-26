// Mock clinic contact details for development. The chat assistant reads the same
// details from app/content/clinic_info.md, so update both files together.
export const CLINIC = {
  name: "CareFlow Clinic",
  address: ["No. 42, Lake View Road", "Colombo 05, Sri Lanka"],
  phone: "+94 11 234 5678",
  whatsapp: "+94 77 123 4567",
  email: "hello@careflowclinic.lk",
  receptionHours: "Monday to Friday, 8:00 to 18:00",
  closedDays: "Closed on weekends and public holidays",
  emergencyNumber: "1990",
};

/** Digits and a leading "+" only, for tel: and wa.me links. */
export function dialable(number: string): string {
  return number.replace(/[^\d+]/g, "");
}
