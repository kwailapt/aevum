(.venv) tsoikwailap@TSOIdeMac-Studio opus_agi % python mutator_daemon.py --poll-interval 30
[mutator] Slow Loop starting (TICK 7.0: Shotgun Mutator).
[mutator] model=qwen3.5:35b-a3b timeout=240s poll=30.0s
[mutator] Recipe version: baseline-v1 | batch_size=3
[mutator] Islands: good=candidate_pool/island_good, explore=candidate_pool/island_explore

[mutator] Mutation triggered: breeder_stagnation
[mutator] threshold=0.1150 best_epi=0.5466 evo=0.392 vel_z=0.00
[mutator] Compute mode: BALANCED temp=0.6 tokens=6144
[mutator] Recipe: baseline-v1
[mutator] Island cross-pollination: 2 AST(s) injected
[mutator] LLM responded in 150.1s
[mutator] Batch: 3/3 variants parsed successfully
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 67 new lines)
[mutator] Variant 1 queued: candidate_1775107833841_v1.py
[llm-nas] AST patch: replacing ['IChingExpert', 'MitoticTransformerBlock'] (2 segment(s), 47 new lines)
[mutator] Variant 2 queued: candidate_1775107833853_v2.py
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 63 new lines)
[mutator] Variant 3 queued: candidate_1775107833865_v3.py
[mutator] Batch complete: 3 candidates queued (150.1s)


(.venv) tsoikwailap@TSOIdeMac-Studio opus_agi % python env_stream.py | python evaluator_daemon.py --threshold 0.10 --instance-id Alpha
[eval_Alpha] Fast Loop starting (TICK 7.0: Evaluator Swarm). Ctrl+C to stop.
[eval_Alpha] threshold=0.1, device=cpu
[eval_Alpha] Candidate pool: agi_workspace/candidate_pool
[eval_Alpha] Islands: good=candidate_pool/island_good, explore=candidate_pool/island_explore
[eval_Alpha] Claimed candidate_1775093697965.py
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 69 new lines)
[eval_Alpha] Candidate candidate_1775093697965.py applied and archived.

  [backbone] Cannot load checkpoint (Error(s) in loading state_dict for AtomicLLM:
	size mismatch for blocks.0.attn.k_proj.weight: copying a param with shape torch.Size([1, 4]) from checkpoint, the shape in current model is torch.Size([2, 4]).
	size mismatch for blocks.0.attn.v_proj.weight: copying a param with shape torch.Size([1, 4]) from checkpoint, the shape in current model is torch.Size([2, 4]).), starting fresh
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644205_1775107698053.py
[eval_Alpha tick 1] B=1 epi=0.1652 gen=644205 elapsed=1.00s evo=0.400 vel=0.000000 breed=blind HOT-SWAP
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644206_1775107700153.py
[eval_Alpha tick 2] B=1 epi=0.1585 gen=644206 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644207_1775107701653.py
[eval_Alpha tick 3] B=1 epi=0.1593 gen=644207 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644208_1775107703472.py
[eval_Alpha tick 4] B=1 epi=0.1489 gen=644208 elapsed=0.15s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644209_1775107705753.py
[eval_Alpha tick 5] B=1 epi=0.1444 gen=644209 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644210_1775107708479.py
[eval_Alpha tick 6] B=1 epi=0.1503 gen=644210 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644211_1775107710632.py
[eval_Alpha tick 7] B=1 epi=0.1551 gen=644211 elapsed=0.16s evo=0.400 vel=0.000000 breed=LOCAL

[eval_Alpha tick 41] B=1 epi=0.1607 gen=644257 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644259_1775107789020.py
[eval_Alpha tick 42] B=1 epi=0.1584 gen=644259 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644261_1775107792681.py
[eval_Alpha tick 43] B=1 epi=0.1521 gen=644261 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Alpha] Blind mutation depth mismatch -- safe failure.
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 44] B=0 epi=0.0000 gen=644262 elapsed=0.06s evo=0.391 vel=-0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644264_1775107798893.py
[eval_Alpha tick 45] B=1 epi=0.1475 gen=644264 elapsed=0.14s evo=0.391 vel=0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644266_1775107802108.py
[eval_Alpha tick 46] B=1 epi=0.1577 gen=644266 elapsed=0.14s evo=0.391 vel=0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644268_1775107804882.py
[eval_Alpha tick 47] B=1 epi=0.1639 gen=644268 elapsed=0.14s evo=0.391 vel=0.000000 breed=LOCAL
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644270_1775107807814.py
[eval_Alpha tick 48] B=1 epi=0.1615 gen=644270 elapsed=0.14s evo=0.392 vel=0.000000 breed=LOCAL

[eval_Alpha tick 57] B=1 epi=0.1613 gen=644288 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
[eval_Alpha] Claimed candidate_1775107833841_v1.py
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 67 new lines)
[eval_Alpha] Candidate candidate_1775107833841_v1.py applied and archived.

  [backbone] Cannot load checkpoint (Error(s) in loading state_dict for AtomicLLM:
	size mismatch for blocks.0.attn.k_proj.weight: copying a param with shape torch.Size([2, 4]) from checkpoint, the shape in current model is torch.Size([1, 4]).
	size mismatch for blocks.0.attn.v_proj.weight: copying a param with shape torch.Size([2, 4]) from checkpoint, the shape in current model is torch.Size([1, 4]).), starting fresh
[eval_Alpha] Hot-swap crash (shape '[1, 128, 0, 2]' is invalid for input of size 128). Rolling back + deep reset.
[deep-rollback] In-memory atomic_core state flushed and reloaded.

  [backbone] Cannot load checkpoint (Error(s) in loading state_dict for AtomicLLM:
	size mismatch for blocks.0.attn.k_proj.weight: copying a param with shape torch.Size([1, 4]) from checkpoint, the shape in current model is torch.Size([2, 4]).
	size mismatch for blocks.0.attn.v_proj.weight: copying a param with shape torch.Size([1, 4]) from checkpoint, the shape in current model is torch.Size([2, 4]).), starting fresh
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 3348)
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644290_1775107834277.py
[eval_Alpha tick 58] B=1 epi=0.1617 gen=644290 elapsed=0.17s evo=0.392 vel=0.000000 breed=blind HOT-SWAP
[eval_Alpha] Claimed candidate_1775107833865_v3.py
[llm-nas] AST patch: replacing ['CausalSelfAttention', 'MitoticTransformerBlock'] (2 segment(s), 63 new lines)
[eval_Alpha] Candidate candidate_1775107833865_v3.py applied and archived.

  [backbone] Cannot load checkpoint (Error(s) in loading state_dict for AtomicLLM:
	size mismatch for blocks.0.attn.k_proj.weight: copying a param with shape torch.Size([2, 4]) from checkpoint, the shape in current model is torch.Size([4, 4]).
	size mismatch for blocks.0.attn.v_proj.weight: copying a param with shape torch.Size([2, 4]) from checkpoint, the shape in current model is torch.Size([4, 4]).), starting fresh
[eval_Alpha] Hot-swap crash (address depth 1 ≠ router depth 2). Rolling back + deep reset.
[deep-rollback] In-memory atomic_core state flushed and reloaded.

  [backbone] Cannot load checkpoint (Error(s) in loading state_dict for AtomicLLM:
	size mismatch for blocks.0.attn.k_proj.weight: copying a param with shape torch.Size([4, 4]) from checkpoint, the shape in current model is torch.Size([2, 4]).
	size mismatch for blocks.0.attn.v_proj.weight: copying a param with shape torch.Size([4, 4]) from checkpoint, the shape in current model is torch.Size([2, 4]).), starting fresh
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 3349)
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644292_1775107836768.py
[eval_Alpha tick 59] B=1 epi=0.1644 gen=644292 elapsed=0.18s evo=0.392 vel=0.000000 breed=blind HOT-SWAP
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 3350)
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644294_1775107839347.py
[eval_Alpha tick 60] B=1 epi=0.1626 gen=644294 elapsed=0.18s evo=0.392 vel=0.000000 breed=LOCAL
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 3351)
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644296_1775107842262.py
[eval_Alpha tick 61] B=1 epi=0.1611 gen=644296 elapsed=0.14s evo=0.392 vel=0.000000 breed=LOCAL
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 3352)
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644298_1775107845030.py
[eval_Alpha tick 62] B=1 epi=0.1509 gen=644298 elapsed=0.13s evo=0.392 vel=0.000000 breed=LOCAL
[eval_Alpha] Blind mutation depth mismatch -- safe failure.
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 3353)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 63] B=0 epi=0.0000 gen=644299 elapsed=0.06s evo=0.384 vel=-0.000000 breed=LOCAL
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 3354)

[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 3624)
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644569_1775108239230.py
[eval_Alpha tick 205] B=1 epi=0.1585 gen=644569 elapsed=0.15s evo=0.384 vel=0.000000 breed=LOCAL
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 3626)
[eval_Alpha] Archived to candidate_pool/island_good/elite_0644570_1775108242734.py
[eval_Alpha tick 206] B=1 epi=0.1418 gen=644570 elapsed=0.15s evo=0.384 vel=0.000000 breed=LOCAL
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 3628)
[eval_Alpha tick 207] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.376 vel=0.000000 breed=blind
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 3630)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 208] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.376 vel=-0.000000 breed=blind
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 3632)
[trace] FIFO eviction: 2 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 209] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.368 vel=-0.000000 breed=blind
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 3633)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 210] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.360 vel=-0.000000 breed=blind
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.88 > 0.3 — scaling threshold to 0.1150 (level 3635)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 211] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.352 vel=-0.000000 breed=blind
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.86 > 0.3 — scaling threshold to 0.1150 (level 3637)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 212] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.344 vel=-0.000000 breed=blind
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.84 > 0.3 — scaling threshold to 0.1150 (level 3639)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 213] B=0 epi=0.0000 gen=644571 elapsed=0.06s evo=0.336 vel=-0.000000 breed=blind
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^

AttributeError: 'str' object has no attribute 'keys'
[eval_Alpha tick 375] HEAT DEATH -- outer loop activated.
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 375] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.000 vel=0.000000 breed=blind STAGNANT
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[eval_Alpha tick 376] HEAT DEATH -- outer loop activated.
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 376] B=0 epi=0.0000 gen=644571 elapsed=0.06s evo=0.000 vel=0.000000 breed=blind STAGNANT
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[eval_Alpha tick 377] HEAT DEATH -- outer loop activated.
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Alpha tick 377] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.000 vel=0.000000 breed=blind STAGNANT
[eval_Alpha] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[eval_Alpha tick 378] HEAT DEATH -- outer loop activated.
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson



(.venv) tsoikwailap@TSOIdeMac-Studio opus_agi % python env_stream.py | python evaluator_daemon.py --threshold 0.10 --instance-id Beta
[eval_Beta] Fast Loop starting (TICK 7.0: Evaluator Swarm). Ctrl+C to stop.
[eval_Beta] threshold=0.1, device=cpu
[eval_Beta] Candidate pool: agi_workspace/candidate_pool
[eval_Beta] Islands: good=candidate_pool/island_good, explore=candidate_pool/island_explore
[eval_Beta] Archived to candidate_pool/island_good/elite_0644230_1775107748658.py
[eval_Beta tick 1] B=1 epi=0.1564 gen=644230 elapsed=0.55s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644231_1775107751742.py
[eval_Beta tick 2] B=1 epi=0.1551 gen=644231 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644232_1775107754804.py
[eval_Beta tick 3] B=1 epi=0.1376 gen=644232 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644234_1775107757519.py
[eval_Beta tick 4] B=1 epi=0.1424 gen=644234 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644236_1775107759989.py
[eval_Beta tick 5] B=1 epi=0.1477 gen=644236 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644238_1775107762555.py
[eval_Beta tick 6] B=1 epi=0.1530 gen=644238 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644240_1775107764532.py
[eval_Beta tick 7] B=1 epi=0.1631 gen=644240 elapsed=0.16s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644242_1775107766910.py
[eval_Beta tick 8] B=1 epi=0.1593 gen=644242 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644244_1775107769537.py
[eval_Beta tick 9] B=1 epi=0.1602 gen=644244 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644246_1775107771895.py
[eval_Beta tick 10] B=1 epi=0.1615 gen=644246 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL

[eval_Beta] Archived to candidate_pool/island_good/elite_0644289_1775107832399.py
[eval_Beta tick 32] B=1 epi=0.1569 gen=644289 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Claimed candidate_1775107833853_v2.py
[llm-nas] AST patch: replacing ['IChingExpert', 'MitoticTransformerBlock'] (2 segment(s), 47 new lines)
[eval_Beta] Candidate candidate_1775107833853_v2.py applied and archived.

  [backbone] Cannot load checkpoint (Error(s) in loading state_dict for AtomicLLM:
	size mismatch for blocks.0.experts.0.net.0.weight: copying a param with shape torch.Size([1, 4]) from checkpoint, the shape in current model is torch.Size([2, 4]).
	size mismatch for blocks.0.experts.0.net.2.weight: copying a param with shape torch.Size([4, 1]) from checkpoint, the shape in current model is torch.Size([4, 2]).
	size mismatch for blocks.0.experts.1.net.0.weight: copying a param with shape torch.Size([1, 4]) from checkpoint, the shape in current model is torch.Size([2, 4]).
	size mismatch for blocks.0.experts.1.net.2.weight: copying a param with shape torch.Size([4, 1]) from checkpoint, the shape in current model is torch.Size([4, 2]).), starting fresh
[eval_Beta] Archived to candidate_pool/island_good/elite_0644291_1775107834696.py
[eval_Beta tick 33] B=1 epi=0.1549 gen=644291 elapsed=0.16s evo=0.400 vel=0.000000 breed=blind HOT-SWAP
[eval_Beta] Archived to candidate_pool/island_good/elite_0644293_1775107837172.py
[eval_Beta tick 34] B=1 epi=0.1627 gen=644293 elapsed=0.15s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644295_1775107839512.py
[eval_Beta tick 35] B=1 epi=0.1550 gen=644295 elapsed=0.17s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Archived to candidate_pool/island_good/elite_0644297_1775107842400.py
[eval_Beta tick 36] B=1 epi=0.1484 gen=644297 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL

[eval_Beta tick 49] B=1 epi=0.1647 gen=644321 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 1.00 > 0.3 — scaling threshold to 0.1150 (level 3366)
[eval_Beta] Archived to candidate_pool/island_good/elite_0644323_1775107881105.py
[eval_Beta tick 50] B=1 epi=0.1635 gen=644323 elapsed=0.13s evo=0.400 vel=0.000000 breed=LOCAL
[pow] Success rate 1.00 > 0.3 — scaling threshold to 0.1150 (level 3368)
[eval_Beta] Archived to candidate_pool/island_good/elite_0644325_1775107883690.py
[eval_Beta tick 51] B=1 epi=0.1600 gen=644325 elapsed=0.14s evo=0.400 vel=0.000000 breed=LOCAL
[eval_Beta] Blind mutation depth mismatch -- safe failure.
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 3370)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Beta tick 52] B=0 epi=0.0000 gen=644326 elapsed=0.07s evo=0.392 vel=-0.000000 breed=LOCAL
[pow] Success rate 0.98 > 0.3 — scaling threshold to 0.1150 (level 3372)
[eval_Beta] Archived to candidate_pool/island_good/elite_0644328_1775107888232.py
[eval_Beta tick 53] B=1 epi=0.1565 gen=644328 elapsed=0.14s evo=0.392 vel=0.000000 breed=LOCAL

[eval_Beta] Archived to candidate_pool/island_good/elite_0644569_1775108239230.py
[eval_Beta tick 179] B=1 epi=0.1418 gen=644569 elapsed=0.15s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
[pow] Success rate 0.96 > 0.3 — scaling threshold to 0.1150 (level 3627)
[eval_Beta] Archived to candidate_pool/island_good/elite_0644570_1775108242735.py
[eval_Beta tick 180] B=1 epi=0.1515 gen=644570 elapsed=0.15s evo=0.384 vel=0.000000 breed=LOCAL STAGNANT
[eval_Beta] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.94 > 0.3 — scaling threshold to 0.1150 (level 3628)
[trace] FIFO eviction: 2 old traces compressed to traces/_compressed_history.ndjson
[eval_Beta tick 181] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.376 vel=-0.000000 breed=blind STAGNANT
[eval_Beta] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.92 > 0.3 — scaling threshold to 0.1150 (level 3629)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Beta tick 182] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.368 vel=-0.000000 breed=blind STAGNANT
[eval_Beta] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.90 > 0.3 — scaling threshold to 0.1150 (level 3631)
[eval_Beta tick 183] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.360 vel=-0.000000 breed=blind STAGNANT
[eval_Beta] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[pow] Success rate 0.88 > 0.3 — scaling threshold to 0.1150 (level 3634)
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Beta tick 184] B=0 epi=0.0000 gen=644571 elapsed=0.06s evo=0.352 vel=-0.000000 breed=blind STAGNANT
[eval_Beta] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())

AttributeError: 'str' object has no attribute 'keys'
[eval_Beta tick 405] HEAT DEATH -- outer loop activated.
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Beta tick 405] B=0 epi=0.0000 gen=644571 elapsed=0.06s evo=0.000 vel=0.000000 breed=blind STAGNANT
[eval_Beta] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[eval_Beta tick 406] HEAT DEATH -- outer loop activated.
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Beta tick 406] B=0 epi=0.0000 gen=644571 elapsed=0.05s evo=0.000 vel=0.000000 breed=blind STAGNANT
[eval_Beta] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^
AttributeError: 'str' object has no attribute 'keys'
[eval_Beta tick 407] HEAT DEATH -- outer loop activated.
[trace] FIFO eviction: 1 old traces compressed to traces/_compressed_history.ndjson
[eval_Beta tick 407] B=0 epi=0.0000 gen=644571 elapsed=0.06s evo=0.000 vel=0.000000 breed=blind STAGNANT
[eval_Beta] Runtime error: AttributeError: 'str' object has no attribute 'keys'
Traceback (most recent call last):
  File "/Volumes/Aevum/Obsidian/Opus_agi/evaluator_daemon.py", line 486, in run
    bred_candidate = breed(population, iching_rules, biogeo_cfg)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 291, in breed
    parent_a = _tournament_select(population, k=3)
  File "/Volumes/Aevum/Obsidian/Opus_agi/local_breeder.py", line 122, in _tournament_select
    keys = list(population.keys())
                ^^^^^^^^^^^^^^^


