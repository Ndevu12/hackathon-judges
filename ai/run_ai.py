#!/usr/bin/env python3
"""
Optional AI authenticity analysis via the Anthropic (Claude) API.

For each analyzed repo, asks Claude — using structured output — whether the
project's commit pattern and code look consistent with being built during the
hackathon window, and writes:
  - work/ai_outputs/<id>.json : the structured verdict (consumed by the dashboard)
  - work/ai_outputs/<id>.txt  : a human-readable rendering

Configuration lives in config.json's `ai` section (model, base_url, max_tokens,
effort, thinking, truncation limits) — all overridable. The API key is read from
ANTHROPIC_API_KEY (shell env or an untracked .env file), never from config.
Requires: pip install anthropic
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from textwrap import shorten

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_config import build_analysis_schema, load_config, override_from_cli  # noqa: E402

try:
    import anthropic
except ImportError:
    anthropic = None


SYSTEM_PROMPT = (
    "You are assisting judges reviewing hackathon submissions. Given a repo's "
    "commit metrics and code context, assess whether the project was genuinely "
    "built during the hackathon window. Be concise, specific, and fair: modern "
    "AI coding tools make large output normal, so weigh commit timing and "
    "patterns (pre-T0 commits, bulk dumps, initial-commit size) over raw volume. "
    "Return only the requested structured fields."
)

# Map the structured verdict to a phrase for the human-readable .txt rendering.
VERDICT_PHRASE = {
    "authentic": "looks consistent with a hackathon project",
    "suspicious": "some suspicious patterns",
    "highly_suspicious": "highly suspicious",
    "inconclusive": "inconclusive — limited signal",
}


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


def make_client(ai_cfg: dict, api_key: str | None):
    """Construct the Anthropic client; key resolves from --api-key then env/.env."""
    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    if ai_cfg.get("base_url"):
        kwargs["base_url"] = ai_cfg["base_url"]
    return anthropic.Anthropic(**kwargs)


def analyze(client, ai_cfg: dict, prompt: str) -> dict:
    """Call Claude with structured output and return the parsed analysis dict."""
    output_config = {"format": {"type": "json_schema", "schema": build_analysis_schema()}}
    if ai_cfg.get("effort"):
        output_config["effort"] = ai_cfg["effort"]
    kwargs = {
        "model": ai_cfg["model"],
        "max_tokens": ai_cfg["max_tokens"],
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
        "output_config": output_config,
    }
    if ai_cfg.get("thinking"):
        kwargs["thinking"] = {"type": "adaptive"}

    response = client.messages.create(**kwargs)
    if response.stop_reason == "refusal":
        raise RuntimeError("model refused the request")
    text = next((block.text for block in response.content if block.type == "text"), "")
    if not text:
        raise RuntimeError("model returned no text content")
    return json.loads(text)


def render_txt(analysis: dict) -> str:
    """Human-readable rendering. The verdict line matches what the UI parses."""
    lines = [analysis.get("summary", "").strip(), ""]
    for obs in analysis.get("observations", []):
        lines.append(f"- {obs}")
    if analysis.get("red_flags"):
        lines.append("")
        lines.append("Red flags:")
        for flag in analysis["red_flags"]:
            lines.append(f"- {flag}")
    verdict = analysis.get("verdict", "inconclusive")
    lines.append("")
    lines.append(f"Overall authenticity assessment: {VERDICT_PHRASE.get(verdict, verdict)}")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI authenticity analysis via the Claude API.")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--work-dir", help="Work directory (default: paths.work_dir from config)")
    parser.add_argument("--only-id", help="Run AI analysis only for this repo id")
    parser.add_argument("--model", help="Model (overrides ai.model from config)")
    parser.add_argument("--base-url", help="API base URL (overrides ai.base_url)")
    parser.add_argument("--api-key", help="API key (overrides the ANTHROPIC_API_KEY env var)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger = logging.getLogger("ai")

    if anthropic is None:
        logger.error("The anthropic SDK is not installed. Run: pip install anthropic")
        return

    config = load_config(Path(args.config) if args.config else None)
    override_from_cli(
        config,
        {"paths.work_dir": args.work_dir, "ai.model": args.model, "ai.base_url": args.base_url},
    )
    ai_cfg = config["ai"]
    paths_cfg = config["paths"]

    if ai_cfg.get("provider", "anthropic") != "anthropic":
        logger.error("Unsupported ai.provider %r (only 'anthropic' is built in).", ai_cfg["provider"])
        return

    work_dir = Path(paths_cfg["work_dir"])
    metrics_dir = work_dir / "metrics"
    ai_outputs_dir = work_dir / "ai_outputs"
    ai_outputs_dir.mkdir(parents=True, exist_ok=True)

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
    client = make_client(ai_cfg, args.api_key)

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

        logger.info("Analyzing %s with %s", repo_id, ai_cfg["model"])
        try:
            analysis = analyze(client, ai_cfg, prompt)
        except anthropic.AuthenticationError:
            logger.error(
                "Authentication failed. Set ANTHROPIC_API_KEY in your environment "
                "or a .env file (or pass --api-key)."
            )
            return
        except Exception as exc:
            logger.error("Analysis failed for %s: %s", repo_id, exc)
            continue

        record = {
            "repo_id": repo_id,
            "repo": repo,
            "model": ai_cfg["model"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **analysis,
        }
        (ai_outputs_dir / f"{repo_id}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (ai_outputs_dir / f"{repo_id}.txt").write_text(render_txt(analysis), encoding="utf-8")
        logger.info("Wrote analysis for %s (%s)", repo_id, analysis.get("verdict"))


if __name__ == "__main__":
    main()
