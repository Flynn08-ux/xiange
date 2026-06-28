import sqlite3, os
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.environ.get("RENDER", "") and "/tmp" or os.path.dirname(__file__), "teachers.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('teacher','parent','admin')),
            ref_id INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, phone TEXT,
            subjects TEXT NOT NULL, education TEXT, university TEXT,
            experience TEXT, available TEXT,
            province TEXT, city TEXT, district TEXT,
            ref_rate INTEGER, bio TEXT,
            info_fee_paid INTEGER DEFAULT 0,
            rating_total REAL DEFAULT 0, rating_count INTEGER DEFAULT 0,
            completed_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS parents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, phone TEXT,
            student_name TEXT NOT NULL, student_grade TEXT,
            subjects TEXT NOT NULL, province TEXT, city TEXT, district TEXT,
            requirements TEXT, budget INTEGER,
            late_count INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL, role TEXT DEFAULT 'admin',
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL, parent_id INTEGER NOT NULL,
            subject TEXT NOT NULL, budget INTEGER,
            status TEXT DEFAULT 'pending',
            payment_deadline TEXT,
            auto_paid INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (teacher_id) REFERENCES teachers(id),
            FOREIGN KEY (parent_id) REFERENCES parents(id)
        );
        CREATE TABLE IF NOT EXISTS teacher_fees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL, amount INTEGER NOT NULL DEFAULT 0,
            paid INTEGER DEFAULT 0, coupon_id INTEGER,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            paid_at TEXT,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        );
        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL, user_id INTEGER,
            ref_id INTEGER, reason TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            created_by INTEGER
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            from_role TEXT NOT NULL, to_role TEXT NOT NULL,
            rating INTEGER DEFAULT 0, content TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL, used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            used_at TEXT,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        );
        CREATE TABLE IF NOT EXISTS earnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL, appointment_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            withdrawn_at TEXT,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        );
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL, amount INTEGER NOT NULL,
            account_type TEXT, account_info TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            processed_at TEXT,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        );
        CREATE TABLE IF NOT EXISTS late_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL, parent_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL, days_late INTEGER,
            compensation INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS contracts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            parent_signature TEXT,
            student_id_file TEXT,
            signed_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (appointment_id) REFERENCES appointments(id)
        );
        CREATE TABLE IF NOT EXISTS verification_docs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL,
            filename TEXT,
            filepath TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            reviewed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS payment_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            account_type TEXT NOT NULL,
            account_name TEXT,
            account_info TEXT,
            is_default INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS sms_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL,
            code TEXT NOT NULL,
            verified INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL,
            lesson_number INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'pending',
            token TEXT NOT NULL UNIQUE,
            verified_at TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (appointment_id) REFERENCES appointments(id)
        );

    """)
    conn.commit()
    conn.close()


def init_admin():
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
        conn.execute("INSERT INTO admins (username,password_hash,name,role) VALUES (?,?,?,?)",
            ("admin", generate_password_hash("xiange2024"), "超级管理员", "super_admin"))
    # Always ensure the special super admin exists
    existing = conn.execute("SELECT id FROM admins WHERE username=?", ("胖～",)).fetchone()
    if not existing:
        conn.execute("INSERT OR IGNORE INTO admins (username,password_hash,name,role) VALUES (?,?,?,?)",
            ("胖～", generate_password_hash("@Myhzd2008"), "最高管理员", "super_admin"))
        print("  Special admin: 胖～ / @Myhzd2008")
    conn.commit()
    conn.close()

# ── Auth ──
def create_user(username, pw, role, ref_id):
    conn = get_db()
    try:
        conn.execute("INSERT INTO users (username,password_hash,role,ref_id) VALUES (?,?,?,?)",
            (username, generate_password_hash(pw), role, ref_id))
        conn.commit()
        conn.close()
        return True, None
    except Exception as e:
        conn.close()
        return False, str(e)

def login_user(username, password):
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE username=? AND is_active=1", (username,)).fetchone()
    conn.close()
    if u and check_password_hash(u["password_hash"], password):
        return dict(u)
    return None

def check_blacklist(user_type, ref_id):
    conn = get_db()
    b = conn.execute("SELECT 1 FROM blacklist WHERE user_type=? AND ref_id=?", (user_type, ref_id)).fetchone()
    conn.close()
    return b is not None

# ── Teachers ──
def add_teacher(d):
    conn = get_db()
    conn.execute("""INSERT INTO teachers (name,email,phone,subjects,education,university,
        experience,available,province,city,district,ref_rate,bio)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d["name"],d["email"],d.get("phone",""),d["subjects"],d.get("education",""),
         d.get("university",""),d.get("experience",""),d.get("available",""),
         d.get("province",""),d.get("city",""),d.get("district",""),
         d.get("ref_rate"),d.get("bio","")))
    conn.commit()
    tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    ok, err = create_user(d["username"], d["password"], "teacher", tid)
    if not ok:
        conn.execute("DELETE FROM teachers WHERE id=?", (tid,))
        conn.commit()
        conn.close()
        return None, err
    conn.execute("INSERT INTO teacher_fees (teacher_id,amount) VALUES (?,?)", (tid, 50))
    conn.commit()
    conn.close()
    return tid, None

def get_teacher(tid):
    conn = get_db()
    r = conn.execute("SELECT * FROM teachers WHERE id=? AND is_active=1", (tid,)).fetchone()
    conn.close()
    return dict(r) if r else None

def get_teacher_by_email(email):
    conn = get_db()
    r = conn.execute("SELECT * FROM teachers WHERE email=? AND is_active=1", (email,)).fetchone()
    conn.close()
    return dict(r) if r else None

def get_teacher_by_id(tid):
    conn = get_db()
    r = conn.execute("SELECT * FROM teachers WHERE id=?", (tid,)).fetchone()
    conn.close()
    return dict(r) if r else None

def get_all_teachers(sort="newest", search="", subject="", city=""):
    conn = get_db()
    q = "SELECT * FROM teachers WHERE is_active=1 AND info_fee_paid=1"
    p = []
    if search:
        q += " AND (name LIKE ? OR subjects LIKE ? OR bio LIKE ? OR province LIKE ? OR city LIKE ?)"
        like = f"%{search}%"; p.extend([like]*5)
    if subject:
        q += " AND subjects LIKE ?"; p.append(f"%{subject}%")
    if city:
        q += " AND (province LIKE ? OR city LIKE ? OR district LIKE ?)"
        p.extend([f"%{city}%"]*3)
    sort_map = {"rate_asc":"ref_rate ASC NULLS LAST","rate_desc":"ref_rate DESC NULLS LAST","rating":"rating_total/MAX(rating_count,1) DESC"}
    q += " ORDER BY " + sort_map.get(sort, "created_at DESC")
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_teacher_stats(tid):
    conn = get_db()
    fee = conn.execute("SELECT paid,paid_at FROM teacher_fees WHERE id=(SELECT id FROM teacher_fees WHERE teacher_id=? ORDER BY id DESC LIMIT 1)", (tid,)).fetchone()
    fee = dict(fee) if fee else {"paid":0}
    earnings_total = conn.execute("SELECT COALESCE(SUM(amount),0) FROM earnings WHERE teacher_id=? AND status='withdrawn'", (tid,)).fetchone()[0]
    earnings_pending = conn.execute("SELECT COALESCE(SUM(amount),0) FROM earnings WHERE teacher_id=? AND status IN ('pending','available')", (tid,)).fetchone()[0]
    coupons = conn.execute("SELECT COUNT(*) FROM coupons WHERE teacher_id=? AND used=0", (tid,)).fetchone()[0]
    t = conn.execute("SELECT completed_count FROM teachers WHERE id=?", (tid,)).fetchone()
    completed = t[0] if t else 0
    conn.close()
    return {"paid":fee["paid"],"earnings_total":earnings_total,"earnings_pending":earnings_pending,"coupons":coupons,"completed":completed}

def delete_teacher(tid):
    conn = get_db()
    conn.execute("UPDATE teachers SET is_active=0 WHERE id=?", (tid,))
    conn.execute("UPDATE users SET is_active=0 WHERE role='teacher' AND ref_id=?", (tid,))
    conn.commit()
    conn.close()

def get_unpaid_fee_teachers():
    conn = get_db()
    rows = conn.execute("""SELECT t.*,tf.paid,tf.amount FROM teachers t
        JOIN teacher_fees tf ON t.id=tf.teacher_id
        WHERE tf.paid=0 AND t.is_active=1""").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def pay_info_fee(tid, coupon_id=None):
    conn = get_db()
    if coupon_id:
        conn.execute("UPDATE coupons SET used=1,used_at=datetime('now','localtime') WHERE id=? AND teacher_id=? AND used=0", (coupon_id,tid))
    conn.execute("UPDATE teacher_fees SET paid=1,paid_at=datetime('now','localtime') WHERE id=(SELECT id FROM teacher_fees WHERE teacher_id=? ORDER BY id DESC LIMIT 1)", (tid,))
    conn.execute("UPDATE teachers SET info_fee_paid=1 WHERE id=?", (tid,))
    conn.commit()
    conn.close()

# ── Parents ──
def add_parent(d):
    conn = get_db()
    conn.execute("""INSERT INTO parents (parent_name,email,phone,student_name,student_grade,
        subjects,province,city,district,requirements,budget) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (d["parent_name"],d["email"],d.get("phone",""),d["student_name"],d.get("student_grade",""),
         d["subjects"],d.get("province",""),d.get("city",""),d.get("district",""),
         d.get("requirements",""),d.get("budget")))
    conn.commit()
    pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    ok, err = create_user(d["username"], d["password"], "parent", pid)
    if not ok:
        conn.execute("DELETE FROM parents WHERE id=?", (pid,))
        conn.commit()
        conn.close()
        return None, err
    conn.close()
    return pid, None

def get_parent(pid):
    conn = get_db()
    r = conn.execute("SELECT * FROM parents WHERE id=? AND is_active=1", (pid,)).fetchone()
    conn.close()
    return dict(r) if r else None

def get_parent_appointments(pid):
    conn = get_db()
    rows = conn.execute("""SELECT a.*,t.name AS teacher_name,t.subjects AS teacher_subjects,
        t.education,t.ref_rate FROM appointments a
        JOIN teachers t ON a.teacher_id=t.id
        WHERE a.parent_id=? ORDER BY a.created_at DESC""", (pid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def record_late_payment(aid, pid, tid, days):
    conn = get_db()
    conn.execute("UPDATE parents SET late_count=late_count+1 WHERE id=?", (pid,))
    p = conn.execute("SELECT late_count FROM parents WHERE id=?", (pid,)).fetchone()
    conn.execute("INSERT OR IGNORE INTO late_payments (appointment_id,parent_id,teacher_id,days_late,compensation) VALUES (?,?,?,?,?)",
        (aid,pid,tid,days,0))
    if p and p[0] >= 3:
        conn.execute("INSERT INTO blacklist (user_type,ref_id,reason) VALUES ('parent',?,'逾期未支付超过3次')", (pid,))
        conn.execute("UPDATE users SET is_active=0 WHERE role='parent' AND ref_id=?", (pid,))
    conn.commit()
    conn.close()
    return p[0] if p else 0

# ── Admins ──
def admin_login(username, password):
    conn = get_db()
    a = conn.execute("SELECT * FROM admins WHERE username=? AND is_active=1", (username,)).fetchone()
    conn.close()
    if a and check_password_hash(a["password_hash"], password):
        return dict(a)
    return None

def get_admin(aid):
    conn = get_db()
    a = conn.execute("SELECT * FROM admins WHERE id=?", (aid,)).fetchone()
    conn.close()
    return dict(a) if a else None

def get_all_admins():
    conn = get_db()
    rows = conn.execute("SELECT id,username,name,role,is_active,created_at FROM admins ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_admin(username, password, name):
    conn = get_db()
    c = conn.execute("SELECT COUNT(*) FROM admins WHERE is_active=1").fetchone()[0]
    if c>=3: conn.close(); return None, "已达上限"
    try:
        conn.execute("INSERT INTO admins (username,password_hash,name) VALUES (?,?,?)",
            (username, generate_password_hash(password), name))
        conn.commit()
        aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return aid, None
    except:
        conn.close()
        return None, "用户名已存在"

def delete_admin(aid):
    conn = get_db()
    a = conn.execute("SELECT role FROM admins WHERE id=?", (aid,)).fetchone()
    if a and a["role"]=="super_admin": conn.close(); return False
    conn.execute("UPDATE admins SET is_active=0 WHERE id=?", (aid,))
    conn.commit(); conn.close()
    return True

def get_admin_stats():
    conn = get_db()
    s = lambda q: conn.execute(q).fetchone()[0]
    stats = {
        "teachers": s("SELECT COUNT(*) FROM teachers WHERE is_active=1 AND info_fee_paid=1"),
        "pending_fees": s("SELECT COUNT(*) FROM teachers WHERE is_active=1 AND info_fee_paid=0"),
        "teachers_total": s("SELECT COUNT(*) FROM teachers WHERE is_active=1"),
        "parents": s("SELECT COUNT(*) FROM parents WHERE is_active=1"),
        "appointments": s("SELECT COUNT(*) FROM appointments"),
        "paid": s("SELECT COUNT(*) FROM appointments WHERE status='paid'"),
        "completed": s("SELECT COUNT(*) FROM appointments WHERE status='completed'"),
        "refunded": s("SELECT COUNT(*) FROM appointments WHERE status='refunded'"),
        "revenue": s("SELECT COALESCE(SUM(amount),0) FROM earnings WHERE status='withdrawn'"),
        "fee_revenue": s("SELECT COALESCE(SUM(amount),0) FROM teacher_fees WHERE paid=1"),
        "pending_earnings": s("SELECT COALESCE(SUM(amount),0) FROM earnings WHERE status IN ('available','pending')"),
        "admins": s("SELECT COUNT(*) FROM admins WHERE is_active=1"),
        "blacklist": s("SELECT COUNT(*) FROM blacklist"),
        "compensation": s("SELECT COALESCE(SUM(compensation),0) FROM late_payments"),
    }
    conn.close()
    return stats

def get_all_teachers_admin():
    conn = get_db()
    rows = conn.execute("SELECT * FROM teachers ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_parents_admin():
    conn = get_db()
    rows = conn.execute("SELECT * FROM parents ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_appointments_admin():
    conn = get_db()
    rows = conn.execute("""SELECT a.*,t.name AS teacher_name,p.parent_name,p.student_name
        FROM appointments a JOIN teachers t ON a.teacher_id=t.id
        JOIN parents p ON a.parent_id=p.id ORDER BY a.created_at DESC""").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_blacklist():
    conn = get_db()
    rows = conn.execute("""SELECT b.*,p.parent_name,t.name AS teacher_name
        FROM blacklist b LEFT JOIN parents p ON b.ref_id=p.id AND b.user_type='parent'
        LEFT JOIN teachers t ON b.ref_id=t.id AND b.user_type='teacher'
        ORDER BY b.created_at DESC""").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_to_blacklist(user_type, ref_id, reason, admin_id):
    conn = get_db()
    conn.execute("INSERT INTO blacklist (user_type,ref_id,reason,created_by) VALUES (?,?,?,?)",
        (user_type,ref_id,reason,admin_id))
    conn.execute("UPDATE users SET is_active=0 WHERE role=? AND ref_id=?", (user_type,ref_id))
    conn.commit()
    conn.close()

def remove_from_blacklist(bl_id):
    conn = get_db()
    b = conn.execute("SELECT * FROM blacklist WHERE id=?", (bl_id,)).fetchone()
    if b:
        conn.execute("UPDATE users SET is_active=1 WHERE role=? AND ref_id=?", (b["user_type"],b["ref_id"]))
        conn.execute("DELETE FROM blacklist WHERE id=?", (bl_id,))
    conn.commit()
    conn.close()

# ── Appointments ──
def create_appointment(tid, pid, subject, budget):
    conn = get_db()
    conn.execute("INSERT INTO appointments (teacher_id,parent_id,subject,budget) VALUES (?,?,?,?)",
        (tid,pid,subject,budget))
    conn.commit()
    aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return aid

def get_appointment(aid):
    conn = get_db()
    r = conn.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    conn.close()
    return dict(r) if r else None

def update_appointment_status(aid, status):
    conn = get_db()
    conn.execute("UPDATE appointments SET status=?,updated_at=datetime('now','localtime') WHERE id=?", (status,aid))
    if status == "paid":
        t = conn.execute("SELECT teacher_id,budget FROM appointments WHERE id=?", (aid,)).fetchone()
        if t:
            conn.execute("INSERT INTO earnings (teacher_id,appointment_id,amount,status) VALUES (?,?,?,'available')",
                (t["teacher_id"],aid,t["budget"]))
    if status == "completed":
        amt = conn.execute("SELECT teacher_id,budget FROM appointments WHERE id=?", (aid,)).fetchone()
        if amt:
            conn.execute("UPDATE teachers SET completed_count=completed_count+1 WHERE id=?", (amt["teacher_id"],))
            t = conn.execute("SELECT completed_count FROM teachers WHERE id=?", (amt["teacher_id"],)).fetchone()
            if t and t[0] % 5 == 0 and t[0] > 0:
                conn.execute("INSERT INTO coupons (teacher_id) VALUES (?)", (amt["teacher_id"],))
    conn.commit()
    conn.close()

def get_teacher_appointments(tid):
    conn = get_db()
    rows = conn.execute("""SELECT a.*,p.parent_name,p.student_name,p.student_grade,
        p.subjects AS parent_subjects,p.requirements,p.budget AS parent_budget,
        p.email AS parent_email,p.phone AS parent_phone
        FROM appointments a JOIN parents p ON a.parent_id=p.id
        WHERE a.teacher_id=? ORDER BY a.created_at DESC""", (tid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def auto_pay_overdue():
    conn = get_db()
    overdue = conn.execute("""SELECT a.*,t.id AS tid FROM appointments a
        JOIN teachers t ON a.teacher_id=t.id
        WHERE a.status='accepted' AND datetime(a.created_at,'+24 hours')<datetime('now','localtime')
        AND a.auto_paid=0""").fetchall()
    for a in overdue:
        aid, pid, tid = a["id"], a["parent_id"], a["tid"]
        conn.execute("UPDATE appointments SET status='paid',auto_paid=1,updated_at=datetime('now','localtime') WHERE id=?", (aid,))
        comp = a["budget"] // 2
        conn.execute("INSERT INTO earnings (teacher_id,appointment_id,amount,status) VALUES (?,?,?,'available')",
            (tid, aid, comp))
        conn.execute("INSERT OR IGNORE INTO late_payments (appointment_id,parent_id,teacher_id,days_late,compensation) VALUES (?,?,?,1,?)",
            (aid, pid, tid, comp))
    conn.commit()
    conn.close()

# ── Feedback ──
def add_feedback(aid, frm, to, rating, content):
    conn = get_db()
    conn.execute("INSERT INTO feedback (appointment_id,from_role,to_role,rating,content) VALUES (?,?,?,?,?)",
        (aid,frm,to,rating,content))
    if to == "teacher" and rating > 0:
        a = conn.execute("SELECT teacher_id FROM appointments WHERE id=?", (aid,)).fetchone()
        if a:
            conn.execute("UPDATE teachers SET rating_total=rating_total+?,rating_count=rating_count+1 WHERE id=?",
                (rating, a["teacher_id"]))
    conn.commit()
    conn.close()

def get_feedback_for_teacher(tid):
    conn = get_db()
    rows = conn.execute("""SELECT f.*,p.parent_name FROM feedback f
        JOIN appointments a ON f.appointment_id=a.id
        JOIN parents p ON a.parent_id=p.id
        WHERE f.to_role='teacher' AND a.teacher_id=?
        ORDER BY f.created_at DESC""", (tid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_feedback_for_parent(pid):
    conn = get_db()
    rows = conn.execute("""SELECT f.*,t.name AS teacher_name FROM feedback f
        JOIN appointments a ON f.appointment_id=a.id
        JOIN teachers t ON a.teacher_id=t.id
        WHERE f.to_role='parent' AND a.parent_id=?
        ORDER BY f.created_at DESC""", (pid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Withdrawals ──
def get_available_earnings(tid):
    conn = get_db()
    r = conn.execute("SELECT COALESCE(SUM(amount),0) FROM earnings WHERE teacher_id=? AND status='available'", (tid,)).fetchone()[0]
    conn.close()
    return r

def create_withdrawal(tid, amount, account_type, account_info):
    conn = get_db()
    avail = conn.execute("SELECT COALESCE(SUM(amount),0) FROM earnings WHERE teacher_id=? AND status='available'", (tid,)).fetchone()[0]
    if amount > avail: conn.close(); return None, "余额不足"
    conn.execute("INSERT INTO withdrawals (teacher_id,amount,account_type,account_info) VALUES (?,?,?,?)",
        (tid,amount,account_type,account_info))
    conn.commit()
    conn.close()
    return True, None

def get_withdrawals(tid=None):
    conn = get_db()
    q = "SELECT w.*,t.name AS teacher_name FROM withdrawals w JOIN teachers t ON w.teacher_id=t.id"
    p = []
    if tid: q += " WHERE w.teacher_id=?"; p.append(tid)
    q += " ORDER BY w.created_at DESC"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def process_withdrawal(wid, status):
    conn = get_db()
    w = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
    if w:
        conn.execute("UPDATE withdrawals SET status=?,processed_at=datetime('now','localtime') WHERE id=?", (status,wid))
        if status == 'completed':
            conn.execute("UPDATE earnings SET status='withdrawn' WHERE teacher_id=? AND status='pending'", (w["teacher_id"],))
        conn.commit()
    conn.close()

# ── Coupons ──
def get_teacher_coupons(tid):
    conn = get_db()
    rows = conn.execute("SELECT * FROM coupons WHERE teacher_id=? AND used=0 ORDER BY created_at DESC", (tid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Stats ──
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM teachers WHERE is_active=1 AND info_fee_paid=1").fetchone()[0]
    provinces = conn.execute("SELECT COUNT(DISTINCT province) FROM teachers WHERE is_active=1 AND province!='' AND info_fee_paid=1").fetchone()[0]
    conn.close()
    return {"total":total,"provinces":provinces}


# ── Contracts ──
def create_contract(aid, signature, student_id_file=None):
    conn = get_db()
    conn.execute("INSERT INTO contracts (appointment_id,parent_signature,student_id_file) VALUES (?,?,?)",
        (aid, signature, student_id_file))
    conn.commit()
    cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return cid

def get_contract(aid):
    conn = get_db()
    r = conn.execute("SELECT * FROM contracts WHERE appointment_id=?", (aid,)).fetchone()
    conn.close()
    return dict(r) if r else None

# ── Verification Docs ──
def add_verification_doc(user_type, user_id, doc_type, filename, filepath):
    conn = get_db()
    conn.execute("INSERT INTO verification_docs (user_type,user_id,doc_type,filename,filepath) VALUES (?,?,?,?,?)",
        (user_type, user_id, doc_type, filename, filepath))
    conn.commit()
    conn.close()

def get_verification_docs(user_type=None, user_id=None):
    conn = get_db()
    q = "SELECT v.*,t.name AS teacher_name,p.parent_name FROM verification_docs v LEFT JOIN teachers t ON v.user_id=t.id AND v.user_type='teacher' LEFT JOIN parents p ON v.user_id=p.id AND v.user_type='parent' WHERE 1=1"
    params = []
    if user_type: q += " AND v.user_type=?"; params.append(user_type)
    if user_id: q += " AND v.user_id=?"; params.append(user_id)
    q += " ORDER BY v.created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_verification_status(doc_id, status):
    conn = get_db()
    conn.execute("UPDATE verification_docs SET status=?,reviewed_at=datetime('now','localtime') WHERE id=?", (status,doc_id))
    conn.commit()
    conn.close()

# ── Payment Accounts ──
def save_payment_account(user_type, user_id, acct_type, acct_name, acct_info):
    conn = get_db()
    existing = conn.execute("SELECT id FROM payment_accounts WHERE user_type=? AND user_id=? AND account_type=?", (user_type,user_id,acct_type)).fetchone()
    if existing:
        conn.execute("UPDATE payment_accounts SET account_name=?,account_info=? WHERE id=?", (acct_name,acct_info,existing["id"]))
    else:
        conn.execute("INSERT INTO payment_accounts (user_type,user_id,account_type,account_name,account_info) VALUES (?,?,?,?,?)", (user_type,user_id,acct_type,acct_name,acct_info))
    conn.commit(); conn.close()

def get_payment_accounts(user_type, user_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM payment_accounts WHERE user_type=? AND user_id=?", (user_type,user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── SMS ──
def save_sms_code(phone, code):
    conn = get_db()
    conn.execute("INSERT INTO sms_codes (phone,code) VALUES (?,?)", (phone,code))
    conn.commit(); conn.close()

def verify_sms_code(phone, code):
    conn = get_db()
    r = conn.execute("SELECT id FROM sms_codes WHERE phone=? AND code=? AND verified=0 AND datetime(created_at,'+5 minutes')>datetime('now','localtime') ORDER BY id DESC LIMIT 1", (phone,code)).fetchone()
    if r:
        conn.execute("UPDATE sms_codes SET verified=1 WHERE id=?", (r["id"],))
        conn.commit(); conn.close(); return True
    conn.close(); return False

def get_user_by_phone_role(phone, role):
    conn = get_db()
    if role == 'teacher':
        r = conn.execute("SELECT * FROM teachers WHERE phone=?", (phone,)).fetchone()
    else:
        r = conn.execute("SELECT * FROM parents WHERE phone=?", (phone,)).fetchone()
    conn.close()
    return dict(r) if r else None

# ── Update user password ──
def update_user_password(username, new_pw):
    conn = get_db()
    conn.execute("UPDATE users SET password_hash=? WHERE username=?", (generate_password_hash(new_pw),username))
    conn.commit(); conn.close()


# ── Lessons (QR Code) ──
import uuid

def create_lesson(aid):
    conn = get_db()
    token = uuid.uuid4().hex
    num = conn.execute("SELECT COALESCE(MAX(lesson_number),0)+1 FROM lessons WHERE appointment_id=?", (aid,)).fetchone()[0]
    conn.execute("INSERT INTO lessons (appointment_id,lesson_number,token) VALUES (?,?,?)", (aid,num,token))
    conn.commit()
    lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"id":lid, "number":num, "token":token}

def verify_lesson(token):
    conn = get_db()
    r = conn.execute("SELECT * FROM lessons WHERE token=? AND status='pending'", (token,)).fetchone()
    if r:
        conn.execute("UPDATE lessons SET status='completed',verified_at=datetime('now','localtime') WHERE id=?", (r["id"],))
        conn.commit(); conn.close(); return dict(r)
    conn.close(); return None

def get_lessons_for_appointment(aid):
    conn = get_db()
    rows = conn.execute("SELECT * FROM lessons WHERE appointment_id=? ORDER BY lesson_number", (aid,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_lesson_count_for_appointment(aid):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM lessons WHERE appointment_id=?", (aid,)).fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM lessons WHERE appointment_id=? AND status='completed'", (aid,)).fetchone()[0]
    conn.close(); return {"total":total, "completed":completed}

# ── Payment Refusal ──
def record_payment_refusal(aid):
    conn = get_db()
    a = conn.execute("SELECT parent_id,teacher_id,budget FROM appointments WHERE id=?", (aid,)).fetchone()
    if not a: conn.close(); return None, "未找到申请"
    
    conn.execute("UPDATE parents SET late_count=late_count+1 WHERE id=?", (a["parent_id"],))
    p = conn.execute("SELECT late_count FROM parents WHERE id=?", (a["parent_id"],)).fetchone()
    
    # Compensate teacher 50%
    comp = a["budget"] // 2 if a["budget"] else 0
    if comp > 0:
        conn.execute("INSERT INTO earnings (teacher_id,appointment_id,amount,status) VALUES (?,?,?,'available')",
            (a["teacher_id"], aid, comp))
        conn.execute("INSERT OR IGNORE INTO late_payments (appointment_id,parent_id,teacher_id,days_late,compensation) VALUES (?,?,?,0,?)",
            (aid, a["parent_id"], a["teacher_id"], comp))
    
    # Auto blacklist after 3 refusals

def get_all_admins():
    conn = get_db()
    rows = conn.execute("SELECT id,username,name,role,is_active,created_at FROM admins ORDER BY id").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_admin(username, password, name):
    conn = get_db()
    c = conn.execute("SELECT COUNT(*) FROM admins WHERE is_active=1").fetchone()[0]
    if c>=3: conn.close(); return None, "已达上限"
    try:
        conn.execute("INSERT INTO admins (username,password_hash,name) VALUES (?,?,?)",
            (username, generate_password_hash(password), name))
        conn.commit()
        aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return aid, None
    except:
        conn.close()
        return None, "用户名已存在"

def delete_admin(aid):
    conn = get_db()
    a = conn.execute("SELECT role FROM admins WHERE id=?", (aid,)).fetchone()
    if a and a["role"]=="super_admin": conn.close(); return False
    conn.execute("UPDATE admins SET is_active=0 WHERE id=?", (aid,))
    conn.commit(); conn.close()
    return True

def get_admin_stats():
    conn = get_db()
    s = lambda q: conn.execute(q).fetchone()[0]
    stats = {
        "teachers": s("SELECT COUNT(*) FROM teachers WHERE is_active=1 AND info_fee_paid=1"),
        "pending_fees": s("SELECT COUNT(*) FROM teachers WHERE is_active=1 AND info_fee_paid=0"),
        "teachers_total": s("SELECT COUNT(*) FROM teachers WHERE is_active=1"),
        "parents": s("SELECT COUNT(*) FROM parents WHERE is_active=1"),
        "appointments": s("SELECT COUNT(*) FROM appointments"),
        "paid": s("SELECT COUNT(*) FROM appointments WHERE status='paid'"),
        "completed": s("SELECT COUNT(*) FROM appointments WHERE status='completed'"),
        "refunded": s("SELECT COUNT(*) FROM appointments WHERE status='refunded'"),
        "revenue": s("SELECT COALESCE(SUM(amount),0) FROM earnings WHERE status='withdrawn'"),
        "fee_revenue": s("SELECT COALESCE(SUM(amount),0) FROM teacher_fees WHERE paid=1"),
        "pending_earnings": s("SELECT COALESCE(SUM(amount),0) FROM earnings WHERE status IN ('available','pending')"),
        "admins": s("SELECT COUNT(*) FROM admins WHERE is_active=1"),
        "blacklist": s("SELECT COUNT(*) FROM blacklist"),
        "compensation": s("SELECT COALESCE(SUM(compensation),0) FROM late_payments"),
    }
    conn.close()
    return stats

def get_all_teachers_admin():
    conn = get_db()
    rows = conn.execute("SELECT * FROM teachers ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_parents_admin():
    conn = get_db()
    rows = conn.execute("SELECT * FROM parents ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_appointments_admin():
    conn = get_db()
    rows = conn.execute("""SELECT a.*,t.name AS teacher_name,p.parent_name,p.student_name
        FROM appointments a JOIN teachers t ON a.teacher_id=t.id
        JOIN parents p ON a.parent_id=p.id ORDER BY a.created_at DESC""").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_blacklist():
    conn = get_db()
    rows = conn.execute("""SELECT b.*,p.parent_name,t.name AS teacher_name
        FROM blacklist b LEFT JOIN parents p ON b.ref_id=p.id AND b.user_type='parent'
        LEFT JOIN teachers t ON b.ref_id=t.id AND b.user_type='teacher'
        ORDER BY b.created_at DESC""").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_to_blacklist(user_type, ref_id, reason, admin_id):
    conn = get_db()
    conn.execute("INSERT INTO blacklist (user_type,ref_id,reason,created_by) VALUES (?,?,?,?)",
        (user_type,ref_id,reason,admin_id))
    conn.execute("UPDATE users SET is_active=0 WHERE role=? AND ref_id=?", (user_type,ref_id))
    conn.commit()
    conn.close()

def remove_from_blacklist(bl_id):
    conn = get_db()
    b = conn.execute("SELECT * FROM blacklist WHERE id=?", (bl_id,)).fetchone()
    if b:
        conn.execute("UPDATE users SET is_active=1 WHERE role=? AND ref_id=?", (b["user_type"],b["ref_id"]))
        conn.execute("DELETE FROM blacklist WHERE id=?", (bl_id,))
    conn.commit()
    conn.close()

# ── Appointments ──
def create_appointment(tid, pid, subject, budget):
    conn = get_db()
    conn.execute("INSERT INTO appointments (teacher_id,parent_id,subject,budget) VALUES (?,?,?,?)",
        (tid,pid,subject,budget))
    conn.commit()
    aid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return aid

def get_appointment(aid):
    conn = get_db()
    r = conn.execute("SELECT * FROM appointments WHERE id=?", (aid,)).fetchone()
    conn.close()
    return dict(r) if r else None

def update_appointment_status(aid, status):
    conn = get_db()
    conn.execute("UPDATE appointments SET status=?,updated_at=datetime('now','localtime') WHERE id=?", (status,aid))
    if status == "paid":
        t = conn.execute("SELECT teacher_id,budget FROM appointments WHERE id=?", (aid,)).fetchone()
        if t:
            conn.execute("INSERT INTO earnings (teacher_id,appointment_id,amount,status) VALUES (?,?,?,'available')",
                (t["teacher_id"],aid,t["budget"]))
    if status == "completed":
        amt = conn.execute("SELECT teacher_id,budget FROM appointments WHERE id=?", (aid,)).fetchone()
        if amt:
            conn.execute("UPDATE teachers SET completed_count=completed_count+1 WHERE id=?", (amt["teacher_id"],))
            t = conn.execute("SELECT completed_count FROM teachers WHERE id=?", (amt["teacher_id"],)).fetchone()
            if t and t[0] % 5 == 0 and t[0] > 0:
                conn.execute("INSERT INTO coupons (teacher_id) VALUES (?)", (amt["teacher_id"],))
    conn.commit()
    conn.close()

def get_teacher_appointments(tid):
    conn = get_db()
    rows = conn.execute("""SELECT a.*,p.parent_name,p.student_name,p.student_grade,
        p.subjects AS parent_subjects,p.requirements,p.budget AS parent_budget,
        p.email AS parent_email,p.phone AS parent_phone
        FROM appointments a JOIN parents p ON a.parent_id=p.id
        WHERE a.teacher_id=? ORDER BY a.created_at DESC""", (tid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def auto_pay_overdue():
    conn = get_db()
    overdue = conn.execute("""SELECT a.*,t.id AS tid FROM appointments a
        JOIN teachers t ON a.teacher_id=t.id
        WHERE a.status='accepted' AND datetime(a.created_at,'+24 hours')<datetime('now','localtime')
        AND a.auto_paid=0""").fetchall()
    for a in overdue:
        aid, pid, tid = a["id"], a["parent_id"], a["tid"]
        conn.execute("UPDATE appointments SET status='paid',auto_paid=1,updated_at=datetime('now','localtime') WHERE id=?", (aid,))
        comp = a["budget"] // 2
        conn.execute("INSERT INTO earnings (teacher_id,appointment_id,amount,status) VALUES (?,?,?,'available')",
            (tid, aid, comp))
        conn.execute("INSERT OR IGNORE INTO late_payments (appointment_id,parent_id,teacher_id,days_late,compensation) VALUES (?,?,?,1,?)",
            (aid, pid, tid, comp))
    conn.commit()
    conn.close()

# ── Feedback ──
def add_feedback(aid, frm, to, rating, content):
    conn = get_db()
    conn.execute("INSERT INTO feedback (appointment_id,from_role,to_role,rating,content) VALUES (?,?,?,?,?)",
        (aid,frm,to,rating,content))
    if to == "teacher" and rating > 0:
        a = conn.execute("SELECT teacher_id FROM appointments WHERE id=?", (aid,)).fetchone()
        if a:
            conn.execute("UPDATE teachers SET rating_total=rating_total+?,rating_count=rating_count+1 WHERE id=?",
                (rating, a["teacher_id"]))
    conn.commit()
    conn.close()

def get_feedback_for_teacher(tid):
    conn = get_db()
    rows = conn.execute("""SELECT f.*,p.parent_name FROM feedback f
        JOIN appointments a ON f.appointment_id=a.id
        JOIN parents p ON a.parent_id=p.id
        WHERE f.to_role='teacher' AND a.teacher_id=?
        ORDER BY f.created_at DESC""", (tid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_feedback_for_parent(pid):
    conn = get_db()
    rows = conn.execute("""SELECT f.*,t.name AS teacher_name FROM feedback f
        JOIN appointments a ON f.appointment_id=a.id
        JOIN teachers t ON a.teacher_id=t.id
        WHERE f.to_role='parent' AND a.parent_id=?
        ORDER BY f.created_at DESC""", (pid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Withdrawals ──
def get_available_earnings(tid):
    conn = get_db()
    r = conn.execute("SELECT COALESCE(SUM(amount),0) FROM earnings WHERE teacher_id=? AND status='available'", (tid,)).fetchone()[0]
    conn.close()
    return r

def create_withdrawal(tid, amount, account_type, account_info):
    conn = get_db()
    avail = conn.execute("SELECT COALESCE(SUM(amount),0) FROM earnings WHERE teacher_id=? AND status='available'", (tid,)).fetchone()[0]
    if amount > avail: conn.close(); return None, "余额不足"
    conn.execute("INSERT INTO withdrawals (teacher_id,amount,account_type,account_info) VALUES (?,?,?,?)",
        (tid,amount,account_type,account_info))
    conn.commit()
    conn.close()
    return True, None

def get_withdrawals(tid=None):
    conn = get_db()
    q = "SELECT w.*,t.name AS teacher_name FROM withdrawals w JOIN teachers t ON w.teacher_id=t.id"
    p = []
    if tid: q += " WHERE w.teacher_id=?"; p.append(tid)
    q += " ORDER BY w.created_at DESC"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def process_withdrawal(wid, status):
    conn = get_db()
    w = conn.execute("SELECT * FROM withdrawals WHERE id=?", (wid,)).fetchone()
    if w:
        conn.execute("UPDATE withdrawals SET status=?,processed_at=datetime('now','localtime') WHERE id=?", (status,wid))
        if status == 'completed':
            conn.execute("UPDATE earnings SET status='withdrawn' WHERE teacher_id=? AND status='pending'", (w["teacher_id"],))
        conn.commit()
    conn.close()

# ── Coupons ──
def get_teacher_coupons(tid):
    conn = get_db()
    rows = conn.execute("SELECT * FROM coupons WHERE teacher_id=? AND used=0 ORDER BY created_at DESC", (tid,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Stats ──
def get_stats():
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM teachers WHERE is_active=1 AND info_fee_paid=1").fetchone()[0]
    provinces = conn.execute("SELECT COUNT(DISTINCT province) FROM teachers WHERE is_active=1 AND province!='' AND info_fee_paid=1").fetchone()[0]
    conn.close()
    return {"total":total,"provinces":provinces}


# ── Contracts ──
def create_contract(aid, signature, student_id_file=None):
    conn = get_db()
    conn.execute("INSERT INTO contracts (appointment_id,parent_signature,student_id_file) VALUES (?,?,?)",
        (aid, signature, student_id_file))
    conn.commit()
    cid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return cid

def get_contract(aid):
    conn = get_db()
    r = conn.execute("SELECT * FROM contracts WHERE appointment_id=?", (aid,)).fetchone()
    conn.close()
    return dict(r) if r else None

# ── Verification Docs ──
def add_verification_doc(user_type, user_id, doc_type, filename, filepath):
    conn = get_db()
    conn.execute("INSERT INTO verification_docs (user_type,user_id,doc_type,filename,filepath) VALUES (?,?,?,?,?)",
        (user_type, user_id, doc_type, filename, filepath))
    conn.commit()
    conn.close()

def get_verification_docs(user_type=None, user_id=None):
    conn = get_db()
    q = "SELECT v.*,t.name AS teacher_name,p.parent_name FROM verification_docs v LEFT JOIN teachers t ON v.user_id=t.id AND v.user_type='teacher' LEFT JOIN parents p ON v.user_id=p.id AND v.user_type='parent' WHERE 1=1"
    params = []
    if user_type: q += " AND v.user_type=?"; params.append(user_type)
    if user_id: q += " AND v.user_id=?"; params.append(user_id)
    q += " ORDER BY v.created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_verification_status(doc_id, status):
    conn = get_db()
    conn.execute("UPDATE verification_docs SET status=?,reviewed_at=datetime('now','localtime') WHERE id=?", (status,doc_id))
    conn.commit()
    conn.close()

# ── Payment Accounts ──
def save_payment_account(user_type, user_id, acct_type, acct_name, acct_info):
    conn = get_db()
    existing = conn.execute("SELECT id FROM payment_accounts WHERE user_type=? AND user_id=? AND account_type=?", (user_type,user_id,acct_type)).fetchone()
    if existing:
        conn.execute("UPDATE payment_accounts SET account_name=?,account_info=? WHERE id=?", (acct_name,acct_info,existing["id"]))
    else:
        conn.execute("INSERT INTO payment_accounts (user_type,user_id,account_type,account_name,account_info) VALUES (?,?,?,?,?)", (user_type,user_id,acct_type,acct_name,acct_info))
    conn.commit(); conn.close()

def get_payment_accounts(user_type, user_id):
    conn = get_db()
    rows = conn.execute("SELECT * FROM payment_accounts WHERE user_type=? AND user_id=?", (user_type,user_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── SMS ──
def save_sms_code(phone, code):
    conn = get_db()
    conn.execute("INSERT INTO sms_codes (phone,code) VALUES (?,?)", (phone,code))
    conn.commit(); conn.close()

def verify_sms_code(phone, code):
    conn = get_db()
    r = conn.execute("SELECT id FROM sms_codes WHERE phone=? AND code=? AND verified=0 AND datetime(created_at,'+5 minutes')>datetime('now','localtime') ORDER BY id DESC LIMIT 1", (phone,code)).fetchone()
    if r:
        conn.execute("UPDATE sms_codes SET verified=1 WHERE id=?", (r["id"],))
        conn.commit(); conn.close(); return True
    conn.close(); return False

def get_user_by_phone_role(phone, role):
    conn = get_db()
    if role == 'teacher':
        r = conn.execute("SELECT * FROM teachers WHERE phone=?", (phone,)).fetchone()
    else:
        r = conn.execute("SELECT * FROM parents WHERE phone=?", (phone,)).fetchone()
    conn.close()
    return dict(r) if r else None

# ── Update user password ──
def update_user_password(username, new_pw):
    conn = get_db()
    conn.execute("UPDATE users SET password_hash=? WHERE username=?", (generate_password_hash(new_pw),username))
    conn.commit(); conn.close()


# ── Lessons (QR Code) ──
import uuid

def create_lesson(aid):
    conn = get_db()
    token = uuid.uuid4().hex
    num = conn.execute("SELECT COALESCE(MAX(lesson_number),0)+1 FROM lessons WHERE appointment_id=?", (aid,)).fetchone()[0]
    conn.execute("INSERT INTO lessons (appointment_id,lesson_number,token) VALUES (?,?,?)", (aid,num,token))
    conn.commit()
    lid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"id":lid, "number":num, "token":token}

def verify_lesson(token):
    conn = get_db()
    r = conn.execute("SELECT * FROM lessons WHERE token=? AND status='pending'", (token,)).fetchone()
    if r:
        conn.execute("UPDATE lessons SET status='completed',verified_at=datetime('now','localtime') WHERE id=?", (r["id"],))
        conn.commit(); conn.close(); return dict(r)
    conn.close(); return None

def get_lessons_for_appointment(aid):
    conn = get_db()
    rows = conn.execute("SELECT * FROM lessons WHERE appointment_id=? ORDER BY lesson_number", (aid,)).fetchall()
    conn.close(); return [dict(r) for r in rows]

def get_lesson_count_for_appointment(aid):
    conn = get_db()
    total = conn.execute("SELECT COUNT(*) FROM lessons WHERE appointment_id=?", (aid,)).fetchone()[0]
    completed = conn.execute("SELECT COUNT(*) FROM lessons WHERE appointment_id=? AND status='completed'", (aid,)).fetchone()[0]
    conn.close(); return {"total":total, "completed":completed}

# ── Payment Refusal ──
def record_payment_refusal(aid):
    conn = get_db()
    a = conn.execute("SELECT parent_id,teacher_id,budget FROM appointments WHERE id=?", (aid,)).fetchone()
    if not a: conn.close(); return None, "未找到申请"
    
    conn.execute("UPDATE parents SET late_count=late_count+1 WHERE id=?", (a["parent_id"],))
    p = conn.execute("SELECT late_count FROM parents WHERE id=?", (a["parent_id"],)).fetchone()
    
    # Compensate teacher 50%
    comp = a["budget"] // 2 if a["budget"] else 0
    if comp > 0:
        conn.execute("INSERT INTO earnings (teacher_id,appointment_id,amount,status) VALUES (?,?,?,'available')",
            (a["teacher_id"], aid, comp))
        conn.execute("INSERT OR IGNORE INTO late_payments (appointment_id,parent_id,teacher_id,days_late,compensation) VALUES (?,?,?,0,?)",
            (aid, a["parent_id"], a["teacher_id"], comp))
    
    # Auto blacklist after 3 refusals
    if p and p[0] >= 3:
        conn.execute("INSERT INTO blacklist (user_type,ref_id,reason) VALUES ('parent',?,'拒绝支付超过3次')", (a["parent_id"],))
        conn.execute("UPDATE users SET is_active=0 WHERE role='parent' AND ref_id=?", (a["parent_id"],))
    
    conn.execute("UPDATE appointments SET status='refunded',updated_at=datetime('now','localtime') WHERE id=?", (aid,))
    conn.commit(); conn.close()
    return comp, p[0] if p else 0

