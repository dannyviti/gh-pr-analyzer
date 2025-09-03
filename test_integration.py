"""
Integration tests for GitHub PR analysis tool.

This module contains comprehensive end-to-end tests for the complete
PR analysis workflow, including CLI interface and error handling.
"""

import pytest
import tempfile
import os
import csv
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import argparse

from github_pr_analyzer import main, parse_arguments, validate_inputs, print_summary, sanitize_repository_name_for_filename, generate_auto_filename, validate_repository_name_format
from github_client import GitHubClient, GitHubAPIError, GitHubAuthenticationError
from pr_analyzer import PRAnalyzer, PRAnalysisError
from csv_reporter import CSVReporter, CSVReportError


class TestEndToEndAnalysis:
    """Test cases for complete analysis workflow with mocked GitHub API."""
    
    def setup_method(self):
        """Set up test environment for each test method."""
        self.tmpdir = tempfile.mkdtemp()
        self.output_file = Path(self.tmpdir) / "integration_test.csv"
        
        # Mock data
        self.mock_prs = [
            {
                'number': 100,
                'title': 'Feature: Add user authentication',
                'state': 'closed',
                'created_at': '2024-12-01T10:00:00Z'
            },
            {
                'number': 101, 
                'title': 'Fix: Critical security vulnerability',
                'state': 'closed',
                'created_at': '2024-12-02T14:30:00Z'
            }
        ]
        
        self.mock_analysis_results = {
            'summary': {
                'total_prs_analyzed': 2,
                'merged_prs': 2,
                'reviewed_prs': 2,
                'avg_time_to_first_review': 4.5,
                'avg_time_to_merge': 24.0,
                'avg_commit_lead_time': 48.0
            },
            'pr_details': [
                {
                    'pr_number': 100,
                    'title': 'Feature: Add user authentication',
                    'state': 'closed',
                    'created_at': '2024-12-01T10:00:00Z',
                    'merged_at': '2024-12-02T10:00:00Z',
                    'time_to_first_review_hours': 4.0,
                    'time_to_merge_hours': 24.0,
                    'commit_lead_time_hours': 48.0,
                    'has_reviews': True,
                    'review_count': 2,
                    'comment_count': 3,
                    'commit_count': 5,
                    'is_merged': True
                },
                {
                    'pr_number': 101,
                    'title': 'Fix: Critical security vulnerability',
                    'state': 'closed', 
                    'created_at': '2024-12-02T14:30:00Z',
                    'merged_at': '2024-12-02T18:30:00Z',
                    'time_to_first_review_hours': 5.0,
                    'time_to_merge_hours': 4.0,
                    'commit_lead_time_hours': 6.0,
                    'has_reviews': True,
                    'review_count': 1,
                    'comment_count': 2,
                    'commit_count': 3,
                    'is_merged': True
                }
            ]
        }
    
    def teardown_method(self):
        """Clean up after each test method."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    @patch('github_pr_analyzer.GitHubClient')
    @patch('github_pr_analyzer.PRAnalyzer')
    @patch('github_pr_analyzer.CSVReporter')
    def test_end_to_end_analysis_success(self, mock_csv_class, mock_analyzer_class, mock_client_class):
        """Test complete successful analysis workflow with all three metrics."""
        # Configure mocks
        mock_client = Mock(spec=GitHubClient)
        mock_client.validate_token.return_value = True
        mock_client.get_repository_info.return_value = {'full_name': 'testowner/test-repo'}
        mock_client_class.return_value = mock_client
        mock_client_class.get_token_from_env.return_value = 'test_token'
        
        mock_analyzer = Mock(spec=PRAnalyzer)
        mock_analyzer.fetch_monthly_prs.return_value = self.mock_prs
        mock_analyzer.analyze_pr_lifecycle_times.return_value = self.mock_analysis_results
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_reporter = Mock(spec=CSVReporter)
        mock_reporter.validate_analysis_results.return_value = True
        mock_reporter.generate_report.return_value = str(self.output_file)
        mock_csv_class.return_value = mock_reporter
        
        # Test arguments
        with patch('sys.argv', ['github_pr_analyzer.py', 'testowner/test-repo', '--output', str(self.output_file)]):
            result = main()
        
        # Verify successful execution
        assert result == 0
        
        # Verify method calls
        mock_client_class.get_token_from_env.assert_called_once()
        mock_client.validate_token.assert_called_once()
        mock_client.get_repository_info.assert_called_once_with('testowner', 'test-repo')
        mock_analyzer.fetch_monthly_prs.assert_called_once_with('testowner', 'test-repo', 1)
        mock_analyzer.analyze_pr_lifecycle_times.assert_called_once_with(self.mock_prs, 'testowner', 'test-repo')
        mock_reporter.validate_analysis_results.assert_called_once_with(self.mock_analysis_results)
        mock_reporter.generate_report.assert_called_once_with(self.mock_analysis_results)
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    @patch('github_pr_analyzer.GitHubClient')
    def test_end_to_end_authentication_failure(self, mock_client_class):
        """Test handling of GitHub authentication failures."""
        mock_client_class.get_token_from_env.side_effect = GitHubAuthenticationError("Invalid token")
        
        with patch('sys.argv', ['github_pr_analyzer.py', 'testowner/test-repo']):
            result = main()
        
        assert result == 1
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    @patch('github_pr_analyzer.GitHubClient')
    def test_end_to_end_repository_not_found(self, mock_client_class):
        """Test handling of repository not found errors."""
        mock_client = Mock(spec=GitHubClient)
        mock_client.validate_token.return_value = True
        mock_client.get_repository_info.side_effect = GitHubAPIError("Repository not found")
        mock_client_class.return_value = mock_client
        mock_client_class.get_token_from_env.return_value = 'test_token'
        
        with patch('sys.argv', ['github_pr_analyzer.py', 'testowner/nonexistent-repo']):
            result = main()
        
        assert result == 1
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    @patch('github_pr_analyzer.GitHubClient')
    @patch('github_pr_analyzer.PRAnalyzer')
    def test_end_to_end_no_prs_found(self, mock_analyzer_class, mock_client_class):
        """Test handling when no PRs are found."""
        # Configure mocks
        mock_client = Mock(spec=GitHubClient)
        mock_client.validate_token.return_value = True
        mock_client.get_repository_info.return_value = {'full_name': 'testowner/empty-repo'}
        mock_client_class.return_value = mock_client
        mock_client_class.get_token_from_env.return_value = 'test_token'
        
        mock_analyzer = Mock(spec=PRAnalyzer)
        mock_analyzer.fetch_monthly_prs.return_value = []  # No PRs found
        mock_analyzer_class.return_value = mock_analyzer
        
        with patch('sys.argv', ['github_pr_analyzer.py', 'testowner/empty-repo']):
            result = main()
        
        # Should exit successfully with no PRs message
        assert result == 0


class TestCLIArgumentParsing:
    """Test cases for command-line interface argument parsing."""
    
    def test_cli_argument_parsing_basic(self):
        """Test basic CLI argument parsing."""
        with patch('sys.argv', ['github_pr_analyzer.py', 'owner/repo']):
            args = parse_arguments()
            
            assert args.repository == 'owner/repo'
            assert args.months == 1
            assert args.output == 'pr_analysis.csv'
            assert args.verbose is False
            assert args.debug is False
            assert args.quiet is False
    
    def test_cli_argument_parsing_all_options(self):
        """Test CLI argument parsing with all options."""
        with patch('sys.argv', [
            'github_pr_analyzer.py', 
            'facebook/react', 
            '--months', '6', 
            '--output', 'react_analysis.csv',
            '--verbose',
            '--debug'
        ]):
            args = parse_arguments()
            
            assert args.repository == 'facebook/react'
            assert args.months == 6
            assert args.output == 'react_analysis.csv'
            assert args.verbose is True
            assert args.debug is True
    
    def test_cli_argument_parsing_short_options(self):
        """Test CLI argument parsing with short option flags."""
        with patch('sys.argv', [
            'github_pr_analyzer.py',
            'kubernetes/kubernetes',
            '-o', 'k8s.csv',
            '-v',
            '-q'
        ]):
            args = parse_arguments()
            
            assert args.repository == 'kubernetes/kubernetes'
            assert args.output == 'k8s.csv'
            assert args.verbose is True
            assert args.quiet is True


class TestInputValidation:
    """Test cases for input validation logic."""
    
    def test_validate_inputs_valid_repository(self):
        """Test input validation with valid repository format."""
        args = argparse.Namespace(
            repository='microsoft/vscode',
            months=3,
            output='test.csv'
        )
        
        owner, repo = validate_inputs(args)
        
        assert owner == 'microsoft'
        assert repo == 'vscode'
    
    def test_validate_inputs_invalid_repository_format(self):
        """Test input validation with invalid repository format."""
        args = argparse.Namespace(
            repository='invalid-format',
            months=1,
            output='test.csv'
        )
        
        with pytest.raises(ValueError, match="Repository must be in format 'owner/repo'"):
            validate_inputs(args)
    
    def test_validate_inputs_empty_owner(self):
        """Test input validation with empty owner."""
        args = argparse.Namespace(
            repository='/repo',
            months=1,
            output='test.csv'
        )
        
        with pytest.raises(ValueError, match="Repository must be in format 'owner/repo' with valid characters"):
            validate_inputs(args)
    
    def test_validate_inputs_empty_repo(self):
        """Test input validation with empty repository name."""
        args = argparse.Namespace(
            repository='owner/',
            months=1,
            output='test.csv'
        )
        
        with pytest.raises(ValueError, match="Repository must be in format 'owner/repo' with valid characters"):
            validate_inputs(args)
    
    def test_validate_inputs_invalid_months(self):
        """Test input validation with invalid months parameter."""
        args = argparse.Namespace(
            repository='owner/repo',
            months=0,
            output='test.csv'
        )
        
        with pytest.raises(ValueError, match="Months parameter must be at least 1"):
            validate_inputs(args)
    
    def test_validate_inputs_months_too_large(self):
        """Test input validation with months parameter too large."""
        args = argparse.Namespace(
            repository='owner/repo',
            months=25,
            output='test.csv'
        )
        
        with pytest.raises(ValueError, match="Months parameter cannot exceed 24"):
            validate_inputs(args)
    
    def test_validate_inputs_creates_output_directory(self):
        """Test input validation creates output directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_output = Path(tmpdir) / "nested" / "subdir" / "output.csv"
            
            args = argparse.Namespace(
                repository='owner/repo',
                months=1,
                output=str(nested_output)
            )
            
            owner, repo = validate_inputs(args)
            
            # Directory should be created
            assert nested_output.parent.exists()
            assert owner == 'owner'
            assert repo == 'repo'


class TestErrorHandlingScenarios:
    """Test cases for various error conditions and edge cases."""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_github_token(self):
        """Test error handling when GITHUB_TOKEN is missing."""
        with patch('sys.argv', ['github_pr_analyzer.py', 'owner/repo']):
            result = main()
        
        assert result == 1
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    @patch('github_pr_analyzer.GitHubClient')
    @patch('github_pr_analyzer.PRAnalyzer')
    def test_pr_analysis_error(self, mock_analyzer_class, mock_client_class):
        """Test handling of PR analysis errors."""
        # Configure mocks
        mock_client = Mock(spec=GitHubClient)
        mock_client.validate_token.return_value = True
        mock_client.get_repository_info.return_value = {'full_name': 'owner/repo'}
        mock_client_class.return_value = mock_client
        mock_client_class.get_token_from_env.return_value = 'test_token'
        
        mock_analyzer = Mock(spec=PRAnalyzer)
        mock_analyzer.fetch_monthly_prs.return_value = [{'number': 1}]
        mock_analyzer.analyze_pr_lifecycle_times.side_effect = PRAnalysisError("Analysis failed")
        mock_analyzer_class.return_value = mock_analyzer
        
        with patch('sys.argv', ['github_pr_analyzer.py', 'owner/repo']):
            result = main()
        
        assert result == 1
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'})
    @patch('github_pr_analyzer.GitHubClient')
    @patch('github_pr_analyzer.PRAnalyzer')
    @patch('github_pr_analyzer.CSVReporter')
    def test_csv_generation_error(self, mock_csv_class, mock_analyzer_class, mock_client_class):
        """Test handling of CSV generation errors."""
        # Configure mocks
        mock_client = Mock(spec=GitHubClient)
        mock_client.validate_token.return_value = True
        mock_client.get_repository_info.return_value = {'full_name': 'owner/repo'}
        mock_client_class.return_value = mock_client
        mock_client_class.get_token_from_env.return_value = 'test_token'
        
        mock_analyzer = Mock(spec=PRAnalyzer)
        mock_analyzer.fetch_monthly_prs.return_value = [{'number': 1}]
        mock_analyzer.analyze_pr_lifecycle_times.return_value = {'pr_details': []}
        mock_analyzer_class.return_value = mock_analyzer
        
        mock_reporter = Mock(spec=CSVReporter)
        mock_reporter.validate_analysis_results.side_effect = CSVReportError("Invalid data")
        mock_csv_class.return_value = mock_reporter
        
        with patch('sys.argv', ['github_pr_analyzer.py', 'owner/repo']):
            result = main()
        
        assert result == 1
    
    def test_keyboard_interrupt(self):
        """Test graceful handling of keyboard interrupt."""
        with patch('github_pr_analyzer.parse_arguments', side_effect=KeyboardInterrupt()):
            result = main()
        
        assert result == 1
    
    def test_unexpected_error(self):
        """Test handling of unexpected errors."""
        with patch('github_pr_analyzer.parse_arguments', side_effect=Exception("Unexpected error")):
            result = main()
        
        assert result == 1


class TestSummaryPrinting:
    """Test cases for summary output formatting."""
    
    def test_print_summary_complete_data(self, capsys):
        """Test summary printing with complete data."""
        analysis_results = {
            'summary': {
                'total_prs_analyzed': 10,
                'merged_prs': 8,
                'reviewed_prs': 9,
                'avg_time_to_first_review': 6.5,
                'avg_time_to_merge': 48.0,
                'avg_commit_lead_time': 72.5
            }
        }
        
        print_summary(analysis_results, "facebook/react", 3, "output.csv")
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Check summary information
        assert "GitHub PR Analysis Results for facebook/react" in output
        assert "Analysis Period: Last 3 months" in output
        assert "Total PRs Analyzed: 10" in output
        assert "Merged PRs: 8 (80.0% of total)" in output
        assert "Reviewed PRs: 9 (90.0% of total)" in output
        
        # Check timing metrics
        assert "Time to First Review: 6.5 hours (0.3 days)" in output
        assert "Time to Merge: 48.0 hours (2.0 days)" in output
        assert "Commit Lead Time: 72.5 hours (3.0 days)" in output
    
    def test_print_summary_missing_metrics(self, capsys):
        """Test summary printing with missing timing metrics."""
        analysis_results = {
            'summary': {
                'total_prs_analyzed': 5,
                'merged_prs': 0,
                'reviewed_prs': 0,
                'avg_time_to_first_review': None,
                'avg_time_to_merge': None,
                'avg_commit_lead_time': None
            }
        }
        
        print_summary(analysis_results, "owner/repo", 1, "output.csv")
        
        captured = capsys.readouterr()
        output = captured.out
        
        # Check handling of missing metrics
        assert "Time to First Review: No data available" in output
        assert "Time to Merge: No data available" in output
        assert "Commit Lead Time: No data available" in output


class TestFileSystemIntegration:
    """Test cases for actual file system operations."""
    
    def setup_method(self):
        """Set up test environment."""
        self.tmpdir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_actual_csv_generation(self):
        """Test actual CSV file generation and content validation."""
        output_path = Path(self.tmpdir) / "actual_test.csv"
        
        # Create real analysis results
        analysis_results = {
            'summary': {
                'total_prs_analyzed': 2,
                'merged_prs': 1,
                'reviewed_prs': 2,
                'avg_time_to_first_review': 8.0,
                'avg_time_to_merge': 48.0,
                'avg_commit_lead_time': 96.0
            },
            'pr_details': [
                {
                    'pr_number': 200,
                    'title': 'Integration test PR',
                    'state': 'closed',
                    'created_at': '2024-12-01T10:00:00Z',
                    'merged_at': '2024-12-03T10:00:00Z',
                    'time_to_first_review_hours': 8.0,
                    'time_to_merge_hours': 48.0,
                    'commit_lead_time_hours': 96.0,
                    'has_reviews': True,
                    'review_count': 2,
                    'comment_count': 3,
                    'commit_count': 5,
                    'is_merged': True
                }
            ]
        }
        
        # Generate actual CSV
        reporter = CSVReporter(str(output_path))
        result_path = reporter.generate_report(analysis_results)
        
        # Verify file exists and content
        assert Path(result_path).exists()
        
        with open(result_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Verify summary comments
            assert 'Total PRs Analyzed: 2' in content
            assert 'Average Time to First Review: 8.0 hours' in content
            assert 'Average Time to Merge: 48.0 hours' in content
            assert 'Average Commit Lead Time: 96.0 hours' in content
            
            # Verify data
            assert '200' in content
            assert 'Integration test PR' in content
            assert '8.00' in content
            assert '48.00' in content
            assert '96.00' in content
        
        # Parse and validate CSV structure
        with open(result_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
            # Find header line (skip comments)
            header_line = None
            data_lines = []
            
            for line in lines:
                if line.strip() and not line.startswith('#'):
                    if 'pr_number' in line:
                        header_line = line
                    elif header_line is not None:
                        data_lines.append(line)
            
            assert header_line is not None
            assert len(data_lines) == 1
            
            # Verify headers include all metrics
            assert 'time_to_first_review_hours' in header_line
            assert 'time_to_merge_hours' in header_line
            assert 'commit_lead_time_hours' in header_line


class TestMainPipelineIntegration:
    """Test cases for main pipeline integration including filename generation."""
    
    def test_main_workflow_includes_repository_context(self):
        """Test that repository name flows through entire pipeline."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'}):
            with patch('sys.argv', ['github_pr_analyzer.py', 'testowner/test-repo']):
                with patch('github_pr_analyzer.GitHubClient') as mock_client_class:
                    with patch('github_pr_analyzer.PRAnalyzer') as mock_analyzer_class:
                        with patch('github_pr_analyzer.CSVReporter') as mock_csv_class:
                            # Setup mocks
                            mock_client = Mock(spec=GitHubClient)
                            mock_client.validate_token.return_value = True
                            mock_client.get_repository_info.return_value = {'full_name': 'testowner/test-repo'}
                            mock_client_class.return_value = mock_client
                            
                            mock_analyzer = Mock(spec=PRAnalyzer)
                            mock_analyzer.fetch_monthly_prs.return_value = [{'number': 123, 'user': {'id': 456, 'login': 'testuser'}}]
                            mock_analyzer.analyze_pr_lifecycle_times.return_value = {
                                'summary': {'repository_name': 'testowner/test-repo', 'total_prs_analyzed': 1},
                                'pr_details': [{'pr_number': 123, 'repository_name': 'testowner/test-repo', 'pr_creator_github_id': '456'}]
                            }
                            mock_analyzer_class.return_value = mock_analyzer
                            
                            mock_reporter = Mock(spec=CSVReporter)
                            mock_reporter.generate_report.return_value = '/path/to/pr_analysis_test-repo.csv'
                            mock_csv_class.return_value = mock_reporter
                            
                            # Run main function
                            result = main()
                            
                            assert result == 0
                            # Verify repository context flows through
                            mock_analyzer.analyze_pr_lifecycle_times.assert_called_once()
                            args = mock_analyzer.analyze_pr_lifecycle_times.call_args[0]
                            assert args[1] == 'testowner'  # owner
                            assert args[2] == 'test-repo'  # repo

    def test_argument_parsing_preserves_repository_format(self):
        """Test that argument parsing maintains owner/repo format correctly."""
        test_cases = [
            ('microsoft/vscode', 'microsoft', 'vscode'),
            ('facebook/react', 'facebook', 'react'),
            ('kubernetes/kubernetes', 'kubernetes', 'kubernetes'),
            ('google/go-github', 'google', 'go-github')
        ]
        
        for repo_arg, expected_owner, expected_repo in test_cases:
            with patch('sys.argv', ['github_pr_analyzer.py', repo_arg]):
                args = parse_arguments()
                owner, repo = validate_inputs(args)
                
                assert owner == expected_owner
                assert repo == expected_repo
                assert args.repository == repo_arg

    def test_auto_filename_generation(self):
        """Test automatic filename generation with repository name."""
        test_cases = [
            ('microsoft', 'vscode', 'pr_analysis_vscode.csv'),
            ('facebook', 'react', 'pr_analysis_react.csv'),
            ('kubernetes', 'kubernetes', 'pr_analysis_kubernetes.csv'),
            ('google', 'go-github', 'pr_analysis_go-github.csv'),
            ('', '', 'pr_analysis.csv'),  # Empty case
            ('test', '', 'pr_analysis.csv'),  # Missing repo
        ]
        
        for owner, repo, expected in test_cases:
            result = generate_auto_filename(owner, repo)
            assert result == expected

    def test_repository_name_sanitization(self):
        """Test filename sanitization for special characters."""
        # Test full repository name sanitization
        full_repo_test_cases = [
            ('normal/repo', 'normal_repo'),
            ('user/repo-with-dashes', 'user_repo-with-dashes'),
            ('owner/repo with spaces', 'owner_repo_with_spaces'),
            ('test/repo:with:colons', 'test_repo_with_colons'),
            ('', 'unknown_repo'),  # Empty case
        ]
        
        for input_name, expected in full_repo_test_cases:
            result = sanitize_repository_name_for_filename(input_name)
            assert result == expected
        
        # Test just repo part sanitization (used in generate_auto_filename)
        repo_part_test_cases = [
            ('repo', 'repo'),
            ('repo-with-dashes', 'repo-with-dashes'),
            ('repo with spaces', 'repo_with_spaces'),
            ('repo:with:colons', 'repo_with_colons'),
            ('repo*with*stars', 'repo_with_stars'),
            ('repo?with?questions', 'repo_with_questions'),
            ('repo"with"quotes', 'repo_with_quotes'),
            ('repo<with>brackets', 'repo_with_brackets'),
            ('repo|with|pipes', 'repo_with_pipes'),
            ('repo\\with\\backslashes', 'repo_with_backslashes'),
        ]
        
        for repo_part, expected in repo_part_test_cases:
            result = sanitize_repository_name_for_filename(repo_part)
            assert result == expected

    def test_custom_output_overrides_auto_filename(self):
        """Test that custom --output parameter takes precedence over auto-generation."""
        with patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'}):
            with patch('sys.argv', ['github_pr_analyzer.py', 'owner/repo', '--output', 'custom_report.csv']):
                with patch('github_pr_analyzer.GitHubClient') as mock_client_class:
                    with patch('github_pr_analyzer.PRAnalyzer') as mock_analyzer_class:
                        with patch('github_pr_analyzer.CSVReporter') as mock_csv_class:
                            # Setup mocks
                            mock_client = Mock(spec=GitHubClient)
                            mock_client.validate_token.return_value = True
                            mock_client.get_repository_info.return_value = {'full_name': 'owner/repo'}
                            mock_client_class.return_value = mock_client
                            
                            mock_analyzer = Mock(spec=PRAnalyzer)
                            mock_analyzer.fetch_monthly_prs.return_value = [{'number': 123, 'user': {'id': 456, 'login': 'testuser'}}]
                            mock_analyzer.analyze_pr_lifecycle_times.return_value = {
                                'summary': {'repository_name': 'owner/repo', 'total_prs_analyzed': 1},
                                'pr_details': [{'pr_number': 123, 'repository_name': 'owner/repo', 'pr_creator_github_id': '456'}]
                            }
                            mock_analyzer_class.return_value = mock_analyzer
                            
                            mock_reporter = Mock(spec=CSVReporter)
                            mock_reporter.generate_report.return_value = 'custom_report.csv'
                            mock_csv_class.return_value = mock_reporter
                            
                            # Run main function
                            result = main()
                            
                            assert result == 0
                            # Verify custom filename is used, not auto-generated
                            mock_csv_class.assert_called_once_with('custom_report.csv')

    def test_summary_output_includes_repository_name(self):
        """Test that console summary output shows repository context."""
        analysis_results = {
            'summary': {'repository_name': 'microsoft/vscode', 'total_prs_analyzed': 5, 'merged_prs': 4, 'reviewed_prs': 5},
            'pr_details': []
        }
        
        with patch('builtins.print') as mock_print:
            print_summary(analysis_results, 'microsoft/vscode', 1, 'pr_analysis_vscode.csv')
            
            # Verify repository name appears in output
            print_calls = [call[0][0] for call in mock_print.call_args_list if call[0]]
            summary_text = '\n'.join(print_calls)
            
            assert 'microsoft/vscode' in summary_text
            assert 'Total PRs Analyzed: 5' in summary_text
            assert 'pr_analysis_vscode.csv' in summary_text

    def test_end_to_end_csv_with_new_fields(self):
        """Test complete workflow generating CSV with all new fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_output.csv"
            
            with patch.dict(os.environ, {'GITHUB_TOKEN': 'test_token'}):
                with patch('sys.argv', ['github_pr_analyzer.py', 'test/repo', '--output', str(output_path)]):
                    with patch('github_pr_analyzer.GitHubClient') as mock_client_class:
                        with patch('github_pr_analyzer.PRAnalyzer') as mock_analyzer_class:
                            # Setup mocks
                            mock_client = Mock(spec=GitHubClient)
                            mock_client.validate_token.return_value = True
                            mock_client.get_repository_info.return_value = {'full_name': 'test/repo'}
                            mock_client_class.return_value = mock_client
                            
                            mock_analyzer = Mock(spec=PRAnalyzer)
                            mock_analyzer.fetch_monthly_prs.return_value = [{'number': 123, 'user': {'id': 456, 'login': 'testuser'}}]
                            mock_analyzer.analyze_pr_lifecycle_times.return_value = {
                                'summary': {'repository_name': 'test/repo', 'total_prs_analyzed': 1, 'merged_prs': 1, 'reviewed_prs': 1},
                                'pr_details': [
                                    {
                                        'pr_number': 123,
                                        'title': 'Test PR',
                                        'repository_name': 'test/repo',
                                        'pr_creator_github_id': '456',
                                        'pr_creator_login': 'testuser',
                                        'time_to_first_review_hours': 2.5,
                                        'time_to_merge_hours': 24.0,
                                        'commit_lead_time_hours': 22.5,
                                        'has_reviews': True,
                                        'is_merged': True
                                    }
                                ]
                            }
                            mock_analyzer_class.return_value = mock_analyzer
                            
                            # Run main function (uses real CSVReporter)
                            result = main()
                            
                            assert result == 0
                            assert output_path.exists()
                            
                            # Verify CSV content includes new fields
                            with open(output_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                assert 'test/repo' in content
                                assert '456' in content  # GitHub ID
                                # Note: login is tracked internally but not in CSV output
                                assert 'repository_name' in content
                                assert 'pr_creator_github_id' in content

    def test_multiple_repositories_maintain_context(self):
        """Test that different repository names are handled correctly."""
        repos_to_test = ['microsoft/vscode', 'facebook/react', 'kubernetes/kubernetes']
        
        for repo_name in repos_to_test:
            owner, repo_part = repo_name.split('/')
            expected_filename = f"pr_analysis_{sanitize_repository_name_for_filename(repo_part)}.csv"
            
            auto_filename = generate_auto_filename(owner, repo_part)
            assert auto_filename == expected_filename

    def test_auto_generated_filename_behavior(self):
        """Test that filenames are auto-generated correctly in realistic scenarios."""
        test_scenarios = [
            ('microsoft/vscode', 'pr_analysis_vscode.csv'),
            ('facebook/react', 'pr_analysis_react.csv'),
            ('kubernetes/kubernetes', 'pr_analysis_kubernetes.csv'),
            ('google/go-github', 'pr_analysis_go-github.csv'),
        ]
        
        for repo_name, expected_filename in test_scenarios:
            owner, repo = repo_name.split('/')
            result = generate_auto_filename(owner, repo)
            assert result == expected_filename


class TestRepositoryNameValidation:
    """Test cases for repository name validation and error handling."""
    
    def test_repository_name_validation(self):
        """Test repository name format validation with various scenarios."""
        valid_cases = [
            'microsoft/vscode',
            'facebook/react',
            'kubernetes/kubernetes',
            'google/go-github',
            'user/repo-name',
            'org/repo_name',
            'owner/123-repo'
        ]
        
        for repo_name in valid_cases:
            assert validate_repository_name_format(repo_name) == True
        
        invalid_cases = [
            '',                    # Empty string
            'no-slash',           # Missing slash
            '/repo',              # Missing owner
            'owner/',             # Missing repo
            'owner//',            # Double slash
            'owner/repo/extra',   # Extra parts
            'owner/ repo',        # Space in repo
            'owner /repo',        # Space in owner
            'owner\trepo',        # Tab character
            'owner\nrepo',        # Newline
            'owner/repo..',       # Invalid characters
        ]
        
        for repo_name in invalid_cases:
            assert validate_repository_name_format(repo_name) == False

    def test_input_validation_with_invalid_repo_names(self):
        """Test that input validation rejects invalid repository names."""
        invalid_repos = [
            'no-slash',
            '/missing-owner',
            'missing-repo/',
            'owner/ repo',
            'owner/repo..'
        ]
        
        for invalid_repo in invalid_repos:
            with patch('sys.argv', ['github_pr_analyzer.py', invalid_repo]):
                args = parse_arguments()
                
                with pytest.raises(ValueError, match="Repository must be in format 'owner/repo' with valid characters"):
                    validate_inputs(args)


if __name__ == "__main__":
    pytest.main([__file__])
