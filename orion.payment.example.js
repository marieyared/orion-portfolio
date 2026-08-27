/* ════════════════════════════════════════════════════════════════════
   ORION PAYMENT CONFIG — TEMPLATE  (copy this file to orion.payment.js)
   --------------------------------------------------------------------
   This is the ONLY place the throwaway willingness-to-pay probe's two
   values live. Loaded by orion.html as a <script> asset (file://-safe,
   same pattern as dossiers/dossiers.js) into window.ORION_PAYMENT.

   SETUP:
     1. Copy this file:   cp orion.payment.example.js orion.payment.js
     2. Paste your real Stripe Payment Link + unlock code into the copy.
     3. orion.payment.js is git-ignored, so your real values never commit.

   If orion.payment.js is absent, orion.html falls back to harmless
   REPLACE_ME placeholders — the app still loads, the probe just no-ops.

   NOTE: the Stripe Payment Link is a PUBLIC checkout URL — it contains no
   banking details. Your bank/payout info lives only in your Stripe account.
════════════════════════════════════════════════════════════════════ */
window.ORION_PAYMENT = {
  // The Stripe Payment Link for Orion Pro. Must be the MONTHLY / recurring
  // link ($15/mo), not a one-off charge. Looks like https://buy.stripe.com/...
  STRIPE_PAYMENT_LINK: "https://buy.stripe.com/REPLACE_ME",

  // The access code you hand to buyers (manual fulfillment). They paste it
  // into the "I've already paid — unlock" box to flip on Pro locally.
  ORION_UNLOCK_CODE: "REPLACE_ME",

  // OWNER OVERRIDE: set true on YOUR machine to get all Pro features free
  // while building. Because orion.payment.js is git-ignored, this never ships
  // to real users — they still see the gate. Keep it false in this template.
  DEV_ALWAYS_PRO: false,
};
