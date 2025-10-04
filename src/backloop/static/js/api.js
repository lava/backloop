// API communication layer

export async function getReviewId() {
    const pathParts = window.location.pathname.split('/');
    return pathParts[2]; // /review/{review_id}/view
}

export async function addComment(commentData) {
    const reviewId = await getReviewId();
    const response = await fetch(`/review/${reviewId}/api/comments`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(commentData)
    });
    
    if (!response.ok) {
        throw new Error('Failed to add comment');
    }
    
    return response.json();
}

export async function deleteComment(commentId) {
    const reviewId = await getReviewId();
    const response = await fetch(`/review/${reviewId}/api/comments/${commentId}`, {
        method: 'DELETE'
    });
    
    if (!response.ok) {
        throw new Error('Failed to delete comment');
    }
    
    return response.json();
}

export async function getFileContent(filePath) {
    const reviewId = await getReviewId();
    const response = await fetch(`/review/${reviewId}/api/file-content?path=${encodeURIComponent(filePath)}`);

    if (response.ok) {
        return response.text();
    }

    console.warn('Could not read file, starting with empty content');
    return '';
}

export async function saveFileEdit(filePath, patch) {
    const reviewId = await getReviewId();
    const response = await fetch(`/review/${reviewId}/api/edit`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            filename: filePath,
            patch: patch
        })
    });
    
    if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save file');
    }
    
    return response.json();
}

export async function fetchDiff(params = {}) {
    const reviewId = await getReviewId();
    if (!reviewId) {
        throw new Error("Could not determine review ID from URL.");
    }

    // Build query string from params
    const queryParams = new URLSearchParams();
    if (params.commit) queryParams.set('commit', params.commit);
    if (params.range) queryParams.set('range', params.range);
    if (params.live) queryParams.set('live', params.live);
    if (params.since) queryParams.set('since', params.since);

    const queryString = queryParams.toString();
    const endpoint = `/review/${reviewId}/api/diff${queryString ? `?${queryString}` : ''}`;
    const response = await fetch(endpoint);

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to fetch diff');
    }

    return response.json();
}

export async function loadComments(reviewId) {
    const response = await fetch(`/review/${reviewId}/api/comments`);
    
    if (!response.ok) {
        throw new Error('Failed to load comments');
    }
    
    return response.json();
}

export async function approveReview(reviewId) {
    const response = await fetch(`/review/${reviewId}/approve`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            timestamp: new Date().toISOString()
        })
    });

    if (!response.ok) {
        throw new Error('Failed to approve review');
    }

    return response.json();
}
