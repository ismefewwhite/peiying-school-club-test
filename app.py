import os
import base64
from datetime import datetime
from io import BytesIO
from functools import wraps
import pytz # 處理時區
from flask import Flask, render_template_string, request, redirect, url_for, flash, send_file, session
from flask_sqlalchemy import SQLAlchemy
import pandas as pd

# 初始化 Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school_clubs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# 設定上傳檔案大小限制 (例如 5MB)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# 管理者帳號設定
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'password123' 

db = SQLAlchemy(app)

# 設定台灣時區
TAIWAN_TZ = pytz.timezone('Asia/Taipei')

def get_taiwan_now():
    """取得目前的台灣時間"""
    return datetime.now(TAIWAN_TZ).replace(tzinfo=None)

# ==========================================
# 1. 資料庫模型
# ==========================================

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    site_title = db.Column(db.String(100), default="快樂國小社團報名")
    welcome_msg = db.Column(db.Text, default="歡迎選修喜歡的社團！")
    # 這裡改成存圖片的 Base64 編碼
    banner_image_data = db.Column(db.Text, nullable=True) 

class Club(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # 封面圖片 Base64
    image_data = db.Column(db.Text, nullable=True)
    
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    max_regular = db.Column(db.Integer, default=20)
    max_waitlist = db.Column(db.Integer, default=5)
    
    weekday = db.Column(db.String(10), nullable=False)
    class_start = db.Column(db.Time, nullable=False)
    class_end = db.Column(db.Time, nullable=False)
    
    registrations = db.relationship('Registration', backref='club', cascade="all, delete-orphan")

    def current_regular_count(self):
        return Registration.query.filter_by(club_id=self.id, status='正取').count()

    def current_waitlist_count(self):
        return Registration.query.filter_by(club_id=self.id, status='備取').count()

class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    club_id = db.Column(db.Integer, db.ForeignKey('club.id'), nullable=False)
    student_name = db.Column(db.String(50), nullable=False)
    student_class = db.Column(db.String(20), nullable=False)
    parent_phone = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=get_taiwan_now)

# ==========================================
# 2. 輔助函式
# ==========================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('請先登入管理者帳號', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_system_config():
    conf = SystemConfig.query.first()
    if not conf:
        conf = SystemConfig()
        db.session.add(conf)
        db.session.commit()
    return conf

def process_image_upload(file_obj):
    """將上傳的檔案轉為 Base64 字串"""
    if file_obj and file_obj.filename != '':
        # 讀取檔案並轉碼
        img_data = file_obj.read()
        b64_str = base64.b64encode(img_data).decode('utf-8')
        return b64_str
    return None

# ==========================================
# 3. HTML 模板 (加入活潑設計)
# ==========================================

BASE_LAYOUT = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ config.site_title }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- 加入 Google Fonts 和一些自訂 CSS -->
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body { 
            background-color: #f0f8ff; /* 淡藍色背景 */
            font-family: 'Noto Sans TC', sans-serif;
            background-image: linear-gradient(120deg, #fdfbfb 0%, #ebedee 100%);
        }
        .navbar {
            background: linear-gradient(to right, #4facfe 0%, #00f2fe 100%); /* 漸層導覽列 */
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .navbar-brand { font-weight: 700; letter-spacing: 1px; color: white !important; }
        .card {
            border: none;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
            transition: transform 0.3s ease;
            overflow: hidden;
        }
        .card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.1); }
        .btn-primary {
            background-color: #4facfe; border: none;
            border-radius: 50px; padding: 10px 20px;
        }
        .btn-primary:hover { background-color: #00f2fe; }
        
        .banner-area {
            background: white; border-radius: 20px; padding: 2rem;
            margin-bottom: 2rem; text-align: center;
            box-shadow: 0 10px 25px rgba(100, 100, 100, 0.1);
        }
        .banner-img {
            max-width: 100%; max-height: 350px;
            border-radius: 15px; margin-top: 15px;
            object-fit: cover;
        }
        .club-cover {
            height: 180px; width: 100%; object-fit: cover;
            background-color: #e9ecef;
        }
        .status-badge { position: absolute; top: 10px; right: 10px; font-weight: bold; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark mb-4">
        <div class="container">
            <a class="navbar-brand" href="/">🏫 {{ config.site_title }}</a>
            <div class="ms-auto">
                {% if session.get('logged_in') %}
                    <a href="/admin" class="btn btn-warning btn-sm fw-bold shadow-sm">⚙️ 管理後台</a>
                    <a href="/logout" class="btn btn-light btn-sm ms-2 text-primary fw-bold">登出</a>
                {% else %}
                    <a href="/login" class="btn btn-outline-light btn-sm fw-bold">🔒 管理者登入</a>
                {% endif %}
            </div>
        </div>
    </nav>
    
    <div class="container pb-5">
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert alert-{{ category }} shadow-sm rounded-pill px-4">{{ message }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
        
        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.ckeditor.com/ckeditor5/39.0.1/classic/ckeditor.js"></script>
</body>
</html>
"""

LOGIN_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", """
<div class="row justify-content-center align-items-center" style="min-height: 60vh;">
    <div class="col-md-4">
        <div class="card p-4">
            <h3 class="text-center mb-4 text-primary fw-bold">管理者登入</h3>
            <form method="POST">
                <div class="mb-3">
                    <label class="fw-bold text-secondary">帳號</label>
                    <input type="text" name="username" class="form-control form-control-lg bg-light" required>
                </div>
                <div class="mb-4">
                    <label class="fw-bold text-secondary">密碼</label>
                    <input type="password" name="password" class="form-control form-control-lg bg-light" required>
                </div>
                <button type="submit" class="btn btn-primary w-100 btn-lg shadow">確認登入</button>
            </form>
        </div>
    </div>
</div>
""")

HOME_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", """
<div class="banner-area">
    <h1 class="fw-bold text-primary mb-3">{{ config.site_title }}</h1>
    <div class="lead text-secondary mb-3">{{ config.welcome_msg | safe }}</div>
    {% if config.banner_image_data %}
        <img src="data:image/jpeg;base64,{{ config.banner_image_data }}" class="banner-img shadow">
    {% endif %}
</div>

<div class="d-flex align-items-center mb-4">
    <div class="bg-primary rounded-pill" style="width: 5px; height: 30px; margin-right: 10px;"></div>
    <h3 class="m-0 fw-bold text-dark">熱門社團一覽</h3>
</div>

<div class="row g-4">
    {% for club in clubs %}
    <div class="col-md-6 col-lg-4">
        <div class="card h-100">
            <!-- 封面圖片 -->
            {% if club.image_data %}
                <img src="data:image/jpeg;base64,{{ club.image_data }}" class="club-cover">
            {% else %}
                <div class="club-cover d-flex align-items-center justify-content-center text-muted bg-light">
                    (無封面圖片)
                </div>
            {% endif %}
            
            <span class="badge bg-warning text-dark status-badge shadow-sm">
                {{ club.weekday }} {{ club.class_start.strftime('%H:%M') }}
            </span>

            <div class="card-body">
                <h4 class="card-title fw-bold">{{ club.name }}</h4>
                <p class="text-muted small mb-2">
                    <i class="bi bi-clock"></i> 報名截止：{{ club.end_time.strftime('%m/%d %H:%M') }}
                </p>
                <div class="d-flex justify-content-between text-center my-3 p-2 rounded bg-light border">
                    <div>
                        <span class="d-block fw-bold text-success fs-5">{{ club.current_regular_count() }}/{{ club.max_regular }}</span>
                        <small class="text-muted">正取名額</small>
                    </div>
                    <div class="border-start"></div>
                    <div>
                        <span class="d-block fw-bold text-secondary fs-5">{{ club.current_waitlist_count() }}/{{ club.max_waitlist }}</span>
                        <small class="text-muted">備取名額</small>
                    </div>
                </div>
                <a href="/club/{{ club.id }}" class="btn btn-outline-primary w-100 fw-bold rounded-pill">👉 查看詳情 & 報名</a>
            </div>
        </div>
    </div>
    {% else %}
    <div class="col-12 text-center py-5">
        <h4 class="text-muted">目前沒有開放的社團 🐢</h4>
    </div>
    {% endfor %}
</div>
""")

CLUB_DETAIL_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", """
<div class="row">
    <div class="col-lg-8 mb-4">
        <div class="card h-100">
            {% if club.image_data %}
                <img src="data:image/jpeg;base64,{{ club.image_data }}" style="height: 300px; object-fit: cover;">
            {% endif %}
            <div class="card-body p-4">
                <div class="d-flex justify-content-between align-items-center mb-3">
                    <h2 class="fw-bold text-primary mb-0">{{ club.name }}</h2>
                    <span class="badge bg-info text-dark fs-6 shadow-sm">
                        {{ club.weekday }} {{ club.class_start.strftime('%H:%M') }} - {{ club.class_end.strftime('%H:%M') }}
                    </span>
                </div>
                <hr>
                <h5 class="fw-bold text-secondary mb-3">社團介紹</h5>
                <div class="club-description lh-lg">
                    {{ club.description | safe }}
                </div>
            </div>
        </div>
    </div>
    <div class="col-lg-4">
        <div class="card border-0 shadow sticky-top" style="top: 20px;">
            <div class="card-header bg-primary text-white text-center py-3">
                <h5 class="m-0 fw-bold">📝 學生報名表</h5>
            </div>
            <div class="card-body p-4 bg-light">
                {% if can_register %}
                    <div class="alert alert-info small border-0 shadow-sm">
                        👋 現在是台灣時間 <b>{{ now_str }}</b><br>
                        請確認時間不衝突再報名喔！
                    </div>
                    <form action="/register/{{ club.id }}" method="POST">
                        <div class="mb-3">
                            <label class="form-label fw-bold">學生姓名</label>
                            <input type="text" name="student_name" class="form-control rounded-pill" required placeholder="例如：王小明">
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold">班級座號</label>
                            <input type="text" name="student_class" class="form-control rounded-pill" required placeholder="例如：60105">
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold">家長電話</label>
                            <input type="tel" name="parent_phone" class="form-control rounded-pill" required>
                        </div>
                        <button type="submit" class="btn btn-success w-100 py-2 fw-bold rounded-pill shadow">確認報名</button>
                    </form>
                {% else %}
                    <div class="text-center py-4">
                        <div class="display-1 mb-3">🔒</div>
                        <h4 class="text-danger fw-bold">無法報名</h4>
                        <p class="text-muted">{{ status_message }}</p>
                        <small class="text-muted">現在時間：{{ now_str }}</small>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
</div>
""")

ADMIN_DASHBOARD_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", """
<div class="d-flex justify-content-between align-items-center mb-4">
    <h2 class="fw-bold text-dark">⚙️ 管理者後台</h2>
    <div>
        <a href="/admin/config" class="btn btn-info text-white fw-bold me-2 shadow-sm">🏠 設定首頁</a>
        <a href="/admin/create" class="btn btn-success fw-bold shadow-sm">+ 新增社團</a>
    </div>
</div>

<div class="card p-0 overflow-hidden shadow">
    <table class="table table-hover mb-0 align-middle">
        <thead class="bg-dark text-white">
            <tr>
                <th class="py-3 ps-4">社團名稱</th>
                <th>上課時間</th>
                <th>報名狀況 (正/備)</th>
                <th class="text-end pe-4">功能操作</th>
            </tr>
        </thead>
        <tbody>
            {% for club in clubs %}
            <tr>
                <td class="ps-4 fw-bold">{{ club.name }}</td>
                <td><span class="badge bg-light text-dark border">{{ club.weekday }} {{ club.class_start.strftime('%H:%M') }}</span></td>
                <td>
                    <span class="text-success fw-bold">{{ club.current_regular_count() }}/{{ club.max_regular }}</span>
                    <span class="text-muted mx-1">|</span>
                    <span class="text-secondary fw-bold">{{ club.current_waitlist_count() }}/{{ club.max_waitlist }}</span>
                </td>
                <td class="text-end pe-4">
                    <a href="/admin/edit/{{ club.id }}" class="btn btn-sm btn-warning fw-bold text-dark me-1">✏️ 編輯</a>
                    <a href="/admin/export/{{ club.id }}" class="btn btn-sm btn-outline-success fw-bold me-1">📥 名單</a>
                    <a href="/admin/delete/{{ club.id }}" class="btn btn-sm btn-outline-danger fw-bold" onclick="return confirm('確定刪除？')">🗑️</a>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
""")

# 表單共用模板 (新增/編輯)
FORM_TEMPLATE_CONTENT = """
<h2 class="mb-4 fw-bold">{{ title }}</h2>
<form method="POST" enctype="multipart/form-data" class="card p-4 shadow-sm border-0">
    <div class="row">
        <div class="col-md-6 mb-3">
            <label class="form-label fw-bold">社團名稱</label>
            <input type="text" name="name" class="form-control" value="{{ club.name if club else '' }}" required>
        </div>
        <div class="col-md-3 mb-3">
            <label class="form-label fw-bold">正取名額</label>
            <input type="number" name="max_regular" class="form-control" value="{{ club.max_regular if club else 20 }}" required>
        </div>
        <div class="col-md-3 mb-3">
            <label class="form-label fw-bold">備取名額</label>
            <input type="number" name="max_waitlist" class="form-control" value="{{ club.max_waitlist if club else 5 }}" required>
        </div>
    </div>

    <!-- 圖片上傳區 -->
    <div class="mb-4 p-3 bg-light rounded border">
        <label class="form-label fw-bold text-primary">🖼️ 社團封面圖片 (直接上傳)</label>
        <input type="file" name="image_file" class="form-control" accept="image/*">
        {% if club and club.image_data %}
            <div class="mt-2 text-muted small">目前已有圖片，若不修改請留空。</div>
        {% endif %}
    </div>

    <h5 class="mt-2 text-primary border-bottom pb-2 fw-bold">🕒 上課時段 (衝堂檢查用)</h5>
    <div class="row mb-3">
        <div class="col-md-4 mb-3">
            <label class="form-label fw-bold">上課日</label>
            <select name="weekday" class="form-select" required>
                {% for day in ['星期一','星期二','星期三','星期四','星期五','星期六','星期日'] %}
                    <option value="{{ day }}" {% if club and club.weekday == day %}selected{% endif %}>{{ day }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="col-md-4 mb-3">
            <label class="form-label fw-bold">開始時間</label>
            <input type="time" name="class_start" class="form-control" value="{{ club.class_start.strftime('%H:%M') if club else '' }}" required>
        </div>
        <div class="col-md-4 mb-3">
            <label class="form-label fw-bold">結束時間</label>
            <input type="time" name="class_end" class="form-control" value="{{ club.class_end.strftime('%H:%M') if club else '' }}" required>
        </div>
    </div>

    <h5 class="mt-2 text-primary border-bottom pb-2 fw-bold">📅 報名開放期間</h5>
    <div class="row">
        <div class="col-md-6 mb-3">
            <label class="form-label fw-bold">開放報名</label>
            <!-- 注意：datetime-local 需要 YYYY-MM-DDTHH:MM 格式 -->
            <input type="datetime-local" name="start_time" class="form-control" 
                   value="{{ club.start_time.strftime('%Y-%m-%dT%H:%M') if club else '' }}" required>
        </div>
        <div class="col-md-6 mb-3">
            <label class="form-label fw-bold">截止報名</label>
            <input type="datetime-local" name="end_time" class="form-control" 
                   value="{{ club.end_time.strftime('%Y-%m-%dT%H:%M') if club else '' }}" required>
        </div>
    </div>
    
    <div class="mb-3">
        <label class="form-label fw-bold">詳細介紹</label>
        <textarea name="description" id="editor">{{ club.description if club else '' }}</textarea>
    </div>
    <div class="d-flex gap-2">
        <button type="submit" class="btn btn-primary btn-lg flex-grow-1 shadow">儲存設定</button>
        <a href="/admin" class="btn btn-secondary btn-lg shadow">取消</a>
    </div>
</form>
<script>
    ClassicEditor.create(document.querySelector('#editor')).catch(error => console.error(error));
</script>
<style> .ck-editor__editable_inline { min-height: 250px; } </style>
"""

ADMIN_FORM_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", FORM_TEMPLATE_CONTENT)

ADMIN_CONFIG_TEMPLATE = BASE_LAYOUT.replace("{% block content %}{% endblock %}", """
<h2 class="mb-4 fw-bold text-primary">🏠 設定首頁與公告</h2>
<form method="POST" enctype="multipart/form-data" class="card p-4 shadow-sm border-0">
    <div class="mb-3">
        <label class="form-label fw-bold">網站標題</label>
        <input type="text" name="site_title" class="form-control form-control-lg" value="{{ config.site_title }}" required>
    </div>
    
    <div class="mb-4 p-3 bg-light rounded border">
        <label class="form-label fw-bold text-primary">🖼️ 首頁橫幅圖片 (Banner)</label>
        <input type="file" name="banner_file" class="form-control" accept="image/*">
        {% if config.banner_image_data %}
            <div class="mt-2">
                <small class="text-muted">目前預覽：</small><br>
                <img src="data:image/jpeg;base64,{{ config.banner_image_data }}" style="height: 100px; border-radius: 10px;">
            </div>
        {% endif %}
    </div>

    <div class="mb-3">
        <label class="form-label fw-bold">歡迎詞 / 公告 (可編輯樣式)</label>
        <textarea name="welcome_msg" id="editor">{{ config.welcome_msg }}</textarea>
    </div>
    <button type="submit" class="btn btn-primary btn-lg shadow">儲存設定</button>
    <a href="/admin" class="btn btn-secondary btn-lg shadow">返回</a>
</form>
<script>
    ClassicEditor.create(document.querySelector('#editor')).catch(error => console.error(error));
</script>
""")

# ==========================================
# 4. 路由與邏輯
# ==========================================

@app.context_processor
def inject_config():
    return dict(config=get_system_config())

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('登入成功！', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('帳號或密碼錯誤', 'danger')
    return render_template_string(LOGIN_TEMPLATE)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('已登出', 'info')
    return redirect(url_for('index'))

@app.route('/')
def index():
    clubs = Club.query.order_by(Club.weekday, Club.class_start).all()
    return render_template_string(HOME_TEMPLATE, clubs=clubs)

@app.route('/club/<int:club_id>')
def club_detail(club_id):
    club = Club.query.get_or_404(club_id)
    # 使用台灣時間
    now = get_taiwan_now()
    now_str = now.strftime('%Y-%m-%d %H:%M')
    
    can_register = True
    status_message = ""

    if now < club.start_time:
        can_register = False
        status_message = f"報名尚未開始 (開放時間：{club.start_time.strftime('%m/%d %H:%M')})"
    elif now > club.end_time:
        can_register = False
        status_message = "報名已截止"
    else:
        reg_count = club.current_regular_count()
        wait_count = club.current_waitlist_count()
        if reg_count >= club.max_regular and wait_count >= club.max_waitlist:
            can_register = False
            status_message = "名額已額滿"

    return render_template_string(CLUB_DETAIL_TEMPLATE, club=club, can_register=can_register, status_message=status_message, now_str=now_str)

@app.route('/register/<int:club_id>', methods=['POST'])
def register_student(club_id):
    club = Club.query.get_or_404(club_id)
    now = get_taiwan_now() # 使用台灣時間

    if not (club.start_time <= now <= club.end_time):
        flash('不在報名時間範圍內，報名失敗。', 'danger')
        return redirect(url_for('club_detail', club_id=club_id))

    student_name = request.form.get('student_name')
    student_class = request.form.get('student_class')
    parent_phone = request.form.get('parent_phone')

    # 重複報名檢查
    existing = Registration.query.filter_by(club_id=club_id, student_class=student_class).first()
    if existing:
        flash('您已經報名過此社團了！', 'warning')
        return redirect(url_for('club_detail', club_id=club_id))

    # 衝堂檢查
    student_regs = Registration.query.filter_by(student_class=student_class).all()
    for reg in student_regs:
        existing_club = reg.club
        if existing_club.weekday == club.weekday:
            if (club.class_start < existing_club.class_end) and (club.class_end > existing_club.class_start):
                flash(f'❌ 報名失敗！與已報名的【{existing_club.name}】上課時間衝突。', 'danger')
                return redirect(url_for('club_detail', club_id=club_id))

    # 正取/備取判定
    status = None
    current_reg = club.current_regular_count()
    current_wait = club.current_waitlist_count()

    if current_reg < club.max_regular:
        status = '正取'
        flash(f'✅ 報名成功！恭喜 {student_name} 為【正取】。', 'success')
    elif current_wait < club.max_waitlist:
        status = '備取'
        flash(f'⚠️ 報名成功，但正取已滿。{student_name} 列為【備取第 {current_wait + 1} 順位】。', 'warning')
    else:
        flash('❌ 很抱歉，本社團已全數額滿。', 'danger')
        return redirect(url_for('club_detail', club_id=club_id))

    new_reg = Registration(
        club_id=club.id, student_name=student_name,
        student_class=student_class, parent_phone=parent_phone, status=status
    )
    db.session.add(new_reg)
    db.session.commit()

    return redirect(url_for('club_detail', club_id=club_id))

# --- 管理者後台 ---

@app.route('/admin')
@login_required
def admin_dashboard():
    clubs = Club.query.order_by(Club.weekday, Club.class_start).all()
    return render_template_string(ADMIN_DASHBOARD_TEMPLATE, clubs=clubs)

@app.route('/admin/config', methods=['GET', 'POST'])
@login_required
def admin_config():
    conf = get_system_config()
    if request.method == 'POST':
        conf.site_title = request.form.get('site_title')
        conf.welcome_msg = request.form.get('welcome_msg')
        
        # 處理圖片上傳
        file = request.files.get('banner_file')
        b64_img = process_image_upload(file)
        if b64_img:
            conf.banner_image_data = b64_img
            
        db.session.commit()
        flash('網站設定已更新', 'success')
        return redirect(url_for('admin_config'))
    return render_template_string(ADMIN_CONFIG_TEMPLATE)

@app.route('/admin/create', methods=['GET', 'POST'])
@login_required
def admin_create():
    if request.method == 'POST':
        try:
            c_start = datetime.strptime(request.form.get('class_start'), '%H:%M').time()
            c_end = datetime.strptime(request.form.get('class_end'), '%H:%M').time()
            
            # 圖片處理
            img_data = process_image_upload(request.files.get('image_file'))
            
            new_club = Club(
                name=request.form.get('name'),
                description=request.form.get('description'),
                image_data=img_data,
                start_time=datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M'),
                end_time=datetime.strptime(request.form.get('end_time'), '%Y-%m-%dT%H:%M'),
                max_regular=int(request.form.get('max_regular')),
                max_waitlist=int(request.form.get('max_waitlist')),
                weekday=request.form.get('weekday'),
                class_start=c_start,
                class_end=c_end
            )
            db.session.add(new_club)
            db.session.commit()
            flash('社團新增成功！', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f'新增失敗: {str(e)}', 'danger')

    return render_template_string(ADMIN_FORM_TEMPLATE, title="新增社團", club=None)

# --- 新增功能：編輯社團 ---
@app.route('/admin/edit/<int:club_id>', methods=['GET', 'POST'])
@login_required
def admin_edit(club_id):
    club = Club.query.get_or_404(club_id)
    
    if request.method == 'POST':
        try:
            club.name = request.form.get('name')
            club.description = request.form.get('description')
            club.max_regular = int(request.form.get('max_regular'))
            club.max_waitlist = int(request.form.get('max_waitlist'))
            club.start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M')
            club.end_time = datetime.strptime(request.form.get('end_time'), '%Y-%m-%dT%H:%M')
            club.weekday = request.form.get('weekday')
            club.class_start = datetime.strptime(request.form.get('class_start'), '%H:%M').time()
            club.class_end = datetime.strptime(request.form.get('class_end'), '%H:%M').time()
            
            # 只有當使用者有上傳新圖片時，才更新圖片
            new_img = process_image_upload(request.files.get('image_file'))
            if new_img:
                club.image_data = new_img
                
            db.session.commit()
            flash('社團修改成功！', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            flash(f'修改失敗: {str(e)}', 'danger')
            
    return render_template_string(ADMIN_FORM_TEMPLATE, title=f"編輯社團：{club.name}", club=club)

@app.route('/admin/delete/<int:club_id>')
@login_required
def admin_delete(club_id):
    club = Club.query.get_or_404(club_id)
    db.session.delete(club)
    db.session.commit()
    flash('社團已刪除', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export/<int:club_id>')
@login_required
def admin_export(club_id):
    club = Club.query.get_or_404(club_id)
    # 使用 pytz 轉換時間顯示
    regs = Registration.query.filter_by(club_id=club_id).all()
    data = []
    for r in regs:
        # 將資料庫時間 (UTC 或 Naive) 轉換為台灣時間字串
        local_time = r.created_at
        if local_time.tzinfo is None:
             # 假設存入時是台灣時間
             pass 
        else:
            local_time = local_time.astimezone(TAIWAN_TZ)
            
        data.append({
            "班級座號": r.student_class,
            "學生姓名": r.student_name,
            "家長電話": r.parent_phone,
            "報名狀態": r.status,
            "報名時間": local_time.strftime('%Y-%m-%d %H:%M:%S')
        })
    df = pd.DataFrame(data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='報名名單')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"{club.name}_名單.xlsx")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        get_system_config()
    app.run(debug=True)