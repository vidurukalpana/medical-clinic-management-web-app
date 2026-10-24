import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { MessageSquare } from "lucide-react";
import { api, type SmsMessage } from "../../lib/api";
import { formatDateTime } from "../../lib/time";
import { Card, EmptyState, ErrorNote, PageHeader, Pagination, Spinner } from "../../components/ui";

const LIMIT = 50;
const KIND_LABEL: Record<SmsMessage["kind"], string> = { confirmation: "Confirmation", reminder: "Reminder" };
const STATUS_LABEL: Record<SmsMessage["status"], string> = {
  queued: "Queued",
  sent: "Sent",
  failed: "Failed",
  logged: "Recorded",
};

/** Every text to patients, newest first. Without a provider they are recorded here and not sent. */
export function SmsOutboxPage() {
  const [offset, setOffset] = useState(0);
  const page = useQuery({
    queryKey: ["sms-outbox", offset],
    queryFn: () => api.smsOutbox(offset, LIMIT),
    refetchInterval: 30_000,
  });
  return (
    <div className="fade-in">
      <PageHeader title="SMS outbox" subtitle="Booking confirmations and day-of reminders to patients." />
      {page.data?.provider === "outbox" && (
        <div className="alert alert-info sms-banner">
          No SMS provider is set up yet, so messages are recorded here but not sent to patients.
        </div>
      )}
      {page.isLoading ? (
        <Spinner />
      ) : page.isError ? (
        <ErrorNote error={page.error} />
      ) : !page.data?.items.length ? (
        <EmptyState icon={<MessageSquare size={22} />} title="No messages yet" hint="New bookings and reminders appear here." />
      ) : (
        <Card className="table-card">
          <div className="table-wrap">
            <table className="table sms-table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Type</th>
                  <th>To</th>
                  <th>Message</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {page.data.items.map((message) => (
                  <tr key={message.id}>
                    <td className="nowrap small">{formatDateTime(message.created_at)}</td>
                    <td>
                      <span className="chip">{KIND_LABEL[message.kind]}</span>
                    </td>
                    <td className="nowrap mono small">{message.phone}</td>
                    <td className="sms-body">{message.body}</td>
                    <td className="nowrap">
                      <span className={`chip ${message.status === "sent" ? "chip-green" : message.status === "failed" ? "chip-red" : ""}`} title={message.error ?? undefined}>
                        {STATUS_LABEL[message.status]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Pagination offset={offset} limit={LIMIT} total={page.data.total} onChange={setOffset} />
        </Card>
      )}
    </div>
  );
}
