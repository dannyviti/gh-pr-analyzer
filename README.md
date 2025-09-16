# GitHub PR Analysis Tool

A comprehensive Python tool for analyzing GitHub pull requests with two powerful analysis modes:

- **PR Lifecycle Analysis**: Analyze review velocity, merge times, and development lead times
- **Reviewer Workload Analysis**: Identify reviewer bottlenecks, overload patterns, and workload distribution

## Features

### PR Lifecycle Analysis (Default Mode)

Analyzes three key timing metrics for GitHub pull requests:

- **Time to First Review**: Time from PR creation to first review activity (comments, approvals, changes requested)
- **Time to Merge**: Time from PR creation to successful merge
- **Commit Lead Time**: Time from first commit to merge (development velocity)

### Reviewer Workload Analysis (New!)

Analyzes reviewer request patterns and workload distribution:

- **Request Tracking**: Count and track reviewer requests across all PRs
- **Overload Detection**: Identify potentially overloaded reviewers with configurable thresholds
- **Statistical Analysis**: Calculate request distribution, averages, and inequality metrics
- **Team Analysis**: Expand team reviewer requests to individual team members
- **Workload Categories**: Classify reviewers as Normal Load, High Load, or Overloaded
- **Distribution Insights**: Gini coefficient analysis and concentration ratios

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
   # - pr_analyzer.py (PR lifecycle analysis logic)
   # - reviewer_analyzer.py (reviewer workload analysis logic)
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

**PR Lifecycle Analysis (Default Mode):**

```bash
python github_pr_analyzer.py owner/repository
```

**Reviewer Workload Analysis:**

```bash
python github_pr_analyzer.py owner/repository --analyze-reviewers
```

### Command Line Options

```bash
python github_pr_analyzer.py owner/repository [OPTIONS]

General Options:
  --months MONTHS                 Number of months to look back (default: 1)
  --output, -o OUTPUT            Output CSV file path (auto-generated if not specified)
  --verbose, -v                  Enable verbose logging
  --debug                        Enable debug logging
  --quiet, -q                    Suppress all output except errors
  --help, -h                     Show help message

Reviewer Workload Analysis:
  --analyze-reviewers            Enable reviewer workload analysis mode
  --reviewer-threshold THRESHOLD Set overload detection threshold (default: 10 requests)
  --include-teams                Include team-based reviewer analysis
  --reviewer-period MONTHS       Time period for reviewer analysis (defaults to --months)

Rate Limiting & Utilities:
  --batch-size SIZE              PRs to process per batch (default: 10)
  --batch-delay DELAY            Delay between batches in seconds (default: 0.1)
  --max-retries RETRIES          Maximum API request retries (default: 3)
  --check-rate-limit             Check GitHub API rate limit status and exit
  --get-username USER_ID         Translate GitHub user ID to username and exit
```

### Examples

#### PR Lifecycle Analysis

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

#### Reviewer Workload Analysis

**Basic reviewer analysis:**

```bash
source venv/bin/activate
python github_pr_analyzer.py facebook/react --analyze-reviewers
```

**Reviewer analysis with custom threshold and team expansion:**

```bash
source venv/bin/activate
python github_pr_analyzer.py kubernetes/kubernetes --analyze-reviewers --reviewer-threshold 15 --include-teams
```

**Analyze reviewer workload over 6 months with custom output:**

```bash
source venv/bin/activate
python github_pr_analyzer.py myorg/myrepo --analyze-reviewers --reviewer-period 6 --output custom_reviewer_analysis.csv
```

## Output

### Console Output

#### PR Lifecycle Analysis

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
Output File: pr_analysis_react.csv

📊 Summary Statistics:
  Total PRs Analyzed: 245
  Merged PRs: 198 (80.8% of total)
  Reviewed PRs: 231 (94.3% of total)

⏱️  Average Timing Metrics:
  Time to First Review: 8.5 hours (0.4 days)
  Time to Merge: 72.3 hours (3.0 days)
  Commit Lead Time: 120.5 hours (5.0 days)

📄 Detailed results saved to: pr_analysis_react.csv
```

#### Reviewer Workload Analysis

The reviewer analysis provides detailed workload insights:

- Total PRs and review requests analyzed
- Reviewer request distribution statistics
- Overloaded reviewer identification
- Workload distribution patterns
- Output file location

Example:

```
GitHub PR Reviewer Analysis Results for kubernetes/kubernetes
============================================================
Analysis Period: Last 3 months
Output File: reviewer_workload_kubernetes.csv

📊 Reviewer Request Statistics:
  Total PRs Analyzed: 1,247
  Total Review Requests: 3,891
  Unique Reviewers: 67
  Average Requests per Reviewer: 58.1

⚠️  Potentially Overloaded Reviewers (≥75 requests):
  - sig-lead-alice: 187 requests (322% of average)
  - core-maintainer-bob: 156 requests (268% of average)
  - senior-reviewer-carol: 98 requests (169% of average)

📈 Request Distribution:
  Top 20% of reviewers handle 68% of all requests
  Moderate inequality in reviewer assignments (Gini: 0.45)
  Reviewer diversity score: 0.55 (higher = more balanced)

📊 Workload Categories:
  Normal Load: 52 reviewers
  High Load: 12 reviewers
  Overloaded: 3 reviewers
  (Analysis includes team-based reviewer requests)

📄 Detailed results saved to: reviewer_workload_kubernetes.csv
```

### CSV Output

The tool generates comprehensive CSV files with detailed analysis data.

#### PR Lifecycle Analysis CSV

| Column                     | Description                         |
| -------------------------- | ----------------------------------- |
| pr_number                  | GitHub PR number                    |
| title                      | PR title (sanitized for CSV)        |
| state                      | PR state (open, closed)             |
| created_at                 | PR creation timestamp               |
| merged_at                  | PR merge timestamp (if merged)      |
| repository_name            | Repository identifier               |
| pr_creator_github_id       | PR creator's GitHub user ID         |
| pr_creator_username        | PR creator's GitHub username        |
| time_to_first_review_hours | Hours from creation to first review |
| time_to_merge_hours        | Hours from creation to merge        |
| commit_lead_time_hours     | Hours from first commit to merge    |
| has_reviews                | Whether the PR has any reviews      |
| review_count               | Number of formal reviews            |
| comment_count              | Number of review comments           |
| commit_count               | Number of commits in the PR         |
| is_merged                  | Whether the PR was merged           |

#### Reviewer Workload Analysis CSV

| Column                 | Description                                              |
| ---------------------- | -------------------------------------------------------- |
| reviewer_login         | GitHub username or team identifier                       |
| reviewer_name          | Display name of reviewer                                 |
| reviewer_type          | Type: 'user' or 'team'                                   |
| total_requests         | Total number of review requests                          |
| pr_numbers             | List of PR numbers where reviewer was requested          |
| request_sources        | How reviewer was requested ('individual' or 'team:name') |
| first_request_date     | Date of first review request                             |
| last_request_date      | Date of most recent review request                       |
| avg_requests_per_month | Average requests per month                               |
| percentage_of_total    | Percentage of all review requests                        |
| workload_status        | Status: 'NORMAL', 'HIGH', or 'OVERLOADED'                |
| workload_category      | Human-readable category                                  |

Both CSV files include comprehensive summary statistics as comments at the top for immediate analysis, including:

- Analysis metadata and configuration
- Statistical summaries (averages, medians, distributions)
- Key insights and recommendations

## Architecture

The tool is built with a modular architecture:

- **`github_client.py`**: GitHub API integration with authentication, rate limiting, and data fetching
  - Enhanced with reviewer request data collection and team member expansion
- **`pr_analyzer.py`**: PR lifecycle analysis logic for timing calculations and data processing
- **`reviewer_analyzer.py`**: Reviewer workload analysis engine with statistical calculations
  - Request aggregation, overload detection, and distribution analysis
- **`csv_reporter.py`**: CSV generation with support for both analysis modes
  - Dual output formats with comprehensive validation
- **`github_pr_analyzer.py`**: Main CLI interface and workflow orchestration
  - Intelligent mode detection and analysis pipeline routing

## Testing

Run the comprehensive test suite (make sure your virtual environment is activated):

```bash
# Activate virtual environment first
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run all tests
python -m pytest -v

# Run specific test modules
python -m pytest test_github_client.py -v        # GitHub API integration
python -m pytest test_pr_analyzer.py -v          # PR lifecycle analysis
python -m pytest test_reviewer_analyzer.py -v    # Reviewer workload analysis
python -m pytest test_csv_reporter.py -v         # CSV generation
python -m pytest test_integration.py -v          # End-to-end workflows
```

The comprehensive test suite includes:

- **57 GitHub client tests**: Authentication, API interactions, data fetching, and reviewer data collection
- **42 PR analyzer tests**: Timing calculations, edge cases, and data processing
- **20 Reviewer analyzer tests**: Workload analysis, statistical calculations, and overload detection
- **33 CSV reporter tests**: Dual-mode formatting, validation, and error handling
- **27 Integration tests**: End-to-end workflows, CLI interface, and error scenarios

**Total: 179 tests** ensuring reliability across all analysis modes and edge cases.

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

1. **Adding new PR metrics**: Extend the `PRAnalyzer` class with additional calculation methods
2. **New reviewer analytics**: Extend the `ReviewerWorkloadAnalyzer` class with advanced statistical methods
3. **Additional output formats**: Implement new reporter classes following the dual-mode `CSVReporter` pattern
4. **Enhanced GitHub integration**: Add support for GitHub Apps, GraphQL API, or different API versions
5. **New analysis modes**: Create additional analysis pipelines following the existing architecture patterns

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
