# Briefedly Google OAuth production compliance

The authoritative detailed lane is [briefedly-google-production-verification-plan.md](briefedly-google-production-verification-plan.md). Status: **BLOCKED BY PROVIDER** and **REQUIRES EXTERNAL ASSESSMENT** before private Gmail production.

Current source requests exactly:

- `openid` — authentication identity scope;
- `email` — email claim scope;
- `https://www.googleapis.com/auth/gmail.readonly` — **Restricted** Gmail scope.

Google's current Gmail scope page classifies `gmail.readonly` as restricted and states that storing or transmitting restricted-scope data on servers requires a security assessment. Briefedly stores encrypted tokens, imported messages, metadata, and derived reports and sends message evidence to Ollama, so the assessment condition applies. Development/testing exceptions do not authorize a public production app.

Hard launch blockers: separate production Google Cloud project; verified brand/domain/homepage; public terms/privacy/support/delete documentation; prominent in-product disclosure immediately before consent; minimum-scope justification and demonstration video; Limited Use disclosure; verified restricted-scope data map and AI use; CASA/Google-designated assessment; incident contact/process; P0 closure; and production lifecycle/restore proof.
