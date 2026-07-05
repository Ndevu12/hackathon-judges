import "server-only";
import fs from "node:fs";
import path from "node:path";
import { parseCsv } from "./csv";
import { readRepoConfig } from "./config";
import { isBucketKey } from "./verdict";
import type {
  Commit,
  DashboardData,
  DataSourceKind,
  Metrics,
  RepoDetail,
  SubmissionInfo,
  SummaryRow,
} from "./types";

interface Source {
  summaryCsv: string;
  metricsDir: string;
  aiDir: string;
  submissionsJson: string;
  kind: Exclude<DataSourceKind, "empty">;
}

function toNum(v: string | undefined): number {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function toBool(v: string | undefined): boolean {
  return Number(v) > 0;
}

function numOrNull(v: string | undefined): number | null {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

// Resolve where to read artifacts from, in priority order:
//   1. env override (HJ_DATA_ROOT repo-layout, or HJ_WORK_DIR)
//   2. live work dir from ../config.json (local `npm run dev`)
//   3. committed web/snapshot/ (deployed build, e.g. Vercel)
function resolveDataSource(): Source | null {
  const root = process.env.HJ_DATA_ROOT;
  if (root) {
    return {
      summaryCsv: path.join(root, "work", "summary", "metrics_summary.csv"),
      metricsDir: path.join(root, "work", "metrics"),
      aiDir: path.join(root, "work", "ai_outputs"),
      submissionsJson: path.join(root, "work", "submissions.json"),
      kind: "env",
    };
  }
  const workDir = process.env.HJ_WORK_DIR;
  if (workDir) {
    return {
      summaryCsv: path.join(workDir, "summary", "metrics_summary.csv"),
      metricsDir: path.join(workDir, "metrics"),
      aiDir: path.join(workDir, "ai_outputs"),
      submissionsJson: path.join(workDir, "submissions.json"),
      kind: "env",
    };
  }

  try {
    const cfg = readRepoConfig();
    if (cfg) {
      const summaryCsv = path.join(cfg.workDir, "summary", "metrics_summary.csv");
      if (fs.existsSync(summaryCsv)) {
        return {
          summaryCsv,
          metricsDir: path.join(cfg.workDir, "metrics"),
          aiDir: path.join(cfg.workDir, "ai_outputs"),
          submissionsJson: path.join(cfg.workDir, "submissions.json"),
          kind: "work",
        };
      }
    }
  } catch {
    // Missing/invalid ../config.json (e.g. on Vercel) — fall through to snapshot.
  }

  const snap = path.join(process.cwd(), "snapshot");
  if (fs.existsSync(path.join(snap, "summary", "metrics_summary.csv"))) {
    return {
      summaryCsv: path.join(snap, "summary", "metrics_summary.csv"),
      metricsDir: path.join(snap, "metrics"),
      aiDir: path.join(snap, "ai_outputs"),
      submissionsJson: path.join(snap, "submissions.json"),
      kind: "snapshot",
    };
  }
  return null;
}

function parseSummaryRow(r: Record<string, string>): SummaryRow {
  const buckets: Record<string, number> = {};
  for (const [k, v] of Object.entries(r)) {
    if (isBucketKey(k)) buckets[k] = toNum(v);
  }
  return {
    repo_id: r.repo_id ?? "",
    repo: r.repo ?? "",
    default_branch: r.default_branch ?? "",
    t0: r.t0 ?? "",
    t1: r.t1 ?? "",
    total_commits: toNum(r.total_commits),
    total_commits_before_t0: toNum(r.total_commits_before_t0),
    total_commits_during_event: toNum(r.total_commits_during_event),
    total_commits_after_t1: toNum(r.total_commits_after_t1),
    total_loc_added: toNum(r.total_loc_added),
    total_loc_deleted: toNum(r.total_loc_deleted),
    max_loc_added_single_commit: toNum(r.max_loc_added_single_commit),
    max_files_changed_single_commit: toNum(r.max_files_changed_single_commit),
    median_minutes_between_commits: toNum(r.median_minutes_between_commits),
    median_minutes_between_commits_during_event: toNum(
      r.median_minutes_between_commits_during_event,
    ),
    buckets,
    has_commits_before_t0: toBool(r.has_commits_before_t0),
    has_bulk_commits: toBool(r.has_bulk_commits),
    has_large_initial_commit_after_t0: toBool(r.has_large_initial_commit_after_t0),
    has_merge_commits: toBool(r.has_merge_commits),
  };
}

function parseCommit(r: Record<string, string>): Commit {
  return {
    repo_id: r.repo_id ?? "",
    seq_index: toNum(r.seq_index),
    sha: r.sha ?? "",
    author_time_iso: r.author_time_iso ?? "",
    minutes_since_prev_commit: numOrNull(r.minutes_since_prev_commit),
    minutes_since_t0: numOrNull(r.minutes_since_t0),
    insertions: toNum(r.insertions),
    deletions: toNum(r.deletions),
    files_changed: toNum(r.files_changed),
    is_merge: toBool(r.is_merge),
    is_before_t0: toBool(r.is_before_t0),
    is_during_event: toBool(r.is_during_event),
    is_after_t1: toBool(r.is_after_t1),
    flag_bulk_commit: toBool(r.flag_bulk_commit),
    subject: r.subject ?? "",
  };
}

// Read work/submissions.json (an array written by scan.py) into a map keyed by
// repo_id: team name, live URL, and members.
function readSubmissions(submissionsJson: string): Record<string, SubmissionInfo> {
  const map: Record<string, SubmissionInfo> = {};
  try {
    if (submissionsJson && fs.existsSync(submissionsJson)) {
      const data = JSON.parse(fs.readFileSync(submissionsJson, "utf8"));
      for (const rec of Array.isArray(data) ? data : []) {
        if (!rec?.repo_id) continue;
        map[rec.repo_id] = {
          repo_id: rec.repo_id,
          teamName: rec.teamName ?? "",
          githubUrl: rec.githubUrl ?? "",
          liveUrl: rec.liveUrl ?? "",
          submittedAt: rec.submittedAt ?? "",
          members: Array.isArray(rec.members)
            ? rec.members.map((m: { name?: string; email?: string }) => ({
                name: m.name ?? "",
                email: m.email ?? "",
              }))
            : [],
        };
      }
    }
  } catch {
    // ignore malformed submissions data
  }
  return map;
}

function readDetail(src: Source, id: string): RepoDetail {
  let metrics: Metrics | null = null;
  try {
    const p = path.join(src.metricsDir, `${id}.json`);
    if (fs.existsSync(p)) metrics = JSON.parse(fs.readFileSync(p, "utf8")) as Metrics;
  } catch {
    /* tolerate missing/partial metrics */
  }

  let commits: Commit[] = [];
  let commitsTotal = 0;
  try {
    const p = path.join(src.metricsDir, `${id}_commits.csv`);
    if (fs.existsSync(p)) {
      const all = parseCsv(fs.readFileSync(p, "utf8"));
      commitsTotal = all.length;
      commits = all.slice(0, 100).map(parseCommit);
    }
  } catch {
    /* tolerate missing/partial commits */
  }

  let aiText: string | null = null;
  try {
    const p = path.join(src.aiDir, `${id}.txt`);
    if (fs.existsSync(p)) aiText = fs.readFileSync(p, "utf8");
  } catch {
    /* tolerate missing AI note */
  }

  return { repoId: id, metrics, commits, commitsTotal, aiText };
}

// Reads all artifacts and returns one serializable dataset. Runs at build time
// (force-static) in prod and per-request in dev, so `npm run dev` reflects the
// latest scan.py run while a deploy is a frozen snapshot.
export function getDashboardData(): DashboardData {
  const generatedAt = new Date().toISOString();
  const src = resolveDataSource();

  if (!src || !fs.existsSync(src.summaryCsv)) {
    return { rows: [], submissions: {}, details: {}, source: "empty", generatedAt };
  }

  const rows = parseCsv(fs.readFileSync(src.summaryCsv, "utf8")).map(parseSummaryRow);
  const submissions = readSubmissions(src.submissionsJson);
  const details: Record<string, RepoDetail> = {};
  for (const row of rows) {
    if (row.repo_id) details[row.repo_id] = readDetail(src, row.repo_id);
  }

  return { rows, submissions, details, source: src.kind, generatedAt };
}
