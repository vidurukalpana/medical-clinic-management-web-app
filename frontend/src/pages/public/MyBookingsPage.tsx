import { useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarPlus, CalendarClock, XCircle, History, KeyRound } from "lucide-react";
import { api, type GuestBooking } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { usePublicDoctors } from "../../lib/hooks";
import { BookingTicket, RescheduleModal, isUpcoming } from "../../components/BookingPieces";
import { Button, EmptyState, ErrorNote, Spinner } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { ChangePasswordCard } from "../staff/AccountPage";

export function MyBookingsPage() {
  const { user, loading } = useAuth();
  const doctors = usePublicDoctors();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [moving, setMoving] = useState<GuestBooking | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  const bookings = useQuery({
    queryKey: ["my-appointments"],
    queryFn: api.myAppointments,
    enabled: user?.role === "patient",
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["my-appointments"] });
    queryClient.invalidateQueries({ queryKey: ["slots"] });
  };
  const cancel = useMutation({
    mutationFn: (id: number) => api.myCancel(id),
    onSuccess: () => {
      refresh();
      toast("Booking cancelled");
    },
    onError: (error) => toast((error as Error).message, "error"),
  });
  const reschedule = useMutation({
    mutationFn: ({ id, startAt }: { id: number; startAt: string }) => api.myReschedule(id, startAt),
    onSuccess: () => {
      setMoving(null);
      refresh();
      toast("Booking moved");
    },
    onError: (error) => toast((error as Error).message, "error"),
  });

  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace state={{ from: "/my-bookings" }} />;
  if (user.role !== "patient") return <Navigate to="/staff" replace />;

  const names = new Map(doctors.data?.map((doctor) => [doctor.id, doctor.display_name]));
  const upcoming = (bookings.data ?? []).filter(isUpcoming).reverse();
  const past = (bookings.data ?? []).filter((booking) => !isUpcoming(booking));

  return (
    <div className="container narrow-page">
      <div className="page-intro page-intro-row">
        <div>
          <span className="eyebrow">Hi, {user.username}</span>
          <h1>My bookings</h1>
          <p className="muted">Bookings you made while signed in. Earlier guest bookings aren't linked automatically.</p>
        </div>
        <div className="row">
          <Button variant="ghost" icon={<KeyRound size={16} />} onClick={() => setShowPassword((v) => !v)}>
            Password
          </Button>
          <Link to="/book" className="btn btn-accent">
            <CalendarPlus size={16} /> New booking
          </Link>
        </div>
      </div>

      {showPassword && (
        <div className="fade-in" style={{ marginBottom: 24 }}>
          <ChangePasswordCard />
        </div>
      )}

      {bookings.isLoading ? (
        <Spinner />
      ) : bookings.isError ? (
        <ErrorNote error={bookings.error} />
      ) : !bookings.data?.length ? (
        <EmptyState
          icon={<CalendarPlus size={22} />}
          title="No bookings yet"
          hint="Book a visit while signed in and it'll show up here."
        />
      ) : (
        <>
          <h2 className="list-title">Upcoming</h2>
          {upcoming.length ? (
            <div className="ticket-list">
              {upcoming.map((booking) => (
                <BookingTicket
                  key={booking.id}
                  booking={booking}
                  doctorName={names.get(booking.doctor_id)}
                  actions={
                    <>
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={<CalendarClock size={15} />}
                        onClick={() => setMoving(booking)}
                      >
                        Reschedule
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        icon={<XCircle size={15} />}
                        loading={cancel.isPending && cancel.variables === booking.id}
                        onClick={() => window.confirm("Cancel this booking?") && cancel.mutate(booking.id)}
                      >
                        Cancel
                      </Button>
                    </>
                  }
                />
              ))}
            </div>
          ) : (
            <p className="muted">Nothing coming up.</p>
          )}
          {past.length > 0 && (
            <>
              <h2 className="list-title">
                <History size={18} /> History
              </h2>
              <div className="ticket-list is-muted">
                {past.map((booking) => (
                  <BookingTicket key={booking.id} booking={booking} doctorName={names.get(booking.doctor_id)} />
                ))}
              </div>
            </>
          )}
        </>
      )}

      {moving && (
        <RescheduleModal
          open
          doctorId={moving.doctor_id}
          onClose={() => setMoving(null)}
          busy={reschedule.isPending}
          onConfirm={(slot) => reschedule.mutate({ id: moving.id, startAt: slot.start_at })}
        />
      )}
    </div>
  );
}
