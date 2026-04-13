# Causal Topology Rules (agentcard-spec v1.1)

## Rule 1: Causal Distance Tax
Λ_effective ≥ Λ_base × exp(α × max_distance(Π))
Default α = 0.1

## Rule 2: Child Capacity
Max children per node: 65,536

## Rule 3: Local Attachment Preference
Prefer predecessors within causal distance ≤ 8
