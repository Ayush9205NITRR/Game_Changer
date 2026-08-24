"""
Account Health Audit  --  Airtable CSV post-mortem
==================================================

KYA KARTA HAI
-------------
"Company List" view ka CSV export leke batata hai:

  1. Kitne accounts ki Account Status/Health khaali hai (stale backlog).
  2. Har column ka FILL RATE -- jo columns poore ke poore khaali ya
     all-zero hain wo turant dikh jaate hain.
  3. STALE rows ke liye: unke at_* inputs maujood hain ya nahi?
       -> inputs hain     = seedha recompute karke backfill ho jaayega
       -> inputs nahi hain = pehle re-enrichment chahiye
     (Yahi wo sawaal hai jiska jawab "pata nahi" tha.)
  4. POPULATED rows se RULE REVERSE-ENGINEER karta hai -- jin rows me
     status already bhari hai, unke at_* values dekh ke batata hai ki
     kaunsa input kis status se map hota hai. Isse backfill ka formula
     mil jaata hai bina automation ke andar jhaanke.

ZERO network, ZERO credits. Sirf local CSV padhta hai.

USAGE
-----
    # Airtable me view kholo -> ... -> Download CSV
    python account_health_audit.py --csv "Company List-Revenue View.csv"

    # agar status column ka naam alag hai
    python account_health_audit.py --csv f.csv --status-col "Account Health"

    # stale rows ke examples bhi dekhne hain
    python account_health_audit.py --csv f.csv --samples 10
"""

import csv
import sys
import argparse
from collections import Counter, defaultdict

csv.field_size_limit(10_000_000)

# Status column ke liye ye naam try kiye jaate hain (case-insensitive)
STATUS_CANDIDATES = ["account status", "account health", "account_health",
                     "account health status", "health", "status"]

# Feature columns ka default prefix
FEATURE_PREFIX = "at_"

BLANK = ("", None, "null", "none", "n/a", "-")


def is_blank(v) -> bool:
    return str(v).strip().lower() in BLANK if v is not None else True


def as_num(v):
    """Numeric value ya None. '1,234' aur '12.5' dono handle karta hai."""
    if is_blank(v):
        return None
    try:
        return float(str(v).replace(",", "").replace("₹", "").replace("$", "").strip())
    except ValueError:
        return None


def has_value(v) -> bool:
    """Feature present hai? Categorical ke liye non-blank kaafi;
    numeric ke liye 0 ko 'never populated' maana jaata hai."""
    if is_blank(v):
        return False
    num = as_num(v)
    return True if num is None else num != 0


def pct(n, d) -> str:
    return f"{(100.0 * n / d):5.1f}%" if d else "  n/a"


def bar(n, d, width=32) -> str:
    return "#" * (int(width * n / d) if d else 0)


def detect_status_col(fieldnames):
    lower = {f.lower().strip(): f for f in fieldnames}
    for cand in STATUS_CANDIDATES:
        if cand in lower:
            return lower[cand]
    # substring fallback
    for f in fieldnames:
        fl = f.lower()
        if "account" in fl and ("health" in fl or "status" in fl):
            return f
    return None


# ─────────────────────────────────────────────────────────────────────
# 1. COVERAGE
# ─────────────────────────────────────────────────────────────────────

def report_coverage(rows, status_col):
    filled = [r for r in rows if not is_blank(r.get(status_col))]
    stale  = [r for r in rows if is_blank(r.get(status_col))]

    print("=" * 78)
    print(f"  1. COVERAGE  --  status column: '{status_col}'")
    print("=" * 78)
    print(f"  Total rows        : {len(rows):,}")
    print(f"  Status FILLED     : {len(filled):,}  ({pct(len(filled), len(rows))})")
    print(f"  Status EMPTY      : {len(stale):,}  ({pct(len(stale), len(rows))})   <- backlog")

    if filled:
        print(f"\n  Existing status values:")
        for val, n in Counter(str(r[status_col]).strip() for r in filled).most_common(15):
            print(f"    {n:>7,}  {pct(n, len(filled))}  {val}")
    return filled, stale


# ─────────────────────────────────────────────────────────────────────
# 2. FILL RATES  (all-zero / all-empty columns pakadne ke liye)
# ─────────────────────────────────────────────────────────────────────

def report_fill_rates(rows, cols, title):
    print("\n" + "=" * 78)
    print(f"  2. FIELD FILL RATES  --  {title}")
    print("=" * 78)
    print(f"  {'column':<34} {'filled':>8} {'non-zero':>9}  {'':<20}")
    print("  " + "-" * 74)

    n = len(rows)
    suspicious = []
    for c in cols:
        vals     = [r.get(c) for r in rows]
        filled   = sum(1 for v in vals if not is_blank(v))
        nums     = [as_num(v) for v in vals]
        numeric  = [x for x in nums if x is not None]
        nonzero  = sum(1 for x in numeric if x != 0)

        flag = ""
        if filled == 0:
            flag = "<- COMPLETELY EMPTY"
            suspicious.append((c, "empty"))
        elif numeric and nonzero == 0:
            flag = "<- ALL ZERO (never populated?)"
            suspicious.append((c, "all-zero"))
        elif filled < n * 0.05:
            flag = "<- <5% filled"
            suspicious.append((c, "sparse"))

        nz_txt = pct(nonzero, n) if numeric else "    cat"
        print(f"  {c[:34]:<34} {pct(filled, n):>8} {nz_txt:>9}  "
              f"{bar(filled, n, 18):<18} {flag}")
    return suspicious


# ─────────────────────────────────────────────────────────────────────
# 3. STALE ROWS: inputs hain ya nahi?  (asli sawaal)
# ─────────────────────────────────────────────────────────────────────

def report_backfillability(stale, feature_cols):
    print("\n" + "=" * 78)
    print("  3. CAN THE BACKLOG BE BACKFILLED FROM EXISTING COLUMNS?")
    print("=" * 78)
    if not stale:
        print("  Koi stale row nahi -- backlog khaali hai.")
        return None
    if not feature_cols:
        print("  Koi at_* feature column nahi mila. --feature-prefix set karo.")
        return None

    have_counts = Counter()
    for r in stale:
        have = sum(1 for c in feature_cols if has_value(r.get(c)))
        have_counts[have] += 1

    n = len(stale)
    ready   = sum(v for k, v in have_counts.items() if k >= max(1, len(feature_cols) // 2))
    partial = sum(v for k, v in have_counts.items() if 0 < k < max(1, len(feature_cols) // 2))
    barren  = have_counts.get(0, 0)

    print(f"  Stale rows                     : {n:,}")
    print(f"  ...with MOST inputs present    : {ready:,}  ({pct(ready, n)})  "
          f"-> recompute karke turant backfill")
    print(f"  ...with SOME inputs present    : {partial:,}  ({pct(partial, n)})  "
          f"-> partial, thoda enrichment")
    print(f"  ...with NO usable inputs       : {barren:,}  ({pct(barren, n)})  "
          f"-> pehle re-enrichment zaroori")

    print(f"\n  Stale rows me har feature ka fill rate:")
    for c in feature_cols:
        f_      = sum(1 for r in stale if not is_blank(r.get(c)))
        usable  = sum(1 for r in stale if has_value(r.get(c)))
        numeric = any(as_num(r.get(c)) is not None for r in stale)
        kind    = "numeric" if numeric else "categorical"
        note    = ""
        if f_ and usable == 0:
            note = "   <- bhara hai lekin sab 0 = pipeline ne chhua hi nahi"
        elif f_ == 0:
            note = "   <- poora khaali"
        print(f"    {c[:34]:<34} {kind:<12} filled {pct(f_, n)}  "
              f"usable {pct(usable, n)}{note}")

    print("\n  VERDICT:")
    if barren > n * 0.5:
        print("    >50% stale rows ke paas inputs hi nahi hain.")
        print("    -> ENRICHMENT pehle. Health recompute uske baad.")
    elif ready > n * 0.5:
        print("    >50% stale rows ke paas inputs maujood hain.")
        print("    -> Pure RECOMPUTE + WRITE job hai, enrichment ki zaroorat nahi.")
    else:
        print("    Mixed. Do batch me karo: pehle 'most inputs present' wale")
        print("    backfill karo, baaki ko enrichment queue me daalo.")
    return {"ready": ready, "partial": partial, "barren": barren, "total": n}


# ─────────────────────────────────────────────────────────────────────
# 4. RULE REVERSE-ENGINEERING  (automation ke andar jhaanke bina)
# ─────────────────────────────────────────────────────────────────────

def report_inferred_rule(filled, status_col, feature_cols, top=6):
    print("\n" + "=" * 78)
    print("  4. INFERRED RULE  --  populated rows se seekha gaya")
    print("=" * 78)
    if not filled:
        print("  Koi populated row nahi -- rule infer nahi kar sakte.")
        return
    if not feature_cols:
        print("  Koi feature column nahi mila.")
        return

    by_status = defaultdict(list)
    for r in filled:
        by_status[str(r[status_col]).strip()].append(r)

    for status, group in sorted(by_status.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"\n  STATUS = '{status}'   ({len(group):,} rows)")
        for c in feature_cols[:12]:
            nums = [as_num(r.get(c)) for r in group]
            nums = [x for x in nums if x is not None]
            if nums and any(x != 0 for x in nums):
                nums.sort()
                med = nums[len(nums) // 2]
                print(f"     {c[:34]:<34} min={nums[0]:<10.4g} med={med:<10.4g} "
                      f"max={nums[-1]:.4g}")
            else:
                cats = Counter(str(r.get(c)).strip() for r in group
                               if not is_blank(r.get(c)))
                if cats:
                    shown = ", ".join(f"{v}({n})" for v, n in cats.most_common(4))
                    print(f"     {c[:34]:<34} {shown}")

    print("\n  Ye numbers dekh ke rule likh lo (ya mujhe paste kar do) --")
    print("  backfill script isi rule ko 4-5K rows par apply karega.")


# ─────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Airtable account-health CSV audit")
    ap.add_argument("--csv", required=True, help="Airtable view ka CSV export")
    ap.add_argument("--status-col", help="Status/health column ka naam (auto-detect default)")
    ap.add_argument("--feature-prefix", default=FEATURE_PREFIX,
                    help=f"Feature columns ka prefix (default: {FEATURE_PREFIX})")
    ap.add_argument("--samples", type=int, default=0, help="Kitne stale rows print karein")
    args = ap.parse_args()

    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols   = list(reader.fieldnames or [])
        rows   = list(reader)

    if not rows:
        print("CSV khaali hai."); sys.exit(1)

    status_col = args.status_col or detect_status_col(cols)
    if not status_col or status_col not in cols:
        print(f"Status column nahi mila. --status-col se batao.\nColumns: {cols[:40]}")
        sys.exit(1)

    feature_cols = [c for c in cols if c.lower().startswith(args.feature_prefix.lower())]

    print(f"\n  File     : {args.csv}")
    print(f"  Columns  : {len(cols)}   Rows: {len(rows):,}")
    print(f"  Features : {len(feature_cols)} matching '{args.feature_prefix}*'\n")

    filled, stale = report_coverage(rows, status_col)
    report_fill_rates(rows, feature_cols or cols[:25], "all rows")
    report_backfillability(stale, feature_cols)
    report_inferred_rule(filled, status_col, feature_cols)

    if args.samples and stale:
        print("\n" + "=" * 78)
        print(f"  SAMPLE STALE ROWS ({min(args.samples, len(stale))})")
        print("=" * 78)
        for r in stale[:args.samples]:
            shown = {c: r.get(c) for c in (feature_cols[:6] or cols[:6])}
            print(f"    {shown}")

    print("\n" + "=" * 78)
    print("  Ye output mujhe paste kar do -- backfill script exact rule ke saath likh dunga.")
    print("=" * 78 + "\n")


if __name__ == "__main__":
    main()
