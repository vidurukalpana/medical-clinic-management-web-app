import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  CalendarDays,
  Users,
  Clock3,
  Stethoscope,
  ShieldCheck,
  Settings,
  LogOut,
  Menu,
  X,
  CalendarPlus,
  Sun,
  Moon,
  Monitor,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { useStaffTheme, type ThemePreference } from "../lib/theme";
import { Avatar, Spinner } from "./ui";
import { ChatWidget } from "./ChatWidget";
import { SiteFooter } from "./SiteFooter";

export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="brand">
      <span className="brand-mark">
        <svg viewBox="0 0 64 64" aria-hidden>
          <path d="M27 14h10v13h13v10H37v13H27V37H14V27h13z" fill="currentColor" />
        </svg>
        <i className="brand-pulse" />
      </span>
      <span className="brand-text">
        Care<b>Flow</b>
      </span>
    </Link>
  );
}

export function PublicLayout() {
  const { user, isStaff, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <div className="public-shell">
      <header className="topnav">
        <div className="container topnav-inner">
          <Brand />
          <button className="icon-btn topnav-toggle" onClick={() => setOpen((v) => !v)} aria-label="Menu">
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
          <nav className={`topnav-links ${open ? "is-open" : ""}`}>
            <NavLink to="/" end>
              Home
            </NavLink>
            <NavLink to="/book">Book a visit</NavLink>
            <NavLink to="/manage">Manage booking</NavLink>
            {user?.role === "patient" && <NavLink to="/my-bookings">My bookings</NavLink>}
            {isStaff && <NavLink to="/staff">Staff portal</NavLink>}
            {user ? (
              <button className="btn btn-ghost btn-sm" onClick={logout}>
                <LogOut size={15} /> Sign out
              </button>
            ) : (
              <Link to="/login" className="btn btn-secondary btn-sm">
                Sign in
              </Link>
            )}
            <Link to="/book" className="btn btn-accent btn-sm">
              <CalendarPlus size={15} /> Book now
            </Link>
          </nav>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      <SiteFooter />
      <ChatWidget />
    </div>
  );
}

const STAFF_NAV = [
  { to: "/staff", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/staff/appointments", label: "Appointments", icon: CalendarDays },
  { to: "/staff/patients", label: "Patients", icon: Users },
  { to: "/staff/schedule", label: "Schedule", icon: Clock3 },
];
const ADMIN_NAV = [
  { to: "/staff/doctors", label: "Doctors", icon: Stethoscope },
  { to: "/staff/users", label: "Accounts", icon: ShieldCheck },
];

const THEME_OPTIONS: { value: ThemePreference; label: string; icon: typeof Sun }[] = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "System", icon: Monitor },
];

function ThemeSwitch() {
  const [theme, setTheme] = useStaffTheme();
  return (
    <div className="segmented theme-switch" role="radiogroup" aria-label="Theme">
      {THEME_OPTIONS.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={theme === value}
          className={theme === value ? "is-selected" : ""}
          onClick={() => setTheme(value)}
        >
          <Icon size={14} /> {label}
        </button>
      ))}
    </div>
  );
}

export function StaffLayout() {
  const { user, loading, isStaff, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [location.pathname]);

  if (loading) return <Spinner label="Opening the staff portal…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (!isStaff) return <Navigate to="/my-bookings" replace />;

  const name = user.doctor?.display_name ?? user.username;
  const nav = isAdmin ? [...STAFF_NAV, ...ADMIN_NAV] : STAFF_NAV;

  return (
    <div className={`staff-shell ${open ? "nav-open" : ""}`}>
      <aside className="sidebar">
        <div className="sidebar-top">
          <Brand to="/staff" />
          <button className="icon-btn sidebar-close" onClick={() => setOpen(false)} aria-label="Close menu">
            <X size={20} />
          </button>
        </div>
        <nav className="sidebar-nav">
          <span className="sidebar-label">Clinic</span>
          {STAFF_NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end}>
              <Icon size={18} /> {label}
            </NavLink>
          ))}
          {isAdmin && <span className="sidebar-label">Administration</span>}
          {isAdmin &&
            ADMIN_NAV.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to}>
                <Icon size={18} /> {label}
              </NavLink>
            ))}
        </nav>
        <div className="sidebar-foot">
          <ThemeSwitch />
          <NavLink to="/staff/account" className="sidebar-user">
            <Avatar name={name} size={36} />
            <span>
              <strong>{name}</strong>
              <small>{user.role === "administrator" ? "Administrator" : "Doctor"}</small>
            </span>
            <Settings size={16} />
          </NavLink>
          <button
            className="btn btn-ghost btn-sm sidebar-logout"
            onClick={async () => {
              await logout();
              navigate("/login");
            }}
          >
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>
      <div className="sidebar-scrim" onClick={() => setOpen(false)} />
      <div className="staff-main">
        <header className="staff-topbar">
          <button className="icon-btn" onClick={() => setOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <Brand to="/staff" />
          <span className="staff-topbar-title">{nav.find((item) => location.pathname === item.to)?.label}</span>
        </header>
        <div className="staff-content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
