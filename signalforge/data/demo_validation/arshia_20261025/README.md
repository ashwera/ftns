# Actual demo validation exports

These files are copies of real local run artifacts, not synthetic successful findings.

- `completed_investigation.json`: Coal India run `research_20261024T232238_39445100e7e3`, completed after four recorded recoveries. Model challenge and deterministic policy adjudication finished. Result: inconclusive / Weak, one issuer source, no independent corroboration.
- `unattended_investigation.json` and `unattended_manifest.json`: browser-started run `research_20261024T234754_a378b8365612`, finished without manual recovery in about 173 seconds. Strict operand validation refused the final draft; result: evidence_gap / Not rated, final semantic review incomplete.
- `f1.json` and `r1.json`: accepted model selection and plan from that unattended run.
- `provider_failover.json`: actual unavailable-Ollama to Groq JSON request trace.

Full raw audits, recovery snapshots and original downloaded PDFs remain in ignored local execution directories. Reports record original URLs, hashes, locators and local paths; these exports alone do not bundle original source bytes. Refer to the root `ARSHIA_DEMO_HANDOVER.md` for reproducibility, commands and limitations. Neither run establishes a novel independently corroborated financial discovery.
