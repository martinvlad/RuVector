//! Round 3 review.
use ed25519_dalek::SigningKey;
use rvf_index::{LayerA, PartitionEntry};
use rvf_runtime::progressive_stream::layers::encode_a;
use rvf_runtime::progressive_stream::StreamIngest;
use rvf_types::SegmentFlags;
use rvf_wire::stream::{StreamDescriptorBuilder, StreamPolicy};
use rvf_wire::writer::write_segment_with_algo;
use std::time::Instant;
#[path = "support/signed.rs"]
#[allow(dead_code)]
mod signed;

fn stream_with(parts: Vec<PartitionEntry>, nvec: usize) -> (Vec<Vec<u8>>, [u8; 32]) {
    let a = LayerA {
        entry_points: vec![],
        top_layers: vec![],
        top_layer_start: 0,
        centroids: vec![vec![0.0; 4]],
        partition_map: parts,
    };
    let idx = encode_a(&a, 4, &[]);
    let mut vp = Vec::new();
    vp.extend_from_slice(&4u16.to_le_bytes());
    vp.extend_from_slice(&(nvec as u32).to_le_bytes());
    for i in 0..nvec as u64 {
        vp.extend_from_slice(&i.to_le_bytes());
        for x in [i as f32, 1.0, 2.0, 3.0] {
            vp.extend_from_slice(&x.to_le_bytes());
        }
    }
    let mut body = write_segment_with_algo(0x02, &idx, SegmentFlags::empty(), 1, 2);
    body.extend(write_segment_with_algo(0x01, &vp, SegmentFlags::empty(), 2, 2));
    let key = SigningKey::from_bytes(&[0xA7; 32]);
    let pk = key.verifying_key().to_bytes();
    let b = StreamDescriptorBuilder::new([3; 16], key)
        .chunk_log2(16)
        .stages(&[1, 2])
        .requires_lower_stages(true)
        .build(&body)
        .unwrap();
    (b.frames_stage_order(&body).collect(), pk)
}

fn part(c: u32, s: u64, e: u64) -> PartitionEntry {
    PartitionEntry { centroid_id: c, vector_id_start: s, vector_id_end: e, segment_ref: 0, block_ref: 0 }
}

/// F3-01: query cost is (#matching partitions) x (visible vectors) because every
/// overlapping partition re-visits and re-pushes the same vectors.
#[test]
fn f3_01_overlapping_partitions_multiply_query_cost() {
    let nvec = 20_000;
    let mut times = Vec::new();
    for p in [250usize, 500, 1000] {
        let parts = (0..p).map(|_| part(0, 0, u64::MAX)).collect();
        let (frames, pk) = stream_with(parts, nvec);
        let keys = [pk];
        let mut ing = StreamIngest::new(StreamPolicy::new(&keys));
        for f in &frames {
            assert!(ing.feed(f).refused.is_none());
        }
        let t = Instant::now();
        let r = ing.query(&[1.0, 1.0, 2.0, 3.0], 5, 16);
        let dt = t.elapsed();
        eprintln!("{p} identical wide partitions x {nvec} vectors: {dt:?}, {} hits", r.envelope.results.len());
        times.push(dt.as_secs_f64());
    }
    // payload for 1000 partitions is only ~20 KB; a 20 MB Layer A carries 1M of them
    assert!(times[2] < 0.5, "query cost grows with partitions x vectors: {times:?}");
}

mod rollback {
    #![cfg(feature = "ed25519")]
    use rvf_runtime::RvfStore;
    use rvf_types::security::SecurityPolicy;
    use super::signed::*;

    /// F3-02: under a signed page the scan no longer looks at newer manifests,
    /// so replacing only the 4 KiB trailing page with an OLDER valid page rolls
    /// a Strict reader back to the old state while the newer segments and
    /// manifest remain in the file. (Rollback by truncation was always possible;
    /// this needs no truncation and leaves the newer data physically present.)
    #[test]
    fn f3_02_page_swap_rolls_back_without_truncation() {
        let d = tempfile::tempdir().unwrap();
        let p = signed_store(d.path()); // 12 vectors, page P1
        let old = std::fs::read(&p).unwrap();
        let old_page = page_of(&old);
        {
            let mut s = RvfStore::open_signed(&p, opts(&[public(&SECRET)]), SecurityPolicy::Strict, &SECRET).unwrap();
            let v = rows(6, 900.0);
            let refs: Vec<&[f32]> = v.iter().map(Vec::as_slice).collect();
            s.ingest_batch(&refs, &(100..106).collect::<Vec<u64>>(), None).unwrap();
            s.close().unwrap();
        }
        let mut now = std::fs::read(&p).unwrap();
        let fresh = RvfStore::open_with_policy(&p, opts(&[public(&SECRET)]), SecurityPolicy::Strict).unwrap();
        assert_eq!(fresh.status().total_vectors, 18);
        drop(fresh);
        set_page(&mut now, &old_page);
        std::fs::write(&p, &now).unwrap();
        let r = RvfStore::open_with_policy(&p, opts(&[public(&SECRET)]), SecurityPolicy::Strict);
        let n = r.map(|s| s.status().total_vectors);
        eprintln!("after swapping in the old page: {n:?} (file still holds the newer manifest)");
        assert!(n.is_err(), "Strict served the rolled-back state");
    }
}

/// F3-03: two sessions that download the SAME descriptor concurrently: the
/// second `commit_pin` fails with a conflict although the pin is identical
/// (the CAS compares against the pin seen at admission, not the identical
/// stored value that documentation says is a no-op).
#[test]
fn f3_03_identical_concurrent_session_gets_spurious_conflict() {
    use rvf_wire::stream::{MemoryPinStore, StreamVerifier};
    let pins = MemoryPinStore::new();
    let key = SigningKey::from_bytes(&[0xA7; 32]);
    let pk = key.verifying_key().to_bytes();
    let body = write_segment_with_algo(0x01, &[1u8; 200], SegmentFlags::empty(), 1, 2);
    let b = StreamDescriptorBuilder::new([4; 16], key).chunk_log2(12).build(&body).unwrap();
    let keys = [pk];
    let mut mk = || {
        let mut p = StreamPolicy::new(&keys);
        p.pins = Some(&pins);
        StreamVerifier::new(p)
    };
    let (mut s1, mut s2) = (mk(), mk());
    let frames: Vec<Vec<u8>> = b.frames_file_order(&body).collect();
    for f in &frames {
        s1.push(f).unwrap();
        s2.push(f).unwrap();
    }
    s1.commit_pin(&pins).expect("first commit");
    let r = s2.commit_pin(&pins);
    assert!(r.is_ok(), "identical pin re-recorded must be a no-op success, got {r:?}");
}

/// F3-04: the `deleted` tombstone set is not charged to any budget; journal
/// segments are small on the wire (12 B per entry) and each is released after
/// parsing, so the set grows with every journal segment in the stream.
#[test]
fn f3_04_tombstone_set_growth_is_unbudgeted() {
    let mut body = Vec::new();
    let nseg = 40u64;
    let per = 100_000u64;
    let mut stages = Vec::new();
    for s in 0..nseg {
        let mut p = Vec::new();
        p.extend_from_slice(&(per as u32).to_le_bytes());
        p.extend_from_slice(&[0u8; 12]);
        for i in 0..per {
            p.push(0x01);
            p.extend_from_slice(&[0u8; 3]);
            p.extend_from_slice(&(s * per + i).to_le_bytes());
        }
        body.extend(write_segment_with_algo(0x04, &p, SegmentFlags::empty(), s + 1, 2));
        stages.push(0u8);
    }
    let key = SigningKey::from_bytes(&[0xA7; 32]);
    let pk = key.verifying_key().to_bytes();
    let b = StreamDescriptorBuilder::new([5; 16], key).chunk_log2(16).stages(&stages).build(&body).unwrap();
    let keys = [pk];
    let rss = || std::fs::read_to_string("/proc/self/statm").unwrap().split_whitespace().nth(1).unwrap().parse::<u64>().unwrap() * 4;
    let before = rss();
    let mut ing = StreamIngest::new(StreamPolicy::new(&keys));
    let mut wire = 0u64;
    for f in b.frames_file_order(&body) {
        wire += f.len() as u64;
        assert!(ing.feed(&f).refused.is_none());
    }
    let grown = (rss() - before) * 1024;
    eprintln!("journal wire {} KB -> resident +{} KB ({:.1}x)", wire / 1024, grown / 1024, grown as f64 / wire as f64);
    assert!(grown < 2 * wire, "tombstone set retains {:.1}x the wire bytes with no budget", grown as f64 / wire as f64);
}
