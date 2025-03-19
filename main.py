from flask import Flask, render_template, url_for, redirect, request, session

app = Flask(__name__)
app.config['SECRET_KEY'] = 'FLASK_SECKEY'

@app.route('/')
def index():
    return render_template('landing.html')

@app.route('/signin/', methods=['GET','POST'])
def signin():
    session['id'] = '123'
    session['email'] = 'kunalm2345@gmail.com'
    session['name'] = 'Kunal'
    session['workspace'] = ['csf111', 'csf222']  # Dummy workspaces
    return redirect(url_for('workspaces'))

@app.route('/workspaces/')
def workspaces():
    if session.get('id') is None:
        return redirect(url_for('index'))
    return render_template('workspaces.html')

@app.route('/create-workspace/', methods=['POST'])
def create_workspace():
    if 'id' not in session:
        return redirect(url_for('signin'))  # Redirect if user not logged in

    new_workspace = request.form.get('workspace_name')
    if new_workspace:
        if 'workspace' not in session:
            session['workspace'] = []
        session['workspace'].append(new_workspace)  # Add new workspace to session
        session.modified = True  # Save session changes

    return redirect(url_for('workspaces'))  # Redirect back to workspaces page

@app.route('/logout/')
def logout():
    session.clear()  # Clears all session data (logs out user)
    return redirect(url_for('index'))  # Redirects to homepage

@app.route('/workspace/<workspace_id>/')
def workspace_view(workspace_id):
    if session.get('id') is None:
        return redirect(url_for('index'))  # Redirect if not logged in

    # Sample questions (Replace with DB query)
    questions = [
        {"id": 1, "text": "What is O(n) complexity?"},
        {"id": 2, "text": "Explain binary search."},
        {"id": 3, "text": "Difference between list and tuple?"}
    ]

    return render_template('workspace_view.html', workspace_id=workspace_id, questions=questions)

# Add Question Page
@app.route('/workspace/<workspace_id>/add-question/', methods=['GET', 'POST'])
def add_question(workspace_id):
    if 'id' not in session or 'workspace' not in session:
        return redirect(url_for('signin'))  # Redirect to sign-in if session is missing

    if request.method == 'POST':
        uploaded_file = request.files.get('question_image')  # Handle file upload
        tags = request.form.get('tags')
        solution = request.form.get('solution')
        practice = request.form.get('practice') == 'on'  # Checkbox returns 'on' if checked

        # Save logic (TODO: Store in DB)
        print(f"Uploaded: {uploaded_file.filename if uploaded_file else 'No file'}")
        print(f"Tags: {tags}, Solution: {solution}, Practice: {practice}")

        return redirect(url_for('workspace_view', workspace_id=workspace_id))  # Redirect after saving

    return render_template('add_question.html', workspace_id=workspace_id)

# Create Question Paper Page
@app.route('/workspace/<workspace_id>/create-qp/', methods=['GET', 'POST'])
def create_qp(workspace_id):
    if 'id' not in session or 'workspace' not in session:
        return redirect(url_for('signin'))  # Redirect to sign-in if session is missing

    # Retrieve existing questions for the workspace
    if 'questions' not in session:
        session['questions'] = {}
    
    questions = session['questions'].get(workspace_id, [])

    # Handle question paper creation
    if request.method == 'POST':
        selected_questions = request.form.getlist('selected_questions')
        session['question_paper'] = selected_questions  # Store selected questions
        session.modified = True
        return redirect(url_for('workspace_view', workspace_id=workspace_id))  # Redirect after saving

    return render_template('create_qp.html', workspace_id=workspace_id, questions=questions)

@app.route('/workspace/<workspace_id>/question-paper/', methods=['GET', 'POST'])
def preview_qp(workspace_id):
    if 'id' not in session or 'workspace' not in session:
        return redirect(url_for('signin'))  # Redirect to sign-in if session is missing

    # Retrieve selected questions from session
    question_paper = session.get('question_paper', {}).get(workspace_id, [])

    # Handle question removal
    if request.method == 'POST' and 'delete_question' in request.form:
        question_id = int(request.form['delete_question'])
        question_paper = [q for q in question_paper if q["id"] != question_id]
        session['question_paper'][workspace_id] = question_paper
        session.modified = True

    return render_template('preview_qp.html', workspace_id=workspace_id, question_paper=question_paper)

@app.route('/workspace/<workspace_id>/download-qp/')
def download_qp(workspace_id):
    return "Download Question Paper - (TODO: Generate PDF)"

@app.route('/workspace/<workspace_id>/download-ans-key/')
def download_ans_key(workspace_id):
    return "Download Answer Key - (TODO: Generate PDF)"

# Practice Questions Page
@app.route('/workspace/<workspace_id>/practice/')
def practice_questions(workspace_id):
    return f"Practice questions for workspace {workspace_id}"  # Replace with actual functionality

# Edit Question Page
@app.route('/workspace/<workspace_id>/edit/<question_id>/')
def edit_question(workspace_id, question_id):
    return f"Edit question {question_id} in {workspace_id}"  # Replace with actual functionality

if __name__ == '__main__':
    app.run(debug=True)