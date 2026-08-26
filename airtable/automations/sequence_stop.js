/*
 * Sequence Stop  --  Airtable automation script
 * =============================================
 *
 * KAHAN LAGTA HAI
 *   Automations -> Create automation
 *     Trigger : "When record matches conditions"
 *               Table     : Contacts
 *               Condition : Engaged  is  checked
 *     Action  : "Run a script"  ->  ye poori file paste kar do
 *
 *     Phir script editor ke left panel me ye INPUT VARIABLES add karo
 *     (naam bilkul yahi rakhna, values trigger record se map karna):
 *
 *         recordId     ->  Airtable record ID
 *         contactName  ->  Contact Name
 *         email        ->  Email
 *         kylasId      ->  Kylas Contact ID
 *         stage        ->  Current Stage
 *
 * ⚠  YE EXTERNAL DEPENDENCY HAI
 *   Airtable khud kisi sequencer ko rok nahi sakta. Ye script sirf ek
 *   webhook maarti hai -- asli "stop" us doosre tool me hota hai.
 *
 *   Do raaste hain:
 *
 *   A) SEEDHA  -- agar tumhara sequencer (Instantly / Smartlead / Lemlist /
 *      Reply.io) ka apna API hai, to WEBHOOK_URL me uska endpoint daalo
 *      aur neeche `body` ko unke schema ke hisaab se badal do. Agar API
 *      key chahiye to HEADERS me daal do.
 *
 *   B) BEECH ME MAKE.COM / n8n / ZAPIER  -- inme "Custom webhook" trigger
 *      banao, uska URL yahan paste karo, aur unhi ke andar sequencer wala
 *      "remove from campaign" step laga do. Ye tab better hai jab
 *      sequencer ka API ganda ho ya retry/logging chahiye.
 *
 *   Jab tak WEBHOOK_URL set nahi hota, script jaan-bujh ke FAIL hoti hai --
 *   taaki chup-chaap ye na lage ki sequence ruk gaya jabki ruka hi nahi.
 */

// ── CONFIG ───────────────────────────────────────────────────────────
const WEBHOOK_URL = '';   // <-- apna Make.com / n8n / sequencer endpoint

const HEADERS = {
    'Content-Type': 'application/json',
    // sequencer API key chahiye to yahan:
    // 'Authorization': 'Bearer xxxxx',
};

// ── INPUTS ───────────────────────────────────────────────────────────
const {
    recordId, contactName, email, kylasId, stage,
} = input.config();

// ── GUARDS ───────────────────────────────────────────────────────────
if (!WEBHOOK_URL) {
    throw new Error(
        'WEBHOOK_URL set nahi hai. Jab tak ye khaali hai, sequence ACTUALLY '
        + 'nahi rukegi -- Airtable sirf field flip kar raha hai. Apne '
        + 'sequencer ka ya Make.com/n8n ka endpoint daalo.');
}

// Email hi wo unique key hai jisse sequencer/Kylas contact match karta hai.
// Nahi hai to stop request bemaani hai -- shor machao, chup mat raho.
if (!email) {
    throw new Error(
        `Contact "${contactName || recordId}" me Email khaali hai. Sequencer `
        + 'isi se contact dhoondhta hai, to stop request bhej nahi sakte. '
        + 'Contacts table me Email bharo.');
}

// ── PAYLOAD ──────────────────────────────────────────────────────────
// Ye generic shape hai. Seedha sequencer API hit kar rahe ho to isko
// unke schema me badal lena.
const body = {
    action        : 'stop_sequence',
    reason        : 'contact_engaged',
    email         : email,
    contactName   : contactName || null,
    kylasContactId: kylasId || null,
    currentStage  : stage || null,
    airtableRecord: recordId,
    triggeredAt   : new Date().toISOString(),
};

// ── BHEJO ────────────────────────────────────────────────────────────
console.log(`Stop signal -> ${email}  (stage: ${stage || 'unknown'})`);

const response = await fetch(WEBHOOK_URL, {
    method : 'POST',
    headers: HEADERS,
    body   : JSON.stringify(body),
});

// 2xx nahi mila to automation ko FAIL hone do -- Airtable ka run history
// tab red dikhayega aur pata chalega ki stop signal gira nahi.
if (!response.ok) {
    const text = await response.text();
    throw new Error(
        `Webhook ne ${response.status} diya -- sequence NAHI ruki.\n`
        + text.slice(0, 500));
}

console.log(`OK -- webhook ne ${response.status} diya. Sequence stop request bhej di.`);
