"""
Enhanced Diff System for QuickFix Generator
Provides advanced version comparison, side-by-side viewing, and change highlighting
"""

import difflib
import json
import html
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from diff_match_patch import diff_match_patch
import logging

logger = logging.getLogger(__name__)

@dataclass
class DiffLine:
    """Represents a single line in a diff"""
    line_type: str  # 'added', 'removed', 'modified', 'unchanged'
    line_number_old: Optional[int]
    line_number_new: Optional[int]
    content: str
    highlight_chars: List[Tuple[int, int]] = None  # Character-level highlights
    
    def __post_init__(self):
        if self.highlight_chars is None:
            self.highlight_chars = []

@dataclass
class DiffChunk:
    """Represents a chunk of changes in a diff"""
    chunk_type: str  # 'context', 'change', 'add', 'delete'
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[DiffLine]
    summary: str = ""

@dataclass
class DiffResult:
    """Complete diff analysis result"""
    old_file: str
    new_file: str
    old_version: Optional[str] = None
    new_version: Optional[str] = None
    chunks: List[DiffChunk] = None
    statistics: Dict[str, int] = None
    similarity_ratio: float = 0.0
    generated_at: datetime = None
    
    def __post_init__(self):
        if self.chunks is None:
            self.chunks = []
        if self.statistics is None:
            self.statistics = {
                'lines_added': 0,
                'lines_removed': 0,
                'lines_modified': 0,
                'lines_unchanged': 0,
                'chars_added': 0,
                'chars_removed': 0
            }
        if self.generated_at is None:
            self.generated_at = datetime.now()

class EnhancedDiffGenerator:
    """Advanced diff generation with multiple output formats"""
    
    def __init__(self):
        self.dmp = diff_match_patch()
        self.dmp.Diff_Timeout = 1.0  # 1 second timeout
        self.dmp.Diff_EditCost = 4
    
    def compare_files(self, old_file: Union[str, Path], new_file: Union[str, Path],
                     old_version: Optional[str] = None, new_version: Optional[str] = None) -> DiffResult:
        """Compare two files and generate comprehensive diff"""
        try:
            old_path = Path(old_file)
            new_path = Path(new_file)
            
            # Read file contents
            old_content = old_path.read_text(encoding='utf-8', errors='ignore')
            new_content = new_path.read_text(encoding='utf-8', errors='ignore')
            
            return self.compare_text(
                old_content, new_content,
                str(old_path), str(new_path),
                old_version, new_version
            )
            
        except Exception as e:
            logger.error(f"Error comparing files: {e}")
            return DiffResult(
                old_file=str(old_file),
                new_file=str(new_file),
                old_version=old_version,
                new_version=new_version
            )
    
    def compare_text(self, old_text: str, new_text: str,
                    old_label: str = "Original", new_label: str = "Modified",
                    old_version: Optional[str] = None, new_version: Optional[str] = None) -> DiffResult:
        """Compare two text strings and generate comprehensive diff"""
        
        result = DiffResult(
            old_file=old_label,
            new_file=new_label,
            old_version=old_version,
            new_version=new_version
        )
        
        # Calculate similarity ratio
        result.similarity_ratio = difflib.SequenceMatcher(None, old_text, new_text).ratio()
        
        # Split into lines for line-by-line comparison
        old_lines = old_text.splitlines(keepends=True)
        new_lines = new_text.splitlines(keepends=True)
        
        # Generate unified diff
        unified_diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=old_label,
            tofile=new_label,
            lineterm=''
        ))
        
        # Parse unified diff into chunks
        result.chunks = self._parse_unified_diff(unified_diff, old_lines, new_lines)
        
        # Calculate statistics
        result.statistics = self._calculate_statistics(result.chunks)
        
        return result
    
    def _parse_unified_diff(self, unified_diff: List[str], 
                          old_lines: List[str], new_lines: List[str]) -> List[DiffChunk]:
        """Parse unified diff output into structured chunks"""
        chunks = []
        current_chunk = None
        old_line_num = 0
        new_line_num = 0
        
        for line in unified_diff:
            if line.startswith('@@'):
                # New chunk header
                if current_chunk:
                    chunks.append(current_chunk)
                
                # Parse chunk header: @@ -old_start,old_count +new_start,new_count @@
                import re
                match = re.match(r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@', line)
                if match:
                    old_start = int(match.group(1))
                    old_count = int(match.group(2)) if match.group(2) else 1
                    new_start = int(match.group(3))
                    new_count = int(match.group(4)) if match.group(4) else 1
                    
                    current_chunk = DiffChunk(
                        chunk_type='change',
                        old_start=old_start,
                        old_count=old_count,
                        new_start=new_start,
                        new_count=new_count,
                        lines=[]
                    )
                    old_line_num = old_start
                    new_line_num = new_start
                    
            elif line.startswith('---') or line.startswith('+++'):
                # File headers, skip
                continue
                
            elif current_chunk is not None:
                # Content line
                if line.startswith('-'):
                    # Removed line
                    diff_line = DiffLine(
                        line_type='removed',
                        line_number_old=old_line_num,
                        line_number_new=None,
                        content=line[1:]  # Remove the '-' prefix
                    )
                    current_chunk.lines.append(diff_line)
                    old_line_num += 1
                    
                elif line.startswith('+'):
                    # Added line
                    diff_line = DiffLine(
                        line_type='added',
                        line_number_old=None,
                        line_number_new=new_line_num,
                        content=line[1:]  # Remove the '+' prefix
                    )
                    current_chunk.lines.append(diff_line)
                    new_line_num += 1
                    
                elif line.startswith(' '):
                    # Unchanged line
                    diff_line = DiffLine(
                        line_type='unchanged',
                        line_number_old=old_line_num,
                        line_number_new=new_line_num,
                        content=line[1:]  # Remove the ' ' prefix
                    )
                    current_chunk.lines.append(diff_line)
                    old_line_num += 1
                    new_line_num += 1
        
        # Add the last chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _calculate_statistics(self, chunks: List[DiffChunk]) -> Dict[str, int]:
        """Calculate diff statistics from chunks"""
        stats = {
            'lines_added': 0,
            'lines_removed': 0,
            'lines_modified': 0,
            'lines_unchanged': 0,
            'chars_added': 0,
            'chars_removed': 0
        }
        
        for chunk in chunks:
            for line in chunk.lines:
                if line.line_type == 'added':
                    stats['lines_added'] += 1
                    stats['chars_added'] += len(line.content)
                elif line.line_type == 'removed':
                    stats['lines_removed'] += 1
                    stats['chars_removed'] += len(line.content)
                elif line.line_type == 'unchanged':
                    stats['lines_unchanged'] += 1
        
        # Calculate modified lines (pairs of add/remove)
        stats['lines_modified'] = min(stats['lines_added'], stats['lines_removed'])
        # Alias used by some callers
        stats['lines_changed'] = stats['lines_added'] + stats['lines_removed']
        
        return stats
    
    def generate_side_by_side_html(self, diff_result: DiffResult) -> str:
        """Generate side-by-side HTML diff view"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Diff: {old_file} vs {new_file}</title>
    <style>
        body {{ font-family: 'Courier New', monospace; margin: 0; padding: 20px; }}
        .stats {{ background: #e9ecef; padding: 10px; margin-bottom: 20px; border-radius: 5px; }}
        table.diff {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
        table.diff th {{ background: #f5f5f5; padding: 8px; border: 1px solid #ddd; font-weight: bold; width: 50%; }}
        table.diff td {{ vertical-align: top; padding: 0; border: 1px solid #ddd; width: 50%; }}
        .line {{ display: flex; min-height: 20px; line-height: 20px; }}
        .line-number {{ width: 50px; background: #f8f8f8; text-align: right; padding: 0 5px; color: #666; border-right: 1px solid #ddd; flex-shrink: 0; }}
        .line-content {{ flex: 1; padding: 0 5px; white-space: pre-wrap; overflow-wrap: break-word; }}
        .added {{ background-color: #d4edda; }}
        .removed {{ background-color: #f8d7da; }}
        .modified {{ background-color: #fff3cd; }}
        .unchanged {{ background-color: #fff; }}
        .highlight {{ background-color: #ffeb3b; }}
    </style>
</head>
<body>
    <h1>File Comparison</h1>
    <div class="stats">
        <strong>Statistics:</strong>
        Lines Added: {lines_added} |
        Lines Removed: {lines_removed} |
        Lines Modified: {lines_modified} |
        Lines Unchanged: {lines_unchanged} |
        Similarity: {similarity:.1%}
    </div>
    <table class="diff">
        <thead>
            <tr>
                <th>{old_file} {old_version}</th>
                <th>{new_file} {new_version}</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>{old_content}</td>
                <td>{new_content}</td>
            </tr>
        </tbody>
    </table>
</body>
</html>
        """
        
        old_content = self._generate_side_content(diff_result, 'old')
        new_content = self._generate_side_content(diff_result, 'new')
        
        return html_template.format(
            old_file=html.escape(diff_result.old_file),
            new_file=html.escape(diff_result.new_file),
            old_version=f"({diff_result.old_version})" if diff_result.old_version else "",
            new_version=f"({diff_result.new_version})" if diff_result.new_version else "",
            lines_added=diff_result.statistics['lines_added'],
            lines_removed=diff_result.statistics['lines_removed'],
            lines_modified=diff_result.statistics['lines_modified'],
            lines_unchanged=diff_result.statistics['lines_unchanged'],
            similarity=diff_result.similarity_ratio,
            old_content=old_content,
            new_content=new_content
        )
    
    def _generate_side_content(self, diff_result: DiffResult, side: str) -> str:
        """Generate HTML content for one side of the diff"""
        lines_html = []
        
        for chunk in diff_result.chunks:
            for line in chunk.lines:
                if side == 'old':
                    line_num = line.line_number_old
                    show_line = line.line_type in ['removed', 'unchanged']
                else:
                    line_num = line.line_number_new
                    show_line = line.line_type in ['added', 'unchanged']
                
                if show_line:
                    css_class = line.line_type
                    line_num_str = str(line_num) if line_num else ""
                    content = html.escape(line.content.rstrip())
                    
                    # Apply character-level highlighting
                    if line.highlight_chars:
                        for start, end in reversed(line.highlight_chars):
                            content = (content[:start] + 
                                     '<span class="highlight">' + 
                                     content[start:end] + 
                                     '</span>' + 
                                     content[end:])
                    
                    lines_html.append(f'''
                        <div class="line {css_class}">
                            <div class="line-number">{line_num_str}</div>
                            <div class="line-content">{content}</div>
                        </div>
                    ''')
                else:
                    # Empty line for alignment
                    lines_html.append(f'''
                        <div class="line">
                            <div class="line-number"></div>
                            <div class="line-content"></div>
                        </div>
                    ''')
        
        return ''.join(lines_html)
    
    def generate_unified_diff_text(self, diff_result: DiffResult) -> str:
        """Generate traditional unified diff text format"""
        lines = []
        lines.append(f"--- {diff_result.old_file}")
        lines.append(f"+++ {diff_result.new_file}")
        
        for chunk in diff_result.chunks:
            # Chunk header
            lines.append(f"@@ -{chunk.old_start},{chunk.old_count} +{chunk.new_start},{chunk.new_count} @@")
            
            # Chunk content
            for line in chunk.lines:
                prefix = {
                    'added': '+',
                    'removed': '-',
                    'unchanged': ' '
                }.get(line.line_type, ' ')
                
                lines.append(prefix + line.content.rstrip())
        
        return '\n'.join(lines)
    
    def generate_json_diff(self, diff_result: DiffResult) -> str:
        """Generate JSON representation of the diff"""
        return json.dumps(asdict(diff_result), indent=2, default=str)
    
    def compare_with_character_diff(self, old_text: str, new_text: str) -> List[Tuple[int, str]]:
        """Generate character-level diff using diff-match-patch"""
        diffs = self.dmp.diff_main(old_text, new_text)
        self.dmp.diff_cleanupSemantic(diffs)
        return diffs
    
    def get_diff_summary(self, diff_result: DiffResult) -> str:
        """Generate a human-readable summary of the diff"""
        stats = diff_result.statistics
        
        summary_parts = []
        
        if stats['lines_added'] > 0:
            summary_parts.append(f"{stats['lines_added']} lines added")
        
        if stats['lines_removed'] > 0:
            summary_parts.append(f"{stats['lines_removed']} lines removed")
        
        if stats['lines_modified'] > 0:
            summary_parts.append(f"{stats['lines_modified']} lines modified")
        
        if stats['lines_unchanged'] > 0:
            summary_parts.append(f"{stats['lines_unchanged']} lines unchanged")
        
        summary = ", ".join(summary_parts) if summary_parts else "No changes detected"
        
        similarity_pct = diff_result.similarity_ratio * 100
        summary += f" (Similarity: {similarity_pct:.1f}%)"
        
        return summary

class DiffManager:
    """Manages diff operations and storage"""
    
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.diffs_dir = self.data_dir / "diffs"
        self.diffs_dir.mkdir(parents=True, exist_ok=True)
        self.diff_generator = EnhancedDiffGenerator()
    
    def create_diff(self, old_file: Union[str, Path], new_file: Union[str, Path],
                   old_version: Optional[str] = None, new_version: Optional[str] = None,
                   save_html: bool = True) -> DiffResult:
        """Create and optionally save a diff"""
        diff_result = self.diff_generator.compare_files(
            old_file, new_file, old_version, new_version
        )
        
        if save_html:
            self.save_diff_html(diff_result)
        
        return diff_result
    
    def save_diff_html(self, diff_result: DiffResult) -> Path:
        """Save diff as HTML file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_name = Path(diff_result.old_file).stem
        new_name = Path(diff_result.new_file).stem
        
        filename = f"diff_{old_name}_vs_{new_name}_{timestamp}.html"
        html_path = self.diffs_dir / filename
        
        html_content = self.diff_generator.generate_side_by_side_html(diff_result)
        html_path.write_text(html_content, encoding='utf-8')
        
        logger.info(f"Diff saved as HTML: {html_path}")
        return html_path
    
    def save_diff_json(self, diff_result: DiffResult) -> Path:
        """Save diff as JSON file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        old_name = Path(diff_result.old_file).stem
        new_name = Path(diff_result.new_file).stem
        
        filename = f"diff_{old_name}_vs_{new_name}_{timestamp}.json"
        json_path = self.diffs_dir / filename
        
        json_content = self.diff_generator.generate_json_diff(diff_result)
        json_path.write_text(json_content, encoding='utf-8')
        
        logger.info(f"Diff saved as JSON: {json_path}")
        return json_path
    
    def list_diffs(self) -> List[Dict[str, Any]]:
        """List all saved diff files (alias for list_saved_diffs)."""
        return self.list_saved_diffs()

    def list_saved_diffs(self) -> List[Dict[str, Any]]:
        """List all saved diff files"""
        diffs = []
        
        for file_path in self.diffs_dir.glob("diff_*.html"):
            stat = file_path.stat()
            diffs.append({
                'filename': file_path.name,
                'path': str(file_path),
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'type': 'html'
            })
        
        for file_path in self.diffs_dir.glob("diff_*.json"):
            stat = file_path.stat()
            diffs.append({
                'filename': file_path.name,
                'path': str(file_path),
                'size': stat.st_size,
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime),
                'type': 'json'
            })
        
        # Sort by creation time (newest first)
        diffs.sort(key=lambda x: x['created'], reverse=True)
        
        return diffs
    
    def cleanup_old_diffs(self, max_age_days: int = 7, max_age_hours: Optional[int] = None) -> int:
        """Clean up old diff files"""
        if max_age_hours is not None:
            cutoff_date = datetime.now() - timedelta(hours=max_age_hours)
        else:
            cutoff_date = datetime.now() - timedelta(days=max_age_days)
        cleaned_count = 0
        
        for file_path in self.diffs_dir.glob("diff_*"):
            if datetime.fromtimestamp(file_path.stat().st_ctime) < cutoff_date:
                try:
                    file_path.unlink()
                    cleaned_count += 1
                    logger.info(f"Cleaned up old diff file: {file_path.name}")
                except Exception as e:
                    logger.error(f"Failed to delete diff file {file_path}: {e}")
        
        return cleaned_count
    
    def compare_text(self, old_text: str, new_text: str, 
                    old_version: Optional[str] = None, new_version: Optional[str] = None) -> DiffResult:
        """Compare two text strings directly"""
        return self.diff_generator.compare_text(
            old_text, new_text,
            old_version=old_version, new_version=new_version
        )