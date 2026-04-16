// crates/aevum-mcp-server/src/transport/mod.rs
#![forbid(unsafe_code)]

#[cfg(feature = "transport-stdio")]
pub mod stdio;

#[cfg(feature = "transport-http")]
pub mod http;
