# GitHub PR Lifecycle Time Analysis Tool

A comprehensive Python tool for analyzing GitHub pull request lifecycle times, providing insights into review velocity,
merge times, and development lead times.

## Features

The tool analyzes three key metrics for GitHub pull requests:

- **Time to First Review**: Time from PR creation to first review activity (comments, approvals, changes requested)
- **Time to Merge**: Time from PR creation to successful merge
- **Commit Lead Time**: Time from first commit to merge (development velocity)

## Installation

### Prerequisites

- Python 3.7 or higher
- GitHub personal access token

### Setup

1. **Clone or download the tool files**:

   ```bash
   # Ensure you have all required files:
   # - github_pr_analyzer.py (main CLI script)
   # - github_client.py (GitHub API client)
   # - pr_analyzer.py (analysis logic)
   # - csv_reporter.py (CSV output generation)
   # - requirements.txt (dependencies)
   ```

2. **Create and activate a virtual environment** (required):

   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

   **Note**: This tool requires a virtual environment to ensure dependency isolation and avoid conflicts with system
   packages. The tool will not run without proper dependency installation in an isolated environment.

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up GitHub authentication**:

   ```bash
   export GITHUB_TOKEN="your_github_token_here"
   ```

   To create a GitHub token:

   - Go to [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens)
   - Generate a new token with `repo` scope for private repositories, or `public_repo` for public repositories only

## Usage

**Important**: Make sure to activate your virtual environment before running the tool:

```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Basic Usage

```bash
python github_pr_analyzer.py owner/repository
```

### Advanced Options

```bash
python github_pr_analyzer.py owner/repository [OPTIONS]

Options:
  --months MONTHS       Number of months to look back (default: 1)
  --output, -o OUTPUT   Output CSV file path (default: pr_analysis.csv)
  --verbose, -v         Enable verbose logging
  --debug               Enable debug logging
  --quiet, -q           Suppress all output except errors
  --help, -h            Show help message
```

### Examples

**Analyze Microsoft VS Code PRs from the last month:**

```bash
source venv/bin/activate
python github_pr_analyzer.py microsoft/vscode
```

**Analyze React PRs from the last 3 months with custom output:**

```bash
source venv/bin/activate
python github_pr_analyzer.py facebook/react --months 3 --output react_analysis.csv
```

**Analyze Kubernetes PRs with verbose logging:**

```bash
source venv/bin/activate
python github_pr_analyzer.py kubernetes/kubernetes --months 6 --output k8s_analysis.csv --verbose
```

## Output

### Console Output

The tool provides a comprehensive summary including:

- Total number of PRs analyzed
- Number of merged and reviewed PRs
- Average timing metrics in hours and days
- Output file location

Example:

```
GitHub PR Analysis Results for facebook/react
=============================================
Analysis Period: Last 3 months
Output File: react_analysis.csv

📊 Summary Statistics:
  Total PRs Analyzed: 245
  Merged PRs: 198 (80.8% of total)
  Reviewed PRs: 231 (94.3% of total)

⏱️  Average Timing Metrics:
  Time to First Review: 8.5 hours (0.4 days)
  Time to Merge: 72.3 hours (3.0 days)
  Commit Lead Time: 120.5 hours (5.0 days)

📄 Detailed results saved to: react_analysis.csv
```

### CSV Output

The tool generates a comprehensive CSV file with the following columns:

| Column                     | Description                         |
| -------------------------- | ----------------------------------- |
| pr_number                  | GitHub PR number                    |
| title                      | PR title (sanitized for CSV)        |
| state                      | PR state (open, closed)             |
| created_at                 | PR creation timestamp               |
| merged_at                  | PR merge timestamp (if merged)      |
| time_to_first_review_hours | Hours from creation to first review |
| time_to_merge_hours        | Hours from creation to merge        |
| commit_lead_time_hours     | Hours from first commit to merge    |
| has_reviews                | Whether the PR has any reviews      |
| review_count               | Number of formal reviews            |
| comment_count              | Number of review comments           |
| commit_count               | Number of commits in the PR         |
| is_merged                  | Whether the PR was merged           |

The CSV file includes summary statistics as comments at the top for immediate analysis.

## Architecture

The tool is built with a modular architecture:

- **`github_client.py`**: GitHub API integration with authentication, rate limiting, and data fetching
- **`pr_analyzer.py`**: Core analysis logic for timing calculations and data processing
- **`csv_reporter.py`**: CSV generation with proper formatting and validation
- **`github_pr_analyzer.py`**: Main CLI interface and workflow orchestration

## Testing

Run the comprehensive test suite (make sure your virtual environment is activated):

```bash
# Activate virtual environment first
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run all tests
python -m pytest -v

# Run specific test modules
python -m pytest test_github_client.py -v
python -m pytest test_pr_analyzer.py -v
python -m pytest test_csv_reporter.py -v
python -m pytest test_integration.py -v
```

The test suite includes:

- 42 GitHub client tests (authentication, API interactions, data fetching)
- 42 PR analyzer tests (timing calculations, edge cases, data processing)
- 23 CSV reporter tests (formatting, validation, error handling)
- 22 integration tests (end-to-end workflows, CLI interface, error scenarios)

## Error Handling

The tool provides comprehensive error handling for:

- **Authentication failures**: Invalid or missing GitHub tokens
- **Repository access**: Non-existent or private repositories
- **API rate limits**: Automatic detection and informative messages
- **Network issues**: Connection failures and timeouts
- **Data validation**: Malformed or missing PR data
- **File operations**: Permission errors and invalid paths

## Limitations

- Requires GitHub personal access token with appropriate repository access
- Subject to GitHub API rate limits (5,000 requests/hour for authenticated users)
- Analysis limited to data available through GitHub's REST API
- Timeline data uses GitHub's preview API which may change

## Contributing

The tool is designed with extensibility in mind:

1. **Adding new metrics**: Extend the `PRAnalyzer` class with additional calculation methods
2. **New output formats**: Implement additional reporter classes following the `CSVReporter` pattern
3. **Enhanced GitHub integration**: Add support for GitHub Apps or different API versions

## Support

For issues and questions:

1. Ensure you're running the tool in an activated virtual environment
2. Check that your GitHub token has appropriate permissions
3. Verify repository name format is `owner/repository`
4. Enable debug logging (`--debug`) for detailed error information
5. Review the comprehensive test suite for usage examples

## License

This tool is provided as-is for educational and analysis purposes. Please respect GitHub's API terms of service and rate
limiting guidelines.
