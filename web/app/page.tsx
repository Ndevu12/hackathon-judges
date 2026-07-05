import { getDashboardData } from "@/lib/data";
import { Dashboard } from "@/components/dashboard";

// Read artifacts at build time (frozen snapshot for deploy) and per-request in
// dev (reflects the latest scan.py run). No runtime filesystem access needed.
export const dynamic = "force-static";

export default function Home() {
  const data = getDashboardData();
  return <Dashboard data={data} />;
}
