# Integration extension points

OpenAI is implemented in assurance/ai.py using the Responses API. Configure OPENAI_API_KEY and OPENAI_MODEL in .env. No key is required for reconciliation.

Future policy administration adapters should return the canonical records documented in docs/PRICING_CONTRACT.md and call assurance.engine.reconcile. Keep network I/O outside the calculation engine. Runs may be saved through assurance.storage.Store, preserving input provenance and exact rule hashes. A separate REST service can wrap these functions when remote access is needed; none is required for this local single-user application.
