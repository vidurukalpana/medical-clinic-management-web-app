import { Link, Route, Routes } from "react-router-dom";
import { PublicLayout, StaffLayout } from "./components/Layouts";
import { HomePage } from "./pages/public/HomePage";
import { BookPage } from "./pages/public/BookPage";
import { ManagePage } from "./pages/public/ManagePage";
import { LoginPage, RegisterPage } from "./pages/public/AuthPages";
import { MyBookingsPage } from "./pages/public/MyBookingsPage";
import { DashboardPage } from "./pages/staff/DashboardPage";
import { AppointmentsPage } from "./pages/staff/AppointmentsPage";
import { PatientsPage } from "./pages/staff/PatientsPage";
import { SchedulePage } from "./pages/staff/SchedulePage";
import { DoctorsPage, UsersPage } from "./pages/staff/AdminPages";
import { AccountPage } from "./pages/staff/AccountPage";
import { useAuth } from "./lib/auth";
import { EmptyState } from "./components/ui";

function AdminOnly({ children }: { children: JSX.Element }) {
  const { isAdmin } = useAuth();
  return isAdmin ? children : <EmptyState title="Administrators only" hint="Ask an administrator for access." />;
}

function NotFound() {
  return (
    <div className="container section">
      <EmptyState title="Page not found" hint="The page you're looking for doesn't exist." />
      <p className="center">
        <Link to="/" className="btn btn-primary">
          Go home
        </Link>
      </p>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<HomePage />} />
        <Route path="book" element={<BookPage />} />
        <Route path="manage" element={<ManagePage />} />
        <Route path="login" element={<LoginPage />} />
        <Route path="register" element={<RegisterPage />} />
        <Route path="my-bookings" element={<MyBookingsPage />} />
        <Route path="*" element={<NotFound />} />
      </Route>
      <Route path="staff" element={<StaffLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="appointments" element={<AppointmentsPage />} />
        <Route path="patients" element={<PatientsPage />} />
        <Route path="schedule" element={<SchedulePage />} />
        <Route path="account" element={<AccountPage />} />
        <Route path="doctors" element={<AdminOnly><DoctorsPage /></AdminOnly>} />
        <Route path="users" element={<AdminOnly><UsersPage /></AdminOnly>} />
      </Route>
    </Routes>
  );
}
