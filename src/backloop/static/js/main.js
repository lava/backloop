// Main entry point for the review application

import { initializeDiffViewer, approveReview, refreshFile, updatePageTitle, isSingleMode, setSingleMode, navigateSingleMode } from './diff-viewer.js';
import { loadAndDisplayComments, preserveComments, restoreComments, preserveInProgressComments, restoreInProgressComments, showInlineReplyForm } from './comments.js';
import { openFileEditor, closeEditModal, saveFileEdit } from './file-editor.js';
import { initializeWebSocket, onEvent } from './websocket-client.js';
import * as api from './api.js';


function isLiveMode() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('live') === 'true';
}

function initControlPanel() {
    const urlParams = new URLSearchParams(window.location.search);
    const sinceInput = document.getElementById('since-input');
    const rangeInput = document.getElementById('range-input');
    const liveControls = document.getElementById('live-controls');
    const rangeControls = document.getElementById('range-controls');
    const modeLiveBtn = document.getElementById('mode-live-btn');
    const modeRangeBtn = document.getElementById('mode-range-btn');

    // Determine current mode from URL params
    const isLive = urlParams.get('live') === 'true';
    const range = urlParams.get('range');
    const commit = urlParams.get('commit');

    if (range || commit) {
        // Range / commit mode
        modeRangeBtn.classList.add('active');
        modeLiveBtn.classList.remove('active');
        liveControls.style.display = 'none';
        rangeControls.style.display = '';
        rangeInput.value = range || (commit + '~1..' + commit);
    } else {
        // Live mode (default)
        modeLiveBtn.classList.add('active');
        modeRangeBtn.classList.remove('active');
        liveControls.style.display = '';
        rangeControls.style.display = 'none';
        sinceInput.value = urlParams.get('since') || 'HEAD';
    }

    // Settings toggle
    const settingsBtn = document.getElementById('settings-toggle-btn');
    const controlPanel = document.getElementById('control-panel');
    settingsBtn.addEventListener('click', () => {
        const isVisible = controlPanel.style.display !== 'none';
        controlPanel.style.display = isVisible ? 'none' : '';
        settingsBtn.classList.toggle('active', !isVisible);
    });

    // Mode toggle clicks
    modeLiveBtn.addEventListener('click', () => {
        modeLiveBtn.classList.add('active');
        modeRangeBtn.classList.remove('active');
        liveControls.style.display = '';
        rangeControls.style.display = 'none';
    });

    modeRangeBtn.addEventListener('click', () => {
        modeRangeBtn.classList.add('active');
        modeLiveBtn.classList.remove('active');
        liveControls.style.display = 'none';
        rangeControls.style.display = '';
        // Pre-fill with merge-base range if empty
        if (!rangeInput.value) {
            rangeInput.value = 'origin/main...HEAD';
        }
    });

    // Apply button
    document.getElementById('control-panel-apply').addEventListener('click', applyControlPanel);

    // Enter key in inputs
    sinceInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') applyControlPanel();
    });
    rangeInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') applyControlPanel();
    });

    // View mode toggle (combined / single file)
    const viewCombinedBtn = document.getElementById('view-combined-btn');
    const viewSingleBtn = document.getElementById('view-single-btn');

    function syncViewToggle() {
        const single = isSingleMode();
        viewSingleBtn.classList.toggle('active', single);
        viewCombinedBtn.classList.toggle('active', !single);
    }

    // Initial state will be set after initializeDiffViewer runs, so observe via MutationObserver
    new MutationObserver(syncViewToggle).observe(
        document.body, { attributes: true, attributeFilter: ['class'] }
    );
    syncViewToggle();

    viewCombinedBtn.addEventListener('click', () => {
        if (isSingleMode()) {
            setSingleMode(false);
            import('./diff-viewer.js').then(m => m.renderDiffContent([])).catch(() => {});
            // Trigger a full reload of diff to re-render all files
            reloadDiffData();
        }
    });

    viewSingleBtn.addEventListener('click', () => {
        if (!isSingleMode()) {
            setSingleMode(true);
            reloadDiffData();
        }
    });
}

function applyControlPanel() {
    const modeLiveBtn = document.getElementById('mode-live-btn');
    const sinceInput = document.getElementById('since-input');
    const rangeInput = document.getElementById('range-input');
    const isLiveSelected = modeLiveBtn.classList.contains('active');

    const params = new URLSearchParams();
    if (isLiveSelected) {
        params.set('live', 'true');
        params.set('since', sinceInput.value.trim() || 'HEAD');
    } else {
        const rangeVal = rangeInput.value.trim();
        if (!rangeVal) return; // Don't navigate with empty range
        params.set('range', rangeVal);
    }

    window.location.search = params.toString();
}

function showStaleBanner() {
    const banner = document.getElementById('stale-banner');
    if (banner && banner.style.display === 'none') {
        // Build live mode URL for this review
        const urlParams = new URLSearchParams(window.location.search);
        const since = urlParams.get('since') || urlParams.get('commit') || 'HEAD';
        const livePath = window.location.pathname + `?live=true&since=${encodeURIComponent(since)}`;

        const link = document.getElementById('stale-banner-link');
        if (link) {
            link.href = livePath;
        }

        banner.style.display = 'block';
    }
}

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

        // Also preserve all in-progress comment forms
        const allInProgressForms = [];
        const commentForms = document.querySelectorAll('.comment-form');
        commentForms.forEach(form => {
            const filePath = form.dataset.filePath;
            if (filePath) {
                const forms = preserveInProgressComments(filePath);
                allInProgressForms.push(...forms);
            }
        });

        // Parse query parameters to get current diff settings
        const urlParams = new URLSearchParams(window.location.search);
        const commit = urlParams.get('commit');
        const range = urlParams.get('range');
        const since = urlParams.get('since');
        const live = urlParams.get('live') === 'true';
        const mock = urlParams.get('mock') === 'true';

        // Fetch review info and update page title
        const reviewInfo = await api.fetchReviewInfo();
        updatePageTitle(reviewInfo);

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

            // Restore in-progress comment forms
            if (allInProgressForms.length > 0) {
                restoreInProgressComments(allInProgressForms);
            }

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
        // Initialize control panel from URL params
        initControlPanel();

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

        // Setup WebSocket event handlers BEFORE initializing the connection
        setupWebSocketHandlers();

        // Initialize WebSocket for real-time updates
        initializeWebSocket();

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

        // Ctrl/Cmd + Enter to submit comment when writing one
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            const activeTextarea = document.activeElement;
            if (activeTextarea && activeTextarea.tagName === 'TEXTAREA' && activeTextarea.closest('.comment-form')) {
                e.preventDefault();
                const submitBtn = activeTextarea.closest('.comment-form').querySelector('[data-action="submit"]');
                if (submitBtn) submitBtn.click();
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

        // [ and ] to navigate files in single mode
        if (isSingleMode() && !e.target.closest('textarea, input')) {
            if (e.key === '[' || e.key === 'ArrowUp' && e.altKey) {
                e.preventDefault();
                navigateSingleMode(-1);
            } else if (e.key === ']' || e.key === 'ArrowDown' && e.altKey) {
                e.preventDefault();
                navigateSingleMode(1);
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

    // Handle comment replied events (agent reply without resolving)
    onEvent('comment_replied', (event) => {
        console.log('Comment replied event received:', event);
        showCommentReply(event.data);
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
        if (!isLiveMode()) {
            showStaleBanner();
            return;
        }
        reloadDiffData();
    });

    // Handle file removed events
    onEvent('file_removed', async (event) => {
        console.log('File removed event received:', event);

        if (!isLiveMode()) {
            showStaleBanner();
            return;
        }

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

        if (!isLiveMode()) {
            showStaleBanner();
            return;
        }

        const filePath = event.data.file_path;

        // Check if the file exists in the current diff
        const anchorId = 'file-' + filePath.replace(/[^a-zA-Z0-9]/g, '-');
        const fileElement = document.getElementById(`${anchorId}-new-pane`);

        if (!fileElement) {
            console.log('File not found in current diff, reloading diff data:', filePath);
            await reloadDiffData();
            return;
        }

        console.log('Auto-refreshing file:', filePath);
        await refreshFile(filePath);
    });
}

// Show a reply on a comment thread without resolving it
function showCommentReply(data) {
    // A reply also resolves the comment, so delegate to updateCommentStatus
    // which handles the badge, reply display, and reply button.
    updateCommentStatus(data);
}

// Update comment status in the UI
function updateCommentStatus(data) {
    const commentId = data.comment_id;
    const commentThread = document.querySelector(`.comment-thread[data-comment-id="${commentId}"]`);

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
        commentThread.style.borderColor = '#1a7f37';
        commentThread.style.backgroundColor = '#e6f4ea';

        if (data.reply_message) {
            const comment = commentThread.querySelector('.comment');
            if (comment) {
                // Remove existing reply/agent-reply if any
                const existingReply = comment.querySelector('.resolution-note') || comment.querySelector('.agent-reply');
                if (existingReply) {
                    existingReply.remove();
                }

                const replyMessageHtml = `
                    <div class="resolution-note" style="margin-top: 8px; padding: 8px; background: #ffffff; border-left: 3px solid #1a7f37; border-radius: 4px;">
                        <div style="font-size: 12px; color: #57606a; margin-bottom: 4px; font-weight: 600;">
                            Agent Reply:
                        </div>
                        <div style="color: #1f2328;">
                            ${escapeHtml(data.reply_message)}
                        </div>
                    </div>
                `;
                comment.insertAdjacentHTML('beforeend', replyMessageHtml);
            }
        }

        // Add reply button if not already present
        const comment = commentThread.querySelector('.comment');
        if (comment && !comment.querySelector('.comment-reply-btn')) {
            const replyBtn = document.createElement('button');
            replyBtn.className = 'btn btn-secondary comment-reply-btn';
            replyBtn.style.cssText = 'margin-top: 8px; font-size: 12px; padding: 2px 10px;';
            replyBtn.textContent = 'Reply';
            replyBtn.addEventListener('click', () => {
                showInlineReplyForm(commentThread, { id: data.comment_id });
            });
            comment.appendChild(replyBtn);
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
