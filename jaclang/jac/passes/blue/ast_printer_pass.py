"""Jac Blue pass for drawing AST."""
from typing import List, Optional

import jaclang.jac.absyntree as ast
from jaclang.jac.passes import Pass


class ASTPrinterPass(Pass):
    """Jac AST convertion to ascii tree."""

    SAVE_OUTPUT = False

    def before_pass(self) -> None:
        """Initialize pass."""
        self.__print_tree(self.ir)
        self.terminate()
        return super().before_pass()

    def __print_tree(
            self,
            root: ast.AstNode,
            marker: str = "+-- ",
            level_markers: Optional[List[str]] = None
    ) -> None:
        """Recursive function that prints the hierarchical structure of a tree.

        Parameters:
        - root: Node instance, possibly containing children Nodes
        - marker: String to print in front of each node  ("+- " by default)
        - level_markers: Internally used by recursion to indicate where to
                        print markers and connections (see explanations below)

        Note: This implementation is found in https://simonhessner.de/python-3-recursively-print-structured-tree-including-hierarchy-markers-using-depth-first-search/
        """
        if root is None:
            return

        empty_str = " " * len(marker)
        connection_str = "|" + empty_str[:-1]
        if not level_markers:
            level_markers = []
        level = len(level_markers)   # recursion level

        def mapper(draw: bool) -> str:
            return connection_str if draw else empty_str

        markers = "".join(map(mapper, level_markers[:-1]))
        markers += marker if level > 0 else ""
        if self.SAVE_OUTPUT:
            f = open(self.SAVE_OUTPUT, "a+")
            print(f"{markers}{root.__class__.__name__}", file=f)
            f.close()
        else:
            print(f"{markers}{root.__class__.__name__}")
        # After root has been printed, recurse down (depth-first) the child nodes.
        for i, child in enumerate(root.kid):
            # The last child will not need connection markers on the current level
            # (see example above)
            is_last = i == len(root.kid) - 1
            self.__print_tree(child, marker, [*level_markers, not is_last])
