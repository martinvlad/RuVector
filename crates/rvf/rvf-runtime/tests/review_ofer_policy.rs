#![cfg(feature = "ed25519")]
//! Adversarial review repros for the Strict policy and tail scan (F-12, F-13).

use rvf_runtime::{RvfOptions, RvfStore};
use rvf_types::security::{SecurityError, SecurityPolicy};
use rvf_types::{RvfError, SegmentFlags, SegmentType};
use rvf_wire::writer::write_segment;

#[path = "support/signed.rs"]
mod signed;
use signed::*;

/// F-12: a plain `RvfStore::open` (the historical, un-policied entry point) of
/// a signed store followed by any write destroys the signature irreversibly;
/// Strict readers then refuse the file as `UnsignedManifest`.
#[test]
fn f12_plain_open_append_silently_unsigns_a_signed_store() {
    let d = tempfile::tempdir().unwrap();
    let p = signed_store(d.path());
    assert!(RvfStore::open_with_policy(&p, opts(&[public(&SECRET)]), SecurityPolicy::Strict).is_ok());
    let mut s = RvfStore::open(&p).unwrap();
    let v = rows(1, 500.0);
    let refs: Vec<&[f32]> = v.iter().map(Vec::as_slice).collect();
    s.ingest_batch(&refs, &[900], None).unwrap();
    s.close().unwrap();
    match RvfStore::open_with_policy(&p, opts(&[public(&SECRET)]), SecurityPolicy::Strict) {
        Err(RvfError::Security(SecurityError::UnsignedManifest { .. })) => {}
        other => panic!("expected UnsignedManifest, got {:?}", other.map(|_| ())),
    }
}

/// F-13: under Permissive (and WarnOnly) a fake MANIFEST header planted at a
/// 64-byte aligned position *inside the payload of a later VEC segment*
/// (attacker-chosen vector floats, e.g. the leftover of a crashed append)
/// beats the real manifest. The store opens with the attacker's directory.
#[test]
fn f13_fake_manifest_inside_trailing_vec_payload_wins_under_permissive() {
    let d = tempfile::tempdir().unwrap();
    let p = d.path().join("plain.rvf");
    {
        let mut s = RvfStore::create(
            &p,
            RvfOptions {
                dimension: 4,
                ..Default::default()
            },
        )
        .unwrap();
        for b in 0..2u64 {
            let v = rows(6, b as f32 * 100.0);
            let refs: Vec<&[f32]> = v.iter().map(Vec::as_slice).collect();
            let ids: Vec<u64> = (0..6).map(|i| b * 10 + i).collect();
            s.ingest_batch(&refs, &ids, None).unwrap();
        }
        s.close().unwrap();
    }
    let real = RvfStore::open_readonly(&p).unwrap().status().total_vectors;
    assert_eq!(real, 12);

    // Fake manifest: epoch 99, dim 4, 0 vectors, empty directory.
    let mut fm = Vec::new();
    fm.extend_from_slice(&99u32.to_le_bytes());
    fm.extend_from_slice(&4u16.to_le_bytes());
    fm.extend_from_slice(&0u64.to_le_bytes());
    fm.extend_from_slice(&0u32.to_le_bytes());
    fm.extend_from_slice(&[0u8; 4]); // profile + metric + reserved
    fm.extend_from_slice(&0u32.to_le_bytes()); // deleted count
    let fake = write_segment(SegmentType::Manifest as u8, &fm, SegmentFlags::empty(), 777);
    // Carrier: an ordinary VEC segment whose payload begins with the fake.
    let carrier = write_segment(SegmentType::Vec as u8, &fake, SegmentFlags::empty(), 778);
    let mut bytes = std::fs::read(&p).unwrap();
    assert_eq!(bytes.len() % 64, 0);
    bytes.extend_from_slice(&carrier);
    std::fs::write(&p, &bytes).unwrap();

    let got = RvfStore::open_readonly(&p).unwrap().status().total_vectors;
    assert_eq!(got, 0, "attacker manifest hidden inside a payload won the tail scan");
}

fn fake_manifest_segment() -> Vec<u8> {
    let mut fm = Vec::new();
    fm.extend_from_slice(&99u32.to_le_bytes());
    fm.extend_from_slice(&4u16.to_le_bytes());
    fm.extend_from_slice(&0u64.to_le_bytes());
    fm.extend_from_slice(&0u32.to_le_bytes());
    fm.extend_from_slice(&[0u8; 4]);
    fm.extend_from_slice(&0u32.to_le_bytes());
    write_segment(SegmentType::Manifest as u8, &fm, SegmentFlags::empty(), 777)
}

/// F-14: legacy (byte-granular) scanning is selected by ONE attacker-writable
/// byte, the first segment header's `checksum_algo`, which no hash covers. On a
/// wire-dialect file this makes the runtime (Permissive/WarnOnly) pick an
/// UNALIGNED fake manifest hidden in a payload, while the rvf-wire aligned
/// scanner (what rvm-rvf and other consumers use) still sees the real one: a
/// parser differential on identical bytes, the class ADR-354 item 4 targets.
#[test]
fn f14_first_header_algo_byte_selects_byte_granular_scan_and_splits_parsers() {
    let d = tempfile::tempdir().unwrap();
    let p = d.path().join("plain.rvf");
    {
        let mut s = RvfStore::create(
            &p,
            RvfOptions {
                dimension: 4,
                ..Default::default()
            },
        )
        .unwrap();
        let v = rows(6, 0.0);
        let refs: Vec<&[f32]> = v.iter().map(Vec::as_slice).collect();
        let ids: Vec<u64> = (0..6).collect();
        s.ingest_batch(&refs, &ids, None).unwrap();
        s.close().unwrap();
    }
    let mut bytes = std::fs::read(&p).unwrap();
    let (real_off, _) = rvf_wire::tail_scan::find_latest_manifest(&bytes).unwrap();
    // carrier: VEC segment, fake manifest at payload offset 8 (not 64-aligned)
    let mut payload = vec![0u8; 8];
    payload.extend_from_slice(&fake_manifest_segment());
    let carrier = write_segment(SegmentType::Vec as u8, &payload, SegmentFlags::empty(), 778);
    bytes.extend_from_slice(&carrier);
    std::fs::write(&p, &bytes).unwrap();

    // Untouched: both agree on the real manifest.
    let (a, _) = rvf_wire::tail_scan::find_latest_manifest(&bytes).unwrap();
    assert_eq!(a, real_off);
    assert_eq!(RvfStore::open_readonly(&p).unwrap().status().total_vectors, 6);

    // Flip the (unhashed) first-segment algo byte to the legacy marker.
    bytes[0x20] = 0;
    std::fs::write(&p, &bytes).unwrap();
    let (b, _) = rvf_wire::tail_scan::find_latest_manifest(&bytes).unwrap();
    assert_eq!(b, real_off, "aligned scanner unaffected");
    let runtime_view = RvfStore::open_readonly(&p).unwrap().status().total_vectors;
    assert_eq!(runtime_view, 0, "runtime followed the unaligned fake manifest");
}

/// Checked and sound: an empty trusted set never means accept-all.
#[test]
fn strict_with_empty_trusted_set_refuses_a_validly_signed_file() {
    let d = tempfile::tempdir().unwrap();
    let p = signed_store(d.path());
    for pol in [SecurityPolicy::Strict, SecurityPolicy::Paranoid] {
        match RvfStore::open_with_policy(&p, opts(&[]), pol) {
            Err(RvfError::Security(SecurityError::UnknownSigner { .. })) => {}
            other => panic!("{pol:?}: {:?}", other.map(|_| ())),
        }
    }
}

/// F-16: under Strict the committed hash covers only the payload. Header
/// fields `seg_type`, `flags`, `segment_id`, `compression`, `timestamp_ns` of
/// a committed segment can be rewritten without detection.
#[test]
fn f16_strict_does_not_authenticate_segment_header_fields() {
    let d = tempfile::tempdir().unwrap();
    let p = signed_store(d.path());
    let mut bytes = std::fs::read(&p).unwrap();
    let segs = segments(&bytes);
    let (off, _, _) = *segs.iter().find(|s| s.1 == SegmentType::Vec as u8).unwrap();
    bytes[off + 5] = SegmentType::Wasm as u8; // type confusion
    bytes[off + 6] ^= 0xFF; // flags
    bytes[off + 0x21] = 3; // compression
    bytes[off + 0x08] ^= 0x55; // segment_id
    bytes[off + 0x18] ^= 0x55; // timestamp
    std::fs::write(&p, &bytes).unwrap();
    let s = RvfStore::open_with_policy(&p, opts(&[public(&SECRET)]), SecurityPolicy::Paranoid)
        .expect("Paranoid still accepts the rewritten header");
    assert_eq!(s.status().total_vectors, 12);
}
