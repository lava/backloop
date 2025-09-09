// Main entry point for the review application

import { initializeDiffViewer, approveReview } from './diff-viewer.js';
import { loadAndDisplayComments } from './comments.js';
import { openFileEditor, closeEditModal, saveFileEdit } from './file-editor.js';
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