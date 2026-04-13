//! UDP clearinghouse — fast χ-Quanta settlement engine.
//!
//! Wire protocol (10 bytes, little-endian):
//!   [0..8]  node_id : u64   — routed via splitmix64 to the correct shard
//!   [8..10] cost    : u16   — must be ≥ LANDAUER_CHI (enforced by deduct)
//!
//! Response (8 bytes):
//!   new balance : u64  — or u64::MAX (INSUFFICIENT) on failed deduction
//!
//! The clearinghouse runs on a dedicated OS thread with a non-blocking socket
//! and a spin-sleep loop.  It does not participate in the Tokio runtime so
//! it cannot be starved by async task scheduling.

use crate::ledger::ShardedLedger;
use crate::thermodynamics::TrilemmaMode;
use std::net::UdpSocket;
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

pub const UDP_ADDR: &str = "0.0.0.0:7777";
const MAX_RPS: u32 = 5_000;

fn notify_systemd(msg: &str) {
    if let Ok(path) = std::env::var("NOTIFY_SOCKET") {
        if let Ok(sock) = std::os::unix::net::UnixDatagram::unbound() {
            let _ = sock.send_to(msg.as_bytes(), path);
        }
    }
}

pub fn serve(ledger: Arc<ShardedLedger>) {
    thread::spawn(move || {
        let socket = UdpSocket::bind(UDP_ADDR).expect("UDP bind failed");
        socket.set_nonblocking(true).expect("set_nonblocking failed");

        notify_systemd("READY=1");
        println!("Clearinghouse online | UDP {UDP_ADDR}");

        let mut buf      = [0u8; 16];
        let mut rps: u32 = 0;
        let mut tick     = Instant::now();
        let mut ctr: u32 = 0;

        loop {
            ctr = ctr.wrapping_add(1);

            // Amortise Instant::now() syscall: sample every 1024 iterations.
            if ctr % 1024 == 0 && tick.elapsed() >= Duration::from_secs(1) {
                rps  = 0;
                tick = Instant::now();
                notify_systemd("WATCHDOG=1");
            }

            match socket.recv_from(&mut buf) {
                Ok((10, src)) => {
                    rps += 1;
                    if rps > MAX_RPS { continue; }

                    let node_id = u64::from_le_bytes(buf[0..8].try_into().unwrap());
                    let cost    = u16::from_le_bytes(buf[8..10].try_into().unwrap()) as u64;

                    // splitmix64 routing happens inside ledger.deduct()
                    // UDP protocol carries no mode field → always Balanced (1× cost)
                    let balance = ledger.deduct(node_id, cost, TrilemmaMode::Balanced);
                    let _ = socket.send_to(&balance.to_le_bytes(), src);
                }
                Ok(_) => {}   // wrong-length packet: ignore
                Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    thread::sleep(Duration::from_micros(100));
                }
                Err(_) => {}
            }
        }
    });
}
