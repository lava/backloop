# Git Diff Reviewer

A web-based git diff viewer and review tool that provides an interface for reviewing code changes. The project consists of:

- **FastAPI web server** - Serves the review interface and API endpoints
- **MCP server integration** - Provides tools for starting review sessions and collecting comments
- **Git integration** - Reads diffs from git repositories and presents them in a reviewable format
- **Review session management** - Handles comment collection and review state

## Key Files

- `src/backloop/server.py` - Main FastAPI web server
- `src/backloop/mcp/server.py` - MCP server integration
- `src/backloop/review_manager.py` - Review session management
- `src/backloop/git_service.py` - Git operations and diff parsing
- `src/backloop/models.py` - Data models
- `src/backloop/api/router.py` - API endpoints

# Python Style Guide

Use empty __init__.py files and keep them empty. All code goes into
separate files.

Alway use package-relative imports of the form `from my_project.foo import bar`

# Testing

Before committing code changes, always run the test suite to ensure nothing is broken:

```bash
uv run pytest
```

For faster feedback during development, you can run specific test files:

```bash
# Run only unit tests (fast)
uv run pytest tests/test_models.py tests/test_git_service.py

# Run E2E integration tests (slower, but comprehensive)
uv run pytest tests/test_e2e_integration.py
```

The E2E integration tests start a real server and test the complete frontend + backend
integration, so they take longer to run but provide the most confidence that everything
works together correctly.