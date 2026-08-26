/*
 * Daily Snapshot  --  Airtable automation script
 * ==============================================
 *
 * KAHAN LAGTA HAI
 *   Automations -> Create automation
 *     Trigger : "At scheduled time"  ->  Daily  ->  11:59 PM
 *               (timezone Airtable ke scheduler me set hota hai)
 *     Action  : "Run a script"  ->  ye poori file paste kar do
 *
 * KYA KARTA HAI
 *   Aaj ke saare Sends rows uthata hai, Domain ke hisaab se group karta
 *   hai, aur Daily Snapshot me har domain ki ek row likh deta hai.
 *
 *   Ye LIVE ROLLUP NAHI hai -- jaan-bujh ke frozen numbers likhta hai,
 *   taaki 3 mahine baad bhi pata rahe ki us din kya hua tha.
 *
 * IDEMPOTENT
 *   Row ka key = "YYYY-MM-DD :: domain.com". Dobara chala do to purani
 *   row UPDATE hoti hai, duplicate nahi banti. Isliye din me kai baar
 *   chalana safe hai, aur ek din miss ho jaaye to backfill bhi ho jaata
 *   hai (TARGET_DATE neeche).
 *
 * DHYAN DO
 *   Jin Sends rows me Domain khaali hai (LinkedIn / Call activity) wo is
 *   snapshot me count NAHI hoti -- snapshot per-domain hai. Script chalne
 *   par batata hai kitni rows is wajah se chhoot gayi.
 */

// ── CONFIG ───────────────────────────────────────────────────────────
// Apna timezone daalo. Isi se decide hota hai ki "aaj" kaunsa din hai.
// Galat rakha to 11:59 PM ka run agle/pichhle din me gir sakta hai.
const TIMEZONE = 'Asia/Kolkata';

// Sends table par filtered view ("Date is today"). Iske bina script poori
// table scan karta hai -- chhoti base par theek, badi par slow.
const SOURCE_VIEW = 'Today (automation source)';

// Backfill karna ho to yahan 'YYYY-MM-DD' daal do, warna null rehne do.
// NOTE: TARGET_DATE set karne par SOURCE_VIEW ignore ho jaata hai (view
// sirf aaj ki rows deta hai), aur script poori table scan karta hai.
const TARGET_DATE = null;

// ── TABLES ───────────────────────────────────────────────────────────
const sendsTable    = base.getTable('Sends');
const snapshotTable = base.getTable('Daily Snapshot');

// ── "AAJ" KAUNSA DIN HAI ─────────────────────────────────────────────
// en-CA locale YYYY-MM-DD format deta hai -- yahi Airtable date fields
// ka format hai, to seedhe string compare kar sakte hain.
function localToday() {
    return new Intl.DateTimeFormat('en-CA', {
        timeZone: TIMEZONE, year: 'numeric', month: '2-digit', day: '2-digit',
    }).format(new Date());
}

const today = TARGET_DATE || localToday();
console.log(`Snapshot date: ${today}  (timezone ${TIMEZONE})`);

// ── SENDS PADHO ──────────────────────────────────────────────────────
const FIELDS = ['Date', 'Domain', 'Opened', 'Replied', 'Meeting Booked',
                'Bounced', 'Spam Complaint'];

let query;
if (!TARGET_DATE && sendsTable.getViewIfExists(SOURCE_VIEW)) {
    query = await sendsTable.getView(SOURCE_VIEW).selectRecordsAsync({ fields: FIELDS });
    console.log(`Source: view '${SOURCE_VIEW}' (${query.records.length} rows)`);
} else {
    query = await sendsTable.selectRecordsAsync({ fields: FIELDS });
    console.log(`Source: poori Sends table (${query.records.length} rows) -- `
              + `view '${SOURCE_VIEW}' nahi mila ya backfill mode on hai`);
}

// ── DOMAIN KE HISAAB SE GROUP KARO ───────────────────────────────────
const byDomain = new Map();   // domainRecordId -> totals
let skippedNoDomain = 0;

for (const rec of query.records) {
    // Date field date-only hai to "YYYY-MM-DD" aata hai; kabhi full ISO
    // aa jaaye to slice bacha leta hai.
    const d = rec.getCellValue('Date');
    if (!d || String(d).slice(0, 10) !== today) continue;

    const domainLinks = rec.getCellValue('Domain');
    if (!domainLinks || domainLinks.length === 0) { skippedNoDomain++; continue; }
    const domain = domainLinks[0];

    if (!byDomain.has(domain.id)) {
        byDomain.set(domain.id, {
            name: domain.name, sent: 0, opened: 0, replied: 0,
            meetings: 0, bounced: 0, spam: 0,
        });
    }
    const t = byDomain.get(domain.id);
    t.sent     += 1;
    t.opened   += rec.getCellValue('Opened')         ? 1 : 0;
    t.replied  += rec.getCellValue('Replied')        ? 1 : 0;
    t.meetings += rec.getCellValue('Meeting Booked') ? 1 : 0;
    t.bounced  += rec.getCellValue('Bounced')        ? 1 : 0;
    t.spam     += rec.getCellValue('Spam Complaint') ? 1 : 0;
}

console.log(`${byDomain.size} domain(s) ki activity mili.`);
if (skippedNoDomain) {
    console.log(`${skippedNoDomain} row(s) skip hui -- Domain khaali tha `
              + `(LinkedIn/Call activity, ye normal hai).`);
}
// NOTE: top-level `return` Airtable ke script environment me illegal hai,
// isliye khaali-din wala case if/else se handle kiya hai.
if (byDomain.size === 0) {
    console.log('Aaj kuch nahi bheja gaya -- koi snapshot row nahi banegi.');
} else {
    // ── PEHLE SE MAUJOOD ROWS DHOONDHO (idempotency) ─────────────────
    const existingQuery = await snapshotTable.selectRecordsAsync({ fields: ['Snapshot Key'] });
    const existingByKey = new Map();
    for (const rec of existingQuery.records) {
        const key = rec.getCellValue('Snapshot Key');
        if (key) existingByKey.set(key, rec.id);
    }

    // ── CREATE / UPDATE LIST BANAO ───────────────────────────────────
    const toCreate = [];
    const toUpdate = [];

    for (const [domainId, t] of byDomain) {
        const key = `${today} :: ${t.name}`;
        const fields = {
            'Snapshot Key'          : key,
            'Date'                  : today,
            'Domain'                : [{ id: domainId }],
            'Sent Today'            : t.sent,
            'Opened Today'          : t.opened,
            'Replied Today'         : t.replied,
            'Meetings Today'        : t.meetings,
            'Bounced Today'         : t.bounced,
            'Spam Complaints Today' : t.spam,
        };

        const existingId = existingByKey.get(key);
        if (existingId) toUpdate.push({ id: existingId, fields });
        else            toCreate.push({ fields });
    }

    // ── LIKHO  (Airtable ek call me max 50 records leta hai) ─────────
    for (let i = 0; i < toCreate.length; i += 50) {
        await snapshotTable.createRecordsAsync(toCreate.slice(i, i + 50));
    }
    for (let i = 0; i < toUpdate.length; i += 50) {
        await snapshotTable.updateRecordsAsync(toUpdate.slice(i, i + 50));
    }

    console.log(`DONE -- ${toCreate.length} nayi row(s), ${toUpdate.length} update.`);
    for (const [, t] of byDomain) {
        console.log(`  ${t.name}: sent ${t.sent}, opened ${t.opened}, `
                  + `replied ${t.replied}, meetings ${t.meetings}, `
                  + `bounced ${t.bounced}, spam ${t.spam}`);
    }
}
