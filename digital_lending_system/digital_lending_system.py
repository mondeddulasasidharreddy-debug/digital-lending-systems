"""
Digital Lending System - simple base project
--------------------------------------------
Features
  Borrower : register, login, apply for loan, view loans, pay EMI, view schedule
  Admin    : view pending applications, approve / reject, view all loans
Tech     : Python 3 (standard library only) + SQLite
Run      : python digital_lending_system.py
Admin    : username 'admin'  password 'admin123'  (created automatically)
"""
import sqlite3
import hashlib
import os
from datetime import date

DB_FILE = "lending.db"
INTEREST_RATE = 12.0          # annual % (flat default for this base version)
MAX_INCOME_MULTIPLE = 10      # eligibility: loan <= 10 x monthly income
MIN_TENURE, MAX_TENURE = 3, 60


# ---------------------------------------------------------------- database
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            salt TEXT NOT NULL,
            pwd_hash TEXT NOT NULL,
            monthly_income REAL DEFAULT 0,
            role TEXT NOT NULL DEFAULT 'borrower'
        );
        CREATE TABLE IF NOT EXISTS loans(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            tenure INTEGER NOT NULL,
            rate REAL NOT NULL,
            emi REAL NOT NULL,
            purpose TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            paid_installments INTEGER NOT NULL DEFAULT 0,
            applied_on TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            loan_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            paid_on TEXT NOT NULL,
            FOREIGN KEY(loan_id) REFERENCES loans(id)
        );
        """)
        if not db.execute("SELECT 1 FROM users WHERE username='admin'").fetchone():
            salt, h = hash_password("admin123")
            db.execute("INSERT INTO users(username,full_name,salt,pwd_hash,role)"
                       " VALUES('admin','System Admin',?,?,'admin')", (salt, h))


# ---------------------------------------------------------------- helpers
def hash_password(password, salt=None):
    salt = salt or os.urandom(16).hex()
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return salt, h.hex()


def calc_emi(principal, annual_rate, months):
    r = annual_rate / 12 / 100
    if r == 0:
        return principal / months
    f = (1 + r) ** months
    return principal * r * f / (f - 1)


def ask_float(prompt):
    try:
        return float(input(prompt))
    except ValueError:
        return None


def ask_int(prompt):
    try:
        return int(input(prompt))
    except ValueError:
        return None


def money(x):
    return f"Rs. {x:,.2f}"


def print_loans(rows):
    if not rows:
        print("  (no loans found)")
        return
    print(f"  {'ID':<4}{'Amount':>14}{'Months':>8}{'EMI':>12}{'Paid':>8}  {'Status':<10}Borrower")
    for r in rows:
        name = r["full_name"] if "full_name" in r.keys() else ""
        print(f"  {r['id']:<4}{r['amount']:>14,.2f}{r['tenure']:>8}{r['emi']:>12,.2f}"
              f"{str(r['paid_installments']) + '/' + str(r['tenure']):>8}  {r['status']:<10}{name}")


# ---------------------------------------------------------------- auth
def register():
    print("\n--- Register ---")
    username = input("Username: ").strip()
    full_name = input("Full name: ").strip()
    password = input("Password (min 6 chars): ")
    income = ask_float("Monthly income: ")
    if not username or not full_name or len(password) < 6 or income is None or income <= 0:
        print("Invalid details. Registration failed.")
        return
    salt, h = hash_password(password)
    try:
        with get_db() as db:
            db.execute("INSERT INTO users(username,full_name,salt,pwd_hash,monthly_income)"
                       " VALUES(?,?,?,?,?)", (username, full_name, salt, h, income))
        print("Registration successful. You can log in now.")
    except sqlite3.IntegrityError:
        print("Username already taken.")


def login():
    print("\n--- Login ---")
    username = input("Username: ").strip()
    password = input("Password: ")
    with get_db() as db:
        user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if user:
        _, h = hash_password(password, user["salt"])
        if h == user["pwd_hash"]:
            print(f"Welcome, {user['full_name']}!")
            return user
    print("Invalid username or password.")
    return None


# ---------------------------------------------------------------- borrower
def apply_loan(user):
    print("\n--- Apply for Loan ---")
    limit = user["monthly_income"] * MAX_INCOME_MULTIPLE
    print(f"Your eligible limit: {money(limit)}  |  Interest: {INTEREST_RATE}% p.a.")
    amount = ask_float("Loan amount: ")
    tenure = ask_int(f"Tenure in months ({MIN_TENURE}-{MAX_TENURE}): ")
    purpose = input("Purpose: ").strip()
    if amount is None or tenure is None or amount <= 0:
        print("Invalid input.")
        return
    if amount > limit:
        print("Amount exceeds your eligibility limit. Application rejected.")
        return
    if not MIN_TENURE <= tenure <= MAX_TENURE:
        print("Invalid tenure.")
        return
    emi = calc_emi(amount, INTEREST_RATE, tenure)
    print(f"Your EMI would be {money(emi)} for {tenure} months "
          f"(total {money(emi * tenure)}).")
    if input("Submit application? (y/n): ").lower() != "y":
        return
    with get_db() as db:
        db.execute("INSERT INTO loans(user_id,amount,tenure,rate,emi,purpose,applied_on)"
                   " VALUES(?,?,?,?,?,?,?)",
                   (user["id"], amount, tenure, INTEREST_RATE, emi, purpose, str(date.today())))
    print("Application submitted. Waiting for admin approval.")


def my_loans(user):
    with get_db() as db:
        rows = db.execute("SELECT * FROM loans WHERE user_id=? ORDER BY id", (user["id"],)).fetchall()
    print("\n--- My Loans ---")
    print_loans(rows)
    return rows


def pay_emi(user):
    rows = [r for r in my_loans(user) if r["status"] == "APPROVED"]
    if not rows:
        print("No active loans to pay.")
        return
    loan_id = ask_int("Enter loan ID to pay EMI: ")
    loan = next((r for r in rows if r["id"] == loan_id), None)
    if not loan:
        print("Invalid loan ID.")
        return
    print(f"EMI due: {money(loan['emi'])}")
    if input("Confirm payment? (y/n): ").lower() != "y":
        return
    paid = loan["paid_installments"] + 1
    status = "CLOSED" if paid >= loan["tenure"] else "APPROVED"
    with get_db() as db:
        db.execute("INSERT INTO payments(loan_id,amount,paid_on) VALUES(?,?,?)",
                   (loan["id"], loan["emi"], str(date.today())))
        db.execute("UPDATE loans SET paid_installments=?, status=? WHERE id=?",
                   (paid, status, loan["id"]))
    print("Payment successful." + (" Loan fully repaid - CLOSED!" if status == "CLOSED" else ""))


def schedule(user):
    rows = my_loans(user)
    loan_id = ask_int("Enter loan ID for repayment schedule: ")
    loan = next((r for r in rows if r["id"] == loan_id), None)
    if not loan:
        print("Invalid loan ID.")
        return
    balance, r = loan["amount"], loan["rate"] / 12 / 100
    print(f"\n  {'No':<4}{'EMI':>12}{'Interest':>12}{'Principal':>12}{'Balance':>14}  Status")
    for i in range(1, loan["tenure"] + 1):
        interest = balance * r
        principal = loan["emi"] - interest
        balance = max(balance - principal, 0)
        st = "PAID" if i <= loan["paid_installments"] else "DUE"
        print(f"  {i:<4}{loan['emi']:>12,.2f}{interest:>12,.2f}{principal:>12,.2f}{balance:>14,.2f}  {st}")


def borrower_menu(user):
    while True:
        print("\n=== Borrower Menu ===\n1. Apply for loan\n2. My loans\n"
              "3. Pay EMI\n4. Repayment schedule\n5. Logout")
        c = input("Choice: ").strip()
        if c == "1":
            apply_loan(user)
        elif c == "2":
            my_loans(user)
        elif c == "3":
            pay_emi(user)
        elif c == "4":
            schedule(user)
        elif c == "5":
            break
        else:
            print("Invalid choice.")


# ---------------------------------------------------------------- admin
def list_loans(status=None):
    q = "SELECT l.*, u.full_name FROM loans l JOIN users u ON u.id=l.user_id"
    args = ()
    if status:
        q += " WHERE l.status=?"
        args = (status,)
    with get_db() as db:
        rows = db.execute(q + " ORDER BY l.id", args).fetchall()
    print_loans(rows)
    return rows


def review_pending():
    print("\n--- Pending Applications ---")
    rows = list_loans("PENDING")
    if not rows:
        return
    loan_id = ask_int("Enter loan ID to review (0 to go back): ")
    if not loan_id or not any(r["id"] == loan_id for r in rows):
        return
    decision = input("Approve (a) or Reject (r)? ").lower()
    new = {"a": "APPROVED", "r": "REJECTED"}.get(decision)
    if not new:
        print("Invalid choice.")
        return
    with get_db() as db:
        db.execute("UPDATE loans SET status=? WHERE id=?", (new, loan_id))
    print(f"Loan {loan_id} marked {new}.")


def admin_menu():
    while True:
        print("\n=== Admin Menu ===\n1. Review pending applications\n"
              "2. View all loans\n3. Logout")
        c = input("Choice: ").strip()
        if c == "1":
            review_pending()
        elif c == "2":
            print("\n--- All Loans ---")
            list_loans()
        elif c == "3":
            break
        else:
            print("Invalid choice.")


# ---------------------------------------------------------------- main
def main():
    init_db()
    while True:
        print("\n===== DIGITAL LENDING SYSTEM =====\n1. Register\n2. Login\n3. Exit")
        c = input("Choice: ").strip()
        if c == "1":
            register()
        elif c == "2":
            user = login()
            if user:
                admin_menu() if user["role"] == "admin" else borrower_menu(user)
        elif c == "3":
            print("Goodbye!")
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
