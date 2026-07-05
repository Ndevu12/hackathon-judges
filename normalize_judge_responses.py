from __future__ import annotations

import json
import re
from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


RAW_RESPONSES_PATH = Path("data/judge-responses-raw.csv")
PROJECT_MAP_PATH = Path("data/project-repo-map.csv")
OUTPUT_PATH = Path("data/judge-responses-normalized.json")


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


def load_project_repo_map() -> Dict[str, str]:
    """Load the project->repo map, cleaning names and urls."""
    df = pd.read_csv(
        PROJECT_MAP_PATH, sep="\\t", header=None, names=["Project", "Repo"], engine="python"
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
    """Hand-maintained aliases for mismatched names."""
    aliases = {
        clean_project_name("BaeFit"): clean_project_name("BaeFit - Megumin Virtual Assistant"),
        clean_project_name("BillionaireTwin"): clean_project_name("BillionaireTwin (Thanh/Giang/Dung)"),
        clean_project_name("Eduflow"): clean_project_name("Eduflow by Kody"),
        clean_project_name("HISTORYLENS"): clean_project_name("HISTORYLENS - LĂNG KÍNH LỊCH SỬ"),
        clean_project_name("IDB Team - Odoo + Cursor"): clean_project_name("IDB Team"),
        clean_project_name("Quantum Bug ; Product name: AirDraw"): clean_project_name("Team: Quantum Bug ; Product name: AirDraw"),
        clean_project_name("World Bias AI"): clean_project_name("World Bias"),
        clean_project_name("finance Flow"): clean_project_name("FinancialFriend"),
        clean_project_name("off clock"): clean_project_name("Off Clock"),
    }

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


def normalize_responses() -> Dict[str, dict]:
    project_repo_map = load_project_repo_map()
    aliases = build_manual_aliases(list(project_repo_map.keys()))

    responses = pd.read_csv(RAW_RESPONSES_PATH)
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
    result = normalize_responses()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"Wrote normalized responses to {OUTPUT_PATH}")
    if result["unmapped_responses"]:
        print("Unmapped projects:")
        for entry in result["unmapped_responses"]:
            print(f"- {entry['project']} (score {entry['score']})")


if __name__ == "__main__":
    main()
