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
    const response = await fetch(`/api/file-content?path=${encodeURIComponent(filePath)}`);
    
    if (response.ok) {
        return response.text();
    }
    
    console.warn('Could not read file, starting with empty content');
    return '';
}

export async function saveFileEdit(filePath, patch) {
    const response = await fetch('/api/edit', {
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

export async function fetchDiff(params) {
    // Filter out null/undefined parameters and determine the endpoint
    const cleanParams = {};
    let endpoint = '/api/diff';

    // If live mode, use the live endpoint and only pass 'since' and 'mock'
    if (params.live === true || params.live === 'true') {
        endpoint = '/api/diff/live';
        if (params.since != null) cleanParams.since = params.since;
        if (params.mock != null) cleanParams.mock = params.mock;
    } else {
        // For non-live mode, pass commit/range/mock
        if (params.commit != null) cleanParams.commit = params.commit;
        if (params.range != null) cleanParams.range = params.range;
        if (params.mock != null) cleanParams.mock = params.mock;
    }

    const queryParams = new URLSearchParams(cleanParams);
    const response = await fetch(`${endpoint}?${queryParams}`);

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