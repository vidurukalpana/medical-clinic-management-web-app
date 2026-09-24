import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays,
  Hourglass,
  Stethoscope,
  CheckCircle2,
  RefreshCw,
  Play,
  Check,
  X,
  LogIn,
  UserX,
  Coffee,
} from "lucide-react";
import { api, type Dashboard, type DashboardAction, type DoctorQueue } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { formatDay, formatTime, greeting } from "../../lib/time";
import { Avatar, Button, Card, EmptyState, ErrorNote, Spinner, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { DoctorSelect, QuickActionButtons } from "./QuickActions";

const REFRESH_MS = 20_000;

const ACTION_STYLE: Record<string, { variant: "primary" | "secondary" | "danger" | "ghost" | "accent"; icon: JSX.Element }> = {
  "Check in": { variant: "primary", icon: <LogIn size={14} /> },
  Start: { variant: "accent", icon: <Play size={14} /> },
  Complete: { variant: "primary", icon: <Check size={14} /> },
  "Mark no-show": { variant: "secondary", icon: <UserX size={14} /> },
  Cancel: { variant: "ghost", icon: <X size={14} /> },
};

function useRunAction() {
  const queryClient = useQueryClient();
  const toast = useToast();
  return useMutation({
    mutationFn: (action: DashboardAction) => api.runAction(action),
    onSuccess: (_, action) => {
      queryClient.invalidateQueries();
      toast(`${action.label} done`);
    },
    onError: (error) => toast((error as Error).message, "error"),
  });
}

function ActionButtons({ actions, subject }: { actions: DashboardAction[]; subject: string }) {
  const run = useRunAction();
  return (
    <div className="action-row">
      {actions.map((action) => {
        const style = ACTION_STYLE[action.label] ?? { variant: "secondary" as const, icon: null };
        const busy = run.isPending && run.variables?.path === action.path && run.variables?.label === action.label;
        return (
          <Button
            key={`${action.path}-${action.label}`}
            size="sm"
            variant={style.variant}
            icon={style.icon}
            loading={busy}
            disabled={run.isPending && !busy}
            onClick={() => {
              if (action.label === "Cancel" && !window.confirm(`Cancel for ${subject}?`)) return;
              run.mutate(action);
            }}
          >
            {action.label}
          </Button>
        );
      })}
    </div>
  );
}

function StatTile({ label, value, icon, tone, hint }: {
  label: string;
  value: number;
  icon: JSX.Element;
  tone: string;
  hint?: string;
}) {
  return (
    <div className={`stat-tile tone-${tone}`}>
      <span className="stat-icon">{icon}</span>
      <div>
        <span className="stat-label">{label}</span>
        <strong className="stat-value">{value}</strong>
        {hint && <span className="stat-hint">{hint}</span>}
      </div>
    </div>
  );
}

function QueueColumn({ queue, index }: { queue: DoctorQueue; index: number }) {
  const current = queue.patients.filter((visit) => visit.status === "in_progress");
  const waiting = queue.patients.filter((visit) => visit.status === "waiting");
  return (
    <div className={`queue-col ${queue.is_active ? "" : "is-inactive"}`}>
      <header className="queue-head">
        <Avatar name={queue.doctor_name} size={38} tone={index % 6} />
        <div>
          <strong>{queue.doctor_name}</strong>
          <span className="muted small">
            {queue.waiting_count} waiting · {queue.in_progress_count} in room
            {!queue.is_active && " · inactive"}
          </span>
        </div>
      </header>

      {current.map((visit) => (
        <div key={visit.id} className="now-serving">
          <div className="now-serving-top">
            <span className="live-dot" /> Now serving
          </div>
          <div className="now-serving-main">
            <span className="queue-token">{String(visit.queue_number).padStart(2, "0")}</span>
            <div>
              <strong>{visit.patient_name}</strong>
              <span className="muted small">{visit.start_at ? `Slot ${formatTime(visit.start_at)}` : "Walk-in"}</span>
            </div>
          </div>
          <ActionButtons actions={visit.actions} subject={visit.patient_name} />
        </div>
      ))}

      {waiting.length === 0 && current.length === 0 ? (
        <div className="queue-empty">
          <Coffee size={20} />
          <span>Queue is clear</span>
        </div>
      ) : (
        <ol className="queue-list">
          {waiting.map((visit, position) => (
            <li key={visit.id} className="queue-item" style={{ animationDelay: `${position * 40}ms` }}>
              <span className="queue-num">{String(visit.queue_number).padStart(2, "0")}</span>
              <div className="queue-item-main">
                <strong>{visit.patient_name}</strong>
                <span className="muted small">
                  {visit.start_at ? formatTime(visit.start_at) : "Walk-in"}
                  {position === 0 && current.length === 0 ? " · next up" : ""}
                </span>
              </div>
              <ActionButtons actions={visit.actions} subject={visit.patient_name} />
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function SummaryBar({ summary }: { summary: Dashboard["summary"] }) {
  const parts = [
    { key: "scheduled", label: "Scheduled", value: summary.scheduled },
    { key: "completed", label: "Completed", value: summary.completed },
    { key: "cancelled", label: "Cancelled", value: summary.cancelled },
    { key: "no_show", label: "No-show", value: summary.no_show },
  ];
  const total = parts.reduce((sum, part) => sum + part.value, 0);
  if (!total) return null;
  return (
    <div className="summary-bar">
      <div className="summary-bar-track">
        {parts.map((part) =>
          part.value ? (
            <span
              key={part.key}
              className={`seg seg-${part.key}`}
              style={{ flexGrow: part.value }}
              title={`${part.label}: ${part.value}`}
            />
          ) : null,
        )}
      </div>
      <div className="summary-bar-legend">
        {parts.map((part) => (
          <span key={part.key}>
            <i className={`seg-${part.key}`} /> {part.label} <b>{part.value}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

function UpdatedAgo({ at }: { at: number }) {
  const [, tick] = useState(0);
  useEffect(() => {
    const timer = window.setInterval(() => tick((n) => n + 1), 5000);
    return () => window.clearInterval(timer);
  }, []);
  const seconds = Math.max(0, Math.round((Date.now() - at) / 1000));
  return <span>{seconds < 5 ? "just now" : seconds < 60 ? `${seconds}s ago` : `${Math.round(seconds / 60)}m ago`}</span>;
}

export function DashboardPage() {
  const { user, isAdmin } = useAuth();
  const [doctorFilter, setDoctorFilter] = useState<number | null>(null);
  const dashboard = useQuery({
    queryKey: ["dashboard", doctorFilter],
    queryFn: () => api.dashboard(doctorFilter ?? undefined),
    refetchInterval: REFRESH_MS,
  });
  const data = dashboard.data;
  const name = user?.doctor?.display_name ?? user?.username;

  return (
    <div className="dashboard fade-in">
      <div className="dash-hero">
        <div>
          <span className="eyebrow eyebrow-light">{data ? formatDay(data.day) : "Today"}</span>
          <h1>
            {greeting()}, {name}
          </h1>
          <p>
            {data
              ? data.summary.waiting
                ? `${data.summary.waiting} ${data.summary.waiting === 1 ? "patient is" : "patients are"} waiting right now.`
                : "No one is waiting. Enjoy the calm."
              : "Loading today's clinic…"}
          </p>
        </div>
        <div className="dash-hero-tools">
          {isAdmin && (
            <div className="dash-filter">
              <DoctorSelect value={doctorFilter} onChange={setDoctorFilter} allowAll />
            </div>
          )}
          <span className="live-pill">
            <span className="live-dot" /> Live · {dashboard.dataUpdatedAt ? <UpdatedAgo at={dashboard.dataUpdatedAt} /> : "…"}
          </span>
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw size={15} className={dashboard.isFetching ? "spin" : ""} />}
            onClick={() => dashboard.refetch()}
          >
            Refresh
          </Button>
        </div>
      </div>

      {dashboard.isLoading ? (
        <Spinner label="Loading dashboard…" />
      ) : dashboard.isError ? (
        <ErrorNote error={dashboard.error} />
      ) : data ? (
        <>
          <div className="stat-grid">
            <StatTile
              label="Appointments today"
              value={data.summary.appointments}
              icon={<CalendarDays size={22} />}
              tone="teal"
              hint={`${data.summary.scheduled} still scheduled`}
            />
            <StatTile label="Waiting" value={data.summary.waiting} icon={<Hourglass size={22} />} tone="amber" />
            <StatTile
              label="In consultation"
              value={data.summary.in_progress}
              icon={<Stethoscope size={22} />}
              tone="violet"
            />
            <StatTile
              label="Completed"
              value={data.summary.completed}
              icon={<CheckCircle2 size={22} />}
              tone="green"
            />
          </div>

          <QuickActionButtons />

          <div className="dash-grid">
            <Card title="Live queues" className="dash-queues">
              {data.doctor_queues.length ? (
                <div className="queue-board">
                  {data.doctor_queues.map((queue, index) => (
                    <QueueColumn key={queue.doctor_id} queue={queue} index={index} />
                  ))}
                </div>
              ) : (
                <EmptyState title="No doctor queues to show" />
              )}
            </Card>

            <Card
              title="Today's appointments"
              className="dash-appointments"
              action={<span className="muted small">{data.appointments.length} total</span>}
            >
              <SummaryBar summary={data.summary} />
              {data.appointments.length ? (
                <ul className="timeline">
                  {data.appointments.map((appointment) => (
                    <li key={appointment.id} className={`timeline-item status-${appointment.status}`}>
                      <span className="timeline-time">
                        <strong>{formatTime(appointment.start_at)}</strong>
                        <small>{formatTime(appointment.end_at)}</small>
                      </span>
                      <span className="timeline-rail" />
                      <div className="timeline-body">
                        <div className="timeline-top">
                          <strong>{appointment.patient_name}</strong>
                          <StatusBadge status={appointment.status} />
                          {appointment.visit_id && <span className="chip">In queue</span>}
                        </div>
                        <span className="muted small">
                          {appointment.doctor_name} · #{appointment.id}
                        </span>
                        {appointment.actions.length > 0 && (
                          <ActionButtons actions={appointment.actions} subject={appointment.patient_name} />
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState
                  icon={<CalendarDays size={22} />}
                  title="No appointments today"
                  hint="Use Book appointment or Add walk-in to fill the day."
                />
              )}
            </Card>
          </div>
        </>
      ) : null}
    </div>
  );
}
