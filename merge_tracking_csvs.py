#!/usr/bin/env python3
"""
Merge PR tracking CSV files from multiple repositories into combined files.

This script auto-discovers all pr_tracking_*.csv and pr_tracking_reviewers_*.csv files
and merges them into combined CSV files for cross-repo analysis in Excel.

Usage:
    python merge_tracking_csvs.py
    python merge_tracking_csvs.py --input-dir /path/to/csvs
    python merge_tracking_csvs.py --output-dir /path/to/output

Examples:
    # Merge all tracking CSVs in current directory
    python merge_tracking_csvs.py
    
    # Merge CSVs from a specific directory
    python merge_tracking_csvs.py --input-dir ~/GitHub/gh-pr-analyzer
    
    # Output to a different directory
    python merge_tracking_csvs.py --output-dir ~/Documents/reports
"""

import argparse
import logging
import sys
from glob import glob
from pathlib import Path

import pandas as pd


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def discover_csv_files(input_dir: Path) -> tuple:
    """
    Discover PR tracking CSV files in the input directory.
    
    Returns:
        Tuple of (pr_metrics_files, reviewer_files)
    """
    logger = logging.getLogger(__name__)
    
    # Find all pr_tracking_*.csv files
    all_tracking_files = list(input_dir.glob("pr_tracking_*.csv"))
    
    # Separate PR metrics files from reviewer files
    pr_metrics_files = [f for f in all_tracking_files if "reviewers" not in f.name]
    reviewer_files = [f for f in all_tracking_files if "reviewers" in f.name]
    
    # Also exclude combined files from previous runs
    pr_metrics_files = [f for f in pr_metrics_files if f.name != "pr_tracking_combined.csv"]
    reviewer_files = [f for f in reviewer_files if f.name != "pr_tracking_reviewers_combined.csv"]
    
    logger.info(f"Found {len(pr_metrics_files)} PR metrics CSV files")
    logger.info(f"Found {len(reviewer_files)} reviewer CSV files")
    
    return pr_metrics_files, reviewer_files


def merge_csv_files(files: list, output_path: Path, file_type: str) -> int:
    """
    Merge multiple CSV files into a single combined file.
    
    Args:
        files: List of Path objects to CSV files
        output_path: Path for the output combined CSV
        file_type: Description for logging (e.g., "PR metrics", "reviewer")
    
    Returns:
        Number of rows in the combined file
    """
    logger = logging.getLogger(__name__)
    
    if not files:
        logger.warning(f"No {file_type} files found to merge")
        return 0
    
    dataframes = []
    
    for file_path in sorted(files):
        try:
            df = pd.read_csv(file_path)
            logger.debug(f"Loaded {file_path.name}: {len(df)} rows")
            dataframes.append(df)
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            continue
    
    if not dataframes:
        logger.error(f"No {file_type} files could be read")
        return 0
    
    # Concatenate all dataframes
    combined_df = pd.concat(dataframes, ignore_index=True)
    
    # Sort by period and repository for easier analysis
    sort_columns = []
    if 'period' in combined_df.columns:
        sort_columns.append('period')
    if 'repository' in combined_df.columns:
        sort_columns.append('repository')
    
    if sort_columns:
        combined_df = combined_df.sort_values(sort_columns)
    
    # Write the combined file
    combined_df.to_csv(output_path, index=False)
    logger.info(f"Created {output_path.name}: {len(combined_df)} rows from {len(files)} files")
    
    return len(combined_df)


def extract_repo_name(filename: str) -> str:
    """Extract repository name from a tracking CSV filename."""
    # pr_tracking_<repo>.csv -> <repo>
    # pr_tracking_reviewers_<repo>.csv -> <repo>
    name = filename.replace("pr_tracking_reviewers_", "").replace("pr_tracking_", "")
    return name.replace(".csv", "")


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Merge PR tracking CSV files from multiple repositories',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --input-dir ~/GitHub/gh-pr-analyzer
  %(prog)s --output-dir ~/Documents/reports
  %(prog)s --input-dir /path/to/csvs --output-dir /path/to/output
        """
    )
    
    parser.add_argument(
        '--input-dir', '-i',
        type=str,
        default='.',
        help='Directory containing pr_tracking_*.csv files (default: current directory)'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        default=None,
        help='Directory for output combined CSV files (default: same as input directory)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_arguments()
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    input_dir = Path(args.input_dir).resolve()
    output_dir = Path(args.output_dir).resolve() if args.output_dir else input_dir
    
    if not input_dir.exists():
        logger.error(f"Input directory not found: {input_dir}")
        return 1
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Output directory: {output_dir}")
    
    # Discover CSV files
    pr_metrics_files, reviewer_files = discover_csv_files(input_dir)
    
    if not pr_metrics_files and not reviewer_files:
        logger.error("No pr_tracking_*.csv files found in the input directory")
        print(f"\n❌ No pr_tracking_*.csv files found in: {input_dir}")
        print("Make sure you've run github_pr_analyzer.py with --tracking-csv first.")
        return 1
    
    # List discovered repos
    repos = set()
    for f in pr_metrics_files:
        repos.add(extract_repo_name(f.name))
    
    print(f"\n📁 Discovered {len(repos)} repositories:")
    for repo in sorted(repos):
        print(f"   • {repo}")
    
    # Merge PR metrics files
    pr_output = output_dir / "pr_tracking_combined.csv"
    pr_rows = merge_csv_files(pr_metrics_files, pr_output, "PR metrics")
    
    # Merge reviewer files
    reviewer_output = output_dir / "pr_tracking_reviewers_combined.csv"
    reviewer_rows = merge_csv_files(reviewer_files, reviewer_output, "reviewer")
    
    # Summary
    print(f"\n✅ Merge complete!")
    print(f"   PR Metrics:    {pr_output.name} ({pr_rows} rows)")
    print(f"   Reviewer Data: {reviewer_output.name} ({reviewer_rows} rows)")
    print(f"\n💡 Next steps:")
    print(f"   1. Open Excel and go to Data > From Text/CSV")
    print(f"   2. Load {pr_output.name} and {reviewer_output.name}")
    print(f"   3. Create pivot tables with 'repository' as a filter to compare repos")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

