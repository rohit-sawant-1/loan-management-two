# Learning notes

Things worth knowing that came up while building. Written to be read again later. Short on purpose.

---

## How much of your salary can go to loan EMIs — the FOIR rule

**FOIR** stands for Fixed Obligation to Income Ratio. It is the share of your monthly income that already goes to fixed payments, including the new loan you are asking for. Banks use it to decide if you can afford one more EMI.

**The general rule in India:** all your EMIs together should stay under **50% of your monthly income.** Some banks use gross income, some use take-home pay.

**By loan type, in 2026:**

| Loan | What banks typically allow |
|---|---|
| Home loan | 40% to 55% of monthly income. Some lenders go to 60–65% for high earners. |
| Personal loan | 50% to 55%. A few stop at 45%. Some go to 60% for very high earners. |
| Car loan | Follows the same principle as the others. |

**Banks often step it up by income:**

| Monthly income | Usual cap |
|---|---|
| Up to ₹50,000 | 50% |
| ₹50,000 to ₹1,00,000 | 55% |
| Above ₹1,00,000 | 60% to 65%, depending on the lender |

The reasoning: someone earning ₹3 lakh a month can give up 60% and still live comfortably. Someone earning ₹30,000 cannot.

**What we use in the app:** 50% for all three loan types. One number, matches the manual, easy to explain.

Sources: [eligibilitytools.in](https://eligibilitytools.in/guides/home-loan-eligibility-india/), [GoCredit FOIR guide](https://gocredit.money/blog/foir-ratio-for-personal-loan), [Ruloans 2026 eligibility](https://www.ruloans.com/blog/home-loan-eligibility-india-2026/)

---

## Indian number grouping, and why software gets it wrong

Most programming languages group digits in threes: 2,500,000. India groups the last three digits, then twos: 25,00,000. Same number, and to an Indian reader the first one looks like a typo.

The names follow the groups. 1,00,000 is one lakh. 1,00,00,000 is one crore. So ₹25,00,000 reads instantly as "twenty-five lakh", while ₹2,500,000 makes you count.

Python, JavaScript and most libraries default to the Western style. Any app for an Indian bank needs its own formatter. Ours is `format_rupees` in `backend/app/utils/finance.py`, and it is used everywhere a rupee amount is shown in a message.

---

## What a request reference number is actually for

Every time anyone clicks something in the app, the server gives that one click a random reference, like `req_444adf97626543ee`. Every log line the server writes while handling that click carries the same reference. The activity log stores it too, which is why it appears in the app.

**Why it matters:** a busy bank server writes millions of log lines a day, all jumbled together from hundreds of people using the app at once. Without a reference, finding the lines for one particular action means guessing from a rough time and a username, and reading through everything else that happened in that window.

**The flow it enables:**

1. A loan officer says "I approved application 6 yesterday and something looked wrong."
2. The manager opens Activity, finds that event, clicks View, and reads out the reference.
3. A developer searches the log for that one string.
4. They immediately get every step of that single click, and nothing else.

Here is a real trace from our own app:

```
07:27:35.401  request_started     PATCH /api/v1/applications/6/status
07:27:35.404  token_validated     user_email=rajan@bank.com
07:27:35.417  status_updated      application_id=6  submitted -> under_review
                                  changed_by=rajan@bank.com  duration_ms=10
07:27:35.418  request_completed   status_code=200  duration_ms=16
```

Four lines, pulled out of thousands, showing who did it, what changed, how long it took, and that it succeeded. If it had crashed instead, the error and the exact line of code that failed would sit in the same group.

**The catch, and why it matters:** this only works if the log is actually kept somewhere. Until we fixed it, our log only existed in the terminal window running the server and vanished when that window closed — so a reference from yesterday was useless. Now the server also writes to `backend/logs/app.log`, keeping the last 5 files of 5 MB each.

This idea is standard in real systems and goes by names like *correlation ID* or *trace ID*.

---

## Why banks never show customers their internal risk score

When a bank scores your application, that score and the rules behind it stay inside the bank. Customers see the outcome, not the working.

Two reasons. First, if customers knew the exact rules, some would arrange their paperwork to just clear each line, which defeats the point. Second, the scoring model is the bank's competitive edge, so it is treated like a trade secret.

This is why "aim it at managers" was Koushik's feedback on the risk tool. Staff see the score. Applicants see approve, reject, or "we need more documents".

---

## FOIR — how a bank works out what you can actually afford

The obvious question a bank asks is "can this person pay this EMI?". The better question, and the one they actually ask, is "can this person pay this EMI **on top of everything they are already paying?**".

That second question has a name: **FOIR — Fixed Obligation to Income Ratio.** Some banks call it DTI, debt-to-income. Same idea. You add up every fixed monthly payment the borrower already has — car loan, an older personal loan, a credit card minimum — add the EMI of the loan they are now asking for, and divide the total by their gross monthly income.

```
FOIR = (existing EMIs + the new EMI) / gross monthly income
```

Most Indian banks cap this somewhere between 40% and 50%. Some tier it by income, giving high earners more room, on the reasoning that somebody on ₹5 lakh a month still has plenty left after 60% goes out, while somebody on ₹25,000 does not. We use a flat 50% for all three loan types (D-14).

**Two ways of saying the same thing.** You can write the rule as a ratio, "total EMIs over income must stay under 50%". Or you can turn it around: "take 50% of monthly income, subtract what they already pay, and whatever is left is the biggest EMI we can give them." The arithmetic is identical — the second is just the first rearranged. Our code uses the second form, because it answers the more useful question directly: how much room is left? That is `max_affordable_emi` in `app/utils/finance.py`.

**Where the bank gets the "existing EMIs" figure.** Not by asking, or at least not only by asking. They pull the CIBIL credit report, which lists every live loan account in the borrower's name along with what each one costs per month, and they cross-check it against six months of bank statements where those EMIs show up as debits. A borrower who forgets to mention a loan does not get away with it. Our POC simply takes the applicant's declared number, which is the honest simplification to make when you have no bureau feed.

**A worked example from our own seed data.** Sanjay earns ₹9,00,000 a year, so ₹75,000 a month. Half of that is ₹37,500 — that is his ceiling. He already pays ₹15,000 a month on other loans, so the room actually left for a new EMI is ₹22,500. He has applied for a ₹40,00,000 home loan over 180 months, which at 12% works out to an EMI of ₹48,007. That is more than double his remaining room, and his FOIR comes to (15,000 + 48,007) / 75,000 = **84%**. No bank lends into that. This is exactly why his application scores 70 and comes back as REQUEST_MORE_INFO rather than an approval.

---

## Why banks replace documents instead of deleting them

When a customer sends a newer copy of a document, a bank doesn't throw the old one away. It marks the old copy as **superseded** (replaced by a newer one) and keeps it. There are two reasons.

**The law says so.** Indian banks must keep KYC records, meaning the documents that prove who a customer is, for **at least five years after the relationship with the customer ends**. That comes from the Prevention of Money Laundering Act and the RBI's KYC Master Direction. So a loan document stays on file long after the loan is repaid.

**The audit trail needs it.** If a loan goes bad, someone will ask what the bank saw when it said yes. If the old payslip was deleted, nobody can answer that.

**Not every "same type" is a replacement, either.** An ID proof can be an Aadhaar *and* a PAN. Income proof is usually three months of payslips. That's why our app keeps several files per type side by side (D-29) and never replaces anything automatically.

*Came up in the Piece 32 browser check, 2026-09-24.*
