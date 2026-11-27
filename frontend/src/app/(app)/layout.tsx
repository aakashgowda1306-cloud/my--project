import { Suspense } from "react";
import { AppShell } from "@/components/app-shell";
import { Loading } from "@/components/ui";

// The shell reads the current URL (usePathname) for navigation highlighting. With Cache
// Components that is request-time data, so it must sit inside a Suspense boundary.
export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="p-8"><Loading /></div>}>
      <AppShell>{children}</AppShell>
    </Suspense>
  );
}
