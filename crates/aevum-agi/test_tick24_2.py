"""TICK 24.2 Verification: RoutingStrategy AST extraction + forward pass."""
import ast
import sys
import torch

# ── Test 1: AST extraction via genome_assembler ──
print("=" * 60)
print("TEST 1: AST extraction of RoutingStrategy from atomic_core.py")
print("=" * 60)

with open("atomic_core.py", "r") as f:
    full_source = f.read()

tree = ast.parse(full_source)
found_classes = []
routing_node = None

for node in ast.iter_child_nodes(tree):
    if isinstance(node, ast.ClassDef):
        found_classes.append(node.name)
        if node.name == "RoutingStrategy":
            routing_node = node

print(f"  All top-level classes: {found_classes}")

if routing_node is None:
    print("  FAIL: RoutingStrategy class NOT found by ast.parse!")
    sys.exit(1)

lines = full_source.splitlines()
start = routing_node.lineno - 1
end = routing_node.end_lineno
extracted = "\n".join(lines[start:end])
print(f"  PASS: Extracted RoutingStrategy (lines {start+1}-{end}, {len(extracted)} chars)")
print()

# ── Test 2: extract_organelle_source integration ──
print("=" * 60)
print("TEST 2: genome_assembler.extract_organelle_source('routing')")
print("=" * 60)

from genome_assembler import extract_organelle_source

for org_type in ["attention", "routing", "expert"]:
    src = extract_organelle_source(full_source, org_type)
    if src is None:
        print(f"  FAIL: extract_organelle_source('{org_type}') returned None!")
        sys.exit(1)
    print(f"  PASS: '{org_type}' -> {len(src)} chars extracted")
print()

# ── Test 3: RoutingStrategy forward pass ──
print("=" * 60)
print("TEST 3: RoutingStrategy standalone forward pass")
print("=" * 60)

from atomic_core import RoutingStrategy

model = RoutingStrategy(d_model=64, n_experts=4)
x = torch.randn(1, 16, 64)
out = model(x)
assert out.shape == x.shape, f"Shape mismatch: {out.shape} != {x.shape}"
print(f"  PASS: RoutingStrategy(d_model=64, n_experts=4) -> {out.shape}")
print()

# ── Test 4: MitoticTransformerBlock still works (checkpoint compat) ──
print("=" * 60)
print("TEST 4: MitoticTransformerBlock forward pass (checkpoint compat)")
print("=" * 60)

from atomic_core import MitoticTransformerBlock

block = MitoticTransformerBlock(d=64, h=4, ff=128)
sd_keys = [k for k in block.state_dict().keys() if "router" in k]
print(f"  State dict router keys: {sd_keys}")
assert "router.weight" in block.state_dict(), "Missing router.weight — checkpoint compat broken!"
assert "router.bias" in block.state_dict(), "Missing router.bias — checkpoint compat broken!"

x = torch.randn(1, 16, 64)
out = block(x)
assert out.shape == x.shape, f"Shape mismatch: {out.shape} != {x.shape}"
print(f"  PASS: MitoticTransformerBlock state dict intact, forward -> {out.shape}")
print()

# ── Test 5: AtomicLLM end-to-end ──
print("=" * 60)
print("TEST 5: AtomicLLM end-to-end forward pass")
print("=" * 60)

from atomic_core import AtomicLLM

llm = AtomicLLM(V=512, d=64, h=4, L=1, ff=128, T=32)
tokens = torch.randint(0, 512, (1, 16))
logits = llm(tokens)
print(f"  PASS: AtomicLLM forward -> {logits.shape}")
print()

print("=" * 60)
print("ALL 5 TESTS PASSED — TICK 24.2 VERIFIED")
print("=" * 60)
