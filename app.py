from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd

app = Flask(__name__)
app.secret_key = "quiz_secret_key"

SHEET_ID = "16Bnz7F28gs4Fj3bH0XjRpQ-_4jcIWCbh37XptYecesU"

# Mapping môn học -> sheet name
SHEET_MAPPING = {
    "toan": "TOAN",
    "ly": "LY",
    "hoa": "HOA",
    "trung": "CHINA"
}

# ===== ĐĂNG NHẬP =====
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        if username:
            session["user"] = username
            return redirect(url_for("choose_subject"))
    return render_template("login.html")

# ===== CHỌN MÔN =====
@app.route("/choose")
def choose_subject():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("choose_subject.html")

# ===== LIST ĐỀ THEO MÔN =====
@app.route("/subject/<subject>")
def subject(subject):
    if "user" not in session:
        return redirect(url_for("login"))

    sheet_name = SHEET_MAPPING.get(subject)
    if not sheet_name:
        return f"Sheet cho môn {subject} không tồn tại!"

    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        quizzes = df.to_dict(orient="records")
    except Exception as e:
        return f"Lỗi khi lấy dữ liệu từ Google Sheet: {e}"

    return render_template("list_quiz.html", subject=subject, quizzes=quizzes)

# ===== XEM KẾT QUẢ (TẠM THỜI) =====
@app.route("/result")
def result():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("result.html", user=session["user"])

# ===== ĐĂNG XUẤT =====
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    app.run(debug=True)
