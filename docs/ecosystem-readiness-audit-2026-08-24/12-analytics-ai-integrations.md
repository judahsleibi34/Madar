# Analytics, AI and integrations

## Analytics

Implemented analytics include stored public-site/event observations, form response summaries, reservation analytics, dataset profiling/cleaning, charts, exports and tenant-scoped dashboard queries. Data workspace routes use user/tenant rate buckets, bounded previews, row/cell/file limits, chunked large CSV handling and private generated artifacts. IP and user-agent are stored on public form/reservation records; explicit retention/deletion policy is missing.

Public analytics are susceptible to bots/spam because the server cannot prove a human visitor. Redis rate limits constrain bursts, but no bot classification or signed first-party event session provides high-integrity counts. Report these metrics as operational estimates, not audited truth. Aggregation queries examined carried tenant scope; no cross-tenant aggregation was demonstrated.

## Implemented AI

The data-analysis planner supports Gemini and a mock provider. OpenAI is declared as a provider but the planner explicitly reports it is not implemented; DeepSeek settings exist but no equivalent completed planner path was verified. Generated Python runs only in a constrained subprocess worker with import, filesystem, network, output, memory, thread and timeout controls. Prompts requesting raw datasets, sensitive values, full dumps or charts through the strict assistant path are blocked before provider use. Token reservations and finalization are database-backed and tenant/user scoped.

Production has no Gemini/OpenAI provider key in the Madar environment and readiness reports AI execution guard disabled. Therefore implemented AI is not production-available. Because entitlement fallback currently grants `ai_analytics` to unmigrated tenants, UI/API commercial state can imply access to an unconfigured feature. G13 is **FAIL as deployed**; it becomes N/A only after AI is explicitly hidden/denied until configured.

Prompt injection remains relevant when untrusted dataset/document content is passed to a model. Current strict aggregate-only context and parser isolation reduce exposure; keep model calls tool-less, tenant-scoped and output-validated. No external AI call was attempted.

## Roadmap, not defects

- Arabic/English/Hebrew OCR: catalog marks future/coming-soon; not implemented as a production capability.
- Private Google Drive: future add-on; no completed Drive OAuth/content flow.
- Advanced analytics chatbot beyond the implemented constrained planner: roadmap.
- WhatsApp: only share-link UX; no messaging integration/add-on.
- Mobile client: prototype/roadmap.

## Other integrations

Google Calendar is configured and worker-ready. Microsoft Calendar code is implemented but production client credentials were not present in the inspected environment; report it unavailable until configured. ICS is implemented. Web Push is operational. SMTP is implemented but unconfigured and failing. OAuth credential encryption uses a dedicated secret; state consumption is atomic. Real provider revocation/outage tests were not run.
