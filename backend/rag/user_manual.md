# Loan Application Management System (LAMS) — User Manual

This manual is the single source of truth the LAMS assistant answers from. Every
number in it matches `backend/app/domain/rules.py`, which is the code that
actually enforces these rules. If one changes, both change.

---

## Section 1 — System Overview

The Loan Application Management System, known as LAMS, is the online loan
service of the bank. It handles three kinds of loan: **personal loans**, **home
loans**, and **auto loans**. The system is available 24 hours a day, seven days
a week, although applications are reviewed by loan officers only during working
hours.

LAMS provides:

- Online loan application submission, with no need to visit a branch
- Live status tracking, so an applicant always knows where their application is
- Document upload and verification by bank staff
- A review dashboard for loan officers
- An analytics dashboard for branch managers
- A complete audit trail of every action taken on every application

An applicant registers once, creates a borrower profile, and can then submit as
many loan applications as they wish. Each application is tracked separately and
moves through its own review process.

---

## Section 2 — Roles and Permissions

LAMS has four kinds of user, and each sees a different part of the system.

**Applicant (the customer).** An applicant may submit loan applications, upload
documents against their own applications, view their own application status and
history, check their eligibility before applying, and ask to change their own
application while it is still `submitted` or `under_review` (see Section 6). An
applicant **cannot see
any other applicant's data**. Attempting to open another customer's application
returns a "forbidden" error. This is enforced by the server on every request,
not merely hidden in the screens.

**Notifications.** LAMS notifies people inside the app itself, with a bell in
the top bar; it does not send email, text messages or push notifications. There
are exactly three kinds. Bank staff — loan officers and branch managers — are
notified when a customer asks to change an application they have already
submitted, and when a customer uploads a document marked as a TEST document. A
customer is notified when their own application's status changes, including
when it is first submitted. Nothing else produces a notification, and a
notification never contains an amount or an identity number.

**Loan Officer (bank staff).** A loan officer may view all loan applications
from every customer, create borrower profiles on a customer's behalf, move an
application from `submitted` to `under_review`, approve or reject an application
under review, add remarks explaining a decision, verify uploaded documents, and
approve or refuse a customer's request to change their application.
A loan officer **cannot disburse a loan** — that is, cannot release the money.

**Branch Manager.** A branch manager may do everything a loan officer can do,
and in addition may **disburse an approved loan**, view the analytics dashboard,
and view the full activity log of everything that has happened in the branch.
Disbursement is restricted to the branch manager because it is the point at
which money actually leaves the bank.

**System Administrator.** The system administrator oversees the system itself
rather than the lending. The administrator may view every customer, every loan
application, every document, every request to change an application, the
dashboard, the full activity log, and the list of every user account and its
role. The administrator also manages the system's own settings, such as whether
customers upload real document files; only the administrator can change a
setting, and every change is recorded in the activity log.
The administrator **cannot do any loan business**: it cannot create
an application or a borrower profile, add or verify a document, move, approve,
reject or disburse an application, or approve or refuse a change request. The
administrator is not a branch manager and cannot run the underwriting review.
Administrator accounts are created by the bank; nobody can register as one.

---

## Section 3 — The Six-Step Loan Workflow

Every loan in LAMS follows the same six steps, in order.

1. **Registration.** The customer creates an account with their email address
   and a password, which also creates their borrower profile.
2. **Application submission.** The customer chooses a loan type, an amount and a
   tenure, states the purpose, and submits. The application is created with
   status `submitted`.
3. **Document upload.** The customer uploads the documents that their loan type
   requires. Documents may be uploaded before or after submission.
4. **Loan officer review.** An officer picks up the application, moves it to
   `under_review`, checks the documents, and verifies them one by one.
5. **Decision.** The officer either approves or rejects the application, and
   records remarks explaining why.
6. **Disbursement.** For an approved loan, the branch manager releases the funds
   and the application moves to `disbursed`. This is the final state.

---

## Section 4 — Required Documents

Every document is stored against a document type. The type names used by the
system are `id_proof`, `income_proof`, `bank_statement`, `property_docs`,
`employment_letter` and `vehicle_quotation`.

**A personal loan requires three documents:**

- `id_proof` — identity proof, such as Aadhaar, PAN card, passport or driving licence
- `income_proof` — income proof, being the last 3 months of salary slips
- `bank_statement` — a bank statement covering the last 6 months

**A home loan requires five documents.** The three above, plus:

- `property_docs` — property documents: the sale deed, the NOC, and the building plan approval
- `employment_letter` — an employment letter from the current employer, for salaried applicants

**An auto loan requires four documents.** The three base documents
(`id_proof`, `income_proof`, `bank_statement`), plus:

- `vehicle_quotation` — a vehicle quotation or proforma invoice from the dealer

**How real uploads work.** When the system administrator has switched real
uploads on, a document must be a genuine PDF, JPG or PNG file — the system
checks the file's actual content, not just its name — and no larger than
5 MB. Every uploaded document is automatically resized and re-saved before
it is stored, which also strips anything hidden inside the file. A
photograph and a signature may also be uploaded; neither is required for
any loan type. When real uploads are switched off, a document is recorded
by its type and file name only, exactly as in earlier versions of the
system.

The system decides for itself, from the document's own content, whether it
looks like demonstration or specimen material rather than a genuine
document — nobody is asked to say which it is. This only decides how
carefully the file is kept; it never means the system has checked whether
a document is a genuine, authentic one. The same document type may be
uploaded more than once, for example an Aadhaar card and a PAN card as
two identity proofs. Only documents that have **not yet been verified** may
be replaced: use **Replace** next to the document on the application page
and choose the newer copy. The new copy keeps the same document type, takes
the old one's place in the checklist, and is checked again by staff. Once a
loan officer has verified a document, it is fixed as part of the record and
can no longer be replaced.

When you upload an identity proof, income proof or bank statement as a file,
you also say which document it is: an **Aadhaar card** or a **PAN card** for
identity proof, a **salary slip** for income proof, or a **bank statement**.
A short form then asks for the details printed on it, such as the name, date
of birth and Aadhaar number on an Aadhaar card. Fill it in and click
**Confirm details**. The document only counts towards your checklist once its
details are confirmed; until then it shows as "needs details". The details
are checked for their format, for example that an Aadhaar number is valid and
a PAN looks like a real PAN. This does not prove a document is genuine. Staff
still check it. **Only the last 4 digits of your Aadhaar number are kept**,
as UIDAI rules require, and the same goes for your bank account number.

If the file is a PDF with its own text in it (most documents downloaded from
a bank, an employer or DigiLocker are), the form **fills itself in** from that
text as soon as it's uploaded. Check every value against the document before
you confirm. A value that was found but doesn't pass its check is marked
"Please check" and must be corrected first. A photo or a scanned copy can't
be read automatically, so its details are typed in by hand. When an Aadhaar
is uploaded, **the first 8 digits of the number are blacked out on the copy
the bank keeps**. If the number can't be found on the file to black it out
(a photo or a scan, for example), the upload is refused: download your
**masked Aadhaar** from myAadhaar (UIDAI's website), which already hides
those digits, and upload that instead.
Nothing you type in these details changes your profile. If a name or date of
birth doesn't match your profile, the form shows a note, and staff will look
at it.

A document the system recognises as demonstration or specimen material is
marked TEST and shown with a TEST badge wherever it appears, and the
document checklist says how many of the uploaded documents are TEST. Loan
officers and the branch manager are notified in-app the moment a TEST
document is uploaded. Marking a document TEST is not the same as verifying
it: a TEST document can still be marked verified for demonstration
purposes, but this is clearly labelled as checking it for the demo, not for
authenticity. The system administrator can permanently remove every TEST
document from the system in one step; real and undeclared documents are
never affected by this.

---

## Section 5 — Eligibility Criteria

These are the rules the system applies when assessing whether a loan can be
granted. They are checked automatically before an application is submitted, and
again by the loan officer during review.

### Personal loan eligibility

- Age: **21 to 60 years**
- Minimum annual income: **₹2,40,000** (that is ₹20,000 a month)
- Minimum CIBIL score: **650**
- Maximum loan amount: **₹25,00,000** (25 lakh)
- Tenure: **12 to 60 months**
- A personal loan is unsecured, so a CIBIL score must be on file. An applicant
  with no CIBIL score at all cannot be considered for a personal loan.

### Home loan eligibility

- Age: **21 to 70 years**, and the loan must be fully repaid before the borrower
  turns **70**. A 55-year-old therefore cannot take a 30-year home loan.
- Minimum annual income: **₹4,80,000** (that is ₹40,000 a month)
- Minimum CIBIL score: **700**
- Maximum loan amount: **₹1,00,00,000** (1 crore). Within that ceiling, the
  amount sanctioned is also limited to about **80% of the assessed property
  value**, which the credit team applies at valuation.
- Tenure: **12 to 360 months**
- The EMI must not exceed 50% of monthly income.

### Auto loan eligibility

- Age: **21 to 65 years**
- Minimum annual income: **₹1,80,000** (that is ₹15,000 a month)
- Minimum CIBIL score: **600**
- Maximum loan amount: **₹50,00,000** (50 lakh). Within that ceiling, the amount
  sanctioned is also limited to about **90% of the vehicle value**.
- Tenure: **12 to 84 months**

### Rules that apply to all three loan types

- The smallest loan LAMS will accept is **₹10,000**.
- Total monthly EMI commitments, including any loans the applicant is already
  repaying, must not exceed **50% of monthly income**. This is the affordability
  rule and it applies to personal, home and auto loans alike.
- A salaried applicant must have been with their current employer for at least
  **6 months**. A self-employed applicant must show at least **2 years** of
  business history.
- An unemployed applicant cannot be approved for any loan.
- An applicant with no CIBIL score can only be considered for a **secured** loan,
  meaning a home loan or an auto loan, where the property or vehicle acts as
  collateral.

---

## Section 6 — Application Status Rules

An application has exactly one status at a time, and can only move forwards.

The five statuses are `submitted`, `under_review`, `approved`, `rejected` and
`disbursed`.

The permitted moves are:

- `submitted` → `under_review`
- `under_review` → `approved`
- `under_review` → `rejected`
- `approved` → `disbursed`

Nothing else is allowed. In particular, an application can never move backwards,
`rejected` is final, and `disbursed` is final.

**Once an application is rejected it cannot be reopened.** The customer must
submit a brand-new application. Only a branch manager may perform the
`approved` → `disbursed` move. Every status change is recorded in the audit log
with who made it, when, and the remarks they wrote.

### Changing an application after it is submitted

A customer can ask to change the **amount**, the **tenure** or the **purpose** of
their application, but only while its status is `submitted` or `under_review`.
Once an application is approved, rejected or disbursed, it can no longer be
changed. The **loan type can never be changed**: if the wrong loan type was
chosen, the customer submits a new application.

Changing an application takes three steps:

1. On the application's page, the customer presses **Request an edit**, ticks the
   details they want to change, and writes why (10 to 1,000 characters).
2. A loan officer or the branch manager reviews the request and either approves
   it or refuses it. A refusal always includes a reason, which the customer sees
   on the application's page.
3. If the request is approved, the customer can change the details they asked
   for, **once**. The new figures must meet the same limits as a new
   application, and the bank checks eligibility again automatically with the
   new figures.

Only one request can be open on an application at a time. If the application is
approved or rejected while a request is still waiting, the request is closed
automatically. Every request, every decision and every change is recorded in
the audit log.

---

## Section 7 — How EMI Is Calculated

EMI stands for Equated Monthly Instalment: the fixed amount paid every month
until the loan is repaid. LAMS uses the standard reducing-balance formula.

```
EMI = P × r × (1 + r)^n / ((1 + r)^n − 1)

where
  P = the loan amount (the principal)
  r = the monthly interest rate, which is the annual rate ÷ 12 ÷ 100
  n = the tenure in months
```

**Worked example.** A loan of ₹5,00,000 at 12% per year over 36 months:

```
  r   = 12 ÷ 12 ÷ 100 = 0.01
  n   = 36
  EMI = ₹16,607 per month
```

When LAMS estimates an EMI before the final interest rate has been set, it uses
an indicative rate of **12% per year**. The rate actually offered depends on the
loan type, the CIBIL score and the tenure.

---

## Section 8 — The Dashboard

The dashboard gives bank staff the state of the branch at a glance. It shows the
total number of applications, a count of applications at each status, a count by
loan type, and the total amount requested across all applications. It also shows
how many applications are awaiting review and the total value of loans that are
approved but not yet paid out.

The dashboard refreshes every 5 minutes, and can be refreshed on demand. Loan
officers and branch managers can both view the dashboard, and the system
administrator can view it too. Applicants cannot.

---

## Section 9 — Processing Times

How long an application takes depends on the loan type.

| Loan type | Usual time | Maximum time |
|---|---|---|
| Personal loan | 2 to 3 business days | 7 business days |
| Home loan | 7 to 10 business days | 21 business days |
| Auto loan | 1 to 2 business days | 5 business days |

A personal loan is normally decided within **2 to 3 business days**. A home loan
takes longer, usually **7 to 10 business days**, because the property has to be
valued and the legal documents checked. An auto loan is the quickest, usually
**1 to 2 business days**.

Loan officers work Monday to Saturday, 9 AM to 6 PM. An application submitted on
a Saturday evening or a Sunday will not be picked up until the next working day,
so an application sitting in `submitted` for 24 hours is entirely normal.

---

## Section 10 — Security and Privacy

Every user signs in with an email address and a password. Passwords are stored
hashed using bcrypt and are never stored in readable form. A session expires
after 24 hours, after which the user signs in again.

Customer data is held on the bank's servers and is fetched fresh with the user's
own session each time it is displayed. A real uploaded document is
encrypted before it is stored, and only opened again for someone allowed to
see it — the applicant it belongs to, bank staff, or the administrator.
Other customer data is protected by the same server-side access checks.

Access is checked on the server for every single request. An applicant can only
ever retrieve their own applications, their own documents and their own profile.

Every status change and every significant action is written to an audit log
recording who did it, what they did, when, and why. The branch manager and the
system administrator can review this log at any time.

---

## Section 11 — Frequently Asked Questions

**What interest rate will I be charged?**
Personal loans carry **10.99% to 18%** per year. Home loans carry **8.5% to 12%**
per year. Auto loans carry **9% to 14%** per year. The exact rate depends on your
CIBIL score, your income and the tenure you choose.

**Is there a processing fee?**
Yes. The processing fee is **0.5% to 2% of the loan amount, subject to a minimum
of ₹500**. It is deducted from the amount disbursed, so the money that reaches
your account is the sanctioned amount minus the fee.

**Can I repay my loan early?**
Yes, after a lock-in period. For a personal loan the lock-in is **6 months**; for
a home loan it is **12 months**. Early repayment carries a charge of **2% of the
outstanding principal**.

**My application was rejected. What happens now?**
A rejected application cannot be reopened. You may **reapply after 90 days**, and
you must submit a **new application** rather than reviving the old one. The
rejection reason is recorded in the remarks and is visible to you, so you know
what to improve. The most common rejection reasons are income below the minimum,
a CIBIL score below the threshold, incomplete or unverified documents, and
problems with the property valuation on a home loan.

**Can I change my application after submitting it?**
Yes, while it is still `submitted` or `under_review`. Open the application, press
**Request an edit**, choose what to change (the amount, the tenure or the
purpose) and explain why. A loan officer or the branch manager approves or
refuses the request. If they approve it, you can make the change once. The loan
type cannot be changed, and an application that has been approved, rejected or
disbursed cannot be changed at all. See Section 6 for the full steps.

**How long must I have been in my job?**
Salaried applicants need at least **6 months** with their current employer.
Self-employed applicants need at least **2 years** of business history.

**How is my income verified?**
For salaried applicants, by salary slips and Form 16. For self-employed
applicants, by 2 years of income tax returns.

**Can I replace a document I have already uploaded?**
Yes, as long as it has not yet been verified. Open your application, find the
document, click **Replace**, and choose the newer copy. The new copy takes the
old one's place and is checked again by staff. Once a loan officer marks a
document as verified, it becomes part of the permanent record and cannot be
replaced.

**Can I add a co-applicant?**
A co-applicant must be added **at the time of submission**. A co-applicant cannot
be added to an application that has already been submitted.

**I have no CIBIL score. Can I still borrow?**
Only for a **secured** loan, which means a home loan or an auto loan where the
property or the vehicle acts as collateral. An unsecured personal loan requires a
CIBIL score of at least 650.

**What is the difference between the sanctioned amount and the disbursed amount?**
The sanctioned amount is what the bank has approved. The disbursed amount is what
actually reaches your bank account, which is the sanctioned amount minus the
processing fee and any other charges.

**What is the maximum I can borrow?**
₹25,00,000 for a personal loan, ₹1,00,00,000 for a home loan, and ₹50,00,000 for
an auto loan. The smallest loan is ₹10,000.

**How much of my income can go towards EMIs?**
No more than **50% of your monthly income**, counting every loan you are already
repaying as well as the new one.

**How do I track my application?**
Sign in and open your applications list. Each application shows its current
status and a full history of every change, with the date and the remarks.

**Who decides my application?**
A loan officer reviews it and approves or rejects it. If it is approved, a branch
manager releases the funds.

**How do I contact the bank staff?**
For questions, ask the **Assistant** in the app first. It answers from this
manual and can tell you where your application stands. To write to the loan
officers directly, email **support@bank.com**, the loan officers' inbox. To
change the details of an application, use **Request an edit** on the
application's page instead: that request goes straight to the loan officers and
the branch manager.

---

## Section 12 — Troubleshooting

**My document upload was rejected.** When real uploads are switched on, a
document must genuinely be a PDF, JPG or PNG file, no larger than 5 MB,
readable, and not password-protected. The system checks the file's actual
content, so renaming a different kind of file does not work. A photograph
or signature must also be a clear, recognisable image at a usable
resolution.

**My application has been in "submitted" for a day.** This is normal. Loan
officers work Monday to Saturday, 9 AM to 6 PM, so an application submitted
outside those hours waits until the next working day.

**I cannot see another person's application.** That is deliberate. Applicants can
only see their own data.

**I cannot disburse an approved loan.** Only a branch manager can disburse. A
loan officer who tries will be refused.

**I was told my status change is invalid.** Applications only move forwards, in
the order given in Section 6. A rejected or disbursed application cannot move at
all.

**I am locked out.** Sessions expire after 24 hours. Sign in again.

**I cannot change my application.** Changes are only possible while the
application is `submitted` or `under_review`, and only after bank staff approve
your edit request. Each approval allows one change. See Section 6.

**Contacting the bank.** Ask the Assistant in the app first. To write to the
loan officers directly, email **support@bank.com**.

---

## Section 13 — Glossary

**CIBIL score** — A three-digit number from 300 to 900 summarising how reliably a
person has repaid credit in the past. Higher is better. Lenders use it to judge
credit risk.

**EMI** — Equated Monthly Instalment. The fixed sum paid every month until a loan
is fully repaid, covering both interest and principal.

**LTV (Loan to Value)** — The loan amount expressed as a percentage of the value
of the asset securing it. A home loan is limited to roughly 80% LTV, and an auto
loan to roughly 90%.

**KYC (Know Your Customer)** — The identity checks a bank must perform before
lending, done in LAMS by verifying the uploaded `id_proof`.

**Sanction letter** — The formal document stating that the bank has approved a
loan, and on what terms.

**Disbursement** — The moment the approved money actually leaves the bank and
reaches the borrower's account.

**Collateral** — An asset pledged against a loan, which the lender may claim if
the borrower stops repaying. A home loan is secured against the property; an auto
loan against the vehicle.

**NPA (Non-Performing Asset)** — A loan on which the borrower has not made a
payment for 90 days or more.

**FOIR (Fixed Obligation to Income Ratio)** — The share of monthly income already
committed to fixed repayments. LAMS caps it at 50%.

**Pre-EMI** — For a home loan paid out in stages during construction, the
interest-only payment made before the full EMI begins.

**Tenure** — The length of the loan in months.

**Principal** — The amount borrowed, before interest.
