import itertools
import unittest
from decimal import Decimal
from fractions import Fraction

from unscored import InputError, audit


def suite(cases=None, systems=None):
    return {
        "version": 1,
        "name": "A declared comparison",
        "systems": systems if systems is not None else ["A", "B"],
        "cases": cases if cases is not None else [{"id": "x"}],
    }


def scored(system, case_id, score):
    return {"system": system, "case_id": case_id, "status": "scored", "score": score}


class AuditTests(unittest.TestCase):
    def test_empty_results_and_exact_report_contract(self):
        report = audit(suite(), [])
        self.assertEqual(set(report), {
            "schema_version", "name", "system_ids", "summary", "systems", "cases",
            "completion_witnesses", "rerun_plan",
        })
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["system_ids"], ["A", "B"])
        self.assertEqual(report["summary"], {
            "verdict": "inconclusive", "winner": None, "case_count": 1,
            "total_weight": "1", "margin": {"lower": "-1", "upper": "1"},
        })
        self.assertEqual(report["systems"], [{
            "id": system, "scored": 0, "missing": 1, "error": 0, "unscored": 0,
            "coverage": "0", "observed_mean": None, "lower": "0", "upper": "1",
            "scored_weight": "0", "unresolved_weight": "1",
        } for system in ["A", "B"]])
        self.assertEqual(report["cases"], [{
            "id": "x", "group": "all", "weight": "1",
            "a": {"status": "missing", "score": None},
            "b": {"status": "missing", "score": None}, "uncertainty": "2",
        }])
        self.assertEqual(report["completion_witnesses"][0], {
            "favored": "A", "hypothetical": True, "scores": {"A": "1", "B": "0"},
            "margin": "1", "winner": "A", "assignments": [
                {"system": "A", "case_id": "x", "score": 1},
                {"system": "B", "case_id": "x", "score": 0},
            ],
        })
        self.assertEqual(report["rerun_plan"], [{
            "system": system, "case_id": "x", "status": "missing", "weight": "1",
            "interval_reduction": "1",
        } for system in ["A", "B"]])

    def test_weighted_bounds_and_diagnostic_mean(self):
        report = audit(suite([{"id": "x", "weight": 2}, {"id": "y"}]), [
            scored("A", "x", 1), scored("B", "x", 0), scored("B", "y", 1),
        ])
        self.assertEqual(report["summary"], {
            "verdict": "a_wins", "winner": "A", "case_count": 2,
            "total_weight": "3", "margin": {"lower": "1/3", "upper": "2/3"},
        })
        self.assertEqual(report["systems"][0], {
            "id": "A", "scored": 1, "missing": 1, "error": 0, "unscored": 0,
            "coverage": "2/3", "observed_mean": "1", "lower": "2/3", "upper": "1",
            "scored_weight": "2", "unresolved_weight": "1",
        })

    def test_observed_only_ranking_cannot_certify_winner(self):
        report = audit(suite([{"id": "x"}, {"id": "y", "weight": 9}]), [
            scored("A", "x", 1), scored("B", "x", 0.2), scored("B", "y", 0.2),
        ])
        self.assertEqual(report["systems"][0]["observed_mean"], "1")
        self.assertEqual(report["systems"][0]["lower"], "1/10")
        self.assertEqual(report["summary"]["verdict"], "inconclusive")
        self.assertEqual([w["winner"] for w in report["completion_witnesses"]], ["A", "B"])

    def test_exact_tie_and_strict_endpoint_ties(self):
        report = audit(suite(), [scored("A", "x", Decimal("0.1")), scored("B", "x", 0.1)])
        self.assertEqual(report["summary"]["verdict"], "tie")
        self.assertIsNone(report["summary"]["winner"])
        self.assertEqual(report["summary"]["margin"], {"lower": "0", "upper": "0"})
        for witness in report["completion_witnesses"]:
            self.assertEqual(witness["assignments"], [])
            self.assertIsNone(witness["winner"])
        for system, value in [("A", 0), ("A", 1), ("B", 0), ("B", 1)]:
            with self.subTest(system=system, value=value):
                boundary = audit(suite(), [scored(system, "x", value)])
                self.assertEqual(boundary["summary"]["verdict"], "inconclusive")
                self.assertIn(None, [w["winner"] for w in boundary["completion_witnesses"]])

    def test_second_declared_system_wins(self):
        report = audit(suite(systems=["Z", "Alpha"]), [
            scored("Z", "x", 0), scored("Alpha", "x", 1),
        ])
        self.assertEqual(report["system_ids"], ["Z", "Alpha"])
        self.assertEqual(report["summary"]["verdict"], "b_wins")
        self.assertEqual(report["summary"]["winner"], "Alpha")

    def test_decimal_weights_scores_and_float_interpretation(self):
        report = audit(suite([{"id": "x", "weight": Decimal("0.1")},
                              {"id": "y", "weight": 0.2}]), [
            scored("A", "x", 0.1), scored("A", "y", Decimal("0.3")),
        ])
        self.assertEqual(report["summary"]["total_weight"], "3/10")
        self.assertEqual(report["systems"][0]["lower"], "7/30")
        self.assertEqual(report["cases"][0]["a"]["score"], "1/10")

    def test_unknown_statuses_and_queue_order(self):
        manifest = suite([{"id": "z", "weight": 1}, {"id": "b", "weight": 3},
                          {"id": "a", "weight": 3, "group": "logic"}], ["Z", "Alpha"])
        rows = [{"system": "Z", "case_id": "a", "status": "error"},
                {"system": "Alpha", "case_id": "b", "status": "unscored"}]
        report = audit(manifest, rows)
        self.assertEqual([c["id"] for c in report["cases"]], ["a", "b", "z"])
        self.assertEqual([(r["case_id"], r["system"]) for r in report["rerun_plan"]],
                         [(case, system) for case in ["a", "b", "z"] for system in ["Alpha", "Z"]])
        self.assertEqual(report["rerun_plan"][0]["interval_reduction"], "3/7")
        self.assertEqual(report["cases"][0]["uncertainty"], "6/7")
        self.assertEqual(report["systems"][0]["error"], 1)
        self.assertEqual(report["systems"][0]["missing"], 2)
        self.assertEqual(report["systems"][1]["unscored"], 1)
        self.assertEqual(audit(manifest, list(reversed(rows))), report)

    def test_api_does_not_modify_inputs(self):
        manifest = suite()
        rows = [scored("A", "x", 0.5)]
        before = repr((manifest, rows))
        audit(manifest, rows)
        self.assertEqual(repr((manifest, rows)), before)

    def test_measuring_any_unknown_cell_reduces_width_by_its_weight(self):
        manifest = suite([{"id": "x", "weight": 2}, {"id": "y", "weight": 3}])
        report = audit(manifest, [])
        before = Fraction(report["summary"]["margin"]["upper"]) - Fraction(report["summary"]["margin"]["lower"])
        for item in report["rerun_plan"]:
            for score in [0, Decimal("0.5"), 1]:
                measured = audit(manifest, [scored(item["system"], item["case_id"], score)])
                after = Fraction(measured["summary"]["margin"]["upper"]) - Fraction(measured["summary"]["margin"]["lower"])
                self.assertEqual(before - after, Fraction(item["interval_reduction"]))

    def test_exhaustive_independent_completion_oracle(self):
        # Four cells, each either unresolved or observed as 0, 1/2, or 1.
        weights = {"x": Fraction(1, 10), "y": Fraction(3, 10)}
        manifest = suite([{"id": "x", "weight": Decimal("0.1")},
                          {"id": "y", "weight": Decimal("0.3")}])
        cells = list(itertools.product(["A", "B"], ["x", "y"]))
        total_weight = sum(weights.values())
        for values in itertools.product([None, 0, Decimal("0.5"), 1], repeat=4):
            with self.subTest(values=values):
                observed = {cell: Fraction(value) for cell, value in zip(cells, values) if value is not None}
                unresolved = [cell for cell in cells if cell not in observed]
                rows = [scored(*cell, value) for cell, value in zip(cells, values) if value is not None]
                report = audit(manifest, rows)
                completions = []
                for bits in itertools.product([0, 1], repeat=len(unresolved)):
                    completed = dict(observed)
                    completed.update(zip(unresolved, bits))
                    scores = {system: sum(weights[case] * completed[system, case] for case in weights) / total_weight
                              for system in ["A", "B"]}
                    completions.append(scores)
                margins = [scores["A"] - scores["B"] for scores in completions]
                self.assertEqual(Fraction(report["summary"]["margin"]["lower"]), min(margins))
                self.assertEqual(Fraction(report["summary"]["margin"]["upper"]), max(margins))
                verdict = "a_wins" if all(m > 0 for m in margins) else "b_wins" if all(m < 0 for m in margins) else "tie" if all(m == 0 for m in margins) else "inconclusive"
                self.assertEqual(report["summary"]["verdict"], verdict)
                for system_report in report["systems"]:
                    scores = [c[system_report["id"]] for c in completions]
                    self.assertEqual(Fraction(system_report["lower"]), min(scores))
                    self.assertEqual(Fraction(system_report["upper"]), max(scores))
                for witness in report["completion_witnesses"]:
                    self.assertIs(witness["hypothetical"], True)
                    completed = dict(observed)
                    assigned = set()
                    for assignment in witness["assignments"]:
                        cell = assignment["system"], assignment["case_id"]
                        self.assertNotIn(cell, observed)
                        self.assertNotIn(cell, assigned)
                        self.assertIs(type(assignment["score"]), int)
                        completed[cell] = assignment["score"]
                        assigned.add(cell)
                    self.assertEqual(assigned, set(unresolved))
                    self.assertTrue(all(completed[cell] == score for cell, score in observed.items()))
                    scores = {system: sum(weights[case] * completed[system, case] for case in weights) / total_weight
                              for system in ["A", "B"]}
                    self.assertEqual(witness["scores"], {key: str(value) for key, value in scores.items()})
                    margin = scores["A"] - scores["B"]
                    self.assertEqual(Fraction(witness["margin"]), margin)
                    self.assertEqual(margin, max(margins) if witness["favored"] == "A" else min(margins))
                    self.assertEqual(witness["winner"], "A" if margin > 0 else "B" if margin < 0 else None)


class ValidationTests(unittest.TestCase):
    def assert_bad(self, manifest=None, rows=None):
        with self.assertRaises(InputError):
            audit(suite() if manifest is None else manifest, [] if rows is None else rows)

    def test_suite_structure_and_unknown_fields(self):
        for manifest in [[], "suite", {}, {**suite(), "extra": 1},
                         {**suite(), "version": True}, {**suite(), "version": 1.0},
                         {**suite(), "version": Decimal(1)}, {**suite(), "version": 2},
                         {**suite(), "cases": []}, {**suite(), "cases": {}},
                         {**suite(), "systems": ["A"]}, {**suite(), "systems": ["A", "B", "C"]},
                         {**suite(), "systems": ["A", "A"]}, {**suite(), "systems": "AB"}]:
            with self.subTest(manifest=manifest):
                self.assert_bad(manifest)

    def test_identifiers_and_names(self):
        for bad in ["", "   ", 1, None, "x" * 201, "bad\nname", "bad\x7fname", "bad\x85name", "\ud800"]:
            with self.subTest(value=bad):
                self.assert_bad({**suite(), "name": bad})
                self.assert_bad(suite(systems=["A", bad]))
                self.assert_bad(suite([{"id": bad}]))
                self.assert_bad(suite([{"id": "x", "group": bad}]))

    def test_cases_reject_duplicate_ids_missing_ids_and_unknown_keys(self):
        for cases in [[{"id": "x"}, {"id": "x"}], [{}], ["x"],
                      [{"id": "x", "weights": 1}]]:
            with self.subTest(cases=cases):
                self.assert_bad(suite(cases))

    def test_invalid_weights_and_numeric_resource_bounds(self):
        for weight in [0, -1, True, "1", None, float("nan"), float("inf"),
                       Decimal("NaN"), Decimal("Infinity"), Decimal("sNaN"),
                       Fraction(1, 2), 10**100, Decimal("1e101"), Decimal("1e-101"),
                       Decimal("0e1000000"), Decimal("1." + "1" * 100)]:
            with self.subTest(weight=weight):
                self.assert_bad(suite([{"id": "x", "weight": weight}]))
        for weight in [10**99, Decimal("1e100"), Decimal("1e-100")]:
            self.assertEqual(audit(suite([{"id": "x", "weight": weight}]), [])["summary"]["case_count"], 1)

    def test_case_count_limit(self):
        from unittest.mock import patch
        with patch("unscored.core.MAX_CASES", 1):
            self.assert_bad(suite([{"id": "x"}, {"id": "y"}]))

    def test_invalid_results_and_scores(self):
        for rows in [{}, "rows", [None], [[]], [{}],
                     [scored("unknown", "x", 0)], [scored("A", "unknown", 0)],
                     [{**scored("A", "x", 0), "extra": 1}],
                     [{"system": "A", "case_id": "x", "status": "missing"}],
                     [{"system": "A", "case_id": "x", "status": []}],
                     [{"system": "A", "case_id": "x", "status": "scored"}],
                     [{"system": "A", "case_id": "x", "status": "error", "score": None}],
                     [{"system": "A", "case_id": "x", "status": "unscored", "score": 0}]]:
            with self.subTest(rows=rows):
                self.assert_bad(rows=rows)
        for score in [-0.01, 1.01, True, "0.5", None, float("nan"), float("inf"), Decimal("NaN")]:
            with self.subTest(score=score):
                self.assert_bad(rows=[scored("A", "x", score)])

    def test_duplicate_pairs_rejected_even_when_status_changes(self):
        for second in [scored("A", "x", 1), {"system": "A", "case_id": "x", "status": "error"}]:
            self.assert_bad(rows=[scored("A", "x", 0), second])


if __name__ == "__main__":
    unittest.main()
