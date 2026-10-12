import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Camera, CameraOff, CheckCircle2, LogIn, ScanLine } from "lucide-react";
import { api, type CheckInLookup } from "../../lib/api";
import { extractCheckinCode, formatCheckinCode } from "../../lib/checkin";
import { formatDay, formatTime, clinicDate } from "../../lib/time";
import { Button, ErrorNote, StatusBadge } from "../../components/ui";
import { useToast } from "../../components/Toast";

/** Reads QR codes from the device camera until one is found. */
function CameraScanner({ onCode, onClose }: { onCode: (text: string) => void; onClose: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let stream: MediaStream | null = null;
    let timer = 0;
    let stopped = false;
    const canvas = document.createElement("canvas");
    (async () => {
      try {
        const { default: jsQR } = await import("jsqr");
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (stopped || !video.current) return;
        video.current.srcObject = stream;
        await video.current.play();
        const tick = () => {
          const element = video.current;
          if (stopped || !element) return;
          if (element.videoWidth) {
            canvas.width = element.videoWidth;
            canvas.height = element.videoHeight;
            const context = canvas.getContext("2d", { willReadFrequently: true })!;
            context.drawImage(element, 0, 0);
            const found = jsQR(context.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height);
            if (found?.data) return onCode(found.data);
          }
          timer = window.setTimeout(tick, 250);
        };
        tick();
      } catch {
        setError("Can't use the camera here. Allow camera access, or type or scan the code instead.");
      }
    })();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
      stream?.getTracks().forEach((track) => track.stop());
    };
  }, [onCode]);
  return (
    <div className="camera-scanner">
      {error ? <p className="muted small">{error}</p> : <video ref={video} muted playsInline />}
      <Button variant="ghost" size="sm" icon={<CameraOff size={14} />} onClick={onClose}>
        Stop camera
      </Button>
    </div>
  );
}

function LookupResult({ lookup, onDone }: { lookup: CheckInLookup; onDone: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const checkIn = useMutation({
    mutationFn: () => api.checkIn(lookup.appointment_id),
    onSuccess: (visit) => {
      queryClient.invalidateQueries();
      toast(`${lookup.patient_name} checked in as No. ${visit.appointment_number ?? visit.queue_number}`);
      onDone();
    },
  });
  const day = clinicDate(new Date(lookup.start_at));
  return (
    <div className={`checkin-result ${lookup.can_check_in ? "is-ready" : "is-blocked"}`}>
      <div className="checkin-result-head">
        <span className="queue-token">{String(lookup.appointment_number).padStart(2, "0")}</span>
        <div>
          <strong>{lookup.patient_name}</strong>
          <span className="muted small">
            {lookup.doctor_name} · {formatDay(day, "short")}, {formatTime(lookup.start_at)} session
          </span>
        </div>
        <StatusBadge status={lookup.status} />
      </div>
      {lookup.problem ? (
        <p className="checkin-problem">{lookup.problem}</p>
      ) : (
        <Button icon={<LogIn size={16} />} loading={checkIn.isPending} onClick={() => checkIn.mutate()}>
          Check in No. {lookup.appointment_number}
        </Button>
      )}
      <ErrorNote error={checkIn.error} />
    </div>
  );
}

/** Find a booking from its QR (camera, handheld scanner or typed code) and check the patient in. */
export function CheckInPanel({ initialCode }: { initialCode?: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [text, setText] = useState(initialCode ?? "");
  const [camera, setCamera] = useState(false);
  const [done, setDone] = useState<string | null>(null);
  const lookup = useMutation({ mutationFn: (code: string) => api.checkInLookup(code) });

  const find = (raw: string) => {
    const code = extractCheckinCode(raw);
    setText(code ? formatCheckinCode(code) : raw);
    setCamera(false);
    setDone(null);
    if (code) lookup.mutate(code);
  };
  const reset = (message: string | null = null) => {
    setText("");
    setDone(message);
    lookup.reset();
    input.current?.focus();
  };

  useEffect(() => {
    if (initialCode) find(initialCode);
    // Only the code in the link opened this page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialCode]);

  return (
    <div className="stack">
      <form
        className="checkin-form"
        onSubmit={(event: FormEvent) => {
          event.preventDefault();
          find(text);
        }}
      >
        <div className="input-icon">
          <ScanLine size={16} />
          <input
            ref={input}
            className="input mono"
            value={text}
            autoFocus
            placeholder="Scan the QR or type the code"
            aria-label="Check-in code"
            onChange={(event) => setText(event.target.value)}
          />
        </div>
        <Button type="submit" variant="secondary" loading={lookup.isPending}>
          Find
        </Button>
        {!camera && (
          <Button type="button" variant="ghost" icon={<Camera size={16} />} onClick={() => setCamera(true)}>
            Use camera
          </Button>
        )}
      </form>
      <p className="muted small">A handheld barcode scanner types the code here. Press Enter if it doesn't.</p>
      {camera && <CameraScanner onCode={find} onClose={() => setCamera(false)} />}
      {done && (
        <p className="checkin-done">
          <CheckCircle2 size={16} /> {done}
        </p>
      )}
      <ErrorNote error={lookup.error} />
      {lookup.data && <LookupResult lookup={lookup.data} onDone={() => reset(`${lookup.data!.patient_name} is in the queue. Ready for the next patient.`)} />}
    </div>
  );
}
