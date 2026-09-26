import { Clock, Mail, MapPin, MessageCircle, Phone, Siren } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Brand } from "./Layouts";

/** Digits and a leading "+" only, for tel: and wa.me links. */
function dialable(number: string): string {
  return number.replace(/[^\d+]/g, "");
}

// Contact details come from GET /api/clinic-contact-details, the same source the
// chat assistant uses. The columns stay hidden until they load.
export function SiteFooter() {
  const { data: contact } = useQuery({
    queryKey: ["clinic-contact-details"],
    queryFn: api.clinicContactDetails,
    staleTime: 10 * 60_000,
  });

  return (
    <footer className="site-footer">
      <div className="container footer-grid">
        <div className="footer-about">
          <Brand />
          <p className="muted">
            Booking only needs a name and phone number. We never ask for symptoms or medical details online.
          </p>
        </div>
        {contact && (
          <address className="footer-col">
            <h2>Contact us</h2>
            <span>
              <MapPin size={16} />
              <span>
                {contact.address_lines.map((line) => (
                  <span key={line} className="footer-line">
                    {line}
                  </span>
                ))}
              </span>
            </span>
            <a href={`tel:${dialable(contact.phone)}`}>
              <Phone size={16} /> {contact.phone}
            </a>
            {contact.whatsapp && (
              <a href={`https://wa.me/${dialable(contact.whatsapp).replace("+", "")}`} target="_blank" rel="noreferrer">
                <MessageCircle size={16} /> WhatsApp {contact.whatsapp}
              </a>
            )}
            {contact.email && (
              <a href={`mailto:${contact.email}`}>
                <Mail size={16} /> {contact.email}
              </a>
            )}
          </address>
        )}
        {contact && (
          <div className="footer-col">
            <h2>Reception hours</h2>
            <span>
              <Clock size={16} />
              <span>
                <span className="footer-line">{contact.reception_hours}</span>
                {contact.closed_days && <span className="footer-line muted">{contact.closed_days}</span>}
              </span>
            </span>
            {contact.emergency_number && (
              <span className="footer-emergency">
                <Siren size={16} /> Emergency? Call {contact.emergency_number} or go to the nearest hospital.
              </span>
            )}
          </div>
        )}
      </div>
      <div className="container footer-bottom muted">
        © {new Date().getFullYear()} {contact?.name ?? "CareFlow Clinic"}
      </div>
    </footer>
  );
}
