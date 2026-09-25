// Staff-only theme preference. The public site is always light; the staff portal lets
// each device choose light, dark, or follow the operating system.
import { useEffect, useState } from "react";

export type ThemePreference = "light" | "dark" | "system";

const KEY = "careflow.staffTheme";
const DARK_QUERY = "(prefers-color-scheme: dark)";

function loadPreference(): ThemePreference {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark" || saved === "system") return saved;
  } catch {
    /* storage unavailable */
  }
  return "system";
}

function setDocumentTheme(theme: "light" | "dark") {
  document.documentElement.dataset.theme = theme;
}

/** Applies the staff theme while the calling component is mounted, and restores light on unmount. */
export function useStaffTheme() {
  const [preference, setPreference] = useState<ThemePreference>(loadPreference);

  useEffect(() => {
    try {
      localStorage.setItem(KEY, preference);
    } catch {
      /* storage unavailable */
    }
    if (preference !== "system") {
      setDocumentTheme(preference);
      return;
    }
    const media = window.matchMedia(DARK_QUERY);
    const apply = () => setDocumentTheme(media.matches ? "dark" : "light");
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [preference]);

  useEffect(() => () => setDocumentTheme("light"), []);

  return [preference, setPreference] as const;
}
