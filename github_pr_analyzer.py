#!/usr/bin/env python3
"""
GitHub PR Lifecycle Time Analysis Tool

This tool analyzes GitHub pull requests to calculate:
- Time from PR creation to first review activity
- Time from PR creation to merge
- Time from first commit to merge (commit lead time)

Usage:
    python github_pr_analyzer.py owner/repo [options]

Environment Variables:
    GITHUB_TOKEN: GitHub personal access token (required)

Examples:
    python github_pr_analyzer.py microsoft/vscode
    python github_pr_analyzer.py facebook/react --months 3 --output react_analysis.csv
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from github_client import GitHubClient, GitHubAPIError, GitHubAuthenticationError
from pr_analyzer import PRAnalyzer, PRAnalysisError  
from csv_reporter import CSVReporter, CSVReportError


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
        description='Analyze GitHub PR lifecycle times',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s microsoft/vscode
  %(prog)s facebook/react --months 3
  %(prog)s kubernetes/kubernetes --months 6 --output k8s_analysis.csv --verbose

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
    
    # Validate months parameter
    if args.months < 1:
        raise ValueError("Months parameter must be at least 1")
    
    if args.months > 24:
        raise ValueError("Months parameter cannot exceed 24 (2 years)")
    
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


def generate_auto_filename(owner: str, repo: str) -> str:
    """
    Generate automatic filename based on repository name.
    
    Args:
        owner: Repository owner (user or organization)
        repo: Repository name
        
    Returns:
        Auto-generated CSV filename
    """
    if not owner or not repo:
        return "pr_analysis.csv"
    
    # Create repository identifier and sanitize it
    repo_identifier = f"{owner}/{repo}"
    sanitized_repo = sanitize_repository_name_for_filename(repo_identifier)
    
    # Extract just the repo name part for cleaner filename
    repo_part = sanitize_repository_name_for_filename(repo)
    
    return f"pr_analysis_{repo_part}.csv"


def print_summary(analysis_results: dict, repository: str, months: int, output_path: str) -> None:
    """
    Print analysis summary to stdout.
    
    Args:
        analysis_results: Dictionary containing analysis results
        repository: Repository name
        months: Number of months analyzed
        output_path: Path to output CSV file
    """
    summary = analysis_results.get('summary', {})
    
    print(f"\nGitHub PR Analysis Results for {repository}")
    print("=" * (35 + len(repository)))
    print(f"Analysis Period: Last {months} month{'s' if months > 1 else ''}")
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
            args.output = generate_auto_filename(owner, repo)
            logger.info(f"Auto-generated output filename: {args.output}")
        
        if not args.check_rate_limit and not args.get_username:
            logger.info(f"Starting GitHub PR analysis for {owner}/{repo}")
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
        
        # Fetch PRs
        logger.info(f"Fetching PRs from last {args.months} month{'s' if args.months > 1 else ''}...")
        try:
            prs = pr_analyzer.fetch_monthly_prs(owner, repo, args.months)
            if not prs:
                print(f"\n⚠️  No PRs found in {owner}/{repo} for the last {args.months} month{'s' if args.months > 1 else ''}")
                return 0
            
            logger.info(f"Found {len(prs)} PRs to analyze")
            
        except (GitHubAPIError, PRAnalysisError) as e:
            logger.error(f"Failed to fetch PRs: {e}")
            print(f"\n❌ Failed to fetch PRs: {e}")
            return 1
        
        # Perform analysis with rate limiting parameters
        logger.info("Analyzing PR lifecycle times...")
        try:
            analysis_results = pr_analyzer.analyze_pr_lifecycle_times(
                prs, owner, repo, 
                batch_size=args.batch_size,
                batch_delay=args.batch_delay,
                max_retries=args.max_retries
            )
        except PRAnalysisError as e:
            logger.error(f"Analysis failed: {e}")
            print(f"\n❌ Analysis failed: {e}")
            return 1
        
        # Generate CSV report
        logger.info(f"Generating CSV report: {args.output}")
        try:
            csv_reporter = CSVReporter(args.output)
            csv_reporter.validate_analysis_results(analysis_results)
            output_file = csv_reporter.generate_report(analysis_results)
            
        except CSVReportError as e:
            logger.error(f"CSV generation failed: {e}")
            print(f"\n❌ Failed to generate CSV report: {e}")
            return 1
        
        # Print summary (unless quiet mode)
        if not args.quiet:
            print_summary(analysis_results, f"{owner}/{repo}", args.months, output_file)
        
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
