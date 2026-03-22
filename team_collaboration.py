"""
Team Collaboration Module
==========================

Enables teams to share fix solutions, templates, and learned patterns
across members via a shared workspace directory or JSON-based exchange
format (suitable for version-control or network-mounted shares).

Phase 3 Feature - Genesis QuickFix Generator
"""

import json
import uuid
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SharedSolution:
    """A fix solution shared by a team member."""
    solution_id: str
    title: str
    description: str
    language: str
    error_pattern: str
    fix_code: str
    author: str
    tags: List[str]
    created_at: str
    updated_at: str
    upvotes: int = 0
    downvotes: int = 0
    usage_count: int = 0
    is_verified: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TeamComment:
    """A comment attached to a shared solution."""
    comment_id: str
    solution_id: str
    author: str
    content: str
    created_at: str
    parent_comment_id: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TeamMember:
    """A registered team member."""
    member_id: str
    username: str
    display_name: str
    role: str          # "admin", "contributor", "viewer"
    joined_at: str
    solutions_shared: int = 0
    solutions_used: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CollaborationActivity:
    """An audit-log entry recording a team action."""
    activity_id: str
    activity_type: str   # "solution_shared", "solution_used", "comment_added", "member_joined"
    actor: str
    target_id: str
    details: str
    timestamp: str

    def to_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class TeamCollaboration:
    """
    Manages sharing of fix solutions, templates, and activity across a team.

    All data is persisted as human-readable JSON files in *collab_dir* which
    can be placed under version control or on a shared network path.
    """

    def __init__(self, collab_dir: str = ".", current_user: str = "anonymous"):
        self.collab_dir = Path(collab_dir)
        self.collab_dir.mkdir(parents=True, exist_ok=True)
        self.current_user = current_user

        self._solutions_file = self.collab_dir / "shared_solutions.json"
        self._comments_file = self.collab_dir / "solution_comments.json"
        self._members_file = self.collab_dir / "team_members.json"
        self._activity_file = self.collab_dir / "collaboration_activity.json"

        self.solutions: Dict[str, SharedSolution] = {}
        self.comments: Dict[str, TeamComment] = {}
        self.members: Dict[str, TeamMember] = {}
        self.activity_log: List[CollaborationActivity] = []

        self._load_all()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        self.solutions = self._load_records(self._solutions_file, SharedSolution)
        self.comments = self._load_records(self._comments_file, TeamComment)
        self.members = self._load_records(self._members_file, TeamMember)
        if self._activity_file.exists():
            try:
                entries = json.loads(self._activity_file.read_text())
                self.activity_log = [CollaborationActivity(**e) for e in entries]
            except (json.JSONDecodeError, TypeError):
                self.activity_log = []

    @staticmethod
    def _load_records(path: Path, cls) -> Dict:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text())
            return {k: cls(**v) for k, v in data.items()}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _save_all(self) -> None:
        self._solutions_file.write_text(
            json.dumps({k: v.to_dict() for k, v in self.solutions.items()}, indent=2)
        )
        self._comments_file.write_text(
            json.dumps({k: v.to_dict() for k, v in self.comments.items()}, indent=2)
        )
        self._members_file.write_text(
            json.dumps({k: v.to_dict() for k, v in self.members.items()}, indent=2)
        )
        self._activity_file.write_text(
            json.dumps([a.to_dict() for a in self.activity_log], indent=2)
        )

    # ------------------------------------------------------------------
    # Members
    # ------------------------------------------------------------------

    def register_member(self, username: str, display_name: str, role: str = "contributor") -> TeamMember:
        """Register a new team member (idempotent — returns existing member if already registered)."""
        mid = self._make_id("member", username)
        if mid in self.members:
            return self.members[mid]

        member = TeamMember(
            member_id=mid,
            username=username,
            display_name=display_name,
            role=role,
            joined_at=datetime.now().isoformat(),
        )
        self.members[mid] = member
        self._record_activity("member_joined", username, mid, f"{display_name} joined the team")
        self._save_all()
        return member

    def get_member(self, username: str) -> Optional[TeamMember]:
        mid = self._make_id("member", username)
        return self.members.get(mid)

    def list_members(self) -> List[TeamMember]:
        return list(self.members.values())

    # ------------------------------------------------------------------
    # Solutions
    # ------------------------------------------------------------------

    def share_solution(
        self,
        title: str,
        description: str,
        language: str,
        error_pattern: str,
        fix_code: str,
        tags: Optional[List[str]] = None,
        author: Optional[str] = None,
    ) -> SharedSolution:
        """Share a new fix solution with the team."""
        author = author or self.current_user
        now = datetime.now().isoformat()
        sid = self._make_id("solution", f"{author}:{title}:{now}")
        solution = SharedSolution(
            solution_id=sid,
            title=title,
            description=description,
            language=language,
            error_pattern=error_pattern,
            fix_code=fix_code,
            author=author,
            tags=tags or [],
            created_at=now,
            updated_at=now,
        )
        self.solutions[sid] = solution
        # Update member statistics
        self._increment_member_stat(author, "solutions_shared")
        self._record_activity("solution_shared", author, sid, f"Shared solution: {title}")
        self._save_all()
        return solution

    def get_solution(self, solution_id: str) -> Optional[SharedSolution]:
        return self.solutions.get(solution_id)

    def search_solutions(
        self,
        language: Optional[str] = None,
        tags: Optional[List[str]] = None,
        query: Optional[str] = None,
    ) -> List[SharedSolution]:
        """Search shared solutions with optional filters."""
        results = list(self.solutions.values())
        if language:
            results = [s for s in results if s.language.lower() == language.lower()]
        if tags:
            tag_set = {t.lower() for t in tags}
            results = [s for s in results if tag_set.intersection({t.lower() for t in s.tags})]
        if query:
            q = query.lower()
            results = [
                s for s in results
                if q in s.title.lower() or q in s.description.lower() or q in s.fix_code.lower()
            ]
        # Sort by upvotes desc, then usage_count desc
        results.sort(key=lambda s: (s.upvotes, s.usage_count), reverse=True)
        return results

    def mark_solution_used(self, solution_id: str, user: Optional[str] = None) -> bool:
        """Record that a solution was applied by a team member."""
        s = self.solutions.get(solution_id)
        if not s:
            return False
        s.usage_count += 1
        user = user or self.current_user
        self._increment_member_stat(user, "solutions_used")
        self._record_activity("solution_used", user, solution_id, f"Used solution: {s.title}")
        self._save_all()
        return True

    def vote_solution(self, solution_id: str, upvote: bool, user: Optional[str] = None) -> bool:
        """Upvote or downvote a solution."""
        s = self.solutions.get(solution_id)
        if not s:
            return False
        if upvote:
            s.upvotes += 1
        else:
            s.downvotes += 1
        user = user or self.current_user
        vote_type = "upvoted" if upvote else "downvoted"
        self._record_activity("solution_voted", user, solution_id, f"{vote_type} solution: {s.title}")
        self._save_all()
        return True

    def verify_solution(self, solution_id: str) -> bool:
        """Mark a solution as verified (admin action)."""
        s = self.solutions.get(solution_id)
        if not s:
            return False
        s.is_verified = True
        s.updated_at = datetime.now().isoformat()
        self._record_activity("solution_verified", self.current_user, solution_id,
                              f"Verified solution: {s.title}")
        self._save_all()
        return True

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def add_comment(
        self,
        solution_id: str,
        content: str,
        author: Optional[str] = None,
        parent_comment_id: Optional[str] = None,
    ) -> Optional[TeamComment]:
        """Add a comment to a solution."""
        if solution_id not in self.solutions:
            return None
        author = author or self.current_user
        cid = self._make_id("comment", f"{solution_id}:{author}:{datetime.now().isoformat()}")
        comment = TeamComment(
            comment_id=cid,
            solution_id=solution_id,
            author=author,
            content=content,
            created_at=datetime.now().isoformat(),
            parent_comment_id=parent_comment_id,
        )
        self.comments[cid] = comment
        self._record_activity("comment_added", author, solution_id,
                              f"Commented on solution {solution_id}")
        self._save_all()
        return comment

    def get_comments(self, solution_id: str) -> List[TeamComment]:
        """Return all top-level comments for a solution (oldest first)."""
        result = [c for c in self.comments.values() if c.solution_id == solution_id]
        result.sort(key=lambda c: c.created_at)
        return result

    # ------------------------------------------------------------------
    # Activity / Stats
    # ------------------------------------------------------------------

    def get_activity_feed(self, limit: int = 50) -> List[CollaborationActivity]:
        """Return the most recent activity entries."""
        return sorted(self.activity_log, key=lambda a: a.timestamp, reverse=True)[:limit]

    def get_team_stats(self) -> Dict[str, Any]:
        """Return aggregate team collaboration statistics."""
        return {
            "total_members": len(self.members),
            "total_solutions": len(self.solutions),
            "total_comments": len(self.comments),
            "total_activity_events": len(self.activity_log),
            "verified_solutions": sum(1 for s in self.solutions.values() if s.is_verified),
            "most_used_solution": self._most_used_solution(),
            "top_contributor": self._top_contributor(),
            "solutions_by_language": self._solutions_by_language(),
        }

    # ------------------------------------------------------------------
    # Export / Import
    # ------------------------------------------------------------------

    def export_solutions(self, output_path: str, language: Optional[str] = None) -> str:
        """Export solutions to a portable JSON file."""
        solutions = self.search_solutions(language=language)
        data = {
            "exported_at": datetime.now().isoformat(),
            "exported_by": self.current_user,
            "language_filter": language,
            "solutions": [s.to_dict() for s in solutions],
        }
        Path(output_path).write_text(json.dumps(data, indent=2))
        return output_path

    def import_solutions(self, input_path: str) -> int:
        """Import solutions from a JSON export file; returns number imported."""
        data = json.loads(Path(input_path).read_text())
        count = 0
        for sdata in data.get("solutions", []):
            sid = sdata["solution_id"]
            if sid not in self.solutions:
                self.solutions[sid] = SharedSolution(**sdata)
                count += 1
        if count:
            self._save_all()
        return count

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_id(prefix: str, seed: str) -> str:
        digest = hashlib.sha256(seed.encode()).hexdigest()[:16]
        return f"{prefix}_{digest}"

    def _record_activity(self, activity_type: str, actor: str, target_id: str, details: str) -> None:
        entry = CollaborationActivity(
            activity_id=str(uuid.uuid4()),
            activity_type=activity_type,
            actor=actor,
            target_id=target_id,
            details=details,
            timestamp=datetime.now().isoformat(),
        )
        self.activity_log.append(entry)

    def _increment_member_stat(self, username: str, stat: str) -> None:
        mid = self._make_id("member", username)
        member = self.members.get(mid)
        if member:
            current = getattr(member, stat, 0)
            setattr(member, stat, current + 1)

    def _most_used_solution(self) -> Optional[str]:
        if not self.solutions:
            return None
        best = max(self.solutions.values(), key=lambda s: s.usage_count)
        return best.title if best.usage_count > 0 else None

    def _top_contributor(self) -> Optional[str]:
        if not self.members:
            return None
        best = max(self.members.values(), key=lambda m: m.solutions_shared)
        return best.username if best.solutions_shared > 0 else None

    def _solutions_by_language(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for s in self.solutions.values():
            counts[s.language] = counts.get(s.language, 0) + 1
        return counts
