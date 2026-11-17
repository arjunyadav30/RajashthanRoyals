RR 2027 ENHANCED PLAYER + MATCHUP ANALYSIS
Generated from the two uploaded candidate CSVs and the supplied Data Pack.zip.

INPUT CANDIDATES
- Batters: 524 rows
- Bowlers: 363 rows
- Unique player IDs across both lists: 572
- No missing player IDs in either uploaded CSV.
- Pakistan-mapped candidates in these two lists: 2 role rows (one player, Zaman Khan, appears in both role files).

SOURCE DATA SCOPE
- Ball-by-ball rows used: 200,961 (innings 1 and 2 only; super-over/other innings excluded)
- Matches with usable ball-by-ball: 867
- IPL matches with usable ball-by-ball: 367
- T20I matches with usable ball-by-ball: 500
- IPL participation window: IPL 2022 through IPL 2026, using the supplied playing_eleven file and is_played=True.
- The supplied Data Pack has IPL 2022-2026 only; it cannot prove whether a player appeared in IPL before 2022.

IPL STATUS CLASSIFICATION
- PLAYED_IN_2026: actual playing-XI appearance in supplied IPL 2026 data.
- PLAYED_2022_2025_ONLY: appearance in supplied IPL 2022-2025 data, no IPL 2026 appearance found in this candidate list.
- NO_IPL_APPEARANCE_IN_SUPPLIED_2022_2026_DATA: no appearance found in supplied IPL seasons 2022-2026.
IMPORTANT: "NO_IPL_APPEARANCE_IN_SUPPLIED_2022_2026_DATA" does NOT mean the player never played IPL. Older seasons, auction contracts, current availability and injury status are not verified.

MATCHUP QUALITY MODEL
1) Build independent player-quality percentiles from the raw ball-by-ball dataset.
2) Batter quality:
   - minimum 30 legal balls
   - 35% strike-rate percentile
   - 25% batting-average percentile
   - 20% boundary-rate percentile
   - 20% dot-ball-avoidance percentile
   - shrinkage priors: 40 balls at 130 SR, 2 dismissals at average 22, 40 balls at 18% boundary rate and 35% dot rate.
3) Bowler quality:
   - minimum 60 legal balls
   - 30% economy percentile (lower economy is better)
   - 30% wickets per 100 legal balls percentile
   - 20% dot-ball percentage percentile
   - 20% boundary-prevention percentile (lower boundary concession is better)
   - shrinkage priors: 60 balls at 8.5 economy, 5.5 wickets/100, 35% dot rate and 18% boundary rate conceded.
4) Quality score is the percentile rank (0-100) of the weighted composite among players meeting the minimum sample threshold.
5) Top-quartile opponents are players with derived quality score >=75.
6) Batter performance against top-quartile bowlers:
   - runs, legal balls, strike rate, average, boundary %, dot %, dismissals, matches.
   - performance score = 35% SR percentile + 25% average percentile + 20% boundary-rate percentile + 20% dot-avoidance percentile.
7) Bowler performance against top-quartile batters:
   - runs conceded, legal balls, wickets, economy, wickets/100, dot %, boundary concession.
   - performance score = 30% economy percentile (lower is better) + 30% wickets/100 percentile + 20% dot % percentile + 20% boundary-prevention percentile.
8) Matchup score = 40% average quality of opponents faced + 60% performance score against top-quartile opponents.
9) Minimum matchup sample to apply score: 20 legal balls against top-quartile opponents.
10) Enhanced rating = 90% existing source rating_100 + 10% matchup score. If the minimum matchup sample is not met, enhanced rating remains the original rating_100 and matchup status is marked LOW_OR_MISSING_MATCHUP_SAMPLE. This avoids penalizing players for insufficient matchup data.
11) IPL-only matchup score is calculated separately using IPL deliveries only; it is N/A when sample is insufficient.

DELIVERY DEFINITIONS
- Legal balls exclude wides and Overstep (no-ball) deliveries.
- Batter runs use the runs column (runs off the bat).
- Bowler runs conceded include batter runs plus wide/no-ball extras; byes and leg-byes are not charged to bowler.
- Bowler wickets include Caught, Bowled, LBW, Stump and Hit Wicket. Run-outs are not credited as bowler wickets.
- Batter dot ball means no runs scored by the batting team on a legal delivery.
- Bowler dot ball means no runs charged to the bowler on a legal delivery.

SIGNED / MINUS VALUES
- Existing delta = impact100 - normal_impact.
- Positive delta: pressure impact above normal.
- Negative delta: pressure impact below normal. It is not a negative player rating or a missing ID.
- For bowlers, negative economy_above_expected means fewer runs conceded than expected (better); positive means more runs conceded than expected (worse).
- A dash in an ID field in an older list means ID was unavailable in that particular mapping; the current two uploaded CSVs have no missing player IDs.

PAKISTAN EXCLUSION
- Pakistan national-team mapped player IDs from the supplied competition_team_player_mapping are excluded from the Non-Pakistan ranked candidate files.
- They are retained in Pakistan_Excluded_From_Rankings.csv for audit.
- Historical opponent-quality calculations use all relevant T20/T20I deliveries; the exclusion applies to candidate rankings, not the historical opponent context.

FILES
- All_Batters_Enhanced_Full.csv / All_Bowlers_Enhanced_Full.csv: every uploaded candidate, including eligibility flag.
- Ranked_Batters_Non_Pakistan.csv / Ranked_Bowlers_Non_Pakistan.csv: eligible non-Pakistan candidate rankings.
- Players_No_IPL_Record_2022_2026_NonPakistan.csv: separate non-Pakistan list with no IPL appearance found in supplied 2022-2026 seasons.
- Players_With_IPL_Record_2022_2026_NonPakistan.csv: non-Pakistan players with an IPL playing-XI appearance in supplied 2022-2026 seasons.
- Batter_vs_Bowler_Matchup_Detail.csv: pair-by-pair batter vs bowler records, split IPL and T20I.
- Derived_Batter_Quality_Pool.csv / Derived_Bowler_Quality_Pool.csv: quality ratings used to judge opponent strength.
- All_Players_Combined_Master_NonPakistan.csv: one row per player ID with batter/bowler summary fields.
- Pakistan_Excluded_From_Rankings.csv: Pakistan-mapped candidates kept separate.

LIMITATIONS
- These are data-derived ratings, not guarantees of future performance.
- Dataset does not establish 2027 auction registration, contract status, availability, injury status or team selection.
- Players with small matchup samples have no matchup adjustment applied.
- IPL experience classification is limited to supplied IPL 2022-2026 records.
