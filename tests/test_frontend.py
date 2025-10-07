"""End-to-end tests for the frontend review interface using Playwright."""

import socket
import subprocess
import time
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
def server_port() -> int:
    """Get a free port for the test server."""
    return find_free_port()


@pytest.fixture(scope="module")
def server_process(server_port: int) -> Generator[subprocess.Popen[bytes], None, None]:
    """Start the FastAPI server for testing."""
    # Start the server in a subprocess
    process = subprocess.Popen(
        ["uv", "run", "server", "--port", str(server_port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Give the server time to start
    time.sleep(2)
    yield process
    # Clean up
    process.terminate()
    process.wait()


@pytest.fixture(scope="module")
def server_url(server_port: int) -> str:
    """Return the base URL for the test server."""
    return f"http://localhost:{server_port}"


def test_review_page_loads(page: Page, server_process: Any, server_url: str) -> None:
    """Test that the review page loads successfully."""
    page.goto(f"{server_url}/?mock=true")

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
    page.goto(f"{server_url}/?mock=true")

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
    page.goto(f"{server_url}/?mock=true")

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
    page.goto(f"{server_url}/?mock=true")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Check that line numbers are present
    line_numbers = page.locator(".line-number")
    expect(line_numbers.first).to_be_visible()


def test_comment_form_appears(page: Page, server_process: Any, server_url: str) -> None:
    """Test that clicking a line shows the comment form."""
    page.goto(f"{server_url}/?mock=true")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Click on a line to show the comment form
    line = page.locator(".diff-line").first
    line.click()

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
    page.goto(f"{server_url}/?mock=true")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Click on a line to show the comment form
    line = page.locator(".diff-line").first
    line.click()

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
    page.goto(f"{server_url}/?mock=true")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Click on a line to show the comment form
    line = page.locator(".diff-line").first
    line.click()

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
    page.goto(f"{server_url}/?mock=true")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Click on a line to show the comment form
    line = page.locator(".diff-line").first
    line.click()

    # Wait for the comment form to appear
    comment_form = page.locator(".comment-form")
    textarea = comment_form.locator("textarea")
    textarea.fill("Comment to delete")

    # Submit the comment
    submit_button = comment_form.locator('button[data-action="submit"]')
    submit_button.click()

    # Wait for the comment thread to appear
    comment_thread = page.locator(".comment-thread")
    expect(comment_thread).to_be_visible()

    # Click the delete button
    delete_button = comment_thread.locator(".comment-delete-btn")
    delete_button.click()

    # Check that the comment thread is removed
    expect(comment_thread).not_to_be_visible()


def test_approve_review_button(page: Page, server_process: Any, server_url: str) -> None:
    """Test that the approve review button works."""
    page.goto(f"{server_url}/?mock=true")

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
    """Test that the WebSocket connection status is displayed."""
    page.goto(f"{server_url}/?mock=true")

    # Wait for the page to load
    page.wait_for_selector("#connection-status")

    # Check that the connection status element exists
    status = page.locator("#connection-status")
    expect(status).to_be_visible()


def test_keyboard_shortcuts_escape(page: Page, server_process: Any, server_url: str) -> None:
    """Test that pressing Escape closes the comment form."""
    page.goto(f"{server_url}/?mock=true")

    # Wait for diff content to be populated
    page.wait_for_selector(".diff-line")

    # Click on a line to show the comment form
    line = page.locator(".diff-line").first
    line.click()

    # Wait for the comment form to appear
    comment_form = page.locator(".comment-form")
    expect(comment_form).to_be_visible()

    # Press Escape
    page.keyboard.press("Escape")

    # Check that the comment form is removed
    expect(comment_form).not_to_be_visible()


def test_file_navigation(page: Page, server_process: Any, server_url: str) -> None:
    """Test that clicking on a file in the tree navigates to it."""
    page.goto(f"{server_url}/?mock=true")

    # Wait for file tree to be populated
    page.wait_for_selector(".file-tree-item")

    # Click on the first file in the tree
    file_item = page.locator(".file-tree-item").first
    file_item.click()

    # The page should scroll to the file section
    # We can verify this by checking if the URL hash changed or if the element is in view
    # For now, we just verify that the click works without errors
