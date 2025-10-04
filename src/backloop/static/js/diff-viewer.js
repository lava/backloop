// Diff viewer and file tree functionality

import * as api from './api.js';
import { showCommentForm } from './comments.js';

// File tree indentation constants
const FILE_TREE_BASE_PADDING = 16;
const FILE_TREE_INDENT_PER_LEVEL = 8;

// Build hierarchical file tree structure
export function buildFileTree(files) {
    const tree = {};
    
    files.forEach(file => {
        const parts = file.path.split('/');
        let current = tree;
        
        for (let i = 0; i < parts.length; i++) {
            const part = parts[i];
            const isFile = i === parts.length - 1;
            
            if (!current[part]) {
                current[part] = isFile ? {
                    type: 'file',
                    data: file,
                    path: file.path
                } : {
                    type: 'folder',
                    children: {},
                    expanded: true
                };
            }
            
            if (!isFile) {
                current = current[part].children;
            }
        }
    });
    
    return tree;
}

// Render file tree
export function renderFileTree(tree, container, depth = 0) {
    const keys = Object.keys(tree).sort((a, b) => {
        const aIsFile = tree[a].type === 'file';
        const bIsFile = tree[b].type === 'file';
        
        if (aIsFile !== bIsFile) {
            return aIsFile ? 1 : -1; // Folders first
        }
        
        return a.localeCompare(b);
    });
    
    keys.forEach(key => {
        const item = tree[key];
        const itemElement = document.createElement('div');
        
        if (item.type === 'file') {
            itemElement.className = 'file-tree-item';
            itemElement.style.paddingLeft = `${FILE_TREE_BASE_PADDING + depth * FILE_TREE_INDENT_PER_LEVEL}px`;
            
            // Determine file status indicator and styling
            let statusIndicator = '';
            let statusClass = '';
            const file = item.data;
            
            switch (file.status) {
                case 'added':
                    statusIndicator = '+ ';
                    statusClass = ' file-added';
                    break;
                case 'deleted':
                    statusIndicator = '- ';
                    statusClass = ' file-deleted';
                    break;
                case 'renamed':
                    statusIndicator = '→ ';
                    statusClass = ' file-renamed';
                    break;
                case 'untracked':
                    statusIndicator = '';
                    statusClass = ' file-untracked';
                    break;
                case 'modified':
                default:
                    statusIndicator = '';
                    statusClass = '';
                    break;
            }
            
            itemElement.className += statusClass;
            
            // Handle binary files and status tags
            let changesDisplay = '';
            if (file.status === 'untracked') {
                changesDisplay = '<span class="status-tag untracked-tag">UNTRACKED</span>';
            } else if (file.binary) {
                changesDisplay = '<span class="binary-indicator">Binary file</span>';
            } else if (file.additions > 0 || file.deletions > 0) {
                changesDisplay = `
                    <span class="additions">+${file.additions}</span>
                    <span class="deletions">−${file.deletions}</span>
                `;
            }
            
            const fileName = file.status === 'renamed'
                ? `${statusIndicator}${file.oldPath} → ${key}`
                : `${statusIndicator}${key}`;

            const tooltipTitle = file.status === 'renamed'
                ? `Renamed from: ${file.oldPath}`
                : file.path;

            itemElement.innerHTML = `
                <svg class="file-icon" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M2 1.75A1.75 1.75 0 013.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0113.25 16h-9.5A1.75 1.75 0 012 14.25V1.75zm1.75-.25a.25.25 0 00-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 00.25-.25V6h-2.75A1.75 1.75 0 019 4.25V1.5H3.75z"/>
                </svg>
                <span class="file-name" title="${tooltipTitle}">${fileName}</span>
                <span class="file-changes">${changesDisplay}</span>
            `;
            
            // Add click handler to scroll to file
            itemElement.addEventListener('click', () => {
                scrollToFile(item.data.path);
                
                // Update active state
                document.querySelectorAll('.file-tree-item').forEach(el => {
                    el.classList.remove('active');
                });
                itemElement.classList.add('active');
            });
            
        } else {
            itemElement.className = 'file-tree-item folder-item';
            itemElement.style.paddingLeft = `${FILE_TREE_BASE_PADDING + depth * FILE_TREE_INDENT_PER_LEVEL}px`;
            const expanded = item.expanded ? '' : 'collapsed';
            itemElement.innerHTML = `
                <span class="folder-toggle">▶</span>
                <svg class="file-icon folder-icon" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M1.75 2A1.75 1.75 0 000 3.75v8.5C0 13.216.784 14 1.75 14h12.5A1.75 1.75 0 0016 12.25v-8.5A1.75 1.75 0 0014.25 2H7.5L6.25.75A1.75 1.75 0 005.086.25H1.75z"/>
                </svg>
                <span class="file-name">${key}</span>
            `;
            
            // Create folder children container
            const childrenContainer = document.createElement('div');
            childrenContainer.className = `folder-children ${expanded}`;
            
            // Add click handler for folder toggle
            itemElement.addEventListener('click', (e) => {
                e.stopPropagation();
                const isExpanded = !childrenContainer.classList.contains('collapsed');
                
                if (isExpanded) {
                    childrenContainer.classList.add('collapsed');
                    itemElement.classList.add('collapsed');
                } else {
                    childrenContainer.classList.remove('collapsed');
                    itemElement.classList.remove('collapsed');
                }
                
                item.expanded = !isExpanded;
            });
            
            container.appendChild(itemElement);
            renderFileTree(item.children, childrenContainer, depth + 1);
            container.appendChild(childrenContainer);
            return;
        }
        
        container.appendChild(itemElement);
    });
}

// Scroll to specific file in diff view using anchors
export function scrollToFile(filePath) {
    // Create a sanitized anchor ID from the file path
    const anchorId = 'file-' + filePath.replace(/[^a-zA-Z0-9]/g, '-');

    // Find the file section in the old pane (we'll scroll both panes via sync)
    const oldPane = document.getElementById('old-pane');
    const oldContent = document.getElementById('old-content');

    if (!oldPane || !oldContent) {
        console.error('Diff panes not found for scrolling');
        return;
    }

    // Find the file section
    const fileSection = oldContent.querySelector(`#${anchorId}-old-pane`);

    if (fileSection) {
        // Calculate the position relative to the scrollable container
        const containerTop = oldContent.offsetTop;
        const elementTop = fileSection.offsetTop;
        const scrollPosition = elementTop - containerTop;

        // Scroll the pane (synchronized scrolling will handle the other pane)
        oldPane.scrollTop = scrollPosition;
    } else {
        console.warn(`File section not found for: ${filePath} (anchor: ${anchorId})`);
    }
}

// Setup click handler for line numbers to show comment forms
export function setupLineClickHandlers() {
    console.log('Setting up global click handler...');
    document.addEventListener('click', (e) => {
        console.log('Document clicked, target:', e.target, 'className:', e.target.className);
        
        // Check if clicking on line number or its children
        const lineNumber = e.target.closest('.line-number');
        console.log('Found line-number element?', lineNumber);
        if (!lineNumber) return;

        e.preventDefault();
        e.stopPropagation();

        const lineElement = lineNumber.closest('.diff-line');
        console.log('Found diff-line?', lineElement);
        if (!lineElement || lineElement.classList.contains('empty-line')) {
            console.log('Line element is empty or not found');
            return;
        }

        // Extract line information
        const fileSection = lineElement.closest('.file-section');
        console.log('Found file-section?', fileSection);
        if (!fileSection) return;
        
        const filePathEl = fileSection.querySelector('.file-path');
        console.log('Found file-path element?', filePathEl);
        if (!filePathEl) return;
        
        const filePath = filePathEl.textContent;
        const diffPane = lineElement.closest('.diff-pane');
        const side = diffPane.id === 'old-pane' ? 'old' : 'new';
        
        const oldNumEl = lineNumber.querySelector('.old-line-num');
        const newNumEl = lineNumber.querySelector('.new-line-num');
        const oldNum = oldNumEl ? oldNumEl.textContent.trim() : null;
        const newNum = newNumEl ? newNumEl.textContent.trim() : null;
        
        console.log('Line numbers - old:', oldNum, 'new:', newNum, 'side:', side);
        
        // Use the appropriate line number for the side
        const lineNum = side === 'old' ? oldNum : newNum;
        
        if (lineNum) {
            console.log('Line clicked (global handler):', filePath, lineNum, side);
            // Show comment form
            showCommentForm(filePath, lineNum, side, lineElement);
        } else {
            console.log('No line number found for side:', side);
        }
    });
    console.log('Global click handler setup complete.');
}

// Sort files to match the file tree order (alphabetically by path)
function sortFilesForDisplay(files) {
    return [...files].sort((a, b) => {
        return a.path.localeCompare(b.path);
    });
}

// Render diff content for all files
export function renderDiffContent(files) {
    const oldPane = document.getElementById('old-content');
    const newPane = document.getElementById('new-content');

    if (!oldPane || !newPane) {
        console.error('Diff panes not found');
        return;
    }

    // Clear existing content
    oldPane.innerHTML = '';
    newPane.innerHTML = '';

    // Sort files to match file tree order
    const sortedFiles = sortFilesForDisplay(files);

    // Render each file
    sortedFiles.forEach(file => {
        renderFile(file, oldPane, newPane);
    });

    // Update file count
    const fileCountEl = document.getElementById('files-count');
    if (fileCountEl) {
        fileCountEl.textContent = files.length;
    }
}

// Render a single file's diff
function renderFile(file, oldPane, newPane) {
    const anchorId = 'file-' + file.path.replace(/[^a-zA-Z0-9]/g, '-');

    // Create file section for old pane
    const oldFileSection = createFileSection(file, 'old', anchorId);
    oldPane.appendChild(oldFileSection);

    // Create file section for new pane
    const newFileSection = createFileSection(file, 'new', anchorId);
    newPane.appendChild(newFileSection);

    // Render chunks
    if (file.is_binary) {
        // Handle binary files
        const binaryMsg = '<div class="binary-message">Binary file</div>';
        oldFileSection.querySelector('.file-content').innerHTML = binaryMsg;
        newFileSection.querySelector('.file-content').innerHTML = binaryMsg;
    } else {
        // Render diff chunks
        file.chunks.forEach(chunk => {
            renderChunk(chunk, oldFileSection, newFileSection, file.path);
        });
    }
}

// Create file section header
function createFileSection(file, side, anchorId) {
    const section = document.createElement('div');
    section.className = 'file-section';
    section.id = `${anchorId}-${side}-pane`;

    const header = document.createElement('div');
    header.className = 'file-header';

    const pathSpan = document.createElement('span');
    pathSpan.className = 'file-path';
    pathSpan.textContent = file.path;

    header.appendChild(pathSpan);

    // Add status badge
    if (file.status) {
        const badge = document.createElement('span');
        badge.className = `status-badge status-${file.status}`;
        badge.textContent = file.status.toUpperCase();
        header.appendChild(badge);
    }

    const content = document.createElement('div');
    content.className = 'file-content';

    section.appendChild(header);
    section.appendChild(content);

    return section;
}

// Render a diff chunk
function renderChunk(chunk, oldSection, newSection, filePath) {
    const oldContent = oldSection.querySelector('.file-content');
    const newContent = newSection.querySelector('.file-content');

    // Check if there's a gap before this chunk
    const existingLines = oldContent.querySelectorAll('.diff-line:not(.empty-line)');
    if (existingLines.length > 0) {
        const lastLine = existingLines[existingLines.length - 1];
        const lastOldNum = parseInt(lastLine.querySelector('.old-line-num')?.textContent || '0');
        const lastNewNum = parseInt(lastLine.querySelector('.new-line-num')?.textContent || '0');

        // Get first line numbers of this chunk
        const firstLine = chunk.lines[0];
        const firstOldNum = firstLine.oldNum ? parseInt(firstLine.oldNum) : null;
        const firstNewNum = firstLine.newNum ? parseInt(firstLine.newNum) : null;

        // Check if there's a gap (more than 1 line difference)
        const oldGap = firstOldNum && lastOldNum && (firstOldNum - lastOldNum > 1);
        const newGap = firstNewNum && lastNewNum && (firstNewNum - lastNewNum > 1);

        if (oldGap || newGap) {
            // Insert gap indicator
            const oldGapLine = createGapIndicator();
            const newGapLine = createGapIndicator();
            oldContent.appendChild(oldGapLine);
            newContent.appendChild(newGapLine);
        }
    }

    chunk.lines.forEach(line => {
        const oldLine = createDiffLine(line, 'old', filePath);
        const newLine = createDiffLine(line, 'new', filePath);

        oldContent.appendChild(oldLine);
        newContent.appendChild(newLine);
    });
}

// Create a gap indicator element
function createGapIndicator() {
    const gapDiv = document.createElement('div');
    gapDiv.className = 'chunk-gap';
    gapDiv.innerHTML = '<div class="gap-line"></div>';
    return gapDiv;
}

// Create a diff line element
function createDiffLine(line, side, filePath) {
    const lineDiv = document.createElement('div');
    lineDiv.className = 'diff-line';

    // Generate unique ID for this line based on file path, line number, and side
    const lineNum = side === 'old' ? line.oldNum : line.newNum;
    if (lineNum && filePath) {
        // Sanitize file path for use in ID
        const sanitizedPath = filePath.replace(/[^a-zA-Z0-9]/g, '-');
        lineDiv.id = `line-${sanitizedPath}-${lineNum}-${side}`;
    }

    // Determine line type class
    switch (line.type) {
        case 'addition':
            lineDiv.classList.add('addition');
            break;
        case 'deletion':
            lineDiv.classList.add('deletion');
            break;
        case 'context':
            lineDiv.classList.add('context');
            break;
    }

    // Create line number section
    const lineNumber = document.createElement('div');
    lineNumber.className = 'line-number';

    const oldNum = document.createElement('span');
    oldNum.className = 'old-line-num';
    oldNum.textContent = line.oldNum || '';

    const newNum = document.createElement('span');
    newNum.className = 'new-line-num';
    newNum.textContent = line.newNum || '';

    lineNumber.appendChild(oldNum);
    lineNumber.appendChild(newNum);

    // Create content section
    const content = document.createElement('div');
    content.className = 'line-content';
    content.textContent = line.content;

    // Handle empty lines based on side and type
    if (side === 'old' && line.type === 'addition') {
        lineDiv.classList.add('empty-line');
        content.innerHTML = '&nbsp;';
    } else if (side === 'new' && line.type === 'deletion') {
        lineDiv.classList.add('empty-line');
        content.innerHTML = '&nbsp;';
    }

    lineDiv.appendChild(lineNumber);
    lineDiv.appendChild(content);

    return lineDiv;
}

// Setup synchronized scrolling between diff panes
export function setupSynchronizedScrolling() {
    const oldPane = document.getElementById('old-pane');
    const newPane = document.getElementById('new-pane');

    if (!oldPane || !newPane) {
        console.error('Diff panes not found for synchronized scrolling');
        return;
    }

    let isScrolling = false;

    const syncScroll = (source, target) => {
        if (isScrolling) return;

        isScrolling = true;
        target.scrollTop = source.scrollTop;
        target.scrollLeft = source.scrollLeft;

        // Use requestAnimationFrame to reset the flag
        requestAnimationFrame(() => {
            isScrolling = false;
        });
    };

    oldPane.addEventListener('scroll', () => syncScroll(oldPane, newPane));
    newPane.addEventListener('scroll', () => syncScroll(newPane, oldPane));
}

// Initialize diff viewer when page loads
export async function initializeDiffViewer() {
    // Parse query parameters to determine diff type
    const urlParams = new URLSearchParams(window.location.search);
    const commit = urlParams.get('commit');
    const range = urlParams.get('range');
    const since = urlParams.get('since');
    const live = urlParams.get('live') === 'true';
    const mock = urlParams.get('mock') === 'true';

    // Setup line click handlers
    setupLineClickHandlers();

    // Setup synchronized scrolling
    setupSynchronizedScrolling();

    // Load diff data
    try {
        const params = { commit, range, since, live, mock };
        const diffData = await api.fetchDiff(params);

        if (diffData && diffData.files) {
            // Build and render file tree
            const fileTree = buildFileTree(diffData.files);
            const fileTreeContainer = document.getElementById('file-tree');
            if (fileTreeContainer) {
                renderFileTree(fileTree, fileTreeContainer);
            }

            // Render diff content
            renderDiffContent(diffData.files);
        }
    } catch (error) {
        console.error('Error loading diff data:', error);
    }
}

// Approve review functionality
export async function approveReview() {
    try {
        const reviewId = await api.getReviewId();
        await api.approveReview(reviewId);

        console.log('Review approved successfully');

        // Try to close the tab
        window.close();

        // If we're still here after a short delay, the close didn't work
        // Show a full-screen approval message instead
        setTimeout(() => {
            document.body.innerHTML = `
                <div style="display: flex; align-items: center; justify-content: center; height: 100vh; background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <div style="text-align: center;">
                        <svg viewBox="0 0 16 16" fill="#3fb950" width="64" height="64" style="margin-bottom: 20px;">
                            <path d="M13.78 4.22a.75.75 0 0 1 0 1.06l-7.25 7.25a.75.75 0 0 1-1.06 0L2.22 9.28a.751.751 0 0 1 .018-1.042.751.751 0 0 1 1.042-.018L6 10.94l6.72-6.72a.75.75 0 0 1 1.06 0Z"/>
                        </svg>
                        <h1 style="font-size: 32px; margin: 0 0 10px 0;">Review Approved</h1>
                        <p style="font-size: 16px; color: #8b949e;">You can close this tab</p>
                    </div>
                </div>
            `;
        }, 100);
    } catch (error) {
        console.error('Error approving review:', error);
        alert('Failed to approve review: ' + error.message);
    }
}

export function showRefreshButton(filePath) {
    // Find the active comment form for this file
    const commentForm = document.querySelector(`.comment-form[data-file-path="${filePath}"]`);

    if (!commentForm) {
        console.warn(`No active comment form found for: ${filePath}`);
        return;
    }

    // Check if refresh button already exists
    if (commentForm.querySelector('.refresh-button')) {
        return;
    }

    const refreshButton = document.createElement('button');
    refreshButton.className = 'btn btn-tertiary refresh-button';
    refreshButton.innerHTML = `
        <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M1.705 8.005a.75.75 0 0 1 .834.656 5.5 5.5 0 0 0 9.592 2.97l-1.204-1.204a.25.25 0 0 1 .177-.427h3.646a.25.25 0 0 1 .25.25v3.646a.25.25 0 0 1-.427.177l-1.38-1.38A7.002 7.002 0 0 1 1.05 8.84a.75.75 0 0 1 .656-.834ZM8 2.5a5.487 5.487 0 0 0-4.131 1.869l1.204 1.204A.25.25 0 0 1 4.896 6H1.25A.25.25 0 0 1 1 5.75V2.104a.25.25 0 0 1 .427-.177l1.38 1.38A7.002 7.002 0 0 1 14.95 7.16a.75.75 0 0 1-1.49.178A5.5 5.5 0 0 0 8 2.5Z"/>
        </svg>
        Refresh File
    `;
    refreshButton.title = 'This file has changed on disk. Click to reload.';
    refreshButton.onclick = async () => {
        await refreshFile(filePath);
        refreshButton.remove();
    };

    const buttonsDiv = commentForm.querySelector('.comment-form-buttons');
    if (buttonsDiv) {
        buttonsDiv.appendChild(refreshButton);
    }
}

export async function refreshFile(filePath) {
    console.log('Refreshing file:', filePath);

    try {
        const urlParams = new URLSearchParams(window.location.search);
        const commit = urlParams.get('commit');
        const range = urlParams.get('range');
        const since = urlParams.get('since');
        const live = urlParams.get('live') === 'true';
        const mock = urlParams.get('mock') === 'true';

        const params = { commit, range, since, live, mock };
        const diffData = await api.fetchDiff(params);

        if (!diffData || !diffData.files) {
            console.error('Failed to fetch updated diff');
            return;
        }

        const updatedFile = diffData.files.find(f => f.path === filePath);
        if (!updatedFile) {
            console.warn(`File ${filePath} not found in updated diff`);
            return;
        }

        const anchorId = 'file-' + filePath.replace(/[^a-zA-Z0-9]/g, '-');
        const oldFileSection = document.getElementById(`${anchorId}-old-pane`);
        const newFileSection = document.getElementById(`${anchorId}-new-pane`);

        if (!oldFileSection || !newFileSection) {
            console.error('File sections not found for re-rendering');
            return;
        }

        const oldContent = oldFileSection.querySelector('.file-content');
        const newContent = newFileSection.querySelector('.file-content');

        if (oldContent && newContent) {
            oldContent.innerHTML = '';
            newContent.innerHTML = '';

            if (updatedFile.is_binary) {
                const binaryMsg = '<div class="binary-message">Binary file</div>';
                oldContent.innerHTML = binaryMsg;
                newContent.innerHTML = binaryMsg;
            } else {
                updatedFile.chunks.forEach(chunk => {
                    renderChunk(chunk, oldFileSection, newFileSection, updatedFile.path);
                });
            }

            updateFileHeaderStats(newFileSection, updatedFile);

            // Remove refresh button from any active comment form
            const commentForm = document.querySelector(`.comment-form[data-file-path="${filePath}"]`);
            if (commentForm) {
                const refreshButton = commentForm.querySelector('.refresh-button');
                if (refreshButton) {
                    refreshButton.remove();
                }
            }

            console.log('File refreshed successfully:', filePath);
        }
    } catch (error) {
        console.error('Error refreshing file:', error);
        alert('Failed to refresh file: ' + error.message);
    }
}

function updateFileHeaderStats(fileSection, file) {
    const header = fileSection.querySelector('.file-header');
    if (!header) return;

    const existingBadge = header.querySelector('.status-badge');
    if (existingBadge && file.status) {
        existingBadge.className = `status-badge status-${file.status}`;
        existingBadge.textContent = file.status.toUpperCase();
    }
}