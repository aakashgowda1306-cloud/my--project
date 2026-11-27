"use client";

import {
  Award, BookOpen, FlaskConical, Home, LogOut, Monitor, MoreHorizontal, Network, Search, Settings, Shield, User,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { authRequest, useApi } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { Brand } from "./ui";

type NavItem = { href: string; label: string; icon: typeof Home; ready: boolean };

// `ready: false` items are shown so learners can see what is coming, but they are
// visibly disabled — no dead links pretending to work.
const NAV: { group: string; items: NavItem[] }[] = [
  { group: "Learn", items: [
    { href: "/dashboard", label: "Dashboard", icon: Home, ready: true },
    { href: "/academy", label: "Academy", icon: BookOpen, ready: true },
  ] },
  { group: "Labs", items: [
    { href: "/soc", label: "SOC Operations", icon: Monitor, ready: true },
    { href: "/siem", label: "SIEM Lab", icon: Search, ready: true },
    { href: "/forensics", label: "Forensics Lab", icon: FlaskConical, ready: false },
    { href: "/network", label: "Network Lab", icon: Network, ready: false },
    { href: "/incidents", label: "Incident Response", icon: Shield, ready: false },
  ] },
  { group: "You", items: [
    { href: "/achievements", label: "Achievements", icon: Award, ready: false },
    { href: "/profile", label: "Profile", icon: User, ready: false },
    { href: "/settings", label: "Settings", icon: Settings, ready: false },
  ] },
];

const MOBILE_TABS = [
  { href: "/dashboard", label: "Home", icon: Home },
  { href: "/academy", label: "Learn", icon: BookOpen },
  { href: "/soc", label: "SOC", icon: Monitor },
  { href: "/siem", label: "SIEM", icon: Search },
];

function isActive(pathname: string, href: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: me } = useApi<Profile>("me");
  const [moreOpen, setMoreOpen] = useState(false);

  // New learners finish onboarding first.
  useEffect(() => {
    if (me && !me.onboarding_completed && pathname !== "/onboarding") router.replace("/onboarding");
  }, [me, pathname, router]);

  async function signOut() {
    await authRequest("logout");
    // Full page load on purpose: it discards every cached response from the old session.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign("/login");
  }

  const initials = me?.display_name.split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase() ?? "";

  const navList = (onNavigate?: () => void) => NAV.map(({ group, items }) => (
    <nav key={group} aria-label={group} className="flex flex-col gap-0.5">
      <h4 className="px-2 pb-2 text-xs font-medium text-faint">{group}</h4>
      {items.map(({ href, label, icon: Icon, ready }) => ready ? (
        <Link key={href} href={href} onClick={onNavigate}
              aria-current={isActive(pathname, href) ? "page" : undefined}
              className={`flex items-center gap-2.5 rounded-lg px-2 py-2 text-sm ${isActive(pathname, href)
                ? "bg-electric/15 text-text shadow-[inset_2px_0_0_var(--color-electric)]" : "text-muted hover:bg-raised hover:text-text"}`}>
          <Icon size={18} aria-hidden /> {label}
        </Link>
      ) : (
        <span key={href} aria-disabled="true" title="Being built next"
              className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-2 py-2 text-sm text-faint">
          <Icon size={18} aria-hidden /> {label}
          <span className="ml-auto rounded border border-line px-1.5 text-[10.5px]">Soon</span>
        </span>
      ))}
    </nav>
  ));

  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[232px_1fr] lg:bg-[linear-gradient(to_right,var(--color-surface)_232px,transparent_232px)]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 btn-primary">
        Skip to content
      </a>
      {/* Desktop sidebar */}
      <aside className="sticky top-0 hidden h-dvh flex-col gap-6 overflow-y-auto border-r border-line-soft bg-surface px-4 py-6 lg:flex">
        <Link href="/dashboard" className="px-2"><Brand /></Link>
        {navList()}
        <div className="mt-auto flex flex-col gap-3">
          <span className="sim-badge self-start">Lab data is simulated</span>
          <button onClick={signOut} className="flex items-center gap-2 px-2 text-sm text-muted hover:text-text">
            <LogOut size={16} aria-hidden /> Sign out
          </button>
        </div>
      </aside>

      <div className="min-w-0">
        {/* Top bar */}
        <header className="flex items-center gap-3 px-4 pt-4 lg:px-8 lg:pt-6">
          <Link href="/dashboard" className="lg:hidden" aria-label="Cybersec Academy home"><Brand compact /></Link>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden text-sm text-muted sm:inline">{me?.display_name}</span>
            <span aria-hidden className="grid h-9 w-9 place-items-center rounded-full border border-line bg-raised text-xs font-semibold">
              {initials}
            </span>
          </div>
        </header>
        <main id="main" className="px-4 pb-28 pt-4 lg:px-8 lg:pb-12">{children}</main>
      </div>

      {/* Mobile bottom tab bar (dedicated mobile navigation, not a shrunken sidebar) */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-30 grid h-[72px] grid-cols-5 border-t border-line bg-surface pb-2 lg:hidden">
        {MOBILE_TABS.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href} aria-current={isActive(pathname, href) ? "page" : undefined}
                className={`flex flex-col items-center justify-center gap-1 text-[11px] ${isActive(pathname, href) ? "text-electric" : "text-faint"}`}>
            <Icon size={22} aria-hidden /> {label}
          </Link>
        ))}
        <button onClick={() => setMoreOpen(true)} aria-expanded={moreOpen}
                className="flex flex-col items-center justify-center gap-1 text-[11px] text-faint">
          <MoreHorizontal size={22} aria-hidden /> More
        </button>
      </nav>

      {moreOpen && (
        <div role="dialog" aria-modal="true" aria-label="More navigation" className="fixed inset-0 z-40 lg:hidden"
             onKeyDown={(e) => e.key === "Escape" && setMoreOpen(false)}>
          <button aria-label="Close menu" className="absolute inset-0 bg-black/50" onClick={() => setMoreOpen(false)} />
          <div className="absolute inset-x-0 bottom-0 flex max-h-[80dvh] flex-col gap-5 overflow-y-auto rounded-t-2xl border-t border-line bg-surface p-5">
            {navList(() => setMoreOpen(false))}
            <button onClick={signOut} className="btn-ghost"><LogOut size={16} aria-hidden /> Sign out</button>
          </div>
        </div>
      )}
    </div>
  );
}
