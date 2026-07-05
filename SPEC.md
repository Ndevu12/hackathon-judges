````markdown
# SPEC: Hackathon GitHub Repo Analyzer

Local tool to analyze GitHub repositories for a hackathon and surface:
- Static, objective metrics and flags about commit history and activity.
- Optional structured AI authenticity analysis via Claude — either the Claude Code CLI on a Pro/Max subscription (default) or the Claude API.

The tool is designed for:
- macOS
- Local, offline-first usage
- ≤ 100 repositories
- GitHub-only repos (public or private if the user has read access)

---

## 1. Goals

1. Enforce rule: **No code before T0**  
   - T0 = hackathon start time (single global T0, with optional per-repo override).
   - If any commit before T0 exists, **raise a red flag** for that metric (do not auto-disqualify).

2. Provide **per-repo and per-commit metrics** that judges can inspect:
   - Commit timing and velocity.
   - Per-commit LOC and file change statistics.
   - Flags for suspicious patterns (e.g., huge bulk commits).

3. Provide **easy cross-repo comparison**:
   - One summary CSV with key metrics and flags per repo.

4. Provide an optional **structured AI report** per repo:
   - Uses Claude via a pluggable provider (subscription CLI by default, or the API).
   - Outputs `work/ai_outputs/<repo_id>.json` (+ a human-readable `.txt`) for the dashboard and human review.

5. Support **caching and resuming**:
   - Repos are cloned into a local folder and reused.
   - Metrics for already-processed repos are not recomputed unless forced.
   - New repos can be appended to the CSV and analyzed incrementally.

---

## 2. Non-Goals

- No automatic disqualification decisions.
- No complex scoring system; judges interpret metrics/flags.
- No web service or UI; this is a CLI-only, local tool.
- No attempt at language-specific static analysis or plagiarism detection beyond generic metrics.

---

## 3. Directory Layout

Implement the tool assuming the following repository structure:

```text
hackathon-analyzer/
  SPEC.md                     # this spec
  scan.py                     # main static analyzer CLI
  hackathon_api.py            # public-API client (teams + submissions)
  ai/
    run_ai.py                 # optional: AI analysis orchestrator
    providers.py              # pluggable AI backends (claude_code | anthropic)
    hackathon_context.md      # editable hackathon description/context
    prompt_template.txt       # LLM prompt template with placeholders
  # No data/ inputs — repos + teams come from the hackathon API (hackathon_api.py).
  work/
    repos/                    # cloned GitHub repositories (cache)
    metrics/                  # per-repo metrics JSON + commit CSVs
    summary/
      metrics_summary.csv     # cross-repo summary for judges
    ai_outputs/               # per-repo AI analysis outputs
    logs/
      scan.log                # optional log file
````

All paths under `work/` should be created automatically if missing.

---

## 4. Dependencies

Assume the following environment:

* OS: macOS
* Required tools:

  * `python3` (≥ 3.10)
  * `git` (available in PATH)
* Optional (AI analysis) — pick one:

  * **Subscription (default, `ai.provider = claude_code`):** the **Claude Code CLI** (`claude`) installed and signed in to a Pro/Max account. Command form: `claude -p --output-format json --json-schema '<SCHEMA>' --model <MODEL> --system-prompt '<SYS>' --tools "" --no-session-persistence` with the prompt on stdin.
  * **API (`ai.provider = anthropic`):** `pip install anthropic` and `ANTHROPIC_API_KEY`.
* Python dependencies: the core CLI (`scan.py`, `hackathon_api.py`, `list_submissions.py`) is standard-library only (`argparse`, `json`, `subprocess`, `urllib`, `datetime`, `statistics`, `os`, `pathlib`, `logging`). Only the `anthropic` AI provider needs a third-party package.

---

## Configuration (`config.json`)

All scripts load a shared, sectioned `config.json` via `common_config.py`.
Precedence is **CLI flag → `config.json` → built-in default**; every setting has
a default, so a partial or absent config still works. Legacy flat configs
(`{"t0","t1","log_level"}`) are promoted into the `window` section automatically.

Sections: `window` (t0/t1), `log_level`, `api` (`base_url`, `public_endpoint`;
the key comes from `HACKATHON_API_KEY`, never config), `paths` (`work_dir`,
`ai_context`, `ai_prompt_template`), `detection` (`bulk_insertion_threshold`,
`bulk_files_threshold`, `time_buckets_hours`), and `ai` (see §13).

**Time buckets are derived, not fixed.** `detection.time_buckets_hours` is a list
of ascending hour boundaries `[b1, b2, …]`. The time-distribution keys become
`commits_0_b1h, commits_b1_b2h, …, commits_after_bNh`. The default `[3, 6, 12, 24]`
reproduces the legacy `commits_0_3h … commits_after_24h` schema exactly. Empty or
non-ascending lists are rejected.

---

## 5. Input: the hackathon public API

Submissions and teams come from the event site's public API (`api.base_url` +
`/api/public`); there are no local input files. The key is supplied via the
`HACKATHON_API_KEY` env var (or `--api-key`) and sent as the `X-Api-Key` header.

`scan.py` fetches `/api/public`, then for each submission:

* derives `repo_id = owner-repo` from `githubUrl` (via `parse_repo_url`);
* joins the submission to its team (`teamId` → `team.id`/`team.mergedFrom`, with a
  `teamName` fallback) to collect member names/emails;
* writes an enriched manifest to `work/submissions.json`
  (`[{repo_id, teamName, githubUrl, liveUrl, submittedAt, members}]`) that the
  dashboard reads for team + live-URL columns.

The global `t0`/`t1` still come from `config.json` (or `--t0/--t1`).

---

## 6. CLI: `scan.py`

### 6.1 Usage

```bash
python3 scan.py \
  --repos data/repos.csv \
  --t0 2025-12-01T10:00:00Z \
  --work-dir work \
  [--t1 2025-12-02T10:00:00Z] \
  [--force] \
  [--no-update] \
  [--log-level INFO]
```

Arguments:

* `--repos PATH` (required)
  Path to repos CSV (`data/repos.csv`).

* `--t0 ISO_DATETIME` (required)
  Global hackathon start time (e.g., `2025-12-01T10:00:00Z`).

  * Used for all repos unless a row has its own `t0` column.
  * Parse as ISO-8601. If no timezone, assume UTC.

* `--t1 ISO_DATETIME` (optional)
  Hackathon end time. Used for “during event” vs “after event” metrics. If omitted:

  * `commits_during_event` = commits with timestamp ≥ T0.
  * `commits_after_event` = 0.

* `--work-dir PATH` (optional, default: `work`)
  Base work directory; contains `repos/`, `metrics/`, `summary/`, `logs/`.

* `--force` (optional)
  If set, recompute metrics for all repos even if metrics file already exists.

* `--no-update` (optional)
  If set, do **not** call `git fetch`/`git pull` for existing clones; use them as-is.

* `--log-level LEVEL` (optional, default: `INFO`)
  Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`).

### 6.2 Behavior Overview

For each row in `repos.csv`:

1. Resolve `repo_id` and `repo_spec` (`id` and `repo` columns).
2. Determine effective `t0`:

   * If row has `t0` column and it is non-empty → use it.
   * Else → use global `--t0`.
3. Skip if `metrics/<repo_id>.json` already exists AND `--force` is not set.
4. Ensure repo is cloned in `work/repos/<repo_id>/`.
5. Determine default branch.
6. Extract commit data from default branch (chronological).
7. Compute metrics and flags.
8. Write:

   * `work/metrics/<repo_id>.json` (summary metrics).
   * `work/metrics/<repo_id>_commits.csv` (per-commit stats).
9. After all repos are processed, write cross-repo:

   * `work/summary/metrics_summary.csv`.

This design naturally supports:

* Stopping and re-running (already-processed repos are skipped).
* Adding new rows to `repos.csv` later.

---

## 7. Cloning and Caching

### 7.1 Repo directory

For a repo with `id = team-alpha`:

* Clone / use: `work/repos/team-alpha/`

### 7.2 Cloning logic

Function: `ensure_cloned(repo_id, repo_spec, repos_root, update=True) -> Path`

1. Compute `repo_dir = repos_root / repo_id`.
2. If `repo_dir` does **not** exist:

   * Determine clone URL:

     * If `repo_spec` contains `"://"` → use as-is.
     * Else → treat as slug:

       * `clone_url = f"https://github.com/{repo_spec}.git"`
   * Run: `git clone <clone_url> <repo_dir>`
3. If `repo_dir` exists:

   * If `update` is `True`:

     * `git -C <repo_dir> fetch --all --prune`
     * Determine default branch (see below).
     * Checkout and hard reset:

       * `git -C <repo_dir> checkout <default_branch>`
       * `git -C <repo_dir> reset --hard origin/<default_branch>`

### 7.3 Default branch detection

Function: `get_default_branch(repo_dir) -> str`

Algorithm:

1. Try:

   * `git -C <repo_dir> symbolic-ref --short refs/remotes/origin/HEAD`
     Example output: `origin/main`
   * If this succeeds, strip `origin/` prefix to get `main`.
2. If that fails:

   * Fallback to `git -C <repo_dir> rev-parse --abbrev-ref HEAD`.

---

## 8. Commit Data Extraction

Function: `collect_commit_data(repo_dir, default_branch) -> List[CommitDict]`

1. Ensure you are on the default branch:

   * `git -C <repo_dir> checkout <default_branch>`
2. Get full commit history in **chronological order** (oldest first):

Use command:

```bash
git -C <repo_dir> log \
  --reverse \
  --pretty=format:'%H%x1f%aI%x1f%an%x1f%ae%x1f%P%x1f%s' \
  --numstat
```

Interpretation:

* Each commit begins with a header line:

  * Fields separated by ASCII `0x1f` (unit separator):

    * `%H`   → commit SHA
    * `%aI`  → author date (ISO-8601)
    * `%an`  → author name
    * `%ae`  → author email
    * `%P`   → parent SHAs (space-separated)
    * `%s`   → subject line
* Followed by `numstat` lines for that commit:

  * `<insertions>\t<deletions>\t<path>`
* Between commits, there is a blank line.

For each commit, compute:

* `sha`                        (string)
* `author_time`                (parsed from `%aI`, timezone-aware)
* `author_name`                (string)
* `author_email`               (string)
* `parents`                    (list of SHAs from `%P`)
* `is_merge`                   (bool, true if len(parents) > 1)
* `subject`                    (string)
* `insertions`                 (int, sum across `numstat` lines, ignoring binary markers like `-`)
* `deletions`                  (int, same as above)
* `files_changed`              (int, count of paths in `numstat`)

Return a Python list of such commit dicts in chronological order.

---

## 9. Metric Computation

Function: `compute_metrics(commits, t0, t1=None) -> MetricsDict`

### 9.1 Time classification

For each commit:

* `is_before_t0` = `commit.author_time < t0`
* If `t1` is provided:

  * `is_during_event` = `t0 <= author_time <= t1`
  * `is_after_t1` = `author_time > t1`
* If `t1` is not provided:

  * `is_during_event` = `author_time >= t0`
  * `is_after_t1` = `False`

Per-commit derived fields:

* `minutes_since_prev_commit`

  * For the first commit: `null`.
  * For others: `(current.author_time - previous.author_time).total_seconds() / 60.0`.

* `minutes_since_t0`

  * `(author_time - t0).total_seconds() / 60.0`
  * Can be negative if before T0.

### 9.2 Bulk commit flag (external code injection heuristic)

Define constants in code:

```python
BULK_INSERTION_THRESHOLD = 1000   # lines
BULK_FILES_THRESHOLD = 50         # files
```

For each commit:

* `flag_bulk_commit` = `True` if:

  * `insertions >= BULK_INSERTION_THRESHOLD` OR
  * `files_changed >= BULK_FILES_THRESHOLD`

Later metrics:

* `has_bulk_commits` = `any(commit.flag_bulk_commit for commit in commits_during_event)`

### 9.3 Repository-level metrics

Compute:

* `total_commits`

* `total_commits_before_t0`

* `total_commits_during_event`

* `total_commits_after_t1` (0 if no `t1`)

* `total_loc_added` (sum of `insertions` across all commits)

* `total_loc_deleted` (sum of `deletions` across all commits)

* `max_loc_added_single_commit`

* `max_files_changed_single_commit`

* `median_minutes_between_commits`

  * Calculate over all `minutes_since_prev_commit` where not `null`.

* `median_minutes_between_commits_during_event`

  * Same, but only for commits where both current and previous are `is_during_event`.

Time distribution relative to T0 (only counting `is_during_event` commits):

Buckets in hours:

* `commits_0_3h`       (0 ≤ Δt < 3h)
* `commits_3_6h`       (3h ≤ Δt < 6h)
* `commits_6_12h`      (6h ≤ Δt < 12h)
* `commits_12_24h`     (12h ≤ Δt < 24h)
* `commits_after_24h`  (Δt ≥ 24h)

Δt = `(author_time - t0).total_seconds() / 3600.0`.

### 9.4 Flags

* `has_commits_before_t0`
  `total_commits_before_t0 > 0`
  (This is the “No code before T0” red-flag metric.)

* `has_bulk_commits`
  `True` if any `flag_bulk_commit` in `is_during_event` commits.

* `has_large_initial_commit_after_t0`
  `True` if:

  * The **first commit that is `is_during_event`** has `flag_bulk_commit == True`.

* `has_merge_commits`
  `True` if any commit has `is_merge == True`.

These flags should be boolean fields.

---

## 10. Per-commit CSV: `work/metrics/<repo_id>_commits.csv`

For each repo, create a CSV with the following columns:

* `repo_id`
* `seq_index`                  (0-based index in chronological order)
* `sha`
* `author_time_iso`            (ISO-8601 string)
* `minutes_since_prev_commit`  (float or empty for first)
* `minutes_since_t0`           (float; can be negative)
* `insertions`
* `deletions`
* `files_changed`
* `is_merge`                   (0 or 1)
* `is_before_t0`               (0 or 1)
* `is_during_event`            (0 or 1)
* `is_after_t1`                (0 or 1)
* `flag_bulk_commit`           (0 or 1)
* `subject`                    (commit subject; safe to keep full string)

This file is intended for judges to inspect commit velocity and patterns directly in a spreadsheet.

---

## 11. Per-repo JSON: `work/metrics/<repo_id>.json`

Example structure:

```json
{
  "repo_id": "team-alpha",
  "repo": "openai/example-repo",
  "remote_url": "https://github.com/openai/example-repo.git",
  "default_branch": "main",
  "t0": "2025-12-01T10:00:00Z",
  "t1": "2025-12-02T10:00:00Z",
  "generated_at": "2025-12-01T15:30:00Z",

  "summary": {
    "total_commits": 23,
    "total_commits_before_t0": 0,
    "total_commits_during_event": 23,
    "total_commits_after_t1": 0,

    "total_loc_added": 4300,
    "total_loc_deleted": 1200,

    "max_loc_added_single_commit": 3000,
    "max_files_changed_single_commit": 80,

    "median_minutes_between_commits": 25.1,
    "median_minutes_between_commits_during_event": 22.5
  },

  "time_distribution": {
    "commits_0_3h": 5,
    "commits_3_6h": 7,
    "commits_6_12h": 8,
    "commits_12_24h": 3,
    "commits_after_24h": 0
  },

  "flags": {
    "has_commits_before_t0": false,
    "has_bulk_commits": true,
    "has_large_initial_commit_after_t0": true,
    "has_merge_commits": false
  }
}
```

Implementation requirements:

* All datetime fields in ISO-8601 with timezone (preferably UTC).
* Use `null` for metrics that cannot be computed (e.g., median with ≤1 commit).

---

## 12. Cross-repo Summary CSV: `work/summary/metrics_summary.csv`

One row per repo with key metrics and flags. Columns:

* `repo_id`

* `repo`

* `default_branch`

* `t0`

* `t1`

* `total_commits`

* `total_commits_before_t0`

* `total_commits_during_event`

* `total_commits_after_t1`

* `total_loc_added`

* `total_loc_deleted`

* `max_loc_added_single_commit`

* `max_files_changed_single_commit`

* `median_minutes_between_commits`

* `median_minutes_between_commits_during_event`

* `commits_0_3h`

* `commits_3_6h`

* `commits_6_12h`

* `commits_12_24h`

* `commits_after_24h`

* `has_commits_before_t0`             (0/1)

* `has_bulk_commits`                  (0/1)

* `has_large_initial_commit_after_t0` (0/1)

* `has_merge_commits`                 (0/1)

This file is the main artifact used by judges to spot deviations across all repos.

---

## 13. AI Analysis (Optional): `ai/run_ai.py` + `ai/providers.py`

### 13.1 Purpose

For each repo with metrics, ask **Claude** for a **structured** authenticity
analysis and write `work/ai_outputs/<repo_id>.json`
(`{verdict, confidence, summary, observations[], red_flags[]}`) plus a
human-readable `<repo_id>.txt`. Structured outputs make the verdict reliable data
the dashboard renders directly (no regex on prose).

The backend is **pluggable** via `ai.provider` (both return the identical schema):

* **`claude_code`** (default) — drives the local **Claude Code CLI**
  (`claude -p --output-format json --json-schema …`) on the user's Claude Pro/Max
  **subscription**. No API key, no per-token API billing; needs the `claude` CLI
  installed and a logged-in account. `ai/providers.py` scrubs `ANTHROPIC_API_KEY`
  from the CLI's environment so it can't silently fall back to API billing.
* **`anthropic`** — calls the Claude API via the official `anthropic` SDK
  (structured output via `output_config.format`). Needs `pip install anthropic`
  and `ANTHROPIC_API_KEY`.

The `ai` section is fully configurable — `provider`, `model` (default
`claude-opus-4-8`), `cli_path`, `cli_timeout`, `base_url`, `max_tokens`, `effort`,
`thinking`, truncation limits. Secrets are never in config: the `anthropic` route
reads `ANTHROPIC_API_KEY` (env or an untracked `.env`); the subscription route
uses the Claude Code login.

### 13.2 Additional input files

* `ai/hackathon_context.md`

  * Free-form markdown text describing the hackathon, rules, goals, and any nuances.
  * Edited by the organizer.

* `ai/prompt_template.txt`

  * Text file with placeholders, all substituted by `build_prompt`:

    * `{{HACKATHON_CONTEXT}}`
    * `{{REPO_ID}}`
    * `{{REPO}}`
    * `{{METRICS_JSON}}`
    * `{{FILE_TREE}}` — truncated repo file tree (`tree_max_entries`/`tree_max_depth`)
    * `{{README_SNIPPET}}` — best README, truncated to `readme_char_limit`
  * The template describes the desired analysis; the **shape** of the output is
    enforced by the structured-output schema (`build_analysis_schema`:
    `verdict`, `confidence`, `summary`, `observations[]`, `red_flags[]`), not by
    the prose — so it does not ask for free-text or a verdict line.

### 13.3 CLI: `ai/run_ai.py`

Usage:

```bash
python3 ai/run_ai.py \
  --config config.json \
  [--provider claude_code|anthropic] \
  [--model claude-opus-4-8] \
  [--only-id team-alpha]
```

Arguments:

* `--config` path to `config.json` (settings resolve CLI > config > default).
* `--work-dir` overrides `paths.work_dir` (default `work`).
* `--provider` / `--model` / `--base-url` / `--api-key` override the `ai` section.
* `--only-id` (optional) if provided, run AI analysis only for that repo id; otherwise run for all repos that have metrics JSON.

Repo → GitHub URL mapping comes from `work/submissions.json` (written by `scan.py` from the API), not a CSV.

### 13.4 Behavior

Build the provider once (`make_provider` dispatches on `ai.provider`), run `preflight()` (e.g. the subscription route checks the `claude` CLI is on PATH), then for each repo:

1. Load `work/metrics/<repo_id>.json`.

2. Read the repo's GitHub URL from `work/submissions.json` (keyed by `repo_id`).

3. Load `ai/hackathon_context.md` and `ai/prompt_template.txt`.

4. Build the file tree + README snippet from the clone under `work/repos/<repo_id>`.

5. Substitute all placeholders (`{{HACKATHON_CONTEXT}}`, `{{REPO_ID}}`, `{{REPO}}`, `{{METRICS_JSON}}`, `{{FILE_TREE}}`, `{{README_SNIPPET}}`) to obtain the final `prompt`.

6. Call `provider.analyze(prompt)`, which returns the validated analysis dict:

   * `claude_code`: `subprocess.run(["claude", "-p", "--output-format", "json", "--model", …, "--system-prompt", …, "--json-schema", …, "--tools", "", "--no-session-persistence"], input=prompt, env=<ANTHROPIC_API_KEY scrubbed>)`, then read `structured_output` from the JSON envelope.
   * `anthropic`: `client.messages.create(..., output_config={"format": {"type": "json_schema", "schema": …}})`, then parse the text block.

7. Write the record (adds `provider`, `model`, `generated_at`) to `work/ai_outputs/<repo_id>.json` and a human-readable rendering to `<repo_id>.txt`.

Error handling: an `AuthError` (missing CLI/login, bad API key, unknown provider) aborts the whole run with guidance; any other per-repo error is logged and the loop continues. AI output is purely advisory; it does not feed back into metrics.

---

## 14. Logging and Error Handling

* Use `logging` module in `scan.py`.

  * Log to console and optionally to `work/logs/scan.log`.
* For each repo:

  * If cloning or analysis fails, log error but continue to the next repo.
  * Do not create partial metrics files; write them only after successful computation.

Error conditions to handle:

* Git clone failure (e.g., private repo without access).
* Git commands failing inside `repo_dir`.
* Invalid or unparsable dates for `t0`/`t1`.
* Empty commit history.

For AI runner:

* If metrics JSON is missing, skip that repo with a warning.
* An `AuthError` (missing CLI/login, invalid API key, unknown provider) aborts the run with actionable guidance; other per-repo failures are logged and skipped.

---

## 15. Implementation Notes

* Use timezone-aware datetimes (`datetime.datetime.fromisoformat` and normalize to UTC if needed).
* Keep all numeric values in metrics JSON as plain numbers (no strings).
* All scripts should be executable with `python3` and not require virtualenv setup.

This spec is sufficient for a coding agent to implement the tool end-to-end.
