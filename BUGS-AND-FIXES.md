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
