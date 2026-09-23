"""Verified explanation candidates. The LLM selects relevance, never writes facts."""

from .localization import DISTRICT_LABELS, INDICATOR_LABELS

def evidence_catalog(result: dict) -> dict:
    """Build statements exclusively from a canonical engine result.

    Decimal formatting here is presentation only and never changes the score.
    Consequences describe the synthetic model, not real-world forecasts.
    """
    catalog = {
        "summary": {"score": f"Балл модели: {result['baseline_score']:.5f} → {result['final_score']:.5f}. Стоимость: {result['total_cost']} из 100; остаток: {result['remaining_budget']}."},
        "strengths": {},
        "risks": {"model": "Данные условные: результат не является прогнозом для реальной Астаны. Удовлетворённость жителей и неопределённость строительства не моделируются."},
        "tradeoffs": {"budget": f"План расходует {result['total_cost']} из 100. Остаток бюджета не даёт бонуса; каждое мероприятие занимает одно из пяти решений."},
        "consequences": {},
        "recommendations": {"compare": "Рассчитайте другой допустимый план из пяти решений и сравните общий балл и результаты районов перед выбором."},
    }
    before = {(x['district'], x['indicator']): x for x in result['critical_indicators_before']}
    after = {(x['district'], x['indicator']): x for x in result['critical_indicators_after']}
    for district, delta in result['district_score_deltas'].items():
        if delta > 0:
            catalog['strengths'][f"gain_{district}"] = f"{DISTRICT_LABELS[district]}: районный балл в модели вырос на {delta:.5f}."
        unchanged = [key for key, value in result['indicator_deltas'][district].items() if value == 0]
        if unchanged:
            catalog['risks'][f"unchanged_{district}"] = f"{DISTRICT_LABELS[district]}: без изменений остались {', '.join(INDICATOR_LABELS[key] for key in unchanged)}. Это не означает, что они критические."
    for (district, indicator), item in before.items():
        if (district, indicator) not in after:
            catalog['consequences'][f"resolved_{district}_{indicator}"] = f"{DISTRICT_LABELS[district]} — {INDICATOR_LABELS[indicator]} ({indicator}): {item['value']:g} → {result['indicators_after'][district][indicator]:g}. Штраф за значение ниже 40 устранён."
    for (district, indicator), item in after.items():
        catalog['risks'][f"critical_{district}_{indicator}"] = f"{DISTRICT_LABELS[district]} — {INDICATOR_LABELS[indicator]} ({indicator}): {item['value']:g}, строго ниже 40. Это даёт штраф в один балл."
        catalog['recommendations'][f"review_{district}_{indicator}"] = f"Проверьте другой план для показателя «{INDICATOR_LABELS[indicator]}» в районе {DISTRICT_LABELS[district]}. Перед выбором рассчитайте бюджет и эффекты."
    catalog['consequences']['critical_count'] = f"Критических показателей по районам: было {len(before)}, стало {len(after)}. Каждое значение строго ниже 40 уменьшает итог на один балл."
    for index, synergy in enumerate(result['applied_synergies']):
        effects = ', '.join(f"{key} {value:+g}" for key, value in synergy['effects'].items())
        catalog['strengths'][f"synergy_{index}"] = f"{' + '.join(synergy['measures'])}: совместный бонус {effects}, район {DISTRICT_LABELS[synergy['district']]}. Бонус фиксированный, задержка его не уменьшает."
    for item in result['measure_contributions']:
        effects = '; '.join(f"{DISTRICT_LABELS[district]}: " + ', '.join(f"{key} {value:+g}" for key, value in changes.items()) for district, changes in item['indicator_effects_before_clip'].items())
        catalog['tradeoffs'][item['measure_id']] = f"{item['measure_id']}: стоимость {item['cost']}, задержка в кварталах — {item['lag']}. Эффекты с учётом задержки, до ограничения 0–100 и совместных бонусов: {effects}. Это изменения показателей, а не отдельные доли итогового балла."
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
