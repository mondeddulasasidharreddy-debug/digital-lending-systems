# Digital Lending System

A simple console-based loan lending project in Python 3 with SQLite (no external libraries needed).

## Run
    python digital_lending_system.py

## Default admin login
    Username: admin
    Password: admin123

## Features
- Borrower: register, login, apply for a loan, view loans, pay EMI, view repayment schedule
- Admin: review pending applications (approve / reject), view all loans
- Passwords stored as salted PBKDF2 hashes
- EMI formula: P * r * (1+r)^n / ((1+r)^n - 1), r = annual rate / 12 / 100

## Rules (editable at the top of the file)
- Interest rate: 12% p.a.
- Eligibility: loan <= 10 x monthly income
- Tenure: 3 to 60 months

## Database
`lending.db` is created automatically on first run (tables: users, loans, payments).
