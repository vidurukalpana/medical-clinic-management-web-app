import { Clock, Mail, MapPin, Phone, Siren } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Brand } from "./Layouts";

/** Digits and a leading "+" only, for tel: and wa.me links. */
function dialable(number: string): string {
  return number.replace(/[^\d+]/g, "");
}

/** WhatsApp logo (lucide has no brand icons). Path from Simple Icons, CC0. */
function WhatsAppIcon({ size = 16 }: { size?: number }) {
  return (
    <svg className="whatsapp-icon" width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z" />
    </svg>
  );
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
          <p className="muted">Caring for you, right on time.</p>
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
              <a
                href={`https://wa.me/${dialable(contact.whatsapp).replace("+", "")}`}
                target="_blank"
                rel="noreferrer"
                aria-label={`WhatsApp ${contact.whatsapp}`}
              >
                <WhatsAppIcon /> {contact.whatsapp}
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
