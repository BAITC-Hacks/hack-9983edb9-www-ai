"""Deterministic scenario validation and scoring using the official data."""

from collections import Counter
from copy import deepcopy

from .data import (
    BUDGET,
    DISTRICTS,
    INCOMPATIBILITIES,
    INDICATOR_WEIGHTS,
    MEASURES,
    REQUIRED_DECISIONS,
    SIMULATION_HORIZON,
    SYNERGIES,
)


def _score(indicators: dict) -> dict:
    district_scores = {
        district: sum(INDICATOR_WEIGHTS[key] * value for key, value in values.items())
        for district, values in indicators.items()
    }
    critical_indicators = [
        {"district": district, "indicator": key, "value": value}
        for district, values in indicators.items()
        for key, value in values.items()
        if value < 40
    ]
    d_avg = sum(
        DISTRICTS[district]["population_share"] * score
        for district, score in district_scores.items()
    )
    min_d = min(district_scores.values())
    n_crit = len(critical_indicators)
    return {
        "district_scores": district_scores,
        "critical_indicators": critical_indicators,
        "D_avg": d_avg,
        "min_D": min_d,
        "N_crit": n_crit,
        "score": 0.7 * d_avg + 0.3 * min_d - n_crit,
    }


def calculate_baseline() -> dict:
    """Return original indicators, district scores, and city scoring components."""
    indicators = deepcopy({
        district: data["indicators"] for district, data in DISTRICTS.items()
    })
    return {"indicators": indicators, **_score(indicators)}


def validate_scenario(selections: list[dict]) -> dict:
    """Validate a list of selections without applying any effects.

    City selections omit district or use None. For invalid input, total_cost
    includes every recognized measure occurrence, including duplicates.
    """
    errors = []
    total_cost = 0
    categories = Counter()
    selected = {}

    if not isinstance(selections, list):
        return {
            "valid": False,
            "errors": ["Scenario must be a list of selections."],
            "total_cost": 0,
            "remaining_budget": BUDGET,
        }
    if len(selections) != REQUIRED_DECISIONS:
        errors.append(f"Exactly {REQUIRED_DECISIONS} measures must be selected.")

    for index, selection in enumerate(selections, start=1):
        if not isinstance(selection, dict):
            errors.append(f"Selection {index} must be an object.")
            continue
        measure_id = selection.get("measure_id")
        if not isinstance(measure_id, str) or measure_id not in MEASURES:
            errors.append(f"Selection {index}: unknown measure_id {measure_id!r}.")
            continue
        measure = MEASURES[measure_id]
        total_cost += measure["cost"]
        categories[measure["category"]] += 1
        if measure_id in selected:
            errors.append(f"Duplicate measure: {measure_id}.")
        else:
            selected[measure_id] = selection

        district = selection.get("district")
        if measure["type"] == "district":
            if not isinstance(district, str) or district not in DISTRICTS:
                errors.append(f"{measure_id} requires a valid district.")
        elif district is not None:
            errors.append(f"{measure_id} is city-level; omit district or use None.")

    if total_cost > BUDGET:
        errors.append(f"Total cost {total_cost} exceeds budget {BUDGET}.")
    for category, count in categories.items():
        if count > 2:
            errors.append(f"Category {category} has {count} measures; maximum is 2.")

    for rule in INCOMPATIBILITIES:
        first, second = rule["measures"]
        if first not in selected or second not in selected:
            continue
        if rule["scope"] == "global":
            errors.append(f"{first} and {second} are globally incompatible.")
        else:
            district = selected[first].get("district")
            if (
                isinstance(district, str)
                and district in DISTRICTS
                and district == selected[second].get("district")
            ):
                errors.append(f"{first} and {second} cannot both target {district}.")

    return {
        "valid": not errors,
        "errors": errors,
        "total_cost": total_cost,
        "remaining_budget": BUDGET - total_cost,
    }


def simulate_scenario(selections: list[dict]) -> dict:
    """Apply a valid scenario without mutating input or official data.

    Invalid scenarios return baseline information, but final_score, score_delta,
    and all after fields remain None. Critical indicators are lists of
    district/indicator/value records. No calculations are rounded.
    """
    validation = validate_scenario(selections)
    baseline = calculate_baseline()
    result = {
        **validation,
        "baseline_score": baseline["score"],
        "final_score": None,
        "score_delta": None,
        "district_scores_before": baseline["district_scores"],
        "district_scores_after": None,
        "indicators_before": baseline["indicators"],
        "indicators_after": None,
        "critical_indicators_before": baseline["critical_indicators"],
        "critical_indicators_after": None,
        "applied_synergies": [],
        "selected_measures": deepcopy(selections),
        "district_score_deltas": None,
        "indicator_deltas": None,
        "measure_contributions": [],
        "clipping_adjustments": None,
    }
    if not validation["valid"]:
        return result

    indicators = deepcopy(baseline["indicators"])
    selected = {selection["measure_id"]: selection for selection in selections}
    # Official measure order makes results independent of selection order.
    for measure_id, measure in MEASURES.items():
        if measure_id not in selected:
            continue
        targets = (
            [selected[measure_id]["district"]]
            if measure["type"] == "district"
            else DISTRICTS
        )
        contribution = {
            "measure_id": measure_id,
            "cost": measure["cost"],
            "lag": measure["lag"],
            "realized_fraction": (SIMULATION_HORIZON - measure["lag"]) / SIMULATION_HORIZON,
            "indicator_effects_before_clip": {},
        }
        for district in targets:
            contribution["indicator_effects_before_clip"][district] = {}
            for key, full_effect in measure["effects"].items():
                realized_effect = (
                    full_effect * (SIMULATION_HORIZON - measure["lag"])
                    / SIMULATION_HORIZON
                )
                indicators[district][key] += realized_effect
                contribution["indicator_effects_before_clip"][district][key] = realized_effect
        result["measure_contributions"].append(contribution)

    for synergy in SYNERGIES:
        if all(measure_id in selected for measure_id in synergy["measures"]):
            district = selected[synergy["district_measure"]]["district"]
            for key, bonus in synergy["effects"].items():
                indicators[district][key] += bonus
            result["applied_synergies"].append({
                "measures": synergy["measures"].copy(),
                "district": district,
                "effects": synergy["effects"].copy(),
            })

    # Contributions are lag-adjusted additive effects, not shares of final Score.
    # Synergies stay separate; clipping is applied only to the combined result.
    clipping_adjustments = {}
    for district, values in indicators.items():
        clipping_adjustments[district] = {}
        for key, value in values.items():
            values[key] = max(0, min(100, value))
            clipping_adjustments[district][key] = values[key] - value

    final = _score(indicators)
    result.update({
        "final_score": final["score"],
        "score_delta": final["score"] - baseline["score"],
        "district_scores_after": final["district_scores"],
        "indicators_after": indicators,
        "critical_indicators_after": final["critical_indicators"],
        "district_score_deltas": {
            district: score - baseline["district_scores"][district]
            for district, score in final["district_scores"].items()
        },
        "indicator_deltas": {
            district: {key: value - baseline["indicators"][district][key]
                       for key, value in values.items()}
            for district, values in indicators.items()
        },
        "clipping_adjustments": clipping_adjustments,
    })
    return result
