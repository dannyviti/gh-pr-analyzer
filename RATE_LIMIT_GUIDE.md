# GitHub API Rate Limit Management Guide

## Overview

GitHub API has strict rate limits to ensure fair usage. This tool implements several strategies to handle and optimize
API usage while respecting these limits.

## Rate Limits

### GitHub API Limits

- **Authenticated requests**: 5,000 requests per hour
- **Unauthenticated requests**: 60 requests per hour (much lower)
- **Reset period**: Every hour (rolling window)

### Tool Usage Patterns

For each PR analyzed, the tool makes **5 API calls**:

1. `get_pr_reviews()` - Fetch PR review data
2. `get_pr_review_comments()` - Fetch review comments
3. `get_pr_timeline()` - Fetch PR timeline events
4. `get_pr_merge_info()` - Fetch merge information
5. `get_pr_commits()` - Fetch commit data

**Example**: Analyzing 100 PRs = ~500 API calls (10% of hourly limit)

## Enhanced Rate Limit Features

### 1. **Automatic Rate Limit Detection**

- Monitors `X-RateLimit-Remaining` header in every response
- Provides detailed error messages when rate limit is exceeded
- Shows exact reset time and wait duration

### 2. **Exponential Backoff with Retry Logic**

- Automatically retries failed requests (default: 3 attempts)
- Uses exponential backoff: 1s, 2s, 4s delays between retries
- Configurable via `--max-retries` parameter

### 3. **Proactive Rate Limit Management**

- Warns when less than 500 requests remain
- Shows critical warnings when less than 100 requests remain
- Logs current usage after each request

### 4. **Batch Processing**

- Processes PRs in configurable batches (default: 10)
- Adds delays between batches to spread API usage
- Configurable via `--batch-size` and `--batch-delay` parameters

### 5. **Rate Limit Status Checking**

- Check current rate limit status without analysis
- Provides usage recommendations
- Use `--check-rate-limit` flag

## Command Line Options

### Rate Limiting Options

```bash
# Control batch processing
--batch-size N          # Number of PRs per batch (default: 10)
--batch-delay N.N        # Delay between batches in seconds (default: 0.1)

# Control retry behavior
--max-retries N          # Maximum API request retries (default: 3)

# Check rate limit status
--check-rate-limit       # Show current rate limit status and exit
```

## Usage Examples

### 1. Check Rate Limit Status

```bash
python github_pr_analyzer.py --check-rate-limit
```

Output:

```
📊 GitHub API Rate Limit Status
========================================
Total Limit: 5,000 requests/hour
Used: 1,234 requests
Remaining: 3,766 requests
Reset Time: 2024-12-18 19:45:23
Usage: 24.7% of limit

✅ Rate limit status looks good for analysis.
```

### 2. Conservative Analysis (Small Batches)

```bash
# Process 5 PRs at a time with 0.5s delay between batches
python github_pr_analyzer.py microsoft/vscode --batch-size 5 --batch-delay 0.5
```

### 3. Aggressive Analysis (Larger Batches)

```bash
# Process 20 PRs at a time with minimal delay (use when rate limit is high)
python github_pr_analyzer.py facebook/react --batch-size 20 --batch-delay 0.05
```

### 4. Handle Network Issues

```bash
# Increase retries for unstable connections
python github_pr_analyzer.py kubernetes/kubernetes --max-retries 5
```

## Rate Limit Strategies

### Strategy 1: Check Before Running

```bash
# Always check rate limit first
python github_pr_analyzer.py --check-rate-limit

# If sufficient, run analysis
python github_pr_analyzer.py owner/repo
```

### Strategy 2: Conservative Approach

```bash
# Use small batches with delays for large repositories
python github_pr_analyzer.py owner/repo --batch-size 5 --batch-delay 1.0
```

### Strategy 3: Time-Based Analysis

```bash
# Analyze fewer months to reduce PR count
python github_pr_analyzer.py owner/repo --months 1
```

## Error Handling

### Rate Limit Exceeded Error

```
❌ GitHub API rate limit exceeded (4998/5000 used).
Rate limit resets at 2024-12-18 19:45:23 (wait 2847 seconds)
```

**Solutions:**

1. Wait for rate limit to reset
2. Use smaller `--batch-size`
3. Increase `--batch-delay`
4. Analyze fewer months with `--months`

### Network/API Errors

The tool automatically retries with exponential backoff for:

- Network timeouts
- Temporary API failures
- HTTP 5xx server errors

## Best Practices

### 1. Monitor Usage

- Always check rate limit before large analyses
- Monitor logs for rate limit warnings
- Use verbose mode (`-v`) to see detailed usage

### 2. Optimize Batch Settings

- **Large repositories (>100 PRs)**: `--batch-size 5 --batch-delay 0.5`
- **Medium repositories (20-100 PRs)**: `--batch-size 10 --batch-delay 0.1` (default)
- **Small repositories (<20 PRs)**: `--batch-size 20 --batch-delay 0.05`

### 3. Time Your Analysis

- Run during off-peak hours if possible
- Avoid running multiple analyses simultaneously
- Consider splitting large analyses across multiple hours

### 4. Use Appropriate Time Windows

```bash
# Instead of analyzing 12 months (many PRs):
python github_pr_analyzer.py owner/repo --months 12

# Consider analyzing 1-3 months for active repos:
python github_pr_analyzer.py owner/repo --months 3
```

## Troubleshooting

### High Rate Limit Usage

```bash
# Check current status
python github_pr_analyzer.py --check-rate-limit

# If usage is high (>90%), wait or use conservative settings
python github_pr_analyzer.py owner/repo --batch-size 3 --batch-delay 2.0
```

### Frequent Network Errors

```bash
# Increase retries and add delays
python github_pr_analyzer.py owner/repo --max-retries 5 --batch-delay 0.5
```

### Analysis Timing Out

```bash
# Reduce scope or increase delays
python github_pr_analyzer.py owner/repo --months 1 --batch-size 5
```

## Advanced Usage

### Custom Rate Limit Management

The tool provides detailed logging to help you optimize usage:

```bash
# Enable verbose logging to see rate limit info
python github_pr_analyzer.py owner/repo -v

# Enable debug logging for detailed API info
python github_pr_analyzer.py owner/repo --debug
```

### Batch Size Calculation

For a repository with N PRs and R remaining rate limit:

- **Minimum batches needed**: ceil(N \* 5 / R) (5 API calls per PR)
- **Recommended batch size**: min(N / 10, R / 50)
- **Recommended delay**: max(0.1, (3600 / R)) seconds

### Example Calculations

- 100 PRs, 1000 remaining requests: batch_size=10, delay=0.1s
- 200 PRs, 500 remaining requests: batch_size=5, delay=0.5s
- 50 PRs, 4000 remaining requests: batch_size=20, delay=0.05s

## Integration with CI/CD

### GitHub Actions Example

```yaml
- name: Check Rate Limit
  run: python github_pr_analyzer.py --check-rate-limit

- name: Analyze PRs (Conservative)
  run: python github_pr_analyzer.py ${{ github.repository }} --batch-size 5 --batch-delay 1.0
```

### Error Handling in Scripts

```bash
#!/bin/bash
# Check rate limit first
if ! python github_pr_analyzer.py --check-rate-limit; then
    echo "Rate limit issues detected"
    exit 1
fi

# Run analysis with conservative settings
python github_pr_analyzer.py owner/repo --batch-size 5 --batch-delay 0.5
```

This comprehensive rate limit management ensures reliable, efficient API usage while respecting GitHub's limits.
