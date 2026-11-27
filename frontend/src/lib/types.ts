// Shapes returned by the FastAPI backend (only the fields the UI uses).

export type Severity = "info" | "low" | "medium" | "high" | "critical";

export interface Profile {
  id: string; display_name: string; role: "student" | "instructor" | "admin";
  experience_level: "beginner" | "intermediate" | "advanced"; learning_goal: string | null;
  onboarding_completed: boolean; streak_days: number;
}

export interface CourseSummary {
  id: string; slug: string; title: string; summary: string; learning_path: string; level: string;
  department: string; total_lessons: number; completed_lessons: number; percent_complete: number | string;
  estimated_minutes: number;
}

export interface Dashboard {
  streak_days: number;
  lessons: { completed: number; total: number; percent: number };
  courses: { slug: string; title: string; total_lessons: number; completed_lessons: number; percent_complete: number | string }[];
  stats: {
    quizzes_passed: number; quiz_attempts: number; avg_quiz_score: string | null; labs_solved: number; labs_total: number;
    investigations_open: number; investigations_closed: number; incidents_open: number; incidents_resolved: number;
    achievements_earned: number; achievements_total: number;
  };
  recent_activity: { activity: string; started_at: string }[];
  next_lesson: { id: string; title: string; course_slug: string; course_title: string; estimated_minutes: number } | null;
}

export interface AlertRow {
  id: number; rule_id: string; rule_name?: string; mitre_technique_id?: string; title: string;
  severity: Exclude<Severity, "info">; first_seen: string; last_seen?: string; event_count: number; summary?: string;
  triage_status: string; investigation_id?: string | null; entity?: Record<string, unknown>;
}

export interface SocOverview {
  events: { total: number; by_severity: Partial<Record<Severity, number>>; by_source: Record<string, number> };
  alerts: {
    total: number; open: number; resolved: number; by_severity: Partial<Record<Severity, number>>;
    by_rule: { rule_id: string; name: string; mitre_technique_id: string; count: number }[];
  };
  incidents: { open: number; resolved: number };
  timeline: { bucket: string; severity: Severity; count: number }[];
  recent_alerts: AlertRow[];
  top_hosts: { host: string; events: number; high_or_critical: number }[];
}

export interface SecurityEvent {
  id: number; event_time: string; source: string; host: string; username: string | null; src_ip: string | null;
  dst_ip: string | null; dst_port: number | null; protocol: string | null; event_code: string; category: string;
  action: string; outcome: string; severity: Severity; process_name: string | null; command_line: string | null;
  message: string; raw: Record<string, unknown>;
}

export interface EventPage { total: number; page: number; page_size: number; items: SecurityEvent[] }

export interface DetectionRule {
  id: string; name: string; severity: Severity; mitre_technique_id: string; mitre_technique_name: string;
  mitre_tactic: string; data_sources: string[]; what_detected: string; why_it_matters: string;
  evidence_guidance: string; analyst_steps: string; defensive_response: string; alert_count?: number;
}

export interface Investigation {
  id: string; kind: string; alert_id: number | null; title: string; status: string; summary: string | null;
  created_at: string; updated_at: string; notes?: { id: string; body: string; created_at: string }[];
}

export interface AlertDetail extends AlertRow {
  rule: DetectionRule; evidence: SecurityEvent[]; investigation: Investigation | null; evidence_event_ids: number[];
}
