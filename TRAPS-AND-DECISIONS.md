# Traps and decisions

Things I found that you should know about, and things only you can answer.

- **Needs your call** — open questions. Each has my recommendation. "Agree" is a valid answer.
- **Traps and differences** — no decision needed, just be aware.
- **Settled** — answered items, kept so we never argue them twice.

---

# Needs your call

This run (Session 33 onwards) is unattended — Rohit is away from the keyboard.
Decisions that would normally wait for him are made and recorded here instead,
each with an ID, so he can review and overturn any of them afterwards.

---

### D-22 · The eligibility timestamp is removed from the stored text, not converted

**What's wrong:** the Application Detail card showed the same event at two times
five and a half hours apart. The paragraph above the assessment printed
`eligibility_checked_at` through the browser's own formatter, which converts to
the reader's timezone. The assessment text below it opened with a line
`build_summary_text` had written as a UTC wall clock. One event, two clocks, one
screen.

**Chosen:** delete the line from the text entirely rather than converting it to
IST. The moment is already stored properly in `eligibility_checked_at`, a real
datetime column that reaches the browser as a datetime, so the card already had
a correct copy — the text's line was a second, worse one.

**Why:** converting it on the server would need the server to decide the
reader's timezone, which it has no business knowing. It also leaves two copies
of one fact that can drift apart later. A time is stored once, as a datetime,
and formatted where it is read. That is how every other date in this app already
works, and the bug existed precisely because this one string opted out.

**The part worth arguing with:** a stored string does not fix itself when the
code that wrote it changes, and fourteen applications in `loan_app.db` still had
the old line in them. So `init_db()` now strips that one line from rows that have
it, alongside the column-adding step from D-18. It is guarded by a `LIKE` and
touches nothing else in the assessment — the rest is the bank's permanent record
of what its rules said at submission and must not be rewritten. If you would
rather the old rows kept their old text, the repair function is
`_drop_baked_in_timestamps()` in `app/database.py` and deleting the one call in
`init_db()` disables it. Your demo data has already been repaired; a re-seed
would have produced clean text anyway.

**Your answer:**

---

### D-23 · One helper for stored-value-to-words, shared by both the screen and the AI

**What's wrong:** `label()` in the browser turned `id_proof` into "Id proof",
which reads as somebody's name rather than the initials it is. The same mistake
existed ten times over in the backend as a bare `replace("_", " ")`, and those
copies feed the AI prompts — so the chatbot and the app could describe the same
document with different words, which is exactly what Rule 12 forbids.

**Chosen:** one function each side, kept deliberately in step. `readable()` in
the new `backend/app/utils/text.py`, and `label()` in
`frontend/src/utils/format.js`, both holding the same short list of words that
are not simply capitalised: ID, KYC, EMI, CIBIL, PAN, AI, NRI. All ten backend
call sites now go through the helper and no raw `replace("_", " ")` survives
anywhere outside it.

**Why not one shared file:** one is Python and one is JavaScript, and there is no
sane way to share a literal between them in this project without a build step
nobody asked for. Two small lists with a comment in each pointing at the other is
the honest version of the trade-off. There is a test that walks every document
type, status and employment status the app can store and asserts no underscore
survives, so a new value added later cannot quietly reintroduce this.

**Your answer:**

---

### D-24 · The review path fails to a sentence, never to a red banner

**What's wrong:** every other AI path in this codebase is wrapped so it cannot
raise. `_review_answer` in `app/routers/chat.py` read `state["risk_assessment"]`
and its keys directly, and `evaluate_loan_application` was called outside any
`try`. Its docstring justified this by saying the caller returns early when data
collection fails — true, and it only covers the errors the graph *records*. An
agent raising part-way through, a network failure inside LangGraph, or a state
shape nobody predicted all escape as a 500, which is a red banner across the
chat mid-demo.

**Chosen:** wrap the whole review branch. Anything that escapes becomes a normal
200 answer saying the review could not be completed, with the application number

### D-25 · The briefing card is guarded against fields the schema says cannot be missing

**What's wrong:** `MorningBriefing.jsx` called `briefing.narrative.split("\n")`
and read `numbers.awaiting_decision` straight out of the response. Both fields
are required by the server's schema, so on any normal day neither can be absent.
But this card renders on the manager's dashboard, and **a React component that
throws while rendering does not fail alone — it takes the whole page white.** A
missing briefing would cost the entire dashboard rather than one card.

**Chosen:** guard both. A missing narrative shows one line saying no summary was
written and keeps the figures below it, which is the same shape as the existing
"AI unavailable — figures only" behaviour. A missing figure shows a dash.

**Why, given the schema says it cannot happen:** it costs three lines, and the
list of things that make it happen anyway is not short — a field renamed on the
server while a browser tab holds the old code, a proxy truncating a response, a
future change making the narrative optional because the AI was down. This whole
audit phase is about failures that are unlikely and bad. The briefing is the
headline demo feature and the first thing on screen after a manager logs in.

**Not on the list you gave me.** It was next to the review crash in the plan
file's phase 3 line ("a briefing that white-screens on missing data") and it is
three lines, so I did it. Say if you would rather it came out.

**Your answer:**

---


### D-26 · "2.5 years" rounds to "3 years", and that loses something real

**What's wrong:** the fix for "3.0 years" on My Profile rounds the number to a
whole one. Priya is stored as exactly 3.0 and now reads "3 years", which is the
bug fixed. But **Rahul Verma is stored as 2.5**, and rounding turns two and a
half years with an employer into three. For a decimal that is genuinely a half,
that is not a display fix — it is a changed fact.

**Chosen:** round anyway, for now. Every other decimal in the demo data is a
whole number that only *looks* fractional because the column is a float, which is
the bug you asked me to fix. Rahul's 2.5 is the single exception in the seeded
data and it does not appear anywhere in the demo path.

**Why I am flagging it rather than just doing it:** the employment rule in the
manual is "a salaried applicant must have been with their current employer for at
least 6 months", so half-years are meaningful to the business, not just to the
display. If a customer with 5.5 years reads "6 years" on their own profile, that
is the app misstating something about them.

**The alternative, if you want it:** show the decimal only when there is one —
`2.5 years`, `3 years` — which is one line in `whole()` in
`frontend/src/utils/format.js`. I did not do it because it makes the helper mean
two different things depending on the value, and `days_waiting` and `risk_score`
genuinely do want the decimal gone. A second, separate helper would be the honest
version.

**Your answer:**

---


### D-18 · How to add three new columns to a database that already has data in it

**What's wrong:** Piece 19 needed three new columns on `loan_applications`. `Base.metadata.create_all()`, the only thing `init_db()` did before now, only creates tables that don't exist yet — it never alters one that's already there. `loan_app.db` and `test.db` both already exist with real rows.

**Chosen:** a small `_add_missing_columns()` step in `database.py`, run every time `init_db()` runs. It reads `PRAGMA table_info(loan_applications)`, and for each of the three new columns not already there, runs `ALTER TABLE ... ADD COLUMN`. Safe to run on every startup — it checks before adding, so it does nothing on a database that already has the columns (including a brand new one, where `create_all` already added them from the model).

**Why:** the alternative was a proper migration tool (Alembic), which is the right answer for a longer-lived project but is a new library, a new folder, and a new command to run before every session — a lot of new surface for three columns in a SQLite file with no other consumers. This is a good decision for a POC's SQLite database; it is not what I would recommend if this were a production system with several people deploying against the same database.

**Your answer:**

---

### D-20 · Several Gemini keys, rotated, before Phase 4 and 5 reach the chat

**What's wrong:** Piece 22's remaining steps put Phase 4 and Phase 5 behind the React chat box. A Phase 5 review is several AI calls for one question, so a single free-tier Gemini key runs dry fast — and the first time it does, it will be in front of an audience. There is currently one key, and one fallback (Ollama), with nothing in between.

**Chosen (Rohit, 2026-09-10):** collect spare free Gemini keys from friends into a comma-separated `GOOGLE_API_KEYS`, and build a rotation ladder inside `llm_provider.py` — key 1, key 2, … then local Ollama, then an honest "offline". Plus distinct error codes per failure mode rather than one generic error. Planned as Piece 23; **it gets built before Piece 22 steps 4 and 5.**

**Why it goes in `llm_provider.py` and nowhere else:** that file's docstring already forbids any other module from importing a provider class directly, so all five phases call `get_llm()`. Building rotation there means Phase 2's chain, Phase 3's agent, Phase 4's MCP chat and Phase 5's graph all inherit it without being edited.

**Two things worth saying out loud:** a `429`/`RESOURCE_EXHAUSTED` retires a key for the day, but a `400`/`403` is a *typo*, not an exhausted quota — that one gets dropped and logged loudly, because silently rotating past a bad key would hide the mistake forever. And per D-19, an exhausted key may change the *wording* of a Phase 5 review but must never change its *decision*, since those numbers are plain Python.

**Your answer:** _(his, 2026-09-10 — this was his design; recorded here so it is not re-argued)_

---

### D-21 · Phase 4 and 5 inherit Phase 3's permission gate for free

**What's wrong:** Phase 4's six MCP tools include three that change real records — `submit_loan_application`, `update_application_status`, `upload_document_metadata`. `update_application_status` can reject or disburse a loan, and Phase 4's own prompt admits those moves "can never be undone". Phase 4 was built for a Streamlit page with no logged-in user, so its tools run as a fixed service account. Wired into the customer-facing chat unchanged, that is a customer approving their own loan.

**Chosen:** wrap Phase 4's tools in the same `acting_as()` block Phase 3 already uses. Checked in the code: `mcp_app.py` imports `api_get/api_post/api_patch` from the same `app.services.loan_api_client` Phase 3 uses, and `service_token()` reads the `acting_as()` ContextVar. So the gate already reaches Phase 4's tools — they just are not currently called inside it.

**Why:** it is not a new permission system. `application_service.py:271` already refuses disbursement to anyone who is not a branch manager, and every endpoint is owner-scoped and was tested twenty ways in Phase 1. The AI inherits all of it and answers 403 exactly where the browser would. Rohit's recollection of the role split was checked against the code and is correct: officers get everything except disburse, managers get disburse too.

**Your answer:** _(his, 2026-09-10 — confirmed against the code)_

---

### D-19 · Phase 5: the LLM writes the prose, plain Python computes the numbers

**What's wrong:** the trainer's Phase 5 reference asks the LLM to compute the debt-to-income ratio, the EMI, the credit and employment risk tiers and the overall risk score itself, and return them as JSON to be parsed with a regex. Their own "common mistakes" table then admits the consequence: *"JSON parsing fails in Risk Assessor — use regex to extract JSON, have fallback values."* For numbers a lending decision hangs on, an occasional silent fallback to made-up defaults is not an acceptable failure mode.

**Chosen:** every number in Phase 5 — EMI, DTI, affordability, credit risk tier, employment risk tier, overall score, and the final decision itself — is computed in plain Python from the same `app/domain/rules.py` thresholds Phase 1's eligibility check already uses (the ones settled in D-10, T-13 and T-14 before Phase 5 was ever built). The LLM's job is narrower and better suited to it: writing the `risk_summary` and the decision `reasoning` a human underwriter actually reads, from figures already known to be correct. If the LLM call fails, times out, or is rate-limited, a short deterministic sentence takes its place and **the decision does not change**.

**Why:** three reasons worth saying out loud in a walkthrough. The decisions are repeatable — the same application always gets the same answer, which is what an auditor and a regulator both want. They are explainable line by line, which the program's own integrity rules require. And a bad JSON day or an exhausted free-tier quota can never alter a lending decision. This still genuinely puts an LLM in the pipeline, traced per-agent in LangSmith, doing the part it is actually good at.

**Your answer:**

---

### D-09 · Angular as a third front-end later?

**My recommendation:** revisit once Phase 5 is demo-ready. Listed in `FUTURE-UPGRADES.md`.

**Your answer:**

---

### Parked, not open

**D-12 · Hosting.** Clarified: we build on Rohit's personal laptop, which has no restrictions. The Wipro laptop is restricted and might only ever open the app in a browser. Whether to host the app online is decided before the demo, not now. One design habit from now on so it stays possible: the front-end reads the backend's address from a setting, never hardcoded.

---

# Traps and differences

No decision needed. These break something quietly if forgotten.

**T-127 · Git would have rewritten line endings inside the demo PDFs.** The demo
kit's PDFs are plain text inside, so git treated them as text, and with
`core.autocrlf` on, a Windows checkout (the Wipro laptop) would have rewritten
their line endings and broken the byte offsets a PDF depends on.
`.gitattributes` now marks PDFs, images and the deck as binary. Fixed in v2.18.1.

**T-126 · Anything that needs a PDF's text must run before the rebuild.** The
rebuild (stage 6 in `file_service`) redraws every page as a picture, so a stored
file has no text at all. Classification (Piece 31) and reading details (Piece 34)
both run on the original bytes for this reason. It also means details started
again after a discard can't be read automatically, only typed. Note too that a
PDF may turn a typed `'` into a curly `’`, so any label rule that has an
apostrophe must accept both.

**T-125 · A document's details decide whether it counts, so check `needs_details` anywhere documents are counted.**
From Piece 33 on, a real file of a type with kinds doesn't count until its details
are confirmed. The rule lives in `document_service.counts_towards_checklist`,
which the checklist and the briefing use. Phase 5's compliance checker reads the
`needs_details` flag over the API. Anything new that counts documents must use
one of the two, or it will disagree with the checklist.

**T-124 · A text box inside any pop-up lost focus after every keystroke.** Found
by Rohit typing the purge phrase (2026-09-24). `Modal.jsx`'s effect listed
`onClose` as a dependency, and pages pass a new `onClose` on every render, so
each keystroke re-ran the effect and moved focus away. Fixed by keeping
`onClose` in a ref and depending on `open` only. It affected every pop-up with a
box to type in, not just the purge one. Watch for the same pattern in any new
effect that takes a callback prop.

**T-123 · The "X/Y submitted" line counts files, not document types.** Found by
Rohit during the Piece 32 browser check (2026-09-24). `DocumentChecklist.jsx`
prints `items.length / required.length`, so two ID proofs on a personal loan
show "2/3 submitted" while income proof and bank statement are still missing,
and three ID proofs would show "3/3". The ticks above it are right, because they
use the server's `missing` list. The bug dates from Piece 14, not Piece 32. Fix:
count `required.length - missing.length` instead. Only the front end changes, and
no trainer test reads this line. Linked to D-29. **Fixed 2026-09-24, v2.15.3.**

**T-122 · A handful of full-suite tests failed near the end of an unrelated
run, not yet identified.** While building Piece 32 (2026-09-23), a full
`pytest` run was started to check nothing broke, then killed partway through
because it was taking too long (RAG and agent tests call real APIs). The
partial output showed roughly six failures in the last 15% of the run —
after everything this piece touched, which was confirmed separately with a
targeted run of `test_uploads.py`, `test_notifications.py`,
`test_admin_role.py`, `test_settings.py` and `tests/phase5/test_agents.py`,
133 of 133 passing. So these failures exist somewhere else in the suite and
were not caused by Piece 32, but their exact names and cause are still
unknown. **Next session: run the full suite to completion (redirect output
straight to a file rather than through `tail`, so progress can be read while
it runs) and find out what they are** before assuming the rest of the app is
clean.

**T-121 · Anything sticky now has to know the top bar's height.** Piece 29 put a
sticky bar at the top, so `thead th` sticks at `top: var(--topbar-h)` instead of
`top: 0`, and the modal overlay sits at z-index 100 above the bar's 50. Any new
sticky heading, floating panel or drawer has to do the same, or it will slide
under the bar or be covered by it. The height is the token `--topbar-h`; never
type 58px.

**T-120 · The manual has always promised document uploads the code never did.**
Section 4 says documents must be PDF, JPG or PNG and under 5 MB, and Section 3
says the customer "uploads" them. The app has only ever recorded a type and a
file name — no file is stored anywhere. Found while writing Piece 28's manual
change. **Closed 2026-09-23 by Piece 31**, which makes real uploads true and
Section 4 now describes them as they actually work. Same family as T-113 (the
encryption the manual promises), also closed by this piece.

**T-119 · Gemini is much slower late at night.** Rohit's own measurement,
2026-09-22/23: at 3pm a normal chat answer came back in 3 to 8 seconds and only
the manual ones took 70+; at midnight everything took about 75 seconds, and the
logs showed `503 UNAVAILABLE`, "high demand". **Confirmed 2026-09-23 in the
afternoon:** the same admin question that took 75 seconds at midnight answered
in **15 seconds**, correctly. So a slow answer is not necessarily our code, and
B2 (the slow manual answers) must be measured in the afternoon before anyone
concludes anything. It also means **demo rehearsals should happen at the hour
the demo happens.**

**T-118 · "I don't have information about that in the user manual" can be wrong.**
Seen 2026-09-22 while checking Piece 27's manual change. The first time the
chatbot was asked what the administrator can do, it answered with the
out-of-scope sentence, although the paragraph had just been ingested and the
search finds it as the top two results. Asked again, it answered correctly
twice, and Gemini had returned `503 UNAVAILABLE` ("high demand") during the
run. So a wrong "not in the manual" is a real possibility in a demo, and it
looks like a confident answer rather than a failure. Ask the same question
twice before believing it. The same answers took 78 and 189 seconds, which is
B2.

**T-117 · Any new address that changes something must not use plain `get_current_user`.**
Found 2026-09-22 while building Piece 27. Most services only restrict customers
and treat everyone else as staff, so a new action guarded by `get_current_user`
alone would let the admin do it. Actions use `require_staff`, `require_manager`
or `require_business_actor` (customer or staff, never the admin). Views use
`require_staff_view` or `require_audit_view`. `tests/ours/test_admin_role.py`
lists every action; add new ones to it. Pieces 28 to 38 add many addresses.

**T-116 · Streamlit treats the admin like a customer.** `frontend-streamlit/app.py`
only knows the three old roles, so an admin there sees "My applications" and
the customer's form. Nothing unsafe, because the API refuses every action with
a 403, but the labels are wrong. Left alone on purpose: Streamlit is its own
iteration (Rule 5), and the demo uses React.

**T-115 · Staff sign-up accepts a role, so an "admin" could register themselves.**
Found 2026-09-22 while planning Piece 27. `POST /auth/register` takes an optional
`role` and only refuses `applicant` and `branch_manager`
(`auth_service.py:42-45`). The moment `UserRole.admin` exists, it must refuse
`admin` too. **Fixed in Piece 27 (`v2.10.0`)**: it now answers 422, and a test
checks it.

**T-114 · Aadhaar numbers may not be stored in full.** UIDAI requires the first 8
digits to be masked before any copy is stored. Store `XXXX XXXX 1234` only, and
black out those digits on stored images, TEST documents included. Pieces 33–34.

**T-113 · The manual promises encryption that doesn't exist.** Section 10 said
"Financial data is encrypted at rest," which was never true. **Closed
2026-09-23 by Piece 31**: uploaded documents are now genuinely Fernet-encrypted
before they touch disk, in both storage folders, and Section 10's wording now
says exactly that rather than the old, wrong, broader claim.

**T-112 · The project lived inside OneDrive.** Everything in it, including
`loan_app.db`, was copied to Microsoft's cloud automatically. **Moved
2026-09-23** to `C:\LAMS\loan-management-two`, outside OneDrive — this part
is closed. What was still open, where uploaded files should live, is
answered in the Settled entry "Piece 31 — two upload folders" above:
`UPLOAD_DIR_SAFE` inside the project (tracked by git), `UPLOAD_DIR_SENSITIVE`
outside it, chosen automatically per file rather than a single fixed rule.

**T-111 · The chat's document tool description lists only 5 types.** The MCP
`upload_document_metadata` docstring (`mcp_server/mcp_app.py:173`) leaves out
`vehicle_quotation`. It's harmless (the API accepts it), but the AI may think
auto loans can't get that document.

**T-110 · Customer-typed text reaches the AI unmarked.** The loan purpose goes
straight into the chatbot's application lookup (`agent/tools.py:143`). A
customer could write instructions there ("ignore your rules…"). The fix is
"spotlighting": wrap customer text in clear markers and tell the agent that it's
information, never instructions. Worth doing alongside Piece 37.

**T-109 · Existing EMIs have no upper limit at signup.** `existing_monthly_emi`
is only `>= 0`. A typo can put in any size of number, and it moves
affordability (D-27). A Piece 26 item.

**T-108 · Gemini's free tier and personal data.** Google's terms for unpaid use
say it may use what we send to improve its products, people may read it, and
"Do not submit sensitive, confidential, or personal information." The chatbot
already sends seed customers' names, incomes and CIBIL scores. Fine for fake
data, but **no REAL document (image or text) goes to Gemini** (settled
2026-09-22). TEST documents may. A paid tier or a private model would change
this, as one setting.

**T-106 · The chatbot treated "how do I contact the bank?" as out of scope, and made up a hotline.**
Found 2026-09-22 while checking Piece 25. The agent's prompt told it to refuse
anything not about loans, so it never searched the manual and answered "call
our customer service hotline", a number that doesn't exist. Fixed in
`agent/prompts.py` (contact questions go to the manual; never invent phone
numbers, websites or emails) and in the `search_loan_policy` description. It
now answers "support@bank.com" from the manual. Worth remembering for any new
kind of question: if the prompt's scope rule doesn't mention it, the agent may
refuse it instead of searching.

**T-107 · The Wipro laptop needs a `git pull` and its own re-ingest before it
shows Piece 25.** Its `chroma_db/` still holds the old manual ("cannot be
modified after submission"), and its database lacks the new table until the
backend restarts on the new code. Steps: pull, restart the backend (it creates
the table and triggers by itself), then `venv\Scripts\python.exe -m rag.ingest`.

**T-105 · SQLite checked almost nothing by itself before Piece 25.**
Found 2026-09-22. It ignores `VARCHAR(500)` (a 5,000-character purpose would
have been stored), it doesn't check that a status or loan type is a real one,
and foreign keys are off on purpose (T-03). Only "not empty" was enforced. Piece
25 adds the database's own checks for `loan_applications` (triggers) and the new
edit-request table (CHECK rules), all built from `rules.py` in
`backend/app/db_checks.py`. The other tables still have none. That's Piece 26.

**T-104 · The support address lives in two places.** `support@bank.com` is a
placeholder for the **loan officers' inbox**, for writing to staff directly. It is
not a help address: the page and the manual both send questions to the Assistant
first (Rohit, 2026-09-22). It is shown on the customer's application page (`SUPPORT_EMAIL` in
`frontend/src/utils/editRequests.js`, Piece 25 step 3) and written in the user
manual so the chatbot can quote it (step 5). When the real address is known,
change both together and re-ingest the manual, or the chatbot and the screen
will give different addresses.

**T-103 · A pop-up with a text box in it loses focus on every keystroke,
unless its `onClose` is stable.** Found 2026-09-22 while planning Piece 25.
`Modal.jsx` re-runs its focus effect whenever `onClose` changes, and every
current caller passes a fresh inline arrow function. None of today's pop-ups
has an input, so it has never shown. The edit-request pop-up does, so its
`onClose` must be wrapped in `useCallback`.

**T-102 · Ingesting a shorter manual leaves old chunks behind.** Found
2026-09-22. `rag/ingest.py` saves chunks under fixed ids (`chunk_0`,
`chunk_1`, ...) and overwrites them, but never deletes ids past the new count.
If an edit makes the manual shorter, the old tail chunks stay searchable. For
Piece 25 that would mean the old "cannot be modified after submission" text
lives on, and the chatbot could still quote it. **Fixed 2026-09-22** (Piece 25 step 5): ingestion now deletes any id not in the new set. Tested offline in `tests/ours/test_ingest_stale_chunks.py`.

**T-101 · A review only works when the backend is on port 8000.**
Found 2026-09-11 while verifying the audit fixes against a running server. The
Phase 5 agents and the Phase 3 tools do not read the database directly — they
call the Phase 1 API over HTTP, exactly the way a browser would, at the address
in `API_BASE_URL` in `backend/.env`, which is `http://localhost:8000`.

Start the backend on any other port and everything that touches the database
through the API degrades: "assess application 7" answers *"The loan system's API
is unavailable right now"*. That is the correct behaviour and it points at the
wrong cause if you do not know this. The app itself answers fine on the other
port; only the AI's own reads fail, because they go back out through the front
door.

Worth keeping because it looks exactly like a broken review. `start-app.ps1`
uses 8000, so this only bites when starting uvicorn by hand.

**T-100 · A React component that throws while rendering takes the whole page, not its own card.**
Worth knowing before writing another dashboard card. An exception inside a
component's render is not caught by the `try` around the fetch that loaded the
data — by then the request has already succeeded. React unmounts the entire tree
above it and the page goes white, so one optional field on one card can cost a
manager the whole dashboard.

This is why `MorningBriefing.jsx` guards fields the server's schema marks
required (D-25). The cheap habit: anything read out of a response with `.split`,
`.map`, `.length` or a nested property gets a `?.` or a `|| {}` even when the
schema says it cannot be null, because the schema describes the server and the
component renders whatever actually arrived.

**T-99 · A stored string does not fix itself when the code that wrote it changes.**
Found 2026-09-11, fixing the eligibility timestamp. The fix to
`build_summary_text` was correct and it changed nothing that any demo would
show, because every application already in the database still carried the old
text. Fourteen of them.

The general shape: **a bug in code that generates stored text is two bugs.** One
in the generator, one in every row it already wrote. Fixing only the first is
how a fix gets reported as done and the screen keeps showing the old thing. The
check takes one query — search the column for the pattern you just removed — and
the repair went next to the column-adding step in `init_db()`, which is already
where this project does one-time data repair (D-18).

**T-98 · The review path was the only AI path in the product that could raise.**
Every other one degrades: Phase 5's agents fall back to deterministic summaries,
the briefing falls back to plain figures and says `written_by_ai: false`, the
chat falls back from agent to manual chain to an honest "nothing is available".
The review branch in `chat.py` called the graph outside any `try` and then read
`state["risk_assessment"]` and its keys directly.

The docstring justified that by saying the caller returns early when data
collection fails. True, and insufficient: it covers the failures the graph
*records* in `state["errors"]`, not the ones that escape it. The agents' own
`try` blocks only wrap their LLM calls — the plain-Python computation before them
is unguarded, so an applicant record missing a field raises straight out of the
graph.

Now wrapped, and the rule worth keeping: **a path is not "safe because the
caller checks" unless the caller checks the thing that actually goes wrong.**
Errors a system reports are the easy half. What reaches a screen as a 500 is
always the other half.


**T-97 · A raw UTC timestamp handed to a model reintroduces the 5.5-hour bug through a door `UtcDateTime` cannot guard.**
Cited by `agent/tools.py` since audit phase 1 and written up here afterwards.
The API sends UTC with a `Z`, which is exactly right for a browser, because the
browser converts it. A model does not convert anything — handed
`2026-09-05T20:13:55Z` it reads the UTC wall clock aloud as though it were local
time, so the chat tells a customer their application was submitted at 8pm when
the app says 1:43am the next day.

`UtcDateTime` protects the API's own responses and cannot reach inside a
sentence built for a prompt. So `_readable_time()` formats the date before it
goes in, and drops the time of day rather than converting it — the time of day
is not what anyone asks about here, and converting it would need this layer to
decide a timezone it has no business deciding.

Same family as T-99 and the eligibility fix: one instant, formatted once, at the
place it is read.

**T-96 · A stored enum handed to a model comes back out in a sentence.**
Cited by `agent/tools.py` since audit phase 1 and written up here afterwards.
Everything those tools return is read twice — by the model, which reasons over
it, and then by a person, because the model echoes the words it was given. Hand
it `id_proof` and "id_proof" appears in a sentence addressed to a loan officer.

Fixed by translating at the point the tool builds its answer. Audit phase 2 then
found ten copies of that translation across the backend, all doing it slightly
wrong ("Id proof"), and replaced them with one shared helper — see D-23.


**T-94 · A model handed a bare number invents a currency, and it picks dollars.**
Found 2026-09-11, in the first real review Rohit ran. The decision maker's prompt
passed `amount_requested` straight through, so the model saw `4000000.0` and
wrote **"$4,000,000.0"** — dollars, on an Indian home loan, with a stray decimal.
The verdict and every number were correct; only the sentence a loan officer
actually reads was wrong, which is the worst place for it.

A model fills a missing unit with whatever is most common in its training data,
and that is dollars. The unit has to be *in* the prompt, not assumed. Fixed by
formatting the amount with `format_rupees()` before it reaches the model, plus
one line telling it this is an Indian bank and never to use a dollar sign. It now
writes "₹40,00,000" — correct lakh grouping, because the prompt showed it that
way.

The risk assessor already did this correctly (`risk_assessor.py:82`), which is
why the EMI always displayed properly. Worth checking any new prompt against
this: **every number going into a prompt needs its unit attached.**

**T-95 · The app-wide 15 second timeout is too short for the assistant.**
The chat's first real review answered in 25 seconds and the browser had already
given up at 15 — an axios default set on the shared client in
`frontend/src/api/client.js`, sensible for the database reads that make up
almost every other request in this app, and simply the wrong measuring stick for
four agents doing real work.

The assistant now passes its own `CHAT_TIMEOUT_MS` of 90 seconds, about three
times the worst real measurement, leaving room for the key ladder to retry
across a couple of keys on a bad day. Deliberately *not* unlimited: if the
backend dies mid-review, or a provider accepts the connection and never answers,
an unlimited wait spins forever with no error and no way out but a page reload.
Slow is normal on that screen; infinite is still not.

**T-92 · The review trigger is anchored to the whole message, and that is the whole design.**
`app/services/review_request.py`, added 2026-09-11. A review costs two AI calls
and about ten seconds, so it must run when someone asks for it and never
otherwise. The pattern requires the message to *start* with one of four verbs
and contain nothing but the instruction:

    "assess application 7"            -> runs a review
    "what happened to application 7"  -> does NOT

Both contain "application 7". An unanchored search would fire on both, which
means a plain question would sometimes cost ten seconds. Anchoring is what
separates them, and it is why this is a phrase check rather than a tool the
model may choose — a model given the choice does not answer the same question
the same way twice, and an unpredictable ten-second branch is the worst thing
to have on stage.

Checked against all seventeen chat messages in the existing test suite before
building: none begins with a trigger verb, so nothing already written changed
behaviour. `reject application 7, income too low` is the near miss, and it fails
on both the verb and the trailing text.

**A copy of the pattern lives in `frontend/src/pages/Assistant.jsx`** (as
`REVIEW_PHRASE`), used only to decide whether to show the "about ten seconds"
line while waiting. Change one, change the other — there is a comment in both
saying so.

**T-93 · A failed review is not an AI failure.**
When a review cannot run — bad application number, a 403, the API down — the
chat answers 200 with the reason in plain words and leaves `ai_status` as
`ai_ok`. Setting the D-20 codes there would make the amber notice say "the AI
has reached today's limit" about a typo, which is worse than saying nothing.
The AI codes describe the *model* misbehaving; everything else is ordinary
product behaviour and reads as such.

**T-91 · An activity row with a type but no number printed "Chat #null".**
Spotted by Rohit on the manager's activity page, 2026-09-11. Mine, from the day
before. The chat rows were written with `entity_type="chat"` and no
`entity_id`, and `Activity.jsx` printed `` `${type} #${id}` `` whenever a type
was present — so eight rows read `Chat #null`. Every other action type has a
real number, which is why it had never shown up before.

Fixed in both places, and the second half is the one that matters:

- The page now prints the number only when there is one, so no future row can
  reproduce this.
- **`chat_action_confirmed` now files itself under the application it changed**,
  not under "chat". A confirmed change always knows its application number, and
  someone auditing application 3 wants that row to appear against application 3.
  Filing an AI-made change under a conversation with no number hides it from
  precisely the person looking for it.
- `chat_message` now stores no `entity_type` at all, so it shows a dash. A
  question genuinely is not about one numbered record — it may touch several or
  none — and a dash is honest where an invented number would not be.

The general rule worth keeping: **never claim an entity type without an id.**
The pair travels together or not at all.

**T-90 · A ReAct tool with several required arguments fails before its own code runs.**
Found 2026-09-11, by Rohit trying the confirmation flow in the browser and
getting "No AI is available at the moment" — which was true of nothing: all
three keys worked and the model answered correctly.

The ReAct format has exactly one `Action Input:` line, so for a tool taking
several arguments LangChain hands **the whole thing to the first parameter**
and leaves the rest empty. With required parameters, pydantic then rejects the
call before the function body is reached, the agent raises, and the chat's
own error handling reports it as an AI failure. `agent/tools.py` already
documented the single-argument version of this; nobody had hit the
multi-argument version because Phase 3's tools are all read-only and simple.

**Two things were needed, and only doing one of them is not enough.** Every
parameter after the first now has a default, so the call actually lands; and
`_unpack()` in `agent/write_tools.py` sorts out what the model meant. The
defaults look sloppy in isolation and are load-bearing — there is a comment
above each saying so.

A real Gemini model was observed writing **six** different shapes for the same
call, all now handled and pinned by tests:

    {'application_id': 1, 'new_status': 'approved', ...}     python dict
    {"application_id": 1, ...}                               json
    application_id: 1, new_status: approved, ...             bare, colons
    application_id=1, new_status=approved, ...               bare, equals
    application_id='1', new_status='approved', ...           equals, quoted
    1, approved, documents all verified                      positional

Splitting is done on commas that sit immediately before another known field
name, so a comma inside a reason ("income too low, and no collateral") stays in
one piece rather than being torn across two fields. Positional values are only
trusted when the count matches exactly — guessing which value is the
application number is how the wrong loan gets approved.

**T-89 · `GOOGLE_API_KEY` takes exactly one key. Extra keys go on `GOOGLE_API_KEYS`.**
Found 2026-09-10. Three keys had been pasted into `GOOGLE_API_KEY` as one
comma-separated string, so the whole 147-character blob went to Google as a
single key and every live AI call failed with `400 API key not valid`. Phase 3's
live tests all failed on it. The fix is just to put one key on that line and the
spares on `GOOGLE_API_KEYS=`, comma-separated.

**A correction worth keeping, because I got this wrong and Rohit was right.**
I first claimed two of the three were not API keys at all — they are 53
characters starting `AQ.Ab8RN`, and I asserted from that shape alone that they
were OAuth tokens. Rohit pushed back, saying AI Studio had labelled them API
keys. He was correct. Asking Google directly — a `GET /v1beta/models?key=…`,
which validates a key without spending generation quota — all three came back
`WORKS`, 50 models visible each.

So **Gemini API keys come in more than one shape**: the familiar 39-character
`AIza…` and a newer 53-character `AQ.…`. Do not judge a key by its prefix or
length, and do not tell someone their key is invalid without testing it. The
one-line check, kept for reuse:

    GET https://generativelanguage.googleapis.com/v1beta/models?key=<the key>

The rotation code needed no change — it splits `GOOGLE_API_KEYS` on commas and
treats `GOOGLE_API_KEY` as a single value, which is right either way, since a
key containing a comma is not a thing.

**T-88 · `PyJWT` is missing from `requirements.txt`, so two of our own tests cannot be collected.**
Found 2026-09-10 on a clean install. `tests/ours/test_chat_uses_agent.py:15` and
`tests/ours/test_agent_acts_as_caller.py` both `import jwt`, which is **PyJWT** —
but `requirements.txt` installs `python-jose[cryptography]` instead, and the two
are different packages that happen to do the same job. On the machine where
those tests were written, PyJWT must have been present by accident (pulled in by
something since removed, or installed by hand). On a fresh venv it is not, so
`pytest tests/ours` stops at collection with `ModuleNotFoundError: No module
named 'jwt'` and **takes the whole folder's other tests down with it**, which is
how a green suite hides two red files.

Not caused by Piece 23 — confirmed by running Phase 1 (27 passed) and the two
LLM files (35 passed) separately.

**Fixed the same day** (Rohit: "resolve it yourself"). Both files now do
`from jose import jwt` instead, which is the library the app itself already
signs and verifies with in `app/utils/auth.py:15`. `jose.jwt.decode` takes the
same arguments as PyJWT's, so it was a one-line import change in each file and
no test logic moved. Chosen over adding `PyJWT` to `requirements.txt` because
one JWT library in a project is better than two that do the same job — a second
one is a thing to keep in step, and a way for a test to pass against a library
the app never uses. `pytest tests/ours` now collects everything: **68 passed**,
up from 55, so those 13 tests ran for the first time on a clean install.

### From the Wipro laptop survey (2026-09-09)

A fresh session ran the eight-section survey on the Wipro machine. Most of what we
braced for was not there: no proxy, no TLS interception, PyPI, the npm registry,
GitHub over HTTPS, Gemini and LangSmith all directly reachable, and ports 8000,
5173 and 8501 all free and bindable as a non-admin. The findings below are what
did come back.

**T-78 · The Wipro laptop needs Python 3.12 — settled 2026-09-09, corrected same day.**
That machine defaults to 3.14.5 and has a per-user 3.13; `py -0p` confirmed no
real 3.11 exists (the 3.11.15 the survey saw lives only inside another project's
`venv\` folder, which cannot seed a new environment). 3.12.6 is now installed.

**The real reason 3.14 fails is Pillow, not numpy.** My first answer here blamed
`numpy==1.26.4`, whose Windows wheels stop at 3.12 — but numpy is not pinned in
`requirements.txt` at all. It is a transitive dependency, and 1.26.4 is merely
what pip happened to pick on this laptop long ago. On a newer Python, pip would
have resolved a newer numpy quite happily. Caught by actually running the
resolver instead of reasoning about it.

What actually breaks: **streamlit 1.36.0 requires `pillow<11`, and Pillow first
published Windows builds for 3.14 at 11.3.** Nothing satisfies both, so pip halts
with `No matching distribution found for pillow<11,>=7.1.0`. A hard wall, not a
slow compile.

Verified by resolving the whole file against three interpreters with
`pip install --dry-run --only-binary=:all: --python-version X`:

| Python | Result |
|---|---|
| 3.12 | all 180 packages resolve as ready-built wheels |
| 3.13 | also resolves cleanly — a genuine fallback |
| 3.14 | fails on Pillow |

So 3.12 is the recommendation and the environment is created with
`py -3.12 -m venv venv` so the 3.14 default is never picked up. **3.13 is a
working backup**, which matters because it is already on that machine. No pins
change and no code changes. The existing per-user 3.13 install also proves the
company catalogue installs without admin rights.

**The lesson worth keeping:** a version number sitting in a `pip list` is not a
constraint. Only what is written in `requirements.txt` is. I read the installed
numpy as though it were pinned and built a recommendation on it, and the
recommendation happened to survive for a completely different reason.

**T-79 · The Ollama models there are not the ones our config names.** The laptop
has `nomic-embed-text:v1.5` and `qwen3.5:0.8b`. Our `.env` and `config.py` default
to `nomic-embed-text` (no tag) for embeddings and `llama3.1` for chat. The
embedding name is one tag away; the chat model is a different model entirely and
much smaller. Fix on our side by setting `OLLAMA_CHAT_MODEL` and
`OLLAMA_EMBED_MODEL` in that machine's `.env`, not by pulling models there.

**T-80 · Do not move the ports.** All three of ours are free on that machine.
`tests/phase3`, `tests/phase4` and `tests/phase5` each hardcode
`http://localhost:8000/health` in their `conftest.py`, so changing the backend
port would break the trainer's own test setup for no gain. Leave them.

**T-81 · Two things the survey could not establish.** It only tested binding on
loopback, never on all interfaces, so whether Windows Firewall prompts on a real
`uvicorn` start — and whether Rohit can approve that prompt himself — is still
unknown. And Cortex XDR is running as the corporate endpoint protection; nothing
tested it against a live dev server or against a folder filling with `node_modules`.
Both are first-run risks, not blockers.

**T-87 · Two separate LangSmith problems, only the first one was ever about
certificates — found and partly fixed 2026-09-09.**

**Problem one, fixed: Python's own certificate list, not a corporate block.**
A plain `requests.get("https://smith.langchain.com")` failed with
`SSLCertVerificationError: unable to get local issuer certificate`, while every
other HTTPS call this project makes (Gemini included) worked fine. Before
assuming a corporate proxy and giving up, this got tested properly: PowerShell's
`Invoke-WebRequest` to the exact same URL succeeded, which means **Windows'
own trust store already trusts the site fine** — only Python's separate,
bundled certificate list (`certifi`) didn't. Not a network block at all, and
not something admin rights would even be relevant to. Fixed by installing
`pip-system-certs` into `backend/venv` — it makes Python defer to the OS trust
store instead of carrying its own. One-time, no admin, done. Not yet added to
`requirements.txt`; small enough that it can be, once confirmed it does not
slow down every other HTTPS call in the app (initial evidence says no — the
real Gemini calls during this same run took normal time).

**Problem two, fixed: the API key itself had a typo.** With the certificate
check out of the way, `GET /sessions` against LangSmith's API came back `403
Forbidden` — which looked exactly like a permissions or workspace problem on
the LangSmith account, and cost an expensive lesson finding that out:
LangSmith's tracing client queues trace uploads on a background thread and
retries hard when refused, and pytest waits for that queue to drain before the
process can exit. The single test file `tests/phase2/test_observability.py`
took **68 minutes** to finish 3 tests because of this — nothing was frozen, it
was retrying the entire time. The actual cause was much simpler: Rohit had
mistyped one digit in `LANGCHAIN_API_KEY`. Corrected, then verified cheaply
first — a direct `client.list_runs(limit=1)` call with no retry loop around it,
confirming the key before spending another hour re-running the test file. Once
confirmed, `tests/phase2` ran clean: **22/22 in 66 seconds.**

**Worth keeping as a general habit:** when a slow, retry-heavy client fails,
verify the fix with the cheapest possible direct call first, not by re-running
the expensive thing that found the problem.

**T-86 · This laptop's Node was 18.20.3; the front-end needs 20+ — found and
fixed 2026-09-09.** `npm run dev` failed immediately with a `node:util` import
error, because Vite 8 (and its bundler, rolldown) requires Node ^20.19.0 or
>=22.12.0. `nvm-windows` was already on the machine, but `nvm use` silently
failed to switch the active version — nvm-windows needs either Administrator
rights or Windows "Developer Mode" to create the symlink it switches on, and
neither was available. Rohit installed **Node JS v22.17.1** through the Wipro
self-service software catalog instead (those installs run elevated already, so
no admin prompt on his side), which lands in `C:\Program Files\nodejs` without
touching the existing Node 18 install or needing PATH changes system-wide.
`node_modules` had to be deleted and reinstalled once Node 22 was active, because
the native `rolldown` binding npm had fetched under Node 18 was for the wrong
platform target. `start-app.ps1` puts `C:\Program Files\nodejs` first on PATH
for its own windows only, so the system default Node is never touched.

**T-85 · `setuptools` 81+ deletes `pkg_resources`, and `opentelemetry-instrumentation`
still imports it — found and fixed 2026-09-09.** A clean `pip install -r
requirements.txt` on a fresh venv pulled setuptools 84.0.0 (nothing in the file
pins it), and the backend failed to start at all:
`ModuleNotFoundError: No module named 'pkg_resources'`. `pkg_resources` was
deprecated for years and setuptools finally dropped it. Fixed by pinning
`setuptools<81` in `requirements.txt`, which still bundles it. Same lesson as
T-78's numpy finding: an unpinned transitive dependency is a ticking clock, not
a fixed fact, and it only goes off on a fresh install.

**T-84 · The provider fallback is automatic for chat and deliberately manual for
embeddings — 2026-09-09.** Rohit asked for the Gemini-to-Ollama switch to happen
by itself, because editing `.env` and restarting mid-demo is not possible. Built
in `get_llm()` using LangChain's own `.with_fallbacks()`, which retries on the
second model on any exception — right for us, since a dead quota, a network block
and a withdrawn model all look different but all mean "ask the other one".

**Embeddings deliberately do NOT do this, and nobody should later "fix" the
inconsistency.** Each provider's vectors live in their own ChromaDB collection
(`poc_01_loan_manual` vs `poc_01_loan_manual_ollama`, per T-46), and Gemini's
embedding model returns 3072 numbers per chunk against Ollama's 768. If
embeddings switched silently, the retriever would search a collection that in
most cases does not exist, and the chatbot would answer from nothing at all —
confidently, no error, no sources. Verified on this laptop: only the Gemini
collection exists here, 42 chunks at 3072 numbers, so that failure mode is live
rather than theoretical. A visible failure beats a confident wrong answer.

Three more decisions inside it, each with a reason:

- **One direction only.** If `.env` names Ollama, Gemini is never called behind
  the user's back. Choosing the local model is usually a privacy or network
  choice, and quietly overriding it would be the worse surprise.
- **The fallback is only attached if Ollama actually answers**, probed with a
  one-second HTTP GET. Otherwise every Gemini failure would become two failures
  and twice the wait.
- **`check_ready()` passes `fallback=False`.** A health check that passes because
  the *other* provider answered reports the opposite of what was asked.

Proved by pointing Gemini at an invalid key with a stand-in Ollama running: the
question failed on Gemini and came back answered by Ollama, no restart. Eight
tests in `tests/ours/test_llm_fallback.py` hold it in place and use no AI quota.

**T-83 · The Ollama fallback could never have run — fixed 2026-09-09.**
`llm_provider.py` imports `langchain_ollama` on its Ollama branch and always has,
but the package was never listed in `requirements.txt` and was not installed in
this laptop's venv either. So the fallback that exists specifically because
"Gemini was blocked on the company network for six weeks" would have died on
`ModuleNotFoundError` the first time anyone actually needed it — on the Wipro
machine, where Ollama is the whole point. It went unnoticed because every test
and every run so far has used Gemini, so that branch of the `if` had never once
executed.

Fixed by pinning `langchain-ollama==1.1.0`, the version whose `langchain-core`
floor (>=1.2.21) our pinned 1.6.2 satisfies. Installing it added three packages
(`langchain-ollama`, `ollama`, `httpx2`) and changed no existing pin; `pip check`
reports nothing new. Proved the branch now builds by constructing both objects
with the Wipro laptop's exact model strings, and confirmed it selects the
separate `poc_01_loan_manual_ollama` collection so the two providers' vectors
still cannot mix (T-46).

**Worth generalising:** a fallback path that no test exercises is not a fallback.
Nothing about this project's green test suite could have caught it, because the
suite never sets `LLM_PROVIDER=ollama`.

**T-82 · The corrupted git repo there is not ours.** `git fsck` found a tree
pointing at a missing blob in `C:\New Folder\Desktop\AI Readiness Project`, which
is a different project in a different folder. A fresh clone sidesteps it entirely.
Worth knowing only so nobody spends time repairing it.


### From the Phase 1 test spec

**T-01 · The 401 vs 403 trap.** FastAPI's built-in bearer token helper returns **403** when the Authorization header is missing. Test `TC-01-P1-API-06` asserts **401**. Fix: turn off the automatic error and raise the 401 ourselves.

**T-02 · The trailing slash trap.** All tests call `/api/v1/applications` with no trailing slash. A route declared as `"/"` under a prefix becomes `/api/v1/applications/` and answers with a redirect. Fix: declare route paths as `""`.

**T-03 · Do not turn on SQLite foreign keys.** Tests `DB-02` and `DB-04` create a loan application pointing at applicant ID 1, which doesn't exist. Switch foreign keys on and both tests fail.

**T-04 · Cascade delete has to be at the ORM level.** `DB-04` deletes an application and expects its documents to vanish. Because of T-03 the database enforces nothing, so SQLAlchemy must be told to cascade on the relationship.

**T-05 · Login takes JSON, not a form.** The test fixture posts JSON with email and password and reads back `access_token`. The OAuth2 form from tutorials breaks every authenticated test at once.

**T-06 · Module paths and function names are fixed by the tests.** `app.utils.finance.calculate_emi(principal, annual_rate, tenure_months)`, `app.services.application_service.validate_status_transition(current, new)` returning True or False, `app.services.applicant_service.create_applicant(db, data)`, and the schema names `CreateApplicantSchema`, `CreateApplicationSchema`, `CreateDocumentSchema`.

**T-07 · `User` and `Applicant` are two different tables.** User is who logs in, Applicant is who borrows.

**T-08 · The trainer's test file uses fixtures it never defines.** `db_session` and `test_user`. We write them.

### From the Phase 1 contradiction sweep (2026-09-05)

**T-15 · Three different test folder layouts.** The Phase 1 doc says `tests/test_unit/` and `tests/test_api/`. The test spec's commands say `pytest tests/ -k "P1"`. The associate guide and the **reviewer guide** say `tests/phase1/`. The reviewer runs `pytest tests/phase1/`, so that is the one that counts.

**T-16 · The Phase 1 doc's folder listing has no `user.py`,** but its own auth code imports `app.models.user.User`. We create it.

**T-17 · The CORS port is wrong for us.** The doc allows only `http://localhost:3000`. Vite runs on **5173**. Get this wrong and React cannot reach the API at all. Allow 5173.

**T-18 · Bad filter value: spec says 400, FastAPI gives 422.** Not tested either way. Follow the user story: check it ourselves and return 400.

**T-19 · The applicant endpoints have no user story.** But the test fixture needs `POST /applicants`, and Phase 3 needs `GET /applicants/{id}`. Build both.

**T-20 · Test database: file, not in-memory.** The test spec's own setup uses a file, `test.db`. Follow it.

**T-21 · Request IDs can collide.** The doc builds them from the millisecond clock. Use a UUID.

**T-22 · `associate_id` is missing from the doc's middleware.** The observability guide requires it in every log line. Read it from the settings file.

**T-23 · Applicant signup creates two rows.** A `User` row to log in and an `Applicant` row as the borrower profile, linked. Manual Section 3 Step 1 confirms it.

**T-24 · Session expiry wording.** Manual says 24 hours of *inactivity*. A JWT expires 24 hours after *issue*. Reword the manual in Phase 2.

**T-25 · The manual describes file rules the system doesn't enforce.** PDF/JPG/PNG, 5MB max. Phase 1 stores only a filename. Becomes real when actual upload is added.

**T-26 · The manual promises things the system doesn't have.** Co-applicants and automated notifications. Build later or trim the manual in Phase 2. Both in `FUTURE-UPGRADES.md`.

### From working through the Phase 5 scoring

**T-13 · Rejecting on score alone is almost impossible.** Lowest possible score is 35. Reject is below 40. Only one combination reaches it: bad credit **and** unemployed **and** unaffordable EMI together. To demo a rejection, the applicant needs all three.

**T-14 · There are only two "medium" risks, and both are defined.** Medium credit risk is CIBIL 650 to 749. Medium employment risk is salaried under 2 years or self-employed. Nothing is undefined.

### From designing the dashboard (2026-09-06)

**T-38 · The trainer's five status colours cannot be used in a pie chart.** Ran them through a colour-accessibility validator against a white surface. Side by side as bars, only one pair is weak: green and red measure ΔE 5.0 apart for a viewer with red-green colour blindness, which a written label beside each bar fully mitigates. But in a pie or donut every colour sits against every other, and there the numbers collapse: **purple vs blue measure ΔE 0.4 under red-green colour blindness** (indistinguishable), and **red vs orange measure ΔE 8.7 with normal colour vision** (below the 15 floor — hard for anyone). So the pipeline chart is horizontal bars with written labels, never a pie. Loan type uses a single blue shade instead, because on that chart colour means quantity, not identity. Worth saying out loud in the demo if accessibility comes up.

**T-39 · Every date and time in the app was 5 hours 30 minutes early.** Found by Rohit on 2026-09-06, and it was real. SQLite records `CURRENT_TIMESTAMP` in **UTC** and hands it back as a plain date and time with nothing saying so — `DateTime(timezone=True)` does not change this, because SQLite has no timezone support. The API passed that straight out as `2026-09-05T20:13:55`, and a browser reads a string with no timezone marker as *the reader's own local time*. In India that showed the wrong day, in the evening instead of the small hours.

Fix: a shared `UtcDateTime` type in `schemas/common.py` that stamps naive database times as UTC on the way out, so the API now sends `2026-09-05T20:13:55Z`. The browser converts that to real local time, and the app is also correct for a reader in another country. Guarded by `tests/ours/test_timestamps.py`, including a test that the recorded time is actually within a minute of now.

**Watch for this again in Phase 2 onwards:** any new response field holding a time must use `UtcDateTime`, not `datetime`.

### From building the list (2026-09-06)

**T-60 · Windows lets two servers bind port 8000, and the stale one answers.** A sharper version of T-40. After adding the chat route, `/api/v1/chat` was missing from `openapi.json` even though `main.py` clearly included the router and a fresh `TestClient` served it fine. The cause: `netstat` showed **two** processes LISTENING on 127.0.0.1:8000. An earlier uvicorn had survived a `Stop-Process`, a second one started alongside it, and requests were being answered by the old one. On Linux the second bind would simply fail; Windows allows it.

The check, whenever the API behaves like yesterday's code:

```bash
netstat -ano | grep ":8000" | grep LISTENING     # more than one line is the bug
```

Kill every uvicorn before starting one:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*uvicorn*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

**T-40 · A backend running without `--reload` makes new code look broken.** Found while testing Piece 18. The server had been left running from an earlier session as `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` — no `--reload`, and using the machine's Python rather than the project's virtual environment. So every new query parameter was silently ignored: a search returned every row, and a deliberately invalid sort column answered 200 instead of the 400 the new code raises. Nothing was wrong with the code at all.

The quick way to tell, before doubting the code: open `http://localhost:8000/openapi.json` and look at whether the parameters you just added are listed. If they are not, the running server is old. Start it the way the README says, from `backend/`:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

**T-41 · Sorting a paged list in the browser is wrong, not just slower.** The list hands back 20 rows at a time. Sorting those in the browser orders the page, not the data, so "largest amount first" shows the largest of *this page* while a bigger one sits on page 3 — with an arrow next to the column implying otherwise. Sorting and searching both belong on the server for any list that is paged. Proved on the seed data: sorting by amount brings a ₹40,00,000 application onto page 1 from page 2.

### From inspecting the whole app (2026-09-06)

**T-42 · Styling scoped to `form` silently skips the filter toolbars.** The stylesheet said `form input, form select, form textarea`. Both filter toolbars — applications and activity — are plain `<div>`s, not forms, so their dropdowns inherited nothing: no border, no padding, and the little label sat *inline beside* the box instead of above it. On screen it read as a broken page, and it was on the first screen anyone sees. Nothing in the code looked wrong, and the build and lint were clean; only a screenshot showed it. Fixed by styling `input, select, textarea` wherever they appear rather than only inside a form. **Rule of thumb: never scope a control's look to its parent element, because controls move.**

**T-43 · Two things that look broken in a full-page screenshot but are not.** A `position: fixed` modal backdrop and a `position: sticky` sidebar are both painted once, at the window's size. Ask a headless browser for a full-page screenshot of a page taller than the window and both appear to stop halfway down, leaving a white band. In a real browser they are correct. Check the CSS before "fixing" either.

**T-44 · React StrictMode makes every page load its data twice, in development only.** `main.jsx` wraps the app in `<React.StrictMode>`, which deliberately runs every effect twice to expose bugs. So the applications list asks the server twice on load when running `npm run dev`. It does **not** happen in the built app. Worth knowing before chasing a double-fetch that is not there — and worth being able to say out loud in a code walkthrough. Proved separately that the search box's own debounce is correct: typing five letters causes exactly one request.

**T-45 · Irreversible actions had no confirmation.** `rejected` and `disbursed` are both terminal in the status machine — nothing moves out of them — yet both were one click on a dropdown away with no "are you sure". Now each opens a dialog naming the application, the status it is moving from and to, and the remarks that will be recorded. The server was always right; this is about not letting a person destroy something by accident.

### The models the trainer mandated no longer exist (2026-09-06)

**T-51 · `gemini-2.0-flash` is retired, and so is `models/text-embedding-004`.** Both are named all through the trainer's documents, and the program's own FAQ says *"Can I use a different LLM instead of Gemini? No."* Google now answers:

```
404 This model models/gemini-2.0-flash is no longer available.
Please update your code to use models/gemini-3.6-flash
```

Rohit's API key is fine — a dead model returns 404, not an auth error. Asking Google what the key *can* use returned 40 chat models and exactly three embedding models: `gemini-embedding-001`, `gemini-embedding-2`, `gemini-embedding-2-preview`. `text-embedding-004` is not among them. **What we use: `gemini-3.8-flash` for chat and `gemini-embedding-001` for embeddings**, both set in `.env` so they are one line to change. `gemini-3.6-flash` also works but answered in 5.3s against 2.1s, and `gemini-2.5-flash` is closed to new users.

This is worth saying out loud in the demo rather than hiding: the POC was specified against models that were withdrawn, and it kept working because the provider is a setting and not a hardcoded string.

**T-52 · The trainer's pinned `langchain-google-genai==1.0.6` cannot embed at all any more.** Every embedding model returned `504 Deadline Exceeded` through that library, three attempts each, while chat through the same library worked. The same models over plain HTTPS answered in **0.58 seconds**. So it was never the key, the network, or the models — the mid-2024 pinned library talks a protocol Google no longer serves for embeddings. Diagnosed by calling `:embedContent` directly with `urllib` and comparing.

**Fix: the LangChain stack is upgraded off the trainer's pins** — `langchain 1.4.0`, `langchain-core 1.6.2`, `langchain-google-genai 4.4.0`, `langchain-community 0.4.2`, `langchain-chroma 1.1.0`, `chromadb 1.5.9`. Phase 1's 37 tests were re-run immediately after and all still pass, so nothing regressed. The tests check behaviour, not library versions.

**T-53 · `from langchain.text_splitter import RecursiveCharacterTextSplitter` no longer exists.** The Phase 2 spec's `ING-02` uses that path; in LangChain 1.x it is `from langchain_text_splitters import RecursiveCharacterTextSplitter`. Our copy of the test uses the current path. Same class, same behaviour — this is an import move, not a change of meaning. Documented in a comment in the test, the same way `T-36` was.

**T-54 · Good news that cancels the old embedding trap.** `T-10` warned that Gemini and Ollama both produced 768 numbers per chunk, so ChromaDB would silently accept one against the other and hand back confident nonsense. `gemini-embedding-001` returns **3072** numbers. Ollama's `nomic-embed-text` still returns 768, so a mix-up now fails **loudly** with a dimension error instead of quietly. The separate-collection rule in `T-46` stays anyway — it costs nothing and does not depend on the sizes staying different.

**T-55 · The free tier is 5 requests a minute, not the 15 the blueprint promises.** Measured, not assumed: firing eight quick calls at each model, `gemini-3.8-flash` refused after one and named `limit: 5` in the error, and also returned a `503 UNAVAILABLE` (the model itself being overloaded). One question in the generation run stalled for **23 seconds** behind exponential-backoff retries. That is fatal in a demo and painful across a 20-test run that makes an LLM call per test.

`gemini-flash-lite-latest` and `gemini-3.5-flash-lite` both completed **8 of 8** with no refusal at all. **So the chat model is `gemini-3.5-flash-lite`**, pinned to that exact version rather than the `-latest` alias, because an alias can silently move to a different model in the middle of a presentation. Answers came back in about **1.3 seconds** against 2–23 seconds, and all six generation checks still pass, because the job here is reading an answer out of supplied text rather than reasoning from scratch — which is what the lite models are good at.

**T-56 · An empty question crashes the embedding API, not just the retriever.** `retriever.invoke("")` raised `400 Bad Request`: asking a model to describe the meaning of an empty string is not a sensible request and Google refuses it. This showed up as `TC-01-P2-RET-05` failing, but it mattered far more in the chat box, where pressing enter on an empty input crashed the answer instead of doing nothing. Fixed with a small `SafeRetriever` wrapper in `rag/rag_chain.py` that returns an empty list for a blank question without asking anyone. There is nothing to search for, so we do not search.

**T-57 · Embeddings are capped at 100 a minute, and the test suite blew through it.** Separate from the chat limit. The suite ingested the manual four times over — once in the fixture, twice proving no duplication, once more for the span test — and 4 × 42 chunks exceeded the limit, failing `OBS-02` with `RESOURCE_EXHAUSTED`. Rather than paper over it with sleeps, `ingest_manual()` now fingerprints the manual's content (a hash of the text plus the chunk settings) and stores it on the collection. If the fingerprint matches and the collection is already full, the embedding step is skipped and says so in the log. Re-ingesting an unchanged manual now costs nothing. `--force` re-embeds anyway, which is what you want after changing the embedding model or switching provider.

**T-58 · The global OpenTelemetry tracer provider can only be set once per process.** `OBS-02` needs spans printing to the console, but the rest of the suite runs with them off, and flipping the setting inside the test did nothing because the provider had already been fixed by the first test that imported the tracer. Not a bug in our code — an OpenTelemetry rule. The test now runs `python -m rag.ingest` as a **subprocess**, which gets a clean interpreter and, as a bonus, checks the actual command a person would type.

**T-59 · `gemini-3.5-flash-lite` ignores the temperature setting.** It warns: *"uses fixed sampling defaults; the sampling parameter(s) temperature will be ignored"*. The Phase 2 spec asks for temperature 0.1, meaning "be predictable and factual". We pass 0.1 and the model disregards it. In practice this has not mattered — every answer is extracted from supplied extracts rather than composed freely, so there is little to vary, and all six generation tests pass repeatedly. Worth knowing before someone asks why the setting is there, and worth remembering for Phase 3, where the agent wants temperature 0 so it picks the same tool for the same question every time. If tool choice turns out to wobble, that is the first thing to check.

### From reading the Phase 2 contract (2026-09-06)

**T-46 · The provider-suffixed collection name breaks two of the trainer's tests.** Our own safety design (T-10) says each LLM provider gets its own ChromaDB collection, named `poc_01_loan_manual_{provider}`, because Gemini and Ollama both produce 768 numbers per chunk and mixing them fails *silently* with confident nonsense. But `TC-01-P2-ING-04` and `TC-01-P2-RET-01` open the collection by its exact literal name:

```python
collection = client.get_collection("poc_01_loan_manual")
```

A suffixed name fails both instantly. **Fix: Gemini, the default, uses the bare name `poc_01_loan_manual`; only Ollama gets a suffix, `poc_01_loan_manual_ollama`.** Both goals are met — the trainer's tests pass on the default provider, and the two providers still never share a collection. Written into `get_collection_name()` with this reason in a comment, because it looks like an inconsistency otherwise.

**T-47 · The manual must literally contain the underscore document names.** `TC-01-P2-RET-01` and `TC-01-P2-GEN-02` search the retrieved text and the model's answer for the tokens `id_proof`, `income_proof`, `bank_statement` and `property`. GEN-02 needs at least three of them. Prose alone ("identity proof", "six months of bank statements") does not match `bank_statement`. So Section 4 of the manual has to name the document types in the same underscore form the database uses, next to the readable description. This is also honest: those are the real values the API accepts.

**T-48 · Everything in Phase 2 is a path relative to `backend/`.** The tests call `TextLoader("rag/user_manual.md")` and `PersistentClient(path="./chroma_db")` with no way to configure either. So `pytest` must be run from `backend/`, and `chroma_db/` sits at `backend/chroma_db/`. Already consistent with how Phase 1 runs; just do not be tempted to move either path.

**T-49 · The exact function shapes Phase 2 tests import.** `rag.ingest.ingest_manual(path)`; `rag.rag_chain.build_rag_chain()` returning the **tuple** `(chain, retriever)`; `rag.rag_chain.answer_question(query, chain, retriever)`. And `chain.invoke("a question")` must take a plain string and return a plain string — not a dict, and not a LangChain message object. Wrap the chain so the last step is `StrOutputParser()`.

**T-50 · Two of the twenty tests need a LangSmith key we do not have.** `OBS-01` and `OBS-04` call the LangSmith API for traces. Without `LANGCHAIN_API_KEY` the ceiling is 18 of 20, and the pass mark is 14, so Phase 2 still clears comfortably. The key is free from smith.langchain.com and worth getting for the full score. Raised with Rohit on 2026-09-06.

### From the mentor chats

**T-09 · Streamlit was overruled, but not replaced.** The Phase 2–4 tests check Streamlit; the demo runs React. Build both. Chat logic lives in the backend, both front-ends are thin screens.

**T-10 · The embedding trap, for Phase 2.** Gemini's embedding model and Ollama's `nomic-embed-text` both produce 768 numbers per chunk. ChromaDB accepts one against the other with **no error** and returns nonsense. Fix: one collection per provider.

### Environment

**T-27 · This laptop had no git, no Python, and no Node.** Found 2026-09-05, installed 2026-09-06: git 2.55, Python 3.11.9, Node 24.19 LTS. This is Rohit's personal laptop, so there are no restrictions on what can be installed.

**T-28 · The editor's shell still has the old PATH.** VS Code was open before the installs, so any shell it starts doesn't see the new tools until VS Code is restarted. Until then, every command I run starts by refreshing the PATH from the registry. Harmless, just noisy. Goes away on Rohit's next VS Code restart.

**T-29 · The project lives inside OneDrive.** Git and OneDrive can fight: OneDrive syncs the hidden `.git` folder while git is writing to it, and that occasionally corrupts the repository. For a solo project with GitHub as the backup, the risk is small and the fix is to re-clone. If it ever misbehaves, the cure is to either move the project out of OneDrive or tell OneDrive to skip this folder.

### Verification session (2026-09-08)

**T-67 - The Phase 2 "9 failures" were the exhausted daily quota, now proven.** The last run of 2026-09-07 failed 9 tests, 3 of them in `test_observability.py`, with the error text truncated so nobody could read it. On 2026-09-08, with the quota reset and no code changed, Phase 2 ran three times and passed 22 of 22 every time. Nothing was ever broken. Closes the open question from T-66.

**T-68 - The two LangSmith tests now run instead of skipping.** `test_langsmith_trace_created` and `test_trace_contains_retrieval_metadata` are guarded by `skipif` on `LANGCHAIN_API_KEY`. On 2026-09-08 both PASSED, so the key is set in `.env`. T-50 recorded them as unproven; they are now proven.

**T-69 - The model actually running is `gemini-3.5-flash-lite`, not the documented Gemini 2.0 Flash.** Every Gemini call in the test output names `gemini-3.5-flash-lite`. `CLAUDE.md`'s stack table still says "Gemini 2.0 Flash by default". Nothing fails, but the document and the running system disagree, and a mentor reading the stack table during a walkthrough would be told the wrong thing. Worth deciding whether to update the doc or pin the model back.

**Answered 2026-09-08 — the doc was wrong, and there was a third value nobody had noticed.** Pinning back to Gemini 2.0 Flash was never an option: Google withdrew it and it answers 404 (T-51). `gemini-3.5-flash-lite` was chosen deliberately because it was the only model that completed 8 of 8 calls without refusing on the free tier's rate limit (T-55). So the stack table was simply out of date, and now names the real models with a pointer to why.

**The real find underneath it:** there were *three* values in play, not two. `.env` said `gemini-3.5-flash-lite`, but `config.py`'s fallback default said **`gemini-3.8-flash`** — a different model again. That default is what runs whenever `.env` is missing that one line, which is exactly what happens on a fresh clone before anyone fills in their own `.env`. So a new machine would have silently run a slower model that was never chosen and never rate-limit tested, and nothing would have said so. `config.py` now matches `.env` and `.env.example`, with the reason written next to it.

**The habit worth keeping:** a setting with a default in code and a value in `.env` is two sources of truth. When they drift, the one that wins is whichever the machine happens to have — and it fails silently, on someone else's laptop, not yours.

**T-70 - Streamlit's `AppTest` does not put `backend/` on the import path.** Driving `mcp_server/chat_interface.py` through `AppTest` dies with `ModuleNotFoundError: No module named 'app'` unless the runner does `sys.path.insert(0, os.getcwd())` or sets `PYTHONPATH`. `streamlit run` sets this up on its own, so the app is fine; only the test driver needs the help. Anyone rerunning that end-to-end check will hit this first.

**T-71 - The Windows console is cp1252 and mangles the app's own output.** Printing the briefing narrative or the Streamlit title through a plain PowerShell pipe raises `UnicodeEncodeError` on the rupee sign and the bank emoji, and a pretty-printer can make correct em dashes *look* like mojibake in the terminal. The data is clean UTF-8; the console is the problem. Set `PYTHONIOENCODING=utf-8` before believing any encoding bug seen at the terminal. This cost a false alarm on 2026-09-08.

### From planning the domain rules (2026-09-06)

**T-32 · Phase 5 reads applicant facts that no table stores.** Employment length and existing loan payments. Raised as D-16.

### PowerShell

**T-34 · No double quotes inside git commit messages.** Windows PowerShell 5.1 mangles a double quote inside an argument to a native program like git, splitting the message into several arguments. The commit fails with a confusing "pathspec did not match" error, and any tag created in the same command lands on the wrong commit. Happened on Piece 7 and needed a tag deleted from GitHub. Rule: commit messages use single quotes or no quotes at all.

### In the trainer's sample code

**T-35 · The trainer's startup log line crashes.** `phase1-fullstack-crud.md` shows `logger.info("startup", event="database_initialized", ...)`. In structlog the first argument already *is* the event, so passing `event=` again raises "got multiple values for argument event" the moment the server starts. Copying that line verbatim means the app never boots. Ours logs `database_initialized` as the event name, which is what the observability checklist actually asks for.

**T-36 · The trainer's DB-02 test reads an id that does not exist yet.** It adds a `LoanApplication` to the session, then immediately builds a `StatusHistory` with `application_id=app.id`. But the row has not been saved, so `app.id` is still `None`, and the history row fails its not-null rule at commit. This would fail on *any* implementation. Our copy adds one `db_session.flush()` after the add, which saves the row and fills in the id. The associate guide allows adapting the skeleton; the reason is in a comment in the test.

**T-37 · pytest does not see `app` from `tests/phase1/`.** With the tests one folder down, pytest puts `tests/` on Python's path, not `backend/`, so `import app` fails. Fixed with `pythonpath = .` in `backend/pytest.ini`.

### Python itself

**T-33 · In Python 3.11, `str()` of a string-enum is not its value.** `str(ApplicationStatus.submitted)` gives `"ApplicationStatus.submitted"`, not `"submitted"`. The trainer's tests hand the rules enum members; the API hands them strings. Any helper that compares them must use `.value` when it's there. Caught while planning Piece 7; the rules file was using `str()` and would have failed UNIT-05. Fixed with a tiny `_v()` helper.

### Packages

**T-30 · passlib 1.7.4 breaks with bcrypt 4.1 or newer.** The trainer pins passlib but not bcrypt. Newer bcrypt removed something passlib reads at startup, so password hashing throws an error. Fix: pin `bcrypt==4.0.1` in `requirements.txt`. Done.

**T-31 · `EmailStr` needs an extra package.** Pydantic's email check, which test UNIT-02 relies on, needs `email-validator` installed separately. The trainer's list leaves it out. Added.

### Security

**T-11 · Never commit the environment file.** `.env` holds the Gemini key and the JWT signing secret. Commit `.env.example` with blank values instead.

**T-12 · The `Chats/` folder never goes to GitHub.** Real colleagues' names. Already in `.gitignore`. Repository stays private.

---

# Settled

### 2026-09-24 · Piece 34 — lean, and the Aadhaar refusal
- **Lean:** read only a PDF's own text. No OCR, no Gemini, no QR, no new
  libraries. The rest is in `FUTURE-UPGRADES.md` ("Around Piece 34").
- **An Aadhaar that can't be blacked out:** refused if real or undeclared, with
  a pointer to UIDAI's masked Aadhaar. A TEST one is stored with a note.

### 2026-09-24 · Browser checks are batched until the programme is built
**Rohit:** too tired to check each piece by hand; the browser checks happen
after all the pieces are built. Each piece still writes its browser check in
`BUILD-PLAN.md`, and they're run together at the end. Pending: 32d, 33.

### 2026-09-24 · Testing trimmed for speed, from Piece 33 on
**Rohit asked:** can we skip testing to speed up building? **Applied as:** no
long test lists per piece. Each piece keeps only (1) the trainer's tests and the
existing test files it touches, run as a targeted set rather than the whole
suite, and (2) one or two new tests for anything legal or demo-critical, plus
any new action added to `test_admin_role.py` (T-117). Everything else is left
to the browser check. Say the word to drop even the core.

### 2026-09-24 · Piece 33 — four answers
- **Kinds:** a demo set of 4 first (Aadhaar, PAN, salary slip, bank statement). The other 7 come later.
- **Counting:** a real file of a type with kinds counts only once its details are confirmed. Name-only documents count as before, which keeps the seed data and the trainer's tests safe.
- **Address on Aadhaar:** optional, never copied to the profile.
- **Where the kind is picked:** in the upload form, with a "Which one?" dropdown.

### 2026-09-24 · D-30 — The manual's promise of Replace is now true: Replace was built (Piece 32d)
**Rohit's answer:** don't reword the manual to "every copy is kept", because real
lenders don't say that to customers, and build the Replace button instead. A
search backed him up: customer-facing lender pages talk about resubmitting an
unclear or mismatched document, never about what the bank keeps internally. So the
manual's existing promise stayed, and gained the *how*. Built as Piece 32d,
v2.16.0. Replaced copies are shown to staff only.

### 2026-09-24 · D-29 — Same-type uploads sit side by side, never replace automatically
**Rohit's answer:** keep both, as now. Some types really do hold several files:
Aadhaar and PAN as ID proof, three months of payslips, a deed plus an NOC plus a
plan. The checklist counts types covered, not files (T-123, fixed in v2.15.3).
**Carried into Piece 33:** a Replace action (the old file kept in history as
superseded, dropped from the checklist, never deleted) is raised as a question
there, once "a second Aadhaar" can be told apart from "an Aadhaar plus a PAN".
Noted in `BUILD-PLAN.md` under Piece 33.

### 2026-09-22 · The Document intelligence programme (Pieces 27–38): decisions
Planned over several rounds with Rohit. The full detail is in `BUILD-PLAN.md`.
- **Order:** 27 Admin → 28 settings switch → 29 top bar → 30 notifications →
  31 real uploads → 32 TEST documents → 33 kinds and fields → 34 reading
  documents → 35 several at once → 36 chat history → 37 documents in chat →
  38 the form in chat. One at a time, each checked in the browser first.
- **Admin = System Administrator:** sees the whole system and administers it,
  but has **no loan-business authority** (no creating, approving, rejecting,
  disbursing or changing loan records) and is not a branch manager. It's done
  by sorting every address into VIEW or ACT, **not** by adding admin to
  `STAFF_ROLES`.
- **Notifications are a completely separate system** from the activity log.
  They're the app's own (no email, SMS or push). Only three triggers: staff
  when a customer asks to edit a submitted application, staff when a customer
  uploads a TEST document, and an applicant when their own application's status
  changes.
- **TEST documents count** towards the checklist, always visibly ("4/4
  submitted, including 2 TEST documents"). Submitted, identified, TEST and
  verified stay four separate facts. **Identification is not authenticity.**
- **No Ollama or local LLM.** Gemini is the only LLM. Local non-AI processing is
  preferred. **REAL documents never go to Gemini** by default; TEST may (T-108).
- **Storage:** SQLite for the details, and files in a folder outside the
  project, encrypted. **No MongoDB.** Production would be PostgreSQL plus object
  storage. **Superseded 2026-09-23 — see the entry below.**
- **Security is proportional:** must-haves are built, and production hardening
  is in `FUTURE-UPGRADES.md`.
- **Extracted data never overwrites the profile**; only Piece 24's approval can.
- **Piece 24 (profile changes):** the customer proposes values and staff
  approve; proof documents are required, so it's built after Pieces 31–34.

### 2026-09-23 · Piece 31 — two upload folders, chosen automatically, never self-declared

**What changed from the line above.** The project moved out of OneDrive
(T-112) to `C:\LAMS\loan-management-two`, so "files must live outside the
project" no longer protects against an accidental cloud sync — it was only
ever protecting against that. Rohit then asked for something more specific:
uploaded demo documents should travel with `git clone` to the Wipro laptop,
same as the code. That needs them **inside** the tracked project, which is
the opposite of the line above.

**The answer is two folders, not one, and the choice between them is never
made by the person uploading:**

- `backend/uploads/` — inside the project, tracked by git. Only a document
  the server is **confident** is TEST/demo material goes here.
- `C:\LAMS\uploads\` — outside the project entirely, never touched by git.
  Everything else: anything real, anything uncertain, and every image
  (Piece 31 has no way to read inside an image yet — that's Piece 34's OCR).
  This is the exact folder T-112 originally asked for; it still exists, now
  scoped to only the documents that actually need it.

**Nobody is asked "real or test" any more.** The self-declared choice and
its consent checkbox are removed from the upload form. `nature`
(test/real/undeclared) still exists and still drives Piece 32's badges,
staff notification and compliance note — only *who sets it* changes, from a
form choice to the server's own classification. There is nothing left in
the request for a client to send that could steer the answer.

**How the server decides — and why it stops short of asking Gemini
directly.** A document's realness isn't known until classification is
done, so letting Gemini judge an unknown document would mean showing it
something not yet known to be safe to show — precisely what T-108 exists to
prevent. The line held: local signals run first, always, with no AI at
all — a PDF's *original* text layer (read before the CDR rebuild step
flattens it away) is checked for SPECIMEN/SAMPLE/TEST/DEMO/DUMMY wording,
a list kept in `rules.SPECIMEN_WATERMARK_PHRASES`. Images and scanned
PDFs have no text layer to check yet, so they always fall to the sensitive
folder in this piece. **Only when that local pass already finds a strong
match** is Gemini asked to confirm — sent the matched text snippet, never
the file — as a second opinion on something already flagged likely-fake,
never as the first or only judge of an unknown document. Any Gemini
failure, timeout or disagreement fails safe. The app's own rule, not
Gemini's answer alone, makes the call: `nature = test` only when *both*
the local match and Gemini's confirmation agree; anything else —
including a Gemini call that simply failed — is `undeclared`, which is
already the existing rule for "treat like real."

**Consent** is now one checkbox, always required, since nobody knows in
advance how a document will be classified: "I agree this document is
stored by the bank and checked by staff."

**Encryption still applies to both folders.** Even a confidently-test file
is Fernet-encrypted before it touches disk, so the git-tracked folder
never holds a readable byte even if the classifier is ever wrong. One
shared key, `UPLOAD_ENCRYPTION_KEY`, is pre-filled with a real value in
`.env.example` rather than left blank like the other secrets — the
safe-zone files travel by `git clone` and need the same key everywhere to
stay readable, and the sensitive-zone files never travel, so sharing costs
them nothing either. This is a different model from `SECRET_KEY`, which
must be unique per machine because it signs logins; it only works because
nothing genuinely sensitive is ever expected to reach either folder in the
first place — the key is defence-in-depth, not the thing standing between
the repo and real PII. That job belongs to the "always use dummy data"
working rule below.

**The working rule this all rests on, stated plainly so it's never
assumed:** this project never uploads a genuine identity document, in
testing or in the demo. Every document used anywhere is dummy or specimen
material. The classifier and the two folders are defence-in-depth on top
of that rule, not a replacement for it — a misclassified dummy document is
a minor annoyance; a genuine document reaching GitHub, misclassified or
not, would not be.

Piece 32's plan mentions a "SPECIMEN backstop... needs the document's
text, so it's built in Piece 34." That backstop is essentially what this
piece now does at upload time instead. Piece 32/34's written plan should
be revisited once this is built, so the two don't describe the same check
twice.

**Revisited, 2026-09-23, when Piece 32 was built.** Confirmed: the bullet
was dropped from Piece 32 rather than deferred to Piece 34, and
`BUILD-PLAN.md` says so at the bullet itself. Nothing else in the old
Piece 32 plan needed to change — the badge, checklist counts, staff
notification and admin purge all built exactly as written, using
`StoredFile.nature` exactly as Piece 31 defined it.

**Built 2026-09-23, tag `v2.14.0`.** Everything above is exactly what
shipped, with two additions found while building:
- **A second, outer safety net in `classify_nature` itself.** Monkeypatching
  `_gemini_confirms_specimen` directly in a test bypassed that function's
  own try/except and produced a real 500 — proof that a failure the inner
  handling didn't anticipate could still take an upload down. `classify_nature`
  now also wraps its whole body: any unexpected break there still lands on
  `undeclared`, never a crash.
- **The rate limits (30 uploads/hour, 100 MB/customer) were written into
  `rules.py` and then genuinely wired up** — found unenforced while closing
  out the piece, added to `document_service._check_rate_limits`, checked
  before the pipeline runs so a rate-limited request fails fast.

**D10 (the switch OFF after real files exist) and "UNDECLARED needs consent
like REAL" are both settled**, taken as recommended: existing files stay
viewable and new uploads use the name form; consent is now one checkbox,
unconditional, since nobody self-declares nature any more.

### 2026-09-22 · D-28 — Customers may edit an application after submitting it
**Answer: yes, the trainer asked for this change himself.** This goes against
the trainer's original rule: "Applications cannot be modified after
submission. Withdraw and resubmit" (`phase2-rag-application.md:385-386`,
`01-POC-BLUEPRINT.md:500`, and our manual at `backend/rag/user_manual.md:181-182`
and `:292`). No trainer test checks that rule, so nothing fails. The manual and
the chatbot must change to match (Rule 12). Built as Piece 25.

### 2026-09-22 · Piece 25 — the four design answers
- **A1: which statuses allow an edit?** Only **submitted** and **under review**.
  Once approved, the approval rests on those figures, and the status can't go
  back to review without breaking the forward-only rule and its Phase 1 test.
- **Which fields?** **Amount, tenure, purpose.** Not loan type: a different
  type is a different loan, so it needs a new application.
- **Eligibility after an edit?** **Re-check it and replace the stored result.**
  The old result is kept in the `application_edited` activity row. This relaxes
  Piece 19's "never changed afterwards", deliberately.
- **Email?** **None.** The staff "Edit requests" page does the job. The customer
  sees "Questions? Contact support@bank.com" (a placeholder, T-104), and the
  chatbot must give the same address when asked how to contact the bank.
- **Database checks for the other tables?** A separate piece, Piece 26, straight
  after this one.

### 2026-09-16 · D-27 — The Risk Assessor now counts the EMIs an applicant already pays
**Answer: fixed.** Phase 5's Risk Assessor was setting `emi_affordability` from
the new EMI against the full 50% of income, ignoring what the applicant already
pays elsewhere — while Phase 1's eligibility check had always netted existing
EMIs off first. Same applicant, same numbers, two different verdicts.

Both now go through the one helper, `max_affordable_emi` in `app/utils/finance.py`.
The trainer's acceptance criterion survives because it is written one-way
("given EMI > 50% of monthly income, then affordability = no") and netting
existing EMIs only ever adds "no" verdicts, never removes one. The trainer's
"assume existing obligations = 10% of income unless specified" fallback is
kept exactly as it was, and only fires when no figure was given at all.

**Worth knowing: no seeded application changes verdict.** Sanjay (application 7,
the one in `BROWSER-CHECKLIST.md`) was already failing on the un-netted ceiling —
his ₹48,007 EMI clears ₹37,500 either way, which is where the 84% ratio and the
score of 70 come from. Every other demo customer either owes nothing elsewhere
or sits well inside the netted room. So the demo figures are untouched, and the
fix is currently invisible on seed data — if we want to *show* FOIR working at
the showcase, the seed data would need an applicant sitting in the band between
the netted room and the bare ceiling. Not done; raise it when the demo script
is written.

7 new tests in `tests/ours/test_risk_assessor_counts_existing_emi.py`, all
stubbed, no quota spent. Tag `v2.4.1`.

---

### 2026-09-08 · T-77 — LangChain's `_Exception` retry marker looked like a crash in the customer-facing reasoning trail

**What's wrong:** the agent's `intermediate_steps` include a step named `_Exception` whenever the model wrote a malformed step and had to be asked to correct itself. Seen live on a customer's refused request: the "how this was worked out" list read `get_application_details`, then `_Exception`. That is a real thing that happened and is worth logging, but it is not an action the assistant took, and a customer reading `_Exception` under their answer sees a crash.

**Fix:** `INTERNAL_STEPS` in `app/routers/chat.py` drops it from what the screen receives. It still appears in the server log, where it belongs. Guarded by a test.

**The lesson:** a framework's internal bookkeeping leaks into anything that renders its raw output. Anything shown to a customer needs a whitelist or a filter, not a straight pass-through of a library's own data structure.

---

### 2026-09-08 · T-76 — A server left running from an earlier session answers with the old code

**What's wrong:** the first live check of the new chat endpoint came back with `mode="rag"` and no `tools_used` field at all — exactly what a broken change looks like. Nothing was broken. A uvicorn from a previous session was still holding port 8000, the new one failed to bind, and every request went to the old code. The bind error only appeared in the log file, not on screen, because the new server was started in the background.

**Fix while testing:** run the check on a free port, and point `API_BASE_URL` at that same port so the agent's tools loop back to the server under test rather than the stale one.

**The lesson:** a background server that fails to start still leaves you with *a* server answering. Before believing a live check, confirm the thing answering is the thing you just built — a new field missing from the response is the cheapest tell.

---

### 2026-09-08 · T-75 — Wiring the agent into the customer chat would have shown one customer another's loan

**What's wrong:** `loan_api_client.service_token()` minted a **branch manager** token for every AI call, whoever was asking. Harmless while Phase 3 was only reachable from a developer's terminal. The moment `/api/v1/chat` routed to the agent, a customer typing "show me application 5" would have been answered with a manager's view of the bank — someone else's loan, their income, their credit score.

**Fix:** `acting_as(email, role)`, a context manager in `app/services/loan_api_client.py`. Every API call inside the block is made **as the person who asked**, so Phase 1's existing owner-scoping does all the work. Deliberately not a new permission system — it reuses the one that already exists and was already tested twenty ways. It is a `ContextVar` rather than a global, because a global would be shared across every request the server handles at once, and two people chatting simultaneously could be served each other's data.

Guarded by six tests in `tests/ours/test_agent_acts_as_caller.py`, and proved live: Priya (customer) and Anita (manager) ask the identical question in the identical box, and Priya is refused.

**The lesson:** a component's security depends on who can reach it, not on what it does. This code was safe for months and became a data breach the day a screen was pointed at it, with no change to the code itself.

---

### 2026-09-08 · T-74 — The Phase 4 chat crashed for the person running it, while every check said it worked

**What's wrong:** running the documented command

```powershell
.\venv\Scripts\streamlit run mcp_server/chat_interface.py --server.port 8502
```

opened a page that immediately died with `ModuleNotFoundError: No module named 'app'`. Streamlit puts **the script's own folder** (`backend/mcp_server`) first on Python's import path — not `backend/`. So `from app.utils.logging_config import ...` looks inside `mcp_server/`, finds no `app` package, and the script dies the moment a browser connects.

**Why every check missed it, which is the part worth remembering:**

- **`pytest tests/phase4` passed all 25.** pytest starts in `backend/` with `pythonpath = .` (T-37), so `app` was already importable. It tested the code, not the command.
- **Streamlit's own `AppTest` passed.** It runs inside a Python process that was itself started from `backend/`, so again `app` was already on the path.
- **The server returned HTTP 200.** That 200 is only the empty page shell. Streamlit does not execute the script until a browser opens a session, so a healthy status code proved nothing at all.
- **`streamlit run` printed "You can now view your Streamlit app"** and no error, because the crash happens per-session, in the browser, not at startup.

Four independent green signals, and the thing was broken for the only person who actually typed the command.

**Fix:** `chat_interface.py` now puts `backend/` on `sys.path` itself, from its own file location, so it works wherever it is launched from rather than depending on the person being in the right folder. Proved both ways: with the fix removed the import fails with exactly the reported error, and with it in place the same conditions import cleanly. Phase 4's 25 tests still pass.

**The lesson, and it is the third time this project has learned a version of it:** *a test that imports your module is not a test that your launch command works.* T-72 was the same shape (every phase passed alone, `pytest tests/` did not run at all), and T-42 before that. **Run the command the person will type, in the state they will be in.**

### 2026-09-08 · T-73 — A ghost button alone on a card reads as plain text, not a control

**What's wrong:** the Morning Briefing's "How this was worked out" control was a `Button` with `variant="ghost"`. Ghost styling is deliberately bare — `background: transparent; border-color: transparent; box-shadow: none` — and only appears on hover. That works in a toolbar, where the buttons beside it make it obviously pressable. This one sits **alone, under a divider**, with nothing next to it, so it rendered as a stray dark line of text. Nothing told a manager it could be pressed until the pointer happened to land on it — and the panel it opens is the whole trust story of the feature, the numbers behind every sentence the AI wrote.

**Found by looking at a screenshot**, not by reading code, not by a test, and not by a clean build. Exactly like T-42, where filter dropdowns had no styling because the CSS was scoped to `form` and the toolbars were plain `<div>`s. **Twice now the same shape of bug has been invisible to everything except a human eye on a rendered page.**

**Fix:** it is a disclosure control, so it now looks like one — a real border, a page-coloured fill, a hover and focus state, and a chevron that rotates to show which way it will move. `aria-expanded` too, so a screen reader gets the same information the chevron gives everyone else.

**Rule of thumb worth keeping:** a ghost or borderless control needs neighbours to be legible. Standing on its own it is just text, and users do not hover hopefully over text.

### 2026-09-08 · T-72 — `pytest tests/` failed to collect, even though every phase passed on its own

**What's wrong:** every phase suite passed when run individually — `pytest tests/phase3`, `pytest tests/phase5`, and so on. But running **all of them together**, which is the first thing a reviewer would type, failed before a single test executed:

```
ERROR collecting tests/phase5/test_e2e.py
import file mismatch:
imported module 'test_e2e' has this __file__ attribute:
  ...\tests\phase3\test_e2e.py
which is not the same as the test file we want to collect:
  ...\tests\phase5\test_e2e.py
Interrupted: 1 error during collection
```

**Why:** `tests/phase3/test_e2e.py` and `tests/phase5/test_e2e.py` share a basename. Without an `__init__.py` in each folder, pytest imports test modules by their bare filename, so the second `test_e2e` collides with the first and collection aborts. `tests/`, `tests/phase1`, `tests/phase2` and `tests/ours` all had one; **phase3, phase4 and phase5 never got one**, because each was created in a different session and nobody ran the whole suite together afterwards.

**Fix:** added the three missing `__init__.py` files, matching the layout the other folders already used. `pytest tests/` now collects all **142** tests and runs them.

**The lesson, and it is the real one:** each phase was verified in isolation and each looked fine. The failure only existed in the combination, and only appeared when someone ran the exact command a reviewer runs. **Test the thing the grader will actually type**, not just the thing you were working on.

### 2026-09-07 · T-66 — The Gemini free tier is 500 requests a **day**, and one full test run gets close

**What happened:** near the end of this run the AI stopped answering entirely — `RESOURCE_EXHAUSTED`, but this time naming `GenerateRequestsPerDayPerProjectPerModel-FreeTier`, `limit: 500`. T-55 documented the *per-minute* cap (5/min) and how the SDK's own backoff rides over it. This is a different, harder wall: once the day's 500 are gone, no amount of waiting inside a run helps. It resets on Google's clock, not ours.

**Why it matters more than it sounds:** Phases 2 through 5 together make well over a hundred LLM calls per full test run — Phase 3's agent alone spends several per test, and Phase 4 and 5 do the same. **Two or three full `pytest tests/` runs in one day can exhaust the daily quota**, and the next thing that asks for an LLM gets nothing. In this run that "next thing" happened to be the Manager's Morning Briefing, which degraded to its plain fallback exactly as designed — nothing broke, but the AI narrative could not be shown.

**What this means before a demo, in order of preference:**

1. **Do not run the full test suite on demo day.** Run it the day before. The demo itself costs only a handful of calls.
2. **Get a paid Gemini key** if the demo matters — this is the real fix, and it is inexpensive.
3. **Install Ollama** as the local fallback the project already supports (`LLM_PROVIDER=ollama` in `.env`, T-51/T-46). It was checked during this run and is **not installed on this laptop**, so that fallback is currently theoretical rather than available. Worth setting up before relying on it.

**What protects us either way:** every AI feature in this project degrades rather than fails — Phase 5's agents fall back to deterministic summaries, and the briefing falls back to the plain figures and says `written_by_ai: false` on the screen. The numbers are never at risk, because no number anywhere is computed by an LLM (D-19).

### 2026-09-07 · T-65 — The Phase 3/4/5 tests write into the real demo database

**What's wrong:** those phases' `running_api` fixture reuses an already-running Phase 1 server if it finds one — and that server is the real one, on the real `loan_app.db`. So every test that submits an application (Phase 4's MCP tests, Phase 5's fixtures) leaves a real row behind. One full run of this project's test suite left **60 applications** named things like "Phase 5 underwriting fixture" and "MCP test application" sitting in the manager's pipeline. The dashboard showed 68 open applications, nearly all of them junk — and that would have been the first screen an Account Delivery Head saw.

**Chosen:** `backend/clean_test_data.py`, which deletes only applications whose purpose matches one of the known test-fixture strings and leaves everything a person typed alone. **Run it before any demo.** The deeper fix — pointing those phases at their own database — was deliberately not attempted this late in the run, because the fixture reuses whatever server is already up, so it would only help someone who remembers to stop their server first. Recorded as the honest recommendation instead: see `RUN-REPORT.md`.

### 2026-09-07 · T-64 — Gemini's `response.content` is sometimes a list, not a string

**What's wrong:** `ChatGoogleGenerativeAI(...).invoke(prompt).content` does not always return a string. On `gemini-3.5-flash-lite` through `langchain-google-genai 4.4.0` it often returns a **list of content blocks** — `[{'type': 'text', 'text': 'OK', 'extras': {...}}]` — so the obvious `response.content.strip()` raises `'list' object has no attribute 'strip'`.

**How it hid:** both Phase 5 agents that call an LLM wrap the call in a try/except with a deterministic fallback, so nothing crashed and every test passed. The pipeline just quietly used the plain fallback sentence every single time instead of the LLM's writing — working, but not doing what it looked like it was doing. Only reading the warning lines in the log (`risk_summary_llm_failed`) showed it.

**Fix:** one shared `multi_agent/llm_text.py` with `text_of(content)`, handling both a plain string and a list of blocks. **Worth checking anywhere else this project reads `.content` from a Gemini response** — Phase 2's chain ends in `StrOutputParser()` so it is unaffected, and Phases 3 and 4 read agent output through LangChain's own agent machinery rather than touching `.content` directly.

**Also worth knowing:** a defensive fallback that swallows an exception silently will hide a bug like this indefinitely. The log line is what made it findable — which is the argument for logging the reason on every fallback path, not just returning the safe value.

### 2026-09-06 · T-63 — `requirements.txt` had been Phase 1 only since Phase 2 started, and installing `fastmcp` unpinned breaks FastAPI

**What's wrong, part one:** `requirements.txt` carried a comment saying "Phase 2+ packages get added when those phases start" — and then nobody ever came back and added them. Every Phase 2, 3 and 4 package (`langchain`, `langchain-google-genai`, `chromadb`, `google-genai`, `langsmith`, and now `fastmcp`/`mcp`) had only ever been installed by hand into this one venv, never written down. A clean checkout plus `pip install -r requirements.txt` would have built a Phase-1-only environment — every later phase's tests would fail on their first import line, on a reviewer's machine, not this one.

**What's wrong, part two:** installing `fastmcp` (any version, including the trainer's own pin `0.4.1`) pulls in the official `mcp` SDK, which does not cap `starlette`'s version — so a plain `pip install fastmcp` drags in the newest starlette (1.6.0+). That breaks FastAPI 0.111.0 outright (`Router.__init__() got an unexpected keyword argument 'on_startup'` — a constructor argument removed upstream) and breaks OpenTelemetry's FastAPI instrumentation the same way. This was found the hard way: installing fastmcp normally broke `app.main` immediately, and the recovery attempt — upgrading FastAPI itself to the newest release instead — broke the OTel instrumentation on a different incompatibility, so that path was abandoned and reverted too.

**Chosen:** pin `starlette==0.37.2` explicitly, alongside `mcp==1.6.0` and `fastmcp==0.4.1`. `mcp`'s own requirement on starlette is only a lower bound, so the older, already-required pin still satisfies it — confirmed in an isolated throwaway venv before touching the real one. Then rewrote `requirements.txt` from a full `pip freeze` of the actual working venv, organised by phase with the reasoning next to every version that isn't the trainer's original pin, and validated it by installing into a brand new venv and importing everything Phase 1 through 4 need. That clean-room install is what should have existed since Phase 2.

**Why it matters:** this is exactly the kind of gap Step 4 of this run exists to catch — invisible in the code, invisible in a passing test suite, only found by actually trying the thing a reviewer would try.

### 2026-09-06 · T-61 — The trainer's Phase 3 status-query test checks the wrong spelling

**What's wrong:** `TC-01-P3-E2E-01` checks the agent's plain-English answer for the literal enum value `under_review`, underscore and all. A correctly working agent writes "the application is currently **under review**" — a space, because that is how English works — so the check fails against an agent that is doing exactly what it should. Same shape of bug as T-36 in Phase 1: the trainer's own test would fail on any implementation that behaves the way the phase is asking it to behave.

**Chosen:** our copy of the test accepts either spelling, with the reason written next to it rather than silently changed. Confirmed first by running the agent directly (`run_agent("What is the status of application 1?", ...)`) and reading its actual answer before touching the test, so the fix is based on what the agent really said, not a guess.

### 2026-09-06 · T-62 — A brand-new LangSmith project isn't queryable within 3 seconds

**What's wrong:** `TC-01-P3-E2E-06` sends one trace, sleeps 3 seconds, then asks LangSmith for that project's runs. The very first trace a *new* project name ever receives has to create the project on LangSmith's server before anything can query it — this is slower than 3 seconds and raises `LangSmithNotFoundError`, not an empty list. It looks like "no traces yet" but is really "the project doesn't exist yet".

**Chosen:** replaced the fixed sleep with a short retry loop (up to six tries, 2.5s apart) that catches `LangSmithNotFoundError` and keeps trying. Confirmed the project (`AI-Readiness-POC-01-P3`) exists now by listing LangSmith's projects directly — this was purely a cold-start problem, not a configuration bug.

---

### 2026-09-06 · D-17 — Charts on the dashboard
**Answer: horizontal bars, no pie chart.** Rohit asked for pie charts; the colour validator showed the trainer's five mandated status colours cannot carry a pie (purple vs blue ΔE 0.4 under red-green colour blindness, red vs orange ΔE 8.7 with normal vision — see T-38). Bars with the status name written beside each one are accessible and give a real answer if an ADH asks. Loan type uses a single blue shade, since colour there means quantity, not identity.

### 2026-09-06 · D-16 — Two more Applicant fields for Phase 5
**Answer: add both.** `years_with_employer` (decimal, 0.5 = six months) and `existing_monthly_emi` (rupees, default 0). Both optional so no test breaks. When missing, Phase 5 falls back to the trainer's assumptions. Employment length also lets us check the manual's rule of 6 months salaried / 2 years self-employed.

### 2026-09-05 · D-13 — The headline showcase feature
**Answer: the Manager's Morning Briefing.** The AI reads the whole pipeline and writes the manager a short summary: what is stuck, what is risky and why, what needs attention today. Apply-by-chatting and policy what-if go to `FUTURE-UPGRADES.md`. This also closes D-08.

### 2026-09-05 · D-14 — EMI percentage for personal and auto loans
**Answer: 50% for all three loan types.** Matches the manual's home rule and the most common bank practice. The fuller bank data, including the income-tiered version, is in `LEARNING-NOTES.md`. One line gets added to manual Section 5 in Phase 2.

### 2026-09-05 · D-15 — Building teammates' features
**Answer: fine to build.** Rohit has talked it through with the team. Draft saving and OCR stay in `FUTURE-UPGRADES.md` and get built after the headline feature and Phase 5. Draft saving will be planned properly when we reach it; the one fixed rule is that drafts live on the server, not in the browser (Rule 13).

### 2026-09-05 · D-07 — Who registers as what
**Answer: Option A.** The normal `/auth/register` address creates bank staff, defaulting to loan officer. Customers sign up through `/auth/register-applicant`, which creates both a login and a borrower profile (T-23). Managers are seeded, never self-registered.

### 2026-09-05 · D-11 — The activity log
**Answer: build it, in Phase 1, small.** Curated business events only. Every row records who acted: a human by email and role, or an AI by which agent it was and which user it was acting for.

### 2026-09-05 · D-10 — Phase 5 risk threshold
**Answer: approve only above 70.**
```
APPROVE            score > 70  AND compliance passed AND EMI affordable
REJECT             score < 40  OR  compliance failed in a way that can't be fixed
REQUEST_MORE_INFO  everything else
```

### 2026-09-05 · D-01 — EMI affordability
**Answer: advisory, not blocking, for all three loan types.** A `check-eligibility` endpoint the form calls before submitting. Blocking would fail `TC-01-P1-API-03`.

### 2026-09-05 · D-02 — Tenure limits per loan type
**Answer: yes.** Personal 12–60, home 12–360, auto 12–84. Verified against all 20 tests.

### 2026-09-05 · D-03 — Home loan maximum
**Answer: ₹1 crore.** Per-type caps: personal ₹25,00,000, auto ₹50,00,000, home ₹1,00,00,000. The trainer's ₹5 crore in Phase 5 is a real setting, not a test value, and no Phase 5 test goes near it.

### 2026-09-05 · D-04 — Vehicle quotation
**Answer: add it.** Sixth allowed document type, required for auto loans in Phase 5.

### 2026-09-05 · D-05 — Date of birth
**Answer: yes, add it.** Nullable column on Applicant. Missing date treated as eligible.

### 2026-09-05 · D-06 — Role-based access
**Answer: yes.** Only `approved → disbursed` is gated behind manager.

### 2026-09-05 · Folder layout
**Answer: approved as written in `BUILD-PLAN.md`.**

### 2026-09-03 · Backend stack
**Answer: Python + FastAPI.**

### 2026-09-03 · Second front-end
**Answer: Streamlit now, Angular considered after Phase 5.**
