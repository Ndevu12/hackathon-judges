"""Pluggable AI-analysis backends for the authenticity check.

Two providers, selected by the ``ai.provider`` config value:

* ``"claude_code"`` (default) — drives the local **Claude Code CLI** (``claude
  -p``), which runs on the user's Claude Pro/Max **subscription**. No API key
  and no per-token API billing; it just needs the CLI installed and a logged-in
  Pro/Max account (``claude`` → ``/login``, or ``claude setup-token`` for
  headless use). The subprocess env is scrubbed of ``ANTHROPIC_API_KEY`` so the
  CLI can't silently fall back to API billing.

* ``"anthropic"`` — calls the Claude API directly with the official
  ``anthropic`` SDK. Requires ``pip install anthropic`` and an
  ``ANTHROPIC_API_KEY``.

Both return the same structured dict, validated against the shared analysis
schema, so everything downstream (the ``.json``/``.txt`` writers and the
dashboard) is provider-agnostic.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Any, Dict, Optional


class AnalysisError(RuntimeError):
    """A recoverable, per-repo failure: log it and move on to the next repo."""


class AuthError(AnalysisError):
    """A setup/auth failure that dooms every repo: abort the run with guidance."""


# Env vars that would make the Claude Code CLI bill the API instead of drawing
# on the subscription. Scrubbed from the child process for the subscription route.
_API_AUTH_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")


class Provider:
    """Common interface: build once, then ``analyze(prompt)`` per repo."""

    label = "provider"

    def preflight(self) -> None:
        """Optional early check (auth/tooling) so we fail before the repo loop."""

    def analyze(self, prompt: str) -> Dict[str, Any]:  # pragma: no cover - abstract
        raise NotImplementedError


class ClaudeCodeProvider(Provider):
    """Analyze via the local Claude Code CLI, on the user's subscription."""

    def __init__(self, ai_cfg: Dict[str, Any], system_prompt: str, schema: Dict[str, Any]):
        self.cli = ai_cfg.get("cli_path") or "claude"
        self.model = ai_cfg["model"]
        self.effort = ai_cfg.get("effort")
        self.timeout = ai_cfg.get("cli_timeout", 300)
        self.system_prompt = system_prompt
        self.schema = schema
        self.label = f"claude-code:{self.model} (subscription)"

    def preflight(self) -> None:
        self._resolve_cli()

    def _resolve_cli(self) -> str:
        path = shutil.which(self.cli)
        if not path:
            raise AuthError(
                f"Claude Code CLI '{self.cli}' not found on PATH. Install it "
                "(https://claude.com/product/claude-code) and run `claude` once to "
                "sign in with your Pro/Max account, or set ai.provider to "
                "'anthropic' to use the API instead."
            )
        return path

    def _child_env(self) -> Dict[str, str]:
        """A copy of the environment with API-key auth removed.

        This guarantees the CLI uses the subscription (OAuth/keychain) login
        rather than silently billing the API when ANTHROPIC_API_KEY is present.
        """
        env = dict(os.environ)
        for var in _API_AUTH_VARS:
            env.pop(var, None)
        return env

    def analyze(self, prompt: str) -> Dict[str, Any]:
        cli = self._resolve_cli()
        cmd = [
            cli,
            "-p",
            "--output-format", "json",
            "--model", self.model,
            "--system-prompt", self.system_prompt,
            "--json-schema", json.dumps(self.schema),
            "--tools", "",  # pure analysis: no file/bash tools
            "--no-session-persistence",
        ]
        if self.effort:
            cmd += ["--effort", str(self.effort)]
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                text=True,
                capture_output=True,
                env=self._child_env(),
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:  # CLI vanished between preflight and now
            raise AuthError(f"Failed to launch Claude Code CLI: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AnalysisError(
                f"Claude Code CLI timed out after {self.timeout}s"
            ) from exc

        if proc.returncode != 0:
            self._raise_for_cli_error(proc)
        return self._parse_envelope(proc.stdout)

    @staticmethod
    def _raise_for_cli_error(proc: "subprocess.CompletedProcess[str]") -> None:
        detail = (proc.stderr or proc.stdout or "").strip()
        low = detail.lower()
        auth_markers = (
            "log in", "login", "unauthorized", "authenticat", "not signed in",
            "oauth", "credit balance", "invalid api key",
        )
        if any(marker in low for marker in auth_markers):
            raise AuthError(
                "Claude Code isn't authenticated for the subscription route. Run "
                "`claude` and sign in with your Pro/Max account (or `claude "
                "setup-token` for headless use). If you meant to use the API "
                "instead, set ai.provider='anthropic'. Original error: " + detail
            )
        raise AnalysisError(
            f"Claude Code CLI failed (exit {proc.returncode}): {detail or 'no output'}"
        )

    def _parse_envelope(self, stdout: str) -> Dict[str, Any]:
        text = (stdout or "").strip()
        if not text:
            raise AnalysisError("Claude Code CLI returned no output")
        try:
            envelope = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AnalysisError(
                f"Could not parse Claude Code CLI output as JSON: {exc}"
            ) from exc
        if envelope.get("is_error"):
            raise AnalysisError(
                "Claude Code CLI reported an error: "
                f"{envelope.get('result') or envelope.get('subtype')}"
            )
        # --json-schema puts the validated object here directly.
        structured = envelope.get("structured_output")
        if isinstance(structured, dict):
            return structured
        # Fallback: the text result should itself be the JSON object.
        result = envelope.get("result")
        if isinstance(result, str) and result.strip():
            return _loads_json_object(result)
        raise AnalysisError(
            "Claude Code CLI output had no structured_output or JSON result"
        )


class AnthropicProvider(Provider):
    """Analyze via the Claude API using the official ``anthropic`` SDK."""

    def __init__(
        self,
        ai_cfg: Dict[str, Any],
        system_prompt: str,
        schema: Dict[str, Any],
        api_key: Optional[str] = None,
    ):
        try:
            import anthropic
        except ImportError as exc:
            raise AuthError(
                "The 'anthropic' SDK is required for ai.provider='anthropic'. "
                "Install it with `pip install -r requirements.txt`, or use the "
                "default subscription route (ai.provider='claude_code')."
            ) from exc
        self._anthropic = anthropic
        kwargs: Dict[str, Any] = {}
        if api_key:
            kwargs["api_key"] = api_key
        if ai_cfg.get("base_url"):
            kwargs["base_url"] = ai_cfg["base_url"]
        self.client = anthropic.Anthropic(**kwargs)
        self.ai_cfg = ai_cfg
        self.system_prompt = system_prompt
        self.schema = schema
        self.model = ai_cfg["model"]
        self.label = f"anthropic:{self.model} (API)"

    def analyze(self, prompt: str) -> Dict[str, Any]:
        output_config: Dict[str, Any] = {
            "format": {"type": "json_schema", "schema": self.schema}
        }
        if self.ai_cfg.get("effort"):
            output_config["effort"] = self.ai_cfg["effort"]
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.ai_cfg["max_tokens"],
            "system": self.system_prompt,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": output_config,
        }
        if self.ai_cfg.get("thinking"):
            kwargs["thinking"] = {"type": "adaptive"}
        try:
            response = self.client.messages.create(**kwargs)
        except self._anthropic.AuthenticationError as exc:
            raise AuthError(
                "Anthropic API authentication failed. Set ANTHROPIC_API_KEY (env "
                "or .env), pass --api-key, or switch to the subscription route "
                "(ai.provider='claude_code')."
            ) from exc
        if response.stop_reason == "refusal":
            raise AnalysisError("the model refused the request")
        text = next((block.text for block in response.content if block.type == "text"), "")
        if not text:
            raise AnalysisError("the model returned no text content")
        return _loads_json_object(text)


def make_provider(
    ai_cfg: Dict[str, Any],
    *,
    system_prompt: str,
    schema: Dict[str, Any],
    api_key: Optional[str] = None,
) -> Provider:
    """Construct the provider named by ``ai_cfg['provider']`` (default subscription)."""
    provider = (ai_cfg.get("provider") or "claude_code").lower()
    if provider in ("claude_code", "claude-code", "subscription"):
        return ClaudeCodeProvider(ai_cfg, system_prompt, schema)
    if provider == "anthropic":
        return AnthropicProvider(ai_cfg, system_prompt, schema, api_key)
    raise AuthError(
        f"Unknown ai.provider {provider!r}. Expected 'claude_code' (subscription) "
        "or 'anthropic' (API key)."
    )


def _loads_json_object(text: str) -> Dict[str, Any]:
    """Parse a JSON object from model text, tolerating ```` ```json ```` fences."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = s[3:]
        if s[:4].lower() == "json":
            s = s[4:]
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(s[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise AnalysisError("could not parse a JSON object from the model output")
