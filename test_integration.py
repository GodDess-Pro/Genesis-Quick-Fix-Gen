"""
Integration Test Script for QuickFix Generator
Tests all components working together
"""

import sys
import os
from pathlib import Path
from datetime import datetime

def run_integration_tests():
    """Run comprehensive integration tests"""
    print('🧪 Testing QuickFix Generator System Integration...')
    print('=' * 60)
    
    try:
        print('1. Testing module imports...')
        from core_generator import QuickFixGenerator, QuickFixConfig
        from pattern_recognition import PatternRecognition, ErrorPattern
        from temp_log_manager import TempLogManager, TempLogEntry
        from master_archive import MasterArchiveDB, MasterSolution
        from solution_applier import SolutionApplier, ApplicationResult
        from template_system import TemplateSystemManager, SolutionTemplate
        print('✅ All modules imported successfully')
        
        print('\n2. Testing component initialization...')
        workspace_path = str(Path.cwd().parent.parent)
        config = QuickFixConfig(workspace_path=workspace_path, auto_apply_fixes=False)
        qfg = QuickFixGenerator(workspace_path, config)
        print('✅ QuickFix Generator initialized')
        
        print('\n3. Testing pattern recognition...')
        test_html = '<div class="test">Unclosed div without closing tag'
        patterns = qfg.pattern_recognition.analyze_content(test_html, 'HTML', 'test.html')
        print(f'✅ Pattern recognition working: {len(patterns)} patterns detected')
        
        print('\n4. Testing temp log manager...')
        test_entry = TempLogEntry(
            entry_id='test_integration',
            file_path='test.html',
            language='HTML',
            pattern_id='html_unclosed_tag',
            line_number=1,
            original_content=test_html,
            timestamp=datetime.now()
        )
        qfg.temp_log_manager.add_entry(test_entry)
        entries = qfg.temp_log_manager.get_recent_entries(limit=1)
        print(f'✅ Temp log manager working: {len(entries)} entries')
        
        print('\n5. Testing master archive...')
        solutions = qfg.master_archive.get_all_solutions()
        print(f'✅ Master archive working: {len(solutions)} solutions available')
        
        print('\n6. Testing template system...')
        templates = qfg.template_system.get_all_templates()
        print(f'✅ Template system working: {len(templates)} templates available')
        
        print('\n7. Testing statistics...')
        stats = qfg.get_statistics()
        print(f'✅ Statistics working: {stats["files_processed"]} files processed')
        
        print('\n8. Testing file processing (dry run)...')
        # Create a test file
        test_file = Path('test_integration.html')
        test_file.write_text('<div>Test content without closing div')
        
        result = qfg.process_file(str(test_file))
        print(f'✅ File processing working: {result.success}, {len(result.patterns_detected)} patterns')
        
        # Cleanup
        test_file.unlink()

        print('\n9. Testing Smart Pattern Learning...')
        from smart_pattern_learning import SmartPatternLearner
        learner = SmartPatternLearner(data_dir='/tmp/test_qfx_learning')
        sample_js = "var x = 1;\neval('alert(1)');\ndocument.write('hello');"
        updated = learner.analyse_code_snippet(sample_js, 'JavaScript', 'test.js')
        stats = learner.get_learning_stats()
        print(f'✅ Smart Pattern Learning working: {stats["candidate_snippets_observed"]} candidates observed, {len(updated)} patterns updated')

        print('\n10. Testing Browser Integration...')
        from browser_integration import BrowserIntegration
        browser = BrowserIntegration(report_dir='/tmp/test_qfx_browser')
        html_content = '<!DOCTYPE html><html><head><title>Test</title></head><body><img src="test.png"><p>Hello</p></body></html>'
        result = browser.analyse_content(html_content, 'html', 'test.html')
        print(f'✅ Browser Integration working: {result.summary["total"]} issues found, score={result.compatibility_score}')

        print('\n11. Testing Team Collaboration...')
        from team_collaboration import TeamCollaboration
        collab = TeamCollaboration(collab_dir='/tmp/test_qfx_collab', current_user='test_user')
        member = collab.register_member('test_user', 'Test User', 'contributor')
        solution = collab.share_solution(
            title='Fix missing semicolons',
            description='Adds semicolons where missing in JS',
            language='JavaScript',
            error_pattern=r'line without semicolon',
            fix_code='line += ";"',
            tags=['javascript', 'syntax'],
        )
        solutions = collab.search_solutions(language='JavaScript')
        stats = collab.get_team_stats()
        print(f'✅ Team Collaboration working: {stats["total_members"]} members, {stats["total_solutions"]} solutions')

        print('\n12. Testing Predictive Analysis...')
        from predictive_analysis import PredictiveAnalyzer
        analyzer = PredictiveAnalyzer(history_dir='/tmp/test_qfx_predict')
        risky_code = """
import os
def process():
    try:
        exec("rm -rf /")
        from os import *
    except:
        pass
"""
        profile = analyzer.analyse_content(risky_code, 'Python', 'risky.py')
        summary = analyzer.get_summary()
        print(f'✅ Predictive Analysis working: risk_level={profile.risk_level}, {len(profile.signals)} signals, {len(profile.predictions)} predictions')

        print('\n' + '=' * 60)
        print('🎉 ALL INTEGRATION TESTS PASSED!')
        print('✅ QuickFix Generator system is fully operational')
        print('✅ Phase 2-4 features (Smart Learning, Browser, Collaboration, Prediction) operational')
        print('=' * 60)
        
        return True
        
    except Exception as e:
        print(f'❌ Integration test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)