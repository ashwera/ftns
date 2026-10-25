# SIGNALFORGE — DEMO DAY DESK SHEET

**25 October2026 · CONDITIONAL GO · audited runtime `df71552` · branch `codex/arshia-demo-readiness`**

**Version freeze:** newer main `8630a67` has unverified xAI migration; do not merge/switch before this demo.

**One sentence:** SignalForge turns company disclosures into a saved, evidence-linked investigation with checked quotations, arithmetic, skeptical review and explicit limits.

**Architecture:** React/Vite → local Python API → search/onboarding → original-PDF evidence gate → F1 angle → R1 plan → investigation/counter-search → quote/number checks → model challenge + deterministic policy → report/export.

**Five demonstrated strengths:** source/page/hash provenance; exact-quotation validation and bounded repair; source-backed deterministic arithmetic; separate skeptical review and refusal; recoverable stages with provider/model audit.

**Five limits:** weak search coverage; no independent corroboration/novel discovery in the completed case; hosted quota/503 variability; incomplete company/index eligibility coverage; generated leads/falsification and live scope reconciliation still need analyst scrutiny. Sidebar archive panels are separate from the current run. Ollama is unavailable here.

**Provider today:** Gemini `gemini-3.1-flash-lite` for full context. Fresh JSON1.072s; full browser case94.74s. Groq120B JSON0.660s; account8K TPM caused413/429. Saved report is the reliable presentation backup. Do not install local models during judging.

## Start (two terminals, from the indicated directories)

```bash
cd /Users/arshiadang/Desktop/fns
SIGNALFORGE_PROVIDER=gemini SIGNALFORGE_MODEL=gemini-3.1-flash-lite SIGNALFORGE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/ SIGNALFORGE_FALLBACK_PROVIDERS='' PYTHONPATH=signalforge/src .venv/bin/python -m signalforge.research_service
```

```bash
cd /Users/arshiadang/Desktop/fns/signalforge/web
npm run dev -- --host 127.0.0.1 --port 5173
```

**URLs:** live `http://127.0.0.1:5173/`; saved backup `http://localhost:5173/`; health `http://127.0.0.1:8765/api/agent/health`. Hosted models need no local model-server command. Keys stay in ignored `.env`; never open it on screen.

**Preload backup:** **01 Signal → Saved investigations →**
`research_20261025T051452_b844776593ba`

Heading: **CIL Renewable Portfolio Expansion Progressing with Commissioned Milestones**. Outcome: **inconclusive / Weak**, final review complete, novelty=false. Issuer reports200/300MW Khavda commissioned; Python ratio≈66.7%. No schedule delay or financial loss established.

**Live flow:** Tab A Company **text field** → exact assigned Research question → **Start research** once → actual ID/stages. Tab B remains the explicitly saved Coal India case. Its saved chooser must be prepared before Tab A starts; active-tab chooser is locked. Show **Claims and model challenge → Source passage… → Calculations → Counterargument → Evidence strength and limitations → Export investigation JSON/Markdown**. Do not use **Saved workspace company** to start research.

**Speaking/time:** Arshia0:00–1:10 (problem/start); Ashwera1:10–3:00 (F1/R1/evidence/calculation); Samaira3:00–5:00 (challenge/limits/close). At1:10 label the switch to the saved example. Keep any live result separate.

**Emergency:** Do not repeatedly resubmit. If model/search/validation fails, read the actual failed stage, retain the job and show Tab B. If services fail, open the saved Markdown at `signalforge/data/research_runs/research_20261025T051452_b844776593ba/investigation_report.md`. Citation-recovery reserve: `research_20261025T000129_2ecbfd3ad81c`; refusal reserve: `research_20261024T234754_a378b8365612`. Resume/provider commands: `ARSHIA_DEMO_HANDOVER.md`.

**Likely questions:** Novel discovery? **No, not established.** Why weak? **One issuer lineage, missing matched independent records.** Quote incident? **Exact14-character text failed15-character context rule; diagnosis fixed, longer original span tested.** Trust? **Traceable claims and checks, not guaranteed truth.** Every company? **No universal coverage; eligibility external.**

**Never claim:** fraud/alpha/novelty; independent confirmation from copied issuer material; capacity equals revenue loss or parent economic ownership; cached report is live assigned-company output; every terminal report completed semantic review; tests measure financial accuracy.

**Checks:** backend359 run/357 passed/2 skipped; frontend44 passed; TypeScript/build passed. Original-PDF skips remain disclosed. Full audit/defence: `SIGNALFORGE_FEATURE_CHEATSHEET.md`, `SIGNALFORGE_5_MIN_DEMO_SCRIPT.md`, `SIGNALFORGE_JUDGE_QA.md`.
