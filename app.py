from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import os
import re

app = Flask(__name__)
app.secret_key = 'SISsecret123'  # session management

DB_NAME = 'sis.db'

# --- Initialize Database ---
def init_db():
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT UNIQUE,
                        username TEXT,
                        password TEXT
                    )''')
        c.execute('''CREATE TABLE answers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        question TEXT,
                        answer TEXT,
                        score INTEGER,
                        feedback TEXT,
                        suggestion TEXT,
                        FOREIGN KEY(user_id) REFERENCES users(id)
                    )''')
        conn.commit()
        conn.close()

init_db()

# --- Routes ---
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('login.html')

@app.route('/intro')
def intro():
    return render_template('intro.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email'].strip()
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        if not email or not username or not password:
            return "Fill all fields!"

        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT INTO users (email, username, password) VALUES (?, ?, ?)", 
                      (email, username, password))
            conn.commit()
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            return "Email already exists!"

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND username=? AND password=?", (email, username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['user_id'] = user[0]
            session['username'] = user[2]
            session['email'] = user[1]
            return redirect('/dashboard')
        else:
            return "Invalid credentials!"

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' in session:
        return render_template('dashboard.html', username=session['username'])
    else:
        return redirect('/')

@app.route('/submit_answer', methods=['POST'])
def submit_answer():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.json
    question = data.get('question')
    answer = data.get('answer')
    # Server-side scoring logic aligned to frontend (/10 scale)
    score = 0
    feedback = ""
    suggestion = ""

    ans = (answer or "").strip()
    # Detect meaningless answers: only numbers, only symbols, or very short
    is_random_numbers = re.fullmatch(r"\d[\d\s]*", ans) is not None
    is_random_symbols = re.fullmatch(r"[^a-zA-Z0-9\s]+", ans) is not None
    words = [w for w in re.split(r"\s+", ans) if w]
    has_no_meaningful = len(words) < 2 or len(ans) < 10

    if is_random_numbers or is_random_symbols or has_no_meaningful:
        score = 1
        feedback = "Meaningless answer. Please enter a meaningful answer."
        suggestion = "Provide more details, examples, or relevant keywords."
    else:
        # Base score
        score = 3

        # Fluency: sentence count or long single answer
        sentences = [s for s in re.split(r'[.!?]+', ans) if s.strip()]
        has_good_flow = len(sentences) >= 2 or (len(sentences) == 1 and len(ans) > 40)
        if has_good_flow:
            score += 2

        # Grammar: simple checks for common confusions
        ans_lower = ans.lower()
        has_common_errors = bool(re.search(r"\b(their|there|they're)\b", ans_lower)) or bool(re.search(r"\b(your|you're)\b", ans_lower)) or bool(re.search(r"\b(its|it's)\b", ans_lower))
        grammar_score = 0
        if not has_common_errors and re.search(r"\b[a-z]{15,}\b", ans_lower):
            grammar_score = 2
        elif has_common_errors:
            grammar_score = 0
        else:
            grammar_score = 1
        score += grammar_score

        # Relevance: check for presence of professional keywords
        scoring_keywords = [
            "motivation","responsibility","quick learner","adaptability","self improvement","skill match","career growth",
            "learning opportunity","contribution","innovation","quality","work culture","customer focus","company growth",
            "short term goals","long term goals","skill development","career planning","experience","dedication","commitment",
            "learning mindset","achievement","planning","time management","problem solving","focus","communication","teamwork",
            "positive attitude","self awareness","growth mindset","deadline","execution","solution","collaboration","coordination",
            "listening","understanding","confidence","leadership","decision making","flexibility","consistency","efficiency","professionalism",
            "integrity","initiative","analytical thinking","stress management","ownership","accountability","result oriented","performance",
            "continuous learning","technical skills","soft skills","domain knowledge","process improvement","best practices","attention to detail",
            "quality assurance","risk management","prioritization","task management","goal oriented","strategic thinking","critical thinking",
            "time efficiency","productivity","work ethics","reliability","dependability","proactive","self motivated","discipline","resilience",
            "pressure handling","conflict resolution","negotiation","adaptation","open minded","feedback acceptance","improvement mindset",
            "self confidence","clarity","articulation","presentation skills","stakeholder management","client handling","business understanding",
            "value addition","impact","measurable results","ownership mindset","collaborative approach","team contribution","cross functional",
            "execution excellence","problem analysis","root cause","solution driven","data driven","logical thinking","structured approach","planning ability",
            "organizational skills","resource management","process optimization","continuous improvement","innovation mindset","lead by example","ethical behavior"
        ]
        found_keywords = sum(1 for k in scoring_keywords if k in ans_lower)
        if found_keywords > 0:
            score += 2
            if found_keywords >= 3 and len(ans) > 60:
                score += 1
                feedback = "Excellent! Fluent, clear answer with good relevance to the question."
            elif found_keywords >= 2:
                feedback = "Good answer with clear relevance and decent flow."
            else:
                feedback = "Answer is relevant but could be more detailed."
        else:
            feedback = "Answer needs to be more relevant to the question asked."

        if score > 10:
            score = 10

        if not suggestion:
            suggestion = "Add specific examples, keywords and improve sentence flow for a higher score."

    # Save to DB
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO answers (user_id, question, answer, score, feedback, suggestion) VALUES (?, ?, ?, ?, ?, ?)",
              (session['user_id'], question, answer, int(score), feedback, suggestion))
    conn.commit()
    conn.close()

    return jsonify({"score": int(score), "feedback": feedback, "suggestion": suggestion})

@app.route('/get_scores')
def get_scores():
    if 'user_id' not in session:
        return jsonify({"error": "Not logged in"}), 401

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT question, answer, score, feedback, suggestion FROM answers WHERE user_id=? ORDER BY id ASC", (session['user_id'],))
    results = c.fetchall()
    conn.close()

    score_list = []
    for r in results:
        score_list.append({
            "question": r[0],
            "answer": r[1],
            "score": r[2],
            "feedback": r[3],
            "suggestion": r[4]
        })

    return jsonify(score_list)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/')
    return jsonify({
        "email": session['email'],
        "username": session['username']
    })

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    port= int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0",port=port)