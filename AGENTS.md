# Repository Guidelines

## Project Structure & Module Organization
- Core CLI: `scan.py` (metrics), `list_submissions.py` (listing helper), `normalize_judge_responses.py` (data cleanup).
- Shared config: `common_config.py` holds the config schema, defaults, and helpers; `config.json` (from `config.example.json`) holds per-event settings.
- AI helpers: `ai/run_ai.py` plus prompt assets in `ai/hackathon_context.md` and `ai/prompt_template.txt`.
- Web viewer: `ui/server.py` with static assets under `ui/static/` for browsing generated metrics.
- Data inputs: `data/` holds CSV exports and normalized judge data.
- Outputs: `work/` is the sandbox for clones, metrics, AI summaries, logs, and summaries; safe to delete/regenerate.

## Build, Test, and Development Commands
- All scripts take `--config config.json`; settings resolve as CLI flag > config.json > built-in default. Shared schema/helpers live in `common_config.py`.
- `python3 scan.py --config config.json`: clone repos and compute metrics; `--force` recomputes, `--no-update` skips git refresh, `--time-buckets`/`--bulk-*` override detection knobs.
- `python3 ai/run_ai.py --config config.json [--only-id <repo>]`: produce AI notes once metrics exist (provider is the configurable `ai.command`).
- `python3 ui/server.py --config config.json`: serve the local dashboard (host/port from the `server` section).
- `python3 normalize_judge_responses.py --config config.json`: regenerate normalized judge data (requires `pandas`).
- `python3 list_submissions.py --config config.json`: list teams with clone URLs.
- Use `python3 <script> --help` for full flag descriptions.

## Coding Style & Naming Conventions
- Python 3.10+, PEP 8, 4-space indent; prefer type hints and `Path` over raw strings.
- Favor clear, imperative function names (`ensure_work_dirs`, `collect_commit_data`) and lower_snake_case for variables/functions; PascalCase reserved for classes.
- Use `logging` (see `setup_logging`) instead of `print`; default INFO level.
- Prefer explicit error handling with actionable messages; avoid silent failures.

## Testing Guidelines
- No formal test suite; validate changes by running the primary flows above against a small sample CSV in `data/`.
- When changing git/metrics logic, spot-check `work/metrics/<id>.json` and `_commits.csv` for expected fields and ordering.
- For UI tweaks, start the server and manually verify tables, flags, and time distributions render correctly.

## Commit & Pull Request Guidelines
- Match existing history: short, imperative summaries (e.g., `Add winners`, `Show judge info`).
- Keep commits scoped; avoid bundling unrelated data refreshes with code changes.
- PRs should describe the change, the commands run, and any datasets or sample repos used; include screenshots for UI adjustments.

## Security & Configuration Tips
- Keep secrets out of `config.json`; it holds public settings (times, thresholds, paths, the AI command). The AI command is user-configurable and executed via subprocess without a shell — only point it at trusted binaries. Use environment variables or local overrides for anything sensitive.
- Avoid committing `work/` outputs unless explicitly requested; they are reproducible and can be large.
- Verify cloned repos come from trusted sources; this tool executes git operations and parses repo contents locally.
