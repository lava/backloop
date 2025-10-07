// Comment management module

import * as api from './api.js';
import { openFileEditor } from './file-editor.js';

let commentIdCounter = 1;
let commentsData = {};
// Track which files have active comment forms (user is writing)
let activeCommentForms = new Map(); // filePath -> textarea element

export function showCommentForm(filePath, lineNumber, side, lineElement) {
    console.log('showCommentForm called:', filePath, lineNumber, side);

    // Check if form already exists for this line
    const existingForm = lineElement.parentElement.querySelector('.comment-form');
    if (existingForm) {
        // Remove from tracking
        activeCommentForms.delete(filePath);
        existingForm.remove();
        return;
    }

    const commentForm = document.createElement('div');
    commentForm.className = 'comment-form';

    // Add "Edit directly" button for "new" side (right column)
    const editDirectlyButton = side === 'new'
        ? '<button class="btn btn-tertiary" data-action="edit-directly" style="margin-left: auto;">Edit directly</button>'
        : '';

    commentForm.innerHTML = `
        <textarea placeholder="Leave a comment..."></textarea>
        <div class="comment-form-buttons">
            <button class="btn btn-secondary" data-action="cancel">Cancel</button>
            <button class="btn btn-primary" data-action="submit">Comment</button>
            ${editDirectlyButton}
        </div>
    `;

    // Store metadata on the form
    commentForm.dataset.filePath = filePath;
    commentForm.dataset.lineNumber = lineNumber;
    commentForm.dataset.side = side;
    commentForm.dataset.lineElementId = lineElement.id;

    // Add event listeners
    const cancelBtn = commentForm.querySelector('[data-action="cancel"]');
    const submitBtn = commentForm.querySelector('[data-action="submit"]');
    const editDirectlyBtn = commentForm.querySelector('[data-action="edit-directly"]');
    const textarea = commentForm.querySelector('textarea');

    cancelBtn.addEventListener('click', () => {
        activeCommentForms.delete(filePath);
        commentForm.remove();
    });
    submitBtn.addEventListener('click', () => submitComment(submitBtn));

    if (editDirectlyBtn) {
        editDirectlyBtn.addEventListener('click', () => openEditDirectly(filePath, lineNumber, commentForm));
    }

    // Insert after the line element
    lineElement.parentElement.insertBefore(commentForm, lineElement.nextSibling);
    textarea.focus();

    // Track this comment form
    activeCommentForms.set(filePath, textarea);
}

export async function submitComment(buttonElement) {
    const form = buttonElement.closest('.comment-form');
    const textarea = form.querySelector('textarea');
    const content = textarea.value.trim();

    if (!content) {
        alert('Please enter a comment.');
        return;
    }

    const filePath = form.dataset.filePath;
    const lineNumber = parseInt(form.dataset.lineNumber);
    const side = form.dataset.side;
    
    try {
        // Make API call to add comment
        const result = await api.addComment({
            file_path: filePath,
            line_number: lineNumber,
            side: side,
            content: content,
            author: 'Reviewer'
        });
        
        const comment = result.data.comment;
        const queuePosition = result.data.queue_position;

        // Add queue position to comment for display
        comment.queuePosition = queuePosition;
        
        // Store comment locally
        const key = `${filePath}:${lineNumber}:${side}`;
        if (!commentsData[key]) {
            commentsData[key] = [];
        }
        commentsData[key].push(comment);
        
        // Get line element by stored ID
        const lineElementId = form.dataset.lineElementId;
        const lineElement = document.getElementById(lineElementId);
        
        // Remove form and display comment with queue position
        activeCommentForms.delete(filePath);
        form.remove();
        displayCommentWithQueue(comment, lineNumber, side, lineElement);
        
        console.log(`Comment added at queue position ${queuePosition}:`, comment);
    } catch (error) {
        console.error('Error adding comment:', error);
        // Fall back to local storage
        const comment = {
            id: commentIdCounter++,
            content: content,
            author: 'Reviewer',
            timestamp: new Date().toLocaleString(),
            filePath: filePath,
            lineNumber: lineNumber,
            side: side,
            queuePosition: commentIdCounter
        };
        
        const key = `${filePath}:${lineNumber}:${side}`;
        if (!commentsData[key]) {
            commentsData[key] = [];
        }
        commentsData[key].push(comment);
        
        const lineElementId = form.dataset.lineElementId;
        const lineElement = document.getElementById(lineElementId);

        activeCommentForms.delete(filePath);
        form.remove();
        displayCommentWithQueue(comment, lineNumber, side, lineElement);
    }
}

export function displayCommentWithQueue(comment, lineNumber, side, lineElement) {
    console.log('Displaying comment:', comment, 'after line element:', lineElement);
    
    if (!lineElement) {
        console.error('Line element is null, cannot display comment');
        return;
    }
    
    // Create comment display element
    const commentDiv = document.createElement('div');
    commentDiv.className = 'comment-thread';
    commentDiv.dataset.commentId = comment.id;
    commentDiv.style.margin = '8px';
    commentDiv.style.maxWidth = 'calc(100% - 16px)';
    commentDiv.style.backgroundColor = '#f6f8fa';
    commentDiv.style.border = '1px solid #d0d7de';
    commentDiv.style.borderRadius = '6px';
    
    // Determine status badge HTML
    let statusBadge = '';
    if (comment.status === 'in_progress') {
        statusBadge = `
            <span style="background: #fb8500; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                In Progress
            </span>
        `;
    } else if (comment.status === 'resolved') {
        statusBadge = `
            <span style="background: #1a7f37; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                ✓ Resolved
            </span>
        `;
        // Update comment appearance for resolved status
        commentDiv.style.opacity = '0.7';
        commentDiv.style.borderColor = '#1a7f37';
        commentDiv.style.backgroundColor = '#e6f4ea';
    } else if (comment.queuePosition) {
        statusBadge = `
            <span style="background: #0969da; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">
                Queue #${comment.queuePosition}
            </span>
        `;
    }

    const replyMessageHtml = comment.reply_message ? `
        <div style="margin-top: 8px; padding: 8px; background: #ffffff; border-left: 3px solid #1a7f37; border-radius: 4px;">
            <div style="font-size: 12px; color: #57606a; margin-bottom: 4px; font-weight: 600;">
                Resolution Note:
            </div>
            <div style="color: #1f2328;">
                ${escapeHtml(comment.reply_message)}
            </div>
        </div>
    ` : '';

    commentDiv.innerHTML = `
        <div class="comment">
            <div class="comment-header">
                <span class="comment-author">${escapeHtml(comment.author)}</span>
                <span class="comment-timestamp">${escapeHtml(comment.timestamp)}</span>
                ${statusBadge}
                <button class="comment-delete-btn" data-comment-id="${comment.id}"
                        style="margin-left: 8px; background: #da3633; color: white; border: none; padding: 2px 8px; border-radius: 4px; font-size: 12px; cursor: pointer;"
                        title="Delete comment">
                    ×
                </button>
            </div>
            <div class="comment-body" ${comment.status === 'resolved' ? 'style="text-decoration: line-through;"' : ''}>${escapeHtml(comment.content)}</div>
            ${replyMessageHtml}
        </div>
    `;
    
    // Add delete event listener
    const deleteBtn = commentDiv.querySelector('.comment-delete-btn');
    deleteBtn.addEventListener('click', () => deleteComment(comment.id, deleteBtn));
    
    // Insert the comment display after the line element
    if (lineElement.parentElement) {
        lineElement.parentElement.insertBefore(commentDiv, lineElement.nextSibling);
        console.log('Comment display element inserted after line element');
    } else {
        console.error('Line element has no parent, cannot insert comment');
    }
}

export async function deleteComment(commentId, buttonElement) {
    try {
        // Make API call to delete comment
        await api.deleteComment(commentId);
        
        // Remove comment from UI
        const commentThread = buttonElement.closest('.comment-thread');
        if (commentThread) {
            commentThread.remove();
        }
        
        // Remove from local storage
        for (const key in commentsData) {
            commentsData[key] = commentsData[key].filter(c => c.id !== commentId);
            if (commentsData[key].length === 0) {
                delete commentsData[key];
            }
        }
        
        console.log('Comment deleted:', commentId);
    } catch (error) {
        console.error('Error deleting comment:', error);
        alert('Failed to delete comment: ' + error.message);
    }
}

export async function loadAndDisplayComments(reviewId) {
    try {
        const comments = await api.loadComments(reviewId);

        // Group comments by location
        comments.forEach(comment => {
            const key = `${comment.file_path}:${comment.line_number}:${comment.side}`;
            if (!commentsData[key]) {
                commentsData[key] = [];
            }
            // Convert queue_position to queuePosition for consistency
            if (comment.queue_position !== undefined) {
                comment.queuePosition = comment.queue_position;
            }
            commentsData[key].push(comment);
        });

        // Display all comments
        for (const [key, locationComments] of Object.entries(commentsData)) {
            const [filePath, lineNumber, side] = key.split(':');

            // Sanitize file path same way as diff-viewer.js
            const sanitizedPath = filePath.replace(/[^a-zA-Z0-9]/g, '-');
            const lineElementId = `line-${sanitizedPath}-${lineNumber}-${side}`;
            const lineElement = document.getElementById(lineElementId);

            if (lineElement) {
                // Display each comment for this location
                for (const comment of locationComments) {
                    displayCommentWithQueue(comment, parseInt(lineNumber), side, lineElement);
                }
            }
        }
    } catch (error) {
        console.error('Error loading comments:', error);
    }
}

// Utility function for escaping HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Open file editor for direct editing
export async function openEditDirectly(filePath, lineNumber, commentForm) {
    // Close the comment form
    if (commentForm) {
        activeCommentForms.delete(filePath);
        commentForm.remove();
    }

    // Open the file editor at the specified line
    await openFileEditor(filePath, parseInt(lineNumber));
}

export function preserveComments() {
    const preservedComments = [];
    const commentThreads = document.querySelectorAll('.comment-thread');

    commentThreads.forEach(thread => {
        const commentId = thread.dataset.commentId;
        if (!commentId) return;

        // Store the entire outer HTML for this comment thread
        preservedComments.push({
            commentId: commentId,
            html: thread.outerHTML,
            // Also store parent line element ID to know where to re-insert
            lineElementId: thread.previousElementSibling?.id
        });
    });

    return preservedComments;
}

export function restoreComments(preservedComments) {
    let restoredCount = 0;

    preservedComments.forEach(preserved => {
        const lineElement = document.getElementById(preserved.lineElementId);
        if (!lineElement || !lineElement.parentElement) {
            console.warn(`Could not find line element ${preserved.lineElementId} to restore comment ${preserved.commentId}`);
            return;
        }

        // Create a temporary div to parse the HTML
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = preserved.html;
        const commentThread = tempDiv.firstChild;

        // Re-attach event listener to delete button
        const deleteBtn = commentThread.querySelector('.comment-delete-btn');
        if (deleteBtn) {
            const commentId = preserved.commentId;
            deleteBtn.addEventListener('click', () => deleteComment(commentId, deleteBtn));
        }

        // Insert after the line element
        lineElement.parentElement.insertBefore(commentThread, lineElement.nextSibling);
        restoredCount++;
    });

    console.log(`Restored ${restoredCount} of ${preservedComments.length} comments`);
}

// Check if user is currently writing a comment on a file
export function isUserWritingComment(filePath) {
    return activeCommentForms.has(filePath);
}

export { commentsData };