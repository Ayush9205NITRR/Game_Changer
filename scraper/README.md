# LinkedIn Intent Scraper → Airtable (v3)

Demand-side LinkedIn lead mining. Buyer posts ("mujhe agency chahiye")
dhoondta hai, unhe score karta hai, aur high-intent posts ke comments bhi
mine karta hai.

## Setup

```bash
pip install requests
cp .env.example .env      # phir .env me apne tokens bharo
python linkedin_intent_to_airtable.py --self-test   # 0 credits
python linkedin_intent_to_airtable.py --dry-run     # 0 credits
python linkedin_intent_to_airtable.py               # asli run
```

Flags: `--self-test` `--dry-run` `--preview-queries` `--comments-only` `--no-comments`
`--preview` `--push-csv FILE` `--push-all` `--yes`

## Preview → review → push

Airtable me kuch bhejne se pehle results dekhne ke liye:

```bash
# 1. Scrape + score + CSV. Airtable ko CHHOOTA BHI NAHI (na read, na write).
python linkedin_intent_to_airtable.py --preview

# 2. CSV kholo (Excel/Sheets), junk rows delete kar do.
#    CSV me SAARE scraped posts hote hain -- filtered wale bhi -- taaki
#    threshold galat laga ho to bina dobara scrape kiye theek kar sako.

# 3. Jo bacha wahi push karo (dedup + schema-aware + confirmation prompt).
python linkedin_intent_to_airtable.py --push-csv linkedin_posts_XXXX.csv
```

`--push-csv` by default wahi quality gate lagata hai jo pipeline lagati hai
(`Lead Type != supply`, `Intent Score >= MIN_INTENT_SCORE`) — `--push-all`
se bypass, `--yes` se prompt skip. Comments CSV bhi isi flag se jaati hai;
header dekh ke script khud pata kar leti hai ki posts hai ya comments.

**DHYAAN:** `--preview` credits kharch karta hai — scraping hi paid part hai.
Bilkul free check ke liye `--dry-run` (cost estimate) aur `--self-test`
(scorer) use karo.

## v2 se kya badla

| | v2 | v3 |
|---|---|---|
| Queries | `#offsite Goa` (hashtag × destination) | demand phrases; hashtag grid optional |
| Geography | destinations (Goa, Coorg, Bali) | **buyer cities** (Gurgaon, BLR, Mumbai) |
| Filtering | koi nahi — sab Airtable me | intent scoring: demand / supply / noise |
| Comments | ❌ | ✅ high-intent posts par 2-stage mining |
| Freshness | ❌ (2 saal purane posts) | `postedLimit` |
| Unknown Airtable field | poora batch 422 | schema introspection → drop + warn |
| Secrets | file me hardcoded | env / `.env` only |
| Budget | ~$728 max, koi guard nahi | ~$8 default + `RUN_BUDGET_USD` hard stop |

## Airtable fields

**Posts table** (`Scraped Marketing Post`) — jo fields maujood nahi hain wo
apne aap drop ho jaate hain (run warn karega). Naye v3 fields:

`Poster Headline` (text) · `Poster Company` (text) · `Mentions` (long text) ·
`Reactions` (number) · `Comment Count` (number) · `Intent Score` (number) ·
`Lead Type` (single select: demand / supply / noise / unclear) ·
`Intent Signals` (long text) · `Detected Location` (text) ·
`Emails Found` (text) · `Phones Found` (text) · `Search Mode` (text)

**Comments table** (`Post Comments`) — naya table banao, warna comment stage
apne aap off ho jaayega:

`Post URL` · `Post Author` · `Comment URL` · `Commenter Name` ·
`Commenter Headline` · `Commenter Company` · `Commenter Profile URL` ·
`Comment Text` · `Comment Date` · `Comment Likes` (number) · `Mentions` ·
`Is Reply` (checkbox) · `Commenter Lead Type` · `Commenter Score` (number) ·
`Emails Found` · `Phones Found` · `Search Query` · `Scraped At`

## Phrasing (v3.1) — sirf 1 match kyun aaya tha

v3.0 ke `INTENT_PHRASES` reference post se copy kiye gaye the: 7-7 shabd
lambe, aur `QUOTE=True` ke saath LinkedIn ko **exact contiguous string**
chahiye. Duniya me ek hi bande ne wo exact line likhi thi — wahi ek match
tha. Baaki 19 phrases usi ek idea ke near-duplicate the.

v3.1 me phrasing do axes me todi gayi hai aur boolean se joda gaya hai:

```
("looking for" OR "can anyone recommend" OR "inviting proposals" OR ...)
AND ("corporate offsite" OR "event agency" OR "team building" OR ...)
NOT hiring NOT "apply now" NOT "job opening"
```

32 demand stems × 21 category terms = **672 combinations, 24 queries, ~$4.80**.

- `DEMAND_STEMS` — 2-4 shabd. Lambe sentences exact-match me mar jaate hain.
  Indian procurement register include hai: *empanelment, inviting proposals,
  seeking quotations, requirement for, RFP for, vendors required*.
- `CATEGORY_TERMS` — topic nouns.
- `EXCLUDE_TERMS` — hiring/webinar shor source par hi katta hai.
- `QUERY_STYLE: "phrase"` — fallback agar LinkedIn boolean ignore kare.

## Kaunsi phrasing chali? (iterate karne ka tareeka)

Har run ke end me **QUERY YIELD** table aata hai:

```
  QUERY YIELD  (fetched -> qualified)
    142 ->  11  ("looking for" OR ...) AND ("corporate offsite" OR ...)
     88 ->   0  (...)   <- fetched but 0 qualified: topic milta hai, demand nahi
      0 ->   0  (...)   <- 0 fetched: query hi kuch nahi laayi
```

`0 fetched` har jagah = boolean support ka issue → `QUERY_STYLE` ko
`"phrase"` kar do. `fetched but 0 qualified` = us stem group ko hata do.

Purani run ka post-mortem bina credit kharch kiye:

```bash
python linkedin_intent_to_airtable.py --analyze-csv linkedin_posts_XXXX.csv
```

Batata hai retrieval problem hai ya scoring: lead-type breakdown, score
histogram, per-query yield, top signals, aur **near misses** (threshold se
thoda neeche wale posts) — agar wo asli leads lagein to `MIN_INTENT_SCORE`
kam kar do.

## Tuning

- **Kam leads aa rahe?** `MIN_INTENT_SCORE` 5 → 3, `POSTED_LIMIT` → `"6months"`,
  `PHRASE_X_CITY` → `True` (18× queries, 18× cost).
- **Junk aa raha?** `MIN_INTENT_SCORE` badhao. `--self-test` se pehle check
  karo ki tumhare sample posts sahi bucket me ja rahe hain.
- **Competitor recon chahiye?** `SEARCH_MODES` me `"hashtag"` add karo +
  `KEEP_SUPPLY_POSTS: True`.
- CSV me **saare** scraped posts jaate hain (score chahe kuch bhi ho), sirf
  Airtable filtered hai — isliye threshold dobara scrape kiye bina tune ho jaata hai.

## Resume / cost

`scrape_progress.txt` me har poori hui query checkpoint hoti hai; rerun
resume karta hai, restart nahi. Har query ke turant baad CSV + Airtable
push hota hai, to credit khatam hone par kuch loss nahi hota.

Default grid: 20 intent queries × 100 posts = ~$4 + comments ~$3.60.
`RUN_BUDGET_USD` (default $10) budget hit hote hi rok deta hai.
