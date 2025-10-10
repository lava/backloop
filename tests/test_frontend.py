"""End-to-end tests for the frontend review interface using Playwright."""

import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Generator

import pytest
import requests
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
    """Create a temporary git repository with test files."""
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
        (repo_path / "test.py").write_text(
            "def hello():\n    print('Hello')\n"
        )
        (repo_path / "README.md").write_text("# Test\n")

        # Initial commit
        subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=repo_path,
            capture_output=True,
            check=True,
        )

        # Make some uncommitted changes for testing
        (repo_path / "test.py").write_text(
            "def hello():\n    print('Hello, World!')\n"
        )
        (repo_path / "README.md").write_text("# Test\n\nModified.\n")

        yield repo_path


@pytest.fixture(scope="module")
def server_port() -> int:
    """Get a free port for the test server."""
    return find_free_port()


@pytest.fixture(scope="module")
def server_process(test_git_repo: Path, server_port: int) -> Generator[subprocess.Popen[bytes], None, None]:
    """Start the FastAPI server for testing."""
    # Start the server in the test git repo
    process = subprocess.Popen(
        ["uv", "run", "server", "--port", str(server_port)],
        cwd=test_git_repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Wait for server to be ready (with health check)
    max_retries = 20  # 10 seconds max
    for i in range(max_retries):
        try:
            response = requests.get(f"http://localhost:{server_port}/health", timeout=1)
            if response.status_code == 200:
                break
        except (requests.ConnectionError, requests.Timeout):
            time.sleep(0.5)
    else:
        process.terminate()
        raise RuntimeError("Server failed to start within 10 seconds")

    yield process
    # Clean up
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


@pytest.fixture(scope="module")
def server_url(server_port: int) -> str:
    """Return the base URL for the test server."""
    return f"http://localhost:{server_port}"


@pytest.fixture(autouse=True)
def configure_page_timeout(page: Page) -> None:
    """Configure shorter timeouts for faster test failures."""
    page.set_default_timeout(5000)  # 5 seconds instead of 30


@pytest.fixture(scope="module")
def loaded_page(page: Page, server_process: Any, server_url: str) -> Page:
    """Return a page that has already loaded the review interface (for module reuse)."""
    page.goto(f"{server_url}/?mock=true")
    page.wait_for_selector(".diff-pane", timeout=5000)
    return page


def test_review_page_loads(page: Page, server_process: Any, server_url: str) -> None:
    """Test that the review page loads successfully."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Check that the page title is correct
    expect(page).to_have_title("Backloop Code Review")

    # Check that the header is present
    header = page.locator("h1")
    expect(header).to_contain_text("Code Review")

    # Check that the approve button is present
    approve_button = page.locator("#approve-review-btn")
    expect(approve_button).to_be_visible()


def test_file_tree_displays(page: Page, server_process: Any, server_url: str) -> None:
    """Test that the file tree is displayed."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for file tree to be populated
    page.wait_for_selector(".file-tree")

    # Check that the file tree has files
    file_tree = page.locator(".file-tree")
    expect(file_tree).to_be_visible()

    # Check that there's at least one file in the tree
    file_items = page.locator(".file-tree-item")
    expect(file_items.first).to_be_visible()


def test_diff_panes_display(page: Page, server_process: Any, server_url: str) -> None:
    """Test that the diff panes are displayed."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-pane")

    # Check that both panes are present
    old_pane = page.locator("#old-pane")
    new_pane = page.locator("#new-pane")

    expect(old_pane).to_be_visible()
    expect(new_pane).to_be_visible()

    # Check that pane headers are correct
    expect(old_pane.locator(".diff-pane-header")).to_contain_text("Before")
    expect(new_pane.locator(".diff-pane-header")).to_contain_text("After")


def test_line_numbers_display(page: Page, server_process: Any, server_url: str) -> None:
    """Test that line numbers are displayed in the diff view."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Check that line numbers are present
    line_numbers = page.locator(".line-number")
    expect(line_numbers.first).to_be_visible()


def test_comment_form_appears(page: Page, server_process: Any, server_url: str) -> None:
    """Test that clicking a line number shows the comment form."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Click on a line number (not the line itself) to show the comment form
    line_number = page.locator(".line-number").first
    line_number.click()

    # Check that the comment form appears
    comment_form = page.locator(".comment-form")
    expect(comment_form).to_be_visible()

    # Check that the form has a textarea
    textarea = comment_form.locator("textarea")
    expect(textarea).to_be_visible()

    # Check that the form has submit and cancel buttons
    submit_button = comment_form.locator('button[data-action="submit"]')
    cancel_button = comment_form.locator('button[data-action="cancel"]')
    expect(submit_button).to_be_visible()
    expect(cancel_button).to_be_visible()


def test_comment_form_cancels(page: Page, server_process: Any, server_url: str) -> None:
    """Test that canceling a comment form removes it."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Click on a line number to show the comment form
    line_number = page.locator(".line-number").first
    line_number.click()

    # Wait for the comment form to appear
    comment_form = page.locator(".comment-form")
    expect(comment_form).to_be_visible()

    # Click the cancel button
    cancel_button = comment_form.locator('button[data-action="cancel"]')
    cancel_button.click()

    # Check that the comment form is removed
    expect(comment_form).not_to_be_visible()


def test_comment_submission(page: Page, server_process: Any, server_url: str) -> None:
    """Test that submitting a comment displays it."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Click on a line number to show the comment form
    line_number = page.locator(".line-number").first
    line_number.click()

    # Wait for the comment form to appear
    comment_form = page.locator(".comment-form")
    expect(comment_form).to_be_visible()

    # Enter a comment
    textarea = comment_form.locator("textarea")
    textarea.fill("This is a test comment")

    # Submit the comment
    submit_button = comment_form.locator('button[data-action="submit"]')
    submit_button.click()

    # Check that the comment thread appears
    comment_thread = page.locator(".comment-thread")
    expect(comment_thread).to_be_visible()

    # Check that the comment content is displayed
    comment_body = comment_thread.locator(".comment-body")
    expect(comment_body).to_contain_text("This is a test comment")


def test_comment_deletion(page: Page, server_process: Any, server_url: str) -> None:
    """Test that deleting a comment removes it."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Click on a line number to show the comment form
    line_number = page.locator(".line-number").first
    line_number.click()

    # Wait for the comment form to appear
    comment_form = page.locator(".comment-form")
    textarea = comment_form.locator("textarea")
    unique_comment_text = "Unique comment to delete 12345"
    textarea.fill(unique_comment_text)

    # Submit the comment
    submit_button = comment_form.locator('button[data-action="submit"]')
    submit_button.click()

    # Wait for the specific comment thread to appear
    comment_thread = page.locator(".comment-thread").filter(has_text=unique_comment_text)
    expect(comment_thread).to_be_visible()

    # Click the delete button
    delete_button = comment_thread.locator(".comment-delete-btn")
    delete_button.click()

    # Check that the comment thread is removed
    expect(comment_thread).not_to_be_visible()


def test_approve_review_button(page: Page, server_process: Any, server_url: str) -> None:
    """Test that the approve review button works."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for the page to load
    page.wait_for_selector("#approve-review-btn")

    # Click the approve button
    approve_button = page.locator("#approve-review-btn")

    # Listen for the confirmation dialog
    page.on("dialog", lambda dialog: dialog.accept())

    approve_button.click()

    # The button should trigger an API call (we can verify this in network logs if needed)
    # For now, we just verify the button is clickable


def test_websocket_connection_status(page: Page, server_process: Any, server_url: str) -> None:
    """Test that the WebSocket connection status element is attached."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for the page to load and WebSocket to connect
    time.sleep(1)

    # Check that the connection status element exists (it's CSS-hidden but has connected class)
    status = page.locator("#connection-status")
    expect(status).to_be_attached()
    expect(status).to_have_class("connection-status connected")


def test_cancel_button_closes_comment_form(page: Page, server_process: Any, server_url: str) -> None:
    """Test that clicking cancel button closes the comment form."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Click on a line number to show the comment form
    line_number = page.locator(".line-number").first
    line_number.click()

    # Wait for the comment form to appear
    comment_form = page.locator(".comment-form")
    expect(comment_form).to_be_visible()

    # Click the cancel button (Escape key is only for closing modals, not comment forms)
    cancel_button = comment_form.locator('button[data-action="cancel"]')
    cancel_button.click()

    # Check that the comment form is removed
    expect(comment_form).not_to_be_visible()


def test_file_navigation(page: Page, server_process: Any, server_url: str) -> None:
    """Test that clicking on a file in the tree navigates to it."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for file tree to be populated
    page.wait_for_selector(".file-tree-item")

    # Click on the first file in the tree
    file_item = page.locator(".file-tree-item").first
    file_item.click()

    # The page should scroll to the file section
    # We can verify this by checking if the URL hash changed or if the element is in view
    # For now, we just verify that the click works without errors


def test_comment_on_deleted_and_added_lines(page: Page, server_process: Any, server_url: str) -> None:
    """Test that users can comment on empty lines (deleted lines in new pane, added lines in old pane)."""
    page.goto(server_url)
    page.wait_for_url("**/review/*/view*")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Test 1: Click on a deleted line in the NEW pane (should be empty/blank)
    # Find a deletion in the old pane to get the shared line index
    old_pane = page.locator("#old-pane")
    deleted_line_old = old_pane.locator(".diff-line.deletion").first

    # Get the file path and shared line index to find the corresponding empty line in new pane
    file_path = deleted_line_old.get_attribute("data-file-path")
    shared_index = deleted_line_old.get_attribute("data-shared-line-index")

    # Find the corresponding empty line in the new pane (same file, same shared index)
    new_pane = page.locator("#new-pane")
    empty_line_in_new = new_pane.locator(f".diff-line[data-file-path='{file_path}'][data-shared-line-index='{shared_index}']")

    # This should be an empty-line
    expect(empty_line_in_new).to_have_class("diff-line deletion empty-line")

    # Try to click on the line number of this empty line
    empty_line_number = empty_line_in_new.locator(".line-number")
    empty_line_number.click()

    # Check that the comment form appears (this should work after the fix)
    comment_form = page.locator(".comment-form")
    expect(comment_form).to_be_visible()

    # Cancel the form
    cancel_button = comment_form.locator('button[data-action="cancel"]')
    cancel_button.click()
    expect(comment_form).not_to_be_visible()

    # Test 2: Click on an added line in the OLD pane (should be empty/blank)
    # Find an addition in the new pane
    added_line_new = new_pane.locator(".diff-line.addition").first

    # Get the file path and shared line index
    file_path2 = added_line_new.get_attribute("data-file-path")
    shared_index2 = added_line_new.get_attribute("data-shared-line-index")

    # Find the corresponding empty line in the old pane (same file, same shared index)
    empty_line_in_old = old_pane.locator(f".diff-line[data-file-path='{file_path2}'][data-shared-line-index='{shared_index2}']")

    # This should be an empty-line
    expect(empty_line_in_old).to_have_class("diff-line addition empty-line")

    # Try to click on the line number of this empty line
    empty_line_number2 = empty_line_in_old.locator(".line-number")
    empty_line_number2.click()

    # Check that the comment form appears
    expect(comment_form).to_be_visible()

    # Enter and submit a comment
    textarea = comment_form.locator("textarea")
    textarea.fill("Comment on empty line (addition in old pane)")
    submit_button = comment_form.locator('button[data-action="submit"]')
    submit_button.click()

    # Check that the comment thread appears with our specific text
    comment_thread = page.locator(".comment-thread").filter(has_text="Comment on empty line (addition in old pane)")
    expect(comment_thread).to_be_visible()
    expect(comment_thread.locator(".comment-body")).to_contain_text("Comment on empty line (addition in old pane)")
