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
  --month YYYY-MM                 Analyze a specific month (e.g., 2024-11). Overrides --months
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

Time-Series Tracking:
  --tracking-csv                 Append summary metrics to pr_tracking_<repo>.csv for Excel graphing

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

**Analyze PRs from a specific month (November 2024):**

```bash
source venv/bin/activate
python github_pr_analyzer.py microsoft/vscode --month 2024-11
```

**Analyze PRs from October 2024 with custom output:**

```bash
source venv/bin/activate
python github_pr_analyzer.py facebook/react --month 2024-10 --output react_oct_2024.csv
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

**Analyze reviewer workload for a specific month:**

```bash
source venv/bin/activate
python github_pr_analyzer.py myorg/myrepo --analyze-reviewers --month 2024-11
```

#### Time-Series Tracking (for Excel Graphing)

The `--tracking-csv` option appends summary metrics to a tracking file (`pr_tracking_<repo>.csv`) each time you run the tool. This enables building historical data for trend analysis in Excel or other tools.

**Build monthly history by running each month:**

```bash
source venv/bin/activate
# Run for November 2024
python github_pr_analyzer.py myorg/myrepo --month 2024-11 --tracking-csv

# Run for December 2024
python github_pr_analyzer.py myorg/myrepo --month 2024-12 --tracking-csv

# Each run appends to: pr_tracking_myrepo.csv
```

**Backfill historical data:**

```bash
source venv/bin/activate
# Run for each past month to build history
python github_pr_analyzer.py myorg/myrepo --month 2024-06 --tracking-csv
python github_pr_analyzer.py myorg/myrepo --month 2024-07 --tracking-csv
python github_pr_analyzer.py myorg/myrepo --month 2024-08 --tracking-csv
# ... continue for each month
```

**Output files created:**

When using `--tracking-csv`, two files are created/appended:

1. `pr_tracking_<repo>.csv` - Summary metrics per month
2. `pr_tracking_reviewers_<repo>.csv` - Individual reviewer data per month

**Summary tracking CSV columns (`pr_tracking_<repo>.csv`):**

| Column | Description |
| ------ | ----------- |
| period | Analysis period (YYYY-MM) |
| repository | Repository name |
| analysis_date | When the analysis was run |
| total_prs | Total PRs in period |
| merged_prs | Number of merged PRs |
| reviewed_prs | Number of reviewed PRs |
| avg_time_to_first_review_hours | Average hours to first review |
| avg_time_to_merge_hours | Average hours to merge |
| avg_commit_lead_time_hours | Average commit lead time |
| total_review_requests | Total reviewer requests |
| unique_reviewers | Count of unique reviewers |
| overloaded_count | Number of overloaded reviewers |
| top_10_overloaded | Top reviewers with counts (e.g., "alice:154,bob:97") |

**Reviewer tracking CSV columns (`pr_tracking_reviewers_<repo>.csv`):**

| Column | Description |
| ------ | ----------- |
| period | Analysis period (YYYY-MM) |
| repository | Repository name |
| reviewer | Reviewer username |
| requests | Number of review requests |
| workload_status | NORMAL, HIGH, or OVERLOADED |
| percentage_of_total | Percentage of all review requests |

This second file makes it easy to create **line charts for individual reviewers** - just create a Pivot Chart in Excel with:
- Rows: `period`
- Columns: `reviewer`
- Values: `requests`

### Excel Dashboard Generation

Once you have tracking CSV files, you can create Excel dashboards to visualize trends over time. The tool includes a script to copy an existing Excel template and update its data connections for different repositories.

#### Creating Your First Dashboard (Template)

1. **Generate tracking data** for your first repository:

   ```bash
   source venv/bin/activate
   # Build up historical data
   python github_pr_analyzer.py myorg/my-first-repo --month 2024-06 --tracking-csv
   python github_pr_analyzer.py myorg/my-first-repo --month 2024-07 --tracking-csv
   # ... repeat for each month
   ```

2. **Create an Excel workbook** with Power Query connections:
   - Open Excel and go to **Data → Get Data → From Text/CSV**
   - Select `pr_tracking_my-first-repo.csv` and load it
   - Repeat for `pr_tracking_reviewers_my-first-repo.csv`
   - Create your charts and pivot tables using this data
   - Save as `CycleTimeAnalysis.xlsx` (this becomes your template)

3. **Recommended charts to create**:
   - **PR Counts Over Time** (Line chart): Track `total_prs`, `merged_prs`, `reviewed_prs` by `period`
   - **Cycle Times** (Line chart): Track `avg_time_to_first_review_hours`, `avg_time_to_merge_hours` by `period`
   - **Reviewer Trends** (Pivot Line chart): Individual reviewer `requests` over `period`
   - **Workload Distribution** (Stacked Bar): `workload_status` counts by `period`

#### Copying the Template for Other Repositories

Once you have a working Excel template, use `copy_excel_template.py` to create dashboards for other repositories:

```bash
source venv/bin/activate

# Generate tracking data for other repos first
python github_pr_analyzer.py myorg/another-repo --month 2024-06 --tracking-csv
python github_pr_analyzer.py myorg/another-repo --month 2024-07 --tracking-csv
# ... repeat for each month

# Copy the template and update data connections
python copy_excel_template.py "/path/to/CycleTimeAnalysis.xlsx" another-repo
```

**Multiple repositories at once:**

```bash
python copy_excel_template.py "/path/to/CycleTimeAnalysis.xlsx" repo1 repo2 repo3
```

**Specify output directory:**

```bash
python copy_excel_template.py "/path/to/CycleTimeAnalysis.xlsx" repo1 repo2 --output-dir /path/to/dashboards
```

This creates:
- `CycleTimeAnalysis_repo1.xlsx`
- `CycleTimeAnalysis_repo2.xlsx`
- `CycleTimeAnalysis_repo3.xlsx`

Each file has its Power Query connections updated to point to the corresponding `pr_tracking_<repo>.csv` and `pr_tracking_reviewers_<repo>.csv` files.

#### Refreshing Data in Excel

After opening a generated Excel file:

1. Go to **Data → Refresh All** to load the latest CSV data
2. If prompted about data source privacy, select "Ignore Privacy Levels"
3. Charts and pivot tables will automatically update

#### Complete Workflow Example

Here's the full workflow for tracking multiple repositories:

```bash
# 1. Activate virtual environment
source venv/bin/activate

# 2. Generate tracking data for all repos (repeat monthly)
for repo in cnn-content-hub cnn-android-7 cnn-ios-7; do
  python github_pr_analyzer.py myorg/$repo --month 2024-11 --tracking-csv
done

# 3. Create Excel dashboards (first time only)
# - Manually create template for first repo with charts
# - Then copy for others:
python copy_excel_template.py ~/Documents/CycleTimeAnalysis.xlsx cnn-android-7 cnn-ios-7

# 4. Open Excel files and refresh data
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
Output File: pr_analysis_react_2024-09-11.csv

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
- **`copy_excel_template.py`**: Excel template copying utility
  - Copies an existing Excel workbook and updates Power Query data connections for new repositories
  - Handles all internal Excel XML structures (connections, charts, pivot tables, etc.)

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
