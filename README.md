# Hackathon GitHub Repo Analyzer

Local CLI for judges: pull hackathon submissions from the event's public API, clone each GitHub repo, compute commit/activity metrics, and optionally produce short-form AI observations. Designed for macOS and ≤100 repos.

<img width="1649" height="715" alt="image" src="https://github.com/user-attachments/assets/f4973def-5f11-402b-b38d-f94df2ad5bd6" />

## Requirements
- macOS with `python3` (3.10+) and `git` in PATH
- **`HACKATHON_API_KEY`** — the hackathon API key (admins only)
- Optional (AI analysis): `pip install -r requirements.txt` (the `anthropic` SDK) and an **`ANTHROPIC_API_KEY`**. See [AI Analysis](#ai-analysis-optional).

Both keys can live in an untracked **`.env`** file (copy `.env.example` → `.env`); every script loads it automatically.

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
| `ai` | Claude analysis: `model`, `base_url`, `max_tokens`, `effort`, `thinking`, truncation limits. Key comes from `ANTHROPIC_API_KEY`. |

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
Analyzes each repo with **Claude** (via the official `anthropic` SDK) and returns a
**structured** authenticity verdict — no external CLI, no regex on model output.

1) `pip install -r requirements.txt` and set `ANTHROPIC_API_KEY` (env or `.env`).
2) Fill `ai/hackathon_context.md` with event details/rules; tweak `ai/prompt_template.txt` if desired.
3) After metrics exist (i.e. after `scan.py`), run:
```bash
python3 ai/run_ai.py --config config.json
```
`--only-id <repo>` limits to one repo; `--model`, `--base-url`, `--api-key` override config/env. It reads `work/submissions.json`, so run `scan.py` first.

Per repo it writes `work/ai_outputs/<id>.json` — `{ verdict, confidence, summary, observations[], red_flags[] }` — which the dashboard renders (verdict badge, confidence, red-flags), plus a human-readable `<id>.txt`.

**Fully configurable — not tied to one model.** The `ai` section:
```jsonc
"ai": {
  "provider": "anthropic",
  "model": "claude-opus-4-8",   // any Claude model (opus / sonnet / haiku)
  "base_url": null,             // or point at a compatible endpoint / ANTHROPIC_BASE_URL
  "max_tokens": 8000,
  "effort": "high",             // low|medium|high|xhigh|max; null to omit
  "thinking": true,             // adaptive thinking; set false for models without it
  "readme_char_limit": 4000, "tree_max_entries": 200, "tree_max_depth": 3
}
```
The key is **never** in config — it's read from `ANTHROPIC_API_KEY`.

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
