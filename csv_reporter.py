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
