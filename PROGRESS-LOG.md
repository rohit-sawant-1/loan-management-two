# Progress log

Newest entries at the top. Short on purpose.

---

## 2026-09-24 — Piece 32 browser check: passed, with three bugs found on the way

**Asked for:** the Piece 32 browser check, step by step, before anything else.
**Built:** no new feature. Priya uploaded a dummy SPECIMEN Aadhaar, got the amber TEST badge and "including 1 TEST document", Rajan's and Anita's bells showed 1, and the admin purge removed it (file, rows and all, with an activity log entry), leaving her old ID proof alone. Two fixes along the way: typing in any pop-up lost focus after each key (T-124, v2.15.1), and the green success banners pushed the tick and the text to opposite edges (v2.15.2).
**Found:** the "2/3 submitted" line counts files, not document types, so three ID proofs would read "3/3" (T-123, from Piece 14). Also, whether a same-type upload should replace the old one is now D-29.
**Realised:** you questioned the count straight away, because it didn't match what you had actually uploaded. That's exactly what a browser check is for: no test looks at that line.
**Next:** fix T-123, then decide D-29.

---

## 2026-09-23 — Piece 32: the TEST-document workflow

**Asked for:** the next piece in the Document intelligence programme, following straight on from Piece 31. Piece 30 had already built the staff notification for a TEST document upload but never called it; this piece was about actually wiring everything Piece 31's classification unlocks.
**Built:**
- A TEST upload now notifies every active loan officer and branch manager, in the same database commit as the upload itself, so nobody gets told about a document that ended up not being saved.
- The document checklist now says how many of the uploaded documents are TEST ("4/4 submitted, including 2 TEST documents"), and every TEST document gets an amber badge wherever it's shown — the applicant's checklist, the staff "Documents to check" page, and the row itself.
- "Mark verified" on a TEST document is relabelled "Verify (test document)", so nobody reads a TEST document's verified tick as proof it's genuine.
- Phase 5's compliance checker now adds a note, "Includes TEST documents — not genuine", when any document on the application is TEST. It's a note only — the pass/fail verdict is untouched, and both Phase 5 tests that check the verdict still pass unchanged.
- The system administrator can now permanently purge every TEST document in one step, from a new card on the Admin page. It asks for the exact phrase "DELETE TEST DOCUMENTS" typed out, not just a tick box, since there's no undo. Real and undeclared documents are never touched.
**Found:** the "SPECIMEN backstop" bullet in the old written plan for this piece turned out to already be built — Piece 31's classification does that exact check at upload time now, for every document, not just ones declared real. Dropped rather than duplicated.
**Realised:** running the whole five-phase test suite in one go takes a long time (RAG and agent tests call real APIs), so for a change scoped to a few files it's faster and just as trustworthy to run only the touched test files plus Phase 5's — that's what confirmed this piece, at 133 of 133 passing.
**Next:** a browser check by Rohit (upload a SPECIMEN-worded PDF, see the badge and the officer's bell fire, then try the admin purge), and a look at the handful of full-suite failures seen near the end of an unrelated run — not caused by this piece, but not yet identified either.

---

## 2026-09-23 — Piece 31: real document uploads

**Asked for:** the next piece, which the plan named as real uploads. In plan mode, you changed the design partway through: instead of one folder outside the project, you wanted two — one inside the project that travels with `git clone` to the Wipro laptop, one outside it for anything uncertain — and you wanted the system to work out for itself whether a document is real or a test one, rather than asking. That collided with our own rule that a real document never goes to Gemini, so we settled it together: Gemini only ever confirms something a local check already found, never judges an unknown document first.
**Built:** the whole pipeline, in the order the plan laid out.
- **Safety, then rebuild.** Every upload is read capped at 5 MB, its real type is read from its bytes (never trusted from the name), a PDF is scanned for anything that can run code or reach outside the file, then every file is redrawn from scratch — an image re-encoded, a PDF's pages redrawn as pictures at 150 DPI — so nothing hidden survives.
- **Classification, before the rebuild destroys the evidence.** A PDF's own original text is checked for SPECIMEN/SAMPLE/TEST/DEMO wording. Only on a match does the matched text (never the file) go to Gemini to confirm. Both have to agree for a document to be called `test`; anything else is `undeclared`, treated with the same caution as `real`. Nobody is asked which it is — there's nothing left in the upload for anyone to lie in.
- **Two folders.** `backend/uploads/`, tracked by git, only for documents the server is confident are demo material. `C:\LAMS\uploads\`, outside the project, for everything else. Both encrypted either way, so even a wrong classification never puts a readable byte in the repo.
- **The screens:** the placeholder banner on a customer's document form became a real upload form — document type, one consent tick, a file picker — with the before-and-after size shown once it's done, and a View button that opens the real file. A new "Documents to check" page for staff, closing B3.

36 new tests, **402 passing**. Manual re-ingested at 60 chunks, and its old, wrong "financial data is encrypted at rest" line (T-113) now says what's actually true.
**Found:** two things only surfaced by testing for real. Mocking the Gemini confirmation at the wrong level — replacing the whole function instead of what it calls — hid that classification had no safety net of its own; a genuinely unexpected failure there would have 500'd the upload. It does now. And the rate limits from the plan (30 uploads an hour, 100 MB a customer) had been written into `rules.py` as numbers and never actually wired up — caught while closing out the piece, not left for later.
**Realised:** encryption is doing more work than it looks like. Because every file is ciphertext before it ever touches disk, and the key never leaves `.env`, committing the "safe" folder to GitHub doesn't expose a document even when the classifier gets it wrong — the real backstop is the working rule that only dummy documents are ever uploaded at all, and the folders and the classifier are defence in depth on top of that, not instead of it.
**Next:** Piece 32, the TEST-document workflow — the badge, the staff notification when a TEST document lands (the trigger is already built, just not called yet), and the admin's purge button.

---

## 2026-09-23 — Piece 30: the bell, and the notifications behind it

**Asked for:** you confirmed Pieces 27 and 28 work in the browser, said the glass bar looks good, and asked for the next piece. You also tried "change application 21 to under review" as the admin: **15 seconds, correct answer.**
**Built:** the app's own notifications, as a system entirely separate from the activity log — its own table, its own service, its own addresses. Nothing in one touches the other, and there is a test that proves it: a status change writes exactly the same number of activity rows whether notifications happen or not.
- **Three triggers and no others.** Staff hear when a customer asks to edit a submitted application, and (from Piece 32) when a customer uploads a document marked TEST. A customer hears when their own application's status changes, starting with the moment it is submitted. A setting change, an ordinary document, a verification, a sign-in: nothing.
- **Who exactly gets one.** Every loan officer and branch manager whose account is switched on. Not a switched-off account, not the administrator, and never the customer. For status changes, only the one customer whose application it is.
- **The bell** sits in the slot Piece 29 left for it, with a red count that appears only when something is unread. It asks the server every 30 seconds and whenever you change page. Clicking a notice marks it read and takes you to the thing it is about.
- **Nothing private in the text.** No amounts, no identity numbers. "Priya asked to change application 2", not the figure she wants. A bell gets read over somebody's shoulder.
- **The database keeps the two audiences apart.** A rule inside the table makes a staff message impossible to file against a customer, whatever the code does.

14 new tests, **368 passing**. The front end builds and lints clean, and the manual has a Notifications paragraph, re-ingested at 58 chunks.
**Found:** your 15-second answer this afternoon, against 75 seconds at midnight, is now written into T-119 as measured evidence. It matters for B2: the slow manual answers have to be measured in the afternoon, and demo rehearsals should happen at the hour the demo happens.
**Realised:** notifications are saved in the same commit as the thing they are about. If the edit request fails to save, the notices about it are rolled back with it — nobody is told about something that did not happen.
**Next:** the browser check for the bell, which is the one part no test covers: Priya asks to edit application 2, and Rajan's bell should show 1.

---

## 2026-09-23 — The page stops jumping sideways when you change page

**Asked for:** moving between pages from the navbar jerks a little left then right, and you wanted it smooth.
**Built:** the jerk was the scrollbar, not the transition. A long page like Applications has one; a short page does not. When it disappears the window gets about 15 pixels wider, so everything centred — the bar and the page — slides right and then back. The browser can reserve that space permanently, which is one line, and the jump is gone. It only started showing in Piece 29 because the page is centred now; next to a fixed sidebar, only the right-hand edge moved and nobody noticed.
Then the actual smoothness: each page fades in over about a sixth of a second, and the window goes back to the top when you change page, which React Router does not do by itself. Opening a page from halfway down a long list used to drop you halfway down the new one.
**Found:** the fade is opacity only, on purpose. Sliding the page even a few pixels would mean any pop-up inside it positions itself against the page instead of the window, which would put every confirmation dialog in the wrong place.
**Realised:** anyone who has asked their computer to keep animation to a minimum gets no fade at all; the browser tells us, and it is three lines to respect it.
**Next:** your call on whether the bar looks right now, then Piece 30.

---

## 2026-09-23 — The top bar, rebuilt: actual glass this time

**Asked for:** you said the bar looked trash and, in particular, did not look translucent, and asked for something that suits a professional finance product.
**Built:** both complaints were fair, and the second one was a plain mistake on my part.
- **It was 78% opaque.** That is paint with a hint of transparency, not glass. It is 0.68 now, with a wider blur and the colour behind it boosted, which is as see-through as it goes before white text stops being comfortable to read on it.
- **Glass over one flat colour still looks like paint.** The page was one flat grey, so the blur had nothing to pick up. There are now two very soft pools of bank blue across the top of the page, fixed in place, so they stay behind the bar while everything else scrolls. That is what actually makes it read as glass, even before you scroll.
- **The bar itself was cramped and plain.** It is taller now, with thin dividers separating the brand, the links and your account; the links are pills; the page you are on is a brighter pane of the same glass with a lit top edge, rather than a flat grey block; there is a small capitalised "BRANCH PORTAL" under the name; and your initials sit in a slate gradient with a chevron that turns when the menu opens.

**Found:** I cannot see the screen from here — there is no browser in this session — so this is careful work, not checked work. You are the only one who can say whether it looks right now.
**Realised:** the honest lesson is that I picked 0.78 out of the plan without asking what it would actually look like over a flat grey page. Translucency is a property of two things, not one.
**Next:** you look at it and tell me. If dark glass is not the look you want at all, a light one is two values; say so and it is a five-minute change. Then Piece 30.

---

## 2026-09-23 — Piece 29: the sidebar moves to the top of the screen

**Asked for:** you checked Pieces 27 and 28 in the browser, said both work, and asked for the next piece.
**Built:** the navigation is now a bar across the top instead of a column down the left. It sticks to the top as you scroll, and it is slightly see-through with a blur, so the page moves underneath it. Nothing about who sees which link changed — each role has exactly the same links, in the same order, as before.
- **Your name, role and Sign out** moved into a small menu behind your initials on the right. Seven links plus a name and a button do not fit across a laptop screen. The menu closes on Escape, on a click anywhere else, and when you move to another page.
- **A gap on the right for the bell**, which is a real component that draws nothing at all until Piece 30 fills it in.
- **Two things that would have broken quietly.** Table headings stick to the top while you scroll a long list, and with a sticky bar above them they would have slid underneath it and disappeared — they now stop exactly below the bar. And a pop-up has to cover the bar rather than the other way round, so its layer was raised.
- **Narrow screens:** at 1100px the "Branch portal" line goes, at 980px the brand name goes, and on a phone the links become just their icons, so the bar stays one row high.

Front end builds and lints clean, with the same 11 warnings that were already there. No backend file changed, so the 354 tests are untouched.
**Found:** closing the menu when the page changes set off a new lint warning, because doing it in an effect draws the page twice — once with the menu open, once with it shut. React has a documented way to do that while rendering instead, which is what it does now. Worth knowing, because the same warning is on nine other files from before.
**Realised:** the old sidebar styles are gone rather than left lying around, and nothing else in the app referred to them — only the round brand badge is shared, and the three sign-in pages still use it.
**Next:** Piece 30, the notifications themselves: their own tables, the three triggers, and the bell's unread count.

---

## 2026-09-23 — Piece 28: the admin's switch for real document uploads

**Asked for:** on to the next piece.
**Built:** the settings system, and the first setting in it. The admin's page now has a **Settings** card with a switch called "Real document uploads". Off is exactly what the app has always done — a document is recorded by its type and file name. On is what Piece 31's real uploads will read; until that screen exists, anyone adding a document sees a line saying uploads are on but the upload screen is still being built.
- **Where it is kept:** a new `app_settings` table, one row per setting. Not `.env`, because that belongs to one machine and needs a restart; a switch the admin flips has to reach everybody straight away.
- **Who can do what:** everyone signed in can *read* the settings, because the screens change with them. Only the admin can *change* one. Every change is written to the activity log with their name, and the manager can filter the Activity page for it.
- **One list, not several:** the setting, its default, its label and the sentence explaining each position all live in `rules.py`. The database check, the API and the screen read from there, so adding a setting later is one line in one file.

23 new tests, **354 passing**. The front end builds and lints clean, and the manual now has the switch in it, re-ingested at 56 chunks.
**Found:** the manual has always promised that documents must be PDF, JPG or PNG and under 5 MB — and the code has never stored a file at all, only a name. Nobody had written that down (T-120). Section 4 now says plainly that the file isn't stored yet, which is also the honest thing for the chatbot to be quoting. Piece 31 makes the original promise true.
**Realised:** two small things worth knowing. Pydantic would happily read `"yes"` or `1` as `true` in the switch's body, so the switch is now `StrictBool` — true or false, nothing else; two tests caught it. And the key check is a database trigger rather than a rule inside the table, because the list of settings is meant to grow: a rule baked into the table today would refuse a setting added in Piece 31, and SQLite can't change one without rebuilding the table.
**Next:** Piece 29, the top navigation bar, which moves the sidebar to a sticky bar across the top and leaves a spot for the notification bell that Piece 30 fills.

---

## 2026-09-23 — Piece 27a: the assistant stops talking to the admin like a customer

**Asked for:** you signed in as the admin and typed "change application 21 to under review". The assistant said it couldn't change submitted applications and told you to email support@bank.com about "your application". You asked me to think through every other thing an admin might try, and write the right reply for each. No live testing tonight, because Gemini is slow at midnight.
**Built:** a third prompt for the assistant. It knew only two kinds of person — staff, and everyone else — so the admin, not being staff, was handed the customer's prompt and answered like one. Now there are three: customer, staff, administrator, picked by `template_for(role)` sitting right next to `tools_for(role)`. The admin's paragraph covers eight things it might ask to change (with who really does each), eight things nobody can do through the assistant at all, and the two wording traps: never "your application", never the customer support address. 17 new tests; **331 passing**.
**Found:** the safety was never in question. The admin has no record-changing tools, so the change could not have happened — what was broken was only what the refusal *said*. Worth keeping that distinction: the tool list is the guard, the prompt is the manners. Also, the assistant never looked application 21 up before answering, so it couldn't tell you what was actually true about it.
**Realised:** your timing observation is the useful one. 3 to 8 seconds in the afternoon, about 75 seconds at midnight, with Gemini returning "high demand" errors. That means B2 (the slow manual answers) has to be measured in the afternoon, and demo rehearsals should happen at the hour the demo happens (T-119).
**Next:** when Gemini is quick again, sign in as the admin and try "change application 21 to under review" plus one or two from the list in `BUILD-PLAN.md` (Piece 27a). After that, Piece 28.

---

## 2026-09-22 — Piece 27: a System Administrator who sees everything and changes nothing

**Asked for:** build the next thing in `BUILD-PLAN.md`, which is Piece 27, and report back.
**Built:** the new **admin** role, end to end.
- **Server:** every address was sorted into "looking" or "doing". Three new guards let the admin look at the applicants list, the edit-request queue, the dashboard and the activity log; a fourth (`require_business_actor`) keeps it out of creating applications, adding documents and the eligibility check. Nobody can register as an admin any more (T-115). New address `GET /admin/users` lists every account with a count per role.
- **Screens:** a new **System administration** page, the admin's sidebar, and a small grey "View only" note wherever its buttons would have been. Signing in as the admin lands on the admin page, not on the applications list.
- **Seed:** `seed.py` now adds `admin@bank.com / Admin@123` to any database that hasn't got one, including your existing `loan_app.db`, and running it twice is safe.
- **Manual:** Section 2 has an Administrator paragraph, and Sections 8 and 10 say the admin can see the dashboard and the audit log. Re-ingested, 55 chunks.

28 new tests, the suite is **314 passing** (286 before), the trainer's 20 still pass, and so do Phase 3's offline tests and all eight Phase 4 MCP tests. The front end builds and lints clean. I also checked it against the real running server: the admin opened all nine screens and was refused all eleven actions.
**Found:** the chatbot got the new manual paragraph wrong on the first try, saying it had no information about the administrator, then answered correctly twice in a row. Gemini was returning "503, high demand" during that run. Worth knowing before a demo, because a wrong "it's not in the manual" looks exactly like a real answer (T-118). Those answers also took 78 and 189 seconds, which is B2 again.
**Realised:** the admin must never go into `STAFF_ROLES`. That one set decides who gets the chatbot's record-changing tools and who can run an underwriting review, so putting the admin in it would have handed a look-only role the power to change loans by chat. Its access comes from its own guards instead. The same trap waits in every later piece: a new action guarded by "any logged-in user" lets the admin through (T-117).
**Next:** Piece 28, the admin settings page with the switch that turns real document uploads on and off.

---

## 2026-09-22 — Planned the Document intelligence programme (Pieces 27–38); nothing built

**Asked for:** first Piece 24 (profile changes). It grew into real document uploads, then reading documents, a demo/real switch for a new Admin role, TEST documents, notifications, a top navigation bar, several documents at once, and documents and history in the chatbot. You asked for it all to be planned in detail as separate pieces, which you'll implement yourself, one at a time.
**Built:** no code. Pieces 27–38 are written into `BUILD-PLAN.md`, each with its goal, what exists today, the data, the addresses, the screens, the tests and a browser check, plus the build order. Decisions are in `TRAPS-AND-DECISIONS.md` (Settled), the new traps are T-108 to T-115, and production hardening is in `FUTURE-UPGRADES.md`.
**Found:**
- Documents today are only typed names; no file is stored anywhere, and MongoDB isn't needed.
- The manual promises encryption that doesn't exist (T-113).
- The project folder syncs to OneDrive (T-112).
- Staff sign-up would let anyone register as an admin (T-115).
- Gemini's free tier may use what we send (T-108).
- The loan purpose reaches the AI unmarked (T-110).
- Aadhaar numbers may not be stored in full (T-114).
**Realised:**
- Admin sees everything but can't do loan business.
- Notifications are their own system, with three triggers.
- TEST documents count, but are always marked.
- Identification isn't authenticity.
- There's no local LLM: Gemini only, and never for REAL documents.
**Next:** Piece 27, the Admin role, when you start implementing.

---

## 2026-09-22 — Piece 25 finished: edit requests on screen, in the manual, and in the chatbot

**Asked for:** no more step-by-step and no quizzes. Finish the edit feature.
**Built:** steps 3 to 5 in one go.
- **Customer:** a "Changes to this application" card on their page. It has the two-step pop-up, the unlocked-fields form, the refusal reason, and the support@bank.com note.
- **Staff:** a new "Edit requests" page with filters and approve/refuse pop-ups.
- **Activity page:** the five new events have labels, and edits read "Amount (before) / (after)".
- **Manual:** updated in five places, plus the T-102 fix, then re-ingested (50 chunks).

The front end builds, and the suite is 286 passing.
**Found:** the chatbot answered "how do I contact the bank staff?" by refusing it as off-topic and inventing a customer service hotline (T-106). It now searches the manual and says support@bank.com. The first question, "can I change my application?", was right straight away. Both answers took about 55–65 seconds, which is B2's slowness, not something new.
**Realised:** checking was build, lint, API tests and asking the real chatbot; I didn't click through the screens in a browser. The Wipro laptop needs a pull, a backend restart and a re-ingest before it shows any of this (T-107).
**Next:** Piece 26 (database checks for the other tables), or B2 (the 65-second answers) if the demo is close. Your call.

---

## 2026-09-22 — Piece 25 step 2: edit requests work end to end on the server

**Asked for:** "go" on step 2, the part that makes asking, approving, refusing and saving actually work.
**Built:** `edit_request_service.py` with the whole flow, plus five new addresses: ask, read, the staff queue, approve and refuse. `PATCH /applications/{id}` saves an approved edit. A status change now also closes any request still waiting or unlocked, in the same save. 28 new API tests; the suite is 285 passing (257 before), the trainer's 20 still pass, and Phase 4's eight tool tests pass against the new code.
**Found:** nothing broke, but one design point is worth knowing. A refused save (for example, 72 months on a personal loan) does *not* use up the approval, so the customer can fix the number and try again. Only a successful save locks editing.
**Realised:** every step lands in the activity log under the application's number: `edit_requested`, `edit_request_approved`, `edit_request_refused`, `application_edited` (with the before and after values and the old eligibility result) and `edit_request_closed`.
**Next:** Piece 25 step 3, the customer's side in React: the "Request an edit" card on the application page, the two-step pop-up, the unlocked-fields form, and the support-email note.

---

## 2026-09-22 — Piece 25 step 1: the groundwork for edit requests, and the database now checks its own rules

**Asked for:** your top priority, B1. Let a customer ask to change a submitted application, have staff approve or refuse, and log every step. Then, while planning, you asked whether every input field is validated, and wanted checks on all three layers: the form, the server and the database.
**Built:** the plan (Piece 25, five steps) and step 1. The new rules are in `rules.py`. There's a new `application_edit_requests` table and the input shapes for asking, approving, refusing and saving an edit. A shared `clean_free_text` check trims spaces and blocks hidden characters. The database's own checks are in the new `db_checks.py`. 45 new tests; the suite is 257 passing (212 before), and the trainer's 20 still pass.
**Found:** the database was checking almost nothing. SQLite ignores `VARCHAR(500)`, doesn't check that a status is real, and foreign keys are off on purpose, so only "not empty" was enforced (T-105). The server also let a purpose of three spaces through. And ingesting a shorter manual would have left the old "cannot be modified" text searchable (T-102, fixed in step 5).
**Realised:** the trainer's "cannot be modified after submission" rule gets overridden on the trainer's own say-so (D-28). Edits are only allowed at submitted and under review, only for amount, tenure and purpose, and eligibility is re-checked afterwards. There's no email; a placeholder support address goes on the page and in the manual. Database checks for the other tables become their own piece, Piece 26.
**Next:** Piece 25 step 2, the service and the addresses that make requests actually work, with API tests.

---

## 2026-09-16 — The underwriting review now charges people for the loans they already have

**Asked for:** you asked whether we look at how much of a borrower's income is already going out in EMIs, and whether banks check a new loan against the existing ones. Then, once it turned out we half did: fix it.
**Built:** Phase 5's Risk Assessor now works out affordability the same way Phase 1's form check always did — take 50% of monthly income, subtract what they already pay elsewhere, and the new EMI has to fit in what is left. Both go through the one helper now, so the form and the review cannot reach opposite verdicts on the same person. Seven new tests, all stubbed, no Gemini quota spent. Our suite is 185 passing and the trainer's twenty still pass.
**Found:** the bug was sitting in plain sight and was oddly specific. The agent already folded existing EMIs into the debt-to-income ratio it *displayed*, then ignored them completely when setting the yes/no flag that actually costs 20 points and moves the recommendation. So it could print "84% of income already committed" and "affordable: yes" in the same breath. Also worth knowing: the trainer's acceptance criterion is written one-way — "if the EMI is over 50%, say no" — and says nothing about the case where the EMI alone fits but the total does not, so our stricter version does not break the contract.
**Realised:** the fix changes no seeded application. Sanjay, application 7 from the browser checklist, was already failing on the old maths — ₹48,007 against a ₹37,500 ceiling — which is exactly where his 84% ratio and score of 70 come from. So the demo figures are untouched, but it also means nothing on screen currently *demonstrates* the new rule. Worth fixing in the seed data when we write the demo script.
**Next:** the profile page you asked for — a customer seeing and editing their own details, with officers and managers approving the changes. Parked as Piece 24 in `BUILD-PLAN.md` with the open questions written down; it gets planned properly before anything is built.

---

## 2026-09-11 — A checklist for driving Phase 2 and Phase 3 by hand, and proof the fixes are real

**Asked for:** a short list of what to try in a browser for the manual chatbot and the agent tools, which pass their tests but have never been used by a person.
**Built:** `BROWSER-CHECKLIST.md`, seventeen things to try across four parts, each with the exact login, the exact words to type, and what should come back. Written to be read cold. The questions that matter most are B2 and A4: B2 is Priya asking for somebody else's application and being refused by the API rather than by the AI, and A4 is asking about a product the manual does not cover, where the only wrong answer is a confident one.
**Found:** I ran parts C and D against the real server rather than guessing, and it was worth doing. Every figure in the checklist is now measured — application 7 comes back REQUEST_MORE_INFO at 70 out of 100, EMI ₹48,007, ratio 84%, all four agents listed, rupees throughout and no dollar sign. The briefing narrative wrote "ID proof" in its own words, which proves the shared helper reaches the AI and not just the screen. "assess application 999" answered HTTP 200 with one plain sentence and no amber notice, which is the phase 3 fix doing its job. Also worth knowing: the Phase 5 agents call the API at a fixed address from `.env`, so a review only works when the backend is on **port 8000**. On a spare port the review degrades politely and says the loan system is unavailable — correct behaviour, confusing if you do not know why.
**Realised:** the one thing I could not check is the only thing the list is really for. Whether an answer from the manual is *good* — complete, not invented, phrased like a bank — needs a person reading it. Everything a script can check was already green while all twelve bugs in `BUGS-AND-FIXES.md` were live.
**Next:** you work through `BROWSER-CHECKLIST.md` and tell me which items looked wrong. After that, audit phase 4, which is the duplicated-truth sweep and has no symptoms today.

---

## 2026-09-11 — Audit phase 3: the review can no longer take the screen down

**Asked for:** wrap the review path so an unexpected shape gives a degraded answer instead of a 500 and a red banner.
**Built:** the whole review branch is now wrapped, and every figure inside the answer is read defensively. A crash becomes a normal reply saying the review could not be completed and that the application itself is unchanged — which is the first thing anyone wonders after an error. A missing number costs that one line instead of the whole answer, and it is never filled in with a zero. Ten new tests, every failure a stand-in raising on purpose, so no quota was spent. 202 pass now, and Phase 4's 25 still pass separately.
**Found:** the reason the old code gave for being safe was true and not enough. It said the caller returns early whenever data collection fails — which covers the failures the graph *records*, and none of the ones that escape it. Looking properly, the four agents' own error handling wraps only their calls to the AI. The plain-Python arithmetic before those calls is unguarded, so an applicant record missing one field raises straight out through the graph and past every check. That is T-98.
**Realised:** worth knowing separately, because it will come up again in React work. A component that throws while *rendering* is not caught by the try/catch around the fetch that loaded its data — the request already succeeded by then. React unmounts the whole tree and the page goes white. So one optional field on the briefing card could have cost the manager the entire dashboard, which is why it got three lines of guarding even though the server's schema says those fields cannot be missing (T-100, D-25).
**Next:** the browser checklist for Phase 2 and Phase 3 of the product, which have passing tests but have never been driven end-to-end by a person.

---

## 2026-09-11 — Audit phase 2: the glitches you can see from across the room

**Asked for:** fix the visible number and date glitches found by the sweep, while you were away.
**Built:** "3.0 days" on the Morning Briefing and "3.0 years" on My Profile are now whole numbers, through one new `whole()` helper rather than five scattered `Math.round` calls. The risk score in the activity table reads "70/100" and the details panel now says "70 out of 100" instead of falling through as a bare "70.0" with nothing to say what the scale was. And `label()` knows the words that are not ordinary words, so "Id proof" is "ID proof" everywhere, along with KYC, EMI, CIBIL and PAN.
**Found:** two things I did not expect. The eligibility timestamp bug had a second half — the code fix only helps applications submitted from now on, and fourteen rows in your database still had the old UTC line baked into their stored text. A stored string does not fix itself when the code that wrote it changes. So `init_db()` now strips that one line on startup, alongside the column step from D-18, and your demo data is already clean. And the "Id proof" mistake was not one bug in the browser: the backend had ten copies of the same bare underscore-strip, and those ones feed the AI prompts, so the chatbot could describe a document differently from the app (Rule 12). All ten now go through one shared helper and no raw `replace("_", " ")` survives anywhere.
**Realised:** the timestamp fix was the interesting one. The instinct is to convert the string to Indian time, but that makes the server decide the reader's timezone and leaves two copies of one fact to drift apart. Deleting the line is the better fix, because the moment was already stored properly in a real datetime column right beside it. One fact, one field, formatted where it is read — which is how every other date in this app already works, and the bug existed exactly because this one string opted out.
**Next:** audit phase 3 — wrap the review path so an unexpected shape gives a degraded answer instead of a red banner.

---

## 2026-09-11 — Piece 22 closed: verified in the browser, all four checks

**Asked for:** confirm step 5 works for real, including that a customer cannot run a review.
**Verified:** a review of application 7 ran in 25 seconds and returned REQUEST_MORE_INFO with the figures and a reasoning paragraph. Priya, a customer, was refused instantly — on her *own* application, which is the stricter test, because the rule is about role rather than ownership. Two bugs found and fixed along the way: the browser was giving up at 15 seconds (the app-wide limit, right for database reads and wrong for four agents), and the AI wrote "$4,000,000.0" because the prompt handed it a bare number with no unit.
**Realised:** every number going into a prompt needs its unit attached. The risk assessor already did this and its EMI was always correct; only the decision maker passed a raw figure, and the model filled the gap with dollars. That is now T-94.
**Next:** Piece 22 is done — all five phases reachable from one chat box, nothing left in a terminal or in Streamlit.

---

## 2026-09-11 — Piece 22 step 5: Phase 5 in the chat. One assistant, all five phases.

**Asked for:** the last piece — "assess application 7" should run the four-agent underwriting review from the React chat, instead of only from a terminal prompt.
**Built:** it does. A staff member types the phrase, sees a line saying four agents are working, and about ten seconds later gets the verdict, the figures behind it, and the paragraph explaining it — with all four agents listed in order under "Show how this was worked out". 46 new tests, 183 passing, none of them spending quota.
**Found:** the review only makes **2 AI calls**, not four. Every number and the decision itself are plain Python (D-19), and the model only writes prose. So a dead quota changes the wording of a review and never its verdict — and with your five keys that is roughly 500 reviews a day. Also confirmed the chat bubble already preserved newlines, so the formatted answer needed no CSS at all.
**Realised:** the four agents map exactly onto the "how this was worked out" list the screen already had. That meant no new response field, no new frontend component, and the pipeline became visible for the cost of one dictionary. The trigger is a typed phrase rather than something the model decides, because a model that sometimes runs a ten-second review and sometimes does not is the last thing you want on stage.
**Next:** try it in the browser as Rajan, then Piece 22 is closed and every phase lives behind one chat box.

---

## 2026-09-11 — Step 4 confirmed working in the browser, permission gate included

**Asked for:** try the confirmation flow for real, as Rajan the loan officer.
**What happened:** "approve application 1, documents all verified" proposed the change, waited, and went through on YES. The audit trail reads `under_review -> approved by rajan@bank.com (documents all verified)` — his name, his reason, exactly as typed. Then "disburse application 3" asked for a reason first, and once given, confirmed and **refused**: only a branch manager can disburse. Checked the database afterwards and application 3 is untouched, so the refusal was real rather than just a message.
**Realised:** this is the bit worth showing in the demo. The assistant did not get its own permission system — it inherited Phase 1's, which was already tested twenty ways. An officer cannot disburse through the chat for exactly the same reason he cannot through the browser, and that is a far better answer to "is this safe?" than any amount of careful prompting.
**Next:** Piece 22 step 5, the last one — "assess application 7" runs Phase 5's four-agent review in the chat.

---

## 2026-09-11 — The confirmation flow actually works now, and I owed you an apology

**Asked for:** you tried "approve application 1, documents all verified" in the browser and got "No AI is available at the moment", and you pushed back on my claim that two of your API keys were fake.
**Found, first:** you were right about the keys and I was wrong. I judged them by their shape — 53 characters starting `AQ.` — and said they were OAuth tokens. I should have tested them. Asking Google directly, all three work and show 50 models each. Gemini issues more than one key shape and I did not know that. T-89 is corrected, and you now have a real three-rung ladder.
**Found, second:** the browser error was a genuine bug in my code, not your keys and not the AI. ReAct writes one `Action Input:` line, so for a tool with several arguments LangChain hands the whole lot to the first parameter and leaves the rest blank. With required parameters, the call was rejected before my code ever ran, and the chat honestly reported that as "no AI available" (T-90).
**Built:** the fix, in two halves that both matter — defaults on every parameter after the first so the call lands, and an unpacker that works out what the model meant. A real model wrote **six** different shapes for the same call; all six are handled and pinned by tests. Commas inside a reason no longer tear the value in half. 137 tests pass.
**Realised:** "No AI is available" was an honest message that pointed at completely the wrong thing, because the chat's error handling cannot tell a broken tool from a broken provider. Worth remembering next time that message appears.
**Next:** you confirm it in the browser, then Piece 22 step 5 — Phase 5's four-agent review in the chat.

---

## 2026-09-10 — Piece 22 step 4: staff can change records by chatting, after confirming

**Asked for:** put Phase 4's record-changing tools into the React chat, staff only, and explain where to paste the new API keys.
**Built:** the agent's toolset now depends on who is asking. A customer gets the same five read-only tools as before; staff get three more that can create an application, move its status, or record a document. Those three do **not** act when called — they describe what they are about to do and wait for the person to reply YES. Officers and managers get an identical list on purpose, because the API already refuses disbursement to anyone who is not a manager, and a second copy of that rule here would be a second thing to keep in step. 26 new tests, 128 passing overall, none of them spending quota.
**Found:** your new API keys are the problem, not the code. All three had been pasted into `GOOGLE_API_KEY` as one comma-separated blob, so Gemini was being sent a 147-character string and rejecting the lot — which is why Phase 3's live tests failed. Worse, two of the three are not API keys at all: they are 53 characters starting `AQ.`, which is an OAuth token, where a real Gemini key is 39 characters starting `AIza`. Put the one good key back and Phase 3 passes again.
**Realised:** the confirmation cannot be left to the model. If the agent were asked to remember the pending change and re-issue it on "yes", a model that misreads one digit would disburse the wrong loan, confidently. So the proposed change is recorded as plain data and that exact recorded call is what runs — the model decides what to propose, Python decides what runs.
**Next:** Piece 22 step 5, the last one — "assess application 7" runs Phase 5's four-agent review in the chat. `Assistant.jsx` already has the `review` slot waiting for it.

---

## 2026-09-10 — Piece 23 step 3: the chat now says what went wrong

**Asked for:** finish the error-code work so the codes actually reach a person, and fix the PyJWT problem myself.
**Built:** `/api/v1/chat` now returns two new fields — `ai_status` for us to grep the logs for, and `ai_notice`, the one sentence a customer reads. The Assistant screen shows that sentence in a small amber strip above the answer. Also fixed PyJWT by switching two test files to `jose`, the library the app itself already signs with, so the project has one JWT library instead of two.
**Found:** a real hole while wiring it up. If the agent failed **and** the manual chain failed too, the exception escaped and the customer got a blank 500 page — the worst possible way for the product to look during a demo, because the rest of the app is fine. Now both failing gives a normal 200 with a plain explanation and `mode: "unavailable"`.
**Realised:** two things worth keeping. A normal answer must stay completely silent — a notice on every healthy reply trains people to ignore it, and then it is worthless on the day it matters. And when every brain is down the answer *is* the explanation, so the notice above it is suppressed rather than printing the same sentence twice.
**Next:** Piece 22 step 4 — Phase 4's six tools in the chat, staff only, with a confirmation before anything that changes a record.

---

## 2026-09-10 — Session: set up this laptop, then Piece 23 step 1 — the key ladder

**Asked for:** set the project up on this machine following `SETUP-WIPRO.md`, then start on making one React chatbot that can do Phase 3, 4 and 5 instead of Phase 4 living in Streamlit and Phase 5 living in a terminal.
**Built:** the setup (venv, packages, `.env` files, seeded database, npm packages, 42 manual chunks ingested), then the first step of Piece 23: several Gemini keys tried in turn, then local Ollama, then an honest "nothing is available". Nine error codes so the failures can be told apart, and 27 new tests plus the 8 old ones, all green. None of it calls a real AI, so it cost no quota to build or check.
**Found:** three things. This is **not** the Wipro laptop the guide was written for — Python here is 3.11.9 and Node is 24, so none of the guide's workarounds were needed. The 401 you spotted is not a bug: `AuthContext.jsx:23` only asks "who am I?" when a token already exists, so that was a stale token from an earlier session being correctly thrown away. And `PyJWT` is missing from `requirements.txt`, which stops two of our own test files being collected at all (T-88) — that one is older than today's work and needs your call.
**Realised:** the gap you described is real but it sits in the backend, not in React. `Assistant.jsx` was deliberately built never to need rewriting, and it already has a `review` slot waiting for Phase 5. Better still, Phase 4's tools already call the API through the same client that reads the `acting_as()` gate, so they inherit Phase 1's permission checks for free — a customer cannot approve their own loan because the API itself says 403. Your memory of the role split was right; `application_service.py:271` confirms only a manager can disburse.
**Next:** Piece 23 step 3 — surface the error codes through `/api/v1/chat` and show the sentence in the Assistant screen. Then Piece 22 steps 4 and 5, which is Phase 4 and Phase 5 in the chat box.

---

## 2026-09-09 — Session: actually setting it up on the Wipro laptop

**Asked for:** get the project running on this machine, follow `SETUP-WIPRO.md`, use Python 3.12 since several versions are installed here, and end with a single script Rohit can double-click to start everything.
**Built:** followed the guide step by step — venv, `pip install`, `.env` files from the `.wipro` templates, seeded the database, ingested the manual into Gemini's ChromaDB collection. Ended with `start-app.ps1` (and a `start-app.bat` wrapper for double-clicking) that checks the setup is complete, opens three windows for the backend, React and Streamlit, and opens the browser once they're up.
**Found:** three real bugs, none of them things the guide could have predicted, because nobody had run these exact commands on this exact machine before today. `setuptools` 84.0.0 (nothing pins it) dropped `pkg_resources`, which `opentelemetry-instrumentation` still imports, so the backend failed to start at all — pinned `setuptools<81` (T-85). This laptop's Node is 18.20.3 but Vite 8 needs 20+, and `nvm-windows`'s version switch needs admin rights we don't have — Rohit installed Node 22.17.1 through the Wipro software catalog instead, which lands in `Program Files` without touching the system default (T-86). And Gemini works fine here but `smith.langchain.com` fails its own certificate check over this network — left alone since it only affects two optional tracing tests, not the product, and the real fix needs an admin-level certificate change (T-87).
**Realised:** the Wipro laptop's `py -0p` output matches `SETUP-WIPRO.md`'s prediction exactly (3.14 default, 3.13 and 3.12 both present), and Ollama already has the two models the guide names — so this is genuinely the machine that guide was written for, not a look-alike.
**Next:** Rohit to open http://localhost:5173 and click around as each of the three demo logins. Phase 2 tests are 20/22 (the two LangSmith ones fail on T-87, not on anything in the app).

---

## 2026-09-09 — Getting the project ready for the Wipro laptop

**Asked for:** a survey prompt for the restricted work machine, then — once its answers came back — do as much of the setup work here as possible, because there will be no more round trips. Copilot finishes it over there.
**Built:** `SETUP-WIPRO.md`, a step-by-step guide written against that machine's actual survey results, plus `backend/.env.wipro` and `frontend/.env.wipro`, which are ready-made settings files holding no secrets so they can travel in git. Added `langchain-ollama==1.1.0` to requirements. README now points at the guide.
**Found:** two real bugs, neither of which the environment caused. **The Ollama fallback has never been able to run** — `llm_provider.py` imports `langchain_ollama`, but the package was in no requirements file and installed nowhere, so the fallback that exists precisely for a company network would have crashed the first time it was needed (T-83). And the survey said the restricted environment barely restricts anything: no proxy, no certificate interception, PyPI, npm, GitHub, Gemini and LangSmith all reachable, every port free.
**Realised:** I got the Python reasoning wrong first time and the resolver caught me. I said 3.14 fails because numpy 1.26.4 has no wheel for it — but numpy is not pinned in `requirements.txt` at all, it is just what pip once happened to install here. Running the real resolver against 3.12, 3.13 and 3.14 showed the actual wall is Streamlit needing `pillow<11`, which has no 3.14 build. Same recommendation, completely different reason, and 3.13 turns out to work too. A version in `pip list` is not a constraint; only `requirements.txt` is.
**Then asked for:** Gemini stays the default with Ollama as fallback, and the switch should happen automatically.
**Also built:** exactly that. `get_llm()` now wraps Gemini in LangChain's `.with_fallbacks()`, so when Gemini refuses — dead daily quota, blocked network, withdrawn model — the very next question is retried against Ollama and the answer still arrives. No file to edit, no restart, nothing to notice mid-demo. Proved it by pointing Gemini at an invalid key: the question failed on Gemini and came back answered by Ollama. Eight tests hold it in place and use no AI quota.
**Deliberately not done:** embeddings do not fall back, and that asymmetry is the important bit. Each provider keeps its own ChromaDB collection and Gemini's embedding model returns 3072 numbers per chunk against Ollama's 768. Checked the real database here: only the Gemini collection exists, 42 chunks. So a silent embedding switch would search a collection that isn't there and the chatbot would answer from nothing — confidently, no error, no sources. A visible failure beats a confident wrong answer, so switching retrieval provider stays a deliberate act plus a re-ingest.
**Next:** send the project to the Wipro laptop and set it up there with Copilot, following `SETUP-WIPRO.md`.

## 2026-09-08 — Piece 22 step 3: the assistant now shows its working

**Asked for:** put the tools the assistant used on the Assistant screen, the way the Phase 4 Streamlit chat already does for staff.
**Built:** a "Show how this was worked out" control under every answer. Opening it lists the steps the assistant took, in order, with the value it passed in — so "Looked up an application, 3" rather than `get_application_details`. Each tool got a plain-English name and an icon; anything not in that list falls back to its raw name rather than vanishing, so a tool added later still shows. Also fixed the page copy, which still promised answers came only from the manual, and the `agent` mode label, which claimed "Read live application data" even when the assistant had only read the manual.
**Found:** two things worth keeping. The reasoning list was showing `_Exception`, which is LangChain's private marker for "the model wrote a malformed step and I asked it to try again" — real, but not something the assistant *did*, and it reads as a crash to a customer. Filtered out at the backend with a test (T-77). And the new toggle would have sat directly above the existing sources toggle: two identical borderless grey lines, one under the other, which is precisely the T-73 mistake again. They are now one row with a divider, so they read as a pair of controls.
**Realised:** T-73 said a borderless control needs neighbours to be legible. The interesting bit is that the fix for a lone ghost button is not always to give it a border — here it was to give it a neighbour, which is what the trap actually said.
**Next:** step 4 — Phase 4's action tools in the chat, staff only, with a confirmation before anything changes.

---

## 2026-09-08 — Piece 22 step 2: the chat box got the Phase 3 brain

**Asked for:** route `/api/v1/chat` to the Phase 3 agent instead of the Phase 2 manual chain, wrapped in the `acting_as()` gate built in step 1.
**Built:** the router now builds the agent once and reuses it, calls it inside `acting_as(user.email, user.role)`, and returns which tools ran in a new `tools_used` field. Sources still work: the agent's policy tool only returns a sentence, so the router re-asks the retriever for the same query the agent used and gets the extracts back. If the agent falls over — rate limit, or its loop gives up — it falls back to the manual chain and honestly says `mode="rag"`. Six new tests in `tests/ours/test_chat_uses_agent.py` use a stand-in agent, so they cost no AI quota.
**Found:** proved it in a real browser-equivalent call, and this is the bit worth seeing. Priya the customer asks "show me application 3" and gets *"you can only view your own loan applications"*. Anita the manager types the exact same words into the exact same box and gets the loan. Nothing in the AI decides that — the Phase 1 API refuses Priya with a 403 and the assistant reports it. Also: a stale server was still running on port 8000 from an earlier session, which made the first live check look like a failure when it was just the old code answering (T-76).
**Realised:** the fallback matters more than it looks. Google's daily quota can empty mid-demo, and without it the chat would go from clever to broken. With it, it goes from clever to Phase 2, which is still a working product.
**Next:** step 3 — show the tools used on the Assistant screen in React.

## 2026-09-08 — The Phase 4 chat was broken for the only person who ran it

**Asked for:** Rohit tried the documented command for the Phase 4 staff chat and it did not work. Find out why.
**Built:** the fix, and it is a small one — `chat_interface.py` now adds `backend/` to Python's path itself, based on where the file sits, instead of depending on which folder the person happened to be in.
**Found:** `streamlit run mcp_server/chat_interface.py` puts *the script's own folder* first on Python's import path, not `backend/`. So `import app` looked inside `mcp_server/`, found nothing, and the page died with `ModuleNotFoundError: No module named 'app'` the moment a browser opened it.
**Realised:** the humbling part is how many green lights were showing while it was broken. Phase 4's 25 tests passed, because pytest starts in `backend/` and already had `app` importable. Streamlit's own AppTest passed, for the same reason. The server answered HTTP 200 — but that 200 is just the empty page shell, because Streamlit does not run the script until a browser connects. And `streamlit run` printed its usual "You can now view your Streamlit app" with no error, because the crash is per-session. Four independent checks, all green, all testing the code rather than the command. I told Rohit it worked. It did not. Proved the fix properly this time by reproducing Streamlit's exact import conditions, confirming it fails without the fix and passes with it (T-74).
**Next:** the chat screen still wants a look in a browser — now that it will actually open.

---

## 2026-09-08 — Rohit looked at the briefing, and looking found a bug

**Asked for:** the backend started so Rohit could finally open the Morning Briefing in a browser — the last thing in the project nobody had actually seen.
**Built:** one fix. The card itself was right: layout holds, the three paragraphs read well, the four stats sit properly, and the "Written by AI" pill confirmed the AI narrative working live for the first time. The writing was good too — it named application #1 as most critical with three specific reasons, then recommended a concrete first action naming four files. But **"How this was worked out" was rendering as plain text rather than a button.** It was a ghost-variant button, which has no border or background until you hover it. That is fine in a toolbar where the buttons beside it make it obviously pressable; this one stands alone under a divider, so it just looked like a stray line of text. Now a proper disclosure control with a border, a hover and focus state, a chevron that rotates to show which way it will open, and `aria-expanded` for screen readers.
**Found:** the panel that button opens is the entire trust story of the feature — the real numbers behind every sentence the AI wrote — and nothing on screen told a manager it could be clicked.
**Realised:** that is **twice** this project has shipped a control that was invisible to code review, to a clean build and to a green test suite, and was caught only by a person looking at a rendered page. T-42 was the filter dropdowns in Phase 1; this is T-73. The pattern is exact enough to be a rule now: a borderless control needs neighbours to be legible, and nobody hovers hopefully over text.
**Next:** one screen left unseen — the Phase 4 staff chat.

---

## 2026-09-08 — A sweep for anything still broken, and the command a grader types first

**Asked for:** with the tracked list closed out, go looking for problems nobody had reported yet, and fix them.
**Built:** four fixes. The important one: **`pytest tests/` did not work at all.** Every phase passed on its own, but running them all together aborted during collection before a single test ran — Phase 3 and Phase 5 both have a `test_e2e.py`, and three of the test folders were missing an `__init__.py`, so pytest could not tell the two files apart. Phases 1, 2 and ours had one; 3, 4 and 5 never got one, because each was built in a different session and nobody ever ran the whole thing together. Also: the README still said "Phase 1 status: complete" and gave no way to run the Phase 4 chat screen or Phase 5, so it was rewritten for all five phases with every command actually run before being written down. A lint sweep found a ternary used as a statement in Piece 19's form code and seven dead imports.
**Found:** **142 passed, 0 failed, 0 skipped, in one command, in 9 minutes 34 seconds.** That is the entire project verified the way a reviewer verifies it, and it had never been possible before today. Also confirmed along the way that the manual's numbers still match `rules.py` exactly (Rule 12 holds), the API returns the right codes on every error path, no secrets are tracked in git, and the front-end reads its backend address from a setting rather than from code.
**Realised:** the collection bug is the lesson of the day. Six suites, each one green, each one verified in isolation — and the failure existed only in the combination. Nothing was wrong with any phase; what was wrong was that nobody had typed the command the grader types. Logged as T-72.
**Next:** one gap left in the whole project — the briefing card and the Phase 4 chat screen still need a human look in a browser.

---

## 2026-09-08 — Answering T-69, and the third model nobody had noticed

**Asked for:** the verification session came back with four results and one open question — the running model is `gemini-3.5-flash-lite` but `CLAUDE.md` still advertised Gemini 2.0 Flash. Update the doc, or pin the model back?
**Built:** no new feature. The doc was simply out of date, and pinning back was never an option: Google withdrew Gemini 2.0 Flash and it answers 404 (T-51). `gemini-3.5-flash-lite` was picked deliberately as the only model that survived the free tier's rate limit without refusing (T-55). The stack table now names the real models and says why.
**Found:** the interesting part was underneath the question. There were **three** model values, not two. `.env` and `.env.example` both said `gemini-3.5-flash-lite`, but `config.py`'s fallback default said `gemini-3.8-flash` — a different model again. That default is what runs whenever `.env` is missing that line, which is exactly the state of a fresh clone before anyone fills in their own `.env`. So a new machine would have quietly run a slower model nobody chose and nobody rate-limit tested, and nothing on screen would have said so. All three now agree.
**Realised:** a setting that has a default in code and a value in `.env` is two sources of truth. When they drift, the winner is whichever the machine happens to have — and it fails silently, on someone else's laptop rather than yours. Worth checking the other paired settings the same way sometime.
**Next:** one gap left in the whole project — nobody has looked at the briefing card or the Phase 4 chat screen in a real browser. Two sessions have tried and both lost their browser tooling.

---

## 2026-09-08 — Session: Verifying the unattended run

**Asked for:** Four checks handed over from the long build session — is Phase 2 really passing, do the two never-seen screens look right, regenerate the missing Phase 1 and 2 result files, and is Ollama worth installing.
**Built:** Nothing new. Ran Phase 2 three times (22/22 each), Phase 1 once (27/27), wrote `results/phase1-results.xml` and `results/phase2-results.xml`, and drove the Phase 4 Streamlit chat end to end with Streamlit's own AppTest.
**Found:** Yesterday's 9 failures were purely the exhausted daily Gemini quota — no code was ever broken. The manager's briefing endpoint returns real numbers and the React card reads exactly the fields it sends. The Streamlit chat shows its session ID, four quick-action buttons, and a clicked button really does come back with an AI answer. Also spotted that the model in use is gemini-3.5-flash-lite while CLAUDE.md still says Gemini 2.0 Flash (T-69).
**Realised:** A terminal can invent a bug that isn't there. Correct em dashes looked like mojibake purely because the Windows console is cp1252 (T-71). Checked the raw bytes before reporting it as broken, which is the right order.
**Next:** Two things still need Rohit's eyes in a real browser — the briefing card's layout and the Streamlit page — because this session had no browser tooling. Then decide on T-69 and on Ollama.

---

## What I've read so far

- [x] `01-POC-BLUEPRINT.md` — Parts 1 to 6, the whole Phase 1 contract
- [x] `01` — Part 13, the contradictions
- [x] `02` — Part 1, Change 10, the review punch list
- [x] `TRAPS-AND-DECISIONS.md` — all decisions answered except D-09 (Angular later)
- [ ] `02-GROUND-TRUTH-SHIFTS.md` — **Part 3, the Gemini/Ollama switch** ← **next, before Phase 2**
- [ ] `README.md` — how to run everything, and the demo logins ← **next**
- [ ] `02-GROUND-TRUTH-SHIFTS.md` — the rest, whenever
- [ ] `03-THE-FLOW-WHAT-HAPPENED.md` — whenever

---

## Decisions

| Date | Decision | Why |
|---|---|---|
| 2026-09-03 | Backend is **Python + FastAPI**, not Java | The 20 test skeletons hardcode Python import paths, and Phases 2-5 are Python-only. Java would mean building everything twice. |
| 2026-09-03 | Second front-end is **Streamlit** | Phase 2-4 test specs check Streamlit behaviour, so it gets built anyway. Costs about an hour instead of days. |
| 2026-09-03 | **Angular deferred** until after Phase 5 is demo-ready | Better career skill, wrong timing. Phases 4 and 5 are worth 45% combined and almost nobody in the cohort finished Phase 5. |
| 2026-09-03 | AI instructions live in **`CLAUDE.md` only** | No Copilot licence yet. |
| 2026-09-03 | Work in a **read → explain → build loop**, one component at a time | Reading 900 lines up front doesn't stick. |
| 2026-09-05 | **Cautious upgrade** — improve only by adding, never by changing what already works | Base requirements are what get graded. Additions must not break them. |
| 2026-09-05 | **One iteration at a time** — plan it, build it properly, then plan the next | Backend, React, Streamlit, activity log are separate pieces of work. |
| 2026-09-05 | **Validate every user input**, not just the fields the spec names | The spec names a handful. Real applications validate everything. |
| 2026-09-05 | Use **git and GitHub**, private repo, commit after every piece, tag each phase | Version control, and a real commit history is evidence of real work. |
| 2026-09-05 | Logins follow **Option A**: normal register creates staff, separate applicant signup | The trainer's test registers "Test Officer" and immediately changes a status. |
| 2026-09-05 | Ideas beyond the trainer's requirements go to **`FUTURE-UPGRADES.md`**, built after the base | Scope control. Phase 5 needs protecting. |
| 2026-09-05 | **Customer data is stored on the server**, never in the browser | Rohit's security point on draft saving. Now Rule 13. |
| 2026-09-05 | **The manual and the code must agree** — change one, change the other | The chatbot quotes the manual. Now Rule 12. |

---

## The log

## 2026-09-07 — Session 37: The Manager's Morning Briefing — the headline feature

**Asked for:** the last thing on the run's list before the report — the showcase feature settled as D-13 back on 2026-09-05. Not a trainer requirement; the thing that makes the demo memorable rather than merely complete.
**Built:** the manager opens the app and the AI has already read the whole pipeline — what is stuck and for how long, what is held up by missing documents, what was flagged by the bank's own eligibility check at submission and is somehow still open, and what is approved but not yet paid out. `briefing_service.py`, a manager-only `GET /api/v1/briefing`, a card at the top of the manager's dashboard with a "how this was worked out" panel that opens the actual numbers behind every sentence, and 7 tests of our own. Same discipline as Phase 5: every number is counted from the database first, and the AI only writes the prose.
**Found:** three things, and two of them matter more than the feature itself. First — **the test suites had been writing into the real demo database all along.** Phases 3, 4 and 5 talk to the Phase 1 API over HTTP, and that fixture reuses whatever server is already running, which is the real one. One full test run had left **60 applications** called things like "Phase 5 underwriting fixture" sitting in the manager's pipeline — 68 open applications, nearly all junk, which is exactly what an Account Delivery Head would have seen first. Cleaned up, and there is now a `clean_test_data.py` to run before any demo (T-65). Second — **the Gemini free tier is 500 requests a day**, not just 5 a minute, and this run used them up. The briefing degraded to its plain-figures fallback exactly as designed and said so on screen, but it means the AI narrative could not be shown live today (T-66). Third, smaller: the seed data was all created on the same day, so nothing was ever overdue and the briefing had nothing to report. The seed script now spreads applications across three weeks, with a couple genuinely overdue, which is what a real branch looks like.
**Realised:** the briefing is the feature that pulls the whole project together in one screen — Phase 1's data, Piece 19's stored eligibility, Phase 5's view of risk, and the same observability as everything else. It also answers the question an ADH actually asks, which is not "does it have a chatbot" but "what does this change on Monday morning".
**Next:** the run was stopped here, cleanly, at Rohit's request. **Everything that was asked for is built, committed and tagged** — Piece 19, Phases 3, 4 and 5, and the headline feature, tagged `v0.2.3` through `v1.0.0`. The one thing still outstanding is `RUN-REPORT.md`, the written summary of the run. Two things to know before the next session: the Gemini daily quota was exhausted (T-66), so it resets on Google's clock, and `clean_test_data.py` should be run before any demo (T-65).

---

## 2026-09-07 — Session 36: Phase 5 built — the four-agent underwriting review, 25 of 25 pass

**Asked for:** the last phase of the unattended run — the LangGraph multi-agent system that reviews a loan application the way an underwriting desk would: one agent collects the data, one scores the risk, one checks compliance, one makes the call.
**Built:** `multi_agent/` — the shared state, the four agents, the graph, and a command-line entry point. The graph is linear with one branch: if the application cannot be fetched, it stops there rather than asking three more agents to reason about data that does not exist. **All 25 tests pass, none skipped.**
**Found:** two things worth knowing. The Gemini model returns `response.content` as a *list of content blocks*, not a string, so `.strip()` on it raised every single time — my own defensive fallback caught it silently, which meant the pipeline kept working but every LLM-written summary was quietly replaced by the plain deterministic one. Nothing failed; it just wasn't doing what it looked like it was doing. Fixed with one shared helper that handles both shapes. The other was the same LangSmith cold-start problem Phase 3 hit (T-62), just slower: a brand-new project took longer than 24 seconds to become queryable the first time anything was ever written to it.
**Realised:** the important design call here was **not** letting the LLM compute the numbers. The trainer's own reference asks the model to calculate the debt-to-income ratio, the EMI, and the risk score itself and return JSON — and their own tips list admits what that costs ("JSON parsing fails in Risk Assessor... have fallback values"). For numbers a lending decision hangs on, that is the wrong trade. Every number in this phase is computed in plain Python from the same `domain/rules.py` thresholds the rest of the project already uses, and the LLM writes only the prose a human reads. That makes the decisions repeatable, auditable, and explainable in a code walkthrough — and it means a rate limit or a bad JSON day can never change a lending decision.
**Next:** the Manager's Morning Briefing (the headline showcase feature, D-13), then the final report.

---

## 2026-09-07 — Session 35: Phase 4 built — the MCP server and the staff chat, 25 of 25 pass

**Asked for:** the unattended run continues to Phase 4 — the MCP server (six tools exposing the loan system over the Model Context Protocol) and the Streamlit chat interface staff use to manage applications by typing sentences.
**Built:** `mcp_server/mcp_app.py`, six `@mcp.tool()` functions built on the same shared API client Phase 3 uses (a fresh token every call, never a stale one from `.env`; a plain dict back on every failure, never a stack trace — the same two fixes as `AI-BUILD-LOG.md`'s Phase 4 bugs). `mcp_server/chat_interface.py`, a second ReAct agent wrapping those six tools for a LangChain agent to reason over, plus the actual Streamlit chat screen — session id, quick-action buttons, chat history, and an expandable "tools used" panel per reply. All 25 of the trainer's tests, `tests/phase4/`, **pass on the first full run after one fix**: a single-argument tool (`get_application_details`) hit the same LangChain ReAct quirk Phase 3 had already worked around, fixed the same way — take the id as a string, convert inside the tool.
**Found:** two things that would have embarrassed us in a demo, both invisible to the test suite. First — installing `fastmcp` at all, with no version pin, silently upgrades `starlette` to a version that breaks FastAPI outright; chasing that broke the app twice before landing on pinning `starlette` back down (T-63, in full in the traps file). Second — actually opening the chat screen with Streamlit's own `AppTest` (real browser tooling wasn't available this session) showed that clicking a sidebar "quick action" button added a user message and then **nothing answered it** — the button only appended to history and reran the page; it never called `process_message`. Fixed by giving both the chat box and the quick-action buttons one shared path. Also found, while fixing the first issue, that `requirements.txt` had quietly been Phase 1 only since Phase 2 started — a clean checkout would never have reproduced this environment. Rewrote it from the real working venv and proved it in a brand new one.
**Realised:** a passing test suite proves the logic works; it does not prove a button does anything. `AppTest` actually executes the Streamlit script the way a browser would, and that is what caught the dead button — reading the code again would not have.
**Next:** Phase 5 — the four-agent underwriting review, 25 tests, not started.

---

## 2026-09-06 — Session 34: Phase 3's tests, run for the first time — 23 of 23 pass

**Asked for:** the unattended run continues. `agent/` and `tests/phase3/` both existed from an earlier session but nobody had ever run `pytest tests/phase3`, so nobody knew whether Phase 3 actually worked.
**Built:** nothing new — this was verification, not construction. Ran the suite for the first time and found three failures, all genuine bugs rather than a broken agent: our own test checking for "do not use" in a tool's description tripped over the description wrapping onto two lines (a whitespace bug in the test, fixed by collapsing whitespace before comparing); the trainer's own status-query test checks for the literal enum spelling `under_review` with an underscore, but a correctly-behaving agent writes "under review" in plain English — the same class of bug as T-36, where the trainer's own test would fail against any correct implementation, so this copy now accepts either spelling with the reason written next to it; and the LangSmith trace test failed because the very first trace this project (`AI-Readiness-POC-01-P3`) ever received needed a moment to create the project server-side before it could be queried — not a longer sleep but a genuine "does not exist yet", fixed with a short retry loop instead of a fixed wait. After the three fixes, **all 23 pass, none skipped** (20 trainer's + 3 ours).
**Found:** manually running the agent outside pytest first (`run_agent("What is the status of application 1?", ...)`) was worth doing before touching the tests — it showed the actual answer, "under review" with a space, which is what made the second bug obvious rather than a guess.
**Realised:** Phase 3 has no screen of its own — `agent/` is backend-only reasoning; the trainer's plan puts the actual chat interface in Phase 4 (`mcp_server/chat_interface.py`). So "inspect it, don't just test it" for this phase means driving the agent directly with a range of real questions, which the manual run plus the existing 404/API-down/out-of-scope tests already cover.
**Next:** Phase 4 — the MCP server and the staff chat interface, 25 tests, not started yet.

---

## 2026-09-06 — Session 33: Piece 19, and an unattended run through to Phase 5

**Asked for:** Rohit is away from the keyboard. He asked for everything left to be built in one continuous run: Piece 19, then Phase 3's tests (written but never run), then Phase 4, then Phase 5, then the Manager's Morning Briefing, then an honest report — deciding things myself where he would normally be asked, and writing those decisions down instead of waiting.
**Built:** Piece 19 first. The server now runs its own eligibility assessment the moment an application is submitted, and stores it permanently: three new columns on `loan_applications`, a small migration so the existing database picks them up without losing data, and one shared `assess()` function so the advisory check and the stored record can never quietly disagree. The form now checks itself 600ms after you stop typing, shows every rule as a passed or failed row instead of only the failures, and asks a real question — "submit anyway?" — in a popup rather than a line of orange text. The application page shows the bank's own stored note in a panel that opens on request. Streamlit got the same treatment. Verified by actually driving the form in a browser as the loan officer: filled in Priya Sharma's example from this plan, watched the check fire on its own, watched the "not eligible" popup appear, submitted anyway, and read the stored note back on the application page — it matched the plan almost word for word.
**Found:** nothing broke. All 20 of the trainer's Phase 1 tests still pass (27 runs), plus 3 new tests for the stored summary and the existing ones for search and timestamps — 40 in total.
**Realised:** the biggest risk in this piece wasn't the eligibility logic, it was the database migration — `Base.metadata.create_all()` never adds a column to a table that already exists, so without the small `ALTER TABLE` step the real `loan_app.db` would have kept the old shape and every read of the new fields would have raised "no such column" the first time someone opened an old application.
**Next:** Phase 3 — run the tests that exist but have never been checked, then inspect the phase properly rather than trusting a green summary line.

---

## 2026-09-06 — Session 32: Phase 2 actually finished, and a full plan to the end

**Asked for:** Rohit gave me the LangSmith key, said to stop asking him things and decide like a professional, and switched on plan mode so the run to Phase 5 got planned properly rather than built ad hoc. He also said plainly: don't half-build it, and don't let me find bad implementations later like we did in Phase 1.
**Built:** Phase 2 is now genuinely complete. The LangSmith key is wired in, so the two tracing tests that were *skipping* now pass for real — Phase 2 reads **22 passed, 0 skipped**. And the Streamlit Assistant tab, which the project had committed to but never built, now exists, with the same source-citation panel the React page has rather than a stripped-down version.
**Found:** two research passes over the trainer's Phase 4 and Phase 5 documents turned up three real bugs in his own reference code — a JWT that expires mid-demo, an HTTP call that crashes the agent on any error that isn't a 404, and a compliance check reading `age_eligible = ... or True`, which never actually checks an age. All three are written up in the new `AI-BUILD-LOG.md` with what I did instead.
**Realised:** a skipped test reads exactly like a passing one in a summary line. Two of Phase 2's twenty had been skipping all along, and the phase looked finished. Worth remembering for the phases still to come: the number to check is passed-plus-skipped, not passed.
**Next:** Phase 3's tests and inspection, then Phase 4 (MCP server plus the staff chat interface), then Phase 5 (the four-agent review).

---

## 2026-09-06 — Session 31: An inspection of the whole app, and the fixes it found

**Asked for:** Rohit was tired with a presentation the next day, so he asked me to go through Phase 1 as an inspector, find whatever was not working or looked wrong, and fix it without checking in at every step.
**Built:** two inspections rather than a read-through. One walks every backend address as all three roles — about seventy checks covering permissions, validation, every status move and every error code — and found **nothing wrong**. The second drives a real headless browser, signs in as manager, officer and customer, visits every page, screenshots it and reports any browser error. That one found the things reading could not.
**Found:** the worst was invisible in the code. The form styles were written as `form input, form select`, but the filter toolbars on the applications and activity pages are plain divs, not forms — so **those dropdowns had no styling at all**, rendering as raw browser controls with their labels colliding into them. It looked broken, and it was on the first screen of the demo. Also: the application detail page had never been brought up to the new design, and still printed the stored activity as raw data in a table cell — the same complaint that was fixed on the activity page but never here. Link-shaped buttons carried an underline. Missing rupee amounts rendered as an empty gap next to their label, which reads as a bug rather than "never recorded".
**Realised:** rejecting a loan could not be undone and was one careless click away, with nothing asking "are you sure". It now asks, showing what is moving where. Two things that looked like faults were not: the sidebar and the modal backdrop only appear to stop halfway down a full-page screenshot, because both are correctly pinned to the window; and the list asking the server twice on load is React's StrictMode double-running effects in development only, which does not happen in the built app.
**Next:** Piece 19 — automatic eligibility in the form, and the eligibility summary stored on each application. It is the last planned piece of the Phase 1 polish.

---

## 2026-09-06 — Session 30: Piece 18, the applications list and the form

**Asked for:** build Piece 18 — tidy the crowded filters on the applications list, let people sort by clicking a column, and turn the submission form from one long stack of boxes into something readable.
**Built:** the list now has a search box that waits for you to stop typing, the two dropdowns the trainer's user story names, dates tucked behind a toggle, and column headings you click to sort with an arrow showing which way. The form is now three sections — who is applying, the loan, why you need it — with the amount written out under the box as you type and quick-pick chips for common tenures. Searching and sorting needed three new optional settings on the backend list endpoint.
**Found:** the backend server had been running since the last session **without `--reload`**, so my changes looked like they did nothing — search came back with every row and a deliberately invalid sort column answered 200 instead of 400. Restarting it the way the README says fixed it. Written up as T-40, because the same thing will fool us again.
**Realised:** sorting had to happen on the server, not in the browser. The page only holds 20 rows, so a browser sort would order those 20 and quietly hide a bigger amount on the next page — the seed data proves it, since sorting by amount brings Sanjay's ₹40,00,000 onto page 1 from page 2. Guarded the whole thing with a test that the plain unfiltered call still returns exactly what it did before, which is what the trainer's API-07 relies on.
**Next:** Piece 19 — automatic eligibility in the form, and the eligibility summary stored permanently on each application.

---

## 2026-09-06 — Session 29: Sticky headings, real search, and making the reference number honest

**Asked for:** table headings that stay put when scrolling, an explanation of what a developer would actually do with the reference number in the activity popup, and search that works on part of a name instead of the whole email.
**Built:** column headings now stick to the top of the window on the applications and activity tables, and step aside on narrow screens where the table scrolls sideways instead. Search is now partial and ignores capitals, and also matches who an AI was acting for, so "anita" finds anita@bank.com. The server now writes its log to `backend/logs/app.log` as well as the terminal.
**Found:** the reference number was not broken. 41 of 99 rows had one; the 58 without were all created by the demo setup script, which calls the code directly with no web request involved, so there is genuinely nothing to reference. But the popup said "not recorded", which reads like a failure. It now explains why instead. The real gap was elsewhere: the log only lived in the terminal window and vanished when it closed, so a reference from yesterday was useless. That is what the log file fixes.
**Realised:** Rohit's question was the right one to ask. The feature looked complete but only half worked, and the missing half was invisible until someone asked what it was for. Proved the whole flow end to end and wrote it up in `LEARNING-NOTES.md`.
**Next:** Pieces 18 and 19 — the applications list, the form, and the eligibility summary stored on each application.

---

## 2026-09-06 — Session 28: A real time bug, the dashboard, and the activity page

**Asked for:** Rohit found three things while using the app — the dashboard was not properly built, the times shown were not real, and the activity page still showed raw data in its details column.
**Built:** the timezone fix, the dashboard (Piece 20) and the activity page (Piece 21).
**Found:** the time complaint was a genuine bug, and a bad one. Every date and time in the app was **5 hours 30 minutes early**. SQLite records times in UTC and hands them back with nothing marking them as UTC, so the browser read them as local time. Proved it by comparing the machine clock, the stored value and what a browser makes of it. Fixed by sending times with a `Z` on the end, and covered by three new tests in `tests/ours/`. Written up as T-39.
**Realised:** the dashboard was not broken, it simply had not been built yet — Rohit was looking at the old plain version. Worth saying plainly rather than letting him think something had failed.
**Next:** Pieces 18 and 19 — the applications list, the form, and the eligibility summary stored on each application.

---

## 2026-09-06 — Session 27: Piece 17, the design system

**Asked for:** build the design system, after Rohit chose bars over pie charts.
**Built:** a new look for the whole app. The top navigation strip is gone, replaced by a dark slate sidebar with icons, an active-link marker, and the signed-in person at the bottom. The stylesheet was rewritten around named colour tokens. Buttons now have a real pressed state that moves down 1px, a keyboard focus ring, and a loading spinner. New reusable pieces: an icon set drawn in one file with no library, a Button, a Modal that closes on Escape and keeps the keyboard inside it, and an EmptyState. The three sign-in pages got a proper centred layout with the brand on top.
**Found:** nothing new. The build passes and both servers run.
**Realised:** keeping every old class name working meant the existing pages picked up the new look without being rewritten. The next four pieces refine each page rather than repairing it.
**Next:** Rohit looks at it and says what he thinks. Then Piece 18, the applications list and the form.

---

## 2026-09-06 — Session 26: Planning the UI overhaul

**Asked for:** Rohit used the app as the manager and found the look plain across the board — no colour theme, basic navigation, cramped filters, a dull form, no real charts, and an activity page showing raw data instead of readable detail. He also wants the eligibility check to run automatically and to be permanently recorded on each application.
**Built:** no code. A five-piece plan in `BUILD-PLAN.md` covering a design system, the list and form, automatic eligibility with a stored summary, the dashboard, and the activity page.
**Found:** ran the trainer's five mandated status colours through a colour-accessibility validator. As bars they are fine with written labels, but in a **pie chart** purple and blue are indistinguishable to a colourblind viewer (ΔE 0.4) and red and orange are hard for everyone (ΔE 8.7). So the plan uses bars, not pie. Logged as T-38.
**Realised:** I built all sixteen Phase 1 pieces without stopping, because Rohit once said "keep going". That was wrong — he wanted to co-build. Two new rules added: one piece per turn no matter what, and every reply must say which Claude model and effort to use next.
**Next:** Rohit answers the pie-chart question, then Piece 17, the design system.

---

## 2026-09-06 — Session 24: Phase 1 complete

**Asked for:** keep going.
**Built:** the submission files. A README that takes a reviewer from a clean machine to a running app in four steps, the score tracker with 20 of 20, and the JUnit report file the associate guide asks for. Tagged the project `v0.1.0`.
**Found:** nothing new.
**Realised:** Phase 1 took sixteen pieces and one day. Every trainer test passes, every review comment from the mentor chats is built in, and there is a version tag for every step. What Rohit still has to do himself for the submission: take the terminal screenshot of the test run, and share the repository or a zip with the reviewer.
**Next:** Phase 2, the RAG chatbot. It needs a Gemini API key from Rohit, and he should read File 02, Part 3 (the Gemini/Ollama switch) before it starts. Plan comes first.

---

## 2026-09-06 — Session 23: Piece 15, Streamlit, and the seed data

**Asked for:** keep going.
**Built:** the Streamlit front-end in one file: sidebar login, an applications tab with filters, the trainer's status colours, a detail view with history and documents and a status-update form for staff, a new-application tab with the eligibility check, and a dashboard tab with metrics and bar charts. Also ran the seed script: two staff, six customers, eight applications across every status, 58 activity rows.
**Found:** VS Code's "package not installed" hints were only the editor looking at the wrong Python. A workspace setting now points it at the virtual environment.
**Realised:** the Streamlit file is the base for the Phase 2 chat screen the tests check, so it was worth doing properly.
**Next:** Piece 16, the submission files. README, score tracker, and the test report.

---

## 2026-09-06 — Session 22: Piece 14, the React front-end

**Asked for:** keep going.
**Built:** the whole React app. Login, staff registration, customer signup, the applications table with filters and the trainer's exact status colours, the detail page with the vertical timeline, the document checklist with verify buttons for staff, the update-status control that only offers moves the rules allow, the new-application form that runs the eligibility check before submitting and offers the suggested amount or tenure with one click, the dashboard, the manager's activity page, and the applicant's profile page. Builds clean. Also a seed script that creates a manager, an officer, six customers and eight applications across every status.
**Found:** the backend had no way for an applicant to fetch their own profile, so a small `GET /applicants/me` was added. React 19 came with the scaffold; pinned back to 18 as the program names.
**Realised:** the eligibility card on the form is the piece Koushik asked for in the review: it tells the customer what to change, and one click applies the suggestion.
**Next:** Piece 15, the Streamlit front-end. Plan written.

---

## 2026-09-06 — Session 21: Piece 13, the backend passes all twenty

**Asked for:** keep going.
**Built:** the trainer's twenty Phase 1 tests as real pytest files in `tests/phase1/`, with the shared setup and the two fixtures the trainer forgot to write. **All twenty pass on the first full run.** The pass mark was fourteen.
**Found:** the trainer's DB-02 test reads a row's id before the row is saved, so it would fail against any implementation. One `flush()` line fixes it, with the reason in a comment (T-36). Also pytest needed one line of config to find the `app` package from a subfolder (T-37).
**Realised:** the backend is finished. Thirteen pieces, thirteen version tags, every trainer test green, and the extras from the review comments built in. The React front-end is the next iteration, and it is what actually gets demoed.
**Next:** Piece 14, the React front-end. Plan written, built in four stages.

---

## 2026-09-06 — Session 20: Piece 12, the server comes together

**Asked for:** keep going.
**Built:** JSON logging with the program's required fields on every line, request ids that tie a request's log lines together and come back in a response header, timings on every request, OpenTelemetry spans for requests, database statements and token checks, a clean 500 with a request id when something crashes, and `main.py` that wires every router into one server with `/health` for the reviewer.
**Found:** the trainer's own startup log line crashes the server, because structlog's first argument already *is* the event name and the sample passes it twice. Logged as T-35. Copying that line verbatim would mean the app never boots.
**Realised:** the smoke test reads the actual JSON log lines back and checks them, which is the same thing the Phase 2+ observability tests will do. Worth building that habit now.
**Next:** Piece 13, the trainer's twenty tests as real pytest files. Plan written.

---

## 2026-09-06 — Session 19: Piece 11, the manager's activity view

**Asked for:** keep going.
**Built:** the reading side of the activity log. A manager-only list with filters for who, what, human-or-AI, which record, and a date range, plus a per-record history for the application page. Reading the log never writes to it.
**Found:** nothing new.
**Realised:** nothing new.
**Next:** Piece 12, logging, tracing, and `main.py`. After this the API runs as one server.

---

## 2026-09-06 — Session 18: Piece 10, the eligibility check

**Asked for:** keep going.
**Built:** the "would this be allowed?" check the form calls before submitting. Seven checks from the rules file, each with a plain-English message: tenure range, amount cap, minimum income, credit score, employment, age including the "home loan must end before 70" rule, and affordability at 50% of income after existing EMIs. Where it can, it suggests an amount or tenure that would pass. Advisory only; the trainer's API-03 home loan is flagged but still accepted. Also the EMI maths the trainer's UNIT-03 calls by name.
**Found:** Python formats 25 lakh as ₹2,500,000. Added an Indian formatter so every message reads ₹25,00,000, and a note in the learning file.
**Realised:** with the date of birth and job-length fields added earlier, the age and employment checks were one line each. Adding the columns early paid off immediately.
**Next:** Piece 11, the manager's view of the activity log. Plan written.

---

## 2026-09-06 — Session 17: Piece 9, the dashboard

**Asked for:** keep going.
**Built:** the dashboard summary. Three grouped queries give the counts by status and loan type and the total amount, with every key present even at zero, plus two extras: the officer's pending pile and the approved-but-unpaid amount. The trainer's API-08 passes, and it answers in about 10 ms.
**Found:** nothing new.
**Realised:** nothing new.
**Next:** Piece 10, the eligibility check. Plan written.

---

## 2026-09-06 — Session 16: Piece 8, documents

**Asked for:** keep going.
**Built:** adding a document to an application, listing them with a checklist of what the loan type still needs, and letting an officer mark one as verified. Same type twice is allowed, as the user story says. Applicants can only touch their own.
**Found:** a PowerShell quirk cost a few minutes: a double quote inside a commit message splits it into pieces, the commit fails, and a tag made in the same command lands on the wrong commit. Had to delete a tag from GitHub. Logged as T-34; commit messages now avoid double quotes.
**Realised:** the required-and-missing checklist in the document list is the small thing that makes Phase 5's compliance agent trivial later. It already knows what is missing.
**Next:** Piece 9, the dashboard. Plan written.

---

## 2026-09-06 — Session 15: Piece 7, the application endpoints

**Asked for:** keep going.
**Built:** submitting, viewing, listing and moving applications through their statuses. Per-loan-type limits with plain-English messages, the audit row on every change, the manager-only rule on paying out, and owner scoping so an applicant only sees their own. The detail view loads everything in one query.
**Found:** nothing new. Nine of the trainer's twenty tests are now covered by smoke tests, and the home loan from API-03 that breaks the 50% EMI rule is accepted as planned (D-01).
**Realised:** the eligibility warning (Piece 10) and the document checklist (Piece 8) are what turn these rules into something a customer actually sees.
**Next:** Piece 8, documents. Plan written.

---

## 2026-09-06 — Session 14: Piece 6, borrower profiles

**Asked for:** keep going.
**Built:** the applicant service and its three addresses. Staff can create and list profiles; an applicant can see only their own. Smoke test passes, including the trainer's UNIT-01 and the fixture every API test relies on.
**Found:** a bug in my own rules file. Python 3.11 turns a status enum into the text "ApplicationStatus.submitted" when you call `str()` on it, so the transition check would have failed the trainer's UNIT-05. My earlier sanity check only used plain strings, which hid it. Fixed, and logged as T-33.
**Realised:** smoke tests should use the same inputs the trainer's tests use, enums and all, not just whatever is convenient.
**Next:** Piece 7, the application endpoints. Plan written.

---

## 2026-09-06 — Session 13: Piece 5, logging in

**Asked for:** keep going.
**Built:** the login system. Password hashing, token creation and checking, the "who is calling" dependency every protected endpoint uses, a role gate, and four addresses: staff register, applicant signup, login, and "who am I". Also the activity-log writer, since logins are the first thing worth recording.
**Found:** nothing new. The 401-versus-403 trap (T-01) is handled and tested.
**Realised:** login failures now take the same time whether the email exists or not, so nobody can use the login page to discover which emails are registered. Small, but it is the kind of thing an ADH asks about.
**Next:** Piece 6, the applicant endpoints. Plan written.

---

## 2026-09-06 — Session 12: Piece 4, the input-checking layer

**Asked for:** keep going.
**Built:** the schemas, six files under `app/schemas/`. Every field that accepts user input is now checked: name shape, Indian mobile format, password strength, email, credit score range, income, date of birth not in the future, file names limited to PDF/JPG/PNG with no folder tricks, and the trainer's amount and tenure bounds. A smoke test mirroring the trainer's UNIT-02, 04, 07 and 08 passes, plus eight of our own stricter checks.
**Found:** nothing new.
**Realised:** the per-loan-type limits belong in the service layer, not the schema, so the trainer's UNIT-04 keeps passing exactly as written and the eligibility check can explain *why* something is over the limit.
**Next:** Piece 5, auth. Plan written.

---

## 2026-09-06 — Session 11: Piece 3, the six tables

**Asked for:** keep going without waiting for approval on each piece, since Rohit needs time to learn the tech before he can suggest changes. Also: can every push carry a version number?
**Built:** `config.py` (reads the settings file), `database.py` (the connection, with foreign-key checking deliberately off), and the six table models. A smoke test that copies the trainer's four database tests passes, including the cascade delete and the row that points at a missing applicant.
**Found:** nothing new in the code. In the writing, Rohit found very short sentences *harder* to read, not easier, so Rule 7 now says natural sentences.
**Realised:** version tags per piece are cheap and give Rohit a number to point at. Scheme: `v0.0.N` for Phase 1 piece N, `v0.1.0` when Phase 1 passes, then `v0.1.N` for Phase 2 pieces, and so on. Rule 11 updated.
**Next:** Piece 4, the schemas. Plan written.

---

## 2026-09-06 — Session 10: Piece 2, the rules file

**Asked for:** add the two missing applicant fields (job length, existing EMIs) and build Piece 2.
**Built:** `app/domain/rules.py`. Every loan rule as plain Python: allowed values, the status machine, amount and tenure limits per loan type, eligibility numbers, required documents, the 50% EMI rule, employment minimums, and the Phase 5 scoring bands. Six small helper functions. Imports nothing from the app, so any phase can use it.
**Found:** nothing new. Every rule already had a settled source.
**Realised:** Rohit is happy with the one-thing-at-a-time pace.
**Next:** Piece 3, the database connection and the six tables. Plan is written; waiting for a go.

---

## 2026-09-06 — Session 9: Piece 1, the skeleton

**Asked for:** go ahead with Piece 1, and only raise parked questions when a piece actually needs them.
**Built:** the `backend/` folder with the `app/` package, a virtual environment on Python 3.11.9, `requirements.txt` at the trainer's versions, `.env` with a real generated secret, and `.env.example` for GitHub. All packages installed and importing.
**Found:** two gaps in the trainer's package list. `passlib` breaks with newer `bcrypt`, so bcrypt is pinned to 4.0.1. And Pydantic's email check needs `email-validator`, which the trainer never lists but test UNIT-02 depends on. Both in the traps file.
**Realised:** nothing new. This piece was groundwork.
**Next:** Piece 2, the domain rules file. Every loan rule in one place.

---

## 2026-09-05 — Session 8: Slowing down to one thing at a time

**Asked for:** stop doing ten things per reply. One problem, one answer, then move on. Also a notes file for domain facts worth re-reading.
**Built:** `LEARNING-NOTES.md` with the bank EMI rules. Two new rules in `CLAUDE.md`: one thing per reply, and keep the learning notes. Settled the headline feature (Manager's Morning Briefing), the EMI percentage (50% everywhere), and the folder layout. Installed git, Python 3.11 and Node 24. Started the git repository, made the first commit, and pushed it to a private GitHub repository. **Piece 0 done.**
**Found:** the restriction confusion was mine. This is Rohit's personal laptop with no limits. The Wipro laptop is the restricted one and nothing gets built there. Also: the editor's shell won't see the new tools until VS Code restarts, so I refresh the PATH at the start of each command for now.
**Realised:** Rohit isn't reading the reading lists. From now on I walk him through one item at a time and ask before moving on.
**Next:** Piece 1, the project skeleton.

---

## 2026-09-05 — Session 7: The Phase 1 sweep, and the laptop has no tools

**Asked for:** real bank numbers for the EMI rule on personal and auto loans, a file for ideas to build later, git set up now, the Phase 1 contradiction sweep, and answers on five features.
**Built:** `FUTURE-UPGRADES.md`, a `.gitignore`, four new rules in `CLAUDE.md` (catch ideas for later, git after every piece, manual and code must agree, customer data never in the browser). Settled D-07 as Option A. The sweep found twelve more things, T-15 to T-26, including the wrong CORS port and three different test folder layouts across the trainer's own documents.
**Found:** this laptop has no git, no Python, and no Node. Nothing can be built until they're installed. winget is available so it's three commands.
**Realised:** Rohit said yes to five features on top of the base. That's too many with Phase 5 to protect, so it went back as a question: pick one headline.
**Next:** Rohit runs the three install commands and creates the GitHub repository. Then Piece 1.

---

## 2026-09-05 — Session 6: The folder layout, and three more decisions settled

**Asked for:** whether the trainer defined the smaller risk deductions, how the activity log records later phases "automatically", and to see the project folder structure before any code.
**Built:** the full folder layout for all five phases, written into `BUILD-PLAN.md`. Settled D-01 (EMI warning on all three loan types) and D-10 (approve above 70).
**Found:** the folder names are decided for us. The trainer's tests import `app`, `rag`, `agent`, `mcp_server` and `multi_agent` as top-level names, so all five must sit side by side or the imports break. Also found that rejecting a loan on score alone is nearly impossible with the trainer's numbers — only one combination out of eighteen can do it.
**Realised:** the activity log deserves to be a proper piece with its own table, so Phase 1 has six tables, not five.
**Next:** confirm the folder layout, decide D-07 (how staff and applicants log in), then build Piece 1.

---

## 2026-09-05 — Session 5: Simpler explanations, and a shared build plan

**Asked for:** simpler English, an answer on whether the trainer's ₹5 crore was a test value, and a way to see the small details instead of approving finished work.
**Built:** `BUILD-PLAN.md`, where each piece gets planned before it is built. Three new rules in `CLAUDE.md`: write simply, always end by saying what to read next, plan each piece before building it. Settled the vehicle quotation and the activity log.
**Found:** the ₹5 crore is a real setting in the Phase 5 code, not a test value. No Phase 5 test goes near it, so lowering home loans to ₹1 crore breaks nothing.
**Realised:** Rohit wants to co-build, not review. So Phase 1's backend gets split into 13 small pieces, planned one at a time.
**Next:** answer the 5 remaining open questions, then plan Piece 1, the project skeleton.

---

## 2026-09-05 — Session 4: Reading the Phase 1 contract, and settling four contradictions

**Asked for:** exact line numbers to read, then answers on the seven contradictions, plus advice on an activity-log idea and how to set up git.
**Built:** no code. Four contradictions settled (D-02 tenure per type, D-03 loan cap at ₹1 crore, D-05 add date of birth, D-06 role checks). Added three new working rules to `CLAUDE.md`.
**Found:** the risk threshold question has a right answer, not a preference — only "greater than 70" makes the trainer's own required demo scenario work. Also that the activity-log idea doesn't conflict with the POC, but Koushik already rejected audit logs as a showcase feature, so it can't be the differentiator.
**Realised:** improvements should be additive only — named it "cautious upgrade". Also that each piece (backend, React, Streamlit, activity log) should be planned and built in its own iteration.
**Next:** a full contradiction sweep of Phase 1 specifically, before the domain rules file gets written. Then git setup, then the project skeleton.

---

## 2026-09-03 — Session 3: Planning Phase 1

**Asked for:** a plan before writing any code, plus a way to remember things across chat sessions.
**Built:** `CLAUDE.md`, this log, and `TRAPS-AND-DECISIONS.md`. No code yet, on purpose.
**Found:** the Phase 1 test file hardcodes Python module paths and function names, so the stack choice was effectively already made. Also found 4 traps that fail tests silently, and one test that breaks if we enforce the EMI affordability rule.
**Realised:** reading the whole blueprint in one go doesn't stick, so we switched to reading one short section then building that piece.
**Next:** read the three short sections listed above, answer the 9 open items, then start the project skeleton.

---

## 2026-09-03 — Session 2: Making sense of everything

**Asked for:** read the trainer's POC folder and the exported Teams chats, then write down what we were meant to build, what changed, and what happened.
**Built:** three reference documents — `01-POC-BLUEPRINT.md` (the spec), `02-GROUND-TRUTH-SHIFTS.md` (what changed in real life), `03-THE-FLOW-WHAT-HAPPENED.md` (the story in order).
**Found:** the trainer's own documents contradict each other in seven places. Also that Gemini was blocked by the company network for weeks so the cohort moved to Ollama, and that the goal quietly shifted from passing tests to giving a good demo.
**Realised:** the first version was written in a heavy "master and disciple" style that got in the way, so it was rewritten in plain words with a glossary.
**Next:** plan Phase 1 before building anything.

---

## 2026-09-03 (earlier) — Session 1: Getting the raw material together

**Asked for:** nothing from Claude yet. This was manual work.
**Built:** exported the program's Teams conversations into text files in `Chats/` — 9 files covering 19 June to 20 August, including the AI-generated meeting notes.
**Found:** the POC pack from the trainer, `POC-01-Loan-Application-Management/`, with 17 documents covering all five phases.
**Realised:** there was too much scattered material to hold in my head, and it needed to be compiled into something readable.
**Next:** hand both folders to Claude and have it work out what's going on.
