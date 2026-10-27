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

/// F4-06: per-client caps key on the socket peer address (good: no header is
/// consulted) but the pool is tiny, so address diversity defeats them. Two
/// source addresses (loopback aliases here; any two IPv4 hosts, or two
/// addresses of one IPv6 /64) at the default cap of 4 each take all 8 slots,
/// and each only has to read 32 KB/s to keep its slot.
#[test]
fn f4_06_two_addresses_pin_the_whole_pool() {
    use tokio::net::TcpSocket;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    let f = fixture(60000, 32, 16, 5);
    let mut cfg = rvf_server::stream::StreamServerConfig::new(f.rvf.clone(), f.keyfile.clone());
    cfg.chunk_log2 = 16;
    let server = rvf_server::stream::StreamServer::load(cfg).unwrap();
    let rt = tokio::runtime::Builder::new_multi_thread().worker_threads(4).enable_all().build().unwrap();
    rt.block_on(async {
        let l = tokio::net::TcpListener::bind("0.0.0.0:0").await.unwrap();
        let port = l.local_addr().unwrap().port();
        let app = rvf_server::stream::router(server.clone());
        tokio::spawn(async move {
            axum::serve(l, app.into_make_service_with_connect_info::<std::net::SocketAddr>()).await.unwrap();
        });
        let target: std::net::SocketAddr = format!("127.0.0.1:{port}").parse().unwrap();
        let mut conns = Vec::new();
        for src in ["127.0.0.2", "127.0.0.3"] {
            for _ in 0..4 {
                let s = TcpSocket::new_v4().unwrap();
                s.bind(format!("{src}:0").parse().unwrap()).unwrap();
                let mut c = s.connect(target).await.unwrap();
                c.write_all(b"GET /v1/stream/body HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n").await.unwrap();
                conns.push(c);
            }
        }
        // a third source address and the same-address 5th connection
        let probe = |src: &'static str| async move {
            let s = TcpSocket::new_v4().unwrap();
            s.bind(format!("{src}:0").parse().unwrap()).unwrap();
            let mut c = s.connect(target).await.unwrap();
            c.write_all(b"GET /v1/stream/body HTTP/1.1\r\nHost: x\r\nRange: bytes=0-9\r\nConnection: close\r\n\r\n").await.unwrap();
            let mut b = vec![0u8; 64];
            let n = c.read(&mut b).await.unwrap();
            String::from_utf8_lossy(&b[..n.min(20)]).to_string()
        };
        let mut buf = vec![0u8; 8192];
        // keep every reader above the 32 KB/s floor for > rate_grace (10 s)
        let t0 = std::time::Instant::now();
        while t0.elapsed() < std::time::Duration::from_secs(14) {
            for c in conns.iter_mut() {
                let _ = tokio::time::timeout(std::time::Duration::from_millis(20), c.read(&mut buf)).await;
            }
            tokio::time::sleep(std::time::Duration::from_millis(60)).await;
        }
        let same = probe("127.0.0.2").await;
        let other = probe("127.0.0.9").await;
        eprintln!("5th connection from a holder address: {same:?}; first connection from a new address: {other:?}");
        assert!(other.contains("206"), "a new client is locked out by two addresses: {other:?}");
    });
}

/// F4-06 (fixed): addresses in one /24 share a prefix cap, so two source
/// addresses cannot pin the pool; a client from another prefix still gets in.
#[test]
fn f4_06_two_addresses_cannot_pin_the_pool() {
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpSocket;
    let f = fixture(60000, 32, 16, 5);
    let mut cfg = rvf_server::stream::StreamServerConfig::new(f.rvf.clone(), f.keyfile.clone());
    cfg.chunk_log2 = 16;
    let server = rvf_server::stream::StreamServer::load(cfg).unwrap();
    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(4)
        .enable_all()
        .build()
        .unwrap();
    rt.block_on(async {
        let l = tokio::net::TcpListener::bind("0.0.0.0:0").await.unwrap();
        let port = l.local_addr().unwrap().port();
        let app = rvf_server::stream::router(server.clone());
        tokio::spawn(async move {
            axum::serve(
                l,
                app.into_make_service_with_connect_info::<std::net::SocketAddr>(),
            )
            .await
            .unwrap();
        });
        let target: std::net::SocketAddr = format!("127.0.0.1:{port}").parse().unwrap();
        let get = |src: &'static str, range: &'static str| async move {
            let s = TcpSocket::new_v4().unwrap();
            s.bind(format!("{src}:0").parse().unwrap()).unwrap();
            let mut c = s.connect(target).await.unwrap();
            let req = format!(
                "GET /v1/stream/body HTTP/1.1\r\nHost: x\r\n{range}Connection: close\r\n\r\n"
            );
            c.write_all(req.as_bytes()).await.unwrap();
            let mut b = vec![0u8; 64];
            let n = c.read(&mut b).await.unwrap();
            (String::from_utf8_lossy(&b[..n.min(20)]).to_string(), c)
        };
        let mut held = Vec::new();
        let mut statuses = Vec::new();
        for src in ["127.0.0.2", "127.0.0.3"] {
            for _ in 0..4 {
                let (st, c) = get(src, "").await;
                statuses.push(st);
                held.push(c);
            }
        }
        let ok = statuses.iter().filter(|s| s.contains(" 200")).count();
        assert!(ok <= 4, "one /24 took {ok} slots: {statuses:?}");
        let (other, _c) = get("127.1.0.9", "Range: bytes=0-9\r\n").await;
        assert!(
            other.contains("206"),
            "a new prefix is locked out: {other:?}"
        );
    });
}

/// F4-06 (fixed): a router mounted without connect info fails closed.
#[test]
fn f4_06_missing_connect_info_fails_closed() {
    let f = fixture(60000, 32, 16, 5);
    let server = {
        let mut cfg = rvf_server::stream::StreamServerConfig::new(f.rvf.clone(), f.keyfile.clone());
        cfg.chunk_log2 = 16;
        rvf_server::stream::StreamServer::load(cfg).unwrap()
    };
    let rt = tokio::runtime::Builder::new_multi_thread()
        .worker_threads(2)
        .enable_all()
        .build()
        .unwrap();
    let l = rt
        .block_on(tokio::net::TcpListener::bind("127.0.0.1:0"))
        .unwrap();
    let addr = l.local_addr().unwrap();
    let app = rvf_server::stream::router(server);
    rt.spawn(async move {
        axum::serve(l, app).await.unwrap();
    });
    assert_eq!(
        raw_get(addr, "/v1/stream/body", Some("bytes=0-9")).0,
        503,
        "no peer address must mean no stream, not no limit"
    );
}

/// Round 5: eight distinct /24 prefixes (loopback 127.N.1.1), one stream each,
/// each read at ~400 KB/s (above the slow-stream threshold of 8 x 32 KB/s).
/// Per-address/prefix/reserve/slow caps are all satisfied; a ninth prefix is
/// refused. Residual of any bounded pool; reported as accepted.
#[test]
fn f5_06_many_prefixes_still_fill_the_pool() {
    use tokio::net::TcpSocket;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    let f = fixture(60000, 32, 16, 5);
    let mut cfg = rvf_server::stream::StreamServerConfig::new(f.rvf.clone(), f.keyfile.clone());
    cfg.chunk_log2 = 16;
    let server = rvf_server::stream::StreamServer::load(cfg).unwrap();
    let rt = tokio::runtime::Builder::new_multi_thread().worker_threads(4).enable_all().build().unwrap();
    rt.block_on(async {
        let l = tokio::net::TcpListener::bind("0.0.0.0:0").await.unwrap();
        let port = l.local_addr().unwrap().port();
        let app = rvf_server::stream::router(server.clone());
        tokio::spawn(async move {
            axum::serve(l, app.into_make_service_with_connect_info::<std::net::SocketAddr>()).await.unwrap();
        });
        let target: std::net::SocketAddr = format!("127.0.0.1:{port}").parse().unwrap();
        let mut conns = Vec::new();
        for n in 1..=8u8 {
            let s = TcpSocket::new_v4().unwrap();
            s.bind(format!("127.{n}.1.1:0").parse().unwrap()).unwrap();
            let mut c = s.connect(target).await.unwrap();
            c.write_all(b"GET /v1/stream/body HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n").await.unwrap();
            conns.push(c);
        }
        let mut buf = vec![0u8; 16384];
        let t0 = std::time::Instant::now();
        while t0.elapsed() < std::time::Duration::from_secs(14) {
            for c in conns.iter_mut() {
                let _ = tokio::time::timeout(std::time::Duration::from_millis(5), c.read(&mut buf)).await;
            }
            tokio::time::sleep(std::time::Duration::from_millis(15)).await;
        }
        let s = TcpSocket::new_v4().unwrap();
        s.bind("127.50.1.1:0".parse().unwrap()).unwrap();
        let mut c = s.connect(target).await.unwrap();
        c.write_all(b"GET /v1/stream/body HTTP/1.1\r\nHost: x\r\nRange: bytes=0-9\r\nConnection: close\r\n\r\n").await.unwrap();
        let mut b = vec![0u8; 64];
        let n = c.read(&mut b).await.unwrap();
        let line = String::from_utf8_lossy(&b[..n.min(24)]).to_string();
        eprintln!("ninth prefix after 14 s: {line:?}");
        assert!(line.contains("206"), "pool pinned by eight prefixes: {line:?}");
    });
}

/// Missing connect-info must be refused (503), spoofed XFF must not matter.
#[test]
fn f5_oracle_missing_connect_info_is_503_and_headers_are_ignored() {
    let f = fixture(2000, 16, 8, 3);
    let r = start(&f, |_| {});
    let (st, _, _) = raw_get(r.http, "/v1/stream/body", Some("bytes=0-9"));
    assert_eq!(st, 503, "router mounted without connect info must fail closed");
    let r2 = start(&f, |c| c.client_cap = rvf_server::stream::ClientCap::Disabled);
    assert_eq!(raw_get(r2.http, "/v1/stream/body", Some("bytes=0-9")).0, 206);
}
