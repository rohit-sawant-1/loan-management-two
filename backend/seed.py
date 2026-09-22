"""
Fill the database with believable demo data.

Run from backend/:   python seed.py

Safe to run more than once: if the manager account already exists, it stops.
The administrator is the exception. It arrived later (Piece 27), so it is
added to any database that doesn't have one yet, even an old one.
Everything goes through the real services, so the status history and the
activity log are as real as they would be from the screens.

Logins it creates (all passwords are printed at the end):
  administrator    admin@bank.com
  branch manager   anita@bank.com
  loan officer     rajan@bank.com
  customers        priya@example.com, rahul@example.com, meera@example.com,
                   arjun@example.com, kavya@example.com, sanjay@example.com
"""

import os
from datetime import date, datetime, timedelta, timezone

os.environ.setdefault("OTEL_EXPORTER", "none")

from app.database import SessionLocal, init_db                               # noqa: E402
from app.models import ActivityLog, ApplicationStatus, User, UserRole         # noqa: E402
from app.schemas import (                                                     # noqa: E402
    ApplicantSignupRequest, CreateApplicationSchema, CreateDocumentSchema,
)
from app.services import application_service, auth_service, document_service  # noqa: E402
from app.utils.auth import hash_password                                      # noqa: E402

ADMIN_EMAIL = "admin@bank.com"
ADMIN_PW = "Admin@123"
MANAGER_PW = "Manager@123"
OFFICER_PW = "Officer@123"
CUSTOMER_PW = "Customer@123"

CUSTOMERS = [
    # name, email, phone, income, employment, cibil, dob, years, existing_emi
    ("Priya Sharma",     "priya@example.com",  "9876543210", 600_000,  "salaried",      720,  date(1994, 3, 15), 3.0, 0),
    ("Rahul Verma",      "rahul@example.com",  "9123456789", 480_000,  "self_employed", 680,  date(1990, 7, 2),  2.5, 4_000),
    ("Meera Nair",       "meera@example.com",  "9988776655", 1_200_000, "salaried",     760,  date(1988, 11, 20), 6.0, 12_000),
    ("Arjun Singh",      "arjun@example.com",  "9012345678", 240_000,  "salaried",      610,  date(1999, 1, 9),  0.5, 0),
    ("Kavya Reddy",      "kavya@example.com",  "9345678901", 300_000,  "salaried",      None, date(2001, 5, 30), 1.0, 0),
    ("Sanjay Kulkarni",  "sanjay@example.com", "9456789012", 900_000,  "salaried",      740,  date(1971, 6, 10), 12.0, 15_000),
]

# applicant email, loan type, amount, tenure, purpose, final status, documents (type, verified),
# days ago it was submitted
#
# The "days ago" column exists because a demo database where every file
# arrived this morning is not what a branch looks like. A real pipeline
# always has something that has been sitting too long, and the manager's
# morning briefing (D-13) has nothing to say without it. These ages are
# spread deliberately: two files well overdue, one borderline, the rest fresh.
APPLICATIONS = [
    ("priya@example.com",  "home",     2_000_000, 120, "Buying a 2BHK flat in Pune",           "under_review",
     [("id_proof", True), ("income_proof", True), ("bank_statement", False), ("property_docs", False)], 11),
    ("priya@example.com",  "personal", 200_000,   24,  "Home renovation",                      "submitted",
     [("id_proof", False)], 6),
    ("rahul@example.com",  "personal", 300_000,   36,  "Working capital for my shop",          "approved",
     [("id_proof", True), ("income_proof", True), ("bank_statement", True)], 8),
    ("meera@example.com",  "auto",     600_000,   60,  "New car",                              "disbursed",
     [("id_proof", True), ("income_proof", True), ("bank_statement", True), ("vehicle_quotation", True)], 20),
    ("arjun@example.com",  "personal", 150_000,   24,  "Laptop and course fees",               "rejected",
     [("id_proof", True), ("income_proof", False)], 14),
    ("kavya@example.com",  "auto",     400_000,   48,  "First car",                            "submitted",
     [("id_proof", False), ("bank_statement", False)], 3),
    ("sanjay@example.com", "home",     4_000_000, 180, "Retirement home in Nashik",            "under_review",
     [("id_proof", True), ("income_proof", True), ("bank_statement", True), ("property_docs", True), ("employment_letter", False)], 1),
    ("meera@example.com",  "personal", 500_000,   48,  "Daughter's college fees",              "submitted",
     [], 0),
]

# The path each final status takes, so the history looks real.
PATH = {
    "submitted":    [],
    "under_review": ["under_review"],
    "approved":     ["under_review", "approved"],
    "rejected":     ["under_review", "rejected"],
    "disbursed":    ["under_review", "approved", "disbursed"],
}
REMARKS = {
    "under_review": "Picked up for review. Documents being checked.",
    "approved":     "All documents verified. Approved as requested.",
    "rejected":     "CIBIL score below the minimum for a personal loan.",
    "disbursed":    "Funds transferred to the applicant's account.",
}


def ensure_admin(db) -> bool:
    """
    Create the System Administrator if it isn't there yet (Piece 27).

    It is kept apart from the rest of the seed on purpose. main() stops early
    when the demo data already exists, so an admin created inside that part
    would never reach a database seeded before Piece 27. This runs first, every
    time, and does nothing if the account already exists. It returns True only
    when it created one.
    """
    if db.query(User).filter(User.email == ADMIN_EMAIL).first():
        return False
    # Seeded, never registered: the register address refuses this role (T-115).
    db.add(User(name="System Administrator", email=ADMIN_EMAIL,
                hashed_password=hash_password(ADMIN_PW), role=UserRole.admin))
    db.commit()
    return True


def main() -> None:
    init_db()
    db = SessionLocal()

    if ensure_admin(db):
        print(f"admin: {ADMIN_EMAIL} (system administrator)")

    if db.query(User).filter(User.email == "anita@bank.com").first():
        print("Seed data already present. Nothing else to do.")
        print(f"  admin     {ADMIN_EMAIL}   {ADMIN_PW}")
        return

    # ---- Bank staff. The manager is seeded, never self-registered (D-07). ----
    manager = User(name="Anita Krishnan", email="anita@bank.com",
                   hashed_password=hash_password(MANAGER_PW), role=UserRole.branch_manager)
    officer = User(name="Rajan Mehta", email="rajan@bank.com",
                   hashed_password=hash_password(OFFICER_PW), role=UserRole.loan_officer)
    db.add_all([manager, officer])
    db.commit()
    db.refresh(manager)
    db.refresh(officer)
    print(f"staff: {manager.email} (manager), {officer.email} (officer)")

    # ---- Customers, through the real signup so each gets a login and a profile. ----
    applicant_by_email = {}
    users_by_email = {}
    for name, email, phone, income, employment, cibil, dob, years, existing in CUSTOMERS:
        user = auth_service.signup_applicant(db, ApplicantSignupRequest(
            name=name, email=email, password=CUSTOMER_PW, phone=phone,
            annual_income=income, employment_status=employment, credit_score=cibil,
            date_of_birth=dob, years_with_employer=years, existing_monthly_emi=existing,
        ))
        users_by_email[email] = user
        from app.models import Applicant
        applicant_by_email[email] = db.query(Applicant).filter(Applicant.email == email).one()
        print(f"customer: {name} <{email}>")

    # ---- Applications, submitted by the customer, moved along by staff. ----
    for email, loan_type, amount, tenure, purpose, final, docs, days_ago in APPLICATIONS:
        customer = users_by_email[email]
        applicant = applicant_by_email[email]
        application = application_service.create_application(
            db, CreateApplicationSchema(applicant_id=applicant.id, loan_type=loan_type,
                                        amount_requested=amount, tenure_months=tenure, purpose=purpose),
            user=customer,
        )
        for doc_type, verified in docs:
            doc = document_service.add_document(
                db, CreateDocumentSchema(application_id=application.id, doc_type=doc_type,
                                         file_name=f"{doc_type}_{applicant.name.split()[0].lower()}.pdf"),
                user=customer,
            )
            if verified:
                document_service.verify_document(db, application.id, doc.id, user=officer)
        for step in PATH[final]:
            actor = manager if step == "disbursed" else officer
            application_service.update_status(db, application.id, ApplicationStatus(step),
                                              REMARKS[step], user=actor)

        if days_ago:
            # Backdate it so the pipeline has a realistic spread of ages, with
            # a couple of files genuinely overdue. Done last, because every
            # status change above refreshes updated_at (the column has
            # onupdate=func.now()), and the morning briefing measures an
            # approved application's staleness from updated_at.
            #
            # SQLite stores naive datetimes that are really UTC (T-39), so
            # this writes naive UTC to match what the database itself does.
            backdated = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days_ago)
            application.submitted_at = backdated
            application.updated_at = backdated
            db.commit()

        aged = f", submitted {days_ago}d ago" if days_ago else ""
        print(f"application #{application.id}: {applicant.name}, {loan_type} {amount:,} / {tenure} mo -> {final}{aged}")

    activity_rows = db.query(ActivityLog).count()
    print(f"\nDone. {activity_rows} activity rows recorded along the way.")
    print("\nLogins:")
    print(f"  admin     {ADMIN_EMAIL}   {ADMIN_PW}")
    print(f"  manager   anita@bank.com   {MANAGER_PW}")
    print(f"  officer   rajan@bank.com   {OFFICER_PW}")
    print(f"  customer  priya@example.com (and the others)   {CUSTOMER_PW}")


if __name__ == "__main__":
    main()
