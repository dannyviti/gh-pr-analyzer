"""
GitHub API client for pull request analysis.

This module provides a client for interacting with the GitHub API
to fetch pull request data, reviews, and related information.
"""

import os
import logging
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any


class GitHubAPIError(Exception):
    """Custom exception for GitHub API related errors."""
    pass


class GitHubRateLimitError(GitHubAPIError):
    """Exception raised when GitHub API rate limit is exceeded."""
    pass


class GitHubAuthenticationError(GitHubAPIError):
    """Exception raised when GitHub API authentication fails."""
    pass


class GitHubClient:
    """
    Client for interacting with GitHub API to fetch pull request data.
    
    This client handles authentication, rate limiting, and provides methods
    to fetch pull requests, reviews, and related data from GitHub repositories.
    """
    
    BASE_URL = "https://api.github.com"
    
    def __init__(self, token: str):
        """
        Initialize GitHub client with authentication token.
        
        Args:
            token: GitHub personal access token for API authentication
            
        Raises:
            GitHubAuthenticationError: If token is empty or None
        """
        if not token:
            raise GitHubAuthenticationError("GitHub token is required")
        
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-PR-Analyzer/1.0'
        })
        
        # Configure logging
        self.logger = logging.getLogger(__name__)
    
    @classmethod
    def get_token_from_env(cls) -> str:
        """
        Read GitHub token from GITHUB_TOKEN environment variable.
        
        Returns:
            GitHub token from environment variable
            
        Raises:
            GitHubAuthenticationError: If GITHUB_TOKEN is not set
        """
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            raise GitHubAuthenticationError(
                "GITHUB_TOKEN environment variable is not set"
            )
        return token
    
    def validate_token(self) -> bool:
        """
        Test API connectivity and token validity.
        
        Returns:
            True if token is valid and API is accessible
            
        Raises:
            GitHubAuthenticationError: If authentication fails
            GitHubAPIError: If API request fails for other reasons
        """
        try:
            response = self.session.get(f"{self.BASE_URL}/user")
            
            if response.status_code == 401:
                raise GitHubAuthenticationError("Invalid GitHub token")
            elif response.status_code == 403:
                raise GitHubRateLimitError("GitHub API rate limit exceeded")
            elif response.status_code != 200:
                raise GitHubAPIError(f"API request failed: {response.status_code}")
            
            self.logger.info("GitHub token validation successful")
            return True
            
        except requests.RequestException as e:
            raise GitHubAPIError(f"Failed to connect to GitHub API: {e}")
    
    def get_repository_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Validate repository access and get repository information.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            
        Returns:
            Dictionary containing repository information
            
        Raises:
            GitHubAPIError: If repository is not accessible or doesn't exist
        """
        try:
            response = self.session.get(f"{self.BASE_URL}/repos/{owner}/{repo}")
            
            if response.status_code == 404:
                raise GitHubAPIError(f"Repository {owner}/{repo} not found or not accessible")
            elif response.status_code == 403:
                raise GitHubRateLimitError("GitHub API rate limit exceeded")
            elif response.status_code != 200:
                raise GitHubAPIError(f"Failed to fetch repository info: {response.status_code}")
            
            repo_info = response.json()
            self.logger.info(f"Successfully accessed repository {owner}/{repo}")
            
            return {
                'name': repo_info['name'],
                'full_name': repo_info['full_name'],
                'private': repo_info['private'],
                'default_branch': repo_info['default_branch'],
                'created_at': repo_info['created_at'],
                'updated_at': repo_info['updated_at']
            }
            
        except requests.RequestException as e:
            raise GitHubAPIError(f"Failed to fetch repository information: {e}")
    
    def _get_rate_limit_info(self, response: requests.Response) -> Dict[str, Any]:
        """Extract rate limit information from response headers."""
        return {
            'remaining': int(response.headers.get('X-RateLimit-Remaining', 0)),
            'limit': int(response.headers.get('X-RateLimit-Limit', 5000)),
            'reset': int(response.headers.get('X-RateLimit-Reset', 0)),
            'used': int(response.headers.get('X-RateLimit-Used', 0))
        }
    
    def _should_wait_for_rate_limit(self, response: requests.Response) -> bool:
        """Check if we should proactively wait due to low remaining rate limit."""
        rate_info = self._get_rate_limit_info(response)
        # Be proactive: if we have less than 100 requests remaining, suggest waiting
        return rate_info['remaining'] < 100
    
    def _calculate_wait_time(self, reset_timestamp: int) -> int:
        """Calculate how long to wait until rate limit resets."""
        current_time = int(time.time())
        wait_time = max(0, reset_timestamp - current_time)
        return wait_time
    
    def _handle_rate_limit(self, response: requests.Response) -> None:
        """
        Handle GitHub API rate limiting with enhanced strategies.
        
        Args:
            response: HTTP response from GitHub API
            
        Raises:
            GitHubRateLimitError: If rate limit is exceeded
        """
        rate_info = self._get_rate_limit_info(response)
        
        # Log current rate limit status
        self.logger.debug(f"API rate limit: {rate_info['remaining']}/{rate_info['limit']} remaining")
        
        # Handle rate limit exceeded - only treat as rate limit if headers are actually present
        # If no rate limit headers are present, this is a regular 403 Forbidden, not a rate limit
        has_rate_limit_headers = 'X-RateLimit-Remaining' in response.headers
        if response.status_code == 403 and has_rate_limit_headers and rate_info['remaining'] == 0:
            wait_time = self._calculate_wait_time(rate_info['reset'])
            reset_time_str = datetime.fromtimestamp(rate_info['reset']).strftime('%Y-%m-%d %H:%M:%S')
            
            raise GitHubRateLimitError(
                f"GitHub API rate limit exceeded ({rate_info['used']}/{rate_info['limit']} used). "
                f"Rate limit resets at {reset_time_str} (wait {wait_time} seconds)"
            )
        
        # Warn when rate limit is getting low
        if rate_info['remaining'] < 100:
            reset_time_str = datetime.fromtimestamp(rate_info['reset']).strftime('%H:%M:%S')
            self.logger.warning(
                f"GitHub API rate limit running low: {rate_info['remaining']}/{rate_info['limit']} "
                f"remaining (resets at {reset_time_str})"
            )
        elif rate_info['remaining'] < 500:
            self.logger.info(f"GitHub API usage: {rate_info['remaining']}/{rate_info['limit']} remaining")
    
    def _make_api_request(self, url: str, params: Optional[Dict[str, Any]] = None,
                         max_retries: int = 3, base_delay: float = 1.0) -> Dict[str, Any]:
        """
        Make authenticated API request with retry logic and exponential backoff.
        
        Args:
            url: API endpoint URL
            params: Query parameters for the request
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds for exponential backoff
            
        Returns:
            JSON response data
            
        Raises:
            GitHubAPIError: If API request fails after all retries
            GitHubRateLimitError: If rate limit is exceeded and cannot be handled
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                response = self.session.get(url, params=params)
                
                # Handle rate limiting
                self._handle_rate_limit(response)
                
                if response.status_code == 401:
                    raise GitHubAuthenticationError("GitHub token is invalid or expired")
                elif response.status_code != 200:
                    raise GitHubAPIError(f"API request failed: {response.status_code} - {response.text}")
                
                if attempt > 0:
                    self.logger.info(f"API request succeeded after {attempt} retries")
                
                return response.json()
                
            except GitHubRateLimitError:
                # Don't retry rate limit errors, let them bubble up
                raise
            except GitHubAuthenticationError:
                # Don't retry auth errors
                raise
                
            except (requests.RequestException, GitHubAPIError) as e:
                last_exception = e
                
                if attempt < max_retries:
                    # Calculate exponential backoff delay
                    delay = base_delay * (2 ** attempt)
                    self.logger.warning(
                        f"API request to {url} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(f"API request to {url} failed after {max_retries + 1} attempts: {e}")
        
        # If we get here, all retries failed
        raise GitHubAPIError(f"GitHub API request to {url} failed after {max_retries + 1} attempts: {last_exception}")
    
    def get_pr_data_batch(self, owner: str, repo: str, pr_numbers: List[int], 
                         batch_size: int = 10, delay_between_batches: float = 0.1) -> Dict[int, Dict[str, Any]]:
        """
        Fetch PR data for multiple PRs in batches to optimize API usage.
        
        This method fetches basic PR data, reviews, comments, timeline, merge info, and commits
        for multiple PRs while respecting rate limits and reducing API calls.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_numbers: List of PR numbers to fetch data for
            batch_size: Number of PRs to process in each batch
            delay_between_batches: Delay in seconds between batches
            
        Returns:
            Dictionary mapping PR number to combined PR data
        """
        pr_data = {}
        
        # Process PRs in batches
        for i in range(0, len(pr_numbers), batch_size):
            batch = pr_numbers[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(pr_numbers) + batch_size - 1) // batch_size
            
            self.logger.info(f"Processing batch {batch_num}/{total_batches} (PRs: {batch})")
            
            for pr_number in batch:
                try:
                    # Collect all data for this PR
                    pr_info = {
                        'reviews': [],
                        'review_comments': [],
                        'timeline': [],
                        'merge_info': None,
                        'commits': []
                    }
                    
                    # Fetch each type of data with individual error handling
                    try:
                        pr_info['reviews'] = self.get_pr_reviews(owner, repo, pr_number) or []
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch reviews for PR #{pr_number}: {e}")
                    
                    try:
                        pr_info['review_comments'] = self.get_pr_review_comments(owner, repo, pr_number) or []
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch review comments for PR #{pr_number}: {e}")
                    
                    try:
                        pr_info['timeline'] = self.get_pr_timeline(owner, repo, pr_number) or []
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch timeline for PR #{pr_number}: {e}")
                    
                    try:
                        pr_info['merge_info'] = self.get_pr_merge_info(owner, repo, pr_number)
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch merge info for PR #{pr_number}: {e}")
                    
                    try:
                        pr_info['commits'] = self.get_pr_commits(owner, repo, pr_number) or []
                    except Exception as e:
                        self.logger.warning(f"Failed to fetch commits for PR #{pr_number}: {e}")
                    
                    pr_data[pr_number] = pr_info
                    
                except Exception as e:
                    self.logger.error(f"Failed to fetch data for PR #{pr_number}: {e}")
                    # Continue with next PR
                    continue
            
            # Add delay between batches to be respectful to the API
            if i + batch_size < len(pr_numbers) and delay_between_batches > 0:
                self.logger.debug(f"Waiting {delay_between_batches}s between batches...")
                time.sleep(delay_between_batches)
        
        return pr_data
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status from GitHub API.
        
        Returns:
            Dictionary containing rate limit information
        """
        url = f"{self.BASE_URL}/rate_limit"
        
        try:
            response = self.session.get(url)
            
            if response.status_code == 401:
                raise GitHubAuthenticationError("GitHub token is invalid or expired")
            elif response.status_code != 200:
                raise GitHubAPIError(f"Failed to get rate limit status: {response.status_code}")
            
            rate_data = response.json()
            
            # Extract core API rate limit info
            core_info = rate_data.get('rate', {})
            
            return {
                'limit': core_info.get('limit', 0),
                'remaining': core_info.get('remaining', 0),
                'reset': core_info.get('reset', 0),
                'used': core_info.get('used', 0),
                'reset_time': datetime.fromtimestamp(core_info.get('reset', 0)).strftime('%Y-%m-%d %H:%M:%S') if core_info.get('reset') else 'Unknown'
            }
            
        except requests.RequestException as e:
            raise GitHubAPIError(f"Failed to check rate limit status: {e}")
    
    def get_user_by_id(self, user_id: int) -> Dict[str, Any]:
        """
        Get user information by GitHub user ID.
        
        This method translates a GitHub user ID to user information including username.
        
        Args:
            user_id: GitHub user ID (integer)
            
        Returns:
            Dictionary containing user information including 'login' (username)
            
        Raises:
            GitHubAPIError: If user lookup fails
            GitHubRateLimitError: If rate limit is exceeded
        """
        if not user_id or user_id <= 0:
            raise GitHubAPIError(f"Invalid user ID: {user_id}")
        
        url = f"{self.BASE_URL}/user/{user_id}"
        
        try:
            user_data = self._make_api_request(url)
            self.logger.debug(f"Successfully fetched user data for ID {user_id}: {user_data.get('login', 'unknown')}")
            return user_data
            
        except GitHubAPIError as e:
            # Re-raise with more context
            raise GitHubAPIError(f"Failed to fetch user data for ID {user_id}: {e}")
    
    def get_username_by_id(self, user_id: int) -> Optional[str]:
        """
        Get username (login) by GitHub user ID.
        
        This is a convenience method that returns just the username string.
        
        Args:
            user_id: GitHub user ID (integer)
            
        Returns:
            Username string, or None if user not found or lookup fails
        """
        try:
            user_data = self.get_user_by_id(user_id)
            return user_data.get('login')
            
        except Exception as e:
            self.logger.warning(f"Failed to get username for user ID {user_id}: {e}")
            return None
    
    def get_pull_requests(self, owner: str, repo: str, since_date: datetime, state: str = "all") -> List[Dict[str, Any]]:
        """
        Fetch pull requests from a repository since a specific date.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            since_date: Fetch PRs created since this date
            state: PR state filter (open, closed, all). Defaults to 'all'
            
        Returns:
            List of pull request data dictionaries
            
        Raises:
            GitHubAPIError: If API request fails
        """
        all_prs = []
        page = 1
        per_page = 100
        
        self.logger.info(f"Fetching pull requests from {owner}/{repo} since {since_date}")
        
        while True:
            params = {
                'state': state,
                'sort': 'created',
                'direction': 'desc',
                'per_page': per_page,
                'page': page
            }
            
            url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls"
            
            try:
                prs_data = self._make_api_request(url, params)
                
                if not prs_data:
                    break
                
                # Filter PRs by date - GitHub API doesn't support date filtering directly
                filtered_prs = []
                for pr in prs_data:
                    pr_created_str = pr['created_at']
                    if pr_created_str.endswith('Z'):
                        pr_created_str = pr_created_str.replace('Z', '+00:00')
                    
                    pr_created = datetime.fromisoformat(pr_created_str)
                    
                    # Normalize timezone information for comparison
                    if pr_created.tzinfo is not None and since_date.tzinfo is None:
                        # Make pr_created timezone-naive like since_date
                        pr_created = pr_created.replace(tzinfo=None)
                    elif pr_created.tzinfo is None and since_date.tzinfo is not None:
                        # Make pr_created timezone-aware like since_date (assume UTC)
                        from datetime import timezone
                        pr_created = pr_created.replace(tzinfo=timezone.utc)
                    
                    if pr_created >= since_date:
                        filtered_prs.append(pr)
                    else:
                        # Since PRs are sorted by creation date desc, we can stop here
                        self.logger.debug(f"Reached PRs older than {since_date}, stopping pagination")
                        all_prs.extend(filtered_prs)
                        return all_prs
                
                all_prs.extend(filtered_prs)
                
                # If we got fewer PRs than requested per page, we've reached the end
                if len(prs_data) < per_page:
                    break
                
                page += 1
                
            except GitHubAPIError:
                raise
            except Exception as e:
                raise GitHubAPIError(f"Failed to fetch pull requests: {e}")
        
        self.logger.info(f"Fetched {len(all_prs)} pull requests from {owner}/{repo}")
        return all_prs
    
    def get_pr_details(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """
        Fetch detailed information for a specific pull request.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            Detailed pull request data dictionary
            
        Raises:
            GitHubAPIError: If API request fails or PR not found
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
        
        try:
            pr_data = self._make_api_request(url)
            self.logger.debug(f"Fetched details for PR #{pr_number} in {owner}/{repo}")
            return pr_data
            
        except GitHubAPIError as e:
            if "404" in str(e):
                raise GitHubAPIError(f"Pull request #{pr_number} not found in {owner}/{repo}")
            raise
    
    def _calculate_date_range(self, months_back: int = 1) -> datetime:
        """
        Calculate the start date for fetching data based on months back from now.
        
        Args:
            months_back: Number of months to go back from current date. Defaults to 1
            
        Returns:
            DateTime object representing the start date for data fetching
        """
        from dateutil.relativedelta import relativedelta
        
        now = datetime.now().replace(microsecond=0)
        start_date = now - relativedelta(months=months_back)
        
        self.logger.debug(f"Calculated date range: {start_date} to {now} ({months_back} month(s) back)")
        return start_date
    
    def get_pr_reviews(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch all reviews for a specific pull request.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            List of review data dictionaries
            
        Raises:
            GitHubAPIError: If API request fails
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        
        try:
            reviews = self._make_api_request(url)
            self.logger.debug(f"Fetched {len(reviews)} reviews for PR #{pr_number} in {owner}/{repo}")
            return reviews
            
        except GitHubAPIError as e:
            if "404" in str(e):
                self.logger.warning(f"PR #{pr_number} not found in {owner}/{repo}")
                return []
            raise
    
    def get_pr_review_comments(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch all review comments for a specific pull request.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            List of review comment data dictionaries
            
        Raises:
            GitHubAPIError: If API request fails
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/comments"
        
        try:
            comments = self._make_api_request(url)
            self.logger.debug(f"Fetched {len(comments)} review comments for PR #{pr_number} in {owner}/{repo}")
            return comments
            
        except GitHubAPIError as e:
            if "404" in str(e):
                self.logger.warning(f"PR #{pr_number} not found in {owner}/{repo}")
                return []
            raise
    
    def get_pr_timeline(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch the complete timeline of events for a pull request.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            List of timeline event dictionaries
            
        Raises:
            GitHubAPIError: If API request fails
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/timeline"
        
        # Use specific Accept header for timeline API
        headers = {'Accept': 'application/vnd.github.mockingbird-preview'}
        
        try:
            timeline = []
            page = 1
            per_page = 100
            
            while True:
                params = {'per_page': per_page, 'page': page}
                
                # Make request with specific headers for timeline API
                response = self.session.get(url, params=params, headers={**self.session.headers, **headers})
                
                # Handle response manually for this special case
                self._handle_rate_limit(response)
                
                if response.status_code == 401:
                    raise GitHubAuthenticationError("GitHub token is invalid or expired")
                elif response.status_code == 404:
                    self.logger.warning(f"PR #{pr_number} not found in {owner}/{repo}")
                    return []
                elif response.status_code != 200:
                    raise GitHubAPIError(f"Timeline API request failed: {response.status_code} - {response.text}")
                
                page_events = response.json()
                
                if not page_events:
                    break
                
                timeline.extend(page_events)
                
                # If we got fewer events than requested per page, we've reached the end
                if len(page_events) < per_page:
                    break
                
                page += 1
            
            self.logger.debug(f"Fetched {len(timeline)} timeline events for PR #{pr_number} in {owner}/{repo}")
            return timeline
            
        except GitHubAPIError:
            raise
        except Exception as e:
            raise GitHubAPIError(f"Failed to fetch PR timeline: {e}")
    
    def get_pr_merge_info(self, owner: str, repo: str, pr_number: int) -> Optional[Dict[str, Any]]:
        """
        Get merge information for a pull request if it has been merged.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            Dictionary containing merge information, or None if not merged
            
        Raises:
            GitHubAPIError: If API request fails
        """
        try:
            # First get the PR details to check if it's merged
            pr_data = self.get_pr_details(owner, repo, pr_number)
            
            if not pr_data.get('merged_at'):
                self.logger.debug(f"PR #{pr_number} in {owner}/{repo} has not been merged")
                return None
            
            # Extract merge information from PR data
            merge_info = {
                'merged_at': pr_data['merged_at'],
                'merged_by': pr_data.get('merged_by'),
                'merge_commit_sha': pr_data.get('merge_commit_sha'),
                'merged': pr_data.get('merged', False)
            }
            
            self.logger.debug(f"Retrieved merge info for PR #{pr_number} in {owner}/{repo}")
            return merge_info
            
        except GitHubAPIError:
            raise
        except Exception as e:
            raise GitHubAPIError(f"Failed to fetch merge information: {e}")
    
    def get_pr_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Fetch all commits in a pull request with their timestamps.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            List of commit data dictionaries with timestamps
            
        Raises:
            GitHubAPIError: If API request fails
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        
        try:
            commits = []
            page = 1
            per_page = 100
            
            while True:
                params = {'per_page': per_page, 'page': page}
                page_commits = self._make_api_request(url, params)
                
                if not page_commits:
                    break
                
                commits.extend(page_commits)
                
                # If we got fewer commits than requested per page, we've reached the end
                if len(page_commits) < per_page:
                    break
                
                page += 1
            
            self.logger.debug(f"Fetched {len(commits)} commits for PR #{pr_number} in {owner}/{repo}")
            return commits
            
        except GitHubAPIError as e:
            if "404" in str(e):
                self.logger.warning(f"PR #{pr_number} not found in {owner}/{repo}")
                return []
            raise
        except Exception as e:
            raise GitHubAPIError(f"Failed to fetch PR commits: {e}")
    
    def get_pr_requested_reviewers(self, owner: str, repo: str, pr_number: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get current requested reviewers for a specific pull request.
        
        This method fetches the current requested reviewers and teams for a PR,
        returning both individual reviewers and teams in separate lists.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            Dictionary with 'users' and 'teams' keys containing requested reviewer data
            
        Raises:
            GitHubAPIError: If API request fails
        """
        if not owner or not repo:
            raise GitHubAPIError("Repository owner and name are required")
        
        if not pr_number or pr_number <= 0:
            raise GitHubAPIError(f"Invalid PR number: {pr_number}")
        
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/requested_reviewers"
        
        try:
            reviewer_data = self._make_api_request(url)
            
            users = reviewer_data.get('users', [])
            teams = reviewer_data.get('teams', [])
            
            self.logger.debug(f"Fetched {len(users)} user reviewers and {len(teams)} team reviewers for PR #{pr_number}")
            
            return {
                'users': users,
                'teams': teams
            }
            
        except GitHubAPIError as e:
            if "404" in str(e):
                self.logger.debug(f"No requested reviewers found for PR #{pr_number} (or PR not found)")
                return {'users': [], 'teams': []}
            raise GitHubAPIError(f"Failed to fetch requested reviewers for PR #{pr_number}: {e}")
    
    def get_team_members(self, org: str, team_slug: str) -> List[Dict[str, Any]]:
        """
        Get members of a GitHub team by organization and team slug.
        
        Args:
            org: Organization name
            team_slug: Team slug (URL-friendly team name)
            
        Returns:
            List of team member user data dictionaries
            
        Raises:
            GitHubAPIError: If API request fails
        """
        if not org or not team_slug:
            raise GitHubAPIError("Organization name and team slug are required")
        
        url = f"{self.BASE_URL}/orgs/{org}/teams/{team_slug}/members"
        
        try:
            members = self._make_api_request(url)
            self.logger.debug(f"Fetched {len(members)} members for team {org}/{team_slug}")
            return members
            
        except GitHubAPIError as e:
            if "404" in str(e):
                self.logger.warning(f"Team {org}/{team_slug} not found or not accessible")
                return []
            raise GitHubAPIError(f"Failed to fetch team members for {org}/{team_slug}: {e}")
    
    def expand_team_reviewers(self, teams: List[Dict[str, Any]], org: str) -> List[Dict[str, Any]]:
        """
        Expand team reviewer requests to individual team members.
        
        This method takes a list of team objects and returns a list of individual
        user objects representing all members of those teams.
        
        Args:
            teams: List of team dictionaries from requested_teams
            org: Organization name to use for team member lookup
            
        Returns:
            List of individual user dictionaries from all team members
        """
        if not teams:
            return []
        
        if not org:
            self.logger.warning("No organization provided for team expansion, skipping")
            return []
        
        expanded_members = []
        
        for team in teams:
            team_slug = team.get('slug')
            team_name = team.get('name', team_slug)
            
            if not team_slug:
                self.logger.warning(f"Team missing slug field, skipping: {team}")
                continue
                
            try:
                members = self.get_team_members(org, team_slug)
                expanded_members.extend(members)
                self.logger.debug(f"Expanded team '{team_name}' to {len(members)} members")
                
            except Exception as e:
                self.logger.warning(f"Failed to expand team '{team_name}': {e}")
                continue
        
        # Remove duplicates based on user ID
        unique_members = {}
        for member in expanded_members:
            user_id = member.get('id')
            if user_id and user_id not in unique_members:
                unique_members[user_id] = member
        
        unique_list = list(unique_members.values())
        self.logger.debug(f"Team expansion resulted in {len(unique_list)} unique members from {len(teams)} teams")
        
        return unique_list
    
    def extract_reviewer_requests_from_pr(self, pr_data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Extract reviewer request data from a pull request object.
        
        This method handles the extraction of requested_reviewers and requested_teams
        data from PR objects, with proper error handling for missing fields.
        
        Args:
            pr_data: Pull request data dictionary from GitHub API
            
        Returns:
            Dictionary with 'users' and 'teams' keys containing reviewer request data
        """
        if not pr_data or not isinstance(pr_data, dict):
            return {'users': [], 'teams': []}
        
        pr_number = pr_data.get('number', 'unknown')
        
        # Extract requested reviewers (individual users)
        requested_users = pr_data.get('requested_reviewers', [])
        if not isinstance(requested_users, list):
            self.logger.warning(f"PR #{pr_number}: requested_reviewers is not a list, treating as empty")
            requested_users = []
        
        # Extract requested teams
        requested_teams = pr_data.get('requested_teams', [])
        if not isinstance(requested_teams, list):
            self.logger.warning(f"PR #{pr_number}: requested_teams is not a list, treating as empty")
            requested_teams = []
        
        self.logger.debug(f"PR #{pr_number}: Found {len(requested_users)} user reviewers and {len(requested_teams)} team reviewers")
        
        return {
            'users': requested_users,
            'teams': requested_teams
        }


def setup_logging(level: str = "INFO") -> None:
    """
    Configure logging for the GitHub client.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
