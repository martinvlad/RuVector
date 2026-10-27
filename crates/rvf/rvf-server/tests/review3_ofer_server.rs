//! Round 3: slot pinning after idle_timeout / total_deadline.
mod support;
use std::io::{Read, Write};
use std::net::TcpStream;
use std::time::{Duration, Instant};
use support::*;

fn open_stream(addr: std::net::SocketAddr) -> TcpStream {
    let mut s = TcpStream::connect(addr).unwrap();
    s.write_all(b"GET /v1/stream/body HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n").unwrap();
    s
}

/// Silent clients are now released after idle_timeout (expected to pass).
#[test]
fn f3_oracle_silent_clients_are_released() {
    let f = fixture(60000, 32, 16, 5);
    let r = start(&f, |c| {
        c.max_concurrent_streams = 2;
        c.idle_timeout = Duration::from_secs(2);
    });
    let _a = open_stream(r.http);
    let _b = open_stream(r.http);
    std::thread::sleep(Duration::from_secs(1));
    assert_eq!(raw_get(r.http, "/v1/stream/body", Some("bytes=0-9")).0, 429);
    std::thread::sleep(Duration::from_secs(5));
    assert_eq!(raw_get(r.http, "/v1/stream/body", Some("bytes=0-9")).0, 206, "slots freed");
}

/// F3-05: a client that reads just fast enough (about 64 KiB per idle_timeout)
/// keeps its slot until total_deadline (default 1 h). Two such readers deny
/// everyone. No minimum-rate rule.
#[test]
fn f3_05_slow_reader_keeps_slot_until_total_deadline() {
    let f = fixture(60000, 32, 16, 5);
    let r = start(&f, |c| {
        c.max_concurrent_streams = 2;
        c.idle_timeout = Duration::from_secs(2);
    });
    let mut readers = Vec::new();
    for _ in 0..2 {
        let mut s = open_stream(r.http);
        s.set_read_timeout(Some(Duration::from_millis(50))).unwrap();
        readers.push(s);
    }
    let t0 = Instant::now();
    let mut buf = [0u8; 4096];
    let mut got = 0usize;
    while t0.elapsed() < Duration::from_secs(12) {
        for s in &mut readers {
            if let Ok(n) = s.read(&mut buf) {
                got += n;
            }
        }
        std::thread::sleep(Duration::from_millis(std::env::var("SLEEP_MS").ok().and_then(|v| v.parse().ok()).unwrap_or(100))); // rate knob
    }
    let (st, _, _) = raw_get(r.http, "/v1/stream/body", Some("bytes=0-9"));
    eprintln!("read {got} bytes in 12 s from 2 slow readers; new request -> {st}");
    assert_eq!(st, 206, "slow readers still hold every slot after 6 idle timeouts");
}
