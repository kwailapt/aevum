//! Aevum CLI — Phase 5 runtime integration.
//!
//! Commands:
//!   aevum run    [--ledger <dir>] [--config <toml>]  — start the Aevum Core runtime
//!   aevum status [--ledger <dir>]                    — show runtime status
//!   aevum verify [--ledger <dir>]                    — verify ledger integrity
//!   aevum export [--ledger <dir>]                    — export PACR records as JSON
//!   aevum merge  <src> <dst>                         — merge two ledger directories

use std::path::PathBuf;

use serde::Deserialize;

use aevum_core::runtime::{
    export_ledger, merge_ledgers, read_status, start, verify_ledger, RuntimeConfig,
};
#[cfg(feature = "light_node")]
use aevum_core::{runtime::start_light, TailscaleForwarder};

// ── Node config (light-node.toml) ─────────────────────────────────────────────

/// `[forwarder]` section in `light-node.toml`.
#[derive(Debug, Deserialize, Default)]
struct ForwarderConfig {
    genesis_tailscale_ip: String,
    genesis_port: u16,
}

/// Subset of fields understood from a `light-node.toml` config file.
///
/// Unknown keys are silently ignored (via `#[serde(deny_unknown_fields)]` is
/// intentionally NOT set so the file can carry deployment notes like `feature`
/// without causing parse errors).
#[derive(Debug, Deserialize, Default)]
struct NodeConfig {
    /// TCP port for the CSO reputation HTTP API.  Maps to `RuntimeConfig::cso_http_port`.
    cso_http_port: Option<u16>,
    /// tokio worker threads.  Maps to `RuntimeConfig::worker_threads`.
    max_threads: Option<usize>,
    /// Ledger directory path.  Maps to `RuntimeConfig::ledger_dir`.
    ledger_path: Option<String>,
    /// Forwarder config (light_node only).
    forwarder: Option<ForwarderConfig>,
    // `feature` and other deployment-only keys are silently ignored.
}

impl NodeConfig {
    /// Load a TOML config file from `path`.  Exits the process on parse error.
    fn load(path: &str) -> Self {
        let text = match std::fs::read_to_string(path) {
            Ok(t) => t,
            Err(e) => {
                eprintln!("aevum: cannot read config '{path}': {e}");
                std::process::exit(1);
            }
        };
        match toml::from_str(&text) {
            Ok(cfg) => cfg,
            Err(e) => {
                eprintln!("aevum: cannot parse config '{path}': {e}");
                std::process::exit(1);
            }
        }
    }

    /// Apply this config on top of a base `RuntimeConfig`.
    ///
    /// Priority: CLI flag `--ledger` was already applied to `base.ledger_dir`
    /// before this call.  `ledger_path` in the TOML overrides it *only* when
    /// `--ledger` was not supplied (detected by checking whether `ledger_dir`
    /// is still the default `"ledger"` path).
    fn apply(self, mut base: RuntimeConfig, ledger_from_cli: bool) -> RuntimeConfig {
        if let Some(port) = self.cso_http_port {
            base.cso_http_port = Some(port);
        }
        if let Some(threads) = self.max_threads {
            base.worker_threads = threads;
        }
        if !ledger_from_cli {
            if let Some(path) = self.ledger_path {
                base.ledger_dir = PathBuf::from(path);
            }
        }
        base
    }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

fn print_usage() {
    eprintln!(
        "aevum — Aevum Core CLI\n\
         \n\
         USAGE:\n\
         \taevum run    [--ledger <dir>] [--config <toml>]\n\
         \taevum status [--ledger <dir>]\n\
         \taevum verify [--ledger <dir>]\n\
         \taevum export [--ledger <dir>]\n\
         \taevum merge  <src-dir> <dst-dir>\n\
         \n\
         OPTIONS:\n\
         \t--ledger <dir>    Ledger directory [default: ledger]\n\
         \t--config <toml>   Node config file (e.g. light-node.toml)"
    );
}

/// Parse `--ledger <dir>` from `args`; removes the two tokens and returns
/// `(path, was_present)`.
fn parse_ledger_flag(args: &mut Vec<String>) -> (PathBuf, bool) {
    if let Some(pos) = args.iter().position(|a| a == "--ledger") {
        if pos + 1 < args.len() {
            let dir = PathBuf::from(args[pos + 1].clone());
            args.drain(pos..=pos + 1);
            return (dir, true);
        }
    }
    (PathBuf::from("ledger"), false)
}

/// Parse `--config <path>` from `args`; removes the two tokens and returns
/// the path string (or `None` if the flag was absent).
fn parse_config_flag(args: &mut Vec<String>) -> Option<String> {
    if let Some(pos) = args.iter().position(|a| a == "--config") {
        if pos + 1 < args.len() {
            let path = args[pos + 1].clone();
            args.drain(pos..=pos + 1);
            return Some(path);
        }
    }
    None
}

// ── tokio entrypoint ──────────────────────────────────────────────────────────

#[tokio::main(flavor = "multi_thread", worker_threads = 2)]
async fn main() {
    let mut args: Vec<String> = std::env::args().skip(1).collect();

    if args.is_empty() {
        print_usage();
        std::process::exit(1);
    }

    let subcmd = args.remove(0);
    match subcmd.as_str() {
        "run" => cmd_run(args).await,
        "status" => cmd_status(args).await,
        "verify" => cmd_verify(args).await,
        "export" => cmd_export(args).await,
        "merge" => cmd_merge(args).await,
        "help" | "--help" | "-h" => print_usage(),
        other => {
            eprintln!("aevum: unknown command '{other}'\n");
            print_usage();
            std::process::exit(1);
        }
    }
}

// ── Subcommand handlers ───────────────────────────────────────────────────────

async fn cmd_run(mut args: Vec<String>) {
    // 1. Parse CLI flags (order of --ledger / --config is irrelevant).
    let (ledger_dir, ledger_from_cli) = parse_ledger_flag(&mut args);
    let config_path = parse_config_flag(&mut args);

    // 2. Start from default RuntimeConfig, apply --ledger.
    let base = RuntimeConfig {
        ledger_dir,
        ..RuntimeConfig::default()
    };

    // 3. Overlay TOML config (if supplied).
    // Keep node_cfg alive so light_node can read [forwarder] after apply().
    let (cfg, node_cfg) = if let Some(ref path) = config_path {
        let node_cfg = NodeConfig::load(path);
        let cfg = node_cfg.apply(base, ledger_from_cli);
        // Re-load to get forwarder field (apply() consumes node_cfg).
        let node_cfg2 = NodeConfig::load(path);
        (cfg, Some(node_cfg2))
    } else {
        (base, None)
    };

    // 4. light_node: Dumb Pipe path — zero DashMap, zero persistence.
    #[cfg(feature = "light_node")]
    {
        let fwd_cfg = node_cfg.and_then(|c| c.forwarder).unwrap_or_else(|| {
            eprintln!("aevum: light_node requires [forwarder] section in --config");
            std::process::exit(1);
        });
        let forwarder =
            TailscaleForwarder::new(&fwd_cfg.genesis_tailscale_ip, fwd_cfg.genesis_port);
        eprintln!(
            "aevum: light_node dumb-pipe starting (→ {}:{})",
            fwd_cfg.genesis_tailscale_ip, fwd_cfg.genesis_port,
        );
        if let Err(e) = start_light(cfg, forwarder).await {
            eprintln!("aevum: light_node failed: {e}");
            std::process::exit(1);
        }
        return;
    }

    // 5. genesis_node: full runtime path.
    #[cfg(not(feature = "light_node"))]
    {
        let _ = node_cfg; // suppress unused warning on genesis builds
        eprintln!(
            "aevum: starting runtime (ledger={}, cso_http_port={}, threads={}{})",
            cfg.ledger_dir.display(),
            cfg.cso_http_port
                .map(|p| p.to_string())
                .unwrap_or_else(|| "disabled".into()),
            cfg.worker_threads,
            config_path
                .as_deref()
                .map(|p| format!(", config={p}"))
                .unwrap_or_default(),
        );

        let _state = match start(cfg).await {
            Ok(s) => s,
            Err(e) => {
                eprintln!("aevum: failed to start runtime: {e}");
                std::process::exit(1);
            }
        };

        tokio::signal::ctrl_c()
            .await
            .expect("failed to listen for ctrl-c");

        eprintln!("aevum: shutdown signal received, exiting.");
    }
}

async fn cmd_status(mut args: Vec<String>) {
    let (ledger_dir, _) = parse_ledger_flag(&mut args);

    match read_status(&ledger_dir).await {
        Some(s) => {
            println!("record_count          : {}", s.record_count);
            println!("bits_erased           : {}", s.bits_erased);
            println!("statistical_complexity: {:.4}", s.statistical_complexity);
            println!("entropy_rate          : {:.4}", s.entropy_rate);
            println!("is_dormant            : {}", s.is_dormant);
            println!("updated_at            : {}", s.updated_at);
        }
        None => {
            eprintln!(
                "aevum: no status found in '{}' — is the runtime running?",
                ledger_dir.display()
            );
            std::process::exit(1);
        }
    }
}

async fn cmd_verify(mut args: Vec<String>) {
    let (ledger_dir, _) = parse_ledger_flag(&mut args);

    match verify_ledger(&ledger_dir).await {
        Ok((total, invalid)) => {
            println!("total   : {total}");
            println!("invalid : {invalid}");
            if invalid > 0 {
                eprintln!("aevum: WARN — {invalid} record(s) failed PACR validation");
                std::process::exit(2);
            } else {
                println!("aevum: ledger OK");
            }
        }
        Err(e) => {
            eprintln!("aevum: verify failed: {e}");
            std::process::exit(1);
        }
    }
}

async fn cmd_export(mut args: Vec<String>) {
    let (ledger_dir, _) = parse_ledger_flag(&mut args);

    match export_ledger(&ledger_dir).await {
        Ok(records) => match serde_json::to_string_pretty(&records) {
            Ok(json) => println!("{json}"),
            Err(e) => {
                eprintln!("aevum: serialisation error: {e}");
                std::process::exit(1);
            }
        },
        Err(e) => {
            eprintln!("aevum: export failed: {e}");
            std::process::exit(1);
        }
    }
}

async fn cmd_merge(args: Vec<String>) {
    if args.len() < 2 {
        eprintln!("aevum: merge requires <src-dir> <dst-dir>");
        print_usage();
        std::process::exit(1);
    }

    let src = PathBuf::from(&args[0]);
    let dst = PathBuf::from(&args[1]);

    if let Err(e) = tokio::fs::create_dir_all(&dst).await {
        eprintln!("aevum: cannot create dst dir '{}': {e}", dst.display());
        std::process::exit(1);
    }

    match merge_ledgers(&src, &dst).await {
        Ok(added) => {
            println!(
                "added {added} new record(s) from '{}' into '{}'",
                src.display(),
                dst.display()
            );
        }
        Err(e) => {
            eprintln!("aevum: merge failed: {e}");
            std::process::exit(1);
        }
    }
}
