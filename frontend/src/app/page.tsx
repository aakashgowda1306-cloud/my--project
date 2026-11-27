import { BookOpen, FlaskConical, Monitor, Network, Search, Shield } from "lucide-react";
import Link from "next/link";
import { Brand, SimBadge } from "@/components/ui";

const LOG = ["02:14:00", "02:14:18", "02:14:36", "02:14:54", "02:15:12", "02:15:30", "02:15:48"];
const PORTS = [40000, 40126, 40252, 40378, 40084, 40210, 40336];

const DEPARTMENTS = [
  { icon: Monitor, title: "SOC Operations Centre", text: "Watch a security dashboard built from 352 synthetic events and triage 18 alerts." },
  { icon: Search, title: "SIEM Investigation Lab", text: "Search Windows, Linux, VPN and firewall logs, then run ten detection rules mapped to MITRE ATT&CK." },
  { icon: FlaskConical, title: "Digital Forensics Lab", text: "Hash evidence files, follow a chain of custody and rebuild a timeline from exported records." },
  { icon: Network, title: "Network Security Lab", text: "Explore a fictional company network, step through a TCP handshake and practise subnetting." },
  { icon: Shield, title: "Incident Response Centre", text: "Take four fictional incidents through nine response stages and write the post-incident report." },
  { icon: BookOpen, title: "Cybersecurity Academy", text: "Short lessons in plain English, each ending with a quiz and a practical task in one of the labs." },
];

const STEPS = [
  ["Learn the idea", "A 15-minute lesson explains one concept with a worked example."],
  ["Investigate", "Open the lab and search the simulated data yourself."],
  ["Submit a finding", "Enter what you found. It is checked on the server."],
  ["Understand why", "See the explanation, earn progress and move to the next lab."],
];

export default function Landing() {
  return (
    <div className="mx-auto max-w-[1200px] px-5 lg:px-8">
      <header className="flex h-[72px] items-center justify-between gap-4">
        <Brand />
        <nav aria-label="Page sections" className="hidden gap-7 text-sm text-muted md:flex">
          <a href="#labs" className="hover:text-text">Labs</a>
          <a href="#how" className="hover:text-text">How it works</a>
          <a href="#safety" className="hover:text-text">Safety</a>
        </nav>
        <div className="flex gap-2.5">
          <Link href="/login" className="btn-ghost">Sign in</Link>
          <Link href="/register" className="btn-primary hidden sm:inline-flex">Create free account</Link>
        </div>
      </header>

      <section className="grid items-center gap-12 pt-10 pb-20 lg:grid-cols-[1fr_1.08fr] lg:gap-14 lg:pt-14">
        <div>
          <h1 className="max-w-[12ch] text-[40px] font-semibold leading-[1.06] tracking-[-0.025em] sm:text-[52px]">
            Practise defending a network that doesn’t exist.
          </h1>
          <p className="mt-5 mb-7 max-w-[46ch] text-[17px] text-muted">
            Cybersec Academy is a free learning platform for cybersecurity beginners. Short lessons, then hands-on
            investigations in the logs, evidence and incidents of ExampleCorp — a company we invented so you can learn
            without touching real systems.
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href="/register" className="btn-primary">Start learning free</Link>
            <a href="#labs" className="btn-ghost">See the labs</a>
          </div>
          <p className="mt-4 text-xs text-faint">Learn. Investigate. Defend. Master Cybersecurity.</p>
        </div>

        <figure className="overflow-hidden rounded-xl border border-line bg-[#08101f]"
                aria-label="Example lab: failed SSH logins that trigger a detection">
          <div className="flex items-center justify-between border-b border-line-soft px-4 py-2.5 text-xs text-faint">
            <span>lnx-bastion-01.corp.example · /var/log/auth.log</span><SimBadge />
          </div>
          <div className="px-4 pt-3.5 pb-1.5 font-mono text-[12.5px] leading-[1.85]">
            {LOG.map((t, i) => (
              <div key={t} className={`truncate ${i >= 4 ? "-ml-2.5 pl-2 shadow-[inset_2px_0_0_var(--color-sev-medium)]" : ""}`}>
                <span className="mr-3 text-faint">Nov 17 {t}</span>sshd:{" "}
                <span className="text-sev-medium">Failed password for root from 203.0.113.45 port {PORTS[i]}</span>
              </div>
            ))}
          </div>
          <figcaption className="mx-4 mt-1.5 mb-4 rounded-lg border border-sev-medium/35 bg-sev-medium/[0.07] px-4 py-3.5">
            <strong className="text-sm"><span className="text-sev-medium">■ Medium</span>&nbsp; CSA-DET-001 · Repeated failed login activity</strong>
            <dl className="mt-2.5 grid grid-cols-[130px_1fr] gap-x-3.5 gap-y-1.5 text-sm">
              <dt className="text-faint">What was detected</dt><dd>12 failed logins for root from 203.0.113.45 in 3 minutes</dd>
              <dt className="text-faint">MITRE ATT&amp;CK</dt><dd>T1110 Brute Force</dd>
              <dt className="text-faint">Your next step</dt><dd>Check whether any attempt from this address succeeded</dd>
            </dl>
          </figcaption>
        </figure>
      </section>

      <section id="labs" className="border-t border-line-soft py-16 lg:py-[72px]">
        <h2 className="max-w-[22ch] text-[30px] font-semibold tracking-tight sm:text-[34px]">Six departments, one fictional company</h2>
        <p className="mt-3 max-w-[60ch] text-muted">
          Every lab shares the same synthetic world, so a clue you find in the SIEM shows up again in forensics and incident response.
        </p>
        <div className="mt-9 grid border-t border-line-soft md:grid-cols-2">
          {DEPARTMENTS.map(({ icon: Icon, title, text }, i) => (
            <div key={title} className={`grid grid-cols-[40px_1fr] gap-3.5 border-b border-line-soft py-5 md:pr-6
                ${i % 2 === 0 ? "md:border-r" : "md:pl-6"}`}>
              <span className="grid h-10 w-10 place-items-center rounded-lg border border-line bg-surface text-electric">
                <Icon size={20} aria-hidden />
              </span>
              <div><h3 className="text-[17px] font-semibold">{title}</h3><p className="mt-1 max-w-[46ch] text-sm text-muted">{text}</p></div>
            </div>
          ))}
        </div>
      </section>

      <section id="how" className="border-t border-line-soft py-16 lg:py-[72px]">
        <h2 className="text-[30px] font-semibold tracking-tight sm:text-[34px]">How every lab works</h2>
        <ol className="mt-9 grid gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-0">
          {STEPS.map(([title, text], i) => (
            <li key={title} className="relative lg:pr-6">
              <span className="relative z-10 mb-3.5 grid h-[30px] w-[30px] place-items-center rounded-full border border-electric bg-abyss text-sm font-semibold text-electric">
                {i + 1}
              </span>
              {i < STEPS.length - 1 && <span aria-hidden className="absolute top-[15px] left-[30px] right-0 hidden h-px bg-line lg:block" />}
              <h3 className="font-semibold">{title}</h3><p className="mt-1 text-sm text-muted">{text}</p>
            </li>
          ))}
        </ol>
      </section>

      <section id="safety" className="grid gap-12 border-t border-line-soft py-16 lg:grid-cols-2 lg:gap-14 lg:py-[72px]">
        <div>
          <h2 className="text-[30px] font-semibold tracking-tight sm:text-[34px]">Built for people starting out</h2>
          <ul className="mt-3">
            {[["Engineering and cybersecurity students", "Turn theory into investigations you can explain in an interview."],
              ["Aspiring SOC and blue-team analysts", "Triage alerts, write verdicts and practise incident workflows."],
              ["Portfolio builders", "Finish labs and share your post-incident reports."]].map(([who, why]) => (
              <li key={who} className="border-b border-line-soft py-3">{who}<span className="block text-sm text-muted">{why}</span></li>
            ))}
          </ul>
        </div>
        <div className="rounded-xl border border-dashed border-line p-7">
          <h2 className="text-2xl font-semibold">A clear safety boundary</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-muted">
            <li>Every log, host, person and incident is fictional.</li>
            <li>External addresses come only from ranges reserved for documentation.</li>
            <li>Nothing in the platform scans, connects to or attacks a real system.</li>
            <li>Every exercise states its objective, environment and restrictions.</li>
          </ul>
        </div>
      </section>

      <section className="flex flex-col items-start justify-between gap-6 border-t border-line-soft py-16 md:flex-row md:items-center lg:py-[72px]">
        <div>
          <h2 className="text-[30px] font-semibold tracking-tight sm:text-[34px]">Your first investigation takes 20 minutes.</h2>
          <p className="mt-3 text-muted">Create an account with your email address. No payment details, no software to install.</p>
        </div>
        <Link href="/register" className="btn-primary h-12 px-6">Create free account</Link>
      </section>

      <footer className="flex flex-col justify-between gap-2 border-t border-line-soft pt-7 pb-10 text-xs text-faint sm:flex-row">
        <span>Cybersec Academy — educational platform. All lab data is synthetic.</span>
        <a href="#safety" className="hover:text-text">Lab safety</a>
      </footer>
    </div>
  );
}
