#!/usr/bin/env python3
"""
GitHub PR Analysis Tool

This tool analyzes GitHub pull requests for:
- PR lifecycle times (default mode):
  * Time from PR creation to first review activity
  * Time from PR creation to merge
  * Time from first commit to merge (commit lead time)
- Reviewer workload analysis (--analyze-reviewers):
  * Reviewer request distribution and overload detection
  * Statistical analysis of reviewer assignments
  * Team-based reviewer analysis and expansion
- Time-series tracking (--tracking-csv):
  * Append summary metrics to a tracking CSV for Excel graphing
  * Track trends over time by running monthly

Usage:
    python github_pr_analyzer.py owner/repo [options]

Environment Variables:
    GITHUB_TOKEN: GitHub personal access token (required)

Examples:
    # PR lifecycle analysis (default) - last N months
    python github_pr_analyzer.py microsoft/vscode
    python github_pr_analyzer.py facebook/react --months 3 --output react_analysis.csv
    
    # PR lifecycle analysis - specific month
    python github_pr_analyzer.py microsoft/vscode --month 2024-11
    
    # Reviewer workload analysis
    python github_pr_analyzer.py kubernetes/kubernetes --analyze-reviewers
    python github_pr_analyzer.py facebook/react --analyze-reviewers --reviewer-threshold 15 --include-teams
    
    # Time-series tracking for Excel
    python github_pr_analyzer.py myorg/myrepo --month 2024-11 --tracking-csv
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from dateutil.relativedelta import relativedelta

from github_client import GitHubClient, GitHubAPIError, GitHubAuthenticationError
from pr_analyzer import PRAnalyzer, PRAnalysisError  
from csv_reporter import CSVReporter, CSVReportError
from reviewer_analyzer import ReviewerWorkloadAnalyzer


def setup_logging(level: str = "INFO", verbose: bool = False) -> None:
    """
    Configure logging for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        verbose: Enable verbose logging output
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Configure format based on verbosity
    if verbose:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    else:
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def check_virtual_environment() -> bool:
    """
    Check if the script is running in a virtual environment.
    
    Returns:
        True if running in a virtual environment, False otherwise
    """
    # Check for common virtual environment indicators
    return (
        hasattr(sys, 'real_prefix') or  # virtualenv
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or  # venv
        os.environ.get('VIRTUAL_ENV') is not None  # environment variable
    )


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    
    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description='Analyze GitHub pull requests for lifecycle times and reviewer workloads',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # PR lifecycle analysis (default) - last N months
  %(prog)s microsoft/vscode
  %(prog)s facebook/react --months 3
  %(prog)s kubernetes/kubernetes --months 6 --output k8s_analysis.csv --verbose
  
  # PR lifecycle analysis - specific month
  %(prog)s microsoft/vscode --month 2024-11
  %(prog)s facebook/react --month 2024-10
  
  # Reviewer workload analysis
  %(prog)s facebook/react --analyze-reviewers
  %(prog)s kubernetes/kubernetes --analyze-reviewers --reviewer-threshold 15
  %(prog)s myorg/myrepo --analyze-reviewers --include-teams --months 6
  %(prog)s myorg/myrepo --analyze-reviewers --month 2024-11
  
  # Time-series tracking (for Excel graphing)
  %(prog)s myorg/myrepo --month 2024-11 --tracking-csv
  %(prog)s myorg/myrepo --month 2024-12 --tracking-csv

Environment Variables:
  GITHUB_TOKEN    GitHub personal access token (required)
        """
    )
    
    parser.add_argument(
        'repository',
        nargs='?',  # Make repository optional
        help='GitHub repository in format owner/repo (e.g., microsoft/vscode)'
    )
    
    parser.add_argument(
        '--months',
        type=int,
        default=1,
        help='Number of months to look back (default: 1)'
    )
    
    parser.add_argument(
        '--month',
        type=str,
        metavar='YYYY-MM',
        help='Specific month to analyze (format: YYYY-MM, e.g., 2024-11). Overrides --months.'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='pr_analysis.csv',
        help='Output CSV file path (default: pr_analysis.csv)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    # Rate limiting options
    parser.add_argument(
        '--batch-size',
        type=int,
        default=10,
        help='Number of PRs to process in each batch (default: 10)'
    )
    
    parser.add_argument(
        '--batch-delay',
        type=float,
        default=0.1,
        help='Delay in seconds between batches (default: 0.1)'
    )
    
    parser.add_argument(
        '--max-retries',
        type=int,
        default=3,
        help='Maximum number of API request retries (default: 3)'
    )
    
    parser.add_argument(
        '--check-rate-limit',
        action='store_true',
        help='Check current GitHub API rate limit status and exit'
    )
    
    parser.add_argument(
        '--get-username',
        type=int,
        metavar='USER_ID',
        help='Translate GitHub user ID to username and exit'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress all output except errors'
    )
    
    parser.add_argument(
        '--tracking-csv',
        action='store_true',
        help='Append summary metrics to a tracking CSV (pr_tracking_<repo>.csv) for time-series analysis'
    )
    
    # Reviewer workload analysis options
    reviewer_group = parser.add_argument_group('reviewer workload analysis')
    
    reviewer_group.add_argument(
        '--analyze-reviewers',
        action='store_true',
        help='Enable reviewer workload analysis mode instead of PR lifecycle analysis'
    )
    
    reviewer_group.add_argument(
        '--reviewer-threshold',
        type=int,
        default=10,
        help='Threshold for detecting overloaded reviewers (default: 10 requests)'
    )
    
    reviewer_group.add_argument(
        '--include-teams',
        action='store_true',
        help='Include team-based reviewer analysis (expands teams to individual members)'
    )
    
    reviewer_group.add_argument(
        '--reviewer-period',
        type=int,
        help='Time period in months for reviewer analysis (defaults to --months value)'
    )
    
    return parser.parse_args()


def validate_repository_name_format(repository: str) -> bool:
    """
    Validate repository name format for consistency.
    
    Args:
        repository: Repository name to validate
        
    Returns:
        True if format is valid, False otherwise
    """
    if not repository:
        return False
    
    # Check for basic owner/repo format
    if '/' not in repository:
        return False
    
    parts = repository.split('/')
    if len(parts) != 2:
        return False
    
    owner, repo = parts
    
    # Check that both parts are non-empty and contain valid characters
    if not owner or not repo:
        return False
    
    # Check for invalid characters (basic validation)
    invalid_chars = set(['..', ' ', '\t', '\n', '\r'])
    for part in parts:
        if any(char in part for char in invalid_chars):
            return False
    
    return True


def validate_inputs(args: argparse.Namespace) -> Tuple[str, str]:
    """
    Validate command-line inputs and extract repository information.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Tuple of (owner, repo) strings
        
    Raises:
        ValueError: If inputs are invalid
    """
    # Validate repository format
    if not validate_repository_name_format(args.repository):
        raise ValueError("Repository must be in format 'owner/repo' with valid characters")
    
    parts = args.repository.split('/')
    
    owner, repo = parts
    
    # Validate repository parts
    if not owner or not repo:
        raise ValueError("Both owner and repository name must be non-empty")
    
    # Validate specific month if provided
    if args.month:
        try:
            start_date, end_date = parse_specific_month(args.month)
            # Check if the month is in the future
            if start_date > datetime.now():
                raise ValueError(f"Cannot analyze future month: {args.month}")
        except ValueError as e:
            raise ValueError(str(e))
    else:
        # Validate months parameter (only if --month not specified)
        if args.months < 1:
            raise ValueError("Months parameter must be at least 1")
        
        if args.months > 24:
            raise ValueError("Months parameter cannot exceed 24 (2 years)")
    
    # Validate reviewer analysis specific parameters
    if hasattr(args, 'analyze_reviewers') and args.analyze_reviewers:
        if args.reviewer_threshold < 1:
            raise ValueError("Reviewer threshold must be at least 1")
        
        if args.reviewer_threshold > 1000:
            raise ValueError("Reviewer threshold cannot exceed 1000")
        
        # Use reviewer_period if specified, otherwise use months
        if args.reviewer_period is not None:
            if args.reviewer_period < 1 or args.reviewer_period > 24:
                raise ValueError("Reviewer period must be between 1 and 24 months")
    
    # Validate output path
    output_path = Path(args.output)
    if output_path.exists() and output_path.is_dir():
        raise ValueError("Output path cannot be a directory")
    
    # Check if output directory is writable
    output_dir = output_path.parent
    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True)
        except PermissionError:
            raise ValueError(f"Cannot create output directory: {output_dir}")
    
    return owner.strip(), repo.strip()


def parse_specific_month(month_str: str) -> Tuple[datetime, datetime]:
    """
    Parse a month string (YYYY-MM) and return the start and end dates for that month.
    
    Args:
        month_str: Month string in YYYY-MM format (e.g., "2024-11")
        
    Returns:
        Tuple of (start_date, end_date) for the specified month
        
    Raises:
        ValueError: If the month string is invalid
    """
    try:
        # Parse the month string
        year, month = month_str.split('-')
        year = int(year)
        month = int(month)
        
        if month < 1 or month > 12:
            raise ValueError(f"Month must be between 1 and 12, got {month}")
        
        if year < 2000 or year > 2100:
            raise ValueError(f"Year must be between 2000 and 2100, got {year}")
        
        # Start of the month (first day at midnight)
        start_date = datetime(year, month, 1, 0, 0, 0)
        
        # End of the month (first day of next month)
        end_date = start_date + relativedelta(months=1)
        
        return start_date, end_date
        
    except ValueError as e:
        if "not enough values to unpack" in str(e) or "invalid literal" in str(e):
            raise ValueError(f"Invalid month format '{month_str}'. Expected YYYY-MM (e.g., 2024-11)")
        raise


def generate_tracking_filename(repo: str) -> str:
    """
    Generate tracking CSV filename based on repository name.
    
    Args:
        repo: Repository name (just the repo part, not owner/repo)
        
    Returns:
        Tracking CSV filename (e.g., pr_tracking_vscode.csv)
    """
    sanitized_repo = sanitize_repository_name_for_filename(repo)
    return f"pr_tracking_{sanitized_repo}.csv"


def generate_reviewer_tracking_filename(repo: str) -> str:
    """
    Generate reviewer tracking CSV filename based on repository name.
    
    Args:
        repo: Repository name (just the repo part, not owner/repo)
        
    Returns:
        Reviewer tracking CSV filename (e.g., pr_tracking_reviewers_vscode.csv)
    """
    sanitized_repo = sanitize_repository_name_for_filename(repo)
    return f"pr_tracking_reviewers_{sanitized_repo}.csv"


def sanitize_repository_name_for_filename(repo_name: str) -> str:
    """
    Sanitize repository name for safe filename usage.
    
    Args:
        repo_name: Repository name in owner/repo format
        
    Returns:
        Sanitized repository name safe for use in filenames
    """
    if not repo_name:
        return "unknown_repo"
    
    # Replace forward slash with underscore
    sanitized = repo_name.replace('/', '_')
    
    # Replace other potentially problematic characters
    sanitized = sanitized.replace('\\', '_')
    sanitized = sanitized.replace(':', '_')
    sanitized = sanitized.replace('*', '_')
    sanitized = sanitized.replace('?', '_')
    sanitized = sanitized.replace('"', '_')
    sanitized = sanitized.replace('<', '_')
    sanitized = sanitized.replace('>', '_')
    sanitized = sanitized.replace('|', '_')
    
    # Remove any remaining whitespace and replace with underscores
    sanitized = '_'.join(sanitized.split())
    
    return sanitized


def generate_auto_filename(owner: str, repo: str, months: int = 1, 
                          specific_month: Optional[str] = None,
                          is_reviewer_analysis: bool = False) -> str:
    """
    Generate automatic filename based on repository name, analysis type, and start date.
    
    Args:
        owner: Repository owner (user or organization)
        repo: Repository name
        months: Number of months to look back (used to calculate start date)
        specific_month: Specific month string (YYYY-MM format) - overrides months if provided
        is_reviewer_analysis: True if generating filename for reviewer analysis
        
    Returns:
        Auto-generated CSV filename with start date (format: prefix_repo_YYYY-MM-DD.csv)
    """
    # Calculate the start date of the analysis period
    if specific_month:
        # Use the specific month as the date string (just YYYY-MM, no day needed)
        date_str = specific_month
    else:
        # Calculate from months back (same logic as _calculate_date_range)
        start_date = datetime.now() - relativedelta(months=months)
        date_str = start_date.strftime("%Y-%m-%d")
    
    if not owner or not repo:
        if is_reviewer_analysis:
            return f"reviewer_analysis_{date_str}.csv"
        else:
            return f"pr_analysis_{date_str}.csv"
    
    # Create repository identifier and sanitize it
    repo_identifier = f"{owner}/{repo}"
    sanitized_repo = sanitize_repository_name_for_filename(repo_identifier)
    
    # Extract just the repo name part for cleaner filename
    repo_part = sanitize_repository_name_for_filename(repo)
    
    if is_reviewer_analysis:
        return f"reviewer_workload_{repo_part}_{date_str}.csv"
    else:
        return f"pr_analysis_{repo_part}_{date_str}.csv"


def print_summary(analysis_results: dict, repository: str, period: str, output_path: str) -> None:
    """
    Print analysis summary to stdout.
    
    Args:
        analysis_results: Dictionary containing analysis results
        repository: Repository name
        period: Analysis period description (e.g., "Last 1 month" or "2024-11")
        output_path: Path to output CSV file
    """
    summary = analysis_results.get('summary', {})
    
    print(f"\nGitHub PR Analysis Results for {repository}")
    print("=" * (35 + len(repository)))
    print(f"Analysis Period: {period}")
    print(f"Output File: {output_path}")
    print()
    
    total = summary.get('total_prs_analyzed', 0)
    merged = summary.get('merged_prs', 0)
    reviewed = summary.get('reviewed_prs', 0)
    
    print(f"📊 Summary Statistics:")
    print(f"  Total PRs Analyzed: {total}")
    print(f"  Merged PRs: {merged} ({merged/total*100:.1f}% of total)" if total > 0 else "  Merged PRs: 0")
    print(f"  Reviewed PRs: {reviewed} ({reviewed/total*100:.1f}% of total)" if total > 0 else "  Reviewed PRs: 0")
    print()
    
    # Timing metrics
    print("⏱️  Average Timing Metrics:")
    
    avg_review = summary.get('avg_time_to_first_review')
    if avg_review is not None:
        days = avg_review / 24
        print(f"  Time to First Review: {avg_review:.1f} hours ({days:.1f} days)")
    else:
        print("  Time to First Review: No data available")
    
    avg_merge = summary.get('avg_time_to_merge')
    if avg_merge is not None:
        days = avg_merge / 24
        print(f"  Time to Merge: {avg_merge:.1f} hours ({days:.1f} days)")
    else:
        print("  Time to Merge: No data available")
    
    avg_lead_time = summary.get('avg_commit_lead_time')
    if avg_lead_time is not None:
        days = avg_lead_time / 24
        print(f"  Commit Lead Time: {avg_lead_time:.1f} hours ({days:.1f} days)")
    else:
        print("  Commit Lead Time: No data available")
    
    print()
    print(f"📄 Detailed results saved to: {output_path}")


def print_reviewer_summary(reviewer_summary: dict, repository: str, period: str, output_path: str) -> None:
    """
    Print reviewer workload analysis summary to stdout.
    
    Args:
        reviewer_summary: Dictionary containing reviewer analysis results
        repository: Repository name  
        period: Analysis period description (e.g., "Last 1 month" or "2024-11")
        output_path: Path to output CSV file
    """
    metadata = reviewer_summary.get('metadata', {})
    statistics = reviewer_summary.get('statistics', {})
    overload_analysis = reviewer_summary.get('overload_analysis', {})
    distribution = reviewer_summary.get('distribution_analysis', {})
    
    print(f"\nGitHub PR Reviewer Analysis Results for {repository}")
    print("=" * (50 + len(repository)))
    print(f"Analysis Period: {period}")
    print(f"Output File: {output_path}")
    print()
    
    # Basic statistics
    total_prs = metadata.get('total_prs_analyzed', 0)
    total_reviewers = statistics.get('total_reviewers', 0)
    total_requests = statistics.get('total_requests', 0)
    threshold = metadata.get('overload_threshold', 10)
    
    print(f"📊 Reviewer Request Statistics:")
    print(f"  Total PRs Analyzed: {total_prs:,}")
    print(f"  Total Review Requests: {total_requests:,}")
    print(f"  Unique Reviewers: {total_reviewers}")
    
    if total_reviewers > 0 and total_requests > 0:
        avg_requests = statistics.get('mean_requests', 0)
        print(f"  Average Requests per Reviewer: {avg_requests:.1f}")
    print()
    
    # Overload analysis
    overloaded = overload_analysis.get('OVERLOADED', [])
    high = overload_analysis.get('HIGH', [])
    normal = overload_analysis.get('NORMAL', [])
    
    if overloaded:
        print(f"⚠️  Potentially Overloaded Reviewers (≥{threshold} requests):")
        for reviewer in overloaded[:5]:  # Show top 5 overloaded reviewers
            reviewer_data = reviewer_summary.get('reviewer_data', {}).get(reviewer, {})
            request_count = reviewer_data.get('total_requests', 0)
            avg_requests = statistics.get('mean_requests', 1)
            percentage = (request_count / avg_requests * 100) if avg_requests > 0 else 0
            print(f"  - {reviewer}: {request_count} requests ({percentage:.0f}% of average)")
        
        if len(overloaded) > 5:
            print(f"  ... and {len(overloaded) - 5} more")
        print()
    
    # Distribution insights
    if distribution:
        concentration = distribution.get('concentration_ratio', 0)
        gini = distribution.get('gini_coefficient', 0)
        diversity = distribution.get('reviewer_diversity_score', 0)
        
        print("📈 Request Distribution:")
        print(f"  Top 20% of reviewers handle {concentration:.1%} of all requests")
        if gini > 0.6:
            print(f"  High inequality in reviewer assignments (Gini: {gini:.2f})")
        elif gini > 0.4:
            print(f"  Moderate inequality in reviewer assignments (Gini: {gini:.2f})")
        else:
            print(f"  Relatively equal reviewer assignment distribution (Gini: {gini:.2f})")
        
        print(f"  Reviewer diversity score: {diversity:.2f} (higher = more balanced)")
        
        # Show underutilized reviewers
        underutilized = distribution.get('underutilized_reviewers', [])
        if underutilized:
            print(f"  {len(underutilized)} reviewers have very low request counts")
        print()
    
    # Summary counts
    print("📊 Workload Categories:")
    print(f"  Normal Load: {len(normal)} reviewers")
    print(f"  High Load: {len(high)} reviewers")
    print(f"  Overloaded: {len(overloaded)} reviewers")
    
    if metadata.get('include_teams'):
        print("  (Analysis includes team-based reviewer requests)")
    
    print()
    print(f"📄 Detailed results saved to: {output_path}")


def main() -> int:
    """
    Main application entry point.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    try:
        # Parse arguments
        args = parse_arguments()
        
        # Check for virtual environment
        if not check_virtual_environment():
            print("⚠️  Warning: This tool requires a virtual environment!")
            print("Please run the following commands to set up a virtual environment:")
            print()
            print("  python3 -m venv venv")
            print("  source venv/bin/activate  # On Windows: venv\\Scripts\\activate")
            print("  pip install -r requirements.txt")
            print()
            print("Then run the tool again.")
            return 1
        
        # Set up logging
        if args.debug:
            log_level = "DEBUG"
        elif args.quiet:
            log_level = "ERROR"
        else:
            log_level = "INFO"
        
        setup_logging(log_level, args.verbose)
        logger = logging.getLogger(__name__)
        
        # Skip validation for utility commands
        if not args.check_rate_limit and not args.get_username:
            if not args.repository:
                print("❌ Error: Repository argument is required unless using --check-rate-limit or --get-username")
                return 1
            
            # Validate inputs
            owner, repo = validate_inputs(args)
        else:
            # Set dummy values for utility commands
            owner, repo = None, None
        
        # Generate auto filename if default output is being used (and not running utility commands)
        if not args.check_rate_limit and not args.get_username and args.output == 'pr_analysis.csv':  # Default value from argument parser
            is_reviewer_mode = getattr(args, 'analyze_reviewers', False)
            # Use reviewer_period if specified for reviewer mode, otherwise use months
            analysis_months_for_filename = args.months
            if is_reviewer_mode and args.reviewer_period:
                analysis_months_for_filename = args.reviewer_period
            # Pass specific_month if provided
            args.output = generate_auto_filename(
                owner, repo, analysis_months_for_filename, 
                specific_month=args.month,
                is_reviewer_analysis=is_reviewer_mode
            )
            logger.info(f"Auto-generated output filename: {args.output}")
        
        if not args.check_rate_limit and not args.get_username:
            analysis_mode = "reviewer workload analysis" if getattr(args, 'analyze_reviewers', False) else "PR lifecycle analysis"
            logger.info(f"Starting GitHub {analysis_mode} for {owner}/{repo}")
            if args.month:
                logger.info(f"Analysis period: {args.month}")
            else:
                logger.info(f"Analysis period: Last {args.months} month{'s' if args.months > 1 else ''}")
            logger.info(f"Output file: {args.output}")
        
        # Initialize GitHub client
        try:
            token = GitHubClient.get_token_from_env()
            github_client = GitHubClient(token)
            github_client.validate_token()
        except GitHubAuthenticationError as e:
            logger.error(f"GitHub authentication failed: {e}")
            print("\n❌ GitHub authentication failed!")
            print("Please ensure GITHUB_TOKEN environment variable is set with a valid token.")
            print("You can create a token at: https://github.com/settings/tokens")
            return 1
        
        # Handle rate limit status check
        if args.check_rate_limit:
            try:
                rate_status = github_client.get_rate_limit_status()
                print("\n📊 GitHub API Rate Limit Status")
                print("=" * 40)
                print(f"Total Limit: {rate_status['limit']:,} requests/hour")
                print(f"Used: {rate_status['used']:,} requests")
                print(f"Remaining: {rate_status['remaining']:,} requests")
                print(f"Reset Time: {rate_status['reset_time']}")
                
                # Calculate percentage used
                if rate_status['limit'] > 0:
                    percentage_used = (rate_status['used'] / rate_status['limit']) * 100
                    print(f"Usage: {percentage_used:.1f}% of limit")
                
                # Provide recommendations
                if rate_status['remaining'] < 100:
                    print("\n⚠️  Warning: Low rate limit remaining!")
                    print("   Consider waiting or using smaller batch sizes.")
                elif rate_status['remaining'] < 500:
                    print("\n💡 Tip: Rate limit is getting low. Consider using --batch-delay.")
                else:
                    print("\n✅ Rate limit status looks good for analysis.")
                
                return 0
                
            except Exception as e:
                logger.error(f"Failed to check rate limit status: {e}")
                print(f"\n❌ Failed to check rate limit status: {e}")
                return 1
        
        # Handle username lookup by user ID
        if args.get_username:
            try:
                user_data = github_client.get_user_by_id(args.get_username)
                username = user_data.get('login', 'Unknown')
                name = user_data.get('name', 'No name set')
                user_type = user_data.get('type', 'Unknown')
                
                print(f"\n👤 GitHub User Information")
                print("=" * 30)
                print(f"User ID: {args.get_username}")
                print(f"Username: {username}")
                print(f"Name: {name}")
                print(f"Type: {user_type}")
                
                if user_data.get('company'):
                    print(f"Company: {user_data.get('company')}")
                if user_data.get('location'):
                    print(f"Location: {user_data.get('location')}")
                if user_data.get('blog'):
                    print(f"Website: {user_data.get('blog')}")
                
                print(f"\n📊 Profile Stats:")
                print(f"Public Repos: {user_data.get('public_repos', 0)}")
                print(f"Followers: {user_data.get('followers', 0)}")
                print(f"Following: {user_data.get('following', 0)}")
                
                return 0
                
            except Exception as e:
                logger.error(f"Failed to get user information: {e}")
                print(f"\n❌ Failed to get user information for ID {args.get_username}: {e}")
                return 1
        
        # Validate repository access
        try:
            repo_info = github_client.get_repository_info(owner, repo)
            logger.info(f"Analyzing repository: {repo_info['full_name']}")
        except GitHubAPIError as e:
            logger.error(f"Repository access failed: {e}")
            print(f"\n❌ Cannot access repository {owner}/{repo}")
            print("Please check that the repository exists and your token has access.")
            return 1
        
        # Initialize PR analyzer
        pr_analyzer = PRAnalyzer(github_client)
        
        # Determine analysis period (use reviewer_period if specified and in reviewer mode)
        analysis_months = args.months
        if getattr(args, 'analyze_reviewers', False) and args.reviewer_period:
            analysis_months = args.reviewer_period
            logger.info(f"Using reviewer-specific analysis period: {analysis_months} month{'s' if analysis_months > 1 else ''}")
        
        # Fetch PRs - either for a specific month or for the last N months
        try:
            if args.month:
                # Specific month mode
                start_date, end_date = parse_specific_month(args.month)
                logger.info(f"Fetching PRs for {args.month}...")
                prs = pr_analyzer.fetch_specific_month_prs(owner, repo, start_date, end_date)
                period_description = args.month
            else:
                # Last N months mode
                logger.info(f"Fetching PRs from last {analysis_months} month{'s' if analysis_months > 1 else ''}...")
                prs = pr_analyzer.fetch_monthly_prs(owner, repo, analysis_months)
                period_description = f"the last {analysis_months} month{'s' if analysis_months > 1 else ''}"
            
            if not prs:
                print(f"\n⚠️  No PRs found in {owner}/{repo} for {period_description}")
                return 0
            
            logger.info(f"Found {len(prs)} PRs to analyze")
            
        except (GitHubAPIError, PRAnalysisError) as e:
            logger.error(f"Failed to fetch PRs: {e}")
            print(f"\n❌ Failed to fetch PRs: {e}")
            return 1
        
        # Determine if we need both analyses (for tracking mode)
        run_pr_analysis = not getattr(args, 'analyze_reviewers', False) or args.tracking_csv
        run_reviewer_analysis = getattr(args, 'analyze_reviewers', False) or args.tracking_csv
        
        pr_analysis_results = None
        reviewer_analysis_results = None
        
        # Run PR lifecycle analysis if needed
        if run_pr_analysis:
            logger.info("Analyzing PR lifecycle times...")
            try:
                pr_analysis_results = pr_analyzer.analyze_pr_lifecycle_times(
                    prs, owner, repo, 
                    batch_size=args.batch_size,
                    batch_delay=args.batch_delay,
                    max_retries=args.max_retries
                )
            except PRAnalysisError as e:
                logger.error(f"PR analysis failed: {e}")
                print(f"\n❌ PR analysis failed: {e}")
                return 1
        
        # Run reviewer workload analysis if needed
        if run_reviewer_analysis:
            logger.info("Analyzing reviewer workload patterns...")
            
            try:
                # Initialize reviewer analyzer
                reviewer_analyzer = ReviewerWorkloadAnalyzer(default_threshold=args.reviewer_threshold)
                
                # Extract organization name for team expansion
                org_name = owner if args.include_teams else None
                
                if args.include_teams:
                    logger.info(f"Team-based analysis enabled, using organization: {org_name}")
                
                # Perform reviewer workload summary
                reviewer_analysis_results = reviewer_analyzer.get_reviewer_workload_summary(
                    prs,
                    threshold=args.reviewer_threshold,
                    include_teams=args.include_teams,
                    org_name=org_name
                )
                
                logger.info(f"Analyzed {reviewer_analysis_results['statistics']['total_reviewers']} reviewers across {len(prs)} PRs")
                
            except Exception as e:
                logger.error(f"Reviewer analysis failed: {e}")
                print(f"\n❌ Reviewer analysis failed: {e}")
                return 1
        
        # Set primary analysis results based on mode (for CSV output and summary display)
        if getattr(args, 'analyze_reviewers', False):
            analysis_results = reviewer_analysis_results
        else:
            analysis_results = pr_analysis_results
        
        # Generate CSV report
        logger.info(f"Generating CSV report: {args.output}")
        try:
            csv_reporter = CSVReporter(args.output)
            
            if getattr(args, 'analyze_reviewers', False):
                # Reviewer analysis CSV generation
                csv_reporter.validate_reviewer_summary(analysis_results)
                output_file = csv_reporter.generate_reviewer_report(analysis_results)
                logger.info("Successfully generated reviewer workload analysis CSV report")
            else:
                # PR lifecycle analysis CSV generation (original functionality)
                csv_reporter.validate_analysis_results(analysis_results)
                output_file = csv_reporter.generate_report(analysis_results)
                logger.info("Successfully generated PR lifecycle analysis CSV report")
            
        except CSVReportError as e:
            logger.error(f"CSV generation failed: {e}")
            print(f"\n❌ Failed to generate CSV report: {e}")
            return 1
        
        # Generate tracking CSV if requested
        if args.tracking_csv:
            try:
                tracking_filename = generate_tracking_filename(repo)
                reviewer_tracking_filename = generate_reviewer_tracking_filename(repo)
                
                if args.month:
                    # Single month mode - just append one row
                    csv_reporter.append_tracking_row(
                        tracking_file=tracking_filename,
                        period=args.month,
                        repository=f"{owner}/{repo}",
                        pr_summary=pr_analysis_results,
                        reviewer_summary=reviewer_analysis_results
                    )
                    csv_reporter.append_reviewer_tracking_rows(
                        tracking_file=reviewer_tracking_filename,
                        period=args.month,
                        repository=f"{owner}/{repo}",
                        reviewer_summary=reviewer_analysis_results,
                        top_n=20
                    )
                    if not args.quiet:
                        print(f"\n📈 Tracking data appended to: {tracking_filename}")
                        print(f"📈 Reviewer tracking appended to: {reviewer_tracking_filename}")
                else:
                    # Multi-month mode - break down by individual months
                    if not args.quiet:
                        print(f"\n📈 Breaking down {analysis_months} months into individual tracking rows...")
                    
                    months_processed = 0
                    for month_offset in range(analysis_months - 1, -1, -1):  # Go from oldest to newest
                        # Calculate the month to analyze
                        target_date = datetime.now() - relativedelta(months=month_offset)
                        month_str = target_date.strftime("%Y-%m")
                        
                        # Calculate start and end dates for this specific month
                        month_start = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                        if month_offset == 0:
                            # Current month - end is now
                            month_end = datetime.now()
                        else:
                            # Past month - end is last day of that month
                            next_month = month_start + relativedelta(months=1)
                            month_end = next_month - relativedelta(days=1)
                            month_end = month_end.replace(hour=23, minute=59, second=59)
                        
                        logger.info(f"Processing {month_str}...")
                        
                        # Fetch PRs for this specific month
                        try:
                            month_prs = pr_analyzer.fetch_specific_month_prs(owner, repo, month_start, month_end)
                        except Exception as e:
                            logger.warning(f"Failed to fetch PRs for {month_str}: {e}")
                            continue
                        
                        if not month_prs:
                            logger.info(f"No PRs found for {month_str}, skipping...")
                            continue
                        
                        # Run PR lifecycle analysis for this month
                        try:
                            month_pr_results = pr_analyzer.analyze_pr_lifecycle_times(
                                month_prs, owner, repo,
                                batch_size=args.batch_size,
                                batch_delay=args.batch_delay,
                                max_retries=args.max_retries
                            )
                        except Exception as e:
                            logger.warning(f"PR analysis failed for {month_str}: {e}")
                            month_pr_results = None
                        
                        # Run reviewer analysis for this month
                        try:
                            month_reviewer_analyzer = ReviewerWorkloadAnalyzer(default_threshold=args.reviewer_threshold)
                            org_name = owner if args.include_teams else None
                            month_reviewer_results = month_reviewer_analyzer.get_reviewer_workload_summary(
                                month_prs,
                                threshold=args.reviewer_threshold,
                                include_teams=args.include_teams,
                                org_name=org_name
                            )
                        except Exception as e:
                            logger.warning(f"Reviewer analysis failed for {month_str}: {e}")
                            month_reviewer_results = None
                        
                        # Append tracking rows for this month
                        if month_pr_results or month_reviewer_results:
                            csv_reporter.append_tracking_row(
                                tracking_file=tracking_filename,
                                period=month_str,
                                repository=f"{owner}/{repo}",
                                pr_summary=month_pr_results,
                                reviewer_summary=month_reviewer_results
                            )
                            if month_reviewer_results:
                                csv_reporter.append_reviewer_tracking_rows(
                                    tracking_file=reviewer_tracking_filename,
                                    period=month_str,
                                    repository=f"{owner}/{repo}",
                                    reviewer_summary=month_reviewer_results,
                                    top_n=20
                                )
                            months_processed += 1
                            logger.info(f"Added tracking data for {month_str}")
                    
                    if not args.quiet:
                        print(f"📈 Added {months_processed} monthly rows to: {tracking_filename}")
                        print(f"📈 Added reviewer data for {months_processed} months to: {reviewer_tracking_filename}")
                
                logger.info(f"Tracking CSV generation complete")
                    
            except CSVReportError as e:
                logger.error(f"Tracking CSV generation failed: {e}")
                print(f"\n❌ Failed to append tracking data: {e}")
                # Don't return 1 - tracking failure shouldn't fail the whole run
        
        # Print summary (unless quiet mode)
        if not args.quiet:
            # Build period description for display
            if args.month:
                period_str = args.month
            else:
                period_str = f"Last {analysis_months} month{'s' if analysis_months > 1 else ''}"
            
            if getattr(args, 'analyze_reviewers', False):
                print_reviewer_summary(analysis_results, f"{owner}/{repo}", period_str, output_file)
            else:
                print_summary(analysis_results, f"{owner}/{repo}", period_str, output_file)
        
        logger.info("Analysis completed successfully")
        return 0
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Analysis interrupted by user")
        return 1
    
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\n❌ Unexpected error occurred: {e}")
        print("Run with --debug for detailed error information")
        return 1


if __name__ == "__main__":
    sys.exit(main())
