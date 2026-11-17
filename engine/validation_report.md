# Engine vs external ranking CSV validation

The reference CSVs are used only for a sanity check. The engine scores are fitted
from the full 2022-01-22 to 2026-11-01 data pack with state-based leverage and are
not tuned or forced to reproduce these tables.

## Batters

- Reference rows: 96; matched to engine universe: 96; qualified in both: 93.
- Spearman (reference rank vs engine qualified rank): 0.539.
- Top-20 overlap: 10/20 (50.0%).

| Player | Old rank | Engine qualified rank | Engine all rank | Pressure balls (engine / old) | Score | Flag |
| --- | --- | --- | --- | --- | --- | --- |
| Harry Brook | 18 | 83 | 695 | 167 / 179 | 47.04 | WIDE |
| Faf du Plessis | 26 | 88 | 755 | 349 / 290 | 46.02 | WIDE |
| Liam Livingstone | 65 | 5 | 6 | 244 / 209 | 56.67 | WIDE |
| Dewald Brevis | 84 | 25 | 86 | 164 / 152 | 52.11 | WIDE |
| Mitchell Marsh | 19 | 74 | 589 | 476 / 531 | 48.11 | WIDE |
| Nitish Rana | 32 | 87 | 752 | 241 / 235 | 46.16 | WIDE |
| Ishan Kishan | 8 | 62 | 477 | 609 / 660 | 49.0 | WIDE |
| William Jacks | 96 | 43 | 170 | 170 / 199 | 50.76 | WIDE |

Rank gaps usually come from three sources: (1) the old table's pressure flag and
the frozen 75th-percentile state-based leverage flag select different deliveries;
(2) the old tables cover only players above their own minimum-sample cut, while
the engine ranks the full universe; (3) empirical-Bayes shrinkage moves small
samples toward the role average, so a high raw rate on few balls does not rank
near the top. Differences are expected and are not forced to zero.

## Bowlers

- Reference rows: 101; matched to engine universe: 101; qualified in both: 92.
- Spearman (reference rank vs engine qualified rank): 0.467.
- Top-20 overlap: 7/20 (35.0%).

| Player | Old rank | Engine qualified rank | Engine all rank | Pressure balls (engine / old) | Score | Flag |
| --- | --- | --- | --- | --- | --- | --- |
| Ravindra Jadeja | 11 | 87 | 575 | 282 / 295 | 45.25 | WIDE |
| Akeal Hosein | 79 | 7 | 24 | 411 / 428 | 55.3 | WIDE |
| Blessing Muzarabani | 93 | 27 | 179 | 203 / 199 | 52.01 | WIDE |
| Mohsin Khan | 28 | 92 | 583 | 203 / 208 | 43.41 | WIDE |
| Trent Boult | 81 | 20 | 109 | 476 / 455 | 52.84 | WIDE |
| Mustafizur Rahman | 18 | 77 | 544 | 396 / 382 | 46.78 | WIDE |
| Rahul Chahar | 96 | 40 | 292 | 198 / 202 | 50.5 | WIDE |
| Mujeeb Ur Rahman | 7 | 63 | 458 | 233 / 250 | 48.71 | WIDE |

Rank gaps usually come from three sources: (1) the old table's pressure flag and
the frozen 75th-percentile state-based leverage flag select different deliveries;
(2) the old tables cover only players above their own minimum-sample cut, while
the engine ranks the full universe; (3) empirical-Bayes shrinkage moves small
samples toward the role average, so a high raw rate on few balls does not rank
near the top. Differences are expected and are not forced to zero.

## Reading the comparison

The reference tables were produced outside this project and use a different pressure
definition. A moderate positive correlation is a useful sanity check; a perfect match
would indicate copying rather than independent estimation. Low correlations, especially
for bowlers, are consistent with the low split-half reliability reported in `meta.json`.
