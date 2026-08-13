#!/usr/bin/env python3
"""Provider-free Taste Platform API using SQLite and optional Ollama."""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from collections import Counter
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent
ALLOWED_TYPES = {"movie", "show", "anime", "game", "music"}


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def validate_item(value: Any) -> tuple[dict[str, str], dict[str, Any]]:
    if not isinstance(value, dict):
        return {"body": "JSON object required"}, {}
    errors: dict[str, str] = {}
    name = value.get("item_name")
    item_type = value.get("item_type")
    rating = value.get("rating")
    notes = value.get("notes", "")
    tags = value.get("tags", [])

    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        errors["item_name"] = "item_name must contain 1-200 characters"
    if item_type not in ALLOWED_TYPES:
        errors["item_type"] = "item_type must be movie, show, anime, game, or music"
    if rating is not None:
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            errors["rating"] = "rating must be an integer from 1 to 5"
        else:
            if not 1 <= rating <= 5:
                errors["rating"] = "rating must be an integer from 1 to 5"
    if not isinstance(notes, str) or len(notes) > 2000:
        errors["notes"] = "notes must be a string of at most 2000 characters"
    if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
        errors["tags"] = "tags must be an array of strings"

    if errors:
        return errors, {}
    cleaned_tags = sorted(
        {tag.strip().casefold() for tag in tags if tag.strip()}
    )[:20]
    return (
        {},
        {
            "item_name": name.strip(),
            "item_type": item_type,
            "rating": rating,
            "notes": notes.strip(),
            "tags": cleaned_tags,
        },
    )


class TasteStore:
    def __init__(self, path: Path, catalog_path: Path | None = None) -> None:
        self.path = path
        source = catalog_path or ROOT / "local_catalog.json"
        self.catalog = json.loads(source.read_text(encoding="utf-8"))

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS taste_items (
                user_id TEXT NOT NULL,
                item_key TEXT NOT NULL,
                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                rating INTEGER,
                notes TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, item_key)
            )
            """
        )
        return conn

    def upsert(self, user_id: str, item: dict[str, Any]) -> dict[str, Any]:
        item_key = f"{item['item_type']}#{slug(item['item_name'])}"
        updated_at = int(time.time())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO taste_items
                    (user_id, item_key, item_name, item_type, rating,
                     notes, tags_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, item_key) DO UPDATE SET
                    item_name = excluded.item_name,
                    item_type = excluded.item_type,
                    rating = excluded.rating,
                    notes = excluded.notes,
                    tags_json = excluded.tags_json,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    item_key,
                    item["item_name"],
                    item["item_type"],
                    item["rating"],
                    item["notes"],
                    json.dumps(item["tags"]),
                    updated_at,
                ),
            )
        return {**item, "updated_at": updated_at}

    def history(
        self, user_id: str, item_type: str | None = None
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM taste_items WHERE user_id = ?"
        params: list[Any] = [user_id]
        if item_type:
            sql += " AND item_type = ?"
            params.append(item_type)
        sql += " ORDER BY updated_at DESC, item_name"
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            {
                "item_name": row["item_name"],
                "item_type": row["item_type"],
                "rating": row["rating"],
                "notes": row["notes"],
                "tags": json.loads(row["tags_json"]),
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def recommendations(
        self, user_id: str, item_type: str | None = None, limit: int = 5
    ) -> list[dict[str, Any]]:
        history = self.history(user_id)
        known = {row["item_name"].casefold() for row in history}
        liked = [row for row in history if (row["rating"] or 0) >= 4]
        favorite_tags = Counter(
            tag for row in liked for tag in row.get("tags", [])
        )
        favorite_types = Counter(row["item_type"] for row in liked)

        scored: list[tuple[int, str, dict[str, Any]]] = []
        for candidate in self.catalog:
            if candidate["name"].casefold() in known:
                continue
            if item_type and candidate["type"] != item_type:
                continue
            shared = [
                tag for tag in candidate.get("tags", []) if favorite_tags[tag]
            ]
            score = sum(favorite_tags[tag] * 3 for tag in shared)
            score += favorite_types[candidate["type"]]
            if not liked:
                score = 1
            reason = (
                "Matches " + ", ".join(shared[:3])
                if shared
                else f"Explores another {candidate['type']} option"
            )
            scored.append(
                (
                    score,
                    candidate["name"].casefold(),
                    {
                        **candidate,
                        "score": score,
                        "reason": reason,
                    },
                )
            )
        scored.sort(key=lambda row: (-row[0], row[1]))
        return [row[2] for row in scored[: max(1, min(limit, 20))]]


def ollama_chat(
    base_url: str,
    model: str,
    message: str,
    history: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> str:
    prompt = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a concise taste recommender. Base your answer only "
                    "on the supplied local profile and candidate list."
                ),
            },
            {
                "role": "system",
                "content": json.dumps(
                    {"profile": history, "candidates": recommendations},
                    ensure_ascii=False,
                ),
            },
            {"role": "user", "content": message},
        ],
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/chat",
        data=json.dumps(prompt).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        body = json.loads(response.read())
    result = str((body.get("message") or {}).get("content") or "").strip()
    if not result:
        raise RuntimeError("Ollama returned an empty response")
    return result


class TasteHandler(BaseHTTPRequestHandler):
    store: TasteStore
    auth_token = ""
    ollama_url = ""
    ollama_model = "llama3.2:3b"
    user_id = "local-user"

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self) -> bool:
        if not self.auth_token:
            return True
        presented = self.headers.get("X-Taste-Token", "")
        return hmac.compare_digest(presented, self.auth_token)

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._json(HTTPStatus.UNAUTHORIZED, {"error": "invalid X-Taste-Token"})
        return False

    def _read_json(self) -> Any:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 64 * 1024:
            raise ValueError("invalid request size")
        try:
            return json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("invalid JSON") from error

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path in {"/health", "/api/health"}:
            self._json(HTTPStatus.OK, {"status": "ok", "mode": "local"})
            return
        if parsed.path == "/api/history":
            if not self._require_auth():
                return
            item_type = parse_qs(parsed.query).get("type", [None])[0]
            if item_type and item_type not in ALLOWED_TYPES:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid type"})
                return
            items = self.store.history(self.user_id, item_type)
            self._json(HTTPStatus.OK, {"items": items, "count": len(items)})
            return
        self._json(
            HTTPStatus.OK,
            {
                "name": "Taste Platform local API",
                "endpoints": [
                    "GET /api/history",
                    "POST /api/profile",
                    "POST /api/recommendations",
                    "POST /api/chat",
                ],
            },
        )

    def do_POST(self) -> None:
        if not self._require_auth():
            return
        try:
            body = self._read_json()
        except ValueError as error:
            self._json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        path = urlsplit(self.path).path
        if path == "/api/profile":
            errors, item = validate_item(body)
            if errors:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "validation failed", "fields": errors},
                )
                return
            self._json(HTTPStatus.OK, {"item": self.store.upsert(self.user_id, item)})
            return

        if path in {"/api/recommendations", "/api/chat"}:
            item_type = body.get("item_type") if isinstance(body, dict) else None
            if item_type and item_type not in ALLOWED_TYPES:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "invalid item_type"})
                return
            recommendations = self.store.recommendations(
                self.user_id,
                item_type,
                int(body.get("limit", 5)) if isinstance(body, dict) else 5,
            )
            if path == "/api/recommendations":
                self._json(HTTPStatus.OK, {"items": recommendations})
                return

            message = str(body.get("message") or "").strip()
            if not message:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "message is required"})
                return
            response = ""
            if self.ollama_url:
                try:
                    response = ollama_chat(
                        self.ollama_url,
                        self.ollama_model,
                        message,
                        self.store.history(self.user_id),
                        recommendations,
                    )
                except (urllib.error.URLError, RuntimeError, TimeoutError):
                    response = ""
            if not response:
                names = ", ".join(item["name"] for item in recommendations[:3])
                response = (
                    f"Based on your local profile, try: {names}."
                    if names
                    else "Add a few rated items before asking for recommendations."
                )
            self._json(
                HTTPStatus.OK,
                {
                    "response": response,
                    "session_id": str(body.get("session_id") or uuid.uuid4()),
                    "recommendations": recommendations,
                },
            )
            return

        self._json(HTTPStatus.NOT_FOUND, {"error": "not found"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("TASTE_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("TASTE_PORT", "8090"))
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path(os.environ.get("TASTE_DB_PATH", "runtime/taste.db")),
    )
    args = parser.parse_args()

    TasteHandler.store = TasteStore(args.database)
    TasteHandler.auth_token = os.environ.get("TASTE_AUTH_TOKEN", "")
    TasteHandler.ollama_url = os.environ.get("TASTE_OLLAMA_URL", "")
    TasteHandler.ollama_model = os.environ.get("TASTE_OLLAMA_MODEL", "llama3.2:3b")
    TasteHandler.user_id = os.environ.get("TASTE_USER_ID", "local-user")

    server = ThreadingHTTPServer((args.host, args.port), TasteHandler)
    print(f"Taste Platform local API: http://{args.host}:{args.port}")
    print(f"Database: {args.database}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
