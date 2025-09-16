"""
Unit tests for CSV reporter module.

This module contains comprehensive tests for the CSVReporter class,
including CSV generation, formatting, and error handling scenarios.
"""

import pytest
import tempfile
import csv
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

from csv_reporter import CSVReporter, CSVReportError
from datetime import datetime


class TestCSVReporter:
    """Test cases for CSVReporter class initialization."""
    
    def test_init_with_valid_path(self):
        """Test CSVReporter initialization with valid output path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.csv"
            reporter = CSVReporter(str(output_path))
            
            assert reporter.output_path == output_path
            assert reporter.logger is not None
    
    def test_init_with_empty_path(self):
        """Test CSVReporter initialization with empty output path raises error."""
        with pytest.raises(CSVReportError, match="Output path is required"):
            CSVReporter("")
    
    def test_init_with_none_path(self):
        """Test CSVReporter initialization with None output path raises error."""
        with pytest.raises(CSVReportError, match="Output path is required"):
            CSVReporter(None)
    
    def test_init_creates_directory(self):
        """Test CSVReporter initialization creates output directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = Path(tmpdir) / "nested" / "dir" / "test.csv"
            reporter = CSVReporter(str(nested_path))
            
            # Directory should be created
            assert nested_path.parent.exists()
            assert reporter.output_path == nested_path


class TestCSVGeneration:
    """Test cases for CSV file generation with all three metrics."""
    
    def setup_method(self):
        """Set up test reporter for each test method."""
        self.tmpdir = tempfile.mkdtemp()
        self.output_path = Path(self.tmpdir) / "test.csv"
        self.reporter = CSVReporter(str(self.output_path))
    
    def teardown_method(self):
        """Clean up after each test method."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_csv_generation_with_complete_data(self):
        """Test CSV generation with complete PR data including all three timing metrics."""
        analysis_results = {
            'summary': {
                'total_prs_analyzed': 2,
                'merged_prs': 1,
                'reviewed_prs': 2,
                'avg_time_to_first_review': 4.5,
                'avg_time_to_merge': 24.0,
                'avg_commit_lead_time': 48.0
            },
            'pr_details': [
                {
                    'pr_number': 123,
                    'title': 'Fix critical bug',
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
                    'pr_number': 124,
                    'title': 'Add new feature',
                    'state': 'open',
                    'created_at': '2024-12-03T15:30:00Z',
                    'merged_at': None,
                    'time_to_first_review_hours': 5.0,
                    'time_to_merge_hours': None,
                    'commit_lead_time_hours': None,
                    'has_reviews': True,
                    'review_count': 1,
                    'comment_count': 0,
                    'commit_count': 3,
                    'is_merged': False
                }
            ]
        }
        
        result_path = self.reporter.generate_report(analysis_results)
        
        # Verify file was created
        assert Path(result_path).exists()
        assert result_path == str(self.output_path)
        
        # Verify CSV content
        with open(result_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Check summary comments
            assert '# Total PRs Analyzed: 2' in content
            assert '# Average Time to First Review: 4.5 hours' in content
            assert '# Average Time to Merge: 24.0 hours' in content
            assert '# Average Commit Lead Time: 48.0 hours' in content
            
            # Check data presence
            assert '123' in content
            assert 'Fix critical bug' in content
            assert '4.00' in content  # time_to_first_review_hours
            assert '24.00' in content  # time_to_merge_hours
            assert '48.00' in content  # commit_lead_time_hours
    
    def test_csv_generation_empty_details(self):
        """Test CSV generation with empty PR details."""
        analysis_results = {
            'summary': {'total_prs_analyzed': 0},
            'pr_details': []
        }
        
        result_path = self.reporter.generate_report(analysis_results)
        
        # File should be created with headers only
        assert Path(result_path).exists()
        
        with open(result_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
            # Should have summary comments and headers, but no data rows
            header_found = False
            for row in rows:
                if row and not row[0].startswith('#') and row[0]:
                    if 'pr_number' in row:
                        header_found = True
                    elif header_found:
                        # This would be a data row, but there shouldn't be any
                        pytest.fail("Found data row when none expected")
            
            assert header_found, "Headers not found in CSV"
    
    def test_csv_generation_missing_analysis_results(self):
        """Test CSV generation with missing analysis results raises error."""
        with pytest.raises(CSVReportError, match="Analysis results are required"):
            self.reporter.generate_report(None)
    
    def test_csv_generation_missing_pr_details(self):
        """Test CSV generation with missing pr_details key raises error."""
        analysis_results = {'summary': {'total': 0}}
        
        with pytest.raises(CSVReportError, match="Analysis results must contain 'pr_details'"):
            self.reporter.generate_report(analysis_results)


class TestCSVHeaders:
    """Test cases for CSV column validation including all three metric columns."""
    
    def setup_method(self):
        """Set up test reporter for each test method."""
        self.tmpdir = tempfile.mkdtemp()
        self.output_path = Path(self.tmpdir) / "test.csv"
        self.reporter = CSVReporter(str(self.output_path))
    
    def teardown_method(self):
        """Clean up after each test method."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_csv_headers_include_all_metrics(self):
        """Test CSV headers include all three timing metric columns."""
        headers = self.reporter._format_csv_headers()
        
        # Verify all expected headers are present
        expected_headers = [
            'pr_number',
            'title', 
            'state',
            'created_at',
            'merged_at',
            'repository_name',
            'pr_creator_github_id',
            'pr_creator_username',
            'time_to_first_review_hours',
            'time_to_merge_hours',
            'commit_lead_time_hours',
            'has_reviews',
            'review_count',
            'comment_count',
            'commit_count',
            'is_merged'
        ]
        
        assert headers == expected_headers
    
    def test_csv_headers_in_generated_file(self):
        """Test CSV headers appear correctly in generated file."""
        analysis_results = {
            'pr_details': [
                {
                    'pr_number': 1,
                    'title': 'Test',
                    'state': 'open',
                    'time_to_first_review_hours': 1.0,
                    'time_to_merge_hours': None,
                    'commit_lead_time_hours': None
                }
            ]
        }
        
        self.reporter.generate_report(analysis_results)
        
        # Read and verify headers
        with open(self.output_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            # Skip comment lines
            for row in reader:
                if row and not row[0].startswith('#'):
                    # This should be the header row
                    assert 'time_to_first_review_hours' in row
                    assert 'time_to_merge_hours' in row
                    assert 'commit_lead_time_hours' in row
                    break

    def test_csv_headers_include_new_fields(self):
        """Test CSV headers include new repository name and PR creator GitHub ID fields."""
        headers = self.reporter._format_csv_headers()
        
        # Verify new fields are present in correct positions
        assert 'repository_name' in headers
        assert 'pr_creator_github_id' in headers
        
        # Verify they appear after merged_at but before timing metrics
        repo_index = headers.index('repository_name')
        creator_index = headers.index('pr_creator_github_id')
        merged_at_index = headers.index('merged_at')
        review_time_index = headers.index('time_to_first_review_hours')
        
        assert repo_index == merged_at_index + 1
        assert creator_index == merged_at_index + 2
        assert review_time_index > creator_index

    def test_csv_data_formatting_with_new_fields(self):
        """Test CSV data formatting includes new repository and creator fields."""
        pr_details = [
            {
                'pr_number': 123,
                'title': 'Test PR with new fields',
                'state': 'closed',
                'created_at': '2024-12-01T10:00:00Z',
                'merged_at': '2024-12-02T15:30:00Z',
                'repository_name': 'facebook/react',
                'pr_creator_github_id': '12345',
                'pr_creator_login': 'testuser',
                'time_to_first_review_hours': 24.5,
                'time_to_merge_hours': 29.5,
                'commit_lead_time_hours': 28.0,
                'has_reviews': True,
                'review_count': 2,
                'comment_count': 5,
                'commit_count': 3,
                'is_merged': True
            }
        ]
        
        rows = self.reporter._format_csv_rows(pr_details)
        
        assert len(rows) == 1
        row = rows[0]
        assert row[5] == 'facebook/react'  # repository_name position
        assert row[6] == '12345'  # pr_creator_github_id position
        assert row[7] == 'testuser'  # pr_creator_username position

    def test_csv_validation_requires_new_fields(self):
        """Test CSV validation requires repository name and creator GitHub ID fields."""
        # Missing repository_name should raise error
        analysis_results_missing_repo = {
            'pr_details': [
                {
                    'pr_number': 123,
                    'pr_creator_github_id': '12345',
                    'pr_creator_login': 'testuser'
                }
            ]
        }
        
        with pytest.raises(CSVReportError, match="missing required field: repository_name"):
            self.reporter.validate_analysis_results(analysis_results_missing_repo)
        
        # Missing pr_creator_github_id should raise error
        analysis_results_missing_creator = {
            'pr_details': [
                {
                    'pr_number': 123,
                    'repository_name': 'facebook/react',
                    'pr_creator_login': 'testuser'
                }
            ]
        }
        
        with pytest.raises(CSVReportError, match="missing required field: pr_creator_github_id"):
            self.reporter.validate_analysis_results(analysis_results_missing_creator)
        
        # Valid data with new fields should pass
        analysis_results_valid = {
            'pr_details': [
                {
                    'pr_number': 123,
                    'repository_name': 'facebook/react',
                    'pr_creator_github_id': '12345',
                    'pr_creator_login': 'testuser'
                }
            ]
        }
        
        assert self.reporter.validate_analysis_results(analysis_results_valid) == True

    def test_csv_generation_with_repository_context(self):
        """Test complete CSV generation with repository context in summary."""
        analysis_results = {
            'summary': {
                'repository_name': 'microsoft/vscode',
                'total_prs_analyzed': 2,
                'merged_prs': 1,
                'reviewed_prs': 2
            },
            'pr_details': [
                {
                    'pr_number': 100,
                    'title': 'Add feature',
                    'state': 'closed',
                    'created_at': '2024-12-01T09:00:00Z',
                    'merged_at': '2024-12-01T15:00:00Z',
                    'repository_name': 'microsoft/vscode',
                    'pr_creator_github_id': '98765',
                    'time_to_first_review_hours': 2.5,
                    'time_to_merge_hours': 6.0,
                    'commit_lead_time_hours': 5.5,
                    'has_reviews': True,
                    'review_count': 1,
                    'comment_count': 3,
                    'commit_count': 2,
                    'is_merged': True
                },
                {
                    'pr_number': 101,
                    'title': 'Fix bug',
                    'state': 'open',
                    'created_at': '2024-12-02T08:00:00Z',
                    'merged_at': None,
                    'repository_name': 'microsoft/vscode',
                    'pr_creator_github_id': '54321',
                    'time_to_first_review_hours': 1.0,
                    'time_to_merge_hours': None,
                    'commit_lead_time_hours': None,
                    'has_reviews': True,
                    'review_count': 1,
                    'comment_count': 2,
                    'commit_count': 1,
                    'is_merged': False
                }
            ]
        }
        
        output_file = self.reporter.generate_report(analysis_results)
        
        # Verify file was generated
        assert Path(output_file).exists()
        
        # Read and verify content
        with open(output_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Verify repository context in summary
            assert '# Repository: microsoft/vscode' in content
            assert '# Total PRs Analyzed: 2' in content
            
            # Verify new fields in data
            assert 'microsoft/vscode' in content
            assert '98765' in content
            assert '54321' in content


class TestCSVDataFormatting:
    """Test cases for data transformation and formatting with all three metrics."""
    
    def setup_method(self):
        """Set up test reporter for each test method."""
        self.tmpdir = tempfile.mkdtemp()
        self.output_path = Path(self.tmpdir) / "test.csv"
        self.reporter = CSVReporter(str(self.output_path))
    
    def teardown_method(self):
        """Clean up after each test method."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_csv_data_formatting_with_all_metrics(self):
        """Test CSV data formatting includes all three timing metrics."""
        pr_details = [
            {
                'pr_number': 100,
                'title': 'Test PR with all metrics',
                'state': 'closed',
                'created_at': '2024-12-01T10:00:00Z',
                'merged_at': '2024-12-02T14:30:00Z',
                'repository_name': 'test/repo',
                'pr_creator_github_id': '12345',
                'pr_creator_login': 'testuser',
                'time_to_first_review_hours': 2.5,
                'time_to_merge_hours': 28.5,
                'commit_lead_time_hours': 72.25,
                'has_reviews': True,
                'review_count': 3,
                'comment_count': 5,
                'commit_count': 8,
                'is_merged': True
            }
        ]
        
        rows = self.reporter._format_csv_rows(pr_details)
        
        assert len(rows) == 1
        row = rows[0]
        
        # Check specific metric formatting
        assert row[0] == '100'  # pr_number
        assert row[1] == 'Test PR with all metrics'  # title
        assert row[5] == 'test/repo'  # repository_name
        assert row[6] == '12345'  # pr_creator_github_id
        assert row[7] == 'testuser'  # pr_creator_username
        assert row[8] == '2.50'  # time_to_first_review_hours
        assert row[9] == '28.50'  # time_to_merge_hours
        assert row[10] == '72.25'  # commit_lead_time_hours
        assert row[15] == 'True'  # is_merged
    
    def test_csv_data_formatting_with_null_metrics(self):
        """Test CSV data formatting handles None values for metrics."""
        pr_details = [
            {
                'pr_number': 101,
                'title': 'Unreviewed PR',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z',
                'merged_at': None,
                'repository_name': 'test/repo',
                'pr_creator_github_id': '67890',
                'pr_creator_login': 'testuser2',
                'time_to_first_review_hours': None,
                'time_to_merge_hours': None,
                'commit_lead_time_hours': None,
                'has_reviews': False,
                'review_count': 0,
                'comment_count': 0,
                'commit_count': 2,
                'is_merged': False
            }
        ]
        
        rows = self.reporter._format_csv_rows(pr_details)
        
        assert len(rows) == 1
        row = rows[0]
        
        # Null metrics should be empty strings
        assert row[8] == ''  # time_to_first_review_hours
        assert row[9] == ''  # time_to_merge_hours
        assert row[10] == ''  # commit_lead_time_hours
        assert row[4] == ''  # merged_at
        # New fields should have values
        assert row[5] == 'test/repo'  # repository_name
        assert row[6] == '67890'  # pr_creator_github_id
    
    def test_text_sanitization(self):
        """Test text sanitization for CSV safety."""
        # Test newlines and tabs
        assert self.reporter._sanitize_text("Line 1\nLine 2\tTabbed") == "Line 1 Line 2 Tabbed"
        
        # Test excessive whitespace
        assert self.reporter._sanitize_text("  Too   many   spaces  ") == "Too many spaces"
        
        # Test long text truncation
        long_text = "A" * 250
        result = self.reporter._sanitize_text(long_text)
        assert len(result) == 200
        assert result.endswith("...")
    
    def test_datetime_formatting(self):
        """Test datetime formatting for consistent CSV output."""
        # Test ISO format with Z
        result = self.reporter._format_datetime("2024-12-01T10:30:45Z")
        assert result == "2024-12-01 10:30:45 UTC"
        
        # Test ISO format with timezone
        result = self.reporter._format_datetime("2024-12-01T10:30:45+00:00")
        assert result == "2024-12-01 10:30:45 UTC"
        
        # Test None value
        assert self.reporter._format_datetime(None) == ""
        
        # Test empty string
        assert self.reporter._format_datetime("") == ""
    
    def test_number_formatting(self):
        """Test numeric value formatting for CSV."""
        # Test float formatting
        assert self.reporter._format_number(12.345) == "12.35"
        assert self.reporter._format_number(0.0) == "0.00"
        assert self.reporter._format_number(100) == "100.00"
        
        # Test None value
        assert self.reporter._format_number(None) == ""


class TestCSVValidation:
    """Test cases for analysis results validation."""
    
    def setup_method(self):
        """Set up test reporter for each test method."""
        self.tmpdir = tempfile.mkdtemp()
        self.output_path = Path(self.tmpdir) / "test.csv"
        self.reporter = CSVReporter(str(self.output_path))
    
    def teardown_method(self):
        """Clean up after each test method."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_validate_valid_analysis_results(self):
        """Test validation of valid analysis results."""
        valid_results = {
            'summary': {'total_prs_analyzed': 1},
            'pr_details': [
                {
                    'pr_number': 123, 
                    'title': 'Test PR',
                    'repository_name': 'test/repo',
                    'pr_creator_github_id': '12345',
                    'pr_creator_login': 'testuser'
                }
            ]
        }
        
        assert self.reporter.validate_analysis_results(valid_results) is True
    
    def test_validate_non_dict_results(self):
        """Test validation fails for non-dictionary results."""
        with pytest.raises(CSVReportError, match="Analysis results must be a dictionary"):
            self.reporter.validate_analysis_results("not a dict")
    
    def test_validate_missing_pr_details(self):
        """Test validation fails for missing pr_details."""
        invalid_results = {'summary': {'total': 0}}
        
        with pytest.raises(CSVReportError, match="Analysis results must contain 'pr_details' key"):
            self.reporter.validate_analysis_results(invalid_results)
    
    def test_validate_non_list_pr_details(self):
        """Test validation fails for non-list pr_details."""
        invalid_results = {'pr_details': 'not a list'}
        
        with pytest.raises(CSVReportError, match="'pr_details' must be a list"):
            self.reporter.validate_analysis_results(invalid_results)
    
    def test_validate_invalid_pr_detail_structure(self):
        """Test validation fails for invalid PR detail structure."""
        invalid_results = {
            'pr_details': [
                'not a dict'
            ]
        }
        
        with pytest.raises(CSVReportError, match="PR detail at index 0 must be a dictionary"):
            self.reporter.validate_analysis_results(invalid_results)
    
    def test_validate_missing_required_fields(self):
        """Test validation fails for missing required fields in PR details."""
        invalid_results = {
            'pr_details': [
                {'title': 'Missing pr_number'}
            ]
        }
        
        with pytest.raises(CSVReportError, match="PR detail at index 0 missing required field: pr_number"):
            self.reporter.validate_analysis_results(invalid_results)


class TestCSVReporterUtilities:
    """Test cases for utility methods."""
    
    def setup_method(self):
        """Set up test reporter for each test method."""
        self.tmpdir = tempfile.mkdtemp()
        self.output_path = Path(self.tmpdir) / "test.csv"
        self.reporter = CSVReporter(str(self.output_path))
    
    def teardown_method(self):
        """Clean up after each test method."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_get_output_path(self):
        """Test get_output_path returns correct path."""
        assert self.reporter.get_output_path() == str(self.output_path)


class TestErrorHandling:
    """Test cases for error handling scenarios."""
    
    def test_csv_generation_with_file_write_error(self):
        """Test CSV generation handles file write errors gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a valid reporter first
            output_path = Path(tmpdir) / "test.csv"
            reporter = CSVReporter(str(output_path))
            
            analysis_results = {
                'pr_details': [{'pr_number': 1}]
            }
            
            # Mock the file open to raise an exception
            with patch('builtins.open', side_effect=PermissionError("Access denied")):
                with pytest.raises(CSVReportError, match="Failed to generate CSV report"):
                    reporter.generate_report(analysis_results)


# Test fixtures
@pytest.fixture
def sample_analysis_results():
    """Fixture providing sample analysis results for testing."""
    return {
        'summary': {
            'total_prs_analyzed': 3,
            'merged_prs': 2,
            'reviewed_prs': 3,
            'avg_time_to_first_review': 6.5,
            'avg_time_to_merge': 48.0,
            'avg_commit_lead_time': 96.5
        },
        'pr_details': [
            {
                'pr_number': 1,
                'title': 'First PR',
                'state': 'closed',
                'created_at': '2024-12-01T08:00:00Z',
                'merged_at': '2024-12-03T08:00:00Z',
                'time_to_first_review_hours': 4.0,
                'time_to_merge_hours': 48.0,
                'commit_lead_time_hours': 72.0,
                'has_reviews': True,
                'review_count': 2,
                'comment_count': 1,
                'commit_count': 5,
                'is_merged': True
            },
            {
                'pr_number': 2,
                'title': 'Second PR with\nnewlines\tand tabs',
                'state': 'open',
                'created_at': '2024-12-02T10:00:00Z',
                'merged_at': None,
                'time_to_first_review_hours': 9.0,
                'time_to_merge_hours': None,
                'commit_lead_time_hours': None,
                'has_reviews': True,
                'review_count': 1,
                'comment_count': 3,
                'commit_count': 2,
                'is_merged': False
            }
        ]
    }


class TestReviewerCSVGeneration:
    """Test reviewer workload analysis CSV generation functionality."""
    
    def setup_method(self):
        """Set up test fixtures for reviewer CSV tests."""
        self.tmpdir = tempfile.mkdtemp()
        self.output_file = Path(self.tmpdir) / "reviewer_test.csv"
        
        # Mock reviewer summary data
        self.mock_reviewer_summary = {
            'metadata': {
                'analysis_date': '2024-12-15T12:00:00',
                'total_prs_analyzed': 25,
                'include_teams': True,
                'overload_threshold': 15,
                'org_name': 'testorg'
            },
            'reviewer_data': {
                'alice': {
                    'login': 'alice',
                    'name': 'Alice Johnson',
                    'total_requests': 20,
                    'pr_numbers': [100, 101, 102, 103, 104],
                    'request_sources': ['individual', 'individual', 'team:core', 'individual', 'team:backend'],
                    'first_request_date': '2024-11-01T10:00:00Z',
                    'last_request_date': '2024-12-10T15:30:00Z'
                },
                'bob': {
                    'login': 'bob',
                    'name': 'Bob Smith',
                    'total_requests': 8,
                    'pr_numbers': [105, 106, 107],
                    'request_sources': ['individual', 'individual', 'individual'],
                    'first_request_date': '2024-11-15T09:00:00Z',
                    'last_request_date': '2024-12-05T14:00:00Z'
                },
                'team:frontend': {
                    'login': 'team:frontend',
                    'name': 'Team: Frontend',
                    'total_requests': 12,
                    'pr_numbers': [108, 109, 110, 111],
                    'request_sources': ['team:frontend', 'team:frontend', 'team:frontend', 'team:frontend'],
                    'first_request_date': '2024-11-20T11:00:00Z',
                    'last_request_date': '2024-12-08T16:00:00Z'
                }
            },
            'statistics': {
                'total_reviewers': 3,
                'total_requests': 40,
                'mean_requests': 13.33,
                'median_requests': 12,
                'std_dev_requests': 6.02,
                'min_requests': 8,
                'max_requests': 20
            },
            'overload_analysis': {
                'OVERLOADED': ['alice'],
                'HIGH': ['team:frontend'],
                'NORMAL': ['bob']
            },
            'distribution_analysis': {
                'concentration_ratio': 0.5,
                'gini_coefficient': 0.35,
                'reviewer_diversity_score': 0.65,
                'top_reviewers': [
                    {'login': 'alice', 'name': 'Alice Johnson', 'total_requests': 20, 'percentage_of_total': 50.0}
                ],
                'underutilized_reviewers': []
            }
        }
    
    def teardown_method(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)
    
    def test_generate_reviewer_report_success(self):
        """Test successful reviewer CSV report generation."""
        reporter = CSVReporter(self.output_file)
        
        output_path = reporter.generate_reviewer_report(self.mock_reviewer_summary)
        
        assert output_path == str(self.output_file)
        assert self.output_file.exists()
        
        # Read and verify CSV content
        with open(self.output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for header comments
        assert "# GitHub PR Reviewer Workload Analysis Report" in content
        assert "# Total PRs Analyzed: 25" in content
        assert "# Overload Threshold: 15 requests" in content
        assert "# Team Analysis Enabled: True" in content
        assert "# Organization: testorg" in content
        assert "# Total Reviewers: 3" in content
        assert "# Total Review Requests: 40" in content
        
        # Check for CSV headers
        assert "reviewer_login,reviewer_name,reviewer_type" in content
        assert "total_requests,pr_numbers,request_sources" in content
        assert "workload_status,workload_category" in content
        
        # Check for data rows
        assert "alice,Alice Johnson,user,20" in content
        assert "bob,Bob Smith,user,8" in content
        assert "team:frontend,Team: Frontend,team,12" in content
    
    def test_reviewer_csv_headers(self):
        """Test reviewer CSV header structure."""
        reporter = CSVReporter(self.output_file)
        
        headers = reporter._format_reviewer_csv_headers()
        
        expected_headers = [
            'reviewer_login', 'reviewer_name', 'reviewer_type',
            'total_requests', 'pr_numbers', 'request_sources',
            'first_request_date', 'last_request_date', 'avg_requests_per_month',
            'percentage_of_total', 'workload_status', 'workload_category'
        ]
        
        assert headers == expected_headers
    
    def test_reviewer_csv_row_formatting(self):
        """Test reviewer CSV data row formatting."""
        reporter = CSVReporter(self.output_file)
        
        overload_analysis = self.mock_reviewer_summary['overload_analysis']
        reviewer_data = self.mock_reviewer_summary['reviewer_data']
        
        rows = reporter._format_reviewer_csv_rows(reviewer_data, overload_analysis)
        
        # Should have 3 rows
        assert len(rows) == 3
        
        # Rows should be sorted by total requests (descending)
        assert rows[0][0] == 'alice'  # 20 requests
        assert rows[1][0] == 'team:frontend'  # 12 requests  
        assert rows[2][0] == 'bob'  # 8 requests
        
        # Check Alice's data (overloaded user)
        alice_row = rows[0]
        assert alice_row[0] == 'alice'  # login
        assert alice_row[1] == 'Alice Johnson'  # name
        assert alice_row[2] == 'user'  # type
        assert alice_row[3] == '20'  # total_requests
        assert '100, 101, 102, 103, 104' in alice_row[4]  # pr_numbers
        assert alice_row[10] == 'OVERLOADED'  # workload_status
        assert alice_row[11] == 'Overloaded'  # workload_category
    
    def test_validate_reviewer_summary_success(self):
        """Test successful reviewer summary validation."""
        reporter = CSVReporter(self.output_file)
        
        # Should not raise any exception
        result = reporter.validate_reviewer_summary(self.mock_reviewer_summary)
        assert result is True
    
    def test_validate_reviewer_summary_invalid_structure(self):
        """Test reviewer summary validation with invalid structures."""
        reporter = CSVReporter(self.output_file)
        
        # Invalid: not a dictionary
        with pytest.raises(CSVReportError, match="must be a dictionary"):
            reporter.validate_reviewer_summary("invalid")
        
        # Invalid: missing required keys
        invalid_summary = {'reviewer_data': {}}
        with pytest.raises(CSVReportError, match="must contain 'metadata' key"):
            reporter.validate_reviewer_summary(invalid_summary)
    
    def test_generate_reviewer_report_empty_data(self):
        """Test reviewer report generation with empty data."""
        reporter = CSVReporter(self.output_file)
        
        empty_summary = {
            'reviewer_data': {},
            'metadata': {},
            'statistics': {},
            'overload_analysis': {'OVERLOADED': [], 'HIGH': [], 'NORMAL': []},
            'distribution_analysis': {}
        }
        
        output_path = reporter.generate_reviewer_report(empty_summary)
        
        assert output_path == str(self.output_file)
        assert self.output_file.exists()
        
        # Read and verify content
        with open(self.output_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should have headers but no data rows
        assert "reviewer_login,reviewer_name,reviewer_type" in content
        lines = content.strip().split('\n')
        
        # Count non-comment lines (should be just the header line)
        non_comment_lines = [line for line in lines if not line.startswith('#') and line.strip()]
        assert len(non_comment_lines) == 1  # Just the header


if __name__ == "__main__":
    pytest.main([__file__])
