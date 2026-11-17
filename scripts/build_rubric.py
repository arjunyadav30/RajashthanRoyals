"""Build the 100-mark scouting rubric for every scored batter and bowler.

Batter (100): overall batting 15, pressure 18, consistency 13, boundary
hitting 10, dot-ball control 8, phase-wise 10, pace & spin 8, recent form 5,
experience 7, sample size 6.

Bowler (100): overall bowling 15, pressure 18, wicket-taking 13, economy 10,
dot-ball % 8, consistency 10, phase-wise 8, batting styles 5, recent form 5,
experience 7, sample size 6.

Percentile criteria are computed inside each role, shrunk toward the role
median when the relevant sample is thin, so a two-match spike cannot reach
the top. Experience uses the fixed 1-7 match table. Sample marks need real
opportunity (innings and balls). Output is one small aggregate row per
player in data_derived/scores/rubric.json; no raw deliveries are copied.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]

EXPERIENCE_TABLE = (
    (76, 7),
    (51, 6),
    (31, 5),
    (21, 4),
    (11, 3),
    (6, 2),
    (1, 1),
)

WEIGHTS = {
    "batter": (
        ("overall", "Overall batting", 15),
        ("pressure", "Pressure batting", 18),
        ("consistency", "Consistency", 13),
        ("boundary", "Boundary hitting", 10),
        ("dot_control", "Dot-ball control", 8),
        ("phase", "Phase-wise batting", 10),
        ("vs_type", "Pace & spin", 8),
        ("form", "Recent form & improvement", 5),
        ("experience", "Matches & experience", 7),
        ("sample", "Sample size", 6),
    ),
    "bowler": (
        ("overall", "Overall bowling", 15),
        ("pressure", "Pressure bowling", 18),
        ("wickets", "Wicket-taking ability", 13),
        ("economy", "Economy rate", 10),
        ("dot_control", "Dot-ball percentage", 8),
        ("consistency", "Consistency", 10),
        ("phase", "Phase-wise bowling", 8),
        ("vs_type", "Batting styles", 5),
        ("form", "Recent form & improvement", 5),
        ("experience", "Matches & experience", 7),
        ("sample", "Sample size", 6),
    ),
}

SKILL_KEYS = {
    key for key in ("overall", "pressure", "consistency", "boundary", "dot_control",
                    "phase", "vs_type", "form", "wickets", "economy")
}


def _num(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value, default=0):
    number = _num(value)
    return int(number) if number is not None else default


def _percentiles(values: dict[str, float]) -> dict[str, float]:
    present = sorted((v, k) for k, v in values.items() if v is not None)
    size = len(present)
    if size == 0:
        return {}
    if size == 1:
        return {present[0][1]: 100.0}
    out: dict[str, float] = {}
    index = 0
    while index < size:
        end = index
        while end + 1 < size and present[end + 1][0] == present[index][0]:
            end += 1
        rank = (index + end) / 2
        score = 100.0 * rank / (size - 1)
        for _, key in present[index : end + 1]:
            out[key] = score
        index = end + 1
    return out


def _adjusted_percentiles(
    raw: dict[str, tuple[float | None, int]],
    prior: float,
    invert: bool = False,
    min_n: int = 0,
) -> dict[str, float]:
    """Shrink each rate toward the role median, then percentile it.

    Thin samples move to the middle instead of the extremes; invert flips
    lower-is-better metrics (economy, dot %, balls per wicket).
    """
    usable = {
        key: value
        for key, (value, count) in raw.items()
        if value is not None and count >= max(1, min_n)
    }
    if not usable:
        return {}
    middle = median(usable.values())
    shrunk = {
        key: middle + (raw[key][1] / (raw[key][1] + prior)) * (value - middle)
        for key, value in usable.items()
    }
    scores = _percentiles(shrunk)
    if invert:
        scores = {key: 100.0 - value for key, value in scores.items()}
    return scores


def _mix(parts, key):
    total_weight = 0.0
    acc = 0.0
    for scores, weight in parts:
        if key in scores:
            acc += scores[key] * weight
            total_weight += weight
    if total_weight == 0:
        return None
    return acc / total_weight


def _marks(percentile, maximum, floor=0.12):
    if percentile is None:
        return 0.0
    return round(maximum * (floor + (1.0 - floor) * percentile / 100.0), 1)


def _experience_rows(matches: int) -> tuple[int, str]:
    for threshold, marks in EXPERIENCE_TABLE:
        if matches >= threshold:
            label = {
                7: "Veteran",
                6: "Experienced",
                5: "Regular",
                4: "Developing",
                3: "Fringe",
                2: "Newcomer",
                1: "Debutant",
            }[marks]
            return marks, label
    return 0, "No matches"


def _split(payload: dict, name: str, block: str) -> dict:
    entry = (payload.get("splits") or {}).get(name) or {}
    return entry.get(block) or {}


def _load_scores(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("players") or payload.get("rows") or []
    return payload


def _batter_feature(row: dict, splits: dict) -> dict:
    career = _split({"splits": splits}, "career", "batting")
    balls = _int(career.get("balls"))
    innings = _int(career.get("innings"))
    matches = _int(career.get("matches")) or _int(row.get("matches"))
    runs = _num(career.get("runs"))
    average = _num(career.get("average"))
    strike_rate = _num(career.get("strike_rate"))
    fours = _int(career.get("fours"))
    sixes = _int(career.get("sixes"))
    boundary_pct = _num(career.get("boundary_pct"))
    dot_pct = _num(career.get("dot_pct"))
    if average is None and runs is not None and innings:
        average = runs / innings

    phases = {}
    for phase in ("powerplay", "middle", "death"):
        block = _split({"splits": splits}, phase, "batting")
        phase_balls = _int(block.get("balls"))
        phase_sr = _num(block.get("strike_rate"))
        if phase_balls >= 15 and phase_sr is not None:
            phases[phase] = (phase_sr, phase_balls)

    styles = {}
    for style in ("vs_pace", "vs_spin"):
        block = _split({"splits": splits}, style, "batting")
        style_balls = _int(block.get("balls"))
        style_sr = _num(block.get("strike_rate"))
        if style_balls >= 20 and style_sr is not None:
            styles[style] = (style_sr, style_balls)

    season = _split({"splits": splits}, "2026", "batting")
    season_balls = _int(season.get("balls"))
    season_sr = _num(season.get("strike_rate"))
    form_balls = _int(row.get("form2026_balls")) or season_balls
    form_impact = _num(row.get("form2026_impact100"))

    return {
        "role": "batter",
        "matches": matches,
        "innings": innings,
        "balls": balls,
        "volume": runs,
        "runs": runs,
        "wickets": None,
        "average": average,
        "strike_rate": strike_rate,
        "boundary_pct": boundary_pct,
        "dot_pct": dot_pct,
        "fours": fours,
        "sixes": sixes,
        "phases": phases,
        "styles": styles,
        "season_sr": (season_sr, season_balls) if season_balls >= 20 else None,
        "form_balls": form_balls,
        "form_impact": form_impact,
        "pressure_balls": _int(row.get("pressure_balls")),
        "impact100": _num(row.get("impact100")),
        "wpa100": _num(row.get("wpa100")),
        "delta": _num(row.get("delta")),
        "econ_above": None,
        "consistency": _num(row.get("consistency")),
        "stability": _num(row.get("stability")),
    }


def _bowler_feature(row: dict, splits: dict) -> dict:
    career = _split({"splits": splits}, "career", "bowling")
    balls = _int(career.get("legal_balls"))
    innings = _int(career.get("innings"))
    matches = _int(career.get("matches")) or _int(row.get("matches"))
    wickets = _num(career.get("wickets"))
    average = _num(career.get("average"))
    economy = _num(career.get("economy"))
    strike_rate = _num(career.get("strike_rate"))
    dot_pct = _num(career.get("dot_pct"))
    if strike_rate is None and balls and wickets:
        strike_rate = balls / wickets

    phases = {}
    for phase in ("powerplay", "middle", "death"):
        block = _split({"splits": splits}, phase, "bowling")
        phase_balls = _int(block.get("legal_balls"))
        phase_econ = _num(block.get("economy"))
        if phase_balls >= 15 and phase_econ is not None:
            phases[phase] = (phase_econ, phase_balls)

    styles = {}
    for style in ("vs_lhb", "vs_rhb"):
        block = _split({"splits": splits}, style, "bowling")
        style_balls = _int(block.get("legal_balls"))
        style_econ = _num(block.get("economy"))
        if style_balls >= 20 and style_econ is not None:
            styles[style] = (style_econ, style_balls)
    if not styles:
        for style in ("vs_pace", "vs_spin"):
            block = _split({"splits": splits}, style, "bowling")
            style_balls = _int(block.get("legal_balls"))
            style_econ = _num(block.get("economy"))
            if style_balls >= 20 and style_econ is not None:
                styles[style] = (style_econ, style_balls)

    season = _split({"splits": splits}, "2026", "bowling")
    season_balls = _int(season.get("legal_balls"))
    season_econ = _num(season.get("economy"))
    form_balls = _int(row.get("form2026_balls")) or season_balls
    form_impact = _num(row.get("form2026_impact100"))

    return {
        "role": "bowler",
        "matches": matches,
        "innings": innings,
        "balls": balls,
        "volume": wickets,
        "runs": None,
        "wickets": wickets,
        "average": average,
        "strike_rate": strike_rate,
        "economy": economy,
        "dot_pct": dot_pct,
        "boundary_pct": None,
        "phases": phases,
        "styles": styles,
        "season_econ": (season_econ, season_balls) if season_balls >= 20 else None,
        "form_balls": form_balls,
        "form_impact": form_impact,
        "pressure_balls": _int(row.get("pressure_balls")),
        "impact100": _num(row.get("impact100")),
        "wpa100": _num(row.get("wpa100")),
        "delta": _num(row.get("delta")),
        "econ_above": _num(row.get("economy_above_expected")),
        "consistency": _num(row.get("consistency")),
        "stability": _num(row.get("stability")),
    }


def _phase_percentiles(features: dict[str, dict], field: str, invert: bool) -> dict[str, dict[str, float]]:
    result = {}
    for phase in ("powerplay", "middle", "death"):
        raw = {
            key: feature["phases"][phase]
            for key, feature in features.items()
            if phase in feature["phases"]
        }
        result[phase] = _adjusted_percentiles(
            raw, prior=60, invert=invert, min_n=15
        )
    return result


def _style_percentiles(features: dict[str, dict], invert: bool) -> dict[str, dict[str, float]]:
    styles = set()
    for feature in features.values():
        styles.update(feature["styles"])
    result = {}
    for style in styles:
        raw = {
            key: feature["styles"][style]
            for key, feature in features.items()
            if style in feature["styles"]
        }
        result[style] = _adjusted_percentiles(
            raw, prior=60, invert=invert, min_n=20
        )
    return result


def _phase_score(feature: dict, tables: dict[str, dict[str, float]], key: str) -> float | None:
    weighted = 0.0
    total_balls = 0
    for phase, table in tables.items():
        if phase not in feature["phases"]:
            continue
        balls = feature["phases"][phase][1]
        if key in table:
            weighted += table[key] * balls
            total_balls += balls
    return weighted / total_balls if total_balls else None


def _style_score(feature: dict, tables: dict[str, dict[str, float]], key: str) -> float | None:
    weighted = 0.0
    total_balls = 0
    for style, table in tables.items():
        if style not in feature["styles"]:
            continue
        balls = feature["styles"][style][1]
        if key in table:
            weighted += table[key] * balls
            total_balls += balls
    return weighted / total_balls if total_balls else None


def _pressure_percentile(feature: dict, key: str, impact, wpa, delta, econ=None) -> float | None:
    parts = [
        (impact.get(key), 0.5),
        (wpa.get(key), 0.3),
        (econ.get(key) if econ is not None else delta.get(key), 0.2),
    ]
    total = sum(weight for value, weight in parts if value is not None)
    if not total:
        return None
    value = sum(score * weight for score, weight in parts if score is not None) / total
    reliability = feature["pressure_balls"] / (feature["pressure_balls"] + 150.0)
    return 50.0 + reliability * (value - 50.0)


def _form_percentile(feature: dict, impact_scores, improve_scores, key: str) -> float | None:
    parts = [(impact_scores, 0.6), (improve_scores, 0.4)]
    total = sum(weight for scores, weight in parts if key in scores)
    if not total:
        return None
    value = sum(scores[key] * weight for scores, weight in parts if key in scores) / total
    reliability = feature["form_balls"] / (feature["form_balls"] + 100.0)
    return 50.0 + reliability * (value - 50.0)


def _risk_label(sample_marks: float, experience_marks: int, pressure_pct) -> tuple[str, str]:
    sample_factor = sample_marks / 6.0
    if sample_factor < 0.4 or experience_marks <= 2 or (pressure_pct is not None and pressure_pct < 40):
        return (
            "High",
            "Thin or one-phase sample; treat the ranking as volatile until more pressure balls accumulate.",
        )
    if sample_factor < 0.75 or experience_marks <= 4:
        return (
            "Medium",
            "Reasonable sample but short of the full opportunity threshold; read alongside the ball count.",
        )
    return (
        "Low",
        "Matches, innings and ball volume clear the opportunity thresholds used by the rubric.",
    )


def build_batter(features: dict[str, dict]) -> dict[str, dict]:
    overall_parts = (
        _adjusted_percentiles(
            {k: (f["volume"], f["balls"]) for k, f in features.items()}, prior=0, min_n=60
        ),
        _adjusted_percentiles(
            {k: (f["average"], f["balls"]) for k, f in features.items()}, prior=150, min_n=60
        ),
        _adjusted_percentiles(
            {k: (f["strike_rate"], f["balls"]) for k, f in features.items()}, prior=150, min_n=60
        ),
    )
    boundary_scores = _adjusted_percentiles(
        {k: (f["boundary_pct"], f["balls"]) for k, f in features.items()}, prior=150, min_n=60
    )
    dot_scores = _adjusted_percentiles(
        {k: (f["dot_pct"], f["balls"]) for k, f in features.items()},
        prior=150, invert=True, min_n=60,
    )
    consistency_scores = _adjusted_percentiles(
        {k: (f["consistency"], f["balls"]) for k, f in features.items()}, prior=0, min_n=60
    )
    stability_scores = _adjusted_percentiles(
        {k: (f["stability"], f["balls"]) for k, f in features.items()}, prior=0, min_n=60
    )
    impact_scores = _adjusted_percentiles(
        {k: (f["impact100"], f["pressure_balls"]) for k, f in features.items()},
        prior=0, min_n=30,
    )
    wpa_scores = _adjusted_percentiles(
        {k: (f["wpa100"], f["pressure_balls"]) for k, f in features.items()},
        prior=0, min_n=30,
    )
    delta_scores = _adjusted_percentiles(
        {k: (f["delta"], f["pressure_balls"]) for k, f in features.items()},
        prior=0, min_n=30,
    )
    phase_tables = _phase_percentiles(features, "strike_rate", invert=False)
    style_tables = _style_percentiles(features, invert=False)
    form_impact = _adjusted_percentiles(
        {k: (f["form_impact"], f["form_balls"]) for k, f in features.items()},
        prior=0, min_n=20,
    )
    improvement = _adjusted_percentiles(
        {
            k: (f["season_sr"][0] - f["strike_rate"], f["form_balls"])
            for k, f in features.items()
            if f["season_sr"] and f["strike_rate"] is not None
        },
        prior=100, min_n=20,
    )

    results = {}
    for key, feature in features.items():
        if feature["balls"] < 1:
            continue
        overall = _mix(
            [(overall_parts[0], 0.4), (overall_parts[1], 0.3), (overall_parts[2], 0.3)],
            key,
        )
        pressure = _pressure_percentile(
            feature, key, impact_scores, wpa_scores, delta_scores
        )
        consistency = _mix(
            [(consistency_scores, 0.6), (stability_scores, 0.4)], key
        )
        boundary = boundary_scores.get(key)
        dot = dot_scores.get(key)
        phase = _phase_score(feature, phase_tables, key)
        vs_type = _style_score(feature, style_tables, key)
        form = _form_percentile(feature, form_impact, improvement, key)

        experience_marks, experience_label = _experience_rows(feature["matches"])
        sample_marks = round(
            6.0
            * min(
                1.0,
                feature["innings"] / 20.0,
                feature["balls"] / 300.0,
                feature["matches"] / 15.0,
            ),
            1,
        )

        criteria = [
            ("overall", _marks(overall, 15), 15),
            ("pressure", _marks(pressure, 18), 18),
            ("consistency", _marks(consistency, 13), 13),
            ("boundary", _marks(boundary, 10), 10),
            ("dot_control", _marks(dot, 8), 8),
            ("phase", _marks(phase, 10), 10),
            ("vs_type", _marks(vs_type, 8), 8),
            ("form", _marks(form, 5), 5),
            ("experience", float(experience_marks), 7),
            ("sample", sample_marks, 6),
        ]
        labels = dict((k, (label, maximum)) for k, label, maximum in WEIGHTS["batter"])
        total = round(sum(score for _, score, _ in criteria), 1)
        skill = sum(score for key_, score, maximum in criteria if key_ in SKILL_KEYS)
        skill_max = sum(maximum for key_, _, maximum in criteria if key_ in SKILL_KEYS)

        results[key] = {
            "player_type": "batter",
            "total": total,
            "role_fit": round(100.0 * skill / skill_max, 1) if skill_max else 0.0,
            "criteria": [
                {
                    "key": key_,
                    "label": labels[key_][0],
                    "score": score,
                    "max": maximum,
                }
                for key_, score, maximum in criteria
            ],
            "matches": feature["matches"],
            "innings": feature["innings"],
            "runs": int(feature["runs"] or 0),
            "wickets": None,
            "average": round(feature["average"], 2) if feature["average"] is not None else None,
            "strike_rate": round(feature["strike_rate"], 1) if feature["strike_rate"] is not None else None,
            "fours": feature["fours"],
            "sixes": feature["sixes"],
            "balls_per_boundary": (
                round(feature["balls"] / (feature["fours"] + feature["sixes"]), 2)
                if feature["fours"] + feature["sixes"]
                else None
            ),
            "experience": experience_label,
            "experience_marks": experience_marks,
            "sample_marks": sample_marks,
            "pressure_percentile": round(pressure, 1) if pressure is not None else None,
        }
    return results


def build_bowler(features: dict[str, dict]) -> dict[str, dict]:
    overall_parts = (
        _adjusted_percentiles(
            {k: (f["wickets"], f["balls"]) for k, f in features.items()}, prior=0, min_n=60
        ),
        _adjusted_percentiles(
            {k: (f["average"], f["balls"]) for k, f in features.items()},
            prior=150, invert=True, min_n=60,
        ),
        _adjusted_percentiles(
            {k: (f["economy"], f["balls"]) for k, f in features.items()},
            prior=150, invert=True, min_n=60,
        ),
    )
    wicket_strike = _adjusted_percentiles(
        {k: (f["strike_rate"], f["balls"]) for k, f in features.items()},
        prior=150, invert=True, min_n=60,
    )
    wicket_count = _adjusted_percentiles(
        {k: (f["wickets"], f["balls"]) for k, f in features.items()}, prior=0, min_n=60
    )
    economy_scores = _adjusted_percentiles(
        {k: (f["economy"], f["balls"]) for k, f in features.items()},
        prior=150, invert=True, min_n=60,
    )
    dot_scores = _adjusted_percentiles(
        {k: (f["dot_pct"], f["balls"]) for k, f in features.items()}, prior=150, min_n=60
    )
    consistency_scores = _adjusted_percentiles(
        {k: (f["consistency"], f["balls"]) for k, f in features.items()}, prior=0, min_n=60
    )
    stability_scores = _adjusted_percentiles(
        {k: (f["stability"], f["balls"]) for k, f in features.items()}, prior=0, min_n=60
    )
    impact_scores = _adjusted_percentiles(
        {k: (f["impact100"], f["pressure_balls"]) for k, f in features.items()},
        prior=0, min_n=30,
    )
    wpa_scores = _adjusted_percentiles(
        {k: (f["wpa100"], f["pressure_balls"]) for k, f in features.items()},
        prior=0, min_n=30,
    )
    econ_above_scores = _adjusted_percentiles(
        {k: (f["econ_above"], f["pressure_balls"]) for k, f in features.items()},
        prior=0, invert=True, min_n=30,
    )
    phase_tables = _phase_percentiles(features, "economy", invert=True)
    style_tables = _style_percentiles(features, invert=True)
    form_impact = _adjusted_percentiles(
        {k: (f["form_impact"], f["form_balls"]) for k, f in features.items()},
        prior=0, min_n=20,
    )
    improvement = _adjusted_percentiles(
        {
            k: (f["economy"] - f["season_econ"][0], f["form_balls"])
            for k, f in features.items()
            if f["season_econ"] and f["economy"] is not None
        },
        prior=100, min_n=20,
    )

    results = {}
    for key, feature in features.items():
        if feature["balls"] < 1:
            continue
        overall = _mix(
            [(overall_parts[0], 0.35), (overall_parts[1], 0.3), (overall_parts[2], 0.35)],
            key,
        )
        pressure = _pressure_percentile(
            feature, key, impact_scores, wpa_scores, econ_above_scores
        )
        wickets = _mix(
            [(wicket_strike, 0.6), (wicket_count, 0.4)], key
        )
        economy = economy_scores.get(key)
        dot = dot_scores.get(key)
        consistency = _mix(
            [(consistency_scores, 0.6), (stability_scores, 0.4)], key
        )
        phase = _phase_score(feature, phase_tables, key)
        vs_type = _style_score(feature, style_tables, key)
        form = _form_percentile(feature, form_impact, improvement, key)

        experience_marks, experience_label = _experience_rows(feature["matches"])
        sample_marks = round(
            6.0
            * min(
                1.0,
                feature["innings"] / 15.0,
                feature["balls"] / 300.0,
                feature["matches"] / 15.0,
            ),
            1,
        )

        criteria = [
            ("overall", _marks(overall, 15), 15),
            ("pressure", _marks(pressure, 18), 18),
            ("wickets", _marks(wickets, 13), 13),
            ("economy", _marks(economy, 10), 10),
            ("dot_control", _marks(dot, 8), 8),
            ("consistency", _marks(consistency, 10), 10),
            ("phase", _marks(phase, 8), 8),
            ("vs_type", _marks(vs_type, 5), 5),
            ("form", _marks(form, 5), 5),
            ("experience", float(experience_marks), 7),
            ("sample", sample_marks, 6),
        ]
        labels = dict((k, (label, maximum)) for k, label, maximum in WEIGHTS["bowler"])
        total = round(sum(score for _, score, _ in criteria), 1)
        skill = sum(score for key_, score, maximum in criteria if key_ in SKILL_KEYS)
        skill_max = sum(maximum for key_, _, maximum in criteria if key_ in SKILL_KEYS)

        results[key] = {
            "player_type": "bowler",
            "total": total,
            "role_fit": round(100.0 * skill / skill_max, 1) if skill_max else 0.0,
            "criteria": [
                {
                    "key": key_,
                    "label": labels[key_][0],
                    "score": score,
                    "max": maximum,
                }
                for key_, score, maximum in criteria
            ],
            "matches": feature["matches"],
            "innings": feature["innings"],
            "runs": None,
            "wickets": int(feature["wickets"] or 0),
            "average": round(feature["average"], 2) if feature["average"] is not None else None,
            "economy": round(feature["economy"], 2) if feature["economy"] is not None else None,
            "dot_pct": round(feature["dot_pct"], 1) if feature["dot_pct"] is not None else None,
            "experience": experience_label,
            "experience_marks": experience_marks,
            "sample_marks": sample_marks,
            "pressure_percentile": round(pressure, 1) if pressure is not None else None,
        }
    return results


def _report(results: dict[str, dict]) -> None:
    for key, entry in results.items():
        criteria = entry["criteria"]
        ranked = sorted(
            (c for c in criteria if c["key"] in SKILL_KEYS),
            key=lambda c: c["score"] / c["max"],
            reverse=True,
        )
        strengths = [
            f"{c['label']} {c['score']:.1f}/{c['max']} ({100 * c['score'] / c['max']:.0f}%)"
            for c in ranked[:2]
            if c["score"] / c["max"] >= 0.65
        ]
        weaknesses = [
            f"{c['label']} {c['score']:.1f}/{c['max']} ({100 * c['score'] / c['max']:.0f}%)"
            for c in sorted(
                (c for c in criteria if c["key"] in SKILL_KEYS),
                key=lambda c: c["score"] / c["max"],
            )[:2]
            if c["score"] / c["max"] <= 0.45
        ]
        risk, reason = _risk_label(
            entry["sample_marks"],
            entry["experience_marks"],
            entry["pressure_percentile"],
        )
        entry["strengths"] = strengths
        entry["weaknesses"] = weaknesses
        entry["risk"] = risk
        entry["risk_reason"] = reason


def build(derived_dir: Path) -> dict:
    all_results: dict[str, dict] = {}
    for role, filename, builder, feature_fn in (
        ("batter", "batters.json", build_batter, _batter_feature),
        ("bowler", "bowlers.json", build_bowler, _bowler_feature),
    ):
        rows = _load_scores(derived_dir / "scores" / filename)
        features: dict[str, dict] = {}
        names: dict[str, str] = {}
        for row in rows:
            key = str(row.get("player_id"))
            if not key or key == "None":
                continue
            stats_path = derived_dir / "stats" / f"{key}.json"
            splits = {}
            if stats_path.exists():
                try:
                    splits = json.loads(stats_path.read_text(encoding="utf-8")).get("splits") or {}
                except (OSError, json.JSONDecodeError):
                    splits = {}
            features[key] = feature_fn(row, splits)
            names[key] = str(row.get("name") or "").strip()

        role_results = builder(features)
        ordered = sorted(role_results.items(), key=lambda item: -item[1]["total"])
        for rank, (key, entry) in enumerate(ordered, start=1):
            entry["rank"] = rank
            entry["player_id"] = key
            entry["name"] = names.get(key, "")
            all_results[f"{role}:{key}"] = entry
        _report(role_results)

    players = dict(
        sorted(
            all_results.items(),
            key=lambda item: (item[1]["player_type"], item[1]["rank"]),
        )
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scale": 100,
        "weights": {
            role: [{"key": key, "label": label, "max": maximum} for key, label, maximum in items]
            for role, items in WEIGHTS.items()
        },
        "experience_table": [
            {"min_matches": threshold, "marks": marks}
            for threshold, marks in EXPERIENCE_TABLE
        ],
        "count": len(players),
        "players": players,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--derived", default=str(ROOT / "data_derived"))
    args = parser.parse_args()
    derived = Path(args.derived)
    payload = build(derived)
    out = derived / "scores" / "rubric.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    top = sorted(
        (
            entry
            for entry in payload["players"].values()
        ),
        key=lambda entry: (entry["player_type"], entry["rank"]),
    )
    batters = [e for e in top if e["player_type"] == "batter"][:5]
    bowlers = [e for e in top if e["player_type"] == "bowler"][:5]
    print(f"Wrote {out} ({payload['count']} players)")
    print("Top batters:", ", ".join(f"{e['name']} {e['total']}" for e in batters))
    print("Top bowlers:", ", ".join(f"{e['name']} {e['total']}" for e in bowlers))


if __name__ == "__main__":
    main()
