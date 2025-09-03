"""
Unit tests for GitHub API client.

This module contains comprehensive tests for the GitHubClient class,
including authentication, error handling, and rate limiting scenarios.
"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from datetime import datetime

from github_client import (
    GitHubClient,
    GitHubAPIError,
    GitHubRateLimitError,
    GitHubAuthenticationError,
    setup_logging
)


class TestGitHubClient:
    """Test cases for GitHubClient class."""
    
    def test_init_with_valid_token(self):
        """Test GitHubClient initialization with valid token."""
        token = "test_token_123"
        client = GitHubClient(token)
        
        assert client.token == token
        assert client.session.headers['Authorization'] == f'token {token}'
        assert 'application/vnd.github.v3+json' in client.session.headers['Accept']
        assert 'GitHub-PR-Analyzer/1.0' in client.session.headers['User-Agent']
    
    def test_init_with_empty_token(self):
        """Test GitHubClient initialization with empty token raises error."""
        with pytest.raises(GitHubAuthenticationError, match="GitHub token is required"):
            GitHubClient("")
    
    def test_init_with_none_token(self):
        """Test GitHubClient initialization with None token raises error."""
        with pytest.raises(GitHubAuthenticationError, match="GitHub token is required"):
            GitHubClient(None)


class TestTokenFromEnvironment:
    """Test cases for reading token from environment variables."""
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': 'env_token_456'})
    def test_token_reading_from_env(self):
        """Test reading GitHub token from environment variable."""
        token = GitHubClient.get_token_from_env()
        assert token == "env_token_456"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_environment_token(self):
        """Test error when GITHUB_TOKEN environment variable is not set."""
        with pytest.raises(GitHubAuthenticationError, match="GITHUB_TOKEN environment variable is not set"):
            GitHubClient.get_token_from_env()
    
    @patch.dict(os.environ, {'GITHUB_TOKEN': ''})
    def test_empty_environment_token(self):
        """Test error when GITHUB_TOKEN environment variable is empty."""
        with pytest.raises(GitHubAuthenticationError, match="GITHUB_TOKEN environment variable is not set"):
            GitHubClient.get_token_from_env()


class TestTokenValidation:
    """Test cases for token validation and API connectivity."""
    
    def setup_method(self):
        """Set up test client for each test method."""
        self.client = GitHubClient("test_token")
    
    @patch('requests.Session.get')
    def test_valid_token_validation(self, mock_get):
        """Test successful token validation."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'login': 'testuser'}
        mock_get.return_value = mock_response
        
        result = self.client.validate_token()
        
        assert result is True
        mock_get.assert_called_once_with("https://api.github.com/user")
    
    @patch('requests.Session.get')
    def test_invalid_token_handling(self, mock_get):
        """Test handling of invalid authentication token."""
        # Mock 401 Unauthorized response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        with pytest.raises(GitHubAuthenticationError, match="Invalid GitHub token"):
            self.client.validate_token()
    
    @patch('requests.Session.get')
    def test_rate_limit_during_validation(self, mock_get):
        """Test rate limit handling during token validation."""
        # Mock 403 Forbidden response (rate limited)
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        
        with pytest.raises(GitHubRateLimitError, match="GitHub API rate limit exceeded"):
            self.client.validate_token()
    
    @patch('requests.Session.get')
    def test_api_error_during_validation(self, mock_get):
        """Test other API errors during token validation."""
        # Mock 500 Internal Server Error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        with pytest.raises(GitHubAPIError, match="API request failed: 500"):
            self.client.validate_token()
    
    @patch('requests.Session.get')
    def test_connection_error_during_validation(self, mock_get):
        """Test network connection errors during token validation."""
        # Mock requests.RequestException
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        
        with pytest.raises(GitHubAPIError, match="Failed to connect to GitHub API"):
            self.client.validate_token()


class TestRepositoryValidation:
    """Test cases for repository access validation."""
    
    def setup_method(self):
        """Set up test client for each test method."""
        self.client = GitHubClient("test_token")
    
    @patch('requests.Session.get')
    def test_repository_validation_success(self, mock_get):
        """Test successful repository access validation."""
        # Mock successful repository response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'name': 'test-repo',
            'full_name': 'testowner/test-repo',
            'private': False,
            'default_branch': 'main',
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-12-01T00:00:00Z'
        }
        mock_get.return_value = mock_response
        
        repo_info = self.client.get_repository_info("testowner", "test-repo")
        
        expected_info = {
            'name': 'test-repo',
            'full_name': 'testowner/test-repo',
            'private': False,
            'default_branch': 'main',
            'created_at': '2023-01-01T00:00:00Z',
            'updated_at': '2023-12-01T00:00:00Z'
        }
        
        assert repo_info == expected_info
        mock_get.assert_called_once_with("https://api.github.com/repos/testowner/test-repo")
    
    @patch('requests.Session.get')
    def test_repository_not_found(self, mock_get):
        """Test handling of non-existent or inaccessible repository."""
        # Mock 404 Not Found response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with pytest.raises(GitHubAPIError, match="Repository testowner/test-repo not found or not accessible"):
            self.client.get_repository_info("testowner", "test-repo")
    
    @patch('requests.Session.get')
    def test_repository_rate_limited(self, mock_get):
        """Test rate limiting during repository validation."""
        # Mock 403 Forbidden response (rate limited)
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        
        with pytest.raises(GitHubRateLimitError, match="GitHub API rate limit exceeded"):
            self.client.get_repository_info("testowner", "test-repo")
    
    @patch('requests.Session.get')
    def test_repository_api_error(self, mock_get):
        """Test other API errors during repository validation."""
        # Mock 500 Internal Server Error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        with pytest.raises(GitHubAPIError, match="Failed to fetch repository info: 500"):
            self.client.get_repository_info("testowner", "test-repo")
    
    @patch('requests.Session.get')
    def test_repository_connection_error(self, mock_get):
        """Test network connection errors during repository validation."""
        # Mock requests.RequestException
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        
        with pytest.raises(GitHubAPIError, match="Failed to fetch repository information"):
            self.client.get_repository_info("testowner", "test-repo")


class TestRateLimitHandling:
    """Test cases for GitHub API rate limiting scenarios."""
    
    def setup_method(self):
        """Set up test client for each test method."""
        self.client = GitHubClient("test_token")
    
    @patch('requests.Session.get')
    def test_rate_limit_handling(self, mock_get):
        """Test rate limit detection and error handling."""
        # Mock rate limited response
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.headers = {
            'X-RateLimit-Remaining': '0',
            'X-RateLimit-Reset': '1640995200'  # Example timestamp
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(GitHubRateLimitError, match="GitHub API rate limit exceeded"):
            self.client._make_api_request("https://api.github.com/test")
    
    @patch('requests.Session.get')
    def test_rate_limit_logging(self, mock_get):
        """Test rate limit status logging."""
        # Mock successful response with rate limit headers
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            'X-RateLimit-Remaining': '4999',
            'X-RateLimit-Limit': '5000'
        }
        mock_response.json.return_value = {'test': 'data'}
        mock_get.return_value = mock_response
        
        with patch.object(self.client.logger, 'debug') as mock_debug:
            result = self.client._make_api_request("https://api.github.com/test")
            
            assert result == {'test': 'data'}
            mock_debug.assert_called_with("API rate limit: 4999/5000 remaining")
    
    @patch('requests.Session.get')
    def test_403_without_rate_limit(self, mock_get):
        """Test 403 response that's not due to rate limiting."""
        # Mock 403 response without rate limit headers
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.headers = {}
        mock_response.text = "Forbidden"
        mock_get.return_value = mock_response
        
        with pytest.raises(GitHubAPIError, match="API request failed: 403"):
            self.client._make_api_request("https://api.github.com/test")


class TestAPIRequestHandling:
    """Test cases for general API request handling."""
    
    def setup_method(self):
        """Set up test client for each test method."""
        self.client = GitHubClient("test_token")
    
    @patch('requests.Session.get')
    def test_successful_api_request(self, mock_get):
        """Test successful API request handling."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        result = self.client._make_api_request("https://api.github.com/test")
        
        assert result == {'data': 'test'}
        mock_get.assert_called_once_with("https://api.github.com/test", params=None)
    
    @patch('requests.Session.get')
    def test_api_request_with_params(self, mock_get):
        """Test API request with query parameters."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        params = {'per_page': 100, 'state': 'all'}
        result = self.client._make_api_request("https://api.github.com/test", params)
        
        assert result == {'data': 'test'}
        mock_get.assert_called_once_with("https://api.github.com/test", params=params)
    
    @patch('requests.Session.get')
    def test_expired_token_handling(self, mock_get):
        """Test handling of expired authentication token."""
        # Mock 401 Unauthorized response
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        with pytest.raises(GitHubAuthenticationError, match="GitHub token is invalid or expired"):
            self.client._make_api_request("https://api.github.com/test")
    
    @patch('requests.Session.get')
    def test_connection_error_in_api_request(self, mock_get):
        """Test connection error handling in API requests."""
        # Mock requests.RequestException
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        
        with pytest.raises(GitHubAPIError, match="Failed to make API request"):
            self.client._make_api_request("https://api.github.com/test")


class TestLoggingSetup:
    """Test cases for logging configuration."""
    
    def test_setup_logging_default_level(self):
        """Test logging setup with default INFO level."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging()
            
            mock_config.assert_called_once_with(
                level=20,  # logging.INFO
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
    
    def test_setup_logging_custom_level(self):
        """Test logging setup with custom DEBUG level."""
        with patch('logging.basicConfig') as mock_config:
            setup_logging("DEBUG")
            
            mock_config.assert_called_once_with(
                level=10,  # logging.DEBUG
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )


# Test fixtures and utility functions
@pytest.fixture
def mock_github_response():
    """Fixture providing a mock GitHub API response."""
    response = Mock()
    response.status_code = 200
    response.headers = {}
    response.json.return_value = {'test': 'data'}
    return response


@pytest.fixture
def github_client():
    """Fixture providing a GitHubClient instance for testing."""
    return GitHubClient("test_token")


class TestPullRequestFetching:
    """Test cases for pull request data fetching."""
    
    def setup_method(self):
        """Set up test client for each test method."""
        self.client = GitHubClient("test_token")
    
    @patch('requests.Session.get')
    def test_pr_fetching_date_filtering(self, mock_get):
        """Test PR fetching with date filtering and range calculations."""
        # Mock PR data with different creation dates
        mock_prs = [
            {
                'number': 1,
                'created_at': '2024-12-01T10:00:00Z',
                'state': 'closed',
                'title': 'Recent PR'
            },
            {
                'number': 2,
                'created_at': '2024-11-15T10:00:00Z',
                'state': 'open',
                'title': 'Older PR'
            }
        ]
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_prs
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        # Test date range calculation
        from datetime import datetime, timedelta
        test_date = datetime(2024, 11, 20)
        
        with patch('github_client.datetime') as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 12, 20)
            mock_datetime.fromisoformat = datetime.fromisoformat
            
            # Test the actual method
            result = self.client.get_pull_requests("testowner", "test-repo", test_date)
            
            # Should return only PRs created after test_date
            assert len(result) == 1
            assert result[0]['number'] == 1
            assert result[0]['created_at'] == '2024-12-01T10:00:00Z'
    
    @patch('requests.Session.get')
    def test_pr_pagination_handling(self, mock_get):
        """Test pagination handling for large PR lists."""
        # Mock first page of PRs
        first_page = [{'number': i, 'created_at': '2024-12-01T10:00:00Z'} for i in range(1, 101)]
        
        # Mock second page of PRs (fewer than per_page to indicate last page)
        second_page = [{'number': i, 'created_at': '2024-12-01T10:00:00Z'} for i in range(101, 150)]
        
        responses = [first_page, second_page]
        
        def mock_api_request(url, params=None):
            page = params.get('page', 1) if params else 1
            if page <= len(responses):
                return responses[page - 1]
            return []
        
        with patch.object(self.client, '_make_api_request', side_effect=mock_api_request):
            from datetime import datetime
            test_date = datetime(2024, 11, 1)
            
            result = self.client.get_pull_requests("testowner", "test-repo", test_date)
            
            # Should return all PRs from both pages
            assert len(result) == 149
            assert result[0]['number'] == 1
            assert result[-1]['number'] == 149
    
    @patch('requests.Session.get')
    def test_get_pr_details_success(self, mock_get):
        """Test successful PR details fetching."""
        mock_pr_data = {
            'number': 123,
            'title': 'Test PR',
            'state': 'closed',
            'created_at': '2024-12-01T10:00:00Z',
            'merged_at': '2024-12-02T15:30:00Z',
            'user': {'login': 'testuser'},
            'base': {'ref': 'main'},
            'head': {'ref': 'feature-branch'}
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_pr_data
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        with patch.object(self.client, '_make_api_request', return_value=mock_pr_data):
            result = self.client.get_pr_details("testowner", "test-repo", 123)
            
            assert result['number'] == 123
            assert result['title'] == 'Test PR'
            assert result['merged_at'] == '2024-12-02T15:30:00Z'
    
    @patch('requests.Session.get')
    def test_get_pr_details_not_found(self, mock_get):
        """Test PR details fetching for non-existent PR."""
        with patch.object(self.client, '_make_api_request', side_effect=GitHubAPIError("API request failed: 404")):
            with pytest.raises(GitHubAPIError, match="Pull request #999 not found in testowner/test-repo"):
                self.client.get_pr_details("testowner", "test-repo", 999)
    
    def test_calculate_date_range(self):
        """Test date range calculations for different time periods."""
        # Test 1 month back
        with patch('github_client.datetime') as mock_datetime:
            mock_now = datetime(2024, 12, 20, 15, 30, 45, 123456)
            mock_datetime.now.return_value = mock_now
            
            from dateutil.relativedelta import relativedelta
            expected_date = mock_now.replace(microsecond=0) - relativedelta(months=1)
            
            result = self.client._calculate_date_range(1)
            
            assert result == expected_date
        
        # Test 3 months back
        with patch('github_client.datetime') as mock_datetime:
            mock_now = datetime(2024, 12, 20, 10, 0, 0)
            mock_datetime.now.return_value = mock_now
            
            from dateutil.relativedelta import relativedelta
            expected_date = mock_now - relativedelta(months=3)
            
            result = self.client._calculate_date_range(3)
            
            assert result == expected_date
    
    @patch('requests.Session.get')
    def test_pr_fetching_with_early_termination(self, mock_get):
        """Test that PR fetching stops when encountering PRs older than since_date."""
        # Mock PRs where some are too old
        mock_prs_page1 = [
            {'number': 1, 'created_at': '2024-12-01T10:00:00Z'},  # Recent
            {'number': 2, 'created_at': '2024-11-01T10:00:00Z'},  # Old - should stop here
        ]
        
        def mock_api_request(url, params=None):
            return mock_prs_page1
        
        with patch.object(self.client, '_make_api_request', side_effect=mock_api_request):
            from datetime import datetime
            test_date = datetime(2024, 11, 15)  # Date between the two PRs
            
            result = self.client.get_pull_requests("testowner", "test-repo", test_date)
            
            # Should only return the recent PR and stop pagination
            assert len(result) == 1
            assert result[0]['number'] == 1


class TestReviewDataFetching:
    """Test cases for review data fetching methods."""
    
    def setup_method(self):
        """Set up test client for each test method."""
        self.client = GitHubClient("test_token")
    
    @patch('requests.Session.get')
    def test_review_data_fetching(self, mock_get):
        """Test PR reviews fetching."""
        mock_reviews = [
            {'id': 1, 'state': 'APPROVED', 'submitted_at': '2024-12-01T10:30:00Z'},
            {'id': 2, 'state': 'CHANGES_REQUESTED', 'submitted_at': '2024-12-01T14:00:00Z'}
        ]
        
        with patch.object(self.client, '_make_api_request', return_value=mock_reviews):
            result = self.client.get_pr_reviews("testowner", "test-repo", 123)
            
            assert len(result) == 2
            assert result[0]['state'] == 'APPROVED'
            assert result[1]['state'] == 'CHANGES_REQUESTED'
    
    @patch('requests.Session.get')
    def test_review_comments_fetching(self, mock_get):
        """Test PR review comments fetching."""
        mock_comments = [
            {'id': 1, 'body': 'This looks good', 'created_at': '2024-12-01T11:00:00Z'},
            {'id': 2, 'body': 'Please fix this', 'created_at': '2024-12-01T15:30:00Z'}
        ]
        
        with patch.object(self.client, '_make_api_request', return_value=mock_comments):
            result = self.client.get_pr_review_comments("testowner", "test-repo", 123)
            
            assert len(result) == 2
            assert result[0]['body'] == 'This looks good'
            assert result[1]['body'] == 'Please fix this'
    
    @patch('requests.Session.get')
    def test_review_data_not_found(self, mock_get):
        """Test handling of PR not found for review data."""
        with patch.object(self.client, '_make_api_request', side_effect=GitHubAPIError("API request failed: 404")):
            reviews = self.client.get_pr_reviews("testowner", "test-repo", 999)
            comments = self.client.get_pr_review_comments("testowner", "test-repo", 999)
            
            assert reviews == []
            assert comments == []


class TestMergeDataFetching:
    """Test cases for merge information fetching."""
    
    def setup_method(self):
        """Set up test client for each test method."""
        self.client = GitHubClient("test_token")
    
    def test_merge_info_for_merged_pr(self):
        """Test merge info fetching for merged PR."""
        mock_pr_data = {
            'number': 123,
            'merged_at': '2024-12-02T10:30:00Z',
            'merged_by': {'login': 'testuser'},
            'merge_commit_sha': 'abc123',
            'merged': True
        }
        
        with patch.object(self.client, 'get_pr_details', return_value=mock_pr_data):
            result = self.client.get_pr_merge_info("testowner", "test-repo", 123)
            
            assert result is not None
            assert result['merged_at'] == '2024-12-02T10:30:00Z'
            assert result['merged_by']['login'] == 'testuser'
            assert result['merged'] is True
    
    def test_merge_info_for_unmerged_pr(self):
        """Test merge info fetching for unmerged PR."""
        mock_pr_data = {
            'number': 123,
            'merged_at': None,
            'merged': False
        }
        
        with patch.object(self.client, 'get_pr_details', return_value=mock_pr_data):
            result = self.client.get_pr_merge_info("testowner", "test-repo", 123)
            
            assert result is None


class TestCommitDataFetching:
    """Test cases for commit data fetching and timestamp parsing."""
    
    def setup_method(self):
        """Set up test client for each test method."""
        self.client = GitHubClient("test_token")
    
    @patch('requests.Session.get')
    def test_commit_data_fetching(self, mock_get):
        """Test PR commits fetching."""
        mock_commits = [
            {
                'sha': 'abc123',
                'commit': {
                    'author': {'date': '2024-11-30T08:00:00Z'},
                    'committer': {'date': '2024-11-30T08:00:00Z'},
                    'message': 'Initial commit'
                }
            },
            {
                'sha': 'def456',
                'commit': {
                    'author': {'date': '2024-12-01T10:00:00Z'},
                    'committer': {'date': '2024-12-01T10:00:00Z'},
                    'message': 'Fix bug'
                }
            }
        ]
        
        with patch.object(self.client, '_make_api_request', return_value=mock_commits):
            result = self.client.get_pr_commits("testowner", "test-repo", 123)
            
            assert len(result) == 2
            assert result[0]['sha'] == 'abc123'
            assert result[1]['sha'] == 'def456'
    
    @patch('requests.Session.get')
    def test_commit_pagination(self, mock_get):
        """Test commit fetching with pagination."""
        # Mock first page of commits
        first_page = [{'sha': f'commit{i}', 'commit': {'author': {'date': '2024-12-01T10:00:00Z'}}} 
                     for i in range(1, 101)]
        
        # Mock second page (smaller)
        second_page = [{'sha': f'commit{i}', 'commit': {'author': {'date': '2024-12-01T10:00:00Z'}}} 
                      for i in range(101, 120)]
        
        responses = [first_page, second_page]
        
        def mock_api_request(url, params=None):
            page = params.get('page', 1) if params else 1
            if page <= len(responses):
                return responses[page - 1]
            return []
        
        with patch.object(self.client, '_make_api_request', side_effect=mock_api_request):
            result = self.client.get_pr_commits("testowner", "test-repo", 123)
            
            assert len(result) == 119
            assert result[0]['sha'] == 'commit1'
            assert result[-1]['sha'] == 'commit119'


class TestTimelineDataParsing:
    """Test cases for timeline event parsing."""
    
    def setup_method(self):
        """Set up test client for each test method."""
        self.client = GitHubClient("test_token")
    
    @patch('requests.Session.get')
    def test_timeline_data_parsing(self, mock_get):
        """Test timeline event fetching and parsing."""
        mock_timeline = [
            {'event': 'reviewed', 'created_at': '2024-12-01T10:30:00Z', 'actor': {'login': 'reviewer'}},
            {'event': 'merged', 'created_at': '2024-12-02T15:00:00Z', 'actor': {'login': 'maintainer'}}
        ]
        
        # Mock the session.get call for timeline API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_timeline
        mock_response.headers = {}
        mock_get.return_value = mock_response
        
        result = self.client.get_pr_timeline("testowner", "test-repo", 123)
        
        assert len(result) == 2
        assert result[0]['event'] == 'reviewed'
        assert result[1]['event'] == 'merged'
    
    @patch('requests.Session.get')
    def test_timeline_not_found(self, mock_get):
        """Test timeline fetching for non-existent PR."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = self.client.get_pr_timeline("testowner", "test-repo", 999)
        
        assert result == []
    
    @patch('requests.Session.get')
    def test_timeline_pagination(self, mock_get):
        """Test timeline fetching with pagination."""
        # First page
        first_page_events = [{'event': f'event{i}', 'created_at': '2024-12-01T10:00:00Z'} 
                            for i in range(1, 101)]
        
        # Second page (smaller, indicating end)
        second_page_events = [{'event': f'event{i}', 'created_at': '2024-12-01T10:00:00Z'} 
                             for i in range(101, 110)]
        
        def mock_session_get(*args, **kwargs):
            params = kwargs.get('params', {})
            page = params.get('page', 1)
            
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {}
            
            if page == 1:
                mock_response.json.return_value = first_page_events
            elif page == 2:
                mock_response.json.return_value = second_page_events
            else:
                mock_response.json.return_value = []
            
            return mock_response
        
        mock_get.side_effect = mock_session_get
        
        result = self.client.get_pr_timeline("testowner", "test-repo", 123)
        
        assert len(result) == 109
        assert result[0]['event'] == 'event1'
        assert result[-1]['event'] == 'event109'


if __name__ == "__main__":
    pytest.main([__file__])
