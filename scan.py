#!/usr/bin/env python3
"""
Hackathon GitHub Repo Analyzer
"""

import argparse
import csv
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_config import (  # noqa: E402
    bucket_index,
    get_bucket_keys,
    load_config,
    override_from_cli,
    validate_buckets,
)
from hackathon_api import (  # noqa: E402
    HackathonApiError,
    build_submission_records,
    fetch_public,
    resolve_api_key,
)


def parse_iso_datetime(value: str) -> datetime:
    """Parse ISO datetime string and ensure timezone-aware (default UTC)."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def ensure_work_dirs(work_dir: Path) -> Dict[str, Path]:
    paths = {
        "repos": work_dir / "repos",
        "metrics": work_dir / "metrics",
        "summary": work_dir / "summary",
        "ai_outputs": work_dir / "ai_outputs",
        "logs": work_dir / "logs",
    }
    for p in paths.values():
        p.mkdir(parents=True, exist_ok=True)
    return paths


def setup_logging(log_level: str, log_dir: Path) -> logging.Logger:
    logger = logging.getLogger("scan")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "scan.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def run_git_command(repo_dir: Path, args: List[str]) -> subprocess.CompletedProcess:
    cmd = ["git", "-C", str(repo_dir)] + args
    return subprocess.run(cmd, capture_output=True, text=True)


def get_default_branch(repo_dir: Path) -> str:
    result = run_git_command(repo_dir, ["symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
    if result.returncode == 0:
        ref = result.stdout.strip()
        if ref.startswith("origin/"):
            return ref[len("origin/") :]
        return ref
    result = run_git_command(repo_dir, ["rev-parse", "--abbrev-ref", "HEAD"])
    result.check_returncode()
    return result.stdout.strip()


def parse_repo_url(raw: str) -> Tuple[str, str]:
    """
    Normalize a repo URL/slug to (owner/repo slug, clone_url candidate).
    Accepts GitHub page URL, HTTPS .git, SSH git@github.com:owner/repo.git, or slug owner/repo.
    """
    if not raw:
        raise ValueError("Empty repo URL")
    trimmed = raw.strip()
    if trimmed.startswith("git@github.com:"):
        path_part = trimmed.split(":", 1)[1]
    elif "://" in trimmed:
        # Strip scheme/host
        after_scheme = trimmed.split("://", 1)[1]
        # Remove possible username@host/
        if "/" in after_scheme:
            path_part = after_scheme.split("/", 1)[1]
        else:
            raise ValueError(f"Could not parse repo URL: {raw}")
    else:
        path_part = trimmed

    path_part = path_part.strip("/")
    if path_part.endswith(".git"):
        path_part = path_part[:-4]
    parts = path_part.split("/")
    if len(parts) < 2:
        raise ValueError(f"Could not extract owner/repo from: {raw}")
    owner, repo = parts[0], parts[1]
    slug = f"{owner}/{repo}"
    clone_url = raw if ("://" in trimmed or trimmed.startswith("git@")) else f"https://github.com/{slug}.git"
    return slug, clone_url


def ensure_cloned(repo_id: str, repo_spec: str, repos_root: Path, update: bool = True) -> Path:
    repo_dir = repos_root / repo_id
    if not repo_dir.exists():
        if "://" in repo_spec:
            clone_url = repo_spec
        else:
            clone_url = f"https://github.com/{repo_spec}.git"
        result = subprocess.run(["git", "clone", clone_url, str(repo_dir)], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"git clone failed for {repo_id}: {result.stderr.strip()}")
    else:
        if update:
            fetch = run_git_command(repo_dir, ["fetch", "--all", "--prune"])
            if fetch.returncode != 0:
                raise RuntimeError(f"git fetch failed for {repo_id}: {fetch.stderr.strip()}")
            default_branch = get_default_branch(repo_dir)
            checkout = run_git_command(repo_dir, ["checkout", default_branch])
            if checkout.returncode != 0:
                raise RuntimeError(f"git checkout failed for {repo_id}: {checkout.stderr.strip()}")
            reset = run_git_command(repo_dir, ["reset", "--hard", f"origin/{default_branch}"])
            if reset.returncode != 0:
                raise RuntimeError(f"git reset failed for {repo_id}: {reset.stderr.strip()}")
    return repo_dir


def collect_commit_data(repo_dir: Path, default_branch: str) -> List[Dict]:
    checkout = run_git_command(repo_dir, ["checkout", default_branch])
    if checkout.returncode != 0:
        raise RuntimeError(f"git checkout {default_branch} failed: {checkout.stderr.strip()}")
    log_cmd = [
        "log",
        "--reverse",
        "--pretty=format:%H%x1f%aI%x1f%an%x1f%ae%x1f%P%x1f%s",
        "--numstat",
    ]
    result = run_git_command(repo_dir, log_cmd)
    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr.strip()}")

    commits: List[Dict] = []
    current: Optional[Dict] = None

    for line in result.stdout.splitlines():
        if not line.strip():
            if current is not None:
                commits.append(current)
                current = None
            continue
        if current is None:
            parts = line.split("\x1f")
            if len(parts) != 6:
                raise RuntimeError("Unexpected git log format")
            sha, author_iso, author_name, author_email, parents_raw, subject = parts
            parents = parents_raw.split() if parents_raw.strip() else []
            current = {
                "sha": sha,
                "author_time": parse_iso_datetime(author_iso),
                "author_name": author_name,
                "author_email": author_email,
                "parents": parents,
                "is_merge": len(parents) > 1,
                "subject": subject,
                "insertions": 0,
                "deletions": 0,
                "files_changed": 0,
            }
            continue
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        ins_raw, del_raw, _path = fields
        insertions = int(ins_raw) if ins_raw.isdigit() else 0
        deletions = int(del_raw) if del_raw.isdigit() else 0
        current["insertions"] += insertions
        current["deletions"] += deletions
        current["files_changed"] += 1

    if current is not None:
        commits.append(current)
    return commits


def compute_metrics(
    commits: List[Dict],
    t0: datetime,
    t1: Optional[datetime],
    bulk_insertion_threshold: int,
    bulk_files_threshold: int,
    bucket_boundaries: List,
) -> Dict:
    commits_enriched = []
    minutes_between_all = []
    minutes_between_event = []
    event_prev_time: Optional[datetime] = None

    for idx, commit in enumerate(commits):
        prev_time = commits[idx - 1]["author_time"] if idx > 0 else None
        minutes_since_prev = None
        if prev_time:
            minutes_since_prev = (commit["author_time"] - prev_time).total_seconds() / 60.0
            minutes_between_all.append(minutes_since_prev)

        if t1:
            is_during = t0 <= commit["author_time"] <= t1
            is_after_t1 = commit["author_time"] > t1
        else:
            is_during = commit["author_time"] >= t0
            is_after_t1 = False
        is_before_t0 = commit["author_time"] < t0

        if is_during and event_prev_time:
            minutes_between_event.append(
                (commit["author_time"] - event_prev_time).total_seconds() / 60.0
            )
        if is_during:
            event_prev_time = commit["author_time"]

        flag_bulk = (
            commit["insertions"] >= bulk_insertion_threshold
            or commit["files_changed"] >= bulk_files_threshold
        )

        commits_enriched.append(
            {
                **commit,
                "minutes_since_prev_commit": minutes_since_prev,
                "minutes_since_t0": (commit["author_time"] - t0).total_seconds() / 60.0,
                "is_before_t0": is_before_t0,
                "is_during_event": is_during,
                "is_after_t1": is_after_t1,
                "flag_bulk_commit": flag_bulk,
            }
        )

    def safe_median(values: List[float]) -> Optional[float]:
        return median(values) if values else None

    total_commits = len(commits_enriched)
    total_commits_before_t0 = sum(1 for c in commits_enriched if c["is_before_t0"])
    total_commits_during_event = sum(1 for c in commits_enriched if c["is_during_event"])
    total_commits_after_t1 = sum(1 for c in commits_enriched if c["is_after_t1"])

    total_loc_added = sum(c["insertions"] for c in commits_enriched)
    total_loc_deleted = sum(c["deletions"] for c in commits_enriched)
    max_loc_added_single_commit = max((c["insertions"] for c in commits_enriched), default=0)
    max_files_changed_single_commit = max((c["files_changed"] for c in commits_enriched), default=0)

    bucket_keys = get_bucket_keys(bucket_boundaries)
    buckets = {key: 0 for key in bucket_keys}

    for c in commits_enriched:
        if not c["is_during_event"]:
            continue
        hours = (c["author_time"] - t0).total_seconds() / 3600.0
        if hours < 0:
            continue
        buckets[bucket_keys[bucket_index(hours, bucket_boundaries)]] += 1

    first_during = next((c for c in commits_enriched if c["is_during_event"]), None)
    has_large_initial_commit_after_t0 = bool(first_during and first_during["flag_bulk_commit"])

    metrics = {
        "summary": {
            "total_commits": total_commits,
            "total_commits_before_t0": total_commits_before_t0,
            "total_commits_during_event": total_commits_during_event,
            "total_commits_after_t1": total_commits_after_t1,
            "total_loc_added": total_loc_added,
            "total_loc_deleted": total_loc_deleted,
            "max_loc_added_single_commit": max_loc_added_single_commit,
            "max_files_changed_single_commit": max_files_changed_single_commit,
            "median_minutes_between_commits": safe_median(minutes_between_all),
            "median_minutes_between_commits_during_event": safe_median(minutes_between_event),
        },
        "time_distribution": buckets,
        "flags": {
            "has_commits_before_t0": total_commits_before_t0 > 0,
            "has_bulk_commits": any(
                c["flag_bulk_commit"] and c["is_during_event"] for c in commits_enriched
            ),
            "has_large_initial_commit_after_t0": has_large_initial_commit_after_t0,
            "has_merge_commits": any(c["is_merge"] for c in commits_enriched),
        },
        "commits": commits_enriched,
    }
    return metrics


def write_commit_csv(path: Path, repo_id: str, commits: List[Dict]) -> None:
    fieldnames = [
        "repo_id",
        "seq_index",
        "sha",
        "author_time_iso",
        "minutes_since_prev_commit",
        "minutes_since_t0",
        "insertions",
        "deletions",
        "files_changed",
        "is_merge",
        "is_before_t0",
        "is_during_event",
        "is_after_t1",
        "flag_bulk_commit",
        "subject",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for idx, c in enumerate(commits):
            writer.writerow(
                {
                    "repo_id": repo_id,
                    "seq_index": idx,
                    "sha": c["sha"],
                    "author_time_iso": c["author_time"].isoformat(),
                    "minutes_since_prev_commit": (
                        f"{c['minutes_since_prev_commit']:.2f}"
                        if c["minutes_since_prev_commit"] is not None
                        else ""
                    ),
                    "minutes_since_t0": f"{c['minutes_since_t0']:.2f}",
                    "insertions": c["insertions"],
                    "deletions": c["deletions"],
                    "files_changed": c["files_changed"],
                    "is_merge": 1 if c["is_merge"] else 0,
                    "is_before_t0": 1 if c["is_before_t0"] else 0,
                    "is_during_event": 1 if c["is_during_event"] else 0,
                    "is_after_t1": 1 if c["is_after_t1"] else 0,
                    "flag_bulk_commit": 1 if c["flag_bulk_commit"] else 0,
                    "subject": c["subject"],
                }
            )


def write_metrics_json(
    path: Path,
    repo_id: str,
    repo_spec: str,
    remote_url: str,
    default_branch: str,
    t0: datetime,
    t1: Optional[datetime],
    metrics: Dict,
) -> None:
    output = {
        "repo_id": repo_id,
        "repo": repo_spec,
        "remote_url": remote_url,
        "default_branch": default_branch,
        "t0": t0.isoformat(),
        "t1": t1.isoformat() if t1 else None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": metrics["summary"],
        "time_distribution": metrics["time_distribution"],
        "flags": metrics["flags"],
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)


def write_summary_csv(path: Path, rows: List[Dict], bucket_keys: List[str]) -> None:
    fieldnames = [
        "repo_id",
        "repo",
        "default_branch",
        "t0",
        "t1",
        "total_commits",
        "total_commits_before_t0",
        "total_commits_during_event",
        "total_commits_after_t1",
        "total_loc_added",
        "total_loc_deleted",
        "max_loc_added_single_commit",
        "max_files_changed_single_commit",
        "median_minutes_between_commits",
        "median_minutes_between_commits_during_event",
        *bucket_keys,
        "has_commits_before_t0",
        "has_bulk_commits",
        "has_large_initial_commit_after_t0",
        "has_merge_commits",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            cleaned = {k: ("" if v is None else v) for k, v in row.items()}
            writer.writerow(cleaned)


def build_repo_rows(
    records: List[Dict], logger: logging.Logger
) -> Tuple[List[Dict], List[Dict]]:
    """Turn API submission records into analyzer rows + an enriched manifest.

    Returns ``(rows, manifest)``: ``rows`` drive cloning/metrics; ``manifest``
    is persisted to ``work/submissions.json`` for the dashboards (team name,
    live URL, members).
    """
    rows: List[Dict] = []
    manifest: List[Dict] = []
    seen: set = set()
    for rec in records:
        try:
            slug, clone_url = parse_repo_url(rec["githubUrl"])
        except ValueError as exc:
            logger.warning("Skipping submission %r: %s", rec.get("teamName"), exc)
            continue
        repo_id = slug.replace("/", "-")
        if repo_id in seen:
            logger.warning(
                "Duplicate repo %s (team %r); keeping first.", repo_id, rec.get("teamName")
            )
            continue
        seen.add(repo_id)
        rows.append({"repo_id": repo_id, "repo_spec": clone_url or slug, "slug": slug, "t0": ""})
        manifest.append({"repo_id": repo_id, **rec})
    return rows, manifest


def build_summary_row(
    repo_id: str,
    repo_spec: str,
    default_branch: str,
    metrics: Dict,
    bucket_keys: List[str],
) -> Dict:
    summary = metrics["summary"]
    time_dist = metrics["time_distribution"]
    flags = metrics["flags"]
    row = {
        "repo_id": repo_id,
        "repo": repo_spec,
        "default_branch": default_branch,
        "t0": metrics.get("t0"),
        "t1": metrics.get("t1"),
        "total_commits": summary["total_commits"],
        "total_commits_before_t0": summary["total_commits_before_t0"],
        "total_commits_during_event": summary["total_commits_during_event"],
        "total_commits_after_t1": summary["total_commits_after_t1"],
        "total_loc_added": summary["total_loc_added"],
        "total_loc_deleted": summary["total_loc_deleted"],
        "max_loc_added_single_commit": summary["max_loc_added_single_commit"],
        "max_files_changed_single_commit": summary["max_files_changed_single_commit"],
        "median_minutes_between_commits": summary["median_minutes_between_commits"],
        "median_minutes_between_commits_during_event": summary[
            "median_minutes_between_commits_during_event"
        ],
    }
    for key in bucket_keys:
        row[key] = time_dist.get(key, 0)
    row["has_commits_before_t0"] = 1 if flags["has_commits_before_t0"] else 0
    row["has_bulk_commits"] = 1 if flags["has_bulk_commits"] else 0
    row["has_large_initial_commit_after_t0"] = (
        1 if flags["has_large_initial_commit_after_t0"] else 0
    )
    row["has_merge_commits"] = 1 if flags["has_merge_commits"] else 0
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Hackathon GitHub Repo Analyzer")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--api-key", help="Hackathon API key (overrides the HACKATHON_API_KEY env var)")
    parser.add_argument("--t0", help="Global hackathon start time (ISO-8601). Overrides config if set.")
    parser.add_argument("--t1", help="Hackathon end time (ISO-8601). Overrides config if set.")
    parser.add_argument("--work-dir", help="Work directory base path (default: paths.work_dir from config)")
    parser.add_argument("--no-update", action="store_true", help="Do not fetch/pull existing clones")
    parser.add_argument("--force", action="store_true", help="Recompute metrics even if cached")
    parser.add_argument("--log-level", help="Logging level (overrides config)")
    parser.add_argument(
        "--bulk-insertion-threshold", type=int,
        help="Override detection.bulk_insertion_threshold",
    )
    parser.add_argument(
        "--bulk-files-threshold", type=int,
        help="Override detection.bulk_files_threshold",
    )
    parser.add_argument(
        "--time-buckets",
        help="Comma-separated ascending hour boundaries (overrides detection.time_buckets_hours)",
    )
    args = parser.parse_args()

    config = load_config(Path(args.config) if args.config else None)

    time_buckets = None
    if args.time_buckets:
        try:
            time_buckets = [
                float(part) if "." in part else int(part)
                for part in (piece.strip() for piece in args.time_buckets.split(","))
                if part
            ]
        except ValueError:
            parser.error(f"Invalid --time-buckets value: {args.time_buckets!r}")

    # Precedence: CLI flags (non-None) > config.json > built-in defaults.
    override_from_cli(
        config,
        {
            "window.t0": args.t0,
            "window.t1": args.t1,
            "log_level": args.log_level,
            "paths.work_dir": args.work_dir,
            "detection.bulk_insertion_threshold": args.bulk_insertion_threshold,
            "detection.bulk_files_threshold": args.bulk_files_threshold,
            "detection.time_buckets_hours": time_buckets,
        },
    )

    work_dir = Path(config["paths"]["work_dir"])
    dirs = ensure_work_dirs(work_dir)
    log_level = config.get("log_level") or "INFO"
    logger = setup_logging(log_level, dirs["logs"])

    boundaries = config["detection"]["time_buckets_hours"]
    try:
        validate_buckets(boundaries)
    except ValueError as exc:
        logger.error("Invalid time buckets: %s", exc)
        return
    bucket_keys = get_bucket_keys(boundaries)
    bulk_insertion_threshold = config["detection"]["bulk_insertion_threshold"]
    bulk_files_threshold = config["detection"]["bulk_files_threshold"]

    t0_value = config["window"]["t0"]
    if not t0_value:
        logger.error("Global t0 is required (provide via --t0 or config window.t0).")
        return
    try:
        global_t0 = parse_iso_datetime(t0_value)
    except Exception as exc:
        logger.error("Failed to parse global t0: %s", exc)
        return
    global_t1 = None
    t1_value = config["window"]["t1"]
    if t1_value:
        try:
            global_t1 = parse_iso_datetime(t1_value)
        except Exception as exc:
            logger.error("Failed to parse global t1: %s", exc)
            return

    try:
        api_key = resolve_api_key(args.api_key)
        public = fetch_public(config, api_key)
    except HackathonApiError as exc:
        logger.error("%s", exc)
        return
    rows, manifest = build_repo_rows(build_submission_records(public), logger)
    if not rows:
        logger.warning("No submissions with a GitHub URL returned by the API.")
        return
    submissions_path = work_dir / "submissions.json"
    with submissions_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    logger.info("Fetched %d submissions from the API.", len(rows))

    summary_rows = []

    for row in rows:
        repo_id = row["repo_id"]
        repo_spec = row["repo_spec"]
        t0_value = row.get("t0", "")
        try:
            repo_t0 = parse_iso_datetime(t0_value) if t0_value else global_t0
        except Exception as exc:
            logger.error("Invalid t0 for repo %s: %s", repo_id, exc)
            continue
        repo_t1 = global_t1

        metrics_json_path = dirs["metrics"] / f"{repo_id}.json"
        commits_csv_path = dirs["metrics"] / f"{repo_id}_commits.csv"

        metrics_data = None
        default_branch = None

        if metrics_json_path.exists() and not args.force:
            logger.info("Skipping %s (cached metrics found; use --force to recompute).", repo_id)
            try:
                with metrics_json_path.open("r", encoding="utf-8") as f:
                    metrics_data = json.load(f)
                    default_branch = metrics_data.get("default_branch")
            except Exception as exc:
                logger.error("Failed to load cached metrics for %s: %s", repo_id, exc)
                continue
        else:
            try:
                repo_dir = ensure_cloned(repo_id, repo_spec, dirs["repos"], update=not args.no_update)
                default_branch = get_default_branch(repo_dir)
                commits = collect_commit_data(repo_dir, default_branch)
                metrics = compute_metrics(
                    commits,
                    repo_t0,
                    repo_t1,
                    bulk_insertion_threshold,
                    bulk_files_threshold,
                    boundaries,
                )
                remote_url_result = run_git_command(repo_dir, ["config", "--get", "remote.origin.url"])
                remote_url = remote_url_result.stdout.strip() if remote_url_result.returncode == 0 else ""
                write_commit_csv(commits_csv_path, repo_id, metrics["commits"])
                write_metrics_json(
                    metrics_json_path,
                    repo_id,
                    repo_spec,
                    remote_url,
                    default_branch,
                    repo_t0,
                    repo_t1,
                    metrics,
                )
                metrics_data = {
                    **metrics,
                    "repo_id": repo_id,
                    "repo": repo_spec,
                    "default_branch": default_branch,
                    "t0": repo_t0.isoformat(),
                    "t1": repo_t1.isoformat() if repo_t1 else None,
                }
                logger.info("Processed %s with %d commits.", repo_id, len(commits))
            except Exception as exc:
                logger.error("Failed processing %s: %s", repo_id, exc)
                continue

        if metrics_data:
            summary_rows.append(
                build_summary_row(
                    repo_id, repo_spec, default_branch or "", metrics_data, bucket_keys
                )
            )

    if summary_rows:
        summary_path = dirs["summary"] / "metrics_summary.csv"
        write_summary_csv(summary_path, summary_rows, bucket_keys)
        logger.info("Wrote summary CSV to %s", summary_path)
    else:
        logger.warning("No summary rows generated.")


if __name__ == "__main__":
    main()
