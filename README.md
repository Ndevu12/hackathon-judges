# Hackathon GitHub Repo Analyzer

Local CLI for judges to clone GitHub submissions, compute commit/activity metrics, and optionally produce short-form AI observations. Designed for macOS and ≤100 repos.

<img width="1649" height="715" alt="image" src="https://github.com/user-attachments/assets/f4973def-5f11-402b-b38d-f94df2ad5bd6" />

## Requirements
- macOS with `python3` (3.10+) and `git` in PATH
- Optional: an AI CLI for summaries — `codex` by default, or any command you configure (e.g. the `claude` CLI). See [AI Analysis](#ai-analysis-optional).
- Optional: `pandas` (only needed by `normalize_judge_responses.py`)

## Layout
```
hackathon-analyzer/
  common_config.py      # shared config schema + helpers (all scripts import this)
  config.json           # your settings (see config.example.json)
  scan.py               # main metrics CLI
  ai/run_ai.py          # optional AI summaries
  ai/hackathon_context.md
  ai/prompt_template.txt
  data/repos.csv        # input list of repos
  work/                 # generated clones, metrics, summaries, ai outputs
```

## Configuration

Everything the tools do is driven by a single `config.json` (start from `config.example.json`). It is organized into sections, and **every setting has a built-in default** — so a partial config, or none at all, still works.

```json
{
  "window":    { "t0": "2025-12-01T10:00:00Z", "t1": "2025-12-02T10:00:00Z" },
  "log_level": "INFO",
  "paths":     { "work_dir": "work", "repos_csv": "data/repos.csv", "...": "..." },
  "detection": { "bulk_insertion_threshold": 1000, "bulk_files_threshold": 50,
                 "time_buckets_hours": [3, 6, 12, 24] },
  "ai":        { "command": ["codex", "..."], "model": "gpt-5.1-codex-mini", "...": "..." },
  "server":    { "host": "0.0.0.0", "port": 8000 }
}
```

| Section | What it controls |
|---------|------------------|
| `window` | Hackathon start (`t0`) and optional end (`t1`), ISO-8601. |
| `log_level` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |
| `paths` | Input/output locations: `work_dir`, `repos_csv`, `project_repo_map`, `judge_responses_raw`, `judge_responses_normalized`, `ai_context`, `ai_prompt_template`. |
| `detection` | Bulk-commit thresholds and the **time-distribution buckets** (see below). |
| `ai` | The pluggable AI command, model, and truncation limits (see [AI Analysis](#ai-analysis-optional)). |
| `server` | Local UI `host`/`port`. |

**Precedence (highest first): CLI flag → `config.json` → built-in default.** Every script takes `--config PATH`; unspecified flags fall through to the config, then to the defaults.

**Tune the time buckets to your event length.** `detection.time_buckets_hours` is a list of ascending hour boundaries; the analyzer counts during-event commits into `0→b1`, `b1→b2`, … and a final `after last` bucket. A 6-hour hackathon might use `[1, 2, 4]`; a 48-hour one `[6, 12, 24, 48]`. The default `[3, 6, 12, 24]` yields columns `commits_0_3h, commits_3_6h, commits_6_12h, commits_12_24h, commits_after_24h`.

> Legacy `config.json` files that only carried top-level `t0`/`t1`/`log_level` are still accepted — they are promoted into the `window` section automatically.

## Input CSV
- Export directly from your Google Form with header: `repo_url[,t0]`
  - Accepts: GitHub page URL (`https://github.com/owner/repo`), HTTPS clone (`...repo.git`), or SSH (`git@github.com:owner/repo.git`).
  - Optional `t0` column for per-repo overrides; leave blank otherwise.
- The analyzer derives:
  - `id = owner-repo` (or uses provided `id` column if present).
  - Clone URL (adds `.git` if needed).

## Quick Start
1) Set `window.t0` (and optional `window.t1`) in `config.json`.
2) Populate `data/repos.csv` from your form export (header `repo_url[,t0]`).
3) Run the analyzer:
```bash
python3 scan.py --config config.json
```
`--repos` and `--work-dir` default to the `paths` values in your config; pass them explicitly to override.

Optional flags (each overrides the config):
- `--t0 <ISO>` / `--t1 <ISO>`: hackathon window
- `--force`: recompute even if metrics already exist
- `--no-update`: skip git fetch/reset for existing clones
- `--log-level DEBUG|INFO|...`
- `--bulk-insertion-threshold N` / `--bulk-files-threshold N`
- `--time-buckets 3,6,12,24`

### Web UI (local viewer)
Serve a minimal UI to browse outputs:
```bash
python3 ui/server.py --config config.json
```
Then open http://localhost:8000 (host/port come from the `server` section; override with `--host`/`--port`). It shows the summary table, metrics flags, time distribution, AI notes, and a commit slice (first 100 rows).

There is also a **Next.js dashboard** in [`web/`](web/) (Tailwind + shadcn/ui, deployable to Vercel) that reads the same `work/` artifacts and judge JSON — see [web/README.md](web/README.md). Run it locally with `cd web && npm install && npm run dev`.

## Outputs
Created under `work/` (auto-created if missing):
- `repos/<id>/` cloned repositories (cached)
- `metrics/<id>.json` per-repo summary metrics
- `metrics/<id>_commits.csv` per-commit stats (chronological)
- `summary/metrics_summary.csv` cross-repo table for judges
- `logs/scan.log` run log
- `ai_outputs/<id>.txt` AI notes (only when run_ai is executed)

## AI Analysis (optional)
1) Fill `ai/hackathon_context.md` with event details/rules.
2) Adjust `ai/prompt_template.txt` if desired.
3) After metrics exist, run:
```bash
python3 ai/run_ai.py --config config.json
```
Use `--only-id team-alpha` to limit to one repo, and `--model <name>` to override the model.

**Pluggable provider.** The `ai.command` in your config is a command template run once per repo. `{model}` and `{prompt}` are substituted; set `ai.prompt_via_stdin: true` to feed the prompt on stdin instead of as an argument. No shell is invoked, so the prompt is passed safely as a single argument (or via stdin).

```jsonc
// codex (default)
"command": ["codex", "--yolo", "exec", "--sandbox", "danger-full-access", "--model", "{model}", "{prompt}"],
"model": "gpt-5.1-codex-mini", "prompt_via_stdin": false

// claude CLI, prompt as an argument
"command": ["claude", "-p", "{prompt}", "--model", "{model}"],
"model": "claude-sonnet-4-5", "prompt_via_stdin": false

// claude CLI, prompt on stdin
"command": ["claude", "-p", "--model", "{model}"],
"model": "claude-sonnet-4-5", "prompt_via_stdin": true
```

Other `ai` knobs: `timeout_seconds` (per-repo call timeout; `null` = unbounded), `readme_char_limit`, `tree_max_entries`, `tree_max_depth`.

## Judge scores & submissions
- `python3 normalize_judge_responses.py --config config.json` merges raw judge scores (`paths.judge_responses_raw`) with the project→repo map into `paths.judge_responses_normalized` (consumed by the UI). Requires `pandas`.
- `python3 list_submissions.py --config config.json` lists teams in submission order with clone URLs.

## Caching & Resuming
- Metrics are skipped if `metrics/<id>.json` exists; use `--force` to recompute.
- Existing clones are refreshed via fetch/reset unless `--no-update` is set.

## Troubleshooting
- Clone failures (auth/private repos) are logged and other repos continue.
- Invalid date strings for `--t0/--t1` or per-row `t0` will be reported and that repo is skipped.
- Invalid `time_buckets_hours` (empty or non-ascending) aborts the run with a clear message.
- A missing/failed AI command writes an error note in `ai_outputs/<id>.txt` and continues.
