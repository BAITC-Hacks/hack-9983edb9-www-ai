"""Regression tests for observed hallucinations and plan comparison."""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.ai_service import EvidenceSelection, analyze_simulation
from backend.explanations import evidence_catalog, render_selection
from backend.main import app
from backend.simulation import simulate_scenario

REFERENCE = [
    {'measure_id': 'M7', 'district': 'Nura'},
    {'measure_id': 'M8', 'district': 'Nura'},
    {'measure_id': 'M10', 'district': 'Nura'},
    {'measure_id': 'M12'},
    {'measure_id': 'M5', 'district': 'Saryarka'},
]
CHEAP = [{'measure_id': m, **({'district': 'Nura'} if m != 'M12' else {})}
         for m in ('M9', 'M11', 'M10', 'M12', 'M4')]
PICKS = dict(summary='score', strengths=['gain_Nura'], risks=['model'],
             tradeoffs=['M7'], consequences=['resolved_Nura_S1', 'resolved_Nura_S2'],
             recommendations=['compare'])


class GroundingTests(TestCase):
    def test_only_actual_critical_indicators_are_called_resolved(self):
        catalog = evidence_catalog(simulate_scenario(REFERENCE))
        self.assertEqual(set(catalog['consequences']),
                         {'resolved_Nura_S1', 'resolved_Nura_S2', 'critical_count'})
        self.assertIn('38 → 48', catalog['consequences']['resolved_Nura_S1'])
        self.assertIn('35 → 43.75', catalog['consequences']['resolved_Nura_S2'])
        self.assertIn('52.55768 → 56.54307', catalog['summary']['score'])
        self.assertIn('3.78250', catalog['strengths']['gain_Nura'])
        self.assertNotIn('critical_Nura_B1', catalog['risks'])

    def test_remaining_critical_is_not_reported_resolved(self):
        catalog = evidence_catalog(simulate_scenario(CHEAP))
        self.assertIn('37.625', catalog['risks']['critical_Nura_S2'])
        self.assertNotIn('resolved_Nura_S2', catalog['consequences'])
        self.assertIn('review_Nura_S2', catalog['recommendations'])

    def test_fabrications_wrong_sections_and_duplicates_are_rejected(self):
        catalog = evidence_catalog(simulate_scenario(REFERENCE))
        for section, ids in [('summary', 'Score is 100'), ('strengths', ['model']),
                             ('consequences', ['resolved_Nura_B1']), ('risks', []),
                             ('risks', ['model', 'model'])]:
            with self.subTest(section=section, ids=ids):
                picks = {**PICKS, section: ids}
                with self.assertRaises(ValueError):
                    render_selection(picks, catalog)

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-only'})
    @patch('backend.ai_service.OpenAI')
    def test_forged_engine_numbers_never_reach_ai(self, factory):
        result = simulate_scenario(REFERENCE)
        for field, value in [('final_score', 100), ('critical_indicators_before', []),
                             ('indicator_deltas', {}), ('selected_measures', [])]:
            altered = {**result, field: value}
            self.assertEqual(analyze_simulation(altered)['error']['code'], 'invalid_simulation')
        factory.assert_not_called()

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-only'})
    @patch('backend.ai_service.OpenAI')
    def test_hallucinated_id_is_controlled_failure(self, factory):
        sdk = factory.return_value.__enter__.return_value
        sdk.responses.parse.return_value = SimpleNamespace(status='completed',
            output_parsed=EvidenceSelection(**{**PICKS, 'consequences': ['resolved_Nura_B1']}))
        result = simulate_scenario(REFERENCE)
        original = deepcopy(result)
        self.assertEqual(analyze_simulation(result)['error']['code'], 'invalid_ai_response')
        self.assertEqual(original, result)


class ComparisonTests(TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))

    def compare(self, a, b):
        return self.client.post('/api/compare', json={'selections_a': a, 'selections_b': b}).json()

    def test_reference_vs_cheap_hand_calculated_difference(self):
        result = self.compare(REFERENCE, CHEAP)
        self.assertTrue(result['valid'])
        c = result['comparison']
        self.assertAlmostEqual(c['score_a'], 56.54307)
        self.assertAlmostEqual(c['score_b'], 55.667385)
        self.assertAlmostEqual(c['score_difference'], -0.875685)
        self.assertEqual((c['cost_a'], c['cost_b']), (95, 61))

    def test_same_plan_reordered_has_zero_difference(self):
        result = self.compare(REFERENCE, REFERENCE[::-1])['comparison']
        self.assertEqual(result['score_difference'], 0)
        self.assertTrue(all(x['difference'] == 0 for x in result['districts'].values()))

    def test_invalid_plan_has_no_comparison(self):
        for a, b in [(REFERENCE, []), ([], REFERENCE)]:
            result = self.compare(a, b)
            self.assertFalse(result['valid'])
            self.assertIsNone(result['comparison'])
            self.assertTrue(result['errors']['a'] or result['errors']['b'])


class RussianDashboardTests(TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))

    def test_labels_and_rules_cover_engine_catalog(self):
        from backend.data import DISTRICTS, MEASURES, INDICATOR_METADATA, INCOMPATIBILITIES
        initial = self.client.get('/api/initial-state').json()
        labels = initial['ui_labels']
        self.assertEqual(set(labels['districts']), set(DISTRICTS))
        self.assertEqual(set(labels['measures']), set(MEASURES))
        self.assertEqual(set(labels['indicators']), set(INDICATOR_METADATA))
        self.assertEqual(set(labels['categories']), {m['category'] for m in MEASURES.values()})
        self.assertEqual(initial['rules'], {'max_per_category': 2, 'incompatibilities': INCOMPATIBILITIES})
        self.assertEqual(labels['districts']['Nura'], 'Нура')

    def test_comparison_explains_lower_score_despite_higher_nura_score(self):
        from backend.comparison import compare_scenarios
        c = compare_scenarios(REFERENCE, CHEAP)['comparison']
        self.assertEqual(c['cost_difference'], -34)
        self.assertLess(c['score_difference'], 0)
        self.assertAlmostEqual(c['districts']['Nura']['difference'], 0.71375)
        self.assertEqual(c['critical_a'], [])
        self.assertEqual(c['critical_b'], [{'district': 'Nura', 'indicator': 'S2', 'value': 37.625}])
        reverse = compare_scenarios(CHEAP, REFERENCE)['comparison']
        self.assertEqual(reverse['cost_difference'], 34)
        self.assertEqual(reverse['critical_b'], [])
        self.assertEqual(reverse['critical_a'], c['critical_b'])

    def test_localized_evidence_retains_fact_ids_and_numbers(self):
        catalog = evidence_catalog(simulate_scenario(REFERENCE))
        output = render_selection(PICKS, catalog)
        self.assertIn('Нура', output['strengths'][0])
        self.assertIn('38 → 48', output['consequences'][0])
        self.assertIn('Школы и детсады', output['consequences'][0])
        self.assertIn('56.54307', output['summary'])
