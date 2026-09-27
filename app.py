from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, date
from openpyxl import Workbook
from io import BytesIO
import os, uuid

BASE=os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER=os.path.join(BASE,'uploads'); os.makedirs(UPLOAD_FOLDER,exist_ok=True)
app=Flask(__name__)
app.config.update(SECRET_KEY=os.environ.get('SECRET_KEY','change-this-secret-in-production'),SQLALCHEMY_DATABASE_URI='sqlite:///'+os.path.join(BASE,'expense_manager.db'),SQLALCHEMY_TRACK_MODIFICATIONS=False,UPLOAD_FOLDER=UPLOAD_FOLDER,MAX_CONTENT_LENGTH=15*1024*1024)
db=SQLAlchemy(app)

class User(db.Model):
    id=db.Column(db.Integer,primary_key=True); username=db.Column(db.String(80),unique=True,nullable=False); password_hash=db.Column(db.String(255),nullable=False); role=db.Column(db.String(20),nullable=False,default='employee'); employee_id=db.Column(db.Integer,db.ForeignKey('employee.id')); active=db.Column(db.Boolean,default=True)
class Employee(db.Model):
    id=db.Column(db.Integer,primary_key=True); code=db.Column(db.String(40),unique=True,nullable=False); name=db.Column(db.String(120),nullable=False); department=db.Column(db.String(100)); designation=db.Column(db.String(100)); email=db.Column(db.String(150)); phone=db.Column(db.String(40)); manager=db.Column(db.String(120)); active=db.Column(db.Boolean,default=True)
class Project(db.Model):
    id=db.Column(db.Integer,primary_key=True); code=db.Column(db.String(50),unique=True,nullable=False); name=db.Column(db.String(160),nullable=False); client=db.Column(db.String(160)); manager=db.Column(db.String(120)); start_date=db.Column(db.Date); end_date=db.Column(db.Date); budget=db.Column(db.Float,default=0); status=db.Column(db.String(30),default='Active')
class Travel(db.Model):
    id=db.Column(db.Integer,primary_key=True); employee_id=db.Column(db.Integer,db.ForeignKey('employee.id'),nullable=False); project_id=db.Column(db.Integer,db.ForeignKey('project.id'),nullable=False); travel_date=db.Column(db.Date,nullable=False); return_date=db.Column(db.Date); origin=db.Column(db.String(120)); destination=db.Column(db.String(120)); purpose=db.Column(db.String(255)); mode=db.Column(db.String(60)); hotel=db.Column(db.String(160)); advance=db.Column(db.Float,default=0); status=db.Column(db.String(30),default='Pending'); manager_note=db.Column(db.String(255)); employee=db.relationship('Employee'); project=db.relationship('Project')
class Expense(db.Model):
    id=db.Column(db.Integer,primary_key=True); claim_no=db.Column(db.String(40),unique=True,nullable=False); employee_id=db.Column(db.Integer,db.ForeignKey('employee.id'),nullable=False); project_id=db.Column(db.Integer,db.ForeignKey('project.id'),nullable=False); travel_id=db.Column(db.Integer,db.ForeignKey('travel.id')); expense_date=db.Column(db.Date,nullable=False); category=db.Column(db.String(80),nullable=False); description=db.Column(db.String(255)); amount=db.Column(db.Float,default=0); gst=db.Column(db.Float,default=0); payment_method=db.Column(db.String(50)); receipt=db.Column(db.String(255)); status=db.Column(db.String(30),default='Pending Manager'); manager_note=db.Column(db.String(255)); finance_note=db.Column(db.String(255)); employee=db.relationship('Employee'); project=db.relationship('Project'); travel=db.relationship('Travel')
class Advance(db.Model):
    id=db.Column(db.Integer,primary_key=True); advance_no=db.Column(db.String(40),unique=True,nullable=False); employee_id=db.Column(db.Integer,db.ForeignKey('employee.id'),nullable=False); project_id=db.Column(db.Integer,db.ForeignKey('project.id'),nullable=False); travel_id=db.Column(db.Integer,db.ForeignKey('travel.id')); request_date=db.Column(db.Date,default=date.today); amount=db.Column(db.Float,default=0); purpose=db.Column(db.String(255)); status=db.Column(db.String(30),default='Pending Manager'); paid_date=db.Column(db.Date); employee=db.relationship('Employee'); project=db.relationship('Project'); travel=db.relationship('Travel')
class AuditLog(db.Model):
    id=db.Column(db.Integer,primary_key=True); created_at=db.Column(db.DateTime,default=datetime.utcnow); username=db.Column(db.String(80)); action=db.Column(db.String(120)); entity=db.Column(db.String(80)); entity_id=db.Column(db.Integer); details=db.Column(db.String(500))

def today(): return date.today()
def d(v): return datetime.strptime(v,'%Y-%m-%d').date() if v else None
def current_user(): return User.query.get(session['user_id']) if session.get('user_id') else None
def money(v): return float(v or 0)
def audit(action,entity,entity_id=None,details=''):
    u=current_user(); db.session.add(AuditLog(username=u.username if u else 'system',action=action,entity=entity,entity_id=entity_id,details=details))

def allowed_roles(*roles):
    def deco(f):
        @wraps(f)
        def w(*a,**k):
            u=current_user()
            if not u: return redirect(url_for('login'))
            if u.role not in roles: flash('You do not have permission for this action.','danger'); return redirect(url_for('dashboard'))
            return f(*a,**k)
        return w
    return deco

def login_required(f): return allowed_roles('admin','manager','employee')(f)

@app.context_processor
def globals_(): return {'today':today(),'logged_user':current_user()}

@app.route('/login',methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(username=request.form.get('username','').strip()).first()
        if u and u.active and check_password_hash(u.password_hash,request.form.get('password','')): session['user_id']=u.id; audit('LOGIN','User',u.id); db.session.commit(); return redirect(url_for('dashboard'))
        flash('Invalid username or password.','danger')
    return render_template('login.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    u=current_user(); eq=Expense.query
    tq=Travel.query; aq=Advance.query
    if u.role=='employee': eq=eq.filter_by(employee_id=u.employee_id); tq=tq.filter_by(employee_id=u.employee_id); aq=aq.filter_by(employee_id=u.employee_id)
    expenses=eq.all(); travels=tq.all(); advances=aq.all(); projects=Project.query.all()
    total=sum(e.amount+e.gst for e in expenses); approved=sum(e.amount+e.gst for e in expenses if e.status in ('Approved','Reimbursed')); pending=sum(e.amount+e.gst for e in expenses if e.status not in ('Approved','Reimbursed','Rejected')); reimbursed=sum(e.amount+e.gst for e in expenses if e.status=='Reimbursed')
    budgets=sum(p.budget or 0 for p in projects); bycat={}
    for e in expenses: bycat[e.category]=bycat.get(e.category,0)+(e.amount+e.gst)
    return render_template('dashboard.html',total=total,approved=approved,pending=pending,reimbursed=reimbursed,budgets=budgets,employees=Employee.query.filter_by(active=True).count(),travel_count=len(travels),advance_total=sum(a.amount for a in advances),bycat=bycat,recent=eq.order_by(Expense.id.desc()).limit(8).all(),projects=projects)

@app.route('/projects',methods=['GET','POST'])
@allowed_roles('admin','manager')
def projects():
    if request.method=='POST':
        try:
            p=Project(code=request.form['code'].strip(),name=request.form['name'].strip(),client=request.form.get('client'),manager=request.form.get('manager'),start_date=d(request.form.get('start_date')),end_date=d(request.form.get('end_date')),budget=money(request.form.get('budget')),status=request.form.get('status','Active')); db.session.add(p); db.session.flush(); audit('CREATE','Project',p.id,p.code); db.session.commit(); flash('Project added.','success')
        except Exception as e: db.session.rollback(); flash('Could not add project: '+str(e),'danger')
        return redirect(url_for('projects'))
    rows=[]
    for p in Project.query.order_by(Project.id.desc()).all():
        actual=sum(e.amount+e.gst for e in Expense.query.filter_by(project_id=p.id).filter(Expense.status!='Rejected').all()); rows.append((p,actual,max((p.budget or 0)-actual,0),((actual/(p.budget or 1))*100 if p.budget else 0)))
    return render_template('projects.html',rows=rows)

@app.route('/employees',methods=['GET','POST'])
@allowed_roles('admin','manager')
def employees():
    if request.method=='POST':
        try:
            e=Employee(code=request.form['code'].strip(),name=request.form['name'].strip(),department=request.form.get('department'),designation=request.form.get('designation'),email=request.form.get('email'),phone=request.form.get('phone'),manager=request.form.get('manager')); db.session.add(e); db.session.flush(); audit('CREATE','Employee',e.id,e.code); db.session.commit(); flash('Employee added.','success')
        except Exception as ex: db.session.rollback(); flash('Could not add employee: '+str(ex),'danger')
        return redirect(url_for('employees'))
    return render_template('employees.html',employees=Employee.query.order_by(Employee.name).all())

@app.route('/travel',methods=['GET','POST'])
@login_required
def travel():
    u=current_user()
    if request.method=='POST':
        emp_id=int(request.form['employee_id']) if u.role in ('admin','manager') else u.employee_id
        t=Travel(employee_id=emp_id,project_id=int(request.form['project_id']),travel_date=d(request.form['travel_date']),return_date=d(request.form.get('return_date')),origin=request.form.get('origin'),destination=request.form.get('destination'),purpose=request.form.get('purpose'),mode=request.form.get('mode'),hotel=request.form.get('hotel'),advance=money(request.form.get('advance')))
        db.session.add(t); db.session.flush(); audit('CREATE','Travel',t.id,f'{t.origin} to {t.destination}'); db.session.commit(); flash('Travel request submitted.','success'); return redirect(url_for('travel'))
    q=Travel.query.order_by(Travel.id.desc());
    if u.role=='employee': q=q.filter_by(employee_id=u.employee_id)
    return render_template('travel.html',travels=q.all(),employees=Employee.query.filter_by(active=True).all(),projects=Project.query.filter_by(status='Active').all(),u=u)

@app.route('/advances',methods=['GET','POST'])
@login_required
def advances():
    u=current_user()
    if request.method=='POST':
        emp_id=int(request.form['employee_id']) if u.role in ('admin','manager') else u.employee_id
        a=Advance(advance_no='ADV-'+uuid.uuid4().hex[:8].upper(),employee_id=emp_id,project_id=int(request.form['project_id']),travel_id=int(request.form['travel_id']) if request.form.get('travel_id') else None,amount=money(request.form.get('amount')),purpose=request.form.get('purpose'))
        db.session.add(a); db.session.flush(); audit('CREATE','Advance',a.id,a.advance_no); db.session.commit(); flash('Advance request submitted.','success'); return redirect(url_for('advances'))
    q=Advance.query.order_by(Advance.id.desc());
    if u.role=='employee': q=q.filter_by(employee_id=u.employee_id)
    return render_template('advances.html',advances=q.all(),employees=Employee.query.filter_by(active=True).all(),projects=Project.query.filter_by(status='Active').all(),travels=Travel.query.order_by(Travel.id.desc()).all(),u=u)

@app.route('/expenses',methods=['GET','POST'])
@login_required
def expenses():
    u=current_user()
    if request.method=='POST':
        emp_id=int(request.form['employee_id']) if u.role in ('admin','manager') else u.employee_id
        f=request.files.get('receipt'); fn=None
        if f and f.filename:
            ext=os.path.splitext(secure_filename(f.filename))[1].lower(); fn=uuid.uuid4().hex+ext; f.save(os.path.join(UPLOAD_FOLDER,fn))
        e=Expense(claim_no='CLM-'+uuid.uuid4().hex[:8].upper(),employee_id=emp_id,project_id=int(request.form['project_id']),travel_id=int(request.form['travel_id']) if request.form.get('travel_id') else None,expense_date=d(request.form['expense_date']),category=request.form['category'],description=request.form.get('description'),amount=money(request.form.get('amount')),gst=money(request.form.get('gst')),payment_method=request.form.get('payment_method'),receipt=fn)
        db.session.add(e); db.session.flush(); audit('CREATE','Expense',e.id,e.claim_no); db.session.commit(); flash('Expense claim submitted.','success'); return redirect(url_for('expenses'))
    q=Expense.query.order_by(Expense.id.desc());
    if u.role=='employee': q=q.filter_by(employee_id=u.employee_id)
    return render_template('expenses.html',expenses=q.all(),employees=Employee.query.filter_by(active=True).all(),projects=Project.query.filter_by(status='Active').all(),travels=Travel.query.order_by(Travel.id.desc()).all(),u=u)

@app.route('/approvals')
@allowed_roles('admin','manager')
def approvals():
    return render_template('approvals.html',expenses=Expense.query.filter(Expense.status.in_(['Pending Manager','Pending Finance'])).order_by(Expense.id.desc()).all(),travels=Travel.query.filter_by(status='Pending').order_by(Travel.id.desc()).all(),advances=Advance.query.filter_by(status='Pending Manager').order_by(Advance.id.desc()).all())

def set_status(obj,status,note='',kind=''):
    obj.status=status
    if isinstance(obj,Expense):
        if status in ('Rejected','Approved'): obj.manager_note=note
        elif status=='Reimbursed': obj.finance_note=note
    elif hasattr(obj,'manager_note'): obj.manager_note=note
    audit('STATUS',kind or obj.__class__.__name__,obj.id,f'{status}: {note}')
    db.session.commit()

@app.route('/expense/<int:id>/status/<status>',methods=['POST'])
@allowed_roles('admin','manager')
def expense_status(id,status):
    e=Expense.query.get_or_404(id); status_map={'approve-manager':'Pending Finance','approve-finance':'Approved','reject':'Rejected','reimburse':'Reimbursed'}; ns=status_map.get(status)
    if not ns: flash('Invalid action','danger'); return redirect(url_for('approvals'))
    if status=='approve-finance' and current_user().role!='admin': flash('Finance approval is restricted to admin in v2.','danger'); return redirect(url_for('approvals'))
    if status=='reimburse' and current_user().role!='admin': flash('Reimbursement is restricted to admin.','danger'); return redirect(url_for('approvals'))
    set_status(e,ns,request.form.get('note',''),'Expense'); flash('Expense updated.','success'); return redirect(url_for('approvals'))

@app.route('/travel/<int:id>/status/<status>',methods=['POST'])
@allowed_roles('admin','manager')
def travel_status(id,status):
    t=Travel.query.get_or_404(id); ns={'approve':'Approved','reject':'Rejected'}.get(status)
    if not ns: return redirect(url_for('approvals'))
    set_status(t,ns,request.form.get('note',''),'Travel'); flash('Travel updated.','success'); return redirect(url_for('approvals'))

@app.route('/advance/<int:id>/status/<status>',methods=['POST'])
@allowed_roles('admin','manager')
def advance_status(id,status):
    a=Advance.query.get_or_404(id); ns={'approve':'Approved','reject':'Rejected','pay':'Paid'}.get(status)
    if not ns: return redirect(url_for('approvals'))
    if status=='pay' and current_user().role!='admin': flash('Advance payment is restricted to admin.','danger'); return redirect(url_for('approvals'))
    if ns=='Paid': a.paid_date=date.today()
    set_status(a,ns,request.form.get('note',''),'Advance'); flash('Advance updated.','success'); return redirect(url_for('approvals'))

@app.route('/audit')
@allowed_roles('admin')
def audit_page(): return render_template('audit.html',logs=AuditLog.query.order_by(AuditLog.id.desc()).limit(300).all())
@app.route('/uploads/<path:filename>')
@login_required
def uploads(filename): return send_from_directory(UPLOAD_FOLDER,filename,as_attachment=True)

@app.route('/reports/export')
@login_required
def export_report():
    wb=Workbook(); ws=wb.active; ws.title='Expenses'; ws.append(['Claim No','Date','Employee','Project','Category','Description','Amount','GST','Total','Payment Method','Status','Receipt'])
    for e in Expense.query.order_by(Expense.expense_date).all(): ws.append([e.claim_no,e.expense_date,e.employee.name,e.project.code,e.category,e.description,e.amount,e.gst,e.amount+e.gst,e.payment_method,e.status,e.receipt or ''])
    ws2=wb.create_sheet('Travel'); ws2.append(['ID','Travel Date','Return Date','Employee','Project','From','To','Purpose','Mode','Hotel','Advance','Status'])
    for t in Travel.query.order_by(Travel.travel_date).all(): ws2.append([t.id,t.travel_date,t.return_date,t.employee.name,t.project.code,t.origin,t.destination,t.purpose,t.mode,t.hotel,t.advance,t.status])
    ws3=wb.create_sheet('Advances'); ws3.append(['Advance No','Request Date','Employee','Project','Amount','Purpose','Status','Paid Date'])
    for a in Advance.query.order_by(Advance.request_date).all(): ws3.append([a.advance_no,a.request_date,a.employee.name,a.project.code,a.amount,a.purpose,a.status,a.paid_date])
    ws4=wb.create_sheet('Projects'); ws4.append(['Code','Project','Client','Manager','Budget','Actual','Variance','Utilization %','Status'])
    for p in Project.query.all():
        actual=sum(e.amount+e.gst for e in Expense.query.filter_by(project_id=p.id).filter(Expense.status!='Rejected').all()); ws4.append([p.code,p.name,p.client,p.manager,p.budget,actual,(p.budget or 0)-actual,(actual/(p.budget or 1))*100 if p.budget else 0,p.status])
    for sh in wb.worksheets:
        sh.freeze_panes='A2'; sh.auto_filter.ref=sh.dimensions
        for col in sh.columns:
            letter=col[0].column_letter; sh.column_dimensions[letter].width=min(max(max(len(str(c.value or '')) for c in col)+2,10),36)
    bio=BytesIO(); wb.save(bio); bio.seek(0); return send_file(bio,as_attachment=True,download_name='project_expense_mis.xlsx',mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.cli.command('init-db')
def init_db(): initialize(); print('Database initialized.')

def initialize():
    db.create_all()
    if not User.query.filter_by(username='admin').first(): db.session.add(User(username='admin',password_hash=generate_password_hash('Admin@123'),role='admin'))
    if not User.query.filter_by(username='manager').first(): db.session.add(User(username='manager',password_hash=generate_password_hash('Manager@123'),role='manager'))
    if not Employee.query.filter_by(code='EMP001').first():
        e=Employee(code='EMP001',name='Demo Employee',department='Projects',designation='Engineer',email='demo@example.com'); db.session.add(e); db.session.flush(); db.session.add(User(username='employee',password_hash=generate_password_hash('Employee@123'),role='employee',employee_id=e.id))
    if not Project.query.first(): db.session.add(Project(code='PRJ-001',name='Demo CCTV Project',client='Demo Client',manager='Demo Manager',budget=1000000,status='Active'))
    db.session.commit()
with app.app_context(): initialize()
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.environ.get('PORT',5000)),debug=True)
