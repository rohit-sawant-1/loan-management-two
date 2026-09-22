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
| 2 | `edit_request_service.py`, the new addresses, `PATCH /applications/{id}`, closing open requests on a status move, API tests | v2.6.0 |
| 3 | React, the customer's side: `EditRequestCard` on the application page, the two-step pop-up, the unlocked-fields form, the support-email note | v2.7.0 |
| 4 | React, the staff side: the "Edit requests" page and sidebar item, and activity labels for the five new events | v2.8.0 |
| 5 | Manual (Section 6, the FAQ, a new "Contacting the bank" section), the T-102 ingestion fix, re-ingest, and asking the chatbot twice | v2.9.0 |

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

## Done

| # | Piece | Finished | Commit |
|---|---|---|---|
| 0 | Tools on the laptop | 2026-09-06 | `02fcf34` first commit; repo at `github.com/l-rohittt-l/loan-application-management` (private) |
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
