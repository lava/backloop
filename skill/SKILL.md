---
name: local-reviewing
description: Opens a browser-based diff viewer where the USER personally reviews and approves CLAUDE's code changes before committing or pushing. Use this skill when the user wants to inspect Claude's work themselves — e.g. "let me review your changes", "open a review session", "put your changes up for review", "I want to approve before we push". Do NOT use this skill when the user asks Claude to review THEIR code or give feedback on their changes — that's a normal code review task, not a local review session.
allowed-tools: mcp__local-review__startreview
---

*IMPORTANT*: This skill critically relies on the availability of the `local-review` MCP server.
If it is not available, tell the user that you're not able to provide local reviews due to
a misconfiguration, and print the list of available MCP tools to help debugging.

The high-level workflow looks like this:

 1) Start a review by calling `startreview()` and give the returned URL to the user
 2) Call `await_comments()`, and wait for a return value
 2a)   ... if receiving a comment, address it:
         - If you need to ask a question or report an issue, call `respond_comment()` with a message
         - Once the work is done, call `resolve_comment()` to mark it as resolved
       Go to (2) to await the next set of comments.
 2b)   ... if receiving REVIEW APPROVED, you are done and the review is approved.


# Reference:

Here's a detailed reference of the MCP server's available tools:

## Tool `startreview()`
Starts a code review session for a commit, range, or live changes.

### Parameters:
- commit: Review changes for a specific commit (e.g., 'abc123', 'HEAD', 'main')
- range: Review changes for a commit range (e.g., 'main..feature', 'abc123..def456')
- since: Review live changes since a commit (defaults to 'HEAD')
- title: Optional title for the review (will be used as the page title)

Note: Exactly one of commit, range, or since must be specified.

The `since` form includes all changes in the local directory that are not committed to git.
The `range` and `commit` forms only include the changes that are part of the specified
git commit range, independent of the current working directory.

### Usage:
This is typically used in one of three ways:
 - Reviewing changes just before committing: startreview(since='HEAD')
 - Reviewing changes just after committing changes: startreview(since='HEAD~1')
 - Reviewing a PR before pushing it: startreview(range='HEAD~3..HEAD')

## Tool `await_comments()`

Wait for review comments to be posted by the user.

Blocks until either:
- A comment is available (returns dict with comment details)
- The review is approved and no comments remain (returns "REVIEW APPROVED")


## Tool `resolve_comment()`

Marks a comment as resolved. Use this after you have addressed a comment.

### Parameters

- `comment_id`: The ID of the comment to mark as resolved

Returns a status message indicating success or failure.


## Tool `respond_comment()`

Sends a reply message on a comment thread. Use this to ask clarifying questions,
report difficulties, or provide non-trivial context back to the reviewer.

### Parameters

- `comment_id`: The ID of the comment to reply to
- `message`: The reply message to send

Returns a status message indicating success or failure.


# Workflow
To reiterate, the high-level workflow looks like this.

 1) Start a review by calling `startreview()` and give the returned URL to the user
 2) Call `await_comments()`, and wait for a return value
 2a)   ... if receiving a comment, address it:
         - If you need to ask a question or report an issue, call `respond_comment()` with a message
         - Once the work is done, call `resolve_comment()` to mark it as resolved
       Go to (2) and await the next set of comments.
 2b)   ... if receiving REVIEW APPROVED, you are done and the review is approved.

The correct parameters for `startreview()` depend on the intent behind starting the review. The
two most common cases are:

1) Reviewing local changes from the current agent session or PR. In this case, the `since=` form
   is used to give a complete picture of everything that's going on in the worktree.
2) Previewing a PR before opening it remotely. In this case the `range=` form is used to make it
   more obvious if important files are missing from the PR, or if unrelated changes were
   accidentally included.

If the parameters are not clear from the context, ask the user for clarification instead of
guessing.

The starting point for both `since` and `range` reviews is usually the merge-base of the
current branch.

If a comment is unclear or missing important information, use `respond_comment()` to ask for
clarification. Always prefer to ask instead of making assumptions, and ensure you have a complete
understanding of the requested change before starting the implementation.

Likewise, if you encounter unexpected difficulties when addressing a comment, prefer to use
`respond_comment()` to outline the issue and options to proceed, instead of blindly plowing through.

Do not use `respond_comment()` to send trivial replies like "ok", "done", "fixed the issue".

