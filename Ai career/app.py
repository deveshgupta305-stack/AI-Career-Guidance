import os
import re
import json
import sqlite3
import time
from flask import Flask, render_template, request, session, redirect, url_for, send_file, jsonify
import PyPDF2
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from google import genai

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "devesh_secret_key_123")

# =========================================================
# 1. Google GenAI Client Configuration
# =========================================================
load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

import time

def safe_generate_content(prompt):
    models_to_try = ['gemini-3.6-flash', 'gemini-2.0-flash', 'gemini-1.5-flash']
    
    for model in models_to_try:
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt
                )
                return response
            except Exception as e:
                error_str = str(e)
                if "503" in error_str or "UNAVAILABLE" in error_str:
                    time.sleep(2 * (attempt + 1))
                else:
                    break
                    
    raise Exception("Google API is busy right now. Please try again after 1 minute.")
# System se variables fetch karein
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "default-fallback-key")

app.config['UPLOAD_FOLDER'] = 'Uploads'
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# =========================================================
# 2. Database Initialization
# =========================================================
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            branch TEXT NOT NULL,
            skills TEXT,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Career Database for Prediction & Skill Gap
CAREERS = {
    "Machine Learning Engineer": {
        "salary": "₹8 - ₹25 LPA",
        "companies": ["Google", "Microsoft", "Amazon", "NVIDIA"],
        "certifications": ["Google ML", "IBM AI", "AWS ML"]
    },
    "Full Stack Developer": {
        "salary": "₹5 - ₹18 LPA",
        "companies": ["TCS", "Infosys", "Accenture", "Zoho"],
        "certifications": ["Meta Frontend", "JavaScript", "React"]
    },
    "Cyber Security Analyst": {
        "salary": "₹6 - ₹20 LPA",
        "companies": ["Cisco", "IBM", "Wipro", "Deloitte"],
        "certifications": ["CEH", "CompTIA Security+", "CISSP"]
    },
    "Software Developer": {
        "salary": "₹4 - ₹15 LPA",
        "companies": ["Infosys", "TCS", "Capgemini", "HCL"],
        "certifications": ["Python", "Java", "DSA"]
    }
}

# Helper functions
def calculate_match(user_skills, required_skills):
    matched = sum(1 for skill in required_skills if skill in user_skills)
    return int((matched / len(required_skills)) * 100) if required_skills else 0

def clean_pdf_text(text):
    """PDF text cleaning for extra spaces & formatting gaps"""
    cleaned_text = re.sub(r'(?<=\b[A-Za-z])\s+(?=[A-Za-z]\b)', '', text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    return cleaned_text.strip()

# =========================================================
# 3. Web Navigation & Authentication Routes
# =========================================================
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        branch = request.form.get('branch', '').strip()
        skills = request.form.get('skills', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match!")

        hashed_password = generate_password_hash(password)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        try:
            cursor.execute(
                '''
                INSERT INTO students (name, email, branch, skills, password)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (name, email, branch, skills, hashed_password)
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error="Email is already registered!")
        except Exception as e:
            conn.close()
            return render_template('register.html', error=f"Database error: {e}")
        finally:
            conn.close()

        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        conn = sqlite3.connect('database.db')
        conn.row_factory = sqlite3.Row 
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM students WHERE email=?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['branch'] = user['branch']
            session['skills'] = user['skills']
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error="Invalid Email or Password!")

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_data = {
        'name': session.get('name', 'Student'),
        'branch': session.get('branch', 'N/A'),
        'skills': session.get('skills', 'N/A'),
        'career_score': 85,
        'resume_score': '80/100',
        'profile_level': 'Intermediate',
        'users_count': '50+',
        'resumes_count': '100+',
        'careers_count': '10+',
        'ai_queries': '500+'
    }

    return render_template('dashboard.html', user=user_data)

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_data = {
        'name': session.get('name', 'Student'),
        'branch': session.get('branch', 'N/A'),
        'skills': session.get('skills', 'N/A')
    }

    return render_template('profile.html', user=user_data, name=user_data['name'], branch=user_data['branch'], skills=user_data['skills'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# =========================================================
# 4. Career Roadmap & Predictor Routes
# =========================================================
ROADMAPS_DB = {
    "Machine Learning Engineer": [
        {
            "phase": "PHASE 1 • FOUNDATIONS",
            "title": "Python & Mathematics",
            "duration": "Weeks 1-4",
            "desc": "Linear Algebra, Calculus, NumPy, Pandas, Git Basics",
            "skills": ["Python Syntax & OOPs", "NumPy & Pandas Dataframes", "Git & GitHub Workflow"]
        },
        {
            "phase": "PHASE 2 • ML CORE",
            "title": "Algorithms & Pipelines",
            "duration": "Weeks 5-9",
            "desc": "Scikit-Learn, Regression, Classification, Model Evaluation",
            "skills": ["Supervised & Unsupervised Learning", "Feature Engineering", "Model Hyperparameter Tuning"]
        },
        {
            "phase": "PHASE 3 • DEEP LEARNING & DEPLOYMENT",
            "title": "Neural Networks & MLOps",
            "duration": "Weeks 10-14",
            "desc": "PyTorch/TensorFlow, Model Serving, Docker, Flask API",
            "skills": ["CNNs & Transformers", "FastAPI / Flask Model Serving", "Docker & Cloud Deployment"]
        }
    ],
    "Full Stack Developer": [
        {
            "phase": "PHASE 1 • FRONTEND CORE",
            "title": "HTML, CSS & JavaScript",
            "duration": "Weeks 1-4",
            "desc": "DOM Manipulation, Responsive Design, ES6+ JavaScript",
            "skills": ["HTML5 & CSS Grid/Flexbox", "JavaScript ES6 Async/Await", "Bootstrap & Tailwind"]
        },
        {
            "phase": "PHASE 2 • BACKEND & DATABASE",
            "title": "Node.js / Python & SQL",
            "duration": "Weeks 5-8",
            "desc": "REST APIs, Authentication, Databases (PostgreSQL / MongoDB)",
            "skills": ["RESTful API Architecture", "Database Schema & SQL Queries", "JWT Auth & Middleware"]
        },
        {
            "phase": "PHASE 3 • FRAMEWORKS & DEPLOYMENT",
            "title": "React / Next.js & Cloud",
            "duration": "Weeks 9-12",
            "desc": "State Management, CI/CD Pipelines, Docker, Vercel/AWS",
            "skills": ["React Hooks & Redux", "Docker & CI/CD", "AWS / Vercel Deployment"]
        }
    ]
}

def generate_custom_roadmap(role):
    return [
        {
            "phase": "PHASE 1 • FOUNDATIONS",
            "title": f"Core Fundamentals of {role}",
            "duration": "Weeks 1-4",
            "desc": f"Master basic tools, syntax, and foundational knowledge required for {role}.",
            "skills": [f"Basic Syntax & Concepts of {role}", "Version Control with Git", "Environment Setup"]
        },
        {
            "phase": "PHASE 2 • INTERMEDIATE PRACTICE",
            "title": "Core Skills & Practical Projects",
            "duration": "Weeks 5-8",
            "desc": f"Build practical hands-on mini projects and learn key tools for {role}.",
            "skills": ["Core Frameworks & Libraries", "Database & API Integration", "Testing & Debugging"]
        },
        {
            "phase": "PHASE 3 • ADVANCED & DEPLOYMENT",
            "title": "Production & Portfolio",
            "duration": "Weeks 9-12",
            "desc": "Prepare capstone projects and get job-ready with portfolio reviews.",
            "skills": ["End-to-End Capstone Project", "CI/CD & Cloud Hosting", "Interview Preparation"]
        }
    ]

@app.route('/roadmap', methods=['GET', 'POST'])
def roadmap():
    target_role = None
    roadmap_phases = []

    if request.method == 'POST':
        preset_role = request.form.get('role')
        custom_role = request.form.get('custom_role')

        if custom_role and custom_role.strip():
            target_role = custom_role.strip()
        elif preset_role:
            target_role = preset_role

        if target_role:
            roadmap_phases = ROADMAPS_DB.get(target_role, generate_custom_roadmap(target_role))

    return render_template('roadmap.html', target_role=target_role, roadmap_phases=roadmap_phases)

@app.route('/career-predict', methods=['GET', 'POST'])
def career_predict():
    if request.method == "POST":
        skills = request.form.get("skills", "").lower()
        interest = request.form.get("interest", "").lower()

        career_key = "Software Developer"
        career_display = "💻 Software Developer"
        reason = []
        roadmap_steps = []

        if "python" in skills and "ai" in interest:
            required = ["python", "numpy", "pandas", "machine learning", "sql", "git"]
            match_score = calculate_match(skills, required)
            career_key = "Machine Learning Engineer"
            career_display = "🤖 Machine Learning Engineer"
            reason = ["Python detected", "AI interest matched"]
            roadmap_steps = ["Learn NumPy", "Learn Pandas", "Machine Learning", "Deep Learning", "Build AI Projects"]

        elif "html" in skills or "javascript" in skills:
            required = ["html", "css", "javascript", "react", "git"]
            match_score = calculate_match(skills, required)
            career_key = "Full Stack Developer"
            career_display = "🌐 Full Stack Developer"
            reason = ["Web development skills detected"]
            roadmap_steps = ["Master CSS/JS", "Learn React", "Build Frontend Portfolios", "Learn Backend Node.js/Flask"]

        elif "security" in interest:
            required = ["networking", "linux", "python", "wireshark", "ethical hacking"]
            match_score = calculate_match(skills, required)
            career_key = "Cyber Security Analyst"
            career_display = "🔐 Cyber Security Analyst"
            reason = ["Interest in security systems detected"]
            roadmap_steps = ["Learn Networking Basics", "Linux Administration", "Ethical Hacking Certifications"]

        else:
            required = ["python", "sql", "git"]
            match_score = calculate_match(skills, required)
            career_key = "Software Developer"
            career_display = "💻 Software Developer"
            reason = ["General programming skills matched"]
            roadmap_steps = ["Learn Core Programming", "Data Structures & Algorithms", "SQL Databases"]

        missing_skills = [skill.title() for skill in required if skill not in skills]

        return render_template(
            "career_predict.html",
            career=career_display,
            reason=reason,
            roadmap=roadmap_steps,
            match_score=match_score,
            top_careers=[],
            missing_skills=missing_skills,
            career_info=CAREERS.get(career_key)
        )

    return render_template("career_predict.html")

@app.route('/skill-gap', methods=['GET', 'POST'])
def skill_gap():
    if request.method == 'POST':
        role = request.form.get('role') or request.form.get('custom_role')
        user_skills_input = request.form.get('skills', '')
        
        user_skills = set([s.strip().lower() for s in user_skills_input.split(',') if s.strip()])
        
        role_skill_db = {
            "Full Stack Developer": ["html", "css", "javascript", "react", "node.js", "python", "sql", "git"],
            "Machine Learning Engineer": ["python", "math", "numpy", "pandas", "scikit-learn", "pytorch", "docker", "git"],
            "Data Scientist": ["python", "sql", "pandas", "statistics", "tableau", "machine learning", "r"]
        }

        if role not in role_skill_db:
            required_skills = ["fundamentals", "core tools", "databases", "version control", "deployment", "best practices"]
        else:
            required_skills = role_skill_db[role]

        matched_skills = [s.title() for s in required_skills if s.lower() in user_skills]
        missing_skills = [s.title() for s in required_skills if s.lower() not in user_skills]
        
        match_percentage = int((len(matched_skills) / len(required_skills)) * 100) if required_skills else 0

        graph_labels = [s.title() for s in required_skills]
        graph_user_scores = [100 if s.lower() in user_skills else 20 for s in required_skills]
        graph_required_scores = [100] * len(required_skills)

        return render_template(
            'skill_gap.html', 
            role=role, 
            user_skills=user_skills_input, 
            matched_skills=matched_skills, 
            missing_skills=missing_skills, 
            match_percentage=match_percentage,
            graph_labels=graph_labels,
            graph_user_scores=graph_user_scores,
            graph_required_scores=graph_required_scores
        )

    return render_template('skill_gap.html', role=None)

# --------------------------------------------------
# AI Resume Analyzer Routes
# --------------------------------------------------
@app.route('/resume-analyzer', methods=['POST'])
@app.route('/resume-api', methods=['POST'])
@app.route('/resume', methods=['POST'])
def analyze_resume_api():
    try:
        if 'resume' not in request.files:
            return jsonify({'error': 'Please upload a PDF file.'}), 400

        file = request.files['resume']
        target_job = request.form.get('target_job') or request.form.get('target_role', 'Software Engineer')

        if file.filename == '':
            return jsonify({'error': 'No file selected.'}), 400

        pdf_reader = PyPDF2.PdfReader(file)
        raw_text = ""
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                raw_text += text + "\n"

        resume_text = clean_pdf_text(raw_text)

        if not resume_text:
            return jsonify({'error': 'Could not extract text from the PDF file.'}), 400

        prompt = f"""
        You are an expert ATS Resume Analyzer.
        Target Job Role: {target_job}
        
        Resume Text:
        {resume_text[:3000]}

        Provide a detailed ATS analysis using clean Markdown:
        1. Estimated ATS Match Score (Always format strictly as: "Score: XX / 100")
        2. Key Strengths & Present Skills
        3. Missing Technical & Soft Keywords
        4. Critical Formatting Fixes
        5. Actionable Improvement Recommendations
        """

       # Naya Code
        response = safe_generate_content(prompt)
        return jsonify({
            'success': True,
            'filename': file.filename,
            'analysis': response.text,
            'report': response.text
        })

    except Exception as e:
        print("SERVER ERROR LOG:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/resume-analyzer', methods=['GET'])
@app.route('/resume', methods=['GET'])
def resume():
    return render_template('resume.html')

@app.route('/resume-builder', methods=['GET', 'POST'])
def resume_builder():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    generated_resume = None

    if request.method == 'POST':
        full_name = request.form.get('full_name', '')
        email = request.form.get('email', '')
        phone = request.form.get('phone', '')
        linkedin = request.form.get('linkedin', '').strip()
        github = request.form.get('github', '').strip()
        target_role = request.form.get('target_role', '')
        skills = request.form.get('skills', '')
        experience = request.form.get('experience', '')
        education = request.form.get('education', '')
        projects = request.form.get('projects', '')

        contact_line = f"**Email:** {email} | **Phone:** {phone}"
        if linkedin:
            contact_line += f" | **LinkedIn:** {linkedin}"
        if github:
            contact_line += f" | **GitHub:** {github}"

        prompt = f"""
        Create an ATS-friendly, clean professional resume for:
        Name: {full_name}
        Contact Details: {contact_line}
        Target Role: {target_role}
        Skills: {skills}
        Education: {education}
        Projects: {projects}
        Work Experience: {experience}

        Structure strictly with Markdown:
        # {full_name}
        {contact_line}
        
        **Target Role:** {target_role}

        ## Professional Summary
        [Write a compelling 3-4 line summary]

        ## Core Skills
        [Group skills into clean bullet points]

        ## Work Experience
        [Detailed bullet points with action verbs]

        ## Key Projects
        [Project Name, Tech Used, Key Achievements]

        ## Education
        [Degree, Institution, Year]
        """

        try:
            response = client.models.generate_content(
                model='gemini-3.6-flash',
                contents=prompt
            )
            generated_resume = response.text
        except Exception as e:
            generated_resume = f"Resume generation error: {str(e)}"

    return render_template("resume_builder.html", resume=generated_resume)

@app.route('/chatbot', methods=['GET', 'POST'])
def chatbot():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    answer = ""
    user_question = ""

    if request.method == 'POST':
        user_question = request.form.get('question', '')

        if user_question:
            try:
                prompt = f"You are an expert Career Counselor AI. Answer this student's query clearly and concisely: {user_question}"
                response = client.models.generate_content(
                    model='gemini-3.6-flash',
                    contents=prompt
                )
                answer = response.text
            except Exception as e:
                answer = f"Error generating response: {str(e)}"

    return render_template('chatbot.html', answer=answer, user_question=user_question)

@app.route('/study-planner', methods=['GET', 'POST'])
def study_planner():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    planner_data = None
    target_role = ""

    if request.method == 'POST':
        target_role = request.form.get('target_role', '').strip()
        current_level = request.form.get('current_level', 'Beginner')
        duration = request.form.get('duration', '4 Weeks')

        if target_role:
            try:
                prompt = f"""
You are an expert career mentor. Generate a detailed, structured, day-by-day study roadmap for learning "{target_role}".

Parameters:
- Target Role/Skill: {target_role}
- Experience Level: {current_level}
- Duration: {duration}

CRITICAL INSTRUCTION: Output MUST be strictly a single, raw, valid JSON object. Do NOT wrap the JSON in Markdown code blocks.

JSON Structure required:
{{
  "overview": "Brief high-level strategy overview for this course.",
  "weeks": [
    {{
      "week_number": 1,
      "week_title": "Focus / Core Topic of Week 1",
      "days": [
        {{"day": "Day 1", "topic": "Topic Name", "task": "Specific practical task"}},
        {{"day": "Day 2", "topic": "Topic Name", "task": "Specific practical task"}},
        {{"day": "Day 3", "topic": "Topic Name", "task": "Specific practical task"}},
        {{"day": "Day 4", "topic": "Topic Name", "task": "Specific practical task"}},
        {{"day": "Day 5", "topic": "Topic Name", "task": "Specific practical task"}},
        {{"day": "Day 6", "topic": "Topic Name", "task": "Specific practical task"}},
        {{"day": "Day 7", "topic": "Weekly Project", "task": "Task details"}}
      ]
    }}
  ],
  "resources": ["Resource 1", "Resource 2", "Resource 3"],
  "final_project": "Description of the milestone project"
}}
"""

                response = safe_generate_content(prompt)

                clean_text = response.text.strip()
                if clean_text.startswith("```"):
                    lines = clean_text.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    clean_text = "\n".join(lines).strip()

                planner_data = json.loads(clean_text)

            except Exception as e:
                planner_data = {
                    "error": f"AI Roadmap error: {str(e)}"
                }

    return render_template('study_planner.html', planner_data=planner_data, target_role=target_role)

# =========================================================
# 6. Report Generation & Download Route
# =========================================================
@app.route('/download-report')
def download_report():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    report_filename = os.path.join(app.config['UPLOAD_FOLDER'], "Career_Report.pdf")
    doc = SimpleDocTemplate(report_filename)
    styles = getSampleStyleSheet()
    story = []

    student_name = session.get('name', 'Student')

    story.append(Paragraph("AI Powered Smart Career Guidance System", styles['Title']))
    story.append(Paragraph("<br/>", styles['Normal']))
    story.append(Paragraph("Student Career Report", styles['Heading2']))
    story.append(Paragraph(f"Name : {student_name}", styles['Normal']))
    story.append(Paragraph("Recommended Career : Machine Learning Engineer", styles['Normal']))
    story.append(Paragraph("Resume Score : 80 / 100", styles['Normal']))
    story.append(Paragraph("Generated by Career Guidance Portal", styles['Normal']))
    
    doc.build(story)
    return send_file(report_filename, as_attachment=True)

# =========================================================
# 7. Admin Authentication & Dashboard
# =========================================================
ADMIN_EMAIL = "deveshgupta991@gmail.com"
ADMIN_PASSWORD = "Dev@9651"

@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
            session.clear()
            session['is_admin'] = True
            session['admin_email'] = email
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid Admin Email or Password!"

    return render_template('admin_login.html', error=error)

@app.route('/admin-dashboard')
def admin_dashboard():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, email, branch, skills FROM students ORDER BY id DESC")
    students_list = cursor.fetchall()
    conn.close()

    return render_template(
        'admin_dashboard.html', 
        admin_email=session.get('admin_email'),
        students=students_list
    )

@app.route('/admin-logout')
def admin_logout():
    session.pop('is_admin', None)
    session.pop('admin_email', None)
    return redirect(url_for('admin_login'))

# Mock Questions DB (Fallback / Standard Sets)
MOCK_QUESTIONS_DB = {
    "Machine Learning Engineer": [
        "What is the difference between Supervised and Unsupervised Learning?",
        "How do you handle overfitting in a Deep Learning model?",
        "Explain the Bias-Variance tradeoff."
    ],
    "Full Stack Developer": [
        "Explain the difference between SQL and NoSQL databases. When would you use which?",
        "What is the Event Loop in JavaScript and how does async/await work?",
        "How do RESTful APIs differ from GraphQL?"
    ],
    "General Tech": [
        "Tell me about a challenging technical project you built and how you solved the main hurdles.",
        "What are Object-Oriented Programming (OOP) core concepts?",
        "How do you manage version control when working in a team using Git?"
    ]
}

@app.route('/mock-interview', methods=['GET', 'POST'])
def mock_interview():
    role = None
    interview_type = None
    questions = []
    user_answers = {}
    feedback = None

    if request.method == 'POST':
        action = request.form.get('action')
        role = request.form.get('role', 'General Tech')
        interview_type = request.form.get('type', 'Technical')

        # Action 1: Start Interview (Fetch Questions)
        if action == 'start':
            questions = MOCK_QUESTIONS_DB.get(role, MOCK_QUESTIONS_DB["General Tech"])
        
        # Action 2: Submit Answers & Generate AI Feedback
        elif action == 'submit':
            questions = MOCK_QUESTIONS_DB.get(role, MOCK_QUESTIONS_DB["General Tech"])
            user_ans_1 = request.form.get('ans_0', '').strip()
            user_ans_2 = request.form.get('ans_1', '').strip()
            user_ans_3 = request.form.get('ans_2', '').strip()

            # AI Feedback Evaluation (Simulated AI Scoring & Tips)
            total_words = len(user_ans_1.split()) + len(user_ans_2.split()) + len(user_ans_3.split())
            score = min(95, max(60, 50 + (total_words // 4)))

            feedback = {
                "score": score,
                "strengths": [
                    "Good understanding of fundamental concepts.",
                    "Structured explanation with practical examples."
                ],
                "improvements": [
                    "Try to include specific industry tools/libraries in your answers.",
                    "Elaborate more on edge cases and error handling."
                ],
                "verdict": "Strong Candidate - Ready for Technical Screening!" if score >= 80 else "Good Attempt - Needs slightly deeper technical detail."
            }

    return render_template('mock_interview.html', 
                           role=role, 
                           interview_type=interview_type, 
                           questions=questions, 
                           feedback=feedback)

# =========================================================
# 8. Server Run
# =========================================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)