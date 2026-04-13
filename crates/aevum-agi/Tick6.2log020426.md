(.venv) tsoikwailap@TSOIdeMac-Studio opus_agi % python mutator_daemon.py --poll-interval 30
[mutator] Slow Loop starting (TICK 6.1 + 6.2).
[mutator] model=qwen3.5:35b-a3b timeout=240s poll=30.0s
[mutator] Recipe version: baseline-v1
[mutator] Islands: good=candidate_pool/island_good, explore=candidate_pool/island_explore

[mutator] Mutation triggered: stagnation (delta_epi=-0.003314)
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.000 vel_z=0.00
[mutator] Compute mode: LOW_EVO_OVERRIDE temp=0.78 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] LLM responded in 73.4s
[llm-nas] No recognizable classes or constants in LLM output.
[mutator] AST patch validation failed -- discarding.

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1000 best_epi=0.5466 evo=0.000 vel_z=0.00
[mutator] Compute mode: LOW_EVO_OVERRIDE temp=0.78 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] LLM responded in 52.0s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 64 new lines)
[mutator] Candidate #1 queued: candidate_1775089373897.py (52.0s)

[mutator] Mutation triggered: outer_loop
[mutator] threshold=0.1000 best_epi=0.5466 evo=0.088 vel_z=0.00
[mutator] Compute mode: LOW_EVO_OVERRIDE temp=0.78 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 1 AST(s) injected
[mutator] LLM responded in 56.9s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 71 new lines)
[mutator] Candidate #2 queued: candidate_1775089460840.py (56.9s)

[mutator] Mutation triggered: outer_loop
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.392 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 54.9s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 60 new lines)
[mutator] Candidate #3 queued: candidate_1775089545834.py (54.9s)

[mutator] Mutation triggered: outer_loop
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.392 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 47.5s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 60 new lines)
[mutator] Candidate #4 queued: candidate_1775089623393.py (47.5s)

[mutator] Mutation triggered: outer_loop
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.392 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 52.6s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 60 new lines)
[mutator] Candidate #5 queued: candidate_1775089706081.py (52.6s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.384 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 55.8s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 63 new lines)
[mutator] Candidate #6 queued: candidate_1775089791878.py (55.8s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.384 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 25.6s
[llm-nas] AST patch: replacing ['MitoticTransformerBlock'] (1 segment(s), 35 new lines)
[mutator] Candidate #7 queued: candidate_1775089847495.py (25.6s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.400 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 54.5s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 60 new lines)
[mutator] Candidate #8 queued: candidate_1775089932099.py (54.5s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.376 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 52.6s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 60 new lines)
[mutator] Candidate #9 queued: candidate_1775090014767.py (52.6s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.384 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 30.4s
[llm-nas] AST patch: replacing ['MitoticTransformerBlock'] (1 segment(s), 35 new lines)
[mutator] Candidate #10 queued: candidate_1775090075224.py (30.4s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.392 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 55.9s
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 60 new lines)
[mutator] Candidate #11 queued: candidate_1775090161190.py (55.9s)

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.400 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=2048
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected





[pow] EMERGENCY FORCED DECAY: mem_overload (87.6% > 85.0%) — threshold rolled back to 0.0870 (level 2399)
[island] Archived to candidate_pool/island_explore/elite_0642294_1775089457420.py
[evaluator tick 4071] B=1 epi=0.1628 gen=642294 elapsed=0.13s evo=0.296 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.6% > 85.0%) — threshold rolled back to 0.0870 (level 2398)
[island] Archived to candidate_pool/island_good/elite_0642295_1775089459156.py
[evaluator tick 4072] B=1 epi=0.1607 gen=642295 elapsed=0.14s evo=0.304 vel=0.000000 breed=LOCAL
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 71 new lines)
[hot-swap] Candidate candidate_1775089460840.py applied and archived.
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[evaluator] Hot-swap crash (The size of tensor a (127) must match the size of tensor b (0) at non-singleton dimension 1). Rolling back.
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.6% > 85.0%) — threshold rolled back to 0.0870 (level 2397)
[island] Archived to candidate_pool/island_good/elite_0642296_1775089461725.py
[evaluator tick 4073] B=1 epi=0.1629 gen=642296 elapsed=0.16s evo=0.312 vel=0.000000 breed=blind HOT-SWAP
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.3% > 85.0%) — threshold rolled back to 0.0870 (level 2396)
[island] Archived to candidate_pool/island_good/elite_0642297_1775089464307.py
[evaluator tick 4074] B=1 epi=0.1630 gen=642297 elapsed=0.15s evo=0.320 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (86.9% > 85.0%) — threshold rolled back to 0.0870 (level 2395)
[island] Archived to candidate_pool/island_good/elite_0642298_1775089466332.py
[evaluator tick 4075] B=1 epi=0.1635 gen=642298 elapsed=0.13s evo=0.328 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (86.3% > 85.0%) — threshold rolled back to 0.0870 (level 2394)
[island] Archived to candidate_pool/island_good/elite_0642299_1775089468330.py
[evaluator tick 4076] B=1 epi=0.1622 gen=642299 elapsed=0.13s evo=0.336 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (85.6% > 85.0%) — threshold rolled back to 0.0870 (level 2393)
[island] Archived to candidate_pool/island_good/elite_0642300_1775089470876.py
[evaluator tick 4077] B=1 epi=0.1457 gen=642300 elapsed=0.12s evo=0.344 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (85.2% > 85.0%) — threshold rolled back to 0.0870 (level 2392)
[island] Archived to candidate_pool/island_good/elite_0642301_1775089473452.py
[evaluator tick 4078] B=1 epi=0.1370 gen=642301 elapsed=0.13s evo=0.352 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 2393)
[island] Archived to candidate_pool/island_good/elite_0642302_1775089475038.py
[evaluator tick 4079] B=1 epi=0.1424 gen=642302 elapsed=0.13s evo=0.360 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 2394)
[island] Archived to candidate_pool/island_good/elite_0642303_1775089477417.py
[evaluator tick 4080] B=1 epi=0.1489 gen=642303 elapsed=0.14s evo=0.368 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 2395)
[island] Archived to candidate_pool/island_good/elite_0642304_1775089480360.py
[evaluator tick 4081] B=1 epi=0.1543 gen=642304 elapsed=0.12s evo=0.376 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2396)
[island] Archived to candidate_pool/island_good/elite_0642305_1775089482938.py
[evaluator tick 4082] B=1 epi=0.1592 gen=642305 elapsed=0.12s evo=0.384 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2397)
[island] Archived to candidate_pool/island_good/elite_0642306_1775089484538.py
[evaluator tick 4083] B=1 epi=0.1616 gen=642306 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2398)
[island] Archived to candidate_pool/island_good/elite_0642307_1775089486661.py
[evaluator tick 4084] B=1 epi=0.1648 gen=642307 elapsed=0.14s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2399)
[island] Archived to candidate_pool/island_good/elite_0642308_1775089489539.py
[evaluator tick 4085] B=1 epi=0.1637 gen=642308 elapsed=0.12s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.3% > 85.0%) — threshold rolled back to 0.0870 (level 2398)
[island] Archived to candidate_pool/island_good/elite_0642309_1775089492213.py
[evaluator tick 4086] B=1 epi=0.1610 gen=642309 elapsed=0.12s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.3% > 85.0%) — threshold rolled back to 0.0870 (level 2397)
[island] Archived to candidate_pool/island_good/elite_0642310_1775089493440.py
[evaluator tick 4087] B=1 epi=0.1578 gen=642310 elapsed=0.12s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.4% > 85.0%) — threshold rolled back to 0.0870 (level 2396)
[island] Archived to candidate_pool/island_good/elite_0642311_1775089495932.py
[evaluator tick 4088] B=1 epi=0.1469 gen=642311 elapsed=0.12s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2395)
[island] Archived to candidate_pool/island_good/elite_0642312_1775089498495.py
[evaluator tick 4089] B=1 epi=0.1476 gen=642312 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2394)
[island] Archived to candidate_pool/island_good/elite_0642313_1775089500112.py
[evaluator tick 4090] B=1 epi=0.1556 gen=642313 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2393)
[island] Archived to candidate_pool/island_good/elite_0642314_1775089502295.py
[evaluator tick 4091] B=1 epi=0.1572 gen=642314 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2392)
[island] Archived to candidate_pool/island_good/elite_0642315_1775089504824.py
[evaluator tick 4092] B=1 epi=0.1637 gen=642315 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2391)
[island] Archived to candidate_pool/island_good/elite_0642316_1775089507511.py
[evaluator tick 4093] B=1 epi=0.1647 gen=642316 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2390)
[island] Archived to candidate_pool/island_good/elite_0642317_1775089508683.py
[evaluator tick 4094] B=1 epi=0.1594 gen=642317 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2389)
[island] Archived to candidate_pool/island_good/elite_0642318_1775089511298.py
[evaluator tick 4095] B=1 epi=0.1488 gen=642318 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2388)
[island] Archived to candidate_pool/island_good/elite_0642319_1775089513813.py
[evaluator tick 4096] B=1 epi=0.1529 gen=642319 elapsed=0.12s evo=0.400 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2387)
[island] Archived to candidate_pool/island_good/elite_0642320_1775089515271.py
[evaluator tick 4097] B=1 epi=0.1579 gen=642320 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2386)
[island] Archived to candidate_pool/island_good/elite_0642321_1775089517524.py
[evaluator tick 4098] B=1 epi=0.1463 gen=642321 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2385)
[island] Archived to candidate_pool/island_good/elite_0642322_1775089520188.py
[evaluator tick 4099] B=1 epi=0.1564 gen=642322 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[topology-guard] Blind mutation depth mismatch -- safe failure.
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2384)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[evaluator tick 4100] B=0 epi=0.0000 gen=642323 elapsed=0.06s evo=0.392 vel=-0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2383)
[island] Archived to candidate_pool/island_good/elite_0642323_1775089524076.py
[evaluator tick 4101] B=1 epi=0.1470 gen=642323 elapsed=0.14s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2382)
[island] Archived to candidate_pool/island_good/elite_0642324_1775089526581.py
[evaluator tick 4102] B=1 epi=0.1571 gen=642324 elapsed=0.12s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2381)
[island] Archived to candidate_pool/island_good/elite_0642325_1775089529441.py
[evaluator tick 4103] B=1 epi=0.1635 gen=642325 elapsed=0.16s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2380)
[island] Archived to candidate_pool/island_good/elite_0642326_1775089531033.py
[evaluator tick 4104] B=1 epi=0.1516 gen=642326 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2379)
[island] Archived to candidate_pool/island_good/elite_0642327_1775089533447.py
[evaluator tick 4105] B=1 epi=0.1632 gen=642327 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2378)
[island] Archived to candidate_pool/island_good/elite_0642328_1775089535964.py
[evaluator tick 4106] B=1 epi=0.1641 gen=642328 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2377)
[island] Archived to candidate_pool/island_good/elite_0642329_1775089538371.py
[evaluator tick 4107] B=1 epi=0.1647 gen=642329 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2376)
[island] Archived to candidate_pool/island_good/elite_0642330_1775089540198.py
[evaluator tick 4108] B=1 epi=0.1517 gen=642330 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2375)
[island] Archived to candidate_pool/island_good/elite_0642331_1775089541957.py
[evaluator tick 4109] B=1 epi=0.1649 gen=642331 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
  [backbone] Partial load: 2 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.5% > 85.0%) — threshold rolled back to 0.0870 (level 2374)
[island] Archived to candidate_pool/island_good/elite_0642332_1775089544381.py
[evaluator tick 4110] B=1 epi=0.1565 gen=642332 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 60 new lines)
[hot-swap] Candidate candidate_1775089545834.py applied and archived.

  [backbone] Cannot load checkpoint (Error(s) in loading state_dict for AtomicLLM:
	size mismatch for blocks.0.attn.k_proj.weight: copying a param with shape torch.Size([4, 4]) from checkpoint, the shape in current model is torch.Size([2, 4]).
	size mismatch for blocks.0.attn.v_proj.weight: copying a param with shape torch.Size([4, 4]) from checkpoint, the shape in current model is torch.Size([2, 4]).), starting fresh
[evaluator] Hot-swap crash (shape '[1, 128, 2, 2]' is invalid for input of size 256). Rolling back.

  [backbone] Cannot load checkpoint (Error(s) in loading state_dict for AtomicLLM:
	size mismatch for blocks.0.attn.k_proj.weight: copying a param with shape torch.Size([2, 4]) from checkpoint, the shape in current model is torch.Size([4, 4]).
	size mismatch for blocks.0.attn.v_proj.weight: copying a param with shape torch.Size([2, 4]) from checkpoint, the shape in current model is torch.Size([4, 4]).), starting fresh
[pow] EMERGENCY FORCED DECAY: mem_overload (87.6% > 85.0%) — threshold rolled back to 0.0870 (level 2373)
[island] Archived to candidate_pool/island_good/elite_0642333_1775089546984.py
[evaluator tick 4111] B=1 epi=0.1626 gen=642333 elapsed=0.18s evo=0.392 vel=0.000000 breed=blind HOT-SWAP
[pow] EMERGENCY FORCED DECAY: mem_overload (87.2% > 85.0%) — threshold rolled back to 0.0870 (level 2372)
[island] Archived to candidate_pool/island_good/elite_0642334_1775089549531.py
[evaluator tick 4112] B=1 epi=0.1571 gen=642334 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
[pow] EMERGENCY FORCED DECAY: mem_overload (86.6% > 85.0%) — threshold rolled back to 0.0870 (level 2371)
[island] Archived to candidate_pool/island_good/elite_0642335_1775089550977.py
[evaluator tick 4113] B=1 epi=0.1630 gen=642335 elapsed=0.16s evo=0.392 vel=0.000000 breed=LOCAL
[pow] EMERGENCY FORCED DECAY: mem_overload (85.8% > 85.0%) — threshold rolled back to 0.0870 (level 2370)
[island] Archived to candidate_pool/island_good/elite_0642336_1775089553190.py
[evaluator tick 4114] B=1 epi=0.1558 gen=642336 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 2371)
[island] Archived to candidate_pool/island_good/elite_0642337_1775089555716.py
[evaluator tick 4115] B=1 epi=0.1618 gen=642337 elapsed=0.14s evo=0.392 vel=0.000000 breed=LOCAL

  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (86.4% > 85.0%) — threshold rolled back to 0.0870 (level 2327)
[island] Archived to candidate_pool/island_good/elite_0642424_1775089711357.py
[evaluator tick 4205] B=1 epi=0.1652 gen=642424 elapsed=0.15s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (85.8% > 85.0%) — threshold rolled back to 0.0870 (level 2326)
[island] Archived to candidate_pool/island_good/elite_0642425_1775089712659.py
[evaluator tick 4206] B=1 epi=0.1495 gen=642425 elapsed=0.14s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (85.2% > 85.0%) — threshold rolled back to 0.0870 (level 2325)
[island] Archived to candidate_pool/island_good/elite_0642426_1775089714093.py
[evaluator tick 4207] B=1 epi=0.1577 gen=642426 elapsed=0.13s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2326)
[island] Archived to candidate_pool/island_good/elite_0642427_1775089715531.py
[evaluator tick 4208] B=1 epi=0.1477 gen=642427 elapsed=0.14s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2327)
[island] Archived to candidate_pool/island_good/elite_0642428_1775089717185.py
[evaluator tick 4209] B=1 epi=0.1544 gen=642428 elapsed=0.13s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped


[pow] EMERGENCY FORCED DECAY: mem_overload (87.7% > 85.0%) — threshold rolled back to 0.0870 (level 2302)
[island] Archived to candidate_pool/island_good/elite_0642477_1775089789978.py
[evaluator tick 4260] B=1 epi=0.1626 gen=642477 elapsed=0.14s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.7% > 85.0%) — threshold rolled back to 0.0870 (level 2301)
[island] Archived to candidate_pool/island_good/elite_0642478_1775089791364.py
[evaluator tick 4261] B=1 epi=0.1644 gen=642478 elapsed=0.14s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 63 new lines)
[hot-swap] Candidate candidate_1775089791878.py applied and archived.
[evaluator] Hot-swap crash (shape '[1, 128, 1, 2]' is invalid for input of size 512). Rolling back.
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.7% > 85.0%) — threshold rolled back to 0.0870 (level 2300)
[island] Archived to candidate_pool/island_good/elite_0642479_1775089792591.py
[evaluator tick 4262] B=1 epi=0.1536 gen=642479 elapsed=0.16s evo=0.384 vel=0.000000 breed=blind HOT-SWAP STAGNANT
  [backbone] Partial load: 4 new params (topology change), 0 dropped
[pow] EMERGENCY FORCED DECAY: mem_overload (87.4% > 85.0%) — threshold rolled back to 0.0870 (level 2299)
[island] Archived to candidate_pool/island_good/elite_0642480_1775089794220.py
[evaluator tick 4263] B=1 epi=0.1395 gen=642480 elapsed=0.14s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT

[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2198)
[island] Archived to candidate_pool/island_good/elite_0642731_1775090271523.py
[evaluator tick 4520] B=1 epi=0.1538 gen=642731 elapsed=0.12s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
[pow] Cold-start grace: mem 87.1% > 85.0% but session tick 1 ≤ 3 — suppressed.
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2199)
[island] Archived to candidate_pool/island_good/elite_0642732_1775090274139.py
[evaluator tick 4521] B=1 epi=0.1516 gen=642732 elapsed=0.13s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
[pow] Cold-start grace: mem 87.2% > 85.0% but session tick 2 ≤ 3 — suppressed.
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2200)
[island] Archived to candidate_pool/island_good/elite_0642733_1775090276166.py
[evaluator tick 4522] B=1 epi=0.1578 gen=642733 elapsed=0.13s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
[pow] Cold-start grace: mem 87.2% > 85.0% but session tick 3 ≤ 3 — suppressed.
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 2201)
[island] Archived to candidate_pool/island_good/elite_0642734_1775090277957.py
[evaluator tick 4523] B=1 epi=0.1469 gen=642734 elapsed=0.14s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
[pow] EMERGENCY FORCED DECAY: mem_overload (87.2% > 85.0%) — threshold rolled back to 0.0870 (level 2200)

