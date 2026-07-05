#!/usr/bin/env python3
"""
Minimal local web UI server to browse hackathon analysis outputs.
Serves static files from ui/static and JSON/text APIs backed by work/* artifacts.
Usage: python3 ui/server.py --work-dir work --port 8000
"""

import argparse
import csv
import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common_config import load_config, override_from_cli  # noqa: E402


class UiHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, work_dir: Path, static_dir: Path, judge_responses_path: Path, **kwargs):
        self.work_dir = work_dir
        self.static_dir = static_dir
        self.judge_responses_path = judge_responses_path
        super().__init__(*args, directory=str(static_dir), **kwargs)

    def _send_json(self, payload, status=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, text, status=200):
        data = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(self.path.split("?", 1)[0])
        if path == "/api/summary":
            return self.handle_summary()
        if path == "/api/judges":
            return self.handle_judges()
        if path.startswith("/api/repo/"):
            return self.handle_repo(path)
        return super().do_GET()

    def handle_summary(self):
        summary_path = self.work_dir / "summary" / "metrics_summary.csv"
        if not summary_path.exists():
            return self._send_json({"error": "summary not found"}, status=404)
        rows = []
        with summary_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return self._send_json({"rows": rows})

    def handle_judges(self):
        if not self.judge_responses_path.exists():
            return self._send_json({"error": "judge data not found"}, status=404)
        try:
            data = json.loads(self.judge_responses_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return self._send_json({"error": f"failed to load judge data: {exc}"}, status=500)
        return self._send_json(data)

    def handle_repo(self, path: str):
        parts = path.split("/")
        if len(parts) < 4:
            return self._send_json({"error": "invalid repo path"}, status=400)
        repo_id = parts[3]
        suffix = "/".join(parts[4:]) if len(parts) > 4 else ""
        metrics_path = self.work_dir / "metrics" / f"{repo_id}.json"
        commits_path = self.work_dir / "metrics" / f"{repo_id}_commits.csv"
        ai_path = self.work_dir / "ai_outputs" / f"{repo_id}.txt"

        if suffix.startswith("metrics"):
            if not metrics_path.exists():
                return self._send_json({"error": "metrics not found"}, status=404)
            data = json.loads(metrics_path.read_text(encoding="utf-8"))
            return self._send_json(data)

        if suffix.startswith("commits"):
            if not commits_path.exists():
                return self._send_json({"error": "commits not found"}, status=404)
            commits = []
            with commits_path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    commits.append(row)
            return self._send_json({"rows": commits})

        if suffix.startswith("ai"):
            if not ai_path.exists():
                return self._send_text("AI output not found.", status=404)
            return self._send_text(ai_path.read_text(encoding="utf-8"))

        return self._send_json({"error": "unknown repo endpoint"}, status=404)


def run_server(work_dir: Path, static_dir: Path, judge_responses_path: Path, host: str, port: int):
    handler = lambda *args, **kwargs: UiHandler(
        *args,
        work_dir=work_dir,
        static_dir=static_dir,
        judge_responses_path=judge_responses_path,
        **kwargs,
    )
    httpd = HTTPServer((host, port), handler)
    print(f"Serving UI at http://localhost:{port} (work dir: {work_dir})")
    httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser(description="Serve local web UI for hackathon analyzer outputs.")
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--work-dir", help="Work directory (default: paths.work_dir from config)")
    parser.add_argument("--port", type=int, help="Port to serve on (default: server.port from config)")
    parser.add_argument("--host", help="Host/interface to bind (default: server.host from config)")
    args = parser.parse_args()

    config = load_config(Path(args.config) if args.config else None)
    override_from_cli(
        config,
        {
            "paths.work_dir": args.work_dir,
            "server.port": args.port,
            "server.host": args.host,
        },
    )
    work_dir = Path(config["paths"]["work_dir"]).resolve()
    judge_responses_path = Path(config["paths"]["judge_responses_normalized"]).resolve()
    static_dir = Path(__file__).resolve().parent / "static"
    run_server(
        work_dir,
        static_dir,
        judge_responses_path,
        config["server"]["host"],
        int(config["server"]["port"]),
    )


if __name__ == "__main__":
    main()
