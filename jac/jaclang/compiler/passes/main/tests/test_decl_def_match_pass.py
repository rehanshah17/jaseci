"""Test pass module."""

import jaclang.compiler.absyntree as ast
from jaclang.compiler.compile import jac_file_to_pass
from jaclang.compiler.passes.main import DeclImplMatchPass
from jaclang.utils.test import TestCase


class DeclImplMatchPassTests(TestCase):
    """Test pass module."""

    def setUp(self) -> None:
        """Set up test."""
        return super().setUp()

    def test_parameter_count_mismatch(self) -> None:
        """Basic test for pass."""
        state = jac_file_to_pass(
            self.fixture_abs_path("defn_decl_mismatch.jac"), DeclImplMatchPass
        )

        expected_stdout_values = (
            "Parameter count mismatch for ability (o)SomeObj.(c)foo.",
            "    8 |",
            "    9 | # Miss match parameter count.",
            "   10 | :obj:SomeObj:can:foo(param1: str) -> str {",
            "      | ^^^^^^^^^^^^^^^^^^^^",
            '   11 |     return "foo";',
            "   12 | }",
            "From the declaration of foo.",
            "    2 |",
            "    3 | obj SomeObj {",
            "    4 |     can foo(param1: str, param2:int) -> str;",
            "      |         ^^^",
            "    5 |     can bar(param1: str, param2:int) -> str;",
            "    6 | }",
        )

        errors_output = ""
        for error in state.errors_had:
            errors_output += error.pretty_print() + "\n"

        for exp in expected_stdout_values:
            self.assertIn(exp, errors_output)

    def test_ability_connected_to_decl(self) -> None:
        """Basic test for pass."""
        state = jac_file_to_pass(self.fixture_abs_path("base.jac"), DeclImplMatchPass)
        self.assertFalse(state.errors_had)
        self.assertIn("(o)Test.(c)say_hi", state.ir.sym_tab.tab)
        self.assertIsNotNone(
            state.ir.sym_tab.tab["(o)Test.(c)say_hi"].decl.name_of.body
        )
        self.assertIn("(o)Test.(c)__init__", state.ir.sym_tab.tab)
        self.assertIsNotNone(
            state.ir.sym_tab.tab["(o)Test.(c)__init__"].decl.name_of.body
        )

    def test_ability_connected_to_decl_post(self) -> None:
        """Basic test for pass."""
        state = jac_file_to_pass(self.fixture_abs_path("base2.jac"), DeclImplMatchPass)
        self.assertFalse(state.errors_had)
        self.assertIn("(o)Test.(c)say_hi", state.ir.sym_tab.tab)
        self.assertIsNotNone(
            state.ir.sym_tab.tab["(o)Test.(c)say_hi"].decl.name_of.body
        )
        self.assertIn("(o)Test.(c)__init__", state.ir.sym_tab.tab)
        self.assertIsNotNone(
            state.ir.sym_tab.tab["(o)Test.(c)__init__"].decl.name_of.body
        )

    def test_arch_ref_has_sym(self) -> None:
        """Basic test for pass."""
        state = jac_file_to_pass(
            self.fixture_abs_path("defs_and_uses.jac"), DeclImplMatchPass
        )
        for i in state.ir.get_all_sub_nodes(ast.ArchRef):
            self.assertIsNotNone(i.sym)
