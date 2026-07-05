# Hackathon GitHub Repo Analyzer

Local CLI for judges: pull hackathon submissions from the event's public API, clone each GitHub repo, compute commit/activity metrics, and optionally produce short-form AI observations. Designed for macOS and ≤100 repos.

<img width="1649" height="715" alt="image" src="https://github.com/user-attachments/assets/f4973def-5f11-402b-b38d-f94df2ad5bd6" />

## Requirements
- macOS with `python3` (3.10+) and `git` in PATH
- **`HACKATHON_API_KEY`** — the hackathon API key (admins only)
- Optional (AI analysis) — pick one backend:
  - **Subscription (default):** the **Claude Code CLI** signed in to a Claude
    Pro/Max account. No API key, no per-token API billing.
  - **API:** `pip install -r requirements.txt` (the `anthropic` SDK) and an
    **`ANTHROPIC_API_KEY`**.

  See [AI Analysis](#ai-analysis-optional).

Secrets can live in an untracked **`.env`** file (copy `.env.example` → `.env`); every script loads it automatically.

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
| `ai` | AI analysis. `provider` (`claude_code` = subscription / `anthropic` = API), `model`, `cli_path`, `cli_timeout`, `base_url`, `max_tokens`, `effort`, `thinking`, truncation limits. Any API key comes from `ANTHROPIC_API_KEY`, never here. |

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
Analyzes each repo with **Claude** and returns a **structured** authenticity
verdict — `{ verdict, confidence, summary, observations[], red_flags[] }`, no
regex on model output. The backend is **pluggable** via `ai.provider`:

| `provider` | Runs on | Auth | Cost |
|------------|---------|------|------|
| **`claude_code`** (default) | the local **Claude Code CLI** (`claude -p`) | your Claude Pro/Max **subscription** login | drawn from your subscription, no API key |
| `anthropic` | the **Claude API** (`anthropic` SDK) | `ANTHROPIC_API_KEY` | per-token API billing |

Both write the same files, so the dashboard is provider-agnostic.

### Subscription route (default — no API key)
1) Install the **Claude Code CLI** (<https://claude.com/product/claude-code>) and sign in with your Pro/Max account: run `claude` and use `/login` (or `claude setup-token` for headless/CI use).
2) Fill `ai/hackathon_context.md` with event details/rules; tweak `ai/prompt_template.txt` if desired.
3) After metrics exist (i.e. after `scan.py`), run:
```bash
python3 ai/run_ai.py --config config.json
```
The run shells out to `claude` with structured output on your subscription. It scrubs `ANTHROPIC_API_KEY` from the CLI's environment so it can't silently fall back to API billing — so make sure you're logged in.

### API route (opt-in)
Set `ai.provider` to `"anthropic"` (or pass `--provider anthropic`), `pip install -r requirements.txt`, and set `ANTHROPIC_API_KEY` (env or `.env`). Then run the same command.

`--only-id <repo>` limits to one repo; `--provider`, `--model`, `--base-url`, `--api-key` override config/env. It reads `work/submissions.json`, so run `scan.py` first. Per repo it writes `work/ai_outputs/<id>.json` (rendered by the dashboard) plus a human-readable `<id>.txt`.

**Fully configurable — not tied to one model or backend.** The `ai` section:
```jsonc
"ai": {
  "provider": "claude_code",    // "claude_code" (subscription) | "anthropic" (API)
  "model": "claude-opus-4-8",   // any Claude model; the CLI also accepts aliases like "opus"
  "cli_path": "claude",         // claude_code: path to the Claude Code CLI
  "cli_timeout": 300,           // claude_code: per-repo subprocess timeout (seconds)
  "base_url": null,             // anthropic: compatible endpoint / ANTHROPIC_BASE_URL
  "max_tokens": 8000,           // anthropic: response token cap
  "effort": "high",             // both: low|medium|high|xhigh|max; null to omit
  "thinking": true,             // anthropic: adaptive thinking (ignored by the CLI)
  "readme_char_limit": 4000, "tree_max_entries": 200, "tree_max_depth": 3
}
```
API keys are **never** in config — the `anthropic` route reads `ANTHROPIC_API_KEY`; the subscription route uses your Claude Code login.

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
