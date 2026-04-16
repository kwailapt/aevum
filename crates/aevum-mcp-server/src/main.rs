// crates/aevum-mcp-server/src/main.rs
//
// Pillar: I/II/III. PACR field: ALL.
// Entry point for the Aevum MCP Gateway.
//
// Usage:
//   aevum-mcp-server --transport stdio
//   aevum-mcp-server --transport http --port 8889

#![forbid(unsafe_code)]

mod resources;
mod router;
mod state;
mod symbolizer;
mod tools;
mod transport;

use std::env;
use std::sync::Arc;

use state::AppState;

const DEFAULT_LEDGER_PATH: &str = "/var/lib/aevum/mcp-ledger.bin";

#[tokio::main(flavor = "multi_thread", worker_threads = 2)]
async fn main() {
    let args: Vec<String> = env::args().collect();
    let transport = parse_transport(&args);
    let _port = parse_port(&args).unwrap_or(8889);
    let ledger_path = parse_ledger_path(&args).unwrap_or_else(|| DEFAULT_LEDGER_PATH.to_owned());

    // Construct shared AppState (opens/creates PACR ledger).
    let app_state: Arc<AppState> = match AppState::new(&ledger_path).await {
        Ok(s) => s,
        Err(e) => {
            eprintln!("fatal: failed to open PACR ledger at {ledger_path}: {e}");
            std::process::exit(1);
        }
    };

    match transport {
        Transport::Stdio => {
            #[cfg(feature = "transport-stdio")]
            transport::stdio::run(Arc::clone(&app_state)).await;
            #[cfg(not(feature = "transport-stdio"))]
            eprintln!("stdio transport not compiled in (missing feature transport-stdio)");
        }
        Transport::Http => {
            #[cfg(feature = "transport-http")]
            transport::http::run(_port, Arc::clone(&app_state)).await;
            #[cfg(not(feature = "transport-http"))]
            eprintln!("http transport not compiled in (missing feature transport-http)");
        }
    }
}

enum Transport {
    Stdio,
    Http,
}

fn parse_transport(args: &[String]) -> Transport {
    for i in 0..args.len() {
        if args[i] == "--transport" {
            if let Some(v) = args.get(i + 1) {
                return match v.as_str() {
                    "http" => Transport::Http,
                    _ => Transport::Stdio,
                };
            }
        }
    }
    Transport::Stdio
}

fn parse_port(args: &[String]) -> Option<u16> {
    for i in 0..args.len() {
        if args[i] == "--port" {
            return args.get(i + 1)?.parse().ok();
        }
    }
    None
}

fn parse_ledger_path(args: &[String]) -> Option<String> {
    for i in 0..args.len() {
        if args[i] == "--ledger" {
            return args.get(i + 1).cloned();
        }
    }
    None
}
