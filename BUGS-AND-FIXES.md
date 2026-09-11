# Bugs we found, and how we found them

A record of what actually went wrong while building this, written to be read
later — for a walkthrough, a presentation, or just to remember why a piece of
code looks the way it does.

`TRAPS-AND-DECISIONS.md` is the working file we keep during the build. **This one
is the story**: what broke, how it surfaced, and what it taught us.

---

## The one pattern behind most of them

Nearly every bug that reached a screen had the same shape:

> **The data was right. The seam between correct data and what a human finally
> reads was wrong.**

That is worth saying plainly, because it explains something uncomfortable: we had
156 passing tests when both of the worst ones shipped. Tests assert on *values* —
`status == "approved"`, `amount == 4000000.0`. They never assert on the sentence
a loan officer reads. So a test suite can be entirely green while the product
says "$4,000,000.0" to a customer.

Once we named the pattern, we went looking for it deliberately instead of waiting
to trip over it. That one sweep found **27 more suspects** in a single pass.

---

## A note on the last two

Bugs 1 to 10 below are things somebody saw on a screen. **Bugs 11 and 12 are not
— nobody has ever seen either of them happen.** They are in this file because
the audit went looking for the *shape* of a bug rather than waiting for one, and
those two are the shape that costs you the demo rather than embarrassing you
during it: a crash where every other comparable path in the product degrades
politely instead.

That is the difference worth pointing at in a walkthrough. The first ten were
found by looking at the product. The last two were found by asking what this
code would do on a day that has not happened yet.

---

## The bugs, in the order we hit them

### 1. The AI wrote dollars on an Indian loan

**What we saw.** The first real underwriting review came back with a good
paragraph — and the phrase **"$4,000,000.0"**. Dollars, on a rupee home loan,
with a stray decimal.

**What was actually wrong.** The verdict was right. Every number was right. The
prompt handed the model the bare value `4000000.0` with no currency attached, and
a model given a number with no unit fills the gap from whatever is commonest in
its training data. That is dollars.

**The fix.** Format the amount as rupees *before* it reaches the model, and tell
the model in one line that this is an Indian bank. It now writes **₹40,00,000** —
with correct Indian lakh grouping, because the prompt showed it that way.

**What it taught us.** *Every value entering a prompt carries its unit and its
meaning.* The risk assessor already did this and its figures were always right;
only the decision maker passed a raw number. Same pipeline, two agents, one
careful and one not.

---

### 2. `[object Object]` in the activity log

**What we saw.** The manager's activity page, details panel:
`Details: [object Object]`.

**What was actually wrong.** Nothing in the data — the row was recorded
perfectly. A React component called `String(value)` on a nested structure, and
that is JavaScript's way of saying "I tried to print this as text and gave up".
Every other detail in the app is a flat value, so it had never come up.

**The fix.** Flatten the nested structure into ordinary labelled rows. The values
inside were always the plain things a manager wants — which application, which
status, what reason.

**Worth noticing.** This was never developer diagnostics. There is a separate
section on that panel holding a reference id for a developer. The Details section
was always meant for the manager; it just was not holding up its end.

---

### 3. The reasoning was right, the browser gave up

**What we saw.** "Timeout of 15000 ms", twice in a row.

**What was actually wrong.** Nothing. The review completed correctly in **21
seconds**. The browser had a 15-second limit, set once for the whole app.

**The fix.** The assistant gets its own 90-second limit; everything else keeps
15. **Not unlimited** — if the backend dies mid-review, an unlimited wait spins
forever with no error and no way out but a page reload. Slow is normal on that
screen; infinite is not.

**What it taught us.** One number for the whole app was right when every request
was a database read answering in milliseconds. The assistant is the first screen
where waiting twenty seconds is *correct behaviour*, and the old limit was simply
the wrong measuring stick for it.

---

### 4. "Chat #null" on the activity page

**What we saw.** Eight rows reading `Chat #null` in the Record column.

**What was actually wrong.** The chat rows were written with a record *type* but
no *number*, because a conversation is not a numbered record. The page printed
`#` followed by a missing number.

**The fix.** Two parts, and the second matters more. The page now prints a number
only when there is one. And **a confirmed AI change files itself under the
application it changed** — so someone auditing application 3 sees that the AI
attempted a disbursement on it, instead of that being buried under a numberless
"chat".

**The rule we kept.** *Never claim an entity type without an id.* The pair travels
together or not at all.

---

### 5. A tool that never reached its own code

**What we saw.** "No AI is available at the moment" — while all the API keys were
working and the model was answering fine.

**What was actually wrong.** The ReAct format has one `Action Input:` line, so
for a tool taking several arguments the whole lot arrives in the *first*
parameter. With required parameters, validation rejected the call before the
function body ever ran. The agent raised, and the chat's own error handling
honestly reported it as an AI failure — pointing at completely the wrong thing.

**The fix.** Two halves, and one without the other does nothing: give the later
parameters defaults so the call actually lands, then work out what the model
meant. A real model was observed writing **six different shapes** for the same
instruction.

**What it taught us.** An honest error message can still point somewhere useless.
"No AI is available" was true of nothing at all — the chat could not tell a
broken tool from a broken provider.

---

### 6. Two of the keys were fine, and I said they were not

**What we saw.** Three keys pasted in, every AI call failing.

**What was actually wrong.** Two things, and the second was my mistake. All three
keys had been pasted into a field that takes exactly one, so a 147-character
string went to Google as a single key. That part was real.

Then I claimed two of the three were not API keys at all, judging by their shape
— 53 characters starting `AQ.` rather than the familiar 39-character `AIza`.
**Rohit pushed back, and he was right.** Tested directly against Google, all
three work. Gemini issues more than one key format.

**What it taught us.** *Do not tell someone their credentials are invalid without
testing them.* The test costs one request and settles it:
`GET https://generativelanguage.googleapis.com/v1beta/models?key=...`

---

### 7. The sweep: 27 more, before anyone saw them

After the dollar sign and the `[object Object]`, we stopped waiting for bugs to
surface and went looking for that exact shape everywhere. What it found:

- **The dollar-sign bug had a twin, still live.** A loan limit written as a bare
  `2,500,000` with no currency at all — feeding the *same prompt* we had just
  fixed. The careful amount sat directly beside an unlabelled one.
- **The assistant wrote rupees the wrong way.** Six places used Western grouping
  (`Rs 2,500,000`) where the rest of the app uses Indian grouping (`₹25,00,000`)
  — on the same screen. One of the six built the confirmation sentence shown
  before a real record change.
- **The timezone bug had a side door.** The 5.5-hour bug is properly fixed across
  the API, but one tool handed the model a raw UTC timestamp. The model would
  read the UTC wall clock aloud as though it were local — the same bug, through a
  door the original fix could not guard.
- **The staff chat dumped raw Python at the model.** Every field of every tool
  answer crossed as `key: repr(value)` — bare floats, ISO timestamps,
  `True`/`False`, and nested dictionaries as Python source. Both earlier bugs, in
  one function, feeding six tools.
- **A missing hint that could invert a decision.** The decision prompt stated a
  risk score out of 100 without saying higher is better — a hint the risk
  assessor's prompt did include. A model can read 70/100 as "seventy percent
  risky" and argue the opposite case.

All fixed in one pass, by category rather than by file.

---

### 8. One event, two clocks, one screen

**What we saw.** The Application Detail card says an eligibility assessment
happened at one time. Open the assessment itself, directly below, and it says the
same assessment happened at a different time — five and a half hours earlier.

**What was actually wrong.** Both of them were telling the truth about the same
instant. The paragraph read `eligibility_checked_at`, which is a proper datetime
field, and the browser converted it to Indian time the way it converts every
other date in the app. The assessment text had its own opening line, written by
the server as a UTC wall clock and then stored as part of the text. India is UTC
plus five and a half hours, so there is the gap.

**The fix, and why it is a deletion.** The instinct is to convert that line to
Indian time. That is the wrong fix twice over: it makes the server guess the
reader's timezone, which it has no way of knowing, and it leaves two copies of
one fact that will drift apart the moment somebody edits one of them. The moment
was *already* stored properly in the field right beside the text. So the line
comes out, and the card's existing, correct copy is the only one.

**The half that nearly got missed.** Changing the code only changes what gets
written from now on. Fourteen applications already in the database still had the
old line inside their stored text, which means the bug would still have been on
screen for every single demo application. **A stored string does not fix itself
when the code that wrote it changes.** So the fix has a second half: on startup
the app strips that one line from rows that have it, guarded so it touches
nothing else in the assessment.

**What it taught us.** *A time is stored once, as a datetime, and formatted where
it is read.* This app already did that everywhere. The bug existed precisely
because one string opted out of the rule — and the rule is not enforceable by a
type, only by noticing.

---

### 9. "Id proof", and the ten places it came from

**What we saw.** "Id proof" where a person would write "ID proof". Small, and the
kind of thing that makes a demo look unfinished.

**What was actually wrong.** The browser turns a stored value like `id_proof`
into words by removing the underscore and capitalising the first letter. That is
right for `under_review`, which becomes "Under review", and wrong for an
abbreviation, which becomes somebody's name.

Then the interesting part. Searching for the same mistake elsewhere found **ten
more copies of it in the backend**, each a bare `replace("_", " ")` written
inline. Those are not cosmetic in the same way: several of them feed text
straight into AI prompts, and the AI repeats what it is handed. So the chatbot
could tell a customer one thing about a document while the screen beside it said
another — which is exactly what the project's own rule about the manual and the
code agreeing exists to prevent.

**The fix.** One function on each side, holding the same short list of words that
are not ordinary words: ID, KYC, EMI, CIBIL, PAN, AI, NRI. All ten backend call
sites go through it, and no raw underscore-strip survives anywhere outside the
helper. A test walks every document type, status and employment status the app
can store and asserts none of them comes out with an underscore still in it, so a
value added next year cannot quietly bring the bug back.

**Worth noticing.** Two copies of that word list, one in Python and one in
JavaScript, is not elegant. Sharing a literal between the two languages would
need a build step nobody asked for. Two small lists, each with a comment pointing
at the other, is the honest version of that trade-off rather than a pretence that
there is only one.

---

### 10. "3.0 days", "3.0 years", "70.0/100"

**What we saw.** The Morning Briefing — the headline feature, the one the demo
opens on — saying an application had been waiting **"3.0 days"**. My Profile
saying someone had been with their employer **"3.0 years"**. The activity table
saying a risk score of **"70.0/100"**.

**What was actually wrong.** Nothing, again, in the data. All three are stored as
decimal numbers for good reasons: days-waiting is rounded to a tenth so the
sorting is stable, and the risk score is computed as a float. JavaScript prints
`3.0` as `3`, so this only shows up where the number really did arrive as a
decimal from the server. Nobody says "three point zero days".

**The fix.** One helper that rounds to a whole number for display, used at all
four places, rather than four separate rounding calls that would each need
finding again later.

**One extra thing fixed while there.** The risk score in the details panel had no
formatting at all — it fell through to "print whatever this is", so a reader saw
`70.0` with nothing to say what the scale was or which direction is good. It now
reads "70 out of 100". That panel is the one place the number appears without a
sentence around it to explain it.

**What it taught us.** This is the same shape as every other bug in this file, at
its smallest: the value was right, the sentence built from it was wrong, and no
test noticed because every test asserts on the value.

---

### 11. The one AI path that could still take the screen down

**What we saw.** Nothing, yet. This one had not happened, and that is the point
of writing it down.

**What was actually wrong.** Every AI path in this product degrades rather than
fails. Phase 5's four agents fall back to short deterministic summaries when the
model is unavailable. The Morning Briefing falls back to the plain figures and
says on the screen that no AI wrote it. The chat falls back from the agent to the
manual, and then to an honest "nothing is available".

The review branch was the exception. It called the four-agent graph with no
`try` around it, then read `state["risk_assessment"]` and the keys inside it
directly. Anything unexpected — an agent raising part-way through, a network
failure inside the graph, a state shape nobody predicted — comes out as an HTTP
500, which reaches a person as a red banner across the chat with a page refresh
as the only way forward. Mid-demo, that is the worst available outcome.

**The argument that was wrong.** The code had a reason, written in its own
comment: the caller returns early whenever data collection fails, so by the time
we read those keys they are always filled in. That is true, and it is not
enough. It covers the failures the graph **records** — the ones it puts in its
own error list and hands back politely. It covers none of the failures that
escape it. And the agents' own error handling turns out to wrap only their calls
to the AI; the plain-Python arithmetic before those calls is unguarded, so an
applicant record missing one field raises straight out through the whole graph.

**The rule worth keeping:** *a path is not safe because the caller checks, unless
the caller checks the thing that actually goes wrong.* Errors a system reports
are the easy half. What reaches a screen as a 500 is always the other half.

**The fix.** The whole branch is wrapped, and a failure becomes a normal answer
saying the review could not be completed — including the fact that the
application itself is unchanged, which is the first thing a loan officer wonders
after an error. Every figure in the answer is now read defensively too, so a
missing number costs that one line rather than the whole answer.

**What it deliberately does not do.** It never invents a verdict. If the review
did not run, the answer says so. A confident made-up decision would be far worse
than an honest failure, and there is a test asserting the words APPROVE and
REJECT cannot appear in an answer for a review that did not happen.

**Ten new tests, no AI quota spent.** Every failure is a stand-in raising on
purpose: four kinds of exception, a state with no risk figures, a half-filled
one, and an empty one.

---

### 12. The card that would have taken the dashboard with it

**What we saw.** Also nothing, and this one is even less likely.

**What was actually wrong.** The Morning Briefing card called `.split()` on the
narrative text and read four figures out of a nested object, with no guard on
either. Both fields are marked required by the server, so on any normal day this
cannot fail.

The reason it is worth three lines anyway is what happens **if** it does. A
React component that throws while rendering does not fail quietly in its own
box — React unmounts everything above it and the page goes white. So one
optional field on one card would cost the manager the entire dashboard, and the
`try` around the request that fetched the data does not help, because by then
the request has already succeeded.

**The fix.** A missing narrative now shows one line saying no summary was written
and keeps the figures underneath, which matches what the card already does when
the AI is unavailable. A missing figure shows a dash.

**The habit worth taking from it.** Anything pulled out of a server response with
`.split`, `.map`, `.length` or a nested property gets a guard, even when the
schema says it cannot be null. The schema describes what the server intends to
send. The component renders whatever actually arrived.

---

## How to look for bugs you do not know about

The method, in four steps, in case it is useful again:

1. **Name the shape of the ones you did find.** Not "a currency bug" — *"correct
   data, wrong presentation, invisible to tests"*. The shape is the thing you can
   search for.
2. **Sweep for that shape everywhere, shallowly.** Thirty suspects read quickly
   beats five analysed deeply, because you are looking for a pattern rather than
   debugging one instance.
3. **Verify the top few yourself before planning.** A plan built on a misreading
   wastes exactly the time it was meant to save.
4. **Fix by category, not by file.** Every rupee amount at once, every prompt at
   once. One decision applied consistently, rather than seven small ones that
   drift apart later.

And the thing worth saying out loud in a walkthrough: **the codebase was already
disciplined about this.** There were helpers for exactly these problems, used
deliberately, with comments citing the original bugs. The leaks were concentrated
in the older layers — written before the discipline existed. That is the normal
shape of technical debt: not bad code, but good habits that arrived after some of
the code did.
