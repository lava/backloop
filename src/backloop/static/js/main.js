// Main entry point for the review application

import { initializeDiffViewer, approveReview, showRefreshButton, refreshFile } from './diff-viewer.js';
import { loadAndDisplayComments, isUserWritingComment, preserveComments, restoreComments } from './comments.js';
import { openFileEditor, closeEditModal, saveFileEdit } from './file-editor.js';
import { initializeWebSocket, onEvent } from './websocket-client.js';
import * as api from './api.js';


function removeFileFromView(filePath) {
    // Remove from file tree
    const anchorId = 'file-' + filePath.replace(/[^a-zA-Z0-9]/g, '-');
    const fileTreeItem = document.querySelector(`.file-tree-item[onclick*="${filePath}"]`);
    if (fileTreeItem) {
        fileTreeItem.remove();
    }

    // Remove from diff view
    const fileSection = document.getElementById(anchorId);
    if (fileSection) {
        fileSection.remove();
    }
}

async function reloadDiffData() {
    try {
        // Preserve existing comments before clearing the diff
        const preservedComments = preserveComments();

        // Parse query parameters to get current diff settings
        const urlParams = new URLSearchParams(window.location.search);
        const commit = urlParams.get('commit');
        const range = urlParams.get('range');
        const since = urlParams.get('since');
        const live = urlParams.get('live') === 'true';
        const mock = urlParams.get('mock') === 'true';

        // Fetch updated diff data
        const params = { commit, range, since, live, mock };
        const diffData = await api.fetchDiff(params);

        if (diffData && diffData.files) {
            // Update file tree
            const { buildFileTree, renderFileTree, renderDiffContent } = await import('./diff-viewer.js');
            const fileTree = buildFileTree(diffData.files);
            const fileTreeContainer = document.getElementById('file-tree');
            if (fileTreeContainer) {
                fileTreeContainer.innerHTML = '';
                renderFileTree(fileTree, fileTreeContainer);
            }

            // Update diff content
            renderDiffContent(diffData.files);

            // Restore comments after diff has been re-rendered
            restoreComments(preservedComments);

            console.log('Diff data reloaded successfully');
        }
    } catch (error) {
        console.error('Error reloading diff data:', error);
        alert('Failed to reload diff data: ' + error.message);
    }
}

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

    // Handle review updated events (e.g., file changes)
    onEvent('review_updated', (event) => {
        console.log('Review updated event received:', event);
        reloadDiffData();
    });

    // Handle file removed events
    onEvent('file_removed', async (event) => {
        console.log('File removed event received:', event);
        const filePath = event.data.file_path;

        let relativePath = filePath;
        let fileFound = false;

        if (filePath.includes('/')) {
            const parts = filePath.split('/');
            for (let i = parts.length - 1; i >= 0; i--) {
                const testPath = parts.slice(i).join('/');
                const anchorId = 'file-' + testPath.replace(/[^a-zA-Z0-9]/g, '-');
                const fileSection = document.getElementById(anchorId);
                if (fileSection) {
                    relativePath = testPath;
                    fileFound = true;
                    break;
                }
            }
        }

        if (fileFound) {
            console.log('Removing file from view:', relativePath);
            removeFileFromView(relativePath);
        } else {
            console.log('File not found in current diff, reloading diff data:', relativePath);
            await reloadDiffData();
        }
    });

    // Handle file changed events
    onEvent('file_changed', async (event) => {
        console.log('File changed event received:', event);
        const filePath = event.data.file_path;

        let relativePath = filePath;
        let fileFound = false;

        if (filePath.includes('/')) {
            const parts = filePath.split('/');
            for (let i = parts.length - 1; i >= 0; i--) {
                const testPath = parts.slice(i).join('/');
                const anchorId = 'file-' + testPath.replace(/[^a-zA-Z0-9]/g, '-');
                if (document.getElementById(`${anchorId}-new-pane`)) {
                    relativePath = testPath;
                    fileFound = true;
                    break;
                }
            }
        }

        if (!fileFound) {
            console.log('File not found in current diff, reloading diff data:', relativePath);
            await reloadDiffData();
            return;
        }

        // Check if user is currently writing a comment on this file
        if (isUserWritingComment(relativePath)) {
            console.log('User is writing comment on file, showing refresh button:', relativePath);
            showRefreshButton(relativePath);
            return;
        }

        console.log('Auto-refreshing file:', relativePath);
        await refreshFile(relativePath);
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
        commentThread.style.backgroundColor = '#e6f4ea';

        const commentBody = commentThread.querySelector('.comment-body');
        if (commentBody) {
            commentBody.style.textDecoration = 'line-through';
        }

        if (data.reply_message) {
            const comment = commentThread.querySelector('.comment');
            if (comment) {
                // Remove existing reply message if any
                const existingReply = comment.querySelector('.resolution-note');
                if (existingReply) {
                    existingReply.remove();
                }

                const replyMessageHtml = `
                    <div class="resolution-note" style="margin-top: 8px; padding: 8px; background: #ffffff; border-left: 3px solid #1a7f37; border-radius: 4px;">
                        <div style="font-size: 12px; color: #57606a; margin-bottom: 4px; font-weight: 600;">
                            Resolution Note:
                        </div>
                        <div style="color: #1f2328;">
                            ${escapeHtml(data.reply_message)}
                        </div>
                    </div>
                `;
                comment.insertAdjacentHTML('beforeend', replyMessageHtml);
            }
        }
    }

    if (statusBadge) {
        const timestampElement = header.querySelector('.comment-timestamp');
        if (timestampElement) {
            timestampElement.insertAdjacentHTML('afterend', statusBadge);
        }
    }
}

// Utility function for escaping HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
