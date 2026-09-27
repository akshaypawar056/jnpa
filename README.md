# Project Expense Manager v2

A local-network Flask + SQLite application for project budgets, employee travel, advances, expense claims, receipts, two-stage approvals, reimbursements, audit trail and Excel MIS.

## Windows installation
1. Install Python 3.11+ and ensure `python` is on PATH.
2. Open Command Prompt in this folder.
3. Run:
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   python -m pip install -r requirements.txt
   python app.py
   ```
4. Open `http://localhost:5000`.
5. For other PCs on the LAN, open `http://SERVER-IP:5000` after allowing TCP 5000 in Windows Firewall.

## Demo accounts
- Admin: `admin` / `Admin@123`
- Manager: `manager` / `Manager@123`
- Employee: `employee` / `Employee@123`

Change these passwords before production use.

## Workflow
Employee creates travel request -> optional advance -> expense claim with receipt -> Manager approval -> Finance/Admin approval -> reimbursement. Project actuals exclude rejected claims and are compared with budget.

## Main v2 additions
- Project budget vs actual and utilization
- Employee master
- Travel requests
- Travel advances and paid tracking
- Expense claim numbers
- Receipt upload
- Manager -> Finance -> Reimbursement lifecycle
- Audit trail
- Excel MIS with Expenses, Travel, Advances and Projects

## Production notes
This is a practical local-network prototype, not a hardened enterprise deployment. For production, put it behind IIS/reverse proxy or a production WSGI server, use PostgreSQL/SQL Server, HTTPS, proper password/secret management, scheduled database backups, antivirus/attachment scanning, file-size/type controls, CSRF protection, and granular approval permissions.
