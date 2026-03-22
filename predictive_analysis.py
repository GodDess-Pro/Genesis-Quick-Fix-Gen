"""
Predictive Analysis Module
============================

Analyses code repositories and historical error data to predict
potential issues before they are introduced — enabling proactive
rather than reactive quality control.

Phase 4 Feature - Genesis QuickFix Generator
"""

import re
import json
import math
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RiskSignal:
    """A single risk indicator extracted from code or history."""
    signal_id: str
    signal_type: str        # "code_smell", "complexity", "historical", "pattern_proximity"
    severity: str           # "critical", "high", "medium", "low"
    description: str
    file_path: str
    line_number: int
    evidence: str           # short code excerpt or metric value
    remediation: str


@dataclass
class PredictedIssue:
    """A predicted future issue derived from one or more risk signals."""
    prediction_id: str
    title: str
    description: str
    predicted_error_type: str
    probability: float      # 0.0 – 1.0
    impact: str             # "critical", "high", "medium", "low"
    file_path: str
    line_number: int
    risk_signals: List[str]  # list of signal_ids
    suggested_actions: List[str]
    predicted_at: str
    confidence: float       # 0.0 – 1.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FileRiskProfile:
    """Aggregated risk assessment for a single file."""
    file_path: str
    language: str
    overall_risk_score: float   # 0.0 (no risk) – 1.0 (very high)
    risk_level: str             # "critical", "high", "medium", "low", "minimal"
    signals: List[RiskSignal]
    predictions: List[PredictedIssue]
    metrics: Dict[str, Any]
    assessed_at: str

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class PredictiveAnalyzer:
    """
    Proactively identifies code that is likely to produce errors.

    Strategy:
    1. *Static risk signals* — code-level heuristics (complexity, known
       anti-patterns, missing guards, etc.)
    2. *Historical risk signals* — files with frequent past errors score
       higher risk.
    3. *Trend detection* — rapid change velocity increases risk.
    4. Signals are combined into *PredictedIssue* objects with probability
       and impact scores.
    """

    # Weights for combining signal types into a composite score
    SIGNAL_WEIGHTS = {
        "code_smell": 0.3,
        "complexity": 0.35,
        "historical": 0.25,
        "pattern_proximity": 0.1,
    }

    SEVERITY_SCORES = {"critical": 1.0, "high": 0.75, "medium": 0.5, "low": 0.25}

    def __init__(self, history_dir: str = "."):
        self.history_dir = Path(history_dir)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._history_file = self.history_dir / "error_history.json"
        self._predictions_file = self.history_dir / "predictions.json"

        # error_history: {file_path: [{"timestamp": ..., "error_type": ..., "severity": ...}]}
        self.error_history: Dict[str, List[Dict]] = defaultdict(list)
        self._predictions: List[PredictedIssue] = []
        self._signal_counter = 0
        self._prediction_counter = 0

        self._load_state()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_state(self) -> None:
        if self._history_file.exists():
            try:
                self.error_history = defaultdict(list, json.loads(self._history_file.read_text()))
            except (json.JSONDecodeError, TypeError):
                pass
        if self._predictions_file.exists():
            try:
                data = json.loads(self._predictions_file.read_text())
                self._predictions = [PredictedIssue(**p) for p in data]
                if self._predictions:
                    self._prediction_counter = max(
                        int(p.prediction_id.split("_")[-1]) for p in self._predictions
                        if p.prediction_id.split("_")[-1].isdigit()
                    )
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

    def _save_state(self) -> None:
        self._history_file.write_text(json.dumps(dict(self.error_history), indent=2))
        self._predictions_file.write_text(
            json.dumps([p.to_dict() for p in self._predictions], indent=2)
        )

    # ------------------------------------------------------------------
    # History recording
    # ------------------------------------------------------------------

    def record_error(self, file_path: str, error_type: str, severity: str) -> None:
        """Record an error occurrence for historical analysis."""
        self.error_history[file_path].append({
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "severity": severity,
        })
        self._save_state()

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def analyse_file(self, file_path: str) -> FileRiskProfile:
        """Run predictive analysis on a single file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_text(errors="replace")
        ext = path.suffix.lower().lstrip(".")
        language = self._detect_language(ext)

        signals = self._extract_risk_signals(content, language, file_path)
        signals += self._historical_signals(file_path)

        predictions = self._generate_predictions(signals, file_path)
        metrics = self._compute_metrics(content, language)
        risk_score = self._compute_risk_score(signals)
        risk_level = self._risk_level(risk_score)

        profile = FileRiskProfile(
            file_path=file_path,
            language=language,
            overall_risk_score=round(risk_score, 3),
            risk_level=risk_level,
            signals=signals,
            predictions=predictions,
            metrics=metrics,
            assessed_at=datetime.now().isoformat(),
        )

        # Persist new predictions
        self._predictions.extend(predictions)
        self._save_state()
        return profile

    def analyse_content(self, content: str, language: str, source_name: str = "<inline>") -> FileRiskProfile:
        """Run predictive analysis on raw content."""
        signals = self._extract_risk_signals(content, language, source_name)
        signals += self._historical_signals(source_name)
        predictions = self._generate_predictions(signals, source_name)
        metrics = self._compute_metrics(content, language)
        risk_score = self._compute_risk_score(signals)
        risk_level = self._risk_level(risk_score)

        return FileRiskProfile(
            file_path=source_name,
            language=language,
            overall_risk_score=round(risk_score, 3),
            risk_level=risk_level,
            signals=signals,
            predictions=predictions,
            metrics=metrics,
            assessed_at=datetime.now().isoformat(),
        )

    def get_high_risk_files(self, threshold: float = 0.6) -> List[str]:
        """
        Return file paths from history that have a high predicted risk,
        based solely on error-recurrence patterns.
        """
        results: List[Tuple[str, float]] = []
        for fp, errors in self.error_history.items():
            if not errors:
                continue
            # Weight recent errors more heavily
            score = 0.0
            now = datetime.now()
            for err in errors:
                try:
                    ts = datetime.fromisoformat(err["timestamp"])
                    age_days = (now - ts).days
                    recency_factor = math.exp(-age_days / 30)  # decay over 30 days
                except (KeyError, ValueError):
                    recency_factor = 0.5
                sev = self.SEVERITY_SCORES.get(err.get("severity", "medium"), 0.5)
                score += sev * recency_factor
            # Normalise
            score = min(1.0, score / 5.0)
            if score >= threshold:
                results.append((fp, score))
        results.sort(key=lambda x: x[1], reverse=True)
        return [fp for fp, _ in results]

    def get_predictions(self, file_path: Optional[str] = None, min_probability: float = 0.0) -> List[PredictedIssue]:
        """Return stored predictions, optionally filtered by file and probability."""
        result = self._predictions
        if file_path:
            result = [p for p in result if p.file_path == file_path]
        result = [p for p in result if p.probability >= min_probability]
        result.sort(key=lambda p: p.probability, reverse=True)
        return result

    def get_summary(self) -> Dict[str, Any]:
        """Return a high-level summary of the predictive analysis state."""
        total_errors = sum(len(v) for v in self.error_history.values())
        high_risk = self.get_high_risk_files(threshold=0.6)
        return {
            "files_tracked": len(self.error_history),
            "total_errors_recorded": total_errors,
            "high_risk_files_count": len(high_risk),
            "high_risk_files": high_risk[:10],
            "total_predictions_generated": len(self._predictions),
            "recent_predictions": len([
                p for p in self._predictions
                if (datetime.now() - datetime.fromisoformat(p.predicted_at)).days < 7
            ]),
        }

    # ------------------------------------------------------------------
    # Risk signal extraction
    # ------------------------------------------------------------------

    def _extract_risk_signals(self, content: str, language: str, file_path: str) -> List[RiskSignal]:
        signals: List[RiskSignal] = []
        lang = language.lower()

        lines = content.splitlines()

        # --- Complexity signals ---
        # File length
        if len(lines) > 500:
            signals.append(self._make_signal(
                "complexity", "medium",
                f"File is very long ({len(lines)} lines) — harder to maintain",
                file_path, 0, f"{len(lines)} lines",
                "Consider splitting into smaller modules",
            ))

        # Long functions (detect by indentation block length)
        signals += self._detect_long_functions(lines, file_path)

        # Deep nesting
        max_depth = self._max_nesting_depth(content)
        if max_depth > 5:
            signals.append(self._make_signal(
                "complexity", "high" if max_depth > 7 else "medium",
                f"Deep nesting level detected (depth {max_depth})",
                file_path, 0, f"max depth: {max_depth}",
                "Refactor to reduce nesting — extract methods or use early returns",
            ))

        # --- Code smell signals ---
        if lang in ("javascript", "js", "typescript", "ts"):
            signals += self._js_smells(lines, file_path)
        elif lang in ("python", "py"):
            signals += self._python_smells(lines, file_path)
        elif lang == "html":
            signals += self._html_smells(lines, file_path)
        elif lang == "css":
            signals += self._css_smells(lines, file_path)

        # --- Generic: TODO / FIXME / HACK markers ---
        for lineno, line in enumerate(lines, start=1):
            if re.search(r'\b(TODO|FIXME|HACK|XXX|BUG)\b', line, re.IGNORECASE):
                signals.append(self._make_signal(
                    "code_smell", "low",
                    "Unresolved TODO/FIXME/HACK comment",
                    file_path, lineno, line.strip()[:100],
                    "Resolve or track in issue tracker",
                ))

        return signals

    def _detect_long_functions(self, lines: List[str], file_path: str) -> List[RiskSignal]:
        signals: List[RiskSignal] = []
        func_start = None
        func_name = ""
        indent_level = None

        for lineno, line in enumerate(lines, start=1):
            m = re.match(r'^(\s*)(def |function |async function |\w+\s*\()', line)
            if m:
                if func_start is not None:
                    length = lineno - func_start
                    if length > 60:
                        signals.append(self._make_signal(
                            "complexity", "medium",
                            f"Long function/method '{func_name}' ({length} lines)",
                            file_path, func_start, f"{length} lines",
                            "Break into smaller, single-responsibility functions",
                        ))
                func_start = lineno
                func_name = line.strip()[:50]
                indent_level = len(m.group(1))

        return signals

    def _max_nesting_depth(self, content: str) -> int:
        depth = max_depth = 0
        for ch in content:
            if ch in "{([":
                depth += 1
                max_depth = max(max_depth, depth)
            elif ch in "})]":
                depth = max(0, depth - 1)
        return max_depth

    def _js_smells(self, lines: List[str], file_path: str) -> List[RiskSignal]:
        signals: List[RiskSignal] = []
        for lineno, line in enumerate(lines, start=1):
            if re.search(r'\bvar\s+\w+', line):
                signals.append(self._make_signal(
                    "code_smell", "low",
                    "Use of 'var' — prone to hoisting bugs",
                    file_path, lineno, line.strip()[:80],
                    "Replace 'var' with 'let' or 'const'",
                ))
            if re.search(r'==\s*null|null\s*==', line):
                signals.append(self._make_signal(
                    "code_smell", "medium",
                    "Loose null comparison (==) — may hide type errors",
                    file_path, lineno, line.strip()[:80],
                    "Use strict equality (=== null)",
                ))
            if re.search(r'catch\s*\(\s*\w*\s*\)\s*\{\s*\}', line):
                signals.append(self._make_signal(
                    "code_smell", "high",
                    "Empty catch block swallows errors silently",
                    file_path, lineno, line.strip()[:80],
                    "Log or re-throw caught errors",
                ))
        return signals

    def _python_smells(self, lines: List[str], file_path: str) -> List[RiskSignal]:
        signals: List[RiskSignal] = []
        for lineno, line in enumerate(lines, start=1):
            if re.match(r'\s*except\s*:', line):
                signals.append(self._make_signal(
                    "code_smell", "high",
                    "Bare 'except:' catches all exceptions including SystemExit",
                    file_path, lineno, line.strip(),
                    "Specify exception type(s): except ValueError: or except Exception as e:",
                ))
            if re.search(r'\bimport\s+\*\b', line):
                signals.append(self._make_signal(
                    "code_smell", "medium",
                    "Wildcard import pollutes namespace",
                    file_path, lineno, line.strip(),
                    "Import only what you need",
                ))
            if re.search(r'\bos\.system\s*\(', line):
                signals.append(self._make_signal(
                    "code_smell", "high",
                    "os.system() is a security risk (shell injection)",
                    file_path, lineno, line.strip(),
                    "Use subprocess.run() with a list of arguments",
                ))
        return signals

    def _html_smells(self, lines: List[str], file_path: str) -> List[RiskSignal]:
        signals: List[RiskSignal] = []
        for lineno, line in enumerate(lines, start=1):
            if re.search(r'<script[^>]*>(?!.*src)', line, re.IGNORECASE):
                signals.append(self._make_signal(
                    "code_smell", "medium",
                    "Inline <script> block — harder to maintain and cache",
                    file_path, lineno, line.strip()[:80],
                    "Move JavaScript to external .js files",
                ))
        return signals

    def _css_smells(self, lines: List[str], file_path: str) -> List[RiskSignal]:
        signals: List[RiskSignal] = []
        for lineno, line in enumerate(lines, start=1):
            if re.search(r'!important', line, re.IGNORECASE):
                signals.append(self._make_signal(
                    "code_smell", "low",
                    "!important overuse reduces CSS maintainability",
                    file_path, lineno, line.strip()[:80],
                    "Refactor CSS specificity instead of using !important",
                ))
        return signals

    def _historical_signals(self, file_path: str) -> List[RiskSignal]:
        """Generate risk signals based on past error history for this file."""
        signals: List[RiskSignal] = []
        errors = self.error_history.get(file_path, [])
        if not errors:
            return signals

        now = datetime.now()
        recent_errors = []
        for err in errors:
            try:
                ts = datetime.fromisoformat(err["timestamp"])
                if (now - ts).days <= 30:
                    recent_errors.append(err)
            except (KeyError, ValueError):
                pass

        if len(recent_errors) >= 3:
            signals.append(self._make_signal(
                "historical", "high",
                f"File had {len(recent_errors)} errors in the last 30 days",
                file_path, 0, f"{len(recent_errors)} recent errors",
                "Review and refactor this high-error-frequency file",
            ))
        elif len(recent_errors) >= 1:
            signals.append(self._make_signal(
                "historical", "medium",
                f"File had {len(recent_errors)} error(s) recently",
                file_path, 0, f"{len(recent_errors)} recent errors",
                "Monitor this file for recurring issues",
            ))

        return signals

    # ------------------------------------------------------------------
    # Prediction generation
    # ------------------------------------------------------------------

    def _generate_predictions(self, signals: List[RiskSignal], file_path: str) -> List[PredictedIssue]:
        """Cluster related signals into actionable predicted issues."""
        predictions: List[PredictedIssue] = []

        if not signals:
            return predictions

        # Group by signal_type
        by_type: Dict[str, List[RiskSignal]] = defaultdict(list)
        for s in signals:
            by_type[s.signal_type].append(s)

        for stype, group in by_type.items():
            if not group:
                continue
            # Probability based on weighted severity
            prob = min(1.0, sum(self.SEVERITY_SCORES.get(s.severity, 0.25) for s in group) / 5.0)
            # Impact level = highest severity in group
            severity_order = ["critical", "high", "medium", "low"]
            impact = min(
                [s.severity for s in group],
                key=lambda x: severity_order.index(x) if x in severity_order else 3,
            )
            confidence = min(1.0, math.log(len(group) + 1) / math.log(6))

            self._prediction_counter += 1
            pid = f"pred_{stype}_{self._prediction_counter:04d}"

            predictions.append(PredictedIssue(
                prediction_id=pid,
                title=f"{stype.replace('_', ' ').title()} Risk in {Path(file_path).name}",
                description=f"{len(group)} {stype} signal(s) detected pointing to likely future issues.",
                predicted_error_type=stype,
                probability=round(prob, 3),
                impact=impact,
                file_path=file_path,
                line_number=group[0].line_number,
                risk_signals=[s.signal_id for s in group],
                suggested_actions=list({s.remediation for s in group})[:5],
                predicted_at=datetime.now().isoformat(),
                confidence=round(confidence, 3),
            ))

        return predictions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_signal(
        self,
        signal_type: str,
        severity: str,
        description: str,
        file_path: str,
        line_number: int,
        evidence: str,
        remediation: str,
    ) -> RiskSignal:
        self._signal_counter += 1
        return RiskSignal(
            signal_id=f"sig_{self._signal_counter:05d}",
            signal_type=signal_type,
            severity=severity,
            description=description,
            file_path=file_path,
            line_number=line_number,
            evidence=evidence[:200],
            remediation=remediation,
        )

    def _compute_metrics(self, content: str, language: str) -> Dict[str, Any]:
        lines = content.splitlines()
        non_blank = [l for l in lines if l.strip()]
        comment_lines = sum(
            1 for l in lines
            if l.strip().startswith(("#", "//", "/*", "*", "<!--"))
        )
        return {
            "total_lines": len(lines),
            "non_blank_lines": len(non_blank),
            "comment_lines": comment_lines,
            "max_line_length": max((len(l) for l in lines), default=0),
            "avg_line_length": round(sum(len(l) for l in non_blank) / max(len(non_blank), 1), 1),
            "nesting_depth": self._max_nesting_depth(content),
        }

    @staticmethod
    def _compute_risk_score(signals: List[RiskSignal]) -> float:
        if not signals:
            return 0.0
        weight_map = PredictiveAnalyzer.SIGNAL_WEIGHTS
        severity_map = PredictiveAnalyzer.SEVERITY_SCORES
        weighted_sum = sum(
            weight_map.get(s.signal_type, 0.25) * severity_map.get(s.severity, 0.25)
            for s in signals
        )
        # Normalise: 10 high-weight, high-severity signals = score 1.0
        return min(1.0, weighted_sum / 10.0)

    @staticmethod
    def _risk_level(score: float) -> str:
        if score >= 0.75:
            return "critical"
        if score >= 0.5:
            return "high"
        if score >= 0.25:
            return "medium"
        if score > 0.0:
            return "low"
        return "minimal"

    @staticmethod
    def _detect_language(ext: str) -> str:
        mapping = {
            "py": "Python", "pyw": "Python",
            "js": "JavaScript", "mjs": "JavaScript",
            "ts": "TypeScript",
            "html": "HTML", "htm": "HTML",
            "css": "CSS",
            "json": "JSON",
            "md": "Markdown",
            "xml": "XML",
            "php": "PHP",
            "java": "Java",
            "cs": "C#",
            "cpp": "C++", "c": "C",
        }
        return mapping.get(ext.lower(), "Unknown")
