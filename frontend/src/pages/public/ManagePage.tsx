import { useState, type FormEvent } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Search, KeyRound, Hash, CalendarClock, XCircle, Trash2, Bookmark, CalendarPlus } from "lucide-react";
import { api, type GuestBooking } from "../../lib/api";
import { usePublicDoctors } from "../../lib/hooks";
import { forgetBooking, loadSavedBookings, type SavedBooking } from "../../lib/savedBookings";
import { BookingTicket, RescheduleModal, isUpcoming } from "../../components/BookingPieces";
import { Button, Card, ErrorNote, Field } from "../../components/ui";
import { useToast } from "../../components/Toast";

export function ManagePage() {
  const [params] = useSearchParams();
  const [bookingId, setBookingId] = useState(params.get("id") ?? "");
  const [token, setToken] = useState("");
  const [saved, setSaved] = useState<SavedBooking[]>(loadSavedBookings);
  const [booking, setBooking] = useState<GuestBooking | null>(null);
  const [credentials, setCredentials] = useState<{ id: number; token: string } | null>(null);
  const [rescheduling, setRescheduling] = useState(false);
  const doctors = usePublicDoctors();
  const toast = useToast();
  const queryClient = useQueryClient();

  const lookup = useMutation({
    mutationFn: (input: { id: number; token: string }) => api.guestBooking(input.id, input.token),
    onSuccess: (result, input) => {
      setBooking(result);
      setCredentials(input);
    },
    onError: () => setBooking(null),
  });

  const cancel = useMutation({
    mutationFn: () => api.guestCancel(credentials!.id, credentials!.token),
    onSuccess: (result) => {
      setBooking(result);
      queryClient.invalidateQueries({ queryKey: ["slots"] });
      toast("Your booking has been cancelled");
    },
    onError: (error) => toast((error as Error).message, "error"),
  });

  const reschedule = useMutation({
    mutationFn: (startAt: string) => api.guestReschedule(credentials!.id, credentials!.token, startAt),
    onSuccess: (result) => {
      setBooking(result);
      setRescheduling(false);
      queryClient.invalidateQueries({ queryKey: ["slots"] });
      toast("Your booking has been moved");
    },
    onError: (error) => toast((error as Error).message, "error"),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const id = Number(bookingId.replace(/^#/, ""));
    if (id > 0 && token.trim()) lookup.mutate({ id, token: token.trim() });
  };

  const doctorName = booking && doctors.data?.find((doctor) => doctor.id === booking.doctor_id)?.display_name;

  return (
    <div className="container narrow-page">
      <div className="page-intro">
        <span className="eyebrow">Manage booking</span>
        <h1>Find your appointment</h1>
        <p className="muted">Enter the booking number and private code from your confirmation.</p>
      </div>

      <div className="manage-layout">
        <Card>
          <form onSubmit={submit} className="stack">
            <Field label="Booking number">
              <div className="input-icon">
                <Hash size={16} />
                <input
                  className="input"
                  value={bookingId}
                  onChange={(event) => setBookingId(event.target.value)}
                  placeholder="1042"
                  inputMode="numeric"
                  required
                />
              </div>
            </Field>
            <Field label="Private code">
              <div className="input-icon">
                <KeyRound size={16} />
                <input
                  className="input mono"
                  value={token}
                  onChange={(event) => setToken(event.target.value)}
                  placeholder="Paste the code you saved"
                  autoComplete="off"
                  spellCheck={false}
                  required
                />
              </div>
            </Field>
            <ErrorNote error={lookup.error} />
            <Button type="submit" loading={lookup.isPending} icon={<Search size={16} />}>
              Find booking
            </Button>
          </form>

          {saved.length > 0 && (
            <div className="saved-list">
              <span className="sidebar-label">
                <Bookmark size={13} /> Saved on this device
              </span>
              {saved.map((item) => (
                <div key={item.id} className="saved-row">
                  <button
                    type="button"
                    className="saved-open"
                    onClick={() => {
                      setBookingId(String(item.id));
                      setToken(item.token);
                      lookup.mutate({ id: item.id, token: item.token });
                    }}
                  >
                    <span className="mono">#{item.id}</span> {item.label}
                  </button>
                  <button
                    type="button"
                    className="icon-btn"
                    aria-label="Forget this booking"
                    onClick={() => {
                      forgetBooking(item.id);
                      setSaved(loadSavedBookings());
                    }}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>

        <div>
          {booking ? (
            <div className="fade-in">
              <BookingTicket
                booking={booking}
                doctorName={doctorName ?? undefined}
                actions={
                  isUpcoming(booking) ? (
                    <>
                      <Button
                        variant="secondary"
                        size="sm"
                        icon={<CalendarClock size={15} />}
                        onClick={() => setRescheduling(true)}
                      >
                        Reschedule
                      </Button>
                      <Button
                        variant="danger"
                        size="sm"
                        icon={<XCircle size={15} />}
                        loading={cancel.isPending}
                        onClick={() => window.confirm("Cancel this booking? This frees the slot for others.") && cancel.mutate()}
                      >
                        Cancel booking
                      </Button>
                    </>
                  ) : booking.status === "cancelled" ? (
                    <Link to={`/book?doctor=${booking.doctor_id}`} className="btn btn-primary btn-sm">
                      <CalendarPlus size={15} /> Book a new time
                    </Link>
                  ) : null
                }
              />
              <RescheduleModal
                open={rescheduling}
                doctorId={booking.doctor_id}
                onClose={() => setRescheduling(false)}
                onConfirm={(slot) => reschedule.mutate(slot.start_at)}
                busy={reschedule.isPending}
              />
            </div>
          ) : (
            <div className="manage-placeholder">
              <KeyRound size={28} />
              <p>Your booking will appear here.</p>
              <p className="muted small">
                Lost your code? Call the clinic reception. For your privacy we can't recover it from a phone number
                online.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
