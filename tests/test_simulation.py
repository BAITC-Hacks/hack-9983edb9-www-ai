"""Regression tests for the committed dataset (external brief not supplied).

Demo: M2 city-wide, M7 + M8 in Nura, M10 in Baikonur, M12 city-wide.
Cost 92, remaining 8; score 52.55768 -> 56.4641375 (+3.9064575).
Expected numbers below are independently worked examples, not engine output.
Run: python -m unittest discover -s tests -v
"""

from copy import deepcopy
from itertools import permutations
import unittest
from unittest.mock import patch

from backend import data, simulation


def plan(*items):
    """Use strings for city measures and (measure, district) for local ones."""
    return [
        {"measure_id": item} if isinstance(item, str)
        else {"measure_id": item[0], "district": item[1]}
        for item in items
    ]


def demo():
    return plan("M2", ("M7", "Nura"), ("M8", "Nura"),
                ("M10", "Baikonur"), "M12")


class SimulationTests(unittest.TestCase):
    def assertInvalid(self, selections, message):
        result = simulation.validate_scenario(selections)
        self.assertFalse(result["valid"])
        self.assertTrue(any(message in error for error in result["errors"]), result)
        return result

    def test_dataset_integrity(self):
        self.assertEqual(data.SIMULATION_HORIZON, 8)
        self.assertEqual(data.BUDGET, 100)
        self.assertEqual(data.REQUIRED_DECISIONS, 5)
        self.assertEqual(len(data.DISTRICTS), 5)
        self.assertEqual(len(data.MEASURES), 14)
        self.assertAlmostEqual(sum(data.INDICATOR_WEIGHTS.values()), 1)
        self.assertAlmostEqual(sum(d["population_share"] for d in data.DISTRICTS.values()), 1)
        for district in data.DISTRICTS.values():
            self.assertEqual(set(district["indicators"]), set(data.INDICATOR_WEIGHTS))
            self.assertTrue(all(0 <= v <= 100 for v in district["indicators"].values()))
        for measure in data.MEASURES.values():
            self.assertTrue(set(measure["effects"]) <= set(data.INDICATOR_WEIGHTS))
            self.assertGreater(measure["cost"], 0)
            self.assertTrue(0 <= measure["lag"] <= 8)

    def test_baseline_hand_calculation(self):
        result = simulation.calculate_baseline()
        # Weighted sums: Esil=62.99, Almaty=57.06, Saryarka=54.65,
        # Baikonur=56.63, Nura=49.18. Population-weighted mean=56.8624.
        expected = {"Esil": 62.99, "Almaty": 57.06, "Saryarka": 54.65,
                    "Baikonur": 56.63, "Nura": 49.18}
        for district, score in expected.items():
            self.assertAlmostEqual(result["district_scores"][district], score)
        self.assertAlmostEqual(result["D_avg"], 56.8624)
        self.assertAlmostEqual(result["min_D"], 49.18)
        self.assertEqual(result["N_crit"], 2)
        self.assertEqual(result["critical_indicators"], [
            {"district": "Nura", "indicator": "S1", "value": 38},
            {"district": "Nura", "indicator": "S2", "value": 35},
        ])  # Values exactly 40 (including Nura T2) are not critical.
        # .7 * 56.8624 + .3 * 49.18 - 2
        self.assertAlmostEqual(result["score"], 52.55768)

    def test_demo_full_result(self):
        result = simulation.simulate_scenario(demo())
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["total_cost"], 92)
        self.assertEqual(result["remaining_budget"], 8)
        # M2: +3 T1, +2.25 B2 everywhere; M12: +4.375 C2 everywhere.
        # Nura: M7 +10 S1, M8 +8.75 S2. Baikonur: M10 +10.5 B1,
        # +1.75 B2, plus the unscaled M10/M12 synergy +2 B1.
        expected = {
            "Esil": [48, 62, 68, 72, 48, 55, 78, 62.25, 75, 74.375],
            "Almaty": [43, 75, 50, 55, 60, 65, 62, 54.25, 50, 64.375],
            "Saryarka": [53, 70, 42, 40, 62, 68, 58, 57.25, 45, 59.375],
            "Baikonur": [55, 68, 55, 50, 58, 60, 64.5, 62, 55, 62.375],
            "Nura": [58, 40, 45, 65, 48, 43.75, 55, 52.25, 60, 54.375],
        }
        keys = ["T1", "T2", "E1", "E2", "S1", "S2", "B1", "B2", "C1", "C2"]
        self.assertEqual(result["indicators_after"], {
            district: dict(zip(keys, values)) for district, values in expected.items()
        })
        for district, score in {"Esil": 63.93, "Almaty": 58,
                                "Saryarka": 55.59, "Baikonur": 58.8525,
                                "Nura": 52.1825}.items():
            self.assertAlmostEqual(result["district_scores_after"][district], score)
        # Final mean=58.299125, minimum=52.1825, zero critical indicators.
        self.assertAlmostEqual(result["baseline_score"], 52.55768)
        self.assertAlmostEqual(result["final_score"], 56.4641375)
        self.assertAlmostEqual(result["score_delta"], 3.9064575)
        self.assertEqual(result["critical_indicators_after"], [])
        self.assertEqual(result["applied_synergies"], [
            {"measures": ["M10", "M12"], "district": "Baikonur", "effects": {"B1": 2}}
        ])
        self.assertEqual(set(result), {
            "valid", "errors", "total_cost", "remaining_budget", "baseline_score",
            "final_score", "score_delta", "district_scores_before", "district_scores_after",
            "indicators_before", "indicators_after", "critical_indicators_before",
            "critical_indicators_after", "applied_synergies", "selected_measures",
        })

    def test_wrong_decision_count(self):
        for selections in [[], demo()[:4], demo() + [{"measure_id": "M14"}]]:
            with self.subTest(count=len(selections)):
                self.assertInvalid(selections, "Exactly 5")

    def test_budget_exceeded(self):
        selections = plan(("M3", "Esil"), ("M5", "Nura"),
                          ("M7", "Nura"), ("M8", "Nura"), "M14")
        result = self.assertInvalid(selections, "exceeds budget")
        self.assertEqual(result["total_cost"], 115)
        self.assertEqual(result["remaining_budget"], -15)

    def test_exact_budget_is_valid(self):
        selections = plan(("M3", "Nura"), ("M7", "Nura"),
                          ("M10", "Esil"), "M12", "M6")
        result = simulation.validate_scenario(selections)
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["total_cost"], 100)
        self.assertEqual(result["remaining_budget"], 0)

    def test_duplicate_cost_is_counted(self):
        selections = plan("M2", ("M7", "Nura"), ("M8", "Nura"),
                          ("M10", "Baikonur"), ("M10", "Esil"))
        result = self.assertInvalid(selections, "Duplicate measure: M10")
        self.assertEqual(result["total_cost"], 90)

    def test_unknown_measure(self):
        for value in ["M99", None, [], 7]:
            with self.subTest(value=value):
                selections = demo()
                selections[0] = {"measure_id": value}
                result = self.assertInvalid(selections, "unknown measure_id")
                self.assertEqual(result["total_cost"], 70)

    def test_invalid_district(self):
        for value in ["Unknown", None, [], 7]:
            with self.subTest(value=value):
                selections = demo()
                selections[1]["district"] = value
                self.assertInvalid(selections, "M7 requires a valid district")
        selections = demo()
        del selections[1]["district"]
        self.assertInvalid(selections, "M7 requires a valid district")

    def test_city_district_rules(self):
        selections = demo()
        selections[0]["district"] = None
        self.assertTrue(simulation.validate_scenario(selections)["valid"])
        selections[0]["district"] = "Esil"
        self.assertInvalid(selections, "M2 is city-level")

    def test_malformed_inputs(self):
        for value in [None, {}, "scenario", 5]:
            with self.subTest(value=value):
                self.assertInvalid(value, "must be a list")
                self.assertIsNone(simulation.simulate_scenario(value)["final_score"])
        for value in [None, [], "M2", 5]:
            selections = demo()
            selections[0] = value
            self.assertInvalid(selections, "must be an object")

    def test_category_limit(self):
        selections = plan(("M7", "Nura"), ("M8", "Nura"),
                          ("M9", "Esil"), "M12", ("M10", "Esil"))
        self.assertInvalid(selections, "Category Social has 3 measures")

    def test_global_incompatibility_across_districts(self):
        for district in ["Esil", "Nura"]:
            selections = plan(("M1", "Esil"), ("M3", district),
                              ("M9", "Nura"), ("M10", "Nura"), "M12")
            self.assertInvalid(selections, "M1 and M3 are globally incompatible")

    def test_local_incompatibilities(self):
        for first, second in [("M4", "M7"), ("M5", "M13")]:
            with self.subTest(pair=(first, second)):
                selections = plan((first, "Esil"), (second, "Esil"),
                                  ("M9", "Nura"), ("M10", "Nura"), "M12")
                self.assertInvalid(selections, f"{first} and {second} cannot both target Esil")
                selections[1]["district"] = "Nura"
                self.assertTrue(simulation.validate_scenario(selections)["valid"])

    def test_lag_four_and_negative_effect(self):
        selections = plan(("M3", "Nura"), ("M11", "Nura"),
                          ("M9", "Esil"), "M12", "M14")
        result = simulation.simulate_scenario(selections)
        self.assertTrue(result["valid"], result["errors"])
        nura = result["indicators_after"]["Nura"]
        self.assertEqual(nura["T1"], 61.25)  # 55 + 16*4/8 - 2*7/8
        self.assertEqual(nura["T2"], 50)  # 40 + 20*4/8
        self.assertEqual(nura["E2"], 67)  # 65 + 4*4/8
        self.assertEqual(nura["B2"], 60.5)  # 50 + 12*7/8
        self.assertEqual(result["indicators_after"]["Esil"]["T1"], 45)
        self.assertEqual(result["applied_synergies"], [])

    def test_transport_synergy_is_unscaled_and_local(self):
        selections = plan(("M1", "Nura"), "M2", ("M9", "Esil"),
                          ("M11", "Esil"), "M14")
        result = simulation.simulate_scenario(selections)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["indicators_after"]["Nura"]["T1"], 64.5)
        self.assertEqual(result["indicators_after"]["Almaty"]["T1"], 43)
        self.assertEqual(result["applied_synergies"], [
            {"measures": ["M1", "M2"], "district": "Nura", "effects": {"T1": 2}}
        ])

    def test_environment_synergy_is_unscaled_and_local(self):
        selections = plan(("M5", "Nura"), "M6", ("M9", "Esil"),
                          ("M11", "Esil"), "M14")
        result = simulation.simulate_scenario(selections)
        self.assertTrue(result["valid"], result["errors"])
        # 65 + 14*5/8 + 3*4/8 + 2 = 77.25
        self.assertEqual(result["indicators_after"]["Nura"]["E2"], 77.25)
        self.assertEqual(result["indicators_after"]["Almaty"]["E2"], 56.5)
        self.assertEqual(result["applied_synergies"], [
            {"measures": ["M5", "M6"], "district": "Nura", "effects": {"E2": 2}}
        ])

    def test_synergy_requires_both_measures(self):
        for pair, local, indicator, expected in [
            (("M1", "M2"), "M1", "T1", (59.5, 58)),
            (("M10", "M12"), "M10", "B1", (65.5, 55)),
            (("M5", "M6"), "M5", "E2", (73.75, 66.5)),
        ]:
            for measure, value in zip(pair, expected):
                with self.subTest(measure=measure):
                    selections = plan((measure, "Nura") if measure == local else measure,
                                      ("M9", "Esil"), ("M11", "Esil"), "M14", ("M4", "Esil"))
                    result = simulation.simulate_scenario(selections)
                    self.assertTrue(result["valid"], result["errors"])
                    self.assertEqual(result["applied_synergies"], [])
                    self.assertEqual(result["indicators_after"]["Nura"][indicator], value)

    def test_clamping_with_synthetic_boundary_fixture(self):
        # Current real data cannot reach both limits; isolate the rule with
        # temporary starting values, without changing committed scenario data.
        districts = deepcopy(data.DISTRICTS)
        districts["Nura"]["indicators"]["T1"] = 1
        districts["Nura"]["indicators"]["B2"] = 99
        selections = plan(("M11", "Nura"), ("M9", "Esil"),
                          ("M4", "Esil"), "M12", "M14")
        with patch.object(simulation, "DISTRICTS", districts):
            result = simulation.simulate_scenario(selections)
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["indicators_after"]["Nura"]["T1"], 0)
        self.assertEqual(result["indicators_after"]["Nura"]["B2"], 100)
        self.assertEqual(result["indicators_before"]["Nura"]["T1"], 1)

    def test_invalid_result_preserves_contract(self):
        result = simulation.simulate_scenario([])
        self.assertFalse(result["valid"])
        self.assertAlmostEqual(result["baseline_score"], 52.55768)
        for field in ["final_score", "score_delta", "district_scores_after",
                      "indicators_after", "critical_indicators_after"]:
            self.assertIsNone(result[field])
        self.assertEqual(result["applied_synergies"], [])
        self.assertEqual(result["selected_measures"], [])
        self.assertEqual(result["total_cost"], 0)
        self.assertEqual(result["remaining_budget"], 100)

    def test_no_mutation_or_output_aliasing(self):
        selections = demo()
        original = deepcopy(selections)
        constants = [data.DISTRICTS, data.MEASURES, data.SYNERGIES,
                     data.INCOMPATIBILITIES, data.INDICATOR_WEIGHTS]
        snapshot = deepcopy(constants)
        simulation.validate_scenario(selections)
        result = simulation.simulate_scenario(selections)
        self.assertEqual(selections, original)
        self.assertEqual(constants, snapshot)
        result["indicators_before"]["Nura"]["S1"] = -999
        result["indicators_after"]["Nura"]["S1"] = -999
        result["selected_measures"][0]["measure_id"] = "changed"
        result["applied_synergies"][0]["effects"]["B1"] = -999
        result["applied_synergies"][0]["measures"].clear()
        baseline = simulation.calculate_baseline()
        baseline["indicators"]["Nura"]["S1"] = -999
        self.assertEqual(constants, snapshot)
        self.assertEqual(selections, original)
        self.assertAlmostEqual(simulation.simulate_scenario(demo())["final_score"], 56.4641375)

    def test_all_selection_orders_have_same_calculations(self):
        expected = simulation.simulate_scenario(demo())
        del expected["selected_measures"]
        for order in permutations(demo()):
            selections = list(order)
            result = simulation.simulate_scenario(selections)
            self.assertEqual(result.pop("selected_measures"), selections)
            self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
