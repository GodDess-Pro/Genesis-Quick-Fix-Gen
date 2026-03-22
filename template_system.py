#!/usr/bin/env python3
"""
QuickFix Template System & Redundancy Reduction
==============================================

Generates templates from successful fixes, detects redundant solutions,
and optimizes the master archive database for better performance.

Author: WorkspaceSentinel QuickFix System
Date: November 17, 2025
"""

import re
import json
import datetime
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict, Counter
import difflib

from master_archive import MasterSolution, MasterArchiveDB

@dataclass
class SolutionTemplate:
    """Template generated from successful solutions"""
    template_id: str
    language: str
    error_pattern_id: str
    template_code: str
    variable_placeholders: List[str]
    confidence_score: float
    generated_from: List[str]  # List of solution IDs
    usage_count: int
    success_rate: float
    created_at: datetime.datetime
    last_updated: datetime.datetime
    tags: List[str]

@dataclass
class RedundancyReport:
    """Report of redundant solutions found"""
    total_solutions: int
    redundant_groups: List[Dict[str, Any]]
    potential_savings: int
    consolidation_recommendations: List[Dict[str, Any]]
    generated_at: datetime.datetime

@dataclass
class TemplateVariable:
    """Variable placeholder in a template"""
    name: str
    pattern: str
    description: str
    examples: List[str]
    validation_regex: Optional[str] = None

class TemplateSystemManager:
    """Manages template generation and redundancy reduction"""
    
    def __init__(self, master_archive: MasterArchiveDB, workspace_path: str):
        self.master_archive = master_archive
        self.workspace_path = Path(workspace_path)
        self.templates_dir = self.workspace_path / "QuickFixGenerator" / "templates"
        self.templates_dir.mkdir(parents=True, exist_ok=True)
        
        # Template storage
        self.templates: Dict[str, SolutionTemplate] = {}
        self.template_variables: Dict[str, List[TemplateVariable]] = {}
        
        # Load existing templates
        self._load_templates()
        
        # Common variable patterns
        self._init_variable_patterns()
        
        print(f"TemplateSystemManager initialized with {len(self.templates)} templates")
    
    def _init_variable_patterns(self):
        """Initialize common variable patterns for different languages"""
        self.variable_patterns = {
            'html': {
                'tag_name': TemplateVariable(
                    name='tag_name',
                    pattern=r'<(\w+)[^>]*>',
                    description='HTML tag name',
                    examples=['div', 'span', 'h1', 'p'],
                    validation_regex=r'^[a-zA-Z][a-zA-Z0-9]*$'
                ),
                'attribute_name': TemplateVariable(
                    name='attribute_name',
                    pattern=r'(\w+)=',
                    description='HTML attribute name',
                    examples=['class', 'id', 'src', 'href'],
                    validation_regex=r'^[a-zA-Z][a-zA-Z0-9-]*$'
                ),
                'attribute_value': TemplateVariable(
                    name='attribute_value',
                    pattern=r'="([^"]*)"',
                    description='HTML attribute value',
                    examples=['container', 'main-content', 'image.jpg']
                )
            },
            'css': {
                'property_name': TemplateVariable(
                    name='property_name',
                    pattern=r'([a-zA-Z-]+)\s*:',
                    description='CSS property name',
                    examples=['color', 'background-color', 'margin', 'padding'],
                    validation_regex=r'^[a-zA-Z-]+$'
                ),
                'property_value': TemplateVariable(
                    name='property_value',
                    pattern=r':\s*([^;]+)',
                    description='CSS property value',
                    examples=['red', '#ffffff', '10px', '1rem']
                ),
                'selector': TemplateVariable(
                    name='selector',
                    pattern=r'^([^{]+){',
                    description='CSS selector',
                    examples=['.container', '#main', 'h1', 'div.header']
                )
            },
            'javascript': {
                'variable_name': TemplateVariable(
                    name='variable_name',
                    pattern=r'\b([a-zA-Z_$][a-zA-Z0-9_$]*)\b',
                    description='JavaScript variable name',
                    examples=['userName', 'totalCount', 'isVisible'],
                    validation_regex=r'^[a-zA-Z_$][a-zA-Z0-9_$]*$'
                ),
                'function_name': TemplateVariable(
                    name='function_name',
                    pattern=r'function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)',
                    description='JavaScript function name',
                    examples=['calculateTotal', 'handleClick', 'validateInput'],
                    validation_regex=r'^[a-zA-Z_$][a-zA-Z0-9_$]*$'
                ),
                'string_literal': TemplateVariable(
                    name='string_literal',
                    pattern=r'["\']([^"\']*)["\']',
                    description='String literal value',
                    examples=['Hello World', 'Error message', 'success']
                )
            },
            'python': {
                'variable_name': TemplateVariable(
                    name='variable_name',
                    pattern=r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b',
                    description='Python variable name',
                    examples=['user_name', 'total_count', 'is_valid'],
                    validation_regex=r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                ),
                'function_name': TemplateVariable(
                    name='function_name',
                    pattern=r'def\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                    description='Python function name',
                    examples=['calculate_total', 'handle_error', 'validate_input'],
                    validation_regex=r'^[a-zA-Z_][a-zA-Z0-9_]*$'
                ),
                'class_name': TemplateVariable(
                    name='class_name',
                    pattern=r'class\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                    description='Python class name',
                    examples=['UserManager', 'DataProcessor', 'ConfigHandler'],
                    validation_regex=r'^[A-Z][a-zA-Z0-9_]*$'
                ),
                'module_name': TemplateVariable(
                    name='module_name',
                    pattern=r'import\s+([a-zA-Z_][a-zA-Z0-9_.]*)',
                    description='Python module name',
                    examples=['os', 'json', 'datetime', 'requests']
                )
            }
        }
    
    def _load_templates(self):
        """Load existing templates from disk"""
        templates_file = self.templates_dir / "solution_templates.json"
        
        if templates_file.exists():
            try:
                with open(templates_file, 'r', encoding='utf-8') as f:
                    templates_data = json.load(f)
                
                for template_id, data in templates_data.items():
                    template = SolutionTemplate(
                        template_id=template_id,
                        language=data['language'],
                        error_pattern_id=data['error_pattern_id'],
                        template_code=data['template_code'],
                        variable_placeholders=data['variable_placeholders'],
                        confidence_score=data['confidence_score'],
                        generated_from=data['generated_from'],
                        usage_count=data['usage_count'],
                        success_rate=data['success_rate'],
                        created_at=datetime.datetime.fromisoformat(data['created_at']),
                        last_updated=datetime.datetime.fromisoformat(data['last_updated']),
                        tags=data['tags']
                    )
                    self.templates[template_id] = template
                
                print(f"Loaded {len(self.templates)} existing templates")
                
            except Exception as e:
                print(f"Error loading templates: {e}")
    
    def _save_templates(self):
        """Save templates to disk"""
        templates_file = self.templates_dir / "solution_templates.json"
        
        try:
            templates_data = {}
            for template_id, template in self.templates.items():
                templates_data[template_id] = {
                    'language': template.language,
                    'error_pattern_id': template.error_pattern_id,
                    'template_code': template.template_code,
                    'variable_placeholders': template.variable_placeholders,
                    'confidence_score': template.confidence_score,
                    'generated_from': template.generated_from,
                    'usage_count': template.usage_count,
                    'success_rate': template.success_rate,
                    'created_at': template.created_at.isoformat(),
                    'last_updated': template.last_updated.isoformat(),
                    'tags': template.tags
                }
            
            with open(templates_file, 'w', encoding='utf-8') as f:
                json.dump(templates_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"Error saving templates: {e}")
    
    def generate_template_from_solutions(self, solutions: List[MasterSolution]) -> Optional[SolutionTemplate]:
        """Generate a template from multiple similar solutions"""
        if len(solutions) < 2:
            return None
        
        # Group solutions by language and pattern
        language = solutions[0].language
        pattern_id = solutions[0].error_pattern_id
        
        # Verify all solutions are for the same pattern
        if not all(s.language == language and s.error_pattern_id == pattern_id for s in solutions):
            return None
        
        # Extract common template structure
        template_code = self._extract_common_template(solutions)
        if not template_code:
            return None
        
        # Identify variable placeholders
        variable_placeholders = self._identify_placeholders(template_code, language)
        
        # Calculate aggregate statistics
        total_applications = sum(s.total_applications for s in solutions)
        successful_applications = sum(s.successful_applications for s in solutions)
        success_rate = successful_applications / total_applications if total_applications > 0 else 0
        
        # Calculate confidence score
        confidence_score = self._calculate_template_confidence(solutions, success_rate)
        
        # Generate template ID
        template_id = self._generate_template_id(language, pattern_id, template_code)
        
        # Combine tags from all solutions
        all_tags = set()
        for solution in solutions:
            all_tags.update(solution.tags)
        
        template = SolutionTemplate(
            template_id=template_id,
            language=language,
            error_pattern_id=pattern_id,
            template_code=template_code,
            variable_placeholders=variable_placeholders,
            confidence_score=confidence_score,
            generated_from=[s.solution_id for s in solutions],
            usage_count=total_applications,
            success_rate=success_rate,
            created_at=datetime.datetime.now(),
            last_updated=datetime.datetime.now(),
            tags=list(all_tags)
        )
        
        print(f"Generated template {template_id} from {len(solutions)} solutions")
        return template
    
    def _extract_common_template(self, solutions: List[MasterSolution]) -> Optional[str]:
        """Extract common template structure from multiple solutions"""
        if not solutions:
            return None
        
        # Start with the first solution template
        base_template = solutions[0].solution_template
        
        # Find common parts with other solutions
        for solution in solutions[1:]:
            base_template = self._find_common_structure(base_template, solution.solution_template)
            if not base_template:
                return None
        
        return base_template
    
    def _find_common_structure(self, template1: str, template2: str) -> Optional[str]:
        """Find common structure between two templates"""
        # Use difflib to find common subsequences
        matcher = difflib.SequenceMatcher(None, template1, template2)
        
        common_parts = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'equal':
                common_parts.append(template1[i1:i2])
            elif tag in ['replace', 'delete', 'insert']:
                # Add placeholder for variable content
                common_parts.append('{variable}')
        
        common_template = ''.join(common_parts)
        
        # Clean up multiple consecutive placeholders
        common_template = re.sub(r'\{variable\}(\{variable\})+', '{variable}', common_template)
        
        return common_template if common_template.strip() else None
    
    def _identify_placeholders(self, template_code: str, language: str) -> List[str]:
        """Identify variable placeholders in template code"""
        placeholders = []
        
        # Extract existing placeholders
        existing_placeholders = re.findall(r'\{([^}]+)\}', template_code)
        placeholders.extend(existing_placeholders)
        
        # Identify language-specific patterns
        if language in self.variable_patterns:
            for var_name, var_pattern in self.variable_patterns[language].items():
                if re.search(var_pattern.pattern, template_code):
                    if var_name not in placeholders:
                        placeholders.append(var_name)
        
        return list(set(placeholders))  # Remove duplicates
    
    def _calculate_template_confidence(self, solutions: List[MasterSolution], success_rate: float) -> float:
        """Calculate confidence score for generated template"""
        # Base confidence on success rate
        confidence = success_rate * 0.6
        
        # Bonus for number of solutions used
        solution_bonus = min(len(solutions) / 10.0, 0.2)
        confidence += solution_bonus
        
        # Bonus for total applications
        total_apps = sum(s.total_applications for s in solutions)
        usage_bonus = min(total_apps / 100.0, 0.2)
        confidence += usage_bonus
        
        return min(confidence, 1.0)
    
    def _generate_template_id(self, language: str, pattern_id: str, template_code: str) -> str:
        """Generate unique template ID"""
        content_hash = hashlib.md5(template_code.encode()).hexdigest()[:8]
        timestamp = datetime.datetime.now().strftime("%Y%m%d")
        return f"template_{language}_{pattern_id}_{timestamp}_{content_hash}"
    
    def find_redundant_solutions(self, language: Optional[str] = None) -> RedundancyReport:
        """Find redundant solutions in the master archive"""
        # Get all solutions
        solutions = list(self.master_archive.solutions_cache.values())
        
        if language:
            solutions = [s for s in solutions if s.language == language]
        
        # Group solutions by error pattern
        pattern_groups = defaultdict(list)
        for solution in solutions:
            pattern_groups[solution.error_pattern_id].append(solution)
        
        redundant_groups = []
        consolidation_recommendations = []
        total_redundant = 0
        
        for pattern_id, pattern_solutions in pattern_groups.items():
            if len(pattern_solutions) < 2:
                continue
            
            # Find similar solutions within each pattern group
            similar_groups = self._find_similar_solutions(pattern_solutions)
            
            for similar_solutions in similar_groups:
                if len(similar_solutions) > 1:
                    # Calculate similarity metrics
                    similarity_score = self._calculate_similarity_score(similar_solutions)
                    
                    group_info = {
                        'pattern_id': pattern_id,
                        'language': similar_solutions[0].language,
                        'solution_count': len(similar_solutions),
                        'similarity_score': similarity_score,
                        'solutions': [
                            {
                                'solution_id': s.solution_id,
                                'success_rate': s.success_rate,
                                'total_applications': s.total_applications,
                                'solution_description': s.solution_description
                            } for s in similar_solutions
                        ]
                    }
                    redundant_groups.append(group_info)
                    total_redundant += len(similar_solutions) - 1  # Keep one, mark others as redundant
                    
                    # Generate consolidation recommendation
                    best_solution = max(similar_solutions, key=lambda x: (x.success_rate, x.total_applications))
                    recommendation = {
                        'action': 'consolidate',
                        'pattern_id': pattern_id,
                        'keep_solution': best_solution.solution_id,
                        'merge_solutions': [s.solution_id for s in similar_solutions if s.solution_id != best_solution.solution_id],
                        'expected_improvement': self._calculate_consolidation_benefit(similar_solutions, best_solution)
                    }
                    consolidation_recommendations.append(recommendation)
        
        return RedundancyReport(
            total_solutions=len(solutions),
            redundant_groups=redundant_groups,
            potential_savings=total_redundant,
            consolidation_recommendations=consolidation_recommendations,
            generated_at=datetime.datetime.now()
        )
    
    def _find_similar_solutions(self, solutions: List[MasterSolution]) -> List[List[MasterSolution]]:
        """Find groups of similar solutions"""
        similar_groups = []
        processed = set()
        
        for i, solution1 in enumerate(solutions):
            if solution1.solution_id in processed:
                continue
            
            similar_group = [solution1]
            processed.add(solution1.solution_id)
            
            for j, solution2 in enumerate(solutions[i+1:], i+1):
                if solution2.solution_id in processed:
                    continue
                
                # Calculate similarity between solutions
                similarity = self._calculate_solution_similarity(solution1, solution2)
                
                if similarity > 0.8:  # High similarity threshold
                    similar_group.append(solution2)
                    processed.add(solution2.solution_id)
            
            if len(similar_group) > 1:
                similar_groups.append(similar_group)
        
        return similar_groups
    
    def _calculate_solution_similarity(self, solution1: MasterSolution, solution2: MasterSolution) -> float:
        """Calculate similarity score between two solutions"""
        # Template similarity
        template_similarity = difflib.SequenceMatcher(
            None, solution1.solution_template, solution2.solution_template
        ).ratio()
        
        # Description similarity
        desc_similarity = difflib.SequenceMatcher(
            None, solution1.solution_description, solution2.solution_description
        ).ratio()
        
        # Tag similarity
        tags1 = set(solution1.tags)
        tags2 = set(solution2.tags)
        tag_similarity = len(tags1 & tags2) / len(tags1 | tags2) if tags1 | tags2 else 0
        
        # Weighted average
        similarity = (template_similarity * 0.5 + desc_similarity * 0.3 + tag_similarity * 0.2)
        
        return similarity
    
    def _calculate_similarity_score(self, solutions: List[MasterSolution]) -> float:
        """Calculate overall similarity score for a group of solutions"""
        if len(solutions) < 2:
            return 0.0
        
        similarities = []
        for i in range(len(solutions)):
            for j in range(i+1, len(solutions)):
                similarity = self._calculate_solution_similarity(solutions[i], solutions[j])
                similarities.append(similarity)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _calculate_consolidation_benefit(self, solutions: List[MasterSolution], best_solution: MasterSolution) -> Dict[str, float]:
        """Calculate expected benefit from consolidating solutions"""
        total_applications = sum(s.total_applications for s in solutions)
        total_successful = sum(s.successful_applications for s in solutions)
        current_success_rate = total_successful / total_applications if total_applications > 0 else 0
        
        # Projected success rate with consolidation
        projected_success_rate = best_solution.success_rate
        
        return {
            'success_rate_improvement': projected_success_rate - current_success_rate,
            'complexity_reduction': (len(solutions) - 1) / len(solutions),
            'maintenance_reduction': len(solutions) - 1
        }
    
    def consolidate_redundant_solutions(self, consolidation_plan: Dict[str, Any]) -> bool:
        """Execute consolidation of redundant solutions"""
        try:
            keep_solution_id = consolidation_plan['keep_solution']
            merge_solution_ids = consolidation_plan['merge_solutions']
            
            # Get the solution to keep
            keep_solution = self.master_archive.solutions_cache.get(keep_solution_id)
            if not keep_solution:
                print(f"Solution to keep not found: {keep_solution_id}")
                return False
            
            # Merge statistics from other solutions
            for merge_id in merge_solution_ids:
                merge_solution = self.master_archive.solutions_cache.get(merge_id)
                if merge_solution:
                    # Update statistics
                    keep_solution.total_applications += merge_solution.total_applications
                    keep_solution.successful_applications += merge_solution.successful_applications
                    
                    # Recalculate success rate
                    keep_solution.success_rate = (keep_solution.successful_applications / 
                                                keep_solution.total_applications)
                    
                    # Merge tags
                    keep_solution.tags = list(set(keep_solution.tags + merge_solution.tags))
                    
                    # Update timestamps
                    keep_solution.last_updated = datetime.datetime.now()
                    
                    # Deprecate the merged solution
                    self.master_archive.deprecate_solution(merge_id, replacement_id=keep_solution_id)
            
            # Update the consolidated solution in the archive
            self.master_archive.add_or_update_solution(keep_solution)
            
            print(f"Consolidated {len(merge_solution_ids)} solutions into {keep_solution_id}")
            return True
            
        except Exception as e:
            print(f"Error consolidating solutions: {e}")
            return False
    
    def generate_all_templates(self, min_solutions: int = 3) -> List[SolutionTemplate]:
        """Generate templates from all suitable solution groups"""
        generated_templates = []
        
        # Group solutions by pattern and language
        pattern_groups = defaultdict(list)
        for solution in self.master_archive.solutions_cache.values():
            if not solution.deprecated:
                key = (solution.language, solution.error_pattern_id)
                pattern_groups[key].append(solution)
        
        for (language, pattern_id), solutions in pattern_groups.items():
            if len(solutions) >= min_solutions:
                # Find similar solution groups
                similar_groups = self._find_similar_solutions(solutions)
                
                for similar_solutions in similar_groups:
                    if len(similar_solutions) >= min_solutions:
                        template = self.generate_template_from_solutions(similar_solutions)
                        if template:
                            self.templates[template.template_id] = template
                            generated_templates.append(template)
        
        if generated_templates:
            self._save_templates()
            print(f"Generated {len(generated_templates)} new templates")
        
        return generated_templates
    
    def apply_template_to_context(self, template_id: str, context: Dict[str, Any]) -> Optional[str]:
        """Apply a template with specific context variables"""
        if template_id not in self.templates:
            return None
        
        template = self.templates[template_id]
        result_code = template.template_code
        
        # Replace placeholders with context values
        for placeholder in template.variable_placeholders:
            if placeholder in context:
                placeholder_pattern = f"{{{placeholder}}}"
                result_code = result_code.replace(placeholder_pattern, str(context[placeholder]))
        
        # Update usage statistics
        template.usage_count += 1
        template.last_updated = datetime.datetime.now()
        self._save_templates()
        
        return result_code
    
    def get_template_recommendations(self, language: str, pattern_id: str) -> List[SolutionTemplate]:
        """Get template recommendations for a specific pattern"""
        recommendations = []
        
        for template in self.templates.values():
            if template.language == language and template.error_pattern_id == pattern_id:
                recommendations.append(template)
        
        # Sort by confidence score and success rate
        recommendations.sort(key=lambda x: (x.confidence_score, x.success_rate), reverse=True)
        
        return recommendations
    
    def export_redundancy_report(self, output_path: str, language: Optional[str] = None):
        """Export redundancy analysis report"""
        report = self.find_redundant_solutions(language)
        
        # Convert to JSON-serializable format
        report_data = {
            'summary': {
                'total_solutions': report.total_solutions,
                'redundant_groups_count': len(report.redundant_groups),
                'potential_savings': report.potential_savings,
                'generated_at': report.generated_at.isoformat()
            },
            'redundant_groups': report.redundant_groups,
            'consolidation_recommendations': report.consolidation_recommendations
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        print(f"Exported redundancy report to {output_path}")
    
    def get_template_statistics(self) -> Dict[str, Any]:
        """Get comprehensive template system statistics"""
        stats = {
            'total_templates': len(self.templates),
            'templates_by_language': defaultdict(int),
            'templates_by_pattern': defaultdict(int),
            'top_templates': [],
            'template_effectiveness': {
                'high_confidence': 0,
                'medium_confidence': 0,
                'low_confidence': 0
            }
        }
        
        # Analyze templates
        template_scores = []
        for template in self.templates.values():
            stats['templates_by_language'][template.language] += 1
            stats['templates_by_pattern'][template.error_pattern_id] += 1
            
            # Categorize by confidence
            if template.confidence_score >= 0.8:
                stats['template_effectiveness']['high_confidence'] += 1
            elif template.confidence_score >= 0.6:
                stats['template_effectiveness']['medium_confidence'] += 1
            else:
                stats['template_effectiveness']['low_confidence'] += 1
            
            # Track for top templates
            score = template.confidence_score * template.success_rate * (template.usage_count / 100)
            template_scores.append((template.template_id, score, template))
        
        # Get top 10 templates
        template_scores.sort(key=lambda x: x[1], reverse=True)
        stats['top_templates'] = [
            {
                'template_id': t[0],
                'score': t[1],
                'language': t[2].language,
                'pattern_id': t[2].error_pattern_id,
                'success_rate': t[2].success_rate,
                'usage_count': t[2].usage_count
            } for t in template_scores[:10]
        ]
        
        # Convert defaultdicts to regular dicts
        stats['templates_by_language'] = dict(stats['templates_by_language'])
        stats['templates_by_pattern'] = dict(stats['templates_by_pattern'])
        
        return stats
    
    def get_all_templates(self) -> List[SolutionTemplate]:
        """Get all templates as a list"""
        return list(self.templates.values())
    
    def generate_templates(self) -> int:
        """Generate templates from master archive (compatibility method)"""
        # Simple template generation for testing
        generated_count = 0
        try:
            solutions = self.master_archive.get_all_solutions()
            for solution in solutions:
                # Generate a simple template for each solution
                template_id = f"template_{solution.language}_{solution.error_pattern_id}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
                template = SolutionTemplate(
                    template_id=template_id,
                    language=solution.language,
                    error_pattern_id=solution.error_pattern_id,
                    template_code=solution.fix_description,
                    variable_placeholders=[],
                    confidence_score=0.8,
                    generated_from=[solution.solution_id],
                    usage_count=0,
                    success_rate=solution.success_rate,
                    created_at=datetime.datetime.now(),
                    last_updated=datetime.datetime.now(),
                    tags=list(solution.tags)
                )
                self.templates[template_id] = template
                generated_count += 1
        except Exception as e:
            print(f"Error generating templates: {e}")
        return generated_count

# Example usage
if __name__ == "__main__":
    from master_archive import MasterArchiveDB
    
    # Initialize components
    workspace_path = "./test_workspace"
    master_archive = MasterArchiveDB(workspace_path)
    template_manager = TemplateSystemManager(master_archive, workspace_path)
    
    # Generate templates from existing solutions
    templates = template_manager.generate_all_templates(min_solutions=2)
    print(f"Generated {len(templates)} templates")
    
    # Find redundant solutions
    redundancy_report = template_manager.find_redundant_solutions()
    print(f"Found {len(redundancy_report.redundant_groups)} redundant groups")
    print(f"Potential savings: {redundancy_report.potential_savings} solutions")
    
    # Export redundancy report
    template_manager.export_redundancy_report("redundancy_report.json")
    
    # Get template statistics
    stats = template_manager.get_template_statistics()
    print(f"Template statistics: {stats}")
    
    print("Template system test completed")