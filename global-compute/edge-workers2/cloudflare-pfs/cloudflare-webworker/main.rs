use anyhow::{Context, Result};
use reqwest::{Client, StatusCode};
use scraper::{Html, Selector};
use serde::{Deserialize, Serialize};
use std::env;
use tokio::time::{sleep, Duration};

#[derive(Debug, Deserialize, Serialize)]
struct Lease {
    lease_id: String,
    items: Vec<String>,
    ttl_s: u64,
}

#[derive(Debug, Deserialize, Serialize)]
struct ResultItem {
    url: String,
    status: u16,
    bytes: Option<usize>,
    sha256: Option<String>,
    links: Option<Vec<String>>,
}

#[derive(Debug, Deserialize, Serialize)]
struct Submit {
    lease_id: String,
    worker_id: String,
    items: Vec<ResultItem>,
}

fn env_default(key: &str, default: &str) -> String {
    env::var(key).unwrap_or_else(|_| default.to_string())
}

async fn fetch_one(client: &Client, url: &str, ua: &str) -> Result<ResultItem> {
    let resp = client
        .get(url)
        .header("user-agent", ua)
        .send()
        .await
        .context("request failed")?;
    let status = resp.status();
    let bytes = resp.bytes().await.unwrap_or_default();
    let mut links: Vec<String> = Vec::new();
    let mut sha: Option<String> = None;
    if status == StatusCode::OK {
        use sha2::{Digest, Sha256};
        let mut hasher = Sha256::new();
        hasher.update(&bytes);
        sha = Some(format!("{:x}", hasher.finalize()));
        if let Some(ct) = resp.headers().get("content-type").and_then(|v| v.to_str().ok()) {
            if ct.to_ascii_lowercase().contains("text/html") {
                let body = String::from_utf8_lossy(&bytes);
                let doc = Html::parse_document(&body);
                let sel = Selector::parse("a").unwrap();
                for a in doc.select(&sel) {
                    if let Some(href) = a.value().attr("href") {
                        links.push(href.to_string());
                    }
                }
            }
        }
    }
    Ok(ResultItem {
        url: url.to_string(),
        status: status.as_u16(),
        bytes: Some(bytes.len()),
        sha256: sha,
        links: if links.is_empty() { None } else { Some(links) },
    })
}

#[tokio::main]
async fn main() -> Result<()> {
    let coord = env_default("COORD_URL", "http://127.0.0.1:8811");
    let worker_id = env_default("WORKER_ID", &format!("osv-{}", hostname::get().unwrap_or_default().to_string_lossy()));
    let lease_n: usize = env_default("SPIDER_LEASE_N", "25").parse().unwrap_or(25);
    let ua = env_default("SPIDER_UA", "pfs-spider-osv");

    let client = Client::builder()
        .use_rustls_tls()
        .http2_prior_knowledge()
        .build()?;

    loop {
        let lease_url = format!("{}/spider/lease?worker_id={}&n={}&ua={}", coord, urlencoding::encode(&worker_id), lease_n, urlencoding::encode(&ua));
        let lease = match client.get(&lease_url).send().await {
            Ok(r) if r.status().is_success() => r.json::<Lease>().await.unwrap_or(Lease { lease_id: String::new(), items: vec![], ttl_s: 0 }),
            _ => { sleep(Duration::from_millis(500)).await; continue; }
        };
        if lease.items.is_empty() || lease.lease_id.is_empty() {
            sleep(Duration::from_millis(200)).await;
            continue;
        }
        // Fetch concurrently
        let mut tasks = Vec::new();
        for u in lease.items.iter() {
            let c = client.clone();
            let ua_s = ua.clone();
            let u_s = u.clone();
            tasks.push(tokio::spawn(async move { fetch_one(&c, &u_s, &ua_s).await.unwrap_or(ResultItem { url: u_s, status: 0, bytes: Some(0), sha256: None, links: None }) }));
        }
        let mut results = Vec::new();
        for t in tasks {
            if let Ok(item) = t.await { results.push(item); }
        }
        let submit = Submit { lease_id: lease.lease_id, worker_id: worker_id.clone(), items: results };
        let _ = client.post(format!("{}/spider/result", coord)).json(&submit).send().await;
        sleep(Duration::from_millis(50)).await;
    }
}
