"""
Browser Integration Module
============================

Detects issues in browser-rendered HTML/CSS/JS content by statically
analysing markup for common browser-compatibility, accessibility, and
rendering problems — without requiring a headless browser.

Phase 3 Feature - Genesis QuickFix Generator
"""

import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class BrowserIssue:
    """Represents a single issue found during browser-compatibility analysis."""
    issue_id: str
    issue_type: str          # "compatibility", "accessibility", "performance", "rendering"
    severity: str            # "critical", "high", "medium", "low"
    browser_targets: List[str]  # affected browsers, e.g. ["ie11", "safari"]
    description: str
    element_snippet: str
    line_number: int
    suggestion: str
    mdn_reference: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BrowserAnalysisResult:
    """Aggregated result of analysing an HTML/CSS/JS resource."""
    file_path: str
    file_type: str
    issues: List[BrowserIssue]
    analysed_at: str
    compatibility_score: float   # 0.0 (many issues) – 1.0 (perfect)
    summary: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        d = asdict(self)
        return d


class BrowserIntegration:
    """
    Static analyser for browser-compatibility and rendering issues.

    Checks HTML, CSS, and JavaScript files for:
    * Deprecated / removed browser APIs
    * Missing vendor prefixes
    * Accessibility attribute omissions
    * Inline-script / mixed-content concerns
    * Layout patterns with poor cross-browser support
    """

    # CSS properties that require vendor prefixes in older browsers
    VENDOR_PREFIX_REQUIRED = {
        "animation": ["-webkit-animation"],
        "transition": ["-webkit-transition"],
        "transform": ["-webkit-transform", "-ms-transform"],
        "flex": ["-webkit-flex", "-ms-flex"],
        "grid": ["-ms-grid"],
        "user-select": ["-webkit-user-select", "-moz-user-select", "-ms-user-select"],
        "appearance": ["-webkit-appearance", "-moz-appearance"],
        "backdrop-filter": ["-webkit-backdrop-filter"],
    }

    # Deprecated HTML elements
    DEPRECATED_HTML_ELEMENTS = [
        "font", "center", "big", "strike", "tt", "u", "s",
        "basefont", "applet", "acronym", "bgsound", "dir",
        "frame", "frameset", "noframes", "isindex", "listing",
        "xmp", "nextid", "noembed",
    ]

    # Deprecated HTML attributes (element, attribute)
    DEPRECATED_HTML_ATTRS = [
        ("*", "bgcolor"),
        ("*", "color"),
        ("*", "face"),
        ("*", "border"),
        ("img", "border"),
        ("table", "cellpadding"),
        ("table", "cellspacing"),
        ("table", "width"),
        ("body", "text"),
        ("body", "link"),
        ("body", "vlink"),
        ("body", "alink"),
    ]

    # JS APIs removed or problematic in modern/strict contexts
    PROBLEMATIC_JS_PATTERNS = [
        (r"\bdocument\.write\s*\(", "document.write() blocks rendering", "performance", "high",
         ["all modern browsers"], "Use DOM manipulation instead of document.write()"),
        (r"\beval\s*\(", "eval() is a security and performance risk", "compatibility", "high",
         ["all browsers"], "Avoid eval(); use JSON.parse() for data, Function for dynamic code"),
        (r"window\.attachEvent\s*\(", "attachEvent is IE-only and removed in modern browsers",
         "compatibility", "critical", ["ie"], "Use addEventListener() instead"),
        (r"\.innerText\b", "innerText has inconsistent behaviour across browsers",
         "compatibility", "medium", ["older browsers"], "Prefer textContent for consistency"),
        (r"\bXMLHttpRequest\b", "XMLHttpRequest is legacy; Fetch API is preferred",
         "compatibility", "low", ["ie11"], "Consider using the Fetch API or axios"),
        (r"setTimeout\s*\(\s*['\"]", "String argument to setTimeout is deprecated",
         "compatibility", "medium", ["all browsers"], "Pass a function reference, not a string"),
    ]

    def __init__(self, report_dir: str = "."):
        self.report_dir = Path(report_dir)
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._issue_counter = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse_file(self, file_path: str) -> BrowserAnalysisResult:
        """Analyse a single file and return a BrowserAnalysisResult."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = path.read_text(errors="replace")
        ext = path.suffix.lower().lstrip(".")

        file_type_map = {
            "html": "html", "htm": "html",
            "css": "css",
            "js": "javascript", "ts": "javascript",
        }
        file_type = file_type_map.get(ext, "html")

        issues = self._analyse_content(content, file_type, file_path)
        return self._build_result(file_path, file_type, issues)

    def analyse_content(self, content: str, file_type: str, source_name: str = "<inline>") -> BrowserAnalysisResult:
        """Analyse raw content string and return a BrowserAnalysisResult."""
        issues = self._analyse_content(content, file_type.lower(), source_name)
        return self._build_result(source_name, file_type.lower(), issues)

    def save_report(self, result: BrowserAnalysisResult) -> str:
        """Save analysis result as a JSON report; return the report path."""
        safe_name = re.sub(r"[^\w\-.]", "_", Path(result.file_path).name)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.report_dir / f"browser_report_{safe_name}_{ts}.json"
        report_path.write_text(json.dumps(result.to_dict(), indent=2))
        return str(report_path)

    # ------------------------------------------------------------------
    # Analysis implementation
    # ------------------------------------------------------------------

    def _analyse_content(self, content: str, file_type: str, source: str) -> List[BrowserIssue]:
        issues: List[BrowserIssue] = []
        if file_type == "html":
            issues += self._check_html(content, source)
        elif file_type == "css":
            issues += self._check_css(content, source)
        elif file_type == "javascript":
            issues += self._check_js(content, source)
        return issues

    def _check_html(self, content: str, source: str) -> List[BrowserIssue]:
        issues: List[BrowserIssue] = []
        lines = content.splitlines()

        for lineno, line in enumerate(lines, start=1):
            line_lower = line.lower()

            # Deprecated elements
            for elem in self.DEPRECATED_HTML_ELEMENTS:
                if re.search(rf"<{elem}[\s>/]", line_lower):
                    issues.append(self._make_issue(
                        "compatibility", "medium",
                        ["all modern browsers"],
                        f"Deprecated HTML element <{elem}>",
                        line.strip(), lineno,
                        f"Replace <{elem}> with a CSS-styled semantic element",
                        f"https://developer.mozilla.org/docs/Web/HTML/Element/{elem}",
                    ))

            # Deprecated attributes
            for _elem, attr in self.DEPRECATED_HTML_ATTRS:
                if re.search(rf'\b{attr}\s*=', line_lower):
                    issues.append(self._make_issue(
                        "compatibility", "medium",
                        ["all modern browsers"],
                        f"Deprecated HTML attribute '{attr}'",
                        line.strip(), lineno,
                        f"Remove '{attr}' attribute and use CSS instead",
                    ))

            # Missing alt on img
            if re.search(r"<img\b", line_lower) and "alt=" not in line_lower:
                issues.append(self._make_issue(
                    "accessibility", "high",
                    ["all browsers"],
                    "Image missing required alt attribute",
                    line.strip(), lineno,
                    "Add alt='description' to every <img> element",
                    "https://developer.mozilla.org/docs/Web/HTML/Element/img#attr-alt",
                ))

            # Missing lang on html
            if re.search(r"<html\b", line_lower) and "lang=" not in line_lower:
                issues.append(self._make_issue(
                    "accessibility", "medium",
                    ["all browsers"],
                    "<html> element missing lang attribute",
                    line.strip(), lineno,
                    "Add lang='en' (or appropriate language code) to <html>",
                    "https://developer.mozilla.org/docs/Web/HTML/Global_attributes/lang",
                ))

            # Inline event handlers
            if re.search(r'\s(onclick|onload|onerror|onsubmit|onkeydown)\s*=', line_lower):
                issues.append(self._make_issue(
                    "compatibility", "low",
                    ["all browsers"],
                    "Inline event handler detected (tight HTML/JS coupling)",
                    line.strip(), lineno,
                    "Move event handling to a JavaScript file using addEventListener()",
                ))

            # Inline styles
            if re.search(r'\bstyle\s*=\s*["\']', line_lower):
                issues.append(self._make_issue(
                    "rendering", "low",
                    ["all browsers"],
                    "Inline style attribute reduces maintainability",
                    line.strip(), lineno,
                    "Move styles to an external CSS file or <style> block",
                ))

            # Mixed content (http in https context)
            if re.search(r'src\s*=\s*["\']http://', line_lower):
                issues.append(self._make_issue(
                    "compatibility", "critical",
                    ["all modern browsers"],
                    "Mixed content: HTTP resource in potentially HTTPS page",
                    line.strip(), lineno,
                    "Use HTTPS URLs for all external resources",
                    "https://developer.mozilla.org/docs/Web/Security/Mixed_content",
                ))

        # Missing viewport meta
        if "<meta" in content.lower() and "viewport" not in content.lower():
            issues.append(self._make_issue(
                "rendering", "high",
                ["mobile browsers"],
                "Missing viewport meta tag — page may not scale on mobile",
                "<head>...</head>", 0,
                'Add <meta name="viewport" content="width=device-width, initial-scale=1">',
                "https://developer.mozilla.org/docs/Web/HTML/Viewport_meta_tag",
            ))

        # Missing charset
        if "<meta" in content.lower() and "charset" not in content.lower():
            issues.append(self._make_issue(
                "compatibility", "medium",
                ["all browsers"],
                "Missing charset declaration",
                "<head>...</head>", 0,
                'Add <meta charset="UTF-8"> as the first element inside <head>',
            ))

        return issues

    def _check_css(self, content: str, source: str) -> List[BrowserIssue]:
        issues: List[BrowserIssue] = []
        lines = content.splitlines()

        for lineno, line in enumerate(lines, start=1):
            line_stripped = line.strip()

            # Check for properties that need vendor prefixes
            for prop, prefixes in self.VENDOR_PREFIX_REQUIRED.items():
                if re.search(rf'\b{re.escape(prop)}\s*:', line_stripped, re.IGNORECASE):
                    missing = [p for p in prefixes if p not in content]
                    if missing:
                        issues.append(self._make_issue(
                            "compatibility", "medium",
                            ["older browsers"],
                            f"CSS property '{prop}' may need vendor prefix(es): {', '.join(missing)}",
                            line_stripped, lineno,
                            f"Add {', '.join(missing)} before the standard property",
                            f"https://developer.mozilla.org/docs/Web/CSS/{prop}",
                        ))

            # !important overuse
            if "!important" in line_stripped:
                issues.append(self._make_issue(
                    "rendering", "low",
                    ["all browsers"],
                    "!important declaration reduces CSS maintainability",
                    line_stripped, lineno,
                    "Refactor specificity instead of using !important",
                ))

            # Absolute positioning
            if re.search(r'position\s*:\s*absolute', line_stripped, re.IGNORECASE):
                issues.append(self._make_issue(
                    "rendering", "low",
                    ["all browsers"],
                    "position:absolute can cause layout issues across screen sizes",
                    line_stripped, lineno,
                    "Consider using flexbox/grid layout instead",
                ))

        return issues

    def _check_js(self, content: str, source: str) -> List[BrowserIssue]:
        issues: List[BrowserIssue] = []
        lines = content.splitlines()

        for regex, desc, itype, severity, browsers, suggestion in self.PROBLEMATIC_JS_PATTERNS:
            for m in re.finditer(regex, content):
                lineno = content[:m.start()].count("\n") + 1
                snippet = lines[lineno - 1].strip() if lineno <= len(lines) else m.group()
                issues.append(self._make_issue(
                    itype, severity, browsers, desc, snippet, lineno, suggestion
                ))

        return issues

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_issue(
        self,
        issue_type: str,
        severity: str,
        browser_targets: List[str],
        description: str,
        element_snippet: str,
        line_number: int,
        suggestion: str,
        mdn_reference: str = "",
    ) -> BrowserIssue:
        self._issue_counter += 1
        return BrowserIssue(
            issue_id=f"browser_{self._issue_counter:04d}",
            issue_type=issue_type,
            severity=severity,
            browser_targets=browser_targets,
            description=description,
            element_snippet=element_snippet[:200],
            line_number=line_number,
            suggestion=suggestion,
            mdn_reference=mdn_reference,
        )

    def _build_result(self, file_path: str, file_type: str, issues: List[BrowserIssue]) -> BrowserAnalysisResult:
        severity_weights = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        total_weight = sum(severity_weights.get(i.severity, 1) for i in issues)
        # Compatibility score: perfect=1.0, degrades with weighted issue count
        score = max(0.0, 1.0 - total_weight * 0.05)
        score = round(min(1.0, score), 3)

        summary = {
            "total": len(issues),
            "critical": sum(1 for i in issues if i.severity == "critical"),
            "high": sum(1 for i in issues if i.severity == "high"),
            "medium": sum(1 for i in issues if i.severity == "medium"),
            "low": sum(1 for i in issues if i.severity == "low"),
        }

        return BrowserAnalysisResult(
            file_path=file_path,
            file_type=file_type,
            issues=issues,
            analysed_at=datetime.now().isoformat(),
            compatibility_score=score,
            summary=summary,
        )
