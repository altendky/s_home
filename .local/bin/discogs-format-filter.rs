#!/usr/bin/env -S cargo +nightly-2026-01-22 -Zscript
---
[dependencies]
ureq = { version = "2", features = ["json"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
serde_yml = "0.0"
clap = { version = "4", features = ["derive"] }
regex = "1"
---

use std::cell::RefCell;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet};
use std::io::{self, BufRead, Write};
use std::process;
use std::thread;
use std::time::{Duration, Instant};

use clap::Parser;
use serde::{Deserialize, Serialize};

const USER_AGENT: &str = "DiscogsFormatFilter/0.1";
const API_BASE: &str = "https://api.discogs.com";

/// Filter a Discogs artist's releases by media format presence/absence.
///
/// Common format names: Vinyl, CD, File, Cassette, DVD, Blu-ray, Box Set.
///
/// Examples:
///   # Find vinyl-only releases (no CD or digital)
///   discogs-format-filter.rs "Artist Name" --has vinyl --not cd --not file
///
///   # Shorthand: only these formats allowed (and at least one must exist)
///   discogs-format-filter.rs "Artist Name" --only vinyl
///
///   # Vinyl-only but don't care about cassette
///   discogs-format-filter.rs "Artist Name" --only vinyl --ignore cassette
///
///   # Only show releases available for under $50
///   discogs-format-filter.rs "Artist Name" --only vinyl --price-limit 50
///
///   # List all releases with their formats (no filter)
///   discogs-format-filter.rs "Artist Name"
///
///   # Skip search by passing a Discogs artist ID directly
///   discogs-format-filter.rs --id 12345 --has vinyl
#[derive(Parser)]
#[command(name = "discogs-format-filter")]
struct Cli {
    /// Artist name to search for
    artist: Option<String>,

    /// Discogs artist ID (bypasses name search)
    #[arg(long)]
    id: Option<u64>,

    /// Require this media format (repeatable, case-insensitive)
    #[arg(long = "has")]
    has: Vec<String>,

    /// Exclude this media format (repeatable, case-insensitive)
    #[arg(long = "not")]
    not: Vec<String>,

    /// Only these formats allowed (repeatable, case-insensitive).
    /// Release must have at least one, and no formats outside this set.
    #[arg(long = "only")]
    only: Vec<String>,

    /// Ignore these formats for filtering and display (repeatable, case-insensitive).
    /// Useful with --only: e.g. --only vinyl --ignore cassette
    #[arg(long = "ignore")]
    ignore: Vec<String>,

    /// Maximum lowest price (USD). Excludes releases above this price
    /// or with nothing for sale.
    #[arg(long = "price-limit")]
    price_limit: Option<f64>,

    /// Show detailed per-request API logging
    #[arg(short, long)]
    verbose: bool,

    /// Maximum number of releases to process (0 = unlimited)
    #[arg(long, default_value_t = 0)]
    limit: usize,

    /// Add matching releases to your Discogs wantlist with a tagged note
    #[arg(long)]
    add_to_wantlist: bool,
}

// ── API response types ─────────────────────────────────────────

#[derive(Deserialize)]
struct Pagination {
    #[allow(dead_code)]
    page: u32,
    pages: u32,
    #[allow(dead_code)]
    #[serde(default)]
    items: u32,
}

#[derive(Deserialize)]
struct SearchResponse {
    #[allow(dead_code)]
    pagination: Pagination,
    results: Vec<SearchHit>,
}

#[derive(Deserialize)]
struct SearchHit {
    id: u64,
    title: String,
    uri: Option<String>,
}

/// Paginated search response used for bulk format pre-filtering.
#[derive(Deserialize)]
struct FormatSearchPage {
    pagination: Pagination,
    results: Vec<FormatSearchResult>,
}

#[derive(Deserialize)]
struct FormatSearchResult {
    id: u64,
}

#[derive(Deserialize)]
struct ArtistDetail {
    id: u64,
    name: String,
    uri: Option<String>,
}

#[derive(Deserialize)]
struct ArtistReleasesPage {
    pagination: Pagination,
    releases: Vec<ArtistRelease>,
}

#[derive(Deserialize)]
struct ArtistRelease {
    id: u64,
    #[serde(rename = "type")]
    kind: String,
    title: String,
    year: Option<u32>,
    role: Option<String>,
    /// Inline format string from artist-releases endpoint (release-type only).
    /// e.g. "CD, Album" or "Vinyl, 12\", LP". Not present on master-type items.
    format: Option<String>,
}

#[derive(Deserialize)]
struct MasterVersionsPage {
    pagination: Pagination,
    versions: Vec<MasterVersion>,
}

#[derive(Deserialize)]
struct MasterVersion {
    major_formats: Option<Vec<String>>,
}

#[derive(Deserialize, Clone)]
struct ArtistCredit {
    name: String,
    #[serde(default)]
    join: String,
    #[serde(default)]
    anv: String,
}

#[derive(Deserialize)]
struct MasterDetail {
    lowest_price: Option<f64>,
    num_for_sale: Option<u32>,
    main_release: Option<u64>,
    #[serde(default)]
    artists: Vec<ArtistCredit>,
}

#[derive(Deserialize)]
struct ReleaseDetail {
    formats: Option<Vec<FormatEntry>>,
    lowest_price: Option<f64>,
    num_for_sale: Option<u32>,
    #[serde(default)]
    artists: Vec<ArtistCredit>,
}

#[derive(Deserialize)]
struct FormatEntry {
    name: String,
}

/// Response from /oauth/identity
#[derive(Deserialize)]
struct IdentityResponse {
    username: String,
}

/// Paginated wantlist response
#[derive(Deserialize)]
struct WantlistPage {
    pagination: Pagination,
    wants: Vec<WantlistItem>,
}

#[derive(Deserialize)]
struct WantlistItem {
    id: u64,
    #[serde(default)]
    notes: Option<String>,
}

/// YAML-serializable tag entry for wantlist notes
#[derive(Serialize, Deserialize, Clone, PartialEq)]
struct FilterTag {
    query: String,
    artist: String,
    date: String,
}

// ── API stats tracking ─────────────────────────────────────────

#[derive(Default)]
struct ApiStats {
    by_endpoint: BTreeMap<String, (u32, u128)>,
    total_requests: u32,
    total_time_ms: u128,
    rate_limit_pauses: u32,
    rate_limit_wait_ms: u128,
    retries_429: u32,
    cache_hits: u32,
    skipped_price: u32,
    skipped_early_exit: u32,
    skipped_prefilter: u32,
    skipped_search: u32,
    requeued: u32,
    requeue_ok: u32,
    requeue_fail: u32,
}

impl ApiStats {
    fn record(&mut self, label: &str, elapsed_ms: u128) {
        self.total_requests += 1;
        self.total_time_ms += elapsed_ms;
        let entry = self.by_endpoint.entry(label.to_string()).or_insert((0, 0));
        entry.0 += 1;
        entry.1 += elapsed_ms;
    }

    fn record_rate_pause(&mut self, wait_ms: u128) {
        self.rate_limit_pauses += 1;
        self.rate_limit_wait_ms += wait_ms;
    }

    fn record_429(&mut self) {
        self.retries_429 += 1;
    }

    fn print_summary(&self, dedup_saved: usize) {
        eprintln!();
        eprintln!("── API usage summary ──────────────────────────────");
        eprintln!(
            "  Total requests:  {}  ({:.1}s network time)",
            self.total_requests,
            self.total_time_ms as f64 / 1000.0
        );
        eprintln!("  By endpoint:");
        for (label, (count, ms)) in &self.by_endpoint {
            eprintln!(
                "    {:30} {:>4} reqs  {:>6.1}s",
                label,
                count,
                *ms as f64 / 1000.0
            );
        }
        if dedup_saved > 0 || self.cache_hits > 0 {
            eprintln!("  Optimizations:");
            if dedup_saved > 0 {
                eprintln!(
                    "    Dedup saved:         {} duplicate releases",
                    dedup_saved
                );
            }
            if self.cache_hits > 0 {
                eprintln!(
                    "    Cache hits:          {} (avoided re-fetch)",
                    self.cache_hits
                );
            }
            if self.skipped_price > 0 {
                eprintln!(
                    "    Price-skip:          {} (over limit, skipped format fetch)",
                    self.skipped_price
                );
            }
            if self.skipped_search > 0 {
                eprintln!(
                    "    Search pre-filter:   {} (masters excluded via bulk search)",
                    self.skipped_search
                );
            }
            if self.skipped_prefilter > 0 {
                eprintln!(
                    "    Inline pre-filter:   {} (rejected by format string, no API call)",
                    self.skipped_prefilter
                );
            }
            if self.skipped_early_exit > 0 {
                eprintln!(
                    "    Early-exit:          {} (excluded format found, stopped paging)",
                    self.skipped_early_exit
                );
            }
        }
        if self.requeued > 0 {
            eprintln!(
                "  Requeued:          {} ({} recovered, {} failed)",
                self.requeued, self.requeue_ok, self.requeue_fail
            );
        }
        if self.rate_limit_pauses > 0 || self.retries_429 > 0 {
            eprintln!(
                "  Rate-limit pauses: {} ({:.1}s waiting)",
                self.rate_limit_pauses,
                self.rate_limit_wait_ms as f64 / 1000.0
            );
            eprintln!("  429 retries:       {}", self.retries_429);
        }
        eprintln!("───────────────────────────────────────────────────");
    }
}

// ── HTTP client with rate-limit handling ────────────────────────

struct Discogs {
    token: String,
    agent: ureq::Agent,
    verbose: bool,
    stats: RefCell<ApiStats>,
}

impl Discogs {
    fn new(token: String, verbose: bool) -> Self {
        Self {
            token,
            agent: ureq::AgentBuilder::new()
                .timeout(Duration::from_secs(30))
                .build(),
            verbose,
            stats: RefCell::new(ApiStats::default()),
        }
    }

    /// GET with auth, rate-limit awareness, 429 retry, and logging.
    fn get<T: serde::de::DeserializeOwned>(
        &self,
        label: &str,
        path: &str,
        params: &[(&str, &str)],
    ) -> Result<T, String> {
        let url = if path.starts_with("http") {
            path.to_string()
        } else {
            format!("{API_BASE}{path}")
        };

        loop {
            let mut req = self
                .agent
                .get(&url)
                .set("User-Agent", USER_AGENT)
                .set("Authorization", &format!("Discogs token={}", self.token));

            for &(k, v) in params {
                req = req.query(k, v);
            }

            let start = Instant::now();

            match req.call() {
                Ok(resp) => {
                    let elapsed = start.elapsed();
                    let elapsed_ms = elapsed.as_millis();

                    let remaining: u32 = resp
                        .header("X-Discogs-Ratelimit-Remaining")
                        .and_then(|s| s.parse().ok())
                        .unwrap_or(60);
                    let limit: u32 = resp
                        .header("X-Discogs-Ratelimit")
                        .and_then(|s| s.parse().ok())
                        .unwrap_or(60);
                    let used: u32 = resp
                        .header("X-Discogs-Ratelimit-Used")
                        .and_then(|s| s.parse().ok())
                        .unwrap_or(0);

                    self.stats.borrow_mut().record(label, elapsed_ms);

                    if self.verbose {
                        eprintln!(
                            "\n    [API] {} {} => 200  {:.0}ms  rate:{}/{}",
                            label, path, elapsed_ms, used, limit
                        );
                    }

                    let body: T = resp.into_json().map_err(|e| format!("JSON parse: {e}"))?;

                    if remaining < 3 {
                        let wait = Duration::from_secs(10);
                        if self.verbose {
                            eprintln!(
                                "    [API] rate-limit remaining={}, pausing {:.0}s",
                                remaining,
                                wait.as_secs()
                            );
                        } else {
                            eprint!(" [rate-limit low, waiting 10s]");
                        }
                        let pause_start = Instant::now();
                        thread::sleep(wait);
                        self.stats
                            .borrow_mut()
                            .record_rate_pause(pause_start.elapsed().as_millis());
                    }

                    return Ok(body);
                }
                Err(ureq::Error::Status(429, _)) => {
                    let elapsed_ms = start.elapsed().as_millis();
                    self.stats.borrow_mut().record(label, elapsed_ms);
                    self.stats.borrow_mut().record_429();
                    let wait = Duration::from_secs(30);
                    if self.verbose {
                        eprintln!(
                            "\n    [API] {} {} => 429  waiting {:.0}s",
                            label,
                            path,
                            wait.as_secs()
                        );
                    } else {
                        eprintln!("\n  Rate-limited. Waiting 30s...");
                    }
                    let pause_start = Instant::now();
                    thread::sleep(wait);
                    self.stats
                        .borrow_mut()
                        .record_rate_pause(pause_start.elapsed().as_millis());
                }
                Err(ureq::Error::Status(401, _)) => {
                    return Err("401 Unauthorized. Check your DISCOGS_TOKEN.".into());
                }
                Err(ureq::Error::Status(404, _)) => {
                    return Err("404 Not Found".into());
                }
                Err(e) => return Err(format!("Request failed: {e}")),
            }
        }
    }

    /// Send a request with the given HTTP method, JSON body, auth, rate-limit,
    /// and 429 retry handling.
    fn request(
        &self,
        method: &str,
        label: &str,
        path: &str,
        body: &serde_json::Value,
    ) -> Result<(), String> {
        let url = if path.starts_with("http") {
            path.to_string()
        } else {
            format!("{API_BASE}{path}")
        };

        loop {
            let start = Instant::now();

            let req = match method {
                "PUT" => self.agent.put(&url),
                "POST" => self.agent.post(&url),
                _ => return Err(format!("unsupported method: {method}")),
            };

            let result = req
                .set("User-Agent", USER_AGENT)
                .set("Authorization", &format!("Discogs token={}", self.token))
                .set("Content-Type", "application/json")
                .send_string(&body.to_string());

            match result {
                Ok(resp) => {
                    let elapsed_ms = start.elapsed().as_millis();
                    let remaining: u32 = resp
                        .header("X-Discogs-Ratelimit-Remaining")
                        .and_then(|s| s.parse().ok())
                        .unwrap_or(60);

                    self.stats.borrow_mut().record(label, elapsed_ms);

                    if self.verbose {
                        let status = resp.status();
                        eprintln!(
                            "\n    [API] {label} {method} {path} => {status}  {elapsed_ms:.0}ms"
                        );
                    }

                    if remaining < 3 {
                        let wait = Duration::from_secs(10);
                        if self.verbose {
                            eprintln!("    [API] rate-limit remaining={remaining}, pausing 10s");
                        }
                        let pause_start = Instant::now();
                        thread::sleep(wait);
                        self.stats
                            .borrow_mut()
                            .record_rate_pause(pause_start.elapsed().as_millis());
                    }

                    return Ok(());
                }
                Err(ureq::Error::Status(429, _)) => {
                    let elapsed_ms = start.elapsed().as_millis();
                    self.stats.borrow_mut().record(label, elapsed_ms);
                    self.stats.borrow_mut().record_429();
                    let wait = Duration::from_secs(30);
                    if self.verbose {
                        eprintln!("\n    [API] {label} {method} {path} => 429  waiting 30s");
                    }
                    let pause_start = Instant::now();
                    thread::sleep(wait);
                    self.stats
                        .borrow_mut()
                        .record_rate_pause(pause_start.elapsed().as_millis());
                }
                Err(e) => return Err(format!("{method} failed: {e}")),
            }
        }
    }

    fn print_stats(&self, dedup_saved: usize) {
        self.stats.borrow().print_summary(dedup_saved);
    }
}

// ── Cached results for a master or release ─────────────────────

#[derive(Clone)]
struct FetchedInfo {
    formats: BTreeSet<String>,
    lowest_price: Option<f64>,
    num_for_sale: Option<u32>,
    artists: Vec<ArtistCredit>,
    /// For masters: main_release from master-detail; for releases: the release id itself
    release_id: Option<u64>,
}

// ── Collected info per logical release ─────────────────────────

struct Info {
    title: String,
    year: Option<u32>,
    role: String,
    formats: BTreeSet<String>,
    url: String,
    lowest_price: Option<f64>,
    num_for_sale: Option<u32>,
    artists: Vec<ArtistCredit>,
    /// Concrete release ID suitable for wantlist (main_release for masters)
    release_id: Option<u64>,
}

// ── Entry point ────────────────────────────────────────────────

fn main() {
    if let Err(e) = run() {
        eprintln!("error: {e}");
        process::exit(1);
    }
}

fn run() -> Result<(), String> {
    let cli = Cli::parse();

    let token = std::env::var("DISCOGS_TOKEN")
        .ok()
        .filter(|s| !s.is_empty())
        .ok_or(
            "DISCOGS_TOKEN not set.\n  \
             Get a personal access token at https://www.discogs.com/settings/developers",
        )?;

    let has: HashSet<String> = cli.has.iter().map(|s| s.to_lowercase()).collect();
    let not: HashSet<String> = cli.not.iter().map(|s| s.to_lowercase()).collect();
    let only: HashSet<String> = cli.only.iter().map(|s| s.to_lowercase()).collect();
    let ignore: HashSet<String> = cli.ignore.iter().map(|s| s.to_lowercase()).collect();
    let have_filters = !has.is_empty() || !not.is_empty() || !only.is_empty();
    let price_limit = cli.price_limit;

    if has.is_empty() && not.is_empty() && only.is_empty() {
        eprintln!("(no format filters; listing all releases with their formats)");
    }

    let api = Discogs::new(token, cli.verbose);
    let need_price = price_limit.is_some();
    // Always fetch master-detail for format-passing masters (for artists + main_release)
    let need_detail = true;

    // ── resolve artist ──────────────────────────────────────────
    let artist_id = match (cli.id, &cli.artist) {
        (Some(id), _) => id,
        (None, Some(name)) => pick_artist(&api, name)?,
        _ => return Err("provide an artist name or --id <ID>".into()),
    };

    // ── show artist info ────────────────────────────────────────
    let artist_path = format!("/artists/{artist_id}");
    let artist_detail: ArtistDetail = api.get("artist-detail", &artist_path, &[])?;
    let artist_uri = artist_detail.uri.as_deref().unwrap_or("(no URL)");
    eprintln!("Artist: {} (id {})", artist_detail.name, artist_detail.id);
    eprintln!("  {artist_uri}");

    // ── fetch artist's release list ─────────────────────────────
    eprintln!("Fetching release list...");
    let all = fetch_artist_releases(&api, artist_id)?;

    // ── OPTIMIZATION 1: dedup by (kind, id) ─────────────────────
    // The artist releases endpoint returns the same master/release
    // multiple times under different roles. Dedup, keeping the first
    // occurrence (preserving role info) and merging roles for display.
    let (deduped, dedup_saved) = dedup_releases(&all);

    let masters: Vec<_> = deduped.iter().filter(|r| r.kind == "master").collect();
    let singles: Vec<_> = deduped.iter().filter(|r| r.kind == "release").collect();
    let total = masters.len() + singles.len();

    eprintln!(
        "{} masters + {} standalone = {} unique releases ({} duplicates removed)",
        masters.len(),
        singles.len(),
        total,
        dedup_saved,
    );

    if total == 0 {
        println!("No releases found.");
        api.print_stats(dedup_saved);
        return Ok(());
    }

    // ── OPTIMIZATION 7: search-based bulk pre-filter for masters ──
    // Use the search endpoint to find which masters have disqualifying
    // formats, eliminating them without individual /versions calls.
    // Search can only EXCLUDE (we trust "format exists" results), never
    // include — masters not found in search still get individual checks.
    let mut search_excluded: HashSet<u64> = HashSet::new();
    if have_filters && !masters.is_empty() {
        let known_ids: HashSet<u64> = masters.iter().map(|m| m.id).collect();

        // Formats whose presence would disqualify a master
        let mut exclude_formats: Vec<String> = Vec::new();
        for f in &not {
            if !ignore.contains(f) {
                exclude_formats.push(title_case(f));
            }
        }
        if !only.is_empty() {
            // For --only, any common format NOT in the allowed set disqualifies
            for fmt in &["CD", "File", "DVD", "Blu-ray", "Box Set", "Shellac"] {
                let lc = fmt.to_lowercase();
                if !only.contains(&lc) && !ignore.contains(&lc) {
                    exclude_formats.push(fmt.to_string());
                }
            }
        }
        exclude_formats.sort();
        exclude_formats.dedup();

        if !exclude_formats.is_empty() {
            eprintln!("Bulk pre-filtering masters via search...");
            for fmt in &exclude_formats {
                eprint!("\r  Searching for masters with {fmt}...\x1b[K");
                match search_masters_with_format(&api, &artist_detail.name, fmt) {
                    Ok(ids) => {
                        let hits: HashSet<u64> = ids.intersection(&known_ids).cloned().collect();
                        if cli.verbose {
                            eprintln!(
                                "\r    search {fmt}: {} results, {} matched known masters\x1b[K",
                                ids.len(),
                                hits.len()
                            );
                        }
                        search_excluded.extend(hits);
                    }
                    Err(e) => {
                        eprintln!(
                            "\r  warning: search for {fmt} failed ({e}), will check individually\x1b[K"
                        );
                    }
                }
            }
            if !search_excluded.is_empty() {
                eprintln!(
                    "\r  Search pre-excluded {}/{} masters\x1b[K",
                    search_excluded.len(),
                    masters.len()
                );
            }
        }
    }

    // ── OPTIMIZATION 2: cache by ID to avoid re-fetching ────────
    let mut master_cache: HashMap<u64, FetchedInfo> = HashMap::new();
    let mut release_cache: HashMap<u64, FetchedInfo> = HashMap::new();

    let item_limit = if cli.limit > 0 { cli.limit } else { usize::MAX };
    let mut infos: Vec<Info> = Vec::with_capacity(total);
    let mut retry_queue: Vec<&DedupRelease> = Vec::new();
    let mut n = 0usize;

    for m in &masters {
        if n >= item_limit {
            break;
        }
        n += 1;
        eprint!("\r  [{n}/{total}] {}\x1b[K", trunc(&m.title, 50));

        // Search pre-filter: skip masters already identified as having
        // a disqualifying format (no individual API call needed)
        if search_excluded.contains(&m.id) {
            api.stats.borrow_mut().skipped_search += 1;
            continue;
        }

        let fetched = if let Some(cached) = master_cache.get(&m.id) {
            api.stats.borrow_mut().cache_hits += 1;
            cached.clone()
        } else {
            match fetch_master_info(
                &api,
                m.id,
                need_price,
                need_detail,
                price_limit,
                &has,
                &not,
                &only,
                &ignore,
            ) {
                Ok(f) => {
                    master_cache.insert(m.id, f.clone());
                    f
                }
                Err(e) if is_transient(&e) => {
                    if cli.verbose {
                        eprintln!(
                            "\n    [RETRY] queuing master {} ({}) for retry: {e}",
                            m.id, m.title
                        );
                    }
                    api.stats.borrow_mut().requeued += 1;
                    retry_queue.push(m);
                    continue;
                }
                Err(e) => {
                    eprintln!("\n  warning: skipping master {} ({}): {e}", m.id, m.title);
                    continue;
                }
            }
        };

        infos.push(Info {
            title: m.title.clone(),
            year: m.year.filter(|&y| y != 0),
            role: m.role.clone().unwrap_or_else(|| "Main".into()),
            formats: fetched.formats,
            url: format!("https://www.discogs.com/master/{}", m.id),
            lowest_price: if need_price {
                fetched.lowest_price
            } else {
                None
            },
            num_for_sale: if need_price {
                fetched.num_for_sale
            } else {
                None
            },
            artists: fetched.artists,
            release_id: fetched.release_id,
        });
    }

    for s in &singles {
        if n >= item_limit {
            break;
        }
        n += 1;
        eprint!("\r  [{n}/{total}] {}\x1b[K", trunc(&s.title, 50));

        // OPTIMIZATION 6: Pre-filter standalone releases using the inline
        // format string from the artist-releases endpoint (e.g. "CD, Album").
        // This avoids a full /releases/{id} fetch for the vast majority of
        // standalones that will fail the format filter.
        if have_filters {
            if let Some(ref fmt_str) = s.format {
                let inline_formats = parse_inline_formats(fmt_str);
                let lc: HashSet<String> = inline_formats
                    .iter()
                    .map(|f| f.to_lowercase())
                    .filter(|f| !ignore.contains(f))
                    .collect();

                // Check --not: if excluded format found, skip
                let not_fail = not.iter().any(|n| lc.contains(n));
                // Check --has: if required format missing, skip
                let has_fail = !has.is_empty() && !has.iter().all(|h| lc.contains(h));
                // Check --only: if non-only format present, skip
                let only_fail =
                    !only.is_empty() && !lc.is_empty() && !lc.iter().all(|f| only.contains(f));

                if not_fail || has_fail || only_fail {
                    api.stats.borrow_mut().skipped_prefilter += 1;
                    continue;
                }
            }
        }

        let fetched = if let Some(cached) = release_cache.get(&s.id) {
            api.stats.borrow_mut().cache_hits += 1;
            cached.clone()
        } else {
            match release_info(&api, s.id) {
                Ok((formats, lowest_price, num_for_sale, artists)) => {
                    let f = FetchedInfo {
                        formats,
                        lowest_price,
                        num_for_sale,
                        artists,
                        release_id: Some(s.id),
                    };
                    release_cache.insert(s.id, f.clone());
                    f
                }
                Err(e) if is_transient(&e) => {
                    if cli.verbose {
                        eprintln!(
                            "\n    [RETRY] queuing release {} ({}) for retry: {e}",
                            s.id, s.title
                        );
                    }
                    api.stats.borrow_mut().requeued += 1;
                    retry_queue.push(s);
                    continue;
                }
                Err(e) => {
                    eprintln!("\n  warning: skipping release {} ({}): {e}", s.id, s.title);
                    continue;
                }
            }
        };

        infos.push(Info {
            title: s.title.clone(),
            year: s.year.filter(|&y| y != 0),
            role: s.role.clone().unwrap_or_else(|| "Main".into()),
            formats: fetched.formats,
            url: format!("https://www.discogs.com/release/{}", s.id),
            lowest_price: if need_price {
                fetched.lowest_price
            } else {
                None
            },
            num_for_sale: if need_price {
                fetched.num_for_sale
            } else {
                None
            },
            artists: fetched.artists,
            release_id: Some(s.id),
        });
    }

    // ── retry queue: process items that failed with transient errors ──
    // Each item gets up to 5 total attempts (1 initial + 4 retries).
    const MAX_ATTEMPTS: u32 = 5;
    let mut pending = retry_queue;
    let mut attempt = 2u32; // first retry is attempt 2

    while !pending.is_empty() && attempt <= MAX_ATTEMPTS {
        eprintln!(
            "\r  Retrying {} item(s) (attempt {attempt}/{MAX_ATTEMPTS})...\x1b[K",
            pending.len()
        );
        let mut still_failing: Vec<&DedupRelease> = Vec::new();

        for item in &pending {
            eprint!(
                "\r  [retry {attempt}/{MAX_ATTEMPTS}] {}\x1b[K",
                trunc(&item.title, 50)
            );

            let result = if item.kind == "master" {
                fetch_master_info(
                    &api,
                    item.id,
                    need_price,
                    need_detail,
                    price_limit,
                    &has,
                    &not,
                    &only,
                    &ignore,
                )
            } else {
                release_info(&api, item.id).map(|(formats, lowest_price, num_for_sale, artists)| {
                    FetchedInfo {
                        formats,
                        lowest_price,
                        num_for_sale,
                        artists,
                        release_id: Some(item.id),
                    }
                })
            };

            match result {
                Ok(fetched) => {
                    api.stats.borrow_mut().requeue_ok += 1;
                    let url = if item.kind == "master" {
                        format!("https://www.discogs.com/master/{}", item.id)
                    } else {
                        format!("https://www.discogs.com/release/{}", item.id)
                    };
                    infos.push(Info {
                        title: item.title.clone(),
                        year: item.year.filter(|&y| y != 0),
                        role: item.role.clone().unwrap_or_else(|| "Main".into()),
                        formats: fetched.formats,
                        url,
                        lowest_price: if need_price {
                            fetched.lowest_price
                        } else {
                            None
                        },
                        num_for_sale: if need_price {
                            fetched.num_for_sale
                        } else {
                            None
                        },
                        artists: fetched.artists,
                        release_id: fetched.release_id,
                    });
                }
                Err(e) if is_transient(&e) && attempt < MAX_ATTEMPTS => {
                    // Still transient and we have more attempts — keep in queue
                    still_failing.push(item);
                }
                Err(e) => {
                    api.stats.borrow_mut().requeue_fail += 1;
                    eprintln!(
                        "\n  warning: giving up on {} {} ({}) after {attempt} attempts: {e}",
                        item.kind, item.id, item.title
                    );
                }
            }
        }

        pending = still_failing;
        attempt += 1;
    }

    eprintln!("\r  Done.\x1b[K");

    // ── apply filter ────────────────────────────────────────────
    let mut hits: Vec<&Info> = infos
        .iter()
        .filter(|r| {
            let lc: HashSet<String> = r
                .formats
                .iter()
                .map(|f| f.to_lowercase())
                .filter(|f| !ignore.contains(f))
                .collect();
            let has_ok = has.iter().all(|h| lc.contains(h));
            let not_ok = !not.iter().any(|n| lc.contains(n));
            let only_ok =
                only.is_empty() || (!lc.is_empty() && lc.iter().all(|f| only.contains(f)));

            let price_ok = match price_limit {
                None => true,
                Some(limit) => match (r.num_for_sale, r.lowest_price) {
                    (Some(n), Some(p)) if n > 0 => p <= limit,
                    _ => false,
                },
            };

            has_ok && not_ok && only_ok && price_ok
        })
        .collect();

    hits.sort_by_key(|r| r.year.unwrap_or(u32::MAX));

    // ── print results ───────────────────────────────────────────
    println!();

    if has.is_empty() && not.is_empty() && only.is_empty() && price_limit.is_none() {
        println!("=== All releases ===");
    } else {
        print!("=== Releases");
        if !only.is_empty() {
            let mut v: Vec<_> = only.iter().map(String::as_str).collect();
            v.sort();
            print!(" only [{}]", v.join(", "));
        }
        if !has.is_empty() {
            let mut v: Vec<_> = has.iter().map(String::as_str).collect();
            v.sort();
            print!(" with [{}]", v.join(", "));
        }
        if !not.is_empty() {
            let mut v: Vec<_> = not.iter().map(String::as_str).collect();
            v.sort();
            print!(" without [{}]", v.join(", "));
        }
        if !ignore.is_empty() {
            let mut v: Vec<_> = ignore.iter().map(String::as_str).collect();
            v.sort();
            print!(" ignoring [{}]", v.join(", "));
        }
        if let Some(limit) = price_limit {
            print!(" under ${:.2}", limit);
        }
        println!(" ===");
    }
    println!();

    if hits.is_empty() {
        println!("  (none)");
    } else {
        for r in &hits {
            let yr = r.year.map(|y| format!(" ({y})")).unwrap_or_default();
            let role = if r.role == "Main" {
                String::new()
            } else {
                format!(" [{}]", r.role)
            };
            let visible: Vec<_> = r
                .formats
                .iter()
                .filter(|f| !ignore.contains(&f.to_lowercase()))
                .cloned()
                .collect();
            let fmts = if visible.is_empty() {
                "(unknown)".to_string()
            } else {
                visible.join(", ")
            };

            println!("  {}{yr}{role}", r.title);
            let by = format_artists(&r.artists);
            if !by.is_empty() {
                println!("    by {by}");
            }
            print!("    Formats: {fmts}");
            if let (Some(nfs), Some(lp)) = (r.num_for_sale, r.lowest_price) {
                if nfs > 0 {
                    print!("  |  ${:.2} ({} for sale)", lp, nfs);
                } else {
                    print!("  |  none for sale");
                }
            }
            println!();
            println!("    {}", r.url);
            println!();
        }
    }

    println!("{} matching / {} total.", hits.len(), infos.len());

    // ── add to wantlist ─────────────────────────────────────────
    if cli.add_to_wantlist && !hits.is_empty() {
        eprintln!();
        eprintln!("Adding {} item(s) to wantlist...", hits.len());

        let username = fetch_identity(&api)?;
        if cli.verbose {
            eprintln!("  Authenticated as: {username}");
        }

        eprintln!("  Fetching existing wantlist...");
        let existing_notes = fetch_wantlist_notes(&api, &username)?;
        if cli.verbose {
            eprintln!("  Wantlist has {} items", existing_notes.len());
        }

        let query_summary = build_query_summary(&has, &not, &only, &ignore, price_limit);
        let date = today_str();
        let new_tag = FilterTag {
            query: query_summary,
            artist: artist_detail.name.clone(),
            date,
        };

        let mut added = 0u32;
        let mut skipped = 0u32;
        for r in &hits {
            let release_id = match r.release_id {
                Some(id) => id,
                None => {
                    eprintln!(
                        "  warning: no release ID for '{}', skipping wantlist add",
                        r.title
                    );
                    skipped += 1;
                    continue;
                }
            };

            let old_notes = existing_notes
                .get(&release_id)
                .map(|s| s.as_str())
                .unwrap_or("");
            let new_notes = update_notes(old_notes, &new_tag);

            let path = format!("/users/{username}/wants/{release_id}");

            eprint!(
                "\r  [{}/{}] {}\x1b[K",
                added + skipped + 1,
                hits.len(),
                trunc(&r.title, 50)
            );

            // PUT ensures the item exists (creates if new, no-op if exists).
            // POST then sets the notes (PUT ignores notes in the body).
            let empty = serde_json::json!({});
            let notes_body = serde_json::json!({ "notes": new_notes });
            match api
                .request("PUT", "wantlist-put", &path, &empty)
                .and_then(|_| api.request("POST", "wantlist-post", &path, &notes_body))
            {
                Ok(()) => added += 1,
                Err(e) => {
                    eprintln!("\n  warning: failed to add '{}' to wantlist: {e}", r.title);
                    skipped += 1;
                }
            }
        }

        eprintln!("\r  Wantlist: {added} added/updated, {skipped} skipped.\x1b[K");
    }

    api.print_stats(dedup_saved);

    Ok(())
}

// ── dedup releases by (kind, id), merge roles ──────────────────

struct DedupRelease {
    id: u64,
    kind: String,
    title: String,
    year: Option<u32>,
    role: Option<String>,
    format: Option<String>,
}

fn dedup_releases(all: &[ArtistRelease]) -> (Vec<DedupRelease>, usize) {
    let mut seen: HashMap<(String, u64), usize> = HashMap::new();
    let mut out: Vec<DedupRelease> = Vec::new();
    let mut dupes = 0usize;

    for r in all {
        let key = (r.kind.clone(), r.id);
        if let Some(&idx) = seen.get(&key) {
            // Merge role info
            let existing = &mut out[idx];
            if let Some(new_role) = &r.role {
                if let Some(ref mut old_role) = existing.role {
                    if !old_role.contains(new_role.as_str()) {
                        old_role.push_str(", ");
                        old_role.push_str(new_role);
                    }
                }
            }
            dupes += 1;
        } else {
            seen.insert(key, out.len());
            out.push(DedupRelease {
                id: r.id,
                kind: r.kind.clone(),
                title: r.title.clone(),
                year: r.year,
                role: r.role.clone(),
                format: r.format.clone(),
            });
        }
    }

    (out, dupes)
}

// ── interactive artist picker ──────────────────────────────────

fn pick_artist(api: &Discogs, name: &str) -> Result<u64, String> {
    eprintln!("Searching for \"{name}\"...");

    let resp: SearchResponse = api.get(
        "search",
        "/database/search",
        &[("q", name), ("type", "artist"), ("per_page", "10")],
    )?;

    match resp.results.len() {
        0 => Err(format!("No artists found for \"{name}\"")),
        1 => {
            let a = &resp.results[0];
            eprintln!("Found: {} (id {})", a.title, a.id);
            Ok(a.id)
        }
        _ => {
            eprintln!("\nMultiple matches:\n");
            for (i, a) in resp.results.iter().enumerate() {
                let uri = a.uri.as_deref().unwrap_or("");
                eprintln!("  {}: {} (id {})  {}", i + 1, a.title, a.id, uri);
            }
            eprintln!();
            eprint!("Pick [1-{}]: ", resp.results.len());
            io::stderr().flush().unwrap();

            let mut buf = String::new();
            io::stdin()
                .lock()
                .read_line(&mut buf)
                .map_err(|e| e.to_string())?;

            let idx: usize = buf
                .trim()
                .parse()
                .map_err(|_| "invalid number".to_string())?;

            if idx < 1 || idx > resp.results.len() {
                return Err("selection out of range".into());
            }

            let a = &resp.results[idx - 1];
            eprintln!("Selected: {} (id {})", a.title, a.id);
            Ok(a.id)
        }
    }
}

// ── paginated fetchers ─────────────────────────────────────────

fn fetch_artist_releases(api: &Discogs, artist_id: u64) -> Result<Vec<ArtistRelease>, String> {
    let mut out = Vec::new();
    let mut page = 1u32;

    loop {
        let p = page.to_string();
        let path = format!("/artists/{artist_id}/releases");
        let resp: ArtistReleasesPage = api.get(
            "artist-releases",
            &path,
            &[
                ("page", &p),
                ("per_page", "100"),
                ("sort", "year"),
                ("sort_order", "asc"),
            ],
        )?;
        let pages = resp.pagination.pages;
        eprint!("\r  page {page}/{pages}\x1b[K");
        out.extend(resp.releases);
        if page >= pages {
            break;
        }
        page += 1;
    }

    eprintln!();
    Ok(out)
}

/// Fetch formats (and optionally price) for a master release.
///
/// OPTIMIZATION 3 (formats-first): Check formats BEFORE price.
/// Since ~91% of masters fail the format filter, this avoids an
/// expensive master-detail call for the vast majority of releases.
/// Previously, price was checked first (costing 1 master-detail per
/// release even when the format filter would reject it).
///
/// OPTIMIZATION 4: Early termination — when paginating versions,
/// if we find an excluded format, stop immediately.
///
/// OPTIMIZATION 5: Use server-side format filter on the versions
/// endpoint to probe for specific format existence with per_page=1.
/// This replaces fetching a full page of 100 versions — particularly
/// helpful when masters have many pages of versions.
fn fetch_master_info(
    api: &Discogs,
    master_id: u64,
    need_price: bool,
    need_detail: bool,
    price_limit: Option<f64>,
    has: &HashSet<String>,
    not: &HashSet<String>,
    only: &HashSet<String>,
    ignore: &HashSet<String>,
) -> Result<FetchedInfo, String> {
    let have_filters = !has.is_empty() || !not.is_empty() || !only.is_empty();

    // ── Step 1: Check formats FIRST (cheap — avoids master-detail for failures) ──
    let formats = if !not.is_empty() || !only.is_empty() {
        master_formats_full_early_exit(api, master_id, not, only, ignore)?
    } else {
        master_formats_full(api, master_id)?
    };

    // Quick check: will this release pass the format filter?
    if have_filters {
        let dominated = {
            let lc: HashSet<String> = formats
                .iter()
                .map(|f| f.to_lowercase())
                .filter(|f| !ignore.contains(f))
                .collect();
            let has_ok = has.iter().all(|h| lc.contains(h));
            let not_ok = !not.iter().any(|n| lc.contains(n));
            let only_ok =
                only.is_empty() || (!lc.is_empty() && lc.iter().all(|f| only.contains(f)));
            !(has_ok && not_ok && only_ok)
        };
        if dominated {
            return Ok(FetchedInfo {
                formats,
                lowest_price: None,
                num_for_sale: None,
                artists: Vec::new(),
                release_id: None,
            });
        }
    }

    // ── Step 2: Format filter passed — fetch master-detail for price/artists/main_release ──
    let (lowest_price, num_for_sale, artists, main_release) = if need_price || need_detail {
        let detail = fetch_master_detail(api, master_id)?;
        if let Some(limit) = price_limit {
            let too_expensive = match (detail.num_for_sale, detail.lowest_price) {
                (Some(n), Some(p)) if n > 0 => p > limit,
                _ => true,
            };
            if too_expensive {
                api.stats.borrow_mut().skipped_price += 1;
                return Ok(FetchedInfo {
                    formats,
                    lowest_price: detail.lowest_price,
                    num_for_sale: detail.num_for_sale,
                    artists: detail.artists,
                    release_id: detail.main_release,
                });
            }
        }
        (
            detail.lowest_price,
            detail.num_for_sale,
            detail.artists,
            detail.main_release,
        )
    } else {
        (None, None, Vec::new(), None)
    };

    Ok(FetchedInfo {
        formats,
        lowest_price,
        num_for_sale,
        artists,
        release_id: main_release,
    })
}

/// Fetch all major_formats across all versions of a master (no server-side filter).
/// Used when no format filters are specified.
fn master_formats_full(api: &Discogs, master_id: u64) -> Result<BTreeSet<String>, String> {
    let mut fmts = BTreeSet::new();
    let mut page = 1u32;

    loop {
        let p = page.to_string();
        let path = format!("/masters/{master_id}/versions");
        let resp: MasterVersionsPage = api.get(
            "master-versions",
            &path,
            &[("page", &p), ("per_page", "100")],
        )?;

        for v in &resp.versions {
            if let Some(mf) = &v.major_formats {
                fmts.extend(mf.iter().cloned());
            }
        }

        if page >= resp.pagination.pages {
            break;
        }
        page += 1;
    }

    Ok(fmts)
}

/// Fetch formats with early termination on excluded format (for --only mode).
/// Fetch formats with early termination.
/// Stops as soon as a disqualifying format is found:
///   - for --not: any format in `excludes`
///   - for --only: any format NOT in `only ∪ ignore`
fn master_formats_full_early_exit(
    api: &Discogs,
    master_id: u64,
    excludes: &HashSet<String>,
    only: &HashSet<String>,
    ignore: &HashSet<String>,
) -> Result<BTreeSet<String>, String> {
    let mut fmts = BTreeSet::new();
    let mut page = 1u32;

    loop {
        let p = page.to_string();
        let path = format!("/masters/{master_id}/versions");
        let resp: MasterVersionsPage = api.get(
            "master-versions",
            &path,
            &[("page", &p), ("per_page", "100")],
        )?;

        for v in &resp.versions {
            if let Some(mf) = &v.major_formats {
                fmts.extend(mf.iter().cloned());
            }
        }

        // Check --not: any explicitly excluded format found?
        let not_fail = !excludes.is_empty()
            && fmts.iter().any(|f| {
                let lc = f.to_lowercase();
                !ignore.contains(&lc) && excludes.contains(&lc)
            });

        // Check --only: any format outside the allowed set?
        let only_fail = !only.is_empty()
            && fmts.iter().any(|f| {
                let lc = f.to_lowercase();
                !ignore.contains(&lc) && !only.contains(&lc)
            });

        if not_fail || only_fail {
            api.stats.borrow_mut().skipped_early_exit += 1;
            break;
        }

        if page >= resp.pagination.pages {
            break;
        }
        page += 1;
    }

    Ok(fmts)
}

/// Bulk-search for master releases by an artist that have a given format.
/// Returns the set of master IDs found. Uses the /database/search endpoint
/// with type=master and format filtering.
fn search_masters_with_format(
    api: &Discogs,
    artist_name: &str,
    format: &str,
) -> Result<HashSet<u64>, String> {
    let mut ids = HashSet::new();
    let mut page = 1u32;

    loop {
        let p = page.to_string();
        let resp: FormatSearchPage = api.get(
            "search-format",
            "/database/search",
            &[
                ("type", "master"),
                ("artist", artist_name),
                ("format", format),
                ("per_page", "100"),
                ("page", &p),
            ],
        )?;

        for r in &resp.results {
            ids.insert(r.id);
        }

        if resp.pagination.pages == 0 || page >= resp.pagination.pages {
            break;
        }
        page += 1;
    }

    Ok(ids)
}

/// Capitalize first letter of a format name for the API.
fn title_case(s: &str) -> String {
    let mut c = s.chars();
    match c.next() {
        None => String::new(),
        Some(first) => {
            let mut out = first.to_uppercase().to_string();
            out.extend(c);
            out
        }
    }
}

fn fetch_master_detail(api: &Discogs, master_id: u64) -> Result<MasterDetail, String> {
    let path = format!("/masters/{master_id}");
    api.get("master-detail", &path, &[])
}

/// Returns (formats, lowest_price, num_for_sale, artists)
fn release_info(
    api: &Discogs,
    release_id: u64,
) -> Result<
    (
        BTreeSet<String>,
        Option<f64>,
        Option<u32>,
        Vec<ArtistCredit>,
    ),
    String,
> {
    let path = format!("/releases/{release_id}");
    let resp: ReleaseDetail = api.get("release-detail", &path, &[])?;

    let mut fmts = BTreeSet::new();
    if let Some(entries) = resp.formats {
        for e in entries {
            fmts.insert(e.name);
        }
    }

    Ok((fmts, resp.lowest_price, resp.num_for_sale, resp.artists))
}

/// Check if an error message indicates a transient/retryable error.
fn is_transient(err: &str) -> bool {
    // 5xx status codes are transient server errors
    for code in &["500", "502", "503", "504"] {
        if err.contains(&format!("status code {code}")) {
            return true;
        }
    }
    // 404 can be transient on Discogs (consistency lag — the artist-releases
    // endpoint just told us this ID exists, so retry before giving up)
    if err.contains("404") {
        return true;
    }
    err.contains("timed out")
        || err.contains("connection reset")
        || err.contains("Connection reset")
}

/// Parse the inline format string from the artist-releases endpoint.
///
/// The format string looks like "CD, Album" or "Vinyl, 12\", 45 RPM" or
/// "2×File, FLAC, Album". We extract known major format names (Vinyl, CD,
/// File, Cassette, DVD, Blu-ray, Box Set) from the comma-separated segments.
fn parse_inline_formats(fmt_str: &str) -> BTreeSet<String> {
    // Known major format names that Discogs uses
    const KNOWN_FORMATS: &[&str] = &[
        "vinyl",
        "cd",
        "file",
        "cassette",
        "dvd",
        "blu-ray",
        "box set",
        "shellac",
        "flexi-disc",
        "lathe cut",
    ];

    let mut found = BTreeSet::new();
    for segment in fmt_str.split(',') {
        let seg = segment.trim();
        // Handle quantity prefixes like "2×CD" or "2xFile"
        let cleaned = seg
            .trim_start_matches(|c: char| c.is_ascii_digit() || c == '×' || c == 'x' || c == 'X')
            .trim();
        let lower = cleaned.to_lowercase();
        for &known in KNOWN_FORMATS {
            if lower == known {
                // Capitalize the first letter for canonical display
                let mut c = known.chars();
                let canonical: String = match c.next() {
                    None => continue,
                    Some(first) => {
                        let mut s = first.to_uppercase().to_string();
                        s.extend(c);
                        s
                    }
                };
                found.insert(canonical);
                break;
            }
        }
    }
    found
}

// ── wantlist support ───────────────────────────────────────────

fn fetch_identity(api: &Discogs) -> Result<String, String> {
    let resp: IdentityResponse = api.get("identity", "/oauth/identity", &[])?;
    Ok(resp.username)
}

/// Fetch all wantlist items, returning a map of release_id → existing notes.
fn fetch_wantlist_notes(api: &Discogs, username: &str) -> Result<HashMap<u64, String>, String> {
    let mut map = HashMap::new();
    let mut page = 1u32;

    loop {
        let p = page.to_string();
        let path = format!("/users/{username}/wants");
        let resp: WantlistPage =
            api.get("wantlist", &path, &[("page", &p), ("per_page", "100")])?;

        for item in &resp.wants {
            let notes = item.notes.clone().unwrap_or_default();
            map.insert(item.id, notes);
        }

        if resp.pagination.pages == 0 || page >= resp.pagination.pages {
            break;
        }
        page += 1;
    }

    Ok(map)
}

/// Build the query summary string from filter args.
/// e.g. "has:vinyl not:cd,file <$50"
fn build_query_summary(
    has: &HashSet<String>,
    not: &HashSet<String>,
    only: &HashSet<String>,
    ignore: &HashSet<String>,
    price_limit: Option<f64>,
) -> String {
    let mut parts = Vec::new();
    if !only.is_empty() {
        let mut v: Vec<_> = only.iter().map(String::as_str).collect();
        v.sort();
        parts.push(format!("only:{}", v.join(",")));
    }
    if !has.is_empty() {
        let mut v: Vec<_> = has.iter().map(String::as_str).collect();
        v.sort();
        parts.push(format!("has:{}", v.join(",")));
    }
    if !not.is_empty() {
        let mut v: Vec<_> = not.iter().map(String::as_str).collect();
        v.sort();
        parts.push(format!("not:{}", v.join(",")));
    }
    if !ignore.is_empty() {
        let mut v: Vec<_> = ignore.iter().map(String::as_str).collect();
        v.sort();
        parts.push(format!("ignore:{}", v.join(",")));
    }
    if let Some(limit) = price_limit {
        parts.push(format!("<${:.0}", limit));
    }
    parts.join(" ")
}

/// Today's date as YYYY-MM-DD using system time.
fn today_str() -> String {
    use std::time::SystemTime;
    let dur = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap();
    let secs = dur.as_secs();
    // Simple date calculation (good enough — no timezone crate needed)
    let days = secs / 86400;
    let (y, m, d) = days_to_ymd(days);
    format!("{y:04}-{m:02}-{d:02}")
}

fn days_to_ymd(days_since_epoch: u64) -> (u64, u64, u64) {
    // Algorithm from http://howardhinnant.github.io/date_algorithms.html
    let z = days_since_epoch + 719468;
    let era = z / 146097;
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    (y, m, d)
}

const TAG_OPEN: &str = "[format-filter]";
const TAG_CLOSE: &str = "[/format-filter]";

/// Update wantlist notes: extract all [format-filter] blocks, coalesce,
/// add/update the current tag, reassemble with one block at the end.
fn update_notes(existing_notes: &str, new_tag: &FilterTag) -> String {
    let re =
        regex::Regex::new(r"(?s)\[format-filter\]\s*\n?(.*?)\n?\s*\[/format-filter\]").unwrap();

    // Extract all tag lines from all blocks
    let mut tags: Vec<FilterTag> = Vec::new();
    for cap in re.captures_iter(existing_notes) {
        if let Some(yaml_str) = cap.get(1) {
            if let Ok(parsed) = serde_yml::from_str::<Vec<FilterTag>>(yaml_str.as_str()) {
                tags.extend(parsed);
            }
        }
    }

    // Strip all blocks from user text
    let user_text = re.replace_all(existing_notes, "").to_string();
    let user_text = user_text.trim().to_string();

    // Remove any existing entry that matches on query+artist (ignoring date)
    tags.retain(|t| !(t.query == new_tag.query && t.artist == new_tag.artist));

    // Append new tag at end
    tags.push(new_tag.clone());

    // Serialize tags back to YAML
    let yaml = serde_yml::to_string(&tags).unwrap_or_default();
    let yaml = yaml.trim().to_string();

    // Reassemble
    if user_text.is_empty() {
        format!("{TAG_OPEN}\n{yaml}\n{TAG_CLOSE}")
    } else {
        format!("{user_text}\n{TAG_OPEN}\n{yaml}\n{TAG_CLOSE}")
    }
}

// ── utilities ──────────────────────────────────────────────────

/// Format artist credits into a display string.
/// Uses `anv` (artist name variation) when present, otherwise `name`.
/// Joins with the `join` field from the API (e.g. "&", ",").
fn format_artists(artists: &[ArtistCredit]) -> String {
    if artists.is_empty() {
        return String::new();
    }
    let mut parts = Vec::new();
    for (i, a) in artists.iter().enumerate() {
        let display_name = if a.anv.is_empty() { &a.name } else { &a.anv };
        parts.push(display_name.clone());
        if i < artists.len() - 1 {
            let joiner = if a.join.is_empty() { " & " } else { &a.join };
            // Discogs join strings don't always include surrounding spaces
            let joiner = if joiner.starts_with(' ') || joiner == "," {
                joiner.to_string()
            } else {
                format!(" {joiner} ")
            };
            parts.push(joiner);
        }
    }
    parts.join("")
}

fn trunc(s: &str, max: usize) -> String {
    if s.chars().count() <= max {
        s.to_string()
    } else {
        let t: String = s.chars().take(max - 1).collect();
        format!("{t}...")
    }
}
