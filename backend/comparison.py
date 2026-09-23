"""Compare two independently validated plans using the same initial data."""
from .simulation import simulate_scenario


def compare_scenarios(selections_a: list, selections_b: list) -> dict:
    a, b = simulate_scenario(selections_a), simulate_scenario(selections_b)
    if not a['valid'] or not b['valid']:
        return {'valid': False, 'errors': {'a': a['errors'], 'b': b['errors']}, 'comparison': None}
    return {'valid': True, 'errors': {}, 'comparison': {
        'score_a': a['final_score'], 'score_b': b['final_score'],
        'score_difference': b['final_score'] - a['final_score'],
        'cost_a': a['total_cost'], 'cost_b': b['total_cost'],
        'districts': {d: {'a': a['district_scores_after'][d], 'b': b['district_scores_after'][d],
                          'difference': b['district_scores_after'][d] - a['district_scores_after'][d]}
                      for d in a['district_scores_after']},
    }}
