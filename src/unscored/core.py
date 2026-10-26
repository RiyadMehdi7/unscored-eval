"""Exact finite-suite bounds; unresolved scores range independently over [0, 1]."""

import math
from decimal import Decimal
from fractions import Fraction


MAX_CASES = 100_000
MAX_TEXT_LENGTH = 200
# Bound decimal representations before Fraction creates powers of ten.
MAX_DECIMAL_DIGITS = 100
MAX_DECIMAL_EXPONENT = 100


class InputError(ValueError):
    """The supplied evaluation does not satisfy the declared input contract."""


def _object(value, required, optional, context):
    if not isinstance(value, dict):
        raise InputError(f"{context} must be an object")
    if required - value.keys():
        raise InputError(f"{context} is missing required fields: {', '.join(sorted(required - value.keys()))}")
    if value.keys() - required - optional:
        raise InputError(f"{context} contains unknown fields")


def _text(value, context):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{context} must be a nonempty string")
    if len(value) > MAX_TEXT_LENGTH:
        raise InputError(f"{context} exceeds {MAX_TEXT_LENGTH} characters")
    if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
        raise InputError(f"{context} must not contain control characters")
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise InputError(f"{context} must contain valid Unicode scalar values")
    return value


def _number(value, context):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise InputError(f"{context} must be a finite number, not a boolean or string")
    if isinstance(value, int):
        if abs(value) >= 10**MAX_DECIMAL_DIGITS:
            raise InputError(f"{context} exceeds the {MAX_DECIMAL_DIGITS}-digit numeric limit")
        decimal = Decimal(value)
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise InputError(f"{context} must be finite")
        decimal = Decimal(str(value))
    else:
        decimal = value
    if not decimal.is_finite():
        raise InputError(f"{context} must be finite")
    if len(decimal.as_tuple().digits) > MAX_DECIMAL_DIGITS or abs(decimal.adjusted()) > MAX_DECIMAL_EXPONENT:
        raise InputError(
            f"{context} exceeds numeric limits ({MAX_DECIMAL_DIGITS} digits, "
            f"adjusted exponent -{MAX_DECIMAL_EXPONENT} through {MAX_DECIMAL_EXPONENT})"
        )
    return Fraction(decimal)


def _validate_suite(suite):
    _object(suite, {"version", "name", "systems", "cases"}, set(), "suite")
    if type(suite["version"]) is not int or suite["version"] != 1:
        raise InputError("suite.version must be integer 1")
    name = _text(suite["name"], "suite.name")
    systems = suite["systems"]
    if not isinstance(systems, list) or len(systems) != 2:
        raise InputError("suite.systems must contain exactly two system IDs")
    systems = [_text(system, f"suite.systems[{index}]") for index, system in enumerate(systems)]
    if systems[0] == systems[1]:
        raise InputError("suite.systems contains duplicate system IDs")
    if not isinstance(suite["cases"], list) or not suite["cases"]:
        raise InputError("suite.cases must be a nonempty list")
    if len(suite["cases"]) > MAX_CASES:
        raise InputError(f"suite.cases exceeds the {MAX_CASES:,}-case limit")
    cases = []
    seen = set()
    for index, case in enumerate(suite["cases"]):
        context = f"suite.cases[{index}]"
        _object(case, {"id"}, {"weight", "group"}, context)
        case_id = _text(case["id"], f"{context}.id")
        if case_id in seen:
            raise InputError(f"{context} has a duplicate case ID")
        seen.add(case_id)
        weight = _number(case.get("weight", 1), f"{context}.weight")
        if weight <= 0:
            raise InputError(f"{context}.weight must be positive")
        group = _text(case.get("group", "all"), f"{context}.group")
        cases.append((case_id, weight, group))
    cases.sort(key=lambda case: case[0])
    return name, systems, cases


def _validate_result(row, context):
    _object(row, {"system", "case_id", "status"}, {"score"}, context)
    system = _text(row["system"], f"{context}.system")
    case_id = _text(row["case_id"], f"{context}.case_id")
    status = row["status"]
    if not isinstance(status, str) or status not in ("scored", "error", "unscored"):
        raise InputError(f"{context}.status must be scored, error, or unscored")
    score = None
    if status == "scored":
        if "score" not in row:
            raise InputError(f"{context} requires score when status is scored")
        score = _number(row["score"], f"{context}.score")
        if not 0 <= score <= 1:
            raise InputError(f"{context}.score must be between 0 and 1")
    elif "score" in row:
        raise InputError(f"{context} forbids score unless status is scored")
    return system, case_id, status, score


def audit(suite: dict, results: list[dict]) -> dict:
    """Return exact bounds, endpoint completions, and an unresolved-cell queue."""
    name, system_ids, cases = _validate_suite(suite)
    if not isinstance(results, list):
        raise InputError("results must be a list of result objects")
    case_ids = {case_id for case_id, _, _ in cases}
    cells = {}
    for index, row in enumerate(results):
        context = f"results[{index}]"
        system, case_id, status, score = _validate_result(row, context)
        if system not in system_ids:
            raise InputError(f"{context} refers to an unknown system")
        if case_id not in case_ids:
            raise InputError(f"{context} refers to an unknown case")
        if (system, case_id) in cells:
            raise InputError(f"{context} duplicates a system/case pair; choose one attempt before export")
        cells[system, case_id] = status, score

    total_weight = sum((weight for _, weight, _ in cases), Fraction())
    systems = []
    bounds = {}
    for system in system_ids:
        counts = dict.fromkeys(("scored", "missing", "error", "unscored"), 0)
        scored_weight = Fraction()
        weighted_score = Fraction()
        for case_id, weight, _ in cases:
            status, score = cells.get((system, case_id), ("missing", None))
            counts[status] += 1
            if status == "scored":
                scored_weight += weight
                weighted_score += weight * score
        unresolved_weight = total_weight - scored_weight
        lower = weighted_score / total_weight
        upper = (weighted_score + unresolved_weight) / total_weight
        bounds[system] = lower, upper
        systems.append({
            "id": system, **counts, "coverage": str(scored_weight / total_weight),
            "observed_mean": str(weighted_score / scored_weight) if scored_weight else None,
            "lower": str(lower), "upper": str(upper), "scored_weight": str(scored_weight),
            "unresolved_weight": str(unresolved_weight),
        })

    a, b = system_ids
    margin_lower = bounds[a][0] - bounds[b][1]
    margin_upper = bounds[a][1] - bounds[b][0]
    if margin_lower > 0:
        verdict, winner = "a_wins", a
    elif margin_upper < 0:
        verdict, winner = "b_wins", b
    elif margin_lower == margin_upper == 0:
        verdict, winner = "tie", None
    else:
        verdict, winner = "inconclusive", None

    case_reports = []
    unresolved = []
    for case_id, weight, group in cases:
        case_report = {"id": case_id, "group": group, "weight": str(weight)}
        unknown_count = 0
        for label, system in zip(("a", "b"), system_ids):
            status, score = cells.get((system, case_id), ("missing", None))
            case_report[label] = {"status": status, "score": str(score) if score is not None else None}
            if status != "scored":
                unknown_count += 1
                unresolved.append((system, case_id, status, weight))
        case_report["uncertainty"] = str(unknown_count * weight / total_weight)
        case_reports.append(case_report)

    witnesses = []
    for favored in system_ids:
        scores = {system: bounds[system][1 if system == favored else 0] for system in system_ids}
        margin = scores[a] - scores[b]
        witnesses.append({
            "favored": favored, "hypothetical": True,
            "scores": {system: str(score) for system, score in scores.items()},
            "margin": str(margin), "winner": a if margin > 0 else b if margin < 0 else None,
            "assignments": [{"system": system, "case_id": case_id, "score": int(system == favored)}
                            for system, case_id, _, _ in sorted(unresolved, key=lambda item: (item[1], item[0]))],
        })
    rerun_plan = [{
        "system": system, "case_id": case_id, "status": status, "weight": str(weight),
        "interval_reduction": str(weight / total_weight),
    } for system, case_id, status, weight in sorted(unresolved, key=lambda item: (-item[3], item[1], item[0]))]
    return {
        "schema_version": 1, "name": name, "system_ids": system_ids,
        "summary": {"verdict": verdict, "winner": winner, "case_count": len(cases),
                    "total_weight": str(total_weight),
                    "margin": {"lower": str(margin_lower), "upper": str(margin_upper)}},
        "systems": systems, "cases": case_reports, "completion_witnesses": witnesses,
        "rerun_plan": rerun_plan,
    }
