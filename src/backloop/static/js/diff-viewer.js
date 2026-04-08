// Diff viewer and file tree functionality

import * as api from './api.js';
import { showCommentForm, preserveInProgressComments, restoreInProgressComments, displayCommentsForCurrentDOM } from './comments.js';

// File tree indentation constants
const FILE_TREE_BASE_PADDING = 16;
const FILE_TREE_INDENT_PER_LEVEL = 8;

// Single-file mode state
const SINGLE_MODE_LINE_THRESHOLD = 50;
let singleMode = false;
let selectedFilePath = null;
let allFiles = []; // cached for re-rendering on selection change

export function isSingleMode() { return singleMode; }

function setSingleMode(enabled) {
    singleMode = enabled;
    document.body.classList.toggle('single-mode', enabled);
    // Update toggle button state
    const toggle = document.getElementById('single-mode-toggle');
    if (toggle) toggle.classList.toggle('active', enabled);
}

// Count total diff lines across all files
function anyFileExceedsLineThreshold(files, threshold) {
    for (const file of files) {
        let fileLines = 0;
        for (const chunk of (file.chunks || [])) {
            fileLines += (chunk.lines || []).length;
        }
        if (fileLines > threshold) return true;
    }
    return false;
}

// Navigate to prev/next file in single mode
export function navigateSingleMode(direction) {
    if (!singleMode || allFiles.length === 0) return;
    const currentIndex = allFiles.findIndex(f => f.path === selectedFilePath);
    const newIndex = Math.max(0, Math.min(allFiles.length - 1, currentIndex + direction));
    if (newIndex !== currentIndex) {
        selectFileInSingleMode(allFiles[newIndex].path);
    }
}

// Select a file in single mode - re-renders just that file's diff
function selectFileInSingleMode(filePath) {
    if (!singleMode) return;
    selectedFilePath = filePath;

    // Update active state in file tree
    document.querySelectorAll('.file-tree-item').forEach(el => {
        el.classList.remove('active');
    });
    const item = document.querySelector(`.file-tree-item[data-file-path="${CSS.escape(filePath)}"]`);
    if (item) item.classList.add('active');

    // Re-render diff with only the selected file
    const file = allFiles.find(f => f.path === filePath);
    if (file) {
        const oldPane = document.getElementById('old-content');
        const newPane = document.getElementById('new-content');
        if (oldPane && newPane) {
            oldPane.innerHTML = '';
            newPane.innerHTML = '';
            renderFile(file, oldPane, newPane);
            // Re-display comments for the newly rendered file
            displayCommentsForCurrentDOM();
        }
    }
}

// Update page title based on review info
export function updatePageTitle(reviewInfo) {
    if (reviewInfo && reviewInfo.title) {
        // Set browser tab title to just the review title
        document.title = reviewInfo.title;

        // Set page heading with prefix
        const heading = document.querySelector('.header h1');
        if (heading) {
            const connectionStatus = heading.querySelector('#connection-status');
            heading.textContent = `Backloop Code Review: ${reviewInfo.title} `;
            if (connectionStatus) {
                heading.appendChild(connectionStatus);
            }
        }
    }
}

// Build hierarchical file tree structure
export function buildFileTree(files) {
    // Collect submodule paths from file metadata
    const submodulePaths = new Set();
    files.forEach(file => {
        if (file.submodule) submodulePaths.add(file.submodule);
    });

    const tree = {};

    files.forEach(file => {
        const parts = file.path.split('/');
        let current = tree;
        let pathSoFar = '';

        for (let i = 0; i < parts.length; i++) {
            const part = parts[i];
            const isFile = i === parts.length - 1;
            pathSoFar = pathSoFar ? `${pathSoFar}/${part}` : part;

            if (!current[part]) {
                current[part] = isFile ? {
                    type: 'file',
                    data: file,
                    path: file.path
                } : {
                    type: 'folder',
                    children: {},
                    expanded: true,
                    isSubmodule: submodulePaths.has(pathSoFar)
                };
            } else if (!isFile && current[part].type === 'file') {
                // A file node needs to become a folder (e.g. a submodule
                // placeholder at "contrib/plugins" collides with files
                // inside "contrib/plugins/...").  Promote to folder.
                current[part] = {
                    type: 'folder',
                    children: {},
                    expanded: true,
                    isSubmodule: submodulePaths.has(pathSoFar)
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
                case 'submodule':
                    statusIndicator = '';
                    statusClass = '';
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
            if (file.status === 'submodule') {
                changesDisplay = '<span class="status-tag submodule-tag">SUBMODULE</span>';
            } else if (file.status === 'untracked') {
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
            
            // Store file path as data attribute for single mode selection
            itemElement.dataset.filePath = file.path;

            // Add click handler to scroll to file (or select in single mode)
            itemElement.addEventListener('click', () => {
                if (singleMode) {
                    selectFileInSingleMode(item.data.path);
                } else {
                    scrollToFile(item.data.path);

                    // Update active state
                    document.querySelectorAll('.file-tree-item').forEach(el => {
                        el.classList.remove('active');
                    });
                    itemElement.classList.add('active');
                }
            });
            
        } else {
            itemElement.className = 'file-tree-item folder-item';
            itemElement.style.paddingLeft = `${FILE_TREE_BASE_PADDING + depth * FILE_TREE_INDENT_PER_LEVEL}px`;
            const expanded = item.expanded ? '' : 'collapsed';
            const submoduleBadge = item.isSubmodule
                ? '<span class="status-tag submodule-tag">SUBMODULE</span>'
                : '';
            itemElement.innerHTML = `
                <span class="folder-toggle">▶</span>
                <svg class="file-icon folder-icon" viewBox="0 0 16 16" fill="currentColor">
                    <path d="M1.75 2A1.75 1.75 0 000 3.75v8.5C0 13.216.784 14 1.75 14h12.5A1.75 1.75 0 0016 12.25v-8.5A1.75 1.75 0 0014.25 2H7.5L6.25.75A1.75 1.75 0 005.086.25H1.75z"/>
                </svg>
                <span class="file-name">${key}</span>
                ${submoduleBadge}
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
        if (!lineElement) {
            console.log('Line element not found');
            return;
        }

        // Allow clicking on empty lines (deleted lines in new pane, added lines in old pane)
        // The comment will use the line number from the opposite side

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
        // For empty lines, use the line number from the opposite side
        let lineNum = side === 'old' ? oldNum : newNum;
        if (!lineNum || lineNum === '') {
            // This is an empty line, use the opposite side's line number
            lineNum = side === 'old' ? newNum : oldNum;
            console.log('Empty line detected, using opposite side line number:', lineNum);
        }

        if (lineNum && lineNum !== '') {
            console.log('Line clicked (global handler):', filePath, lineNum, side);
            // Show comment form
            showCommentForm(filePath, lineNum, side, lineElement);
        } else {
            console.log('No line number found for either side:', side);
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

    // Cache files for single mode re-rendering
    allFiles = sortFilesForDisplay(files);

    // Clear existing content
    oldPane.innerHTML = '';
    newPane.innerHTML = '';

    if (singleMode) {
        // In single mode, render only the selected file (or first file)
        if (!selectedFilePath || !allFiles.find(f => f.path === selectedFilePath)) {
            selectedFilePath = allFiles.length > 0 ? allFiles[0].path : null;
        }
        if (selectedFilePath) {
            const file = allFiles.find(f => f.path === selectedFilePath);
            if (file) renderFile(file, oldPane, newPane);
            // Highlight selected file in tree
            setTimeout(() => {
                document.querySelectorAll('.file-tree-item').forEach(el => el.classList.remove('active'));
                const item = document.querySelector(`.file-tree-item[data-file-path="${CSS.escape(selectedFilePath)}"]`);
                if (item) item.classList.add('active');
            }, 0);
        }
    } else {
        // Render each file
        allFiles.forEach(file => {
            renderFile(file, oldPane, newPane);
        });
    }

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
        let sharedLineCounter = 0;
        file.chunks.forEach(chunk => {
            sharedLineCounter = renderChunk(
                chunk,
                oldFileSection,
                newFileSection,
                file.path,
                sharedLineCounter
            );
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

    const leftGroup = document.createElement('span');
    leftGroup.className = 'file-header-left';

    const pathSpan = document.createElement('span');
    pathSpan.className = 'file-path';
    pathSpan.textContent = file.path;

    leftGroup.appendChild(pathSpan);

    // Add expand full file button
    // Old side: no button for added/untracked files (no prior version exists)
    // New side: no button for deleted files (file no longer exists)
    const showExpand = !file.is_binary
        && !(side === 'old' && (file.status === 'added' || file.status === 'untracked'))
        && !(side === 'new' && file.status === 'deleted');
    if (showExpand) {
        const expandBtn = document.createElement('button');
        expandBtn.className = 'expand-file-btn';
        expandBtn.title = 'Show full file';
        expandBtn.innerHTML = `<svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M8 1a.75.75 0 0 1 .53.22l2.5 2.5a.75.75 0 0 1-1.06 1.06L8 2.81 6.03 4.78a.75.75 0 0 1-1.06-1.06l2.5-2.5A.75.75 0 0 1 8 1zM5.03 11.22a.75.75 0 0 1 1.06 0L8 13.19l1.97-1.97a.75.75 0 1 1 1.06 1.06l-2.5 2.5a.75.75 0 0 1-1.06 0l-2.5-2.5a.75.75 0 0 1 0-1.06z"/>
        </svg>`;
        expandBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            expandFullFile(file, side, anchorId);
        });
        leftGroup.appendChild(expandBtn);
    }

    header.appendChild(leftGroup);

    const rightGroup = document.createElement('span');
    rightGroup.className = 'file-header-right';

    // Add status badge
    if (file.status) {
        const badge = document.createElement('span');
        badge.className = `status-badge status-${file.status}`;
        badge.textContent = file.status.toUpperCase();
        rightGroup.appendChild(badge);
    }

    // Add submodule badge
    if (file.submodule) {
        const subBadge = document.createElement('span');
        subBadge.className = 'status-tag submodule-tag';
        subBadge.textContent = `SUBMODULE: ${file.submodule}`;
        rightGroup.appendChild(subBadge);
    }

    header.appendChild(rightGroup);

    const content = document.createElement('div');
    content.className = 'file-content';

    section.appendChild(header);
    section.appendChild(content);

    return section;
}

// Determine the git ref for the old (before) and new (after) sides of the diff
function getRefsForSides() {
    const urlParams = new URLSearchParams(window.location.search);
    const commit = urlParams.get('commit');
    const range = urlParams.get('range');
    const since = urlParams.get('since');

    if (commit) {
        return { oldRef: `${commit}~1`, newRef: commit };
    } else if (range) {
        const parts = range.split('..');
        return { oldRef: parts[0], newRef: parts[1] || 'HEAD' };
    } else {
        // Live mode
        return { oldRef: since || 'HEAD', newRef: null };
    }
}

// Expand a file section to show the full file content
async function expandFullFile(file, side, anchorId) {
    const sectionId = `${anchorId}-${side}-pane`;
    const section = document.getElementById(sectionId);
    if (!section) return;

    const contentEl = section.querySelector('.file-content');
    const btn = section.querySelector('.expand-file-btn');

    // Toggle: if already expanded, collapse back to diff
    if (section.dataset.expanded === 'true') {
        collapseToChunks(file, side, anchorId);
        return;
    }

    // Show loading state
    if (btn) {
        btn.classList.add('loading');
        btn.title = 'Loading...';
    }

    const refs = getRefsForSides();
    const ref = side === 'old' ? refs.oldRef : refs.newRef;
    const filePath = file.path;

    try {
        const content = await api.getFileContent(filePath, ref);
        if (!content) {
            if (btn) {
                btn.classList.remove('loading');
                btn.title = 'Show full file';
            }
            return;
        }

        const lines = content.split('\n');
        // Remove trailing empty line from split if file ends with newline
        if (lines.length > 0 && lines[lines.length - 1] === '') {
            lines.pop();
        }

        // Build a set of changed line numbers for highlighting
        const changedLines = new Set();
        const lineTypes = new Map();
        for (const chunk of (file.chunks || [])) {
            for (const line of chunk.lines) {
                const num = side === 'old' ? line.oldNum : line.newNum;
                if (num && line.type !== 'context') {
                    changedLines.add(num);
                    lineTypes.set(num, line.type);
                }
            }
        }

        // Clear current content and render full file
        contentEl.innerHTML = '';

        const sanitizedPath = file.path.replace(/[^a-zA-Z0-9]/g, '-');

        lines.forEach((lineText, idx) => {
            const lineNum = idx + 1;
            const lineDiv = document.createElement('div');
            lineDiv.className = 'diff-line';
            lineDiv.id = `line-${sanitizedPath}-${lineNum}-${side}`;

            const type = lineTypes.get(lineNum);
            if (type === 'addition') {
                lineDiv.classList.add('addition');
            } else if (type === 'deletion') {
                lineDiv.classList.add('deletion');
            } else {
                lineDiv.classList.add('context');
            }

            const lineNumDiv = document.createElement('div');
            lineNumDiv.className = 'line-number';

            const numSpan = document.createElement('span');
            numSpan.className = side === 'old' ? 'old-line-num' : 'new-line-num';
            numSpan.textContent = lineNum;
            lineNumDiv.appendChild(numSpan);

            const contentSpan = document.createElement('span');
            contentSpan.className = 'line-content';
            contentSpan.textContent = lineText || '\u00a0';

            lineDiv.appendChild(lineNumDiv);
            lineDiv.appendChild(contentSpan);
            contentEl.appendChild(lineDiv);
        });

        // Re-display any existing comments for this file
        displayCommentsForCurrentDOM();

        section.dataset.expanded = 'true';
        if (btn) {
            btn.classList.remove('loading');
            btn.classList.add('active');
            btn.title = 'Collapse to diff';
        }
    } catch (err) {
        console.error('Failed to expand full file:', err);
        if (btn) {
            btn.classList.remove('loading');
            btn.title = 'Show full file';
        }
    }
}

// Collapse an expanded file section back to diff chunks
function collapseToChunks(file, side, anchorId) {
    const sectionId = `${anchorId}-${side}-pane`;
    const section = document.getElementById(sectionId);
    if (!section) return;

    const contentEl = section.querySelector('.file-content');
    contentEl.innerHTML = '';

    // Find the paired section on the other side
    const otherSide = side === 'old' ? 'new' : 'old';
    const otherSectionId = `${anchorId}-${otherSide}-pane`;
    const otherSection = document.getElementById(otherSectionId);

    // Re-render chunks for both sides together
    let sharedLineCounter = 0;
    for (const chunk of (file.chunks || [])) {
        sharedLineCounter = renderChunk(
            chunk,
            side === 'old' ? section : otherSection,
            side === 'new' ? section : otherSection,
            file.path,
            sharedLineCounter,
        );
    }

    // Re-display any existing comments for this file
    displayCommentsForCurrentDOM();

    section.dataset.expanded = 'false';
    const btn = section.querySelector('.expand-file-btn');
    if (btn) {
        btn.classList.remove('active');
        btn.title = 'Show full file';
    }
}

// Render a diff chunk
function renderChunk(chunk, oldSection, newSection, filePath, startingIndex = 0) {
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

    let lineIndex = startingIndex;

    chunk.lines.forEach(line => {
        lineIndex += 1;
        const oldLine = createDiffLine(line, 'old', filePath, lineIndex);
        const newLine = createDiffLine(line, 'new', filePath, lineIndex);

        oldContent.appendChild(oldLine);
        newContent.appendChild(newLine);
    });

    return lineIndex;
}

// Create a gap indicator element
function createGapIndicator() {
    const gapDiv = document.createElement('div');
    gapDiv.className = 'chunk-gap';
    gapDiv.innerHTML = '<div class="gap-line"></div>';
    return gapDiv;
}

// Create a diff line element
function createDiffLine(line, side, filePath, sharedLineIndex) {
    const lineDiv = document.createElement('div');
    lineDiv.className = 'diff-line';

    // Generate unique ID for this line based on file path, line number, and side
    // For empty lines, use the opposite side's line number
    let lineNum = side === 'old' ? line.oldNum : line.newNum;
    if ((!lineNum || lineNum === '') && filePath) {
        lineNum = side === 'old' ? line.newNum : line.oldNum;
    }

    if (lineNum && filePath) {
        // Sanitize file path for use in ID
        const sanitizedPath = filePath.replace(/[^a-zA-Z0-9]/g, '-');
        lineDiv.id = `line-${sanitizedPath}-${lineNum}-${side}`;
    }

    // Attach metadata to link the corresponding lines across panes
    lineDiv.dataset.filePath = filePath;
    lineDiv.dataset.side = side;
    lineDiv.dataset.sharedLineIndex = String(sharedLineIndex);
    lineDiv.dataset.oldLineNumber = line.oldNum || '';
    lineDiv.dataset.newLineNumber = line.newNum || '';

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
    const modeParam = urlParams.get('mode');

    // Check if single mode is forced via query param
    if (modeParam === 'single') {
        setSingleMode(true);
    }

    // Setup single mode toggle button in sidebar header
    setupSingleModeToggle();

    // Setup line click handlers
    setupLineClickHandlers();

    // Setup synchronized scrolling
    setupSynchronizedScrolling();

    // Load review info and diff data
    try {
        // Fetch review info and update page title
        const reviewInfo = await api.fetchReviewInfo();
        updatePageTitle(reviewInfo);

        // Fetch diff data
        const params = { commit, range, since, live, mock };
        const diffData = await api.fetchDiff(params);

        if (diffData && diffData.files) {
            // Auto-enable single mode if total diff lines exceed threshold
            if (!singleMode && modeParam !== 'all') {
                if (anyFileExceedsLineThreshold(diffData.files, SINGLE_MODE_LINE_THRESHOLD)) {
                    setSingleMode(true);
                    console.log(`Auto-enabled single file mode (file with >${SINGLE_MODE_LINE_THRESHOLD} diff lines found)`);
                }
            }

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

// Setup the single mode toggle button in the sidebar header
function setupSingleModeToggle() {
    const header = document.querySelector('.files-sidebar-header');
    if (!header) return;

    const toggle = document.createElement('button');
    toggle.id = 'single-mode-toggle';
    toggle.className = 'single-mode-toggle';
    toggle.title = 'Toggle single file mode';
    toggle.innerHTML = `
        <svg viewBox="0 0 16 16" fill="currentColor" width="14" height="14">
            <path d="M2 1.75A1.75 1.75 0 013.75 0h6.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0113.25 16h-9.5A1.75 1.75 0 012 14.25V1.75zm1.75-.25a.25.25 0 00-.25.25v12.5c0 .138.112.25.25.25h9.5a.25.25 0 00.25-.25V6h-2.75A1.75 1.75 0 019 4.25V1.5H3.75z"/>
        </svg>
    `;
    if (singleMode) toggle.classList.add('active');

    toggle.addEventListener('click', (e) => {
        e.stopPropagation();
        setSingleMode(!singleMode);
        // Re-render with current files
        if (allFiles.length > 0) {
            renderDiffContent(allFiles);
        }
    });

    // Insert before the file count badge
    const filesCount = header.querySelector('.files-count');
    if (filesCount) {
        header.insertBefore(toggle, filesCount);
    } else {
        header.appendChild(toggle);
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

// Store pending file updates keyed by file path
const pendingFileUpdates = new Map();

// Get line numbers of all open (non-resolved) comments and in-progress forms for a file
function getCommentLineNumbers(filePath) {
    const lineNumbers = new Set();
    const anchorId = 'file-' + filePath.replace(/[^a-zA-Z0-9]/g, '-');

    // Find comment threads attached to this file
    const fileSelectors = [
        `#${anchorId}-old-pane .comment-thread`,
        `#${anchorId}-new-pane .comment-thread`,
        `#${anchorId}-old-pane .comment-form`,
        `#${anchorId}-new-pane .comment-form`,
    ];

    for (const selector of fileSelectors) {
        const elements = document.querySelectorAll(selector);
        elements.forEach(el => {
            // Walk backwards to find the .diff-line this is attached to
            let sibling = el.previousElementSibling;
            while (sibling && !sibling.classList.contains('diff-line')) {
                sibling = sibling.previousElementSibling;
            }
            if (sibling) {
                const oldNum = parseInt(sibling.dataset.oldLineNumber);
                const newNum = parseInt(sibling.dataset.newLineNumber);
                if (!isNaN(oldNum)) lineNumbers.add(oldNum);
                if (!isNaN(newNum)) lineNumbers.add(newNum);
            }
        });
    }

    return lineNumbers;
}

// Check if any chunk in the updated file overlaps with comment line numbers
function hasCommentOverlap(updatedFile, commentLineNumbers) {
    if (commentLineNumbers.size === 0) return false;

    for (const chunk of updatedFile.chunks || []) {
        const chunkOldEnd = chunk.old_start + chunk.old_lines;
        const chunkNewEnd = chunk.new_start + chunk.new_lines;
        for (const lineNum of commentLineNumbers) {
            if ((lineNum >= chunk.old_start && lineNum < chunkOldEnd) ||
                (lineNum >= chunk.new_start && lineNum < chunkNewEnd)) {
                return true;
            }
        }
    }
    return false;
}

// Show a refresh indicator on the file header
function showRefreshIndicator(filePath, updatedFile) {
    const anchorId = 'file-' + filePath.replace(/[^a-zA-Z0-9]/g, '-');
    // Show on the new-pane header (right side, more visible)
    const fileSection = document.getElementById(`${anchorId}-new-pane`);
    if (!fileSection) return;

    const header = fileSection.querySelector('.file-header');
    if (!header) return;

    // Don't add duplicate indicators
    if (header.querySelector('.refresh-indicator')) return;

    const indicator = document.createElement('button');
    indicator.className = 'refresh-indicator';
    indicator.title = 'File changed on disk - click to refresh';
    indicator.innerHTML = '&#x21bb;'; // ↻ character
    indicator.addEventListener('click', async (e) => {
        e.stopPropagation();
        const pending = pendingFileUpdates.get(filePath);
        if (pending) {
            pendingFileUpdates.delete(filePath);
            applyFileUpdate(filePath, pending);
        }
    });

    header.appendChild(indicator);
}

// Remove the refresh indicator from a file header
function removeRefreshIndicator(filePath) {
    const anchorId = 'file-' + filePath.replace(/[^a-zA-Z0-9]/g, '-');
    const fileSection = document.getElementById(`${anchorId}-new-pane`);
    if (!fileSection) return;

    const indicator = fileSection.querySelector('.refresh-indicator');
    if (indicator) indicator.remove();
}

// Apply a file update to the DOM (re-render chunks)
function applyFileUpdate(filePath, updatedFile) {
    const preservedForms = preserveInProgressComments(filePath);

    const anchorId = 'file-' + filePath.replace(/[^a-zA-Z0-9]/g, '-');
    const oldFileSection = document.getElementById(`${anchorId}-old-pane`);
    const newFileSection = document.getElementById(`${anchorId}-new-pane`);

    if (!oldFileSection || !newFileSection) return;

    const oldContent = oldFileSection.querySelector('.file-content');
    const newContent = newFileSection.querySelector('.file-content');

    if (!oldContent || !newContent) return;

    oldContent.innerHTML = '';
    newContent.innerHTML = '';

    if (updatedFile.is_binary) {
        const binaryMsg = '<div class="binary-message">Binary file</div>';
        oldContent.innerHTML = binaryMsg;
        newContent.innerHTML = binaryMsg;
    } else {
        let sharedLineCounter = 0;
        (updatedFile.chunks || []).forEach(chunk => {
            sharedLineCounter = renderChunk(
                chunk,
                oldFileSection,
                newFileSection,
                updatedFile.path,
                sharedLineCounter
            );
        });
    }

    updateFileHeaderStats(newFileSection, updatedFile);
    removeRefreshIndicator(filePath);

    // Update the allFiles cache
    const idx = allFiles.findIndex(f => f.path === filePath);
    if (idx !== -1) {
        allFiles[idx] = updatedFile;
    }

    if (preservedForms && preservedForms.length > 0) {
        restoreInProgressComments(preservedForms);
    }

    console.log('File update applied:', filePath);
}

export async function refreshFile(filePath) {
    console.log('Refreshing file:', filePath);

    try {
        const updatedFile = await api.fetchFileDiff(filePath);

        if (!updatedFile) {
            console.warn(`File ${filePath} not found in updated diff`);
            return;
        }

        // Update the allFiles cache
        const idx = allFiles.findIndex(f => f.path === filePath);
        if (idx !== -1) {
            allFiles[idx] = updatedFile;
        }

        // In single mode, if this file isn't currently displayed, skip DOM update
        if (singleMode && selectedFilePath !== filePath) {
            console.log('File not currently displayed in single mode, cached update only:', filePath);
            return;
        }

        // Check if any open comments overlap with the changed lines
        const commentLineNumbers = getCommentLineNumbers(filePath);
        if (hasCommentOverlap(updatedFile, commentLineNumbers)) {
            // Store the pending update and show a refresh indicator
            pendingFileUpdates.set(filePath, updatedFile);
            showRefreshIndicator(filePath, updatedFile);
            console.log('File has comment overlap, showing refresh indicator:', filePath);
            return;
        }

        // No overlap — apply immediately
        applyFileUpdate(filePath, updatedFile);
    } catch (error) {
        console.error('Error refreshing file:', error);
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
