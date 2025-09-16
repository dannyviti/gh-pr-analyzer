"""
Reviewer workload analysis module.

This module provides functionality to analyze reviewer workloads across pull requests,
identify potential overload situations, and generate statistical insights about
reviewer request distribution patterns.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict, Counter
import statistics
from datetime import datetime, timedelta


class ReviewerWorkloadAnalyzer:
    """
    Analyzes reviewer workload patterns across pull requests.
    
    This class provides methods to aggregate reviewer request data from multiple PRs,
    calculate statistical metrics, detect overload patterns, and analyze reviewer
    distribution to identify bottlenecks and imbalances.
    """
    
    def __init__(self, default_threshold: int = 10):
        """
        Initialize the reviewer workload analyzer.
        
        Args:
            default_threshold: Default threshold for considering a reviewer "overloaded"
                              (number of review requests)
        """
        self.default_threshold = default_threshold
        self.logger = logging.getLogger(__name__)
        
        # Internal state for analysis results
        self._reviewer_data = {}
        self._analysis_metadata = {}
    
    def aggregate_reviewer_requests(self, prs: List[Dict[str, Any]], 
                                   include_teams: bool = True,
                                   org_name: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate reviewer request data across multiple pull requests.
        
        This method processes a list of PRs and counts how many times each reviewer
        (individual or team member) has been requested to review.
        
        Args:
            prs: List of pull request data dictionaries
            include_teams: Whether to include team-based reviewer analysis
            org_name: Organization name for team member expansion (required if include_teams=True)
            
        Returns:
            Dictionary mapping reviewer login to aggregated request data:
            {
                'reviewer_login': {
                    'login': str,
                    'name': str,
                    'total_requests': int,
                    'pr_numbers': List[int],
                    'request_sources': List[str],  # 'individual' or 'team:<team_name>'
                    'first_request_date': str,
                    'last_request_date': str
                }
            }
        """
        if not prs:
            self.logger.warning("No PRs provided for reviewer request aggregation")
            return {}
        
        reviewer_requests = defaultdict(lambda: {
            'login': '',
            'name': '',
            'total_requests': 0,
            'pr_numbers': [],
            'request_sources': [],
            'first_request_date': None,
            'last_request_date': None
        })
        
        self.logger.info(f"Aggregating reviewer requests from {len(prs)} PRs")
        
        for pr in prs:
            pr_number = pr.get('number')
            pr_created_at = pr.get('created_at')
            
            if not pr_number:
                self.logger.warning("PR missing number field, skipping")
                continue
            
            # Process requested_reviewers (individual users)
            requested_reviewers = pr.get('requested_reviewers', [])
            if isinstance(requested_reviewers, list):
                for reviewer in requested_reviewers:
                    if not isinstance(reviewer, dict):
                        continue
                    
                    login = reviewer.get('login')
                    if not login:
                        continue
                    
                    # Update reviewer data
                    reviewer_data = reviewer_requests[login]
                    reviewer_data['login'] = login
                    reviewer_data['name'] = reviewer.get('name') or reviewer.get('display_name') or login
                    reviewer_data['total_requests'] += 1
                    reviewer_data['pr_numbers'].append(pr_number)
                    reviewer_data['request_sources'].append('individual')
                    
                    # Track date range
                    if pr_created_at:
                        if not reviewer_data['first_request_date'] or pr_created_at < reviewer_data['first_request_date']:
                            reviewer_data['first_request_date'] = pr_created_at
                        if not reviewer_data['last_request_date'] or pr_created_at > reviewer_data['last_request_date']:
                            reviewer_data['last_request_date'] = pr_created_at
            
            # Process requested_teams (if enabled)
            if include_teams:
                requested_teams = pr.get('requested_teams', [])
                if isinstance(requested_teams, list):
                    for team in requested_teams:
                        if not isinstance(team, dict):
                            continue
                        
                        team_name = team.get('name') or team.get('slug')
                        if not team_name:
                            continue
                        
                        # For team requests, we would need to expand to individual members
                        # This is a simplified version - real implementation would use GitHubClient
                        # to expand team members using expand_team_reviewers()
                        
                        # Note: In a real implementation, this would call:
                        # github_client.expand_team_reviewers([team], org_name)
                        # For now, we'll just track the team request as a placeholder
                        
                        team_login = f"team:{team_name}"
                        reviewer_data = reviewer_requests[team_login]
                        reviewer_data['login'] = team_login
                        reviewer_data['name'] = f"Team: {team_name}"
                        reviewer_data['total_requests'] += 1
                        reviewer_data['pr_numbers'].append(pr_number)
                        reviewer_data['request_sources'].append(f'team:{team_name}')
                        
                        # Track date range
                        if pr_created_at:
                            if not reviewer_data['first_request_date'] or pr_created_at < reviewer_data['first_request_date']:
                                reviewer_data['first_request_date'] = pr_created_at
                            if not reviewer_data['last_request_date'] or pr_created_at > reviewer_data['last_request_date']:
                                reviewer_data['last_request_date'] = pr_created_at
        
        # Convert defaultdict to regular dict and clean up data
        final_data = {}
        for login, data in reviewer_requests.items():
            if data['total_requests'] > 0:
                # Remove duplicates from pr_numbers
                data['pr_numbers'] = list(set(data['pr_numbers']))
                final_data[login] = dict(data)
        
        self.logger.info(f"Aggregated requests for {len(final_data)} reviewers")
        self._reviewer_data = final_data
        
        return final_data
    
    def detect_reviewer_overload(self, reviewer_data: Dict[str, Dict[str, Any]], 
                                threshold: Optional[int] = None) -> Dict[str, List[str]]:
        """
        Detect potentially overloaded reviewers based on request counts.
        
        Args:
            reviewer_data: Aggregated reviewer request data from aggregate_reviewer_requests()
            threshold: Request count threshold for overload detection (uses default if None)
            
        Returns:
            Dictionary categorizing reviewers by overload status:
            {
                'OVERLOADED': List[str],  # Reviewers exceeding threshold
                'HIGH': List[str],        # Reviewers at 75-100% of threshold  
                'NORMAL': List[str]       # Reviewers below 75% of threshold
            }
        """
        if not reviewer_data:
            return {'OVERLOADED': [], 'HIGH': [], 'NORMAL': []}
        
        threshold = threshold or self.default_threshold
        high_threshold = int(threshold * 0.75)
        
        categorized = {
            'OVERLOADED': [],
            'HIGH': [],
            'NORMAL': []
        }
        
        for login, data in reviewer_data.items():
            request_count = data.get('total_requests', 0)
            
            if request_count >= threshold:
                categorized['OVERLOADED'].append(login)
            elif request_count >= high_threshold:
                categorized['HIGH'].append(login)
            else:
                categorized['NORMAL'].append(login)
        
        self.logger.info(
            f"Overload detection (threshold={threshold}): "
            f"{len(categorized['OVERLOADED'])} overloaded, "
            f"{len(categorized['HIGH'])} high, "
            f"{len(categorized['NORMAL'])} normal"
        )
        
        return categorized
    
    def calculate_reviewer_statistics(self, reviewer_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate statistical metrics for reviewer request distribution.
        
        Args:
            reviewer_data: Aggregated reviewer request data
            
        Returns:
            Dictionary containing statistical metrics:
            {
                'total_reviewers': int,
                'total_requests': int,
                'mean_requests': float,
                'median_requests': float,
                'std_dev_requests': float,
                'min_requests': int,
                'max_requests': int,
                'percentile_75': float,
                'percentile_90': float,
                'percentile_95': float
            }
        """
        if not reviewer_data:
            return {
                'total_reviewers': 0,
                'total_requests': 0,
                'mean_requests': 0.0,
                'median_requests': 0.0,
                'std_dev_requests': 0.0,
                'min_requests': 0,
                'max_requests': 0,
                'percentile_75': 0.0,
                'percentile_90': 0.0,
                'percentile_95': 0.0
            }
        
        request_counts = [data.get('total_requests', 0) for data in reviewer_data.values()]
        total_requests = sum(request_counts)
        
        stats = {
            'total_reviewers': len(reviewer_data),
            'total_requests': total_requests,
            'mean_requests': statistics.mean(request_counts),
            'median_requests': statistics.median(request_counts),
            'min_requests': min(request_counts),
            'max_requests': max(request_counts),
        }
        
        # Calculate standard deviation (handle single data point case)
        if len(request_counts) > 1:
            stats['std_dev_requests'] = statistics.stdev(request_counts)
        else:
            stats['std_dev_requests'] = 0.0
        
        # Calculate percentiles
        if request_counts:
            stats['percentile_75'] = self._calculate_percentile(request_counts, 75)
            stats['percentile_90'] = self._calculate_percentile(request_counts, 90)
            stats['percentile_95'] = self._calculate_percentile(request_counts, 95)
        else:
            stats['percentile_75'] = 0.0
            stats['percentile_90'] = 0.0
            stats['percentile_95'] = 0.0
        
        self.logger.debug(f"Calculated reviewer statistics: {stats}")
        return stats
    
    def analyze_reviewer_distribution(self, reviewer_data: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze patterns in reviewer request distribution.
        
        This method identifies concentration patterns, diversity metrics, and
        potential bottlenecks in reviewer assignments.
        
        Args:
            reviewer_data: Aggregated reviewer request data
            
        Returns:
            Dictionary containing distribution analysis:
            {
                'concentration_ratio': float,     # % of requests handled by top 20% reviewers
                'gini_coefficient': float,        # Inequality measure (0=equal, 1=max inequality)
                'top_reviewers': List[Dict],      # Top 10 most requested reviewers
                'underutilized_reviewers': List[Dict],  # Reviewers with very low request counts
                'reviewer_diversity_score': float     # Measure of request distribution evenness
            }
        """
        if not reviewer_data:
            return {
                'concentration_ratio': 0.0,
                'gini_coefficient': 0.0,
                'top_reviewers': [],
                'underutilized_reviewers': [],
                'reviewer_diversity_score': 0.0
            }
        
        # Sort reviewers by request count (descending)
        sorted_reviewers = sorted(
            reviewer_data.items(),
            key=lambda x: x[1].get('total_requests', 0),
            reverse=True
        )
        
        request_counts = [data[1].get('total_requests', 0) for data in sorted_reviewers]
        total_requests = sum(request_counts)
        
        # Calculate concentration ratio (requests handled by top 20% of reviewers)
        top_20_percent_count = max(1, len(sorted_reviewers) // 5)
        top_20_percent_requests = sum(request_counts[:top_20_percent_count])
        concentration_ratio = top_20_percent_requests / total_requests if total_requests > 0 else 0.0
        
        # Calculate Gini coefficient for inequality measurement
        gini_coefficient = self._calculate_gini_coefficient(request_counts)
        
        # Identify top reviewers (top 10)
        top_reviewers = []
        for i, (login, data) in enumerate(sorted_reviewers[:10]):
            percentage = (data.get('total_requests', 0) / total_requests * 100) if total_requests > 0 else 0.0
            top_reviewers.append({
                'login': login,
                'name': data.get('name', login),
                'total_requests': data.get('total_requests', 0),
                'percentage_of_total': round(percentage, 2)
            })
        
        # Identify underutilized reviewers (bottom 25% or those with <= 2 requests)
        avg_requests = total_requests / len(reviewer_data) if reviewer_data else 0
        underutilized_threshold = max(2, avg_requests * 0.25)
        
        underutilized_reviewers = []
        for login, data in sorted_reviewers:
            if data.get('total_requests', 0) <= underutilized_threshold:
                underutilized_reviewers.append({
                    'login': login,
                    'name': data.get('name', login),
                    'total_requests': data.get('total_requests', 0)
                })
        
        # Calculate diversity score (1 / Gini coefficient, capped at 1.0)
        reviewer_diversity_score = min(1.0, (1.0 - gini_coefficient)) if gini_coefficient < 1.0 else 0.0
        
        analysis = {
            'concentration_ratio': round(concentration_ratio, 3),
            'gini_coefficient': round(gini_coefficient, 3),
            'top_reviewers': top_reviewers,
            'underutilized_reviewers': underutilized_reviewers,
            'reviewer_diversity_score': round(reviewer_diversity_score, 3)
        }
        
        self.logger.info(
            f"Distribution analysis: {len(top_reviewers)} top reviewers, "
            f"{len(underutilized_reviewers)} underutilized, "
            f"concentration ratio: {analysis['concentration_ratio']:.1%}"
        )
        
        return analysis
    
    def _calculate_percentile(self, data: List[float], percentile: float) -> float:
        """Calculate the specified percentile of a dataset."""
        if not data:
            return 0.0
        
        sorted_data = sorted(data)
        n = len(sorted_data)
        
        if percentile == 100:
            return float(sorted_data[-1])
        
        # Use linear interpolation method (R-6/R-7 method)
        # This matches common statistical implementations
        h = (percentile / 100) * (n - 1)
        
        if h <= 0:
            return float(sorted_data[0])
        elif h >= n - 1:
            return float(sorted_data[-1])
        else:
            # Linear interpolation between adjacent values
            lower_idx = int(h)
            upper_idx = lower_idx + 1
            weight = h - lower_idx
            
            return float(sorted_data[lower_idx] * (1 - weight) + sorted_data[upper_idx] * weight)
    
    def _calculate_gini_coefficient(self, values: List[float]) -> float:
        """
        Calculate the Gini coefficient for measuring inequality.
        
        Returns value between 0 (perfect equality) and 1 (maximum inequality).
        """
        if not values or len(values) == 1:
            return 0.0
        
        # Sort values in ascending order
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        # Calculate Gini coefficient using the formula:
        # G = (2 * sum(i * x_i)) / (n * sum(x_i)) - (n + 1) / n
        # where i is the rank and x_i is the value
        
        total_sum = sum(sorted_values)
        if total_sum == 0:
            return 0.0
        
        weighted_sum = sum((i + 1) * value for i, value in enumerate(sorted_values))
        
        gini = (2 * weighted_sum) / (n * total_sum) - (n + 1) / n
        
        # Ensure result is within [0, 1] bounds
        return max(0.0, min(1.0, gini))
    
    def get_reviewer_workload_summary(self, prs: List[Dict[str, Any]], 
                                    threshold: Optional[int] = None,
                                    include_teams: bool = True,
                                    org_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a comprehensive reviewer workload summary.
        
        This method combines all analysis methods to provide a complete overview
        of reviewer workload patterns and potential issues.
        
        Args:
            prs: List of pull request data dictionaries
            threshold: Overload detection threshold (uses default if None)
            include_teams: Whether to include team-based analysis
            org_name: Organization name for team member expansion
            
        Returns:
            Comprehensive summary dictionary containing:
            - Aggregated reviewer data
            - Statistical metrics  
            - Overload categorization
            - Distribution analysis
            - Analysis metadata
        """
        self.logger.info("Generating comprehensive reviewer workload summary")
        
        # Aggregate reviewer request data
        reviewer_data = self.aggregate_reviewer_requests(prs, include_teams, org_name)
        
        # Calculate statistics
        statistics_data = self.calculate_reviewer_statistics(reviewer_data)
        
        # Detect overload
        overload_data = self.detect_reviewer_overload(reviewer_data, threshold)
        
        # Analyze distribution
        distribution_data = self.analyze_reviewer_distribution(reviewer_data)
        
        # Generate metadata
        metadata = {
            'analysis_date': datetime.now().isoformat(),
            'total_prs_analyzed': len(prs),
            'include_teams': include_teams,
            'overload_threshold': threshold or self.default_threshold,
            'org_name': org_name
        }
        
        summary = {
            'metadata': metadata,
            'reviewer_data': reviewer_data,
            'statistics': statistics_data,
            'overload_analysis': overload_data,
            'distribution_analysis': distribution_data
        }
        
        self.logger.info(f"Summary generated for {len(reviewer_data)} reviewers across {len(prs)} PRs")
        return summary
