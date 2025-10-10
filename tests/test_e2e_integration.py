"""End-to-end integration tests for frontend + server using real data.

These tests start an actual FastAPI server with a real git repository and test
the complete interaction between the frontend (via Playwright) and backend,
including WebSocket connections, comment workflows, and review approval.
"""

import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Generator

import pytest
from playwright.sync_api import Page, expect


def find_free_port() -> int:
    """Find a random free port on the system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


@pytest.fixture(scope="module")
def test_git_repo() -> Generator[Path, None, None]:
    """Create a temporary git repository with test files for E2E testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize git repo
        subprocess.run(
            ["git", "init"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        # Configure git
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        # Create initial file structure
        (repo_path / "src").mkdir()
        (repo_path / "src" / "main.py").write_text(
            "def hello():\n    print('Hello')\n"
        )
        (repo_path / "README.md").write_text("# Test Project\n\nThis is a test.\n")

        # Initial commit
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        # Make some changes for testing
        (repo_path / "src" / "main.py").write_text(
            "def hello():\n    print('Hello, World!')\n\ndef goodbye():\n    print('Goodbye')\n"
        )
        (repo_path / "README.md").write_text(
            "# Test Project\n\nThis is a test project for E2E testing.\n"
        )
        (repo_path / "src" / "utils.py").write_text(
            "def helper():\n    return 42\n"
        )

        # Second commit with changes
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Add features and utils"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        # Make some uncommitted changes so the default `since=HEAD` review shows diffs
        (repo_path / "README.md").write_text(
            "# Test Project\n\nThis is a test project for E2E testing.\n\nUncommitted changes here!\n"
        )
        (repo_path / "src" / "main.py").write_text(
            "def hello():\n    print('Hello, World! (modified)')\n\ndef goodbye():\n    print('Goodbye')\n"
        )

        yield repo_path


@pytest.fixture(scope="module")
def server_port() -> int:
    """Get a free port for the test server."""
    return find_free_port()


@pytest.fixture(scope="module")
def server_process(
    test_git_repo: Path, server_port: int
) -> Generator[subprocess.Popen[bytes], None, None]:
    """Start the FastAPI server in the test git repository."""
    # Start the server in the test repository directory
    process = subprocess.Popen(
        ["uv", "run", "server", "--port", str(server_port)],
        cwd=test_git_repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Give the server more time to start and initialize
    time.sleep(3)

    # Check if the process is still running
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        raise RuntimeError(
            f"Server failed to start. stdout: {stdout.decode()}, stderr: {stderr.decode()}"
        )

    yield process

    # Clean up
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@pytest.fixture(scope="module")
def server_url(server_port: int) -> str:
    """Return the base URL for the test server."""
    return f"http://localhost:{server_port}"


@pytest.fixture(scope="module")
def review_url(server_process: Any, server_url: str) -> str:
    """Get the URL for the active review session.

    The server creates a default review session on startup.
    """
    # Give the server a moment to create the default review session
    time.sleep(0.5)

    # The server will redirect / to the most recent review
    # We just return the base URL and let the redirect happen
    return server_url


class TestBasicPageLoading:
    """Test basic page loading and UI elements with real server."""

    def test_review_page_loads(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test that the review page loads successfully with real data."""
        page.goto(review_url)

        # Wait for redirect to complete
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Check that the page title is correct
        expect(page).to_have_title("Backloop Code Review")

        # Check that the header is present
        header = page.locator("h1")
        expect(header).to_contain_text("Code Review")

    def test_file_tree_displays_real_files(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test that the file tree displays actual files from the git diff."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for file tree to be populated with real data
        page.wait_for_selector(".file-tree", timeout=10000)

        # Check that the file tree has files
        file_tree = page.locator(".file-tree")
        expect(file_tree).to_be_visible()

        # Check that we can see our actual test files
        # We should have at least the uncommitted changes (README.md and src/main.py)
        file_items = page.locator(".file-tree-item")
        # Just check that we have some files - the exact count depends on git diff behavior
        expect(file_items.first).to_be_visible()

    def test_diff_content_shows_real_changes(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test that the diff view shows actual git diff content."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for diff content to be populated
        page.wait_for_selector(".diff-line", timeout=10000)

        # Check that diff panes are visible
        old_pane = page.locator("#old-pane")
        new_pane = page.locator("#new-pane")
        expect(old_pane).to_be_visible()
        expect(new_pane).to_be_visible()

        # Check that we can see actual content from our test files
        # Look for content that should be in the diff
        page_content = page.content()
        assert "Hello" in page_content or "README" in page_content

    def test_websocket_connects(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test that WebSocket connection is established."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for WebSocket connection
        # The connection status element exists but may be hidden in CSS
        status = page.locator("#connection-status")
        expect(status).to_be_attached()

        # Wait a bit for WebSocket to connect
        time.sleep(2)

        # Check that the status has the 'connected' class (indicating successful connection)
        # The element may be CSS-hidden but still have the class
        expect(status).to_have_class("connection-status connected", timeout=5000)


class TestCommentWorkflow:
    """Test the complete comment creation and management workflow."""

    def test_add_comment_to_line(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test adding a comment to a specific line."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for diff content
        page.wait_for_selector(".diff-line", timeout=10000)

        # Click on a line number to show the comment form (not the line itself)
        line_number = page.locator(".line-number").first
        line_number.click()

        # Wait for the comment form to appear
        comment_form = page.locator(".comment-form")
        expect(comment_form).to_be_visible(timeout=5000)

        # Enter a comment
        textarea = comment_form.locator("textarea")
        test_comment = "This is an E2E integration test comment"
        textarea.fill(test_comment)

        # Submit the comment
        submit_button = comment_form.locator('button[data-action="submit"]')
        submit_button.click()

        # Check that the comment thread appears
        comment_thread = page.locator(".comment-thread").filter(
            has_text=test_comment
        )
        expect(comment_thread).to_be_visible(timeout=5000)

        # Check that the comment content is displayed
        comment_body = comment_thread.locator(".comment-body")
        expect(comment_body).to_contain_text(test_comment)

    def test_delete_comment(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test deleting a comment."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for diff content
        page.wait_for_selector(".diff-line", timeout=10000)

        # Add a comment first
        line_number = page.locator(".line-number").first
        line_number.click()

        comment_form = page.locator(".comment-form")
        textarea = comment_form.locator("textarea")
        test_comment = "Comment to be deleted"
        textarea.fill(test_comment)

        submit_button = comment_form.locator('button[data-action="submit"]')
        submit_button.click()

        # Wait for the comment to appear
        comment_thread = page.locator(".comment-thread").filter(
            has_text=test_comment
        )
        expect(comment_thread).to_be_visible(timeout=5000)

        # Delete the comment
        delete_button = comment_thread.locator(".comment-delete-btn")
        delete_button.click()

        # Check that the comment thread is removed
        expect(comment_thread).not_to_be_visible()

    def test_cancel_comment_form(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test canceling a comment form."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for diff content
        page.wait_for_selector(".diff-line", timeout=10000)

        # Click on a line number
        line_number = page.locator(".line-number").first
        line_number.click()

        # Wait for form
        comment_form = page.locator(".comment-form")
        expect(comment_form).to_be_visible()

        # Enter some text
        textarea = comment_form.locator("textarea")
        textarea.fill("This will be canceled")

        # Click cancel
        cancel_button = comment_form.locator('button[data-action="cancel"]')
        cancel_button.click()

        # Check that form is removed
        expect(comment_form).not_to_be_visible()

    def test_multiple_comments_on_different_lines(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test adding multiple comments on different lines."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for diff content
        page.wait_for_selector(".diff-line", timeout=10000)

        # Add first comment
        line_numbers = page.locator(".line-number")
        first_line_num = line_numbers.nth(0)
        first_line_num.click()

        comment_form = page.locator(".comment-form")
        textarea = comment_form.locator("textarea")
        textarea.fill("First comment")
        comment_form.locator('button[data-action="submit"]').click()

        # Wait for first comment to appear
        first_comment = page.locator(".comment-thread").filter(has_text="First comment")
        expect(first_comment).to_be_visible(timeout=5000)

        # Add second comment on a different line
        second_line_num = line_numbers.nth(5)
        second_line_num.click()

        # Need to wait for the new comment form to appear
        page.wait_for_selector(".comment-form", timeout=5000)
        comment_form = page.locator(".comment-form")
        textarea = comment_form.locator("textarea")
        textarea.fill("Second comment")
        comment_form.locator('button[data-action="submit"]').click()

        # Wait for second comment to appear
        second_comment = page.locator(".comment-thread").filter(
            has_text="Second comment"
        )
        expect(second_comment).to_be_visible(timeout=5000)

        # Both comments should be visible
        expect(first_comment).to_be_visible()
        expect(second_comment).to_be_visible()


class TestReviewApproval:
    """Test the review approval workflow."""

    def test_approve_review_button_works(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test that clicking approve triggers the approval workflow."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for page to load
        page.wait_for_selector("#approve-review-btn", timeout=10000)

        # Set up dialog handler before clicking
        page.on("dialog", lambda dialog: dialog.accept())

        # Click the approve button
        approve_button = page.locator("#approve-review-btn")
        approve_button.click()

        # The approval should be processed
        # We can check for network activity or status changes
        # For now, just verify the button was clickable and dialog appeared
        time.sleep(1)


class TestFileNavigation:
    """Test file navigation in the file tree."""

    def test_click_file_in_tree(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test that clicking a file in the tree navigates to it."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for file tree
        page.wait_for_selector(".file-tree-item", timeout=10000)

        # Click on the first file
        file_item = page.locator(".file-tree-item").first
        file_item.click()

        # The page should scroll or navigate to the file section
        # Just verify no error occurred
        time.sleep(0.5)


class TestRealTimeUpdates:
    """Test real-time updates via WebSocket."""

    def test_comment_persistence_across_reload(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test that comments persist and reload correctly."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Add a comment
        page.wait_for_selector(".diff-line", timeout=10000)
        line_number = page.locator(".line-number").first
        line_number.click()

        comment_form = page.locator(".comment-form")
        textarea = comment_form.locator("textarea")
        persistent_comment = "This comment should persist across reload"
        textarea.fill(persistent_comment)
        comment_form.locator('button[data-action="submit"]').click()

        # Wait for comment to appear
        comment_thread = page.locator(".comment-thread").filter(
            has_text=persistent_comment
        )
        expect(comment_thread).to_be_visible(timeout=5000)

        # Reload the page
        page.reload()
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for page to fully load
        page.wait_for_selector(".diff-line", timeout=10000)

        # Comment should still be there
        reloaded_comment = page.locator(".comment-thread").filter(
            has_text=persistent_comment
        )
        expect(reloaded_comment).to_be_visible(timeout=5000)

    def test_in_progress_comment_survives_file_change(
        self, page: Page, server_process: Any, review_url: str, test_git_repo: Path
    ) -> None:
        """Test that an in-progress comment doesn't disappear when the underlying file changes."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for diff content to load
        page.wait_for_selector(".diff-line", timeout=10000)

        # Click on a line to open the comment form
        line_number = page.locator(".line-number").first
        line_number.click()

        # Wait for the comment form to appear
        comment_form = page.locator(".comment-form")
        expect(comment_form).to_be_visible(timeout=5000)

        # Start typing a comment (but don't submit it yet)
        textarea = comment_form.locator("textarea")
        in_progress_text = "This comment is being written while the file changes"
        textarea.fill(in_progress_text)

        # Verify the comment text is there
        expect(textarea).to_have_value(in_progress_text)

        # Now modify the underlying file to trigger a file change
        readme_path = test_git_repo / "README.md"
        readme_path.write_text(
            "# Test Project\n\nThis is a test project for E2E testing.\n\nFile modified during comment!\n"
        )

        # Give some time for the file change to be detected and processed
        # The system should reload the file content but preserve the in-progress comment
        # File watchers can take a moment to detect changes
        time.sleep(3)

        # The comment form should still be visible
        expect(comment_form).to_be_visible()

        # The textarea should still contain the in-progress comment text
        expect(textarea).to_have_value(in_progress_text)

        # We should be able to submit the comment successfully
        submit_button = comment_form.locator('button[data-action="submit"]')
        submit_button.click()

        # The comment should appear as a thread
        comment_thread = page.locator(".comment-thread").filter(
            has_text=in_progress_text
        )
        expect(comment_thread).to_be_visible(timeout=5000)


class TestCommentAlignment:
    """Test that comments and forms maintain alignment between old/new panes."""

    def test_comment_creates_spacer_in_opposite_pane(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test that adding a comment creates a spacer in the opposite pane for alignment."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for diff content
        page.wait_for_selector(".diff-line", timeout=10000)

        # Add a comment to a line in the new (right) pane
        line_numbers = page.locator("#new-pane .line-number")
        line_numbers.first.click()

        comment_form = page.locator(".comment-form")
        textarea = comment_form.locator("textarea")
        test_comment = "Comment for alignment test"
        textarea.fill(test_comment)
        comment_form.locator('button[data-action="submit"]').click()

        # Wait for comment to appear
        comment_thread = page.locator(".comment-thread").filter(has_text=test_comment)
        expect(comment_thread).to_be_visible(timeout=5000)

        # Check that a spacer was created in the old (left) pane
        # The spacer should have the class 'comment-spacer'
        spacer = page.locator("#old-pane .comment-spacer").first
        expect(spacer).to_be_attached()

        # The spacer should have a height set (not 0px or empty)
        spacer_height = spacer.evaluate("el => el.style.height")
        assert spacer_height != "", "Spacer should have a height set"
        assert spacer_height != "0px", "Spacer height should not be 0"

    def test_comment_form_creates_spacer_in_opposite_pane(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test that opening a comment form creates a spacer in the opposite pane."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for diff content
        page.wait_for_selector(".diff-line", timeout=10000)

        # Click a line number to open comment form in the new (right) pane
        line_numbers = page.locator("#new-pane .line-number")
        line_numbers.first.click()

        # Wait for form to appear
        comment_form = page.locator(".comment-form")
        expect(comment_form).to_be_visible(timeout=5000)

        # Check that a form spacer was created in the old (left) pane
        form_spacer = page.locator("#old-pane .comment-form-spacer").first
        expect(form_spacer).to_be_attached()

        # Wait a moment for requestAnimationFrame to set the height
        time.sleep(0.2)

        # The spacer should have a height
        spacer_height = form_spacer.evaluate("el => el.style.height")
        assert spacer_height != "" and spacer_height != "0px", f"Form spacer should have a height set, got: {spacer_height}"

        # Cancel the form and verify spacer is removed
        cancel_button = comment_form.locator('button[data-action="cancel"]')
        cancel_button.click()

        # Form should be gone
        expect(comment_form).not_to_be_visible()

        # Spacer should also be gone
        expect(form_spacer).not_to_be_attached()

    def test_deleting_comment_removes_spacer(
        self, page: Page, server_process: Any, review_url: str
    ) -> None:
        """Test that deleting a comment also removes its spacer."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for diff content
        page.wait_for_selector(".diff-line", timeout=10000)

        # Add a comment
        line_numbers = page.locator("#new-pane .line-number")
        line_numbers.first.click()

        comment_form = page.locator(".comment-form")
        textarea = comment_form.locator("textarea")
        test_comment = "Comment to be deleted with spacer"
        textarea.fill(test_comment)
        comment_form.locator('button[data-action="submit"]').click()

        # Wait for comment to appear
        comment_thread = page.locator(".comment-thread").filter(has_text=test_comment)
        expect(comment_thread).to_be_visible(timeout=5000)

        # Get the comment ID to find the specific spacer
        comment_id = comment_thread.get_attribute("data-comment-id")

        # Verify spacer exists with matching comment ID
        spacer = page.locator(f"#old-pane .comment-spacer[data-comment-id='{comment_id}']")
        expect(spacer).to_be_attached()

        # Delete the comment
        delete_button = comment_thread.locator(".comment-delete-btn")
        delete_button.click()

        # Comment should be gone
        expect(comment_thread).not_to_be_visible()

        # Spacer should also be gone
        expect(spacer).not_to_be_attached()


class TestCommentResolution:
    """Test comment resolution workflow with real-time UI updates."""

    def test_comment_auto_resolves_via_websocket(
        self, page: Page, server_process: Any, review_url: str, test_git_repo: Path
    ) -> None:
        """Test that comment UI automatically updates to 'resolved' when resolved via WebSocket."""
        page.goto(review_url)
        page.wait_for_url("**/review/*/view*", timeout=10000)

        # Wait for diff content
        page.wait_for_selector(".diff-line", timeout=10000)

        # Add a comment specifically on the RIGHT pane (new side) to test the bug
        # This ensures the spacer is created in the left pane BEFORE the comment thread
        # in DOM order, which would cause querySelector to find the spacer first
        line_number = page.locator("#new-pane .line-number").first
        line_number.click()

        comment_form = page.locator(".comment-form")
        textarea = comment_form.locator("textarea")
        test_comment = "Comment that will be auto-resolved"
        textarea.fill(test_comment)

        submit_button = comment_form.locator('button[data-action="submit"]')
        submit_button.click()

        # Wait for the comment to appear
        comment_thread = page.locator(".comment-thread").filter(has_text=test_comment)
        expect(comment_thread).to_be_visible(timeout=5000)

        # Verify the comment is NOT resolved initially (no resolved badge)
        resolved_badge = comment_thread.locator('span:has-text("✓ Resolved")')
        expect(resolved_badge).not_to_be_visible()

        # Extract the comment ID from the DOM
        comment_id = comment_thread.get_attribute("data-comment-id")
        assert comment_id is not None, "Comment ID should be present"

        # Simulate a WebSocket message arriving that resolves the comment
        # This is what would happen when the MCP tool calls resolve_comment
        page.evaluate(
            f"""
            (async () => {{
                // Simulate the websocket-client.js handleEvent function receiving a message
                const event = {{
                    type: 'comment_resolved',
                    data: {{
                        comment_id: '{comment_id}',
                        status: 'resolved',
                        reply_message: 'Test resolution from WebSocket'
                    }}
                }};

                // Find the websocket handler and trigger it
                // The handler is registered via onEvent in main.js
                // We need to manually dispatch this through the event system

                // Check if window has the websocket client's event handlers
                if (!window._websocketEventHandlers) {{
                    throw new Error('WebSocket event handlers not initialized');
                }}

                // Trigger the event through the registered handlers
                const eventType = event.type;
                const handlers = window._websocketEventHandlers[eventType];

                if (!handlers || handlers.length === 0) {{
                    throw new Error(`No handlers registered for ${{eventType}}`);
                }}

                // Call each handler
                handlers.forEach(handler => {{
                    handler(event);
                }});

                return 'Event dispatched successfully';
            }})()
            """
        )

        # Now verify that the comment appears resolved
        time.sleep(0.5)  # Small delay for UI update
        resolved_badge = comment_thread.locator('span:has-text("✓ Resolved")')
        expect(resolved_badge).to_be_visible(timeout=5000)

        # Check that visual styling is applied
        comment_body = comment_thread.locator(".comment-body")
        expect(comment_body).to_have_css("text-decoration-line", "line-through")

        # Check that the resolution note appears
        resolution_note = comment_thread.locator(".resolution-note")
        expect(resolution_note).to_be_visible()
        expect(resolution_note).to_contain_text("Test resolution")
