import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { checkinUrl, formatCheckinCode } from "../lib/checkin";

/** The booking's check-in QR; on its own it only lets signed-in staff find the booking. */
export function CheckInQr({ code, size = 168 }: { code: string; size?: number }) {
  const [svg, setSvg] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    // Always dark on white so scanners read it in either theme.
    QRCode.toString(checkinUrl(code), { type: "svg", margin: 1, errorCorrectionLevel: "M", color: { dark: "#0f172a", light: "#ffffff" } })
      .then((markup) => current && setSvg(markup))
      .catch(() => current && setSvg(null));
    return () => {
      current = false;
    };
  }, [code]);
  return (
    <figure className="checkin-qr">
      {svg ? (
        <div className="checkin-qr-image" style={{ width: size, height: size }} dangerouslySetInnerHTML={{ __html: svg }} />
      ) : (
        <div className="checkin-qr-image" style={{ width: size, height: size }} />
      )}
      <figcaption>
        <strong className="mono">{formatCheckinCode(code)}</strong>
        <span className="muted small">Show this at reception to check in</span>
      </figcaption>
    </figure>
  );
}
