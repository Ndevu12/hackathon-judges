// Shared data types for the dashboard. The Python analyzer emits CSV (all
// string values) + JSON; these types describe the parsed/coerced shape.

export interface Member {
  name: string;
  email: string;
}

// One submission from the hackathon API, persisted to work/submissions.json by
// scan.py and keyed here by the derived repo_id.
export interface SubmissionInfo {
  repo_id: string;
  teamName: string;
  githubUrl: string;
  liveUrl: string;
  submittedAt: string;
  members: Member[];
}

export interface SummaryRow {
  repo_id: string;
  repo: string;
  default_branch: string;
  t0: string;
  t1: string;
  total_commits: number;
  total_commits_before_t0: number;
  total_commits_during_event: number;
  total_commits_after_t1: number;
  total_loc_added: number;
  total_loc_deleted: number;
  max_loc_added_single_commit: number;
  max_files_changed_single_commit: number;
  median_minutes_between_commits: number;
  median_minutes_between_commits_during_event: number;
  // Every `/^commits_/` column, in file order. Bucket names are config-driven
  // (detection.time_buckets_hours), so they are never hardcoded.
  buckets: Record<string, number>;
  has_commits_before_t0: boolean;
  has_bulk_commits: boolean;
  has_large_initial_commit_after_t0: boolean;
  has_merge_commits: boolean;
}

export interface Metrics {
  repo_id: string;
  repo: string;
  remote_url: string;
  default_branch: string;
  t0: string;
  t1: string | null;
  generated_at: string;
  summary: Record<string, number | null>;
  time_distribution: Record<string, number>; // dynamic keys
  flags: {
    has_commits_before_t0: boolean;
    has_bulk_commits: boolean;
    has_large_initial_commit_after_t0: boolean;
    has_merge_commits: boolean;
  };
}

export interface Commit {
  repo_id: string;
  seq_index: number;
  sha: string;
  author_time_iso: string;
  minutes_since_prev_commit: number | null;
  minutes_since_t0: number | null;
  insertions: number;
  deletions: number;
  files_changed: number;
  is_merge: boolean;
  is_before_t0: boolean;
  is_during_event: boolean;
  is_after_t1: boolean;
  flag_bulk_commit: boolean;
  subject: string;
}

export interface RepoDetail {
  repoId: string;
  metrics: Metrics | null;
  commits: Commit[]; // first 100 for display
  commitsTotal: number; // true count for the "(N)" label
  aiText: string | null;
}

export type DataSourceKind = "env" | "work" | "snapshot" | "empty";

export interface DashboardData {
  rows: SummaryRow[];
  submissions: Record<string, SubmissionInfo>; // keyed by repo_id
  details: Record<string, RepoDetail>;
  source: DataSourceKind;
  generatedAt: string;
}
