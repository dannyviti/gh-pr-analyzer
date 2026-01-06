"""
CSV reporting module for GitHub PR analysis results.

This module provides functionality to export PR lifecycle analysis results
to CSV format with all three timing metrics and detailed PR information.
"""

import csv
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path


class CSVReportError(Exception):
    """Custom exception for CSV reporting related errors."""
    pass


class CSVReporter:
    """
    CSV reporter for GitHub PR lifecycle analysis results.
    
    This class handles the formatting and export of PR analysis data
    to CSV files with proper headers and data formatting.
    """
    
    def __init__(self, output_path: str):
        """
        Initialize CSV reporter with output file path.
        
        Args:
            output_path: Path where the CSV file will be written
            
        Raises:
            CSVReportError: If output path is invalid
        """
        if not output_path:
            raise CSVReportError("Output path is required")
        
        self.output_path = Path(output_path)
        self.logger = logging.getLogger(__name__)
        
        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
    
    def generate_report(self, analysis_results: Dict[str, Any]) -> str:
        """
        Generate CSV report from PR analysis results.
        
        Args:
            analysis_results: Dictionary containing summary and detailed PR analysis
            
        Returns:
            Path to the generated CSV file
            
        Raises:
            CSVReportError: If report generation fails
        """
        if not analysis_results:
            raise CSVReportError("Analysis results are required")
        
        if 'pr_details' not in analysis_results:
            raise CSVReportError("Analysis results must contain 'pr_details'")
        
        pr_details = analysis_results['pr_details']
        summary = analysis_results.get('summary', {})
        
        try:
            # Generate CSV headers
            headers = self._format_csv_headers()
            
            # Format CSV rows
            rows = self._format_csv_rows(pr_details)
            
            # Write CSV file
            with open(self.output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write summary information as comments
                self._write_summary_header(writer, summary)
                
                # Write headers
                writer.writerow(headers)
                
                # Write data rows
                writer.writerows(rows)
            
            self.logger.info(f"Generated CSV report with {len(pr_details)} PRs at {self.output_path}")
            
            return str(self.output_path)
            
        except Exception as e:
            raise CSVReportError(f"Failed to generate CSV report: {e}")
    
    def _format_csv_headers(self) -> List[str]:
        """
        Define CSV column structure with all three timing metrics.
        
        Returns:
            List of CSV column headers
        """
        return [
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
    
    def _format_csv_rows(self, pr_details: List[Dict[str, Any]]) -> List[List[str]]:
        """
        Format PR data rows for CSV output with all three timing metrics.
        
        Args:
            pr_details: List of detailed PR analysis results
            
        Returns:
            List of CSV data rows
        """
        if not pr_details:
            return []
        
        rows = []
        
        for pr in pr_details:
            try:
                row = [
                    str(pr.get('pr_number', '')),
                    self._sanitize_text(pr.get('title', '')),
                    str(pr.get('state', '')),
                    self._format_datetime(pr.get('created_at')),
                    self._format_datetime(pr.get('merged_at')),
                    str(pr.get('repository_name', '')),
                    str(pr.get('pr_creator_github_id', '')),
                    str(pr.get('pr_creator_login', '')),
                    self._format_number(pr.get('time_to_first_review_hours')),
                    self._format_number(pr.get('time_to_merge_hours')),
                    self._format_number(pr.get('commit_lead_time_hours')),
                    str(pr.get('has_reviews', False)),
                    str(pr.get('review_count', 0)),
                    str(pr.get('comment_count', 0)),
                    str(pr.get('commit_count', 0)),
                    str(pr.get('is_merged', False))
                ]
                
                rows.append(row)
                
            except Exception as e:
                self.logger.warning(f"Failed to format PR #{pr.get('pr_number', 'unknown')}: {e}")
                continue
        
        return rows
    
    def _write_summary_header(self, writer: csv.writer, summary: Dict[str, Any]) -> None:
        """
        Write summary information as CSV comments.
        
        Args:
            writer: CSV writer instance
            summary: Summary statistics dictionary
        """
        if not summary:
            return
        
        # Write summary as comments
        writer.writerow([f"# GitHub PR Lifecycle Analysis Report - Generated {datetime.now().isoformat()}"])
        
        # Include repository name if available
        repository_name = summary.get('repository_name', '')
        if repository_name:
            writer.writerow([f"# Repository: {repository_name}"])
        
        writer.writerow([f"# Total PRs Analyzed: {summary.get('total_prs_analyzed', 0)}"])
        writer.writerow([f"# Merged PRs: {summary.get('merged_prs', 0)}"])
        writer.writerow([f"# Reviewed PRs: {summary.get('reviewed_prs', 0)}"])
        
        # Add average metrics if available
        avg_review = summary.get('avg_time_to_first_review')
        if avg_review is not None:
            writer.writerow([f"# Average Time to First Review: {avg_review} hours"])
        
        avg_merge = summary.get('avg_time_to_merge')
        if avg_merge is not None:
            writer.writerow([f"# Average Time to Merge: {avg_merge} hours"])
        
        avg_commit_lead = summary.get('avg_commit_lead_time')
        if avg_commit_lead is not None:
            writer.writerow([f"# Average Commit Lead Time: {avg_commit_lead} hours"])
        
        writer.writerow([])  # Empty line before headers
    
    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text for CSV output by handling special characters.
        
        Args:
            text: Text to sanitize
            
        Returns:
            Sanitized text safe for CSV
        """
        if not text:
            return ""
        
        # Replace newlines and tabs with spaces
        sanitized = str(text).replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        
        # Remove excessive whitespace
        sanitized = ' '.join(sanitized.split())
        
        # Truncate very long titles
        if len(sanitized) > 200:
            sanitized = sanitized[:197] + "..."
        
        return sanitized
    
    def _format_datetime(self, datetime_str: Optional[str]) -> str:
        """
        Format datetime string for CSV output.
        
        Args:
            datetime_str: ISO datetime string or None
            
        Returns:
            Formatted datetime string or empty string
        """
        if not datetime_str:
            return ""
        
        try:
            # Parse and reformat to ensure consistent format
            if datetime_str.endswith('Z'):
                datetime_str = datetime_str.replace('Z', '+00:00')
            
            dt = datetime.fromisoformat(datetime_str)
            # Format as YYYY-MM-DD HH:MM:SS UTC
            return dt.strftime('%Y-%m-%d %H:%M:%S UTC')
            
        except (ValueError, TypeError):
            # Return original string if parsing fails
            return str(datetime_str)
    
    def _format_number(self, number: Optional[float]) -> str:
        """
        Format numeric values for CSV output.
        
        Args:
            number: Numeric value or None
            
        Returns:
            Formatted number string or empty string
        """
        if number is None:
            return ""
        
        try:
            # Format to 2 decimal places
            return f"{float(number):.2f}"
        except (ValueError, TypeError):
            return ""
    
    def get_output_path(self) -> str:
        """
        Get the output file path.
        
        Returns:
            Output file path as string
        """
        return str(self.output_path)
    
    def generate_reviewer_report(self, reviewer_summary: Dict[str, Any]) -> str:
        """
        Generate CSV report from reviewer workload analysis results.
        
        Args:
            reviewer_summary: Dictionary containing reviewer workload analysis data
            
        Returns:
            Path to the generated CSV file
            
        Raises:
            CSVReportError: If report generation fails
        """
        if not reviewer_summary:
            raise CSVReportError("Reviewer summary is required")
        
        if 'reviewer_data' not in reviewer_summary:
            raise CSVReportError("Reviewer summary must contain 'reviewer_data'")
        
        reviewer_data = reviewer_summary['reviewer_data']
        metadata = reviewer_summary.get('metadata', {})
        statistics = reviewer_summary.get('statistics', {})
        overload_analysis = reviewer_summary.get('overload_analysis', {})
        distribution_analysis = reviewer_summary.get('distribution_analysis', {})
        
        try:
            # Generate reviewer CSV headers
            headers = self._format_reviewer_csv_headers()
            
            # Format reviewer CSV rows
            rows = self._format_reviewer_csv_rows(reviewer_data, overload_analysis)
            
            # Write CSV file
            with open(self.output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write reviewer summary information as comments
                self._write_reviewer_summary_header(writer, metadata, statistics, distribution_analysis)
                
                # Write headers
                writer.writerow(headers)
                
                # Write data rows
                writer.writerows(rows)
            
            self.logger.info(f"Generated reviewer CSV report with {len(reviewer_data)} reviewers at {self.output_path}")
            
            return str(self.output_path)
            
        except Exception as e:
            raise CSVReportError(f"Failed to generate reviewer CSV report: {e}")
    
    def _format_reviewer_csv_headers(self) -> List[str]:
        """
        Define CSV column structure for reviewer workload analysis.
        
        Returns:
            List of CSV column headers for reviewer data
        """
        return [
            'reviewer_login',
            'reviewer_name',
            'reviewer_type',
            'total_requests',
            'pr_numbers',
            'request_sources',
            'first_request_date',
            'last_request_date',
            'avg_requests_per_month',
            'percentage_of_total',
            'workload_status',
            'workload_category'
        ]
    
    def _format_reviewer_csv_rows(self, reviewer_data: Dict[str, Dict[str, Any]], 
                                  overload_analysis: Dict[str, List[str]]) -> List[List[str]]:
        """
        Format reviewer data rows for CSV output.
        
        Args:
            reviewer_data: Dictionary of reviewer request data
            overload_analysis: Dictionary containing overload categorization
            
        Returns:
            List of CSV data rows
        """
        if not reviewer_data:
            return []
        
        rows = []
        total_requests = sum(data.get('total_requests', 0) for data in reviewer_data.values())
        
        # Create lookup for workload status
        workload_status = {}
        for status, reviewers in overload_analysis.items():
            for reviewer in reviewers:
                workload_status[reviewer] = status
        
        # Calculate months for average calculation (estimate from date range)
        months_analyzed = 1  # Default to 1 month if we can't determine
        
        for login, data in reviewer_data.items():
            try:
                requests = data.get('total_requests', 0)
                
                # Calculate average requests per month
                avg_per_month = requests / months_analyzed
                
                # Calculate percentage of total requests
                percentage = (requests / total_requests * 100) if total_requests > 0 else 0.0
                
                # Determine reviewer type (individual or team)
                reviewer_type = 'team' if login.startswith('team:') else 'user'
                
                # Format PR numbers list
                pr_numbers_str = ', '.join(str(pr) for pr in data.get('pr_numbers', []))
                
                # Format request sources
                sources_str = ', '.join(data.get('request_sources', []))
                
                # Get workload status
                status = workload_status.get(login, 'NORMAL')
                
                # Determine workload category based on status
                if status == 'OVERLOADED':
                    category = 'Overloaded'
                elif status == 'HIGH':
                    category = 'High Load'
                else:
                    category = 'Normal Load'
                
                row = [
                    str(login),
                    self._sanitize_text(data.get('name', login)),
                    reviewer_type,
                    str(requests),
                    pr_numbers_str,
                    sources_str,
                    self._format_datetime(data.get('first_request_date')),
                    self._format_datetime(data.get('last_request_date')),
                    self._format_number(avg_per_month),
                    self._format_number(percentage),
                    status,
                    category
                ]
                
                rows.append(row)
                
            except Exception as e:
                self.logger.warning(f"Failed to format reviewer {login}: {e}")
                continue
        
        # Sort rows by total requests (descending)
        rows.sort(key=lambda x: int(x[3]) if x[3].isdigit() else 0, reverse=True)
        
        return rows
    
    def _write_reviewer_summary_header(self, writer: csv.writer, metadata: Dict[str, Any], 
                                     statistics: Dict[str, Any], distribution: Dict[str, Any]) -> None:
        """
        Write reviewer analysis summary information as CSV comments.
        
        Args:
            writer: CSV writer instance
            metadata: Analysis metadata dictionary
            statistics: Statistical summary dictionary
            distribution: Distribution analysis dictionary
        """
        # Write header information
        writer.writerow([f"# GitHub PR Reviewer Workload Analysis Report - Generated {datetime.now().isoformat()}"])
        
        # Metadata information
        if metadata:
            total_prs = metadata.get('total_prs_analyzed', 0)
            threshold = metadata.get('overload_threshold', 10)
            include_teams = metadata.get('include_teams', False)
            org_name = metadata.get('org_name', 'N/A')
            
            writer.writerow([f"# Total PRs Analyzed: {total_prs}"])
            writer.writerow([f"# Overload Threshold: {threshold} requests"])
            writer.writerow([f"# Team Analysis Enabled: {include_teams}"])
            if include_teams:
                writer.writerow([f"# Organization: {org_name}"])
        
        # Statistical summary
        if statistics:
            total_reviewers = statistics.get('total_reviewers', 0)
            total_requests = statistics.get('total_requests', 0)
            mean_requests = statistics.get('mean_requests', 0)
            median_requests = statistics.get('median_requests', 0)
            
            writer.writerow([f"# Total Reviewers: {total_reviewers}"])
            writer.writerow([f"# Total Review Requests: {total_requests}"])
            writer.writerow([f"# Average Requests per Reviewer: {mean_requests:.2f}"])
            writer.writerow([f"# Median Requests per Reviewer: {median_requests:.2f}"])
        
        # Distribution insights
        if distribution:
            concentration = distribution.get('concentration_ratio', 0)
            gini = distribution.get('gini_coefficient', 0)
            diversity = distribution.get('reviewer_diversity_score', 0)
            
            writer.writerow([f"# Top 20% Reviewers Handle: {concentration:.1%} of requests"])
            writer.writerow([f"# Gini Coefficient (inequality): {gini:.3f}"])
            writer.writerow([f"# Diversity Score: {diversity:.3f}"])
        
        writer.writerow([])  # Empty line before headers
    
    def validate_analysis_results(self, analysis_results: Dict[str, Any]) -> bool:
        """
        Validate analysis results structure for CSV generation.
        
        Args:
            analysis_results: Analysis results dictionary to validate
            
        Returns:
            True if results are valid for CSV generation
            
        Raises:
            CSVReportError: If validation fails
        """
        if not isinstance(analysis_results, dict):
            raise CSVReportError("Analysis results must be a dictionary")
        
        if 'pr_details' not in analysis_results:
            raise CSVReportError("Analysis results must contain 'pr_details' key")
        
        pr_details = analysis_results['pr_details']
        if not isinstance(pr_details, list):
            raise CSVReportError("'pr_details' must be a list")
        
        # Validate required fields in each PR detail
        required_fields = ['pr_number', 'repository_name', 'pr_creator_github_id', 'pr_creator_login']
        for i, pr in enumerate(pr_details):
            if not isinstance(pr, dict):
                raise CSVReportError(f"PR detail at index {i} must be a dictionary")
            
            for field in required_fields:
                if field not in pr:
                    raise CSVReportError(f"PR detail at index {i} missing required field: {field}")
        
        return True
    
    def validate_reviewer_summary(self, reviewer_summary: Dict[str, Any]) -> bool:
        """
        Validate reviewer summary structure for CSV generation.
        
        Args:
            reviewer_summary: Reviewer summary dictionary to validate
            
        Returns:
            True if summary is valid for CSV generation
            
        Raises:
            CSVReportError: If validation fails
        """
        if not isinstance(reviewer_summary, dict):
            raise CSVReportError("Reviewer summary must be a dictionary")
        
        # Check for required top-level keys
        required_keys = ['reviewer_data', 'metadata', 'statistics', 'overload_analysis']
        for key in required_keys:
            if key not in reviewer_summary:
                raise CSVReportError(f"Reviewer summary must contain '{key}' key")
        
        reviewer_data = reviewer_summary['reviewer_data']
        if not isinstance(reviewer_data, dict):
            raise CSVReportError("'reviewer_data' must be a dictionary")
        
        # Validate required fields in each reviewer entry
        required_reviewer_fields = ['login', 'total_requests', 'pr_numbers']
        for login, data in reviewer_data.items():
            if not isinstance(data, dict):
                raise CSVReportError(f"Reviewer data for '{login}' must be a dictionary")
            
            for field in required_reviewer_fields:
                if field not in data:
                    raise CSVReportError(f"Reviewer data for '{login}' missing required field: {field}")
        
        # Validate metadata structure
        metadata = reviewer_summary['metadata']
        if not isinstance(metadata, dict):
            raise CSVReportError("'metadata' must be a dictionary")
        
        # Validate statistics structure  
        statistics = reviewer_summary['statistics']
        if not isinstance(statistics, dict):
            raise CSVReportError("'statistics' must be a dictionary")
        
        # Validate overload analysis structure
        overload_analysis = reviewer_summary['overload_analysis']
        if not isinstance(overload_analysis, dict):
            raise CSVReportError("'overload_analysis' must be a dictionary")
        
        expected_categories = ['OVERLOADED', 'HIGH', 'NORMAL']
        for category in expected_categories:
            if category not in overload_analysis:
                raise CSVReportError(f"'overload_analysis' must contain '{category}' key")
            
            if not isinstance(overload_analysis[category], list):
                raise CSVReportError(f"'overload_analysis[{category}]' must be a list")
        
        return True
    
    def append_tracking_row(self, tracking_file: str, period: str, repository: str,
                           pr_summary: Dict[str, Any], reviewer_summary: Dict[str, Any]) -> str:
        """
        Append a summary row to a tracking CSV for time-series analysis.
        
        Creates the file with headers if it doesn't exist, then appends a single
        row with summary metrics for the specified period.
        
        Args:
            tracking_file: Path to the tracking CSV file
            period: Analysis period (e.g., "2024-11" or "Last 3 months")
            repository: Repository name (owner/repo)
            pr_summary: PR lifecycle analysis summary dictionary
            reviewer_summary: Reviewer workload analysis summary dictionary
            
        Returns:
            Path to the tracking CSV file
            
        Raises:
            CSVReportError: If appending fails
        """
        tracking_path = Path(tracking_file)
        
        # Define tracking CSV headers
        headers = [
            'period',
            'repository',
            'analysis_date',
            'total_prs',
            'merged_prs',
            'reviewed_prs',
            'avg_time_to_first_review_hours',
            'avg_time_to_merge_hours',
            'avg_commit_lead_time_hours',
            'total_review_requests',
            'unique_reviewers',
            'overloaded_count',
            'top_10_overloaded'
        ]
        
        try:
            # Extract PR summary metrics
            pr_stats = pr_summary.get('summary', {})
            total_prs = pr_stats.get('total_prs_analyzed', 0)
            merged_prs = pr_stats.get('merged_prs', 0)
            reviewed_prs = pr_stats.get('reviewed_prs', 0)
            avg_first_review = pr_stats.get('avg_time_to_first_review')
            avg_merge = pr_stats.get('avg_time_to_merge')
            avg_lead_time = pr_stats.get('avg_commit_lead_time')
            
            # Extract reviewer summary metrics
            reviewer_stats = reviewer_summary.get('statistics', {})
            reviewer_metadata = reviewer_summary.get('metadata', {})
            overload_analysis = reviewer_summary.get('overload_analysis', {})
            reviewer_data = reviewer_summary.get('reviewer_data', {})
            
            total_requests = reviewer_stats.get('total_requests', 0)
            unique_reviewers = reviewer_stats.get('total_reviewers', 0)
            
            # Get overloaded reviewers
            overloaded_list = overload_analysis.get('OVERLOADED', [])
            overloaded_count = len(overloaded_list)
            
            # Format top 10 overloaded reviewers with counts
            top_10_parts = []
            for reviewer in overloaded_list[:10]:
                rev_data = reviewer_data.get(reviewer, {})
                count = rev_data.get('total_requests', 0)
                top_10_parts.append(f"{reviewer}:{count}")
            top_10_str = ','.join(top_10_parts)
            
            # Build the data row
            row = [
                period,
                repository,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                str(total_prs),
                str(merged_prs),
                str(reviewed_prs),
                self._format_number(avg_first_review),
                self._format_number(avg_merge),
                self._format_number(avg_lead_time),
                str(total_requests),
                str(unique_reviewers),
                str(overloaded_count),
                top_10_str
            ]
            
            # Check if file exists to determine if we need headers
            file_exists = tracking_path.exists()
            
            # Ensure parent directory exists
            tracking_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Append to CSV (create with headers if new)
            with open(tracking_path, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                if not file_exists:
                    writer.writerow(headers)
                    self.logger.info(f"Created tracking CSV with headers: {tracking_file}")
                
                writer.writerow(row)
            
            self.logger.info(f"Appended tracking row for {period} to {tracking_file}")
            return str(tracking_path)
            
        except Exception as e:
            raise CSVReportError(f"Failed to append tracking row: {e}")
    
    def append_reviewer_tracking_rows(self, tracking_file: str, period: str, repository: str,
                                      reviewer_summary: Dict[str, Any], top_n: int = 20) -> str:
        """
        Append reviewer-level tracking rows to a CSV for individual reviewer trend analysis.
        
        Creates one row per reviewer (top N by request count) for the specified period.
        This enables tracking individual reviewer workload trends over time in Excel.
        
        Args:
            tracking_file: Path to the reviewer tracking CSV file
            period: Analysis period (e.g., "2024-11")
            repository: Repository name (owner/repo)
            reviewer_summary: Reviewer workload analysis summary dictionary
            top_n: Number of top reviewers to track (default: 20)
            
        Returns:
            Path to the tracking CSV file
            
        Raises:
            CSVReportError: If appending fails
        """
        tracking_path = Path(tracking_file)
        
        # Define reviewer tracking CSV headers
        headers = [
            'period',
            'repository',
            'reviewer',
            'requests',
            'workload_status',
            'percentage_of_total'
        ]
        
        try:
            # Extract reviewer data
            reviewer_data = reviewer_summary.get('reviewer_data', {})
            overload_analysis = reviewer_summary.get('overload_analysis', {})
            statistics = reviewer_summary.get('statistics', {})
            
            total_requests = statistics.get('total_requests', 0)
            
            # Create workload status lookup
            workload_status = {}
            for status, reviewers in overload_analysis.items():
                for reviewer in reviewers:
                    workload_status[reviewer] = status
            
            # Sort reviewers by request count (descending) and take top N
            sorted_reviewers = sorted(
                reviewer_data.items(),
                key=lambda x: x[1].get('total_requests', 0),
                reverse=True
            )[:top_n]
            
            # Check if file exists to determine if we need headers
            file_exists = tracking_path.exists()
            
            # Ensure parent directory exists
            tracking_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Build rows for each reviewer
            rows = []
            for reviewer_login, data in sorted_reviewers:
                requests = data.get('total_requests', 0)
                status = workload_status.get(reviewer_login, 'NORMAL')
                percentage = (requests / total_requests * 100) if total_requests > 0 else 0.0
                
                rows.append([
                    period,
                    repository,
                    reviewer_login,
                    str(requests),
                    status,
                    self._format_number(percentage)
                ])
            
            # Append to CSV (create with headers if new)
            with open(tracking_path, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                if not file_exists:
                    writer.writerow(headers)
                    self.logger.info(f"Created reviewer tracking CSV with headers: {tracking_file}")
                
                writer.writerows(rows)
            
            self.logger.info(f"Appended {len(rows)} reviewer tracking rows for {period} to {tracking_file}")
            return str(tracking_path)
            
        except Exception as e:
            raise CSVReportError(f"Failed to append reviewer tracking rows: {e}")