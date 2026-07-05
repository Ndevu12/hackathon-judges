#!/usr/bin/env python3
"""
Optional AI analysis runner using a configurable CLI (see ai.command in config).
"""

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path
from textwrap import shorten

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_config import build_ai_command, load_config, override_from_cli  # noqa: E402


def load_submissions_map(work_dir: Path) -> dict:
    """Map repo_id -> GitHub URL from work/submissions.json (written by scan.py)."""
    path = work_dir / "submissions.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {rec["repo_id"]: rec.get("githubUrl", "") for rec in data if rec.get("repo_id")}


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def find_candidate_readmes(repo_dir: Path) -> list[Path]:
    names = {"README.md", "README.MD", "README", "readme.md", "readme"}
    candidates = []
    for path in repo_dir.rglob("*"):
        if path.name in names and path.is_file() and ".git" not in path.parts:
            candidates.append(path)
    return candidates


def read_best_readme(repo_dir: Path, limit_chars: int = 4000) -> str:
    candidates = find_candidate_readmes(repo_dir)
    if not candidates:
        return "No README found."
    # pick the longest meaningful README (by size), preferring shorter than limit but >50 chars
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    for candidate in candidates:
        content = candidate.read_text(encoding="utf-8", errors="ignore")
        if len(content.strip()) > 50:
            return shorten(content, width=limit_chars, placeholder="... [truncated]")
    content = candidates[0].read_text(encoding="utf-8", errors="ignore")
    return shorten(content, width=limit_chars, placeholder="... [truncated]")


def render_tree(repo_dir: Path, max_entries: int = 200, max_depth: int = 3) -> str:
    lines = []

    def walk(path: Path, depth: int) -> None:
        nonlocal lines
        if len(lines) >= max_entries:
            return
        prefix = "  " * depth
        try:
            entries = sorted(path.iterdir(), key=lambda p: p.name.lower())
        except Exception:
            return
        for entry in entries:
            if len(lines) >= max_entries:
                return
            name = entry.name
            if name in {".git", "__pycache__", "node_modules"}:
                continue
            lines.append(f"{prefix}{name}/" if entry.is_dir() else f"{prefix}{name}")
            if entry.is_dir() and depth + 1 < max_depth:
                walk(entry, depth + 1)

    walk(repo_dir, 0)
    if len(lines) >= max_entries:
        lines.append("... [truncated]")
    return "\n".join(lines) if lines else "No files listed."


def build_prompt(
    template: str,
    context: str,
    repo_id: str,
    repo: str,
    metrics_json: str,
    file_tree: str,
    readme_snippet: str,
) -> str:
    return (
        template.replace("{{HACKATHON_CONTEXT}}", context)
        .replace("{{REPO_ID}}", repo_id)
        .replace("{{REPO}}", repo)
        .replace("{{METRICS_JSON}}", metrics_json)
        .replace("{{FILE_TREE}}", file_tree)
        .replace("{{README_SNIPPET}}", readme_snippet)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run optional AI analysis via a configurable CLI.")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--work-dir", help="Work directory (default: paths.work_dir from config)")
    parser.add_argument("--only-id", help="Run AI analysis only for this repo id")
    parser.add_argument("--model", help="Model name (overrides ai.model from config)")
    args = parser.parse_args()

    config = load_config(Path(args.config) if args.config else None)
    override_from_cli(
        config,
        {
            "paths.work_dir": args.work_dir,
            "ai.model": args.model,
        },
    )
    ai_cfg = config["ai"]
    paths_cfg = config["paths"]

    work_dir = Path(paths_cfg["work_dir"])
    metrics_dir = work_dir / "metrics"
    ai_outputs_dir = work_dir / "ai_outputs"
    ai_outputs_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("ai")

    repos_map = load_submissions_map(work_dir)
    if not repos_map:
        logger.error("No work/submissions.json found. Run scan.py first.")
        return
    context_path = Path(paths_cfg["ai_context"])
    template_path = Path(paths_cfg["ai_prompt_template"])

    if not context_path.exists() or not template_path.exists():
        logger.error("Missing AI context or template files.")
        return

    hackathon_context = load_text(context_path)
    prompt_template = load_text(template_path)

    if args.only_id:
        target_ids = [args.only_id]
    else:
        target_ids = [
            path.stem for path in metrics_dir.glob("*.json") if not path.name.endswith("_commits.json")
        ]

    for repo_id in target_ids:
        metrics_path = metrics_dir / f"{repo_id}.json"
        if not metrics_path.exists():
            logger.warning("Metrics file missing for %s, skipping.", repo_id)
            continue
        if repo_id not in repos_map:
            logger.warning("Repo id %s not in submissions.json, skipping.", repo_id)
            continue
        repo = repos_map[repo_id]
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        repo_dir = work_dir / "repos" / repo_id
        file_tree = (
            render_tree(repo_dir, ai_cfg["tree_max_entries"], ai_cfg["tree_max_depth"])
            if repo_dir.exists()
            else "Repo directory not found."
        )
        readme_snippet = (
            read_best_readme(repo_dir, ai_cfg["readme_char_limit"])
            if repo_dir.exists()
            else "Repo directory not found."
        )
        prompt = build_prompt(
            prompt_template,
            hackathon_context,
            repo_id,
            repo,
            json.dumps(metrics, indent=2),
            file_tree,
            readme_snippet,
        )

        argv, stdin_data = build_ai_command(
            ai_cfg["command"], ai_cfg["model"], prompt, ai_cfg["prompt_via_stdin"]
        )
        output_path = ai_outputs_dir / f"{repo_id}.txt"
        logger.info("Running %s for %s", argv[0], repo_id)
        try:
            result = subprocess.run(
                argv,
                input=stdin_data,
                capture_output=True,
                text=True,
                timeout=ai_cfg["timeout_seconds"],
            )
        except FileNotFoundError as exc:
            logger.error("AI command %r not found: %s", argv[0], exc)
            output_path.write_text(
                f"ERROR: AI command not available: {argv[0]}\n", encoding="utf-8"
            )
            continue
        except subprocess.TimeoutExpired:
            logger.error("AI command timed out for %s", repo_id)
            output_path.write_text(
                f"ERROR: AI command timed out after {ai_cfg['timeout_seconds']}s\n",
                encoding="utf-8",
            )
            continue

        if result.returncode != 0:
            logger.error("AI command failed for %s: %s", repo_id, result.stderr.strip())
            output_path.write_text(
                f"ERROR: AI command failed ({result.returncode})\n{result.stderr}",
                encoding="utf-8",
            )
            continue

        output_path.write_text(result.stdout, encoding="utf-8")
        logger.info("Wrote AI output to %s", output_path)


if __name__ == "__main__":
    main()
