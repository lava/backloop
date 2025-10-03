// File editing functionality

import * as api from './api.js';

export async function openFileEditor(filePath, lineNumber = null) {
    try {
        const fileContent = await api.getFileContent(filePath);
        showEditModal(filePath, fileContent, lineNumber);
    } catch (error) {
        console.error('Error opening file editor:', error);
        alert('Failed to open file editor: ' + error.message);
    }
}

// Store original content separately to avoid HTML attribute encoding issues
let originalFileContent = '';

export function showEditModal(filePath, content, jumpToLine = null) {
    // Remove existing modal if any
    const existingModal = document.querySelector('.edit-modal');
    if (existingModal) {
        existingModal.remove();
    }

    originalFileContent = content;

    const modal = document.createElement('div');
    modal.className = 'edit-modal';

    // Generate line numbers
    const lines = content.split('\n');
    const lineNumbersHTML = lines.map((_, i) => {
        const lineNum = i + 1;
        const isHighlighted = jumpToLine && lineNum === jumpToLine;
        return `<div class="${isHighlighted ? 'highlighted-line' : ''}">${lineNum}</div>`;
    }).join('');

    modal.innerHTML = `
        <div class="edit-modal-content">
            <div class="edit-modal-header">
                <div class="edit-modal-title">Edit: ${escapeHtml(filePath)}</div>
                <button class="edit-modal-close">&times;</button>
            </div>
            <div class="edit-modal-body">
                <div class="edit-line-numbers">${lineNumbersHTML}</div>
                <textarea class="edit-textarea" spellcheck="false" data-file-path="${escapeHtml(filePath)}">${escapeHtml(content)}</textarea>
            </div>
            <div class="edit-modal-footer">
                <button class="btn btn-secondary" data-action="cancel">Cancel</button>
                <button class="btn btn-primary" data-action="save">Save Changes</button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    const textarea = modal.querySelector('.edit-textarea');
    textarea.focus();

    // Set up line number synchronization
    const lineNumbersEl = modal.querySelector('.edit-line-numbers');
    textarea.addEventListener('scroll', () => {
        lineNumbersEl.scrollTop = textarea.scrollTop;
    });

    // Update line numbers on content change
    textarea.addEventListener('input', () => {
        const newLines = textarea.value.split('\n');
        const newLineNumbersHTML = newLines.map((_, i) => `<div>${i + 1}</div>`).join('');
        lineNumbersEl.innerHTML = newLineNumbersHTML;
    });

    // Add event listeners
    const closeBtn = modal.querySelector('.edit-modal-close');
    const cancelBtn = modal.querySelector('[data-action="cancel"]');
    const saveBtn = modal.querySelector('[data-action="save"]');

    closeBtn.addEventListener('click', closeEditModal);
    cancelBtn.addEventListener('click', closeEditModal);
    saveBtn.addEventListener('click', saveFileEdit);

    // Jump to specific line if requested
    if (jumpToLine) {
        const lineHeight = 16; // matches CSS line-height
        const targetScrollTop = (jumpToLine - 1) * lineHeight;
        textarea.scrollTop = targetScrollTop;
        lineNumbersEl.scrollTop = targetScrollTop;

        // Select the line
        setTimeout(() => {
            const startPos = content.split('\n').slice(0, jumpToLine - 1).join('\n').length + (jumpToLine > 1 ? 1 : 0);
            const endPos = startPos + (lines[jumpToLine - 1] ? lines[jumpToLine - 1].length : 0);
            textarea.setSelectionRange(startPos, endPos);
        }, 100);
    }
}

export function closeEditModal() {
    const modal = document.querySelector('.edit-modal');
    if (modal) {
        modal.remove();
    }
}

export async function saveFileEdit() {
    const modal = document.querySelector('.edit-modal');
    if (!modal) return;

    const textarea = modal.querySelector('.edit-textarea');
    const filePath = textarea.dataset.filePath;
    const newContent = textarea.value;

    try {
        // Create a unified diff patch using module-level originalFileContent
        const patch = createUnifiedDiff(originalFileContent, newContent, filePath);

        const result = await api.saveFileEdit(filePath, patch);
        console.log('File saved successfully:', result);

        // Close modal
        closeEditModal();

        // Reload page to show updated diff
        window.location.reload();

    } catch (error) {
        console.error('Error saving file:', error);
        alert('Failed to save file: ' + error.message);
    }
}

// Create a unified diff patch from original and new content
function createUnifiedDiff(originalContent, newContent, filePath) {
    // Handle the case where content doesn't end with newline
    const originalEndsWithNewline = originalContent.endsWith('\n');
    const newEndsWithNewline = newContent.endsWith('\n');
    
    // Split lines properly - remove empty trailing element from split
    let originalLines = originalContent.split('\n');
    let newLines = newContent.split('\n');

    // When content ends with \n, split creates an empty string at the end
    if (originalEndsWithNewline && originalLines[originalLines.length - 1] === '') {
        originalLines.pop();
    }
    if (newEndsWithNewline && newLines[newLines.length - 1] === '') {
        newLines.pop();
    }
    
    // Simple unified diff creation - replace entire file
    // In a real implementation, you'd use a proper diff algorithm
    let patch = `--- a/${filePath}\n+++ b/${filePath}\n`;
    patch += `@@ -1,${originalLines.length} +1,${newLines.length} @@\n`;
    
    // Add all old lines as deletions
    for (let i = 0; i < originalLines.length; i++) {
        patch += `-${originalLines[i]}`;
        // Add newline unless it's the last line and original doesn't end with newline
        if (i < originalLines.length - 1 || originalEndsWithNewline) {
            patch += '\n';
        } else {
            patch += '\n\\ No newline at end of file\n';
        }
    }
    
    // Add all new lines as additions
    for (let i = 0; i < newLines.length; i++) {
        patch += `+${newLines[i]}`;
        // Add newline unless it's the last line and new doesn't end with newline
        if (i < newLines.length - 1 || newEndsWithNewline) {
            patch += '\n';
        } else {
            patch += '\n\\ No newline at end of file\n';
        }
    }
    
    return patch;
}

export function showLineEditOption(lineElement, filePath, lineNumber, side) {
    // Remove existing edit indicators
    const existingIndicators = lineElement.querySelectorAll('.line-edit-indicator');
    existingIndicators.forEach(indicator => indicator.remove());
    
    // Add edit indicator
    const editIndicator = document.createElement('div');
    editIndicator.className = 'line-edit-indicator';
    editIndicator.textContent = 'Edit';
    editIndicator.title = 'Edit this file';
    editIndicator.addEventListener('click', (e) => {
        e.stopPropagation();
        openFileEditor(filePath, parseInt(lineNumber));
    });
    
    const lineNumberEl = lineElement.querySelector('.line-number');
    if (lineNumberEl) {
        lineNumberEl.style.position = 'relative';
        lineNumberEl.appendChild(editIndicator);
    }
}

// Utility function for escaping HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}