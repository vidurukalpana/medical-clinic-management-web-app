// Opt-in, per-device list of guest booking codes so a visitor can reopen a booking
// later without retyping the code. Tokens stay in this browser only.
export interface SavedBooking {
  id: number;
  token: string;
  label: string;
}

const KEY = "careflow.savedBookings";

export function loadSavedBookings(): SavedBooking[] {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as SavedBooking[]) : [];
  } catch {
    return [];
  }
}

function persist(items: SavedBooking[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
  } catch {
    /* storage unavailable */
  }
}

export function saveBooking(item: SavedBooking) {
  persist([item, ...loadSavedBookings().filter((saved) => saved.id !== item.id)].slice(0, 10));
}

export function forgetBooking(id: number) {
  persist(loadSavedBookings().filter((saved) => saved.id !== id));
}
