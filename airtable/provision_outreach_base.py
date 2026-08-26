#!/usr/bin/env python3
"""
Outreach Command Center  --  Airtable base provisioner
======================================================

KYA KARTA HAI
-------------
Cold-outreach tracking ka poora Airtable base khada karta hai:
7 tables, saare plain fields, aur saare inter-table links
(reciprocal field ka naam bhi theek karke).

KYA NAHI KAR SAKTA (Airtable API ki limitation, script ki nahi)
---------------------------------------------------------------
Airtable Web API in field types ko CREATE nahi karne deta -- ye
sirf UI se banto hain:

    formula, rollup, count, lookup

Aur API me views + automations banane ka koi endpoint hi nahi hai.

Isliye script do kaam karta hai:
  1. Jo API se ban sakta hai wo BANA deta hai (tables + fields + links).
  2. Jo API se nahi banta uske liye exact click-by-click steps
     print kar deta hai  ->  `--manual`

    Dono ka single source of truth isi file me hai (DERIVED / VIEWS /
    AUTOMATIONS), taaki doc aur code kabhi drift na karein.

TOKEN
-----
Airtable Personal Access Token chahiye in scopes ke saath:

    schema.bases:write      (tables + fields banane ke liye)
    schema.bases:read       (idempotent re-run ke liye)

Token env se aata hai -- NEVER hardcode, repo public hai:

    export AIRTABLE_TOKEN=patXXXX.yyyy

WORKSPACE ID
------------
Naya base kisi workspace ke andar hi banta hai. Workspace ID Airtable
ke URL me dikhta hai jab workspace khula ho:

    https://airtable.com/wspAbC123XyZ/...
                         ^^^^^^^^^^^^

    export AIRTABLE_WORKSPACE_ID=wspAbC123XyZ

USAGE
-----
    # 0 network -- schema graph validate karta hai
    python provision_outreach_base.py --self-test

    # 0 network -- kya-kya banega wo print karta hai
    python provision_outreach_base.py --dry-run

    # asli run -- base banata hai
    python provision_outreach_base.py --workspace-id wspXXXX

    # base pehle se hai, sirf missing cheezein add karo (idempotent)
    python provision_outreach_base.py --base-id appXXXX

    # formula / rollup / view / automation ke manual steps
    python provision_outreach_base.py --manual
"""

import os
import sys
import json
import time
import argparse
import logging
from urllib import request as urlrequest
from urllib import error as urlerror

API_ROOT = "https://api.airtable.com/v0"
BASE_NAME = "Outreach Command Center"

# Airtable meta API 5 req/s per base allow karta hai. Thoda margin rakhte hain.
RATE_SLEEP = 0.25
HTTP_TIMEOUT = 30

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# ①  FIELD HELPERS  --  Airtable field-model JSON banane ke shortcuts
# ══════════════════════════════════════════════════════════════════════

def text(name, desc=""):
    return {"name": name, "type": "singleLineText", "description": desc}


def longtext(name, desc=""):
    return {"name": name, "type": "multilineText", "description": desc}


def email(name, desc=""):
    return {"name": name, "type": "email", "description": desc}


def number(name, desc="", precision=0):
    return {"name": name, "type": "number", "description": desc,
            "options": {"precision": precision}}


def checkbox(name, desc=""):
    return {"name": name, "type": "checkbox", "description": desc,
            "options": {"icon": "check", "color": "greenBright"}}


def date(name, desc=""):
    return {"name": name, "type": "date", "description": desc,
            "options": {"dateFormat": {"name": "iso"}}}


def select(name, choices, desc=""):
    return {"name": name, "type": "singleSelect", "description": desc,
            "options": {"choices": [{"name": c} for c in choices]}}


# Ye field types Airtable me PRIMARY field nahi ban sakte.
ILLEGAL_PRIMARY = {
    "multipleRecordLinks", "rollup", "count", "multipleLookupValues",
    "checkbox", "multipleSelects", "multipleAttachments", "button",
    "singleCollaborator", "multipleCollaborators", "createdTime",
    "lastModifiedTime", "createdBy", "lastModifiedBy",
}


# ══════════════════════════════════════════════════════════════════════
# ②  TABLES  --  har table ka pehla field = primary field
# ══════════════════════════════════════════════════════════════════════

TABLES = [
    {
        "name": "Domains",
        "description": "Har sending domain aur uski health.",
        "fields": [
            text("Domain Name", "Primary. e.g. get-yourbrand.com"),
            select("Status", ["Warming", "Active", "Cooling Off", "Blocked"],
                   "Manual status. Health Status formula alag hai (auto)."),
            date("Warmup Start Date"),
            checkbox("SPF Set Up"),
            checkbox("DKIM Set Up"),
            checkbox("DMARC Set Up"),
            longtext("Notes"),
        ],
    },
    {
        "name": "Inboxes",
        "description": "Har domain par chalne wale mailboxes.",
        "fields": [
            email("Inbox Email", "Primary. Poora mailbox address."),
            select("Provider", ["Gmail", "Outlook", "Other"]),
            number("Daily Limit", "Is inbox se ek din me max kitne emails."),
            select("Warmup Stage",
                   ["Week 1", "Week 2", "Week 3", "Week 4", "Full Pace"]),
        ],
    },
    {
        "name": "Content",
        "description": "Har email template / subject line / CTA jo test ho raha hai.",
        "fields": [
            text("Template Name", "Primary. e.g. 'V2 - pain-led - short'"),
            text("Subject Line"),
            longtext("Body Variant"),
            select("CTA Type",
                   ["Ask for time", "Ask a question", "Soft offer", "Other"]),
        ],
    },
    {
        "name": "Contacts",
        "description": "Ek row per contact/deal. Yahi record Kylas se sync hota hai.",
        "fields": [
            text("Contact Name", "Primary."),
            email("Email", "UNIQUE KEY -- Kylas match isi par hota hai. "
                           "Har row me bharna zaroori hai."),
            text("Company"),
            text("Kylas Contact ID", "Kylas ka apna record ID -- re-sync "
                                     "reliable rakhne ke liye."),
            select("Current Stage",
                   ["New", "Touch 1 Sent", "Sequence Active",
                    "CNC-1", "CNC-2", "CNC-3", "Connect Later",
                    "Activation", "MQL", "Meeting Booked", "Meeting Done",
                    "SQL", "Lost"]),
            date("Last Activity Date"),
        ],
    },
    {
        "name": "Sends",
        "description": "Activity log -- ek row per outreach event "
                       "(email / LinkedIn / call).",
        "fields": [
            text("Activity", "Primary. e.g. 'Email 1 - John Doe'."),
            date("Date"),
            select("Channel", ["Email", "LinkedIn", "Call"]),
            checkbox("Delivered"),
            checkbox("Opened"),
            checkbox("Replied"),
            select("Reply Type",
                   ["Positive", "Negative", "Out of Office", "No Reply"]),
            checkbox("Bounced"),
            checkbox("Spam Complaint"),
            select("Call Outcome", ["CNC-1", "CNC-2", "CNC-3", "Connected"],
                   "Sirf Channel = Call ke liye."),
            checkbox("Meeting Booked"),
        ],
    },
    {
        "name": "Intent Signals",
        "description": "Ek row per engagement event. Sends se alag rakha hai "
                       "taaki ek contact ke multiple signals count/score ho sakein.",
        "fields": [
            # NOTE: Airtable primary field LINK nahi ho sakta, isliye
            # 'Signal' text primary hai aur 'Contact' link uske baad aata hai.
            text("Signal", "Primary. e.g. 'Link Clicked - John Doe'."),
            select("Signal Type",
                   ["Email Opened", "Link Clicked", "Replied", "Call Connected",
                    "LinkedIn Reply", "Website Visit", "Meeting Booked"]),
            date("Date"),
            select("Strength", ["Low", "Medium", "High"],
                   "Strength Score formula isko 1/2/3 me badalta hai."),
        ],
    },
    {
        "name": "Daily Snapshot",
        "description": "Ek row per domain per din. Scheduled snapshot hai, "
                       "live rollup nahi -- isliye trend dikhta hai.",
        "fields": [
            # NOTE: 'Date + Domain' ka composite primary Airtable support nahi
            # karta. Snapshot Key dono ko jodta hai -> automation upsert kar
            # sakti hai aur linked-record preview me row pehchani jaati hai.
            text("Snapshot Key", "Primary. Format: 'YYYY-MM-DD :: domain.com'. "
                                 "Automation isi se dedupe karti hai."),
            date("Date"),
            number("Sent Today"),
            number("Opened Today"),
            number("Replied Today"),
            number("Meetings Today"),
            number("Bounced Today"),
            number("Spam Complaints Today"),
        ],
    },
]


# ══════════════════════════════════════════════════════════════════════
# ③  LINKS  --  tables ban jaane ke BAAD add hote hain
# ══════════════════════════════════════════════════════════════════════
#
# Airtable har link field ke saath doosri table me ek RECIPROCAL field
# apne aap bana deta hai. Isliye har rishta yahan SIRF EK BAAR likha hai
# aur `reverse` me uske auto-bane field ka naam diya hai -- script use
# create ke baad rename kar deti hai. Dono taraf se link banayenge to
# Airtable 2 ki jagah 4 fields bana dega.

LINKS = [
    # from_table, field, to_table, reverse (linked table par auto-field ka naam)
    {"from": "Inboxes", "field": "Domain", "to": "Domains",
     "reverse": "Linked Inboxes", "single": True,
     "desc": "Ye inbox kis domain par hai."},

    {"from": "Sends", "field": "Contact", "to": "Contacts",
     "reverse": "Sends", "single": True,
     "desc": "Ye activity kis contact ke liye thi."},

    {"from": "Sends", "field": "Domain", "to": "Domains",
     "reverse": "Sends", "single": True,
     "desc": "Sirf Email channel. Domains ke rollups isi link se chalte hain."},

    {"from": "Sends", "field": "Inbox", "to": "Inboxes",
     "reverse": "Sends", "single": True,
     "desc": "Sirf Email channel."},

    {"from": "Sends", "field": "Content", "to": "Content",
     "reverse": "Sends", "single": True,
     "desc": "Sirf Email channel. Content ke rollups isi link se chalte hain."},

    {"from": "Intent Signals", "field": "Contact", "to": "Contacts",
     "reverse": "Intent Signals", "single": True,
     "desc": "Total Intent Score rollup isi link se chalta hai."},

    {"from": "Intent Signals", "field": "Source Domain", "to": "Domains",
     "reverse": "Intent Signals", "single": True,
     "desc": "Optional -- signal kis domain se aaya."},

    {"from": "Intent Signals", "field": "Source Inbox", "to": "Inboxes",
     "reverse": "Intent Signals", "single": True,
     "desc": "Optional -- signal kis inbox se aaya."},

    {"from": "Daily Snapshot", "field": "Domain", "to": "Domains",
     "reverse": "Daily Snapshots", "single": True,
     "desc": "Ye snapshot row kis domain ki hai."},
]


# ══════════════════════════════════════════════════════════════════════
# ④  DERIVED FIELDS  --  formula / rollup / count  (UI-ONLY)
# ══════════════════════════════════════════════════════════════════════
#
# Airtable API in field types ko create NAHI karne deta. Ye list `--manual`
# ke steps generate karti hai, aur --self-test check karta hai ki har
# formula sirf un fields ko reference kare jo sach me exist karte hain.

DERIVED = [
    # ---- Sends: checkbox/select ko 1/0 me badalne wale helpers -----------
    # Rollup checkbox ko SUM nahi kar sakta, isliye ye helper zaroori hain.
    {"table": "Sends", "name": "Opened Num", "kind": "formula",
     "formula": 'IF({Opened}, 1, 0)',
     "why": "Domains/Content ke Opens Count rollup ke liye."},
    {"table": "Sends", "name": "Replied Num", "kind": "formula",
     "formula": 'IF({Replied}, 1, 0)',
     "why": "Replies Count rollup ke liye."},
    {"table": "Sends", "name": "Bounced Num", "kind": "formula",
     "formula": 'IF({Bounced}, 1, 0)',
     "why": "Bounces Count rollup ke liye."},
    {"table": "Sends", "name": "Spam Num", "kind": "formula",
     "formula": 'IF({Spam Complaint}, 1, 0)',
     "why": "Spam Count rollup ke liye."},
    {"table": "Sends", "name": "Meeting Num", "kind": "formula",
     "formula": 'IF({Meeting Booked}, 1, 0)',
     "why": "Content ke Meeting Rate ke liye."},
    {"table": "Sends", "name": "Positive Reply Num", "kind": "formula",
     "formula": 'IF({Reply Type} = "Positive", 1, 0)',
     "why": "Content ke Positive Reply Rate ke liye."},

    # ---- Intent Signals: single-select ko number me badlo ----------------
    {"table": "Intent Signals", "name": "Strength Score", "kind": "formula",
     "formula": 'IF({Strength} = "High", 3, IF({Strength} = "Medium", 2, '
                'IF({Strength} = "Low", 1, 0)))',
     "why": "Strength ek single-select hai -- SUM nahi ho sakta. Contacts ka "
            "Total Intent Score isi numeric field ko rollup karta hai."},

    # ---- Contacts --------------------------------------------------------
    {"table": "Contacts", "name": "Engaged", "kind": "formula",
     "formatting": "Checkbox ke roop me format karo (Formatting tab).",
     "formula": 'OR({Current Stage}="Connect Later", {Current Stage}="Activation", '
                '{Current Stage}="MQL", {Current Stage}="Meeting Booked", '
                '{Current Stage}="Meeting Done", {Current Stage}="SQL")',
     "why": "TRUE hote hi automated sequence ruk jaani chahiye."},
    {"table": "Contacts", "name": "Total Intent Score", "kind": "rollup",
     "link": "Intent Signals", "target": "Strength Score", "agg": "SUM(values)",
     "why": "Contact ke saare intent signals ka total score."},

    # ---- Domains ---------------------------------------------------------
    {"table": "Domains", "name": "Total Sent", "kind": "count",
     "link": "Sends",
     "why": "Is domain se linked Sends rows ki ginti."},
    {"table": "Domains", "name": "Opens Count", "kind": "rollup",
     "link": "Sends", "target": "Opened Num", "agg": "SUM(values)"},
    {"table": "Domains", "name": "Replies Count", "kind": "rollup",
     "link": "Sends", "target": "Replied Num", "agg": "SUM(values)"},
    {"table": "Domains", "name": "Bounces Count", "kind": "rollup",
     "link": "Sends", "target": "Bounced Num", "agg": "SUM(values)"},
    {"table": "Domains", "name": "Spam Count", "kind": "rollup",
     "link": "Sends", "target": "Spam Num", "agg": "SUM(values)"},
    {"table": "Domains", "name": "Open Rate", "kind": "formula",
     "formatting": "Percent, 1 decimal.",
     "formula": 'IF({Total Sent} = 0, BLANK(), {Opens Count} / {Total Sent})'},
    {"table": "Domains", "name": "Reply Rate", "kind": "formula",
     "formatting": "Percent, 1 decimal.",
     "formula": 'IF({Total Sent} = 0, BLANK(), {Replies Count} / {Total Sent})'},
    {"table": "Domains", "name": "Bounce Rate", "kind": "formula",
     "formatting": "Percent, 1 decimal.",
     "formula": 'IF({Total Sent} = 0, BLANK(), {Bounces Count} / {Total Sent})'},
    {"table": "Domains", "name": "Spam Complaint Rate", "kind": "formula",
     "formatting": "Percent, 2 decimals (0.1% threshold dikhna chahiye).",
     "formula": 'IF({Total Sent} = 0, BLANK(), {Spam Count} / {Total Sent})'},
    {"table": "Domains", "name": "Health Status", "kind": "formula",
     "why": "0-send domains ko 'No Data' milta hai -- warna Open Rate 0 hone "
            "ki wajah se har naya domain jhoota 'At Risk' dikhata.",
     "formula":
        'IF(\n'
        '  {Total Sent} = 0,\n'
        '  "No Data",\n'
        '  IF(\n'
        '    {Spam Complaint Rate} > 0.001,\n'
        '    "Blocked",\n'
        '    IF(\n'
        '      {Bounce Rate} > 0.03,\n'
        '      "At Risk",\n'
        '      IF(\n'
        '        {Open Rate} < 0.2,\n'
        '        "At Risk",\n'
        '        "Healthy"\n'
        '      )\n'
        '    )\n'
        '  )\n'
        ')'},

    # ---- Content ---------------------------------------------------------
    {"table": "Content", "name": "Total Sent", "kind": "count",
     "link": "Sends"},
    {"table": "Content", "name": "Opens Count", "kind": "rollup",
     "link": "Sends", "target": "Opened Num", "agg": "SUM(values)"},
    {"table": "Content", "name": "Replies Count", "kind": "rollup",
     "link": "Sends", "target": "Replied Num", "agg": "SUM(values)"},
    {"table": "Content", "name": "Positive Replies Count", "kind": "rollup",
     "link": "Sends", "target": "Positive Reply Num", "agg": "SUM(values)"},
    {"table": "Content", "name": "Meetings Count", "kind": "rollup",
     "link": "Sends", "target": "Meeting Num", "agg": "SUM(values)"},
    {"table": "Content", "name": "Open Rate", "kind": "formula",
     "formatting": "Percent, 1 decimal.",
     "formula": 'IF({Total Sent} = 0, BLANK(), {Opens Count} / {Total Sent})'},
    {"table": "Content", "name": "Reply Rate", "kind": "formula",
     "formatting": "Percent, 1 decimal.",
     "formula": 'IF({Total Sent} = 0, BLANK(), {Replies Count} / {Total Sent})'},
    {"table": "Content", "name": "Positive Reply Rate", "kind": "formula",
     "formatting": "Percent, 1 decimal.",
     "formula": 'IF({Total Sent} = 0, BLANK(), '
                '{Positive Replies Count} / {Total Sent})'},
    {"table": "Content", "name": "Meeting Rate", "kind": "formula",
     "formatting": "Percent, 1 decimal.",
     "formula": 'IF({Total Sent} = 0, BLANK(), {Meetings Count} / {Total Sent})'},
]


# ══════════════════════════════════════════════════════════════════════
# ⑤  VIEWS  --  UI-ONLY (API me view banane ka endpoint hi nahi hai)
# ══════════════════════════════════════════════════════════════════════

VIEWS = [
    {"table": "Sends", "name": "By Domain", "type": "Grid",
     "setup": "Group by -> Domain"},
    {"table": "Sends", "name": "By Content", "type": "Grid",
     "setup": "Group by -> Content"},
    {"table": "Sends", "name": "Positive Replies", "type": "Grid",
     "setup": 'Filter -> Reply Type  is  Positive'},
    {"table": "Sends", "name": "Meetings Booked", "type": "Grid",
     "setup": 'Filter -> Meeting Booked  is  checked'},
    {"table": "Contacts", "name": "By Stage", "type": "Grid",
     "setup": "Group by -> Current Stage"},
    {"table": "Contacts", "name": "Hot / Engaged", "type": "Grid",
     "setup": 'Filter -> Engaged  is  checked',
     "note": "Engaged ek formula field hai -- filter me 'is checked' tabhi "
             "dikhega jab usko Checkbox formatting di gayi ho."},
    {"table": "Domains", "name": "By Status", "type": "Grid",
     "setup": "Group by -> Status"},

    # Ye 7 requested views ke alawa hai -- Daily Snapshot automation isko
    # padhti hai. Iske bina script poori Sends table scan karti hai.
    {"table": "Sends", "name": "Today (automation source)", "type": "Grid",
     "setup": 'Filter -> Date  is  today',
     "note": "AUTOMATION HELPER. daily_snapshot.js isi view ko padhta hai "
             "taaki poori Sends table scan na karni pade. Naam exactly yahi "
             "rakhna -- script isko naam se dhoondhta hai."},
]


# ══════════════════════════════════════════════════════════════════════
# ⑥  AUTOMATIONS  --  UI-ONLY
# ══════════════════════════════════════════════════════════════════════

AUTOMATIONS = [
    {"name": "Daily Snapshot",
     "trigger": "At scheduled time -> Daily -> 11:59 PM (apna timezone set karo)",
     "action": "Run a script  ->  automations/daily_snapshot.js",
     "note": "Script ko Sends + Domains + Daily Snapshot teeno tables ka "
             "access dena padta hai (script editor khud maang leta hai)."},
    {"name": "Sequence Stop",
     "trigger": "When record matches conditions -> Contacts -> Engaged is checked",
     "action": "Run a script  ->  automations/sequence_stop.js",
     "note": "EXTERNAL DEPENDENCY -- Airtable khud kisi sequencer ko rok nahi "
             "sakta. Script ek webhook maarti hai; URL apne sequencer ka "
             "(Make.com / n8n / Zapier / Instantly / Smartlead) daalna padega."},
]


# ══════════════════════════════════════════════════════════════════════
# ⑦  SELF-TEST  --  0 network. Schema graph sahi hai ya nahi.
# ══════════════════════════════════════════════════════════════════════

def self_test() -> int:
    """Schema ki internal consistency check karta hai. Returns error count."""
    errors, warns = [], []
    tbl_by_name = {t["name"]: t for t in TABLES}

    # -- tables ------------------------------------------------------------
    if len(tbl_by_name) != len(TABLES):
        errors.append("Duplicate table names TABLES me.")

    for t in TABLES:
        if not t["fields"]:
            errors.append(f"[{t['name']}] ka koi field hi nahi.")
            continue
        primary = t["fields"][0]
        if primary["type"] in ILLEGAL_PRIMARY:
            errors.append(
                f"[{t['name']}] ka primary field '{primary['name']}' type "
                f"'{primary['type']}' hai -- Airtable isko primary nahi banne deta.")
        names = [f["name"] for f in t["fields"]]
        for n in set(names):
            if names.count(n) > 1:
                errors.append(f"[{t['name']}] me duplicate field '{n}'.")
        for f in t["fields"]:
            if f["type"] == "singleSelect":
                ch = [c["name"] for c in f["options"]["choices"]]
                if not ch:
                    errors.append(f"[{t['name']}.{f['name']}] select bina choices ke.")
                if len(set(ch)) != len(ch):
                    errors.append(f"[{t['name']}.{f['name']}] me duplicate choices.")

    # -- links -------------------------------------------------------------
    # Har link do naye field naam paida karta hai: source par `field`,
    # target par `reverse`. Dono ko table ke existing fields se takraana
    # nahi chahiye.
    projected = {t["name"]: {f["name"] for f in t["fields"]} for t in TABLES}
    for lk in LINKS:
        for side in ("from", "to"):
            if lk[side] not in tbl_by_name:
                errors.append(f"Link '{lk['field']}' ka {side}-table "
                              f"'{lk[side]}' TABLES me hai hi nahi.")
        if lk["from"] not in projected or lk["to"] not in projected:
            continue
        if lk["field"] in projected[lk["from"]]:
            errors.append(f"[{lk['from']}] me '{lk['field']}' pehle se hai -- "
                          f"link field clash karega.")
        projected[lk["from"]].add(lk["field"])
        if lk["reverse"] in projected[lk["to"]]:
            errors.append(f"[{lk['to']}] me '{lk['reverse']}' pehle se hai -- "
                          f"reciprocal field clash karega.")
        projected[lk["to"]].add(lk["reverse"])

    # -- derived fields ----------------------------------------------------
    # Formula sirf un fields ko reference kare jo tab tak exist karte hon.
    for d in DERIVED:
        if d["table"] not in projected:
            errors.append(f"Derived '{d['name']}' ki table '{d['table']}' nahi mili.")
            continue
        if d["name"] in projected[d["table"]]:
            errors.append(f"[{d['table']}] me derived '{d['name']}' "
                          f"pehle se maujood field se clash karta hai.")
        projected[d["table"]].add(d["name"])

    derived_names = {(d["table"], d["name"]) for d in DERIVED}
    for d in DERIVED:
        if d["kind"] == "formula":
            for ref in _refs(d["formula"]):
                if ref not in projected[d["table"]]:
                    errors.append(f"[{d['table']}.{d['name']}] formula me "
                                  f"'{{{ref}}}' hai jo table me exist nahi karta.")
        else:
            # rollup / count -- link field target table tak jaata ho
            if d["link"] not in projected[d["table"]]:
                errors.append(f"[{d['table']}.{d['name']}] link field "
                              f"'{d['link']}' nahi mila.")
            if d["kind"] == "rollup":
                tgt_tbl = _link_target(d["table"], d["link"])
                if tgt_tbl is None:
                    errors.append(f"[{d['table']}.{d['name']}] ka link "
                                  f"'{d['link']}' kisi table ko point nahi karta.")
                elif d["target"] not in projected.get(tgt_tbl, set()):
                    errors.append(f"[{d['table']}.{d['name']}] rollup target "
                                  f"'{d['target']}' {tgt_tbl} me nahi hai.")
                elif (tgt_tbl, d["target"]) in derived_names:
                    # rollup ek formula field ko point kar raha hai -- legal
                    # hai, par order matter karta hai. Warn kar dete hain.
                    warns.append(f"[{d['table']}.{d['name']}] rollup "
                                 f"'{tgt_tbl}.{d['target']}' par depend karta "
                                 f"hai -- usko pehle banao.")

    # -- views --------------------------------------------------------------
    for v in VIEWS:
        if v["table"] not in projected:
            errors.append(f"View '{v['name']}' ki table '{v['table']}' nahi mili.")

    # -- verify ka round-trip ----------------------------------------------
    # Declared schema se nakli "live" banao -> _diff_schema ko us par chalao
    # -> structural gap ZERO aana chahiye. Isse verify ki logic 0 network me
    # test ho jaati hai.
    rt = _diff_schema(_synthetic_live())
    rt_structural = (rt["missing_tables"] + rt["missing_fields"]
                     + rt["wrong_types"] + rt["missing_links"]
                     + rt["wrong_links"] + rt["extra_fields"])
    for x in rt_structural:
        errors.append(f"verify round-trip: apne hi schema par gap mila -- {x}")
    if len(rt["todo_derived"]) != len(DERIVED):
        errors.append(f"verify round-trip: {len(DERIVED)} derived expected the, "
                      f"{len(rt['todo_derived'])} pending mile.")

    # -- report -------------------------------------------------------------
    n_fields = sum(len(t["fields"]) for t in TABLES)
    log.info("\n" + "=" * 66)
    log.info("SELF-TEST  --  Outreach Command Center schema")
    log.info("=" * 66)
    log.info(f"  tables            : {len(TABLES)}")
    log.info(f"  plain fields      : {n_fields}   (API bana degi)")
    log.info(f"  link fields       : {len(LINKS)} x2 = {len(LINKS) * 2}   (API bana degi)")
    log.info(f"  derived fields    : {len(DERIVED)}   (UI-only)")
    log.info(f"  views             : {len(VIEWS)}   (UI-only)")
    log.info(f"  automations       : {len(AUTOMATIONS)}   (UI-only)")

    for w in warns:
        log.info(f"  NOTE  {w}")
    if errors:
        log.info("")
        for e in errors:
            log.info(f"  FAIL  {e}")
        log.info(f"\n  {len(errors)} error(s).")
    else:
        log.info("\n  OK -- schema graph consistent hai.")
    log.info("=" * 66 + "\n")
    return len(errors)


def _refs(formula: str):
    """Formula string se {Field Name} refs nikaalta hai."""
    out, i = [], 0
    while True:
        a = formula.find("{", i)
        if a == -1:
            return out
        b = formula.find("}", a)
        if b == -1:
            return out
        out.append(formula[a + 1:b])
        i = b + 1


def _link_target(table: str, field: str):
    """`table.field` link kis table ko point karta hai."""
    for lk in LINKS:
        if lk["from"] == table and lk["field"] == field:
            return lk["to"]
        if lk["to"] == table and lk["reverse"] == field:
            return lk["from"]
    return None


# ══════════════════════════════════════════════════════════════════════
# ⑧  AIRTABLE API CLIENT
# ══════════════════════════════════════════════════════════════════════

class AirtableError(RuntimeError):
    pass


class Meta:
    """Airtable meta API ka patla wrapper (sirf stdlib)."""

    def __init__(self, token: str):
        self.token = token

    def _call(self, method: str, url: str, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urlrequest.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        if data:
            req.add_header("Content-Type", "application/json")
        try:
            with urlrequest.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                time.sleep(RATE_SLEEP)
                return json.loads(r.read().decode() or "{}")
        except urlerror.HTTPError as e:
            detail = e.read().decode(errors="replace")[:600]
            raise AirtableError(f"{method} {url} -> HTTP {e.code}\n  {detail}")
        except urlerror.URLError as e:
            raise AirtableError(
                f"{method} {url} -> network error: {e.reason}\n"
                f"  (api.airtable.com tak pahunch nahi ban rahi -- "
                f"proxy/firewall check karo)")

    def whoami(self):
        return self._call("GET", f"{API_ROOT}/meta/whoami")

    def bases(self):
        out, offset = [], None
        while True:
            url = f"{API_ROOT}/meta/bases"
            if offset:
                url += f"?offset={offset}"
            page = self._call("GET", url)
            out.extend(page.get("bases", []))
            offset = page.get("offset")
            if not offset:
                return out

    def create_base(self, name, workspace_id, tables):
        return self._call("POST", f"{API_ROOT}/meta/bases", {
            "name": name, "workspaceId": workspace_id, "tables": tables})

    def tables(self, base_id):
        return self._call(
            "GET", f"{API_ROOT}/meta/bases/{base_id}/tables").get("tables", [])

    def create_table(self, base_id, table):
        return self._call(
            "POST", f"{API_ROOT}/meta/bases/{base_id}/tables", table)

    def create_field(self, base_id, table_id, field):
        return self._call(
            "POST", f"{API_ROOT}/meta/bases/{base_id}/tables/{table_id}/fields",
            field)

    def rename_field(self, base_id, table_id, field_id, new_name):
        return self._call(
            "PATCH",
            f"{API_ROOT}/meta/bases/{base_id}/tables/{table_id}/fields/{field_id}",
            {"name": new_name})


# ══════════════════════════════════════════════════════════════════════
# ⑨  PROVISION
# ══════════════════════════════════════════════════════════════════════

def provision(api: Meta, workspace_id: str, base_id: str,
              base_name: str = BASE_NAME, assume_yes: bool = False) -> str:
    """Base + tables + links ensure karta hai. Idempotent hai."""

    # ---- base -------------------------------------------------------------
    if base_id:
        log.info(f"\n[base] maujooda base use kar rahe hain: {base_id}")
        live = api.tables(base_id)
        _confirm_existing(live, assume_yes)
    else:
        existing = [b for b in api.bases() if b.get("name") == base_name]
        if existing:
            base_id = existing[0]["id"]
            log.info(f"\n[base] '{base_name}' pehle se hai -> {base_id}")
            log.info("       (naya nahi banega; missing cheezein add hongi)")
            live = api.tables(base_id)
            _confirm_existing(live, assume_yes)
        else:
            log.info(f"\n[base] '{base_name}' bana rahe hain "
                     f"(workspace {workspace_id})...")
            payload = [{"name": t["name"], "description": t["description"],
                        "fields": _strip(t["fields"])} for t in TABLES]
            res = api.create_base(base_name, workspace_id, payload)
            base_id = res["id"]
            log.info(f"       OK -> {base_id}  ({len(TABLES)} tables)")
            live = api.tables(base_id)

    ids = {t["name"]: t["id"] for t in live}

    # ---- missing tables / fields (sirf re-run par relevant) ---------------
    for t in TABLES:
        if t["name"] not in ids:
            log.info(f"[table] '{t['name']}' missing tha -> bana rahe hain")
            res = api.create_table(base_id, {
                "name": t["name"], "description": t["description"],
                "fields": _strip(t["fields"])})
            ids[t["name"]] = res["id"]
            continue
        have = {f["name"] for f in _fields_of(live, t["name"])}
        for f in t["fields"][1:]:          # primary already exists
            if f["name"] not in have:
                log.info(f"[field] {t['name']}.{f['name']} -> add")
                api.create_field(base_id, ids[t["name"]], _strip([f])[0])

    # ---- links ------------------------------------------------------------
    live = api.tables(base_id)
    for lk in LINKS:
        src_id, dst_id = ids[lk["from"]], ids[lk["to"]]
        if any(f["name"] == lk["field"] for f in _fields_of(live, lk["from"])):
            log.info(f"[link]  {lk['from']}.{lk['field']} -> pehle se hai, skip")
            continue

        before = {f["id"] for f in _fields_of(live, lk["to"])}
        opts = {"linkedTableId": dst_id}
        if lk.get("single"):
            opts["prefersSingleRecordLink"] = True

        body = {"name": lk["field"], "type": "multipleRecordLinks",
                "description": lk["desc"], "options": opts}
        try:
            api.create_field(base_id, src_id, body)
        except AirtableError as e:
            # prefersSingleRecordLink kuch plans/versions par reject ho sakta
            # hai -- bina uske dobara try karo.
            if "prefersSingleRecordLink" not in str(e):
                raise
            log.info(f"[link]  {lk['from']}.{lk['field']} -> "
                     f"prefersSingleRecordLink reject hua, bina uske retry")
            body["options"] = {"linkedTableId": dst_id}
            api.create_field(base_id, src_id, body)

        log.info(f"[link]  {lk['from']}.{lk['field']}  ->  {lk['to']}")

        # Airtable ne target table me reciprocal field bana diya hoga.
        # Usko dhoondh ke user-facing naam do.
        live = api.tables(base_id)
        new = [f for f in _fields_of(live, lk["to"]) if f["id"] not in before]
        if len(new) == 1:
            api.rename_field(base_id, dst_id, new[0]["id"], lk["reverse"])
            log.info(f"        reciprocal '{new[0]['name']}' -> "
                     f"'{lk['reverse']}' (on {lk['to']})")
            live = api.tables(base_id)
        elif not new:
            log.info(f"        WARN reciprocal field nahi mila on {lk['to']} -- "
                     f"haath se '{lk['reverse']}' rename kar dena")
        else:
            log.info(f"        WARN {lk['to']} par {len(new)} naye fields mile, "
                     f"rename skip kiya -- manually check karo")

    return base_id


# ══════════════════════════════════════════════════════════════════════
# ⑨b  VERIFY  --  live base vs repo schema
# ══════════════════════════════════════════════════════════════════════
#
# Isse GitHub sach me source of truth banta hai: live base repo se alag
# ho to pata chal jaata hai. Comparison PURE function hai (_diff_schema),
# isliye --self-test use 0 network me check kar leta hai.

def _diff_schema(live):
    """Live schema ko declared schema se compare karta hai.

    Returns dict of lists. `missing_*` = structural, script bana sakti hai.
    `todo_derived` = UI-only, haath se banane hain -- ye FAILURE nahi hai.
    """
    by_name = {t["name"]: t for t in live}
    ids_to_name = {t["id"]: t["name"] for t in live}
    out = {"missing_tables": [], "missing_fields": [], "wrong_types": [],
           "missing_links": [], "wrong_links": [], "todo_derived": [],
           "extra_fields": []}

    declared = {}      # table -> {field name: expected type}
    for t in TABLES:
        declared.setdefault(t["name"], {})
        for f in t["fields"]:
            declared[t["name"]][f["name"]] = f["type"]
    for lk in LINKS:
        declared.setdefault(lk["from"], {})[lk["field"]] = "multipleRecordLinks"
        declared.setdefault(lk["to"], {})[lk["reverse"]] = "multipleRecordLinks"

    for t in TABLES:
        if t["name"] not in by_name:
            out["missing_tables"].append(t["name"])
            continue
        have = {f["name"]: f for f in by_name[t["name"]].get("fields", [])}

        for f in t["fields"]:
            got = have.get(f["name"])
            if got is None:
                out["missing_fields"].append(f"{t['name']}.{f['name']}")
            elif got.get("type") != f["type"]:
                out["wrong_types"].append(
                    f"{t['name']}.{f['name']}: chahiye {f['type']}, "
                    f"mila {got.get('type')}")

        # repo me declare nahi kiya gaya field -- sirf info, error nahi
        for name in have:
            if name not in declared.get(t["name"], {}):
                out["extra_fields"].append(f"{t['name']}.{name}")

    # links -- naam bhi aur target table bhi
    for lk in LINKS:
        for tbl, fld, target in ((lk["from"], lk["field"], lk["to"]),
                                 (lk["to"], lk["reverse"], lk["from"])):
            if tbl not in by_name:
                continue
            got = next((f for f in by_name[tbl].get("fields", [])
                        if f["name"] == fld), None)
            if got is None:
                out["missing_links"].append(f"{tbl}.{fld} -> {target}")
            elif got.get("type") != "multipleRecordLinks":
                out["wrong_links"].append(
                    f"{tbl}.{fld}: link hona chahiye, hai {got.get('type')}")
            else:
                points_to = ids_to_name.get(
                    (got.get("options") or {}).get("linkedTableId"))
                # `target in by_name` guard: agar target table hi missing hai
                # to wo alag se report ho chuka hai, dobara shor mat machao.
                # Warna mismatch flag karo -- points_to None ho (anjaan table
                # id) tab bhi, kyunki wo bhi galat hi hai.
                if target in by_name and points_to != target:
                    out["wrong_links"].append(
                        f"{tbl}.{fld}: {target} ko point karna chahiye, "
                        f"kar raha hai {points_to or 'anjaan table'}")

    # derived (UI-only) -- kitne ban chuke, kitne baaki
    for d in DERIVED:
        if d["table"] not in by_name:
            out["todo_derived"].append(f"{d['table']}.{d['name']} [{d['kind']}]")
            continue
        got = next((f for f in by_name[d["table"]].get("fields", [])
                    if f["name"] == d["name"]), None)
        if got is None:
            out["todo_derived"].append(f"{d['table']}.{d['name']} [{d['kind']}]")

    return out


def verify(api: Meta, base_id: str) -> int:
    """Live base ko repo schema se compare karke report deta hai.

    Exit code: structural cheez missing ho to 1, warna 0. UI-only derived
    fields pending hon to bhi 0 -- wo expected hai jab tak haath se na bano.
    """
    live = api.tables(base_id)
    d = _diff_schema(live)

    log.info("\n" + "=" * 66)
    log.info(f"VERIFY  --  base {base_id}  vs  repo schema")
    log.info("=" * 66)
    log.info(f"  live base me {len(live)} table(s) mile.\n")

    structural = (d["missing_tables"] + d["missing_fields"] + d["wrong_types"]
                  + d["missing_links"] + d["wrong_links"])

    def dump(title, items, marker):
        if items:
            log.info(f"  {title}  ({len(items)})")
            for x in items:
                log.info(f"      {marker} {x}")
            log.info("")

    dump("MISSING TABLES", d["missing_tables"], "-")
    dump("MISSING FIELDS", d["missing_fields"], "-")
    dump("GALAT TYPE", d["wrong_types"], "!")
    dump("MISSING LINKS", d["missing_links"], "-")
    dump("GALAT LINK TARGET", d["wrong_links"], "!")

    if d["todo_derived"]:
        log.info(f"  UI SE BANANE BAAKI  ({len(d['todo_derived'])} of "
                 f"{len(DERIVED)})   <- ye error nahi hai")
        for x in d["todo_derived"]:
            log.info(f"      . {x}")
        log.info("      steps:  --manual\n")
    else:
        log.info(f"  Saare {len(DERIVED)} derived fields ban chuke hain.\n")

    if d["extra_fields"]:
        log.info(f"  REPO ME NAHI HAIN  ({len(d['extra_fields'])})   "
                 f"<- tumhare apne fields, chhue nahi jaayenge")
        for x in d["extra_fields"][:20]:
            log.info(f"      + {x}")
        if len(d["extra_fields"]) > 20:
            log.info(f"      ... aur {len(d['extra_fields']) - 20}")
        log.info("")

    if structural:
        log.info(f"  {len(structural)} structural gap(s). Theek karne ke liye "
                 f"bina --dry-run ke chalao.")
    else:
        log.info("  OK -- structure repo se match karta hai.")
    log.info("=" * 66 + "\n")
    return 1 if structural else 0


def _synthetic_live():
    """TABLES+LINKS se nakli live schema. --self-test isse _diff_schema ka
    round-trip check karta hai, bina network ke."""
    tbl_id = {t["name"]: f"tbl{i}" for i, t in enumerate(TABLES)}
    out = []
    for t in TABLES:
        fields = [{"id": f"fld{t['name']}{i}", "name": f["name"],
                   "type": f["type"]} for i, f in enumerate(t["fields"])]
        for lk in LINKS:
            if lk["from"] == t["name"]:
                fields.append({"id": f"lnk{lk['from']}{lk['field']}",
                               "name": lk["field"], "type": "multipleRecordLinks",
                               "options": {"linkedTableId": tbl_id[lk["to"]]}})
            if lk["to"] == t["name"]:
                fields.append({"id": f"rev{lk['to']}{lk['reverse']}",
                               "name": lk["reverse"], "type": "multipleRecordLinks",
                               "options": {"linkedTableId": tbl_id[lk["from"]]}})
        out.append({"id": tbl_id[t["name"]], "name": t["name"], "fields": fields})
    return out


def _confirm_existing(live, assume_yes: bool):
    """Maujooda base me likhne se pehle dikha do ki andar kya hai.

    Sabse badi risk: base me pehle se koi table hamare 7 me se kisi ke naam
    ka ho. Tab script us table me apne fields ADD kar degi -- delete kuch
    nahi karti, par user ki maujooda table badal jaayegi. Isliye poochte hain.
    """
    if not live:
        log.info("       base khaali hai -- saare 7 tables banenge.")
        return

    ours = {t["name"] for t in TABLES}
    clashes = [t["name"] for t in live if t["name"] in ours]
    others = [t["name"] for t in live if t["name"] not in ours]

    log.info(f"\n       base me pehle se {len(live)} table(s) hain:")
    for name in others:
        log.info(f"         - {name}   (chhua nahi jaayega)")
    for name in clashes:
        log.info(f"         - {name}   <-- NAAM MATCH KARTA HAI, isme fields "
                 f"ADD honge")

    log.info(f"\n       {len(ours) - len(clashes)} naye table banenge, "
             f"{len(clashes)} maujooda me fields add honge.")
    log.info("       Script kuch DELETE nahi karti -- sirf add/rename karti hai.")

    if assume_yes:
        log.info("       --yes diya hai, aage badh rahe hain.\n")
        return
    if not sys.stdin.isatty():
        log.info("\nFAIL -- non-interactive shell hai. Confirm nahi kar sakte.\n"
                 "  Sab theek lage to --yes lagake dobara chalao.\n")
        sys.exit(1)

    ans = input("       Aage badhein? [y/N] ").strip().lower()
    if ans not in ("y", "yes"):
        log.info("       Abort. Kuch nahi badla.\n")
        sys.exit(0)
    log.info("")


def _strip(fields):
    """description khaali ho to hata do -- API usko accept karta hai par
    khaali string se field ka description blank-but-set ho jaata hai."""
    out = []
    for f in fields:
        g = dict(f)
        if not g.get("description"):
            g.pop("description", None)
        out.append(g)
    return out


def _fields_of(live, table_name):
    for t in live:
        if t["name"] == table_name:
            return t.get("fields", [])
    return []


# ══════════════════════════════════════════════════════════════════════
# ⑩  PRINTERS
# ══════════════════════════════════════════════════════════════════════

def print_plan():
    log.info("\n" + "=" * 66)
    log.info(f"PLAN  --  base '{BASE_NAME}'")
    log.info("=" * 66)
    for t in TABLES:
        log.info(f"\n  {t['name']}")
        for i, f in enumerate(t["fields"]):
            tag = "  [PRIMARY]" if i == 0 else ""
            log.info(f"      {f['name']:<26} {f['type']}{tag}")
        for lk in LINKS:
            if lk["from"] == t["name"]:
                log.info(f"      {lk['field']:<26} link -> {lk['to']}")
            if lk["to"] == t["name"]:
                log.info(f"      {lk['reverse']:<26} link -> {lk['from']}  "
                         f"(auto-reciprocal)")
        d = [x for x in DERIVED if x["table"] == t["name"]]
        for x in d:
            log.info(f"      {x['name']:<26} {x['kind']}  << UI-only")
    log.info("\n" + "=" * 66)
    log.info("UI-only kaam ke liye:  python provision_outreach_base.py --manual")
    log.info("=" * 66 + "\n")


def print_manual():
    log.info("\n" + "=" * 70)
    log.info("MANUAL STEPS  --  jo Airtable API se nahi ban sakta")
    log.info("=" * 70)
    log.info("\nAirtable API formula / rollup / count / lookup fields create")
    log.info("nahi karne deta, aur views + automations ka to koi endpoint hi")
    log.info("nahi hai. Neeche sab kuch hai -- order maayne rakhta hai.\n")

    log.info("-" * 70)
    log.info("STEP 1  --  DERIVED FIELDS  (isi order me banao)")
    log.info("-" * 70)
    cur = None
    for i, d in enumerate(DERIVED, 1):
        if d["table"] != cur:
            cur = d["table"]
            log.info(f"\n  ==== {cur} ====")
        log.info(f"\n  {i}. {d['name']}   [{d['kind']}]")
        if d["kind"] == "formula":
            for ln in d["formula"].split("\n"):
                log.info(f"        {ln}")
        elif d["kind"] == "rollup":
            log.info(f"        Link field  : {d['link']}")
            log.info(f"        Roll up     : {d['target']}")
            log.info(f"        Aggregation : {d['agg']}")
        elif d["kind"] == "count":
            log.info(f"        Count field on link: {d['link']}")
        if d.get("formatting"):
            log.info(f"        Format      : {d['formatting']}")
        if d.get("why"):
            log.info(f"        Kyun        : {d['why']}")

    log.info("\n" + "-" * 70)
    log.info("STEP 2  --  VIEWS")
    log.info("-" * 70)
    # Table ke hisaab se group karo -- VIEWS list ka order chahe jo ho,
    # ek table ka heading do baar na chhape.
    for tname in dict.fromkeys(v["table"] for v in VIEWS):
        log.info(f"\n  ==== {tname} ====")
        for v in (x for x in VIEWS if x["table"] == tname):
            log.info(f"    - '{v['name']}' ({v['type']}) :  {v['setup']}")
            if v.get("note"):
                log.info(f"        NOTE: {v['note']}")

    log.info("\n" + "-" * 70)
    log.info("STEP 3  --  AUTOMATIONS")
    log.info("-" * 70)
    for a in AUTOMATIONS:
        log.info(f"\n  '{a['name']}'")
        log.info(f"    Trigger : {a['trigger']}")
        log.info(f"    Action  : {a['action']}")
        log.info(f"    NOTE    : {a['note']}")
    log.info("\n" + "=" * 70 + "\n")


# ══════════════════════════════════════════════════════════════════════
# ⑪  MAIN
# ══════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(
        description="Outreach Command Center -- Airtable base provisioner")
    ap.add_argument("--self-test", action="store_true",
                    help="0 network. Schema graph validate karo.")
    ap.add_argument("--dry-run", action="store_true",
                    help="0 network. Kya-kya banega wo print karo.")
    ap.add_argument("--manual", action="store_true",
                    help="0 network. Formula/rollup/view/automation ke steps.")
    ap.add_argument("--verify", action="store_true",
                    help="Live base ko repo schema se compare karo "
                         "(kuch likhta nahi). --base-id chahiye.")
    ap.add_argument("--workspace-id", default=os.environ.get("AIRTABLE_WORKSPACE_ID"),
                    help="wspXXXX -- naya base banane ke liye zaroori.")
    ap.add_argument("--base-id", default=os.environ.get("AIRTABLE_BASE_ID"),
                    help="appXXXX -- maujooda base me add karna ho to.")
    ap.add_argument("--base-name",
                    default=os.environ.get("AIRTABLE_BASE_NAME", BASE_NAME),
                    help=f"Naya base banate waqt ka naam (default: {BASE_NAME}). "
                         f"--base-id ke saath ignore ho jaata hai.")
    ap.add_argument("--yes", "-y", action="store_true",
                    help="Maujooda base me likhne se pehle confirm mat poocho.")
    args = ap.parse_args()

    if args.self_test:
        sys.exit(1 if self_test() else 0)
    if args.dry_run:
        if self_test():
            sys.exit(1)
        print_plan()
        sys.exit(0)
    if args.manual:
        print_manual()
        sys.exit(0)

    # asli run -- pehle schema khud sahi hona chahiye
    if self_test():
        log.info("Schema me error hai -- provision abort.")
        sys.exit(1)

    token = os.environ.get("AIRTABLE_TOKEN", "").strip()
    if not token:
        log.info("\nFAIL -- AIRTABLE_TOKEN set nahi hai.\n"
                 "  export AIRTABLE_TOKEN=patXXXX.yyyy\n"
                 "  Scopes chahiye: schema.bases:write, schema.bases:read\n")
        sys.exit(1)
    if args.verify:
        if not args.base_id:
            log.info("\nFAIL -- --verify ke liye --base-id chahiye "
                     "(ya AIRTABLE_BASE_ID env).\n")
            sys.exit(1)
        try:
            sys.exit(verify(Meta(token), args.base_id))
        except AirtableError as e:
            log.info(f"\nFAIL -- {e}\n")
            sys.exit(1)

    if not args.base_id and not args.workspace_id:
        log.info("\nFAIL -- naya base banane ke liye --workspace-id chahiye.\n"
                 "  Airtable me workspace kholo, URL me wspXXXX dikhega.\n"
                 "  Ya phir maujooda base me add karna ho to --base-id do.\n")
        sys.exit(1)

    api = Meta(token)
    try:
        who = api.whoami()
        log.info(f"[auth] OK -- {who.get('id', '?')}")

        # Galat scopes wala token sabse common failure hai. Aadha base bana
        # ke beech me marne se accha hai abhi bata dein.
        scopes = set(who.get("scopes") or [])
        missing = {"schema.bases:write", "schema.bases:read"} - scopes
        if scopes and missing:
            log.info(f"\nFAIL -- token me ye scope(s) nahi hain: "
                     f"{', '.join(sorted(missing))}\n"
                     f"  Airtable -> Developer hub -> Personal access tokens "
                     f"me add karke dobara chalao.\n")
            sys.exit(1)

        base_id = provision(api, args.workspace_id, args.base_id,
                            args.base_name, args.yes)
    except AirtableError as e:
        log.info(f"\nFAIL -- {e}\n")
        sys.exit(1)

    log.info("\n" + "=" * 66)
    log.info(f"DONE -- tables + fields + links ready.  base: {base_id}")
    log.info("=" * 66)
    log.info("\nAb UI wala hissa baaki hai (API se nahi ban sakta):")
    log.info("    python provision_outreach_base.py --manual\n")


if __name__ == "__main__":
    main()
