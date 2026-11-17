"""Compare the engine scores with the external reference rankings (not a target)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from precompute import _canon_id

REFERENCE_FILES = (
    ("All_Batter_Rankings.csv", "batter"),
    ("All_Bowler_Rankings.csv", "bowler"),
)


def _spearman(a: pd.Series, b: pd.Series) -> float | None:
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if len(joined) < 3:
        return None
    return float(joined["a"].rank().corr(joined["b"].rank()))


def _load_reference(rankings_dir: Path):
    frames = {}
    for filename, role in REFERENCE_FILES:
        path = rankings_dir / filename
        if not path.exists():
            continue
        df = pd.read_csv(path)
        df["pid"] = df["player_id"].map(_canon_id)
        df = df[df["pid"].notna()]
        frames[role] = df
    return frames


def validate(engine_batters: pd.DataFrame, engine_bowlers: pd.DataFrame, rankings_dir: Path, out_path: Path):
    references = _load_reference(Path(rankings_dir))
    summary = {}
    lines = [
        "# Engine vs external ranking CSV validation",
        "",
        "The reference CSVs are used only for a sanity check. The engine scores are fitted",
        "from the full 2022-01-22 to 2026-11-01 data pack with state-based leverage and are",
        "not tuned or forced to reproduce these tables.",
        "",
    ]
    for role, engine in (("batter", engine_batters), ("bowler", engine_bowlers)):
        reference = references.get(role)
        if reference is None or reference.empty:
            summary[role] = {"available": False}
            lines.append(f"## {role.title()}s\n\nReference CSV not available.\n")
            continue
        ours = engine[
            [
                "player_id",
                "name",
                "all_rank",
                "qualified_rank",
                "qualification_status",
                "score",
                "pressure_balls",
                "eb_weight",
                "SAMPLE_FLAG",
            ]
        ].rename(
            columns={
                "player_id": "eng_pid",
                "name": "eng_name",
                "all_rank": "eng_all_rank",
                "qualified_rank": "eng_qualified_rank",
                "qualification_status": "eng_status",
                "score": "eng_score",
                "pressure_balls": "eng_pressure_balls",
                "eb_weight": "eng_eb_weight",
                "SAMPLE_FLAG": "eng_flag",
            }
        )
        ours["eng_pid"] = ours["eng_pid"].astype(str)
        merged = reference.merge(ours, left_on="pid", right_on="eng_pid", how="inner")
        both = merged[merged["eng_status"].eq("QUALIFIED")]
        rho = _spearman(both["rank"], both["eng_qualified_rank"])
        top_old = set(reference.nsmallest(20, "rank")["pid"])
        top_new = set(engine[engine["qualification_status"].eq("QUALIFIED")].head(20)["player_id"].astype(str))
        overlap = len(top_old & top_new)
        diffs = both.assign(rank_diff=both["rank"] - both["eng_qualified_rank"]).sort_values(
            "rank_diff", key=lambda s: s.abs(), ascending=False
        ).head(8)
        summary[role] = {
            "available": True,
            "reference_players": int(len(reference)),
            "matched": int(len(merged)),
            "qualified_matched": int(len(both)),
            "spearman_rank": round(rho, 3) if rho is not None else None,
            "top20_overlap": int(overlap),
            "top20_overlap_pct": round(100.0 * overlap / 20.0, 1),
            "largest_rank_gaps": [
                {
                    "name": row["eng_name"],
                    "old_rank": int(row["rank"]),
                    "engine_qualified_rank": int(row["eng_qualified_rank"]),
                    "engine_all_rank": int(row["eng_all_rank"]),
                    "engine_pressure_balls": int(row["eng_pressure_balls"]),
                    "old_pressure_balls": int(row["pressure_balls"]) if pd.notna(row["pressure_balls"]) else None,
                    "engine_score": float(row["eng_score"]),
                    "sample_flag": row["eng_flag"],
                }
                for _, row in diffs.iterrows()
            ],
        }
        lines += [
            f"## {role.title()}s",
            "",
            f"- Reference rows: {len(reference)}; matched to engine universe: {len(merged)}; qualified in both: {len(both)}.",
            f"- Spearman (reference rank vs engine qualified rank): {summary[role]['spearman_rank']}.",
            f"- Top-20 overlap: {overlap}/20 ({summary[role]['top20_overlap_pct']}%).",
            "",
            "| Player | Old rank | Engine qualified rank | Engine all rank | Pressure balls (engine / old) | Score | Flag |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for item in summary[role]["largest_rank_gaps"]:
            lines.append(
                f"| {item['name']} | {item['old_rank']} | {item['engine_qualified_rank']} | "
                f"{item['engine_all_rank']} | {item['engine_pressure_balls']} / {item['old_pressure_balls']} | "
                f"{item['engine_score']} | {item['sample_flag']} |"
            )
        lines += [
            "",
            "Rank gaps usually come from three sources: (1) the old table's pressure flag and",
            "the frozen 75th-percentile state-based leverage flag select different deliveries;",
            "(2) the old tables cover only players above their own minimum-sample cut, while",
            "the engine ranks the full universe; (3) empirical-Bayes shrinkage moves small",
            "samples toward the role average, so a high raw rate on few balls does not rank",
            "near the top. Differences are expected and are not forced to zero.",
            "",
        ]
    lines += [
        "## Reading the comparison",
        "",
        "The reference tables were produced outside this project and use a different pressure",
        "definition. A moderate positive correlation is a useful sanity check; a perfect match",
        "would indicate copying rather than independent estimation. Low correlations, especially",
        "for bowlers, are consistent with the low split-half reliability reported in `meta.json`.",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return summary
