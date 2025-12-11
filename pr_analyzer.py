"""
Pull request analysis module for GitHub PR lifecycle time analysis.

This module provides functionality to analyze pull requests and calculate
timing metrics for review, merge, and commit lead times.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dateutil.relativedelta import relativedelta

from github_client import GitHubClient, GitHubAPIError


class PRAnalysisError(Exception):
    """Custom exception for PR analysis related errors."""
    pass


class PRAnalyzer:
    """
    Analyzer for GitHub pull request data and lifecycle timing calculations.
    
    This class orchestrates the collection of pull request data from GitHub
    and performs filtering and analysis operations on the collected data.
    """
    
    def __init__(self, github_client: GitHubClient):
        """
        Initialize PR analyzer with a GitHub client.
        
        Args:
            github_client: GitHubClient instance for API interactions
            
        Raises:
            PRAnalysisError: If github_client is None or invalid
        """
        if not github_client:
            raise PRAnalysisError("GitHubClient is required")
        
        if not isinstance(github_client, GitHubClient):
            raise PRAnalysisError("Invalid GitHubClient instance provided")
        
        self.github_client = github_client
        self.logger = logging.getLogger(__name__)
    
    def fetch_monthly_prs(self, owner: str, repo: str, months_back: int = 1) -> List[Dict[str, Any]]:
        """
        Orchestrate PR data collection for the specified time period.
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            months_back: Number of months to look back from current date. Defaults to 1
            
        Returns:
            List of pull request data dictionaries filtered to the specified time period
            
        Raises:
            PRAnalysisError: If data collection fails
            GitHubAPIError: If GitHub API requests fail
        """
        if not owner or not repo:
            raise PRAnalysisError("Repository owner and name are required")
        
        if months_back < 1:
            raise PRAnalysisError("months_back must be at least 1")
        
        try:
            # Calculate the date range for PR fetching
            since_date = self.github_client._calculate_date_range(months_back)
            
            self.logger.info(f"Fetching PRs from {owner}/{repo} for last {months_back} month(s)")
            
            # Fetch all PRs from the specified date range
            prs = self.github_client.get_pull_requests(owner, repo, since_date)
            
            # Additional filtering to ensure we only get PRs from the exact time period
            filtered_prs = self._filter_prs_by_date(prs, since_date)
            
            self.logger.info(f"Successfully collected {len(filtered_prs)} PRs from {owner}/{repo}")
            
            return filtered_prs
            
        except GitHubAPIError:
            # Re-raise GitHub API errors without wrapping
            raise
        except Exception as e:
            raise PRAnalysisError(f"Failed to fetch monthly PRs: {e}")
    
    def fetch_specific_month_prs(self, owner: str, repo: str, 
                                  start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """
        Fetch PR data for a specific date range (typically a single month).
        
        Args:
            owner: Repository owner (user or organization)
            repo: Repository name
            start_date: Start of the date range (inclusive)
            end_date: End of the date range (exclusive)
            
        Returns:
            List of pull request data dictionaries filtered to the specified date range
            
        Raises:
            PRAnalysisError: If data collection fails
            GitHubAPIError: If GitHub API requests fail
        """
        if not owner or not repo:
            raise PRAnalysisError("Repository owner and name are required")
        
        if start_date >= end_date:
            raise PRAnalysisError("start_date must be before end_date")
        
        try:
            self.logger.info(f"Fetching PRs from {owner}/{repo} for {start_date.strftime('%Y-%m')}")
            
            # Fetch all PRs from the start date
            prs = self.github_client.get_pull_requests(owner, repo, start_date)
            
            # Filter to only include PRs within the specific date range
            filtered_prs = self._filter_prs_by_date(prs, start_date, end_date)
            
            self.logger.info(f"Successfully collected {len(filtered_prs)} PRs from {owner}/{repo} for {start_date.strftime('%Y-%m')}")
            
            return filtered_prs
            
        except GitHubAPIError:
            # Re-raise GitHub API errors without wrapping
            raise
        except Exception as e:
            raise PRAnalysisError(f"Failed to fetch PRs for specific month: {e}")
    
    def _filter_prs_by_date(self, prs: List[Dict[str, Any]], since_date: datetime, 
                            until_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Filter pull requests to only include those created within the specified date range.
        
        Args:
            prs: List of pull request data dictionaries
            since_date: Only include PRs created on or after this date
            until_date: Only include PRs created before this date (optional, exclusive)
            
        Returns:
            List of pull requests filtered by creation date
            
        Raises:
            PRAnalysisError: If date filtering fails due to invalid data
        """
        if not prs:
            self.logger.debug("No PRs to filter")
            return []
        
        filtered_prs = []
        
        try:
            for pr in prs:
                if not pr.get('created_at'):
                    self.logger.warning(f"PR #{pr.get('number', 'unknown')} missing created_at field")
                    continue
                
                # Parse the creation date from GitHub API format
                try:
                    created_at_str = pr['created_at']
                    # Handle both 'Z' and timezone offset formats
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str.replace('Z', '+00:00')
                    
                    pr_created = datetime.fromisoformat(created_at_str)
                    
                    # Remove timezone info for comparison (both dates should be timezone-naive or both timezone-aware)
                    if pr_created.tzinfo is not None and since_date.tzinfo is None:
                        pr_created = pr_created.replace(tzinfo=None)
                    
                    # Check if PR is within date range
                    if pr_created >= since_date:
                        # If until_date is specified, also check upper bound
                        if until_date is not None:
                            if pr_created < until_date:
                                filtered_prs.append(pr)
                                self.logger.debug(f"Included PR #{pr.get('number')} created at {pr_created}")
                            else:
                                self.logger.debug(f"Filtered out PR #{pr.get('number')} created at {pr_created} (after {until_date})")
                        else:
                            filtered_prs.append(pr)
                            self.logger.debug(f"Included PR #{pr.get('number')} created at {pr_created}")
                    else:
                        self.logger.debug(f"Filtered out PR #{pr.get('number')} created at {pr_created} (before {since_date})")
                        
                except ValueError as e:
                    self.logger.warning(f"Failed to parse date for PR #{pr.get('number', 'unknown')}: {e}")
                    continue
            
            date_range_str = f"from {since_date}"
            if until_date:
                date_range_str += f" to {until_date}"
            self.logger.info(f"Filtered {len(prs)} PRs down to {len(filtered_prs)} within date range ({date_range_str})")
            
        except Exception as e:
            raise PRAnalysisError(f"Failed to filter PRs by date: {e}")
        
        return filtered_prs
    
    def get_pr_summary_stats(self, prs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate summary statistics for a list of pull requests.
        
        Args:
            prs: List of pull request data dictionaries
            
        Returns:
            Dictionary containing summary statistics
        """
        if not prs:
            return {
                'total_prs': 0,
                'open_prs': 0,
                'closed_prs': 0,
                'merged_prs': 0,
                'draft_prs': 0
            }
        
        stats = {
            'total_prs': len(prs),
            'open_prs': 0,
            'closed_prs': 0,
            'merged_prs': 0,
            'draft_prs': 0,
            'earliest_pr': None,
            'latest_pr': None
        }
        
        earliest_date = None
        latest_date = None
        
        for pr in prs:
            # Count by state
            state = pr.get('state', '').lower()
            if state == 'open':
                stats['open_prs'] += 1
            elif state == 'closed':
                stats['closed_prs'] += 1
            
            # Count merged PRs (merged is a subset of closed)
            if pr.get('merged_at'):
                stats['merged_prs'] += 1
            
            # Count draft PRs
            if pr.get('draft', False):
                stats['draft_prs'] += 1
            
            # Track date range
            try:
                created_at_str = pr.get('created_at', '')
                if created_at_str:
                    if created_at_str.endswith('Z'):
                        created_at_str = created_at_str.replace('Z', '+00:00')
                    
                    pr_created = datetime.fromisoformat(created_at_str)
                    if pr_created.tzinfo is not None:
                        pr_created = pr_created.replace(tzinfo=None)
                    
                    if earliest_date is None or pr_created < earliest_date:
                        earliest_date = pr_created
                        stats['earliest_pr'] = pr.get('number')
                    
                    if latest_date is None or pr_created > latest_date:
                        latest_date = pr_created
                        stats['latest_pr'] = pr.get('number')
                        
            except (ValueError, TypeError):
                continue
        
        if earliest_date:
            stats['date_range_start'] = earliest_date.isoformat()
        if latest_date:
            stats['date_range_end'] = latest_date.isoformat()
        
        self.logger.debug(f"Generated stats for {stats['total_prs']} PRs: "
                         f"{stats['merged_prs']} merged, {stats['open_prs']} open, "
                         f"{stats['draft_prs']} draft")
        
        return stats
    
    def analyze_pr_lifecycle_times(self, prs: List[Dict[str, Any]], owner: str, repo: str, 
                                  batch_size: int = 10, batch_delay: float = 0.1,
                                  max_retries: int = 3) -> Dict[str, Any]:
        """
        Calculate review, merge, and commit lead times for all pull requests.
        
        Args:
            prs: List of pull request data dictionaries
            owner: Repository owner (user or organization)
            repo: Repository name
            batch_size: Number of PRs to process in each batch (for rate limiting)
            batch_delay: Delay in seconds between batches
            max_retries: Maximum number of API request retries
            
        Returns:
            Dictionary containing summary statistics and detailed analysis results
            
        Raises:
            PRAnalysisError: If analysis fails
        """
        if not prs:
            self.logger.info("No PRs to analyze")
            return {'summary': {'total_prs_analyzed': 0}, 'pr_details': []}
        
        if not owner or not repo:
            raise PRAnalysisError("Repository owner and name are required for analysis")
        
        analysis_results = []
        
        self.logger.info(f"Analyzing lifecycle times for {len(prs)} PRs from {owner}/{repo}")
        
        successful_analyses = 0
        failed_analyses = 0
        
        for pr in prs:
            pr_number = None
            try:
                # Enhanced PR data validation
                if not isinstance(pr, dict):
                    self.logger.error(f"PR data is not a dictionary: {type(pr)}, skipping")
                    failed_analyses += 1
                    continue
                
                pr_number = pr.get('number')
                if not pr_number:
                    self.logger.warning("PR missing number field, skipping")
                    failed_analyses += 1
                    continue
                
                # Validate required PR fields
                required_fields = ['title', 'state', 'created_at']
                missing_fields = [field for field in required_fields if field not in pr]
                if missing_fields:
                    self.logger.warning(f"PR #{pr_number} missing required fields: {missing_fields}")
                
                self.logger.debug(f"Analyzing PR #{pr_number}")
                
                # Initialize default values for API data
                reviews = []
                review_comments = []
                timeline = []
                merge_info = None
                commits = []
                
                # Fetch additional data with individual error handling
                try:
                    reviews = self.github_client.get_pr_reviews(owner, repo, pr_number) or []
                except Exception as e:
                    self.logger.warning(f"Failed to fetch reviews for PR #{pr_number}: {e}")
                
                try:
                    review_comments = self.github_client.get_pr_review_comments(owner, repo, pr_number) or []
                except Exception as e:
                    self.logger.warning(f"Failed to fetch review comments for PR #{pr_number}: {e}")
                
                try:
                    timeline = self.github_client.get_pr_timeline(owner, repo, pr_number) or []
                except Exception as e:
                    self.logger.warning(f"Failed to fetch timeline for PR #{pr_number}: {e}")
                
                try:
                    merge_info = self.github_client.get_pr_merge_info(owner, repo, pr_number)
                except Exception as e:
                    self.logger.warning(f"Failed to fetch merge info for PR #{pr_number}: {e}")
                
                try:
                    commits = self.github_client.get_pr_commits(owner, repo, pr_number) or []
                except Exception as e:
                    self.logger.warning(f"Failed to fetch commits for PR #{pr_number}: {e}")
                
                # Combine all review activities
                all_activities = reviews + review_comments + timeline
                
                # Calculate timing metrics with error handling
                time_to_first_review = self._calculate_time_to_first_review(pr, all_activities)
                time_to_merge = self._calculate_time_to_merge(pr, merge_info)
                commit_lead_time = self._calculate_commit_lead_time(pr, commits, merge_info)
                
                # Extract PR creator information with enhanced error handling
                pr_creator_github_id, pr_creator_login = self._extract_pr_creator_data(pr)
                
                # Validate repository name consistency
                repository_name = f"{owner}/{repo}"
                if not owner or not repo:
                    self.logger.error(f"Invalid repository name format for PR #{pr_number}: {repository_name}")
                
                # Create analysis result with defaults for missing data
                result = {
                    'pr_number': pr_number,
                    'title': pr.get('title', 'Unknown Title'),
                    'state': pr.get('state', 'unknown'),
                    'created_at': pr.get('created_at'),
                    'merged_at': merge_info.get('merged_at') if merge_info else None,
                    'repository_name': repository_name,
                    'pr_creator_github_id': pr_creator_github_id,
                    'pr_creator_login': pr_creator_login,
                    'time_to_first_review_hours': time_to_first_review,
                    'time_to_merge_hours': time_to_merge,
                    'commit_lead_time_hours': commit_lead_time,
                    'has_reviews': len(reviews) > 0,
                    'review_count': len(reviews),
                    'comment_count': len(review_comments),
                    'commit_count': len(commits),
                    'is_merged': merge_info is not None
                }
                
                analysis_results.append(result)
                successful_analyses += 1
                
            except Exception as e:
                failed_analyses += 1
                pr_ref = f"#{pr_number}" if pr_number else "unknown"
                self.logger.error(f"Failed to analyze PR {pr_ref}: {e}", exc_info=True)
                continue
        
        # Log analysis statistics
        total_attempted = successful_analyses + failed_analyses
        self.logger.info(f"Analysis complete: {successful_analyses}/{total_attempted} PRs processed successfully")
        if failed_analyses > 0:
            self.logger.warning(f"{failed_analyses} PRs failed analysis but pipeline continued")
        
        return self._format_analysis_results(analysis_results)
    
    def _calculate_time_to_first_review(self, pr: Dict[str, Any], activities: List[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate time from PR creation to first review activity.
        
        Args:
            pr: Pull request data dictionary
            activities: List of all review activities (reviews, comments, timeline events)
            
        Returns:
            Time to first review in hours, or None if no review activity found
        """
        if not pr.get('created_at'):
            return None
        
        try:
            # Parse PR creation time
            created_at_str = pr['created_at']
            if created_at_str.endswith('Z'):
                created_at_str = created_at_str.replace('Z', '+00:00')
            
            pr_created = datetime.fromisoformat(created_at_str)
            if pr_created.tzinfo is not None:
                pr_created = pr_created.replace(tzinfo=None)
            
            # Find first review activity
            first_review = self._get_first_review_activity(activities)
            
            if not first_review:
                self.logger.debug(f"No review activity found for PR #{pr.get('number')}")
                return None
            
            # Parse first review time
            review_time_str = first_review.get('created_at') or first_review.get('submitted_at')
            if not review_time_str:
                return None
            
            if review_time_str.endswith('Z'):
                review_time_str = review_time_str.replace('Z', '+00:00')
            
            review_time = datetime.fromisoformat(review_time_str)
            if review_time.tzinfo is not None:
                review_time = review_time.replace(tzinfo=None)
            
            # Calculate time difference in hours
            time_diff = review_time - pr_created
            hours = time_diff.total_seconds() / 3600
            
            self.logger.debug(f"PR #{pr.get('number')} first review after {hours:.2f} hours")
            
            return round(hours, 2)
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate review time for PR #{pr.get('number', 'unknown')}: {e}")
            return None
    
    def _calculate_time_to_merge(self, pr: Dict[str, Any], merge_info: Optional[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate time from PR creation to merge.
        
        Args:
            pr: Pull request data dictionary
            merge_info: Merge information dictionary, or None if not merged
            
        Returns:
            Time to merge in hours, or None if not merged
        """
        if not merge_info or not merge_info.get('merged_at'):
            return None
        
        if not pr.get('created_at'):
            return None
        
        try:
            # Parse PR creation time
            created_at_str = pr['created_at']
            if created_at_str.endswith('Z'):
                created_at_str = created_at_str.replace('Z', '+00:00')
            
            pr_created = datetime.fromisoformat(created_at_str)
            if pr_created.tzinfo is not None:
                pr_created = pr_created.replace(tzinfo=None)
            
            # Parse merge time
            merged_at_str = merge_info['merged_at']
            if merged_at_str.endswith('Z'):
                merged_at_str = merged_at_str.replace('Z', '+00:00')
            
            merged_at = datetime.fromisoformat(merged_at_str)
            if merged_at.tzinfo is not None:
                merged_at = merged_at.replace(tzinfo=None)
            
            # Calculate time difference in hours
            time_diff = merged_at - pr_created
            hours = time_diff.total_seconds() / 3600
            
            self.logger.debug(f"PR #{pr.get('number')} merged after {hours:.2f} hours")
            
            return round(hours, 2)
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate merge time for PR #{pr.get('number', 'unknown')}: {e}")
            return None
    
    def _calculate_commit_lead_time(self, pr: Dict[str, Any], commits: List[Dict[str, Any]], 
                                   merge_info: Optional[Dict[str, Any]]) -> Optional[float]:
        """
        Calculate time from first commit to merge (commit lead time).
        
        Args:
            pr: Pull request data dictionary
            commits: List of commit data dictionaries
            merge_info: Merge information dictionary, or None if not merged
            
        Returns:
            Commit lead time in hours, or None if not merged or no commits
        """
        if not merge_info or not merge_info.get('merged_at'):
            return None
        
        if not commits:
            return None
        
        try:
            # Find first commit timestamp
            first_commit_time = self._get_first_commit_timestamp(commits)
            if not first_commit_time:
                return None
            
            # Parse merge time
            merged_at_str = merge_info['merged_at']
            if merged_at_str.endswith('Z'):
                merged_at_str = merged_at_str.replace('Z', '+00:00')
            
            merged_at = datetime.fromisoformat(merged_at_str)
            if merged_at.tzinfo is not None:
                merged_at = merged_at.replace(tzinfo=None)
            
            # Calculate time difference in hours
            time_diff = merged_at - first_commit_time
            hours = time_diff.total_seconds() / 3600
            
            self.logger.debug(f"PR #{pr.get('number')} commit lead time: {hours:.2f} hours")
            
            return round(hours, 2)
            
        except Exception as e:
            self.logger.warning(f"Failed to calculate commit lead time for PR #{pr.get('number', 'unknown')}: {e}")
            return None
    
    def _get_first_review_activity(self, activities: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Find the first review activity from a list of activities.
        
        Args:
            activities: List of review activities (reviews, comments, timeline events)
            
        Returns:
            Dictionary of first review activity, or None if none found
        """
        if not activities:
            return None
        
        review_activities = []
        
        for activity in activities:
            # Check if this is a review-related activity
            activity_type = activity.get('event') or activity.get('state')
            
            # Include reviews, review comments, and specific timeline events
            if (activity_type in ['APPROVED', 'CHANGES_REQUESTED', 'COMMENTED', 'reviewed'] or
                activity.get('review_id') or  # Review comments have review_id
                'diff_hunk' in activity):  # Review comments have diff_hunk
                
                timestamp_field = activity.get('created_at') or activity.get('submitted_at')
                if timestamp_field:
                    try:
                        # Parse timestamp for sorting
                        timestamp_str = timestamp_field
                        if timestamp_str.endswith('Z'):
                            timestamp_str = timestamp_str.replace('Z', '+00:00')
                        
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if timestamp.tzinfo is not None:
                            timestamp = timestamp.replace(tzinfo=None)
                        
                        review_activities.append((timestamp, activity))
                        
                    except ValueError:
                        continue
        
        if not review_activities:
            return None
        
        # Sort by timestamp and return the earliest
        review_activities.sort(key=lambda x: x[0])
        return review_activities[0][1]
    
    def _get_first_commit_timestamp(self, commits: List[Dict[str, Any]]) -> Optional[datetime]:
        """
        Find the timestamp of the first commit in the PR.
        
        Args:
            commits: List of commit data dictionaries
            
        Returns:
            DateTime of the first commit, or None if no valid commits found
        """
        if not commits:
            return None
        
        commit_times = []
        
        for commit in commits:
            # Try to get commit timestamp from commit.author.date or commit.committer.date
            commit_data = commit.get('commit', {})
            
            # Prefer author date over committer date
            author_date = commit_data.get('author', {}).get('date')
            committer_date = commit_data.get('committer', {}).get('date')
            
            # Try author date first, then committer date if author fails
            for timestamp_str in [author_date, committer_date]:
                if timestamp_str:
                    try:
                        if timestamp_str.endswith('Z'):
                            timestamp_str = timestamp_str.replace('Z', '+00:00')
                        
                        timestamp = datetime.fromisoformat(timestamp_str)
                        if timestamp.tzinfo is not None:
                            timestamp = timestamp.replace(tzinfo=None)
                        
                        commit_times.append(timestamp)
                        break  # Successfully parsed, move to next commit
                        
                    except ValueError:
                        continue  # Try next timestamp option
        
        if not commit_times:
            return None
        
        # Return the earliest commit time
        return min(commit_times)
    
    def _extract_pr_creator_data(self, pr: Dict[str, Any]) -> Tuple[str, str]:
        """
        Extract PR creator GitHub ID and login from PR data with enhanced error handling.
        
        Args:
            pr: Pull request data dictionary from GitHub API
            
        Returns:
            Tuple of (github_id, login) - both as strings, empty if not available
        """
        pr_number = pr.get('number', 'unknown')
        
        try:
            # Handle case where PR data is None or not a dict
            if not isinstance(pr, dict):
                self.logger.error(f"PR #{pr_number} data is not a dictionary: {type(pr)}")
                return '', ''
            
            user_data = pr.get('user')
            
            # Handle various user data states
            if user_data is None:
                self.logger.warning(f"PR #{pr_number} has null user data - possibly deleted user account")
                return '', ''
            
            if not isinstance(user_data, dict):
                self.logger.warning(f"PR #{pr_number} user data is not a dictionary: {type(user_data)}")
                return '', ''
            
            if not user_data:  # Empty dict
                self.logger.warning(f"PR #{pr_number} has empty user data dictionary")
                return '', ''
            
            # Extract GitHub ID with type validation
            github_id = user_data.get('id')
            github_id_str = ''
            
            if github_id is not None:
                try:
                    # Validate that ID is numeric
                    github_id_int = int(github_id)
                    if github_id_int <= 0:
                        self.logger.warning(f"PR #{pr_number} has invalid GitHub ID (non-positive): {github_id}")
                        github_id_str = ''
                    else:
                        github_id_str = str(github_id_int)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"PR #{pr_number} has non-numeric GitHub ID: {github_id} ({e})")
                    github_id_str = ''
            else:
                self.logger.info(f"PR #{pr_number} missing GitHub user ID")
            
            # Extract login with validation
            login = user_data.get('login', '')
            if login and not isinstance(login, str):
                self.logger.warning(f"PR #{pr_number} login is not a string: {type(login)}")
                login = str(login) if login else ''
            
            # Log data extraction issues
            if not github_id_str and not login:
                self.logger.warning(f"PR #{pr_number} has user object but missing both ID and login")
            elif not github_id_str:
                self.logger.info(f"PR #{pr_number} missing GitHub ID but has login: {login}")
            elif not login:
                self.logger.info(f"PR #{pr_number} missing login but has GitHub ID: {github_id_str}")
            else:
                self.logger.debug(f"PR #{pr_number} created by user {login} (ID: {github_id_str})")
            
            return github_id_str, login
            
        except Exception as e:
            self.logger.error(f"Unexpected error extracting creator data for PR #{pr_number}: {e}", exc_info=True)
            return '', ''
    
    def _format_analysis_results(self, analysis: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Format and structure the analysis results with all three timing metrics.
        
        Args:
            analysis: List of raw analysis result dictionaries
            
        Returns:
            Dictionary with summary statistics and detailed PR analysis
        """
        if not analysis:
            return {'summary': {'total_prs_analyzed': 0}, 'pr_details': []}
        
        # Add summary statistics to the results
        total_prs = len(analysis)
        merged_prs = [pr for pr in analysis if pr['is_merged']]
        reviewed_prs = [pr for pr in analysis if pr['has_reviews']]
        
        # Extract repository name from first PR (all should have same repo)
        repository_name = analysis[0].get('repository_name', '') if analysis else ''
        
        summary_stats = {
            'total_prs_analyzed': total_prs,
            'merged_prs': len(merged_prs),
            'reviewed_prs': len(reviewed_prs),
            'repository_name': repository_name,
            'avg_time_to_first_review': None,
            'avg_time_to_merge': None,
            'avg_commit_lead_time': None
        }
        
        # Calculate averages for PRs with data
        review_times = [pr['time_to_first_review_hours'] for pr in analysis 
                       if pr['time_to_first_review_hours'] is not None]
        if review_times:
            summary_stats['avg_time_to_first_review'] = round(sum(review_times) / len(review_times), 2)
        
        merge_times = [pr['time_to_merge_hours'] for pr in analysis 
                      if pr['time_to_merge_hours'] is not None]
        if merge_times:
            summary_stats['avg_time_to_merge'] = round(sum(merge_times) / len(merge_times), 2)
        
        lead_times = [pr['commit_lead_time_hours'] for pr in analysis 
                     if pr['commit_lead_time_hours'] is not None]
        if lead_times:
            summary_stats['avg_commit_lead_time'] = round(sum(lead_times) / len(lead_times), 2)
        
        self.logger.info(f"Analysis complete: {total_prs} PRs, {len(merged_prs)} merged, {len(reviewed_prs)} reviewed")
        
        return {
            'summary': summary_stats,
            'pr_details': analysis
        }
