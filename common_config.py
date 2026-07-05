"""Shared configuration for the hackathon-judges CLI tools.

This module is the single source of truth for every tunable setting. All of the
scripts (`scan.py`, `ai/run_ai.py`, `list_submissions.py`) load their
configuration through `load_config` and then apply command-line overrides with
`override_from_cli`.

Precedence, highest first:
    1. CLI flags      (applied via override_from_cli; only non-None values win)
    2. config.json    (deep-merged over the defaults)
    3. DEFAULT_CONFIG (the built-in defaults below)

Every default below equals the value that used to be hardcoded, so a config
file that omits a section — or is missing entirely — reproduces the original
behavior exactly. Legacy config files that only carry top-level ``t0``/``t1``/
``log_level`` are still accepted (see ``_apply_legacy_shim``).

Standard library only: this module must stay importable by every script without
adding third-party dependencies.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


# Built-in defaults. ``window.t0``/``window.t1`` are None so that, absent both a
# config value and a CLI flag, callers can detect "no start time provided" and
# fail loudly (matching the original scan.py behavior).
DEFAULT_CONFIG: Dict[str, Any] = {
    "window": {"t0": None, "t1": None},
    "log_level": "INFO",
    # Repo list + team metadata come from the hackathon site's public API. The
    # API key is a secret provided via the HACKATHON_API_KEY env var, never here.
    "api": {
        "base_url": "https://cursor-hackathon-site.vercel.app",
        "public_endpoint": "/api/public",
    },
    "paths": {
        "work_dir": "work",
        "ai_context": "ai/hackathon_context.md",
        "ai_prompt_template": "ai/prompt_template.txt",
    },
    "detection": {
        "bulk_insertion_threshold": 1000,
        "bulk_files_threshold": 50,
        "time_buckets_hours": [3, 6, 12, 24],
    },
    # Optional AI authenticity analysis via the Anthropic (Claude) API. The API
    # key is a secret read from ANTHROPIC_API_KEY (env or a .env file), never here.
    # Fully configurable: swap the model, point base_url elsewhere, toggle thinking.
    "ai": {
        "provider": "anthropic",
        "model": "claude-opus-4-8",
        "base_url": None,          # optional; else ANTHROPIC_BASE_URL / SDK default
        "max_tokens": 8000,
        "effort": "high",          # low|medium|high|xhigh|max; null to omit
        "thinking": True,          # adaptive thinking; set false for models without it
        "readme_char_limit": 4000,
        "tree_max_entries": 200,
        "tree_max_depth": 3,
    },
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``override`` into ``base`` in place, returning ``base``.

    Nested dicts are merged key by key; lists and scalars replace wholesale.
    Replacing (not element-merging) lists is deliberate: ``time_buckets_hours``
    and ``ai.command`` must be overridable as complete units.
    """
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _apply_legacy_shim(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Promote legacy top-level ``t0``/``t1`` keys into the ``window`` section.

    Older config files were flat: ``{"t0": ..., "t1": ..., "log_level": ...}``.
    We only migrate when there is no explicit ``window`` section, so a new-style
    config always takes precedence.
    """
    if "window" not in raw:
        window: Dict[str, Any] = {}
        if "t0" in raw:
            window["t0"] = raw.pop("t0")
        if "t1" in raw:
            window["t1"] = raw.pop("t1")
        if window:
            raw["window"] = window
    return raw


def load_dotenv(path: Optional[Path] = None) -> None:
    """Load ``KEY=VALUE`` lines from a ``.env`` file into ``os.environ``.

    Defaults to a ``.env`` beside this module (the repo root). Existing
    environment variables are never overwritten. This lets secrets like
    ``HACKATHON_API_KEY`` and ``ANTHROPIC_API_KEY`` live in an untracked ``.env``
    instead of the shell profile or the committed config.
    """
    env_path = Path(path) if path else Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: Optional[Path]) -> Dict[str, Any]:
    """Return the effective configuration: defaults deep-merged with the file.

    ``path`` of None yields a deep copy of the defaults (so scripts run without a
    ``--config`` flag). A path that does not exist raises ``FileNotFoundError``;
    invalid JSON or a non-object top level raises ``ValueError`` with a message
    naming the file. Also loads a ``.env`` file (if present) into the environment.
    """
    load_dotenv()
    merged = copy.deepcopy(DEFAULT_CONFIG)
    if path is None:
        return merged
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"Config file {path} must contain a JSON object")
    raw = _apply_legacy_shim(raw)
    return deep_merge(merged, raw)


def override_from_cli(config: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Apply non-None CLI overrides onto ``config`` in place.

    ``overrides`` maps dotted paths to values, e.g.
    ``{"window.t0": args.t0, "paths.work_dir": args.work_dir}``. A value of None
    means "flag not supplied" and is skipped, so config/defaults show through.
    """
    for dotted, value in overrides.items():
        if value is None:
            continue
        keys = dotted.split(".")
        node = config
        for key in keys[:-1]:
            node = node.setdefault(key, {})
        node[keys[-1]] = value
    return config


def _fmt(number: Any) -> str:
    """Render a bucket boundary: drop the trailing ``.0`` on whole numbers."""
    value = float(number)
    return str(int(value)) if value.is_integer() else str(number)


def validate_buckets(boundaries: Any) -> None:
    """Raise ValueError unless ``boundaries`` is a strictly ascending, positive list."""
    if not isinstance(boundaries, list) or not boundaries:
        raise ValueError(
            "detection.time_buckets_hours must be a non-empty list of hour boundaries"
        )
    previous = 0.0
    for boundary in boundaries:
        if isinstance(boundary, bool) or not isinstance(boundary, (int, float)):
            raise ValueError(
                f"time_buckets_hours entries must be numbers, got {boundary!r}"
            )
        if boundary <= 0:
            raise ValueError(
                f"time_buckets_hours entries must be positive, got {boundary}"
            )
        if boundary <= previous:
            raise ValueError(
                f"time_buckets_hours must be strictly ascending, got {boundaries}"
            )
        previous = float(boundary)


def get_bucket_keys(boundaries: List[Any]) -> List[str]:
    """Return the time-distribution column keys for the given hour boundaries.

    ``[3, 6, 12, 24]`` yields the legacy keys, in order::

        commits_0_3h, commits_3_6h, commits_6_12h, commits_12_24h, commits_after_24h
    """
    keys: List[str] = []
    low: Any = 0
    for boundary in boundaries:
        keys.append(f"commits_{_fmt(low)}_{_fmt(boundary)}h")
        low = boundary
    keys.append(f"commits_after_{_fmt(low)}h")
    return keys


def bucket_index(hours: float, boundaries: List[Any]) -> int:
    """Return the bucket index for ``hours`` (matches the legacy if/elif chain).

    The final index (``len(boundaries)``) is the "after the last boundary" bucket.
    """
    for index, boundary in enumerate(boundaries):
        if hours < boundary:
            return index
    return len(boundaries)


def build_analysis_schema() -> Dict[str, Any]:
    """JSON schema for the structured authenticity analysis returned per repo."""
    return {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["authentic", "suspicious", "highly_suspicious", "inconclusive"],
            },
            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            "summary": {"type": "string"},
            "observations": {"type": "array", "items": {"type": "string"}},
            "red_flags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["verdict", "confidence", "summary", "observations", "red_flags"],
        "additionalProperties": False,
    }
