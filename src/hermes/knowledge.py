from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from .config import KNOWLEDGE_DIR, REPORT_DIR
from .database import HermesDB

SUPPORTED = {".txt", ".md", ".json", ".log", ".pdf"}
TOKEN_PATTERN = re.compile(r"[a-zA-ZÀ-ÿ0-9_\-]{2,}")


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _chunks(text: str, size: int = 1400, overlap: int = 180) -> list[str]:
    clean = re.sub(r"\r\n?", "\n", text).strip()
    if not clean:
        return []
    result: list[str] = []
    cursor = 0
    while cursor < len(clean):
        end = min(len(clean), cursor + size)
        if end < len(clean):
            split = clean.rfind("\n", cursor, end)
            if split <= cursor + size // 2:
                split = clean.rfind(" ", cursor, end)
            if split > cursor:
                end = split
        result.append(clean[cursor:end].strip())
        if end >= len(clean):
            break
        cursor = max(cursor + 1, end - overlap)
    return [chunk for chunk in result if chunk]


def _read_pdf(path: Path) -> list[tuple[int | None, str]]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return []
    pages: list[tuple[int | None, str]] = []
    reader = PdfReader(str(path))
    for number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.extend((number, chunk) for chunk in _chunks(text))
    return pages


def read_document(path: Path) -> list[tuple[int | None, str]]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".json":
        try:
            text = json.dumps(json.loads(text), ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    return [(None, chunk) for chunk in _chunks(text)]


class KnowledgeBase:
    def __init__(self, db: HermesDB) -> None:
        self.db = db

    def index_all(self, include_reports: bool = True) -> dict[str, Any]:
        candidates = [path for path in KNOWLEDGE_DIR.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED]
        if include_reports:
            candidates.extend(
                path for path in REPORT_DIR.rglob("*")
                if path.is_file() and path.suffix.lower() in {".txt", ".md", ".json", ".log"}
            )
        indexed = skipped = errors = 0
        details: list[dict[str, Any]] = []
        known = {item["path"]: item for item in self.db.indexed_documents()}
        for path in sorted(set(candidates)):
            relative = str(path.relative_to(path.parents[1])) if path.is_relative_to(KNOWLEDGE_DIR) else str(path)
            collection = path.parent.name if path.parent != KNOWLEDGE_DIR else "geral"
            previous = known.get(str(path.resolve()))
            modified = path.stat().st_mtime
            if previous and abs(float(previous["modified_at"]) - modified) < 0.001:
                skipped += 1
                continue
            try:
                chunks = read_document(path)
                if not chunks:
                    skipped += 1
                    details.append({"path": relative, "status": "sem texto ou dependência opcional ausente"})
                    continue
                self.db.replace_document(str(path.resolve()), collection, path.stem, modified, chunks)
                indexed += 1
            except (OSError, ValueError) as exc:
                errors += 1
                details.append({"path": relative, "status": f"erro: {exc}"})
        return {"indexed": indexed, "skipped": skipped, "errors": errors, "details": details}

    def search(self, query: str, collection: str | None = None, limit: int = 6) -> list[dict[str, Any]]:
        query_tokens = _tokens(query)
        if not query_tokens:
            return []
        query_counts = Counter(query_tokens)
        results: list[dict[str, Any]] = []
        for chunk in self.db.all_chunks(collection):
            content_tokens = _tokens(chunk["content"])
            if not content_tokens:
                continue
            counts = Counter(content_tokens)
            overlap = sum(min(counts[token], amount) for token, amount in query_counts.items())
            if overlap == 0:
                continue
            phrase_bonus = 2.0 if query.lower() in chunk["content"].lower() else 0.0
            rarity_bonus = sum(1 / math.sqrt(max(1, counts[token])) for token in query_counts if token in counts)
            score = overlap * 2.5 + rarity_bonus + phrase_bonus
            results.append({
                "score": round(score, 3),
                "title": chunk["title"],
                "collection": chunk["collection"],
                "path": chunk["path"],
                "page": chunk["page"],
                "content": chunk["content"],
            })
        return sorted(results, key=lambda item: item["score"], reverse=True)[: max(1, min(limit, 20))]

    def status(self) -> dict[str, Any]:
        documents = self.db.indexed_documents()
        return {
            "documents": len(documents),
            "chunks": sum(int(item["chunks"]) for item in documents),
            "collections": sorted({item["collection"] for item in documents}),
            "items": documents,
            "supported": sorted(SUPPORTED),
        }
