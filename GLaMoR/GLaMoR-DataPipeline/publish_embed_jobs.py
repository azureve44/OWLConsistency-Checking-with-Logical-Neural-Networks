#!/usr/bin/env python3
from __future__ import annotations
import argparse
import base64
import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib import error, parse, request
DEFAULT_API_BASE = "http://127.0.0.1:15672/api"
DEFAULT_VHOST = "/"
DEFAULT_QUEUE = "embed"
DEFAULT_USER = "rabbitmq_user"
DEFAULT_PASS = "rabbitmq_password"
DEFAULT_CONSISTENT_ROOT = Path("./data/ont_modules")
DEFAULT_INCONSISTENT_ROOT = Path("./data/ont_modules_inconsistent_rdf")
DEFAULT_OUTPUT_ROOT = Path("../GLaMoR_Model_Training/embeddings")
DEFAULT_MANIFEST_DIR = Path("./data/embed_publish_manifests")
@dataclass(frozen=True)
class Job:
    source_type: str
    input_file: Path
    output_file: Path
class RabbitMQHttpClient:
    def __init__(self, api_base: str, user: str, password: str, vhost: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.vhost = parse.quote(vhost, safe="")
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        self._auth_header = f"Basic {token}"
    def _request(self, method: str, path: str, payload: dict | None = None) -> dict | None:
        data = None
        headers = {"Authorization": self._auth_header}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(f"{self.api_base}{path}", data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"RabbitMQ API {method} {path} failed with HTTP {exc.code}: {body}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"RabbitMQ API {method} {path} failed: {exc}") from exc
        if not raw:
            return None
        return json.loads(raw.decode("utf-8"))
    def ensure_queue(self, queue: str) -> None:
        self._request(
            "PUT",
            f"/queues/{self.vhost}/{parse.quote(queue, safe='')}",
            {"auto_delete": False, "durable": True, "arguments": {}},
        )
    def publish(self, queue: str, payload: str) -> None:
        result = self._request(
            "POST",
            f"/exchanges/{self.vhost}/amq.default/publish",
            {
                "properties": {},
                "routing_key": queue,
                "payload": payload,
                "payload_encoding": "string",
            },
        )
        if not result or not result.get("routed"):
            raise RuntimeError(f"RabbitMQ did not route payload to queue '{queue}': {payload}")
    def get_queue_state(self, queue: str) -> dict:
        return self._request("GET", f"/queues/{self.vhost}/{parse.quote(queue, safe='')}") or {}
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish ontology filenames into the embed queue with manifest/count reporting.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="RabbitMQ management API base URL.")
    parser.add_argument("--user", default=DEFAULT_USER, help="RabbitMQ username.")
    parser.add_argument("--password", default=DEFAULT_PASS, help="RabbitMQ password.")
    parser.add_argument("--vhost", default=DEFAULT_VHOST, help="RabbitMQ vhost.")
    parser.add_argument("--queue", default=DEFAULT_QUEUE, help="Target queue name.")
    parser.add_argument("--consistent-root", type=Path, default=DEFAULT_CONSISTENT_ROOT)
    parser.add_argument("--inconsistent-root", type=Path, default=DEFAULT_INCONSISTENT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR)
    parser.add_argument("--manifest-prefix", help="Optional manifest filename prefix. Defaults to a timestamp.")
    parser.add_argument("--include", nargs="+", choices=["consistent", "inconsistent"], default=["consistent", "inconsistent"])
    parser.add_argument("--skip-existing", action="store_true", help="Skip jobs whose .npy output already exists and is non-empty.")
    parser.add_argument("--limit", type=int, help="Optional cap on total candidate files after enumeration.")
    parser.add_argument("--dry-run", action="store_true", help="Write manifest/summary without publishing to RabbitMQ.")
    return parser.parse_args()
def iter_jobs(args: argparse.Namespace) -> Iterable[Job]:
    roots = []
    if "consistent" in args.include:
        roots.append(("consistent", args.consistent_root))
    if "inconsistent" in args.include:
        roots.append(("inconsistent", args.inconsistent_root))
    yielded = 0
    for source_type, root in roots:
        if not root.is_dir():
            raise FileNotFoundError(f"Input root does not exist: {root}")
        for path in sorted(root.glob("*.owl")):
            output_path = args.output_root / f"{path.stem}.npy"
            yield Job(source_type=source_type, input_file=path, output_file=output_path)
            yielded += 1
            if args.limit is not None and yielded >= args.limit:
                return
def write_manifest(manifest_path: Path, rows: list[dict[str, str]]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_type", "input_file", "payload", "output_file", "status", "reason"],
        )
        writer.writeheader()
        writer.writerows(rows)
def main() -> int:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    args.manifest_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    prefix = args.manifest_prefix or f"embed_publish_{timestamp}"
    manifest_path = args.manifest_dir / f"{prefix}.csv"
    summary_path = args.manifest_dir / f"{prefix}.summary.json"
    client = RabbitMQHttpClient(args.api_base, args.user, args.password, args.vhost)
    if not args.dry_run:
        client.ensure_queue(args.queue)
    rows: list[dict[str, str]] = []
    counts = Counter()
    source_counts: dict[str, Counter] = {"consistent": Counter(), "inconsistent": Counter()}
    for job in iter_jobs(args):
        counts["candidates"] += 1
        source_counts[job.source_type]["candidates"] += 1
        payload = job.input_file.name
        status = "pending"
        reason = ""
        if args.skip_existing and job.output_file.is_file() and job.output_file.stat().st_size > 0:
            status = "skipped"
            reason = "output_exists"
            counts["skipped_existing"] += 1
            source_counts[job.source_type]["skipped_existing"] += 1
        elif args.dry_run:
            status = "dry_run"
            counts["would_publish"] += 1
            source_counts[job.source_type]["would_publish"] += 1
        else:
            client.publish(args.queue, payload)
            status = "published"
            counts["published"] += 1
            source_counts[job.source_type]["published"] += 1
        rows.append(
            {
                "source_type": job.source_type,
                "input_file": str(job.input_file.resolve()),
                "payload": payload,
                "output_file": str(job.output_file.resolve()),
                "status": status,
                "reason": reason,
            }
        )
    write_manifest(manifest_path, rows)
    queue_state = client.get_queue_state(args.queue)
    summary = {
        "manifest_csv": str(manifest_path.resolve()),
        "summary_json": str(summary_path.resolve()),
        "dry_run": args.dry_run,
        "include": args.include,
        "skip_existing": args.skip_existing,
        "counts": dict(counts),
        "source_counts": {key: dict(value) for key, value in source_counts.items()},
        "queue": {
            "name": queue_state.get("name"),
            "messages": queue_state.get("messages"),
            "messages_ready": queue_state.get("messages_ready"),
            "messages_unacknowledged": queue_state.get("messages_unacknowledged"),
            "consumers": queue_state.get("consumers"),
        },
        "output_root": str(args.output_root.resolve()),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
