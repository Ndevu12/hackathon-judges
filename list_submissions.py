#!/usr/bin/env python3
"""
Print hackathon submissions (team name, repo URL, live URL) from the public API,
in the order the API returns them.

Usage:
    python3 list_submissions.py [--config config.json] [--names-only]

Requires the API key via the HACKATHON_API_KEY env var (or --api-key).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_config import load_config  # noqa: E402
from hackathon_api import (  # noqa: E402
    HackathonApiError,
    build_submission_records,
    fetch_public,
    resolve_api_key,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="List hackathon submissions from the public API.")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--api-key", help="Hackathon API key (overrides the HACKATHON_API_KEY env var)")
    parser.add_argument("--names-only", action="store_true", help="Only print team names")
    args = parser.parse_args()

    config = load_config(Path(args.config) if args.config else None)
    try:
        public = fetch_public(config, resolve_api_key(args.api_key))
    except HackathonApiError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1

    records = build_submission_records(public)
    if not records:
        sys.stderr.write("No submissions returned by the API.\n")
        return 0

    for idx, rec in enumerate(records, start=1):
        team = rec["teamName"] or "(unnamed team)"
        if args.names_only:
            print(f"{idx:02d}. {team}")
        else:
            live = f"  |  live: {rec['liveUrl']}" if rec.get("liveUrl") else ""
            print(f"{idx:02d}. {team} -> {rec['githubUrl']}{live}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
