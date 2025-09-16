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
        mock_response.headers = {
            'X-RateLimit-Remaining': '5000',
            'X-RateLimit-Limit': '5000',
            'X-RateLimit-Reset': '1640995200',
            'X-RateLimit-Used': '0'
        }
        mock_get.return_value = mock_response
        
        with pytest.raises(GitHubAuthenticationError, match="GitHub token is invalid or expired"):
            self.client._make_api_request("https://api.github.com/test")
    
    @patch('requests.Session.get')
    def test_connection_error_in_api_request(self, mock_get):
        """Test connection error handling in API requests."""
        # Mock requests.RequestException
        mock_get.side_effect = requests.ConnectionError("Connection failed")
        
        with pytest.raises(GitHubAPIError, match="GitHub API request to .* failed after .* attempts"):
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
        mock_response.headers = {
            'X-RateLimit-Remaining': '5000',
            'X-RateLimit-Limit': '5000',
            'X-RateLimit-Reset': '1640995200',
            'X-RateLimit-Used': '0'
        }
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


class TestReviewerDataFetching:
    """Test cases for reviewer request data fetching and processing."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a GitHubClient with mocked session for testing."""
        with patch('github_client.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            mock_session.headers = {}
            
            client = GitHubClient("test_token")
            client.session = mock_session
            return client, mock_session
    
    def test_get_pr_requested_reviewers_success(self, mock_client):
        """Test successful retrieval of requested reviewers for a PR."""
        client, mock_session = mock_client
        
        # Mock the API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            'X-RateLimit-Remaining': '5000',
            'X-RateLimit-Limit': '5000',
            'X-RateLimit-Reset': '1640995200',
            'X-RateLimit-Used': '0'
        }
        mock_response.json.return_value = {
            'users': [
                {'id': 1, 'login': 'reviewer1'},
                {'id': 2, 'login': 'reviewer2'}
            ],
            'teams': [
                {'id': 10, 'slug': 'team-frontend', 'name': 'Frontend Team'},
                {'id': 11, 'slug': 'team-backend', 'name': 'Backend Team'}
            ]
        }
        mock_session.get.return_value = mock_response
        
        result = client.get_pr_requested_reviewers('owner', 'repo', 123)
        
        # Verify the API call
        expected_url = "https://api.github.com/repos/owner/repo/pulls/123/requested_reviewers"
        mock_session.get.assert_called_once_with(expected_url, params=None)
        
        # Verify the result structure
        assert 'users' in result
        assert 'teams' in result
        assert len(result['users']) == 2
        assert len(result['teams']) == 2
        assert result['users'][0]['login'] == 'reviewer1'
        assert result['teams'][0]['slug'] == 'team-frontend'
    
    def test_get_pr_requested_reviewers_empty_response(self, mock_client):
        """Test handling empty reviewer response."""
        client, mock_session = mock_client
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            'X-RateLimit-Remaining': '5000',
            'X-RateLimit-Limit': '5000',
            'X-RateLimit-Reset': '1640995200',
            'X-RateLimit-Used': '0'
        }
        mock_response.json.return_value = {'users': [], 'teams': []}
        mock_session.get.return_value = mock_response
        
        result = client.get_pr_requested_reviewers('owner', 'repo', 123)
        
        assert result['users'] == []
        assert result['teams'] == []
    
    def test_get_pr_requested_reviewers_not_found(self, mock_client):
        """Test handling 404 response for requested reviewers."""
        client, mock_session = mock_client
        
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_session.get.return_value = mock_response
        
        # Simulate the GitHubAPIError that would be raised by _make_api_request
        with patch.object(client, '_make_api_request', side_effect=GitHubAPIError("404 Not Found")):
            result = client.get_pr_requested_reviewers('owner', 'repo', 123)
            
            # Should return empty lists for 404
            assert result['users'] == []
            assert result['teams'] == []
    
    def test_get_pr_requested_reviewers_invalid_params(self, mock_client):
        """Test input validation for get_pr_requested_reviewers."""
        client, mock_session = mock_client
        
        # Test missing owner
        with pytest.raises(GitHubAPIError, match="Repository owner and name are required"):
            client.get_pr_requested_reviewers('', 'repo', 123)
        
        # Test missing repo
        with pytest.raises(GitHubAPIError, match="Repository owner and name are required"):
            client.get_pr_requested_reviewers('owner', '', 123)
        
        # Test invalid PR number
        with pytest.raises(GitHubAPIError, match="Invalid PR number"):
            client.get_pr_requested_reviewers('owner', 'repo', 0)
        
        with pytest.raises(GitHubAPIError, match="Invalid PR number"):
            client.get_pr_requested_reviewers('owner', 'repo', -1)
    
    def test_get_team_members_success(self, mock_client):
        """Test successful retrieval of team members."""
        client, mock_session = mock_client
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            'X-RateLimit-Remaining': '5000',
            'X-RateLimit-Limit': '5000',
            'X-RateLimit-Reset': '1640995200',
            'X-RateLimit-Used': '0'
        }
        mock_response.json.return_value = [
            {'id': 1, 'login': 'member1'},
            {'id': 2, 'login': 'member2'},
            {'id': 3, 'login': 'member3'}
        ]
        mock_session.get.return_value = mock_response
        
        result = client.get_team_members('myorg', 'team-slug')
        
        # Verify the API call
        expected_url = "https://api.github.com/orgs/myorg/teams/team-slug/members"
        mock_session.get.assert_called_once_with(expected_url, params=None)
        
        # Verify the result
        assert len(result) == 3
        assert result[0]['login'] == 'member1'
        assert result[2]['login'] == 'member3'
    
    def test_get_team_members_not_found(self, mock_client):
        """Test handling 404 response for team members."""
        client, mock_session = mock_client
        
        # Simulate the GitHubAPIError that would be raised by _make_api_request
        with patch.object(client, '_make_api_request', side_effect=GitHubAPIError("404 Not Found")):
            result = client.get_team_members('myorg', 'nonexistent-team')
            
            # Should return empty list for 404
            assert result == []
    
    def test_get_team_members_invalid_params(self, mock_client):
        """Test input validation for get_team_members."""
        client, mock_session = mock_client
        
        # Test missing org
        with pytest.raises(GitHubAPIError, match="Organization name and team slug are required"):
            client.get_team_members('', 'team-slug')
        
        # Test missing team_slug
        with pytest.raises(GitHubAPIError, match="Organization name and team slug are required"):
            client.get_team_members('myorg', '')
    
    def test_expand_team_reviewers_success(self, mock_client):
        """Test successful expansion of team reviewers to individual members."""
        client, mock_session = mock_client
        
        teams = [
            {'id': 10, 'slug': 'team-frontend', 'name': 'Frontend Team'},
            {'id': 11, 'slug': 'team-backend', 'name': 'Backend Team'}
        ]
        
        # Mock the get_team_members calls
        def mock_get_team_members(org, team_slug):
            if team_slug == 'team-frontend':
                return [{'id': 1, 'login': 'frontend1'}, {'id': 2, 'login': 'frontend2'}]
            elif team_slug == 'team-backend':
                return [{'id': 3, 'login': 'backend1'}, {'id': 1, 'login': 'frontend1'}]  # Duplicate ID 1
            return []
        
        with patch.object(client, 'get_team_members', side_effect=mock_get_team_members):
            result = client.expand_team_reviewers(teams, 'myorg')
        
        # Should have 3 unique members (duplicate removed)
        assert len(result) == 3
        user_ids = [member['id'] for member in result]
        assert 1 in user_ids
        assert 2 in user_ids
        assert 3 in user_ids
    
    def test_expand_team_reviewers_empty_teams(self, mock_client):
        """Test expand_team_reviewers with empty teams list."""
        client, mock_session = mock_client
        
        result = client.expand_team_reviewers([], 'myorg')
        
        assert result == []
    
    def test_expand_team_reviewers_no_org(self, mock_client):
        """Test expand_team_reviewers with no organization provided."""
        client, mock_session = mock_client
        
        teams = [{'id': 10, 'slug': 'team-frontend', 'name': 'Frontend Team'}]
        
        result = client.expand_team_reviewers(teams, '')
        
        assert result == []
    
    def test_expand_team_reviewers_missing_slug(self, mock_client):
        """Test expand_team_reviewers with team missing slug field."""
        client, mock_session = mock_client
        
        teams = [
            {'id': 10, 'name': 'Frontend Team'},  # Missing slug
            {'id': 11, 'slug': 'team-backend', 'name': 'Backend Team'}
        ]
        
        with patch.object(client, 'get_team_members') as mock_get_members:
            mock_get_members.return_value = [{'id': 3, 'login': 'backend1'}]
            
            result = client.expand_team_reviewers(teams, 'myorg')
        
        # Should only process the team with valid slug
        assert len(result) == 1
        assert result[0]['login'] == 'backend1'
        mock_get_members.assert_called_once_with('myorg', 'team-backend')
    
    def test_expand_team_reviewers_api_error(self, mock_client):
        """Test expand_team_reviewers handling API errors gracefully."""
        client, mock_session = mock_client
        
        teams = [
            {'id': 10, 'slug': 'team-frontend', 'name': 'Frontend Team'},
            {'id': 11, 'slug': 'team-backend', 'name': 'Backend Team'}
        ]
        
        def mock_get_team_members(org, team_slug):
            if team_slug == 'team-frontend':
                raise GitHubAPIError("API Error")
            elif team_slug == 'team-backend':
                return [{'id': 3, 'login': 'backend1'}]
            return []
        
        with patch.object(client, 'get_team_members', side_effect=mock_get_team_members):
            result = client.expand_team_reviewers(teams, 'myorg')
        
        # Should return only successful team expansion
        assert len(result) == 1
        assert result[0]['login'] == 'backend1'
    
    def test_extract_reviewer_requests_from_pr_success(self, mock_client):
        """Test successful extraction of reviewer requests from PR data."""
        client, mock_session = mock_client
        
        pr_data = {
            'number': 123,
            'requested_reviewers': [
                {'id': 1, 'login': 'reviewer1'},
                {'id': 2, 'login': 'reviewer2'}
            ],
            'requested_teams': [
                {'id': 10, 'slug': 'team-frontend'}
            ]
        }
        
        result = client.extract_reviewer_requests_from_pr(pr_data)
        
        assert 'users' in result
        assert 'teams' in result
        assert len(result['users']) == 2
        assert len(result['teams']) == 1
        assert result['users'][0]['login'] == 'reviewer1'
        assert result['teams'][0]['slug'] == 'team-frontend'
    
    def test_extract_reviewer_requests_from_pr_empty_data(self, mock_client):
        """Test extraction from PR with no reviewer data."""
        client, mock_session = mock_client
        
        pr_data = {'number': 123}  # Missing reviewer fields
        
        result = client.extract_reviewer_requests_from_pr(pr_data)
        
        assert result['users'] == []
        assert result['teams'] == []
    
    def test_extract_reviewer_requests_from_pr_invalid_data(self, mock_client):
        """Test extraction from invalid PR data."""
        client, mock_session = mock_client
        
        # Test None data
        result = client.extract_reviewer_requests_from_pr(None)
        assert result == {'users': [], 'teams': []}
        
        # Test non-dict data
        result = client.extract_reviewer_requests_from_pr("invalid")
        assert result == {'users': [], 'teams': []}
    
    def test_extract_reviewer_requests_from_pr_invalid_lists(self, mock_client):
        """Test extraction from PR with invalid reviewer list data."""
        client, mock_session = mock_client
        
        pr_data = {
            'number': 123,
            'requested_reviewers': 'not-a-list',  # Should be a list
            'requested_teams': {'invalid': 'dict'}  # Should be a list
        }
        
        result = client.extract_reviewer_requests_from_pr(pr_data)
        
        # Should gracefully handle invalid data
        assert result['users'] == []
        assert result['teams'] == []


if __name__ == "__main__":
    pytest.main([__file__])
