# Remote-ingestion policy

Production now explicitly sets `ALLOW_REMOTE_DATASET_URLS=false`.

The AI isolated-worker feature was not enabled as a workaround. Readiness truthfully reports both local AI execution and remote ingestion disabled. Local managed-upload parsing remains available through the separately isolated parser worker.

Enabling remote URLs in the future requires a separately reviewed isolated worker, pinned HTTPS/SSRF policy, resource ceilings, health contract, and fault testing. Until then the controlled disabled response is the intended behavior.
