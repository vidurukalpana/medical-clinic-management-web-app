/** "K7M2PQX9RT" → "K7M2P-QX9RT", easier to read aloud or type. */
export function formatCheckinCode(code: string): string {
  return code.length === 10 ? `${code.slice(0, 5)}-${code.slice(5)}` : code;
}

/** The QR opens this staff page, so reception can also scan with a phone camera. */
export function checkinUrl(code: string): string {
  return `${window.location.origin}/staff/check-in?code=${code}`;
}

/** Accepts a scanned link, a formatted code or a typed one. */
export function extractCheckinCode(scanned: string): string {
  let value = scanned.trim();
  if (value.includes("code=")) {
    try {
      value = new URL(value).searchParams.get("code") ?? value;
    } catch {
      value = value.split("code=").pop() ?? value;
    }
  }
  return value.toUpperCase().replace(/[^A-Z0-9]/g, "");
}
