"""
LinkedIn INTENT Scraper -> Airtable  [v3 : INTENT + COMMENTS EDITION]
=====================================================================

KYUN NAYA SCRIPT? (v2 wala post-jaisa lead kabhi nahi pakad paata)
-------------------------------------------------------------------
Reference post (Kunal Munjal / FYNX):

    "Looking to connect with corporate event agencies in Gurgaon.
     We're looking for agencies that organise corporate outings, sports
     days, team-building & wellness experiences ...
     If you're an agency in this space, or know someone who is, let's connect."
    #CorporateEvents #CorporateOutings #SportsEvents #Gurgaon #EmployeeEngagement

v2 is post ko 3 structural reasons se MISS karta hai:

  1. VOCABULARY MISMATCH
     v2 sirf "#offsite", "#SKO", "#workation" type hashtags dhoondta hai.
     Is post par un me se EK BHI hashtag nahi hai.

  2. GEOGRAPHY MISMATCH  <-- sabse bada
     v2 ki LOCATIONS list poori ki poori DESTINATIONS hai (Goa, Coorg, Bali...).
     Lekin buyer apne HQ city se post karta hai -- "Gurgaon" -- jo list me hai
     hi nahi. Demand HQ cities se aati hai, destinations se nahi.

  3. INTENT BLINDNESS
     "#offsite Goa" 90% SUPPLY-side content laata hai -- event companies apne
     hi offsite ki photos post karti hain. v2 ke paas demand ("mujhe agency
     chahiye") aur supply ("hum agency hain") me farq karne ka koi tareeka
     nahi. Lead wahi pehla wala hai.

  4. COMMENTS = ASLI GOLDMINE, aur v2 unhe chhodta hai
     Is post par 11 comments hain. Hiya Agrawal ne "vipul bansal at Enout"
     tag kiya hai. Har aisa comment ek warm, pre-qualified lead hai --
     ya to vendor jo bik raha hai, ya buyer jo same cheez dhoond raha hai.

v3 CHAAR CHEEZEIN ADD KARTA HAI
--------------------------------
  A. INTENT QUERIES  -- natural-language demand phrases x BUYER cities
                        (hashtag grid bhi chalta rahega, dono modes on).
  B. INTENT SCORING  -- har post ko demand/supply/noise regex families se
                        score karke Lead Type nikaalta hai. Junk Airtable
                        tak pahunchta hi nahi.
  C. COMMENT MINING  -- sirf high-score posts ke comments scrape karke
                        alag Airtable table me daalta hai (2-stage, taaki
                        junk posts ke comments par paisa waste na ho).
  D. FRESHNESS       -- postedLimit se sirf naye posts. 2 saal purana
                        "looking for agency" post dead lead hai.

Plus reliability upgrades: Airtable SCHEMA INTROSPECTION (unknown field ->
422 wali crash khatam), env-based secrets, per-stage cost estimate, aur
SELF_TEST mode jisse bina ek bhi credit kharch kiye scorer tune kar sako.

SECRETS -- IMPORTANT
--------------------
Is file me koi token HARDCODE nahi hai aur karna bhi mat. Repo public hai.
Tokens env se aate hain:

    export APIFY_TOKENS="apify_api_xxx,apify_api_yyy,apify_api_zzz"
    export AIRTABLE_TOKEN="patXXXX.yyyy"

ya same folder me ek `.env` file bana lo (wo .gitignore me hai):

    APIFY_TOKENS=apify_api_xxx,apify_api_yyy
    AIRTABLE_TOKEN=patXXXX.yyyy

QUICK START
-----------
    pip install requests
    python linkedin_intent_to_airtable.py --self-test   # 0 credits, scorer check
    python linkedin_intent_to_airtable.py --dry-run     # 0 credits, cost + queries
    python linkedin_intent_to_airtable.py               # asli run
"""

import os
import re
import csv
import sys
import json
import time
import hashlib
import logging
import argparse
import requests
from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse, quote


# ══════════════════════════════════════════════════════════════════════
# ① CONFIG  <- SIRF YEH BLOCK EDIT KARO  (tokens yahan NAHI -- env me)
# ══════════════════════════════════════════════════════════════════════

CONFIG = {

    # ── AIRTABLE TARGET ───────────────────────────────────────────────
    "AIRTABLE_BASE_ID"       : "appNjXRYNAQ2Nuiah",
    "AIRTABLE_TABLE"         : "Scraped Marketing Post",
    # Comments ke liye alag table. Base me bana lo (fields neeche
    # COMMENT_FIELD_ORDER me listed hain). Agar table nahi mila to
    # comment stage apne aap OFF ho jaayega -- posts phir bhi chalenge.
    "AIRTABLE_COMMENTS_TABLE": "Post Comments",

    # ── ACTORS ────────────────────────────────────────────────────────
    "ACTOR"          : "harvestapi",                      # post search
    "COMMENTS_ACTOR" : "harvestapi~linkedin-post-comments",

    # ── SEARCH MODES ──────────────────────────────────────────────────
    # "intent"  = demand phrases x buyer cities   (NAYA -- asli leads)
    # "hashtag" = purana prefix x destination grid (supply-side recon)
    # DEFAULT = sirf "intent" -- kyunki asli leads wahin hain aur free
    # keys me itna hi budget hai. "hashtag" add karoge to supply-side
    # (competitor recon) bhi aayega, lekin cost 3x+ ho jaayega.
    "SEARCH_MODES": ["intent"],

    # ── (A) INTENT GRID ───────────────────────────────────────────────
    # Yeh wo exact language hai jo buyer use karta hai. Reference post ki
    # pehli line literally pehli entry hai.
    "INTENT_PHRASES": [
        "looking to connect with corporate event agencies",
        "looking for a corporate event agency",
        "looking for an event management company",
        "looking for offsite venues",
        "looking for a team building agency",
        "recommendations for corporate offsite",
        "suggest a good offsite location",
        "planning our annual offsite",
        "planning a team offsite",
        "planning our sales kickoff",
        "need a corporate event partner",
        "looking for team outing options",
        "looking for corporate outing venues",
        "shortlisting event agencies",
        "any recommendations for a corporate retreat",
        "looking for a workation venue",
        "looking for resorts for corporate offsite",
        "hiring an agency for our annual day",
        "looking for sports day organisers",
        "employee engagement activity vendors",
    ],

    # BUYER cities -- yahan se demand aati hai. NOTE: yeh destinations
    # (Goa/Coorg/Bali) se ALAG list hai. Reference post "Gurgaon" hai.
    "BUYER_CITIES": [
        "Gurgaon", "Gurugram", "Delhi", "Noida", "NCR",
        "Bangalore", "Bengaluru", "Mumbai", "Pune", "Hyderabad",
        "Chennai", "Kolkata", "Ahmedabad", "Jaipur", "Chandigarh",
        "Dubai", "Singapore",
    ],

    # Phrase ko quotes me bhejein? (LinkedIn phrase-match karta hai --
    # precision badhti hai, recall thoda girta hai.)
    "QUOTE_INTENT_PHRASES" : True,
    # City ke bina bhi bare phrase chalao (broad sweep). Costly but best recall.
    "INCLUDE_BARE_PHRASE"  : True,
    # Phrase x city cross-product. DEFAULT False -- quoted phrase search
    # already tight hai, aur city dimension cost ko 18x kar deta hai
    # (20 queries -> 360). Recall kam pad raha ho tabhi True karo.
    "PHRASE_X_CITY"        : False,

    # ── (B) HASHTAG GRID (purana v2 behaviour) ────────────────────────
    "PREFIXES": [
        "offsite", "corporateoffsite", "salesoffsite", "salesmeet",
        "salesretreat", "leadershipoffsite", "leadershipmeet",
        "leadershipretreat", "teamoffsite", "annualoffsite",
        "saleskickoff", "SKO", "workation",
        # v3 additions -- reference post ke actual hashtags:
        "corporateevents", "corporateoutings", "sportsevents",
        "employeeengagement", "teambuilding", "corporateretreat",
    ],
    "LOCATIONS": [
        "Manesar", "Neemrana", "Jim Corbett", "Agra", "Surajkund",
        "Morni Hills", "Kasauli",
        "Rishikesh", "Mussoorie", "Shimla", "Manali", "Dharamshala",
        "Srinagar", "Gulmarg", "Auli", "Dehradun",
        "Goa", "Lonavala", "Mahabaleshwar", "Alibaug", "Karjat",
        "Igatpuri", "Lavasa", "Panchgani", "Gokarna",
        "Udaipur", "Jaipur", "Jodhpur", "Jaisalmer", "Ranthambore", "Pushkar",
        "Coorg", "Ooty", "Munnar", "Wayanad", "Kabini", "Chikmagalur",
        "Kodaikanal", "Mahabalipuram", "Kumarakom",
        "Andaman", "Pondicherry", "Varkala",
        "Thailand", "Bangkok", "Phuket", "Pattaya", "Hua Hin",
        "Koh Samui", "Chiang Mai",
        "Vietnam", "Da Nang", "Ho Chi Minh City", "Hanoi", "Phu Quoc",
        "Bali", "Jakarta",
        "Maldives",
    ],
    "INCLUDE_BARE_PREFIX": False,

    # Sab kuch ignore karke sirf yeh queries chalani ho to yahan daalo.
    # Entries: plain string, ya {"q": "...", "mode": "intent"}.
    "QUERY_OVERRIDE": [],

    # ── SCALE + FRESHNESS ─────────────────────────────────────────────
    "MAX_POSTS"      : 100,     # per query cap (v2 me 400 tha -- intent
                                # queries me precision zyada hai, 100 kaafi)
    "PAGES_TO_FETCH" : 50,      # sirf tab jab MAX_POSTS = None
    # '1h' | '24h' | 'week' | 'month' | '3months' | '6months' | 'year' | None
    "POSTED_LIMIT"   : "3months",
    "SORT_BY"        : "date",  # 'date' (fresh leads) | 'relevance'

    # ── (C) INTENT SCORING ────────────────────────────────────────────
    # Score >= MIN_INTENT_SCORE hi Airtable jaata hai. CSV me SAB jaata hai
    # (isliye threshold galat lage to bina dobara scrape kiye re-tune kar sakte ho).
    "MIN_INTENT_SCORE"       : 5,
    "PUSH_BELOW_THRESHOLD"   : False,
    # Supply-side (vendor self-promo) posts bhi chahiye? competitor recon
    # ke liye kaam ke hote hain, lekin lead nahi hain.
    "KEEP_SUPPLY_POSTS"      : False,

    # ── (D) COMMENT MINING ────────────────────────────────────────────
    "SCRAPE_COMMENTS"          : True,
    "COMMENT_MIN_SCORE"        : 7,    # isse upar wale posts ke hi comments
    "MAX_COMMENTS_PER_POST"    : 30,
    "MAX_COMMENT_POSTS_PER_RUN": 60,   # hard budget guard
    "COMMENT_BATCH_SIZE"       : 10,   # ek actor run me kitne post URLs
    "SCRAPE_REPLIES"           : True, # nested replies bhi (vendor tags aksar
                                       # reply me hote hain)

    # ── CREDIT / COST ─────────────────────────────────────────────────
    # HARD STOP: is run me itne se zyada estimated spend hote hi ruk jao.
    # Misconfigured grid ($290 wali galti) se bachne ke liye. None = no cap.
    "RUN_BUDGET_USD"         : 10.00,
    "PROACTIVE_CREDIT_CHECK" : True,
    "MIN_CREDIT_BUFFER_USD"  : 0.25,
    "COST_PER_1K_POSTS"      : 2.00,
    "COST_PER_1K_COMMENTS"   : 2.00,   # comments alag item ke roop me bill hote hain

    # ── RESUME ────────────────────────────────────────────────────────
    "PROGRESS_FILE" : os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "scrape_progress.txt"),
    "LEAD_QUEUE_FILE": os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "comment_queue.jsonl"),
    "RESCRAPE_DONE" : False,

    # ── SAFETY ────────────────────────────────────────────────────────
    "DRY_RUN"         : False,
    "SKIP_DUPLICATES" : True,
}


# ══════════════════════════════════════════════════════════════════════
# DO NOT EDIT BELOW THIS LINE
# ══════════════════════════════════════════════════════════════════════

HERE = os.path.dirname(os.path.abspath(__file__))


# ─────────────────────────────────────────────────────────────────────
# SECRETS  (env / .env only -- kabhi hardcode mat karna)
# ─────────────────────────────────────────────────────────────────────

def load_dotenv(path=os.path.join(HERE, ".env")) -> None:
    """Minimal .env loader -- koi dependency nahi. Existing env ko override
    nahi karta (shell hamesha jeetta hai)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


load_dotenv()

APIFY_TOKENS = [t.strip() for t in os.environ.get("APIFY_TOKENS", "").split(",") if t.strip()]
AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN", "").strip()

AIRTABLE_BASE_ID       = CONFIG["AIRTABLE_BASE_ID"]
AIRTABLE_TABLE         = CONFIG["AIRTABLE_TABLE"]
AIRTABLE_COMMENTS_TBL  = CONFIG["AIRTABLE_COMMENTS_TABLE"]
ACTOR_CHOICE           = CONFIG["ACTOR"]
COMMENTS_ACTOR_ID      = CONFIG["COMMENTS_ACTOR"]
MAX_POSTS              = CONFIG["MAX_POSTS"]
PAGES_TO_FETCH         = CONFIG["PAGES_TO_FETCH"]
POSTED_LIMIT           = CONFIG["POSTED_LIMIT"]
SORT_BY                = CONFIG["SORT_BY"]
MIN_INTENT_SCORE       = CONFIG["MIN_INTENT_SCORE"]
PUSH_BELOW_THRESHOLD   = CONFIG["PUSH_BELOW_THRESHOLD"]
KEEP_SUPPLY_POSTS      = CONFIG["KEEP_SUPPLY_POSTS"]
SCRAPE_COMMENTS        = CONFIG["SCRAPE_COMMENTS"]
COMMENT_MIN_SCORE      = CONFIG["COMMENT_MIN_SCORE"]
MAX_COMMENTS_PER_POST  = CONFIG["MAX_COMMENTS_PER_POST"]
MAX_COMMENT_POSTS      = CONFIG["MAX_COMMENT_POSTS_PER_RUN"]
COMMENT_BATCH_SIZE     = CONFIG["COMMENT_BATCH_SIZE"]
SCRAPE_REPLIES         = CONFIG["SCRAPE_REPLIES"]
RUN_BUDGET_USD         = CONFIG["RUN_BUDGET_USD"]
PROACTIVE_CREDIT_CHECK = CONFIG["PROACTIVE_CREDIT_CHECK"]
COST_PER_1K_POSTS      = CONFIG["COST_PER_1K_POSTS"]
COST_PER_1K_COMMENTS   = CONFIG["COST_PER_1K_COMMENTS"]
PROGRESS_FILE          = CONFIG["PROGRESS_FILE"]
LEAD_QUEUE_FILE        = CONFIG["LEAD_QUEUE_FILE"]
RESCRAPE_DONE          = CONFIG["RESCRAPE_DONE"]
DRY_RUN                = CONFIG["DRY_RUN"]
SKIP_DUPLICATES        = CONFIG["SKIP_DUPLICATES"]

MIN_CREDIT_BUFFER_USD  = CONFIG["MIN_CREDIT_BUFFER_USD"]
AIRTABLE_BATCH_SIZE    = 10

ACTORS = {
    "curious_coder": "curious_coder~linkedin-post-search-scraper",
    "harvestapi"   : "harvestapi~linkedin-post-search",
}
ACTOR_ID = ACTORS.get(ACTOR_CHOICE, ACTORS["harvestapi"])

TIMESTAMP           = datetime.now().strftime("%Y%m%d_%H%M%S")
CSV_POSTS_FILE      = os.path.join(HERE, f"linkedin_posts_{TIMESTAMP}.csv")
CSV_COMMENTS_FILE   = os.path.join(HERE, f"linkedin_comments_{TIMESTAMP}.csv")
FAILED_ROWS_FILE    = os.path.join(HERE, f"failed_rows_{TIMESTAMP}.csv")
LOG_FILE            = os.path.join(HERE, f"run_log_{TIMESTAMP}.log")


# ─────────────────────────────────────────────────────────────────────
# QUERY BUILDING
# ─────────────────────────────────────────────────────────────────────

def build_queries() -> list:
    """Returns list of {"q": str, "mode": "intent"|"hashtag", "id": str}."""
    out, seen = [], set()

    def add(q, mode):
        q = " ".join(q.split())
        qid = f"{mode}::{q}"
        if qid in seen:
            return
        seen.add(qid)
        out.append({"q": q, "mode": mode, "id": qid})

    if CONFIG["QUERY_OVERRIDE"]:
        for entry in CONFIG["QUERY_OVERRIDE"]:
            if isinstance(entry, dict):
                add(entry["q"], entry.get("mode", "intent"))
            else:
                add(entry, "hashtag" if str(entry).lstrip().startswith("#") else "intent")
        return out

    modes = CONFIG["SEARCH_MODES"]

    if "intent" in modes:
        for phrase in CONFIG["INTENT_PHRASES"]:
            p = f'"{phrase}"' if CONFIG["QUOTE_INTENT_PHRASES"] else phrase
            if CONFIG["INCLUDE_BARE_PHRASE"]:
                add(p, "intent")
            if CONFIG["PHRASE_X_CITY"]:
                for city in CONFIG["BUYER_CITIES"]:
                    add(f"{p} {city}", "intent")

    if "hashtag" in modes:
        if CONFIG["INCLUDE_BARE_PREFIX"]:
            for pfx in CONFIG["PREFIXES"]:
                add(f"#{pfx}", "hashtag")
        for pfx in CONFIG["PREFIXES"]:
            for loc in CONFIG["LOCATIONS"]:
                add(f"#{pfx} {loc}", "hashtag")

    return out


QUERIES = build_queries()


# ─────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────

def setup_logging():
    handlers = [logging.StreamHandler(sys.stdout)]
    # 0-credit modes ke liye khaali log file mat banao.
    if not {"--self-test", "--preview-queries"} & set(sys.argv):
        handlers.append(logging.FileHandler(LOG_FILE, encoding="utf-8"))
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  [%(levelname)-8s]  %(message)s",
        datefmt="%H:%M:%S",
        handlers=handlers,
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
    "scored_demand"       : 0,
    "scored_supply"       : 0,
    "scored_noise"        : 0,
    "below_threshold"     : 0,
    "queued_for_comments" : 0,
    "comments_fetched"    : 0,
    "comments_pushed"     : 0,
    "csv_saved"           : False,
    "airtable_success"    : 0,
    "airtable_failed"     : 0,
    "airtable_skipped_dup": 0,
    "retry_success"       : 0,
    "queries_done"        : 0,
    "queries_skipped_done": 0,
    "queries_total"       : len(QUERIES),
    "errors"              : [],
    "query_results"       : {},
    "keys_status"         : {},
    "top_leads"           : [],
}


# ─────────────────────────────────────────────────────────────────────
# EXCEPTIONS + TOKEN ROTATION  (v2 se same, proven)
# ─────────────────────────────────────────────────────────────────────

class ApifyCreditExhausted(Exception):
    """Is key ka credit khatam -- agle key par jao."""


class ApifyTokenInvalid(Exception):
    """Ye key auth hi fail kar raha -- skip karo."""


class AllKeysExhausted(Exception):
    """Koi key nahi bacha."""


class TokenManager:
    def __init__(self, tokens):
        self.tokens = list(tokens)
        self.idx    = 0
        self.dead   = set()

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
# PROGRESS / RESUME  (JSONL, v2 ke plain-text file se backward compatible)
# ─────────────────────────────────────────────────────────────────────

def load_progress() -> dict:
    done = {"query": set(), "comments": set()}
    if RESCRAPE_DONE or not os.path.exists(PROGRESS_FILE):
        return done
    with open(PROGRESS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                kind = rec.get("kind", "query")
                if kind in done:
                    done[kind].add(rec.get("id", ""))
            except json.JSONDecodeError:
                # v2 legacy line: bare query text. Dono modes ke liye map karo.
                done["query"].add(f"hashtag::{line}")
                done["query"].add(f"intent::{line}")
    return done


def mark_done(kind: str, item_id: str) -> None:
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": kind, "id": item_id,
                            "at": datetime.now(timezone.utc).isoformat()}) + "\n")


def queue_lead(entry: dict) -> None:
    with open(LEAD_QUEUE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_lead_queue() -> list:
    if not os.path.exists(LEAD_QUEUE_FILE):
        return []
    out, seen = [], set()
    with open(LEAD_QUEUE_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = rec.get("post_url")
            if url and url not in seen:
                seen.add(url)
                out.append(rec)
    return out


# ══════════════════════════════════════════════════════════════════════
# ② INTENT ENGINE  -- v3 ka dimaag
# ══════════════════════════════════════════════════════════════════════
#
# Keyword search bahut shor laati hai. Har post ko regex families se score
# karke hum teen buckets me daalte hain:
#
#   demand  -> koi kuch DHOOND raha hai        = LEAD  (yahi chahiye)
#   supply  -> koi kuch BECH raha hai          = competitor/partner recon
#   noise   -> hiring / course / random        = phenko
#
# Har family par cap laga hai taaki ek hi phrase 5 baar repeat karke score
# inflate na kar sake.
# ──────────────────────────────────────────────────────────────────────

def _rx(pattern: str):
    return re.compile(pattern, re.IGNORECASE | re.UNICODE)


# (label, weight, regex) -- family -> [rules], cap
SIGNAL_FAMILIES = {
    # ── DEMAND: strong, explicit "hume chahiye" ───────────────────────
    "demand_strong": {
        "cap": 8,
        "rules": [
            ("looking_to_connect", 4, _rx(r"looking\s+to\s+connect\s+with")),
            ("looking_for_vendor", 4, _rx(r"looking\s+for\s+(an?\s+|some\s+)?"
                                          r"(corporate\s+)?(event\s+)?"
                                          r"(agenc|vendor|partner|planner|organi[sz]er|"
                                          r"venue|resort|property|supplier|dmc)")),
            ("in_search_of",       4, _rx(r"\b(in\s+search\s+of|on\s+the\s+lookout\s+for|"
                                          r"scouting\s+for|sourcing)\b")),
            ("need_help",          3, _rx(r"\b(need|want)\s+(help\s+)?"
                                          r"(a|an|some|to\s+find|finding|recommendations?)\b")),
            ("recommendations",    3, _rx(r"\b(recommendations?|suggestions?|referrals?)\b")),
            ("shortlisting",       4, _rx(r"\b(shortlist(ing|ed)?|evaluating\s+(vendors|agencies)|"
                                          r"rfp|rfq|request\s+for\s+proposal|quotation|"
                                          r"send\s+(me\s+)?(your\s+)?(proposal|quote|deck))\b")),
            ("help_me_find",       4, _rx(r"\b(help\s+(me|us)\s+(find|plan|source))\b")),
        ],
    },

    # ── DEMAND: soft CTA -- "reach out / tag someone" ─────────────────
    "demand_soft": {
        "cap": 5,
        "rules": [
            ("lets_connect",   2, _rx(r"\blet'?s\s+connect\b")),
            ("dm_me",          2, _rx(r"\b(dm|pm|inbox|message)\s+me\b|\bdrop\s+(me\s+)?a\s+(dm|message)\b")),
            ("know_someone",   3, _rx(r"\b(know\s+someone|knows\s+someone|tag\s+(someone|them)|"
                                      r"refer\s+someone|point\s+me\s+to)\b")),
            ("reach_out",      2, _rx(r"\b(reach\s+out|get\s+in\s+touch|comment\s+below|"
                                      r"drop\s+(a\s+)?comment)\b")),
            ("share_details",  2, _rx(r"\b(share\s+(your\s+)?(details|profile|portfolio|deck)|"
                                      r"do\s+share)\b")),
        ],
    },

    # ── PLANNING: budget/dates/headcount = real, funded project ───────
    "planning": {
        "cap": 6,
        "rules": [
            ("planning_verb", 3, _rx(r"\b(planning|organi[sz]ing|hosting|arranging|curating)\s+"
                                     r"(our|an|a|the|this)\b")),
            ("upcoming",      2, _rx(r"\b(upcoming|next\s+month|this\s+quarter|"
                                     r"q[1-4]\s|early\s+next\s+year)\b")),
            ("headcount",     3, _rx(r"\b(\d{2,4}\s*(pax|people|employees|participants|attendees|"
                                     r"members|folks)|group\s+of\s+\d{2,4}|team\s+of\s+\d{2,4})\b")),
            ("budget",        3, _rx(r"\b(budget|per\s+(head|pax|person)|inr\s*[\d,]+|"
                                     r"₹\s*[\d,]+|\$\s*[\d,]+\s*per)\b")),
            ("dates",         2, _rx(r"\b(dates?\s+(are|is|:)|from\s+\d{1,2}(st|nd|rd|th)?\s+"
                                     r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec))\b")),
        ],
    },

    # ── CATEGORY: hai hi humare business ka topic ─────────────────────
    "category": {
        "cap": 6,
        "rules": [
            ("offsite",        3, _rx(r"\b(off[-\s]?site|offsites)\b")),
            ("team_building",  3, _rx(r"\bteam[-\s]?building|team[-\s]?bonding\b")),
            ("corp_outing",    3, _rx(r"\bcorporate\s+(outing|event|trip|picnic|party)|team\s+outing\b")),
            ("sports_day",     3, _rx(r"\b(sports\s+day|sports\s+event|annual\s+day|"
                                      r"family\s+day|fun\s+day)\b")),
            ("sko",            3, _rx(r"\b(sales\s+kick[-\s]?off|\bsko\b|kickoff\s+meet)\b")),
            ("retreat",        3, _rx(r"\b(retreat|workation|work[-\s]?cation|"
                                      r"leadership\s+meet|town\s?hall|conclave)\b")),
            ("mice",           3, _rx(r"\b(mice|incentive\s+travel|corporate\s+travel|"
                                      r"employee\s+engagement|wellness\s+experience)\b")),
            ("venue",          2, _rx(r"\b(venue|resort|banquet|property|hotel)s?\b")),
        ],
    },

    # ── SUPPLY: vendor apna dhol baja raha hai -> lead NAHI ───────────
    "supply": {
        "cap": 12,
        "rules": [
            ("we_organised",  4, _rx(r"\bwe\s+(organi[sz]ed|hosted|curated|executed|delivered|"
                                     r"conducted|wrapped\s+up|pulled\s+off)\b")),
            ("our_client",    4, _rx(r"\b(our\s+(client|guests?|patrons)|"
                                     r"thank\s+you\s+.{0,30}\s+for\s+trusting|"
                                     r"glad\s+to\s+host|proud\s+to\s+have\s+hosted)\b")),
            ("we_offer",      4, _rx(r"\bwe\s+(offer|provide|specialis?[ez]e|are\s+a\s+"
                                     r"(leading|premier|full[-\s]service))\b")),
            ("dm_us",         3, _rx(r"\b(dm\s+us|contact\s+us|call\s+us|book\s+(with\s+)?us|"
                                     r"write\s+to\s+us|visit\s+our\s+website|enquire\s+now)\b")),
            ("portfolio",     2, _rx(r"\b(our\s+portfolio|our\s+packages?|our\s+properties|"
                                     r"clients\s+include|book\s+now|limited\s+slots)\b")),
            ("testimonial",   2, _rx(r"\b(glimpses?\s+(of|from)|highlights?\s+from|"
                                     r"throwback|recap\s+of)\b")),
        ],
    },

    # ── NOISE: hiring / edtech / spam -- keyword search me flood karte hain ──
    "noise": {
        "cap": 12,
        "rules": [
            ("hiring",   6, _rx(r"\b(we\s+are\s+hiring|we'?re\s+hiring|now\s+hiring|job\s+(opening|alert)|"
                                r"apply\s+now|vacancy|share\s+your\s+(cv|resume)|"
                                r"open\s+(position|role)s?|#hiring)\b")),
            ("edu",      4, _rx(r"\b(webinar|masterclass|cohort|batch\s+starts|enroll|"
                                r"certification|internship|free\s+course)\b")),
            ("crypto",   4, _rx(r"\b(crypto|forex|trading\s+signals|investment\s+opportunity)\b")),
            ("congrats", 3, _rx(r"\b(congratulations|happy\s+to\s+share|thrilled\s+to\s+announce|"
                                r"excited\s+to\s+join|new\s+role)\b")),
        ],
    },
}

# Location detection -- BUYER_CITIES + LOCATIONS + aliases
LOCATION_ALIASES = {
    "gurugram": "Gurgaon", "gurgaon": "Gurgaon",
    "bengaluru": "Bangalore", "bangalore": "Bangalore",
    "ncr": "Delhi NCR", "delhi ncr": "Delhi NCR", "new delhi": "Delhi",
    "bombay": "Mumbai", "calcutta": "Kolkata", "madras": "Chennai",
}


def _location_vocab() -> dict:
    vocab = {}
    for name in list(CONFIG["BUYER_CITIES"]) + list(CONFIG["LOCATIONS"]):
        vocab[name.lower()] = name
    vocab.update(LOCATION_ALIASES)
    return vocab


LOC_VOCAB = _location_vocab()
LOC_REGEX = _rx(r"\b(" + "|".join(sorted((re.escape(k) for k in LOC_VOCAB),
                                         key=len, reverse=True)) + r")\b")

EMAIL_RX   = _rx(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RX   = _rx(r"(?:\+91[\-\s]?)?\b[6-9]\d{9}\b|\+\d{1,3}[\-\s]?\d{6,12}")
HASHTAG_RX = _rx(r"#\w+")


def score_intent(text: str) -> dict:
    """Post text -> {score, lead_type, signals, family_scores}."""
    text = text or ""
    fam_scores, hits = {}, []

    for family, spec in SIGNAL_FAMILIES.items():
        total = 0
        for label, weight, rx in spec["rules"]:
            if rx.search(text):
                total += weight
                hits.append(f"{family}:{label}")
        fam_scores[family] = min(total, spec["cap"])

    positive = (fam_scores["demand_strong"] + fam_scores["demand_soft"]
                + fam_scores["planning"] + fam_scores["category"])
    negative = fam_scores["supply"] + fam_scores["noise"]
    score = positive - negative

    if fam_scores["noise"] >= 4 and fam_scores["demand_strong"] < 4:
        lead_type = "noise"
    elif fam_scores["demand_strong"] >= 3 and fam_scores["demand_strong"] >= fam_scores["supply"]:
        lead_type = "demand"
    elif fam_scores["supply"] > fam_scores["demand_strong"] + fam_scores["demand_soft"]:
        lead_type = "supply"
    elif positive >= 5:
        lead_type = "demand"
    else:
        lead_type = "unclear"

    # Category ka koi zikr hi nahi -> topic hi humara nahi.
    if fam_scores["category"] == 0:
        score -= 3

    return {
        "score"        : score,
        "lead_type"    : lead_type,
        "signals"      : ", ".join(hits[:14]),
        "family_scores": fam_scores,
    }


def detect_locations(text: str) -> str:
    if not text:
        return ""
    found, seen = [], set()
    for m in LOC_REGEX.finditer(text):
        canon = LOC_VOCAB.get(m.group(1).lower(), m.group(1))
        if canon not in seen:
            seen.add(canon)
            found.append(canon)
    return ", ".join(found[:6])


def extract_contacts(text: str) -> tuple:
    emails = ", ".join(dict.fromkeys(EMAIL_RX.findall(text or "")))[:500]
    phones = ", ".join(dict.fromkeys(m.group(0) for m in PHONE_RX.finditer(text or "")))[:200]
    return emails, phones


# ─────────────────────────────────────────────────────────────────────
# PARSING  -- actor output schema thoda badalta rehta hai, isliye har
# field ke liye multiple key fallbacks (defensive, v2 wali style).
# ─────────────────────────────────────────────────────────────────────

def strip_tracking_params(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url)
        return urlunparse((p.scheme, p.netloc, p.path, "", "", "")).rstrip("/")
    except Exception:
        return url


def _first(raw: dict, *keys, default=""):
    for k in keys:
        v = raw.get(k)
        if v not in (None, "", [], {}):
            return v
    return default


def _dig(raw: dict, *paths, default=""):
    """_dig(raw, ("engagement","likes"), ("socialContent","numLikes"))"""
    for path in paths:
        cur = raw
        ok = True
        for key in path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and cur not in (None, "", [], {}):
            return cur
    return default


def _as_int(val) -> int:
    try:
        if isinstance(val, str):
            val = re.sub(r"[^\d]", "", val) or "0"
        return int(float(val))
    except Exception:
        return 0


def extract_hashtags(text: str) -> str:
    return ", ".join(dict.fromkeys(HASHTAG_RX.findall(text or "")))


def _parse_date(raw: dict, *keys) -> str:
    posted = raw.get("postedAt")
    candidates = []
    if isinstance(posted, dict):
        candidates += [posted.get("date"), posted.get("timestamp")]
    for k in keys:
        candidates.append(raw.get(k))
    for v in candidates:
        if v in (None, ""):
            continue
        if isinstance(v, (int, float)) or (isinstance(v, str) and v.isdigit()):
            try:
                ts = float(v)
                if ts > 1e11:      # ms
                    ts /= 1000.0
                return datetime.fromtimestamp(ts, tz=timezone.utc) \
                    .strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except Exception:
                continue
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00")) \
                    .strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except Exception:
                continue
    return ""


def detect_post_type(raw: dict) -> str:
    url = str(_first(raw, "linkedinUrl", "postUrl", "url"))
    if "groupPost" in url or "groupPost" in str(raw.get("shareUrn", "")):
        return "group_post"
    if any(raw.get(k) for k in ("repostId", "repost", "reposted",
                                "repostedContent", "resharedPost")):
        return "repost"
    return "post"


def _author_type(raw: dict) -> str:
    a = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    t = a.get("type") or raw.get("authorType") or "profile"
    return "company" if "compan" in str(t).lower() else "profile"


def _mentions(raw: dict, content: str) -> str:
    """Tagged people/companies. Reference post me 'FYNX Varun Chetal Anish Mukhi'
    bilkul yahi hai -- aur wo log khud bhi leads hain."""
    out = []
    for key in ("mentions", "taggedProfiles", "taggedCompanies", "entities"):
        val = raw.get(key)
        if isinstance(val, list):
            for m in val:
                if isinstance(m, dict):
                    out.append(str(_first(m, "name", "fullName", "title", "text")))
                elif m:
                    out.append(str(m))
    # Emails pehle hata do, warna "kunal@fynx.in" se "fynx.in" mention ban jaata hai.
    clean = EMAIL_RX.sub(" ", content or "")
    for m in re.finditer(r"@([A-Za-z][\w .'-]{1,39})", clean):
        out.append(m.group(1).strip(" .'-"))
    return ", ".join(dict.fromkeys(x for x in out if x))[:500]


HEADLINE_COMPANY_RX = _rx(r"(?:@|\bat\s)\s*([A-Z][\w&.\-']*(?:\s+[A-Z][\w&.\-']*){0,3})")


# Fallback: "Founder - FYNX | ..." wali shape. Lekin "Founder - Helping teams
# scale" jaisi filler headlines bhi isi shape ki hoti hain, isliye gerund /
# stopword se shuru hone wale segments reject kar dete hain.
HEADLINE_DASH_RX = _rx(r"^[^|@]{2,40}?\s+[-\u2013]\s+([A-Z][\w&.\-']*"
                       r"(?:\s+[A-Z][\w&.\-']*){0,2})")
_NOT_A_COMPANY = {"helping", "building", "transforming", "empowering", "making",
                  "driving", "scaling", "creating", "ex", "formerly", "we", "i"}


def company_from_headline(headline: str) -> str:
    """LinkedIn headlines me company aksar "@ Enout", "at Enout" ya
    "Founder - FYNX" ki shape me hoti hai."""
    if not headline:
        return ""
    m = HEADLINE_COMPANY_RX.search(headline)
    if m:
        return m.group(1).strip()
    m = HEADLINE_DASH_RX.search(headline)
    if m:
        cand = m.group(1).strip()
        head = cand.split()[0].lower()
        if head not in _NOT_A_COMPANY and not head.endswith("ing"):
            return cand
    return ""


def is_comment_item(raw: dict) -> bool:
    """harvestapi comments ko dataset me ALAG items ke roop me bhi push karta
    hai (jab scrapeComments on ho). Unhe post samajh ke parse mat karo."""
    if raw.get("type") in ("comment", "reply"):
        return True
    keys = set(raw.keys())
    return bool({"commentUrl", "commentId", "commenter"} & keys) or (
        "postUrl" in keys and "text" in keys and "author" in keys
        and "linkedinUrl" not in keys)


def parse_post(raw: dict, scraped_at: str, query: dict) -> dict:
    author   = raw.get("author") if isinstance(raw.get("author"), dict) else {}
    content  = str(_first(raw, "content", "text", "postContent", "description"))
    post_url = strip_tracking_params(str(_first(raw, "linkedinUrl", "postUrl", "url")))

    intent  = score_intent(content)
    emails, phones = extract_contacts(content)

    reactions = _as_int(_dig(raw, ("engagement", "reactions"), ("engagement", "likes"),
                             ("socialContent", "numLikes"), default=0)
                        or _first(raw, "numLikes", "likes", "reactionsCount", default=0))
    n_comments = _as_int(_dig(raw, ("engagement", "comments"),
                              ("socialContent", "numComments"), default=0)
                         or _first(raw, "commentsCount", "numComments", default=0))
    shares = _as_int(_dig(raw, ("engagement", "shares"), ("engagement", "reposts"),
                          ("socialContent", "numShares"), default=0)
                     or _first(raw, "shares", "reposts", default=0))

    return {
        "Post URL"          : post_url,
        "Post Date"         : _parse_date(raw, "date", "postedDate", "publishedAt"),
        "Poster Name"       : str(_first(author, "name", "fullName")
                                  or _first(raw, "authorName", "name")),
        "Poster Headline"   : str(_first(author, "headline", "occupation", "subtitle")
                                  or _first(raw, "authorHeadline"))[:500],
        "Poster Profile URL": strip_tracking_params(
                                  str(_first(author, "linkedinUrl", "url", "profileUrl")
                                      or _first(raw, "authorUrl", "profileUrl"))),
        "Poster Company"    : (str(_first(author, "companyName", "company")
                                   or _dig(raw, ("author", "company", "name"), default=""))
                               or company_from_headline(
                                   str(_first(author, "headline", "occupation", "subtitle"))))[:200],
        "Hashtags"          : extract_hashtags(content),
        "Mentions"          : _mentions(raw, content),
        "Post Content"      : content,
        "Post Type"         : detect_post_type(raw),
        "Author Type"       : _author_type(raw),
        "Reactions"         : reactions,
        "Comment Count"     : n_comments,
        "Shares"            : shares,
        "Intent Score"      : intent["score"],
        "Lead Type"         : intent["lead_type"],
        "Intent Signals"    : intent["signals"],
        "Detected Location" : detect_locations(content),
        "Emails Found"      : emails,
        "Phones Found"      : phones,
        "Search Query"      : query["q"],
        "Search Mode"       : query["mode"],
        "Scraped At"        : scraped_at,
    }


def parse_comment(raw: dict, parent: dict, scraped_at: str) -> dict:
    author = raw.get("author") if isinstance(raw.get("author"), dict) else \
             (raw.get("commenter") if isinstance(raw.get("commenter"), dict) else {})
    text = str(_first(raw, "text", "content", "commentText", "comment"))
    intent = score_intent(text)
    emails, phones = extract_contacts(text)

    return {
        "Post URL"           : parent.get("post_url", ""),
        "Post Author"        : parent.get("poster_name", ""),
        "Comment URL"        : strip_tracking_params(
                                   str(_first(raw, "commentUrl", "linkedinUrl", "url"))),
        "Commenter Name"     : str(_first(author, "name", "fullName")
                                   or _first(raw, "authorName", "commenterName")),
        "Commenter Headline" : str(_first(author, "headline", "occupation", "subtitle")
                                   or _first(raw, "authorHeadline"))[:500],
        "Commenter Company"  : company_from_headline(
                                   str(_first(author, "headline", "occupation", "subtitle")
                                       or _first(raw, "authorHeadline")))[:200],
        "Commenter Profile URL": strip_tracking_params(
                                   str(_first(author, "linkedinUrl", "url", "profileUrl")
                                       or _first(raw, "authorUrl", "profileUrl"))),
        "Comment Text"       : text,
        "Comment Date"       : _parse_date(raw, "createdAt", "date", "publishedAt"),
        "Comment Likes"      : _as_int(_first(raw, "likes", "reactionsCount",
                                              "numLikes", default=0)),
        "Mentions"           : _mentions(raw, text),
        "Is Reply"           : bool(_first(raw, "isReply", "parentCommentId", default=False)),
        "Commenter Lead Type": intent["lead_type"],
        "Commenter Score"    : intent["score"],
        "Emails Found"       : emails,
        "Phones Found"       : phones,
        "Search Query"       : parent.get("query", ""),
        "Scraped At"         : scraped_at,
    }


def comment_key(c: dict) -> str:
    if c.get("Comment URL"):
        return c["Comment URL"]
    seed = f"{c.get('Post URL','')}|{c.get('Commenter Profile URL','')}|{c.get('Comment Text','')[:80]}"
    return "sha1:" + hashlib.sha1(seed.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────
# APIFY  -- generic runner + key rotation
# ─────────────────────────────────────────────────────────────────────

_LIMIT_WORDS = ("usage", "credit", "limit", "exceeded", "insufficient",
                "payment", "quota")


def get_remaining_credit(token: str):
    """Bacha hua monthly credit (USD), ya None agar reliably nahi nikla."""
    try:
        resp = requests.get("https://api.apify.com/v2/users/me/limits",
                            params={"token": token}, timeout=10)
        if resp.status_code != 200:
            return None
        data    = resp.json().get("data", {})
        limits  = data.get("limits", {}) or {}
        current = data.get("current", {}) or {}
        max_usd, used_usd = limits.get("maxMonthlyUsageUsd"), current.get("monthlyUsageUsd")
        if max_usd is not None and used_usd is not None:
            return max(0.0, float(max_usd) - float(used_usd))
        return None
    except Exception:
        return None


def build_search_payload(query: dict) -> dict:
    if ACTOR_CHOICE == "curious_coder":
        return {
            "searchUrl": ("https://www.linkedin.com/search/results/content/"
                          f"?keywords={quote(query['q'])}"
                          "&origin=GLOBAL_SEARCH_HEADER&sortBy=date_posted"),
            "maxResults": MAX_POSTS or 100,
        }
    payload = {"searchQueries": [query["q"]]}
    if MAX_POSTS:
        payload["maxPosts"] = MAX_POSTS
    else:
        payload["scrapePages"] = PAGES_TO_FETCH
    if POSTED_LIMIT:
        payload["postedLimit"] = POSTED_LIMIT
    if SORT_BY:
        payload["sortBy"] = SORT_BY
    # Comments yahan se NAHI. Stage B alag se, sirf high-intent posts par --
    # warna har junk post ke comments ka bhi bill aata hai.
    payload["scrapeComments"]  = False
    payload["scrapeReactions"] = False
    return payload


def build_comments_payload(post_urls: list) -> dict:
    return {
        "posts"        : post_urls,
        "maxItems"     : MAX_COMMENTS_PER_POST * len(post_urls),
        "scrapeReplies": SCRAPE_REPLIES,
    }


def start_run(actor_id: str, payload: dict, token: str) -> str:
    url  = f"https://api.apify.com/v2/acts/{actor_id}/runs"
    resp = requests.post(url, json=payload, params={"token": token}, timeout=30)

    if resp.status_code == 402:
        raise ApifyCreditExhausted(f"HTTP 402: {resp.text[:150]}")
    if resp.status_code == 401:
        raise ApifyTokenInvalid("HTTP 401 unauthorized")
    if not resp.ok:
        if any(k in resp.text.lower() for k in _LIMIT_WORDS):
            raise ApifyCreditExhausted(f"HTTP {resp.status_code}: {resp.text[:150]}")
        log.error(f"  Apify Error {resp.status_code}: {resp.text[:400]}")
        resp.raise_for_status()

    run_id = resp.json()["data"]["id"]
    log.info(f"  Run ID  : {run_id}")
    return run_id


def wait_for_run(run_id: str, token: str, poll: int = 10, timeout: int = 1800) -> None:
    url, elapsed = f"https://api.apify.com/v2/actor-runs/{run_id}", 0
    while elapsed < timeout:
        try:
            data = requests.get(url, params={"token": token}, timeout=15).json()["data"]
            status = data["status"]
        except Exception as e:
            log.warning(f"  Poll error: {e} -- retrying...")
            time.sleep(poll); elapsed += poll; continue
        if status == "SUCCEEDED":
            log.info(f"  SUCCEEDED after {elapsed // 60}m {elapsed % 60}s")
            return
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            msg = (data.get("statusMessage") or "").lower()
            if any(k in msg for k in _LIMIT_WORDS):
                raise ApifyCreditExhausted(f"run {status}: {data.get('statusMessage','')[:150]}")
            raise RuntimeError(f"Run {run_id} ended with: {status}")
        log.info(f"  Status: {status} | {elapsed // 60}m {elapsed % 60}s elapsed...")
        time.sleep(poll); elapsed += poll
    raise TimeoutError(f"Timed out after {timeout // 60} min")


def fetch_dataset(run_id: str, token: str) -> list:
    url, items, offset = f"https://api.apify.com/v2/actor-runs/{run_id}/dataset/items", [], 0
    while True:
        resp = requests.get(url, params={"token": token, "limit": 1000, "offset": offset},
                            timeout=60)
        resp.raise_for_status()
        page = resp.json()
        if not page:
            break
        items.extend(page)
        if len(page) < 1000:
            break
        offset += 1000
    return items


def run_actor_with_rotation(actor_id: str, payload: dict, tm: TokenManager,
                            est_cost: float = 0.0) -> list:
    """Credit khatam -> agli key -> wahi payload retry. Saare keys mar gaye
    to AllKeysExhausted. Baaki errors caller ko bubble hote hain."""
    while True:
        token = tm.current_token()
        if token is None:
            raise AllKeysExhausted("no usable Apify keys left")
        label = tm.current_label()

        if PROACTIVE_CREDIT_CHECK:
            remaining = get_remaining_credit(token)
            buffer = max(MIN_CREDIT_BUFFER_USD, est_cost)
            if remaining is not None and remaining <= buffer:
                log.warning(f"  {label}: sirf ~${remaining:.2f} bacha "
                            f"(buffer ${buffer:.2f}) -- rotate")
                tm.kill_current(f"credit low (~${remaining:.2f})")
                continue
        try:
            run_id = start_run(actor_id, payload, token)
            wait_for_run(run_id, token)
            return fetch_dataset(run_id, token)
        except ApifyCreditExhausted as e:
            log.warning(f"  {label}: CREDIT EXHAUSTED ({e}) -> agli key")
            tm.kill_current("credit exhausted")
        except ApifyTokenInvalid as e:
            log.warning(f"  {label}: invalid ({e}) -> skip key")
            tm.kill_current("token invalid")


# ─────────────────────────────────────────────────────────────────────
# COST ESTIMATION
# ─────────────────────────────────────────────────────────────────────

def cost_per_query() -> float:
    per_query = MAX_POSTS if MAX_POSTS else PAGES_TO_FETCH * 50
    return round((per_query / 1000) * COST_PER_1K_POSTS, 4)


def estimate_cost(tm: TokenManager) -> dict:
    global MIN_CREDIT_BUFFER_USD

    log.info("=" * 62)
    log.info("  COST ESTIMATION")
    log.info("=" * 62)

    per_query   = MAX_POSTS if MAX_POSTS else PAGES_TO_FETCH * 50
    n_intent    = sum(1 for q in QUERIES if q["mode"] == "intent")
    n_hashtag   = len(QUERIES) - n_intent
    total_posts = per_query * len(QUERIES)
    posts_cost  = round((total_posts / 1000) * COST_PER_1K_POSTS, 2)
    cpq         = cost_per_query()

    comment_items = (MAX_COMMENT_POSTS * MAX_COMMENTS_PER_POST) if SCRAPE_COMMENTS else 0
    comments_cost = round((comment_items / 1000) * COST_PER_1K_COMMENTS, 2)
    est_cost      = round(posts_cost + comments_cost, 2)

    MIN_CREDIT_BUFFER_USD = max(MIN_CREDIT_BUFFER_USD, cpq)

    log.info(f"  Post actor       : {ACTOR_ID}")
    log.info(f"  Queries          : {len(QUERIES)}  "
             f"(intent {n_intent} | hashtag {n_hashtag})")
    log.info(f"  Freshness filter : postedLimit={POSTED_LIMIT}  sortBy={SORT_BY}")
    log.info(f"  Stage A (posts)  : {len(QUERIES)} x {per_query} = "
             f"~{total_posts} posts  ->  ~${posts_cost} MAX")
    if SCRAPE_COMMENTS:
        log.info(f"  Stage B (comments): <= {MAX_COMMENT_POSTS} posts x "
                 f"{MAX_COMMENTS_PER_POST} = ~{comment_items} items  ->  ~${comments_cost} MAX")
    log.info(f"  TOTAL            : ~${est_cost} MAX  "
             f"(sirf actually returned items ka bill aata hai)")

    if cpq > 0:
        credits = [get_remaining_credit(t) for t in tm.alive_tokens()]
        known   = [c for c in credits if c is not None]
        if known and len(known) == len(credits):
            total_credit = sum(known)
            stats["available_credit_usd"] = round(total_credit, 2)
            log.info(f"  Available credit : ~${total_credit:.2f} across "
                     f"{tm.alive_count()} key(s)")
            if total_credit < est_cost:
                coverable = int(total_credit // cpq) if cpq else 0
                log.warning(f"  ! INSUFFICIENT -- need ~${est_cost}, have ~${total_credit:.2f}")
                log.warning(f"  ! ~{min(coverable, len(QUERIES))}/{len(QUERIES)} queries "
                            f"is run me poori hongi.")
                log.warning(f"  ! Fix: MAX_POSTS kam karo, PHRASE_X_CITY=False karo, "
                            f"ya aur keys add karo.")
                log.warning(f"  ! Progress {os.path.basename(PROGRESS_FILE)} me checkpoint "
                            f"hoti hai -- rerun resume karega, restart nahi.")
            else:
                log.info("  OK -- credit poori grid ke liye kaafi lag raha hai.")
        else:
            log.info("  Available credit : unknown -- reactive rotation handle karega.")

    if RUN_BUDGET_USD and est_cost > RUN_BUDGET_USD:
        log.warning(f"  ! Grid ka MAX (~${est_cost}) RUN_BUDGET_USD "
                    f"(${RUN_BUDGET_USD:.2f}) se upar hai.")
        log.warning(f"  ! Run budget hit hote hi ruk jaayega -- baaki queries "
                    f"progress file me pending rahengi (agla run resume karega).")

    stats["estimated_cost_usd"] = est_cost
    log.info("")
    return {"total_posts": total_posts, "estimated_cost": est_cost}


# ─────────────────────────────────────────────────────────────────────
# CSV (incremental append)
# ─────────────────────────────────────────────────────────────────────

def append_csv(path: str, rows: list) -> None:
    if not rows:
        return
    write_header = not os.path.exists(path)
    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()),
                                    extrasaction="ignore")
            if write_header:
                writer.writeheader()
            writer.writerows(rows)
        stats["csv_saved"] = True
    except Exception as e:
        log.error(f"  CSV append FAILED ({os.path.basename(path)}): {e}")


# ══════════════════════════════════════════════════════════════════════
# ③ AIRTABLE  -- SCHEMA-AWARE
# ══════════════════════════════════════════════════════════════════════
#
# v2 ki sabse badi silent failure: table me na maujood field bhejo to
# Airtable poora batch 422 UNKNOWN_FIELD_NAME se reject kar deta hai.
# v3 me naye fields (Intent Score, Lead Type, ...) hain, to hum pehle
# table ka schema padhte hain aur:
#   - jo fields table me nahi hain unhe DROP kar dete hain (crash nahi),
#   - baaki ko field ke asli type ke hisaab se coerce karte hain,
#   - missing fields ki list warn kar dete hain taaki tum bana sako.
# ──────────────────────────────────────────────────────────────────────

TEXT_TYPES   = {"singleLineText", "multilineText", "richText", "email",
                "url", "phoneNumber", "barcode"}
NUMBER_TYPES = {"number", "percent", "currency", "rating", "duration",
                "autoNumber", "count"}
BOOL_TYPES   = {"checkbox"}


class TableSchema:
    def __init__(self, name: str, fields: dict):
        self.name        = name
        self.field_types = fields          # field name -> airtable type
        self.exists      = fields is not None

    def known(self, field: str) -> bool:
        return field in self.field_types

    def coerce(self, field: str, value):
        ftype = self.field_types.get(field, "singleLineText")
        if value is None:
            return None
        if ftype in BOOL_TYPES:
            return bool(value)
        if ftype in NUMBER_TYPES:
            try:
                num = float(value)
                return int(num) if num.is_integer() else num
            except Exception:
                return None
        if ftype in TEXT_TYPES or ftype in ("singleSelect", "multipleSelects"):
            if isinstance(value, bool):
                return "Yes" if value else "No"
            return str(value)
        return str(value)

    def build_record(self, row: dict) -> dict:
        fields = {}
        for key, val in row.items():
            if not self.known(key):
                continue
            coerced = self.coerce(key, val)
            if coerced in (None, ""):
                continue
            fields[key] = coerced
        return {"fields": fields}


def fetch_table_schemas() -> dict:
    """Base ke saare tables ka schema. Returns {table name: TableSchema}."""
    out = {}
    try:
        resp = requests.get(
            f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables",
            headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}"}, timeout=15)
        resp.raise_for_status()
        for tbl in resp.json().get("tables", []):
            out[tbl["name"]] = TableSchema(
                tbl["name"], {f["name"]: f.get("type", "singleLineText")
                              for f in tbl.get("fields", [])})
    except Exception as e:
        log.warning(f"  Schema fetch failed: {e}")
    return out


POST_FIELD_ORDER = [
    "Post URL", "Post Date", "Poster Name", "Poster Headline",
    "Poster Profile URL", "Poster Company", "Hashtags", "Mentions",
    "Post Content", "Post Type", "Author Type", "Reactions", "Comment Count",
    "Shares", "Intent Score", "Lead Type", "Intent Signals",
    "Detected Location", "Emails Found", "Phones Found", "Search Query",
    "Search Mode", "Scraped At",
]

COMMENT_FIELD_ORDER = [
    "Post URL", "Post Author", "Comment URL", "Commenter Name",
    "Commenter Headline", "Commenter Company", "Commenter Profile URL", "Comment Text",
    "Comment Date", "Comment Likes", "Mentions", "Is Reply",
    "Commenter Lead Type", "Commenter Score", "Emails Found", "Phones Found",
    "Search Query", "Scraped At",
]


def warn_missing_fields(schema: TableSchema, expected: list) -> None:
    missing = [f for f in expected if not schema.known(f)]
    if missing:
        log.warning(f"  '{schema.name}' me ye fields nahi hain -- inka data "
                    f"Airtable me DROP hoga (CSV me phir bhi rahega):")
        for f in missing:
            log.warning(f"      - {f}")
        log.warning("  Airtable me ye fields bana do to next run se bharne lagenge.")


def get_existing_keys(table: str, field: str) -> set:
    """Dedup ke liye ek column ki saari values."""
    if not SKIP_DUPLICATES:
        return set()
    log.info(f"  Fetching existing '{field}' from '{table}' (dup check)...")
    url      = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(table)}"
    headers  = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
    existing, offset = set(), None
    while True:
        params = {"fields[]": field, "pageSize": 100}
        if offset:
            params["offset"] = offset
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            for rec in data.get("records", []):
                val = rec.get("fields", {}).get(field, "")
                if val:
                    existing.add(val)
            offset = data.get("offset")
            if not offset:
                break
        except Exception as e:
            log.warning(f"  Dup check failed: {e} -- skipping")
            return set()
    log.info(f"  Found {len(existing)} existing records")
    return existing


def push_batch(batch: list, schema: TableSchema, url: str, headers: dict) -> tuple:
    records = [schema.build_record(r) for r in batch]
    records = [r for r in records if r["fields"]]
    if not records:
        return 0, []
    try:
        resp = requests.post(url, json={"records": records, "typecast": True},
                             headers=headers, timeout=30)
        if resp.status_code == 200:
            return len(resp.json().get("records", [])), []
        log.error(f"    HTTP {resp.status_code}: {resp.text[:300]}")
        return 0, batch
    except requests.exceptions.Timeout:
        log.error("    Timeout"); return 0, batch
    except Exception as e:
        log.error(f"    Exception: {e}"); return 0, batch


def push_rows(rows: list, table: str, schema: TableSchema,
              dedup_field: str, existing: set, key_fn=None) -> list:
    """Dedup -> batch push -> existing set update. Returns failed rows."""
    if not rows or not schema.exists:
        return []

    url     = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{quote(table)}"
    headers = {"Authorization": f"Bearer {AIRTABLE_TOKEN}",
               "Content-Type": "application/json"}
    key_fn  = key_fn or (lambda r: r.get(dedup_field, ""))

    if SKIP_DUPLICATES:
        before = len(rows)
        seen_now = set()
        fresh = []
        for r in rows:
            k = key_fn(r)
            if k and (k in existing or k in seen_now):
                continue
            seen_now.add(k)
            fresh.append(r)
        skipped = before - len(fresh)
        stats["airtable_skipped_dup"] += skipped
        if skipped:
            log.info(f"  Duplicates skipped: {skipped} | New: {len(fresh)}")
        rows = fresh

    if not rows:
        log.info("  Nothing new to push.")
        return []

    total_batches, failed_rows = (len(rows) + AIRTABLE_BATCH_SIZE - 1) // AIRTABLE_BATCH_SIZE, []
    log.info(f"  Pushing {len(rows)} records to '{table}' in {total_batches} batches...")

    for n, i in enumerate(range(0, len(rows), AIRTABLE_BATCH_SIZE), start=1):
        batch = rows[i: i + AIRTABLE_BATCH_SIZE]
        ok, failed = push_batch(batch, schema, url, headers)
        if ok:
            stats["airtable_success"] += ok
            for r in batch:
                if key_fn(r):
                    existing.add(key_fn(r))
            log.info(f"  Batch {n}/{total_batches}  OK  {ok} pushed")
        if failed:
            log.warning(f"  Batch {n}/{total_batches}  retrying...")
            time.sleep(2)
            ok2, failed2 = push_batch(failed, schema, url, headers)
            if ok2:
                stats["retry_success"]    += ok2
                stats["airtable_success"] += ok2
                for r in failed:
                    if key_fn(r):
                        existing.add(key_fn(r))
            if failed2:
                stats["airtable_failed"] += len(failed2)
                failed_rows.extend(failed2)
        time.sleep(0.25)
    return failed_rows


# ─────────────────────────────────────────────────────────────────────
# PRE-FLIGHT
# ─────────────────────────────────────────────────────────────────────

def preflight_env() -> bool:
    log.info("  Checking credentials (env / .env)...")
    ok = True
    if not APIFY_TOKENS:
        log.error("  FAIL -- APIFY_TOKENS env var khaali hai.")
        log.error('         export APIFY_TOKENS="apify_api_xxx,apify_api_yyy"')
        stats["errors"].append("APIFY_TOKENS not set")
        ok = False
    if not AIRTABLE_TOKEN:
        log.error("  FAIL -- AIRTABLE_TOKEN env var khaali hai.")
        log.error('         export AIRTABLE_TOKEN="patXXXX.yyyy"')
        stats["errors"].append("AIRTABLE_TOKEN not set")
        ok = False
    if ok:
        log.info(f"  OK -- {len(APIFY_TOKENS)} Apify key(s) + Airtable token loaded")
    return ok


def preflight_validate_keys(tm: TokenManager) -> None:
    log.info("  Validating Apify keys...")
    for i, token in enumerate(tm.tokens):
        try:
            resp = requests.get("https://api.apify.com/v2/users/me",
                                params={"token": token}, timeout=10)
            if resp.status_code == 200:
                user = resp.json().get("data", {})
                cr   = get_remaining_credit(token)
                log.info(f"    key #{i+1}: OK ({user.get('username')})"
                         + (f" | ~${cr:.2f} left" if cr is not None else ""))
            else:
                log.warning(f"    key #{i+1}: INVALID (HTTP {resp.status_code}) -- skip")
                tm.dead.add(i)
                stats["keys_status"][f"key #{i+1}"] = "invalid at preflight"
        except Exception as e:
            log.warning(f"    key #{i+1}: check failed ({e}) -- skip")
            tm.dead.add(i)
            stats["keys_status"][f"key #{i+1}"] = f"preflight error: {e}"


def preflight_airtable() -> tuple:
    """Returns (ok, posts_schema, comments_schema_or_None)."""
    global SCRAPE_COMMENTS
    log.info("  Checking Airtable base + tables + schema...")
    try:
        resp = requests.get(
            f"https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables",
            headers={"Authorization": f"Bearer {AIRTABLE_TOKEN}"}, timeout=15)
        if resp.status_code == 401:
            log.error("  FAIL -- Airtable token invalid"); return False, None, None
        if resp.status_code == 403:
            log.error("  FAIL -- token needs scopes: data.records:write + schema.bases:read")
            return False, None, None
        if resp.status_code == 404:
            log.error(f"  FAIL -- base not found: {AIRTABLE_BASE_ID}"); return False, None, None
        resp.raise_for_status()
    except Exception as e:
        log.error(f"  FAIL -- {e}"); return False, None, None

    schemas = {t["name"]: TableSchema(
        t["name"], {f["name"]: f.get("type", "singleLineText") for f in t.get("fields", [])})
        for t in resp.json().get("tables", [])}

    if AIRTABLE_TABLE not in schemas:
        log.error(f"  FAIL -- table '{AIRTABLE_TABLE}' not found")
        log.error(f"         Available: {list(schemas)}")
        return False, None, None

    posts_schema = schemas[AIRTABLE_TABLE]
    log.info(f"  OK -- posts table '{AIRTABLE_TABLE}' "
             f"({len(posts_schema.field_types)} fields)")
    warn_missing_fields(posts_schema, POST_FIELD_ORDER)

    comments_schema = schemas.get(AIRTABLE_COMMENTS_TBL)
    if SCRAPE_COMMENTS:
        if comments_schema is None:
            log.warning(f"  Comments table '{AIRTABLE_COMMENTS_TBL}' nahi mila -- "
                        f"comment mining OFF kar rahe hain.")
            log.warning(f"  Banane ke liye ye fields chahiye: {', '.join(COMMENT_FIELD_ORDER)}")
            SCRAPE_COMMENTS = False
        else:
            log.info(f"  OK -- comments table '{AIRTABLE_COMMENTS_TBL}' "
                     f"({len(comments_schema.field_types)} fields)")
            warn_missing_fields(comments_schema, COMMENT_FIELD_ORDER)
    return True, posts_schema, comments_schema


def run_preflight(tm: TokenManager) -> tuple:
    log.info("=" * 62)
    log.info("  PRE-FLIGHT CHECKS")
    log.info("=" * 62)
    if not preflight_env():
        return False, None, None
    preflight_validate_keys(tm)
    if tm.alive_count() == 0:
        log.error("  Pre-flight FAILED -- koi valid Apify key nahi bacha\n")
        return False, None, None
    ok, posts_schema, comments_schema = preflight_airtable()
    if not ok:
        log.error("  Pre-flight FAILED -- Airtable\n")
        return False, None, None
    log.info(f"  All checks passed -- {tm.alive_count()} usable key(s)\n")
    return True, posts_schema, comments_schema


# ══════════════════════════════════════════════════════════════════════
# ④ STAGE A -- POSTS
# ══════════════════════════════════════════════════════════════════════

def process_query_results(raw_items: list, query: dict, scraped_at: str,
                          schema: TableSchema, existing: set) -> None:
    parsed = []
    for i, raw in enumerate(raw_items):
        if not isinstance(raw, dict) or is_comment_item(raw):
            continue
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

    # CSV me SAB jaata hai -- threshold baad me bina re-scrape ke tune kar sako.
    append_csv(CSV_POSTS_FILE, parsed)

    keep = []
    for p in parsed:
        lt = p["Lead Type"]
        stats["scored_demand" if lt == "demand" else
              "scored_supply" if lt == "supply" else "scored_noise"] += 1

        if lt == "supply" and not KEEP_SUPPLY_POSTS:
            continue
        if p["Intent Score"] < MIN_INTENT_SCORE and not PUSH_BELOW_THRESHOLD:
            stats["below_threshold"] += 1
            continue
        keep.append(p)

        if (SCRAPE_COMMENTS and p["Post URL"]
                and p["Intent Score"] >= COMMENT_MIN_SCORE
                and p["Comment Count"] > 0):
            queue_lead({"post_url": p["Post URL"], "poster_name": p["Poster Name"],
                        "query": p["Search Query"], "score": p["Intent Score"]})
            stats["queued_for_comments"] += 1

    top = sorted(parsed, key=lambda r: r["Intent Score"], reverse=True)[:3]
    for t in top:
        if t["Intent Score"] >= MIN_INTENT_SCORE:
            stats["top_leads"].append(
                (t["Intent Score"], t["Poster Name"], t["Post Content"][:90].replace("\n", " ")))

    log.info(f"  Scored: {len(parsed)} posts -> {len(keep)} qualify "
             f"(demand-only, score >= {MIN_INTENT_SCORE})")

    if not keep:
        return
    failed = push_rows(keep, AIRTABLE_TABLE, schema, "Post URL", existing)
    if failed:
        append_csv(FAILED_ROWS_FILE, failed)
        log.warning(f"  {len(failed)} rows failed -> {os.path.basename(FAILED_ROWS_FILE)}")


def stage_a_posts(tm: TokenManager, schema: TableSchema, existing: set,
                  done: dict) -> None:
    log.info("=" * 62)
    log.info("  STAGE A -- POST SEARCH + INTENT SCORING")
    log.info("=" * 62)
    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    cpq   = cost_per_query()
    spent = 0.0

    for idx, query in enumerate(QUERIES, 1):
        if RUN_BUDGET_USD and spent + cpq > RUN_BUDGET_USD:
            log.warning(f"\n  BUDGET STOP -- ~${spent:.2f} spend ho chuka "
                        f"(cap ${RUN_BUDGET_USD:.2f}). Stage A rok rahe hain.")
            log.warning("  Baaki queries pending hain -- agla run resume karega.")
            break
        if query["id"] in done["query"]:
            stats["queries_skipped_done"] += 1
            continue

        log.info(f"\n  -- Query {idx}/{len(QUERIES)} [{query['mode']}]: {query['q']}"
                 f"   ({tm.current_label()}, {tm.alive_count()} keys left)")
        try:
            raw = run_actor_with_rotation(ACTOR_ID, build_search_payload(query), tm, cpq)
        except AllKeysExhausted:
            log.error("  SAARE Apify keys khatam. Ab tak ka data push ho chuka hai.")
            log.error("  Naye keys env me daal ke dobara chalao -- progress resume karegi.")
            raise
        except Exception as e:
            log.error(f"  Query {idx} FAILED: {e}")
            stats["errors"].append(f"Query '{query['q']}' failed: {e}")
            continue   # done mark NAHI -- agle run me retry hoga

        spent += cpq
        count = len(raw)
        stats["query_results"][query["q"]] = count
        stats["raw_fetched"]  += count
        stats["queries_done"] += 1
        log.info(f"  Fetched: {count} posts")

        process_query_results(raw, query, scraped_at, schema, existing)
        mark_done("query", query["id"])
        if idx < len(QUERIES):
            time.sleep(3)


# ══════════════════════════════════════════════════════════════════════
# ⑤ STAGE B -- COMMENT MINING  (sirf high-intent posts par)
# ══════════════════════════════════════════════════════════════════════

def stage_b_comments(tm: TokenManager, schema: TableSchema, done: dict) -> None:
    if not SCRAPE_COMMENTS or schema is None or not schema.exists:
        return

    queue = [q for q in load_lead_queue() if q["post_url"] not in done["comments"]]
    queue.sort(key=lambda q: q.get("score", 0), reverse=True)
    queue = queue[:MAX_COMMENT_POSTS]

    log.info("\n" + "=" * 62)
    log.info("  STAGE B -- COMMENT MINING")
    log.info("=" * 62)
    if not queue:
        log.info("  Queue khaali -- koi high-intent post comments ke liye nahi mila.")
        return
    log.info(f"  {len(queue)} high-intent post(s) (score >= {COMMENT_MIN_SCORE}), "
             f"batch size {COMMENT_BATCH_SIZE}")

    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    existing   = get_existing_keys(AIRTABLE_COMMENTS_TBL, "Comment URL")
    by_url     = {q["post_url"]: q for q in queue}
    est        = round((COMMENT_BATCH_SIZE * MAX_COMMENTS_PER_POST / 1000)
                       * COST_PER_1K_COMMENTS, 4)

    for i in range(0, len(queue), COMMENT_BATCH_SIZE):
        batch_urls = [q["post_url"] for q in queue[i: i + COMMENT_BATCH_SIZE]]
        n = i // COMMENT_BATCH_SIZE + 1
        log.info(f"\n  -- Comment batch {n} ({len(batch_urls)} posts) "
                 f"[{tm.current_label()}]")
        try:
            raw = run_actor_with_rotation(COMMENTS_ACTOR_ID,
                                          build_comments_payload(batch_urls), tm, est)
        except AllKeysExhausted:
            log.error("  Keys khatam -- comment stage yahin rok rahe hain.")
            return
        except Exception as e:
            log.error(f"  Comment batch {n} FAILED: {e}")
            stats["errors"].append(f"Comment batch {n} failed: {e}")
            continue

        parsed = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            parent_url = strip_tracking_params(
                str(_first(item, "postUrl", "post", "parentPostUrl", "sourceUrl")))
            parent = by_url.get(parent_url) or {}
            if not parent and len(batch_urls) == 1:
                parent = by_url.get(batch_urls[0], {})
            parent = dict(parent)
            parent.setdefault("post_url", parent_url or (batch_urls[0] if len(batch_urls) == 1 else ""))
            try:
                c = parse_comment(item, parent, scraped_at)
                if c["Commenter Name"] or c["Comment Text"]:
                    parsed.append(c)
            except Exception as e:
                log.warning(f"  Comment parse skip: {e}")

        stats["comments_fetched"] += len(parsed)
        log.info(f"  Fetched: {len(parsed)} comment(s)")
        if parsed:
            append_csv(CSV_COMMENTS_FILE, parsed)
            before = stats["airtable_success"]
            failed = push_rows(parsed, AIRTABLE_COMMENTS_TBL, schema,
                               "Comment URL", existing, key_fn=comment_key)
            stats["comments_pushed"] += stats["airtable_success"] - before
            if failed:
                append_csv(FAILED_ROWS_FILE, failed)

        for url in batch_urls:
            mark_done("comments", url)
        time.sleep(3)


# ══════════════════════════════════════════════════════════════════════
# ⑥ SELF-TEST  -- 0 credits. Scorer ko tune karne ke liye.
# ══════════════════════════════════════════════════════════════════════

SAMPLES = [
    # 1. Reference post -- ye HIGH score karna chahiye (lead_type=demand).
    ("REFERENCE (Kunal Munjal / FYNX)", """
Looking to connect with corporate event agencies in Gurgaon.

We're looking for agencies that organise corporate outings, sports days,
team-building & wellness experiences and are looking for premium venues
for their clients.

If you're an agency in this space, or know someone who is, let's connect.

FYNX Varun Chetal Anish Mukhi

#CorporateEvents #CorporateOutings #SportsEvents #Gurgaon #EmployeeEngagement
"""),
    # 2. Classic buyer post with budget/headcount -- highest score.
    ("BUYER with budget", """
Planning our annual offsite for a team of 120 in December. Budget is
around INR 15,000 per head, 3 nights. Looking for an agency that can
handle travel + venue + team building. Please DM me with your deck.
"""),
    # 3. Vendor self-promo -- v2 isi type se bhar jaata tha. Score LOW ho.
    ("VENDOR self-promo", """
Glimpses from the corporate offsite we organised for our client at Goa
last week! Our team curated 3 days of team-building activities.
We offer end-to-end offsite planning. DM us to book your next offsite.
#offsite #Goa #teambuilding
"""),
    # 4. Hiring noise -- keyword search me flood karta hai. Reject ho.
    ("HIRING noise", """
We are hiring an Event Manager for our Gurgaon office! Apply now and
share your CV. Great opportunity to work on corporate events and offsites.
#hiring #jobopening
"""),
    # 5. Off-topic -- category signal zero.
    ("OFF-TOPIC", """
Congratulations to the whole team on closing our Series B! Thrilled to
announce this new chapter. Looking to connect with fellow founders.
"""),
]


def run_self_test() -> None:
    print("\n" + "=" * 62)
    print("  INTENT SCORER SELF-TEST  (0 Apify credits used)")
    print("=" * 62)
    print(f"  MIN_INTENT_SCORE  = {MIN_INTENT_SCORE}   (Airtable cutoff)")
    print(f"  COMMENT_MIN_SCORE = {COMMENT_MIN_SCORE}   (comment mining cutoff)")
    for label, text in SAMPLES:
        r = score_intent(text)
        verdict = "PUSH" if (r["score"] >= MIN_INTENT_SCORE
                             and (r["lead_type"] != "supply" or KEEP_SUPPLY_POSTS)) else "drop"
        mine = "+comments" if r["score"] >= COMMENT_MIN_SCORE else ""
        print(f"\n  [{verdict:4}] {label}")
        print(f"         score={r['score']:>3}  type={r['lead_type']:<8} {mine}")
        print(f"         families={r['family_scores']}")
        print(f"         location={detect_locations(text) or '-'}")
        print(f"         signals={r['signals'][:150]}")
    print("\n" + "=" * 62)
    print("  Expected: REFERENCE + BUYER = PUSH | VENDOR/HIRING/OFF-TOPIC = drop")
    print("  Galat lag raha? SIGNAL_FAMILIES ke weights ya MIN_INTENT_SCORE tune karo.")
    print("=" * 62 + "\n")


def preview_queries(limit: int = 25) -> None:
    n_intent = sum(1 for q in QUERIES if q["mode"] == "intent")
    print("\n" + "=" * 62)
    print(f"  QUERY PREVIEW -- {len(QUERIES)} total "
          f"(intent {n_intent} | hashtag {len(QUERIES) - n_intent})")
    print("=" * 62)
    for q in QUERIES[:limit]:
        print(f"  [{q['mode']:<7}] {q['q']}")
    if len(QUERIES) > limit:
        print(f"  ... aur {len(QUERIES) - limit} more")
    print()


# ─────────────────────────────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────────────────────────────

def print_final_report():
    elapsed = int((datetime.now(timezone.utc)
                   - datetime.fromisoformat(stats["run_start"])).total_seconds())
    log.info("\n" + "=" * 62)
    log.info("  FINAL RUN REPORT")
    log.info("=" * 62)
    log.info(f"  Actor              : {stats['actor']}")
    log.info(f"  Est. MAX cost      : ${stats['estimated_cost_usd']} USD")
    if stats["available_credit_usd"] is not None:
        log.info(f"  Credit at start    : ${stats['available_credit_usd']} USD")
    log.info(f"  Queries done       : {stats['queries_done']}/{stats['queries_total']}")
    if stats["queries_skipped_done"]:
        log.info(f"  Queries skipped    : {stats['queries_skipped_done']} (already done)")
    remaining = stats["queries_total"] - stats["queries_done"] - stats["queries_skipped_done"]
    if remaining > 0:
        log.info(f"  Queries remaining  : {remaining}  (rerun to resume)")
    log.info("  " + "-" * 44)
    log.info(f"  Raw posts fetched  : {stats['raw_fetched']}")
    log.info(f"  Parsed OK          : {stats['parsed_ok']}   "
             f"(skipped {stats['parse_skipped']})")
    log.info("  " + "-" * 44)
    log.info("  INTENT BREAKDOWN")
    log.info(f"    demand (LEADS)   : {stats['scored_demand']}")
    log.info(f"    supply (vendors) : {stats['scored_supply']}")
    log.info(f"    noise / unclear  : {stats['scored_noise']}")
    log.info(f"    below threshold  : {stats['below_threshold']} "
             f"(score < {MIN_INTENT_SCORE})")
    log.info("  " + "-" * 44)
    log.info(f"  Comments queued    : {stats['queued_for_comments']}")
    log.info(f"  Comments fetched   : {stats['comments_fetched']}")
    log.info(f"  Comments pushed    : {stats['comments_pushed']}")
    log.info("  " + "-" * 44)
    log.info(f"  Airtable pushed    : {stats['airtable_success']}")
    log.info(f"  Duplicates skipped : {stats['airtable_skipped_dup']}")
    log.info(f"  Retry recovered    : {stats['retry_success']}")
    log.info(f"  Permanently failed : {stats['airtable_failed']}")
    if stats["top_leads"]:
        log.info("  " + "-" * 44)
        log.info("  TOP LEADS THIS RUN")
        for score, name, snippet in sorted(stats["top_leads"], reverse=True)[:8]:
            log.info(f"    [{score:>3}] {name}: {snippet}")
    if stats["keys_status"]:
        log.info("  " + "-" * 44)
        log.info("  Keys retired:")
        for k, reason in stats["keys_status"].items():
            log.info(f"    {k}: {reason}")
    log.info("  " + "-" * 44)
    log.info(f"  CSV (posts)        : {os.path.basename(CSV_POSTS_FILE)}")
    if stats["comments_fetched"]:
        log.info(f"  CSV (comments)     : {os.path.basename(CSV_COMMENTS_FILE)}")
    log.info(f"  Duration           : {elapsed // 60}m {elapsed % 60}s")
    log.info(f"  Log file           : {os.path.basename(LOG_FILE)}")
    if stats["errors"]:
        log.error("  ERRORS:")
        for err in stats["errors"][:20]:
            log.error(f"    - {err}")
    log.info("=" * 62)


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────

def parse_args():
    ap = argparse.ArgumentParser(description="LinkedIn intent scraper -> Airtable")
    ap.add_argument("--self-test", action="store_true",
                    help="Scorer ko sample posts par chalao (0 credits)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Queries + cost dikhao, scrape mat karo")
    ap.add_argument("--preview-queries", action="store_true",
                    help="Generated query list print karo")
    ap.add_argument("--comments-only", action="store_true",
                    help="Stage A skip karke sirf pending comment queue chalao")
    ap.add_argument("--no-comments", action="store_true",
                    help="Stage B skip karo")
    return ap.parse_args()


def main():
    global DRY_RUN, SCRAPE_COMMENTS
    args = parse_args()

    if args.self_test:
        run_self_test()
        return
    if args.preview_queries:
        preview_queries(len(QUERIES))
        return
    if args.dry_run:
        DRY_RUN = True
    if args.no_comments:
        SCRAPE_COMMENTS = False

    tm = TokenManager(APIFY_TOKENS)

    log.info("=" * 62)
    log.info("  LinkedIn INTENT -> Airtable  [v3]")
    log.info("=" * 62)
    log.info(f"  Post actor      : {ACTOR_CHOICE} ({ACTOR_ID})")
    log.info(f"  Comments actor  : {COMMENTS_ACTOR_ID}")
    log.info(f"  Apify keys      : {len(APIFY_TOKENS)}")
    log.info(f"  Search modes    : {CONFIG['SEARCH_MODES']}")
    log.info(f"  Queries         : {len(QUERIES)}")
    log.info(f"  Min intent score: {MIN_INTENT_SCORE}")
    log.info(f"  Comment mining  : {SCRAPE_COMMENTS}")
    log.info(f"  DRY_RUN         : {DRY_RUN}")
    log.info("=" * 62 + "\n")

    ok, posts_schema, comments_schema = run_preflight(tm)
    if not ok:
        log.error("Aborting.")
        sys.exit(1)

    estimate_cost(tm)
    preview_queries()

    if DRY_RUN:
        log.info("DRY RUN -- --dry-run hata ke chalao actual run ke liye.")
        return

    done = load_progress()
    if done["query"] or done["comments"]:
        log.info(f"  Resuming: {len(done['query'])} queries + "
                 f"{len(done['comments'])} comment-jobs already done -- skipping.\n")

    existing = get_existing_keys(AIRTABLE_TABLE, "Post URL")

    try:
        if not args.comments_only:
            stage_a_posts(tm, posts_schema, existing, done)
        stage_b_comments(tm, comments_schema, done)
    except AllKeysExhausted:
        pass
    except KeyboardInterrupt:
        log.warning("\n  Interrupted -- ab tak ka data saved hai, rerun resume karega.")
    finally:
        print_final_report()


if __name__ == "__main__":
    main()
