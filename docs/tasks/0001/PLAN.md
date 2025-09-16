# Technical Implementation Plan: PR Metrics User Comparison Feature

## Task Description

Add the ability to compare PR metrics for a list of people against the average metrics of the repository. This feature
will allow users to specify GitHub usernames or IDs and see how their individual PR performance metrics (time to first
review, time to merge, commit lead time) compare to the repository averages.

## Required Changes

### Core Files to Modify

1. **`github_pr_analyzer.py`** - Main CLI script

   - Add new command-line arguments for user comparison mode
   - Add user comparison workflow orchestration

2. **`pr_analyzer.py`** - Analysis logic

   - Add methods for user-specific metric calculations
   - Add comparison logic against repository averages
   - Add user filtering and grouping functionality

3. **`csv_reporter.py`** - CSV output generation

   - Add new CSV output format for user comparison reports
   - Add summary statistics for individual users vs averages

4. **New file: `user_comparison.py`** - User comparison logic
   - Core logic for user metric comparisons
   - Statistical analysis and difference calculations
   - User data validation and lookup

### Test Files to Create/Modify

1. **`test_user_comparison.py`** - New test file for user comparison functionality
2. **`test_pr_analyzer.py`** - Add tests for new methods in PRAnalyzer
3. **`test_csv_reporter.py`** - Add tests for new CSV format
4. **`test_integration.py`** - Add end-to-end tests for user comparison feature

## Implementation Phases

### Phase 1: Core User Comparison Infrastructure

**Implementation:**

- Create `user_comparison.py` module with `UserMetricsComparator` class
- Add methods to calculate individual user metrics from PR data
- Add methods to calculate comparison statistics (percentage differences, rankings)
- Add user data validation and normalization

**Tests:**

- Unit tests for `UserMetricsComparator` class methods
- Tests for metric calculation accuracy
- Tests for edge cases (users with no PRs, invalid user data)
- Tests for statistical comparison calculations

### Phase 2: CLI Integration and Analysis Pipeline

**Implementation:**

- Extend `github_pr_analyzer.py` with new command-line arguments:
  - `--compare-users` flag to enable comparison mode
  - `--users` argument to specify list of usernames/IDs to compare
  - `--output-format` argument to choose between standard and comparison output
- Modify `PRAnalyzer` class to support user-specific analysis
- Add user filtering and grouping methods to `pr_analyzer.py`

**Tests:**

- Unit tests for new `PRAnalyzer` methods
- CLI argument parsing tests
- Integration tests for user comparison workflow
- Tests for user filtering and data grouping logic

### Phase 3: Enhanced CSV Reporting

**Implementation:**

- Extend `CSVReporter` class to support user comparison output format
- Add new CSV structure with user comparison data
- Add summary statistics showing user metrics vs repository averages
- Include percentage differences and relative rankings

**Tests:**

- Unit tests for new CSV output format
- Tests for user comparison CSV structure
- Tests for summary statistics accuracy
- Tests for CSV validation with comparison data

### Phase 4: Error Handling and Edge Cases

**Implementation:**

- Add comprehensive error handling for invalid usernames/IDs
- Handle cases where specified users have no PRs in the analysis period
- Add warnings for users not found in repository data
- Implement graceful degradation when some users can't be found

**Tests:**

- Tests for error handling with invalid user inputs
- Tests for edge cases (no PRs for user, user not found)
- Tests for warning messages and graceful failures
- Integration tests covering error scenarios

## Detailed Technical Changes

### Command Line Interface Changes

New arguments for `github_pr_analyzer.py`:

```bash
python github_pr_analyzer.py owner/repo --compare-users --users "user1,user2,user3"
python github_pr_analyzer.py owner/repo --compare-users --users-file users.txt
```

### New CSV Output Format

The comparison mode will generate a CSV with:

- Individual user metrics
- Repository averages for comparison
- Percentage differences from average
- Relative rankings among compared users

### Data Flow Changes

1. **Standard Mode**: Repository → All PRs → Aggregate Metrics → CSV
2. **Comparison Mode**: Repository → All PRs → Filter by Users → Individual Metrics → Compare vs Average → Comparison
   CSV

### API Extensions

**New methods in `PRAnalyzer`:**

- `calculate_user_metrics(prs, user_identifier)` - Calculate metrics for specific user
- `get_users_from_prs(prs)` - Extract all unique users from PR data
- `filter_prs_by_user(prs, user_identifier)` - Filter PRs by creator

**New class `UserMetricsComparator`:**

- `compare_user_to_average(user_metrics, repo_averages)` - Calculate comparison statistics
- `rank_users(user_metrics_dict)` - Rank users by performance metrics
- `validate_user_identifiers(user_list)` - Validate and normalize user inputs

## Testing Strategy

### Unit Tests

- Each new method will have comprehensive unit tests
- Mock GitHub API responses for consistent testing
- Edge case coverage for all comparison calculations

### Integration Tests

- End-to-end tests for complete user comparison workflow
- CLI integration tests for new command-line arguments
- CSV output validation for comparison format

### Functional Tests

- Test complete user comparison scenarios
- Verify accuracy of percentage calculations and rankings
- Test error handling and user feedback messages

## Success Criteria

1. Users can specify a list of GitHub usernames/IDs for comparison
2. System calculates individual metrics for each specified user
3. Comparison statistics show how each user performs relative to repository average
4. CSV output includes both individual metrics and comparison data
5. Appropriate error handling for invalid or missing users
6. All existing functionality remains unchanged and working
7. Comprehensive test coverage for new features

