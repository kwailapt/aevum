import copy
import json
import psutil
import io
import math
import random
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F
from fs_bus import FileSystemBus
from fractal_router import ASTHasher, KroneckerFractalRouter, FractalAddress
VOCAB_SIZE = 512
EMBED_DIM = 4
NUM_HEADS = 2
NUM_LAYERS = 1
FF_DIM = 2
MAX_SEQ_LEN = 128
DROPOUT = 0.018
BASE_LR = 8.11e-05
ICHING_OFFSET = 0
ICHING_COUNT = 64
BIOGEO_OFFSET = 64
BIOGEO_COUNT = 16
LOGIC_OFFSET = 80
LOGIC_COUNT = 8
HNODE_OFFSET = 88
HNODE_COUNT = 128
EDGE_START = 216
EDGE_END = 217
SEP_TOKEN = 218
PAD_TOKEN = 219
HEXAGRAM_CHARS = [chr(19904 + i) for i in range(64)]
BIOGEO_NAMES = ['BG3_△▽◯', 'Harmonizer_⎇⎈', 'Spiral_◎', 'Vesica_⊛', 'HEK_⬡', 'Cross_✚', 'Wave_∿', 'Infinity_∞', 'Shield_◇', 'Balance_☯', 'Star_✦', 'Flower_✿', 'Ankh_☥', 'Torus_◉', 'Grid_▦', 'Resonance_♒']
LOGIC_NAMES = ['AND_∧', 'OR_∨', 'NOT_¬', 'XOR_⊕', 'IMP_⇒', 'EQV_⇔', 'ALL_∀', 'EXS_∃']

class CausalSelfAttention(nn.Module):

    def __init__(self, d: int, h: int, drop: float=DROPOUT, window: int=16):
        super().__init__()
        assert d % h == 0
        self.h, self.hd = (h, d // h)
        self.window = window
        self.num_kv_heads = h
        self.q_proj = nn.Linear(d, d, bias=False)
        self.k_proj = nn.Linear(d, d, bias=False)
        self.v_proj = nn.Linear(d, d, bias=False)
        self.proj = nn.Linear(d, d, bias=False)
        self.drop = nn.Dropout(drop)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, T, C = x.shape
        q = self.q_proj(x).reshape(B, T, self.h, self.hd).permute(0, 2, 1, 3)
        k = self.k_proj(x).reshape(B, T, self.num_kv_heads, self.hd).permute(0, 2, 1, 3)
        v = self.v_proj(x).reshape(B, T, self.num_kv_heads, self.hd).permute(0, 2, 1, 3)
        i = torch.arange(T, device=x.device).unsqueeze(0)
        j = torch.arange(T, device=x.device).unsqueeze(1)
        causal_mask = torch.tril(torch.ones(T, T, dtype=torch.bool, device=x.device))
        window_mask = i - j < self.window
        valid_mask = causal_mask & window_mask
        att = q @ k.transpose(-2, -1) / math.sqrt(self.hd)
        att = att.masked_fill(~valid_mask, float('-inf'))
        att = self.drop(F.softmax(att, dim=-1))
        return self.proj((att @ v).transpose(1, 2).reshape(B, T, C))

class IChingExpert(nn.Module):

    def __init__(self, d: int, ff: int, drop: float):
        super().__init__()
        self.gate = nn.Linear(d, ff, bias=False)
        self.proj = nn.Linear(d, ff, bias=False)
        self.out_proj = nn.Linear(ff, d, bias=False)
        self.drop = nn.Dropout(drop)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        gate_out = F.relu(self.gate(x))
        proj_out = self.proj(x)
        x = gate_out * proj_out
        return self.out_proj(x)

class RoutingStrategy(nn.Module):
    def __init__(self, d_model: int, n_experts: int, drop: float=0.1, top_k: int=2):
        super().__init__()
        self.d_model = d_model
        self.n_experts = n_experts
        self.top_k = min(top_k, n_experts)
        self.router = nn.Linear(d_model, n_experts)
        nn.init.xavier_uniform_(self.router.weight)
        nn.init.zeros_(self.router.bias)
        self.temperature = nn.Parameter(torch.ones(1) * 0.5)
        self.experts = nn.ModuleList([IChingExpert(d_model, d_model * 2, drop) for _ in range(n_experts)])
        self.expert_dropout = nn.Dropout(drop)
        self.load_balancing_weight = 0.01
        self.entropy_reg_weight = 0.001
        self.temp_lr = 0.01
        self.sinkhorn_iters = 3
        self.expert_usage_buffer = torch.zeros(n_experts)
        self.load_balancing_loss = 0.0

    def _sinkhorn(self, log_alpha: torch.Tensor, iters: int = 3) -> torch.Tensor:
        for _ in range(iters):
            log_alpha = log_alpha - torch.logsumexp(log_alpha, dim=-1, keepdim=True)
            log_alpha = log_alpha - torch.logsumexp(log_alpha, dim=-2, keepdim=True)
        gates = log_alpha.exp()
        gates = gates / (gates.sum(dim=-1, keepdim=True) + 1e-8)
        return gates

    def forward(self, x: torch.Tensor, experts=None, router_idx: int = 0, **kwargs) -> torch.Tensor:
        B, T, D = x.shape
        _experts = experts if experts is not None else self.experts
        n_exp = len(_experts) if hasattr(_experts, '__len__') else self.n_experts
        scores = self.router(x) / self.temperature.clamp(min=0.1)
        if T > 1 and n_exp > 1:
            doubly_stochastic = self._sinkhorn(scores, self.sinkhorn_iters)
        else:
            doubly_stochastic = F.softmax(scores, dim=-1)
        topk_vals, topk_idx = torch.topk(doubly_stochastic, self.top_k, dim=-1)
        topk_gates = topk_vals / (topk_vals.sum(dim=-1, keepdim=True) + 1e-8)
        expert_out = torch.zeros_like(x)
        for k in range(self.top_k):
            idx_k = topk_idx[:, :, k]
            gate_k = topk_gates[:, :, k].unsqueeze(-1)
            gate_k = self.expert_dropout(gate_k)
            for i, expert in enumerate(_experts):
                mask = (idx_k == i).unsqueeze(-1).float()
                expert_out = expert_out + mask * gate_k * expert(x)
        if self.training:
            self.load_balancing_loss = self._compute_load_balancing_loss(doubly_stochastic)
            with torch.no_grad():
                self.expert_usage_buffer = doubly_stochastic.mean(dim=(0, 1)).detach()
        return x + expert_out

    def _compute_load_balancing_loss(self, gates: torch.Tensor) -> torch.Tensor:
        expert_usage = gates.mean(dim=(0, 1))
        target = torch.ones_like(expert_usage) / self.n_experts
        return self.n_experts * F.mse_loss(expert_usage, target)

    def update_temperature(self, loss):
        if self.training:
            grad = torch.autograd.grad(loss, self.temperature, retain_graph=True)[0]
            if grad is not None:
                self.temperature.data -= self.temp_lr * grad
            self.temperature.data = torch.clamp(self.temperature.data, 0.1, 2.0)
            return self.temperature.item()
        return self.temperature.item()

    def compute_load_balancing_loss(self, gates):
        return self._compute_load_balancing_loss(gates)

class MitoticTransformerBlock(nn.Module):

    def __init__(self, d: int, h: int, ff: int, drop: float=0.1):
        super().__init__()
        self.d = d
        self.ff = ff
        self.drop = drop
        self.ln1 = nn.LayerNorm(d)
        self.attn = CausalSelfAttention(d, h, drop)
        self.ln2 = nn.LayerNorm(d)
        self.experts = nn.ModuleList([IChingExpert(d, ff, drop) for _ in range(2)])
        self.num_experts = 2
        self.router = nn.Linear(d, 2)
        nn.init.zeros_(self.router.bias)

    def mitosis(self):
        if self.num_experts >= 32:
            return False
        new_experts = nn.ModuleList()
        for expert in self.experts:
            new_experts.append(expert)
            mutant = IChingExpert(self.d, self.ff, self.drop).to(next(self.parameters()).device)
            mutant.load_state_dict(expert.state_dict())
            with torch.no_grad():
                for param in mutant.parameters():
                    param.add_(torch.randn_like(param) * 0.05)
            new_experts.append(mutant)
        self.experts = new_experts
        self.num_experts *= 2
        old_router = self.router
        self.router = nn.Linear(self.d, self.num_experts)
        with torch.no_grad():
            self.router.weight[:old_router.out_features, :] = old_router.weight
            self.router.bias[:old_router.out_features] = old_router.bias
            self.router.weight[old_router.out_features:, :] = nn.init.normal_(torch.empty(self.router.weight[old_router.out_features:, :].shape), mean=0.0, std=0.02)
            self.router.bias[old_router.out_features:] = 0.0
        return True

    def forward(self, x: torch.Tensor, router_idx: int=0) -> torch.Tensor:
        x = x + self.attn(self.ln1(x))
        attn_out = self.ln2(x)
        scores = self.router(attn_out)
        gates = torch.sigmoid(scores)
        expert_out = 0.0
        for i, expert in enumerate(self.experts):
            expert_out += gates[:, :, i:i + 1] * expert(x)
        x = x + expert_out
        return x

class AtomicLLM(nn.Module):

    def __init__(self, V=512, d=4, h=2, L=1, ff=2, T=128, drop=0.018):
        super().__init__()
        self.V, self.d, self.T = (V, d, T)
        self.tok_emb = nn.Embedding(V, d)
        self.pos_emb = nn.Parameter(torch.zeros(1, T, d))
        self.drop = nn.Dropout(drop)
        self.blocks = nn.ModuleList([MitoticTransformerBlock(d, h, ff, drop) for _ in range(L)])
        self.ln_f = nn.LayerNorm(d)
        self.head = nn.Linear(d, V, bias=False)
        self.tok_emb.weight = self.head.weight
        self.num_experts = 1
        self._init()

    def _init(self):
        nn.init.normal_(self.tok_emb.weight, std=0.02)
        nn.init.normal_(self.pos_emb, std=0.02)
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.normal_(m.weight, std=0.02)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def trigger_mitosis(self):
        success = False
        for blk in self.blocks:
            if blk.mitosis():
                success = True
        if success:
            self.num_experts *= 2
        return success

    def forward(self, idx: torch.Tensor, router_idx: int=0) -> torch.Tensor:
        B, T = idx.shape
        x = self.drop(self.tok_emb(idx) + self.pos_emb[:, :T, :])
        for blk in self.blocks:
            x = blk(x, router_idx)
        return self.head(self.ln_f(x))

class StateCodec:

    @staticmethod
    def encode(nodes: List[int], edges: List[Tuple[int, ...]], iching: List[int], biogeo: List[int], logic: List[int]) -> torch.Tensor:
        toks: List[int] = []
        for e in edges:
            toks.append(EDGE_START)
            toks.extend((HNODE_OFFSET + n % HNODE_COUNT for n in e))
            toks.append(EDGE_END)
        toks.append(SEP_TOKEN)
        toks.extend((ICHING_OFFSET + h % ICHING_COUNT for h in iching))
        toks.append(SEP_TOKEN)
        toks.extend((BIOGEO_OFFSET + b % BIOGEO_COUNT for b in biogeo))
        toks.append(SEP_TOKEN)
        toks.extend((LOGIC_OFFSET + l % LOGIC_COUNT for l in logic))
        toks = toks[:MAX_SEQ_LEN]
        toks += [PAD_TOKEN] * (MAX_SEQ_LEN - len(toks))
        return torch.tensor(toks, dtype=torch.long).unsqueeze(0)

    @staticmethod
    def decode(tokens: List[int]) -> Dict[str, Any]:
        res: Dict[str, Any] = {'edges': [], 'iching': [], 'biogeo': [], 'logic': []}
        cur: List[int] = []
        in_e = False
        for t in tokens:
            if t == PAD_TOKEN:
                continue
            if t == EDGE_START:
                in_e, cur = (True, [])
            elif t == EDGE_END:
                if cur:
                    res['edges'].append(tuple(cur))
                in_e = False
            elif in_e and HNODE_OFFSET <= t < HNODE_OFFSET + HNODE_COUNT:
                cur.append(t - HNODE_OFFSET)
            elif ICHING_OFFSET <= t < ICHING_OFFSET + ICHING_COUNT:
                res['iching'].append(t - ICHING_OFFSET)
            elif BIOGEO_OFFSET <= t < BIOGEO_OFFSET + BIOGEO_COUNT:
                res['biogeo'].append(t - BIOGEO_OFFSET)
            elif LOGIC_OFFSET <= t < LOGIC_OFFSET + LOGIC_COUNT:
                res['logic'].append(t - LOGIC_OFFSET)
        return res

    @staticmethod
    def format_symbols(iching: List[int], biogeo: List[int], logic: List[int]) -> str:
        ic = ''.join((HEXAGRAM_CHARS[i % 64] for i in iching))
        bg = ','.join((BIOGEO_NAMES[i % 16].split('_')[1] for i in biogeo[:3]))
        lg = ''.join((LOGIC_NAMES[i % 8].split('_')[1] for i in logic[:4]))
        return f'{ic} | {bg} | {lg}'

class HyperRewriter:

    @staticmethod
    def seed(n_nodes: int=32, n_edges: int=16, edge_k: int=3) -> Tuple[List[int], List[Tuple[int, ...]]]:
        ns = list(range(n_nodes))
        es = [tuple(random.sample(ns, min(edge_k, len(ns)))) for _ in range(n_edges)]
        return (ns, es)

    @staticmethod
    def rewrite(nodes: List[int], edges: List[Tuple[int, ...]], rate: float=0.3) -> Tuple[List[int], List[Tuple[int, ...]]]:
        if not edges:
            return (nodes, edges)
        nxt = max((max(e) for e in edges if e), default=0) + 1
        out: List[Tuple[int, ...]] = []
        for e in edges:
            if random.random() < rate and len(e) >= 2:
                d = nxt
                nxt += 1
                nodes.append(d)
                out.append((e[0], e[1], d))
                out.append((d, e[-1], e[0]))
            else:
                out.append(e)
        return (nodes, out)

class AtomicCore:

    def __init__(self, fs: FileSystemBus, device: str='cpu'):
        self.fs = fs
        self.device = torch.device(device)
        self.backbone = self._load_or_create_backbone()
        self.optimizer = torch.optim.AdamW(self.backbone.parameters(), lr=BASE_LR)
        self.iching_rules = self._cfg('population/iching_rules.json', self._default_iching)
        self.biogeo_cfg = self._cfg('population/biogeo_cfg.json', self._default_biogeo)
        self.epi_cfg = self._cfg('population/epi_cfg.json', self._default_epi)
        self.fractal_router = KroneckerFractalRouter(depth=2)
        self.ast_hasher = ASTHasher()
        _pop_raw = self.fs.read('population/elites.json')
        self.population: Dict[str, Any] = _pop_raw if isinstance(_pop_raw, dict) else {}
        _ckpt_raw = self.fs.read('memory/checkpoint.json')
        ckpt = _ckpt_raw if isinstance(_ckpt_raw, dict) else {}
        self.gen = ckpt.get('generation', 0)
        self.cumulative_regret = ckpt.get('cumulative_regret', 0.0)
        self.best_epi = ckpt.get('best_epiplexity', 0.0)
        self.meta_epi_thr = ckpt.get('meta_epi_thr', 0.15)
        self.meta_regret_thr = ckpt.get('meta_regret_thr', 7.0)
        self.pop_cap = 120
        self.stagnation_counter = 0
        self.meta_window = 30
        self.meta_window_epi_accum: List[float] = []
        _meta_raw = self.fs.read('memory/meta_es_state.json')
        saved_meta = _meta_raw if isinstance(_meta_raw, dict) else {}
        self.meta_step_sizes: Dict[str, float] = saved_meta.get('step_sizes', {})
        self.meta_baseline_epi: float = saved_meta.get('baseline_epi', 0.0)
        self.meta_snapshot: Optional[Dict[str, Any]] = None
        self.meta_perturbation: Optional[Dict[str, float]] = None
        self.meta_trial_active = False
        self.meta_successes = saved_meta.get('successes', 0)
        self.meta_trials = saved_meta.get('trials', 0)
        if not self.meta_step_sizes:
            self._init_meta_step_sizes()

    def _cfg(self, path: str, default_fn) -> dict:
        d = self.fs.read(path)
        if d and isinstance(d, dict):
            return d
        d = default_fn()
        self.fs.write(path, d)
        return d

    @staticmethod
    def _default_iching():
        return {str(i): {'w': 1.0, 'mr': 0.3} for i in range(64)}

    @staticmethod
    def _default_biogeo():
        return {'active': list(range(16)), 'rw': [1.0] * 16}

    @staticmethod
    def _default_epi():
        return {'eps': 1e-08, 'div_w': 1.0, 'scale': 1.0, 'therm_pen': 10.0, 'W_thermo': 0.1, 'W_latency': 0.05, 'W_complexity': 0.02, 'W_info': 0.03, 'latency_baseline_ms': 50.0, 'max_params': 500000}

    def _load_or_create_backbone(self) -> AtomicLLM:
        data = self.fs.read_bytes('models/backbone.pt')
        m = AtomicLLM().to(self.device)
        if data is not None:
            try:
                state = torch.load(io.BytesIO(data), map_location=self.device, weights_only=False)
                missing, unexpected = m.load_state_dict(state, strict=False)
                if missing:
                    print(f'  [backbone] Partial load: {len(missing)} new params (topology change), {len(unexpected)} dropped')
                m.num_experts = len(m.blocks[0].experts)
                return m
            except Exception as e:
                print(f'\n  [backbone] Cannot load checkpoint ({e}), starting fresh')
        self._persist_backbone(m)
        return m

    def _persist_backbone(self, m: AtomicLLM):
        buf = io.BytesIO()
        torch.save(m.state_dict(), buf)
        self.fs.write_bytes('models/backbone.pt', buf.getvalue())

    def _vary(self) -> Dict[str, Any]:
        if isinstance(self.population, dict) and self.population and (random.random() < 0.7):
            keys = list(self.population.keys())
            ws = [self.population[k].get('epi', 0.01) for k in keys]
            par = self.population[random.choices(keys, [w / sum(ws) for w in ws], k=1)[0]]
            nodes = par.get('nodes', list(range(32)))
            edges = sorted(list(set((tuple(sorted(e)) for e in par.get('edges', [])))))
            iching = list(par.get('ic_idx', range(16)))
            biogeo = list(par.get('bg_idx', range(4)))
            logic = list(par.get('lg_idx', range(4)))
        else:
            nodes, edges = HyperRewriter.seed(random.randint(32, 64), random.randint(12, 20))
            iching = [random.randint(0, 63) for _ in range(15)] + [0]
            biogeo = self._biogeo_sample(4)
            logic = [random.randint(0, 7) for _ in range(4)]
        h0 = torch.randint(0, 64, (1,))
        mr = self.iching_rules.get(str(h0.item()), {}).get('mr', 0.25) or 0.2
        nodes, edges = HyperRewriter.rewrite(nodes, edges, rate=mr * 0.85 if mr * 0.85 > 0.15 else 0.15)
        if len(edges) > 48:
            edges = edges[:min(len(edges), 48)]
        nodes = list(dict.fromkeys(sorted(nodes)))
        if not edges:
            nodes, edges_t = HyperRewriter.seed(16, 8)
            edges = [list(e) for e in edges_t]
        st = StateCodec.encode(nodes, edges, iching, biogeo, logic).to(self.device)
        with torch.no_grad():
            self.backbone.eval()
            logits = self.backbone(st, router_idx=h0)
            shift = logits[:, :-1, :]
            temp = 1.0 + random.uniform(-0.3, 0.3)
            probs = F.softmax(shift / max(temp, 0.5), dim=-1)
            probs = torch.nan_to_num(probs, nan=1.0 / VOCAB_SIZE).clamp(min=1e-10)
            probs = probs / probs.sum(-1, keepdim=True)
            pred = torch.multinomial(probs.reshape(-1, VOCAB_SIZE), 1).reshape(1, -1)
            mix = torch.rand(1, st.shape[1] - 1, device=self.device) < 0.25
            mutated = st.clone()
            mutated[:, 1:] = torch.where(mix, pred, st[:, 1:])
            dec = StateCodec.decode(mutated[0].tolist())
            if dec['iching']:
                iching = dec['iching'][:16]
            if dec['biogeo']:
                biogeo = dec['biogeo'][:4]
            if dec['logic']:
                logic = dec['logic'][:4]
            if dec['edges']:
                edges = list(set((tuple(sorted(e)) for e in dec['edges'])))
                nodes = sorted(set((n for e in edges for n in e)))
        icing = iching if iching else [random.randint(0, 63) for _ in range(16)]
        if not biogeo:
            biogeo = self._biogeo_sample(4)
        if not logic:
            logic = [random.randint(0, 7) for _ in range(4)]
        if not edges:
            nodes, edges_t = HyperRewriter.seed(16, 8)
            edges = [list(e) for e in edges_t]
        return {'nodes': nodes, 'edges': edges, 'ic_idx': iching, 'bg_idx': biogeo, 'lg_idx': logic, 'sym_str': StateCodec.format_symbols(iching, biogeo, logic)}

    def _biogeo_sample(self, k: int) -> List[int]:
        active = self.biogeo_cfg.get('active', list(range(BIOGEO_COUNT)))
        rw = self.biogeo_cfg.get('rw', [1.0] * BIOGEO_COUNT)
        ws = [max(rw[i % len(rw)], 0.01) for i in active]
        return random.choices(active, [w / sum(ws) for w in ws], k=k)

    def calculate_unified_fitness(self, epi_base: float, cpu: float, mem: float, forward_ms: float, param_count: int, probe_success_rate: float) -> Tuple[float, Dict[str, float]]:
        """Combine base reward, resource/latency/complexity costs, and
        information gain efficiency into a single epi scalar.

        All penalty/bonus weights are meta-evolvable via (1+1)-ES.
        Returns (epi, cost_breakdown_dict).
        """
        eps = self.epi_cfg.get('eps', 1e-08)
        w_thermo = self.epi_cfg.get('W_thermo', 0.1)
        resource_cost = w_thermo * (cpu / 100.0 + mem / 100.0)
        w_latency = self.epi_cfg.get('W_latency', 0.05)
        latency_baseline = self.epi_cfg.get('latency_baseline_ms', 50.0)
        latency_excess = max(0.0, forward_ms - latency_baseline)
        latency_cost = w_latency * (latency_excess / max(latency_baseline, 1.0))
        w_complexity = self.epi_cfg.get('W_complexity', 0.02)
        max_params = self.epi_cfg.get('max_params', 500000)
        complexity_cost = w_complexity * (param_count / max(max_params, 1))
        w_info = self.epi_cfg.get('W_info', 0.03)
        info_gain_bonus = w_info * min(1.0, probe_success_rate)
        epi = max(epi_base - resource_cost - latency_cost - complexity_cost + info_gain_bonus, eps)
        breakdown = {'resource_cost': resource_cost, 'latency_cost': latency_cost, 'complexity_cost': complexity_cost, 'info_gain_bonus': info_gain_bonus, 'forward_ms': forward_ms, 'param_count': param_count, 'probe_success_rate': probe_success_rate}
        return (epi, breakdown)

    def _evaluate(self, cand: Dict) -> Dict[str, Any]:
        if sys.stdin.isatty():
            tokens = self._fallback_chaos_sequence()
        else:
            line = sys.stdin.readline().strip()
            if line:
                data = json.loads(line)
                tokens = data['tokens'][:MAX_SEQ_LEN]
            else:
                tokens = self._fallback_chaos_sequence()
        tokens += [PAD_TOKEN] * (MAX_SEQ_LEN - len(tokens))
        st = torch.tensor(tokens[:MAX_SEQ_LEN], dtype=torch.long).unsqueeze(0).to(self.device)
        self.backbone.train()
        router_idx = cand['ic_idx'][0] % 64 if cand['ic_idx'] else 0
        t_fwd = time.monotonic()
        logits = self.backbone(st, router_idx=router_idx)
        forward_ms = (time.monotonic() - t_fwd) * 1000.0
        param_count = sum((p.numel() for p in self.backbone.parameters()))
        target = st[:, 1:].reshape(-1)
        pred = logits[:, :-1].reshape(-1, VOCAB_SIZE)
        mask = target != PAD_TOKEN
        loss = F.cross_entropy(pred[mask], target[mask]) if mask.any() else torch.tensor(math.log(VOCAB_SIZE), device=self.device, requires_grad=True)
        eps = self.epi_cfg.get('eps', 1e-08)
        div_w = self.epi_cfg.get('div_w', 1.0)
        scale = self.epi_cfg.get('scale', 1.0)
        therm_pen = self.epi_cfg.get('therm_pen', 10.0)
        unique = len(set(st[0].tolist()) - {PAD_TOKEN}) / VOCAB_SIZE
        entropy_penalty = 0.0
        if unique < 0.15:
            entropy_penalty = therm_pen * (0.15 - unique)
        topo_penalty = 0.0
        ic_vals = [ICHING_OFFSET + h % ICHING_COUNT for h in cand['ic_idx'][:2]]
        addr = FractalAddress(tuple((v % 64 for v in ic_vals[:2])))
        self.fractal_router.route(addr)
        if self.fractal_router.total_routed > 100:
            cv2 = self.fractal_router.variance()
            if cv2 > 2.0:
                topo_penalty = therm_pen * 0.1 * (cv2 - 2.0)
        regret = loss.item() + entropy_penalty + topo_penalty
        epi_base = scale / (regret + eps) * (1.0 + div_w * unique)
        _self_proc = psutil.Process()
        cpu = _self_proc.cpu_percent(interval=None)
        _rss = _self_proc.memory_info().rss
        mem = _rss / psutil.virtual_memory().total * 100.0
        probe_success_rate = 0.0
        probe_stats = self.fs.read('telemetry/sandbox_probe_stats.json')
        if isinstance(probe_stats, dict):
            probe_success_rate = probe_stats.get('success_rate', 0.0)
        epi, fitness_breakdown = self.calculate_unified_fitness(epi_base=epi_base, cpu=cpu, mem=mem, forward_ms=forward_ms, param_count=param_count, probe_success_rate=probe_success_rate)
        return {'epi': epi, 'regret': regret, 'loss': loss, 'unique': unique, 'penalty': entropy_penalty, 'topo_penalty': topo_penalty, 'thermo_cost': fitness_breakdown['resource_cost'], 'forward_ms': forward_ms, 'param_count': param_count, 'latency_cost': fitness_breakdown['latency_cost'], 'complexity_cost': fitness_breakdown['complexity_cost'], 'info_gain_bonus': fitness_breakdown['info_gain_bonus'], 'probe_success_rate': probe_success_rate}

    @staticmethod
    def _fallback_chaos_sequence() -> List[int]:
        """Local Lorenz fallback when stdin pipe is unavailable (degraded mode)."""
        CHAOS_BASE, N_BINS = (220, 96)
        x, y, z = (random.uniform(-15, 15), random.uniform(-15, 15), random.uniform(10, 40))
        dt = 0.005
        tokens: List[int] = []
        for _ in range(85):
            for _ in range(4):
                dx = 10.0 * (y - x)
                dy = x * (28.0 - z) - y
                dz = x * y - 8.0 / 3.0 * z
                x, y, z = (x + dx * dt, y + dy * dt, z + dz * dt)
            tx = CHAOS_BASE + int(max(0, min(N_BINS - 1, (x + 25.0) / 50.0 * N_BINS)))
            ty = CHAOS_BASE + N_BINS + int(max(0, min(N_BINS - 1, (y + 35.0) / 70.0 * N_BINS)))
            tz = CHAOS_BASE + 2 * N_BINS + int(max(0, min(N_BINS - 1, z / 55.0 * N_BINS)))
            tokens.extend([tx, ty, tz])
        return tokens

    def _select_and_compress(self, cand: Dict, met: Dict):
        if not isinstance(self.population, dict):
            self.population = {}
        key = f'g{self.gen:07d}_{int(time.time() * 1000) % 100000:05d}'
        self.population[key] = {'nodes': cand['nodes'], 'edges': cand['edges'], 'ic_idx': cand['ic_idx'], 'bg_idx': cand['bg_idx'], 'lg_idx': cand['lg_idx'], 'sym_str': cand['sym_str'], 'epi': met['epi'], 'regret': met['regret'], 'unique': met['unique'], 'gen': self.gen, 't': time.time()}
        if len(self.population) > self.pop_cap:
            ranked = sorted(self.population.items(), key=lambda kv: kv[1]['epi'], reverse=True)
            total = sum((v['epi'] for _, v in ranked)) or 1.0
            cum = 0.0
            keep = {}
            for k, v in ranked:
                cum += v['epi']
                keep[k] = v
                if cum / total >= 0.8 and len(keep) >= 5:
                    break
            self.population = keep
        if len(self.population) >= 4:
            vals = sorted((v['epi'] for v in self.population.values()), reverse=True)
            ratios = [vals[i + 1] / vals[i] for i in range(min(len(vals) - 1, 6)) if vals[i] > 1e-08]
            if ratios:
                mean_r = sum(ratios) / len(ratios)
                var_r = sum(((r - mean_r) ** 2 for r in ratios)) / len(ratios)
                if var_r < 0.01:
                    self.fs.write('memory/fractal.json', {'gen': self.gen, 'ratios': ratios, 'var': var_r})
            self.fs.write('population/elites.json', self.population)

    def _init_meta_step_sizes(self):
        self.meta_step_sizes = {}
        for k in self.iching_rules:
            self.meta_step_sizes[f'ic_{k}_w'] = 0.01
            self.meta_step_sizes[f'ic_{k}_mr'] = 0.02
        for i in range(len(self.biogeo_cfg.get('rw', []))):
            self.meta_step_sizes[f'bg_rw_{i}'] = 0.02
        self.meta_step_sizes['epi_div_w'] = 0.01
        self.meta_step_sizes['epi_scale'] = 0.01
        self.meta_step_sizes['epi_W_latency'] = 0.005
        self.meta_step_sizes['epi_W_complexity'] = 0.003
        self.meta_step_sizes['epi_W_info'] = 0.005
        self.meta_step_sizes['epi_latency_baseline_ms'] = 2.0
        self.meta_step_sizes['epi_max_params'] = 5000.0

    def _flatten_rules(self) -> Dict[str, float]:
        flat: Dict[str, float] = {}
        for k, r in self.iching_rules.items():
            flat[f'ic_{k}_w'] = r['w']
            flat[f'ic_{k}_mr'] = r['mr']
        for i, v in enumerate(self.biogeo_cfg.get('rw', [])):
            flat[f'bg_rw_{i}'] = v
        flat['epi_div_w'] = self.epi_cfg['div_w']
        flat['epi_scale'] = self.epi_cfg['scale']
        flat['epi_W_latency'] = self.epi_cfg.get('W_latency', 0.05)
        flat['epi_W_complexity'] = self.epi_cfg.get('W_complexity', 0.02)
        flat['epi_W_info'] = self.epi_cfg.get('W_info', 0.03)
        flat['epi_latency_baseline_ms'] = self.epi_cfg.get('latency_baseline_ms', 50.0)
        flat['epi_max_params'] = self.epi_cfg.get('max_params', 500000)
        return flat

    def _unflatten_rules(self, flat: Dict[str, float]):
        for k in self.iching_rules:
            self.iching_rules[k]['w'] = flat.get(f'ic_{k}_w', self.iching_rules[k]['w'])
            self.iching_rules[k]['mr'] = max(0.02, min(0.9, flat.get(f'ic_{k}_mr', self.iching_rules[k]['mr'])))
        rw = self.biogeo_cfg.get('rw', [])
        for i in range(len(rw)):
            rw[i] = max(0.01, flat.get(f'bg_rw_{i}', rw[i]))
        self.epi_cfg['div_w'] = max(0.01, flat.get('epi_div_w', self.epi_cfg['div_w']))
        self.epi_cfg['scale'] = max(0.01, flat.get('epi_scale', self.epi_cfg['scale']))
        self.epi_cfg['W_latency'] = max(0.0, flat.get('epi_W_latency', self.epi_cfg.get('W_latency', 0.05)))
        self.epi_cfg['W_complexity'] = max(0.0, flat.get('epi_W_complexity', self.epi_cfg.get('W_complexity', 0.02)))
        self.epi_cfg['W_info'] = max(0.0, flat.get('epi_W_info', self.epi_cfg.get('W_info', 0.03)))
        self.epi_cfg['latency_baseline_ms'] = max(1.0, flat.get('epi_latency_baseline_ms', self.epi_cfg.get('latency_baseline_ms', 50.0)))
        self.epi_cfg['max_params'] = max(100, int(flat.get('epi_max_params', self.epi_cfg.get('max_params', 500000))))

    def _meta_take_snapshot(self):
        self.meta_snapshot = {'rules_flat': self._flatten_rules(), 'iching_rules': copy.deepcopy(self.iching_rules), 'biogeo_cfg': copy.deepcopy(self.biogeo_cfg), 'epi_cfg': copy.deepcopy(self.epi_cfg)}

    def _meta_apply_perturbation(self):
        flat = self._flatten_rules()
        self.meta_perturbation = {}
        for key, val in flat.items():
            sigma = self.meta_step_sizes.get(key, 0.01)
            delta = random.gauss(0, sigma)
            self.meta_perturbation[key] = delta
            flat[key] = val + delta
        self._unflatten_rules(flat)
        self._persist_rule_files()

    def _meta_rollback(self):
        if self.meta_snapshot is None:
            return
        self.iching_rules = self.meta_snapshot['iching_rules']
        self.biogeo_cfg = self.meta_snapshot['biogeo_cfg']
        self.epi_cfg = self.meta_snapshot['epi_cfg']
        self._persist_rule_files()

    def _persist_rule_files(self):
        self.fs.write('population/iching_rules.json', self.iching_rules)
        self.fs.write('population/biogeo_cfg.json', self.biogeo_cfg)
        self.fs.write('population/epi_cfg.json', self.epi_cfg)

    def _meta_evaluate_window(self):
        if not self.meta_window_epi_accum:
            return
        avg_epi = sum(self.meta_window_epi_accum) / len(self.meta_window_epi_accum)
        improved = avg_epi > self.meta_baseline_epi and self.meta_baseline_epi > 0
        self.meta_trials += 1
        if improved:
            self.meta_successes += 1
            for key in self.meta_step_sizes:
                self.meta_step_sizes[key] *= 1.2
            action = 'KEEP'
            delta_pct = (avg_epi - self.meta_baseline_epi) / max(self.meta_baseline_epi, 1e-08) * 100
        else:
            self._meta_rollback()
            for key in self.meta_step_sizes:
                self.meta_step_sizes[key] *= 0.82
            action = 'ROLLBACK'
            delta_pct = (avg_epi - self.meta_baseline_epi) / max(self.meta_baseline_epi, 1e-08) * 100 if self.meta_baseline_epi > 0 else 0
        event = {'gen': self.gen, 'action': action, 'avg_epi': avg_epi, 'baseline_epi': self.meta_baseline_epi, 'delta_pct': round(delta_pct, 2), 'successes': self.meta_successes, 'trials': self.meta_trials, 'avg_step_size': sum(self.meta_step_sizes.values()) / max(len(self.meta_step_sizes), 1), 't': time.time()}
        self.fs.append('logs/meta_evolution.ndjson', event)
        self.fs.write('memory/meta_es_state.json', {'step_sizes': self.meta_step_sizes, 'baseline_epi': avg_epi, 'successes': self.meta_successes, 'trials': self.meta_trials})
        success_rate = self.meta_successes / max(self.meta_trials, 1)
        print(f"\n  [meta-evo] gen {self.gen}: {action} | epi {self.meta_baseline_epi:.3f} -> {avg_epi:.3f} ({delta_pct:+.1f}%) | success rate {success_rate:.0%} | avg step {event['avg_step_size']:.4f}")
        self.fs.commit(f'Meta-evo gen {self.gen}: {action} | avg_epi {self.meta_baseline_epi:.2f} -> {avg_epi:.2f} ({delta_pct:+.1f}%)')
        self.meta_baseline_epi = avg_epi
        self.meta_window_epi_accum = []
        self._meta_take_snapshot()
        self._meta_apply_perturbation()

    def _meta_evolve(self, met: Dict):
        epi, regret, loss = (met['epi'], met['regret'], met.get('loss'))
        if loss is not None and loss.requires_grad:
            eff_lr = BASE_LR * min(1.0, epi / max(self.meta_epi_thr, 1e-08))
            for pg in self.optimizer.param_groups:
                pg['lr'] = eff_lr
            self.optimizer.zero_grad()
            try:
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.backbone.parameters(), 1.0)
                self.optimizer.step()
            except RuntimeError:
                pass
        if epi > self.meta_epi_thr and regret < self.meta_regret_thr:
            self.stagnation_counter = 0
            self.meta_epi_thr = max(self.meta_epi_thr, epi * 0.85)
            self.meta_regret_thr = min(self.meta_regret_thr, regret * 1.15)
        else:
            self.stagnation_counter += 1
        if self.stagnation_counter > 100:
            self._safe_mitosis()
            self.stagnation_counter = 0
        self.meta_window_epi_accum.append(epi)
        if not self.meta_trial_active:
            if len(self.meta_window_epi_accum) >= self.meta_window:
                self.meta_baseline_epi = sum(self.meta_window_epi_accum) / len(self.meta_window_epi_accum)
                self.meta_window_epi_accum = []
                self._meta_take_snapshot()
                self._meta_apply_perturbation()
                self.meta_trial_active = True
                print(f'\n  [meta-evo] Baseline established: avg_epi = {self.meta_baseline_epi:.3f}. Starting trials.')
            return
        if len(self.meta_window_epi_accum) >= self.meta_window:
            self._meta_evaluate_window()
        if self.gen % 10 == 0:
            self._persist_backbone(self.backbone)

    def _safe_mitosis(self):
        if self.backbone.num_experts >= 64:
            return
        self._persist_backbone(self.backbone)
        if self.backbone.trigger_mitosis():
            self.optimizer = torch.optim.AdamW(self.backbone.parameters(), lr=BASE_LR)
            print(f'\n  [mitosis] Expert count: {self.backbone.num_experts}. Optimizer rebuilt. Population preserved.')
            self.fs.commit(f'Mitosis: experts {self.backbone.num_experts // 2} -> {self.backbone.num_experts}')

    def iterate(self) -> Dict[str, Any]:
        self.gen += 1
        cand = self._vary()
        met = self._evaluate(cand)
        self._select_and_compress(cand, met)
        self._meta_evolve(met)
        self.cumulative_regret += met['regret']
        if met['epi'] > self.best_epi:
            self.best_epi = met['epi']
        log = {'gen': self.gen, 'epi': met['epi'], 'regret': met['regret'], 'cum_reg': self.cumulative_regret, 'best_epi': self.best_epi, 'pop': len(self.population), 'sym': cand.get('sym_str', ''), 'forward_ms': met.get('forward_ms', 0.0), 'param_count': met.get('param_count', 0), 'latency_cost': met.get('latency_cost', 0.0), 'complexity_cost': met.get('complexity_cost', 0.0), 'info_gain_bonus': met.get('info_gain_bonus', 0.0)}
        self.fs.append('logs/evolution.ndjson', log)
        return log
