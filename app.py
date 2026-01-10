from flask import (
    Flask, render_template, request,
    redirect, url_for, session,
    flash, jsonify
)
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import json
import os
app = Flask(__name__)
app.secret_key = "quiz_secret_key"

# ================= GOOGLE SHEET =================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

service_account_info = json.loads(
    os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
)

service_account_info = json.loads(
    os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
)

creds = Credentials.from_service_account_info(
    service_account_info,
    scopes=SCOPES
)

gc = gspread.authorize(creds)


SHEET_ID = "16Bnz7F28gs4Fj3bH0XjRpQ-_4jcIWCbh37XptYecesU"
sh = gc.open_by_key(SHEET_ID)

# ================= CACHE =================
QUIZ_CACHE = {}
CACHE_TIME = 0
CACHE_EXPIRE = 300  # 5 phút


def load_quiz_from_sheet():
    global QUIZ_CACHE, CACHE_TIME

    print("🔄 Load quiz từ Google Sheet")
    QUIZ_CACHE = {}

    sheets = {
        "list": "LIST",
        "toan": "TOAN",
        "ly": "LY",
        "hoa": "HOA",
        "trung": "CHINA",
    }

    for key, sheet_name in sheets.items():
        ws = sh.worksheet(sheet_name)
        QUIZ_CACHE[key] = ws.get_all_records()

    CACHE_TIME = time.time()



def get_quiz(key):
    if time.time() - CACHE_TIME > CACHE_EXPIRE or not QUIZ_CACHE:
        load_quiz_from_sheet()
    return QUIZ_CACHE.get(key, [])


# ================= USERS =================
ws_user = sh.worksheet("USERS")

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Vui lòng nhập đầy đủ tài khoản và mật khẩu", "error")
            return render_template("login.html")

        rows = ws_user.get_all_values()[1:]
        for row in rows:
            if row[0] == username and row[1] == password:
                session["user"] = username
                return redirect(url_for("choose_subject"))

        flash("Sai tài khoản hoặc mật khẩu", "error")

    return render_template("login.html")


# ================= REGISTER =================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm", "").strip()
        fullname = request.form.get("fullname", "").strip()
        phone = request.form.get("phone", "").strip()

        if not all([username, password, confirm, fullname, phone]):
            flash("Vui lòng nhập đầy đủ thông tin", "error")
            return render_template("register.html")

        if password != confirm:
            flash("Mật khẩu xác nhận không khớp", "error")
            return render_template("register.html")

        rows = ws_user.get_all_values()[1:]
        for row in rows:
            if row and row[0] == username:
                flash("Tài khoản đã tồn tại", "error")
                return render_template("register.html")

        ws_user.append_row([
            username, password, fullname, phone,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])

        flash("Đăng ký thành công, mời đăng nhập", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


# ================= CHỌN MÔN =================
@app.route("/choose-subject")
def choose_subject():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("choose_subject.html")


# ================= CHỌN ĐỀ =================
@app.route("/list-quiz/<subject>")
def list_quiz(subject):
    if "user" not in session:
        return redirect(url_for("login"))

    subject = subject.lower()

    quiz_list = [
        q for q in get_quiz("list")
        if q["subject"].strip().lower() == subject
    ]

    return render_template(
        "list_quiz.html",
        subject=subject,
        quiz_list=quiz_list
    )


# ================= TRANG LÀM BÀI =================
@app.route("/quiz/<subject>/<quiz_id>")
def quiz(subject, quiz_id):
    if "user" not in session:
        return redirect(url_for("login"))

    quiz_name = ""
    for q in get_quiz("list"):
        if q["quiz_id"] == quiz_id:
            quiz_name = q["quiz_name"]
            break

    return render_template(
        "quiz.html",
        subject=subject,
        quiz_id=quiz_id,
        quiz_name=quiz_name
    )


# ================= API LẤY CÂU HỎI =================
@app.route("/api/quiz/<subject>/<quiz_id>")
def api_quiz(subject, quiz_id):
    if "user" not in session:
        return jsonify({"error": "login required"}), 401

    subject = subject.lower()
    quiz_id = str(quiz_id).strip()

    print("SUBJECT:", subject)
    print("QUIZ_ID URL:", quiz_id)
    print("QUIZ_ID SHEET:", [q.get("quiz_id") for q in get_quiz(subject)])

    questions = [
        q for q in get_quiz(subject)
        if str(q.get("quiz_id")).strip().upper() == str(quiz_id).strip().upper()
           == quiz_id.upper()
    ]

    return jsonify(questions)

#=================THÊM ROUTE==============

@app.route("/submit/<subject>/<quiz_id>", methods=["POST"])
def submit(subject, quiz_id):
    if "user" not in session:
        return jsonify({"error": "login required"}), 401

    data = request.get_json()
    user_answers = data.get("answers", {})

    # Lấy câu hỏi theo quiz_id
    questions = [
        q for q in get_quiz(subject)
        if str(q.get("quiz_id")).strip().upper()
           == str(quiz_id).strip().upper()
    ]

    score = 0
    for idx, q in enumerate(questions):
        if user_answers.get(str(idx)) == q.get("correct_answer"):
            score += 1

    # (tạm thời chưa lưu sheet, chỉ trả kết quả)
    return jsonify({
        "score": score,
        "total": len(questions)
    })


# ================= SUBMIT + CHẤM ĐIỂM =================
@app.route("/submit-name/<subject>/<quiz_name>", methods=["POST"])
def submit_quiz(subject, quiz_name):
    if "user" not in session:
        return jsonify({"error": "login required"}), 401

    data = request.get_json()
    user_answers = data.get("answers", {})

    questions = [
        q for q in get_quiz(subject)
        if q["quiz_name"] == quiz_name
    ]

    score = 0
    for idx, q in enumerate(questions):
        correct = q["correct_answer"]
        user_ans = user_answers.get(str(idx)) or user_answers.get(idx)

        if user_ans == correct:
            score += 1

    # ===== LƯU KẾT QUẢ VÀO SHEET RESULT =====
    try:
        ws_result = sh.worksheet("RESULT")

        ws_result.append_row([
            session["user"],
            subject,
            quiz_id,  # <-- khóa thật
            quiz_name,  # <-- chỉ để hiển thị
            json.dumps(user_answers),
            score,
            len(questions),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])

    except:
        pass

    return jsonify({
        "score": score,
        "total": len(questions)
    })

# ================= XEM KẾT QUẢ =================
@app.route("/result")
def result():
    if "user" not in session:
        return redirect(url_for("login"))

    try:
        ws_result = sh.worksheet("RESULT")
        rows = ws_result.get_all_records()
    except:
        rows = []

    user_rows = [
        r for r in rows
        if r.get("username") == session["user"]
    ]

    return render_template(
        "result.html",
        results=user_rows
    )

# ================= REVIEW BÀI LÀM =================
@app.route("/review/<subject>/<quiz_id>")
def review(subject, quiz_id):
    if "user" not in session:
        return redirect(url_for("login"))

    # 1️⃣ Lấy câu hỏi theo quiz_id
    questions = [
        q for q in get_quiz(subject)
        if str(q.get("quiz_id")).strip() == str(quiz_id).strip()
    ]

    # 2️⃣ Lấy kết quả gần nhất của user
    try:
        ws_result = sh.worksheet("RESULT")
        rows = ws_result.get_all_records()
    except:
        rows = []

    user_result = None
    for r in reversed(rows):
        if (
            r.get("username") == session["user"]
            and r.get("subject") == subject
            and str(r.get("quiz_id")).strip() == str(quiz_id).strip()
        ):
            user_result = r
            break

    # 3️⃣ Parse answers
    user_answers = {}
    quiz_name = ""
    if user_result:
        import json
        quiz_name = user_result.get("quiz_name", "")
        user_answers = json.loads(user_result.get("answers", "{}"))

    return render_template(
        "review.html",
        subject=subject,
        quiz_id=quiz_id,
        quiz_name=quiz_name,
        questions=questions,
        answers=user_answers
    )



# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
