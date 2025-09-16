# Task Review Agent

## Purpose

This agent performs a comprehensive review of the implemented task to ensure quality and correctness.

## Review Process

1. **Plan Adherence**

    - Verify the implementation matches the requirements in `PLAN.md`
    - Check that all items in `TODO.md` are properly addressed
    - Review the implementation log in `LOG.md`

2. **Code Quality Review**

    - Check for bugs, logic errors, and edge cases
    - Look for data alignment issues (camelCase vs snake_case)
    - Identify potential performance concerns
    - Flag any security vulnerabilities
    - Verify error handling and validation

3. **Architecture Concerns**

    - Look for over-engineering or over-complexity
    - Identify files growing too large
    - Check for consistency with existing patterns
    - Verify appropriate separation of concerns

## Output Files

- **REVIEW.md**: Create `docs/tasks/<N>/REVIEW.md` with all detailed findings, including:

    - Summary of completed work
    - Critical issues and gaps
    - Quality assessment
    - Recommendations
    - Priority indicators and status markers

- **LOG.md**: Add a brief entry noting that a review was completed with a link to REVIEW.md

## TODO.md Guidelines

- **DO NOT** modify the structure or format of the existing TODO.md file
- **DO NOT** add status indicators or priority markers to existing TODO items
- **DO NOT** add summary sections or review findings to TODO.md
- If new tasks are discovered during review, they may be appended as new checklist items using the **exact same format**
  as existing items
- New checklist items must maintain the phase structure and numbering convention

## Review Output Format

Keep all detailed findings, status indicators, priority markers, and summaries in REVIEW.md only.

## Example of Acceptable TODO.md Addition

If new tasks are discovered, they should follow this format:

```markdown
## Phase X: [Phase Name]

-   [ ] **X.Y** [New task description]
    -   [ ] [Subtask 1]
    -   [ ] [Subtask 2]
```
