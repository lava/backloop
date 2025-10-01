// Main entry point for the review application

import { initializeDiffViewer, approveReview } from './diff-viewer.js';
import { loadAndDisplayComments } from './comments.js';
import { openFileEditor, closeEditModal, saveFileEdit } from './file-editor.js';
import { initializeWebSocket, onEvent } from './websocket-client.js';
import * as api from './api.js';

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Review application initializing...');

    try {
        // Initialize diff viewer
        await initializeDiffViewer();

        // Load existing comments if we're in a review context
        const reviewId = await api.getReviewId();
        if (reviewId) {
            await loadAndDisplayComments(reviewId);
        }

        // Setup approve button
        const approveButton = document.getElementById('approve-review-btn');
        if (approveButton) {
            approveButton.addEventListener('click', approveReview);
        }

        // Setup keyboard shortcuts
        setupKeyboardShortcuts();

        // Initialize WebSocket for real-time updates
        initializeWebSocket();

        // Setup WebSocket event handlers
        setupWebSocketHandlers();

        console.log('Review application initialized successfully');
    } catch (error) {
        console.error('Error initializing review application:', error);
    }
});

// Setup keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', (e) => {
        // ESC to close modals
        if (e.key === 'Escape') {
            const modal = document.querySelector('.edit-modal');
            if (modal) {
                closeEditModal();
            }
        }

        // Ctrl/Cmd + Enter to approve review
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            const approveButton = document.getElementById('approve-review-btn');
            if (approveButton && !approveButton.disabled) {
                approveReview();
            }
        }

        // Ctrl/Cmd + S to save file editor
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            const modal = document.querySelector('.edit-modal');
            if (modal) {
                e.preventDefault();
                saveFileEdit();
            }
        }
    });
}

// Setup WebSocket event handlers
function setupWebSocketHandlers() {
    // Handle comment dequeued events
    onEvent('comment_dequeued', (event) => {
        console.log('Comment dequeued event received:', event);
        updateCommentStatus(event.data);
    });

    // Handle comment resolved events
    onEvent('comment_resolved', (event) => {
        console.log('Comment resolved event received:', event);
        updateCommentStatus(event.data);
    });

    // Handle review approved events
    onEvent('review_approved', (event) => {
        console.log('Review approved event received:', event);
        // Could show a notification or update UI
    });
}

// Update comment status in the UI
function updateCommentStatus(data) {
    const commentId = data.comment_id;
    const commentThread = document.querySelector(`[data-comment-id="${commentId}"]`);

    if (!commentThread) {
        console.warn(`Comment thread not found for comment ${commentId}`);
        return;
    }

    // Update status badge
    const header = commentThread.querySelector('.comment-header');
    if (!header) {
        return;
    }

    // Remove existing status badges
    const existingBadge = header.querySelector('span[style*="background"]');
    if (existingBadge && existingBadge.className !== 'comment-author' && existingBadge.className !== 'comment-timestamp') {
        existingBadge.remove();
    }

    // Add new status badge
    let statusBadge = '';
    if (data.status === 'in_progress') {
        statusBadge = `
            <span style="background: #fb8500; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                In Progress
            </span>
        `;
    } else if (data.status === 'resolved') {
        statusBadge = `
            <span style="background: #1a7f37; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                ✓ Resolved
            </span>
        `;
        // Update comment appearance for resolved status
        commentThread.style.opacity = '0.7';
        commentThread.style.borderColor = '#1a7f37';

        const commentBody = commentThread.querySelector('.comment-body');
        if (commentBody) {
            commentBody.style.textDecoration = 'line-through';
        }
    }

    if (statusBadge) {
        const timestampElement = header.querySelector('.comment-timestamp');
        if (timestampElement) {
            timestampElement.insertAdjacentHTML('afterend', statusBadge);
        }
    }
}

// Make functions globally available for inline event handlers
window.showCommentForm = window.showCommentForm || function() {};
window.submitComment = window.submitComment || function() {};
window.deleteComment = window.deleteComment || function() {};
window.openFileEditor = openFileEditor;
window.closeEditModal = closeEditModal;
window.saveFileEdit = saveFileEdit;
window.approveReview = approveReview;

// Export main functions for external use
export { 
    initializeDiffViewer, 
    approveReview,
    openFileEditor,
    closeEditModal,
    saveFileEdit
};