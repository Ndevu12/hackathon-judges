# Hackathon GitHub Repo Analyzer

Local CLI for judges: pull hackathon submissions from the event's public API, clone each GitHub repo, compute commit/activity metrics, and optionally produce short-form AI observations. Designed for macOS and ≤100 repos.

<img width="1649" height="715" alt="image" src="https://github.com/user-attachments/assets/f4973def-5f11-402b-b38d-f94df2ad5bd6" />

## Requirements
- macOS with `python3` (3.10+) and `git` in PATH
- **`HACKATHON_API_KEY`** environment variable — the hackathon API key (shared with admins only)
- Optional: an AI CLI for summaries — `codex` by default, or any command you configure (e.g. the `claude` CLI). See [AI Analysis](#ai-analysis-optional).

## Layout
```text
hackathon-analyzer/
  common_config.py      # shared config schema + helpers
  hackathon_api.py      # public-API client (teams + submissions)
  config.json           # your settings (see config.example.json)
  scan.py               # main metrics CLI
  ai/run_ai.py          # optional AI summaries
  list_submissions.py   # print submissions from the API
  work/                 # generated clones, metrics, summary, submissions.json
  web/                  # Next.js dashboard (see web/README.md)
```

## Data source: the hackathon API
Submissions and teams come from the event site's public API — **there are no local input files**. Provide the key (admins only) via the environment:
```bash
export HACKATHON_API_KEY="…"
```
`scan.py` fetches `/api/public`, derives `repo_id = owner-repo` from each submission's `githubUrl`, and writes `work/submissions.json` (team name, live URL, members) for the dashboard. Pass `--api-key` to override the env var.

## Configuration
Settings live in `config.json` (start from `config.example.json`), organized into sections; every setting has a built-in default.

| Section | Controls |
|---------|----------|
| `window` | Hackathon start (`t0`) and optional end (`t1`), ISO-8601. |
| `log_level` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. |
| `api` | `base_url` + `public_endpoint`. **The key is never here** — it comes from `HACKATHON_API_KEY`. |
| `paths` | `work_dir`, `ai_context`, `ai_prompt_template`. |
| `detection` | Bulk-commit thresholds and the config-driven `time_buckets_hours`. |
| `ai` | The pluggable AI command, model, and truncation limits. |

**Precedence: CLI flag → `config.json` → built-in default.** Every script takes `--config PATH`.

**Tune the time buckets to your event length.** `detection.time_buckets_hours` is a list of ascending hour boundaries; a 6-hour hackathon might use `[1, 2, 4]`, a 48-hour one `[6, 12, 24, 48]`.

## Quick Start
```bash
export HACKATHON_API_KEY="…"
# set window.t0 (+ optional window.t1) in config.json, then:
python3 scan.py --config config.json
```
Optional flags (each overrides config): `--t0/--t1`, `--force`, `--no-update`, `--log-level`, `--bulk-insertion-threshold N`, `--bulk-files-threshold N`, `--time-buckets 3,6,12,24`, `--api-key`.

## Outputs
Created under `work/` (auto-created if missing):
- `submissions.json` — team name, live URL, and members per repo (for the dashboard)
- `repos/<id>/` cloned repositories (cached)
- `metrics/<id>.json` per-repo summary metrics
- `metrics/<id>_commits.csv` per-commit stats (chronological)
- `summary/metrics_summary.csv` cross-repo table for judges
- `logs/scan.log` run log
- `ai_outputs/<id>.txt` AI notes (only when `run_ai` is executed)

## Dashboard (`web/`)
A Next.js dashboard (Tailwind + shadcn/ui, Vercel-deployable) reads the `work/` artifacts and shows the submissions table, red-flag columns, time distribution, AI verdicts, **team members**, and **live project URLs**.
```bash
cd web && npm install && npm run dev   # http://localhost:3000
```
See [web/README.md](web/README.md) for the snapshot/deploy flow.

## AI Analysis (optional)
1) Fill `ai/hackathon_context.md` with event details/rules.
2) Adjust `ai/prompt_template.txt` if desired.
3) After metrics exist (i.e. after `scan.py`), run:
```bash
python3 ai/run_ai.py --config config.json
```
Use `--only-id team-alpha` to limit to one repo, and `--model <name>` to override the model. It reads `work/submissions.json` for the repo list, so run `scan.py` first.

**Pluggable provider.** The `ai.command` in your config is a command template run once per repo. `{model}` and `{prompt}` are substituted; set `ai.prompt_via_stdin: true` to feed the prompt on stdin instead of as an argument. No shell is invoked.

```jsonc
// codex (default)
"command": ["codex", "--yolo", "exec", "--sandbox", "danger-full-access", "--model", "{model}", "{prompt}"],
"model": "gpt-5.1-codex-mini", "prompt_via_stdin": false

// claude CLI, prompt on stdin
"command": ["claude", "-p", "--model", "{model}"],
"model": "claude-sonnet-4-5", "prompt_via_stdin": true
```

Other `ai` knobs: `timeout_seconds` (`null` = unbounded), `readme_char_limit`, `tree_max_entries`, `tree_max_depth`.

## List submissions
`python3 list_submissions.py --config config.json` prints teams in submission order with their repo + live URLs (from the API).

## Caching & Resuming
- Metrics are skipped if `metrics/<id>.json` exists; use `--force` to recompute.
- Existing clones are refreshed via fetch/reset unless `--no-update` is set.

## Troubleshooting
- Missing/invalid key → `401 Unauthorized`; set `HACKATHON_API_KEY` (or `--api-key`).
- Clone failures (private repos) are logged and other repos continue.
- Invalid dates or `time_buckets_hours` (empty/non-ascending) abort with a clear message.
- A missing/failed AI command writes an error note in `ai_outputs/<id>.txt` and continues.
