#!/usr/bin/env python3
"""
Master Archive Database
=======================

SQLite-backed solution storage with in-memory caching.
Stores MasterSolution records – proven fix patterns with success-rate tracking.

Author: WorkspaceSentinel QuickFix System
"""

import sqlite3
import json
import threading
import datetime
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MasterSolution:
    """A proven fix solution stored in the master archive."""

    solution_id: str
    language: str
    error_pattern_id: str
    solution_template: str
    solution_description: str
    fix_description: str = ""
    confidence: float = 0.8
    success_rate: float = 1.0
    total_applications: int = 0
    successful_applications: int = 0
    tags: List[str] = field(default_factory=list)
    requires_backup: bool = True
    deprecated: bool = False
    replacement_id: Optional[str] = None
    last_updated: datetime.datetime = field(default_factory=datetime.datetime.now)
    created_date: datetime.datetime = field(default_factory=datetime.datetime.now)
    last_used: Optional[datetime.datetime] = None

    def __post_init__(self):
        if not self.fix_description:
            self.fix_description = self.solution_description

    # Convenience aliases (read-only; not stored as dataclass fields so
    # asdict() won't duplicate them – callers use them directly).
    @property
    def description(self) -> str:
        return self.solution_description

    @property
    def application_count(self) -> int:
        return self.total_applications


# ---------------------------------------------------------------------------
# Default solutions seeded on first run
# ---------------------------------------------------------------------------

_DEFAULT_SOLUTIONS: List[Dict[str, Any]] = [
    # HTML
    {
        "solution_id": "html_unclosed_tag_fix",
        "language": "html",
        "error_pattern_id": "html_unclosed_tag",
        "solution_template": "<{tag}>{content}</{tag}>",
        "solution_description": "Add missing closing tag",
        "fix_description": "Wrap content with matching closing tag",
        "confidence": 0.9,
        "tags": ["html", "syntax", "tag"],
    },
    {
        "solution_id": "html_invalid_attribute_fix",
        "language": "html",
        "error_pattern_id": "html_invalid_attribute",
        "solution_template": "",
        "solution_description": "Remove invalid HTML attribute",
        "fix_description": "Remove the unrecognised attribute from the element",
        "confidence": 0.75,
        "tags": ["html", "attribute"],
    },
    # CSS
    {
        "solution_id": "css_missing_semicolon_fix",
        "language": "css",
        "error_pattern_id": "css_missing_semicolon",
        "solution_template": "{property}: {value};",
        "solution_description": "Add missing semicolon after CSS declaration",
        "fix_description": "Append semicolon to the CSS property declaration",
        "confidence": 0.95,
        "tags": ["css", "syntax", "semicolon"],
    },
    {
        "solution_id": "css_invalid_property_fix",
        "language": "css",
        "error_pattern_id": "css_invalid_property",
        "solution_template": "",
        "solution_description": "Remove or replace invalid CSS property",
        "fix_description": "Remove the unrecognised CSS property",
        "confidence": 0.7,
        "tags": ["css", "property"],
    },
    # JavaScript
    {
        "solution_id": "js_missing_semicolon_fix",
        "language": "javascript",
        "error_pattern_id": "js_missing_semicolon",
        "solution_template": "{statement};",
        "solution_description": "Add missing semicolon after JavaScript statement",
        "fix_description": "Append semicolon to the statement",
        "confidence": 0.9,
        "tags": ["javascript", "syntax", "semicolon"],
    },
    {
        "solution_id": "js_undefined_variable_fix",
        "language": "javascript",
        "error_pattern_id": "js_undefined_variable",
        "solution_template": "let {variable};",
        "solution_description": "Declare undefined variable",
        "fix_description": "Add variable declaration before first use",
        "confidence": 0.7,
        "tags": ["javascript", "variable", "declaration"],
    },
    # Python
    {
        "solution_id": "python_indentation_error_fix",
        "language": "python",
        "error_pattern_id": "python_indentation_error",
        "solution_template": "    {code}",
        "solution_description": "Fix Python indentation error",
        "fix_description": "Correct the indentation to match the surrounding block",
        "confidence": 0.85,
        "tags": ["python", "indentation", "syntax"],
    },
    {
        "solution_id": "python_missing_import_fix",
        "language": "python",
        "error_pattern_id": "python_missing_import",
        "solution_template": "import {module}",
        "solution_description": "Add missing Python import statement",
        "fix_description": "Insert the missing import at the top of the file",
        "confidence": 0.8,
        "tags": ["python", "import"],
    },
    # JSON
    {
        "solution_id": "json_trailing_comma_fix",
        "language": "json",
        "error_pattern_id": "json_trailing_comma",
        "solution_template": "",
        "solution_description": "Remove trailing comma in JSON",
        "fix_description": "Delete trailing comma before closing bracket/brace",
        "confidence": 0.95,
        "tags": ["json", "syntax", "comma"],
    },
    {
        "solution_id": "json_invalid_quotes_fix",
        "language": "json",
        "error_pattern_id": "json_invalid_quotes",
        "solution_template": '"{value}"',
        "solution_description": "Replace invalid quotes in JSON",
        "fix_description": "Replace single quotes with double quotes",
        "confidence": 0.9,
        "tags": ["json", "syntax", "quotes"],
    },
]


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS master_solutions (
    solution_id          TEXT PRIMARY KEY,
    language             TEXT NOT NULL,
    error_pattern_id     TEXT NOT NULL,
    solution_template    TEXT NOT NULL,
    solution_description TEXT NOT NULL,
    fix_description      TEXT NOT NULL,
    confidence           REAL NOT NULL DEFAULT 0.8,
    success_rate         REAL NOT NULL DEFAULT 1.0,
    total_applications   INTEGER NOT NULL DEFAULT 0,
    successful_applications INTEGER NOT NULL DEFAULT 0,
    tags                 TEXT NOT NULL DEFAULT '[]',
    requires_backup      INTEGER NOT NULL DEFAULT 1,
    deprecated           INTEGER NOT NULL DEFAULT 0,
    replacement_id       TEXT,
    last_updated         TEXT NOT NULL,
    created_date         TEXT NOT NULL,
    last_used            TEXT
)
"""


def _row_to_solution(row: sqlite3.Row) -> MasterSolution:
    """Convert a database row to a MasterSolution instance."""
    d = dict(row)
    d["tags"] = json.loads(d.get("tags") or "[]")
    d["requires_backup"] = bool(d["requires_backup"])
    d["deprecated"] = bool(d["deprecated"])

    def _parse_dt(val: Optional[str]) -> Optional[datetime.datetime]:
        if not val:
            return None
        try:
            return datetime.datetime.fromisoformat(val)
        except (ValueError, TypeError):
            return None

    d["last_updated"] = _parse_dt(d["last_updated"]) or datetime.datetime.now()
    d["created_date"] = _parse_dt(d["created_date"]) or datetime.datetime.now()
    d["last_used"] = _parse_dt(d.get("last_used"))

    return MasterSolution(**d)


def _solution_to_row(s: MasterSolution) -> dict:
    """Flatten a MasterSolution to a dict suitable for SQLite."""
    return {
        "solution_id": s.solution_id,
        "language": s.language,
        "error_pattern_id": s.error_pattern_id,
        "solution_template": s.solution_template,
        "solution_description": s.solution_description,
        "fix_description": s.fix_description,
        "confidence": s.confidence,
        "success_rate": s.success_rate,
        "total_applications": s.total_applications,
        "successful_applications": s.successful_applications,
        "tags": json.dumps(s.tags),
        "requires_backup": int(s.requires_backup),
        "deprecated": int(s.deprecated),
        "replacement_id": s.replacement_id,
        "last_updated": s.last_updated.isoformat(),
        "created_date": s.created_date.isoformat(),
        "last_used": s.last_used.isoformat() if s.last_used else None,
    }


class MasterArchiveDB:
    """SQLite-backed master solution archive with in-memory cache."""

    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "master_archive.db"
        self._lock = threading.Lock()

        # In-memory cache: solution_id -> MasterSolution
        self.solutions_cache: Dict[str, MasterSolution] = {}

        self._init_db()
        self._load_cache()
        self._seed_defaults()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(_CREATE_TABLE_SQL)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _load_cache(self) -> None:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM master_solutions").fetchall()
        for row in rows:
            sol = _row_to_solution(row)
            self.solutions_cache[sol.solution_id] = sol

    def _seed_defaults(self) -> None:
        """Insert built-in solutions if they don't already exist."""
        now = datetime.datetime.now()
        for data in _DEFAULT_SOLUTIONS:
            if data["solution_id"] not in self.solutions_cache:
                sol = MasterSolution(
                    solution_id=data["solution_id"],
                    language=data["language"],
                    error_pattern_id=data["error_pattern_id"],
                    solution_template=data["solution_template"],
                    solution_description=data["solution_description"],
                    fix_description=data.get("fix_description", ""),
                    confidence=data.get("confidence", 0.8),
                    tags=data.get("tags", []),
                    created_date=now,
                    last_updated=now,
                )
                self._persist(sol)
                self.solutions_cache[sol.solution_id] = sol

    # ------------------------------------------------------------------
    # Internal persistence
    # ------------------------------------------------------------------

    def _persist(self, solution: MasterSolution) -> None:
        row = _solution_to_row(solution)
        placeholders = ", ".join(["?" for _ in row])
        columns = ", ".join(row.keys())
        values = list(row.values())
        sql = (
            f"INSERT OR REPLACE INTO master_solutions ({columns}) "
            f"VALUES ({placeholders})"
        )
        with self._get_conn() as conn:
            conn.execute(sql, values)

    # ------------------------------------------------------------------
    # Public CRUD
    # ------------------------------------------------------------------

    def add_solution(self, solution: MasterSolution) -> bool:
        """Add a new solution. Returns False if a solution with the same id exists."""
        with self._lock:
            if solution.solution_id in self.solutions_cache:
                return False
            self._persist(solution)
            self.solutions_cache[solution.solution_id] = solution
            return True

    def add_or_update_solution(self, solution: MasterSolution) -> None:
        """Insert or replace a solution."""
        with self._lock:
            solution.last_updated = datetime.datetime.now()
            self._persist(solution)
            self.solutions_cache[solution.solution_id] = solution

    def get_solution(self, solution_id: str) -> Optional[MasterSolution]:
        return self.solutions_cache.get(solution_id)

    def get_all_solutions(self) -> List[MasterSolution]:
        return list(self.solutions_cache.values())

    def get_solutions_for_pattern(
        self, pattern_id: str, language: str
    ) -> List[MasterSolution]:
        """Return all non-deprecated solutions matching pattern and language."""
        return [
            s for s in self.solutions_cache.values()
            if s.error_pattern_id == pattern_id
            and s.language == language
            and not s.deprecated
        ]

    def find_best_solution(
        self, language: str, pattern_id: str
    ) -> Optional[MasterSolution]:
        """Find the highest-confidence non-deprecated solution for a pattern."""
        candidates = self.get_solutions_for_pattern(pattern_id, language)
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.confidence)

    def get_best_solution(
        self,
        pattern_id: str,
        language: str,
        auto_applicable_only: bool = False,
    ) -> Optional[MasterSolution]:
        """Find the best solution, optionally restricted to high-confidence ones."""
        candidates = self.get_solutions_for_pattern(pattern_id, language)
        if auto_applicable_only:
            candidates = [c for c in candidates if c.confidence >= 0.8]
        if not candidates:
            return None
        return max(candidates, key=lambda s: (s.confidence, s.success_rate))

    # ------------------------------------------------------------------
    # Statistics tracking
    # ------------------------------------------------------------------

    def record_solution_application(
        self,
        solution_id: str,
        file_path: str,
        success: bool,
        execution_time: float,
    ) -> None:
        """Record a solution application and update statistics."""
        with self._lock:
            sol = self.solutions_cache.get(solution_id)
            if sol is None:
                return
            sol.total_applications += 1
            if success:
                sol.successful_applications += 1
            if sol.total_applications > 0:
                sol.success_rate = sol.successful_applications / sol.total_applications
            sol.last_used = datetime.datetime.now()
            sol.last_updated = datetime.datetime.now()
            self._persist(sol)

    def record_successful_application(self, solution_id: str) -> None:
        """Convenience wrapper – record a single successful application."""
        self.record_solution_application(solution_id, "", True, 0.0)

    def update_solution_auto_apply(
        self, solution_id: str, enable: bool
    ) -> bool:
        """Enable or disable auto-apply by adjusting solution confidence."""
        with self._lock:
            sol = self.solutions_cache.get(solution_id)
            if sol is None:
                return False
            # Raise/lower confidence so the 0.8 threshold check works
            sol.confidence = 0.9 if enable else 0.5
            sol.last_updated = datetime.datetime.now()
            self._persist(sol)
            return True

    def deprecate_solution(
        self, solution_id: str, replacement_id: Optional[str] = None
    ) -> None:
        """Mark a solution as deprecated."""
        with self._lock:
            sol = self.solutions_cache.get(solution_id)
            if sol is None:
                return
            sol.deprecated = True
            sol.replacement_id = replacement_id
            sol.last_updated = datetime.datetime.now()
            self._persist(sol)

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        solutions = list(self.solutions_cache.values())
        active = [s for s in solutions if not s.deprecated]
        by_language: Dict[str, int] = {}
        for s in active:
            by_language[s.language] = by_language.get(s.language, 0) + 1

        total_apps = sum(s.total_applications for s in active)
        total_success = sum(s.successful_applications for s in active)

        return {
            "total_solutions": len(solutions),
            "active_solutions": len(active),
            "deprecated_solutions": len(solutions) - len(active),
            "solutions_by_language": by_language,
            "total_applications": total_apps,
            "total_successful_applications": total_success,
            "overall_success_rate": (
                total_success / total_apps if total_apps > 0 else 0.0
            ),
        }
