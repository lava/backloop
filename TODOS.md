# Git Viewer - Implementation Tasks

## Project Goals

Build a local web-based git diff viewer that replicates GitHub's PR review interface:
- **Side-by-side diff view** showing old code (left) and new code (right)  
- **Visual change highlighting** with red backgrounds for deletions, green for additions
- **Line-level commenting** by clicking on line numbers
- **Clean GitHub-style UI** with proper syntax highlighting
- **Works with mock data first** to nail the UI before integrating with real git

Key reference: GitHub's PR Files Changed tab interface (see screenshot.png)

## Current Tasks - Frontend First Approach

### Task 1: Create Side-by-Side Diff Viewer with Mock Data ✅
- [x] Create index.html with split-pane layout structure
- [x] Build mock diff data structure in JavaScript mimicking a real git diff
- [x] Implement dual-column rendering (old file | new file)
- [x] Add synchronized scrolling between left and right panes
- [x] Display file path header above each diff section
- [x] Add expand/collapse for file sections

### Task 2: GitHub-Style Diff Visualization ✅
- [x] Implement line numbering on both sides (old and new line numbers)
- [x] Add background colors: light red for deletions, light green for additions
- [x] Style unchanged context lines with gray line numbers
- [x] Add +/- indicators in the gutter
- [x] Implement proper alignment when lines are added/removed
- [x] Add line highlighting on hover

### Task 3: Comment System UI
- [ ] Make line numbers clickable to trigger comment mode
- [ ] Create comment form that appears inline when line is clicked
- [ ] Display existing comments inline with the diff
- [ ] Add comment counter badges on commented lines
- [ ] Implement comment collapse/expand
- [ ] Store comments in localStorage for persistence

## Upcoming Tasks (Backend Integration)

### Task 4: Mock Data Refinement
- [ ] Create comprehensive mock data covering edge cases
- [ ] Add support for multiple file diffs
- [ ] Include binary file indicators
- [ ] Add file rename detection display

### Task 5: API Design and Backend Connection
- [ ] Design REST API endpoints based on frontend needs
- [ ] Replace mock data with API calls
- [ ] Implement real git diff parsing
- [ ] Add WebSocket for real-time comment updates

### Task 6: Polish and Features
- [ ] Add syntax highlighting with Prism.js or highlight.js
- [ ] Implement file tree navigator
- [ ] Add search within diff
- [ ] Create CLI launcher that auto-opens browser
- [ ] Add keyboard shortcuts (j/k navigation, etc.)

## Technical Notes

**Mock Data Structure Example:**
```javascript
const mockDiff = {
  files: [{
    path: '.github/workflows/release.yaml',
    oldPath: '.github/workflows/release.yaml',
    additions: 2,
    deletions: 2,
    chunks: [{
      oldStart: 193,
      oldLines: 7,
      newStart: 193,
      newLines: 7,
      lines: [
        { type: 'context', oldNum: 193, newNum: 193, content: '    gh release create...' },
        { type: 'deletion', oldNum: 194, newNum: null, content: '      --title "$RELEASE_TITLE"' },
        { type: 'addition', oldNum: null, newNum: 194, content: '      --title "$RELEASE_TITLE"' },
        // ...
      ]
    }]
  }]
};
```

**Key UI Elements to Match:**
- File header with path and +/- stats
- Line numbers in gray
- Deletion lines with light red background (#ffeef0)
- Addition lines with light green background (#e6ffed)
- Plus icon button for adding comments
- Inline comment threads