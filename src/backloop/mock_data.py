"""Mock data for testing and demonstration purposes."""

from backloop.models import GitDiff, DiffFile, DiffChunk, DiffLine, LineType


def get_mock_diff() -> GitDiff:
    """Get mock diff data for testing and demonstration purposes."""

    # Create mock diff data
    mock_lines = [
        DiffLine(type=LineType.CONTEXT, oldNum=1, newNum=1, content="name: CI"),
        DiffLine(type=LineType.CONTEXT, oldNum=2, newNum=2, content=""),
        DiffLine(type=LineType.CONTEXT, oldNum=3, newNum=3, content="on:"),
        DiffLine(type=LineType.CONTEXT, oldNum=4, newNum=4, content="  push:"),
        DiffLine(
            type=LineType.CONTEXT, oldNum=5, newNum=5, content="    branches: [ main ]"
        ),
        DiffLine(type=LineType.CONTEXT, oldNum=6, newNum=6, content="  pull_request:"),
        DiffLine(
            type=LineType.CONTEXT, oldNum=7, newNum=7, content="    branches: [ main ]"
        ),
        DiffLine(type=LineType.CONTEXT, oldNum=8, newNum=8, content=""),
        DiffLine(type=LineType.CONTEXT, oldNum=9, newNum=9, content="jobs:"),
        DiffLine(type=LineType.CONTEXT, oldNum=10, newNum=10, content="  test:"),
        DiffLine(
            type=LineType.CONTEXT,
            oldNum=11,
            newNum=11,
            content="    runs-on: ubuntu-latest",
        ),
        DiffLine(
            type=LineType.ADDITION, oldNum=None, newNum=12, content="    strategy:"
        ),
        DiffLine(
            type=LineType.ADDITION, oldNum=None, newNum=13, content="      matrix:"
        ),
        DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=14,
            content='        python-version: [3.8, 3.9, "3.10", "3.11"]',
        ),
        DiffLine(type=LineType.CONTEXT, oldNum=12, newNum=15, content="    steps:"),
        DiffLine(
            type=LineType.CONTEXT,
            oldNum=13,
            newNum=16,
            content="    - uses: actions/checkout@v3",
        ),
        DiffLine(
            type=LineType.DELETION,
            oldNum=14,
            newNum=None,
            content="    - name: Set up Python 3.9",
        ),
        DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=17,
            content="    - name: Set up Python ${{ matrix.python-version }}",
        ),
        DiffLine(
            type=LineType.CONTEXT,
            oldNum=15,
            newNum=18,
            content="      uses: actions/setup-python@v3",
        ),
        DiffLine(type=LineType.CONTEXT, oldNum=16, newNum=19, content="      with:"),
        DiffLine(
            type=LineType.DELETION,
            oldNum=17,
            newNum=None,
            content="        python-version: 3.9",
        ),
        DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=20,
            content="        python-version: ${{ matrix.python-version }}",
        ),
        DiffLine(
            type=LineType.CONTEXT,
            oldNum=18,
            newNum=21,
            content="    - name: Install dependencies",
        ),
        DiffLine(type=LineType.CONTEXT, oldNum=19, newNum=22, content="      run: |"),
        DiffLine(
            type=LineType.CONTEXT,
            oldNum=20,
            newNum=23,
            content="        python -m pip install --upgrade pip",
        ),
        DiffLine(
            type=LineType.DELETION,
            oldNum=21,
            newNum=None,
            content="        pip install -r requirements.txt",
        ),
        DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=24,
            content="        pip install -e .",
        ),
        DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=25,
            content="        pip install pytest pytest-cov",
        ),
        DiffLine(
            type=LineType.CONTEXT, oldNum=22, newNum=26, content="    - name: Run tests"
        ),
        DiffLine(
            type=LineType.DELETION, oldNum=23, newNum=None, content="      run: pytest"
        ),
        DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=27,
            content="      run: pytest --cov=src --cov-report=xml",
        ),
        DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=28,
            content="    - name: Upload coverage to Codecov",
        ),
        DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=29,
            content="      uses: codecov/codecov-action@v3",
        ),
        DiffLine(type=LineType.ADDITION, oldNum=None, newNum=30, content="      with:"),
        DiffLine(
            type=LineType.ADDITION,
            oldNum=None,
            newNum=31,
            content="        file: ./coverage.xml",
        ),
        DiffLine(type=LineType.CONTEXT, oldNum=24, newNum=32, content=""),
    ]

    mock_chunk = DiffChunk(
        old_start=1, old_lines=25, new_start=1, new_lines=32, lines=mock_lines
    )

    mock_file = DiffFile(
        path=".github/workflows/ci.yml",
        old_path=".github/workflows/ci.yml",
        status="modified",
        additions=15,
        deletions=8,
        is_binary=False,
        chunks=[mock_chunk],
    )

    return GitDiff(files=[mock_file])
