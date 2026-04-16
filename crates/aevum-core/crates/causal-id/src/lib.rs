// crates/causal-id/src/lib.rs
//
// Pillar: I (causal partial order). PACR field: ι.
//
// Generates globally unique, monotonically sortable CausalIds in ULID format.
//
// # ULID encoding (128 bits)
//
//   Bits [127:80] — 48-bit millisecond timestamp
//                   Physical basis: enables efficient range scans over
//                   causal-temporal neighbourhoods in storage (Pillar I).
//                   NOT used for causal ordering — Π determines that.
//
//   Bits  [79:0]  — 80-bit randomness
//                   Provides ~2^80 unique IDs per millisecond per process.
//                   Probability of collision at 10^11 nodes generating 10^6
//                   IDs/ms each: negligible (birthday bound >> 10^11 × 10^6).
//
// # Monotonicity
//
// Within the same millisecond, the lower 16 bits act as a sequence counter,
// guaranteeing lexicographic monotonicity for serialized records from a
// single generator instance. This is O(1) and lock-free.
//
// # Entropy source
//
// Uses a thread-local xorshift64* PRNG seeded from system time + an atomic
// counter. This is NOT cryptographically secure, but ULID collision resistance
// depends on the birthday bound over 80 random bits, not secrecy. For a
// system at 10^11 scale, the collision probability per second is ~10^-15.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]

use pacr_types::CausalId;
use std::cell::Cell;
use std::fmt;
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

// ── Entropy source ─────────────────────────────────────────────────────────────

/// Global counter used to differentiate per-thread seeds at startup.
static GLOBAL_SEED_COUNTER: AtomicU64 = AtomicU64::new(1);

thread_local! {
    /// Per-thread xorshift64* state.  Seeded once from time + global counter.
    static PRNG_STATE: Cell<u64> = Cell::new(0);
}

/// Generate a pseudorandom `u64` using xorshift64*.
///
/// Quality: passes BigCrush. Period = 2^64 - 1.
/// Not cryptographically secure, but sufficient for ULID collision avoidance.
fn rand_u64() -> u64 {
    PRNG_STATE.with(|cell| {
        let mut x = cell.get();

        if x == 0 {
            // First call on this thread: seed from wall time + global counter.
            let nanos = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|d| d.subsec_nanos())
                .unwrap_or(0) as u64;
            let cnt = GLOBAL_SEED_COUNTER.fetch_add(1, Ordering::Relaxed);
            // Mix time and counter to avoid identical seeds when multiple
            // threads initialise within the same nanosecond.
            x = nanos
                .wrapping_add(cnt.wrapping_mul(0x9e37_79b9_7f4a_7c15));
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
        }

        // xorshift64*
        x ^= x << 12;
        x ^= x >> 25;
        x ^= x << 27;
        let result = x.wrapping_mul(0x2545_f491_4f6c_dd1d);
        cell.set(x);
        result
    })
}

/// Returns the current time in milliseconds since UNIX epoch.
fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}

// ── Per-thread last-generated state ───────────────────────────────────────────

thread_local! {
    /// The full 128-bit value of the last CausalId generated on this thread.
    /// Used to enforce strict monotonicity: within the same millisecond we
    /// increment the previous value by 1 (ULID spec §monotonicity).
    static LAST_ID: Cell<u128> = Cell::new(0);
}

// ── Public API ─────────────────────────────────────────────────────────────────

/// Error returned by the ULID generator.
#[derive(Debug, Clone, thiserror::Error)]
pub enum CausalIdError {
    /// The 80-bit random part overflowed within a single millisecond.
    /// Physical meaning: this thread generated 2^80 IDs in < 1 ms, which
    /// is physically impossible with current hardware. This error exists for
    /// completeness; in practice it will never fire.
    #[error(
        "ULID random-part overflow: 2^80 IDs generated within one millisecond. \
         This is a theoretical limit; contact the Aevum maintainers."
    )]
    SequenceOverflow,
}

/// Generates a new [`CausalId`] in ULID format.
///
/// # Monotonicity guarantee
/// Within a single thread, IDs are strictly increasing: each call returns a
/// value greater than the previous. This is the ULID spec §monotonicity
/// guarantee: within the same millisecond, the previous 128-bit value is
/// incremented by 1 in the random part.
///
/// # Thread safety
/// Thread-local state only — no cross-thread synchronisation.
/// IDs from different threads are unique (with overwhelming probability)
/// but are NOT globally ordered (causal order comes from Π, not ι values).
///
/// # Complexity
/// O(1). No locks.
///
/// # Errors
/// Returns [`CausalIdError::SequenceOverflow`] if the 80-bit random counter
/// would overflow (requires 2^80 calls within a single millisecond).
pub fn new_id() -> Result<CausalId, CausalIdError> {
    let ms = now_ms();
    let ts_part: u128 = ((ms & 0xFFFF_FFFF_FFFF) as u128) << 80;

    let new_id = LAST_ID.with(|cell| {
        let prev = cell.get();
        let prev_ts = prev >> 80;

        let id = if (ms as u128) > prev_ts {
            // New millisecond: generate a fresh random 80-bit lower half.
            let r_hi: u128 = (rand_u64() as u128) << 16;
            let r_lo: u128 = (rand_u64() & 0xFFFF) as u128;
            ts_part | r_hi | r_lo
        } else {
            // Same millisecond: increment the full 128-bit value by 1.
            // This keeps the timestamp prefix intact and increments the random part.
            let next = prev.checked_add(1).ok_or(CausalIdError::SequenceOverflow)?;
            // Ensure increment did not spill into the timestamp bits.
            if next >> 80 != prev >> 80 {
                return Err(CausalIdError::SequenceOverflow);
            }
            next
        };

        cell.set(id);
        Ok(id)
    })?;

    Ok(CausalId(new_id))
}

/// Generates a new [`CausalId`] that is guaranteed to succeed.
///
/// Falls back to a fully random ID (no timestamp locality) in the extremely
/// rare case of sequence overflow. Use this when you prefer robustness over
/// strict per-millisecond monotonicity.
#[must_use]
pub fn new_id_infallible() -> CausalId {
    new_id().unwrap_or_else(|_| {
        // Sequence overflow: use pure random fallback
        // The timestamp bits are set to 0xFFFF_FFFF_FFFF to sort last,
        // making it visually obvious these are overflow IDs.
        let rand_hi: u128 = (rand_u64() as u128) << 16;
        let rand_lo: u128 = (rand_u64() & 0xFFFF) as u128;
        CausalId(0xFFFF_FFFF_FFFF_0000_0000_0000_0000_0000_u128 | rand_hi | rand_lo)
    })
}

// ── Crockford Base32 display ───────────────────────────────────────────────────

/// Crockford Base32 alphabet (excludes I, L, O, U to avoid confusion).
const CROCKFORD: &[u8; 32] = b"0123456789ABCDEFGHJKMNPQRSTVWXYZ";

/// Encodes a [`CausalId`] as a 26-character Crockford Base32 string.
///
/// This is the canonical human-readable representation of a ULID.
/// Format: `01ARZ3NDEKTSV4RRFFQ69G5FAV` (26 chars, lexicographically sortable).
#[must_use]
pub fn encode(id: CausalId) -> String {
    // 128 bits → 26 × 5-bit groups (130 bits; 2 leading bits are always 0 in ULID)
    let mut buf = [0u8; 26];
    let mut n = id.0;
    for ch in buf.iter_mut().rev() {
        *ch = CROCKFORD[(n & 0x1F) as usize];
        n >>= 5;
    }
    // SAFETY: all bytes come from CROCKFORD which is pure ASCII.
    String::from_utf8(buf.to_vec()).unwrap_or_else(|_| format!("{:032X}", id.0))
}

/// Decodes a Crockford Base32 ULID string back to a [`CausalId`].
///
/// # Errors
/// Returns [`DecodeError`] if the string is not a valid 26-character ULID.
pub fn decode(s: &str) -> Result<CausalId, DecodeError> {
    let bytes = s.as_bytes();
    if bytes.len() != 26 {
        return Err(DecodeError::WrongLength { got: bytes.len() });
    }

    let mut n = 0_u128;
    for &b in bytes {
        let digit = crockford_digit(b).ok_or(DecodeError::InvalidChar(b as char))?;
        n = (n << 5) | u128::from(digit);
    }

    Ok(CausalId(n))
}

fn crockford_digit(b: u8) -> Option<u8> {
    match b {
        b'0'..=b'9' => Some(b - b'0'),
        b'A'..=b'H' => Some(b - b'A' + 10),
        b'J' | b'K' => Some(b - b'J' + 18),
        b'M' | b'N' => Some(b - b'M' + 20),
        b'P'..=b'T' => Some(b - b'P' + 22),
        b'V'..=b'Z' => Some(b - b'V' + 27),
        // lowercase aliases
        b'a'..=b'h' => Some(b - b'a' + 10),
        b'j' | b'k' => Some(b - b'j' + 18),
        b'm' | b'n' => Some(b - b'm' + 20),
        b'p'..=b't' => Some(b - b'p' + 22),
        b'v'..=b'z' => Some(b - b'v' + 27),
        _ => None,
    }
}

/// Error decoding a Crockford Base32 ULID string.
#[derive(Debug, Clone, thiserror::Error)]
pub enum DecodeError {
    #[error("ULID must be 26 characters; got {got}")]
    WrongLength { got: usize },
    #[error("Invalid Crockford Base32 character: '{0}'")]
    InvalidChar(char),
}

/// Display wrapper that shows a [`CausalId`] as a Crockford Base32 ULID.
pub struct UlidDisplay(pub CausalId);

impl fmt::Display for UlidDisplay {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&encode(self.0))
    }
}

// ── Tests ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashSet;

    #[test]
    fn generated_ids_are_unique() {
        let ids: HashSet<u128> = (0..10_000)
            .map(|_| new_id().unwrap().0)
            .collect();
        // All 10 000 should be distinct
        assert_eq!(ids.len(), 10_000);
    }

    #[test]
    fn generated_ids_are_monotonic() {
        let ids: Vec<CausalId> = (0..1_000).map(|_| new_id().unwrap()).collect();
        for w in ids.windows(2) {
            assert!(w[0] <= w[1], "IDs must be non-decreasing");
        }
    }

    #[test]
    fn encode_decode_roundtrip() {
        for _ in 0..100 {
            let id = new_id().unwrap();
            let s = encode(id);
            let decoded = decode(&s).unwrap();
            assert_eq!(id, decoded);
        }
    }

    #[test]
    fn encode_produces_26_chars() {
        let id = new_id().unwrap();
        assert_eq!(encode(id).len(), 26);
    }

    #[test]
    fn genesis_encodes_as_zeros() {
        let s = encode(CausalId::GENESIS);
        assert!(s.chars().all(|c| c == '0'));
    }

    #[test]
    fn timestamp_prefix_is_set() {
        let id = new_id().unwrap();
        // Top 48 bits should be a plausible Unix timestamp in ms (> 2020-01-01)
        let ms = (id.0 >> 80) as u64;
        assert!(ms > 1_577_836_800_000_u64, "timestamp looks implausible: {ms}");
    }
}
