#!/usr/bin/env python3
"""Range-aware include span merging and upstream fragment rebuilding tests for agents_bundle."""
import unittest

from tests.helpers import AgentsBundleTestCase


class TestIncludes(AgentsBundleTestCase):
    def _span(self, mod, key, start, end, chain=()):
        lines = {n: f"l{n}" for n in range(start, end + 1)} if start is not None else {}
        whole = "whole" if start is None else None
        return mod.IncludeSpan(key, "f.txt", start, end, lines, list(chain), whole_text=whole)

    def test_slice_merge_and_whole_file_absorption(self):
        mod = self._load_bundle_module()
        with self.subTest(case="overlapping and contained slices merge"):
            merged = mod.merge_spans(
                [self._span(mod, "a", 2, 4), self._span(mod, "a", 3, 6), self._span(mod, "a", 3, 4)]
            )
            self.assertEqual(len(merged), 1)
            meta, text = mod.render_span(merged[0])
            self.assertEqual(meta["name"], "f.txt:2-6")
            self.assertEqual(text, "===== $ sed -n '2,6p' f.txt =====\nl2\nl3\nl4\nl5\nl6")
        with self.subTest(case="disjoint slices and other files stay separate"):
            merged = mod.merge_spans(
                [self._span(mod, "a", 1, 2), self._span(mod, "a", 5, 6), self._span(mod, "b", 1, 2)]
            )
            self.assertEqual([(s.key, s.start, s.end) for s in merged], [("a", 1, 2), ("a", 5, 6), ("b", 1, 2)])
        with self.subTest(case="bridging slice joins two slices"):
            merged = mod.merge_spans(
                [self._span(mod, "a", 1, 2), self._span(mod, "a", 5, 6), self._span(mod, "a", 2, 5)]
            )
            self.assertEqual([(s.start, s.end) for s in merged], [(1, 6)])
            self.assertEqual(sorted(merged[0].lines), [1, 2, 3, 4, 5, 6])
        with self.subTest(case="whole file absorbs slices in either order"):
            for order in ([(2, 3), None], [None, (2, 3)]):
                spans = [self._span(mod, "a", *(rng or (None, None))) for rng in order]
                merged = mod.merge_spans(spans)
                self.assertEqual(len(merged), 1)
                self.assertIsNotNone(merged[0].whole_text)
                self.assertEqual(mod.render_span(merged[0])[0]["name"], "f.txt")

    def test_span_from_upstream_fragment(self):
        mod = self._load_bundle_module()
        key = str((self.tmp / "big.txt").resolve())
        sliced = mod.span_from_fragment(
            {"kind": "file", "name": "big.txt:2-3", "chain": ["todo_md"]},
            "===== $ sed -n '2,3p' big.txt =====\nline2\nline3",
            self.tmp,
        )
        self.assertEqual((sliced.key, sliced.start, sliced.end), (key, 2, 3))
        self.assertEqual(sliced.lines, {2: "line2", 3: "line3"})
        self.assertEqual(sliced.chain, ["todo_md"])
        whole = mod.span_from_fragment(
            {"kind": "file", "name": "big.txt", "chain": []},
            "===== $ cat big.txt =====\nline1\nline2",
            self.tmp,
        )
        self.assertEqual((whole.key, whole.start, whole.whole_text), (key, None, "line1\nline2"))
        explicit = mod.span_from_fragment(
            {"kind": "file", "name": "x", "resolved_path": "/abs/x.txt"},
            "===== $ cat x =====\nbody",
            self.tmp,
        )
        self.assertEqual(explicit.key, "/abs/x.txt")


if __name__ == "__main__":
    unittest.main()
