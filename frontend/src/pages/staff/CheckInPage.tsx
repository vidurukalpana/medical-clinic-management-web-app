import { useSearchParams } from "react-router-dom";
import { Card, PageHeader } from "../../components/ui";
import { CheckInPanel } from "./CheckInPanel";

/** Opened by scanning a patient's QR with a phone camera, or from the dashboard. */
export function CheckInPage() {
  const [params] = useSearchParams();
  return (
    <div className="fade-in narrow-staff">
      <PageHeader title="Check in" subtitle="Scan the QR on the patient's booking, or type its code." />
      <Card>
        <CheckInPanel initialCode={params.get("code") ?? undefined} />
      </Card>
    </div>
  );
}
