# Driving Phase 2 and Phase 3 by hand, in a browser

Phase 2 is the chatbot that answers from the user manual. Phase 3 is the
assistant that also reads live application data and decides for itself which to
use. Both have passing tests. **Neither has ever been used by a person**, and
that is a real gap, because every bug in `BUGS-AND-FIXES.md` got past a green
test suite by living in the seam between correct data and a readable sentence.

Work through this when you have half an hour. It is written to be read cold.

**Parts C and D I already ran once against the real server**, so the figures
below are measured rather than predicted: application 7 really does come back
REQUEST_MORE_INFO at 70/100 with an EMI of ₹48,007, and the briefing really does
write "ID proof". What I could not check is Parts A and B — the manual questions
and the ownership refusals — because those need a person reading whether the
answer is any good, which is the whole reason this list exists.

---

## Before you start

1. Run `start-app.ps1` from the project root. Three windows open and the browser
   lands on http://localhost:5173.
2. **These questions spend real Gemini quota.** There are about 20 of them; the
   free tier is 500 requests a day per key and you have five keys, so this is
   comfortably affordable — but do not run the whole list four times in a row on
   the morning of the demo.
3. Keep a note of anything that looks wrong, even slightly. "That reads oddly" is
   exactly the signal this list is for. You are not testing whether it works, you
   are testing whether it is *presentable*.

The three logins:

| Who | Email | Password |
|---|---|---|
| Branch manager | anita@bank.com | Manager@123 |
| Loan officer | rajan@bank.com | Officer@123 |
| Customer (Priya) | priya@example.com | Customer@123 |

Priya owns applications **1** (home, ₹20,00,000, approved) and **2** (personal,
₹2,00,000, submitted). Application **7** is Sanjay's home loan for ₹40,00,000,
under review — that is the one worth assessing.

---

## Part A — Phase 2: does it answer from the manual?

Log in as **Priya** (priya@example.com / Customer@123) and open **Assistant**.

**A1. A straightforward policy question.**
Type: `What is the minimum CIBIL score for a personal loan?`
Expect: **650**. Under the answer, "Show the N manual extracts" opens to show the
text it read. Check the label above the answer says it came from the manual or
from the assistant — both are fine, the point is that it says which.

**A2. A question with a number that must be formatted.**
Type: `What is the maximum I can borrow on a personal loan?`
Expect: **₹25,00,000** — rupees, grouped the Indian way with two digits then two
then three. If you see `Rs 2,500,000` or a dollar sign, that is the bug from
audit phase 1 and it has come back.

**A3. A question the manual answers with a table.**
Type: `How long does a home loan take to process?`
Expect: **7 to 10 business days**, and probably the 21-day maximum too.

**A4. A question about something the manual genuinely does not cover.**
Type: `Do you offer education loans?`
Expect: it says it does not know, or that the manual does not cover it. **What it
must not do is invent an answer.** This is the single most important question on
this page — a chatbot that confidently makes up a lending policy in front of an
audience is worse than no chatbot.

**A5. The same question twice, worded differently.**
Type: `What documents do I need?` then `Which papers must I submit with my
application?`
Expect: the same set of documents both times. And check the wording: it should
say **"ID proof"**, not "Id proof" and not "id_proof". That was fixed in audit
phase 2 and this is where you would see it come back.

---

## Part B — Phase 3: does it read live data, and only what it should?

Still logged in as **Priya**.

**B1. Her own application.**
Type: `What is the status of my application?` or `Show me application 2`
Expect: the real personal loan for **₹2,00,000**, status submitted. Open "Show
how this was worked out" underneath — it should list a step like "Looked up an
application, 2", in plain words rather than a function name.

**B2. Somebody else's application. This is the one that matters.**
Type: `Show me application 7`
Expect: **a refusal.** Something like "you can only view your own loan
applications". Application 7 belongs to Sanjay.

Nothing in the AI decides this. The assistant asks the same API the browser
would, as Priya, and the API says no — the same refusal she would get from the
address bar. Worth saying out loud in the demo when someone asks whether it is
safe.

**B3. Now prove the other half.** Log out. Log in as **Anita**
(anita@bank.com / Manager@123), open Assistant, and type the **exact same
words**: `Show me application 7`
Expect: the loan details, for ₹40,00,000. Same question, same box, different
person, different answer.

**B4. A question that needs both brains.**
Type: `Am I eligible for a personal loan?` (as Priya, so log back in as her)
Expect: it should use the manual's rules *and* know something about her. Whatever
it says, check the amounts are rupees and the statuses read as words ("under
review", not "under_review").

**B5. Something it has no tool for.**
Type: `What is the weather in Pune?`
Expect: a polite refusal to go outside its job. Not an error, not a crash, and
not an answer about the weather.

---

## Part C — Phase 5 through the same box, and the things phase 3 of the audit fixed

Log in as **Rajan** (rajan@bank.com / Officer@123).

**C1. The four-agent review.**
Type exactly: `assess application 7`
Expect: a line saying four agents are working, a counter, then after roughly ten
to twenty-five seconds a verdict, the figures behind it, and a paragraph. Check:

- the amount reads **₹40,00,000**, not `$4,000,000.0`
- the risk score reads **"Risk score 70/100"** — seventy exactly, with no
  `.0`. That figure is plain Python, not the AI, so it is the same every time.
  The EMI beside it should read **₹48,007** and the ratio **84%**.
- any missing documents are named as words, e.g. "ID proof, bank statement"
- "Show how this was worked out" lists all four agents in order

**C2. A review of an application that does not exist.**
Type: `assess application 999`
Expect: one plain sentence saying it could not run the review, and **no red
banner**. The page must stay usable and you should be able to type the next
question straight away.

**C3. A near miss that must not trigger a review.**
Type: `what happened to application 7`
Expect: a normal, quick answer. **Not** a ten-second four-agent review. Both
sentences contain "application 7"; only the first is an instruction to assess it.

---

## Part D — the audit phase 2 fixes, on screen

**D1. The Morning Briefing.** Log in as **Anita** and look at the dashboard, then
open "How this was worked out".
Expect, under "Waiting longer than the branch's targets", three applications —
**3, 2 and 6** — reading **"9 days"**, **"7 days"** and **"4 days"**. Those are
stored as 9.1, 7.1 and 4.1, so before this fix they printed "9.1 days". The day
count creeps up as the demo data ages, so treat the shape as the thing to check
rather than the exact number.

Under "Held up by missing documents", the document names should read **"ID
proof"**, "income proof", "bank statement" — no underscores and no "Id proof".

**D2. The activity log.** As Anita, open **Activity**. You do not need to run a
review first — there are already four in there from earlier sessions, all of
application 7, all stored with a risk score of exactly 70.0.
Expect: a review row reading something like "REQUEST_MORE_INFO · risk 70/100" —
no `.0`. Click **View** on it: the details panel should say **"70 out of 100"**,
and no row should say `[object Object]` or `Chat #null`.

**D3. The eligibility card, which is the fix I am least able to check for you.**
Open any application, for example http://localhost:5173/applications/1, and find
"Eligibility at submission". Read the timestamp in the paragraph, then click
"Show the full assessment".
Expect: **the assessment text now has no timestamp of its own at all.** It starts
"Applicant: …". Previously it opened with a UTC time five and a half hours behind
the one in the paragraph above it.

**D4. My Profile.** Log in as **Priya**, open My Profile.
Expect: years with employer reads **"3 years"**, not "3.0 years". Priya is stored
as exactly 3.0, so this is the clearest place to see the fix.

**One thing to decide here.** Rahul Verma is stored as **2.5** years, and
rounding to a whole number turns that into "3 years". For a decimal that is
genuinely a half, rounding loses something real. I left it rounded because every
other value in the demo data is a whole number and "2.5 years" was not the bug
you asked me to fix — but if you would rather it showed halves, it is one line in
`frontend/src/utils/format.js` and D-26 in the traps file is where I wrote that
down.

---

## What to tell me afterwards

For anything that looked wrong, the useful three lines are: which login, what you
typed, and what appeared. A screenshot beats a description for anything visual.

If everything passes, say so — that is the first time a person will have driven
Phase 2 and Phase 3 end to end, and it is worth recording in the log as its own
entry.
