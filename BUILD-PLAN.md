# Build plan

This is where we plan each piece **before** building it.

1. I write the plan for one small piece here.
2. You read it and suggest changes.
3. We build it.
4. It gets marked done, committed to git, and I plan the next piece.

Only one piece is being planned at a time, so you can see the details instead of approving a finished pile of code.

---

## The folder layout for the whole project

### The one rule that decides this layout

The trainer's test files import code by name. Those names are fixed:

| Phase | The tests write | So the folder must be called |
|---|---|---|
| 1 | `from app.models.application import ...` | `app` |
| 2 | `from rag.ingest import ingest_manual` | `rag` |
| 3 | `from agent.tools import ...` | `agent` |
| 4 | `from mcp_server.mcp_app import mcp` | `mcp_server` |
| 5 | `from multi_agent.agents.compliance_checker import ...` | `multi_agent` |

None of those names has a parent folder in front of it. In Python that means **all five must sit side by side, in the same folder**, and that folder is where we run everything from. Nesting them under something like `ai/` would break every later-phase test on its first line.

### Does this layout slow the app down?

No. Folder layout has no effect on speed. Python reads the files once when the server starts, and after that the layout is irrelevant. Speed comes from other places, and those are planned in:

- **Piece 3** — indexes on the columns we filter and sort by: `status`, `loan_type`, `applicant_id`, `submitted_at`
- **Piece 7** — loading an application's history and documents in one query, not one query per row (the N+1 problem the trainer warns about)
- **Piece 9** — the dashboard counts done as a single grouped query, not by loading every application
- **Piece 12** — the timing on every request, so we can see the 200ms and 500ms targets being met

The names are the trainer's because the tests force them. The organisation around them is ours.

### The proposed layout

```
FINAL_CHANCE/                     ← the git repository starts here
│
├── CLAUDE.md                     ← instructions for me
├── PROGRESS-LOG.md               ← what we did, session by session
├── TRAPS-AND-DECISIONS.md        ← what we found, what you decided
├── BUILD-PLAN.md                 ← this file
├── FUTURE-UPGRADES.md            ← ideas for after the base is done
├── 01-POC-BLUEPRINT.md           ← the three reference documents
├── 02-GROUND-TRUTH-SHIFTS.md
├── 03-THE-FLOW-WHAT-HAPPENED.md
├── .gitignore
│
├── POC-01-Loan-Application-Management/   ← trainer's originals, never edited
├── Chats/                                ← never goes to GitHub
│
├── backend/                      ← all Python lives here, run everything from here
│   │
│   ├── app/                      ← PHASE 1 — the API
│   │   ├── main.py               starts the server, wires everything together
│   │   ├── config.py             reads the settings file
│   │   ├── database.py           the database connection
│   │   ├── domain/
│   │   │   └── rules.py          every loan rule, in one place
│   │   ├── models/               the database tables
│   │   │   ├── user.py           who can log in, with a role
│   │   │   ├── applicant.py      who borrows, with date of birth
│   │   │   ├── application.py    the loan request
│   │   │   ├── document.py       uploaded paperwork, six types
│   │   │   ├── status_history.py the audit trail of status changes
│   │   │   └── activity_log.py   who did what, human or AI
│   │   ├── schemas/              input checking on every field
│   │   ├── routers/              the web addresses
│   │   │   ├── auth.py           staff register, applicant signup, login
│   │   │   ├── applicants.py
│   │   │   ├── applications.py   includes the eligibility check
│   │   │   ├── documents.py
│   │   │   ├── dashboard.py
│   │   │   └── activity.py       manager-only activity view
│   │   ├── services/             the actual logic
│   │   ├── middleware/           runs on every request: logging, request ID
│   │   └── utils/                tokens, EMI maths, logging setup, tracing setup
│   │
│   ├── llm_provider.py           ← the Gemini / Ollama switch, used by phases 2 to 5
│   │
│   ├── rag/                      ← PHASE 2
│   │   ├── user_manual.md
│   │   ├── ingest.py
│   │   ├── rag_chain.py
│   │   └── chatbot.py            Streamlit chat, for the tests
│   │
│   ├── agent/                    ← PHASE 3
│   │   ├── tools.py
│   │   ├── prompts.py
│   │   ├── summarizer.py
│   │   └── agent.py
│   │
│   ├── mcp_server/               ← PHASE 4
│   │   ├── mcp_app.py
│   │   └── chat_interface.py     Streamlit chat, for the tests
│   │
│   ├── multi_agent/              ← PHASE 5
│   │   ├── state.py
│   │   ├── graph.py
│   │   └── agents/
│   │       ├── data_collector.py
│   │       ├── risk_assessor.py
│   │       ├── compliance_checker.py
│   │       └── decision_maker.py
│   │
│   ├── tests/
│   │   ├── conftest.py
│   │   └── phase1/  phase2/  phase3/  phase4/  phase5/    ← what the reviewer runs
│   │
│   ├── seed.py                   fills the database with demo data
│   ├── requirements.txt
│   ├── .env                      secrets, never committed
│   └── .env.example              same file, secrets blanked out
│
├── frontend/                     ← FIRST front-end: React + Vite. This is the demo.
│   ├── src/
│   │   ├── api/                  talks to the backend; address comes from a setting
│   │   ├── components/
│   │   ├── pages/
│   │   └── App.jsx
│   └── package.json
│
├── frontend-streamlit/           ← SECOND front-end: Streamlit
│   └── app.py
│
└── results/                      ← test reports for submission, never committed
```

---

## The pieces of Phase 1

| # | Piece | What it is | Status |
|---|---|---|---|
| 0 | Tools on the laptop | Install git, Python, Node. Create the GitHub repository. | **Done 2026-09-06** |
| 1 | Project skeleton | Folders, virtual environment, package list, settings file | **Done 2026-09-06** |
| 2 | Domain rules | Every loan rule in one file | **Done 2026-09-06** |
| 3 | Database + 6 models | Six tables, with indexes on the filtered columns | **Done 2026-09-06** |
| 4 | Schemas | Input checking on every field, not just the ones the trainer names | **Done 2026-09-06** |
| 5 | Auth | Staff register, applicant signup, login, token, roles (Option A) | **Done 2026-09-06** |
| 6 | Applicant endpoints | Create and view a borrower | **Done 2026-09-06** |
| 7 | Application endpoints | Create, view, list, change status. History and documents loaded in one query. | **Done 2026-09-06** |
| 8 | Document endpoints | Record an uploaded document | **Done 2026-09-06** |
| 9 | Dashboard endpoint | The counts, as one grouped query | **Done 2026-09-06** |
| 10 | Eligibility check | Warns the form before submitting, all three loan types | **Done 2026-09-06** |
| 11 | Activity log | One table, one write helper, one manager-only page. Records human or AI actor. | **Done 2026-09-06** |
| 12 | Logging, tracing, and `main.py` | JSON logs with request ID and associate ID; timings on every request; the server itself | **Done 2026-09-06** |
| 13 | Tests | All 20, in `tests/phase1/`, named as the trainer's file says | **Done 2026-09-06 — 20 of 20 pass** |
| 14 | React front-end | The demo. Backend address from a setting, never hardcoded. | **Done 2026-09-06** |
| 15 | Streamlit front-end | List, form, dashboard | **Done 2026-09-06** |
| 16 | Seed data and test report | Demo data, then the submission files | **Done 2026-09-06** |

**Phase 1 is complete.** Tagged `v0.1.0`.

---

# PHASE 2 — the chatbot that reads the manual

**20% of the marks · 20 tests · 14 to pass.**

You write a user manual for the loan system, then build a chatbot that answers
only from it. Ask it something the manual does not cover and it must say so
rather than invent an answer.

## The pieces

| # | Piece | What it is | Status |
|---|---|---|---|
| 22 | Packages and the provider switch | Phase 2 dependencies, `.env` settings, and the one file allowed to choose Gemini or Ollama | |
| 23 | The user manual | All 13 sections, every number matching `rules.py` | |
| 24 | Ingestion | Load, chunk, embed, store in ChromaDB | |
| 25 | The RAG chain | Retrieve 4 chunks, answer from them, refuse when out of scope | |
| 26 | Observability | LangSmith tracing, the five OTel spans, structured logs | |
| 27 | The chat screens | React chat page, and the Streamlit one the later tests need | |
| 28 | The 20 tests | `tests/phase2/`, named as the trainer's spec writes them | |

## Piece 22 — Packages and the provider switch

**The problem it solves.** Gemini was blocked on the company network for six
weeks and the whole cohort had to move to Ollama. It can fail again, including
during a presentation. So the provider is a setting, not a decision baked into
fourteen files.

**The one rule:** `backend/llm_provider.py` is the *only* file in the project
allowed to import `ChatGoogleGenerativeAI`, `ChatOllama`, or either embeddings
class. Everything else — ingestion, the chain, the Phase 3 tools, the Phase 5
agents — calls `get_llm()`, `get_embeddings()` and `get_collection_name()`.
Switching providers is then one line in `.env`.

**The collection-name subtlety (T-46).** The obvious design gives each provider
its own collection, `poc_01_loan_manual_gemini` and `..._ollama`, so the two can
never be mixed — and mixing them fails *silently*, handing back confident
nonsense, because both models produce vectors of exactly 768 numbers. But the
trainer's `ING-04` and `RET-01` open the collection by its literal name
`poc_01_loan_manual`. So: **Gemini keeps the bare name, and only Ollama gets a
suffix.** Tests pass, and the collections still never collide.

**Packages**, at the trainer's pinned versions: `langchain==0.2.6`,
`langchain-google-genai==1.0.6`, `langchain-community==0.2.6`,
`langchain-chroma==0.1.2`, `chromadb==0.5.3`, `streamlit==1.36.0`, plus
`langsmith` and `langchain-ollama` for the fallback.

**New `.env` settings:** `LLM_PROVIDER`, `LLM_AUTO_FALLBACK`,
`GEMINI_CHAT_MODEL`, `GEMINI_EMBED_MODEL`, `OLLAMA_BASE_URL`,
`OLLAMA_CHAT_MODEL`, `OLLAMA_EMBED_MODEL`, `CHROMA_PERSIST_DIR`,
`CHROMA_COLLECTION`, `CHUNK_SIZE=512`, `CHUNK_OVERLAP=50`, `TOP_K_RESULTS=4`,
and the three LangSmith ones. `GOOGLE_API_KEY` is already there.

**A cautious check before anything else:** installing these must not disturb
Phase 1. The 37 tests get run again straight after the install, before a line of
Phase 2 code is written.

---

## Piece 0 — Tools on the laptop

Checked on 2026-09-05: git, Python and Node are not installed. winget is. This is Rohit's personal laptop, so anything can be installed.

Claude is running the installs. If you'd rather do it yourself, the commands are:

```powershell
winget install --id Git.Git -e --source winget
winget install --id Python.Python.3.11 -e --source winget
winget install --id OpenJS.NodeJS.LTS -e --source winget
```

Then close PowerShell, open it again, and check all three answer:

```powershell
git --version
python --version
node --version
```

Then tell git who you are, once, using the same name and email you'll use on GitHub:

```powershell
git config --global user.name "Rohit Sawant"
git config --global user.email "your-github-email@example.com"
```

**On GitHub:**
1. Sign in, click **New repository**.
2. Name: `poc-01-loan-application-management`.
3. Set it to **Private**.
4. Leave every "initialize with" box **unticked**. We already have files.
5. Click Create, then copy the HTTPS address it shows, and paste it to me.

I'll connect the folder to it and push. The first push will open a browser window asking you to sign in to GitHub; that's normal.

---

## Piece 1 — Project skeleton

Runs as soon as Piece 0 is done.

**Creates:** the `backend/` folder with an empty `app/` package inside, the `frontend-streamlit/` folder, a Python virtual environment inside `backend/`, the package list, the settings file and its blank example, and the first commit.

**The virtual environment** is a private copy of Python for this project. Packages installed into it don't touch anything else on the laptop, and the exact versions the trainer specifies stay pinned.

**The package list** uses the trainer's versions from `TECH_STACK_REFERENCE.md` for Phase 1 only: FastAPI, uvicorn, SQLAlchemy, pydantic, python-jose, passlib with bcrypt, structlog, the OpenTelemetry packages, python-dotenv, pytest, httpx. Phase 2+ packages get added when those phases start.

**The settings file** holds: the database address, the JWT secret, the token lifetime, `POC_ID`, `PHASE`, `ASSOCIATE_ID`, and the allowed front-end origin (5173).

**Nothing here depends on any open question.**

---

## Piece 2 — Domain rules

**One file:** `backend/app/domain/rules.py`.

**What it is:** every business rule of the loan system, written once, as plain Python constants and a few tiny helper functions. Nothing else in the project types a loan limit or a status transition by hand. They import it from here.

**Why it matters more than its size:** the same rules appear in five places across the five phases: Phase 1 validation, the Phase 2 manual, the Phase 3 tool that reports status, the Phase 4 tool that changes status, and the Phase 5 compliance and decision agents. If each phase has its own copy, they drift, and the chatbot ends up contradicting the app. One file, imported everywhere, and they cannot drift.

**One design choice:** this file imports nothing from the rest of the app. No database, no models, no FastAPI. Just numbers, sets, and small functions. That way Phase 3 and Phase 5 can import it without dragging in the whole web server. The status and document *enums* live in the models (the tests import them from there), but they use the same string values as this file, so they compare equal.

**What goes in it:**

| Group | Contents | Source |
|---|---|---|
| Allowed values | loan types, statuses, document types (six, with vehicle quotation), employment statuses, user roles | Blueprint Part 5, D-04, D-07 |
| Status machine | which status can move to which, and which move needs a manager | Blueprint Part 5, D-06 |
| Amounts | global 10,000 to 1 crore; per type: personal 25 lakh, auto 50 lakh, home 1 crore | Blueprint Part 6, D-03 |
| Tenure | global 6 to 360; per type: personal 12–60, home 12–360, auto 12–84 | Blueprint Part 6, D-02 |
| Eligibility | minimum CIBIL, minimum income, age range per type; home loan must end before 70 | Manual Section 5, D-05 |
| Documents | required documents per loan type | Manual Section 4, D-04 |
| Affordability | EMI may not exceed 50% of monthly income; default interest 12% for estimates | D-14, Phase 5 doc |
| Employment | salaried need 6 months with current employer, self-employed need 2 years | Manual Section 11 FAQ |
| Phase 5 scoring | approve above 70, reject below 40, the deduction table | D-10, T-13, T-14 |
| Helpers | `is_valid_transition`, `requires_manager`, `tenure_range`, `amount_limit`, `required_documents`, `missing_documents` | — |

**What does not go in it:** the EMI formula. The tests require that at `app.utils.finance.calculate_emi`, so it lives there. Eligibility *checking* (which needs EMI maths and an applicant's data) goes in a service in Piece 10. This file only holds the numbers and the yes/no rules.

**Tests it satisfies:** UNIT-05 and UNIT-06 (status transitions) end up as one-line wrappers around this file.

**Open before building:** D-16 in the traps file. Two Phase 5 rules reference applicant data the table does not have.

---

## Piece 3 — Database and the six tables

**Files:** `app/database.py` (the connection), `app/models/__init__.py`, and one file per table in `app/models/`.

**What a "model" is:** a Python class that describes one database table. Each attribute is a column. SQLAlchemy reads these classes and creates the tables for us. So this piece is "describe the six tables in Python".

### The connection — `database.py`

- Opens the SQLite file named in `.env`.
- Sets `check_same_thread=False`, which SQLite needs when a web server handles several requests at once (trainer's common-mistake #1).
- **Does not turn on foreign-key enforcement.** Two of the trainer's tests create records pointing at an applicant that doesn't exist, and would fail if SQLite checked (T-03).
- Provides `Base` and `get_db`, which the tests import by those exact names (T-06).

### The six tables

| Table | File | Columns | Notes |
|---|---|---|---|
| **users** | `user.py` | id, name, email, hashed_password, role, is_active, created_at | Who logs in. `role` is one of the three in the rules file. Email unique. |
| **applicants** | `applicant.py` | id, user_id, name, email, phone, **date_of_birth**, credit_score, annual_income, employment_status, **years_with_employer**, **existing_monthly_emi**, created_at | Who borrows. The three bold columns are our additions (D-05, D-16), all optional. `user_id` links to a login when the applicant signed up themselves; empty when an officer created the record. |
| **loan_applications** | `application.py` | id, applicant_id, loan_type, amount_requested, tenure_months, purpose, status, submitted_at, updated_at | The loan request. Also defines the `LoanType` and `ApplicationStatus` enums the tests import. |
| **documents** | `document.py` | id, application_id, doc_type, file_name, uploaded_at, verified | Six document types. Deleted automatically when the application is deleted (T-04). |
| **status_history** | `status_history.py` | id, application_id, old_status, new_status, changed_by, changed_at, remarks | The audit trail. Also deleted with the application. |
| **activity_log** | `activity_log.py` | id, actor_type, actor_id, actor_role, on_behalf_of, action, entity_type, entity_id, details, request_id, ip_address, created_at | Your idea (D-11). `actor_type` is "human" or "ai". `actor_id` is the email, or the agent's name. `on_behalf_of` is the user an AI was acting for. |

### Speed, built in now

Indexes on every column we will filter or sort by: `status`, `loan_type`, `applicant_id`, `submitted_at` on applications; `application_id` on documents and history; `created_at`, `actor_id` and `entity_id` on the activity log; `email` on users and applicants. An index is a lookup table the database keeps so it can find rows without reading the whole table.

### Tests this piece satisfies

DB-01, DB-03, DB-04 pass with the models alone. DB-02 needs the models plus the fixtures from Piece 13.

### Nothing open. All decisions this needs are settled.

---

## Piece 4 — Schemas, the input-checking layer

**What a schema is:** a description of what a request is allowed to contain. When someone sends data to the API, it is checked against the schema before any of our code runs. If a field is missing, too long, the wrong type, or out of range, the API answers with a 422 error listing exactly what was wrong, and our code never sees the bad data. Pydantic is the library that does this.

**Files, one per topic in `app/schemas/`:** `auth.py` (register, applicant signup, login, token), `applicant.py`, `application.py` (create, status change, list, the eligibility check, and the detailed response with the applicant and history nested inside), `document.py`, `activity.py`.

**The names the tests fix:** `CreateApplicantSchema`, `CreateApplicationSchema`, `CreateDocumentSchema` (T-06).

**Rule 6 applied — every field gets checked, not just the ones the trainer lists:**

| Field | Check |
|---|---|
| name | 2 to 100 characters, letters, spaces, dots and hyphens only |
| email | a real email shape (this is what test UNIT-02 checks) |
| phone | exactly 10 digits, Indian mobile |
| password | 8 to 72 characters, at least one capital letter and one digit (72 is bcrypt's hard limit) |
| credit_score | optional; if given, 300 to 900 (UNIT-08) |
| annual_income | more than zero, sane upper bound |
| date_of_birth | optional; not in the future; not before 1900 |
| years_with_employer | optional; zero or more, at most 60 |
| existing_monthly_emi | zero or more |
| amount_requested | 10,000 to 1 crore (UNIT-04). The per-type cap is checked in the service, so this test keeps passing exactly as written. |
| tenure_months | 6 to 360. Per-type range checked in the service, same reason. |
| purpose | 3 to 500 characters |
| doc_type | one of the six (UNIT-07) |
| file_name | 1 to 255 characters, must end in .pdf, .jpg, .jpeg or .png (manual Section 12) |
| remarks | up to 1,000 characters |
| status filter | one of the five, else 400 (T-18) |
| page / limit | page 1 or more; limit 1 to 100 |

**Why per-type limits live in the service, not here:** the trainer's UNIT-04 test builds a `CreateApplicationSchema` with `loan_type="personal"` and only checks the global amount bounds. If the schema also enforced the 25-lakh personal cap, the test would still pass, but the eligibility check in Piece 10 needs to explain *why* something is over the limit, which is a service job. Keeping schemas to shape-and-range and services to business rules is the cleaner split.

**Tests this piece satisfies on its own:** UNIT-02, UNIT-04, UNIT-07, UNIT-08.

**Nothing open.**

---

## Piece 5 — Auth: who you are, and what you're allowed to do

**What it is:** the login system. Register, sign up, log in, get a token, and a small piece that every protected endpoint uses to say "who is calling, and are they allowed?"

**How a token works, in plain words:** when you log in with the right password, the server hands you a long string of text called a JWT. It contains your email and role, signed with the server's secret so it cannot be forged. You send it back with every later request in a header, and the server reads it to know who you are without asking for the password again. It expires after 24 hours.

**Files:**

| File | Holds |
|---|---|
| `utils/auth.py` | hash a password, check a password, create a token, read a token |
| `dependencies.py` | `get_current_user` (reads the token, loads the user, or answers 401) and `require_role(...)` for endpoints only some roles may call |
| `services/auth_service.py` | the logic: register staff, sign up an applicant (creates both rows, T-23), check a login |
| `services/activity_service.py` | one small function, `record(...)`, that writes an activity-log row. Created here because logins are the first thing worth recording; every later piece reuses it. |
| `routers/auth.py` | the four addresses below |

**Addresses:**

| Method | Address | What it does | Answers |
|---|---|---|---|
| POST | `/api/v1/auth/register` | Staff account. Defaults to loan officer (D-07). The trainer's test uses this. | 201, 409 if email exists, 422 if weak password |
| POST | `/api/v1/auth/register-applicant` | Customer signup. One request creates the login and the borrower profile. | 201, 409 |
| POST | `/api/v1/auth/login` | JSON body in, token out (T-05) | 200, 401 without saying which field was wrong |
| GET | `/api/v1/auth/me` | Who am I, from the token | 200, 401 |

**Two traps handled here:**
- T-01: the built-in bearer helper answers 403 when the header is missing. We turn its automatic error off and raise 401 ourselves, which is what test API-06 expects.
- Login failures say "invalid email or password", never which one, so nobody can use the login page to discover which emails exist.

**What gets recorded in the activity log:** staff registered, applicant signed up, login succeeded, login failed (with the email tried, so a manager can spot someone guessing passwords).

**Tests this piece satisfies:** the `auth_token` fixture every API test depends on, and API-06.

**Nothing open.**

---

## Piece 6 — Applicant endpoints

**What it is:** creating and viewing a borrower profile. Small piece, but it carries the first owner-scoping rule (the peer bug from Change 10) and the function the trainer's UNIT-01 test calls by name.

**Files:** `services/applicant_service.py`, `routers/applicants.py`.

**Addresses:**

| Method | Address | Who may call | Answers |
|---|---|---|---|
| POST | `/api/v1/applicants` | Staff | 201, 409 duplicate email, 422 bad data. The trainer's `test_applicant` fixture uses this with an officer's token. |
| GET | `/api/v1/applicants` | Staff | 200, paged list |
| GET | `/api/v1/applicants/{id}` | Staff see anyone. **An applicant sees only their own profile**; asking for someone else's gets 403. | 200, 403, 404 |

**The function the test names:** `applicant_service.create_applicant(db, data)` must accept exactly a session and a `CreateApplicantSchema`, and return an object with `id`, `email`, `credit_score` and `created_at` filled in (UNIT-01).

**Recorded in the activity log:** `applicant_created`, with who created it.

**Nothing open.**

---

## Piece 7 — Application endpoints, the heart of Phase 1

**What it is:** submitting a loan application, viewing one, listing them with filters, and moving one through its statuses. Half of the trainer's API tests hit these four addresses.

**Files:** `services/application_service.py`, `routers/applications.py`.

**Addresses:**

| Method | Address | Who | Answers |
|---|---|---|---|
| POST | `/api/v1/applications` | Anyone logged in. An applicant may only apply for themselves. | 201; 404 unknown applicant; 422 missing fields or a per-type rule broken; 403 applying for someone else |
| GET | `/api/v1/applications` | Staff see all. Applicants see only their own. | 200 with `items`, `total_count`, `page`, `limit`; **400** for a bad status or loan type (T-18) |
| GET | `/api/v1/applications/{id}` | Staff, or the owning applicant | 200 with the applicant, every status change and every document nested; 403; 404 |
| PATCH | `/api/v1/applications/{id}/status` | Staff only. `approved → disbursed` needs a manager (D-06). | 200; **400 "Invalid status transition"**; 403; 404 |

**The function the tests name:** `application_service.validate_status_transition(current, new)` returning True or False (UNIT-05, UNIT-06). It is a one-line wrapper around the rules file.

**What happens on submit:** the applicant must exist; the amount and tenure must be inside the per-loan-type range (D-02, D-03), with a plain-English message if not; the application is created with status `submitted`; a first history row is written with no old status; an activity row is written; all committed together.

**What happens on a status change:** the move must be allowed by the rules file; if it is the manager-only move, the caller must be a manager; the status changes, `updated_at` refreshes, a history row records who and why, an activity row is written; all committed together.

**Speed:** the detail view loads the applicant, the history and the documents in **one** query, not one per row. The list view joins the applicant's name in the same query. This is the trainer's "no N+1" requirement.

**Filters on the list:** status, loan type, submitted from date, submitted to date. All combined with AND. Sorted newest first. Page and limit as in the spec.

**Tests this piece satisfies:** UNIT-05, UNIT-06, API-01, API-02, API-03, API-04, API-05, API-06, API-07.

**One bug fixed on the way:** T-33.

**Nothing open.**

---

## Piece 8 — Document endpoints

**What it is:** recording which documents an applicant has provided, and letting a loan officer mark one as checked. Phase 1 stores only the file name, not the file itself; real upload is in `FUTURE-UPGRADES.md`.

**Files:** `services/document_service.py`, `routers/documents.py`. The router is mounted under `/api/v1/applications` so the addresses read naturally.

**Addresses:**

| Method | Address | Who | Answers |
|---|---|---|---|
| POST | `/api/v1/applications/{id}/documents` | Staff, or the owning applicant | 201; 404 unknown application; 422 bad type or file name; 403 |
| GET | `/api/v1/applications/{id}/documents` | Staff, or the owning applicant | 200 with `items`, plus `required` and `missing` lists so the screen can show a checklist |
| PATCH | `/api/v1/applications/{id}/documents/{doc_id}/verify` | Staff only | 200; 404; 403 |

**Two things from the manual, built in:** the same document type may be uploaded twice and both are kept (user story 05). Officers verify documents (manual Section 2), which is what the `verify` address does, and it is what makes `kyc_verified` possible in Phase 5.

**Small design choice:** the trainer's `CreateDocumentSchema` carries `application_id` because UNIT-07 builds it that way. The endpoint gets the id from the address instead, so the body is just `doc_type` and `file_name`. The service accepts the trainer's schema; the router builds it from the address plus the body.

**Recorded in the activity log:** `document_added`, `document_verified`.

**Tests this piece satisfies:** none directly (the trainer's document tests are database-level and already pass), but user story 05 and Phase 5's compliance checker depend on it.

**Nothing open.**

---

## Piece 9 — Dashboard

**What it is:** one address that gives the manager the numbers: how many applications in total, how many at each status, how many of each loan type, and the total amount requested. The trainer's test API-08 checks the first three keys.

**Files:** `services/dashboard_service.py`, `routers/dashboard.py`, `schemas/dashboard.py`.

**Address:** `GET /api/v1/dashboard/summary`, staff only. Answers 200 always, with zeros when the database is empty (the spec says an empty database is not an error).

**Speed:** three small grouped queries, not a loop over every application. The database counts rows by status and by loan type itself and hands back the totals. That is what keeps this under the 500ms target no matter how many applications there are.

**A cautious upgrade:** every status and every loan type appears in the answer even when its count is zero, so the front-end never has to guess which keys exist. Two extra numbers that cost nothing: `pending_review` (submitted plus under review, the officer's to-do pile) and `approved_amount` (the rupees waiting to be paid out).

**Recorded in the activity log:** `dashboard_viewed`.

**Tests this piece satisfies:** API-08.

**Nothing open.**

---

## Piece 10 — The eligibility check

**What it is:** the answer to "would this loan be allowed?", asked by the form *before* the customer submits. It comes back with a plain-English list of problems and, where it can, a suggested amount or tenure that would pass. This is Koushik's "stop users applying if they don't meet the criteria and tell them what to adjust", done as advice rather than a hard block, so the trainer's API-03 keeps passing (D-01).

**Files:** `utils/finance.py` (the EMI maths, including the function UNIT-03 calls by name), `utils/dates.py` (age from a date of birth), `services/eligibility_service.py`, `routers/eligibility.py`.

**Address:** `POST /api/v1/applications/check-eligibility`, anyone logged in; an applicant may only check for themselves. Body: applicant id, loan type, amount, tenure. Answers 200 always, with `eligible` true or false.

**The checks, in order, every one sourced from the rules file:**

| Check | Rule | If it fails |
|---|---|---|
| Tenure | inside the per-type range (D-02) | says the allowed range |
| Amount | under the per-type cap (D-03) | says the cap |
| Income | at or above the minimum for the type | says the minimum |
| Credit score | at or above the minimum for the type; personal loans need a score at all | says the minimum |
| Employment | not unemployed; enough time in the job if we know it | explains |
| Age | inside the range, if we know the date of birth; a home loan must end before 70 | suggests the longest tenure that fits |
| Affordability | this EMI plus existing EMIs at most 50% of monthly income (D-14), at the default 12% rate | suggests the largest amount that fits at this tenure, and the shortest tenure that fits at this amount |

**Why the EMI formula lives in `utils/finance.py`:** the trainer's UNIT-03 imports `app.utils.finance.calculate_emi(principal, annual_rate, tenure_months)` by that exact path and expects about ₹16,607 for ₹5,00,000 at 12% over 36 months.

**Recorded in the activity log:** `eligibility_checked`, with the outcome.

**Tests this piece satisfies:** UNIT-03.

**Nothing open.**

---

## Piece 11 — The activity log, the reading side

**What it is:** the table and the writer already exist (Pieces 3 and 5), and every service has been writing to it since. This piece is the manager's window onto it. Rohit's idea (D-11).

**File:** `routers/activity.py`, plus two read functions added to `services/activity_service.py`.

**Addresses, branch manager only:**

| Method | Address | What it gives |
|---|---|---|
| GET | `/api/v1/activity` | A page of events, newest first. Filters: who (`actor_id`), what (`action`), human or AI (`actor_type`), which record (`entity_type` + `entity_id`), date range. All combined with AND. |
| GET | `/api/v1/activity/entity/{type}/{id}` | Everything that ever happened to one record, oldest first. For the application detail page: "the full story of application 5". |

**What a row shows:** who acted (a person's email, or an AI agent's name and who it was acting for), what they did, which record, the details, the request id that ties it to the server log line, and when.

**What is deliberately not here:** the big-version items in `FUTURE-UPGRADES.md`. No export, no search box, no retention rules. One page, filters, done.

**Recorded in the activity log:** nothing. Reading the log does not write to the log, or it would fill itself up.

**Tests this piece satisfies:** none of the trainer's, by design. It is ours.

**Nothing open.**

---

## Piece 12 — Logging, tracing, and the server itself

**What it is:** three things the program grades that are invisible to a user, plus the file that turns all the pieces into one running server.

**Files:** `utils/logging_config.py`, `utils/otel_config.py`, `middleware/logging_middleware.py`, and `main.py`.

### Logging — `logging_config.py`

Every log line becomes one line of JSON with the fields the observability guide demands: `timestamp`, `level`, `poc_id`, `phase`, `associate_id`, plus whatever the event adds. The three identity fields come from the settings file and are stamped on automatically, so no piece of code has to remember them. Within a request, the request id, method and path are attached to every line too, so you can pull one request's whole story out of the log with a single filter.

### Tracing — `otel_config.py`

OpenTelemetry "spans" are timed, labelled steps. The guide requires three for Phase 1: `http.request` (automatic, one per request), `db.query` (one per database statement), and `auth.validate` (one per token check). The database spans come from hooking SQLAlchemy's statement events, so every query anywhere in the app gets timed without touching the services. Spans print to the console when `OTEL_EXPORTER=console`, and are switched off with `none` so the tests stay quiet.

### The request middleware — `logging_middleware.py`

Runs around every request. Makes a request id (or reuses one the caller sent), logs `request_started`, times the work, logs `request_completed` with the status code and duration, and returns the id in an `X-Request-ID` header. If anything crashes, it logs the full stack trace with the request id and returns a clean 500 carrying that id, so a user can quote it and we can find the exact failure.

### `main.py`

Reads the settings, configures logging and tracing, creates the tables on startup, adds CORS for the Vite port (T-17), mounts every router at its `/api/v1/...` address, and adds `/health` for the reviewer's `curl`. This is the `app.main:app` the trainer's tests import and `uvicorn` runs.

**Tests this piece satisfies:** none directly, but the API tests cannot run at all until `app.main` exists. Every "mandatory log event" in the Phase 1 spec is now produced.

**Nothing open.**

---

## Piece 13 — The trainer's twenty tests

**What it is:** the trainer's `phase1-test-spec.md` turned into real test files that pytest runs. This is what the reviewer re-runs against our code, so the names and layout have to match what they expect.

**Files:** `backend/pytest.ini`, `backend/tests/conftest.py`, and `backend/tests/phase1/test_unit.py`, `test_api.py`, `test_db.py`.

**Layout:** `tests/phase1/`, because that is what the reviewer's guide runs (T-15). Each test function keeps the trainer's name and carries its test-case id in a docstring, so the mapping is visible.

**The shared setup (`conftest.py`):** the trainer's `client`, `auth_token` and `test_applicant` fixtures as written, using a file called `test.db` that is created before each test and deleted after (T-20). Plus the two fixtures the trainer's tests use but never define, `db_session` and `test_user` (T-08). Spans are switched off so the output stays readable.

**One adaptation, documented:** the trainer's DB-02 reads `app.id` before the row has been saved, so the id is still empty and the test would fail on *any* implementation. A one-line `flush()` after adding the row makes it work, and the associate guide allows adapting the skeleton. Logged as T-36.

**Small trap on the way:** with tests in `tests/phase1/`, pytest does not put `backend/` on Python's path by itself, so `import app` fails. `pytest.ini` fixes that with one line.

**Target:** 20 of 20. The pass mark is 14, but there is no reason to leave any behind.

**Nothing open.**

---

## Piece 14 — The React front-end

**What it is:** the screens. This is what gets demoed, so it matters more than its marks. It talks to the backend over HTTP and holds nothing but the login token (Rule 13).

**Tools:** React 18 with Vite (the build tool the program names), Axios for the HTTP calls, React Router for moving between pages. Plain JavaScript rather than TypeScript, and plain CSS rather than a component library, so every file is readable by someone new to the stack.

**The one setting that matters:** the backend address comes from `VITE_API_BASE_URL` in a `.env` file, never typed into the code. That is what keeps hosting possible later (D-12).

**Folder layout:**

```
frontend/
├── .env.example            VITE_API_BASE_URL=http://localhost:8000
├── index.html
├── package.json
└── src/
    ├── main.jsx            starts React, wires the router
    ├── App.jsx             the routes, and which role may see which
    ├── api/
    │   └── client.js       one Axios instance: base address, token on every call, logout on 401
    ├── auth/
    │   └── AuthContext.jsx who is logged in, their role, login and logout
    ├── components/
    │   ├── Layout.jsx      the header and navigation, links change with the role
    │   ├── StatusBadge.jsx the five colours, exactly as the spec lists them
    │   ├── Timeline.jsx    the vertical status history
    │   ├── DocumentChecklist.jsx  required / uploaded / missing
    │   ├── Spinner.jsx
    │   └── ErrorBanner.jsx
    ├── pages/
    │   ├── Login.jsx
    │   ├── StaffRegister.jsx        the trainer's register address
    │   ├── ApplicantSignup.jsx      the customer signup
    │   ├── ApplicationList.jsx      table, filters, status colours
    │   ├── ApplicationDetail.jsx    everything about one application, update-status for staff
    │   ├── NewApplication.jsx       the form, with the eligibility check before submit
    │   ├── Dashboard.jsx            the counts
    │   ├── Activity.jsx             manager only
    │   └── MyProfile.jsx            the applicant's own details
    └── styles.css
```

**Two doors, one app (D-07):** applicants and staff log in on the same page. After login the app looks at the role. An applicant lands on their own applications and can apply. Staff land on the full list and can review. A manager also gets the dashboard and the activity view. Links a role cannot use are not shown, and the pages behind them redirect if reached by typing the address.

**What the trainer's user stories require, and where it lands:**

| Story | Where |
|---|---|
| US-09 list with filters and exact status colours | `ApplicationList`, `StatusBadge` |
| US-10 form with client-side checks, server errors shown, redirect to the new application | `NewApplication` |
| US-11 detail with a vertical timeline, spinner, update-status button for officers | `ApplicationDetail`, `Timeline` |
| Dashboard page | `Dashboard` |
| Login and register storing the token in localStorage | `Login`, `StaffRegister`, `AuthContext` |
| Axios with base URL and the token added automatically | `api/client.js` |

**Beyond the spec, from the review comments:** the eligibility check runs before submit and shows the problems and suggestions (Koushik's "tell them what to adjust"); the document checklist shows what is still missing; the activity page for the manager.

**Client-side checks mirror the server's rules** (Rule 6): same ranges, same formats, same messages where sensible. The server's check is still the real one; the client's is for a good error message before the round trip.

**Built in stages, each committed:** 14a the shell (client, auth, layout, login, routes), 14b applications (list, detail, new with eligibility), 14c documents and status update, 14d dashboard, activity, profile, and polish.

**Nothing open.** D-12 is honoured by the `.env` setting.

---

## Piece 15 — The Streamlit front-end

**What it is:** the second front-end the program requires (user story 12). The minimum is a list with filters, a submission form and a dashboard, all talking to the same backend with the token in the header. Streamlit is a Python library that turns a script into a web page, so this is one file.

**Why it is worth doing properly, not just ticking the box:** the Phase 2, 3 and 4 test specs check Streamlit behaviour (`st.session_state`, port 8501). This file becomes the base those chat screens are built on.

**File:** `frontend-streamlit/app.py`. Runs with `streamlit run frontend-streamlit/app.py` from the project root, on port 8501. The backend address comes from an environment variable with a sensible default, same rule as React.

**What it does:** a login box in the sidebar (token kept in `st.session_state`, which lives on the server side of Streamlit, not in the browser). Then three tabs: Applications (filters, table, status colours), New application (the form, with the eligibility check), Dashboard (the numbers). Staff and applicants see the same tabs; the backend already limits what each can see.

**Package:** `streamlit==1.36.0` from the trainer's list, added to `requirements.txt` and installed into the same virtual environment.

**Nothing open.**

---

## Piece 16 — Seed data, test report, and the submission files

**What it is:** the last mile. Demo data that makes the screens look real, the test report file the program requires, the score tracker, and a README so a reviewer can run everything from a clean machine.

**Files:** `backend/seed.py` (already written and run), `MY_SCORES.md`, `README.md`, and the generated `backend/results/phase1-results.xml`.

**The seed:** two staff (a seeded manager, an officer), six customers with logins and profiles covering every interesting case (no CIBIL score, a 55-year-old wanting a long home loan, a new-to-job applicant, existing EMIs), and eight applications spread across all five statuses with documents in various states of verification. Everything goes through the real services, so the history and activity log are genuine.

**The report:** `pytest --junitxml=results/phase1-results.xml`, as the associate guide specifies. The file is generated, not committed (`results/` is ignored); it goes in the submission package alongside a terminal screenshot, which Rohit takes himself.

**Still Rohit's to do for submission:** the terminal screenshot of the full test run, and pushing or zipping the source. Both are in the associate guide's Step 6 and 7.

**Nothing open.**

---

# PHASE 1 POLISH — making the app look and feel like a real product

Rohit used the app as the manager on 2026-09-06 and gave detailed feedback. Everything below comes from that. **None of this changes a rule or a test** — the backend already works and all 20 trainer tests pass. This is visual and interaction work on top, plus one small backend addition for the stored eligibility summary.

Split into five pieces so each one can be read and changed before the next starts.

| # | Piece | What it fixes |
|---|---|---|
| ~~17~~ | ~~The design system~~ | **Done 2026-09-06.** Tag `v0.1.1`. |
| ~~18~~ | ~~Applications list + new application form~~ | **Done 2026-09-06.** Tag `v0.1.4`. |
| **19** | Automatic eligibility + stored summary | Eligibility is manual and minimal; nothing is recorded |
| ~~20~~ | ~~Dashboard~~ | **Done 2026-09-06.** Tag `v0.1.2`. |
| ~~21~~ | ~~Activity page~~ | **Done 2026-09-06.** Tag `v0.1.2`. |

Pieces 20 and 21 were brought forward because Rohit hit them while using the app. Piece 19, the stored eligibility summary, is the last one left.

---

## The colour problem, and what the evidence says

The trainer fixed five colours in user story 09 and we cannot change them:
`submitted` blue, `under_review` orange, `approved` green, `rejected` red, `disbursed` purple.

That is five saturated colours already spoken for, spread right across the spectrum. So the app's own theme has to stay out of their way, or everything turns into noise.

**I ran those five colours through a colour-accessibility validator** rather than guessing. The results decide two things in this plan:

| Test | Result |
|---|---|
| Side-by-side bars, neighbouring colours only | **One failure:** green and red sit ΔE 5.0 apart for a viewer with red-green colour blindness (about 1 man in 12). Everything else passes. |
| Every colour against every other, which is what a **pie chart** does | **Two failures:** purple vs blue measure **ΔE 0.4** under red-green colour blindness — effectively the same colour. Red vs orange measure ΔE 8.7 even with **normal** colour vision. |

Plain reading: in a pie chart of statuses, a colourblind viewer cannot tell "submitted" from "disbursed" at all, and nobody can reliably tell "rejected" from "under review". In a bar chart, only one pair is weak, and a written label next to each bar fixes it completely.

**So: bar charts for status, not a pie.** Not a style opinion — the numbers are above, and it is exactly the kind of thing an ADH might probe. It also gives Rohit a genuinely good answer in a code walkthrough.

### The theme that results

Because the five status colours must stay loud, **everything else in the app goes quiet.** Chrome becomes deep slate, near-navy. Status pills become the only saturated colour on screen, which makes them easier to read, not harder.

```
--ink-900  #0f172a   sidebar, headings, primary buttons
--ink-700  #334155   body text
--ink-500  #64748b   muted text, axis labels
--line     #e2e8f0   hairline borders
--surface  #ffffff   cards
--page     #f1f5f9   page background
--focus    #3b82f6   focus outline only, never a fill
```

The five status colours: unchanged, and used **only** inside pills and chart bars, always beside a written label.

---

## Piece 17 — The design system

**Files:** `styles.css` rewritten around tokens; `components/Layout.jsx` rebuilt; new `components/ui/` with `Card`, `Button`, `Modal`, `Toolbar`, `Field`, `EmptyState`, `Skeleton`.

**Navigation changes from a top strip to a left sidebar.** Dark slate, the bank mark at the top, grouped links with small icons, the signed-in person at the bottom. A thin top bar keeps the page title and a sign-out control. This one change does more for "does this look like a real product" than anything else on the list.

**Buttons get real states.** Rest, hover, a genuine pressed state that moves the button down 1px, a focus ring for keyboard users, and a disabled state. The dashboard refresh button gets a spinning icon while it is actually fetching — the thing Rohit noticed was missing.

**A modal component**, since three pages need one. Opens with a short fade and lift, closes on Escape or a click outside, returns keyboard focus where it came from, and traps focus while open.

**Tables** get proper column alignment, numbers right-aligned in tabular figures so digits line up, a hover row tint, and a real empty state instead of a bare sentence.

**Nothing in this piece changes behaviour.** Same screens, same data, same rules.

---

## Piece 18 — Applications list and the new-application form

**The list:** filters move into a proper toolbar — a search box on the left, then filter controls, then a result count and the clear button on the right, on one line that wraps sensibly instead of the current crowd. Sort becomes explicit: click a column heading to sort by it, with an arrow showing which way. Row hover, and the whole row stays clickable.

**The form:** currently one long stack of inputs. It becomes three labelled sections — *Who is applying*, *The loan*, *Why* — on a card, with the live eligibility panel beside it rather than below. Amount gets a formatted preview underneath as you type ("₹20,00,000"), tenure gets quick-pick chips for common terms, and each field shows its rule as a hint until you break it, then shows the error.

### The one real decision in this piece: where sorting and searching happen

They happen **on the server**, not in the browser. The list is paged at 20 rows, and there are 99 applications in the seed data. If the browser sorted, it would sort only the 20 rows it happens to be holding, so "sort by amount, highest first" would show the highest of *this page* while quietly hiding a bigger one on page 3. That is not a sort, it is a lie with an arrow next to it. Same for search: the browser can only search what it has already been given.

So two small additions to the backend. Both are **purely additive** (Rule 4) — every new setting is optional, and with none of them supplied the endpoint behaves exactly as it does today, newest first.

**Checked against the trainer's twenty tests before writing a line:** the only list test is `TC-01-P1-API-07`, which calls `GET /applications?status=submitted` and counts the rows that come back. It sends no search, no sort, no order, so it takes every default and the result is unchanged. Nothing else in the twenty touches the list. Safe.

### The backend half

**`services/application_service.list_applications`** gains three optional arguments:

| Argument | Does what | Default |
|---|---|---|
| `search` | Partial, ignores capitals. Matches the applicant's **name**, the applicant's **email**, or — when what you typed is a number — the **application id**. So "anit", "ANITA", "anita@", and "42" all find something sensible. | none |
| `sort_by` | `id`, `applicant_name`, `loan_type`, `amount_requested`, `tenure_months`, `status`, `submitted_at` | `submitted_at` |
| `order` | `asc` or `desc` | `desc` |

Two details worth knowing. Sorting by applicant name needs a real join rather than the `joinedload` we use now, and it has to be an **outer** join: T-03 says foreign keys are off, so an application can point at an applicant that does not exist, and an inner join would silently drop those rows from the list. And every sort gets `id` added as a tie-breaker underneath, so two applications submitted in the same second never swap places between page 1 and page 2.

**`routers/applications.py`** takes the three as query parameters and checks `sort_by` and `order` against the allowed lists, answering **400** with the allowed values if either is wrong. That matches how bad `status` and `loan_type` values are already handled (T-18), so the whole endpoint speaks with one voice.

**A new test file, `tests/ours/test_list_search_sort.py`**, kept out of `tests/phase1/` so the trainer's suite stays exactly as the spec writes it. It covers: search finds a partial name ignoring capitals, search by number finds that application, sorting by amount really does put the largest first across the whole set rather than the page, a bad `sort_by` is a 400, and — the one that matters most — **calling the list with no settings at all returns exactly what it returned before.**

### The front-end half

**`pages/ApplicationList.jsx`**, rebuilt around the toolbar Piece 17 already provides:

- Search box on the left with the magnifier icon, **waiting 350ms after you stop typing** before asking the server, so a nine-letter name is one request instead of nine.
- Status and loan type stay as dropdowns — the trainer's US-09 names them specifically, so they keep their shape.
- Dates move behind "More filters", the same pattern as the activity page, so the default row is calm.
- On the right: how many matched, and a Clear button that says how many filters are on.
- Column headings become clickable, with `sortAsc`/`sortDesc` arrows that are already drawn in `Icon.jsx`. First click sorts, clicking the same one again flips the direction.
- The empty state becomes the proper `EmptyState` component instead of a grey sentence in a table cell.

**`pages/NewApplication.jsx`**, same fields and same behaviour, better shape:

- Three sections using the `.form-section` styles Piece 17 already defines: *Who is applying*, *The loan*, *Why you need it*.
- Under the amount box, the number written out as you type — "₹20,00,000" — because a row of digits is genuinely hard to read and this is the field people get wrong.
- Tenure gets quick-pick chips for the common terms of the chosen loan type, and the chips change when the loan type does.
- Every field shows its rule as a quiet hint, and swaps to a red message only once it is actually broken.

**Not in this piece:** the automatic eligibility check, the pass/fail assessment card and the "submit anyway" modal are all Piece 19. The existing Check-eligibility button and panel carry on working exactly as they do now.

---

## Piece 19 — Automatic eligibility, and the stored summary

Two halves: the live check in the browser, and the permanent record on the server.

**Live, in the form.** The check stops being a button you have to remember. As soon as applicant, loan type, amount and tenure are all filled and individually valid, the app asks the server automatically, waiting about 600ms after typing stops so it does not fire on every keystroke. The result appears in the panel beside the form and updates as you change things. The button stays, as an explicit "check again".

**The result panel** becomes a proper assessment card: a clear verdict line, then every rule that was checked shown as a passed or failed row — tenure, amount, income, credit score, employment, age, affordability — not just the failures. Seeing seven green rows and one red one is far more convincing than one line of red text. Failures carry their suggestion with a one-click "use this" as now.

**On submit, when not eligible**, a modal appears rather than the current inline warning: what failed, what the consequence is, and two clear choices — go back and adjust, or submit anyway. That is a decision point, which is what modals are for.

**The stored summary — the backend half.** This is the part Rohit asked for and it does not exist yet.

When an application is created, **the server runs the eligibility assessment itself** and stores the outcome on the application. Not the browser's copy — the server's own, so it cannot be skipped or faked by anything calling the API.

Three new columns on `loan_applications`, all optional so nothing existing breaks:

| Column | Holds |
|---|---|
| `eligibility_passed` | true or false at the moment of submission |
| `eligibility_summary` | the readable text below |
| `eligibility_checked_at` | when |

The summary reads like a note a person would write:

```
Eligibility assessed at submission on 06 Sep 2026, 01:52.

Applicant: Priya Sharma — CIBIL 720, annual income ₹6,00,000,
salaried 3 years, age 32.
Requested: home loan of ₹20,00,000 over 120 months.
Estimated EMI ₹28,694 a month at the indicative rate of 12%.

Result: NOT ELIGIBLE — 6 of 7 rules met.

  PASS  Tenure within 12–360 months for a home loan
  PASS  Amount within the ₹1,00,00,000 home loan limit
  PASS  Annual income at or above ₹4,80,000
  PASS  CIBIL score at or above 700
  PASS  Employment: salaried, 3 years with current employer
  PASS  Age 32 within 21–70, and the loan ends before age 70
  FAIL  Affordability — the estimated EMI of ₹28,694 exceeds the
        50% of monthly income available for loan payments (₹25,000)

Submitted anyway by priya@example.com.
```

Shown on the application detail page in its own panel, and it means every application carries a permanent record of what the bank knew and what the rules said at that moment. Phase 5's decision agent gets a large head start from it.

**Checked against the tests:** API-01's application passes eligibility; API-03's home loan is the one that fails affordability. Neither is blocked, both still return 201, and the extra fields in the response do not affect what the tests assert. Safe.

---

## Piece 20 — Dashboard

**A row of four stat tiles** at the top: total applications, awaiting review, total requested, approved but not yet paid. Large figures, a quiet label above, and the two rupee figures in tabular digits.

**The pipeline**, as horizontal bars in workflow order — submitted, under review, approved, rejected, disbursed — each in its mandated colour with the status name and count written beside it. Horizontal because the labels are long words; written labels because of the green/red finding above. A thin stacked bar across the top shows the same thing as parts of a whole.

**By loan type**, as horizontal bars in a **single blue shade, darker meaning more.** Deliberately not the status colours: on that chart colour means "how many", not "which status", and using one hue keeps the page from having two competing colour languages.

**No charting library.** These forms are simple enough to draw directly, which gives exact control over bar thickness, rounded ends and gaps, adds nothing to the download, and leaves code Rohit can read line by line in a walkthrough. A library would fight the design and be one more thing to explain.

**The refresh button** spins while loading and briefly shows a tick when done.

> **Decision for Rohit — see the message with this plan.** Pie charts were asked for; the validator argues against them for status. There is a defensible middle option.

---

## Piece 20 and 21 — Dashboard and activity page

Both built in Session 28, before this file's entries for them were written up. See `PROGRESS-LOG.md`, session 28, for what changed.

---

## Piece 21 — Activity page

**The toolbar** currently puts seven controls in one crowded row. It becomes: a search box, then a compact filter row, then an expandable "more filters" area for the date range and record lookup. Everything stays — nothing is removed — it is just no longer all shouting at once.

**The table** loses the raw data column. Each row becomes: when, who (with an "AI" tag and who it acted for, when it was an agent), what happened in plain words, and which record. A "View" control on each row opens a **modal** with the full story — every field laid out as labelled rows, the technical details formatted properly rather than dumped as one string, and the request id shown as something you could quote to a developer.

**Plain-word action names.** `status_changed` becomes "Status changed", `eligibility_checked` becomes "Eligibility checked", and so on, with a small icon per kind of action.

---

# PHASE 3 — the agent with five tools

**20% of the marks · 20 tests · 14 to pass.**

`agent/tools.py`, `agent/prompts.py`, `agent/summarizer.py` and `agent/agent.py` were built in the session that ended with "Phase 3 tests (written, not yet run)" — five tools reading live data over the same shared `loan_api_client.py` Phase 4 and 5 also use, a ReAct-style agent built with LangChain, and a summarizer for any tool answer over roughly 2000 characters. No front-end: this phase is reasoning only, and the trainer's own plan puts the chat screen in Phase 4.

This run's job was to actually run `tests/phase3/` for the first time and inspect the phase, not to build it again. See PROGRESS-LOG.md, Session 34, and T-61/T-62 in `TRAPS-AND-DECISIONS.md` for what that found: two bugs in the tests themselves (one ours, one the trainer's own — same class as T-36) and no bugs in the agent's own behaviour. **All 23 tests pass, none skipped**, after those two fixes plus a whitespace-in-description assertion fix. Tag `v0.3.0`.

---

# PHASE 4 — the MCP server and the staff chat

**25% of the marks · 25 tests · 18 to pass.** The heaviest phase.

**`mcp_server/mcp_app.py`** — six `@mcp.tool()` functions (`submit_loan_application`, `get_application_details`, `update_application_status`, `list_applications_by_filter`, `get_dashboard_summary`, `upload_document_metadata`), each calling the Phase 1 API through the shared `app.services.loan_api_client` Phase 3 already uses, and each returning a plain dict — real data on success, `{"error": ..., "detail": ...}` on any failure, never an exception. `mcp.tool_invoke` OTel span and a structured log line on every call, per the trainer's own observability table.

**`mcp_server/chat_interface.py`** — the same six operations wrapped again as LangChain tools (`MCP_TOOLS`), feeding a second ReAct agent built the same way Phase 3's is, at temperature 0. `build_executor()` and `process_message()` carry no Streamlit code, so importing this module for a test never touches the UI; the actual chat screen lives in `main()`, called only under `streamlit run`. Session id in the sidebar, four quick-action buttons, full chat history, and an expandable "tools used" panel under every reply that called one.

**What this run did, not what it built from scratch:** the trainer's spec, the fastmcp version fight, and everything found along the way are in `PROGRESS-LOG.md` Session 35 and `TRAPS-AND-DECISIONS.md` T-63. Two real bugs came out of actually running and driving the thing rather than trusting the test suite: a LangChain ReAct quirk on the one single-argument tool (fixed the same way Phase 3 fixed it — take the id as a string), and a dead "quick action" button in the Streamlit screen that added a message but never asked the agent anything, found with Streamlit's own `AppTest` since real browser tooling was not available this session. **All 25 tests pass, none skipped.** Tag `v0.4.0`.

---

# PHASE 5 — the four-agent underwriting review

**20% of the marks · 25 tests · 18 to pass.**

**`multi_agent/state.py`** — the `LoanProcessingState` TypedDict every agent reads and writes, plus an `initial_state()` helper so every field starts with a sensible empty default and no agent ever meets a missing key.

**The four agents**, each in its own file under `multi_agent/agents/`:

- **Data collector** fetches the application, its applicant and its documents through the same shared API client Phases 3 and 4 use. The application response already embeds the applicant, so this is one HTTP call, not two.
- **Risk assessor** computes the EMI, the debt-to-income ratio, affordability, the credit and employment risk tiers and the overall 0-100 score — all in plain Python from `domain/rules.py`. The LLM writes only the two-sentence summary a human reads (D-19).
- **Compliance checker** verifies documents, KYC, the amount limit and — unlike the trainer's own reference, which contains `age_eligible = ... or True` and never checks an age at all — a real age check against `AGE_LIMITS`, including the rule that a home loan must be repaid before 70 (`AI-BUILD-LOG.md`, D-05).
- **Decision maker** applies the bands settled in D-10: approve above 70, reject below 40, everything else asks for more information — with a missing document treated as fixable and an over-limit amount or ineligible age treated as not. The LLM writes the reasoning paragraph explaining a decision that has already been made.

**`multi_agent/graph.py`** — the LangGraph `StateGraph` wiring those four in order, with one conditional edge: if data collection failed, end there. `graph.execute` and `agent.{name}.activate` OTel spans, `supervisor_routing` log lines, and per-agent traces in the `AI-Readiness-POC-01-P5` LangSmith project.

**`multi_agent/main.py`** — the command-line entry point from the trainer's Step 7.7, printing each agent's message and the final decision.

**All 25 tests pass, none skipped.** Two bugs found by running it rather than reading it: Gemini returning `.content` as a list of blocks rather than a string (T-64), which silently replaced every LLM summary with the fallback, and the same LangSmith cold-start wait Phase 3 hit (T-62). Tag `v0.5.0`.

---

# THE HEADLINE FEATURE — the Manager's Morning Briefing

Settled as D-13 on 2026-09-05, built after Phase 5 cleared. Not a trainer requirement — this is the thing that makes the demo memorable rather than merely complete. Everything else in this project answers a question the manager asked; this is the one screen that tells them what to ask about.

**What it is.** The manager opens the app in the morning and the AI has already read the whole pipeline: what is stuck and for how long, what is risky and why, what needs a decision today, and what is quietly fine. One short briefing, in plain English, written the way a good deputy would summarise the desk before a morning meeting.

**Where the numbers come from.** Every figure is computed in Python first, from the database, before any LLM sees anything — the same discipline as Phase 5 (D-19): applications sitting in one status longer than expected, the value at risk in each bucket, applications that failed their own eligibility check at submission (Piece 19's stored summary earns its keep here), documents still missing on applications waiting for review, and anything approved but not yet disbursed. The LLM turns that already-correct picture into a few readable paragraphs. If the LLM is unavailable the briefing still renders — as the numbers, without the prose.

**Why it demos well.** It uses every phase at once: Phase 1's data, Phase 5's underwriting view of risk, Phase 2's manual for policy phrasing, and the same observability everything else has. And it answers the question an Account Delivery Head actually asks, which is not "does it have a chatbot" but "what does this change on Monday morning".

**Shape:**

- `app/services/briefing_service.py` — gathers the facts (one grouped set of queries, no N+1), then asks the LLM for the narrative, with a deterministic fallback.
- `GET /api/v1/briefing` — manager-only, same role gate as the activity log.
- A card at the top of the manager's dashboard in React, with a refresh and a "how this was worked out" panel showing the underlying numbers, so nothing is a black box.
- Tests in `tests/ours/`, because this is ours, not the trainer's.

---

# PIECE 22 — One assistant in React that gets smarter, with role-gated tools

Decided by Rohit on 2026-09-08, and he was right to push back.

**What was wrong.** Phases 3, 4 and 5 were built as separate things reachable only from a Python prompt or their own Streamlit page. The React Assistant — the screen a customer actually sees, and the one in the demo — still only had Phase 2's brain. So the smartest parts of the product were invisible in the product. Rohit's instinct was that each phase should build *on top of* the Phase 2 chatbot in the same window, and the trainer's own folder layout works against that by giving each phase its own screen. Three chat screens that each know different things is a strange thing to show an Account Delivery Head.

**The endpoint was already designed for this.** `app/routers/chat.py` says so in its own docstring: one chat door, each phase replaces the brain behind it, the `mode` field says which brain answered. The design was right; the wiring just stopped at Phase 2.

### The safety problem this exposes, and it is the important part

`loan_api_client.service_token()` currently mints a **branch manager** token for every AI call, whatever role the person asking actually has. That is fine while the agent is only reachable from a developer's terminal. Wire it into the customer-facing chat unchanged and **a customer asking "show me application 5" gets someone else's loan.**

So the first thing built is not a feature, it is the gate.

### Who gets what

| | Manual (Phase 2) | Read own applications | Read all applications | Change data (Phase 4) | Underwriting review (Phase 5) |
|---|---|---|---|---|---|
| **Customer** | yes | yes | **no** | **no** | **no** |
| **Loan officer** | yes | yes | yes | yes, except disburse | yes |
| **Branch manager** | yes | yes | yes | yes, including disburse | yes |

The officer line is my call, as Rohit asked: officers get everything except paying money out, which mirrors exactly what the Phase 1 screens already allow them to do (D-06). Nothing in the chat lets anyone do something the normal screens would refuse — the chat is a different door to the same building, not a wider one.

### How the gate works

`service_token()` gains a caller argument. Instead of always being a manager, the agent calls the Phase 1 API **as the person who asked the question**. Then every owner-scoped check the API already has — the ones Phase 1 was tested on — applies to the AI exactly as it applies to the browser. A customer's token cannot fetch another customer's application, because the API already refuses that with a 403.

This is deliberately *not* a new permission system. It reuses the one that already exists and is already tested, which is the only kind worth trusting.

### The build order

1. **The gate.** `service_token(email, role)` acts as the caller. Tests that a customer's chat cannot reach another customer's data — the security test comes before the feature.
2. **Phase 3 into the chat.** `/api/v1/chat` routes to the agent instead of the RAG chain. Policy questions still reach the manual, because `search_loan_policy` is one of the agent's five tools. `mode` becomes `"agent"`, and the reply carries which tools ran, so the screen can show it.
3. **The screen.** The Assistant page shows the tools used per answer, the way the Phase 4 chat already does. Sources still show for manual answers.
4. **Phase 4 into the chat, staff only.** The action tools appear only for staff. A destructive instruction restates what it will do and asks first, matching the confirmation dialogs Piece 19 and the detail page already use.
5. **Phase 5 into the chat.** "Assess application 7" runs the four-agent review and shows the verdict with its reasoning.

Each step keeps every existing test green, and each is committed separately.

### Deliberately parked

The trainer's `agent_app.py` (a separate Streamlit screen for Phase 3) is **not** being built. The React Assistant is the demo, and a fourth chat screen nobody opens is not worth the confusion. Recorded in `FUTURE-UPGRADES.md` in case a reviewer asks for it literally.

---

# PIECE 23 — Keeping the AI answering, and saying plainly when it cannot

Decided by Rohit on 2026-09-10, before steps 4 and 5 of Piece 22 get built.

**Why this comes first.** Piece 22's remaining steps put Phase 4 and Phase 5 behind the chat box. Phase 5 is the expensive one: a four-agent review is several AI calls for a single question, so one free Gemini key runs dry quickly. Rohit is collecting spare free keys from friends. There is no point wiring in the feature most likely to exhaust a key before the thing that survives an exhausted key exists.

**Where it goes.** `llm_provider.py` and nowhere else. Its own docstring already forbids any other file from importing a provider class directly, so every phase — the Phase 2 chain, Phase 3's agent, Phase 4's MCP chat, Phase 5's graph — passes through `get_llm()`. Build the rotation there and all five phases inherit it without being touched.

### The ladder, in order

Each rung is tried only when the one above it has genuinely run out.

1. **Gemini key 1**, then key 2, then key 3… from a comma-separated `GOOGLE_API_KEYS` in `.env`. The existing single `GOOGLE_API_KEY` keeps working as a fallback so nothing already set up breaks.
2. **A key is retired for the day** only on a real quota/rate-limit answer (HTTP 429, or Google's `RESOURCE_EXHAUSTED`). A wrong key (`400`/`403`) is a mistake, not an exhausted quota — that one is dropped and logged loudly, because silently rotating past a typo would hide it forever.
3. **Local Ollama**, once every Gemini key is spent. This already exists as a LangChain fallback; it now becomes the last rung rather than the only one.
4. **Offline.** Nothing answered. The chat says so honestly instead of showing a spinner that never ends.

### The error codes

Rohit asked for distinct codes per failure, reasoned out rather than copied. Each is a short machine-readable string in the reply plus a sentence a customer can read. `Assistant.jsx` shows the sentence; the code goes in the logs and is what we grep for when something goes wrong mid-demo.

| Code | What actually happened | What the person sees |
|---|---|---|
| `ai_ok` | normal | (nothing — the answer) |
| `ai_key_invalid` | a key was rejected as malformed or unauthorised | "One of the AI keys is not valid. The others are still being used." |
| `ai_quota_exhausted` | every Gemini key hit its daily limit; fell through to Ollama | "The online AI has reached today's limit, so a local model answered. Answers may be shorter." |
| `ai_provider_unreachable` | network refused / DNS / TLS — Gemini could not even be contacted | "The AI service cannot be reached from this network right now." |
| `ai_local_not_running` | Ollama is not listening on its port at all | "No AI is available. The local model is not running." |
| `ai_local_model_missing` | Ollama answered, but 404s the model name | "The local AI is running but the model it needs is not installed." |
| `ai_local_timeout` | Ollama accepted the request and never finished in time | "The local AI is taking too long to answer. It may not have enough memory on this machine." |
| `ai_local_truncated` | answered, but stopped mid-thought / hit its token ceiling | "The local AI ran out of room before finishing its answer." |
| `ai_all_exhausted` | every rung of the ladder failed | "No AI is available at the moment. Everything else in the app still works." |

The last four are the Wipro-laptop cases Rohit predicted: a small machine running a thinking model can accept a request and then stall or truncate, which is a different problem from not running at all, and lumping them together is what makes a demo failure impossible to diagnose while someone is watching.

### One thing this must never do

Phase 5's numbers are computed in plain Python, never by the LLM (D-19). So an exhausted key can change the *wording* of a review and must never change its *decision*. Whatever this layer does on failure, the verdict, the EMI, the DTI and the risk tiers stay exactly as they were.

### Health, so we know before the demo does

`/api/v1/health` already reports a `chat_fallback`. It gains an honest summary: which provider is live, how many keys remain unspent, and whether Ollama is answering. A traffic light we can look at *before* presenting rather than discovering mid-question. This is a read of local state, not an AI call — checking it costs no quota.

### The build order

1. Key rotation and the ladder inside `llm_provider.py`, with the error codes. Unit-tested with fake failures — **no real API calls**, so this costs nothing to build and verify.
2. The health summary.
3. The codes surfaced through `/api/v1/chat`, and the sentence shown in `Assistant.jsx`.

Only then do Piece 22 steps 4 and 5 get built on top.

---

# PIECE 22 STEP 4 — Phase 4's tools in the chat, staff only, with a confirmation

Planned 2026-09-10. This is the step with teeth: three of Phase 4's six tools
change real records, and one of them can reject or disburse a loan.

### What changes

`build_agent()` learns a role. Today it always builds the same five read-only
tools; now the toolset depends on who is asking:

| Role | Tools |
|---|---|
| Customer | the five read-only Phase 3 tools, exactly as today |
| Loan officer | those five **plus** Phase 4's write tools |
| Branch manager | the same as an officer |

Officer and manager get the same list on purpose. The difference between them
is disbursement, and that is **already enforced by the API**
(`application_service.py:271` refuses it to anyone who is not a manager). Adding
a second rule here would be a second place to get it wrong, and the two could
drift. The officer's disburse attempt comes back as a 403 the agent reads aloud.

### The gate is nearly free, and that is the point

Phase 4's MCP tools already call the API through `app.services.loan_api_client`,
the same client Phase 3's tools use, and `service_token()` already reads the
`acting_as()` ContextVar. The chat endpoint already wraps the agent call in
`acting_as(user.email, user.role.value)`. So the moment those tools are in the
list, they run as the person who typed the question and inherit every
owner-scoping and role check Phase 1 was tested on. No new permission logic.

### The confirmation, chosen by Rohit on 2026-09-10

Type the change, then confirm in the chat:

1. Staff types "reject application 5, income too low".
2. The assistant does **not** act. It replies: *"I am about to reject
   application 5, with the reason 'income too low'. Reply YES to go ahead."*
3. Only the next message carrying a yes performs it.

So the endpoint has to remember one pending action per person between two
messages. Kept server-side, keyed by user email, never in the browser
(Rule 13). One pending action per person, replaced if they type a different
instruction — no queue, nothing to get out of order.

**A pending action expires.** Five minutes, so an abandoned "reply YES" cannot
be completed by accident an hour later when the screen has scrolled and nobody
remembers what #5 was.

**Only writes are gated.** Reading is free and instant, as now. Wrapping reads
in a confirmation would make the assistant tedious and teach staff to type YES
without reading it, which is worse than no confirmation at all.

### How the write actually happens

The confirmation cannot be left to the model. If the agent were asked to
remember the pending change and re-issue it on "yes", a model that hallucinates
a different application number disburses the wrong loan. So the pending action
is captured as **plain data** — tool name and arguments — and on confirmation
that exact recorded call is executed directly, with no second visit to the LLM.
The model decides *what to propose*; Python decides *what runs*.

### The build order

1. Role-aware `build_agent(role)` and a per-role agent cache in the router.
2. The pending-action store, with its expiry.
3. The write tools, which propose rather than act.
4. Confirmation handling in `/api/v1/chat`.
5. Tests: a customer cannot see the write tools at all; an officer's disburse
   is refused by the API; a write needs a yes; an expired action does nothing.

---

# PIECE 24 — The customer's own profile page, with edits that staff approve

> **Update 2026-09-22.** Its open questions were answered while planning the Document intelligence programme below:
> - **The customer proposes the new values; staff approve**, and approving applies them. The old value keeps being used until then.
> - **Editable by request:** phone, annual income, employment status, years with employer, existing EMIs.
> - **Not editable:** name, email, date of birth, CIBIL score (it comes from the bureau).
> - **Proof documents are required** for everything except phone, so this piece is built **after Pieces 31–34** (real uploads and reading documents).
> - An approval re-checks eligibility on open applications (as Piece 25 does).
> - Staff see requests on a *Profiles* tab of the Edit requests page, plus a staff page for each customer.
> - A payslip's extracted net pay can *suggest* the new income, but never sets it on its own.

Asked for by Rohit on 2026-09-16, straight after the D-27 fix. **Not planned in
detail yet — this is a placeholder so the ask does not get lost.** The next
session plans it properly and asks him the open questions before building.

### What he asked for

- A customer, logged in, can see a profile page of their own details.
- They can edit some of those fields themselves — including their existing
  monthly EMIs, which today can only be set once at signup and never changed.
- Only "safe" fields are editable. Rohit left the choice of which ones to me.
- A customer can only ever see their own profile, never anybody else's.
- Loan officers and managers can see any customer's profile details, including
  the existing-EMI figure.
- When a customer edits a field, the change does **not** apply immediately. It
  goes to the loan officer and the manager as a request, and either of them can
  approve it.

### The open questions, for the session that plans this

1. Which fields are safe to self-edit? The honest split is that anything the
   lending decision rests on — income, CIBIL, employment, date of birth,
   existing EMIs — cannot be changed on the customer's word alone, which is
   exactly why he wants the approval step. Contact details (phone) are lower
   stakes. Name and email touch identity and login.
2. Does the *current* value keep applying while a change is pending? It has to,
   or a customer could stall an unfavourable figure by editing it.
3. What happens to an application submitted while an edit is pending?
4. Does an approved edit re-run the stored eligibility assessment on that
   applicant's open applications? Piece 19 stores that assessment permanently,
   so an approved income change makes the stored note stale.
5. New table, or a status column? A pending-change table is the honest shape,
   since one customer can have several fields in flight at once.
6. Where do staff see the queue — the existing activity page, the dashboard, or
   a page of its own?

### What this must not break

Piece 19's stored eligibility summary, and the D-27 affordability maths that
now reads `existing_monthly_emi` in two places. Both Phase 1's form check and
Phase 5's Risk Assessor use that field, so a change to it moves real verdicts.

---

# PIECE 25 — Customers ask to edit their application, staff approve or refuse

Asked for by Rohit on 2026-09-22 (`TO-FIX-SORTED.md` B1, his top priority).
Planned the same day; the full plan is in
`~/.claude/plans/trainer-himself-said-to-kind-breeze.md`. This is the short
version.

### Why

A customer who spots a mistake after submitting has no way to fix it. The
trainer's manual said "withdraw and resubmit", but withdraw was never built.
The trainer then said to change this rule (D-28). So a customer now **asks**,
bank staff **approve or refuse** (a refusal must give a reason), and only
after approval can the customer change the fields they asked for, **once**.
Every step lands in the activity log.

### Settled 2026-09-22

- Edits are only possible while the application is **submitted** or **under review** (A1).
- Only **amount, tenure and purpose** can change. Loan type can't: a different type means a new application.
- An approved edit **re-checks eligibility** and replaces the stored result. The old result is kept in the activity row.
- **No email.** The staff page does the job. The customer sees "Questions? Contact support@bank.com" (a placeholder), and the chatbot gives the same address.
- Every input is checked in **three places**: the form, the server's schema, and the database itself.

### My defaults (Rohit can overturn any of them)

- One open request per application.
- Approval unlocks the fields for one save.
- Staff decide the whole request, not part of it.
- Either an officer or the manager can decide.
- A reason is 10 to 1,000 characters. A refusal note is required, 10 to 1,000 characters.
- A request is closed automatically if the status moves on.
- Saving with nothing changed is refused.

### Steps (one per turn, each committed and tagged)

| Step | What | Tag |
|---|---|---|
| 1 | Rules, the new `application_edit_requests` table, schemas, the `check_free_text` helper, and the database's own checks (triggers on `loan_applications`, CHECK rules on the new table) | v2.5.0 ✅ |
| 2 | `edit_request_service.py`, the new addresses, `PATCH /applications/{id}`, closing open requests on a status move, API tests | v2.6.0 ✅ |
| 3 | React, the customer's side: `EditRequestCard` on the application page, the two-step pop-up, the unlocked-fields form, the support-email note | v2.7.0 ✅ |
| 4 | React, the staff side: the "Edit requests" page and sidebar item, and activity labels for the five new events | v2.8.0 ✅ |
| 5 | Manual (Section 6, the FAQ, a new "Contacting the bank" section), the T-102 ingestion fix, re-ingest, and asking the chatbot twice | v2.9.0 ✅ |

### What this must not break

- The trainer's 20 Phase 1 tests. The new database checks use only the global bounds, and every trainer row sits inside them.
- The Phase 2 ingestion tests.
- D-22: no dates baked into stored text.
- D-27: affordability goes through the same helper.

---

# PIECE 26 — The database checks its own rules for the other tables

Placeholder, decided 2026-09-22 while planning Piece 25. Piece 25 found that
SQLite checks almost nothing by itself: it ignores `VARCHAR` lengths, it
doesn't check enum values, and foreign keys are off on purpose (T-03). Piece 25
fixes that for `loan_applications` and its own new table. This piece does the
same for **applicants, users, documents and status history**, using the same
pattern (triggers built from `rules.py`, see `backend/app/db_checks.py`).

Needs its own plan first. The trainer's database tests insert rows directly,
some with made-up values (for example `phone="1234567890"` in DB-01, which our
schema would refuse), so every trigger has to be checked against those tests
before it's added.

---

# DOCUMENT INTELLIGENCE PROGRAMME — Pieces 27 to 38

Planned 2026-09-22 with Rohit, across several rounds. **Built so far: 27 to 35, plus 32d (Replace)** (see Done at the bottom); 36 is next. Rohit implements these himself, **one piece at a time, in the order below**. Each piece is finished, tested and checked in the browser before the next one starts. The full reasoning, with the research sources, is in `~/.claude/plans/trainer-himself-said-to-kind-breeze.md`. The decisions are also recorded in `TRAPS-AND-DECISIONS.md` (Settled, 2026-09-22).

## Build order

| Order | Piece | One line | Needs first | Size |
|---|---|---|---|---|
| 1st | **27 — Admin role** | A System Administrator who can see everything but can't do loan business | — | Small |
| 2nd | **28 — Admin settings + document mode switch** | Admin turns "real document uploads" on or off | 27 | Small |
| 3rd | **29 — Top navigation bar** | The sidebar becomes a sticky, see-through bar at the top, with a spot for the bell | — | Small–medium |
| 4th | **30 — In-app notifications** | Separate notification tables; the bell shows staff and customer notices | 29 | Medium |
| 5th | **31 — Real upload foundation** | Real files: safety gate, rebuild, standards, TEST/REAL, encrypted storage outside the project | 28 | Large |
| 6th | **32 — TEST-document workflow** | TEST badges everywhere, staff notified, admin can clear TEST documents | 30, 31 | Small–medium |
| 7th | **33 — Document kinds + fields, typed by hand** | Aadhaar shows Aadhaar fields, and so on; the user types them; no AI | 31 | Medium |
| 8th | **34 — Reading documents** | Local OCR, patterns and checksums fill the fields; Gemini only for TEST documents | 33 | Large |
| 9th | **35 — Several documents at once** | A batch of up to 5, each processed on its own, missing fields per document | 34 | Medium |
| 10th | **36 — Saved chat sessions** | The Assistant keeps past conversations | — | Medium |
| 11th | **37 — Documents in the chatbot** | 📎 in chat → the same pipeline | 34, 35, 36 | Medium |
| 12th | **38 — Per-document missing-field form in the chat** | A structured form inside the chat, one Confirm & submit | 37 | Small–medium |

**Can move earlier:** 29 and 30 don't depend on any document work, and 36 stands alone. **Parked, and they come after this programme:** Piece 24 (profile changes with proof, needs 31–34), Piece 26 (database checks for the other tables), B2 (slow chatbot answers).

**How every piece is done** (the same loop as always):
1. Read the piece below and the files it names.
2. Answer its open decisions, if any.
3. Build it.
4. Run `pytest tests/ours tests/phase1 -q`, plus the non-AI Phase 3 and 4 tests (`tests/phase3/test_context.py`, the offline tests in `tests/phase3/test_tools.py`, and `tests/phase4/test_mcp_server.py`). Then `npm run build` and `npm run lint` in `frontend/`.
5. Update `user_manual.md` if any rule changed (Rule 12), and re-ingest.
6. Log it, commit it, and tag it (middle digit: v2.10.0, v2.11.0, and so on).
7. ~~Check it in the browser with the demo logins, **before** starting the next piece.~~ **Changed 2026-09-24 (Rohit):** browser checks are batched. Each piece still writes its browser check, but they're all run together once the programme's pieces are built. Pending so far: Piece 32d (Replace), Piece 33 (details form), Piece 34 (upload each demo-kit PDF; the Aadhaar's stored copy shows the digits blacked out), Piece 35 (Upload several → three demo-kit PDFs → Upload all → Confirm all; Rajan's bell shows 3, which is expected).

## Decisions that apply to every piece (settled 2026-09-22)

- **Admin = System Administrator.** It sees the whole system and administers it. It has **no loan-business authority** (no creating, approving, rejecting, disbursing or changing loan records), and it is **not** a branch manager.
- **Notifications are a completely separate system from the activity log**, with their own tables, service, recipients, types and read/unread state. Only three triggers exist:
  - **staff**: a customer asks to edit a submitted application
  - **staff**: a customer uploads a document declared TEST
  - **applicant**: *their own* application's status changes

  The app's own notifications only: no email, SMS or push.
- **TEST documents count towards the checklist**, but are always visibly marked ("4/4 submitted, including 2 TEST documents"). Four facts stay separate: *submitted*, *identified as a kind*, *marked TEST*, *verified/authenticated*. Counting never means authentic.
- **Identification ≠ authenticity.** "Looks like a PAN card" is never "a genuine PAN card".
- **No Ollama or local LLM.** Gemini is the only LLM. Local *non-LLM* processing (PDF text, image work, OCR, patterns, checksums, parsing) is preferred wherever it works.
- **REAL documents never go to Gemini** by default: not the image, not the text. **TEST documents may.** Google's free-tier terms let it use submissions and have people read them, and say not to send personal data (T-108).
- **Uploaded files live outside the project folder**, at a path set in `.env`, and are encrypted. The project currently sits in OneDrive, which Rohit will move (T-112).
- **Security is proportional.** Must-have protections for the demo are built. Production hardening goes to `FUTURE-UPGRADES.md` (the "Document intelligence — production hardening" section).
- **Extracted document data never overwrites the profile.** Profile changes only happen through Piece 24's staff approval.
- **The trainer's name-only document route stays exactly as it is**, because Phase 1 UNIT-07 and Phase 4 MCP-06 use it.

---

# PIECE 27 — Admin role

**Goal:** a new **System Administrator** role that can **view** the whole system and administer it, but **can't act** in the loan business. Branch manager, loan officer and customer behave exactly as before.

**Needs first:** nothing. **Open decisions:** none (D1 settled).

**Status: built 2026-09-22, tag `v2.10.0`.** Where the build differs from the plan below:
- **No `AdminUserResponse`.** `UserResponse` (from `/auth/me`) already has exactly the six fields, so `AdminUserListResponse` reuses it. The query is in a small new `services/admin_service.py`.
- **`homeFor` lives in `frontend/src/auth/home.js`**, not in `AuthContext.jsx`. A file that exports components should export nothing else, or Vite's fast refresh (and the linter) complains.
- **The chat's review refusal has its own sentence for the admin.** The customer's sentence says "your own application", which means nothing to an admin. Customers get exactly the same words as before.
- **A small `ViewOnly` component** (`components/ViewOnly.jsx`) is the "View only" note in all three places, and there's a new `settings` icon for the Administration link. The Assistant link stays where it is for every role.
- **Streamlit is unchanged.** It treats the admin like a customer, and the API still refuses every action (T-116).
- **Browser check step 1:** a restart alone doesn't create the admin. Run `seed.py`.

### What exists today (inspected 2026-09-22)
- `UserRole` in `backend/app/models/user.py:16-20` has `applicant`, `loan_officer`, `branch_manager`, mirrored in `rules.ROLES` (`rules.py:49`). The `role` column is plain text in SQLite, so **no database change is needed** for a new value.
- `rules.STAFF_ROLES = {"loan_officer", "branch_manager"}` (`rules.py:52`) is used in three sensitive places:
  - which chatbot tools a role gets (`agent/agent.py:107-124`; staff get the write tools)
  - who may run a four-agent review (`routers/chat.py:331`)
  - the chat's per-role agent cache

  **So `admin` must NOT be added to `STAFF_ROLES`.**
- **Sign-up gap:** `POST /auth/register` accepts a `role` and only refuses `applicant` and `branch_manager` (`services/auth_service.py:42-45`). Once `admin` exists, anyone could register as an admin unless it's refused too.
- Guards in `backend/app/dependencies.py:65-84`: `require_role(...)`, `require_staff` (officer or manager), `require_manager`.
- Many addresses use plain `get_current_user` and treat "not a customer" as staff, because the services only restrict `applicant`. For *views* that already gives an admin the right access. For three *creating actions* it would wrongly let an admin act.
- Seeding (`backend/seed.py:86-103`) returns early if Anita exists, so an admin added there would never reach the existing `loan_app.db`.
- React:
  - `AuthContext.jsx:53-55` defines `isApplicant`, `isStaff`, `isManager`
  - `App.jsx:20-39` has `RequireAuth` / `PublicOnly` and role arrays, and every redirect goes to `/applications`
  - `Login.jsx:25` goes to `/applications`
  - `Layout.jsx:41-48` builds the sidebar links by role
  - the "New application" buttons (`ApplicationList.jsx:113, 215`) and the add-document form (`DocumentChecklist.jsx:114`) show to anyone

### VIEW vs ACT: every address and what changes

| Address | View or act | Guard today | Admin after | Change |
|---|---|---|---|---|
| `GET /applications`, `GET /applications/{id}` | view | any login (customers scoped) | ✅ sees all | none |
| `GET /applicants/{id}` | view | any login | ✅ | none |
| `GET /applicants` (list) | view | `require_staff` | ✅ | → `require_staff_view` |
| `GET /applications/{id}/documents` | view | any login | ✅ | none |
| `GET /applications/{id}/edit-requests` | view | any login | ✅ | none |
| `GET /edit-requests` (the queue) | view | `require_staff` | ✅ | → `require_staff_view` |
| `GET /dashboard/summary` | view | `require_staff` | ✅ | → `require_staff_view` |
| `GET /activity`, `GET /activity/entity/{type}/{id}` | view (audit) | `require_manager` | ✅ | → `require_audit_view` |
| `GET /admin/users` | view (**new**) | — | ✅ admin only | new, `require_admin` |
| `POST /applications` (create) | **act** | any login | ❌ | → `require_business_actor` |
| `POST /applications/{id}/documents` (add) | **act** | any login | ❌ | → `require_business_actor` |
| `POST /applications/check-eligibility` | **act** (part of creating; writes an activity row) | any login | ❌ | → `require_business_actor` |
| `POST /applicants` (create profile) | act | `require_staff` | ❌ | none |
| `PATCH /applications/{id}/status` (approve, reject, disburse) | act | `require_staff` (+ manager for disburse) | ❌ | none |
| `PATCH /applications/{id}/documents/{doc}/verify` | act | `require_staff` | ❌ | none |
| `POST /edit-requests/{id}/approve` and `/refuse` | act | `require_staff` | ❌ | none |
| `POST /applications/{id}/edit-requests`, `PATCH /applications/{id}` | act (customer only) | owner check in the service | ❌ (already refused) | none |
| `GET /briefing` (Morning Briefing) | the manager's daily work list; uses Gemini | `require_manager` | ❌ **kept manager-only**: it's an operational tool, not monitoring | none |
| `POST /chat` | view, through the chatbot | any login | ✅ **read-only chatbot**: not in `STAFF_ROLES`, so no write tools and no reviews; its lookups use the view access above | none |
| `GET /auth/me` | view | any login | ✅ | none |

### Backend changes
1. **`models/user.py`:** add `admin = "admin"` to `UserRole`. **`rules.py`:** add `"admin"` to `ROLES` and a constant `ADMIN_ROLE = "admin"`, with a comment saying why it is *not* in `STAFF_ROLES`.
2. **`dependencies.py`**, new guards built on `require_role`, each with a comment:
   - `require_admin = require_role(UserRole.admin)`
   - `require_staff_view = require_role(UserRole.loan_officer, UserRole.branch_manager, UserRole.admin)`: "can look at staff screens"
   - `require_audit_view = require_role(UserRole.branch_manager, UserRole.admin)`: "can read the audit log"
   - `require_business_actor(user = Depends(get_current_user))`: raises 403 with *"The system administrator can view records but cannot create or change them."* if `user.role == UserRole.admin`, otherwise returns the user.
3. **Swap the guards on the 7 rows marked in the table** (applicants list, queue, dashboard, both activity routes, create application, add document, eligibility check). Nothing else changes, and `require_staff` / `require_manager` stay exactly as they are.
4. **`auth_service.register_staff`:** refuse `UserRole.admin` with *"Administrator accounts are created by the bank, not by registration"* (router already turns `RuleViolation` into 422).
5. **New `backend/app/routers/admin.py`:** `GET /api/v1/admin/users` (`require_admin`) returns every user (`id`, `name`, `email`, `role`, `is_active`, `created_at`) plus `counts_by_role`. Schema `AdminUserResponse` / `AdminUserListResponse` in a new `schemas/admin.py`. Register in `main.py` with prefix `/api/v1/admin`.
6. **`seed.py`:** a new idempotent `ensure_admin(db)` that creates `System Administrator` / `admin@bank.com` / `Admin@123` **if missing**. `main()` calls it **before** the "Seed data already present" early return, so the existing database gets the admin too. Add `ADMIN_PW` next to the other passwords, and print the admin login at the end.

### Frontend changes
7. **`auth/AuthContext.jsx`:** add `isAdmin`, `canViewStaffScreens` (staff or admin) and `canViewAudit` (manager or admin), plus an exported helper `homeFor(user)` (admin → `/admin`, everyone else → `/applications`).
8. **`App.jsx`:**
   - `RequireAuth`'s role-mismatch redirect, `PublicOnly` and the `*` route all go to `homeFor(user)`
   - `ADMIN = ["admin"]`
   - `/dashboard` and `/edit-requests` → `[...STAFF, "admin"]`; `/activity` → `["branch_manager", "admin"]`
   - `/applications/new` → `["applicant", ...STAFF]`
   - new `/admin` → `ADMIN`
9. **`pages/Login.jsx`:** `login()` already returns the user, so navigate to `location.state?.from || homeFor(me)`.
10. **`components/Layout.jsx`**, links for admin: **Administration** (new), **All applications**, **Dashboard**, **Edit requests**, **Activity**, **Assistant**. Hide "New application" for admin. `Dashboard`/`Edit requests` use `canViewStaffScreens`, and `Activity` uses `canViewAudit`.
11. **Hide action controls from admin**, with a small muted "View only" line where they would be:
    - `ApplicationList.jsx`: both "New application" buttons
    - `DocumentChecklist.jsx`: the add-document form
    - `EditRequests.jsx`: the Approve/Refuse buttons

    "Update status" and "Mark verified" are already `isStaff`-only.
12. **`pages/ApplicationDetail.jsx`:** the "Everything that happened" audit panel (lines ~92 and ~267) shows for `isManager || isAdmin`.
13. **New `pages/Admin.jsx`, "System administration":**
    - a short explanation of the role
    - a count per role
    - a table of all accounts (name, email, role, active, joined)
    - a note: "Settings arrive in the next piece."

    Use the existing `card`, `table-wrap`, `pill` and `EmptyState`.

### Manual (Rule 12)
14. `backend/rag/user_manual.md`, Section 2 "Roles and Permissions": add an **Administrator** paragraph. The administrator:
    - can see every customer, application, document, edit request, the dashboard and the audit log
    - manages system settings and user accounts
    - **cannot** create, approve, reject or disburse anything, or change a loan record
    - is created by the bank and can't register

    Re-ingest: `venv\Scripts\python.exe -m rag.ingest`.

### Tests: new `backend/tests/ours/test_admin_role.py` (offline, no Gemini)
Helper `_admin_token(client)`: register a user, set `role = UserRole.admin` through `TestingSessionLocal`, then log in. The same pattern as `_manager` in `test_edit_requests.py`.
- `POST /auth/register` with `"role": "admin"` → **422**; with no role → 201 and `loan_officer` (the trainer's default, unchanged).
- Admin `GET /auth/me` → `role == "admin"`.
- **Admin can view (200):**
  - `GET /applications` and `/applications/{id}`
  - `GET /applicants` and `/applicants/{id}`
  - `GET /applications/{id}/documents`
  - `GET /applications/{id}/edit-requests`
  - `GET /edit-requests`
  - `GET /dashboard/summary`
  - `GET /activity` and `/activity/entity/application/{id}`
  - `GET /admin/users` (counts include every role)
- **Admin cannot act (403):**
  - `POST /applications`
  - `POST /applicants`
  - `POST /applications/{id}/documents`
  - `PATCH …/documents/{id}/verify`
  - `PATCH /applications/{id}/status`
  - `POST /edit-requests/{id}/approve` and `/refuse`
  - `POST /applications/check-eligibility`
  - `GET /briefing`
  - `POST /applications/{id}/edit-requests`
  - `PATCH /applications/{id}`
- `GET /admin/users` → 403 for an officer, a manager and a customer.
- `agent.agent.tools_for("admin")` contains **no** tool from `WRITE_TOOLS`.
- `seed.ensure_admin(db)` run twice → exactly one admin row.
- Existing suites unchanged: `tests/ours` + `tests/phase1` (286 before this piece).

### Must not break
- Trainer Phase 1 (registration defaults to loan officer; `test_db`), Phase 3 tool and prompt tests, Phase 4 MCP tests (they call the API as the service account `anita@bank.com`, a manager: unchanged).
- The manager's disbursement rule (`application_service.py:271`), the chatbot's write tools and reviews (still `STAFF_ROLES` only), and every customer-scoping check.

### Browser check
1. Run `venv\Scripts\python.exe seed.py` from `backend/` (a restart alone doesn't create the admin), then log in as **admin@bank.com / Admin@123**. You land on **System administration** with every account listed.
2. All applications → open one. Everything is visible, but there's **no** Update status, Add document or New application; a "View only" note shows instead.
3. Edit requests: the queue is visible, marked View only, with no Approve or Refuse. Dashboard and Activity open.
4. Assistant: "how many applications are under review?" gets an answer. "Assess application 7" is refused (staff only).
5. Anita, Rajan, Priya: everything exactly as before, and nobody else has an Administration link.

---

# PIECE 27a — What the assistant says to the administrator

Built 2026-09-23, just after midnight, tag `v2.10.1`. Found by Rohit that evening: signed in as
the admin, he typed *"change application 21 to under review"* and the assistant
answered *"I cannot change submitted applications directly. To get help with
your application, please email our support team at support@bank.com."*

**What was wrong.** Nothing unsafe — the admin has no record-changing tools, so
no change was ever possible. But the assistant knew only two kinds of person:
`agent.py` asked "is this role in `STAFF_ROLES`?" and gave everyone else the
customer prompt. The admin is not staff, so it was spoken to as a customer:
"your application", and an instruction to email the customer support address.
It also never looked application 21 up, so it didn't say the true reason.

**The fix.** A third prompt, `ADMIN_EXTRA` + `ADMIN_REACT_TEMPLATE`, chosen by
the new `template_for(role)` next to `tools_for(role)`. The twelve-line ReAct
format block became one `REACT_FORMAT` constant shared by all three prompts;
the customer's and staff's prompts are unchanged character for character, which
a test checks. **This changes only what a refusal says.** What actually stops a
change is the tool list, and that is untouched.

## The cases it covers, and what the admin is told

**How to speak to them:** never "your application", never "email
support@bank.com" (that is the customers' address), and look a record up before
answering a question about it.

| If the admin asks to… | The answer says | Who does it instead |
|---|---|---|
| Move an application to under review, approve or reject it | The administrator can view records but not change them | A loan officer or the branch manager |
| Disburse an approved loan | Same | The branch manager only |
| Create or submit an application, or change its amount, tenure or purpose | Same | The customer, after staff approve their edit request |
| Add a document | Same | The customer or bank staff |
| Mark a document verified | Same | Bank staff |
| Approve or refuse an edit request | Same | A loan officer or the branch manager |
| Create a borrower profile, or change a customer's details | Same | Bank staff |
| Run a full underwriting review | Refused in code before any AI call, with its own sentence | Loan officers and the branch manager |

| Things nobody can do through the assistant, whoever asks | What it says |
|---|---|
| Create, delete or switch off an account; change a role or a password | Accounts are created by the bank |
| Delete, hide or edit a record or its history | LAMS keeps a permanent audit trail on purpose |
| Change a rule, a limit, an interest rate or a fee | Those are policy; the manual states them |
| Change a system setting | Not something the assistant can do |
| Send an email, a text or a notification | The app has no sending of any kind |
| Read the activity log, or list the accounts | They are on the Activity page and the System administration page, which the admin can open |
| Act as, or on behalf of, another person | Refused |
| Insist, or claim the role makes the limits not apply | The same answer, in the same words |

## Tests (offline, no Gemini)
`tests/ours/test_admin_role.py` gained 17: each role gets its own prompt, the
customer's prompt picks up neither other paragraph, all three still render with
the four ReAct variables (a stray brace would crash at the first message), and
the admin prompt names every case in the tables above. 331 passing.

**Not checked against a live Gemini yet.** Rohit asked to leave it, because at
midnight answers were taking 75 seconds; at 3pm the same questions took 3 to 8
seconds, with only the manual ones slow (T-119). Try it when it is quick again:
sign in as the admin and type *"change application 21 to under review"*.

---

# PIECE 28 — Admin settings + document mode switch

**Goal:** the admin can turn **"Real document uploads"** ON or OFF for the whole app. **OFF = today's behaviour exactly** (type a file name). ON is the switch that Piece 31's real uploads will read. This piece builds the switch and the settings system, not the uploads.

**Needs first:** 27. **Open decisions:**
- **D10**: if the switch is turned OFF after real files exist, what happens? Recommended: existing files stay viewable, and only *new* uploads go back to name-only. Confirm when Piece 31 is built.
- **Who sees the current mode:** everyone needs to *read* it (the form changes), and only the admin can *change* it.

**Status: built 2026-09-23, tag `v2.11.0`.** Where the build differs from the plan below:
- **The words for each position live in `rules.SETTINGS`** (`off_text`, `on_text`) and are served with the setting, so the screen has no second copy of what the switch means. A new read address, `GET /api/v1/admin/settings/real-uploads` (admin only), carries them along with who changed it and when — the plan's screen needed that and had nowhere to get it.
- **The key check is a trigger, not a CHECK rule in the table.** A CHECK rule is baked in when the table is created, so a database made today would refuse a setting added in Piece 31, and SQLite can't alter a CHECK without rebuilding the table. The trigger is rebuilt from the registry on every startup. Piece 25's table could use a CHECK because its list of statuses never grows; this list is meant to.
- **The body takes `StrictBool`.** Plain `bool` in Pydantic accepts `"yes"`, `"true"` and `1`. A switch that changes the app for everybody takes `true` or `false` and nothing else. Two tests were failing until this changed, which is how it was found.
- **The manual gained a sentence** in Section 4 saying documents are recorded by name today and the file itself is not stored yet (Rule 12). It has always promised PDF/JPG/PNG uploads under 5 MB, which the code has never done — see T-120.
- **`entity_type="setting"`** was added to the activity page's filter list, so a manager can search for setting changes.
- **Not tried against a live Gemini.** Rohit asked to skip AI testing that night (T-119). The manual was re-ingested: 56 chunks.

### What exists
There's no settings table and no settings screen. There's nowhere to store an app-wide flag; `.env` is per-machine and needs a restart.

### Data
- **New table `app_settings`** (model `backend/app/models/app_setting.py`):

  | Column | Type |
  |---|---|
  | `key` | String(64), primary key |
  | `value` | Text, JSON-encoded |
  | `updated_by` | String(150), nullable |
  | `updated_at` | DateTime (timezone), `server_default=now()` / `onupdate` |

  Registered in `models/__init__.py`. It's a new table, so `create_all` makes it with no migration.
- **Registry in `rules.py`**: `SETTINGS = {"real_uploads_enabled": {"type": "bool", "default": False, "label": "Real document uploads"}}`. Unknown keys are refused everywhere. A CHECK rule on `key` limits it to the registry's keys.

### Service and addresses
- New `backend/app/services/settings_service.py`: `get(db, key)` returns the stored value or the registry default, `get_public(db)` returns a dict of every setting, and `set(db, key, value, *, user, meta)` validates the type against the registry, saves, and writes an **activity** row `setting_changed` (`{"key", "from", "to"}`). That's audit only: **no notification** (settled).
- `GET /api/v1/settings` (any logged-in user) → `{"real_uploads_enabled": false}`.
- `PUT /api/v1/admin/settings/real-uploads` (`require_admin`), body `{"enabled": true}` (Pydantic, `extra="forbid"`) → the new value.

### Frontend
- New hook `frontend/src/settings/useSettings.js`: fetches `GET /settings` once per page load, returns `{ realUploads, reload }`. The flag lives only in memory, like everything else (Rule 13 only allows the login token in the browser).
- `pages/Admin.jsx`: a **Settings** card with a labelled toggle (checkbox styled as a switch), a sentence explaining each position ("OFF: documents are recorded by name, as today. ON: customers upload real files (available from Piece 31)."), who changed it last and when, and a confirmation pop-up before switching.
- `DocumentChecklist.jsx`: reads `realUploads`. OFF → exactly today's form. ON → a small info banner ("Real uploads are switched on; the upload screen arrives with Piece 31. Names are recorded meanwhile.") above today's form. Piece 31 replaces this.
- `utils/activity.js`: label `setting_changed` → "Setting changed" (icon `shield`), detail labels `key`, `from`, `to`.

### Tests (`tests/ours/test_settings.py`)
- The default is `false` with nothing stored.
- `PUT` as admin → 200, and `GET` reflects it. As officer, manager or customer → 403. A non-boolean body or extra keys → 422.
- An activity row `setting_changed` is written with from/to, and **no notification row** once Piece 30 exists (add that assertion then).
- Setting an unknown key through the service → error.

### Must not break
The OFF path is byte-for-byte today's form. The trainer tests don't touch settings.

### Browser check
- Admin → System administration → Settings → switch ON (confirm), and it shows who changed it and when.
- As Priya on an application: the info banner appears above the old form.
- Switch OFF: the banner is gone.
- Anita → Activity shows "Setting changed".

---

# PIECE 29 — Top navigation bar

**Goal:** move the navigation from the left sidebar to a **sticky, translucent top bar**. It fits the current design, respects role-based links, and has a spot for the notification bell (filled in by Piece 30). **No functional changes.**

**Needs first:** none. Build it after 27 so the admin links exist. **Open decisions:**
- **D9**: with 6–7 links plus the bell and the account, what goes where? Recommended: page links in the bar; name, role and **Sign out** in an avatar menu on the right; at narrow widths the links scroll sideways, as the current small-screen layout already does.
- **Colour:** keep the current dark brand colour as a translucent dark bar (`rgba(15, 23, 42, 0.78)`) with a blur, or a light translucent bar. Recommended: **dark translucent**, which matches today's sidebar.

**Status: built 2026-09-23, tag `v2.12.0`. Both recommendations above were taken** — links in the bar, the account behind the initials, dark translucent. Say the word if you want the light bar instead; it is two token values (`--topbar-bg` and the link colours). Where the build differs from the plan below:
- **The account menu closes on a page change by comparing the address while rendering**, not in an effect. An effect would draw the new page once with the menu still open and again with it shut, which is exactly what the linter's "cascading renders" warning is about. It was a new warning until this changed, and the count is back to the 11 that were already there.
- **Three widths, not one.** Under 1100px the brand's "Branch portal" line goes, under 980px the brand name goes, and under 560px the links become icons only. One breakpoint left the bar wrapping onto two rows on a phone.
- **The bell is a real component that renders nothing** (`components/NotificationBell.jsx`), so Piece 30 changes that one file and the bar's layout is already final.
- **The `bell` icon is in `Icon.jsx` now**, unused until Piece 30, as the plan says.

**Second pass, same day (`v2.12.1`), after Rohit said it looked cheap and not translucent.** He was right on both counts:
- **It was 78% opaque**, which is paint, not glass. Now 0.68 with a 20px blur and the colour behind it boosted, which is as transparent as it can be while white text stays comfortably readable on it.
- **Glass over one flat colour still looks like paint**, because the blur has nothing to pick up. The page now carries two very soft pools of bank blue across its top, fixed in place so they stay behind the bar while the content scrolls.
- **Third pass (`v2.12.2`): the sideways jump when changing page.** Not the transition at all — the scrollbar. A long page has one, a short page does not, and losing it makes the window ~15px wider, so everything centred slides right and back. `html { scrollbar-gutter: stable }` keeps the space reserved either way. It only became visible in Piece 29 because the page is centred now; beside a fixed sidebar only the right-hand edge moved. Each page also fades in over 160ms (opacity only — a transform would break `position: fixed` pop-ups inside it) and starts at the top, since React Router leaves the scroll where it was.
- **The bar was cramped.** 62px tall now, hairline dividers separating the brand, the links and the account, pill-shaped links, the current page as a brighter pane of the same glass with a lit top edge, a small capitalised "BRANCH PORTAL" under the name, and the initials in a slate gradient with the chevron turning when the menu opens.

### What exists
- `components/Layout.jsx`: `<div class="shell">` with `<aside class="sidebar">` (brand, `nav.sidebar-nav` links from an array with `show` flags, a footer with avatar and Sign out) and `<main class="page"><Outlet/></main>`. `isActive()` has a special case for `/applications`.
- `styles.css:100-160`: sidebar styles, width from `--sidebar-w: 244px`.
- `styles.css:779-803`: under 860px the sidebar already lays down as a top row with scrolling links.
- **Sticky table headings:** `thead th { position: sticky; top: 0 }` (Session 29). Under a sticky top bar they would slide *under* the bar. They must stick at `top: var(--topbar-h)` instead.
- Modals (`.modal-overlay`) must stay above the bar (z-index).

### Changes
- `Layout.jsx`: replace `aside.sidebar` with `header.topbar`:
  - brand on the left
  - `nav.topnav` with the **same links array and `show` rules** (no change to who sees what)
  - on the right, a `<div className="topbar-actions">` holding an **empty `NotificationBell` slot** (a component that renders nothing until Piece 30) and an **avatar menu button** that opens a small panel with the name, role and Sign out

  Keep `isActive()`. Add `aria-current="page"` on the active link and a "Skip to content" link for keyboard users.
- `styles.css`:
  - new tokens `--topbar-h: 58px`, `--topbar-bg: rgba(15, 23, 42, 0.78)`
  - `.topbar { position: sticky; top: 0; z-index: 50; height: var(--topbar-h); backdrop-filter: saturate(1.4) blur(10px); background: var(--topbar-bg); border-bottom: 1px solid rgba(255,255,255,.08); }`
  - `.shell` becomes a column
  - `.page` keeps its max width, centred
  - `thead th` sticky at `top: var(--topbar-h)`
  - `.modal-overlay` z-index above 50
  - the small-screen rules are reworked for the bar (links scroll sideways; the avatar menu stays)
  - remove the sidebar-only rules once nothing uses them
- `components/ui/Icon.jsx`: add a `bell` icon (needed in Piece 30; harmless now).

### Tests
Front-end only. `npm run build` and `npm run lint`: no new errors. The backend suite is untouched.

### Browser check (all four roles; widths 1280, 980, 860, 390)
- The bar stays at the top while scrolling a long list, and the page shows faintly through it.
- Table headings stick just *below* the bar.
- Pop-ups cover the bar.
- Each role sees exactly the links it saw before, in the same order.
- The avatar menu opens and closes (Escape, clicking outside) and Sign out works.
- Keyboard: Tab reaches the skip link, every link, the avatar menu.

---

# PIECE 30 — In-app notifications (separate system)

**Goal:** the app's own notifications, a bell with an unread count in the top bar, as a **system completely separate from the activity log** (its own tables, service, recipients, types, read/unread). **Only three triggers.**

**Needs first:** 29 (the bell slot). **Open decisions:**
- **Does the admin receive staff notifications?** Not specified. Recommended: **no** for now; "bank staff" means loan officers and branch managers.
- **Is "application submitted" a status change** for the customer? Recommended: **yes**. The application's first status is `submitted`, so the customer gets "Application 9 submitted", and the same when staff submit on their behalf.

**Status: built 2026-09-23, tag `v2.13.0`. Both recommendations above were taken:** the admin gets no staff notifications (it is not staff, Piece 27), and submitting counts as the first status change. Where the build differs from the plan below:
- **`notify_staff_test_document` takes the applicant's name as an argument** rather than digging it out of the document. Piece 32 knows who uploaded; the notification service should not have to walk three relationships to find out.
- **Trigger 3 sets `application.applicant` by hand** before calling, in both call sites, so the message can be written without a second query for a record the caller already has.
- **A profile with no login gets nothing, and staff are not told instead.** Staff can create a borrower profile with no account behind it; there is simply nobody to address the message to. There is a test for it.
- **`timeAgo` is new in `utils/format.js`**, using the browser's own relative-time formatter: a bell is read at a glance, and a full date makes you work out how long ago it was.
- **Not checked in a browser yet**, and the panel is the one part no test covers.

### Triggers (the only ones)

| # | Audience | When | Recipients | Called from |
|---|---|---|---|---|
| 1 | staff | a customer asks to edit an already-submitted application | every **active** loan officer and branch manager | `edit_request_service.create_request`, same commit |
| 2 | staff | a customer uploads a document declared **TEST** | every active loan officer and branch manager | Piece 32 (the function is built and tested here, but called there) |
| 3 | applicant | **their own** application's status changes (including the first `submitted`) | the applicant's login user, if the profile has one (staff-created profiles without a login get nothing) | `application_service.create_application` and `update_status`, same commit |

**Not notified (settled):** setting changes, ordinary REAL uploads, verifications, logins, anything else.

### Data
**New table `notifications`**, model `backend/app/models/notification.py`, one row **per recipient**:

| Column | Type |
|---|---|
| `id` | primary key |
| `recipient_user_id` | FK `users.id`, indexed |
| `audience` | enum `staff` / `applicant` |
| `type` | enum `edit_requested` / `test_document_uploaded` / `application_status_changed` |
| `title` | String(120) |
| `body` | String(300) |
| `link` | String(200): an in-app path such as `/applications/7` |
| `entity_type` | String(40) |
| `entity_id` | Integer |
| `created_at` | indexed |
| `read_at` | nullable |

- **CHECK rules** keep the audiences apart: `edit_requested` and `test_document_uploaded` only with audience `staff`; `application_status_changed` only with audience `applicant`. That's enforced by the database itself.
- **Index** on `(recipient_user_id, read_at, created_at)` for the unread count.
- **Content rule:** no Aadhaar, PAN or account numbers and no amounts in text. For example, "Priya Sharma asked to change application 2" or "Application 7 is now Approved". A bell can be seen on a shared screen.

### Service: `backend/app/services/notification_service.py`
- `notify_staff_edit_requested(db, edit_request)`
- `notify_staff_test_document(db, document)`, used by 32
- `notify_applicant_status(db, application, old_status, new_status)`
- `_staff_recipients(db)`: active users whose role is in `rules.STAFF_ROLES`
- `list_for(db, user, *, unread_only, limit, before_id)`, `unread_count(db, user)`, `mark_read(db, user, id)`, `mark_all_read(db, user)`

None of them commit; the caller's commit covers both the event and its notifications, so they succeed or fail together. **None of them read or write the activity log.**

### Addresses (`backend/app/routers/notifications.py`, prefix `/api/v1/notifications`, any logged-in user, always **only their own**)
- `GET ""?unread_only=false&limit=20&before_id=` → items (newest first) + `unread_count`
- `GET /unread-count` → `{"count": n}` (tiny, for polling)
- `POST /{id}/read` → 204. Someone else's notification → 404, not 403, so ids can't be probed.
- `POST /read-all` → 204

### Frontend
- `components/NotificationBell.jsx` in the top-bar slot:
  - a bell icon with a red count badge (hidden at 0; "9+" above 9)
  - **polls `GET /unread-count` every 30 seconds** and on every route change
  - clicking opens a panel of the latest 20 (title, body, relative time, unread dot)
  - clicking an item marks it read and navigates to `link`
  - "Mark all read"
  - an empty state
  - it closes on Escape or on clicking outside

  The same component serves customers and staff; they simply get different notifications.
- Staff and customers never see each other's types, because the server only returns the user's own rows.

### Tests (`tests/ours/test_notifications.py`)
- **Trigger 1:** a customer's edit request → one row for each active officer and manager (audience `staff`); the customer gets none; an inactive officer gets none; admin gets none.
- **Trigger 3:** a status change → exactly one row for *that* applicant; another customer none; staff none. Creating an application → "submitted" notice to its owner.
- `notify_staff_test_document` → staff rows only (called directly in this piece).
- **No notification** for a setting change, a REAL document name-only add, or a verification.
- The CHECK rule: inserting `edit_requested` with audience `applicant` fails.
- Unread count, mark one, mark all. Reading someone else's → 404.
- The activity log row count is identical with or without the notifications (they're independent).

### Manual
Section 2: staff are notified in the app about edit requests and TEST uploads; customers are notified when their application's status changes. Re-ingest.

### Browser check
1. Priya asks to edit application 2 → Rajan's and Anita's bell shows 1 → click → application 2 opens and the badge clears.
2. Rajan moves application 2 to under review → Priya's bell shows "Application 2 is now Under review".
3. Rahul's bell doesn't change.
4. Change the Piece 28 setting → no bell anywhere.

---

# PIECE 31 — Real upload foundation

**Goal:** with the admin switch **ON**, customers and staff upload **real files**. Every file passes a **safety gate**, is **rebuilt** (so nothing hidden survives), is checked against **per-document-type standards**, is marked **TEST / REAL / UNDECLARED** (fixed forever), and is stored **encrypted, outside the project folder**. Staff and admin can **view** files, and every view is logged. A **"Documents to check"** page lists unverified documents (finishing **B3**). With the switch **OFF** nothing changes. The trainer's name-only route is untouched.

**Needs first:** 28. **Open decisions:** D10 and the UNDECLARED-consent
question below are settled by taking their recommendations (see the note
just below). **Final numbers in the standards table** below (researched
defaults) stand as written.

**Status: built 2026-09-23, tag `v2.14.0`, 36 new tests, 402 passing.** The storage design below —
one folder, outside the project, self-declared nature — is superseded.
The actual design is: **two** folders, chosen **automatically** by the
server, never self-declared. Full reasoning in `TRAPS-AND-DECISIONS.md`,
Settled, "Piece 31 — two upload folders, chosen automatically, never
self-declared." In short:
- `backend/uploads/` (tracked by git) for documents the server is
  confident are TEST/demo material; `C:\LAMS\uploads\` (outside the
  project, never in git) for everything else — real, uncertain, and every
  image (no OCR yet).
- The uploader is never asked Real or Test. `nature` is set by the server:
  a local check of a PDF's original text layer for SPECIMEN/SAMPLE/
  TEST/DEMO/DUMMY wording, confirmed by Gemini only when that local check
  already found a match (sent the matched text only, never the file) —
  never Gemini as the first or only judge, consistent with T-108. Anything
  short of both agreeing is `undeclared`, treated like `real`.
- The env vars below (`UPLOAD_DIR`, one folder) become
  `UPLOAD_DIR_SAFE` / `UPLOAD_DIR_SENSITIVE`, two folders. The "refuse to
  start if inside the project" rule now applies only to the sensitive one.
- D10 and "UNDECLARED needs consent like REAL" are both taken as written
  below; consent is now one checkbox, unconditional, since nobody knows in
  advance how a document will be classified.

**Two more things found while building, beyond the redesign above:**
- **`classify_nature` got its own outer safety net**, separate from
  `_gemini_confirms_specimen`'s. An upload must never fail outright because
  classification broke in a way that function's own handling didn't
  anticipate — any such failure now still lands on `undeclared`.
- **The rate limits (30/hour, 100 MB/customer) were written into `rules.py`
  and then actually wired up** in `document_service._check_rate_limits`,
  checked before the pipeline runs.

### Current state (answers Rohit's storage questions)
- Today a "document" is a SQLite row in `documents` (`id`, `application_id`, `doc_type`, `file_name`, `uploaded_at`, `verified`) created from typed JSON. **No file is stored anywhere.**
- Linked to people through `documents.application_id → loan_applications.applicant_id → applicants.user_id`.
- **MongoDB isn't needed.** SQLite keeps the metadata, and the bytes go in a folder behind a small storage interface. In production, that folder becomes S3 or Azure Blob, and SQLite becomes PostgreSQL.

### Must-have protections (built here) vs production hardening (future)

| Must-have now | Production later (`FUTURE-UPGRADES.md`) |
|---|---|
| The real type is read from the file's bytes (`filetype`), and must match its extension and the per-type allow-list | Antivirus (ClamAV) or a sandbox scan |
| A 5 MB cap, enforced while reading | Object storage with its own access policies |
| A PDF danger-marker scan (`/JavaScript`, `/JS`, `/OpenAction`, `/AA`, `/Launch`, `/EmbeddedFile`, `/RichMedia`, `/XFA`, `/SubmitForm`, `/GoToR`) → refuse and log `upload_blocked` | Keys held in a key vault (KMS) instead of `.env` |
| Password-protected PDFs refused | Retention and deletion schedules (DPDP) |
| **Rebuild (CDR):** images decoded and re-encoded with Pillow (strips hidden data such as GPS); PDFs **re-drawn page by page as pictures** with `pypdfium2` at 150 DPI and put into a new PDF | Separate upload servers |
| Pillow's pixel limit (50 MP); page caps per type | Tamper detection on scans |
| A random stored name (UUID) in `UPLOAD_DIR` (from `.env`, **outside the project**); refuse to start uploads if it's unset or inside the project folder | |
| **Encrypted at rest** with `cryptography.Fernet`, key `UPLOAD_ENCRYPTION_KEY` in `.env` | |
| Files served with the detected type, `X-Content-Type-Options: nosniff`, `Content-Security-Policy: default-src 'none'; sandbox`, and an encoded `Content-Disposition` | |
| Display names cleaned (letters, digits, space, `. _ - ( )`, max 100) and never sent to the AI | |
| Owner, staff or admin may view; only owner or staff may upload; every staff/admin view logged `document_viewed` | |
| 30 uploads per user per hour; 100 MB per customer | |
| SHA-256 stored (duplicates across customers can be flagged later) | |
| Consent checkbox for REAL/UNDECLARED, stored with a timestamp | |

### Per-document-type standards (in `rules.py` as `UPLOAD_STANDARDS`, mirrored in `frontend/src/utils/uploadStandards.js`)

Researched from IBPS, NSDL PAN, UPSC, SSC and DigiLocker, plus our manual's 5 MB. Upload limit 5 MB everywhere. The server rebuilds each file to the standard, and refuses it with a plain reason if it can't.

| Type | Accepted | Rebuilt as | Pixels | Stored size | Pages |
|---|---|---|---|---|---|
| `photograph` (**new, optional**) | JPEG, PNG | JPEG | exactly **200 × 230** (IBPS), centre-cropped; the original must be at least that | **20–50 KB** | — |
| `signature` (**new, optional**) | JPEG, PNG | JPEG | exactly **140 × 60** (IBPS) | **10–20 KB** | — |
| `id_proof` | PDF, JPEG, PNG | PDF stays PDF; images → JPEG | PDF pages drawn at 150 DPI; images long side ≤1600, short side ≥800 | image 30–300 KB; PDF ≤300 KB per page | 1–4 |
| `income_proof` | PDF, JPEG, PNG | same | same | whole file ≤2 MB | 1–20 |
| `bank_statement` | **PDF only** | PDF | same | ≤3 MB | 1–30 |
| `property_docs` | PDF, JPEG, PNG | same | same | ≤3 MB | 1–30 |
| `employment_letter` | PDF, JPEG, PNG | same | same | ≤1 MB | 1–5 |
| `vehicle_quotation` | PDF, JPEG, PNG | same | same | ≤1 MB | 1–5 |

Almost-blank images and pages are refused. `photograph` and `signature` are added to `rules.DOCUMENT_TYPES`, but **not** to any `REQUIRED_DOCUMENTS` list, so Phase 5 and the demo figures don't move. The trainer's UNIT-07 still refuses `passport_copy`.

### Data
- **New table `stored_files`**, model `models/stored_file.py`, with CHECK rules on `nature`, sizes > 0 and `content_type` in the allowed three:

  | Column | Notes |
  |---|---|
  | `id` | |
  | `applicant_id` | FK, indexed |
  | `application_id` | nullable |
  | `stored_name` | UUID + extension, unique |
  | `display_name` | |
  | `content_type` | |
  | `size_bytes`, `original_size_bytes` | |
  | `pages`, `width`, `height` | |
  | `sha256` | indexed |
  | `nature` | enum `test` / `real` / `undeclared` |
  | `consent_at` | nullable |
  | `uploaded_by` | |
  | `uploaded_at` | |

- **`documents.file_id`:** a nullable FK, added by extending `database._add_missing_columns()` to the `documents` table (the D-18 pattern). Name-only documents simply have no `file_id`.
- **Nature is fixed:** a trigger (like `db_checks.py`) refuses any UPDATE that changes `stored_files.nature`.

### Libraries (explain each before adding, Rule 3; all pip-only, fine on the Wipro laptop)
- `pypdf`: opens a PDF to check for danger markers and passwords
- `pypdfium2`: Chrome's PDF engine; draws pages as pictures and (Piece 34) reads their text
- `cryptography`: Fernet encryption
- Pin the already-installed `Pillow` and `filetype` too

### Code
- New `backend/app/services/file_service.py`, where every upload passes these stages in order:
  1. `read_capped`
  2. `detect_type`
  3. `check_allowed_for(doc_type)`
  4. `scan_pdf_markers`
  5. `rebuild_image` / `rebuild_pdf`
  6. `apply_standard` (pixels, KB, pages, blank)
  7. `encrypt_and_store`
  8. `sha256`

  Each stage raises a `RuleViolation` with a plain sentence. The storage functions `save`, `open` and `delete` sit behind one small interface, so the folder can become object storage later.
- `document_service.add_uploaded_document(...)`: creates the `stored_files` row and the `documents` row (`file_name` = the display name) in one commit, and records `document_added` (with `size_before`, `size_after`, `nature`) or `upload_blocked` (with the reason).
- New addresses:
  - `POST /api/v1/applications/{id}/documents/upload` (multipart: `doc_type`, `nature`, `consent`, `file`). Needs `require_business_actor` plus the owner-or-staff check, and **returns 409 if the switch is OFF**.
  - `GET /api/v1/files/{file_id}`: owner, staff or admin. Decrypts and streams with the safe headers, and logs `document_viewed` for staff and admin.
  - `GET /api/v1/documents/unverified`: `require_staff_view`.
- `DocumentResponse` gains optional `file_id`, `size_bytes`, `original_size_bytes`, `content_type`, `nature`.

### Frontend
- `DocumentChecklist.jsx` with the switch ON, a real upload form:
  - document type
  - **"Is this a real document or a TEST document for a demo?"** (Real / Test, required)
  - a **consent checkbox** for Real ("I agree this document is stored by the bank and checked by staff")
  - a file picker for one file, plus the allowed types and sizes for the chosen type (from `uploadStandards.js`), checked before sending
  - the list shows **"2.4 MB → 180 KB"**
  - **View** fetches `/files/{id}` with the token as a blob and opens it in a new tab (in memory only, Rule 13)

  With the switch OFF: today's form.
- New `pages/DocumentsToCheck.jsx` (staff; admin view-only): unverified documents across all applications, newest first, with View and Mark verified (staff only). Add a route and a top-bar link.
- `utils/activity.js`: labels for `document_viewed` and `upload_blocked`.

### Manual
- Section 4 and Section 12: the per-type table, 5 MB, automatic rebuilding, the photograph and signature sizes, "every document is checked by staff", and "the assistant never reads your documents".
- **Section 10: correct "financial data is encrypted at rest"** to what is true: uploaded documents are encrypted; the database is protected by server access (T-113).
- Re-ingest.

### Tests (`tests/ours/test_uploads.py`; files built in memory, nothing real)
- **Attacks refused:**
  - a program renamed `.pdf`, and HTML renamed `.jpg`
  - an SVG
  - a JPEG with a zip appended (the rebuilt file no longer contains the zip bytes)
  - a PDF with `add_js` / OpenAction, and an encrypted PDF
  - a pixel bomb, and too many pages
  - over 5 MB
  - an empty file
  - a blank page
  - a photograph smaller than 200×230, and a signature the wrong shape
  - a path-trick display name, and a line-break display name
- **Accepted:** a phone-sized JPEG → ~≤300 KB; a photograph → exactly 200×230 at 20–50 KB; a scan-like PDF (`Image.save(format="PDF")`) → rebuilt, ≤300 KB per page.
- The encryption round trip: the bytes on disk aren't the original; `GET /files/{id}` returns the rebuilt file.
- **Permissions:** another customer → 404/403; admin can view but not upload; the rate limit.
- The switch OFF → upload 409; the name-only route still works (plus Phase 4 `test_mcp_server.py`).
- Changing `nature` through SQL is refused.

### Browser check (switch ON, `.env` with `UPLOAD_DIR` and the key set)
- **Priya:** upload a phone photo of a payslip as Real (tick consent), and see "3.1 MB → 240 KB". Upload a `.pdf` that is really a text file, and see it refused with a plain reason.
- **Rajan:** Documents to check → View → Mark verified.
- **Anita → Activity:** `document_viewed` and `upload_blocked` are there.
- Switch OFF: the old name form is back, and the uploaded file is still viewable.

---

# PIECE 32 — TEST-document workflow

**Goal:** a document declared **TEST** is unmistakable everywhere, **staff are notified immediately** (notification trigger 2), the checklist counts it but says so, and the admin can clear demo clutter. **TEST ≠ genuine** is kept in the data, not just the screen.

**Status: built 2026-09-23, tag `v2.15.0`, 133 targeted tests passing (all
of `tests/ours/test_uploads.py`, `test_notifications.py`,
`test_admin_role.py`, `test_settings.py`, and `tests/phase5/test_agents.py`).**
The badge wording suggested below was used as written. One thing found while
building: the "SPECIMEN backstop" bullet just below turned out to already be
built — Piece 31's `classify_nature` does that exact check at upload time,
for every document, not just ones declared REAL — so it was dropped rather
than duplicated in Piece 34. See `TRAPS-AND-DECISIONS.md`.

**Browser check: passed 2026-09-24.** Every point in the browser check below
worked. It turned up three small bugs, each fixed and tagged on its own, listed
in Done as 32a to 32c. They were fixed straight away without being planned here
first, which was a Rule 9 miss (noted rather than hidden). Same-type uploads were
settled as D-29: keep both.

**Needs first:** 30, 31. **Open decisions:** the badge wording. Suggested: **"TEST DOCUMENT — for demonstration only. Not a genuine customer document."**

### Changes
- **Badges:** a `TestBadge` component (strong amber pill with an icon), shown on every row, on Documents to check, on the application's document card, and in the View tab title. The server always sends `nature`, and the screen never guesses it.
- **Checklist summary:** `DocumentListResponse` gains `test_count` and `real_count` alongside `required` and `missing`. The card says **"Documents complete — 4/4 submitted, including 2 TEST documents"**. Missing items stay as they are.
- **Four facts kept separate, on screen and in the data:** *submitted* (a row exists), *identified as a kind* (Piece 33/34), *marked TEST* (`nature`), and *verified* (`verified`). "Mark verified" on a TEST document is labelled **"Verified (test document — checked for the demo, not for authenticity)"**, and the stored `verified` flag stays as it is (Phase 5 unchanged).
- **Phase 5 honesty:** the compliance checker (`multi_agent/agents/compliance_checker.py`) adds a note, **"Includes TEST documents — not genuine"**, when any document on the application is TEST. It's a note only; the verdict logic is unchanged. Check the Phase 5 tests still pass.
- **Notification:** `document_service.add_uploaded_document` calls `notification_service.notify_staff_test_document(...)` when `nature == test`, in the same commit. REAL and UNDECLARED uploads notify nobody (settled).
- **Admin clean-up:** `POST /api/v1/admin/test-documents/purge` (`require_admin`, body `{"confirm": "DELETE TEST DOCUMENTS"}`). It deletes every TEST `stored_files` row, its encrypted file and its `documents` row, logs `test_documents_purged` with the count (activity only), and adds a button with a confirmation pop-up on the Admin page.
- ~~**The SPECIMEN backstop** (declared REAL but the text says SPECIMEN) needs the document's text, so it's built in **Piece 34**.~~ **Dropped.** Piece 31's `classify_nature` already runs this exact check at upload time, for every document — there is nothing left for Piece 34 to add here.

### Tests
- A TEST upload → a notification row for each active officer and manager, and none for the customer or admin.
- A REAL upload → no notification.
- `test_count` is right.
- The Phase 5 compliance note appears with a TEST document.
- Purge: admin only; the files are gone from disk; REAL documents are untouched.
- `nature` can't be changed.

### Browser check
- Priya uploads a SPECIMEN Aadhaar as **Test** → the amber badge shows, and the checklist says "including 1 TEST document".
- Rajan's bell → "Priya Sharma uploaded a TEST document on application 1".
- Admin → Purge TEST documents → gone.

---

# PIECE 32d — Replacing a document

**Status: built 2026-09-24, tag `v2.16.0`, 15 new tests; 144 passing across the new file, uploads, notifications, admin and Phase 1, plus 13 in Phase 3 context and Phase 4 MCP.** Built as planned. One addition: the purge handles a chain. If the purged TEST copy had itself been replaced later, the older copy points at that newest copy rather than coming back as current. Browser check still to do.

**Why now:** D-30 (2026-09-24). The manual has always told customers a document can be replaced until it is verified, but the app had no way to do it, so the chatbot was promising something the app couldn't do. Rohit asked for the Replace button now, ahead of Piece 33.

**What real lenders do, and so what the manual says:** a customer-facing FAQ says a document can be re-uploaded or replaced until it has been checked. It does *not* tell customers that old copies are kept; that's internal record-keeping. So the manual's existing wording stays true, and it only gains *how* to do it. (Search, 2026-09-24: lenders talk about "resubmission" of unclear or mismatched documents, and nothing more.)

### Rules
- Only a **current, unverified** document can be replaced. A verified one is part of the permanent record (422). An already-replaced one can't be replaced again (422).
- The replacement **keeps the old one's type**. The request doesn't carry a type at all, so it can't be changed.
- **Who can:** anyone who can add a document today (`require_business_actor`), which means the customer who owns the application, a loan officer, or the manager. The admin can't (view only, Piece 27).
- The new copy goes through **exactly the same path** as a normal add. On the name route that's the name only. On the upload route it's the full safety, rebuild and classification pipeline, the switch, the rate limits, and the TEST notification.
- **Nothing is deleted.** The old row stays, marked `replaced_by_id` (the new row's id) and `replaced_at`. Its encrypted file stays too, and staff can still view it.
- **A replaced document stops counting everywhere:** the checklist, the TEST/REAL counts, Documents to check, the Morning Briefing, and the application detail. The application detail is what Phase 4's MCP tool and Phase 5's compliance checker read, so they stop counting it too.
- **Who sees replaced copies:** staff and the admin see them in a "Replaced copies" list under the documents. The customer doesn't, which matches what real lenders show.
- **The purge:** if a TEST document that replaced an older one is purged, the older one becomes current again (its `replaced_by_id` is cleared). The purge takes away demo clutter and puts back what was there before.
- An activity row `document_replaced` records the old id, the new id and the type. There's **no new notification**, because the three triggers are settled.

### Data
- `documents` gains `replaced_by_id` (INTEGER, nullable) and `replaced_at` (DATETIME, nullable), added to old databases by `_add_missing_columns`, the same way Piece 31 added `file_id`.

### Addresses
- `POST /api/v1/applications/{id}/documents/{doc_id}/replace`, with body `{file_name}`. This is the name-only route, which works whatever the switch says, like the trainer's add route.
- `POST /api/v1/applications/{id}/documents/{doc_id}/replace/upload`, as multipart `consent` + `file`. It returns 409 when real uploads are off, like the upload route.
- `GET .../documents` gains `replaced: [...]`, which is always empty for a customer. `items` holds current documents only.

### Code
- `document_service.add_document` and `add_uploaded_document` each gain an optional `replaces=` argument. When it's given, the old row is marked in the **same commit** as the new one, so there's never a half-replaced document. `replace_document(...)` checks the rules above and then calls one of them.
- `verify_document` refuses a replaced document.
- `ApplicationDetail.documents` leaves out replaced rows (one validator in the schema).
- `unverified_documents` and the briefing leave out replaced rows.
- `admin_service.purge_test_documents` restores whatever a purged document had replaced.

### Screens
- In the uploaded table, an unverified row gets a **Replace** button, for everyone except the admin. It opens a pop-up with the same controls as the upload form: a file and the consent tick when real uploads are on, or a file name when they're off.
- A collapsed **"Replaced copies (n)"** section appears under the table, for staff and the admin only, showing when each one was replaced, with View where there's a file.
- Streamlit isn't changed (it's the trainer-check front end, and it lists documents only).

### Manual
The FAQ "Can I replace a document I have already uploaded?" and the paragraph in the documents section gain the *how*: "use **Replace** next to it; the new copy takes its place and is checked again." There's no mention of what the bank keeps internally. Then re-ingest.

### Tests (`tests/ours/test_document_replace.py`, offline)
- Replace by name, and replace by upload. The new document is current, and the old one has `replaced_by_id`.
- A verified document is refused, a replaced one is refused, another customer gets 403, and the admin gets 403.
- The old one is gone from `items`, from Documents to check, and from the application detail, and the checklist is still correct.
- `replaced` is empty for the customer and has one entry for staff.
- Verifying a replaced document is refused.
- The activity row is written.
- Purging a TEST replacement brings the old one back.
- The trainer's Phase 1 tests are unchanged: nothing about the existing routes changes unless Replace is used.

**Tag:** `v2.16.0` (middle digit: an ordinary new feature).

---

# PIECE 33 — Document kinds, their fields, and manual entry

**Status: built 2026-09-24, tag `v2.17.0`.** Built to the decisions just below. Testing was trimmed at Rohit's request (speed over coverage): two core tests (the Aadhaar number is never stored in full, and only confirmed details count while name-only documents still do), plus the new addresses in the admin test. 112 existing tests (Phase 1, uploads, replace, notifications, Phase 3 context, Phase 4 MCP) still pass. Differences from the plan below: the extraction hangs off `document_id`; there are no DB triggers, because both tables are new, so plain CHECK constraints do the job, including one that refuses an unmasked Aadhaar or account number; the admin can open the details read-only. Browser check still to do.

**Goal:** after uploading, the user says **which document it is** (Aadhaar, PAN, payslip…), and a **form with that document's fields** appears, grouped per document. The user types the values. Required fields stay required. Each value records **where it came from**. **No AI and no OCR in this piece.** Piece 34 adds automatic filling into the same structure.

**Needs first:** 31.

**Decisions, answered by Rohit 2026-09-24 (these override anything below that disagrees):**
1. **Demo set of 4 kinds first:** Aadhaar and PAN (inside `id_proof`), salary slip (`income_proof`), bank statement (`bank_statement`). The other 7 in the table come later, as registry entries only. A type with no kinds counts exactly as today.
2. **Counts only once confirmed**, but only for a **real file of a type that has kinds**. Name-only documents (every seeded document, every trainer test) count exactly as before. A confirmed TEST document counts. One helper, `counts_towards_checklist`, is used by the checklist, the briefing and Documents to check. `DocumentResponse.needs_details` lets Phase 4 and 5 skip the same documents.
3. **Address on Aadhaar: optional.** At most 300 characters, never copied to the profile.
4. **The kind is picked in the upload form** ("Which one?" under ID proof). A type with one kind picks it automatically. The upload and replace/upload routes take an optional `kind` and create the extraction in the same commit. The details form opens straight after.
5. The extraction hangs off the **document** (`document_id`), not the file, since the document row exists from the moment of upload. A replacement copy (Piece 32d) gets its own, empty extraction.
6. The bank account number is masked to its last 4 digits, the same way as Aadhaar.

The full implementation plan is in `~/.claude/plans/alright-now-plan-for-smooth-flame.md`.

**Original open decisions (now answered above):**
- Confirm the field lists below.
- **Address** is a new field that doesn't exist anywhere in the app today. Confirm it's wanted.
- **Replace (from D-29, 2026-09-24).** Settled: several files per type stay side by side, and nothing replaces anything automatically. Ask Rohit whether this piece adds a **Replace** action on a document row. The old file would be kept in history as superseded and dropped from the checklist, never deleted. This is the first piece where "a second Aadhaar" can be told apart from "an Aadhaar plus a PAN", so the question belongs here.

**Carried in from the Piece 32 browser check (2026-09-24):**
- The checklist counts **types covered**, not files (`required − missing`, T-123). When "only confirmed documents count" arrives in this piece, keep it counting per type: a type is covered when at least one of its documents is confirmed.
- Every pop-up is now safe for typing (T-124). The field form can use `Modal` freely.

### Document inventory (from the code and manual) and the proposed fields
Present today: 6 types (`rules.DOCUMENT_TYPES`) + the manual's Section 4 descriptions. A **kind** sits *inside* a type, so `doc_type` and every trainer test are untouched.

| Kind | Inside type | Fields (R = required) | Checked against |
|---|---|---|---|
| Aadhaar | `id_proof` | Name R, DOB R, Gender, Aadhaar number R (**stored masked: `XXXX XXXX 1234`**), Address (new) | Verhoeff checksum; profile name and DOB |
| PAN | `id_proof` | Name R, Father's name, DOB R, PAN R | format `AAAAA9999A`; profile |
| Passport | `id_proof` | Surname R, Given names R, Passport number R, Nationality, DOB R, Sex, Expiry R | not expired; profile |
| Driving licence | `id_proof` | Name R, DL number R, DOB R, Valid until R | not expired; profile |
| Salary slip | `income_proof` | Employer R, Employee name R, Pay month R, Gross pay, Net pay R | name; 12 × net vs declared income |
| Form 16 | `income_proof` | Employer, Employee PAN, Assessment year R, Gross salary R | PAN vs PAN on file |
| ITR | `income_proof` | Assessment year R, Total income R | declared income |
| Bank statement | `bank_statement` | Account holder R, Bank, Account number (masked), Period from R, Period to R | covers ≥ 6 months |
| Property document | `property_docs` | Document kind (deed/NOC/plan) R, Property address, Date | staff review |
| Employment letter | `employment_letter` | Employer R, Employee name R, Designation, Date of joining R | years with employer |
| Vehicle quotation | `vehicle_quotation` | Dealer R, Make/model R, On-road price R, Date | loan amount ≤ price |

Not in the app, so not proposed: educational certificates, generic "loan documents".

### Data
- **Registry** `backend/app/domain/document_kinds.py`, a sibling of `rules.py`: each kind's `doc_type`, label, and fields (`key`, `label`, `required`, `type` (text/date/number/id/select), `validator`, `mask`). Mirrored in `frontend/src/utils/documentKinds.js`.
- **Validators** `backend/app/domain/validators.py` (plain Python):
  - Verhoeff (Aadhaar)
  - PAN format
  - date plausibility (DOB not in the future, age 18–100; expiry after today)
  - money > 0
  - name match to the profile, with `difflib` from the standard library (a warning, not a block)
- **New table `document_extractions`:**

  | Column | Notes |
  |---|---|
  | `id` | |
  | `file_id` | FK |
  | `application_id` | |
  | `declared_kind` | |
  | `detected_kind` | nullable, Piece 34 |
  | `detection_score` | nullable |
  | `status` | `needs_input` / `confirmed` / `discarded` |
  | `batch_id` | nullable, Piece 35 |
  | `verification_level` | `not_verified` / `consistency_checked` / `cryptographically_verified` / `staff_verified` |
  | `document_id` | nullable; set on confirm |
  | `created_by`, `confirmed_by`, `confirmed_at` | |

- **New table `extracted_fields`:** `id`, `extraction_id`, `field_key`, `value` (**masked where the registry says**), `machine_value` (what the machine read, kept when the user changes it), `source` (`qr` / `mrz` / `text_layer` / `ocr` / `gemini` / `user`), `confidence` (0–1), `state` (`extracted` / `uncertain` / `missing` / `user_entered` / `user_corrected`), `check_note`.
- CHECK rules on both tables.
- **The full Aadhaar number is never stored anywhere** (UIDAI; T-114). Before saving, it's reduced to the last 4 digits.

### Flow and addresses
1. The upload (Piece 31) returns a file → the user picks the **kind** → `POST /api/v1/applications/{id}/extractions` `{file_id, declared_kind}` creates an extraction with every field in state `missing`.
2. `GET /api/v1/extractions/{id}` returns the form data.
3. `PATCH /api/v1/extractions/{id}/fields` `{field_key: value, ...}` sets `state` to `user_entered` (or `user_corrected` if a machine value existed) and runs the validators; problems come back per field.
4. `POST /api/v1/extractions/{id}/confirm` checks that every required field is present and valid, then sets `confirmed` and links the `documents` row. **Only confirmed documents count** towards the checklist when the switch is ON.
5. `POST /api/v1/extractions/{id}/discard`.

Permissions: the owner or staff write (`require_business_actor`); admin views.

**Profiles are never changed from here** (settled); a mismatch with the profile is shown as a warning.

### Frontend
- `components/DocumentReviewForm.jsx` (reused in chat in Piece 38): **one card per document**.
  - The header shows the kind, the file name and the TEST badge.
  - A table: **Field | Value | State**. State tags: *Extracted* (green), *Uncertain — please check* (amber, with a "this is right" tick), *Missing* (empty required box), *You entered*.
  - Required fields are marked, and there are per-field errors from the validators.
  - A **Confirm** button.
  - Shown on the application page after an upload.

### Tests
- Required fields enforced.
- Verhoeff: a good number passes, and one wrong digit fails.
- PAN format.
- **The Aadhaar is stored masked** (the database has only the last 4).
- `user_corrected` keeps `machine_value`.
- Can't confirm twice.
- Another customer's extraction → 404.
- Admin: view yes, edit no.
- An unconfirmed draft doesn't count towards the checklist.

### Browser check
Priya uploads a TEST Aadhaar → picks "Aadhaar card" → the form shows Name, DOB, Gender, Aadhaar number, Address → a wrong Aadhaar digit is refused → Confirm. The document shows **"XXXX XXXX 1234"**.

---

# PIECE 34 — Reading documents: OCR, identification, extraction

## The lean version, decided 2026-09-24. This replaces the plan below it.

**Status: built 2026-09-24, tag `v2.18.0`.** Built as written below. Core tests: an Aadhaar PDF is read, stored masked, and the stored copy's pixels are black where the first 8 digits were; an Aadhaar photo is refused and a TEST one without a number is stored; the database refuses a full number. 148 tests (Phase 1 + every upload-related file) pass. One small find: PDFs turn a typed ' into a curly ’, so labels like "Father's Name" accept both. The demo kit is in `backend/demo_documents/`, made by `scripts/make_specimen_docs.py`, and matches Priya's seed details. Browser check batched.

**Rohit's two answers:** (1) **Lean, PDFs only.** Read the text a PDF already has inside it, with no OCR, no Gemini, no QR, and no new libraries. (2) **An Aadhaar that can't be blacked out is refused if it's real or undeclared**, with a pointer to UIDAI's masked Aadhaar. A TEST one is stored with a warning. The rest of the old plan goes to `FUTURE-UPGRADES.md`: RapidOCR for photos and scans, Gemini reading TEST payslips, UIDAI Secure QR signature checks, passport MRZ.

**Why it lives inside the upload pipeline.** The rebuild (stage 6 in `file_service`) redraws every page as a picture, and that destroys the PDF's text. So the reading has to happen before it, just like classification does, and the blacking-out has to happen *during* it, on the redrawn page. Reading a text layer takes milliseconds, so the upload stays one quick request, with no background job and no polling.

**Flow, when an upload comes with a `kind` (Piece 33):**
1. `file_service.process_upload(doc_type, source, kind=None)`. For a PDF, a new step between classify and rebuild reads each page's text **with each character's position** (pypdfium2 `get_charbox`).
2. `document_reader.read(kind, pages)` finds the fields with plain rules: labels like "Name", "DOB", "Net Pay", and patterns like the 12-digit Aadhaar and the PAN shape. Every value goes through Piece 33's `validators`. A value that passes is `extracted` (source `text_layer`, confidence 0.95). One that is found but fails a check is `uncertain`, with the check's message as the note, and it must be retyped before Confirm. Nothing found means `missing`. **Nothing is ever invented.**
3. **Blacking out:** for every Aadhaar-like number on a page (it can appear more than once), the first 8 digits' boxes become black rectangles, drawn on the redrawn page before it's encoded. The stored copy never has them. The number itself leaves the reader already masked (`XXXX XXXX 1234`).
4. **If an Aadhaar can't be blacked out** (a photo, a scan, or a PDF whose text has no Aadhaar number): an already-masked Aadhaar (text shows `XXXX XXXX 1234`) is fine. Otherwise, **TEST** is stored with a note on the number field ("not blacked out on the stored copy, TEST document"), and **real or undeclared is refused**: "We couldn't find the Aadhaar number to black it out. Please upload UIDAI's masked Aadhaar (from myAadhaar) instead."
5. **Identification:** keyword scoring ("Unique Identification Authority", "Income Tax Department", "Salary Slip", "Statement of Account"…) sets `detected_kind` and `detection_score`. If it disagrees with the declared kind, the form shows a warning. It's **never switched automatically**.
6. `add_uploaded_document` hands the reading to `extraction_service.create_extraction(…, reading=…)`, which fills the fields in the same commit as before.

**Limits, said plainly:** a photo, a scan, or starting details again after a discard can't be read (the text is gone after the rebuild), so those fields are typed by hand. The form says "Not read automatically". Reading is identification, never authenticity.

**Code:** `app/services/document_reader.py` (new: text with positions, the rules per kind, identification, Aadhaar boxes); `file_service.py` (the reading step, `rebuild_pdf` takes boxes to black out, and the refusal); `document_service.py` and `extraction_service.py` (pass the reading through); `ExtractionResponse` gains `detected_kind`, `detected_label` and `read_automatically`; `DocumentReviewForm.jsx` shows the automatic-fill line, the mismatch warning, and the "please check" state. `confirm` refuses while any field is still `uncertain`.

**Demo kit:** `backend/scripts/make_specimen_docs.py` writes four SPECIMEN PDFs, each with a real text layer, to `backend/demo_documents/`: an Aadhaar-style card (a fake, checksum-valid number), a PAN-style card, a payslip and a bank statement page. Each fills its form completely when uploaded.

**Manual (Rule 12):** automatic filling from PDFs, the blacking-out, the refusal and what to do about it, and that photos and scans are typed by hand.

**Tests (core only, per the trimmed-testing rule):** (1) an Aadhaar PDF is read and masked, and its stored copy is black where the first 8 digits were; (2) a real or undeclared Aadhaar photo is refused, and a TEST one is stored. Piece 33's masking test is adapted, since a JPEG Aadhaar is now refused. Then Phase 1 plus the touched test files.

**Browser check (batched):** upload each demo-kit PDF with its kind. The form opens already filled in, and the Aadhaar's stored copy (View) shows the first 8 digits blacked out.

**Tag:** `v2.18.0`.

---

## The original plan (2026-09-22), kept for reference

**Goal:** the Piece 33 form **fills itself in** from the file. Local, non-AI processing is used first. **Gemini is used only for TEST documents**, only for fields that rules can't read, and only on masked text, never images. Nothing is invented: no evidence means the field stays missing.

**Needs first:** 33. **Open decisions:**
- **A speed check on the Wipro laptop first.** Time RapidOCR on one A4 page. If it takes more than about 10 seconds a page, the fallback is Gemini reading the image **for TEST documents only**.
- **Aadhaar redaction failure:** if the number can't be located on the image to black it out, what happens? Recommended: **refuse to store a REAL Aadhaar** and ask the customer for UIDAI's own *masked Aadhaar* download; for TEST documents, store it with a warning.

### Pipeline (every step except the marked one is local and non-AI)

| Step | Tool | Output |
|---|---|---|
| Text from digital PDFs | `pypdfium2` text layer | exact text, confidence 0.95 |
| Text from scans and photos | **RapidOCR** (`rapidocr-onnxruntime`, a small OCR model on `onnxruntime`, already installed; not an LLM) | lines with a confidence and a position |
| Aadhaar | **Secure QR first** (`zxing-cpp` decodes it; parse UIDAI's format; **verify UIDAI's signature** with `cryptography` and UIDAI's public certificate) → name, DOB, gender, address, last 4 digits. Otherwise OCR + pattern + **Verhoeff**. | a valid QR gives `cryptographically_verified` (it proves the QR was issued by UIDAI, not who is uploading it) |
| Passport | **MRZ** (the two machine lines) parsed with its **check digits** | `consistency_checked` if the digits pass |
| PAN, driving licence | patterns + nearby words ("Name", "Father's Name", "Date of Birth") | |
| Identifying the kind | keyword/pattern scoring ("Unique Identification Authority", "Income Tax Department" + PAN pattern, `P<IND`, "Salary Slip"/"Payslip") | `detected_kind` + score; a **mismatch with the declared kind is shown, never switched** |
| **Payslips, Form 16, ITR, bank statement header, employment letter, vehicle quotation** | **Gemini, TEST documents only.** It receives the **OCR text with Aadhaar, PAN and account numbers masked first**, and returns a fixed JSON form. **Grounding check:** every value must appear in the OCR text, or it's downgraded to *uncertain*. REAL and UNDECLARED: skipped, and the fields stay for manual entry with a note "not read automatically for real documents". | |
| **SPECIMEN backstop** | if the text contains "SPECIMEN" or "SAMPLE" but the nature is REAL | a warning badge for staff ("declared real, looks like a test file"); **not a notification** (only the three triggers exist) |
| Masking | the Aadhaar number reduced to its last 4; **the first 8 digits blacked out on the stored image** using the OCR positions | |

**Confidence → state:**
- Sources, strongest first:
  - signed QR 1.0
  - MRZ with valid check digits 0.99
  - text layer 0.95
  - OCR pattern: the OCR line's confidence
  - Gemini grounded: at most 0.7
- **≥ 0.85 → extracted**; **0.5–0.85 → uncertain** (the user must tick "this is right"); **lower, or not found → missing**.
- A failed checksum or format forces *uncertain*.
- **Nothing is ever filled without evidence.**

**Identification ≠ authenticity, written into the screen and the manual.** We can't verify:
- PAN (Protean's service needs registration)
- passport genuineness (the chip can't be read from a scan)
- Aadhaar online (licensed agencies only)
- salary slips

DigiLocker and the Account Aggregator are the future routes.

### Background processing
Reading can take seconds, and the web client times out after 15 seconds. So:
- `POST …/extractions` returns at once with status `processing`.
- The work runs in a FastAPI background task.
- The screen checks `GET /extractions/{id}` every 2 seconds until it's `needs_input`.
- No Redis or Celery.

### Code
- `backend/app/services/text_service.py` (text layer / OCR)
- `document_reader.py` (identify, extract per kind, validate, confidence, mask, redact)
- `document_ai.py` (the **one** function that calls Gemini, through `llm_provider.get_llm()`; it refuses unless `nature == test`)
- a UIDAI public certificate file in `backend/app/domain/certs/`

**Libraries** (explain before adding): `rapidocr-onnxruntime` (brings `opencv-python-headless`) and `zxing-cpp`. Pinned.

### Demo kit
`backend/scripts/make_specimen_docs.py` generates **SPECIMEN** sample documents with Pillow:
- an Aadhaar-style card (fake name, a checksum-valid fake number, **no real UIDAI QR**, so it shows as *not cryptographically verified*, which is honest)
- a PAN-style card
- a payslip
- a bank statement page

Each is watermarked **"SPECIMEN — NOT A REAL DOCUMENT"**, and they're written to `backend/demo_documents/`. They exist so the ADH demo never needs a real document.

### Tests
- Verhoeff and MRZ samples (ICAO specimen lines).
- QR signature verification with a test key pair.
- Identification scores on specimen text.
- The grounding check downgrades a value not in the text.
- **REAL never calls Gemini** (the stub asserts it's not called), and TEST does.
- Masking and redaction: the stored image's pixels at the number's position are black.
- The background status flow.
- OCR tests marked `slow`.

### Browser check
Priya uploads the **SPECIMEN Aadhaar** as Test:
- after a few seconds the form fills (Name, DOB, Address *extracted*; the number shows `XXXX XXXX 1234`; *not cryptographically verified*)
- she fills anything missing and confirms

Uploading the same file as **Real** → staff see "declared real, looks like a test file".

---

# PIECE 35 — Several documents at once

## The reviewed plan, 2026-09-24. This replaces everything below it.

**Status: built 2026-09-24, tag `v2.19.0`.** Built as reviewed. The lock smoke check ran 40 uploads in 20 rounds of two at once, all stored and all read. 134 targeted tests pass, and the front end builds and lints clean. Browser check batched.

Rohit asked for a review of the plan before building. The review found two real problems (the first two below), and the rest are smaller. The full version is in `~/.claude/plans/alright-now-plan-for-smooth-flame.md`.

**What the review changed:**
1. **PDFium can crash the server when two uploads run at once.** pypdfium2's docs: PDFium is not thread-safe, not even on different documents, and elsewhere it has corrupted memory and killed server processes. Our upload routes run in parallel threads, so "2 at a time" would make this routine, and it could already happen with two people uploading at once. **Fix: one process-wide lock** (`app/services/pdfium_lock.py`) around every PDFium call. The slow Gemini step stays outside it.
2. **The batch check was useless, and I'd claimed it wasn't.** A browser-made, optional `batch_id` stops nobody who skips the screen. **Dropped.** The server's real guard already exists: 30 uploads an hour and 100 MB per customer. **Rohit: the 3 is a screen limit only**, because it's about waiting time. This leaves Piece 35 front end only, apart from the lock.
3. The details pop-up (33–34) isn't browser-checked yet, so sharing its table must leave it behaving exactly as now.
4. File-name guessing matches whole words ("pan" must not match "company.pdf").
5. Three TEST files mean three bell notices per staff member. That's accurate, so it's kept.
6. Name-only mode gets no batch upload.
7. The front end has no test runner, so the screen is checked by build, lint and the browser.

**Build:** the lock in `file_service._pdf_text_layer`, `file_service.rebuild_pdf` and `document_reader.pages_with_positions`. `guessFromFileName()` in `utils/documentKinds.js`. `MAX_FILES_AT_ONCE = 3`. In `DocumentChecklist.jsx`, "Upload several at once" opens `BatchUploadForm`, with rows (guessed type and kind, remove), one consent tick, and Upload all (two workers, one request per file, each with the 2-minute limit, per-row status, a refusal never stops the others). `DetailsTable.jsx` is moved out of `DocumentReviewForm.jsx`. `BatchReview.jsx` shows inline cards with one "Confirm all" that reports per document. Plus the manual line and re-ingest.

**Verification:** a one-off smoke script (20 rounds of two PDF uploads in parallel threads), the Phase 1 and upload test files, build and lint. **Browser check (batched):** Priya → Upload several → the demo-kit Aadhaar, PAN and payslip → three guessed rows → Upload all → three filled cards → Confirm all → three results. Rajan's bell shows 3, which is expected.

**Tag:** `v2.19.0`.

---

## The original plan (2026-09-22), kept for reference

**Goal:** upload **up to 5 documents in one go** (Aadhaar + PAN + bank statement + payslip). **Each is processed separately.** One failing doesn't block the others. Missing fields are shown **per document**, with one "Confirm & submit".

**Needs first:** 34. **Open decisions:** none expected (5 files, 5 MB each).

### Design
- A `batch_id` (UUID) created on the screen and sent with each upload. `document_extractions.batch_id` is already in place from Piece 33.
- The screen sends the files **one request each** (at most 2 at a time), so each gets its own safety check, rebuild, extraction and status.
- `GET /api/v1/extraction-batches/{batch_id}` gives each document's status, kind, TEST/REAL and missing required fields.
- **"What is this?" dropdown per file**, pre-filled by keyword matching on the file name (and in Piece 37, on the chat text), and corrected by `detected_kind` when confident. A mismatch is shown, never silently switched.
- **Confirm & submit** confirms each document separately and reports per document: "Aadhaar saved · PAN needs 1 more field · Bank statement refused: password-protected".

### Frontend
- The upload form accepts several files (showing each with its own type and Real/Test choice).
- Below it, a `DocumentReviewForm` card **per document**, with the missing fields inside each card.

### Tests
- A batch of 3 where 1 is refused: the other 2 continue.
- Per-document missing fields.
- A 6th file refused.
- The batch summary is correct.
- Each document's `nature` is independent.

### Browser check
Priya selects the SPECIMEN Aadhaar, PAN and payslip together, marks all three Test → three cards → Aadhaar asks for nothing, PAN asks for the number → one Confirm & submit → three results.

---

# D-31 to D-33 — three audit decisions, built together (2026-09-24)

Rohit: "use logical thinking to find the best options for each yourself and go ahead." So these were decided by reasoning, not by asking. Each is small, so they're built as one piece. **Tag:** `v2.19.2`.

**Status: built 2026-09-24, `v2.19.2`.** Built as written. 35 tests ran (extractions, the D-32 rule, the trainer's AGENT-06, and Phase 1): all passed in 26 seconds. `TYPES_WITH_KINDS` was removed from `document_kinds.py`, since D-33 left it unused with a comment describing the old rule.

**D-31: the SPECIMEN check uses Gemini keys only, never local Ollama.**
- *Why:* the settled rule says Gemini only for documents. The check exists to stop false "TEST" labels, and a small local model is a weaker second opinion: a wrong YES would put a possibly real document in the git-tracked folder.
- *Build:* `llm_provider.get_gemini_llm(temperature)` returns the key ladder (key 1 → 2 → 3) with no local rung, and raises if no key is configured. `file_service._gemini_confirms_specimen` uses it. Any failure is still "no" (undeclared), the cautious answer. It stays in `llm_provider.py`, the only file allowed to choose providers.

**D-32: the employment letter is for salaried home-loan applicants only.**
- *Why:* the manual comes from the trainer's own spec, and it's right: a self-employed person has no employer to write the letter.
- *Build:* `rules.required_documents(loan_type, employment_status=None)` and `missing_documents(..., employment_status=None)` drop `employment_letter` from a home loan only when the status is **known** and isn't salaried. An unknown status keeps it required, so the trainer's AGENT-06 and E2E-06 (whose applicants have no status) behave exactly as before. The callers pass the applicant's status: the checklist (`document_service.list_documents`), the briefing, and Phase 5's compliance checker. The seed's two home loans (Priya, Sanjay) are salaried, so no demo figure changes.

**D-33: a document with no form counts on upload, and staff check it.** This is none of a, b or c. It's a better fourth option.
- *Why:* Piece 33's rule, "a real file counts once its details are confirmed", is right for the 4 documents that have a form. A passport, driving licence, voter ID, Form 16 or ITR has no form, so the same rule could never be met. It should fall back to how every document worked before Piece 33: counted on upload, checked by staff. An "Other document" form with made-up fields (option a) adds typing but checks nothing, and building four proper forms now (option b) is a bigger piece for documents the demo doesn't use (it stays in `FUTURE-UPGRADES.md`).
- *Build:*
  - `Document.needs_details` becomes "a kind was declared and its details aren't confirmed yet". A document with no declared kind never needs details.
  - The "Which one?" dropdown gains **"Something else (passport, driving licence, voter ID)"** under ID proof and **"Something else (Form 16, ITR)"** under income proof. These send no kind. The file-name guesser learns passport, licence, voter, form16 and ITR.
- *Privacy guard, needed because of the new choice:* "Something else" must not become a way to store an Aadhaar unmasked. So for **every ID proof PDF**, whatever kind was picked, any Aadhaar-shaped number in its text that passes the Verhoeff check has its first 8 digits blacked out on the stored copy. (A photo still can't be checked. That's the OCR item in `FUTURE-UPGRADES.md`, and the manual says an Aadhaar must be uploaded as an Aadhaar.)

**Manual:** Section 4 says the employment letter is for salaried applicants only, explains "Something else", and says an Aadhaar number is blacked out on any ID proof PDF. Re-ingest once.

**Tests, the smallest set (said to Rohit before running):** `tests/ours/test_extractions.py`, adapted so "Something else" counts on upload and an ID-proof PDF uploaded without a kind still has its Aadhaar blacked out. Also the trainer's AGENT-06 on its own (offline), and `tests/phase1`. About 2 minutes.

---

# PIECE 36 — Saved chat sessions

**Goal:** the Assistant keeps conversations. A side list shows past chats; open one and carry on. Kept on the **server** (Rule 13), light and fast.

**Needs first:** none (it can be built any time). **Open decisions:**
- **Can the admin read other people's chats?** Recommended: **no.** Chats are private to their owner, even for the admin.
- **How many earlier turns does the AI see?** Recommended: **0 for now** (answers already take about 60 seconds, B2); a setting `CHAT_CONTEXT_TURNS`, up to 4 later.

### What exists
`POST /chat` answers each message on its own (`session_id` accepted and ignored). The conversation lives in `Assistant.jsx` state and is gone on refresh.

### Data
- **`chat_sessions`:** `id`, `user_id` FK (indexed), `title` (the first message's first 60 characters; **no AI call**), `created_at`, `updated_at` (indexed), `archived`.
- **`chat_messages`:** `id`, `session_id` FK, `role` (`user` / `assistant`), `content`, `mode`, `tools_used` (JSON), `sources` (JSON), `extraction_batch_id` (nullable, Piece 37), `created_at`.
- **Indexes** on `(user_id, updated_at)` and `(session_id, created_at)`.

### Addresses
- `GET /api/v1/chat/sessions?limit=20&before=`
- `POST /api/v1/chat/sessions`
- `PATCH /api/v1/chat/sessions/{id}` (rename, archive)
- `GET /api/v1/chat/sessions/{id}/messages?limit=30&before_id=`

All are **owner only** (others → 404). `POST /chat` now uses `session_id`: it creates a session if none is given, refuses someone else's, and saves both the question and the answer. The activity row stays as it is.

### Performance (assessed)
Two small indexed tables. The page loads 20 sessions and the last 30 messages, with older ones loaded on scroll. **Storing history costs almost nothing. Sending it to the AI is the expensive part**, so it's off by default.

### Frontend
`Assistant.jsx`:
- a left panel with **New chat** and the list of sessions (title, date)
- opening one loads its last 30 messages
- "Load earlier" at the top
- the current session is kept in the page's address (`/assistant/:sessionId`), so a refresh reopens it

### Tests
- Owner only.
- Pagination.
- Messages saved in order.
- The AI receives 0 earlier turns (stub).
- Refusing a foreign `session_id`.

### Browser check
Chat as Priya → refresh → the conversation is still there → New chat → the old one is in the list → open it and continue.

---

# PIECE 37 — Documents in the chatbot

**Goal:** in the Assistant, the user attaches files (📎) and says what they are, for example *"This is my Aadhaar and PAN, both fake for the demo."* They go through **the same pipeline** (31–35). The chat shows **document cards** built by React from real data, never as text the AI wrote.

**Needs first:** 34, 35, 36. **Open decisions:**
- **Customers only at first?** Recommended: yes. Staff attaching on a customer's behalf comes later.
- **Which application**, when the customer has several open? Recommended: the chat asks with a dropdown of their open applications. That's a plain choice, not the AI.

### Scope, deliberately small
The chatbot **may**:
- accept supported documents
- identify them
- start extraction
- ask for missing fields
- help confirm them
- answer questions about **confirmed** fields ("what date of birth did you read?", answered from the stored fields)

It **may not** change a status, approve, verify, or touch another application.

### Design
- **Attachments don't go through the AI.**
  - The screen uploads each file to `POST /api/v1/chat/attachments` (the same service as Piece 31: `session_id`, application, `doc_type`, `nature`).
  - It creates a batch (Piece 35) linked to the chat message (`chat_messages.extraction_batch_id`).
- **TEST/REAL from the message:** keyword matching ("fake", "test", "demo", "specimen") **pre-ticks "Test"**, and the user confirms the choice on the attach panel. Never assumed silently.
- **What the AI sees:** only a summary line such as *"2 documents attached: Aadhaar (TEST), PAN (TEST); 1 field missing."* **Document text is never put in the prompt**, so hidden instructions inside a document have nowhere to go (OWASP LLM01).
- **Limits:** ~~up to 5 files per message~~ **at most 3 files per message (Rohit, 2026-09-24)**, 5 MB each. The 3 is a **screen limit** (it's about waiting time); the server's guard is the same as for any upload, 30 an hour and 100 MB per customer (Piece 35 review).
- **No chat timeout can be too short (Rohit, 2026-09-24):** the files never ride on the chat request. Each is uploaded on its own request with the 2-minute upload limit (T-128), exactly as in Piece 35, and the chat message only carries the batch's summary line. So the chat's own 90-second limit only ever covers the AI's answer.

### Tests
- Attach → a batch is created and linked to the message.
- The prompt the AI receives never contains the document's text (stub captures it).
- "fake" pre-ticks Test.
- Another customer's application refused.
- The limits.

### Browser check
Priya: 📎 SPECIMEN Aadhaar + PAN, typing "these are fake for the demo" → both are marked Test → cards appear in the chat.

---

# PIECE 38 — Per-document missing-field form inside the chat

**Goal:** when documents attached in chat have missing fields, the chat shows a **structured form grouped per document** (Aadhaar: DOB; PAN: PAN number) with **one Confirm & submit**, and reports the result per document. It survives a refresh.

**Needs first:** 37. **Open decisions:** none expected.

### Design
- Reuse `DocumentReviewForm` (Piece 33) inside the assistant's message bubble, one card per document. It's rendered from `GET /extraction-batches/{id}`, not from anything the AI wrote.
- The chat's text says only what it can prove: *"I read most of your Aadhaar, but not your date of birth."* That's generated from the field states in code, not by the AI.
- **Confirm & submit** confirms each document through the Piece 33 address and posts a per-document result message into the session (Piece 36), so it's there after a refresh.
- Uncertain fields need the "this is right" tick. Required stays required.

### Tests
- Confirming from chat gives the same result as from the application page.
- Per-document grouping.
- A refresh reloads the form in its current state.

### Browser check
Priya attaches the SPECIMEN Aadhaar (the DOB is deliberately unreadable) and PAN (the number unreadable) → two small forms in the chat → she fills both → Confirm & submit → "Aadhaar saved · PAN saved" → the application's checklist shows them with TEST badges.

---

## Done

| # | Piece | Finished | Commit |
|---|---|---|---|
| 0 | Tools on the laptop | 2026-09-06 | `02fcf34` first commit. The live repo is now `github.com/rohit-sawant-1/loan-management-two`; the older `l-rohittt-l/loan-application-management` is out of date. |
| 1 | Project skeleton | 2026-09-06 | `backend/` with `app/` package, venv on Python 3.11.9, `requirements.txt` at trainer's versions plus two fixes (T-30, T-31), `.env` with a generated secret, `.env.example` |
| 2 | Domain rules | 2026-09-06 | `app/domain/rules.py`: every rule as plain constants and six helpers. No imports from the app. Sanity checks pass. |
| 3 | Database + 6 models | 2026-09-06 | `config.py`, `database.py`, and `models/` with the six tables. Smoke test mirrors DB-01 to DB-04 and passes. Tag `v0.0.3`. |
| 4 | Schemas | 2026-09-06 | `schemas/` with six files. Every input field checked. Smoke test mirrors UNIT-02, 04, 07, 08 plus eight stricter checks; all pass. Tag `v0.0.4`. |
| 5 | Auth | 2026-09-06 | `utils/auth.py`, `dependencies.py`, `services/auth_service.py`, `services/activity_service.py`, `services/errors.py`, `routers/auth.py`. Smoke test covers the trainer's fixture, 401-not-403, role gate, applicant signup creating two rows, and five activity-log rows. Tag `v0.0.5`. |
| 6 | Applicant endpoints | 2026-09-06 | `services/applicant_service.py`, `routers/applicants.py`. Smoke test covers UNIT-01, the `test_applicant` fixture, and owner scoping (an applicant is blocked from other profiles, the list, and creating). Tag `v0.0.6`. |
| 7 | Application endpoints | 2026-09-06 | `services/application_service.py`, `routers/applications.py`. Smoke test covers UNIT-05, UNIT-06, API-01 to API-07, per-type limits, the 400 on backward moves, manager-only disbursement, and owner scoping. Tag `v0.0.7`. |
| 8 | Document endpoints | 2026-09-06 | `services/document_service.py`, `routers/documents.py`, `DocumentUploadBody` and `DocumentListResponse` schemas. Add, list with a required/missing checklist, verify. Smoke test passes. Tag `v0.0.8`. |
| 9 | Dashboard | 2026-09-06 | `services/dashboard_service.py`, `routers/dashboard.py`, `schemas/dashboard.py`. Three grouped queries, every key present at zero, two extra numbers. API-08 passes; answers in ~10 ms. Tag `v0.0.9`. |
| 10 | Eligibility check | 2026-09-06 | `utils/finance.py` (EMI maths, UNIT-03, and an Indian rupee formatter), `utils/dates.py`, `services/eligibility_service.py`, `routers/eligibility.py`. Seven checks with plain-English messages and suggestions. Twenty-one smoke checks pass. Tag `v0.0.10`. |
| 11 | Activity log, reading side | 2026-09-06 | `routers/activity.py` and two read functions in `activity_service.py`. Manager-only list with six filters, and a per-record history. Smoke test passes. Tag `v0.0.11`. |
| 12 | Logging, tracing, `main.py` | 2026-09-06 | `utils/logging_config.py`, `utils/otel_config.py`, `middleware/logging_middleware.py`, `main.py`; `auth.validate` span in `dependencies.py`; `duration_ms` on the create and status-change logs. Smoke test reads the JSON log lines back and checks every required field. Tag `v0.0.12`. |
| 13 | The trainer's 20 tests | 2026-09-06 | `pytest.ini`, `tests/conftest.py`, `tests/phase1/test_unit.py`, `test_api.py`, `test_db.py`. **All 20 pass** (27 runs with parametrised cases). One documented adaptation, T-36. Tag `v0.0.13`. |
| 14 | React front-end | 2026-09-06 | `frontend/` on Vite with React 18, Axios and React Router. Nine pages, six components, the API client with token and 401 handling, client-side checks mirroring the server. Builds clean. Added `GET /applicants/me` to the backend so an applicant can load their own profile. Tag `v0.0.14`. |
| 15 | Streamlit front-end | 2026-09-06 | `frontend-streamlit/app.py`. Sidebar login with the token in `st.session_state`; tabs for the list (filters, status colours, detail with history and documents, status update for staff), the form with the eligibility check, and the dashboard. Serves on 8501. Tag `v0.0.15`. |
| 18 | Applications list and the form | 2026-09-06 | Server-side `search`, `sort_by` and `order` on the list endpoint, all optional so the plain call is unchanged; `tests/ours/test_list_search_sort.py` (7 pass) guards that. Front-end: search box with a 350ms wait, sortable column headings, dates behind a toggle, proper empty state; the form split into three sections with an amount preview and tenure chips. Trainer's 20 still pass. Tag `v0.1.4`. |
| 16 | Seed data, report, submission files | 2026-09-06 | `backend/seed.py` (2 staff, 6 customers, 8 applications, 58 activity rows), `README.md`, `MY_SCORES.md`, `results/phase1-results.xml` (27 runs, 0 failures). Tags `v0.0.16` and **`v0.1.0`**. |
| 19 | Automatic eligibility, and the stored summary | 2026-09-06 | Backend: three nullable columns on `loan_applications` (`eligibility_passed`, `eligibility_summary`, `eligibility_checked_at`), a SQLite `ALTER TABLE` migration in `database.py` so the existing `loan_app.db` and `test.db` pick them up, `eligibility_service.assess()` shared by the advisory check and the permanent record, `EligibilityRuleCheck` schema. `create_application` now runs the assessment itself and stores it, `submitted_at`/eligibility never blocks a 201. Front-end: the check in `NewApplication.jsx` fires on its own 600ms after typing stops, the result panel became a rule-by-rule assessment card, and submitting while not eligible opens a decision modal instead of an inline warning. The detail page shows the stored note in a collapsed panel. Streamlit got the same rule-by-rule list and an expander with the stored note. `tests/ours/test_eligibility_summary.py` (3 pass) plus all 20 trainer tests still pass (27 runs). Verified in a real browser: Priya Sharma's home loan example from this plan reproduced exactly. Tag `v0.2.3`. |
| 25 | Edit requests: customers ask, staff approve or refuse, every step logged; the database checks its own rules for applications | 2026-09-22 | `v2.5.0` to `v2.9.0` |
| 27 | Admin role: a System Administrator that sees everything and can't do loan business | 2026-09-22 | `v2.10.0` |
| 27a | What the assistant says to the admin: a third prompt, so it stops talking to the admin like a customer | 2026-09-23 | `v2.10.1` |
| 28 | Admin settings, and the switch for real document uploads | 2026-09-23 | `v2.11.0` |
| 29 | The sidebar becomes a sticky top bar, with the account behind its initials | 2026-09-23 | `v2.12.0` |
| 29b | The bar rebuilt: real glass, and dressed properly | 2026-09-23 | `v2.12.1` |
| 29c | No more sideways jump when changing page; pages fade in and start at the top | 2026-09-23 | `v2.12.2` |
| 30 | In-app notifications: their own tables, three triggers, and the bell | 2026-09-23 | `v2.13.0` |
| 31 | Real document uploads: the safety and rebuild pipeline, automatic classification, two storage folders, Documents to check | 2026-09-23 | `v2.14.0` |
| 32 | TEST documents: badges, the staff notification, the checklist note, the compliance note, the admin purge. Browser check passed 2026-09-24 | 2026-09-23 | `v2.15.0` |
| 32a | Found in the browser check: typing in any pop-up lost focus after every key (T-124) | 2026-09-24 | `v2.15.1` |
| 32b | Found in the browser check: green banners pushed the tick and the message to opposite edges | 2026-09-24 | `v2.15.2` |
| 32c | Found in the browser check: "X/Y submitted" counted files, not document types (T-123) | 2026-09-24 | `v2.15.3` |
| 32d | Replacing a document: Replace on any unverified row, the old copy kept but counting nowhere, replaced copies shown to staff only (D-30) | 2026-09-24 | `v2.16.0` |
| 33 | Document kinds and their details: Aadhaar, PAN, salary slip, bank statement; typed in, checked, confirmed; only confirmed real files count | 2026-09-24 | `v2.17.0` |
| 34 | Reading documents, lean: a PDF's own text fills the form; Aadhaar digits blacked out on the stored copy; an Aadhaar that can't be blacked out is refused unless TEST; SPECIMEN demo kit | 2026-09-24 | `v2.18.0` |
| 34a | PDFs and images marked binary in git, so a Windows checkout can't break the demo PDFs (T-127) | 2026-09-24 | `v2.18.1` |
| 34b | Uploads and Replace wait up to 2 minutes, not 15 seconds (T-128) | 2026-09-24 | `v2.18.2` |
| 35a | Audit fixes: the manual states the upload rules the code enforces (PAN, PDF-only statements, page and hourly limits); three findings opened as D-31 to D-33 | 2026-09-24 | `v2.19.1` |
| 35b | D-31 to D-33: the SPECIMEN check is Gemini-only; the employment letter is for salaried home-loan applicants only; "Something else" documents count on upload, with any ID-proof PDF's Aadhaar blacked out | 2026-09-24 | `v2.19.2` |
| 35 | Several documents at once: up to 3, one request each, 2 at a time; inline cards with Confirm all; one lock around PDFium so parallel uploads can't crash the server | 2026-09-24 | `v2.19.0` |
