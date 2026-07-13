"""
LinkedIn Post Scraper → Airtable Pipeline  [MULTI-KEY EDITION]
==============================================================
NAYA KYA HAI (vs pichhli version)
---------------------------------
  1. QUERIES prefixes × locations grid se AUTO-GENERATE hoti hain.
       query format = "#<prefix> <location>"   e.g. "#offsite Dubai"

  2. MULTIPLE APIFY KEYS + AUTO-ROTATION.
       Ek key ka credit khatam hote hi script khud-ba-khud agle key
       par switch kar jaati hai. Saare keys khatam ho jaayein to gracefully
       ruk jaati hai (jo scrape ho chuka hai wo pehle hi push ho chuka hoga).

  3. INCREMENTAL PUSH.
       Har query ke baad turant CSV + Airtable mein push hota hai. Matlab jaise hi
       koi credit exhaust ho, uss tak ka data already saved hai — kuch loss nahi.

  4. RESUMABLE.
       Har successfully-scraped query ek progress file (PROGRESS_FILE) mein
       likhi jaati hai. Agli baar naye keys daal ke rerun karoge to already-done
       queries khud skip ho jaayengi — dobara paisa nahi lagega.

  5. UPFRONT CREDIT-SUFFICIENCY CHECK.
       Run shuru hone se pehle script batati hai ki tumhare paas jitna credit hai
       usme poori grid complete hogi ya nahi, aur kitni queries actually poori
       hongi is run mein — taaki "aadhi grid hi chali" wala surprise na ho.

SECRETS — IMPORTANT
--------------------
Is repo (Ayush9205NITRR/Game_Changer) PUBLIC hai. CONFIG block mein neeche
sirf PLACEHOLDER tokens hain — apne real Apify/Airtable tokens yahan
locally fill karo lekin us fill-in ko kabhi commit mat karo (`git diff`
check kar lena commit se pehle). Agar koi real token kabhi bhi is file
mein commit ho jaaye, turant Apify/Airtable dashboard se usko revoke +
naya generate karo — public repo mein commit hote hi leaked maana jaata hai.

HOW TO USE
----------
1. CONFIG block mein apne saare Apify keys (list) + Airtable token daalo
   (sirf apni local copy mein — commit mat karna).
2. prefixes / locations / MAX_POSTS adjust karo.
3. pip install requests
4. python linkedin_to_airtable.py
"""

import os
import re
import csv
import sys
import time
import logging
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse, quote


# ══════════════════════════════════════════════════════════════════════
# ① CONFIG  ← SIRF YEH BLOCK EDIT KARO
# ══════════════════════════════════════════════════════════════════════

CONFIG = {

    # ── APIFY KEYS (LIST) ─────────────────────────────────────────────
    # Jitne free keys hain sab yahan daalo. Order mein use honge:
    # pehla khatam → doosra → teesra ... Ek key ka credit khatam hote hi
    # script apne aap next par chali jaati hai.
    "APIFY_TOKENS": [
        "apify_api_KEY_1_YAHAN_PASTE_KARO",
        # "apify_api_KEY_2_YAHAN_PASTE_KARO",
        # "apify_api_KEY_3_YAHAN_PASTE_KARO",
        # ... jitne chaaho add karo
    ],

    # ── AIRTABLE ──────────────────────────────────────────────────────
    "AIRTABLE_TOKEN"   : "pat_YAHAN_PASTE_KARO",

    # ── AIRTABLE TARGET ───────────────────────────────────────────────
    "AIRTABLE_BASE_ID" : "appNjXRYNAQ2Nuiah",
    "AIRTABLE_TABLE"   : "Scraped LinkedIn Posts",

    # ── ACTOR ─────────────────────────────────────────────────────────
    # "curious_coder" → FREE  |  "harvestapi" → paid (~$2/1k, zyada reliable)
    "ACTOR" : "harvestapi",

    # ── QUERY GRID ────────────────────────────────────────────────────
    # Final queries = har prefix × har location  →  "#<prefix> <location>"
    "PREFIXES": [
        "offsite", "corporateoffsite", "salesoffsite", "salesmeet",
        "salesretreat", "leadershipoffsite", "leadershipmeet",
        "leadershipretreat", "teamoffsite", "annualoffsite",
        "saleskickoff", "SKO", "workation",
    ],
    "LOCATIONS": [
        "Goa", "Bali", "Phuket", "Manesar", "Neemrana", "Jim Corbett",
        "Agra", "Surajkund", "Morni Hills", "Kasauli",
    ],

    # ── EXHAUST MODE ──────────────────────────────────────────────────
    # QUERY_OVERRIDE agar non-empty ho to GRID ignore hokar SIRF yeh
    # queries chalti hain.
    "QUERY_OVERRIDE": [],

    # Grid mode mein bare prefix (bina location) bhi add karna ho to True.
    "INCLUDE_BARE_PREFIX": False,

    # ── SCALE ─────────────────────────────────────────────────────────
    # DHYAAN: grid = len(PREFIXES) × len(LOCATIONS) queries banti hain.
    # Cost per query ≈ (MAX_POSTS/1000) * $2 (harvestapi). Poori grid ka
    # cost estimate + tumhare keys ka available credit — dono run start
    # hone se pehle print hote hain (COST ESTIMATION section dekho).
    "MAX_POSTS"        : 400,
    "PAGES_TO_FETCH"   : 50,     # sirf tab use hota hai jab MAX_POSTS = None

    # ── CREDIT CHECK ──────────────────────────────────────────────────
    "PROACTIVE_CREDIT_CHECK" : True,
    # Buffer floor — actual buffer = max(iska value, ek query ka estimated
    # cost). Isse ek key ko aisi query start karne se roka jaata hai jise
    # wo poora finish hi nahi kar sakta (jo pehle reactive-fail + wasted
    # partial-run karta tha).
    "MIN_CREDIT_BUFFER_USD"  : 0.25,

    # ── RESUME ────────────────────────────────────────────────────────
    # Progress file jisme successfully-scraped queries record hoti hain.
    # Agli run isi file ko padh ke already-done queries skip karti hai.
    "PROGRESS_FILE"    : os.path.join(os.path.dirname(os.path.abspath(__file__)), "scrape_progress.txt"),
    "RESCRAPE_DONE"    : False,   # True karo agar progress ignore karke sab dobara chalana ho

    # ── SAFETY ────────────────────────────────────────────────────────
    "DRY_RUN"          : False,   # True = sirf estimate, na scrape na push
    "SKIP_DUPLICATES"  : True,
    # True karke dekho ki "duplicate" mark hui posts ki actual Post URLs kya
    # hain — Airtable mein wo URL search karke verify karo ki wo pehle se
    # kisi aur query se already push ho chuki thi (real dup) ya nahi (bug).
    "LOG_DUPLICATE_URLS": True,
}

# ══════════════════════════════════════════════════════════════════════
# DO NOT EDIT BELOW THIS LINE
# ══════════════════════════════════════════════════════════════════════

# ── Build query list ──────────────────────────────────────────────────
if CONFIG["QUERY_OVERRIDE"]:
    SEARCH_QUERY = list(CONFIG["QUERY_OVERRIDE"])
else:
    SEARCH_QUERY = []
    if CONFIG["INCLUDE_BARE_PREFIX"]:
        SEARCH_QUERY += [f"#{p}" for p in CONFIG["PREFIXES"]]
    SEARCH_QUERY += [
        f"#{prefix} {location}"
        for prefix in CONFIG["PREFIXES"]
        for location in CONFIG["LOCATIONS"]
    ]

# ── Credentials / settings from CONFIG ────────────────────────────────
APIFY_TOKENS = [t.strip() for t in CONFIG["APIFY_TOKENS"] if t and t.strip()]
AIRTABLE_TOKEN = CONFIG["AIRTABLE_TOKEN"].strip()

AIRTABLE_BASE_ID    = CONFIG["AIRTABLE_BASE_ID"]
AIRTABLE_TABLE      = CONFIG["AIRTABLE_TABLE"]
ACTOR_CHOICE        = CONFIG["ACTOR"]
PAGES_TO_FETCH      = CONFIG["PAGES_TO_FETCH"]
MAX_POSTS           = CONFIG["MAX_POSTS"]
DRY_RUN             = CONFIG["DRY_RUN"]
SKIP_DUPLICATES     = CONFIG["SKIP_DUPLICATES"]
LOG_DUPLICATE_URLS  = CONFIG["LOG_DUPLICATE_URLS"]
PROACTIVE_CREDIT_CHECK = CONFIG["PROACTIVE_CREDIT_CHECK"]
PROGRESS_FILE        = CONFIG["PROGRESS_FILE"]
RESCRAPE_DONE         = CONFIG["RESCRAPE_DONE"]
AIRTABLE_BATCH_SIZE = 10

# Runtime-adjustable buffer (synced with real cost/query in estimate_cost()).
MIN_CREDIT_BUFFER_USD  = CONFIG["MIN_CREDIT_BUFFER_USD"]

APIFY_COST_PER_1K = 2.00 if ACTOR_CHOICE == "harvestapi" else 0.0

ACTORS = {
    "curious_coder" : "curious_coder~linkedin-post-search-scraper",
    "harvestapi"    : "harvestapi~linkedin-post-search",
}
ACTOR_ID = ACTORS.get(ACTOR_CHOICE, ACTORS["curious_coder"])

TIMESTAMP        = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_BACKUP_FILE  = f"linkedin_posts_{TIMESTAMP}.csv"
FAILED_ROWS_FILE = f"failed_rows_{TIMESTAMP}.csv"
LOG_FILE         = f"run_log_{TIMESTAMP}.log"


# ─────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────

def setup_logging():
    fmt = "%(asctime)s  [%(levelname)-8s]  %(message)s"
    logging.basicConfig(
        level=logging.INFO, format=fmt, datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout),
                  logging.FileHandler(LOG_FILE, encoding="utf-8")]
    )

setup_logging()
log = logging.getLogger(__name__)

stats = {
    "run_start"           : datetime.now(timezone.utc).isoformat(),
    "actor"               : ACTOR_CHOICE,
    "estimated_cost_usd"  : None,
    "available_credit_usd": None,
    "raw_fetched"         : 0,
    "parsed_ok"           : 0,
    "parse_skipped"       : 0,
    "csv_saved"           : False,
    "airtable_success"    : 0,
    "airtable_failed"     : 0,
    "airtable_skipped_dup": 0,
    "retry_success"       : 0,
    "queries_done"        : 0,
    "queries_skipped_done": 0,
    "queries_total"       : len(SEARCH_QUERY),
    "errors"              : [],
    "query_results"       : {},
    "keys_status"         : {},   # key label -> reason it died (agar mara)
}


# ─────────────────────────────────────────────────────────────────────
# CUSTOM EXCEPTIONS  (key rotation ke liye)
# ─────────────────────────────────────────────────────────────────────

class ApifyCreditExhausted(Exception):
    """Is key ka credit khatam — agle key par jao."""

class ApifyTokenInvalid(Exception):
    """Ye key auth hi fail kar raha — skip karo."""


# ─────────────────────────────────────────────────────────────────────
# TOKEN MANAGER
# ─────────────────────────────────────────────────────────────────────

class TokenManager:
    """Apify keys ko sequence mein rotate karta hai."""
    def __init__(self, tokens):
        self.tokens = list(tokens)
        self.idx    = 0
        self.dead   = set()   # exhausted / invalid indices

    def current_token(self):
        while self.idx < len(self.tokens) and self.idx in self.dead:
            self.idx += 1
        return self.tokens[self.idx] if self.idx < len(self.tokens) else None

    def current_label(self):
        return f"key #{self.idx + 1}/{len(self.tokens)}"

    def kill_current(self, reason):
        if self.idx < len(self.tokens):
            self.dead.add(self.idx)
            stats["keys_status"][f"key #{self.idx + 1}"] = reason
        self.idx += 1

    def alive_count(self):
        return sum(1 for i in range(len(self.tokens)) if i not in self.dead)

    def alive_tokens(self):
        return [t for i, t in enumerate(self.tokens) if i not in self.dead]


# ─────────────────────────────────────────────────────────────────────
# PROGRESS / RESUME
# ─────────────────────────────────────────────────────────────────────

def load_completed_queries() -> set:
    if RESCRAPE_DONE or not os.path.exists(PROGRESS_FILE):
        return set()
    with open(PROGRESS_FILE, encoding="utf-8") as f:
        return {line.rstrip("\n") for line in f if line.strip()}

def mark_query_done(query: str) -> None:
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(query + "\n")


# ─────────────────────────────────────────────────────────────────────
# HELPERS  (parsing)
# ─────────────────────────────────────────────────────────────────────

def strip_tracking_params(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", "")).rstrip("/")
    except Exception:
        return url

def extract_hashtags(text: str) -> str:
    if not text:
        return ""
    return ", ".join(re.findall(r"#\w+", text))

def detect_post_type(raw: dict) -> str:
    try:
        url = raw.get("linkedinUrl", "") or raw.get("postUrl", "") or raw.get("url", "")
        if "groupPost" in url or "groupPost" in str(raw.get("shareUrn", "")):
            return "group_post"
        if (raw.get("repostId") or raw.get("repost") or raw.get("reposted")
                or raw.get("repostedContent") or raw.get("resharedPost")):
            return "repost"
        return "post"
    except Exception:
        return "post"

def make_linkedin_search_url(query: str) -> str:
    encoded = quote(query)
    return (f"https://www.linkedin.com/search/results/content/"
            f"?keywords={encoded}&origin=GLOBAL_SEARCH_HEADER&sortBy=date_posted")

def _parse_post_date(raw: dict) -> str:
    posted = raw.get("postedAt")
    if isinstance(posted, dict):
        d = posted.get("date")
        if d:
            try:
                return datetime.fromisoformat(str(d).replace("Z", "+00:00")) \
                    .strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except Exception:
                pass
        ts = posted.get("timestamp")
        if ts:
            try:
                return datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc) \
                    .strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except Exception:
                pass
    for key in ("date", "postedDate", "postedAt", "publishedAt"):
        v = raw.get(key)
        if isinstance(v, str) and v:
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")) \
                    .strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except Exception:
                pass
    return ""

def _parse_shares(raw: dict) -> str:
    eng = raw.get("engagement") or raw.get("socialContent") or {}
    val = (eng.get("shares") if isinstance(eng, dict) else None)
    if val is None and isinstance(eng, dict):
        val = eng.get("reposts") or eng.get("numShares")
    if val is None:
        val = raw.get("shares") or raw.get("reposts") or 0
    try:
        return str(int(val))
    except Exception:
        return "0"

def _author_type(raw: dict) -> str:
    a = raw.get("author") or {}
    t = (a.get("type") if isinstance(a, dict) else None) or raw.get("authorType") or "profile"
    return "company" if "compan" in str(t).lower() else "profile"

def parse_post(raw: dict, scraped_at: str, query: str) -> dict:
    author = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    post_url = strip_tracking_params(
        raw.get("linkedinUrl") or raw.get("postUrl") or raw.get("url") or "")
    poster_name = (author.get("name") or raw.get("authorName") or raw.get("name") or "")
    poster_url = strip_tracking_params(
        author.get("linkedinUrl") or author.get("url")
        or raw.get("authorUrl") or raw.get("profileUrl") or "")
    content  = raw.get("content") or raw.get("text") or raw.get("postContent") or ""
    hashtags = extract_hashtags(content)
    return {
        "Post URL"          : post_url,
        "Post Date"         : _parse_post_date(raw),
        "Poster Name"       : poster_name,
        "Poster Profile URL": poster_url,
        "Hashtags"          : hashtags,
        "Post Content"      : content,
        "Post Type"         : detect_post_type(raw),
        "Author Type"       : _author_type(raw),
        "Shares"            : _parse_shares(raw),
        "Search Query"      : query,
        "Scraped At"        : scraped_at,
    }


# ─────────────────────────────────────────────────────────────────────
# PRE-FLIGHT CHECKS
# ─────────────────────────────────────────────────────────────────────

def preflight_check_env(tm: TokenManager) -> bool:
    log.info("  Checking credentials in CONFIG...")
    ok = True
    if not APIFY_TOKENS:
        log.error("  FAIL — CONFIG['APIFY_TOKENS'] khaali hai")
        stats["errors"].append("No Apify tokens in CONFIG")
        ok = False
    else:
        placeholders = [t for t in APIFY_TOKENS if "YAHAN_PASTE" in t or "PASTE_YOUR" in t]
        if placeholders:
            log.error(f"  FAIL — {len(placeholders)} Apify key(s) abhi placeholder hain")
            stats["errors"].append("Apify token placeholder(s) not replaced")
            ok = False
    if not AIRTABLE_TOKEN or "YAHAN_PASTE" in AIRTABLE_TOKEN or "PASTE_YOUR" in AIRTABLE_TOKEN:
        log.error("  FAIL — CONFIG['AIRTABLE_TOKEN'] set karo")
        stats["errors"].append("AIRTABLE_TOKEN not set")
        ok = False
    if ok:
        log.info(f"  OK — {len(APIFY_TOKENS)} Apify key(s) + Airtable token present")
    return ok

def preflight_validate_keys(tm: TokenManager) -> None:
    """Har Apify key ka auth check. Invalid keys ko dead mark kar do."""
    log.info("  Validating Apify keys...")
    for i, token in enumerate(tm.tokens):
        try:
            resp = requests.get("https://api.apify.com/v2/users/me",
                                params={"token": token}, timeout=10)
            if resp.status_code == 200:
                user = resp.json().get("data", {})
                cr = get_remaining_credit(token)
                cr_txt = f" | ~${cr:.2f} left" if cr is not None else ""
                log.info(f"    key #{i+1}: OK ({user.get('username')}){cr_txt}")
            else:
                log.warning(f"    key #{i+1}: INVALID (HTTP {resp.status_code}) — skip")
                tm.dead.add(i)
                stats["keys_status"][f"key #{i+1}"] = "invalid at preflight"
        except Exception as e:
            log.warning(f"    key #{i+1}: check failed ({e}) — skip")
            tm.dead.add(i)
            stats["keys_status"][f"key #{i+1}"] = f"preflight error: {e}"

def preflight_check_airtable() -> bool:
    log.info("  Checking Airtable token + base + table...")
    try:
        resp = requests.get(
            f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables",
            headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}"}, timeout=10)
        if resp.status_code == 401:
            log.error("  FAIL — Airtable token invalid"); return False
        if resp.status_code == 403:
            log.error("  FAIL — Token needs: data.records:write + schema.bases:read"); return False
        if resp.status_code == 404:
            log.error(f"  FAIL — Base not found: {AIRTABLE_BASE_ID}"); return False
        resp.raise_for_status()
        table_names = [t["name"] for t in resp.json().get("tables", [])]
        if AIRTABLE_TABLE not in table_names:
            log.error(f"  FAIL — Table '{AIRTABLE_TABLE}' not found")
            log.error(f"         Available: {table_names}")
            return False
        log.info(f"  OK — Base: {AIRTABLE_BASE_ID} | Table: '{AIRTABLE_TABLE}'")
        return True
    except Exception as e:
        log.error(f"  FAIL — {e}")
        return False

def run_preflight_checks(tm: TokenManager) -> bool:
    log.info("=" * 60)
    log.info("  PRE-FLIGHT CHECKS")
    log.info("=" * 60)
    if not preflight_check_env(tm):
        log.error("  Pre-flight FAILED — CONFIG mein tokens bharo\n")
        return False
    preflight_validate_keys(tm)
    if tm.alive_count() == 0:
        log.error("  Pre-flight FAILED — koi valid Apify key nahi bacha\n")
        return False
    if not preflight_check_airtable():
        log.error("  Pre-flight FAILED — Airtable\n")
        return False
    log.info(f"  All checks passed — {tm.alive_count()} usable key(s)\n")
    return True


# ─────────────────────────────────────────────────────────────────────
# CREDIT CHECK  (best-effort proactive)
# ─────────────────────────────────────────────────────────────────────

def get_remaining_credit(token: str):
    """Bacha hua monthly credit (USD) return karta hai, ya None agar
    reliably nahi nikal paaya (to script reactive rotation par bharosa karti hai)."""
    try:
        resp = requests.get("https://api.apify.com/v2/users/me/limits",
                            params={"token": token}, timeout=10)
        if resp.status_code != 200:
            return None
        data    = resp.json().get("data", {})
        limits  = data.get("limits", {}) or {}
        current = data.get("current", {}) or {}
        max_usd  = limits.get("maxMonthlyUsageUsd")
        used_usd = current.get("monthlyUsageUsd")
        if max_usd is not None and used_usd is not None:
            return max(0.0, float(max_usd) - float(used_usd))
        return None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────
# COST ESTIMATION  (+ credit sufficiency check)
# ─────────────────────────────────────────────────────────────────────

def estimate_cost(tm: TokenManager) -> dict:
    global MIN_CREDIT_BUFFER_USD

    log.info("=" * 60)
    log.info("  COST ESTIMATION")
    log.info("=" * 60)
    queries     = SEARCH_QUERY
    per_query   = MAX_POSTS if MAX_POSTS else PAGES_TO_FETCH * 50
    total_posts = per_query * len(queries)
    est_cost    = round((total_posts / 1000) * APIFY_COST_PER_1K, 4)
    cost_per_q  = round((per_query / 1000) * APIFY_COST_PER_1K, 4)

    # Buffer floor: kabhi bhi ek query ke actual cost se kam nahi honi
    # chahiye, warna key "enough" lagegi lekin mid-run exhaust ho jaayegi.
    MIN_CREDIT_BUFFER_USD = max(MIN_CREDIT_BUFFER_USD, cost_per_q)

    log.info(f"  Actor            : {ACTOR_ID}")
    log.info(f"  Grid             : {len(CONFIG['PREFIXES'])} prefixes × "
             f"{len(CONFIG['LOCATIONS'])} locations = {len(queries)} queries")
    log.info(f"  Per query (cap)  : ~{per_query} posts  (~${cost_per_q})")
    log.info(f"  Total (cap)      : ~{total_posts} posts  →  ~${est_cost} MAX")
    log.info(f"  (Sirf actually returned posts ke liye pay karte ho — ye ek MAX hai.)")

    # ── Credit sufficiency check ────────────────────────────────────
    if cost_per_q > 0:
        credits = [get_remaining_credit(t) for t in tm.alive_tokens()]
        known   = [c for c in credits if c is not None]
        if known and len(known) == len(credits):
            total_credit = sum(known)
            stats["available_credit_usd"] = round(total_credit, 2)
            coverable_queries = int(total_credit // cost_per_q)
            log.info(f"  Available credit : ~${total_credit:.2f} across {tm.alive_count()} key(s)")
            if total_credit < est_cost:
                log.warning(f"  ⚠ INSUFFICIENT CREDIT — grid needs ~${est_cost}, you have ~${total_credit:.2f}")
                log.warning(f"  ⚠ Only ~{min(coverable_queries, len(queries))}/{len(queries)} queries will "
                            f"complete this run before keys run out.")
                log.warning(f"  ⚠ Fix: lower MAX_POSTS, trim PREFIXES/LOCATIONS, or add more keys to "
                            f"CONFIG['APIFY_TOKENS'].")
                log.warning(f"  ⚠ Already-completed queries are checkpointed in {os.path.basename(PROGRESS_FILE)} — "
                            f"rerunning later (with more keys) will resume, not restart.")
            else:
                log.info(f"  ✓ Credit looks sufficient for the full grid.")
        else:
            log.info("  Available credit : unknown (Apify limits API didn't return usable data) — "
                      "reactive rotation will handle exhaustion mid-run.")

    stats["estimated_cost_usd"] = est_cost
    log.info("")
    return {"total_posts": total_posts, "estimated_cost": est_cost, "queries": queries}


# ─────────────────────────────────────────────────────────────────────
# APIFY — PAYLOAD + RUN + WAIT + FETCH  (har call token leta hai)
# ─────────────────────────────────────────────────────────────────────

def build_payload(query: str) -> dict:
    if ACTOR_CHOICE == "curious_coder":
        return {"searchUrl": make_linkedin_search_url(query),
                "maxResults": MAX_POSTS or 100}
    payload = {"searchQueries": [query]}
    if MAX_POSTS:
        payload["maxPosts"] = MAX_POSTS
    else:
        payload["scrapePages"] = PAGES_TO_FETCH
    return payload

_LIMIT_WORDS = ("usage", "credit", "limit", "exceeded", "insufficient", "payment", "quota")

def start_single_run(query: str, token: str) -> str:
    url     = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs"
    payload = build_payload(query)
    log.info(f"  Payload: {payload}")
    resp = requests.post(url, json=payload, params={"token": token}, timeout=30)

    if resp.status_code == 402:
        raise ApifyCreditExhausted(f"HTTP 402: {resp.text[:150]}")
    if resp.status_code == 401:
        raise ApifyTokenInvalid("HTTP 401 unauthorized")
    if not resp.ok:
        low = resp.text.lower()
        if any(k in low for k in _LIMIT_WORDS):
            raise ApifyCreditExhausted(f"HTTP {resp.status_code}: {resp.text[:150]}")
        log.error(f"  Apify Error {resp.status_code}: {resp.text[:400]}")
        resp.raise_for_status()

    run_id = resp.json()["data"]["id"]
    log.info(f"  Run ID  : {run_id}")
    return run_id

def wait_for_run(run_id: str, token: str, poll: int = 10, timeout: int = 1800) -> None:
    url     = f"https://api.apify.com/v2/actor-runs/{run_id}"
    elapsed = 0
    log.info(f"  Waiting (timeout: {timeout // 60} min)...")
    while elapsed < timeout:
        try:
            data   = requests.get(url, params={"token": token}, timeout=15).json()["data"]
            status = data["status"]
        except Exception as e:
            log.warning(f"  Poll error: {e} — retrying...")
            time.sleep(poll); elapsed += poll; continue
        if status == "SUCCEEDED":
            log.info(f"  SUCCEEDED after {elapsed // 60}m {elapsed % 60}s"); return
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            msg = (data.get("statusMessage") or "").lower()
            if any(k in msg for k in _LIMIT_WORDS):
                raise ApifyCreditExhausted(f"run {status}: {data.get('statusMessage','')[:150]}")
            raise RuntimeError(f"Run {run_id} ended with: {status}")
        log.info(f"  Status: {status} | {elapsed // 60}m {elapsed % 60}s elapsed...")
        time.sleep(poll); elapsed += poll
    raise TimeoutError(f"Timed out after {timeout // 60} min")

def fetch_dataset(run_id: str, token: str) -> list:
    url       = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items"
    all_items = []
    offset    = 0
    while True:
        resp = requests.get(url, params={"token": token, "limit": 1000, "offset": offset},
                            timeout=60)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            break
        all_items.extend(items)
        if len(items) < 1000:
            break
        offset += 1000
    return all_items


# ─────────────────────────────────────────────────────────────────────
# SCRAPE ONE QUERY — WITH KEY ROTATION
# ─────────────────────────────────────────────────────────────────────

def scrape_query(query: str, tm: TokenManager):
    """Ek query scrape karta hai. Credit khatam ho to next key par retry.
    Returns: raw items list, ya None agar SAARE keys khatam ho gaye."""
    while True:
        token = tm.current_token()
        if token is None:
            return None
        label = tm.current_label()

        # Proactive: run se pehle credit check
        if PROACTIVE_CREDIT_CHECK:
            remaining = get_remaining_credit(token)
            if remaining is not None and remaining <= MIN_CREDIT_BUFFER_USD:
                log.warning(f"  {label}: sirf ~${remaining:.2f} bacha (buffer ${MIN_CREDIT_BUFFER_USD:.2f}) — rotate")
                tm.kill_current(f"credit low (~${remaining:.2f})")
                continue

        try:
            run_id = start_single_run(query, token)
            wait_for_run(run_id, token)
            return fetch_dataset(run_id, token)
        except ApifyCreditExhausted as e:
            log.warning(f"  {label}: CREDIT EXHAUSTED ({e}) → agli key par ja rahe")
            tm.kill_current("credit exhausted")
            continue   # same query, next key
        except ApifyTokenInvalid as e:
            log.warning(f"  {label}: invalid ({e}) → skip key")
            tm.kill_current("token invalid")
            continue
        # baaki errors (timeout / actor fail) caller ko bubble honge


# ─────────────────────────────────────────────────────────────────────
# CSV (incremental append)
# ─────────────────────────────────────────────────────────────────────

def append_csv(path: str, rows: list) -> None:
    if not rows:
        return
    write_header = not os.path.exists(path)
    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            if write_header:
                writer.writeheader()
            writer.writerows(rows)
        stats["csv_saved"] = True
    except Exception as e:
        log.error(f"  CSV append FAILED: {e}")


# ─────────────────────────────────────────────────────────────────────
# AIRTABLE PUSH  (existing_urls in-memory maintain hota hai)
# ─────────────────────────────────────────────────────────────────────

def get_existing_post_urls() -> set:
    if not SKIP_DUPLICATES:
        return set()
    log.info("  Fetching existing URLs (duplicate check)...")
    url      = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}"
    headers  = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    existing = set()
    offset   = None
    while True:
        params = {"fields[]": "Post URL", "pageSize": 100}
        if offset:
            params["offset"] = offset
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            for rec in data.get("records", []):
                u = rec.get("fields", {}).get("Post URL", "")
                if u:
                    existing.add(u)
            offset = data.get("offset")
            if not offset:
                break
        except Exception as e:
            log.warning(f"  Duplicate check failed: {e} — skipping")
            return set()
    log.info(f"  Found {len(existing)} existing records")
    return existing

def build_airtable_record(parsed: dict) -> dict:
    fields = {
        "Post URL"          : parsed.get("Post URL")           or "",
        "Poster Name"       : parsed.get("Poster Name")        or "",
        "Poster Profile URL": parsed.get("Poster Profile URL") or "",
        "Hashtags"          : parsed.get("Hashtags")           or "",
        "Post Content"      : parsed.get("Post Content")       or "",
        "Post Type"         : parsed.get("Post Type")          or "post",
        "Author Type"       : parsed.get("Author Type")        or "profile",
        "Shares"            : str(parsed.get("Shares")         or "0"),
        "Search Query"      : parsed.get("Search Query")       or "",
    }
    if parsed.get("Post Date"):
        fields["Post Date"]  = parsed["Post Date"]
    if parsed.get("Scraped At"):
        fields["Scraped At"] = parsed["Scraped At"]
    return {"fields": fields}

def push_single_batch(batch: list, headers: dict, url: str) -> tuple:
    records = [build_airtable_record(p) for p in batch]
    try:
        resp = requests.post(url, json={"records": records}, headers=headers, timeout=30)
        if resp.status_code == 200:
            return len(resp.json().get("records", [])), []
        log.error(f"    HTTP {resp.status_code}: {resp.text[:300]}")
        return 0, batch
    except requests.exceptions.Timeout:
        log.error("    Timeout"); return 0, batch
    except Exception as e:
        log.error(f"    Exception: {e}"); return 0, batch

def push_to_airtable(parsed_posts: list, existing_urls: set) -> list:
    """Filter dups → push → existing_urls update. Returns failed rows."""
    url     = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}", "Content-Type": "application/json"}

    if SKIP_DUPLICATES and existing_urls:
        before = len(parsed_posts)
        dup_urls = [p["Post URL"] for p in parsed_posts if p["Post URL"] in existing_urls]
        parsed_posts = [p for p in parsed_posts if p["Post URL"] not in existing_urls]
        skipped = before - len(parsed_posts)
        stats["airtable_skipped_dup"] += skipped
        if skipped:
            log.info(f"  Duplicates skipped: {skipped} | New: {len(parsed_posts)}")
            if LOG_DUPLICATE_URLS:
                for u in dup_urls[:5]:
                    log.info(f"    dup → {u}")
                if len(dup_urls) > 5:
                    log.info(f"    ... +{len(dup_urls) - 5} more (check any of the above in Airtable to verify)")

    if not parsed_posts:
        log.info("  Nothing new to push.")
        return []

    total_batches  = (len(parsed_posts) + AIRTABLE_BATCH_SIZE - 1) // AIRTABLE_BATCH_SIZE
    failed_records = []
    log.info(f"  Pushing {len(parsed_posts)} records in {total_batches} batches...")

    for batch_num, i in enumerate(range(0, len(parsed_posts), AIRTABLE_BATCH_SIZE), start=1):
        batch           = parsed_posts[i: i + AIRTABLE_BATCH_SIZE]
        success, failed = push_single_batch(batch, headers, url)
        if success:
            stats["airtable_success"] += success
            for p in batch:
                if p["Post URL"]:
                    existing_urls.add(p["Post URL"])
            log.info(f"  Batch {batch_num}/{total_batches}  ✓  {success} pushed")
        if failed:
            log.warning(f"  Batch {batch_num}/{total_batches}  retrying...")
            time.sleep(2)
            r_success, r_failed = push_single_batch(failed, headers, url)
            if r_success:
                stats["retry_success"]    += r_success
                stats["airtable_success"] += r_success
                for p in failed:
                    if p["Post URL"]:
                        existing_urls.add(p["Post URL"])
            if r_failed:
                stats["airtable_failed"] += len(r_failed)
                failed_records.extend(r_failed)
        time.sleep(0.25)
    return failed_records


# ─────────────────────────────────────────────────────────────────────
# FLUSH ONE QUERY  (parse → csv → airtable)
# ─────────────────────────────────────────────────────────────────────

def flush_query(raw_items: list, query: str, scraped_at: str, existing_urls: set) -> None:
    parsed = []
    for i, raw in enumerate(raw_items):
        try:
            p = parse_post(raw, scraped_at, query)
            if not p["Post URL"] and not p["Poster Name"]:
                stats["parse_skipped"] += 1
                continue
            parsed.append(p)
            stats["parsed_ok"] += 1
        except Exception as e:
            log.warning(f"  Skipping post #{i}: {e}")
            stats["parse_skipped"] += 1

    if not parsed:
        return
    append_csv(CSV_BACKUP_FILE, parsed)          # backup pehle
    failed = push_to_airtable(parsed, existing_urls)
    if failed:
        append_csv(FAILED_ROWS_FILE, failed)
        log.warning(f"  {len(failed)} rows failed → {FAILED_ROWS_FILE}")


# ─────────────────────────────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────────────────────────────

def print_final_report():
    elapsed = (datetime.now(timezone.utc) -
               datetime.fromisoformat(stats["run_start"])).seconds
    log.info("\n" + "=" * 60)
    log.info("  FINAL RUN REPORT")
    log.info("=" * 60)
    log.info(f"  Actor             : {stats['actor']}")
    log.info(f"  Est. MAX cost     : ${stats['estimated_cost_usd']} USD")
    if stats["available_credit_usd"] is not None:
        log.info(f"  Credit at start   : ${stats['available_credit_usd']} USD")
    log.info(f"  Queries done      : {stats['queries_done']}/{stats['queries_total']}")
    if stats["queries_skipped_done"]:
        log.info(f"  Queries skipped   : {stats['queries_skipped_done']} (already in {os.path.basename(PROGRESS_FILE)})")
    remaining = stats["queries_total"] - stats["queries_done"] - stats["queries_skipped_done"]
    if remaining > 0:
        log.info(f"  Queries remaining : {remaining}  (rerun after adding keys to resume)")
    log.info(f"  {'─' * 40}")
    log.info(f"  Raw posts fetched : {stats['raw_fetched']}")
    log.info(f"  Parsed OK         : {stats['parsed_ok']}")
    log.info(f"  Parse skipped     : {stats['parse_skipped']}")
    log.info(f"  {'─' * 40}")
    log.info(f"  Airtable pushed   : {stats['airtable_success']}")
    log.info(f"  Duplicates skipped: {stats['airtable_skipped_dup']}")
    log.info(f"  Retry recovered   : {stats['retry_success']}")
    log.info(f"  Permanently failed: {stats['airtable_failed']}")
    log.info(f"  {'─' * 40}")
    if stats["keys_status"]:
        log.info(f"  Keys retired      :")
        for k, reason in stats["keys_status"].items():
            log.info(f"    {k}: {reason}")
        log.info(f"  {'─' * 40}")
    log.info(f"  CSV backup        : {'✓ ' + CSV_BACKUP_FILE if stats['csv_saved'] else '—'}")
    log.info(f"  Duration          : {elapsed // 60}m {elapsed % 60}s")
    log.info(f"  Log file          : {LOG_FILE}")
    if stats["errors"]:
        log.error("  ERRORS:")
        for err in stats["errors"]:
            log.error(f"    • {err}")
    log.info("=" * 60)


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────

def main():
    tm = TokenManager(APIFY_TOKENS)

    log.info("=" * 60)
    log.info("  LinkedIn → Airtable  [MULTI-KEY]")
    log.info("=" * 60)
    log.info(f"  Actor           : {ACTOR_CHOICE} ({ACTOR_ID})")
    log.info(f"  Apify keys      : {len(APIFY_TOKENS)}")
    log.info(f"  Queries (grid)  : {len(SEARCH_QUERY)}")
    log.info(f"  DRY_RUN         : {DRY_RUN}")
    log.info(f"  SKIP_DUPLICATES : {SKIP_DUPLICATES}")
    log.info("=" * 60 + "\n")

    # Step 1 — Pre-flight
    if not run_preflight_checks(tm):
        log.error("Aborting.")
        sys.exit(1)

    # Step 2 — Cost estimate + credit sufficiency
    estimate = estimate_cost(tm)
    queries  = estimate["queries"]

    if DRY_RUN:
        log.info("DRY RUN — DRY_RUN=False karke actually chalao.")
        sys.exit(0)

    # Step 3 — dup-check ek baar
    existing_urls = get_existing_post_urls()

    # Step 4 — resume: already-done queries load karo
    completed = load_completed_queries()
    if completed:
        log.info(f"  Resuming: {len(completed)} queries already done ({os.path.basename(PROGRESS_FILE)}) — skipping those.\n")

    # Step 5 — Scrape + push per query (rotation + resume built-in)
    log.info("\n" + "=" * 60)
    log.info("  SCRAPING + PUSHING (per query)")
    log.info("=" * 60)
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")

    # Poora loop try/finally mein hai — Ctrl+C ya koi bhi unexpected crash ho,
    # ab tak jo ho chuka uska final report hamesha print hota hai, aur jo query
    # abhi tak mark_query_done tak nahi pahunchi wo agli run mein retry hogi
    # (progress file + Airtable Post-URL dedup safe hai, kuch bhi duplicate
    # push nahi hoga chahe beech mein kahin bhi abort ho jaaye).
    try:
        for idx, query in enumerate(queries, 1):
            if query in completed:
                stats["queries_skipped_done"] += 1
                continue

            log.info(f"\n  ── Query {idx}/{len(queries)}: {query}  "
                     f"[{tm.current_label()}, {tm.alive_count()} keys left]")
            try:
                raw = scrape_query(query, tm)
                if raw is None:
                    log.error("  SAARE Apify keys khatam ho gaye — ruk rahe hain.")
                    log.error("  Ab tak ka data already push ho chuka hai. Naye keys CONFIG mein daal ke")
                    log.error("  dobara chalao — progress file bache hue queries se resume kar dega.")
                    break

                count = len(raw)
                stats["query_results"][query] = count
                stats["raw_fetched"] += count
                stats["queries_done"] += 1
                log.info(f"  Fetched: {count} posts")

                flush_query(raw, query, scraped_at, existing_urls)
                mark_query_done(query)   # sirf yahan mark hota hai — pura parse+push safe hone ke baad
            except Exception as e:   # scrape / parse / push kahin bhi fail ho — is query ko skip karo, run mat rokna
                log.error(f"  Query {idx} FAILED: {e}")
                stats["errors"].append(f"Query '{query}' failed: {e}")
                stats["query_results"].setdefault(query, 0)
                continue   # not marked done — will retry on next run

            if idx < len(queries):
                time.sleep(3)
    except KeyboardInterrupt:
        log.warning("\n  Interrupted (Ctrl+C) — jo ho chuka wo already saved/pushed hai.")
        log.warning("  Dobara chalao to progress file se wahi se resume hoga, shuru se nahi.")
    finally:
        # Step 6 — Report (chahe loop poora chale, break ho, error se ruke, ya Ctrl+C ho)
        print_final_report()


if __name__ == "__main__":
    main()
