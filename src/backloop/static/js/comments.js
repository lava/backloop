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

        // Also remove the form spacer from the opposite pane
        const formSpacerId = existingForm.dataset.formSpacerId;
        if (formSpacerId) {
            const spacer = document.getElementById(formSpacerId);
            if (spacer) {
                spacer.remove();
            }
        }
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

    const removeFormAndSpacer = () => {
        activeCommentForms.delete(filePath);
        const formSpacerId = commentForm.dataset.formSpacerId;
        if (formSpacerId) {
            const spacer = document.getElementById(formSpacerId);
            if (spacer) {
                spacer.remove();
            }
        }
        commentForm.remove();
    };

    cancelBtn.addEventListener('click', removeFormAndSpacer);
    submitBtn.addEventListener('click', () => submitComment(submitBtn));

    if (editDirectlyBtn) {
        editDirectlyBtn.addEventListener('click', () => openEditDirectly(filePath, lineNumber, commentForm));
    }

    // Insert after the line element
    lineElement.parentElement.insertBefore(commentForm, lineElement.nextSibling);
    textarea.focus();

    // Create and insert a matching spacer in the opposite pane for the form
    insertFormSpacerInOppositPane(lineElement, commentForm, side);

    // Track this comment form
    activeCommentForms.set(filePath, textarea);
}

// Insert a spacer for the comment form in the opposite pane
function insertFormSpacerInOppositPane(lineElement, commentForm, side) {
    const oppositeSide = side === 'old' ? 'new' : 'old';
    const filePath = lineElement.dataset.filePath;
    const sharedLineIndex = lineElement.dataset.sharedLineIndex;

    console.log(
        'Trying to insert form spacer using shared index',
        { lineId: lineElement.id, oppositeSide, filePath, sharedLineIndex }
    );

    if (!filePath || !sharedLineIndex) {
        console.warn('Missing diff metadata on line element; cannot align form spacer');
        return;
    }

    const oppositeLineElement = findLineElementBySharedIndex(filePath, sharedLineIndex, oppositeSide);

    console.log('Found opposite line element for form spacer?', !!oppositeLineElement);

    if (!oppositeLineElement || !oppositeLineElement.parentElement) {
        console.warn('Could not find opposite line element to insert form spacer');
        return;
    }

    // Create a spacer element that matches the height of the form
    const spacer = document.createElement('div');
    const spacerId = `form-spacer-${Date.now()}-${Math.random()}`;
    spacer.id = spacerId;
    spacer.className = 'comment-form-spacer';
    spacer.style.visibility = 'hidden'; // Invisible but takes up space
    spacer.style.margin = '8px';
    spacer.style.maxWidth = 'calc(100% - 16px)';

    // Store the spacer ID on the form so we can remove it later
    commentForm.dataset.formSpacerId = spacerId;

    // Insert the spacer after the opposite line element FIRST
    oppositeLineElement.parentElement.insertBefore(spacer, oppositeLineElement.nextSibling);

    // Copy the exact height after the form renders
    // Use requestAnimationFrame to ensure layout is calculated
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            const height = commentForm.offsetHeight;
            spacer.style.height = `${height}px`;
            console.log(`Form spacer height set to ${height}px for spacer ${spacerId}`);
        });
    });

    console.log('Form spacer inserted in opposite pane for alignment');
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

        // Remove form spacer before removing form
        const formSpacerId = form.dataset.formSpacerId;
        if (formSpacerId) {
            const spacer = document.getElementById(formSpacerId);
            if (spacer) {
                spacer.remove();
            }
        }

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

        // Remove form spacer before removing form
        const formSpacerId = form.dataset.formSpacerId;
        if (formSpacerId) {
            const spacer = document.getElementById(formSpacerId);
            if (spacer) {
                spacer.remove();
            }
        }

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

        // Create and insert a matching spacer in the opposite pane to maintain alignment
        insertSpacerInOppositPane(lineElement, commentDiv, side);
    } else {
        console.error('Line element has no parent, cannot insert comment');
    }
}

// Insert a spacer element in the opposite pane to maintain alignment
function insertSpacerInOppositPane(lineElement, commentDiv, side) {
    const oppositeSide = side === 'old' ? 'new' : 'old';
    const filePath = lineElement.dataset.filePath;
    const sharedLineIndex = lineElement.dataset.sharedLineIndex;

    console.log(
        'Trying to insert comment spacer using shared index',
        { lineId: lineElement.id, oppositeSide, filePath, sharedLineIndex }
    );

    if (!filePath || !sharedLineIndex) {
        console.warn('Missing diff metadata on line element; cannot align comment spacer');
        return;
    }

    const oppositeLineElement = findLineElementBySharedIndex(filePath, sharedLineIndex, oppositeSide);

    console.log('Found opposite line element for comment spacer?', !!oppositeLineElement);

    if (!oppositeLineElement || !oppositeLineElement.parentElement) {
        console.warn('Could not find opposite line element to insert spacer');
        return;
    }

    // Create a spacer element that matches the height of the comment
    const spacer = document.createElement('div');
    spacer.className = 'comment-spacer';
    spacer.dataset.commentId = commentDiv.dataset.commentId;
    spacer.style.visibility = 'hidden'; // Invisible but takes up space
    spacer.style.margin = '8px';
    spacer.style.maxWidth = 'calc(100% - 16px)';

    // Insert the spacer after the opposite line element FIRST
    oppositeLineElement.parentElement.insertBefore(spacer, oppositeLineElement.nextSibling);

    // Copy the exact height after the comment renders
    // Use requestAnimationFrame to ensure layout is calculated
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            const height = commentDiv.offsetHeight;
            spacer.style.height = `${height}px`;
            console.log(`Comment spacer height set to ${height}px for comment ${commentDiv.dataset.commentId}`);
        });
    });

    console.log('Spacer inserted in opposite pane for alignment');
}

function findLineElementBySharedIndex(filePath, sharedLineIndex, side) {
    const candidates = document.querySelectorAll(
        `.diff-line[data-side="${side}"][data-shared-line-index="${sharedLineIndex}"]`
    );

    if (!candidates || candidates.length === 0) {
        return null;
    }

    return Array.from(candidates).find(candidate => candidate.dataset.filePath === filePath) || null;
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

        // Remove the corresponding spacer from the opposite pane
        const spacer = document.querySelector(`.comment-spacer[data-comment-id="${commentId}"]`);
        if (spacer) {
            spacer.remove();
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
        // Remove form spacer
        const formSpacerId = commentForm.dataset.formSpacerId;
        if (formSpacerId) {
            const spacer = document.getElementById(formSpacerId);
            if (spacer) {
                spacer.remove();
            }
        }

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

// Preserve all in-progress comment forms for a specific file
export function preserveInProgressComments(filePath) {
    const preservedForms = [];

    // Find all comment forms for this file
    const commentForms = document.querySelectorAll(`.comment-form[data-file-path="${filePath}"]`);

    commentForms.forEach(commentForm => {
        const textarea = commentForm.querySelector('textarea');
        if (!textarea) return;

        // Get the line element that the comment form is attached to
        const lineElement = commentForm.previousElementSibling;
        if (!lineElement || !lineElement.classList.contains('diff-line')) {
            return;
        }

        preservedForms.push({
            filePath: commentForm.dataset.filePath,
            lineElementId: lineElement.id,
            content: textarea.value,
            side: commentForm.dataset.side,
            lineNumber: commentForm.dataset.lineNumber
        });
    });

    return preservedForms;
}

// Restore in-progress comment forms after file refresh
export function restoreInProgressComments(preservedForms) {
    if (!preservedForms || preservedForms.length === 0) {
        return 0;
    }

    let restoredCount = 0;

    preservedForms.forEach((preservedForm, index) => {
        const lineElement = document.getElementById(preservedForm.lineElementId);
        if (!lineElement) {
            console.warn(`Could not find line element ${preservedForm.lineElementId} to restore in-progress comment`);
            return;
        }

        // Check if a form already exists at this line
        const existingForm = lineElement.nextElementSibling;
        if (existingForm && existingForm.classList.contains('comment-form')) {
            return;
        }

        // Recreate the comment form
        showCommentForm(preservedForm.filePath, preservedForm.lineNumber, preservedForm.side, lineElement);

        // Find the textarea that was just created (it's the next sibling after the line element)
        const recreatedForm = lineElement.nextElementSibling;
        if (recreatedForm && recreatedForm.classList.contains('comment-form')) {
            const textarea = recreatedForm.querySelector('textarea');
            if (textarea) {
                textarea.value = preservedForm.content;
                restoredCount++;
            }
        }
    });

    if (restoredCount > 0) {
        console.log(`Restored ${restoredCount} in-progress comment(s)`);
    }

    return restoredCount;
}

export { commentsData };
