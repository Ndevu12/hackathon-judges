"""Client for the hackathon site's public API.

The analyzer sources its repo list and team metadata from the live event site
(https://cursor-hackathon-site.vercel.app) instead of local CSV files.

The API key is a shared secret ("admins only") and must never be committed.
Provide it via the ``HACKATHON_API_KEY`` environment variable, or ``--api-key``
on the CLI. Standard library only (uses ``urllib``).
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from typing import Dict, List, Optional

API_KEY_ENV = "HACKATHON_API_KEY"

# Well-known CA bundle locations, tried when the OpenSSL default paths load no
# certificates (common on macOS Homebrew Python, whose default cafile is unset).
_CA_BUNDLE_CANDIDATES = (
    "/etc/ssl/cert.pem",
    "/usr/local/etc/openssl@3/cert.pem",
    "/opt/homebrew/etc/openssl@3/cert.pem",
    "/etc/pki/tls/certs/ca-bundle.crt",
    "/etc/ssl/certs/ca-certificates.crt",
)


def _ssl_context() -> ssl.SSLContext:
    """Return an SSL context, tolerating environments with no default CA bundle.

    ``create_default_context`` honors ``SSL_CERT_FILE`` and OpenSSL's default
    paths. When those load no CAs, fall back to certifi (if installed) then the
    known system bundles above, so verification keeps working out of the box.
    """
    context = ssl.create_default_context()
    try:
        if context.cert_store_stats().get("x509_ca", 0) > 0:
            return context
    except Exception:
        return context

    candidates = []
    try:
        import certifi  # optional dependency; used only if already present

        candidates.append(certifi.where())
    except Exception:
        pass
    candidates.extend(_CA_BUNDLE_CANDIDATES)
    for path in candidates:
        if path and os.path.exists(path):
            try:
                context.load_verify_locations(cafile=path)
                return context
            except Exception:
                continue
    return context


class HackathonApiError(RuntimeError):
    """Raised for any API configuration, auth, network, or parsing failure."""


def resolve_api_key(cli_key: Optional[str] = None) -> str:
    """Return the API key from the CLI flag or the environment, or raise."""
    key = (cli_key or os.environ.get(API_KEY_ENV, "")).strip()
    if not key:
        raise HackathonApiError(
            f"Missing API key. Set the {API_KEY_ENV} environment variable "
            "(or pass --api-key)."
        )
    return key


def fetch_public(config: Dict, api_key: str, timeout: int = 30) -> Dict:
    """GET the /api/public payload (teams + submissions + config + counts)."""
    api_cfg = config.get("api", {}) or {}
    base_url = str(api_cfg.get("base_url", "")).rstrip("/")
    endpoint = api_cfg.get("public_endpoint", "/api/public")
    if not base_url:
        raise HackathonApiError("api.base_url is not configured.")
    url = f"{base_url}{endpoint}"
    request = urllib.request.Request(
        url, headers={"X-Api-Key": api_key, "Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise HackathonApiError(
                "401 Unauthorized — check HACKATHON_API_KEY."
            ) from exc
        raise HackathonApiError(f"API request to {url} failed ({exc.code}).") from exc
    except urllib.error.URLError as exc:
        raise HackathonApiError(f"Could not reach the API at {url}: {exc.reason}") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise HackathonApiError(f"API returned invalid JSON from {url}.") from exc


def _normalize_team_name(name: str) -> str:
    return (name or "").strip().lower()


def build_submission_records(public: Dict) -> List[Dict]:
    """Join submissions with their team into analyzer-ready records.

    Each record: ``{teamName, githubUrl, liveUrl, submittedAt, members}`` where
    ``members`` is ``[{name, email}, ...]``. Teams are matched by ``teamId``
    against ``team.id`` (or a ``team.mergedFrom`` id), with a ``teamName``
    fallback for merged teams whose submission still carries the old id.
    """
    teams = public.get("teams", []) or []
    submissions = public.get("submissions", []) or []

    by_id: Dict[str, Dict] = {}
    by_name: Dict[str, Dict] = {}
    for team in teams:
        if team.get("id"):
            by_id.setdefault(team["id"], team)
        for merged in team.get("mergedFrom", []) or []:
            by_id.setdefault(merged, team)
        by_name.setdefault(_normalize_team_name(team.get("teamName", "")), team)

    records: List[Dict] = []
    for sub in submissions:
        github_url = (sub.get("githubUrl") or "").strip()
        if not github_url:
            continue
        team = by_id.get(sub.get("teamId")) or by_name.get(
            _normalize_team_name(sub.get("teamName", ""))
        )
        members = [
            {"name": m.get("name", ""), "email": m.get("email", "")}
            for m in (team.get("members", []) if team else [])
        ]
        records.append(
            {
                "teamName": sub.get("teamName", ""),
                "githubUrl": github_url,
                "liveUrl": (sub.get("liveUrl") or "").strip(),
                "submittedAt": sub.get("submittedAt", ""),
                "members": members,
            }
        )
    return records
