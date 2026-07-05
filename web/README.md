# Hackathon Analyzer — Web UI

Next.js dashboard for the hackathon-judges analyzer. Reads the analyzer's
`work/` artifacts + judge JSON and renders the submissions table, flags, AI
verdicts, and per-repo detail drawer. Replaces the Python `ui/server.py`
dashboard (which still works in parallel).

Stack: Next.js (App Router) + React 19 + Tailwind v4 + shadcn/ui (base-nova).

## Local development

```bash
cd web
npm install
npm run dev        # http://localhost:3000
```

The dev server reflects the **latest `scan.py` run** live: it reads the work dir
and judge JSON from the repo-root `../config.json` on each request.

Point it at other data with env vars (see `.env.example`):

```bash
HJ_DATA_ROOT=/path/to/a/checkout npm run dev   # reads <root>/work + <root>/data
```

## Data resolution

`lib/data.ts` picks a source in priority order:

1. **Env** — `HJ_DATA_ROOT` (repo layout) or `HJ_WORK_DIR` (+ `HJ_JUDGE_JSON`).
2. **Live work dir** — from `../config.json` (`paths.work_dir` +
   `paths.judge_responses_normalized`). Used during local `npm run dev`.
3. **Committed snapshot** — `web/snapshot/`. Used on deploy, where the local
   `work/` dir is absent.

No data anywhere → the UI renders empty states.

## Deploy (Vercel)

The app is `force-static`: the page reads artifacts at **build time** and bakes
them into static HTML, so no runtime filesystem access is needed.

```bash
# 1. Freeze the current analyzer output into web/snapshot/
npm run sync
# 2. Commit + push
git add web/snapshot && git commit -m "Update dashboard snapshot" && git push
```

Vercel settings:

- **Root Directory:** `web`
- Framework preset: **Next.js** · Install: `npm install` · Build: `npm run build`
- Node: **20+**

With root = `web`, `../config.json` and `../work` are absent, so the build reads
`web/snapshot/`. Re-run `npm run sync` + push to publish a new snapshot.

## Layout

```text
app/            page.tsx (force-static RSC) + layout + globals.css (theme)
components/     dashboard (client root) + table/chips/drawer + ui/ (shadcn)
lib/            data.ts (source resolver), types, csv, judges, verdict, format
scripts/        sync-snapshot.mjs
snapshot/       committed frozen data for deploy
```
