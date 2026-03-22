"""
Smart Pattern Learning System
==============================

Machine-learning-inspired pattern discovery and adaptation system.
Learns new error patterns from historical fix data and code analysis,
continuously improving detection accuracy over time.

Phase 2 Feature - Genesis QuickFix Generator
"""

import re
import json
import math
import hashlib
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field


@dataclass
class LearnedPattern:
    """Represents a pattern discovered through learning."""
    pattern_id: str
    language: str
    pattern_regex: str
    description: str
    sample_matches: List[str]
    occurrence_count: int
    confidence: float          # 0.0 – 1.0
    fix_success_rate: float    # 0.0 – 1.0
    first_seen: str
    last_seen: str
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PatternFeedback:
    """User / system feedback for a specific pattern detection."""
    pattern_id: str
    file_path: str
    was_correct: bool
    suggested_fix: Optional[str]
    timestamp: str
    notes: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


class SmartPatternLearner:
    """
    Learns new error patterns from historical data and user feedback.

    The learner:
    * Analyses raw fix history to discover recurring code constructs.
    * Maintains a confidence score per pattern based on how often it leads
      to a successful fix.
    * Accepts explicit user feedback to reinforce or penalise patterns.
    * Exports learned patterns so they can be consumed by PatternRecognition.
    """

    # Minimum occurrences before a candidate is promoted to a learned pattern
    MIN_OCCURRENCES_FOR_PATTERN = 3
    # Minimum confidence threshold to surface a pattern in suggestions
    MIN_CONFIDENCE_THRESHOLD = 0.5
    # Confidence adjustment per positive / negative feedback
    FEEDBACK_WEIGHT = 0.1

    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.learned_patterns_file = self.data_dir / "learned_patterns.json"
        self.feedback_log_file = self.data_dir / "pattern_feedback.json"

        self.learned_patterns: Dict[str, LearnedPattern] = {}
        self.feedback_log: List[PatternFeedback] = []

        # Raw occurrence counters keyed by (language, normalised_snippet)
        self._occurrence_counter: Counter = Counter()
        # Fix outcome counters keyed by pattern_id
        self._fix_outcomes: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"success": 0, "failure": 0}
        )

        self._load_state()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        """Load persisted learned patterns and feedback."""
        if self.learned_patterns_file.exists():
            try:
                data = json.loads(self.learned_patterns_file.read_text())
                for pid, pdata in data.items():
                    self.learned_patterns[pid] = LearnedPattern(**pdata)
            except (json.JSONDecodeError, TypeError):
                pass

        if self.feedback_log_file.exists():
            try:
                entries = json.loads(self.feedback_log_file.read_text())
                self.feedback_log = [PatternFeedback(**e) for e in entries]
                # Rebuild fix-outcome counters from persisted feedback
                for fb in self.feedback_log:
                    key = "success" if fb.was_correct else "failure"
                    self._fix_outcomes[fb.pattern_id][key] += 1
            except (json.JSONDecodeError, TypeError):
                pass

    def _save_state(self) -> None:
        """Persist learned patterns and feedback to disk."""
        patterns_data = {pid: p.to_dict() for pid, p in self.learned_patterns.items()}
        self.learned_patterns_file.write_text(json.dumps(patterns_data, indent=2))

        feedback_data = [fb.to_dict() for fb in self.feedback_log]
        self.feedback_log_file.write_text(json.dumps(feedback_data, indent=2))

    # ------------------------------------------------------------------
    # Core learning
    # ------------------------------------------------------------------

    def analyse_code_snippet(self, code: str, language: str, file_path: str = "") -> List[str]:
        """
        Analyse a code snippet and record candidate patterns.

        Returns a list of candidate pattern IDs that were updated.
        """
        candidates = self._extract_candidate_patterns(code, language)
        updated: List[str] = []

        for regex, sample in candidates:
            key = (language.lower(), regex)
            self._occurrence_counter[key] += 1
            count = self._occurrence_counter[key]

            pid = self._make_pattern_id(language, regex)

            if pid in self.learned_patterns:
                # Update existing pattern
                p = self.learned_patterns[pid]
                p.occurrence_count = count
                p.last_seen = datetime.now().isoformat()
                if sample not in p.sample_matches:
                    p.sample_matches = (p.sample_matches + [sample])[:10]
                p.confidence = self._calculate_confidence(pid, count)
                updated.append(pid)
            elif count >= self.MIN_OCCURRENCES_FOR_PATTERN:
                # Promote candidate to a learned pattern
                now = datetime.now().isoformat()
                new_pattern = LearnedPattern(
                    pattern_id=pid,
                    language=language,
                    pattern_regex=regex,
                    description=self._generate_description(regex, language),
                    sample_matches=[sample],
                    occurrence_count=count,
                    confidence=self._calculate_confidence(pid, count),
                    fix_success_rate=0.0,
                    first_seen=now,
                    last_seen=now,
                    tags=[language.lower(), "auto-learned"],
                )
                self.learned_patterns[pid] = new_pattern
                updated.append(pid)

        if updated:
            self._save_state()
        return updated

    def _extract_candidate_patterns(self, code: str, language: str) -> List[Tuple[str, str]]:
        """
        Extract candidate error patterns from raw code.

        Returns a list of (regex_pattern, sample_text) tuples.
        """
        candidates: List[Tuple[str, str]] = []
        lang = language.lower()

        # --- Generic patterns (all languages) ---
        generic_checks = [
            # Deeply nested callbacks / closures
            (r"\}\s*\)\s*\}\s*\)\s*\}", "deeply nested closures"),
            # Very long single lines (>120 chars) — potential readability issue
        ]
        for regex, _ in generic_checks:
            for m in re.finditer(regex, code):
                candidates.append((regex, m.group()))

        # Long lines
        for line in code.splitlines():
            if len(line) > 120:
                candidates.append((r".{121,}", line[:80]))

        # --- Language-specific patterns ---
        if lang in ("javascript", "js", "typescript", "ts"):
            js_patterns = [
                r"var\s+\w+",                       # var usage (prefer let/const)
                r"==\s*null",                        # loose null check
                r"eval\s*\(",                        # eval usage
                r"document\.write\s*\(",             # document.write
                r"setTimeout\s*\(\s*['\"]",          # setTimeout with string
            ]
            for regex in js_patterns:
                for m in re.finditer(regex, code):
                    candidates.append((regex, m.group()))

        elif lang in ("python", "py"):
            py_patterns = [
                r"except\s*:",                       # bare except
                r"print\s*\(",                       # print statements (possible debug)
                r"import\s+\*",                      # wildcard import
                r"os\.system\s*\(",                  # os.system call
                r"exec\s*\(",                        # exec() usage
            ]
            for regex in py_patterns:
                for m in re.finditer(regex, code):
                    candidates.append((regex, m.group()))

        elif lang in ("html",):
            html_patterns = [
                r"<[^>]+\s+style\s*=",              # inline styles
                r"<script[^>]*>(?!.*src)",           # inline script blocks
                r"onclick\s*=",                      # inline event handlers
                r"<table",                           # table layout usage
            ]
            for regex in html_patterns:
                for m in re.finditer(regex, code, re.IGNORECASE):
                    candidates.append((regex, m.group()))

        elif lang in ("css",):
            css_patterns = [
                r"!important",                       # !important overuse
                r"position\s*:\s*absolute",          # absolute positioning
                r"z-index\s*:\s*9{3,}",             # extreme z-index
            ]
            for regex in css_patterns:
                for m in re.finditer(regex, code, re.IGNORECASE):
                    candidates.append((regex, m.group()))

        return candidates

    # ------------------------------------------------------------------
    # Feedback
    # ------------------------------------------------------------------

    def record_feedback(
        self,
        pattern_id: str,
        file_path: str,
        was_correct: bool,
        suggested_fix: Optional[str] = None,
        notes: str = "",
    ) -> bool:
        """
        Record user or system feedback for a pattern detection.

        Updates the pattern's confidence and fix_success_rate.
        Returns True if the pattern was found and updated.
        """
        fb = PatternFeedback(
            pattern_id=pattern_id,
            file_path=file_path,
            was_correct=was_correct,
            suggested_fix=suggested_fix,
            timestamp=datetime.now().isoformat(),
            notes=notes,
        )
        self.feedback_log.append(fb)

        key = "success" if was_correct else "failure"
        self._fix_outcomes[pattern_id][key] += 1

        if pattern_id in self.learned_patterns:
            p = self.learned_patterns[pattern_id]
            # Adjust confidence
            delta = self.FEEDBACK_WEIGHT if was_correct else -self.FEEDBACK_WEIGHT
            p.confidence = max(0.0, min(1.0, p.confidence + delta))
            # Recalculate fix success rate
            outcomes = self._fix_outcomes[pattern_id]
            total = outcomes["success"] + outcomes["failure"]
            p.fix_success_rate = outcomes["success"] / total if total > 0 else 0.0
            self._save_state()
            return True

        self._save_state()
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_suggestions(self, language: str, min_confidence: Optional[float] = None) -> List[LearnedPattern]:
        """
        Return learned patterns for *language* above the confidence threshold.
        """
        threshold = min_confidence if min_confidence is not None else self.MIN_CONFIDENCE_THRESHOLD
        lang = language.lower()
        return [
            p for p in self.learned_patterns.values()
            if p.language.lower() == lang and p.confidence >= threshold
        ]

    def get_all_patterns(self) -> List[LearnedPattern]:
        """Return all learned patterns."""
        return list(self.learned_patterns.values())

    def get_pattern(self, pattern_id: str) -> Optional[LearnedPattern]:
        """Return a specific learned pattern by ID."""
        return self.learned_patterns.get(pattern_id)

    def get_learning_stats(self) -> Dict[str, Any]:
        """Return a summary of the learning system's state."""
        patterns = list(self.learned_patterns.values())
        by_lang: Counter = Counter(p.language for p in patterns)
        avg_confidence = (
            sum(p.confidence for p in patterns) / len(patterns) if patterns else 0.0
        )
        return {
            "total_learned_patterns": len(patterns),
            "patterns_by_language": dict(by_lang),
            "average_confidence": round(avg_confidence, 3),
            "total_feedback_entries": len(self.feedback_log),
            "candidate_snippets_observed": len(self._occurrence_counter),
            "high_confidence_patterns": sum(
                1 for p in patterns if p.confidence >= 0.8
            ),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_pattern_id(language: str, regex: str) -> str:
        digest = hashlib.sha256(f"{language.lower()}:{regex}".encode()).hexdigest()[:12]
        return f"learned_{language.lower()}_{digest}"

    @staticmethod
    def _generate_description(regex: str, language: str) -> str:
        return f"Auto-learned {language} pattern matching: {regex[:60]}"

    def _calculate_confidence(self, pattern_id: str, occurrence_count: int) -> float:
        """
        Confidence is a combination of:
        * Occurrence frequency (logarithmic saturation)
        * Fix success rate from feedback
        """
        # Frequency component: saturates around 10+ occurrences
        freq_score = min(1.0, math.log(occurrence_count + 1) / math.log(11))

        outcomes = self._fix_outcomes.get(pattern_id, {"success": 0, "failure": 0})
        total = outcomes["success"] + outcomes["failure"]
        fix_score = outcomes["success"] / total if total > 0 else 0.5  # neutral prior

        # Weighted average: frequency 60%, fix success 40%
        return round(0.6 * freq_score + 0.4 * fix_score, 3)
