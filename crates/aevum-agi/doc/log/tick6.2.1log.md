(.venv) tsoikwailap@TSOIdeMac-Studio opus_agi % python mutator_daemon.py --poll-interval 30
[mutator] Slow Loop starting (TICK 6.1 + 6.2).
[mutator] model=qwen3.5:35b-a3b timeout=240s poll=30.0s
[mutator] Recipe version: baseline-v1
[mutator] Islands: good=candidate_pool/island_good, explore=candidate_pool/island_explore

[mutator] Mutation triggered: outer_loop
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.400 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 97.9s
[llm-nas] Patch rejected: identity mutation (no actual change).
[mutator] AST patch validation failed -- discarding.

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.384 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 60.2s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 71 new lines)
[mutator] Candidate #1 queued: candidate_1775091421584.py (60.2s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.376 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 57.7s
[llm-nas] Patch rejected: identity mutation (no actual change).
[mutator] AST patch validation failed -- discarding.

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.392 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 88.1s
[llm-nas] Patch rejected: identity mutation (no actual change).
[mutator] AST patch validation failed -- discarding.

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.384 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 58.2s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 67 new lines)
[mutator] Candidate #2 queued: candidate_1775091715668.py (58.2s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.376 vel_z=-0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 90.0s
[llm-nas] Patch rejected: identity mutation (no actual change).
[mutator] AST patch validation failed -- discarding.

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.384 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 90.7s
[llm-nas] Patch rejected: identity mutation (no actual change).
[mutator] AST patch validation failed -- discarding.


[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.400 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 59.3s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 70 new lines)
[mutator] Candidate #3 queued: candidate_1775092045849.py (59.3s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.392 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 31.4s
[llm-nas] AST patch: replacing ['MitoticTransformerBlock'] (1 segment(s), 35 new lines)
[mutator] Candidate #4 queued: candidate_1775092107318.py (31.4s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.400 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected




(.venv) tsoikwailap@TSOIdeMac-Studio opus_agi % python env_stream.py | python evaluator_daemon.py --threshold 0.10
[evaluator] Fast Loop starting (TICK 6.1 + 6.2). Ctrl+C to stop.
[evaluator] threshold=0.1, device=cpu
[evaluator] Candidate pool: agi_workspace/candidate_pool
[evaluator] Islands: good=candidate_pool/island_good, explore=candidate_pool/island_explore
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2058)
[island] Archived to candidate_pool/island_good/elite_0642976_1775091224254.py
[evaluator tick 4780] B=1 epi=0.1637 gen=642976 elapsed=0.86s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2059)
[island] Archived to candidate_pool/island_good/elite_0642977_1775091226361.py
[evaluator tick 4781] B=1 epi=0.1630 gen=642977 elapsed=0.15s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2060)
[island] Archived to candidate_pool/island_good/elite_0642978_1775091227292.py
[evaluator tick 4782] B=1 epi=0.1587 gen=642978 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2061)
[island] Archived to candidate_pool/island_good/elite_0642979_1775091229847.py
[evaluator tick 4783] B=1 epi=0.1544 gen=642979 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2062)
[island] Archived to candidate_pool/island_good/elite_0642980_1775091230786.py
[evaluator tick 4784] B=1 epi=0.1659 gen=642980 elapsed=0.15s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2063)
[island] Archived to candidate_pool/island_good/elite_0642981_1775091233751.py
[evaluator tick 4785] B=1 epi=0.1550 gen=642981 elapsed=0.18s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2064)
[island] Archived to candidate_pool/island_good/elite_0642982_1775091235883.py
[evaluator tick 4786] B=1 epi=0.1601 gen=642982 elapsed=0.16s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2065)
[island] Archived to candidate_pool/island_good/elite_0642983_1775091237234.py
[evaluator tick 4787] B=1 epi=0.1482 gen=642983 elapsed=0.19s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2066)
[island] Archived to candidate_pool/island_good/elite_0642984_1775091239942.py
[evaluator tick 4788] B=1 epi=0.1579 gen=642984 elapsed=0.18s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2067)
[island] Archived to candidate_pool/island_good/elite_0642985_1775091242074.py
[evaluator tick 4789] B=1 epi=0.1551 gen=642985 elapsed=0.17s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2068)
[island] Archived to candidate_pool/island_good/elite_0642986_1775091243279.py
[evaluator tick 4790] B=1 epi=0.1629 gen=642986 elapsed=0.15s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2069)
[island] Archived to candidate_pool/island_good/elite_0642987_1775091246034.py
[evaluator tick 4791] B=1 epi=0.1563 gen=642987 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2070)
[island] Archived to candidate_pool/island_good/elite_0642988_1775091248806.py
[evaluator tick 4792] B=1 epi=0.1616 gen=642988 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2071)
[island] Archived to candidate_pool/island_good/elite_0642989_1775091250411.py
[evaluator tick 4793] B=1 epi=0.1607 gen=642989 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2072)
[island] Archived to candidate_pool/island_good/elite_0642990_1775091252741.py
[evaluator tick 4794] B=1 epi=0.1608 gen=642990 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2073)
[island] Archived to candidate_pool/island_good/elite_0642991_1775091255260.py
[evaluator tick 4795] B=1 epi=0.1605 gen=642991 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2074)
[island] Archived to candidate_pool/island_good/elite_0642992_1775091258065.py
[evaluator tick 4796] B=1 epi=0.1563 gen=642992 elapsed=0.11s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2075)
[island] Archived to candidate_pool/island_good/elite_0642993_1775091259258.py
[evaluator tick 4797] B=1 epi=0.1569 gen=642993 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2076)
[island] Archived to candidate_pool/island_good/elite_0642994_1775091261969.py
[evaluator tick 4798] B=1 epi=0.1565 gen=642994 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2077)
[island] Archived to candidate_pool/island_good/elite_0642995_1775091264720.py
[evaluator tick 4799] B=1 epi=0.1655 gen=642995 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL


[evaluator tick 4811] B=1 epi=0.1628 gen=643007 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 2090)
[island] Archived to candidate_pool/island_good/elite_0643008_1775091293590.py
[evaluator tick 4812] B=1 epi=0.1649 gen=643008 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2091)
[island] Archived to candidate_pool/island_good/elite_0643009_1775091294869.py
[evaluator tick 4813] B=1 epi=0.1627 gen=643009 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2092)
[island] Archived to candidate_pool/island_good/elite_0643010_1775091297659.py
[evaluator tick 4814] B=1 epi=0.1607 gen=643010 elapsed=0.15s evo=0.400 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2093)
[island] Archived to candidate_pool/island_good/elite_0643011_1775091300338.py
[evaluator tick 4815] B=1 epi=0.1428 gen=643011 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2094)
[island] Archived to candidate_pool/island_good/elite_0643012_1775091301549.py
[evaluator tick 4816] B=1 epi=0.1496 gen=643012 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2095)
[island] Archived to candidate_pool/island_good/elite_0643013_1775091304136.py
[evaluator tick 4817] B=1 epi=0.1597 gen=643013 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2096)
[island] Archived to candidate_pool/island_good/elite_0643014_1775091306829.py



[evaluator tick 4826] B=1 epi=0.1548 gen=643022 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 1.00 > 0.3 — scaling threshold to 0.1150 (level 2105)
[island] Archived to candidate_pool/island_good/elite_0643023_1775091325360.py
[evaluator tick 4827] B=1 epi=0.1584 gen=643023 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL STAGNANT
[topology-guard] Blind mutation depth mismatch -- safe failure.
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2106)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[evaluator tick 4828] B=0 epi=0.0000 gen=643024 elapsed=0.06s evo=0.392 vel=-0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2107)
[island] Archived to candidate_pool/island_good/elite_0643024_1775091329136.py
[evaluator tick 4829] B=1 epi=0.1528 gen=643024 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2108)
[island] Archived to candidate_pool/island_good/elite_0643025_1775091331836.py
[evaluator tick 4830] B=1 epi=0.1647 gen=643025 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
[topology-guard] Blind mutation depth mismatch -- safe failure.
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2109)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[evaluator tick 4831] B=0 epi=0.0000 gen=643026 elapsed=0.06s evo=0.384 vel=-0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2110)
[island] Archived to candidate_pool/island_good/elite_0643026_1775091335176.py
[evaluator tick 4832] B=1 epi=0.1541 gen=643026 elapsed=0.13s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT


[evaluator tick 4841] B=1 epi=0.1626 gen=643035 elapsed=0.13s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2120)
[island] Archived to candidate_pool/island_good/elite_0643036_1775091358376.py
[evaluator tick 4842] B=1 epi=0.1462 gen=643036 elapsed=0.14s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
[topology-guard] Blind mutation depth mismatch -- safe failure.
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 2121)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[evaluator tick 4843] B=0 epi=0.0000 gen=643037 elapsed=0.09s evo=0.376 vel=-0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 2122)
[island] Archived to candidate_pool/island_good/elite_0643037_1775091364204.py
[evaluator tick 4844] B=1 epi=0.1628 gen=643037 elapsed=0.12s evo=0.376 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 2123)
[island] Archived to candidate_pool/island_good/elite_0643038_1775091365328.py
[evaluator tick 4845] B=1 epi=0.1477 gen=643038 elapsed=0.13s evo=0.376 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 2124)
[island] Archived to candidate_pool/island_good/elite_0643039_1775091368155.py
[evaluator tick 4846] B=1 epi=0.1577 gen=643039 elapsed=0.12s evo=0.376 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 2125)
[island] Archived to candidate_pool/island_good/elite_0643040_1775091370977.py
[evaluator tick 4847] B=1 epi=0.1579 gen=643040 elapsed=0.13s evo=0.376 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 2126)
[island] Archived to candidate_pool/island_good/elite_0643041_1775091373269.py
[evaluator tick 4848] B=1 epi=0.1481 gen=643041 elapsed=0.12s evo=0.376 vel=0.000000 breed=LOCAL STAGNANT
[topology-guard] Blind mutation depth mismatch -- safe failure.
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2127)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[evaluator tick 4849] B=0 epi=0.0000 gen=643042 elapsed=0.06s evo=0.368 vel=-0.000000 breed=LOCAL STAGNANT


[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2134)
[island] Archived to candidate_pool/island_good/elite_0643048_1775091390556.py
[evaluator tick 4856] B=1 epi=0.1557 gen=643048 elapsed=0.12s evo=0.368 vel=0.000000 breed=LOCAL STAGNANT
[topology-guard] Blind mutation depth mismatch -- safe failure.
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2135)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[evaluator tick 4857] B=0 epi=0.0000 gen=643049 elapsed=0.05s evo=0.360 vel=-0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2136)
[island] Archived to candidate_pool/island_good/elite_0643049_1775091394747.py
[evaluator tick 4858] B=1 epi=0.1564 gen=643049 elapsed=0.13s evo=0.360 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2137)
[island] Archived to candidate_pool/island_good/elite_0643050_1775091397030.py
[evaluator tick 4859] B=1 epi=0.1612 gen=643050 elapsed=0.13s evo=0.360 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2138)
[island] Archived to candidate_pool/island_good/elite_0643051_1775091399686.py
[evaluator tick 4860] B=1 epi=0.1579 gen=643051 elapsed=0.13s evo=0.360 vel=0.000000 breed=LOCAL STAGNANT

[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2147)
[island] Archived to candidate_pool/island_good/elite_0643060_1775091419842.py
[evaluator tick 4869] B=1 epi=0.1651 gen=643060 elapsed=0.13s evo=0.360 vel=0.000000 breed=LOCAL STAGNANT
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 71 new lines)
[hot-swap] Candidate candidate_1775091421584.py applied and archived.
[evaluator] Hot-swap crash (name 'd' is not defined). Rolling back.
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2148)
[island] Archived to candidate_pool/island_good/elite_0643061_1775091422547.py
[evaluator tick 4870] B=1 epi=0.1593 gen=643061 elapsed=0.15s evo=0.360 vel=0.000000 breed=blind HOT-SWAP STAGNANT
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2149)
[island] Archived to candidate_pool/island_good/elite_0643062_1775091425252.py
[evaluator tick 4871] B=1 epi=0.1549 gen=643062 elapsed=0.15s evo=0.360 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2150)
[island] Archived to candidate_pool/island_good/elite_0643063_1775091426616.py
[evaluator tick 4872] B=1 epi=0.1543 gen=643063 elapsed=0.13s evo=0.360 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2151)
[island] Archived to candidate_pool/island_good/elite_0643064_1775091429196.py
[evaluator tick 4873] B=1 epi=0.1645 gen=643064 elapsed=0.13s evo=0.360 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2152)
[island] Archived to candidate_pool/island_good/elite_0643065_1775091432086.py
[evaluator tick 4874] B=1 epi=0.1523 gen=643065 elapsed=0.13s evo=0.360 vel=0.000000 breed=LOCAL STAGNANT

[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2540)
[island] Archived to candidate_pool/island_good/elite_0643440_1775092071020.py
[evaluator tick 5262] B=1 epi=0.1488 gen=643440 elapsed=0.15s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2541)
[island] Archived to candidate_pool/island_good/elite_0643441_1775092072249.py
[evaluator tick 5263] B=1 epi=0.1616 gen=643441 elapsed=0.14s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2542)
[island] Archived to candidate_pool/island_good/elite_0643442_1775092073976.py
[evaluator tick 5264] B=1 epi=0.1631 gen=643442 elapsed=0.15s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2543)
[island] Archived to candidate_pool/island_good/elite_0643443_1775092075320.py
[evaluator tick 5265] B=1 epi=0.1571 gen=643443 elapsed=0.15s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2544)
[island] Archived to candidate_pool/island_good/elite_0643444_1775092076875.py
[evaluator tick 5266] B=1 epi=0.1600 gen=643444 elapsed=0.14s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2545)
[island] Archived to candidate_pool/island_good/elite_0643445_1775092078103.py
[evaluator tick 5267] B=1 epi=0.1570 gen=643445 elapsed=0.14s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2546)
[island] Archived to candidate_pool/island_good/elite_0643446_1775092079763.py
[evaluator tick 5268] B=1 epi=0.1571 gen=643446 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2547)
[island] Archived to candidate_pool/island_good/elite_0643447_1775092080938.py
[evaluator tick 5269] B=1 epi=0.1593 gen=643447 elapsed=0.14s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2548)
[island] Archived to candidate_pool/island_good/elite_0643448_1775092082363.py
[evaluator tick 5270] B=1 epi=0.1598 gen=643448 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2549)
[island] Archived to candidate_pool/island_good/elite_0643449_1775092083732.py
[evaluator tick 5271] B=1 epi=0.1615 gen=643449 elapsed=0.15s evo=0.392 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2550)
[island] Archived to candidate_pool/island_good/elite_0643450_1775092085020.py

