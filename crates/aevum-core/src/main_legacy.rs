mod causal_dag;
mod clearinghouse;
mod epiplexity;
mod gateway;
mod ledger;
mod thermodynamics;

use axum::{routing::post, Router};
use reqwest::Client;
use std::sync::Arc;
use std::time::Duration;

use gateway::GatewayState;
use ledger::ShardedLedger;
use thermodynamics::NessMonitor;

const LEDGER_DIR: &str = "ledger";
const HTTP_ADDR:  &str = "0.0.0.0:8888";

/// NESS reporter cadence.  Every 60 s the monitor snapshots σ and resets
/// the epoch counters for a rolling one-minute window.
const NESS_REPORT_SECS: u64 = 60;

#[tokio::main]
async fn main() {
    let api_key = std::env::var("ALIYUN_API_KEY")
        .expect("ALIYUN_API_KEY environment variable not set");

    // ── Shared NESS monitor ───────────────────────────────────────────────────
    let ness = NessMonitor::new();

    // ── Sharded ledger (16 × 1 M slots, splitmix64 routing) ──────────────────
    let ledger = Arc::new(
        ShardedLedger::open(LEDGER_DIR, ness.clone())
            .expect("Failed to open sharded ledger"),
    );

    // ── UDP clearinghouse (dedicated OS thread, non-blocking spin) ────────────
    clearinghouse::serve(ledger.clone());

    // ── NESS + Epiplexity reporter (async task, 60 s rolling window) ────────────
    {
        let ness_ref = ledger.ness();
        let dag_ref  = ledger.dag();
        tokio::spawn(async move {
            let mut interval =
                tokio::time::interval(Duration::from_secs(NESS_REPORT_SECS));
            loop {
                interval.tick().await;
                let snap = ness_ref.snapshot_and_reset();
                let dag_len = dag_ref.len();
                println!(
                    "[NESS] σ={:.2} χ/s | {} | P={:.2e} W \
                     | minted={} deducted={} | dag_records={}",
                    snap.sigma, snap.state, snap.power_w,
                    snap.minted, snap.deducted, dag_len,
                );
            }
        });
    }

    // ── HTTP gateway ──────────────────────────────────────────────────────────
    let state = GatewayState {
        client:  Client::new(),
        ledger,
        api_key,
    };

    let app = Router::new()
        .route("/v1/chat/completions", post(gateway::handle_completions))
        .with_state(state);

    println!(
        "Aevum Core v{} | shards={} slots/shard={} | HTTP {} | UDP {}",
        env!("CARGO_PKG_VERSION"),
        ledger::N_SHARDS,
        ledger::SLOTS_PER_SHARD,
        HTTP_ADDR,
        clearinghouse::UDP_ADDR,
    );

    axum::Server::bind(&HTTP_ADDR.parse().unwrap())
        .serve(app.into_make_service())
        .await
        .unwrap();
}
