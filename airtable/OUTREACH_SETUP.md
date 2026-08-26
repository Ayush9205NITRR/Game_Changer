# Outreach Command Center — Airtable setup

Cold-outreach tracking base: contact sequencing (LinkedIn + cold email + calls),
domain/inbox health, content performance, aur intent signals — sab Kylas CRM se
sync hone ke liye taiyaar.

---

## Pehle ye padho — base abhi BANA NAHI hai

Do cheezein raaste me aa gayin. Dono ke aage-peeche ka kaam pura ho chuka hai,
sirf trigger dabana baaki hai.

### 1. Is session se Airtable tak pahunch nahi hai

`api.airtable.com` is workspace ki egress policy me blocked hai:

```
CONNECT tunnel failed, response 403   (host: api.airtable.com:443)
```

Token dene se bhi farak nahi padta — request network se hi bahar nahi jaati.
Base ID dene se bhi nahi. Isliye ye command **tumhe apni machine se**
chalani padegi:

```bash
export AIRTABLE_TOKEN=patXXXX.yyyy        # scopes: schema.bases:write + :read
python3 airtable/provision_outreach_base.py --base-id appXomnU6fddl1b1H
```

`appXomnU6fddl1b1H` = **Cold Email Base** (tumne khud banaya). Naya base
banwana ho to `--base-id` ki jagah `--workspace-id wspXXXX --base-name "..."`
de dena.

Script wahi likha hai jo yahan chal jaata to main khud chalata. 7 tables,
44 plain fields, 9 links (dono taraf ke reciprocal fields ke saath) — sab
ek command me.

> Base me pehle se ek table hai. Script kuch **delete nahi karti** — sirf
> naye tables/fields add karti hai aur reciprocal links rename karti hai.
> Chalne se pehle wo dikhati hai ki base me kya mila aur kya chhuega, phir
> confirm maangti hai. Bina pooche chalana ho to `--yes` laga do.
>
> Ek hi cheez dhyan se dekhna: agar tumhari maujooda table ka naam hamare
> 7 me se kisi se match karta hai (`Contacts`, `Sends`, `Domains`,
> `Inboxes`, `Content`, `Intent Signals`, `Daily Snapshot`), to script usi
> table me fields add kar degi, nayi nahi banayegi. Confirmation screen
> isko `<-- NAAM MATCH KARTA HAI` karke highlight karti hai.

> ⚠️ **Script live API ke against test nahi hua** — kyunki host block hai.
> Schema graph offline validate ho chuka hai (`--self-test` clean hai) aur
> request shapes Airtable ke documented meta API ke hisaab se hain, par
> pehla real run tumhara hoga. Isliye script idempotent hai: fail ho to
> dobara chala do, jo ban chuka hai use skip kar degi.

### 2. Airtable ka API aadhi cheezein bana hi nahi sakta

Ye Airtable ki limitation hai, script ki nahi:

| Cheez | API se ban sakta? |
|---|---|
| Base, tables, links, text/number/date/select/checkbox fields | ✅ Haan |
| **formula** fields | ❌ Nahi |
| **rollup / count / lookup** fields | ❌ Nahi |
| **Views** | ❌ Endpoint hi nahi hai |
| **Automations** | ❌ Endpoint hi nahi hai |

Matlab poora analytics layer (rates, health status, intent score), saare
views, aur dono automations **UI se** banane padenge.

Iske liye click-by-click steps script khud print karta hai — 0 network:

```bash
python3 airtable/provision_outreach_base.py --manual
```

Ye steps script ke andar hi data ke roop me rehte hain, isliye doc aur code
kabhi alag nahi hote.

---

## Order of operations

```
1. python3 airtable/provision_outreach_base.py --self-test     # 0 network, sanity
2. python3 airtable/provision_outreach_base.py --dry-run       # 0 network, kya banega
3. python3 airtable/provision_outreach_base.py \               # asli run
       --base-id appXomnU6fddl1b1H
4. python3 airtable/provision_outreach_base.py --manual        # UI steps
   4a. Derived fields   (order maayne rakhta hai — dependencies hain)
   4b. Views
   4c. Automations      (automations/*.js paste karo)
5. Kylas sync connect karo
```

**Step 4a ka order chhodna mat.** `Domains.Open Rate` formula
`Domains.Opens Count` rollup par depend karta hai, jo `Sends.Opened Num`
formula par depend karta hai. `--manual` sahi order me print karta hai;
usi kram me banao warna Airtable "field not found" dega.

---

## Token setup

Airtable PAT chahiye in scopes ke saath:

- `schema.bases:write` — tables + fields banane ke liye
- `schema.bases:read` — idempotent re-run ke liye

Base ID Airtable ke URL me `app` se shuru hone wala hissa hai:

```
https://airtable.com/appXomnU6fddl1b1H/tblfsN7CythOuOirF/viw5gCJRhzinmdPZl
                     ^^^^^^^^^^^^^^^^^  = Cold Email Base
```

Naya base **banwana** ho (maujooda me add karne ki jagah) to workspace ID
chahiye — wo bhi URL me hi dikhta hai jab workspace khula ho:

```
https://airtable.com/wspAbC123XyZ/...
                     ^^^^^^^^^^^^
```

> Repo public hai — token kabhi commit mat karna. Script sirf env se padhta
> hai, kahin likhta nahi. `.gitignore` me `.env` pehle se hai.

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
