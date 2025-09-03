// Comprehensive mock diff data structure covering edge cases and file types
const mockDiff = {
    files: [{
        path: '.github/workflows/ci.yml',
        oldPath: '.github/workflows/ci.yml',
        status: 'modified', // modified, added, deleted, renamed, copied
        additions: 15,
        deletions: 8,
        binary: false,
        chunks: [{
            oldStart: 1,
            oldLines: 25,
            newStart: 1,
            newLines: 32,
            lines: [
                { type: 'context', oldNum: 1, newNum: 1, content: 'name: CI' },
                { type: 'context', oldNum: 2, newNum: 2, content: '' },
                { type: 'context', oldNum: 3, newNum: 3, content: 'on:' },
                { type: 'context', oldNum: 4, newNum: 4, content: '  push:' },
                { type: 'context', oldNum: 5, newNum: 5, content: '    branches: [ main ]' },
                { type: 'context', oldNum: 6, newNum: 6, content: '  pull_request:' },
                { type: 'context', oldNum: 7, newNum: 7, content: '    branches: [ main ]' },
                { type: 'context', oldNum: 8, newNum: 8, content: '' },
                { type: 'context', oldNum: 9, newNum: 9, content: 'jobs:' },
                { type: 'context', oldNum: 10, newNum: 10, content: '  test:' },
                { type: 'context', oldNum: 11, newNum: 11, content: '    runs-on: ubuntu-latest' },
                { type: 'addition', oldNum: null, newNum: 12, content: '    strategy:' },
                { type: 'addition', oldNum: null, newNum: 13, content: '      matrix:' },
                { type: 'addition', oldNum: null, newNum: 14, content: '        python-version: [3.8, 3.9, "3.10", "3.11"]' },
                { type: 'context', oldNum: 12, newNum: 15, content: '    steps:' },
                { type: 'context', oldNum: 13, newNum: 16, content: '    - uses: actions/checkout@v3' },
                { type: 'deletion', oldNum: 14, newNum: null, content: '    - name: Set up Python 3.9' },
                { type: 'addition', oldNum: null, newNum: 17, content: '    - name: Set up Python ${{ matrix.python-version }}' },
                { type: 'context', oldNum: 15, newNum: 18, content: '      uses: actions/setup-python@v3' },
                { type: 'context', oldNum: 16, newNum: 19, content: '      with:' },
                { type: 'deletion', oldNum: 17, newNum: null, content: '        python-version: 3.9' },
                { type: 'addition', oldNum: null, newNum: 20, content: '        python-version: ${{ matrix.python-version }}' },
                { type: 'context', oldNum: 18, newNum: 21, content: '    - name: Install dependencies' },
                { type: 'context', oldNum: 19, newNum: 22, content: '      run: |' },
                { type: 'context', oldNum: 20, newNum: 23, content: '        python -m pip install --upgrade pip' },
                { type: 'deletion', oldNum: 21, newNum: null, content: '        pip install -r requirements.txt' },
                { type: 'addition', oldNum: null, newNum: 24, content: '        pip install -e .' },
                { type: 'addition', oldNum: null, newNum: 25, content: '        pip install pytest pytest-cov' },
                { type: 'context', oldNum: 22, newNum: 26, content: '    - name: Run tests' },
                { type: 'deletion', oldNum: 23, newNum: null, content: '      run: pytest' },
                { type: 'addition', oldNum: null, newNum: 27, content: '      run: pytest --cov=src --cov-report=xml' },
                { type: 'addition', oldNum: null, newNum: 28, content: '    - name: Upload coverage to Codecov' },
                { type: 'addition', oldNum: null, newNum: 29, content: '      uses: codecov/codecov-action@v3' },
                { type: 'addition', oldNum: null, newNum: 30, content: '      with:' },
                { type: 'addition', oldNum: null, newNum: 31, content: '        file: ./coverage.xml' },
                { type: 'context', oldNum: 24, newNum: 32, content: '' }
            ]
        }]
    }]
};

export default mockDiff;