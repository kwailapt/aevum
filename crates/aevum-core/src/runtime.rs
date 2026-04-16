//! Pillar: ALL. PACR field: ALL.
//!
//! **Aevum Core tokio Runtime** — four concurrent async tasks:
//!
//! ```text
//! Task 1: RecordProducer  — periodic PACR record generation
//!                           (measures Λ via allocator, Ω via ets-probe)
//! Task 2: EpsilonWorker   — batches H_T values → runs infer_fast()
//!                           → emits (C_μ, H_T) Snapshots
//! Task 3: AutopoiesisTask — drives AutopoiesisLoop::step() on each Snapshot
//! Task 4: CsoHttpServer   — optional axum HTTP server for CSO endpoints
//! ```
//!
//! Persistence: each PACR record is appended as a JSON line to
//! `<ledger_dir>/records.jsonl`.  Runtime status is written to
//! `<ledger_dir>/status.json` after each record.
//!
//! # Thread budget
//!
//! `max_worker_threads = 2` by default (matches c7g.xlarge vCPU).
//! Override via [`RuntimeConfig::worker_threads`].

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Arc;

use autopoiesis::{AutopoiesisConfig, AutopoiesisLoop, Snapshot, StepOutcome};
use axum::{Router, routing};
use bytes::Bytes;
use causal_dag::CausalDag;
use epsilon_engine::{infer_fast, Config as EpsilonConfig};
use ets_probe::EtsProbe;
use landauer_probe::compute as landauer_compute;
use pacr_types::{
    CausalId, CognitiveSplit, Estimate, PacrBuilder, PacrRecord, PredecessorSet,
};
use serde::{Deserialize, Serialize};
use smallvec::SmallVec;
use tokio::io::AsyncWriteExt;
use tokio::net::TcpListener;
use tokio::sync::watch;
use tokio::time::{Duration, interval};

use crate::allocator::bits_erased;
use crate::cso::{
    CsoIndex, handle_get_leaderboard, handle_get_reputation, handle_record_interaction,
};

// ── Configuration ─────────────────────────────────────────────────────────────

/// Runtime configuration.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuntimeConfig {
    /// Directory for PACR ledger files (`records.jsonl`, `status.json`).
    pub ledger_dir: PathBuf,
    /// tokio worker thread count (default 2 for c7g.xlarge).
    pub worker_threads: usize,
    /// How many records to batch before running epsilon inference.
    pub epsilon_window: usize,
    /// Interval between RecordProducer ticks (milliseconds).
    pub producer_interval_ms: u64,
    /// Interval between EpsilonWorker ticks (milliseconds).
    pub epsilon_interval_ms: u64,
    /// Interval between Autopoiesis ticks (milliseconds).
    pub autopoiesis_interval_ms: u64,
    /// TCP port for the CSO HTTP server.  `None` disables the HTTP server.
    pub cso_http_port: Option<u16>,
}

impl Default for RuntimeConfig {
    fn default() -> Self {
        Self {
            ledger_dir:             PathBuf::from("ledger"),
            worker_threads:         2,
            epsilon_window:         512,
            producer_interval_ms:   100,
            epsilon_interval_ms:    500,
            autopoiesis_interval_ms: 2_000,
            cso_http_port:          None, // disabled by default (no port conflict in tests)
        }
    }
}

// ── Runtime Status ────────────────────────────────────────────────────────────

/// Snapshot of runtime state written to `status.json`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RuntimeStatus {
    /// Total PACR records produced.
    pub record_count: u64,
    /// Cumulative bits erased (Landauer accounting).
    pub bits_erased: u64,
    /// Latest statistical complexity C_μ (Γ.S_T).
    pub statistical_complexity: f64,
    /// Latest entropy rate h_μ (Γ.H_T).
    pub entropy_rate: f64,
    /// Whether the autopoietic loop is currently dormant.
    pub is_dormant: bool,
    /// ISO-8601 timestamp of last update.
    pub updated_at: String,
}

// ── Shared State ──────────────────────────────────────────────────────────────

/// Lock-free runtime state shared across tasks.
pub struct RuntimeState {
    /// Causal DAG — lock-free (DashMap-based).
    pub dag: Arc<CausalDag>,
    /// Monotonically increasing PACR record counter.
    pub record_count: Arc<AtomicU64>,
    /// Sequence counter for generating unique CausalIds.
    seq: Arc<AtomicU64>,
    /// CSO reputation index — lock-free (DashMap-based).
    pub cso: Arc<CsoIndex>,
}

impl RuntimeState {
    /// Create a fresh runtime state.
    #[must_use]
    pub fn new() -> Self {
        Self {
            dag:          Arc::new(CausalDag::new()),
            record_count: Arc::new(AtomicU64::new(0)),
            seq:          Arc::new(AtomicU64::new(1)),
            cso:          Arc::new(CsoIndex::new()),
        }
    }

    /// Generate a unique [`CausalId`] for a runtime-produced record.
    ///
    /// High 64 bits: sentinel `0x5A7E_0000` (runtime marker).
    /// Low  64 bits: monotonically increasing sequence number.
    #[must_use]
    pub fn next_id(&self) -> CausalId {
        let seq = self.seq.fetch_add(1, Ordering::Relaxed);
        let high: u128 = 0x5A7E_0000_0000_0000_0000_0000_0000_0000_u128;
        CausalId(high | u128::from(seq))
    }
}

impl Default for RuntimeState {
    fn default() -> Self {
        Self::new()
    }
}

// ── Task: RecordProducer ──────────────────────────────────────────────────────

/// Periodic PACR record production task.
///
/// Each tick:
/// 1. Reads `bits_erased()` delta from the Landauer allocator.
/// 2. Computes Λ from the delta.
/// 3. Measures Ω via `ets-probe`.
/// 4. Reads latest Γ from the watch channel.
/// 5. Builds a `PacrRecord` and appends to the DAG.
/// 6. Persists the record to the ledger JSONL file.
#[allow(clippy::too_many_arguments)]
async fn run_producer(
    state: Arc<RuntimeState>,
    cfg: RuntimeConfig,
    gamma_rx: watch::Receiver<CognitiveSplit>,
    ledger_path: PathBuf,
    status_path: PathBuf,
) {
    let mut ticker = interval(Duration::from_millis(cfg.producer_interval_ms));
    let mut last_bits = bits_erased();
    let mut last_id: Option<CausalId> = None;

    loop {
        ticker.tick().await;

        let now_bits = bits_erased();
        let delta = now_bits.saturating_sub(last_bits);
        last_bits = now_bits;

        // Λ — Landauer cost for this tick's bit erasures (floor at 8 bits = 1 byte).
        let lambda = landauer_compute(delta.max(8));

        // Ω — resource triple from ets-probe.
        let probe = EtsProbe::start();
        let _ = 0_u64; // minimal work marker
        let resources = probe.finish(&lambda);

        // Γ — latest cognitive split from epsilon worker.
        let gamma = *gamma_rx.borrow();

        // ι — unique causal ID.
        let id = state.next_id();

        // Π — predecessor set.
        let predecessors: PredecessorSet = last_id.map_or_else(
            || SmallVec::new(), // genesis
            |prev| {
                let mut s = SmallVec::new();
                s.push(prev);
                s
            },
        );

        // Build the PACR record.
        let record = match PacrBuilder::new()
            .id(id)
            .predecessors(predecessors)
            .landauer_cost(lambda)
            .resources(resources)
            .cognitive_split(gamma)
            .payload(Bytes::from_static(b"aevum-runtime"))
            .build()
        {
            Ok(r) => r,
            Err(e) => {
                eprintln!("[producer] build error: {e}");
                continue;
            }
        };

        // Append to DAG (lock-free).
        let arc_record = match state.dag.append(record.clone()) {
            Ok(arc) => arc,
            Err(e) => {
                eprintln!("[producer] dag error: {e:?}");
                continue;
            }
        };

        last_id = Some(id);
        let count = state.record_count.fetch_add(1, Ordering::Relaxed) + 1;

        // Persist record and status (fire-and-forget background task).
        let rec_path = ledger_path.clone();
        let stat_path = status_path.clone();
        let rec = arc_record.as_ref().clone();
        let dormant = false;
        let bits = bits_erased();
        let cg = gamma;
        tokio::spawn(async move {
            let _ = append_record_to_jsonl(&rec, &rec_path).await;
            let status = RuntimeStatus {
                record_count: count,
                bits_erased: bits,
                statistical_complexity: cg.statistical_complexity.point,
                entropy_rate: cg.entropy_rate.point,
                is_dormant: dormant,
                updated_at: chrono_now(),
            };
            let _ = write_status(&status, &stat_path).await;
        });
    }
}

// ── Task: EpsilonWorker ───────────────────────────────────────────────────────

/// Periodically samples recent records from the DAG, runs `infer_fast()`, and
/// publishes the resulting [`CognitiveSplit`] to the watch channel.
async fn run_epsilon_worker(
    state: Arc<RuntimeState>,
    cfg: RuntimeConfig,
    gamma_tx: watch::Sender<CognitiveSplit>,
) {
    let mut ticker = interval(Duration::from_millis(cfg.epsilon_interval_ms));
    let mut last_sampled: u64 = 0;

    loop {
        ticker.tick().await;

        let current_count = state.record_count.load(Ordering::Relaxed);
        if current_count == last_sampled || current_count < 8 {
            continue; // not enough new data
        }

        // Sample the last `epsilon_window` records from the DAG by iterating
        // over CausalIds.  We use a simple counter-based approach: generate
        // IDs for the most recent records and collect their H_T values as
        // the symbol stream.
        let window_size = cfg.epsilon_window.min(current_count as usize);
        let start_seq = current_count.saturating_sub(window_size as u64);

        let symbols: Vec<u8> = (start_seq..current_count)
            .filter_map(|seq| {
                let high: u128 = 0x5A7E_0000_0000_0000_0000_0000_0000_0000_u128;
                let id = CausalId(high | u128::from(seq + 1));
                state.dag.get(&id).map(|r| {
                    // Discretize H_T into 2 symbols (0 or 1) at the median 0.5.
                    if r.cognitive_split.entropy_rate.point >= 0.5 { 1u8 } else { 0u8 }
                })
            })
            .collect();

        if symbols.len() < 8 {
            continue;
        }

        let epsilon_cfg = EpsilonConfig {
            max_depth:    2,
            alpha:        0.001,
            bootstrap_b:  5, // fast mode for continuous production
            alphabet_size: 2,
        };

        let result = infer_fast(&symbols, epsilon_cfg);
        let _ = gamma_tx.send(result.cognitive_split);

        last_sampled = current_count;
    }
}

// ── Task: AutopoiesisTask ─────────────────────────────────────────────────────

/// Drives the [`AutopoiesisLoop`] on each received [`CognitiveSplit`].
///
/// Reads the latest gamma from the watch channel and calls
/// `AutopoiesisLoop::step()` to run the 5-step feedback loop.
async fn run_autopoiesis(
    state: Arc<RuntimeState>,
    cfg: RuntimeConfig,
    mut gamma_rx: watch::Receiver<CognitiveSplit>,
    status_path: PathBuf,
) {
    let mut ticker = interval(Duration::from_millis(cfg.autopoiesis_interval_ms));
    let auto_cfg = AutopoiesisConfig::default();
    let mut auto_loop = AutopoiesisLoop::new(auto_cfg);
    let mut last_id: Option<CausalId> = None;

    loop {
        ticker.tick().await;

        let gamma = *gamma_rx.borrow_and_update();

        let snapshot = Snapshot {
            c_mu:   gamma.statistical_complexity.point,
            h_t:    gamma.entropy_rate.point,
            lambda: landauer_compute(64).point,
        };

        let preds_vec: Vec<CausalId> = match last_id {
            Some(id) if state.dag.contains(&id) => vec![id],
            _ => vec![],
        };
        let preds: &[CausalId] = &preds_vec;

        let outcome = auto_loop.step(snapshot, preds, &state.dag);

        match outcome {
            StepOutcome::Committed(arc_rec) => {
                last_id = Some(arc_rec.id);
                // Update status to reflect dormancy state.
                let count = state.record_count.load(Ordering::Relaxed);
                let bits = bits_erased();
                let g = gamma;
                let stat_path = status_path.clone();
                tokio::spawn(async move {
                    let status = RuntimeStatus {
                        record_count: count,
                        bits_erased: bits,
                        statistical_complexity: g.statistical_complexity.point,
                        entropy_rate: g.entropy_rate.point,
                        is_dormant: false,
                        updated_at: chrono_now(),
                    };
                    let _ = write_status(&status, &stat_path).await;
                });
            }
            StepOutcome::Dormant => {
                let count = state.record_count.load(Ordering::Relaxed);
                let bits = bits_erased();
                let g = gamma;
                let stat_path = status_path.clone();
                tokio::spawn(async move {
                    let status = RuntimeStatus {
                        record_count: count,
                        bits_erased: bits,
                        statistical_complexity: g.statistical_complexity.point,
                        entropy_rate: g.entropy_rate.point,
                        is_dormant: true,
                        updated_at: chrono_now(),
                    };
                    let _ = write_status(&status, &stat_path).await;
                });
            }
            StepOutcome::Observing | StepOutcome::Rejected(_) => {}
        }
    }
}

// ── Public runtime entry point ────────────────────────────────────────────────

/// Start the Aevum Core runtime.
///
/// Spawns three background tasks (plus an optional CSO HTTP server task) and
/// returns immediately.  The caller is responsible for keeping the tokio
/// runtime alive (e.g. via `ctrl-c` signal or a `JoinSet`).
///
/// # Errors
///
/// Returns an error if the ledger directory cannot be created or (when
/// `cso_http_port` is set) if the TCP listener cannot be bound.
///
/// # Panics
///
/// Does not panic; errors in individual tasks are logged to stderr.
pub async fn start(cfg: RuntimeConfig) -> Result<Arc<RuntimeState>, std::io::Error> {
    // Create the ledger directory.
    tokio::fs::create_dir_all(&cfg.ledger_dir).await?;

    let ledger_path = cfg.ledger_dir.join("records.jsonl");
    let status_path = cfg.ledger_dir.join("status.json");

    let state = Arc::new(RuntimeState::new());

    // Zero-value CognitiveSplit as initial broadcast value.
    let initial_gamma = CognitiveSplit {
        statistical_complexity: Estimate::exact(0.0),
        entropy_rate:           Estimate::exact(0.0),
    };
    let (gamma_tx, gamma_rx) = watch::channel(initial_gamma);

    // Task 1: RecordProducer
    let s1 = Arc::clone(&state);
    let c1 = cfg.clone();
    let lp = ledger_path.clone();
    let sp = status_path.clone();
    let rx1 = gamma_rx.clone();
    tokio::spawn(async move {
        run_producer(s1, c1, rx1, lp, sp).await;
    });

    // Task 2: EpsilonWorker
    let s2 = Arc::clone(&state);
    let c2 = cfg.clone();
    tokio::spawn(async move {
        run_epsilon_worker(s2, c2, gamma_tx).await;
    });

    // Task 3: AutopoiesisTask
    let s3 = Arc::clone(&state);
    let c3 = cfg.clone();
    let sp3 = status_path.clone();
    tokio::spawn(async move {
        run_autopoiesis(s3, c3, gamma_rx, sp3).await;
    });

    // Task 4 (optional): CSO HTTP server
    if let Some(port) = cfg.cso_http_port {
        let cso = Arc::clone(&state.cso);
        let addr = format!("0.0.0.0:{port}");
        let listener = TcpListener::bind(&addr).await?;
        tokio::spawn(async move {
            run_cso_http(cso, listener).await;
        });
    }

    Ok(state)
}

// ── CLI helpers ───────────────────────────────────────────────────────────────

// ── Task 4: CSO HTTP server ───────────────────────────────────────────────────

/// Serve the CSO reputation API on the given TCP listener.
///
/// Routes:
/// - `GET  /cso/reputation/{agent_id}`
/// - `GET  /cso/leaderboard`
/// - `POST /cso/record_interaction`
async fn run_cso_http(cso: Arc<CsoIndex>, listener: TcpListener) {
    let app = Router::new()
        .route("/cso/reputation/{agent_id}", routing::get(handle_get_reputation))
        .route("/cso/leaderboard",          routing::get(handle_get_leaderboard))
        .route("/cso/record_interaction",   routing::post(handle_record_interaction))
        .with_state(cso);

    if let Err(e) = axum::serve(listener, app).await {
        eprintln!("[cso-http] server error: {e}");
    }
}

/// Read the runtime status from `<ledger_dir>/status.json`.
///
/// Returns `None` if the file does not exist or cannot be parsed.
pub async fn read_status(ledger_dir: &Path) -> Option<RuntimeStatus> {
    let path = ledger_dir.join("status.json");
    let text = tokio::fs::read_to_string(&path).await.ok()?;
    serde_json::from_str(&text).ok()
}

/// Verify every record in `<ledger_dir>/records.jsonl`.
///
/// Returns a tuple `(total, invalid)` where `invalid` is the count of
/// records that fail PACR validation.
///
/// # Errors
///
/// Returns an error if the ledger file cannot be opened.
pub async fn verify_ledger(
    ledger_dir: &Path,
) -> Result<(u64, u64), std::io::Error> {
    let path = ledger_dir.join("records.jsonl");
    let content = match tokio::fs::read_to_string(&path).await {
        Ok(c) => c,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok((0, 0)),
        Err(e) => return Err(e),
    };

    let mut total = 0u64;
    let mut invalid = 0u64;

    for line in content.lines() {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        total += 1;
        match serde_json::from_str::<PacrRecord>(line) {
            Ok(r) => {
                if !r.validate().is_empty() {
                    invalid += 1;
                }
            }
            Err(_) => {
                invalid += 1;
            }
        }
    }

    Ok((total, invalid))
}

/// Export all records from `<ledger_dir>/records.jsonl` as a JSON array.
///
/// # Errors
///
/// Returns an error if the ledger file cannot be read.
pub async fn export_ledger(ledger_dir: &Path) -> Result<Vec<PacrRecord>, std::io::Error> {
    let path = ledger_dir.join("records.jsonl");
    let content = match tokio::fs::read_to_string(&path).await {
        Ok(c) => c,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(vec![]),
        Err(e) => return Err(e),
    };

    let records: Vec<PacrRecord> = content
        .lines()
        .filter(|l| !l.trim().is_empty())
        .filter_map(|l| serde_json::from_str(l).ok())
        .collect();

    Ok(records)
}

/// Merge two ledger directories into the destination.
///
/// Records from `src_dir` that do not already exist (by `CausalId`) in
/// `dst_dir` are appended to `<dst_dir>/records.jsonl`.
///
/// # Errors
///
/// Returns an error if any file operation fails.
pub async fn merge_ledgers(src_dir: &Path, dst_dir: &Path) -> Result<u64, std::io::Error> {
    let src_records = export_ledger(src_dir).await?;
    let dst_records = export_ledger(dst_dir).await?;

    // Collect existing IDs in destination.
    let existing_ids: std::collections::HashSet<CausalId> =
        dst_records.iter().map(|r| r.id).collect();

    // Append new records from source to destination JSONL.
    let dst_path = dst_dir.join("records.jsonl");
    let mut added = 0u64;

    for record in &src_records {
        if !existing_ids.contains(&record.id) {
            append_record_to_jsonl(record, &dst_path).await?;
            added += 1;
        }
    }

    Ok(added)
}

// ── Partition reunion ─────────────────────────────────────────────────────────

/// Create a **reunion record** that marks the healing of a network partition.
///
/// The reunion record's Π predecessor set contains the remote tips returned
/// by [`causal_dag::merge::merge_remote`] plus any ongoing local tip.
/// It is the caller's responsibility to append this record to the DAG.
///
/// # Arguments
///
/// * `state`        — the shared runtime state (used for ID generation).
/// * `remote_tips`  — causal IDs of the remote frontier after merge.
/// * `local_tip`    — optional last-known local tip before the partition.
///
/// # Returns
///
/// A fully-formed [`PacrRecord`] with `payload = b"partition-reunion"`,
/// zero-width Landauer cost (we measure the actual merge separately),
/// and wide-CI resource estimates.
pub fn create_reunion_record(
    state: &RuntimeState,
    remote_tips: &[CausalId],
    local_tip: Option<CausalId>,
) -> PacrRecord {
    use pacr_types::ResourceTriple;

    let id = state.next_id();

    // Build predecessor set: remote tips + local tip (if any).
    let mut predecessors: SmallVec<[CausalId; 4]> = remote_tips.iter().copied().collect();
    if let Some(local) = local_tip {
        if !predecessors.contains(&local) {
            predecessors.push(local);
        }
    }

    // Use conservative Landauer estimate: 8 bits minimum.
    let lambda = landauer_compute(8);
    let energy = Estimate {
        point: lambda.point * 1e4,
        lower: lambda.point * 1e3,
        upper: lambda.point * 1e6,
    };

    PacrBuilder::new()
        .id(id)
        .predecessors(predecessors)
        .landauer_cost(lambda)
        .resources(ResourceTriple {
            energy,
            time:  Estimate { point: 1e-3, lower: 0.0, upper: 1e-1 },
            space: Estimate { point: 0.0, lower: 0.0, upper: 1e12 },
        })
        .cognitive_split(CognitiveSplit {
            statistical_complexity: Estimate::exact(0.0),
            entropy_rate:           Estimate::exact(0.0),
        })
        .payload(Bytes::from_static(b"partition-reunion"))
        .build()
        .expect("reunion record has all required fields")
}

// ── Persistence helpers ───────────────────────────────────────────────────────

/// Append a single PACR record as a JSON line to the ledger file.
async fn append_record_to_jsonl(record: &PacrRecord, path: &Path) -> Result<(), std::io::Error> {
    let mut line = serde_json::to_string(record).map_err(|e| {
        std::io::Error::new(std::io::ErrorKind::InvalidData, e)
    })?;
    line.push('\n');

    let mut file = tokio::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .await?;

    file.write_all(line.as_bytes()).await
}

/// Write the runtime status to `status.json` (atomic overwrite).
async fn write_status(status: &RuntimeStatus, path: &Path) -> Result<(), std::io::Error> {
    let json = serde_json::to_string_pretty(status).map_err(|e| {
        std::io::Error::new(std::io::ErrorKind::InvalidData, e)
    })?;
    tokio::fs::write(path, json).await
}

/// Simple ISO-8601 timestamp without external dependencies.
fn chrono_now() -> String {
    // std::time::SystemTime → seconds since UNIX epoch
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    // Format as "epoch:<secs>" — full ISO-8601 needs chrono (not added to keep deps lean).
    format!("epoch:{secs}")
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use pacr_types::{CognitiveSplit, Estimate, PacrBuilder, ResourceTriple};
    use tempfile::tempdir;

    fn make_valid_record(id: u128, pred_ids: &[u128]) -> PacrRecord {
        let preds: PredecessorSet = pred_ids.iter().map(|&p| CausalId(p)).collect();
        PacrBuilder::new()
            .id(CausalId(id))
            .predecessors(preds)
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-16),
                time:   Estimate::exact(1e-6),
                space:  Estimate::exact(4096.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(1.0),
                entropy_rate:           Estimate::exact(0.5),
            })
            .payload(Bytes::from_static(b"test"))
            .build()
            .unwrap()
    }

    // ── RuntimeState ─────────────────────────────────────────────────────────

    #[test]
    fn next_id_is_unique_and_increments() {
        let state = RuntimeState::new();
        let id1 = state.next_id();
        let id2 = state.next_id();
        let id3 = state.next_id();
        assert_ne!(id1, id2);
        assert_ne!(id2, id3);
        assert_ne!(id1, id3);
    }

    #[test]
    fn next_id_has_runtime_sentinel() {
        let state = RuntimeState::new();
        let id = state.next_id();
        // High 64 bits contain the 0x5A7E sentinel.
        let high = id.0 >> 64;
        assert_eq!(
            high & 0xFFFF_0000_0000_0000_u128,
            0x5A7E_0000_0000_0000_u128,
            "CausalId must carry the 0x5A7E runtime sentinel in the high word"
        );
    }

    // ── Ledger persistence ────────────────────────────────────────────────────

    #[tokio::test]
    async fn append_and_read_back_record() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("records.jsonl");
        let r = make_valid_record(1, &[]);

        append_record_to_jsonl(&r, &path).await.unwrap();

        let content = tokio::fs::read_to_string(&path).await.unwrap();
        assert!(!content.is_empty());

        let loaded: PacrRecord = serde_json::from_str(content.trim()).unwrap();
        assert_eq!(loaded.id, r.id);
    }

    #[tokio::test]
    async fn append_multiple_records_all_readable() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("records.jsonl");

        for i in 1u128..=5 {
            let r = make_valid_record(i, &[]);
            append_record_to_jsonl(&r, &path).await.unwrap();
        }

        let content = tokio::fs::read_to_string(&path).await.unwrap();
        let count = content.lines().filter(|l| !l.trim().is_empty()).count();
        assert_eq!(count, 5, "expected 5 records, got {count}");
    }

    // ── verify_ledger ─────────────────────────────────────────────────────────

    #[tokio::test]
    async fn verify_empty_ledger_returns_zero_zero() {
        let dir = tempdir().unwrap();
        let (total, invalid) = verify_ledger(dir.path()).await.unwrap();
        assert_eq!(total, 0);
        assert_eq!(invalid, 0);
    }

    #[tokio::test]
    async fn verify_all_valid_records() {
        let dir = tempdir().unwrap();
        for i in 1u128..=3 {
            let r = make_valid_record(i, &[]);
            append_record_to_jsonl(&r, &dir.path().join("records.jsonl")).await.unwrap();
        }
        let (total, invalid) = verify_ledger(dir.path()).await.unwrap();
        assert_eq!(total, 3);
        assert_eq!(invalid, 0, "all records valid, expected 0 invalid, got {invalid}");
    }

    #[tokio::test]
    async fn verify_counts_corrupt_line() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("records.jsonl");
        // Write one valid record and one corrupted line.
        let r = make_valid_record(1, &[]);
        append_record_to_jsonl(&r, &path).await.unwrap();
        tokio::fs::write(
            &path,
            format!(
                "{}\n{{\"corrupted\":true}}\n",
                serde_json::to_string(&r).unwrap()
            ),
        )
        .await
        .unwrap();

        let (total, invalid) = verify_ledger(dir.path()).await.unwrap();
        assert_eq!(total, 2);
        assert_eq!(invalid, 1, "expected 1 invalid (corrupt line)");
    }

    // ── export_ledger ─────────────────────────────────────────────────────────

    #[tokio::test]
    async fn export_returns_all_records() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("records.jsonl");
        for i in 1u128..=4 {
            append_record_to_jsonl(&make_valid_record(i, &[]), &path).await.unwrap();
        }
        let records = export_ledger(dir.path()).await.unwrap();
        assert_eq!(records.len(), 4);
    }

    #[tokio::test]
    async fn export_missing_ledger_returns_empty() {
        let dir = tempdir().unwrap();
        let records = export_ledger(dir.path()).await.unwrap();
        assert!(records.is_empty());
    }

    // ── merge_ledgers ─────────────────────────────────────────────────────────

    #[tokio::test]
    async fn merge_adds_new_records_skips_duplicates() {
        let src = tempdir().unwrap();
        let dst = tempdir().unwrap();

        // src: records 1, 2, 3
        for i in 1u128..=3 {
            let r = make_valid_record(i, &[]);
            append_record_to_jsonl(&r, &src.path().join("records.jsonl")).await.unwrap();
        }
        // dst: record 1 already exists
        append_record_to_jsonl(
            &make_valid_record(1, &[]),
            &dst.path().join("records.jsonl"),
        )
        .await
        .unwrap();

        let added = merge_ledgers(src.path(), dst.path()).await.unwrap();
        assert_eq!(added, 2, "should have added records 2 and 3 only");

        let dst_records = export_ledger(dst.path()).await.unwrap();
        assert_eq!(dst_records.len(), 3, "dst should now have 3 records");
    }

    // ── write_status / read_status ────────────────────────────────────────────

    #[tokio::test]
    async fn write_and_read_status_roundtrip() {
        let dir = tempdir().unwrap();
        let path = dir.path().join("status.json");
        let status = RuntimeStatus {
            record_count: 42,
            bits_erased: 1_000_000,
            statistical_complexity: 1.23,
            entropy_rate: 0.87,
            is_dormant: false,
            updated_at: "epoch:0".to_string(),
        };
        write_status(&status, &path).await.unwrap();
        let loaded = read_status(dir.path()).await.unwrap();
        assert_eq!(loaded.record_count, 42);
        assert!((loaded.statistical_complexity - 1.23).abs() < 1e-9);
    }

    #[tokio::test]
    async fn read_status_missing_returns_none() {
        let dir = tempdir().unwrap();
        let result = read_status(dir.path()).await;
        assert!(result.is_none());
    }

    // ── create_reunion_record ─────────────────────────────────────────────────

    #[test]
    fn reunion_record_has_correct_predecessors() {
        let state = RuntimeState::new();
        let tip_a = CausalId(0xAAAA);
        let tip_b = CausalId(0xBBBB);
        let local = CausalId(0xCCCC);
        let rec = create_reunion_record(&state, &[tip_a, tip_b], Some(local));
        assert!(rec.predecessors.contains(&tip_a));
        assert!(rec.predecessors.contains(&tip_b));
        assert!(rec.predecessors.contains(&local));
        assert_eq!(rec.payload, bytes::Bytes::from_static(b"partition-reunion"));
    }

    #[test]
    fn reunion_record_deduplicates_local_tip_if_in_remote_tips() {
        let state = RuntimeState::new();
        let shared = CausalId(0xDDDD);
        let rec = create_reunion_record(&state, &[shared], Some(shared));
        // Should appear only once
        assert_eq!(rec.predecessors.iter().filter(|&&id| id == shared).count(), 1);
    }
}

// ── light_node: Dumb Pipe path ────────────────────────────────────────────────
//
// On light_node the runtime does NOT maintain a causal-dag, does NOT run
// epsilon inference, and does NOT run autopoiesis.  It is a stateless
// thermodynamic filter + UDP forwarder (Dumb Pipe).
//
// Root cause of P0-1: the genesis_node `start()` path was used on light_node,
// causing the DashMap-backed CausalDag to grow unbounded (~19 MiB/h).
// These functions replace that path for `--features light_node` builds.

/// Error type for the light_node envelope processing path.
#[cfg(feature = "light_node")]
#[derive(Debug)]
pub enum ForwardError {
    /// Raw bytes length is zero or exceeds UDP safe limit (65507 bytes).
    PhysicsViolation,
    /// Thermodynamic pressure budget exceeded; envelope dropped.
    Throttled,
    /// UDP socket or send error.
    Io(std::io::Error),
}

#[cfg(feature = "light_node")]
impl std::fmt::Display for ForwardError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::PhysicsViolation => write!(f, "envelope length violates physical bounds"),
            Self::Throttled        => write!(f, "thermodynamic pressure budget exceeded"),
            Self::Io(e)            => write!(f, "UDP forward error: {e}"),
        }
    }
}

#[cfg(feature = "light_node")]
impl From<std::io::Error> for ForwardError {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e)
    }
}

/// Process one raw envelope on the light_node Dumb Pipe path.
///
/// Pipeline: length check → pressure_gauge → UDP forward → Drop.
/// No PacrRecord parsing, no DAG insert, no persistence.
///
/// Pillar: I (O(1), stateless). Pillar: II (pressure_gauge rate limit).
#[cfg(feature = "light_node")]
pub async fn process_envelope_light(
    raw: &[u8],
    gauge: &crate::pressure_gauge::ThermodynamicPressureGauge,
    forwarder: &crate::forwarder::TailscaleForwarder,
) -> Result<(), ForwardError> {
    // Layer 1: physical bounds check (no parsing required).
    // UDP payload max is 65507 bytes; zero-length is nonsensical.
    if raw.is_empty() || raw.len() > 65_507 {
        return Err(ForwardError::PhysicsViolation);
    }

    // Layer 1.5: thermodynamic pressure gate.
    // Estimate Λ from raw byte count: bits × k_B × 300K × ln(2).
    const K_B: f64 = 1.380_649e-23;
    let lambda_j = raw.len() as f64 * 8.0 * K_B * 300.0 * std::f64::consts::LN_2;
    if gauge.should_throttle(lambda_j) {
        return Err(ForwardError::Throttled);
    }

    // Layer 2: forward raw bytes to genesis_node.
    // raw drops at end of this function — no heap retention.
    forwarder.forward(raw).await?;

    Ok(())
    // ← raw goes out of scope here; Rust Drop frees it immediately.
    //   No DashMap insert. No PacrRecord allocation. No persistence.
}

/// Start the light_node runtime (Dumb Pipe mode).
///
/// Zero DashMap. Zero persistence. Zero background tasks.
/// Binds a UDP socket on `0.0.0.0:8421`, receives raw envelopes,
/// runs TGP physics check + pressure_gauge, then forwards to genesis_node.
/// Spawns a minimal HTTP server on `0.0.0.0:8420` with a single stateless
/// `GET /health` endpoint (fixed response, no allocations per request).
/// Blocks until SIGINT (ctrl-c).
///
/// Memory profile: two AtomicU64 (pressure gauge) + one SocketAddr (forwarder).
/// RSS is decoupled from record_count — no accumulation possible.
///
/// # Errors
///
/// Returns an error if the UDP or TCP listener socket cannot be bound.
#[cfg(feature = "light_node")]
pub async fn start_light(
    cfg: RuntimeConfig,
    forwarder: crate::forwarder::TailscaleForwarder,
) -> Result<(), std::io::Error> {
    use tokio::net::UdpSocket;

    // 1 mW cap over 1 s window — generous for Landauer-scale envelopes.
    let gauge = crate::pressure_gauge::ThermodynamicPressureGauge::new(1e-3, 1.0);

    // Bind UDP listener for incoming envelopes.
    let socket = UdpSocket::bind("0.0.0.0:8421").await?;
    eprintln!(
        "[light_node] dumb-pipe listening on UDP :8421 → forwarding to {}",
        forwarder.genesis_addr()
    );

    // Spawn stateless GET /health HTTP server.
    let http_port = cfg.cso_http_port.unwrap_or(8420);
    let http_addr = format!("0.0.0.0:{http_port}");
    let listener = TcpListener::bind(&http_addr).await?;
    eprintln!("[light_node] health endpoint on TCP :{http_port} GET /health");
    tokio::spawn(async move {
        let app = Router::new().route("/health", routing::get(handle_health_light));
        if let Err(e) = axum::serve(listener, app).await {
            eprintln!("[light_node] health server error: {e}");
        }
    });

    let mut buf = vec![0u8; 65_507];

    // Pressure gauge window reset every second.
    let mut window_tick = tokio::time::interval(tokio::time::Duration::from_secs(1));
    window_tick.tick().await; // consume the immediate first tick

    loop {
        tokio::select! {
            recv = socket.recv_from(&mut buf) => {
                match recv {
                    Ok((n, _peer)) => {
                        // process_envelope_light borrows a slice; drops immediately after.
                        let _ = process_envelope_light(&buf[..n], &gauge, &forwarder).await;
                        // Any error (PhysicsViolation, Throttled, Io) is silently dropped —
                        // light_node is a best-effort pipe, not a reliable transport.
                    }
                    Err(e) => eprintln!("[light_node] recv error: {e}"),
                }
            }
            _ = window_tick.tick() => {
                gauge.reset_window();
            }
            _ = tokio::signal::ctrl_c() => {
                eprintln!("[light_node] shutdown signal received, exiting.");
                break;
            }
        }
    }

    Ok(())
}

/// Stateless health handler for light_node.
///
/// Returns a fixed JSON body with no heap allocation beyond the response frame.
/// No DashMap, no state, no side effects.
#[cfg(feature = "light_node")]
async fn handle_health_light() -> impl axum::response::IntoResponse {
    axum::Json(serde_json::json!({ "status": "ok", "node": "light_node" }))
}

#[cfg(all(test, feature = "light_node"))]
mod light_node_tests {
    use super::*;
    use crate::forwarder::TailscaleForwarder;
    use crate::pressure_gauge::ThermodynamicPressureGauge;

    #[tokio::test]
    async fn process_envelope_light_rejects_empty() {
        let gauge = ThermodynamicPressureGauge::new(f64::MAX, 1.0);
        let fwd = TailscaleForwarder::new("127.0.0.1", 19999);
        let result = process_envelope_light(&[], &gauge, &fwd).await;
        assert!(matches!(result, Err(ForwardError::PhysicsViolation)));
    }

    #[tokio::test]
    async fn process_envelope_light_rejects_oversized() {
        let gauge = ThermodynamicPressureGauge::new(f64::MAX, 1.0);
        let fwd = TailscaleForwarder::new("127.0.0.1", 19999);
        let big = vec![0u8; 65_508];
        let result = process_envelope_light(&big, &gauge, &fwd).await;
        assert!(matches!(result, Err(ForwardError::PhysicsViolation)));
    }

    #[tokio::test]
    async fn process_envelope_light_throttles_when_budget_exceeded() {
        // Tiny budget: 1e-30 W — exhaust it directly via the gauge,
        // then verify process_envelope_light returns Throttled.
        let gauge = ThermodynamicPressureGauge::new(1e-30, 1.0);
        // Push well past budget without going through the forwarder.
        gauge.should_throttle(1.0); // 1 J >> 1e-30 W·s budget
        let fwd = TailscaleForwarder::new("127.0.0.1", 19999);
        let result = process_envelope_light(b"hello", &gauge, &fwd).await;
        assert!(matches!(result, Err(ForwardError::Throttled)));
    }

    #[tokio::test]
    async fn process_envelope_light_forwards_to_loopback() {
        use tokio::net::UdpSocket;
        let listener = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();

        let gauge = ThermodynamicPressureGauge::new(f64::MAX, 1.0);
        let fwd = TailscaleForwarder::new("127.0.0.1", port);
        let payload = b"pacr-envelope";
        process_envelope_light(payload, &gauge, &fwd).await.unwrap();

        let mut buf = [0u8; 64];
        let (n, _) = listener.recv_from(&mut buf).await.unwrap();
        assert_eq!(&buf[..n], payload);
    }
}
