"""Verified explanation candidates. The LLM selects relevance, never writes facts."""


def evidence_catalog(result: dict) -> dict:
    """Build statements exclusively from a canonical engine result.

    Decimal formatting here is presentation only and never changes the score.
    Consequences describe the synthetic model, not real-world forecasts.
    """
    catalog = {
        "summary": {"score": f"Model Score: {result['baseline_score']:.5f} → {result['final_score']:.5f}. Cost: {result['total_cost']} of 100; remaining: {result['remaining_budget']}."},
        "strengths": {},
        "risks": {"model": "These synthetic results are not a forecast of actual Astana outcomes; resident satisfaction and construction uncertainty are not modeled."},
        "tradeoffs": {"budget": f"The plan spends {result['total_cost']} of 100. Unspent budget gives no Score bonus; each chosen measure uses one of five decision slots."},
        "consequences": {},
        "recommendations": {"compare": "Calculate another valid five-decision allocation and compare both Score and district outcomes before choosing a plan."},
    }
    before = {(x['district'], x['indicator']): x for x in result['critical_indicators_before']}
    after = {(x['district'], x['indicator']): x for x in result['critical_indicators_after']}
    for district, delta in result['district_score_deltas'].items():
        if delta > 0:
            catalog['strengths'][f"gain_{district}"] = f"{district}'s district score increases by {delta:.5f} in the model."
        unchanged = [key for key, value in result['indicator_deltas'][district].items() if value == 0]
        if unchanged:
            catalog['risks'][f"unchanged_{district}"] = f"{district}: {', '.join(unchanged)} receive no net improvement in this plan. Unchanged does not necessarily mean critical."
    for (district, indicator), item in before.items():
        if (district, indicator) not in after:
            catalog['consequences'][f"resolved_{district}_{indicator}"] = f"{district} {indicator} rises from {item['value']:g} to {result['indicators_after'][district][indicator]:g}, removing its below-40 penalty."
    for (district, indicator), item in after.items():
        catalog['risks'][f"critical_{district}_{indicator}"] = f"{district} {indicator} is {item['value']:g}, strictly below 40, so it incurs one Score penalty point."
        catalog['recommendations'][f"review_{district}_{indicator}"] = f"Test an alternative targeting {district} {indicator}; validate its budget and effects with the engine before recommending it."
    catalog['consequences']['critical_count'] = f"Critical district–indicator pairs: {len(before)} before, {len(after)} after. Each value strictly below 40 costs one Score point."
    for index, synergy in enumerate(result['applied_synergies']):
        effects = ', '.join(f"{key} {value:+g}" for key, value in synergy['effects'].items())
        catalog['strengths'][f"synergy_{index}"] = f"{' + '.join(synergy['measures'])} activates {effects} in {synergy['district']}; this fixed bonus is not reduced by lag."
    for item in result['measure_contributions']:
        effects = '; '.join(f"{district}: " + ', '.join(f"{key} {value:+g}" for key, value in changes.items()) for district, changes in item['indicator_effects_before_clip'].items())
        catalog['tradeoffs'][item['measure_id']] = f"{item['measure_id']} costs {item['cost']} and starts after {item['lag']} quarters. Its lag-adjusted effects before clipping and synergies are {effects}. These are not additive shares of final Score."
    return catalog


def render_selection(selection: dict, catalog: dict) -> dict:
    """Reject invented IDs, wrong sections, omissions, and duplicates."""
    if set(selection) != set(catalog):
        raise ValueError('Invalid explanation sections')
    rendered = {}
    for section, candidates in catalog.items():
        ids = [selection[section]] if section == 'summary' else selection[section]
        if not isinstance(ids, list) or not 1 <= len(ids) <= 3:
            raise ValueError('Invalid explanation selection')
        if any(not isinstance(key, str) or key not in candidates for key in ids) or len(set(ids)) != len(ids):
            raise ValueError('Unknown or repeated evidence')
        texts = [candidates[key] for key in ids]
        rendered[section] = texts[0] if section == 'summary' else texts
    return rendered
