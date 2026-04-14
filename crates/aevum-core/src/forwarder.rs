//! Pillar: I. PACR field: none (light_node does not produce PACR records).
//!
//! **TailscaleForwarder** — stateless UDP pipe to genesis_node.
//!
//! Design: End-to-End Principle (Saltzer, Reed, Clark 1984).
//! Intelligence at the edges (M1 genesis_node), dumb pipe in the middle (AWS light_node).
//!
//! This module forwards raw envelope bytes to the genesis_node via Tailscale UDP.
//! It does NOT parse CTP/AgentCard, does NOT maintain causal-dag,
//! does NOT produce PacrRecords. It is a thermodynamic filter + pipe.
//!
//! # Complexity
//!
//! O(1) per call. No heap-allocated state. No DashMap. No persistence.
//! Each `forward` call binds an ephemeral UDP socket, sends, and drops it.

#![forbid(unsafe_code)]

use std::net::SocketAddr;

use tokio::net::UdpSocket;

/// Stateless UDP forwarder to the genesis_node over Tailscale.
///
/// Pillar: I — O(1), lock-free, no shared mutable state.
pub struct TailscaleForwarder {
    genesis_addr: SocketAddr,
}

impl TailscaleForwarder {
    /// Construct a forwarder targeting `genesis_ip:port`.
    ///
    /// # Panics
    ///
    /// Panics if `genesis_ip` is not a valid IP address string.
    /// This is intentional: a misconfigured genesis address is a fatal
    /// startup error, not a recoverable runtime condition.
    #[must_use]
    pub fn new(genesis_ip: &str, port: u16) -> Self {
        let addr_str = format!("{genesis_ip}:{port}");
        let genesis_addr = addr_str
            .parse()
            .expect("genesis_tailscale_ip must be a valid IP address");
        Self { genesis_addr }
    }

    /// Forward `raw_bytes` to genesis_node via UDP.
    ///
    /// Binds an ephemeral local socket, sends once, drops the socket.
    /// O(1). No state retained after return.
    ///
    /// # Errors
    ///
    /// Returns `std::io::Error` if the socket cannot be bound or the send fails.
    pub async fn forward(&self, raw_bytes: &[u8]) -> Result<(), std::io::Error> {
        let socket = UdpSocket::bind("0.0.0.0:0").await?;
        socket.send_to(raw_bytes, self.genesis_addr).await?;
        Ok(())
    }

    /// Return the configured genesis address (for logging/status).
    #[must_use]
    pub fn genesis_addr(&self) -> SocketAddr {
        self.genesis_addr
    }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn new_parses_valid_ip() {
        let f = TailscaleForwarder::new("100.113.207.108", 8420);
        assert_eq!(f.genesis_addr().port(), 8420);
    }

    #[test]
    #[should_panic(expected = "genesis_tailscale_ip must be a valid IP address")]
    fn new_panics_on_invalid_ip() {
        TailscaleForwarder::new("not-an-ip", 8420);
    }

    #[tokio::test]
    async fn forward_sends_to_loopback() {
        // Bind a listener on loopback to receive the forwarded bytes.
        let listener = UdpSocket::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();

        let forwarder = TailscaleForwarder::new("127.0.0.1", port);
        let payload = b"test-envelope";
        forwarder.forward(payload).await.unwrap();

        let mut buf = [0u8; 64];
        let (n, _) = listener.recv_from(&mut buf).await.unwrap();
        assert_eq!(&buf[..n], payload);
    }
}
