from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_config import load_config, override_from_cli  # noqa: E402


def clean_project_name(name: str) -> str:
    """Normalize project names for matching."""
    normalized = re.sub(r"\s+", " ", str(name).strip())
    return normalized.lower()


def extract_first_url(text: str) -> Optional[str]:
    """Return the first URL from the provided text, if any."""
    if not isinstance(text, str):
        return None
    match = re.search(r"https?://[^\s,]+", text)
    return match.group(0).strip() if match else None


def load_project_repo_map(path: Path) -> Dict[str, str]:
    """Load the project->repo map, cleaning names and urls."""
    df = pd.read_csv(
        path, sep="\\t", header=None, names=["Project", "Repo"], engine="python"
    )
    mapping: Dict[str, str] = {}
    for _, row in df.iterrows():
        project_raw = row["Project"]
        repo_raw = row["Repo"]

        # Skip header row and entries without a usable URL.
        repo_url = extract_first_url(repo_raw)
        if not repo_url:
            continue

        project_key = clean_project_name(project_raw)
        mapping[project_key] = repo_url
    return mapping


def build_manual_aliases(mapping_keys: List[str]) -> Dict[str, str]:
    """Hand-maintained aliases for mismatched names.

    Add entries per hackathon when a judge response's project name doesn't
    match the name in project-repo-map.csv, e.g.:
        clean_project_name("Short Name"): clean_project_name("Full Team Name"),
    """
    aliases: Dict[str, str] = {}

    # Keep only aliases that point to a known key.
    return {k: v for k, v in aliases.items() if v in mapping_keys}


def resolve_project_repo(
    project_clean: str,
    mapping: Dict[str, str],
    aliases: Dict[str, str],
) -> Optional[str]:
    """Find the repo URL for a cleaned project name."""
    if project_clean in mapping:
        return mapping[project_clean]

    if project_clean in aliases:
        target = aliases[project_clean]
        return mapping.get(target)

    # Conservative fuzzy match to catch small differences.
    close = get_close_matches(project_clean, mapping.keys(), n=1, cutoff=0.9)
    if close:
        return mapping[close[0]]

    return None


def normalize_responses(raw_path: Path, project_map_path: Path) -> Dict[str, dict]:
    project_repo_map = load_project_repo_map(project_map_path)
    aliases = build_manual_aliases(list(project_repo_map.keys()))

    responses = pd.read_csv(raw_path)
    normalized: Dict[str, dict] = {}
    unmapped: List[dict] = []

    aggregator: Dict[str, dict] = defaultdict(
        lambda: {"project": None, "responses": [], "raw_project_names": set()}
    )

    for _, row in responses.iterrows():
        project_raw = row["Project"]
        project_clean = clean_project_name(project_raw)
        repo_url = resolve_project_repo(project_clean, project_repo_map, aliases)
        entry = {
            "timestamp": row["Timestamp"],
            "score": int(row["Score"]),
            "thoughts": row["Thoughts"] if not (pd.isna(row["Thoughts"])) else None,
        }

        if repo_url:
            agg = aggregator[repo_url]
            agg["project"] = agg["project"] or project_raw.strip()
            agg["raw_project_names"].add(project_raw.strip())
            agg["responses"].append(entry)
        else:
            unmapped.append({"project": project_raw.strip(), **entry})

    for repo_url, data in aggregator.items():
        scores = [resp["score"] for resp in data["responses"]]
        normalized[repo_url] = {
            "project": data["project"],
            "raw_project_names": sorted(data["raw_project_names"]),
            "responses": data["responses"],
            "average_score": round(sum(scores) / len(scores), 3),
        }

    return {"by_repo": normalized, "unmapped_responses": unmapped}


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize judge responses into per-repo JSON.")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--raw", help="Raw judge responses CSV (default: paths.judge_responses_raw)")
    parser.add_argument("--project-map", help="Project->repo map CSV (default: paths.project_repo_map)")
    parser.add_argument("--output", help="Where to write normalized JSON (default: paths.judge_responses_normalized)")
    args = parser.parse_args()

    config = load_config(Path(args.config) if args.config else None)
    override_from_cli(
        config,
        {
            "paths.judge_responses_raw": args.raw,
            "paths.project_repo_map": args.project_map,
            "paths.judge_responses_normalized": args.output,
        },
    )
    paths_cfg = config["paths"]
    raw_path = Path(paths_cfg["judge_responses_raw"])
    project_map_path = Path(paths_cfg["project_repo_map"])
    output_path = Path(paths_cfg["judge_responses_normalized"])

    result = normalize_responses(raw_path, project_map_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Wrote normalized responses to {output_path}")
    if result["unmapped_responses"]:
        print("Unmapped projects:")
        for entry in result["unmapped_responses"]:
            print(f"- {entry['project']} (score {entry['score']})")


if __name__ == "__main__":
    main()
