"""Pin the suite's imports to the tree under test.

pytest's default ``prepend`` import mode leaves the invocation's working
directory at the front of ``sys.path``. When pytest is invoked from a different
checkout -- the main clone or another linked worktree that hosts the run -- and
is pointed at test files inside the tree under test, a top-level
``import scripts...`` or ``import mcp...`` then resolves from the hosting tree.
The two trees can hold different revisions, so the verdict belongs to the wrong
tree. Inserting the tree root at the front of ``sys.path`` makes the tree under
test win regardless of the invocation's working directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

TREE_ROOT = str(Path(__file__).resolve().parents[2])

if TREE_ROOT in sys.path:
    sys.path.remove(TREE_ROOT)
sys.path.insert(0, TREE_ROOT)
