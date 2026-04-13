//! Aevum CLI — Phase 5 runtime integration.
//!
//! Commands:
//!   aevum run    [--ledger <dir>]  — start the Aevum Core runtime
//!   aevum status [--ledger <dir>]  — show runtime status
//!   aevum verify [--ledger <dir>]  — verify ledger integrity
//!   aevum export [--ledger <dir>]  — export PACR records as JSON
//!   aevum merge  <src> <dst>       — merge two ledger directories

use std::path::PathBuf;

use aevum_core::runtime::{
    RuntimeConfig, export_ledger, merge_ledgers, read_status, start, verify_ledger,
};

fn print_usage() {
    eprintln!(
        "aevum — Aevum Core CLI\n\
         \n\
         USAGE:\n\
         \taevum run    [--ledger <dir>]\n\
         \taevum status [--ledger <dir>]\n\
         \taevum verify [--ledger <dir>]\n\
         \taevum export [--ledger <dir>]\n\
         \taevum merge  <src-dir> <dst-dir>\n\
         \n\
         OPTIONS:\n\
         \t--ledger <dir>   Ledger directory [default: ledger]"
    );
}

/// Parse `--ledger <dir>` from `args` (mutable slice); returns the value and
/// removes the two consumed arguments in-place.
fn parse_ledger_flag(args: &mut Vec<String>) -> PathBuf {
    if let Some(pos) = args.iter().position(|a| a == "--ledger") {
        if pos + 1 < args.len() {
            let dir = PathBuf::from(args[pos + 1].clone());
            args.drain(pos..=pos + 1);
            return dir;
        }
    }
    PathBuf::from("ledger")
}

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
        "help" | "--help" | "-h" => {
            print_usage();
        }
        other => {
            eprintln!("aevum: unknown command '{other}'\n");
            print_usage();
            std::process::exit(1);
        }
    }
}

// ── Subcommand handlers ───────────────────────────────────────────────────────

async fn cmd_run(mut args: Vec<String>) {
    let ledger_dir = parse_ledger_flag(&mut args);

    let cfg = RuntimeConfig {
        ledger_dir,
        worker_threads: 2,
        ..RuntimeConfig::default()
    };

    eprintln!(
        "aevum: starting runtime (ledger={})",
        cfg.ledger_dir.display()
    );

    let _state = match start(cfg).await {
        Ok(s) => s,
        Err(e) => {
            eprintln!("aevum: failed to start runtime: {e}");
            std::process::exit(1);
        }
    };

    // Wait for Ctrl-C.
    tokio::signal::ctrl_c()
        .await
        .expect("failed to listen for ctrl-c");

    eprintln!("aevum: shutdown signal received, exiting.");
}

async fn cmd_status(mut args: Vec<String>) {
    let ledger_dir = parse_ledger_flag(&mut args);

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
    let ledger_dir = parse_ledger_flag(&mut args);

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
    let ledger_dir = parse_ledger_flag(&mut args);

    match export_ledger(&ledger_dir).await {
        Ok(records) => {
            match serde_json::to_string_pretty(&records) {
                Ok(json) => println!("{json}"),
                Err(e) => {
                    eprintln!("aevum: serialisation error: {e}");
                    std::process::exit(1);
                }
            }
        }
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

    // Ensure dst exists.
    if let Err(e) = tokio::fs::create_dir_all(&dst).await {
        eprintln!("aevum: cannot create dst dir '{}': {e}", dst.display());
        std::process::exit(1);
    }

    match merge_ledgers(&src, &dst).await {
        Ok(added) => {
            println!("added {added} new record(s) from '{}' into '{}'",
                src.display(), dst.display());
        }
        Err(e) => {
            eprintln!("aevum: merge failed: {e}");
            std::process::exit(1);
        }
    }
}
