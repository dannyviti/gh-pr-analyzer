"""
Unit tests for PR analyzer module.

This module contains comprehensive tests for the PRAnalyzer class,
including data collection, filtering, and analysis scenarios.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from pr_analyzer import PRAnalyzer, PRAnalysisError
from github_client import GitHubClient, GitHubAPIError


class TestPRAnalyzer:
    """Test cases for PRAnalyzer class initialization."""
    
    def test_init_with_valid_github_client(self):
        """Test PRAnalyzer initialization with valid GitHubClient."""
        mock_client = Mock(spec=GitHubClient)
        analyzer = PRAnalyzer(mock_client)
        
        assert analyzer.github_client == mock_client
        assert analyzer.logger is not None
    
    def test_init_with_none_client(self):
        """Test PRAnalyzer initialization with None client raises error."""
        with pytest.raises(PRAnalysisError, match="GitHubClient is required"):
            PRAnalyzer(None)
    
    def test_init_with_invalid_client(self):
        """Test PRAnalyzer initialization with invalid client type raises error."""
        invalid_client = "not_a_client"
        with pytest.raises(PRAnalysisError, match="Invalid GitHubClient instance provided"):
            PRAnalyzer(invalid_client)


class TestMonthlyPRFetching:
    """Test cases for monthly PR data collection."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_fetch_monthly_prs_success(self):
        """Test successful monthly PR fetching."""
        # Mock data
        mock_prs = [
            {'number': 1, 'created_at': '2024-12-01T10:00:00Z', 'state': 'closed'},
            {'number': 2, 'created_at': '2024-12-02T15:30:00Z', 'state': 'open'}
        ]
        
        # Configure mocks
        mock_since_date = datetime(2024, 11, 20)
        self.mock_client._calculate_date_range.return_value = mock_since_date
        self.mock_client.get_pull_requests.return_value = mock_prs
        
        # Test the method
        result = self.analyzer.fetch_monthly_prs("testowner", "test-repo")
        
        # Verify calls and results
        self.mock_client._calculate_date_range.assert_called_once_with(1)
        self.mock_client.get_pull_requests.assert_called_once_with("testowner", "test-repo", mock_since_date)
        assert len(result) == 2
        assert result[0]['number'] == 1
        assert result[1]['number'] == 2
    
    def test_fetch_monthly_prs_custom_months(self):
        """Test monthly PR fetching with custom months back."""
        mock_prs = []
        mock_since_date = datetime(2024, 9, 20)
        
        self.mock_client._calculate_date_range.return_value = mock_since_date
        self.mock_client.get_pull_requests.return_value = mock_prs
        
        result = self.analyzer.fetch_monthly_prs("testowner", "test-repo", months_back=3)
        
        self.mock_client._calculate_date_range.assert_called_once_with(3)
        assert result == []
    
    def test_fetch_monthly_prs_invalid_params(self):
        """Test monthly PR fetching with invalid parameters."""
        # Test empty owner
        with pytest.raises(PRAnalysisError, match="Repository owner and name are required"):
            self.analyzer.fetch_monthly_prs("", "test-repo")
        
        # Test empty repo
        with pytest.raises(PRAnalysisError, match="Repository owner and name are required"):
            self.analyzer.fetch_monthly_prs("testowner", "")
        
        # Test invalid months_back
        with pytest.raises(PRAnalysisError, match="months_back must be at least 1"):
            self.analyzer.fetch_monthly_prs("testowner", "test-repo", months_back=0)
    
    def test_fetch_monthly_prs_github_api_error(self):
        """Test monthly PR fetching when GitHub API fails."""
        mock_since_date = datetime(2024, 11, 20)
        self.mock_client._calculate_date_range.return_value = mock_since_date
        self.mock_client.get_pull_requests.side_effect = GitHubAPIError("API failed")
        
        # Should re-raise GitHubAPIError without wrapping
        with pytest.raises(GitHubAPIError, match="API failed"):
            self.analyzer.fetch_monthly_prs("testowner", "test-repo")
    
    def test_fetch_monthly_prs_unexpected_error(self):
        """Test monthly PR fetching with unexpected errors."""
        self.mock_client._calculate_date_range.side_effect = Exception("Unexpected error")
        
        with pytest.raises(PRAnalysisError, match="Failed to fetch monthly PRs"):
            self.analyzer.fetch_monthly_prs("testowner", "test-repo")


class TestPRDataFiltering:
    """Test cases for PR data filtering operations."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_monthly_pr_filtering_with_valid_dates(self):
        """Test date-based PR filtering with valid date formats."""
        since_date = datetime(2024, 11, 15)
        mock_prs = [
            {'number': 1, 'created_at': '2024-12-01T10:00:00Z'},  # Should be included
            {'number': 2, 'created_at': '2024-11-20T15:30:00Z'},  # Should be included
            {'number': 3, 'created_at': '2024-11-10T08:00:00Z'},  # Should be filtered out
            {'number': 4, 'created_at': '2024-11-15T12:00:00Z'},  # Should be included (exact date)
        ]
        
        result = self.analyzer._filter_prs_by_date(mock_prs, since_date)
        
        # Should include PRs 1, 2, and 4 (created on or after since_date)
        assert len(result) == 3
        included_numbers = [pr['number'] for pr in result]
        assert 1 in included_numbers
        assert 2 in included_numbers
        assert 4 in included_numbers
        assert 3 not in included_numbers
    
    def test_monthly_pr_filtering_with_timezone_formats(self):
        """Test PR filtering with different timezone formats."""
        since_date = datetime(2024, 11, 15)
        mock_prs = [
            {'number': 1, 'created_at': '2024-12-01T10:00:00Z'},           # UTC format
            {'number': 2, 'created_at': '2024-11-20T15:30:00+00:00'},     # Explicit timezone
            {'number': 3, 'created_at': '2024-11-10T08:00:00-05:00'},     # Different timezone
        ]
        
        result = self.analyzer._filter_prs_by_date(mock_prs, since_date)
        
        # Should include PRs 1 and 2, exclude PR 3
        assert len(result) == 2
        included_numbers = [pr['number'] for pr in result]
        assert 1 in included_numbers
        assert 2 in included_numbers
    
    def test_monthly_pr_filtering_empty_list(self):
        """Test PR filtering with empty PR list."""
        result = self.analyzer._filter_prs_by_date([], datetime(2024, 11, 15))
        assert result == []
    
    def test_monthly_pr_filtering_missing_created_at(self):
        """Test PR filtering with missing created_at fields."""
        since_date = datetime(2024, 11, 15)
        mock_prs = [
            {'number': 1, 'created_at': '2024-12-01T10:00:00Z'},  # Valid
            {'number': 2, 'state': 'open'},                       # Missing created_at
            {'number': 3, 'created_at': None},                    # None created_at
            {'number': 4, 'created_at': '2024-11-20T15:30:00Z'},  # Valid
        ]
        
        result = self.analyzer._filter_prs_by_date(mock_prs, since_date)
        
        # Should include only PRs with valid dates (1 and 4)
        assert len(result) == 2
        included_numbers = [pr['number'] for pr in result]
        assert 1 in included_numbers
        assert 4 in included_numbers
    
    def test_monthly_pr_filtering_invalid_date_format(self):
        """Test PR filtering with invalid date formats."""
        since_date = datetime(2024, 11, 15)
        mock_prs = [
            {'number': 1, 'created_at': '2024-12-01T10:00:00Z'},  # Valid
            {'number': 2, 'created_at': 'invalid-date-format'},   # Invalid format
            {'number': 3, 'created_at': '2024-11-20T15:30:00Z'},  # Valid
        ]
        
        result = self.analyzer._filter_prs_by_date(mock_prs, since_date)
        
        # Should include only PRs with valid dates (1 and 3)
        assert len(result) == 2
        included_numbers = [pr['number'] for pr in result]
        assert 1 in included_numbers
        assert 3 in included_numbers
    
    def test_monthly_pr_filtering_exception_handling(self):
        """Test PR filtering exception handling."""
        # Pass invalid prs parameter to trigger exception
        with pytest.raises(PRAnalysisError, match="Failed to filter PRs by date"):
            # This should cause an exception in the filtering logic
            self.analyzer._filter_prs_by_date("not_a_list", datetime(2024, 11, 15))


class TestPRDataCollection:
    """Test cases for comprehensive PR data collection scenarios."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_pr_data_collection_flow(self):
        """Test complete PR data collection workflow with mocked components."""
        # Mock raw PR data from GitHub API
        raw_prs = [
            {'number': 1, 'created_at': '2024-12-01T10:00:00Z', 'state': 'closed', 'merged_at': '2024-12-02T15:00:00Z'},
            {'number': 2, 'created_at': '2024-11-25T08:30:00Z', 'state': 'open', 'merged_at': None},
            {'number': 3, 'created_at': '2024-11-05T12:00:00Z', 'state': 'closed', 'merged_at': None},  # Too old
        ]
        
        # Configure mock client
        since_date = datetime(2024, 11, 15)
        self.mock_client._calculate_date_range.return_value = since_date
        self.mock_client.get_pull_requests.return_value = raw_prs
        
        # Execute the data collection
        result = self.analyzer.fetch_monthly_prs("testowner", "test-repo")
        
        # Verify the workflow
        self.mock_client._calculate_date_range.assert_called_once_with(1)
        self.mock_client.get_pull_requests.assert_called_once_with("testowner", "test-repo", since_date)
        
        # Should include PRs 1 and 2 (created after since_date), exclude PR 3
        assert len(result) == 2
        included_numbers = [pr['number'] for pr in result]
        assert 1 in included_numbers
        assert 2 in included_numbers
        assert 3 not in included_numbers
    
    def test_pr_data_collection_with_filtering(self):
        """Test PR data collection with additional filtering applied."""
        # Create test data with PRs spanning multiple months
        raw_prs = [
            {'number': 10, 'created_at': '2024-12-15T10:00:00Z', 'state': 'open'},
            {'number': 11, 'created_at': '2024-12-01T14:00:00Z', 'state': 'closed'},
            {'number': 12, 'created_at': '2024-11-28T09:00:00Z', 'state': 'open'},
            {'number': 13, 'created_at': '2024-11-20T16:30:00Z', 'state': 'closed'},
        ]
        
        since_date = datetime(2024, 11, 25)
        self.mock_client._calculate_date_range.return_value = since_date
        self.mock_client.get_pull_requests.return_value = raw_prs
        
        result = self.analyzer.fetch_monthly_prs("testowner", "test-repo", months_back=2)
        
        # Verify configuration
        self.mock_client._calculate_date_range.assert_called_once_with(2)
        
        # Should include PRs 10, 11, and 12 (created on or after since_date)
        assert len(result) == 3
        included_numbers = [pr['number'] for pr in result]
        assert 10 in included_numbers
        assert 11 in included_numbers
        assert 12 in included_numbers
        assert 13 not in included_numbers


class TestPRSummaryStats:
    """Test cases for PR summary statistics generation."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_get_pr_summary_stats_empty_list(self):
        """Test summary stats generation with empty PR list."""
        result = self.analyzer.get_pr_summary_stats([])
        
        expected = {
            'total_prs': 0,
            'open_prs': 0,
            'closed_prs': 0,
            'merged_prs': 0,
            'draft_prs': 0
        }
        
        assert result == expected
    
    def test_get_pr_summary_stats_with_data(self):
        """Test summary stats generation with PR data."""
        mock_prs = [
            {'number': 1, 'state': 'open', 'merged_at': None, 'draft': False, 'created_at': '2024-12-01T10:00:00Z'},
            {'number': 2, 'state': 'closed', 'merged_at': '2024-12-02T15:00:00Z', 'draft': False, 'created_at': '2024-11-25T08:00:00Z'},
            {'number': 3, 'state': 'closed', 'merged_at': None, 'draft': False, 'created_at': '2024-11-28T12:00:00Z'},
            {'number': 4, 'state': 'open', 'merged_at': None, 'draft': True, 'created_at': '2024-11-30T14:00:00Z'},
        ]
        
        result = self.analyzer.get_pr_summary_stats(mock_prs)
        
        assert result['total_prs'] == 4
        assert result['open_prs'] == 2
        assert result['closed_prs'] == 2
        assert result['merged_prs'] == 1
        assert result['draft_prs'] == 1
        assert result['earliest_pr'] == 2  # PR #2 created on 11-25
        assert result['latest_pr'] == 1    # PR #1 created on 12-01
    
    def test_get_pr_summary_stats_date_handling(self):
        """Test summary stats date range calculations."""
        mock_prs = [
            {'number': 5, 'state': 'open', 'created_at': '2024-12-15T10:00:00Z'},
            {'number': 6, 'state': 'closed', 'created_at': '2024-11-10T08:00:00Z'},
        ]
        
        result = self.analyzer.get_pr_summary_stats(mock_prs)
        
        assert 'date_range_start' in result
        assert 'date_range_end' in result
        assert result['date_range_start'] == '2024-11-10T08:00:00'
        assert result['date_range_end'] == '2024-12-15T10:00:00'


class TestPRLifecycleAnalysis:
    """Test cases for PR lifecycle timing analysis."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_analyze_pr_lifecycle_times_empty_list(self):
        """Test lifecycle analysis with empty PR list."""
        result = self.analyzer.analyze_pr_lifecycle_times([], "testowner", "test-repo")
        
        expected = {'summary': {'total_prs_analyzed': 0}, 'pr_details': []}
        assert result == expected
    
    def test_analyze_pr_lifecycle_times_invalid_params(self):
        """Test lifecycle analysis with invalid parameters."""
        mock_prs = [{'number': 1}]
        
        # Test empty owner
        with pytest.raises(PRAnalysisError, match="Repository owner and name are required"):
            self.analyzer.analyze_pr_lifecycle_times(mock_prs, "", "test-repo")
        
        # Test empty repo
        with pytest.raises(PRAnalysisError, match="Repository owner and name are required"):
            self.analyzer.analyze_pr_lifecycle_times(mock_prs, "testowner", "")
    
    def test_analyze_pr_lifecycle_times_success(self):
        """Test successful PR lifecycle analysis."""
        mock_prs = [
            {
                'number': 123,
                'title': 'Test PR',
                'state': 'closed',
                'created_at': '2024-12-01T10:00:00Z'
            }
        ]
        
        # Mock GitHub client responses
        self.mock_client.get_pr_reviews.return_value = [
            {'id': 1, 'state': 'APPROVED', 'submitted_at': '2024-12-01T14:00:00Z'}
        ]
        self.mock_client.get_pr_review_comments.return_value = []
        self.mock_client.get_pr_timeline.return_value = []
        self.mock_client.get_pr_merge_info.return_value = {
            'merged_at': '2024-12-02T10:00:00Z',
            'merged_by': {'login': 'testuser'}
        }
        self.mock_client.get_pr_commits.return_value = [
            {
                'sha': 'abc123',
                'commit': {
                    'author': {'date': '2024-11-30T08:00:00Z'},
                    'committer': {'date': '2024-11-30T08:00:00Z'}
                }
            }
        ]
        
        result = self.analyzer.analyze_pr_lifecycle_times(mock_prs, "testowner", "test-repo")
        
        assert 'summary' in result
        assert 'pr_details' in result
        assert result['summary']['total_prs_analyzed'] == 1
        assert len(result['pr_details']) == 1
        
        pr_detail = result['pr_details'][0]
        assert pr_detail['pr_number'] == 123
        assert pr_detail['time_to_first_review_hours'] is not None
        assert pr_detail['time_to_merge_hours'] is not None
        assert pr_detail['commit_lead_time_hours'] is not None
        assert pr_detail['is_merged'] is True
        assert pr_detail['has_reviews'] is True


class TestReviewTimeCalculations:
    """Test cases for review timing calculations with mock data."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_review_time_calculations(self):
        """Test review time calculations with mock timing data."""
        pr = {'number': 123, 'created_at': '2024-12-01T10:00:00Z'}
        
        activities = [
            {'state': 'APPROVED', 'submitted_at': '2024-12-01T14:00:00Z'},  # 4 hours later
            {'created_at': '2024-12-01T16:00:00Z', 'diff_hunk': '@@ -1 +1 @@'}  # Review comment, 6 hours later
        ]
        
        result = self.analyzer._calculate_time_to_first_review(pr, activities)
        
        # Should return time to first review (4 hours)
        assert result == 4.0
    
    def test_review_time_with_timezone_formats(self):
        """Test review time calculation with different timezone formats."""
        pr = {'number': 123, 'created_at': '2024-12-01T10:00:00+00:00'}  # Explicit timezone
        
        activities = [
            {'state': 'CHANGES_REQUESTED', 'submitted_at': '2024-12-01T13:30:00Z'}  # Z format
        ]
        
        result = self.analyzer._calculate_time_to_first_review(pr, activities)
        
        # 3.5 hours difference
        assert result == 3.5
    
    def test_review_time_no_activities(self):
        """Test review time calculation with no review activities."""
        pr = {'number': 123, 'created_at': '2024-12-01T10:00:00Z'}
        activities = []
        
        result = self.analyzer._calculate_time_to_first_review(pr, activities)
        
        assert result is None
    
    def test_review_time_missing_created_at(self):
        """Test review time calculation with missing PR created_at."""
        pr = {'number': 123}  # Missing created_at
        activities = [{'state': 'APPROVED', 'submitted_at': '2024-12-01T14:00:00Z'}]
        
        result = self.analyzer._calculate_time_to_first_review(pr, activities)
        
        assert result is None


class TestMergeTimeCalculations:
    """Test cases for merge timing calculations with mock data."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_merge_time_calculations(self):
        """Test merge time calculations with mock timing data."""
        pr = {'number': 123, 'created_at': '2024-12-01T10:00:00Z'}
        merge_info = {'merged_at': '2024-12-02T14:00:00Z', 'merged': True}
        
        result = self.analyzer._calculate_time_to_merge(pr, merge_info)
        
        # 28 hours between creation and merge
        assert result == 28.0
    
    def test_merge_time_unmerged_pr(self):
        """Test merge time calculation for unmerged PR."""
        pr = {'number': 123, 'created_at': '2024-12-01T10:00:00Z'}
        merge_info = None  # Not merged
        
        result = self.analyzer._calculate_time_to_merge(pr, merge_info)
        
        assert result is None
    
    def test_merge_time_missing_merge_info(self):
        """Test merge time calculation with missing merge timestamp."""
        pr = {'number': 123, 'created_at': '2024-12-01T10:00:00Z'}
        merge_info = {'merged': False, 'merged_at': None}
        
        result = self.analyzer._calculate_time_to_merge(pr, merge_info)
        
        assert result is None


class TestCommitLeadTimeCalculations:
    """Test cases for commit-to-merge lead time calculations."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_commit_lead_time_calculations(self):
        """Test commit lead time calculations with mock commit data."""
        pr = {'number': 123, 'created_at': '2024-12-01T10:00:00Z'}
        
        commits = [
            {
                'sha': 'abc123',
                'commit': {
                    'author': {'date': '2024-11-30T08:00:00Z'},  # First commit
                    'committer': {'date': '2024-11-30T08:00:00Z'}
                }
            },
            {
                'sha': 'def456',
                'commit': {
                    'author': {'date': '2024-12-01T12:00:00Z'},  # Later commit
                    'committer': {'date': '2024-12-01T12:00:00Z'}
                }
            }
        ]
        
        merge_info = {'merged_at': '2024-12-02T10:00:00Z'}
        
        result = self.analyzer._calculate_commit_lead_time(pr, commits, merge_info)
        
        # From first commit (Nov 30, 08:00) to merge (Dec 2, 10:00) = 50 hours
        assert result == 50.0
    
    def test_commit_lead_time_single_commit(self):
        """Test commit lead time with single commit."""
        pr = {'number': 123}
        
        commits = [
            {
                'sha': 'abc123',
                'commit': {
                    'author': {'date': '2024-12-01T08:00:00Z'},
                    'committer': {'date': '2024-12-01T08:00:00Z'}
                }
            }
        ]
        
        merge_info = {'merged_at': '2024-12-01T16:00:00Z'}
        
        result = self.analyzer._calculate_commit_lead_time(pr, commits, merge_info)
        
        # 8 hours from commit to merge
        assert result == 8.0
    
    def test_commit_lead_time_no_commits(self):
        """Test commit lead time with no commits."""
        pr = {'number': 123}
        commits = []
        merge_info = {'merged_at': '2024-12-01T16:00:00Z'}
        
        result = self.analyzer._calculate_commit_lead_time(pr, commits, merge_info)
        
        assert result is None
    
    def test_commit_lead_time_unmerged(self):
        """Test commit lead time for unmerged PR."""
        pr = {'number': 123}
        commits = [{'sha': 'abc123', 'commit': {'author': {'date': '2024-12-01T08:00:00Z'}}}]
        merge_info = None
        
        result = self.analyzer._calculate_commit_lead_time(pr, commits, merge_info)
        
        assert result is None


class TestReviewActivityDetection:
    """Test cases for detecting and parsing review activities."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_multiple_review_activities(self):
        """Test detection of various review activity types."""
        activities = [
            {'state': 'APPROVED', 'submitted_at': '2024-12-01T15:00:00Z'},
            {'created_at': '2024-12-01T12:00:00Z', 'diff_hunk': '@@ -1 +1 @@'},  # Earlier comment
            {'event': 'reviewed', 'created_at': '2024-12-01T16:00:00Z'},
            {'event': 'commented', 'created_at': '2024-12-01T14:00:00Z'}
        ]
        
        result = self.analyzer._get_first_review_activity(activities)
        
        # Should return the earliest review activity (comment at 12:00)
        assert result is not None
        assert result['created_at'] == '2024-12-01T12:00:00Z'
        assert 'diff_hunk' in result
    
    def test_review_activity_with_review_id(self):
        """Test detection of review comments with review_id."""
        activities = [
            {'review_id': 123, 'created_at': '2024-12-01T10:30:00Z', 'body': 'Good work'},
            {'state': 'APPROVED', 'submitted_at': '2024-12-01T11:00:00Z'}
        ]
        
        result = self.analyzer._get_first_review_activity(activities)
        
        # Should return the earlier review comment
        assert result['review_id'] == 123
        assert result['created_at'] == '2024-12-01T10:30:00Z'
    
    def test_no_review_activities(self):
        """Test when no review activities are found."""
        activities = [
            {'event': 'opened', 'created_at': '2024-12-01T10:00:00Z'},
            {'event': 'closed', 'created_at': '2024-12-01T16:00:00Z'}
        ]
        
        result = self.analyzer._get_first_review_activity(activities)
        
        assert result is None


class TestCommitTimestampDetection:
    """Test cases for commit timestamp parsing and detection."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_single_commit_prs(self):
        """Test commit timestamp detection for single commits."""
        commits = [
            {
                'sha': 'abc123',
                'commit': {
                    'author': {'date': '2024-12-01T08:00:00Z'},
                    'committer': {'date': '2024-12-01T08:05:00Z'}
                }
            }
        ]
        
        result = self.analyzer._get_first_commit_timestamp(commits)
        
        # Should prefer author date over committer date
        expected = datetime(2024, 12, 1, 8, 0, 0)
        assert result == expected
    
    def test_multiple_commit_prs(self):
        """Test commit timestamp detection for multiple commits."""
        commits = [
            {
                'sha': 'def456',
                'commit': {
                    'author': {'date': '2024-12-01T12:00:00Z'},  # Later commit
                    'committer': {'date': '2024-12-01T12:00:00Z'}
                }
            },
            {
                'sha': 'abc123',
                'commit': {
                    'author': {'date': '2024-11-30T08:00:00Z'},  # Earlier commit
                    'committer': {'date': '2024-11-30T08:00:00Z'}
                }
            }
        ]
        
        result = self.analyzer._get_first_commit_timestamp(commits)
        
        # Should return the earliest commit timestamp
        expected = datetime(2024, 11, 30, 8, 0, 0)
        assert result == expected
    
    def test_commits_missing_author_date(self):
        """Test commit parsing when author date is missing."""
        commits = [
            {
                'sha': 'abc123',
                'commit': {
                    'committer': {'date': '2024-12-01T08:00:00Z'}  # Only committer date
                    # Missing author date
                }
            }
        ]
        
        result = self.analyzer._get_first_commit_timestamp(commits)
        
        # Should use committer date as fallback
        expected = datetime(2024, 12, 1, 8, 0, 0)
        assert result == expected
    
    def test_commits_invalid_dates(self):
        """Test commit parsing with invalid date formats."""
        commits = [
            {
                'sha': 'abc123',
                'commit': {
                    'author': {'date': 'invalid-date-format'},
                    'committer': {'date': '2024-12-01T08:00:00Z'}
                }
            }
        ]
        
        result = self.analyzer._get_first_commit_timestamp(commits)
        
        # Should use valid committer date
        expected = datetime(2024, 12, 1, 8, 0, 0)
        assert result == expected


class TestEdgeCaseHandling:
    """Test cases for edge cases in PR analysis."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
    
    def test_unreviewed_pr_handling(self):
        """Test analysis of PRs with no review activity."""
        mock_prs = [{'number': 123, 'created_at': '2024-12-01T10:00:00Z', 'state': 'open'}]
        
        # Mock empty responses
        self.mock_client.get_pr_reviews.return_value = []
        self.mock_client.get_pr_review_comments.return_value = []
        self.mock_client.get_pr_timeline.return_value = []
        self.mock_client.get_pr_merge_info.return_value = None
        self.mock_client.get_pr_commits.return_value = []
        
        result = self.analyzer.analyze_pr_lifecycle_times(mock_prs, "testowner", "test-repo")
        
        pr_detail = result['pr_details'][0]
        assert pr_detail['time_to_first_review_hours'] is None
        assert pr_detail['has_reviews'] is False
        assert pr_detail['is_merged'] is False
    
    def test_unmerged_pr_handling(self):
        """Test analysis of PRs that are not yet merged."""
        mock_prs = [{'number': 123, 'created_at': '2024-12-01T10:00:00Z', 'state': 'open'}]
        
        # Mock PR with reviews but no merge
        self.mock_client.get_pr_reviews.return_value = [
            {'state': 'APPROVED', 'submitted_at': '2024-12-01T14:00:00Z'}
        ]
        self.mock_client.get_pr_review_comments.return_value = []
        self.mock_client.get_pr_timeline.return_value = []
        self.mock_client.get_pr_merge_info.return_value = None  # Not merged
        self.mock_client.get_pr_commits.return_value = [
            {'sha': 'abc123', 'commit': {'author': {'date': '2024-12-01T08:00:00Z'}}}
        ]
        
        result = self.analyzer.analyze_pr_lifecycle_times(mock_prs, "testowner", "test-repo")
        
        pr_detail = result['pr_details'][0]
        assert pr_detail['time_to_first_review_hours'] is not None
        assert pr_detail['time_to_merge_hours'] is None
        assert pr_detail['commit_lead_time_hours'] is None
        assert pr_detail['has_reviews'] is True
        assert pr_detail['is_merged'] is False
    
    def test_merged_without_review(self):
        """Test analysis of PRs that were merged without formal review."""
        mock_prs = [{'number': 123, 'created_at': '2024-12-01T10:00:00Z', 'state': 'closed'}]
        
        # Mock PR with merge but no reviews
        self.mock_client.get_pr_reviews.return_value = []
        self.mock_client.get_pr_review_comments.return_value = []
        self.mock_client.get_pr_timeline.return_value = []
        self.mock_client.get_pr_merge_info.return_value = {
            'merged_at': '2024-12-02T10:00:00Z'
        }
        self.mock_client.get_pr_commits.return_value = [
            {'sha': 'abc123', 'commit': {'author': {'date': '2024-12-01T08:00:00Z'}}}
        ]
        
        result = self.analyzer.analyze_pr_lifecycle_times(mock_prs, "testowner", "test-repo")
        
        pr_detail = result['pr_details'][0]
        assert pr_detail['time_to_first_review_hours'] is None
        assert pr_detail['time_to_merge_hours'] is not None
        assert pr_detail['commit_lead_time_hours'] is not None
        assert pr_detail['has_reviews'] is False
        assert pr_detail['is_merged'] is True


# Test fixtures
@pytest.fixture
def mock_github_client():
    """Fixture providing a mock GitHubClient."""
    return Mock(spec=GitHubClient)


@pytest.fixture
def pr_analyzer(mock_github_client):
    """Fixture providing a PRAnalyzer instance with mock client."""
    return PRAnalyzer(mock_github_client)


class TestPRCreatorDataExtraction:
    """Test cases for PR creator data extraction functionality."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
        
        # Setup mock responses for github client methods
        self.mock_client.get_pr_reviews.return_value = []
        self.mock_client.get_pr_review_comments.return_value = []
        self.mock_client.get_pr_timeline.return_value = []
        self.mock_client.get_pr_merge_info.return_value = None
        self.mock_client.get_pr_commits.return_value = []

    def test_pr_analysis_extracts_creator_data(self):
        """Test that PR analysis extracts creator GitHub ID and login from API response."""
        mock_prs = [
            {
                'number': 123,
                'title': 'Test PR',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z',
                'user': {
                    'id': 12345,
                    'login': 'testuser'
                }
            }
        ]
        
        result = self.analyzer.analyze_pr_lifecycle_times(mock_prs, "testowner", "test-repo")
        
        assert len(result['pr_details']) == 1
        pr_detail = result['pr_details'][0]
        
        # Verify creator data extraction
        assert pr_detail['pr_creator_github_id'] == '12345'
        assert pr_detail['pr_creator_login'] == 'testuser'
        assert pr_detail['repository_name'] == 'testowner/test-repo'

    def test_pr_analysis_handles_missing_creator(self):
        """Test behavior when PR user data is missing or null."""
        mock_prs = [
            {
                'number': 123,
                'title': 'Test PR',
                'state': 'open', 
                'created_at': '2024-12-01T10:00:00Z',
                'user': None  # Missing user data
            }
        ]
        
        result = self.analyzer.analyze_pr_lifecycle_times(mock_prs, "testowner", "test-repo")
        
        assert len(result['pr_details']) == 1
        pr_detail = result['pr_details'][0]
        
        # Should handle gracefully with empty strings
        assert pr_detail['pr_creator_github_id'] == ''
        assert pr_detail['pr_creator_login'] == ''
        assert pr_detail['repository_name'] == 'testowner/test-repo'

    def test_analysis_results_include_repository_name(self):
        """Test that repository name is included in both summary and PR details."""
        mock_prs = [
            {
                'number': 100,
                'title': 'First PR',
                'state': 'closed',
                'created_at': '2024-12-01T09:00:00Z',
                'user': {'id': 11111, 'login': 'user1'}
            },
            {
                'number': 101,
                'title': 'Second PR',
                'state': 'open',
                'created_at': '2024-12-01T11:00:00Z',
                'user': {'id': 22222, 'login': 'user2'}
            }
        ]
        
        result = self.analyzer.analyze_pr_lifecycle_times(mock_prs, "facebook", "react")
        
        # Verify repository name in summary
        assert result['summary']['repository_name'] == 'facebook/react'
        
        # Verify repository name in all PR details
        for pr_detail in result['pr_details']:
            assert pr_detail['repository_name'] == 'facebook/react'

    def test_pr_analysis_with_various_user_formats(self):
        """Test different user object structures from GitHub API."""
        mock_prs = [
            # Complete user data
            {
                'number': 1,
                'title': 'Complete user data',
                'state': 'closed',
                'created_at': '2024-12-01T08:00:00Z',
                'user': {'id': 12345, 'login': 'completeuser'}
            },
            # Missing login field
            {
                'number': 2,
                'title': 'Missing login',
                'state': 'open',
                'created_at': '2024-12-01T09:00:00Z',
                'user': {'id': 67890}  # No login field
            },
            # Missing id field
            {
                'number': 3,
                'title': 'Missing ID',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z',
                'user': {'login': 'noiduser'}  # No id field
            },
            # Empty user object
            {
                'number': 4,
                'title': 'Empty user object',
                'state': 'open',
                'created_at': '2024-12-01T11:00:00Z',
                'user': {}
            },
            # No user field at all
            {
                'number': 5,
                'title': 'No user field',
                'state': 'open',
                'created_at': '2024-12-01T12:00:00Z'
                # No 'user' field
            }
        ]
        
        result = self.analyzer.analyze_pr_lifecycle_times(mock_prs, "test", "repo")
        
        assert len(result['pr_details']) == 5
        pr_details = result['pr_details']
        
        # Complete data should work
        assert pr_details[0]['pr_creator_github_id'] == '12345'
        assert pr_details[0]['pr_creator_login'] == 'completeuser'
        
        # Missing login should have empty login but valid ID
        assert pr_details[1]['pr_creator_github_id'] == '67890'
        assert pr_details[1]['pr_creator_login'] == ''
        
        # Missing ID should have empty ID but valid login
        assert pr_details[2]['pr_creator_github_id'] == ''
        assert pr_details[2]['pr_creator_login'] == 'noiduser'
        
        # Empty user object should have empty values
        assert pr_details[3]['pr_creator_github_id'] == ''
        assert pr_details[3]['pr_creator_login'] == ''
        
        # Missing user field should have empty values
        assert pr_details[4]['pr_creator_github_id'] == ''
        assert pr_details[4]['pr_creator_login'] == ''


class TestErrorHandlingAndEdgeCases:
    """Test cases for error handling and edge cases in PR analysis."""
    
    def setup_method(self):
        """Set up test analyzer for each test method."""
        self.mock_client = Mock(spec=GitHubClient)
        self.analyzer = PRAnalyzer(self.mock_client)
        
        # Setup default mock responses
        self.mock_client.get_pr_reviews.return_value = []
        self.mock_client.get_pr_review_comments.return_value = []
        self.mock_client.get_pr_timeline.return_value = []
        self.mock_client.get_pr_merge_info.return_value = None
        self.mock_client.get_pr_commits.return_value = []

    def test_missing_pr_creator_data_handling(self):
        """Test behavior when PR creator data is missing or malformed."""
        malformed_prs = [
            # PR with completely missing user field
            {
                'number': 1,
                'title': 'No user field',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z'
                # No 'user' field at all
            },
            # PR with null user
            {
                'number': 2,
                'title': 'Null user',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z',
                'user': None
            },
            # PR with non-dict user
            {
                'number': 3,
                'title': 'String user',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z',
                'user': "invalid_user_data"
            },
            # PR with invalid GitHub ID
            {
                'number': 4,
                'title': 'Invalid GitHub ID',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z',
                'user': {'id': 'not_a_number', 'login': 'testuser'}
            },
            # PR with negative GitHub ID
            {
                'number': 5,
                'title': 'Negative GitHub ID',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z',
                'user': {'id': -123, 'login': 'testuser'}
            }
        ]
        
        result = self.analyzer.analyze_pr_lifecycle_times(malformed_prs, "test", "repo")
        
        assert len(result['pr_details']) == 5
        
        # All PRs should have empty creator data due to various issues
        for pr_detail in result['pr_details']:
            assert pr_detail['pr_creator_github_id'] == ''
            # Some may have login, some may not
            assert pr_detail['repository_name'] == 'test/repo'

    def test_api_response_edge_cases(self):
        """Test handling of incomplete or malformed API responses."""
        # PR with minimal valid data
        minimal_pr = {
            'number': 123,
            'title': 'Minimal PR',
            'state': 'open',
            'created_at': '2024-12-01T10:00:00Z',
            'user': {'id': 456, 'login': 'testuser'}
        }
        
        # Simulate API failures for different endpoints
        self.mock_client.get_pr_reviews.side_effect = Exception("Reviews API failed")
        self.mock_client.get_pr_review_comments.side_effect = Exception("Comments API failed")
        self.mock_client.get_pr_timeline.side_effect = Exception("Timeline API failed")
        self.mock_client.get_pr_merge_info.side_effect = Exception("Merge info API failed")
        self.mock_client.get_pr_commits.side_effect = Exception("Commits API failed")
        
        result = self.analyzer.analyze_pr_lifecycle_times([minimal_pr], "test", "repo")
        
        # Should still process the PR despite API failures
        assert len(result['pr_details']) == 1
        pr_detail = result['pr_details'][0]
        
        # Basic PR data should be preserved
        assert pr_detail['pr_number'] == 123
        assert pr_detail['title'] == 'Minimal PR'
        assert pr_detail['pr_creator_github_id'] == '456'
        assert pr_detail['pr_creator_login'] == 'testuser'
        assert pr_detail['repository_name'] == 'test/repo'
        
        # Counts should be zero due to API failures
        assert pr_detail['review_count'] == 0
        assert pr_detail['comment_count'] == 0
        assert pr_detail['commit_count'] == 0

    def test_error_recovery_maintains_pipeline(self):
        """Test that pipeline continues processing other PRs when individual PR data is problematic."""
        mixed_prs = [
            # Valid PR
            {
                'number': 1,
                'title': 'Valid PR',
                'state': 'closed',
                'created_at': '2024-12-01T08:00:00Z',
                'user': {'id': 111, 'login': 'user1'}
            },
            # Invalid PR (not a dict)
            "this_is_not_a_dict",
            # PR missing number
            {
                'title': 'No number',
                'state': 'open',
                'created_at': '2024-12-01T09:00:00Z',
                'user': {'id': 222, 'login': 'user2'}
            },
            # Valid PR again
            {
                'number': 4,
                'title': 'Another valid PR',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z',
                'user': {'id': 444, 'login': 'user4'}
            },
            # PR with missing required fields
            {
                'number': 5,
                'state': 'open',
                # Missing title and created_at
                'user': {'id': 555, 'login': 'user5'}
            }
        ]
        
        result = self.analyzer.analyze_pr_lifecycle_times(mixed_prs, "test", "repo")
        
        # Should process the valid PRs (PR #1, #4, and #5 with defaults)
        assert len(result['pr_details']) == 3
        
        # Verify the valid PRs were processed correctly
        pr_numbers = [pr['pr_number'] for pr in result['pr_details']]
        assert 1 in pr_numbers
        assert 4 in pr_numbers
        assert 5 in pr_numbers
        
        # Check that PR #5 got default values for missing fields
        pr5 = next(pr for pr in result['pr_details'] if pr['pr_number'] == 5)
        assert pr5['title'] == 'Unknown Title'  # Default value

    def test_repository_name_validation_edge_cases(self):
        """Test repository name validation with various edge cases."""
        valid_pr = {
            'number': 123,
            'title': 'Test PR',
            'state': 'open',
            'created_at': '2024-12-01T10:00:00Z',
            'user': {'id': 456, 'login': 'testuser'}
        }
        
        # Test with invalid owner/repo combinations - should raise PRAnalysisError
        edge_cases = [
            ('', 'repo'),  # Empty owner
            ('owner', ''),  # Empty repo
            ('', ''),       # Both empty
        ]
        
        for owner, repo in edge_cases:
            with pytest.raises(PRAnalysisError, match="Repository owner and name are required"):
                self.analyzer.analyze_pr_lifecycle_times([valid_pr], owner, repo)

    def test_error_logging_for_missing_fields(self, caplog):
        """Test that appropriate logging occurs when data is missing."""
        import logging
        
        # Set log level to capture warnings
        caplog.set_level(logging.WARNING)
        
        problematic_prs = [
            # PR with missing user data
            {
                'number': 1,
                'title': 'No user',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z'
            },
            # PR with empty user object
            {
                'number': 2,
                'title': 'Empty user',
                'state': 'open',
                'created_at': '2024-12-01T10:00:00Z',
                'user': {}
            }
        ]
        
        result = self.analyzer.analyze_pr_lifecycle_times(problematic_prs, "test", "repo")
        
        # Check that appropriate warning logs were generated
        log_messages = ' '.join([record.message for record in caplog.records])
        assert 'missing user data' in log_messages or 'empty user data' in log_messages

    def test_csv_generation_with_incomplete_data(self):
        """Test that CSV can be generated even with incomplete PR data."""
        from csv_reporter import CSVReporter
        import tempfile
        from pathlib import Path
        
        # Create analysis results with incomplete data
        incomplete_results = {
            'summary': {
                'repository_name': 'test/repo',
                'total_prs_analyzed': 2,
                'merged_prs': 1,
                'reviewed_prs': 1
            },
            'pr_details': [
                {
                    'pr_number': 1,
                    'title': 'Complete PR',
                    'state': 'closed',
                    'created_at': '2024-12-01T08:00:00Z',
                    'merged_at': '2024-12-01T16:00:00Z',
                    'repository_name': 'test/repo',
                    'pr_creator_github_id': '123',
                    'pr_creator_login': 'user1',
                    'time_to_first_review_hours': 2.0,
                    'time_to_merge_hours': 8.0,
                    'commit_lead_time_hours': 7.5,
                    'has_reviews': True,
                    'review_count': 1,
                    'comment_count': 2,
                    'commit_count': 3,
                    'is_merged': True
                },
                {
                    'pr_number': 2,
                    'title': 'Incomplete PR',
                    'state': 'open',
                    'created_at': '2024-12-01T12:00:00Z',
                    'merged_at': None,
                    'repository_name': 'test/repo',
                    'pr_creator_github_id': '',  # Missing creator data
                    'pr_creator_login': '',      # Missing creator data
                    'time_to_first_review_hours': None,  # Missing timing data
                    'time_to_merge_hours': None,
                    'commit_lead_time_hours': None,
                    'has_reviews': False,
                    'review_count': 0,
                    'comment_count': 0,
                    'commit_count': 0,
                    'is_merged': False
                }
            ]
        }
        
        # Generate CSV with incomplete data
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "incomplete_test.csv"
            reporter = CSVReporter(str(output_path))
            
            # Should not raise an error despite incomplete data
            output_file = reporter.generate_report(incomplete_results)
            assert Path(output_file).exists()
            
            # Verify CSV content handles missing values
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'test/repo' in content
                assert '123' in content  # Complete PR creator ID
                # Empty values should be handled gracefully


if __name__ == "__main__":
    pytest.main([__file__])
