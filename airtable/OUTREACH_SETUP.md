# Outreach Command Center — Airtable setup

Cold-outreach tracking base: contact sequencing (LinkedIn + cold email + calls),
domain/inbox health, content performance, aur intent signals — sab Kylas CRM se
sync hone ke liye taiyaar.

---

## Chalane ka tareeka — GitHub Actions

Schema ka source of truth **repo hai** (`airtable/provision_outreach_base.py`).
Usko live base par apply karne ke liye kahin kuch local chalane ki zaroorat
nahi — GitHub Actions se ho jaata hai.

### Ek baar ka setup

**1. Airtable PAT banao**
Airtable → Developer hub → Personal access tokens → Create token
- Scopes: `schema.bases:write`, `schema.bases:read`
- Access: wahi base jise chhuna hai (**Cold Email Base**)

**2. GitHub me secret daalo**
Repo → Settings → Secrets and variables → Actions → New repository secret
- Name: `AIRTABLE_TOKEN`
- Value: token paste karo

Token repo me kabhi nahi jaata — sirf GitHub Secrets me rehta hai, aur
workflow use env var ke roop me padhta hai.

**3. Workflow chalao**
Actions tab → **"Airtable: provision base"** → Run workflow

Base ID pehle se bhara hua aata hai (`appXomnU6fddl1b1H`). Teen mode hain:

| Mode | Kya karta hai |
|---|---|
| `verify` *(default)* | Kuch likhta nahi. Live base ko repo schema se compare karke batata hai kya missing hai. |
| `dry-run` | Kuch likhta nahi. Poora plan print karta hai. |
| `provision` | **Likhta hai.** Tables + fields + links banata hai, phir turant verify karke dikhata hai. |

Pehli baar: `dry-run` → dekh lo → phir `provision`.

Har run ke baad **job summary me UI wale steps** aa jaate hain — 28 formula/
rollup fields, 8 views, 2 automations — GitHub me hi padh lena, kahin aur
jaane ki zaroorat nahi.

### Nightly drift check

Workflow roz 04:17 UTC par `verify` chalata hai. Red run ka matlab: live base
repo se alag ho gaya (kisi ne UI se field badal diya, ya abhi provision hua
hi nahi). Ye kuch likhta nahi — sirf batata hai.

### Local se chalana ho to

```bash
export AIRTABLE_TOKEN=patXXXX.yyyy
python3 airtable/provision_outreach_base.py --base-id appXomnU6fddl1b1H
```

Script token hamesha `AIRTABLE_TOKEN` env var se uthata hai — kahin hardcode
nahi hai. `--base-id` bhi `AIRTABLE_BASE_ID` env se aa sakta hai.

> **Claude Code ke web session se ye nahi ho sakta.** Wahan
> `api.airtable.com` egress policy me blocked hai (`CONNECT tunnel failed,
> response 403`), isliye token hone par bhi request bahar nahi jaati. GitHub
> Actions ka runner us policy ke peeche nahi hai — isiliye wahan chalta hai.

---

## Ye script Airtable me kya NAHI bana sakti

Airtable ki limitation hai, script ki nahi:

| Cheez | API se ban sakta? |
|---|---|
| Base, tables, links, text/number/date/select/checkbox fields | ✅ Haan |
| **formula** fields | ❌ Nahi |
| **rollup / count / lookup** fields | ❌ Nahi |
| **Views** | ❌ Endpoint hi nahi hai |
| **Automations** | ❌ Endpoint hi nahi hai |

Matlab poora analytics layer (rates, health status, intent score), saare
views, aur dono automations **UI se** banane padenge. Unke click-by-click
steps har workflow run ki job summary me hote hain, ya:

```bash
python3 airtable/provision_outreach_base.py --manual
```

Ye steps script ke andar hi data ke roop me rehte hain, isliye doc aur code
kabhi alag nahi hote. `--verify` batata hai inme se kitne ban chuke hain.

> ⚠️ **Script live Airtable ke against kabhi chali nahi hai** — jis session
> me likhi gayi wahan host blocked tha. Schema graph offline validate ho
> chuka hai (`--self-test`, jisme `--verify` ka round-trip bhi shaamil hai)
> aur request shapes documented meta API ke hisaab se hain, par pehla real
> run tumhara hoga. Isliye script idempotent hai: fail ho to dobara chala
> do, jo ban chuka hai use skip kar degi.

---

## Order of operations

```
1. AIRTABLE_TOKEN secret daalo          (GitHub Settings)
2. Workflow -> mode: dry-run            (kuch nahi likhta, plan dikhata hai)
3. Workflow -> mode: provision          (tables + fields + links)
4. Job summary ke UI steps karo:
   4a. Derived fields   (order maayne rakhta hai -- dependencies hain)
   4b. Views
   4c. Automations      (automations/*.js paste karo)
5. Workflow -> mode: verify             (sab bana ya nahi, confirm)
6. Kylas sync connect karo
```

**Step 4a ka order chhodna mat.** `Domains.Open Rate` formula
`Domains.Opens Count` rollup par depend karta hai, jo `Sends.Opened Num`
formula par depend karta hai. `--manual` sahi order me print karta hai;
usi kram me banao warna Airtable "field not found" dega.

Base ID Airtable ke URL me `app` se shuru hone wala hissa hai:

```
https://airtable.com/appXomnU6fddl1b1H/tblfsN7CythOuOirF/viw5gCJRhzinmdPZl
                     ^^^^^^^^^^^^^^^^^  = Cold Email Base
```

> Base me pehle se ek table hai. Script kuch **delete nahi karti** — sirf
> naye tables/fields add karti hai aur reciprocal links rename karti hai.
> Agar tumhari maujooda table ka naam hamare 7 me se kisi se match karta hai
> (`Contacts`, `Sends`, `Domains`, `Inboxes`, `Content`, `Intent Signals`,
> `Daily Snapshot`), to script usi table me fields add kar degi, nayi nahi
> banayegi. `dry-run` pehle chala ke dekh lena.

---

## Poora schema

Ye block `--dry-run` ke output se generate hua hai, haath se nahi likha —
jo script banayegi bilkul yahi hai.

`<< UI-only` matlab wo field tumhe UI se banana hai.

```
Domains
    Domain Name                singleLineText  [PRIMARY]
    Status                     singleSelect
    Warmup Start Date          date
    SPF Set Up                 checkbox
    DKIM Set Up                checkbox
    DMARC Set Up               checkbox
    Notes                      multilineText
    Linked Inboxes             link -> Inboxes  (auto-reciprocal)
    Sends                      link -> Sends  (auto-reciprocal)
    Intent Signals             link -> Intent Signals  (auto-reciprocal)
    Daily Snapshots            link -> Daily Snapshot  (auto-reciprocal)
    Total Sent                 count  << UI-only
    Opens Count                rollup  << UI-only
    Replies Count              rollup  << UI-only
    Bounces Count              rollup  << UI-only
    Spam Count                 rollup  << UI-only
    Open Rate                  formula  << UI-only
    Reply Rate                 formula  << UI-only
    Bounce Rate                formula  << UI-only
    Spam Complaint Rate        formula  << UI-only
    Health Status              formula  << UI-only

Inboxes
    Inbox Email                email  [PRIMARY]
    Provider                   singleSelect
    Daily Limit                number
    Warmup Stage               singleSelect
    Domain                     link -> Domains
    Sends                      link -> Sends  (auto-reciprocal)
    Intent Signals             link -> Intent Signals  (auto-reciprocal)

Content
    Template Name              singleLineText  [PRIMARY]
    Subject Line               singleLineText
    Body Variant               multilineText
    CTA Type                   singleSelect
    Sends                      link -> Sends  (auto-reciprocal)
    Total Sent                 count  << UI-only
    Opens Count                rollup  << UI-only
    Replies Count              rollup  << UI-only
    Positive Replies Count     rollup  << UI-only
    Meetings Count             rollup  << UI-only
    Open Rate                  formula  << UI-only
    Reply Rate                 formula  << UI-only
    Positive Reply Rate        formula  << UI-only
    Meeting Rate               formula  << UI-only

Contacts
    Contact Name               singleLineText  [PRIMARY]
    Email                      email
    Company                    singleLineText
    Kylas Contact ID           singleLineText
    Current Stage              singleSelect
    Last Activity Date         date
    Sends                      link -> Sends  (auto-reciprocal)
    Intent Signals             link -> Intent Signals  (auto-reciprocal)
    Engaged                    formula  << UI-only
    Total Intent Score         rollup  << UI-only

Sends
    Activity                   singleLineText  [PRIMARY]
    Date                       date
    Channel                    singleSelect
    Delivered                  checkbox
    Opened                     checkbox
    Replied                    checkbox
    Reply Type                 singleSelect
    Bounced                    checkbox
    Spam Complaint             checkbox
    Call Outcome               singleSelect
    Meeting Booked             checkbox
    Contact                    link -> Contacts
    Domain                     link -> Domains
    Inbox                      link -> Inboxes
    Content                    link -> Content
    Opened Num                 formula  << UI-only
    Replied Num                formula  << UI-only
    Bounced Num                formula  << UI-only
    Spam Num                   formula  << UI-only
    Meeting Num                formula  << UI-only
    Positive Reply Num         formula  << UI-only

Intent Signals
    Signal                     singleLineText  [PRIMARY]
    Signal Type                singleSelect
    Date                       date
    Strength                   singleSelect
    Contact                    link -> Contacts
    Source Domain              link -> Domains
    Source Inbox               link -> Inboxes
    Strength Score             formula  << UI-only

Daily Snapshot
    Snapshot Key               singleLineText  [PRIMARY]
    Date                       date
    Sent Today                 number
    Opened Today               number
    Replied Today              number
    Meetings Today             number
    Bounced Today              number
    Spam Complaints Today      number
    Domain                     link -> Domains
```

### Table links — kaun kisse juda hai

```
                    ┌───────────┐
                    │  Domains  │
                    └─────┬─────┘
       ┌──────────────────┼──────────────────┬────────────────┐
       │                  │                  │                │
       ▼                  ▼                  ▼                ▼
  ┌─────────┐        ┌─────────┐    ┌───────────────┐  ┌──────────────┐
  │ Inboxes │───────▶│  Sends  │◀───│ Intent Signals│  │Daily Snapshot│
  └─────────┘        └────┬────┘    └───────┬───────┘  └──────────────┘
                          │                 │
                     ┌────┴────┐            │
                     ▼         ▼            ▼
                ┌─────────┐ ┌──────────────────┐
                │ Content │ │     Contacts     │
                └─────────┘ └──────────────────┘
```

Har rishta ek hi baar banta hai — Airtable doosri taraf reciprocal field
apne aap bana deta hai, aur script use sahi naam de deti hai:

| Rishta | Source field | Reciprocal (auto, renamed) |
|---|---|---|
| Inboxes → Domains | `Inboxes.Domain` | `Domains.Linked Inboxes` |
| Sends → Contacts | `Sends.Contact` | `Contacts.Sends` |
| Sends → Domains | `Sends.Domain` | `Domains.Sends` |
| Sends → Inboxes | `Sends.Inbox` | `Inboxes.Sends` |
| Sends → Content | `Sends.Content` | `Content.Sends` |
| Intent Signals → Contacts | `Intent Signals.Contact` | `Contacts.Intent Signals` |
| Intent Signals → Domains | `Intent Signals.Source Domain` | `Domains.Intent Signals` |
| Intent Signals → Inboxes | `Intent Signals.Source Inbox` | `Inboxes.Intent Signals` |
| Daily Snapshot → Domains | `Daily Snapshot.Domain` | `Domains.Daily Snapshots` |

> Dono taraf se link field banane ki koshish mat karna — Airtable tab 2 ki
> jagah 4 fields bana deta hai. Script isiliye har rishta ek hi baar banati
> hai aur reciprocal ko rename karti hai.

---

## Spec se 6 jagah hatna pada — aur kyun

Har ek Airtable ki hard limitation hai. Koi bhi tumhare intent ko nahi
badalta, sirf usko Airtable me possible banata hai.

**1. `Intent Signals` ka primary field `Contact` link nahi ho sakta**
Airtable link field ko primary nahi banne deta. Isliye primary
`Signal` (text) hai — jaise `"Link Clicked - John Doe"` — aur `Contact`
link uske turant baad. Wahi pattern jo tumne khud `Sends.Activity` me use
kiya tha.

**2. `Daily Snapshot` ka primary `Date` ki jagah `Snapshot Key`**
Tumne likha tha *"Date — primary field, combine with Domain for uniqueness"*.
Airtable me composite primary key hota hi nahi. `Snapshot Key`
(`"2026-08-26 :: get-yourbrand.com"`) wahi kaam karta hai jo tum chahte the:
automation isse dedupe karti hai (isliye dobara chalana safe hai), aur linked
record preview me row pehchani jaati hai. `Date` alag date field ke roop me
maujood hai — grouping/filtering usi par karna.
*Primary field UI se ek click me badla ja sakta hai agar plain `Date` hi chahiye.*

**3. `Intent Signals.Source` ko 2 fields me toda**
Ek Airtable link field sirf **ek** table ko point kar sakta hai, "Domains
**ya** Inboxes" nahi. Isliye `Source Domain` aur `Source Inbox` — dono
optional. Jo relevant ho wo bharo.

**4. `Strength` ko SUM karne ke liye numeric helper chahiye**
`Strength` single-select hai (Low/Medium/High) — Airtable text ko SUM nahi
karta, to `Total Intent Score` seedhe usko rollup nahi kar sakta. Isliye
`Intent Signals.Strength Score` formula: High=3, Medium=2, Low=1. Rollup
usko SUM karta hai. **Weights badalne hon to bas wahi ek formula badlo.**

**5. Checkbox counts ke liye 1/0 helper formulas**
Rollup checkbox ko SUM nahi kar sakta. `Sends` par 6 chhote formula fields
hain (`Opened Num`, `Replied Num`, `Bounced Num`, `Spam Num`, `Meeting Num`,
`Positive Reply Num`) jo checkbox → 1/0 karte hain. Rate formulas inhi
rollups ko divide karte hain — bilkul wahi jo tumne suggest kiya tha
("create two number rollups and a formula field dividing one by the other").

**6. `Health Status` me `"No Data"` ka case joda**
Tumhare rules literally lagate to **har naya domain turant "At Risk"**
dikhta — kyunki 0 sends par Open Rate 0 hai, aur 0 < 20%. Isliye pehla
check `Total Sent = 0 → "No Data"` hai. Baaki thresholds bilkul tumhare
hisaab se: spam > 0.1% → Blocked, bounce > 3% → At Risk, open < 20% → At Risk,
warna Healthy.

---

## Automations

Dono UI se banani hain. Scripts `airtable/automations/` me ready hain.

### 1. Daily Snapshot — `automations/daily_snapshot.js`

```
Trigger : At scheduled time  →  Daily  →  11:59 PM
Action  : Run a script       →  daily_snapshot.js paste karo
```

Aaj ke Sends uthata hai, Domain se group karta hai, har domain ki ek row
`Daily Snapshot` me likh deta hai.

Script ke top par **`TIMEZONE` set karna zaroori hai** (default
`Asia/Kolkata`). Galat rakha to 11:59 PM ka run galat din me gir sakta hai.

`Snapshot Key` ki wajah se ye idempotent hai — dobara chalane par purani row
update hoti hai, duplicate nahi banti. Din miss ho jaaye to script me
`TARGET_DATE = '2026-08-20'` daal ke backfill kar sakte ho.

> Script `Sends` par **`Today (automation source)`** naam ka view padhta hai
> (filter: `Date is today`) taaki poori table scan na karni pade. Ye view
> `--manual` ke Step 2 me hai — naam exactly wahi rakhna. View na mile to
> script full scan par fall back kar deta hai.

**Ek baat jaan-bujh ke aisi hai:** jin Sends rows me `Domain` khaali hai
(LinkedIn aur Call activity) wo snapshot me count nahi hoti — snapshot
per-domain hai. Script har run me batata hai kitni rows is wajah se chhooti.

### 2. Sequence Stop — `automations/sequence_stop.js`

```
Trigger : When record matches conditions  →  Contacts  →  Engaged is checked
Action  : Run a script                    →  sequence_stop.js paste karo
```

**🚩 Ye wo cheez hai jo tumne flag karne ko kaha tha — aur haan, external
tool chahiye.**

Airtable khud kisi sequencer ko rok nahi sakta. `Engaged` sirf ek Airtable
field hai; usse Instantly/Smartlead/Lemlist me kuch nahi hota. Beech me kuch
chahiye hi chahiye. Do raaste:

- **Seedha** — sequencer ka apna API ho to `WEBHOOK_URL` me uska endpoint
  daalo aur payload unke schema me badal do. Kam moving parts.
- **Make.com / n8n / Zapier** — unme "Custom webhook" trigger banao, URL
  yahan paste karo, aur "remove from campaign" step wahan lagao. Better jab
  sequencer ka API ganda ho, ya retry + logging chahiye.

Script me `WEBHOOK_URL` khaali chhoda hai aur wo **jaan-bujh ke fail hoti
hai** jab tak set na ho — taaki chup-chaap ye na lage ki sequence ruk gayi
jabki asal me sirf checkbox tick hua tha. Isi tarah non-2xx response par bhi
throw karti hai, taaki Airtable ke run history me red dikhe.

Automation banate waqt script editor me ye input variables add karne honge
(naam bilkul yahi): `recordId`, `contactName`, `email`, `kylasId`, `stage`.

---

## Kylas sync se pehle

- **`Contacts.Email` hi unique key hai.** Har row me bhara hona chahiye —
  matching isi par hoti hai. Airtable field ko "required" nahi bana sakta,
  isliye sync ke pehle blank-email rows ka filtered view bana ke check kar
  lena.
- **`Kylas Contact ID` bharna.** Email badal jaaye tab bhi re-sync isse
  reliable rehta hai. Email ke bharose mat rehna.
- **`Current Stage` ke naam exact match hone chahiye.** Kylas ke stages aur
  yahan ke 13 options — spelling/case bilkul same. `CNC-1` ≠ `CNC 1`.
- **`Engaged` formula hai, likha nahi ja sakta.** Kylas ise overwrite karne
  ki koshish na kare — wo `Current Stage` se apne aap nikalta hai.

---

## Files

```
.github/workflows/
└── airtable-provision.yml       # verify / dry-run / provision + nightly drift

airtable/
├── provision_outreach_base.py   # schema ka single source of truth + provisioner
├── OUTREACH_SETUP.md            # ye file
└── automations/
    ├── daily_snapshot.js        # scheduled, 11:59 PM
    └── sequence_stop.js         # Engaged → webhook
```

`provision_outreach_base.py` sirf script nahi, **schema ka source of truth**
hai. Tables, fields, links, derived fields, views, automations — sab usme
data ke roop me hain. Schema badalna ho to wahi file edit karo, `--self-test`
chalao (references, primary-field legality, link clashes sab check karta
hai), phir dobara run karo.
