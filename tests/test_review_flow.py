import pytest
from fastapi.testclient import TestClient
from backloop.server import app
from backloop.services.review_service import ReviewService

# A fixture to manage the client's lifecycle, ensuring lifespan events are called
@pytest.fixture(scope="module")
def client():
    """Create a TestClient instance with the lifespan context."""
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="module", autouse=True)
def setup_default_review(client: TestClient):
    """Ensure a default review session is created before tests run."""
    # Access the service via app.state, which is populated by the lifespan event
    review_service: ReviewService = app.state.review_service
    if not review_service.get_most_recent_review():
        review_service.create_review_session(since="HEAD")

def get_latest_review_id() -> str:
    """Helper to get the ID of the most recent review session."""
    review_service: ReviewService = app.state.review_service
    review = review_service.get_most_recent_review()
    assert review is not None
    return review.id

def test_redirect_to_latest_review(client: TestClient):
    """Test GET / redirects to the latest review."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    review_id = get_latest_review_id()
    assert f"/review/{review_id}" in response.headers["location"]

def test_get_review_view(client: TestClient):
    """Test GET /review/{review_id}/view serves the HTML file."""
    review_id = get_latest_review_id()
    response = client.get(f"/review/{review_id}/view")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<title>Backloop Code Review</title>" in response.text

def test_get_review_diff(client: TestClient):
    """Test GET /review/{review_id}/api/diff returns diff data."""
    review_id = get_latest_review_id()
    response = client.get(f"/review/{review_id}/api/diff")
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert isinstance(data["files"], list)

def test_comment_flow(client: TestClient):
    """Test creating and listing a comment."""
    review_id = get_latest_review_id()

    # 1. Create a comment
    comment_data = {
        "file_path": "src/backloop/server.py",
        "line_number": 10,
        "side": "new",
        "content": "This is a test comment.",
        "author": "Test User",
    }
    response = client.post(f"/review/{review_id}/api/comments", json=comment_data)
    assert response.status_code == 200
    create_data = response.json()
    assert create_data["status"] == "success"
    assert "comment" in create_data["data"]
    comment_id = create_data["data"]["comment"]["id"]
    assert comment_id is not None

    # 2. Get comments and verify the new one is there
    response = client.get(f"/review/{review_id}/api/comments")
    assert response.status_code == 200
    comments = response.json()
    assert isinstance(comments, list)
    assert any(c["id"] == comment_id for c in comments)
    assert any(c["content"] == "This is a test comment." for c in comments)

def test_approve_review(client: TestClient):
    """Test POST /review/{review_id}/approve approves a review."""
    review_id = get_latest_review_id()
    timestamp = "2025-10-04T10:00:00Z"
    approval_data = {
        "file_path": "test", "line_number": 1, "side": "new", "content": "approval",
        "timestamp": timestamp
    }
    response = client.post(f"/review/{review_id}/approve", json=approval_data)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["status"] == "approved"
    assert data["data"]["timestamp"] == timestamp
