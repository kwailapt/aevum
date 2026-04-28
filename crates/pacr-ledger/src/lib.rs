// crates/pacr-ledger/src/lib.rs
//
// Pillar: I (append-only, causally ordered). PACR fields: all (stores full records).
//
// An append-only, content-addressed persistent store for PACR records.
//
// # Storage model
//
// Physical basis: the Second Law of Thermodynamics mandates that erasing a
// committed record would require expending energy — it is not physically "free".
// Append-only storage is the engineering realisation of this irreversibility.
//
// # File format
//
// The ledger is a single flat file with this layout:
//
//   [8 bytes] Magic header: b"AEVUMLDR"
//   [8 bytes] Version: 0x0000_0000_0001_0000 (major=1, minor=0)
//   [repeated records:]
//     [4 bytes, LE u32] Record length in bytes
//     [N bytes]         JSON-encoded PacrRecord (UTF-8)
//
// JSON is used for debuggability and forward compatibility. Binary encoding
// (bincode / postcard) would be more efficient but requires a fixed schema.
// Since PACR is append-only, JSON's verbosity is the conservative choice.
//
// # In-memory index
//
// A `HashMap<CausalId, u64>` maps each record's ι to its byte offset in the
// file. This allows O(1) random access by causal ID.
//
// On open, the entire file is replayed to rebuild the index. For large ledgers,
// a separate index file (Bloom filter + offset table) could be added; that is
// a future evolution proposal, not a Day-0 requirement.
//
// # Durability
//
// Each `append()` calls `file.sync_data()` to flush OS page cache to disk.
// This is conservative but correct. Batched writes are a future optimisation.

#![forbid(unsafe_code)]
#![deny(clippy::all, clippy::pedantic)]
#![allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::cast_possible_wrap,
    clippy::similar_names,
    clippy::doc_markdown,
    clippy::unreadable_literal,
    clippy::redundant_closure,
    clippy::unwrap_or_default,
    clippy::doc_overindented_list_items,
    clippy::cloned_instead_of_copied,
    clippy::needless_pass_by_value,
    clippy::cast_lossless,
    clippy::module_name_repetitions,
    clippy::into_iter_without_iter,
    clippy::unnested_or_patterns,
    clippy::let_underscore_untyped,
    clippy::manual_let_else,
    clippy::suspicious_open_options,
    clippy::iter_not_returning_iterator,
    clippy::must_use_candidate,
    clippy::ptr_arg,
    clippy::manual_midpoint,
    clippy::map_unwrap_or,
    clippy::bool_to_int_with_if,
    clippy::missing_panics_doc
)]

use pacr_types::{CausalId, PacrRecord, ValidationIssue};
use std::collections::HashMap;
use std::fs::{File, OpenOptions};
use std::io::{BufReader, Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};

// ── File format constants ──────────────────────────────────────────────────────

const MAGIC: &[u8; 8] = b"AEVUMLDR";
const VERSION: u64 = 0x0000_0000_0001_0000; // major=1, minor=0
const HEADER_SIZE: u64 = 16; // 8 (magic) + 8 (version)

// ── Error type ─────────────────────────────────────────────────────────────────

/// Errors produced by [`PacrLedger`] operations.
#[derive(Debug, thiserror::Error)]
pub enum LedgerError {
    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("JSON serialisation error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Record with id {0} already exists in the ledger (append-only violation)")]
    DuplicateId(CausalId),

    #[error("Ledger file has wrong magic header (expected AEVUMLDR)")]
    BadMagic,

    #[error("Unsupported ledger version: {0:#018x}")]
    UnsupportedVersion(u64),

    #[error("Corrupt record at offset {offset}: {reason}")]
    CorruptRecord { offset: u64, reason: String },

    #[error("Physical validation failed: {0:?}")]
    PhysicsViolation(Vec<ValidationIssue>),

    #[error("Predecessor {predecessor} of record {child} not present in the ledger")]
    MissingPredecessor {
        child: CausalId,
        predecessor: CausalId,
    },
}

// ── PacrLedger ─────────────────────────────────────────────────────────────────

/// An append-only, content-addressed persistent store for PACR records.
///
/// # Guarantees
/// - **Append-only**: once a record is committed, it cannot be modified or deleted.
/// - **Content-addressed**: records are looked up by their causal ID (ι).
/// - **Causally consistent**: all predecessors of a record must exist before
///   the record can be appended (topological invariant).
/// - **Physically validated**: records with physics violations are rejected by
///   default (configurable with [`PacrLedger::allow_physics_violations`]).
pub struct PacrLedger {
    /// Path to the ledger file (kept for diagnostics).
    path: PathBuf,

    /// The ledger file, kept open for appends.
    file: File,

    /// Current end-of-file position (next write offset).
    write_pos: u64,

    /// In-memory index: CausalId → byte offset of the 4-byte length prefix.
    index: HashMap<CausalId, u64>,

    /// If `true`, records with physics violations are appended with a warning
    /// rather than rejected. Default: `false`.
    allow_violations: bool,
}

impl PacrLedger {
    /// Opens (or creates) the ledger at `path`.
    ///
    /// If the file already exists, replays all records to rebuild the index.
    /// If the file is new, writes the magic header.
    ///
    /// # Errors
    /// Returns [`LedgerError`] if the file cannot be opened, or if any
    /// existing record fails to deserialise.
    pub fn open(path: impl AsRef<Path>) -> Result<Self, LedgerError> {
        let path = path.as_ref().to_owned();
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .open(&path)?;

        let file_len = file.metadata()?.len();

        if file_len == 0 {
            // New file: write header.
            let mut ledger = Self {
                path,
                file,
                write_pos: 0,
                index: HashMap::new(),
                allow_violations: false,
            };
            ledger.write_header()?;
            Ok(ledger)
        } else {
            // Existing file: validate header and replay records.
            let mut ledger = Self {
                path,
                file,
                write_pos: file_len,
                index: HashMap::new(),
                allow_violations: false,
            };
            ledger.validate_header()?;
            ledger.replay_index()?;
            Ok(ledger)
        }
    }

    /// Allow appending records that have physics violations.
    /// Disabled by default — physical violations are rejected.
    /// Enable this for testing or when ingesting data from untrusted sensors.
    pub fn allow_physics_violations(&mut self, allow: bool) {
        self.allow_violations = allow;
    }

    /// Appends a PACR record to the ledger.
    ///
    /// # Invariants enforced
    /// 1. No duplicate causal ID (append-only).
    /// 2. All predecessors must already be in the ledger (topological order).
    /// 3. No self-reference (no causal loops).
    /// 4. Physical validity (unless `allow_physics_violations` is set).
    ///
    /// # Complexity
    /// O(|Π|) for predecessor checks + O(|record|) for serialisation.
    ///
    /// # Errors
    /// Returns [`LedgerError`] if any invariant is violated or I/O fails.
    pub fn append(&mut self, record: PacrRecord) -> Result<(), LedgerError> {
        // ── Invariant 1: no duplicate ID ─────────────────────────────────────
        if self.index.contains_key(&record.id) {
            return Err(LedgerError::DuplicateId(record.id));
        }

        // ── Invariant 2: all predecessors present ─────────────────────────────
        for pred in &record.predecessors {
            if !pred.is_genesis() && !self.index.contains_key(pred) {
                return Err(LedgerError::MissingPredecessor {
                    child: record.id,
                    predecessor: *pred,
                });
            }
        }

        // ── Invariant 3 + 4: validate record ─────────────────────────────────
        let issues = record.validate();
        if !issues.is_empty() && !self.allow_violations {
            return Err(LedgerError::PhysicsViolation(issues));
        }

        // ── Serialise ─────────────────────────────────────────────────────────
        let json = serde_json::to_vec(&record)?;
        let len = u32::try_from(json.len()).map_err(|_| {
            std::io::Error::new(
                std::io::ErrorKind::InvalidData,
                "record JSON exceeds 4 GB — reduce payload size",
            )
        })?;

        // ── Write: length prefix + JSON ───────────────────────────────────────
        let offset = self.write_pos;
        self.file.seek(SeekFrom::End(0))?;
        self.file.write_all(&len.to_le_bytes())?;
        self.file.write_all(&json)?;
        self.file.sync_data()?;

        // ── Update index ──────────────────────────────────────────────────────
        self.index.insert(record.id, offset);
        self.write_pos += 4 + u64::from(len);

        Ok(())
    }

    /// Retrieves a record by its causal ID.
    ///
    /// Returns `None` if the ID is not in the ledger.
    ///
    /// # Complexity
    /// O(|record|) for deserialisation; O(1) index lookup.
    ///
    /// # Errors
    /// Returns [`LedgerError`] if the file seek or deserialisation fails.
    pub fn get(&mut self, id: &CausalId) -> Result<Option<PacrRecord>, LedgerError> {
        let offset = match self.index.get(id) {
            Some(&off) => off,
            None => return Ok(None),
        };

        self.file.seek(SeekFrom::Start(offset))?;
        let record = read_record_at(&mut self.file, offset)?;
        Ok(Some(record))
    }

    /// Returns the number of records in the ledger.
    #[must_use]
    pub fn len(&self) -> usize {
        self.index.len()
    }

    /// Returns `true` if the ledger contains no records.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        self.index.is_empty()
    }

    /// Returns `true` if the ledger contains a record with this causal ID.
    #[must_use]
    pub fn contains(&self, id: &CausalId) -> bool {
        self.index.contains_key(id)
    }

    /// Returns the path to the underlying ledger file.
    #[must_use]
    pub fn path(&self) -> &Path {
        &self.path
    }

    /// Iterates all records in file order (topological order by insertion).
    ///
    /// Returns a separate reader to avoid borrowing `self.file`.
    ///
    /// # Errors
    /// Returns [`LedgerError`] if the file cannot be opened for reading.
    pub fn iter(&self) -> Result<LedgerIterator, LedgerError> {
        let file = File::open(&self.path)?;
        let mut reader = BufReader::new(file);
        // Skip header
        reader.seek(SeekFrom::Start(HEADER_SIZE))?;
        Ok(LedgerIterator { reader })
    }

    // ── Internal ───────────────────────────────────────────────────────────────

    fn write_header(&mut self) -> Result<(), LedgerError> {
        self.file.seek(SeekFrom::Start(0))?;
        self.file.write_all(MAGIC)?;
        self.file.write_all(&VERSION.to_le_bytes())?;
        self.file.sync_data()?;
        self.write_pos = HEADER_SIZE;
        Ok(())
    }

    fn validate_header(&mut self) -> Result<(), LedgerError> {
        self.file.seek(SeekFrom::Start(0))?;
        let mut magic = [0u8; 8];
        self.file.read_exact(&mut magic)?;
        if &magic != MAGIC {
            return Err(LedgerError::BadMagic);
        }
        let mut ver_bytes = [0u8; 8];
        self.file.read_exact(&mut ver_bytes)?;
        let ver = u64::from_le_bytes(ver_bytes);
        // Accept version 1.x (minor version bumps are forward-compatible)
        if ver >> 16 != 1 {
            return Err(LedgerError::UnsupportedVersion(ver));
        }
        Ok(())
    }

    fn replay_index(&mut self) -> Result<(), LedgerError> {
        let mut offset = HEADER_SIZE;
        let file_len = self.file.metadata()?.len();

        self.file.seek(SeekFrom::Start(HEADER_SIZE))?;

        while offset < file_len {
            let record = read_record_at(&mut self.file, offset).map_err(|e| match e {
                LedgerError::Io(io_err) => LedgerError::CorruptRecord {
                    offset,
                    reason: io_err.to_string(),
                },
                LedgerError::Json(json_err) => LedgerError::CorruptRecord {
                    offset,
                    reason: json_err.to_string(),
                },
                other => other,
            })?;

            let json_len = {
                // Re-read length to compute next offset
                self.file.seek(SeekFrom::Start(offset))?;
                let mut len_buf = [0u8; 4];
                self.file.read_exact(&mut len_buf)?;
                u64::from(u32::from_le_bytes(len_buf))
            };

            self.index.insert(record.id, offset);
            offset += 4 + json_len;
            self.file.seek(SeekFrom::Start(offset))?;
        }

        Ok(())
    }
}

/// Reads a single record from the current file position.
///
/// Expects the file pointer to be at the 4-byte length prefix.
fn read_record_at(file: &mut File, _offset: u64) -> Result<PacrRecord, LedgerError> {
    let mut len_buf = [0u8; 4];
    file.read_exact(&mut len_buf)?;
    let len = u32::from_le_bytes(len_buf) as usize;

    let mut json_buf = vec![0u8; len];
    file.read_exact(&mut json_buf)?;

    let record = serde_json::from_slice(&json_buf)?;
    Ok(record)
}

// ── Iterator ───────────────────────────────────────────────────────────────────

/// An iterator over PACR records in insertion order.
/// Created by [`PacrLedger::iter`].
pub struct LedgerIterator {
    reader: BufReader<File>,
}

impl Iterator for LedgerIterator {
    type Item = Result<PacrRecord, LedgerError>;

    fn next(&mut self) -> Option<Self::Item> {
        // Try to read the 4-byte length prefix.
        let mut len_buf = [0u8; 4];
        match self.reader.read_exact(&mut len_buf) {
            Ok(()) => {}
            Err(e) if e.kind() == std::io::ErrorKind::UnexpectedEof => return None,
            Err(e) => return Some(Err(LedgerError::Io(e))),
        }

        let len = u32::from_le_bytes(len_buf) as usize;
        let mut json_buf = vec![0u8; len];
        if let Err(e) = self.reader.read_exact(&mut json_buf) {
            return Some(Err(LedgerError::Io(e)));
        }

        Some(serde_json::from_slice(&json_buf).map_err(LedgerError::Json))
    }
}

// ── Tests ──────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use bytes::Bytes;
    use pacr_types::{CognitiveSplit, Estimate, PacrBuilder, PredecessorSet, ResourceTriple};
    use smallvec::smallvec;

    fn tmp_path(suffix: &str) -> PathBuf {
        let path = std::env::temp_dir().join(format!("pacr_ledger_test_{suffix}.bin"));
        let _ = std::fs::remove_file(&path);
        path
    }

    fn make_record(id: u128, preds: PredecessorSet) -> PacrRecord {
        PacrBuilder::new()
            .id(CausalId(id))
            .predecessors(preds)
            .landauer_cost(Estimate::exact(1e-20))
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-19),
                time: Estimate::exact(1e-9),
                space: Estimate::exact(64.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(1.0),
                entropy_rate: Estimate::exact(0.5),
            })
            .payload(Bytes::from_static(b"test"))
            .build()
            .expect("test record should be valid")
    }

    #[test]
    fn create_and_reopen() {
        let path = tmp_path("reopen");
        {
            let mut ledger = PacrLedger::open(&path).unwrap();
            ledger.allow_physics_violations(true);
            let r = make_record(1, smallvec![CausalId::GENESIS]);
            ledger.append(r).unwrap();
            assert_eq!(ledger.len(), 1);
        }
        // Reopen and check index was replayed
        let ledger = PacrLedger::open(&path).unwrap();
        assert_eq!(ledger.len(), 1);
        assert!(ledger.contains(&CausalId(1)));
    }

    #[test]
    fn duplicate_id_rejected() {
        let path = tmp_path("dup");
        let mut ledger = PacrLedger::open(&path).unwrap();
        ledger.allow_physics_violations(true);
        let r = make_record(42, smallvec![CausalId::GENESIS]);
        ledger.append(r.clone()).unwrap();
        assert!(matches!(ledger.append(r), Err(LedgerError::DuplicateId(_))));
    }

    #[test]
    fn missing_predecessor_rejected() {
        let path = tmp_path("pred");
        let mut ledger = PacrLedger::open(&path).unwrap();
        ledger.allow_physics_violations(true);
        // Predecessor CausalId(99) does not exist in the ledger
        let r = make_record(1, smallvec![CausalId(99)]);
        assert!(matches!(
            ledger.append(r),
            Err(LedgerError::MissingPredecessor { .. })
        ));
    }

    #[test]
    fn causal_chain_appends_in_order() {
        let path = tmp_path("chain");
        let mut ledger = PacrLedger::open(&path).unwrap();
        ledger.allow_physics_violations(true);

        let r1 = make_record(1, smallvec![CausalId::GENESIS]);
        let r2 = make_record(2, smallvec![CausalId(1)]);
        let r3 = make_record(3, smallvec![CausalId(1), CausalId(2)]);

        ledger.append(r1).unwrap();
        ledger.append(r2).unwrap();
        ledger.append(r3).unwrap();

        assert_eq!(ledger.len(), 3);
    }

    #[test]
    fn get_returns_correct_record() {
        let path = tmp_path("get");
        let mut ledger = PacrLedger::open(&path).unwrap();
        ledger.allow_physics_violations(true);
        let r = make_record(7, smallvec![CausalId::GENESIS]);
        ledger.append(r).unwrap();

        let retrieved = ledger.get(&CausalId(7)).unwrap().unwrap();
        assert_eq!(retrieved.id, CausalId(7));
    }

    #[test]
    fn get_returns_none_for_missing_id() {
        let path = tmp_path("miss");
        let mut ledger = PacrLedger::open(&path).unwrap();
        let result = ledger.get(&CausalId(999)).unwrap();
        assert!(result.is_none());
    }

    #[test]
    fn iter_returns_records_in_insertion_order() {
        let path = tmp_path("iter");
        let mut ledger = PacrLedger::open(&path).unwrap();
        ledger.allow_physics_violations(true);

        ledger
            .append(make_record(10, smallvec![CausalId::GENESIS]))
            .unwrap();
        ledger
            .append(make_record(20, smallvec![CausalId(10)]))
            .unwrap();
        ledger
            .append(make_record(30, smallvec![CausalId(20)]))
            .unwrap();

        let ids: Vec<u128> = ledger.iter().unwrap().map(|r| r.unwrap().id.0).collect();

        assert_eq!(ids, vec![10, 20, 30]);
    }

    #[test]
    fn physics_violation_rejected_by_default() {
        use pacr_types::PacrBuilder;
        let path = tmp_path("phys");
        let mut ledger = PacrLedger::open(&path).unwrap();

        // Energy below Landauer floor — physics violation
        let bad = PacrBuilder::new()
            .id(CausalId(1))
            .predecessors(smallvec![CausalId::GENESIS])
            .landauer_cost(Estimate::exact(1e-10)) // Λ = 1e-10 J
            .resources(ResourceTriple {
                energy: Estimate::exact(1e-20), // E < Λ — violation!
                time: Estimate::exact(1e-9),
                space: Estimate::exact(64.0),
            })
            .cognitive_split(CognitiveSplit {
                statistical_complexity: Estimate::exact(1.0),
                entropy_rate: Estimate::exact(0.5),
            })
            .payload(Bytes::from_static(b"bad"))
            .build()
            .unwrap();

        assert!(matches!(
            ledger.append(bad),
            Err(LedgerError::PhysicsViolation(_))
        ));
    }
}
