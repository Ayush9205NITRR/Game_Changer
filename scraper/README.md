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
