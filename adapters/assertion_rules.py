"""
Shared helpers for extracting CIR assertions from C/C++ style test bodies.
Used by the gtest / unity / cpputest / bosch adapters to avoid duplication.
"""

from __future__ import annotations

import re
from typing import List

from adapters.cir import CIRAssertion, AssertionType


def body_after(content: str, pos: int) -> str:
    """Return the brace-balanced `{...}` block starting at/after `pos` (empty if none)."""
    brace = content.find("{", pos)
    if brace == -1:
        return ""
    depth, i = 1, brace + 1
    n = len(content)
    while i < n and depth:
        c = content[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return content[brace:i]


def find_balanced_blocks(content: str, header_re: re.Pattern) -> List[tuple]:
    """
    Return list of (name, body) for each test whose declaration matches
    `header_re` (must expose a 'name' group). Single-pass, O(n) over the file.
    """
    out = []
    for m in header_re.finditer(content):
        name = m.groupdict().get("name", "test")
        body = body_after(content, m.end() - 1)
        if body:
            out.append((name, body))
    return out


# (regex, assertion type, expected-group, actual-group)
_GTEST_RULES = [
    (r"EXPECT_EQ\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.EQUAL, 1, 2),
    (r"ASSERT_EQ\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.EQUAL, 1, 2),
    (r"EXPECT_NE\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.NOT_EQUAL, 1, 2),
    (r"EXPECT_STREQ\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.STRING_EQUAL, 1, 2),
    (r"EXPECT_NEAR\s*\(\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.NEAR, 1, 2),
    (r"EXPECT_GT\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.GREATER, 2, 1),
    (r"EXPECT_GE\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.GREATER_EQUAL, 2, 1),
    (r"EXPECT_LT\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.LESS, 2, 1),
    (r"EXPECT_LE\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.LESS_EQUAL, 2, 1),
    (r"EXPECT_TRUE\s*\(\s*([^;]+?)\s*\)", AssertionType.TRUE, None, 1),
    (r"EXPECT_FALSE\s*\(\s*([^;]+?)\s*\)", AssertionType.FALSE, None, 1),
    (r"EXPECT_THROW\s*\(", AssertionType.THROWS, None, None),
    (r"EXPECT_CALL\s*\(", AssertionType.CALLED, None, None),
]

_UNITY_RULES = [
    (r"TEST_ASSERT_EQUAL(?:_INT|_UINT|_HEX)?\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.EQUAL, 1, 2),
    (r"TEST_ASSERT_EQUAL_FLOAT\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.NEAR, 1, 2),
    (r"TEST_ASSERT_EQUAL_STRING\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.STRING_EQUAL, 1, 2),
    (r"TEST_ASSERT_NOT_EQUAL\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.NOT_EQUAL, 1, 2),
    (r"TEST_ASSERT_TRUE\s*\(\s*([^;]+?)\s*\)", AssertionType.TRUE, None, 1),
    (r"TEST_ASSERT_FALSE\s*\(\s*([^;]+?)\s*\)", AssertionType.FALSE, None, 1),
    (r"TEST_ASSERT_NULL\s*\(\s*([^;]+?)\s*\)", AssertionType.NULL, None, 1),
    (r"TEST_ASSERT_NOT_NULL\s*\(\s*([^;]+?)\s*\)", AssertionType.NOT_NULL, None, 1),
    (r"TEST_ASSERT_GREATER_THAN\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.GREATER, 1, 2),
]

_CPPUTEST_RULES = [
    (r"CHECK_EQUAL\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.EQUAL, 1, 2),
    (r"LONGS_EQUAL\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.EQUAL, 1, 2),
    (r"DOUBLES_EQUAL\s*\(\s*([^,]+?)\s*,\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.NEAR, 1, 2),
    (r"STRCMP_EQUAL\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.STRING_EQUAL, 1, 2),
    (r"CHECK_TRUE\s*\(\s*([^;]+?)\s*\)", AssertionType.TRUE, None, 1),
    (r"CHECK_FALSE\s*\(\s*([^;]+?)\s*\)", AssertionType.FALSE, None, 1),
    (r"CHECK\s*\(\s*([^;]+?)\s*\)", AssertionType.TRUE, None, 1),
    (r"POINTERS_EQUAL\s*\(\s*([^,]+?)\s*,\s*([^;]+?)\s*\)", AssertionType.EQUAL, 1, 2),
    (r"mock\(\)\.expectOneCall", AssertionType.CALLED, None, None),
]


def extract_assertions(body: str, ruleset: str = "gtest") -> List[CIRAssertion]:
    rules = {
        "gtest": _GTEST_RULES,
        "unity": _UNITY_RULES,
        "cpputest": _CPPUTEST_RULES,
        "bosch": _GTEST_RULES + _UNITY_RULES,  # BOSCH custom macros often mix styles
    }.get(ruleset, _GTEST_RULES)

    found: List[CIRAssertion] = []
    for pattern, atype, exp_g, act_g in rules:
        for m in re.finditer(pattern, body):
            exp = m.group(exp_g).strip() if exp_g and m.lastindex and exp_g <= m.lastindex else None
            act = m.group(act_g).strip() if act_g and m.lastindex and act_g <= m.lastindex else None
            found.append(CIRAssertion(type=atype, expected=exp, actual=act, raw=m.group(0).strip()))
    return found
