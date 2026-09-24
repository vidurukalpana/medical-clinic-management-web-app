# CareFlow Clinic — React frontend

A React + TypeScript single-page app for the Medical Clinic Booking and Queue API. It has two parts:

- **Public site**: browse doctors, book as a guest (name and phone only), manage a booking with its private code, and optional patient accounts with a "My bookings" page.
- **Staff portal** (`/staff`): a live dashboard with doctor queues and today's appointments, appointment search, patient records, weekly schedules and time off. Administrators also get doctor and account management.

## Technology

- [Vite](https://vitejs.dev/) + React 18 + TypeScript
- React Router for routing
- TanStack Query for data fetching, caching and the dashboard's 20-second live refresh
- lucide-react icons and a hand-written CSS design system (`src/styles.css`) with automatic light and dark themes

## Run locally

1. Start the backend first (see the root `README.md`) so the API is at `http://127.0.0.1:8000`.
2. Install Node.js 20 or newer, then in this folder run:

```bash
npm install
npm run dev
```

3. Open http://localhost:5173.

The backend doesn't enable CORS, so the Vite dev server proxies every `/api` request to the backend. To point it somewhere else, copy `.env.example` to `.env.local` and change `VITE_API_PROXY_TARGET`. Set `VITE_CLINIC_TIMEZONE` to the same value as the backend's `CLINIC_TIMEZONE` (default `Asia/Colombo`). All dates and times are shown in the clinic's timezone.

### Production build

```bash
npm run build     # type-checks, then writes static files to dist/
npm run preview   # serves dist/ locally
```

In production, serve `dist/` from the same origin as the API, or put both behind a reverse proxy that routes `/api` to FastAPI and everything else to `index.html`.

## Sign-in

Use the accounts seeded by the backend (`admin`, `doctor1`, `doctor2`) with the passwords from the backend `.env`. Administrators and doctors land in the staff portal. Patients who register at `/register` land on **My bookings**.

## Project layout

```
src/
  lib/          API client + types (api.ts), auth context, clinic-timezone helpers, hooks
  components/   UI primitives, layouts, slot picker, patient picker, toasts
  pages/public/ Home, booking wizard, manage booking, sign-in/registration, My bookings
  pages/staff/  Dashboard, appointments, patients, schedule, admin pages, account
```

## Privacy notes

- The booking form collects only a name and phone number and asks patients not to include medical details.
- A guest's private booking code is shown once. It's stored in the browser only if the patient ticks **Remember this booking on this device**.
- The staff session token is kept in `localStorage` and cleared on sign-out or when the API returns 401.
