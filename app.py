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
