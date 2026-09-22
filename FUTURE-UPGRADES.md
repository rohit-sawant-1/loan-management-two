# Future upgrades

Ideas that came up while we worked, that go **beyond** what the trainer asked for.

Nothing here gets built until the base requirement it sits on is done and passing its tests. This file exists so good ideas don't get lost, and so they don't sneak into the build early and eat time.

Each entry says where the idea came from, why it waits, and a rough size.

---

## Activity log — the "big version"

The Phase 1 activity log is deliberately small: one table, one write function, one manager-only page. These are the pieces we left out on purpose.

| Idea | Why it waits | Size |
|---|---|---|
| Store the full text of every request and response | Storage grows fast, and most of it is never read | Medium |
| Search page with filters and date ranges | Useful only once there is a lot of activity | Medium |
| Export to Excel or CSV | Managers ask for this in real banks; not needed for a demo | Small |
| Retention rules (delete or archive after N days) | Only matters at scale | Small |
| Alerts when something looks suspicious, like many failed logins | Genuinely useful, but it's a separate feature | Medium |
| A developer-only screen for raw errors | Never shown to bank users; belongs in a log tool, not the app | Small |

---

## Features your teammates claimed

These were posted in the group chat as other people's showcase features. Rohit has talked it through with the team, so building them is fine. They wait until our own headline feature and Phase 5 are done.

| Idea | Claimed by | What it is | Size |
|---|---|---|---|
| Draft saving | Sindhu | Save a half-finished application and come back to it. **Must be stored server-side, tied to the logged-in user, never in the browser.** Drafts are separate from submitted applications, because the manual says submitted applications cannot be edited. | Small |
| OCR document reading | Md Alam | Upload a photo of a PAN card, the system reads the fields off it and checks it really is a PAN card. Gemini can read images directly, so no extra library. | Medium |
| AI risk simulator | Yaswanth | A what-if tool estimating approval chance. Phase 5 already gives us a manager-facing risk assessment, so this may not be needed at all. | Medium |

---

## Showcase features not chosen as the headline

Three ideas came up for our own unique feature. **The Manager's Morning Briefing is the headline** (settled 2026-09-05). These two wait.

| Idea | What it is | Size |
|---|---|---|
| Apply by chatting | Talk to the assistant instead of filling a form. It asks one question at a time, checks each answer against the rules, and submits at the end. Reuses the Phase 4 tools. | Medium |
| Policy what-if | The manager asks "what if we raise the minimum credit score to 700?" and the system recalculates the pipeline and shows what changes. | Medium |

---

## Parked while Piece 22 puts Phases 3-5 into the React chat

Rohit's instruction on 2026-09-08: **get the trainer's Phase 3, 4 and 5 functions working in the React app first.** These three are the things set aside to do that, each worth picking up afterwards. Read this section before starting any of them.

| Idea | What it is | Why it was parked | Size |
|---|---|---|---|
| **`agent_app.py`, the trainer's separate Phase 3 Streamlit screen** | The Phase 3 spec's folder listing includes a standalone Streamlit UI for the agent (line 68 of `phase3-context-engineering.md`, run command at line 562). It is **not** in that phase's submission checklist and **no test touches it**. | The React Assistant is the demo, and Piece 22 puts the same agent there. A fourth chat screen nobody opens adds confusion, not marks. Build it only if a reviewer asks for the folder layout literally. | Small |
| **Merging the Phase 4 staff chat into the React assistant** | `mcp_server/chat_interface.py` stays a separate Streamlit page for now. Piece 22 gives React its own staff-only action tools, so the two overlap. | The Streamlit page is what Phase 4's 25 tests import (`build_executor`, `process_message`, `MCP_TOOLS`). Deleting or moving it would break a passing phase for no gain. Keep both until after the demo, then decide. | Medium |
| **The Streamlit front-end catching up with React** | `frontend-streamlit/app.py` has Phase 2's assistant but will not gain Phases 3-5 during Piece 22. | React is the demo (T-09). Streamlit exists because Phase 2-4 tests check it, and those tests pass. Bringing it level is polish, not a requirement. | Medium |

---

## Automatic provider switching, when one AI runs out

Raised by Rohit on 2026-09-07, right after the Gemini free tier's **daily** 500-request cap ran out mid-run (T-66). Parked deliberately — he wants to discuss the options before anything is built.

**The idea:** instead of one provider with a manual `LLM_PROVIDER` setting, try providers in order and move to the next when one refuses. Gemini first, then something else, so a quota wall never costs the demo its AI narrative.

**What already exists:** `llm_provider.py` has the switch, `get_llm()` is the single place every phase asks for a model, and `.env` already carries the provider choice. So this is a change in one file, not a change everywhere — that part was designed for back in Phase 2.

**What still needs deciding (the actual discussion):**

| Question | The options |
|---|---|
| Fall back to what? | A second hosted free tier (another key, no install, its own limits) · Ollama running locally (no limits, no key, but a ~5GB download, slower, and not possible on the Wipro laptop) · both, chained |
| Does the screen say which AI answered? | Name the provider on screen, the way the briefing already says "Written by AI" — honest, and a good thing to point at in a demo · or log it only and keep the UI quiet |
| How much switching logic is worth explaining? | Every extra provider is one more thing to justify in a mentor code walkthrough |

**Worth remembering before building it:** nothing actually broke when the quota ran out. Every AI feature already degrades to deterministic text and says so, and no number anywhere is computed by an LLM (D-19) — so a dead provider costs prose, not correctness. This is insurance on narrative quality, not a fix for something broken, and it should stay small.

**Size:** Small to Medium, depending on whether Ollama is in scope.

---

## Things the manual promises that the system doesn't do yet

The user manual is written for Phase 2. It describes some things the trainer's Phase 1 never builds. Either build them later or trim the manual.

| Idea | Where the manual says it | Size |
|---|---|---|
| Real file upload with PDF/JPG/PNG and a 5MB cap, plus view and download for staff | Section 12. Koushik also asked for staff download in a review. | Medium |
| Co-applicants | Section 11 FAQ | Medium |
| Automated status notifications by email | Section 1 features list | Small once email works |
| Session expiry based on inactivity, not a fixed 24 hours | Section 10. Needs refresh tokens. | Medium |

---

## Everything else

| Idea | Where it came from | Why it waits | Size |
|---|---|---|---|
| Angular as a third front-end | Your career interest (D-09) | Days of work; Phases 4 and 5 need them more | Large |
| SMS OTP | Your idea | Needs a paid gateway and DLT registration we can't get. Email OTP is the realistic version. | Blocked |
| Hosting the app online | Your idea, so it can be used from the Wipro laptop through a browser | Decide before the demo, not now. See D-12. | Medium |
| SonarQube code quality gates | A peer ran it targeting 80% coverage and A ratings | Good answer to "how do you ensure quality?", but not graded | Medium |
| Automated tests for the React app | Came up while finishing Phase 1; the program grades only backend tests | Vitest plus React Testing Library for the form validation and the status badge colours | Small |
| A `python -m app` entry so `uvicorn` is not typed by hand | Convenience noticed writing the README | One file | Tiny |
| RAGAS automated answer scoring | Scoring rubric mentions it as optional | Only useful once Phase 2 answers exist | Small |
| Remember each officer's last filter and sort | Noticed building Piece 18 — a manager who always looks at "under review, oldest first" retypes it every visit | Needs a per-user settings table on the server (never the browser, Rule 13). Nice, not graded. | Small |
| Export the filtered list to a spreadsheet | Same place — the toolbar is the natural home for a download button | Belongs with the activity-log export already listed above, so build both together or neither | Small |
| The search box should also match the purpose text | Piece 18 searches name, email and application number | Purpose is free text, so it needs a proper text index to stay fast once there are thousands of rows | Small |

## Around Piece 25 — edit requests

Left out of Piece 25 on purpose (2026-09-22), so the base feature gets finished first.

| Idea | Where it came from | Why it waits | Size |
|---|---|---|---|
| Email the manager and the customer when a request is made or decided | Your notes in `TO-FIX.md` ("email to manager", "common email to request edits") | No email sending exists at all. It needs a mail account, credentials in `.env`, and it's one more thing that can fail during a demo. The in-app staff page does the job for now. | Medium |
| Ask for, approve and refuse edit requests from the chatbot | Natural next step once Piece 25 works on screen | Needs a new write tool with the YES confirmation, an MCP handler, and permission checks. The manual update in Piece 25 already lets the chatbot *explain* the process. | Small |
| Edit requests in the Streamlit front-end | Keeping the two front-ends level | Rule 5: React first, then decide if Streamlit needs it | Small |
| A count of waiting requests next to "Edit requests" in the sidebar | Came up planning Piece 25 | One extra request on every page load; nice, not needed | Tiny |
