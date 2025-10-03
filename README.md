# Backloop

A web-based git diff viewer and review tool that enables AI-assisted
code reviews with Claude.

## Overview

Backloop provides a streamlined workflow for reviewing code changes with
AI assistance. It works by:

1. **Capturing git diffs** - Monitors your repository for changes
   (uncommitted, specific commits, or commit ranges)
2. **Presenting a review interface** - Opens a web UI showing the diff
   with an inline commenting system
3. **AI integration** - Claude can see your comments through MCP tools
   and address them iteratively
4. **Resolution tracking** - Comments are marked as resolved as Claude
   fixes issues, continuing until you approve

This creates a collaborative review loop where you mark issues in the UI
and Claude automatically sees and addresses them.

## MCP Server Setup

To add the MCP server to Claude Code, run:

```bash
claude mcp add local-review -- uvx run --from backloop backloop-mcp
```

## Standalone Usage

You can also use Backloop without an agent, as a standalone diff
viewer:

```bash
uv run server
```

This starts the web server which you can use to view and comment on
diffs manually.

## MCP Tools Reference

Once configured, Claude has access to these MCP tools:

### `startreview`
Starts a new review session. Exactly one parameter must be specified:
- `since='HEAD'` - Review uncommitted changes (default)
- `commit='abc123'` - Review a specific commit
- `range='main..feature'` - Review a range of commits

**Examples:**
- Review before committing: `startreview(since='HEAD')`
- Review after committing: `startreview(since='HEAD~1')`
- Review a PR branch: `startreview(range='origin/main..HEAD')`

### `await_comments`
Blocks until either a comment is posted or the review is approved.
Returns comment details (including the originating `review_id`) or "REVIEW APPROVED".

### `resolve_comment`
Marks a specific comment as resolved by its ID.
