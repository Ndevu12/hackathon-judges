# Repository Guidelines

## Project Structure & Module Organization
- Core CLI: `scan.py` (metrics), `list_submissions.py` (listing helper).
- Data source: `hackathon_api.py` fetches teams + submissions from the event's public API (repo list, team metadata) — there are no local input files.
- Shared config: `common_config.py` holds the config schema, defaults, and helpers; `config.json` (from `config.example.json`) holds per-event settings.
- AI helpers: `ai/run_ai.py` plus prompt assets in `ai/hackathon_context.md` and `ai/prompt_template.txt`.
- Dashboard: the Next.js app under `web/` reads `work/` artifacts (see `web/README.md`).
- Outputs: `work/` is the sandbox for clones, metrics, AI summaries, logs, summary, and `submissions.json`; safe to delete/regenerate.

## Build, Test, and Development Commands
- Put secrets in an untracked `.env` (copy `.env.example`): `HACKATHON_API_KEY` (scan) and `ANTHROPIC_API_KEY` (AI). Every script loads `.env` automatically. All scripts take `--config config.json`; settings resolve as CLI flag > config.json > built-in default.
- `python3 scan.py --config config.json`: fetch submissions from the API, clone repos, compute metrics, write `work/submissions.json`; `--force` recomputes, `--no-update` skips git refresh, `--time-buckets`/`--bulk-*` override detection knobs.
- `python3 ai/run_ai.py --config config.json [--only-id <repo>]`: AI authenticity analysis via the Claude API (structured output → `work/ai_outputs/<id>.json`; reads `work/submissions.json`). Needs `pip install -r requirements.txt` + `ANTHROPIC_API_KEY`; `--model`/`--base-url`/`--api-key` override.
- `python3 list_submissions.py --config config.json`: list teams with repo + live URLs from the API.
- `cd web && npm run dev`: run the dashboard; `npm run sync` freezes `work/` into `web/snapshot/` for deploy.
- Use `python3 <script> --help` for full flag descriptions.

## Coding Style & Naming Conventions
- Python 3.10+, PEP 8, 4-space indent; prefer type hints and `Path` over raw strings.
- Favor clear, imperative function names (`ensure_work_dirs`, `collect_commit_data`) and lower_snake_case for variables/functions; PascalCase reserved for classes.
- Use `logging` (see `setup_logging`) instead of `print`; default INFO level.
- Prefer explicit error handling with actionable messages; avoid silent failures.

## Testing Guidelines
- No formal test suite; validate changes by running the primary flows above (with `HACKATHON_API_KEY` set).
- When changing git/metrics logic, spot-check `work/metrics/<id>.json` and `_commits.csv` for expected fields and ordering.
- For UI tweaks, run `cd web && npm run dev` and manually verify the table, flags, team info, and time distributions render correctly.

## Commit & Pull Request Guidelines
- Match existing history: short, imperative summaries (e.g., `Add winners`, `Show judge info`).
- Keep commits scoped; avoid bundling unrelated data refreshes with code changes.
- PRs should describe the change, the commands run, and any datasets or sample repos used; include screenshots for UI adjustments.

## Security & Configuration Tips
- Secrets (`HACKATHON_API_KEY`, `ANTHROPIC_API_KEY`) come from the environment or an untracked `.env`, never `config.json` or git. `config.json` holds only public settings (times, thresholds, paths, model, base URLs).
- The API returns member emails (PII); they surface in the dashboard, which is admin-facing — be mindful before sharing a deployed link.
- AI analysis calls the Anthropic API directly (no subprocess/CLI); model and `base_url` are configurable via the `ai` section.
- Avoid committing `work/` outputs unless explicitly requested; they are reproducible and can be large.
- Verify cloned repos come from trusted sources; this tool executes git operations and parses repo contents locally.
