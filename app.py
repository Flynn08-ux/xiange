import os, re, random, uuid
from datetime import timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from database import (
    init_db, init_admin, login_user, check_blacklist, 
    add_teacher, get_teacher, get_teacher_by_id, get_all_teachers,
    get_pending_lessons_for_teacher, get_verified_lessons_for_teacher,
    get_last_lesson_for_appointment, end_lesson,
    get_teacher_stats, delete_teacher, get_unpaid_fee_teachers, pay_info_fee,
    add_parent, get_parent, get_parent_appointments, record_late_payment,
    admin_login, get_admin, get_all_admins, add_admin, delete_admin,
    get_admin_stats, get_all_teachers_admin, get_all_parents_admin,
    get_all_appointments_admin, get_blacklist, add_to_blacklist, remove_from_blacklist,
    create_appointment, get_appointment, update_appointment_status,
    get_teacher_appointments, auto_pay_overdue,
    add_feedback, get_feedback_for_teacher, get_feedback_for_parent,
    get_available_earnings, create_withdrawal, get_withdrawals, process_withdrawal,
    get_teacher_coupons, get_stats,
    save_sms_code, verify_sms_code, phone_exists, get_user_by_phone_role, update_user_password,
    create_contract, get_contract, add_verification_doc, get_verification_docs,
    update_verification_status, save_payment_account, get_payment_accounts,
    add_notification, get_notifications, get_unread_notification_count,
    mark_notification_read, mark_all_notifications_read, delete_notification,
)
from regions import get_provinces, region_info
from universities import UNIVERSITIES

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "xiange-2024-stable-secret-key")
app.permanent_session_lifetime = timedelta(hours=8)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
@app.before_request
def refresh_session():
    """每次请求刷新会话过期时间"""
    if session.get("user_id") or session.get("admin_id"):
        session.permanent = True

SUBJECTS = [
    "\u8bed\u6587","\u6570\u5b66","\u82f1\u8bed","\u7269\u7406","\u5316\u5b66","\u751f\u7269",
    "\u5386\u53f2","\u5730\u7406","\u653f\u6cbb","\u7f16\u7a0b","\u7f8e\u672f","\u97f3\u4e50",
    "\u94a2\u7434","\u5409\u4ed6","\u5c0f\u63d0\u7434","\u821e\u8e48","\u4e66\u6cd5","\u56f4\u68cb",
    "\u7fbd\u6bdb\u7403","\u6e38\u6cf3","\u6b66\u672f","\u5176\u5b83",
]

GRADES = ["\u5c0f\u5b66\u4e00\u5e74\u7ea7","\u5c0f\u5b66\u4e8c\u5e74\u7ea7","\u5c0f\u5b66\u4e09\u5e74\u7ea7","\u5c0f\u5b66\u56db\u5e74\u7ea7","\u5c0f\u5b66\u4e94\u5e74\u7ea7","\u5c0f\u5b66\u516d\u5e74\u7ea7","\u521d\u4e00","\u521d\u4e8c","\u521d\u4e09","\u9ad8\u4e00","\u9ad8\u4e8c","\u9ad8\u4e09","\u5927\u5b66/\u6210\u4eba"]

def admin_ctx():
    if "admin_id" in session:
        return get_admin(session["admin_id"])
    return None

def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                flash("\u8bf7\u5148\u767b\u5f55", "error")
                return redirect(url_for("login"))
            if role is not None and session.get("role") != role:
                flash("\u6743\u9650\u4e0d\u8db3", "error")
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ── API ──

@app.route("/api/send-sms", methods=["POST"])
def api_send_sms():
    phone = request.form.get("phone","").strip()
    if not phone or len(phone) < 5:
        return jsonify({"error": "手机号无效"}), 400
    code = str(random.randint(100000, 999999))
    save_sms_code(phone, code)
    return jsonify({"message": f"【测试模式】验证码 {code}，已发送到 {phone[:3]}****{phone[-4:]}"})
@app.route("/api/regions")
def api_regions():
    return jsonify(region_info())

# ── Public Pages ──
@app.route("/")
def index():
    stats = get_stats()
    teachers = get_all_teachers(sort="newest")[:6]
    return render_template("index.html", stats=stats, teachers=teachers,
                           subjects=SUBJECTS, provinces=get_provinces(), admin=admin_ctx(),
                           user=session.get("user_id"), role=session.get("role"))

@app.route("/teachers")
def teachers():
    sort = request.args.get("sort","newest")
    search = request.args.get("search","")
    subject = request.args.get("subject","")
    city = request.args.get("city","")
    teachers = get_all_teachers(sort=sort, search=search, subject=subject, city=city)
    return render_template("teachers.html", teachers=teachers, subjects=SUBJECTS,
                           provinces=get_provinces(), sort=sort, search=search,
                           selected_subject=subject, selected_city=city,
                           admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))

@app.route("/teacher/<int:tid>")
def teacher_detail(tid):
    teacher = get_teacher(tid)
    if not teacher:
        flash("\u672a\u627e\u5230\u8be5\u6559\u5e08", "error")
        return redirect(url_for("teachers"))
    subjects = [s.strip() for s in teacher["subjects"].split(",") if s.strip()]
    return render_template("teacher.html", teacher=teacher, subjects=subjects,
                           admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))

@app.route("/health")
def health():
    return "OK", 200


def admin_required(f):
    @wraps(f)
    def wrapper(*a,**k):
        if "admin_id" not in session:
            flash("请先登录管理员","error")
            return redirect(url_for("admin_login"))
        return f(*a,**k)
    return wrapper

def admin_ctx():
    if "admin_id" in session:
        return get_admin(session["admin_id"])
    return None

@app.route("/admin")
@admin_required
def admin_dashboard():
    _adm = admin_ctx()
    _aname = _adm["name"] if _adm else "管理员"
    html = """<!DOCTYPE html><html lang=zh-CN>
<head><meta charset=UTF-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>弦歌 · 管理后台</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:linear-gradient(135deg,#f5f0ff 0%,#e8e0f0 100%);min-height:100vh;font-family:system-ui,-apple-system,sans-serif}
.header{background:linear-gradient(135deg,#6b4fa0,#8b6fbf);color:#fff;padding:20px 28px}
.header h1{font-size:1.5rem;font-weight:600;margin-bottom:4px}
.header p{font-size:.85rem;opacity:.8}
.nav{display:flex;flex-wrap:wrap;gap:4px;padding:12px 28px;background:#fff;border-bottom:1px solid #e0d8ea}
.nav a{padding:8px 14px;border-radius:8px;text-decoration:none;font-size:.85rem;color:#4a3a5a;transition:all .2s}
.nav a:hover{background:#eee8f5;color:#6b4fa0}
.nav a.active{background:#6b4fa0;color:#fff}
.content{max-width:1100px;margin:0 auto;padding:24px 28px}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:16px;margin-bottom:28px}
.stat-card{background:#fff;border:1px solid #e0d8ea;border-radius:14px;padding:24px 20px;text-align:center;transition:transform .15s,box-shadow .15s}
.stat-card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(107,79,160,.12)}
.stat-num{font-size:2rem;font-weight:800;color:#6b4fa0}
.stat-lbl{font-size:.8rem;color:#8a7a9a;margin-top:4px}
.features{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}
.feat-card{background:#fff;border:1px solid #e0d8ea;border-radius:14px;padding:20px;transition:transform .15s,box-shadow .15s}
.feat-card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(107,79,160,.1)}
.feat-card h3{font-size:.95rem;color:#4a3a5a;margin-bottom:8px}
.feat-card p{font-size:.8rem;color:#8a7a9a;line-height:1.5}
.feat-card a{display:inline-block;margin-top:10px;padding:6px 16px;background:linear-gradient(135deg,#6b4fa0,#8b6fbf);color:#fff;border-radius:8px;text-decoration:none;font-size:.8rem}
.feat-card a:hover{opacity:.9}
</style></head><body>
<div class=header><h1>弦歌 · 管理后台</h1><p>欢迎回来，__ANAME__</p></div>
<div class=nav>
<a href=/admin class=active>概览</a>
<a href=/admin/teachers>教师管理</a>
<a href=/admin/parents>家长管理</a>
<a href=/admin/admins>管理员管理</a>
<a href=/admin/appointments>申请管理</a>
<a href=/admin/verification>认证管理</a>
<a href=/admin/fees>费用管理</a>
<a href=/admin/blacklist>黑名单</a>
<a href=/admin/qrcodes>收款码</a>
<a href=/admin/orders>订单</a>
<a href=/admin/logout>退出</a>
</div>
<div class=content>
<div class=stats-grid>
<div class=stat-card><div class=stat-num>0</div><div class=stat-lbl>认证教师</div></div>
<div class=stat-card><div class=stat-num>0</div><div class=stat-lbl>家长用户</div></div>
<div class=stat-card><div class=stat-num>0</div><div class=stat-lbl>已成交</div></div>
<div class=stat-card><div class=stat-num>0</div><div class=stat-lbl>管理员</div></div>
<div class=stat-card><div class=stat-num>0</div><div class=stat-lbl>收入（元）</div></div>
<div class=stat-card><div class=stat-num>0</div><div class=stat-lbl>待提现</div></div>
</div>
<div class=features>
<div class=feat-card><h3>家教中心</h3><p>管理每位教师的教学详情、学生信息、课程记录和收入情况</p><a href=/admin/teachers>进入家教中心</a></div>
<div class=feat-card><h3>家校中心</h3><p>查看家长与学生的学习需求、课程评价和反馈</p><a href=/admin/parents>进入家校中心</a></div>
<div class=feat-card><h3>管理员管理</h3><p>添加、删除管理员，实时查看管理团队</p><a href=/admin/admins>管理管理员</a></div>
<div class=feat-card><h3>费用与提现</h3><p>查看教师信息费、管理提现申请和补贴</p><a href=/admin/fees>查看费用</a></div>
<div class=feat-card><h3>黑名单</h3><p>将违规用户加入黑名单，禁止其操作</p><a href=/admin/blacklist>管理黑名单</a></div>
<div class=feat-card><h3>收款码与订单</h3><p>设置微信、支付宝收款码，确认付款订单</p><a href=/admin/qrcodes>管理收款</a></div>
</div></div></body></html>"""
    html = html.replace("__ANAME__", _aname)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/about")
def about():
    return render_template("about.html", admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))

# ── Auth ──
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        user = login_user(username, password)
        if user:
            if check_blacklist(user["role"], user["ref_id"]):
                flash("\u60a8\u5df2\u88ab\u52a0\u5165\u9ed1\u540d\u5355\uff0c\u65e0\u6cd5\u767b\u5f55", "error")
                return render_template("login.html")
            tok = uuid.uuid4().hex
            db = get_db()
            db.execute("UPDATE users SET session_token=? WHERE id=?", (tok, user["id"]))
            db.commit(); db.close()
            session["user_id"] = user["id"]
            session["user_name"] = user.get("name", username)
            session["role"] = user["role"]
            session["ref_id"] = user["ref_id"]
            session["username"] = username
            session["session_token"] = tok
            session.permanent = True
            if user["role"] == "teacher":
                return redirect(url_for("teacher_center"))
            elif user["role"] == "parent":
                return redirect(url_for("parent_center"))
        flash("\u7528\u6237\u540d\u6216\u5bc6\u7801\u9519\u8bef", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("\u5df2\u9000\u51fa\u767b\u5f55", "info")
    return redirect(url_for("index"))

@app.route("/admin/apply", methods=["GET","POST"])
def admin_apply():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        email = request.form.get("email","").strip()
        reason = request.form.get("reason","").strip()
        if not name or not email:
            flash("请填写姓名和邮箱","error")
        else:
            admins = get_all_admins()
            for a in admins:
                add_notification("admin", a["id"],
                    f"管理员申请：{name}",
                    f"{name}（{email}）申请成为管理员。理由：{reason}",
                    "/admin/admins")
            flash("申请已提交，管理员会尽快处理","success")
        return redirect(url_for("admin_apply"))
    return render_template("admin_apply.html")


# ── Teacher Registration ──
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        data = {
            "username": request.form.get("username","").strip(),
            "password": request.form.get("password","").strip(),
            "name": request.form.get("name","").strip(),
            "email": request.form.get("email","").strip(),
            "phone": request.form.get("phone","").strip(),
            "subjects": ",".join(request.form.getlist("subjects")),
            "education": request.form.get("education","").strip(),
            "university": request.form.get("university","").strip(),
            "experience": request.form.get("experience","").strip(),
            "available": request.form.get("available","").strip(),
            "province": request.form.get("province","").strip(),
            "city": request.form.get("city","").strip(),
            "district": request.form.get("district","").strip(),
            "ref_rate": request.form.get("ref_rate", type=int),
            "bio": request.form.get("bio","").strip(),
        }
        errors = []
        if not data["username"]: errors.append("\u8bf7\u8f93\u5165\u7528\u6237\u540d")
        if not data["password"] or len(data["password"]) < 4: errors.append("\u5bc6\u7801\u81f3\u5c114\u4f4d")
        if not data["name"]: errors.append("\u8bf7\u8f93\u5165\u59d3\u540d")
        if not data["email"] or not re.match(r"[^@]+@[^@]+\.[^@]+", data["email"]): errors.append("\u8bf7\u8f93\u5165\u6709\u6548\u90ae\u7bb1")
        if not data["subjects"]: errors.append("\u8bf7\u81f3\u5c11\u9009\u62e9\u4e00\u4e2a\u79d1\u76ee")
        if errors:
            for e in errors: flash(e, "error")
            return render_template("register.html", subjects=SUBJECTS, provinces=get_provinces(), unis=UNIVERSITIES, data=data), 400
        try:
            tid, err = add_teacher(data)
            if err:
                flash(err, "error")
                return render_template("register.html", subjects=SUBJECTS, provinces=get_provinces(), unis=UNIVERSITIES, data=data), 400
            flash("\u6ce8\u518c\u6210\u529f\uff01\u8bf7\u7ef4\u62a4\u4fe1\u606f\u8d39\u540e\u624d\u80fd\u5f00\u59cb\u63a5\u5355", "success")
            return redirect(url_for("login"))
        except Exception as e:
            flash(f"\u6ce8\u518c\u5931\u8d25\uff1a{e}", "error")
            return render_template("register.html", subjects=SUBJECTS, provinces=get_provinces(), unis=UNIVERSITIES, data=data), 400
    return render_template("register.html", subjects=SUBJECTS, provinces=get_provinces(), unis=UNIVERSITIES)

# ── Parent Registration (via Apply) ──
@app.route("/apply/<int:tid>", methods=["GET","POST"])
def parent_apply(tid):
    teacher = get_teacher(tid)
    if not teacher:
        flash("\u672a\u627e\u5230\u8be5\u6559\u5e08", "error")
        return redirect(url_for("teachers"))
    if request.method == "POST":
        data = {
            "username": request.form.get("username","").strip(),
            "password": request.form.get("password","").strip(),
            "parent_name": request.form.get("parent_name","").strip(),
            "email": request.form.get("email","").strip(),
            "phone": request.form.get("phone","").strip(),
            "student_name": request.form.get("student_name","").strip(),
            "student_grade": request.form.get("student_grade","").strip(),
            "subjects": request.form.get("subjects","").strip(),
            "province": request.form.get("province","").strip(),
            "city": request.form.get("city","").strip(),
            "district": request.form.get("district","").strip(),
            "requirements": request.form.get("requirements","").strip(),
            "budget": request.form.get("budget", type=int),
        }
        errors = []
        if not data["username"]: errors.append("\u8bf7\u8f93\u5165\u7528\u6237\u540d")
        if not data["password"] or len(data["password"]) < 4: errors.append("\u5bc6\u7801\u81f3\u5c114\u4f4d")
        if not data["parent_name"]: errors.append("\u8bf7\u8f93\u5165\u60a8\u7684\u59d3\u540d")
        if not data["email"] or not re.match(r"[^@]+@[^@]+\.[^@]+", data["email"]): errors.append("\u8bf7\u8f93\u5165\u6709\u6548\u90ae\u7bb1")
        if not data["student_name"]: errors.append("\u8bf7\u8f93\u5165\u5b66\u751f\u59d3\u540d")
        if not data["subjects"]: errors.append("\u8bf7\u8f93\u5165\u79d1\u76ee")
        if not data["budget"]: errors.append("\u8bf7\u8f93\u5165\u51fa\u4ef7")
        if errors:
            for e in errors: flash(e, "error")
            return render_template("apply.html", teacher=teacher, provinces=get_provinces(), grades=GRADES, data=data), 400
        try:
            pid, err = add_parent(data)
            if err:
                flash(err, "error")
                return render_template("apply.html", teacher=teacher, provinces=get_provinces(), grades=GRADES, data=data), 400
            aid = create_appointment(tid, pid, data["subjects"], data["budget"])
            flash("\u7533\u8bf7\u5df2\u63d0\u4ea4\uff01\u8bf7\u7b49\u5f85\u8001\u5e08\u786e\u8ba4", "success")
            session["user_id"] = 0; session["user_name"] = "家长"; session["role"] = "parent"; session["ref_id"] = pid
            return redirect(url_for("parent_center"))
        except Exception as e:
            flash(f"\u63d0\u4ea4\u5931\u8d25\uff1a{e}", "error")
            return render_template("apply.html", teacher=teacher, provinces=get_provinces(), grades=GRADES, data=data), 400
    return render_template("apply.html", teacher=teacher, provinces=get_provinces(), grades=GRADES)

# ── Teacher Center ──
@app.route("/teacher/center")
@login_required("teacher")
def teacher_center():
    tid = session["ref_id"]
    teacher = get_teacher(tid)
    if not teacher: flash("\u6559\u5e08\u4fe1\u606f\u4e0d\u5b58\u5728","error"); return redirect(url_for("index"))
    if not teacher["info_fee_paid"]:
        return redirect(url_for("teacher_pay_fee"))
    stats = get_teacher_stats(tid)
    appointments = get_teacher_appointments(tid)
    feedback = get_feedback_for_teacher(tid)
    coupons = get_teacher_coupons(tid)
    available = get_available_earnings(tid)
    subjects = [s.strip() for s in teacher["subjects"].split(",") if s.strip()]
    pending_lessons = get_pending_lessons_for_teacher(tid)
    verified_lessons = get_verified_lessons_for_teacher(tid)
    return render_template("teacher_center.html", teacher=teacher, stats=stats,
                           appointments=appointments, feedback=feedback, coupons=coupons,
                           available=available, subjects=subjects,
                           pending_lessons=pending_lessons, verified_lessons=verified_lessons,
                           admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))

@app.route("/teacher/pay-fee", methods=["GET","POST"])
@login_required("teacher")
def teacher_pay_fee():
    tid = session["ref_id"]
    teacher = get_teacher(tid)
    if not teacher: return redirect(url_for("index"))
    if teacher["info_fee_paid"]:
        return redirect(url_for("teacher_center"))
    coupons = get_teacher_coupons(tid)
    if request.method == "POST":
        cid = request.form.get("coupon_id", type=int)
        pay_info_fee(tid, cid)
        flash("\u4fe1\u606f\u8d39\u652f\u4ed8\u6210\u529f\uff01\u60a8\u73b0\u5728\u53ef\u4ee5\u5f00\u59cb\u63a5\u5355\u4e86", "success")
        return redirect(url_for("teacher_center"))
    return render_template("pay_fee.html", teacher=teacher, coupons=coupons,
                           admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))

@app.route("/teacher/withdraw", methods=["GET","POST"])
@login_required("teacher")
def teacher_withdraw():
    tid = session["ref_id"]
    if request.method == "POST":
        amount = request.form.get("amount", type=int)
        acct_type = request.form.get("account_type","").strip()
        acct_info = request.form.get("account_info","").strip()
        if not amount or amount <= 0: flash("\u8bf7\u8f93\u5165\u6709\u6548\u91d1\u989d","error")
        elif not acct_type: flash("\u8bf7\u9009\u62e9\u8d26\u6237\u7c7b\u578b","error")
        elif not acct_info: flash("\u8bf7\u8f93\u5165\u8d26\u53f7\u4fe1\u606f","error")
        else:
            ok, err = create_withdrawal(tid, amount, acct_type, acct_info)
            if err: flash(err, "error")
            else: flash("\u63d0\u73b0\u7533\u8bf7\u5df2\u63d0\u4ea4\uff0c\u7b49\u5f85\u7ba1\u7406\u5458\u5904\u7406","success")
        return redirect(url_for("teacher_center"))
    return redirect(url_for("teacher_center"))

@app.route("/teacher/feedback/<int:aid>", methods=["POST"])
@login_required("teacher")
def teacher_give_feedback(aid):
    tid = session["ref_id"]
    rating = request.form.get("rating", type=int) or 5
    content = request.form.get("content","").strip()
    add_feedback(aid, "teacher", "parent", rating, content)
    flash("\u8bc4\u4ef7\u5df2\u63d0\u4ea4", "success")
    return redirect(url_for("teacher_center"))

# ── Parent Center ──
@app.route("/parent/center")
@login_required("parent")
def parent_center():
    pid = session["ref_id"]
    parent = get_parent(pid)
    if not parent: flash("\u4fe1\u606f\u4e0d\u5b58\u5728","error"); return redirect(url_for("index"))
    appointments = get_parent_appointments(pid)
    feedback = get_feedback_for_parent(pid)
    return render_template("parent_center.html", parent=parent, appointments=appointments,
                           feedback=feedback, admin=admin_ctx(),
                           user=session.get("user_id"), role=session.get("role"))

@app.route("/parent/feedback/<int:aid>", methods=["POST"])
@login_required("parent")
def parent_give_feedback(aid):
    rating = request.form.get("rating", type=int) or 5
    content = request.form.get("content","").strip()
    add_feedback(aid, "parent", "teacher", rating, content)
    flash("\u8bc4\u4ef7\u5df2\u63d0\u4ea4", "success")
    return redirect(url_for("parent_center"))

# ── Appointment Actions ──
@app.route("/appointment/<int:aid>/<action>", methods=["POST"])
def appointment_action(aid, action):
    apt = get_appointment(aid)
    if not apt: flash("\u672a\u627e\u5230\u8be5\u7533\u8bf7","error"); return redirect(url_for("index"))
    if action == "accept":
        update_appointment_status(aid, "accepted")
        flash("\u5df2\u63a5\u53d7\u8be5\u7533\u8bf7","success")
    elif action == "decline":
        update_appointment_status(aid, "declined")
        flash("\u5df2\u62d2\u7edd\u8be5\u7533\u8bf7","info")
    elif action == "pay":
        update_appointment_status(aid, "paid")
        flash("\u4ed8\u6b3e\u6210\u529f\uff01\u5df2\u5411\u8001\u5e08\u5c55\u793a\u60a8\u7684\u8054\u7cfb\u65b9\u5f0f","success")
    elif action == "satisfied":
        update_appointment_status(aid, "completed")
        flash("\u5df2\u786e\u8ba4\u6ee1\u610f\uff0c\u8bfe\u65f6\u8d39\u5c06\u7ed3\u7b97\u7ed9\u8001\u5e08","success")
    elif action == "refund":
        update_appointment_status(aid, "refunded")
        flash("\u5df2\u7533\u8bf7\u9000\u6b3e\uff0c\u5168\u989d\u9000\u56de","info")
    elif action == "complete":
        update_appointment_status(aid, "completed")
        flash("\u5df2\u6807\u8bb0\u4e3a\u5b8c\u6210","success")
    return redirect(request.referrer or url_for("index"))

# ── Admin Routes ──
@app.route("/admin/login", methods=["GET","POST"], endpoint="admin_login")
def admin_login_view():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        key = request.form.get("key","").strip()
        a = admin_login(username, password)
        if a and key == "0608":
            session["admin_id"] = a["id"]
            session["admin_name"] = a["name"]
            flash("欢迎回来，" + a["name"], "success")
            return redirect(url_for("admin_dashboard"))
        if a:
            flash("\u5bc6\u94a5\u9519\u8bef", "error")
        else:
            flash("\u7528\u6237\u540d\u6216\u5bc6\u7801\u9519\u8bef", "error")
    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_session_token", None)
    flash("\u5df2\u9000\u51fa\u7ba1\u7406\u540e\u53f0","info")
    return redirect(url_for("index"))


def admin_required(f):
    @wraps(f)
    def wrapper(*a,**k):
        if "admin_id" not in session: flash("\u8bf7\u5148\u767b\u5f55\u7ba1\u7406\u5458","error"); return redirect(url_for("admin_login"))
        return f(*a,**k)
    return wrapper

@app.route("/admin/teachers")
@admin_required
def admin_teachers():
    teachers = get_all_teachers_admin()
    return render_template("admin_teachers.html", teachers=teachers, admin=admin_ctx())

@app.route("/admin/teacher/<int:tid>/delete", methods=["POST"])
@admin_required
def admin_teacher_delete(tid):
    delete_teacher(tid)
    flash("\u5df2\u5220\u9664\u8be5\u6559\u5e08","success")
    return redirect(url_for("admin_teachers"))

@app.route("/admin/parents")
@admin_required
def admin_parents():
    parents = get_all_parents_admin()
    return render_template("admin_parents.html", parents=parents, admin=admin_ctx())

@app.route("/admin/appointments")
@admin_required
def admin_appointments():
    appointments = get_all_appointments_admin()
    return render_template("admin_appointments.html", appointments=appointments, admin=admin_ctx())

@app.route("/admin/appointment/<int:aid>/<action>", methods=["POST"])
@admin_required
def admin_force_appointment(aid, action):
    update_appointment_status(aid, action)
    flash(f"\u5df2\u5f3a\u5236\u66f4\u65b0\u4e3a\uff1a{action}","success")
    return redirect(url_for("admin_appointments"))

@app.route("/admin/admins", methods=["GET","POST"])
@admin_required
def admin_manage():
    admins = get_all_admins()
    return render_template("admin_admins.html", admins=admins, admin=admin_ctx())

@app.route("/admin/admin/add", methods=["POST"])
@admin_required
def admin_add():
    u = request.form.get("username","").strip()
    p = request.form.get("password","").strip()
    n = request.form.get("name","").strip()
    if not u or not p or not n: flash("\u8bf7\u586b\u5199\u5b8c\u6574\u4fe1\u606f","error")
    else:
        aid, err = add_admin(u, p, n)
        if err: flash(err,"error")
        else: flash(f"\u5df2\u6dfb\u52a0\u7ba1\u7406\u5458\uff1a{n}","success")
    return redirect(url_for("admin_manage"))

@app.route("/admin/admin/<int:aid>/delete", methods=["POST"])
@admin_required
def admin_del(aid):
    ok = delete_admin(aid)
    flash("\u5df2\u79fb\u9664" if ok else "\u65e0\u6cd5\u5220\u9664\u8d85\u7ea7\u7ba1\u7406\u5458","success" if ok else "error")
    return redirect(url_for("admin_manage"))

# ── Admin: Blacklist ──
@app.route("/admin/blacklist")
@admin_required
def admin_blacklist():
    blacklist = get_blacklist()
    teachers = get_all_teachers_admin()
    parents = get_all_parents_admin()
    return render_template("admin_blacklist.html", blacklist=blacklist, teachers=teachers,
                           parents=parents, admin=admin_ctx())

@app.route("/admin/blacklist/add", methods=["POST"])
@admin_required
def admin_blacklist_add():
    user_type = request.form.get("user_type")
    ref_id = request.form.get("ref_id", type=int)
    reason = request.form.get("reason","").strip()
    if user_type and ref_id:
        add_to_blacklist(user_type, ref_id, reason, session["admin_id"])
        flash("\u5df2\u52a0\u5165\u9ed1\u540d\u5355","success")
    return redirect(url_for("admin_blacklist"))

@app.route("/admin/blacklist/<int:blid>/remove", methods=["POST"])
@admin_required
def admin_blacklist_remove(blid):
    remove_from_blacklist(blid)
    flash("\u5df2\u79fb\u9664\u51fa\u9ed1\u540d\u5355","success")
    return redirect(url_for("admin_blacklist"))

# ── Admin: Fees ──
@app.route("/admin/fees")
@admin_required
def admin_fees():
    unpaid = get_unpaid_fee_teachers()
    withdrawals = get_withdrawals()
    return render_template("admin_fees.html", unpaid=unpaid, withdrawals=withdrawals, admin=admin_ctx())

@app.route("/admin/withdrawal/<int:wid>/<action>", methods=["POST"])
@admin_required
def admin_process_withdrawal(wid, action):
    process_withdrawal(wid, action)
    flash("\u5df2\u5904\u7406\u63d0\u73b0\u7533\u8bf7","success")
    return redirect(url_for("admin_fees"))



# ── QR Code Lesson System ──

@app.route("/lesson/generate/<int:aid>", methods=["POST"])
def lesson_generate(aid):
    """Parent generates a QR code for a lesson session."""
    from database import get_appointment
    apt = get_appointment(aid)
    if not apt:
        flash("\u672a\u627e\u5230\u8be5\u7533\u8bf7","error")
        return redirect(url_for("index"))
    
    lesson = create_lesson(aid)
    flash(f"\u7b2c{lesson['number']}\u8282\u8bfe\u5df2\u751f\u6210\uff0c\u8bf7\u5c55\u793a\u4e8c\u7ef4\u7801\u7ed9\u8001\u5e08\u626b\u63cf","success")
    return redirect(f"/lesson/show/{lesson['token']}")

@app.route("/lesson/show/<token>")
def lesson_show_qr(token):
    """Show QR code page for a lesson."""
    from database import get_db as _db
    db = _db()
    r = db.execute("SELECT l.*,a.teacher_id,a.subject FROM lessons l JOIN appointments a ON l.appointment_id=a.id WHERE l.token=?", (token,)).fetchone()
    db.close()
    if not r:
        flash("\u672a\u627e\u5230\u8be5\u8282\u8bfe","error")
        return redirect(url_for("index"))
    
    lesson = dict(r)
    # Get teacher name
    from database import get_teacher
    teacher = get_teacher(lesson["teacher_id"])
    
    # Build verification URL
    verify_url = request.host_url.rstrip('/') + "/lesson/verify/" + token
    
    return render_template("lesson_qr.html",
        lesson=lesson, teacher=teacher, verify_url=verify_url,
        admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))

@app.route("/lesson/verify/<token>")
def lesson_verify(token):
    """Teacher scans/opens the QR code URL to verify a lesson."""
    result = verify_lesson(token)
    if result:
        flash(f"\u7b2c{result['lesson_number']}\u8282\u8bfe\u5df2\u786e\u8ba4\u4e0a\u8bfe\uff01\u5df2\u5728\u5e73\u53f0\u5907\u6848","success")
    else:
        flash("\u4e8c\u7ef4\u7801\u5df2\u8fc7\u671f\u6216\u65e0\u6548","error")
    if session.get("role") == "teacher":
        return redirect(url_for("teacher_center"))
    return redirect(url_for("index"))

@app.route("/lesson/end/<token>", methods=["POST"])
def lesson_end(token):
    """Teacher ends a lesson after teaching is complete."""
    result = end_lesson(token)
    if result:
        flash(f"\u7b2c{result['lesson_number']}\u8282\u8bfe\u5df2\u7ed3\u675f\u6388\u8bfe\uff0c\u5df2\u901a\u77e5\u5bb6\u957f","success")
    else:
        flash("\u65e0\u6cd5\u7ed3\u675f\u8be5\u8282\u8bfe\uff0c\u53ef\u80fd\u5df2\u7ecf\u7ed3\u675f\u4e86","error")
    return redirect(url_for("teacher_center"))

@app.route("/lesson/list/<int:aid>")
def lesson_list(aid):
    """List all lessons for an appointment."""
    from database import get_appointment, get_teacher
    apt = get_appointment(aid)
    if not apt:
        flash("\u672a\u627e\u5230\u8be5\u7533\u8bf7","error")
        return redirect(url_for("index"))
    teacher = get_teacher(apt["teacher_id"])
    lessons = get_lessons_for_appointment(aid)
    stats = get_lesson_count_for_appointment(aid)
    return render_template("lesson_list.html", apt=apt, teacher=teacher,
        lessons=lessons, stats=stats,
        admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))

# ── Payment Refusal ──
@app.route("/appointment/<int:aid>/refuse-payment", methods=["POST"])
@app.route("/parent/appointment/<int:aid>/refuse", methods=["POST"])
def refuse_payment(aid):
    """Parent refuses to pay after lesson. Teacher gets 50% compensation."""
    comp, count = record_payment_refusal(aid)
    if comp is None:
        flash("\u64cd\u4f5c\u5931\u8d25","error")
    else:
        flash(f"\u5df2\u8bb0\u5f55\u62d2\u7edd\u652f\u4ed8\uff0c\u8001\u5e08\u83b7\u5f97{comp}\u5143\u8865\u8d34\uff08\u7b2c{count}\u6b21\uff09","info")
        if count >= 3:
            flash("\u8be5\u5bb6\u957f\u5df2\u8fbe3\u6b21\u62d2\u7edd\u652f\u4ed8\uff0c\u5df2\u81ea\u52a8\u52a0\u5165\u9ed1\u540d\u5355","error")
    return redirect(url_for("teacher_dashboard", teacher_id=request.form.get("teacher_id", 0)))


@app.after_request
def security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# Initialize database at module level (runs on gunicorn import)
init_db()
init_admin()



# ── Find Students (Teacher browses parent listings) ──
@app.route("/find-students")
@login_required("teacher")
def find_students():
    tid = session["ref_id"]
    parents = get_parent_listings(exclude_teacher_id=tid)
    coupons = get_teacher_coupons(tid)
    # Calculate 70% contact fee for each parent
    for p in parents:
        p["contact_fee"] = (p["budget"] or 100) * 70 // 100
    return render_template("find_students.html", parents=parents, coupons=coupons,
                           admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))

@app.route("/buy-lead/<int:parent_id>", methods=["POST"])
@login_required("teacher")
def buy_lead_route(parent_id):
    tid = session["ref_id"]
    cid = request.form.get("coupon_id", type=int)
    # Get parent budget and calculate 70%
    db = get_db(); p = db.execute("SELECT budget FROM parents WHERE id=?", (parent_id,)).fetchone(); db.close()
    fee = (p["budget"] or 100) * 70 // 100 if p else 70
    if has_bought_contact("teacher", tid, parent_id):
        flash("\u60a8\u5df2\u7ecf\u8d2d\u4e70\u8fc7\u8be5\u7ebf\u7d22", "info")
    else:
        bid = buy_lead("teacher", tid, "parent", parent_id, fee, cid)
        flash(f"\u8d2d\u4e70\u6210\u529f\uff01\u652f\u4ed98{fee}\u5143\uff08\u7ebf\u7d22\u8d39\u4e3a\u5bb6\u957f\u51fa\u4ef7\u768470%\uff09\uff0c\u5df2\u83b7\u5f97\u8054\u7cfb\u65b9\u5f0f", "success")
    return redirect(url_for("teacher_center"))

@app.route("/bought-leads")
@login_required("teacher")
def bought_leads():
    tid = session["ref_id"]
    leads = get_bought_leads(tid)
    return render_template("bought_leads.html", leads=leads,
                           admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))



@app.route("/find-teachers")
@login_required("parent")
def find_teachers():
    pid = session["ref_id"]
    teachers = get_teacher_listings(exclude_parent_id=pid)
    return render_template("find_teachers.html", teachers=teachers,
                           admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))

@app.route("/parent/buy-lead/<int:teacher_id>", methods=["POST"])
@login_required("parent")
def parent_buy_lead(teacher_id):
    pid = session["ref_id"]
    fee = 70
    db = get_db(); t = db.execute("SELECT ref_rate FROM teachers WHERE id=?", (teacher_id,)).fetchone(); db.close()
    if t and t["ref_rate"]: fee = t["ref_rate"] * 70 // 100
    if has_bought_contact("parent", pid, teacher_id):
        flash("\u60a8\u5df2\u7ecf\u8d2d\u4e70\u8fc7\u8be5\u8001\u5e08\u7684\u8054\u7cfb\u65b9\u5f0f", "info")
    else:
        bid = buy_lead("parent", pid, "teacher", teacher_id, fee)
        flash(f"\u8d2d\u4e70\u6210\u529f\uff01\u5df2\u652f\u4ed8{fee}\u5143\uff0c\u5df2\u83b7\u5f97\u8001\u5e08\u8054\u7cfb\u65b9\u5f0f", "success")
    return redirect(url_for("parent_center"))


@app.route("/parent/register", methods=["GET","POST"])
def parent_register():
    if request.method == "POST":
        d = {
            "username": request.form.get("username","").strip(),
            "password": request.form.get("password","").strip(),
            "parent_name": request.form.get("parent_name","").strip(),
            "email": request.form.get("email","").strip(),
            "phone": request.form.get("phone","").strip(),
            "student_name": request.form.get("student_name","").strip(),
            "student_grade": request.form.get("student_grade","").strip(),
            "student_level": request.form.get("student_level","").strip(),
            "subjects": request.form.get("subjects","").strip(),
            "province": request.form.get("province","").strip(),
            "city": request.form.get("city","").strip(),
            "district": request.form.get("district","").strip(),
            "requirements": request.form.get("requirements","").strip(),
            "budget": request.form.get("budget", type=int),
        }
        errors = []
        if not d["username"]: errors.append("请输入用户名")
        if not d["password"] or len(d["password"]) < 4: errors.append("密码至少4位")
        if not d["parent_name"]: errors.append("请输入您的姓名")
        if not d["phone"]: errors.append("请输入手机号")
        elif phone_exists(d["phone"], "parent"): errors.append("该手机号已被其他账号使用")
        sms_code = request.form.get("sms_code","").strip()
        if not sms_code or not verify_sms_code(d["phone"], sms_code):
            errors.append("手机验证码错误或已过期")
        if not d["email"] or not re.match(r"[^@]+@[^@]+\.[^@]+", d["email"]): errors.append("请输入有效邮箱")
        if not d["student_name"]: errors.append("请输入学生姓名")
        if not d["subjects"]: errors.append("请输入需要辅导的科目")
        if errors:
            for e in errors: flash(e, "error")
            return render_template("parent_register.html", grades=GRADES, provinces=get_provinces(), data=d), 400
        try:
            pid, err = add_parent(d)
            if err:
                flash(err, "error")
                return render_template("parent_register.html", grades=GRADES, provinces=get_provinces(), data=d), 400
            # Auto login
            user = login_user(d["username"], d["password"])
            if user:
                session["user_id"] = user["id"]
                session["user_name"] = user.get("name", "家长")
                session["role"] = "parent"
                session["ref_id"] = pid
                session.permanent = True
            flash("注册成功！欢迎加入弦歌 🎉 建议您先上传学生证件并签署保证书", "success")
            return redirect(url_for("parent_center"))
        except Exception as e:
            if "UNIQUE" in str(e): flash("用户名或邮箱已被注册", "error")
            else: flash(f"注册失败：{e}", "error")
            return render_template("parent_register.html", grades=GRADES, provinces=get_provinces(), data=d), 400
    return render_template("parent_register.html", grades=GRADES, provinces=get_provinces())


@app.route("/admin/teacher/<int:tid>/center")
@admin_required
def admin_teacher_center(tid):
    teacher = get_teacher_by_id(tid)
    if not teacher: flash("教师不存在","error"); return redirect(url_for("admin_teachers"))
    appointments = get_teacher_appointments(tid)
    feedback = get_feedback_for_teacher(tid)
    stats = get_teacher_stats(tid)
    subjects = [s.strip() for s in teacher["subjects"].split(",") if s.strip()]
    available = get_available_earnings(tid)
    coupons = get_teacher_coupons(tid)
    return render_template("teacher_center.html", teacher=teacher, stats=stats,
        appointments=appointments, feedback=feedback, coupons=coupons,
        available=available, subjects=subjects,
        admin=admin_ctx(), user=True, role="admin")

@app.route("/admin/parent/<int:pid>/center")
@admin_required
def admin_parent_center(pid):
    parent = get_parent(pid)
    if not parent: flash("家长不存在","error"); return redirect(url_for("admin_parents"))
    appointments = get_parent_appointments(pid)
    feedback = get_feedback_for_parent(pid)
    return render_template("parent_center.html", parent=parent,
        appointments=appointments, feedback=feedback,
        admin=admin_ctx(), user=True, role="admin")


@app.route("/admin/verify-ai/<int:doc_id>", methods=["POST"])
@admin_required
def admin_verify_ai(doc_id):
    from database import get_db as _db
    from universities import UNIVERSITIES
    import importlib
    try:
        ai_mod = importlib.import_module("ai_verify")
    except:
        flash("AI module not found", "error")
        return redirect(url_for("admin_verification"))
    
    db = _db()
    doc = db.execute("SELECT * FROM verification_docs WHERE id=?", (doc_id,)).fetchone()
    db.close()
    if not doc:
        flash("Document not found", "error")
        return redirect(url_for("admin_verification"))
    
    fp = os.path.join(UPLOAD_FOLDER, doc["filepath"])
    if not os.path.exists(fp):
        flash("File not found", "error")
        return redirect(url_for("admin_verification"))
    
    result, info = ai_mod.verify_document(fp, UNIVERSITIES)
    
    if result is True:
        update_verification_status(doc_id, "approved")
        flash(f"AI matched university: {info}", "success")
    elif result is False:
        flash(f"AI no match. Extracted text: {info[:100]}...", "info")
    else:
        flash(f"AI error: {info}", "warning")
    
    return redirect(url_for("admin_verification"))


@app.route("/parent/<int:parent_id>/delete", methods=["POST"])
def parent_delete(parent_id):
    email = request.form.get("email","").strip()
    ok = delete_parent(parent_id, email)
    if ok:
        session.clear()
        flash("您的资料已成功注销，感谢使用弦歌", "success")
        return redirect(url_for("index"))
    flash("验证失败，请确认邮箱地址正确", "error")
    return redirect(url_for("parent_center"))


@app.route("/admin/parent/<int:pid>/delete", methods=["POST"])
@admin_required
def admin_parent_delete(pid):
    admin_delete_parent(pid)
    flash("\u5df2\u5220\u9664\u8be5\u5bb6\u957f", "success")
    return redirect(url_for("admin_parents"))


@app.route("/admin/teacher/<int:tid>/reset-password", methods=["POST"])
@admin_required
def admin_teacher_reset(tid):
    from database import get_db as _db
    pw = request.form.get("new_password","").strip()
    if not pw or len(pw) < 4: flash("密码至少4位","error"); return redirect(url_for("admin_teachers"))
    db = _db()
    u = db.execute("SELECT username FROM users WHERE role='teacher' AND ref_id=?", (tid,)).fetchone()
    db.close()
    if u: update_user_password(u["username"], pw); flash(f"密码已重置: {pw}","success")
    else: flash("用户不存在","error")
    return redirect(url_for("admin_teachers"))

@app.route("/admin/parent/<int:pid>/reset-password", methods=["POST"])
@admin_required
def admin_parent_reset(pid):
    from database import get_db as _db
    pw = request.form.get("new_password","").strip()
    if not pw or len(pw) < 4: flash("密码至少4位","error"); return redirect(url_for("admin_parents"))
    db = _db()
    u = db.execute("SELECT username FROM users WHERE role='parent' AND ref_id=?", (pid,)).fetchone()
    db.close()
    if u: update_user_password(u["username"], pw); flash(f"密码已重置: {pw}","success")
    else: flash("用户不存在","error")
    return redirect(url_for("admin_parents"))





@app.route("/admin/qrcodes", methods=["GET","POST"])
@admin_required
def admin_qrcodes():
    if request.method == "POST":
        for key in ["alipay", "wechat"]:
            if key in request.files:
                f = request.files[key]
                if f and f.filename:
                    ext = f.filename.rsplit(".",1)[1].lower() if "." in f.filename else "png"
                    fn = f"qr_{key}.{ext}"
                    f.save(os.path.join(app.static_folder, fn))
        flash("二维码已更新","success")
        return redirect(url_for("admin_qrcodes"))
    alipay_exists = os.path.exists(os.path.join(app.static_folder, "qr_alipay.jpg"))
    wechat_exists = os.path.exists(os.path.join(app.static_folder, "qr_wechat.jpg"))
    return render_template("admin_qrcodes.html", alipay=alipay_exists, wechat=wechat_exists, admin=admin_ctx())

@app.route("/payment")
def payment():
    alipay = os.path.exists(os.path.join(app.static_folder, "qr_alipay.jpg"))
    wechat = os.path.exists(os.path.join(app.static_folder, "qr_wechat.jpg"))
    return render_template("payment.html", alipay=alipay, wechat=wechat, admin=admin_ctx())


@app.route("/payment/report", methods=["POST"])
def payment_report():
    method = request.form.get("method","")
    conn = get_db()
    conn.execute("INSERT INTO payment_orders (payment_method,status) VALUES (?,?)", (method,"pending"))
    conn.commit()
    flash("\u5df2\u63d0\u4ea4\uff0c\u7b49\u5f85\u7ba1\u7406\u5458\u786e\u8ba4\u4ed8\u6b3e","info")
    return redirect(url_for("payment"))

@app.route("/admin/orders")
@admin_required
def admin_orders():
    return "<!DOCTYPE html><html><head><meta charset=UTF-8><title>收款订单</title></head><body><h1>收款订单</h1><p>暂无订单</p><a href=/admin>返回管理后台</a></body></html>", 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/admin/order/<int:oid>/confirm", methods=["POST"])
@admin_required
def admin_confirm_order(oid):
    conn = get_db()
    conn.execute("UPDATE payment_orders SET status='paid',confirmed_at=datetime('now','localtime') WHERE id=?", (oid,))
    conn.commit(); conn.close()
    flash("\u5df2\u786e\u8ba4\u6536\u6b3e","success")
    return redirect(url_for("admin_orders"))

# ── Account Management ──
@app.route("/account")
@login_required()
def account_page():
    user_type = session["role"]
    uid = session["ref_id"]
    if user_type == "teacher":
        from database import get_teacher
        info = get_teacher(uid)
    else:
        info = get_parent(uid)
    accounts = get_payment_accounts(user_type, uid)
    return render_template("account.html", info=info, accounts=accounts,
        user_type=user_type, uid=uid, user=session.get("user_id"), role=session.get("role"))

# ── Notifications Center ──
@app.route("/notifications")
@login_required()
def notifications_page():
    user_type = session["role"]
    uid = session["ref_id"]
    notes = get_notifications(user_type, uid)
    unread = get_unread_notification_count(user_type, uid)
    return render_template("notifications.html", notes=notes, unread=unread,
        user=session.get("user_id"), role=session.get("role"))

@app.route("/notifications/read/<int:nid>", methods=["POST"])
@login_required()
def notification_read(nid):
    mark_notification_read(nid)
    return "", 204

@app.route("/notifications/read-all", methods=["POST"])
@login_required()
def notification_read_all():
    mark_all_notifications_read(session["role"], session["ref_id"])
    return "", 204

@app.route("/notifications/delete/<int:nid>", methods=["POST"])
@login_required()
def notification_delete(nid):
    delete_notification(nid)
    return "", 204

@app.route("/api/notifications/count")
@login_required()
def api_notification_count():
    try:
        count = get_unread_notification_count(session["role"], session["ref_id"])
        return jsonify({"count": count})
    except:
        return jsonify({"count": 0})

if __name__ == "__main__":
    print(f"  \u5f26\u6b4c server \u2192 http://127.0.0.1:" + str(os.environ.get("PORT", 8080)))
    print(f"  \u7ba1\u7406\u5458\uff1aadmin / xiange2024")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=(os.environ.get("RENDER") is None))


import os, uuid
from flask import send_from_directory

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_EXT = {"png","jpg","jpeg","gif","pdf"}

def allowed_file(fn):
    return "." in fn and fn.rsplit(".",1)[1].lower() in ALLOWED_EXT

# ── SMS Simulation ──
@app.route("/forgot-password", methods=["GET","POST"])
def forgot_password():
    if request.method == "POST":
        step = request.form.get("step","")
        phone = request.form.get("phone","").strip()
        code = request.form.get("code","").strip()
        role = request.form.get("role","teacher")
        
        if step == "send":
            if not phone or len(phone) < 5:
                flash("请输入有效的手机号","error")
                return render_template("forgot_password.html", step="phone", phone="")
            sim_code = str(random.randint(100000, 999999))
            save_sms_code(phone, sim_code)
            flash(f"验证码已发送到 {phone[:3]}****{phone[-4:]}（测试用验证码：{sim_code}）","info")
            return render_template("forgot_password.html", step="verify", phone=phone, role=role)
        
        elif step == "verify":
            if verify_sms_code(phone, code):
                return render_template("forgot_password.html", step="reset", phone=phone, role=role)
            flash("验证码错误或已过期","error")
            return render_template("forgot_password.html", step="verify", phone=phone, role=role)
        
        elif step == "reset":
            new_pw = request.form.get("new_password","").strip()
            if not new_pw or len(new_pw) < 4:
                flash("密码至少4位","error")
                return render_template("forgot_password.html", step="reset", phone=phone, role=role)
            user = get_user_by_phone_role(phone, role)
            if user:
                username = user.get("username") or (role + str(user["id"]))
                update_user_password(username, new_pw)
                flash("密码已重置，请登录","success")
                return redirect(url_for("login"))
            flash("未找到该手机号对应的账号","error")
    return render_template("forgot_password.html", step="phone")

# ── Contract Signing ──
@app.route("/contract/<int:aid>")
@login_required("parent")
def contract_page(aid):
    from database import get_appointment, get_teacher
    apt = get_appointment(aid)
    if not apt or apt["parent_id"] != session.get("ref_id"):
        flash("无权限","error"); return redirect(url_for("index"))
    teacher = get_teacher(apt["teacher_id"])
    contract = get_contract(aid)
    return render_template("contract.html", apt=apt, teacher=teacher, contract=contract)

@app.route("/contract/<int:aid>/sign", methods=["POST"])
@login_required("parent")
def contract_sign(aid):
    from database import get_appointment
    apt = get_appointment(aid)
    if not apt or apt["parent_id"] != session.get("ref_id"):
        flash("无权限","error"); return redirect(url_for("index"))
    
    signature = request.form.get("signature","").strip()
    name = request.form.get("parent_name","").strip()
    
    # Handle student ID upload
    student_id_file = None
    if "student_id" in request.files:
        file = request.files["student_id"]
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit(".",1)[1].lower()
            fn = f"sid_{aid}_{uuid.uuid4().hex[:8]}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, fn))
            student_id_file = fn
            add_verification_doc("parent", apt["parent_id"], "campus_card", file.filename, fn)
    
    if not signature:
        flash("请签署合同","error")
        return redirect(url_for("contract_page", aid=aid))
    
    create_contract(aid, signature, student_id_file)
    flash("合同签署成功！","success")
    return redirect(url_for("parent_center"))

# ── Upload Verification Docs ──
@app.route("/upload/<user_type>/<int:uid>", methods=["GET","POST"])
@login_required()
def upload_docs(user_type, uid):
    if session.get("ref_id") != uid or session.get("role") != user_type:
        flash("无权限","error"); return redirect(url_for("index"))
    
    if request.method == "POST":
        doc_type = request.form.get("doc_type","school")
        if "file" not in request.files:
            flash("请选择文件","error")
            return redirect(url_for("upload_docs", user_type=user_type, uid=uid))
        file = request.files["file"]
        if file and file.filename and allowed_file(file.filename):
            ext = file.filename.rsplit(".",1)[1].lower()
            fn = f"{doc_type}_{uid}_{uuid.uuid4().hex[:8]}.{ext}"
            file.save(os.path.join(UPLOAD_FOLDER, fn))
            add_verification_doc(user_type, uid, doc_type, file.filename, fn)
            flash("上传成功，等待管理员审核","success")
        else:
            flash("文件格式不支持（支持 jpg/png/pdf）","error")
        return redirect(url_for("upload_docs", user_type=user_type, uid=uid))
    
    docs = get_verification_docs(user_type, uid)
    return render_template("upload_docs.html", user_type=user_type, uid=uid, docs=docs,
                           admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))

# ── Admin: Verification ──
@app.route("/admin/verification")
@admin_required
def admin_verification():
    docs = get_verification_docs()
    return render_template("admin_verification.html", docs=docs, admin=admin_ctx())

@app.route("/admin/verification/<int:did>/<action>", methods=["POST"])
@admin_required
def admin_verification_action(did, action):
    update_verification_status(did, action)
    flash(f"已{'通过' if action=='approved' else '拒绝'}认证","success")
    return redirect(url_for("admin_verification"))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ── Payment Account Settings ──
@app.route("/settings/payment", methods=["GET","POST"])
@login_required()
def payment_settings():
    user_type = session["role"]
    uid = session["ref_id"]
    
    if request.method == "POST":
        acct_type = request.form.get("account_type","")
        acct_name = request.form.get("account_name","").strip()
        acct_info = request.form.get("account_info","").strip()
        if not acct_type or not acct_name or not acct_info:
            flash("请填写完整信息","error")
        else:
            save_payment_account(user_type, uid, acct_type, acct_name, acct_info)
            flash("绑定成功","success")
        return redirect(url_for("payment_settings"))
    
    accounts = get_payment_accounts(user_type, uid)
    return render_template("payment_settings.html", accounts=accounts,
                           user_type=user_type, uid=uid,
                           admin=admin_ctx(), user=session.get("user_id"), role=session.get("role"))





