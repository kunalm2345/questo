from flask import Flask, render_template, url_for, redirect, request, session
from wtforms import SelectMultipleField, SubmitField, FileField, BooleanField, TextAreaField, StringField
from wtforms.validators import DataRequired
from flask_wtf import FlaskForm
import requests
from bson import ObjectId  # For handling MongoDB ObjectId
from pymongo import MongoClient

# MongoDB connection
client = MongoClient("mongodb+srv://f20231146:Zc2Li5sO9UG6ZeEo@cluster0.koj5w.mongodb.net/?retryWrites=true&w=majority")
db = client['questoDB']
qp_coll = db['QuestionPapers']
q_coll = db['Questions']
user_coll = db['Users']
work_coll = db['Workspaces']

# Google OAuth credentials
CLIENT_ID = "435559535537-g0c328qb3ua1g0fdqqkjbrd6d646788d.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "http://127.0.0.1:5000/callback"

AUTH_URL = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v1/userinfo"
SCOPES = "https://www.googleapis.com/auth/userinfo.profile https://www.googleapis.com/auth/userinfo.email"

app = Flask(__name__)
app.config['SECRET_KEY'] = 'FLASK_SECKEY'


class AddQForm(FlaskForm):
    question_file = FileField('Upload Question', validators=[DataRequired()])
    question_text = TextAreaField('Question Text', validators=[DataRequired()])
    tags = StringField('Tags', validators=[DataRequired()])
    sol = TextAreaField('Solution', validators=[DataRequired()])
    practice = BooleanField('Set this as a practice question')
    submit = SubmitField('Save')

class WorkspaceForm(FlaskForm):
    key = StringField('Workspace Key', validators=[DataRequired()])
    submit = SubmitField('Create Workspace')

@app.route('/')
def index():
    if session.get('id'):
        return redirect(url_for('workspaces'))
    return render_template('landing.html')


@app.route('/signin/')
def signin():
    # Step 1: Redirect the user to Google's OAuth URL
    auth_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent"
    }
    auth_url = f"{AUTH_URL}?{'&'.join([f'{key}={value}' for key, value in auth_params.items()])}"
    return redirect(auth_url)


@app.route('/callback/')
def callback():
    # Step 2: Handle the callback from Google and exchange the code for an access token
    code = request.args.get('code')
    if not code:
        return "Error: No code provided!", 400

    token_data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    # Exchange the code for a token
    token_response = requests.post(TOKEN_URL, data=token_data)
    token_response_json = token_response.json()

    if "access_token" not in token_response_json:
        return f"Error: {token_response_json.get('error_description', 'Failed to retrieve access token')}", 400

    access_token = token_response_json["access_token"]

    # Step 3: Use the token to fetch user information
    headers = {"Authorization": f"Bearer {access_token}"}
    userinfo_response = requests.get(USERINFO_URL, headers=headers)
    userinfo = userinfo_response.json()

    if "email" not in userinfo:
        return "Error: Failed to retrieve user information", 400

    # Add user to the database if not already present
    user = user_coll.find_one({"email": userinfo["email"]})
    if not user:
        new_user = {
            "email": userinfo["email"],
            "name": userinfo["name"],
            "workspaces": []
        }
        result = user_coll.insert_one(new_user)
        user_id = result.inserted_id
    else:
        user_id = user["_id"]

    # Set session variables
    session['id'] = str(user_id)
    session['email'] = user.get("email")
    session['name'] = user.get("name")
    session['workspaces'] = user.get("workspaces", [])  # Assuming 'workspaces' is a list of workspace IDs

    return redirect(url_for('workspaces'))


from bson import ObjectId  # Ensure you import ObjectId for MongoDB object matching

@app.route('/workspaces/', methods=['GET', 'POST'])
def workspaces():
    # Check if the user is logged in
    if 'id' not in session:
        return redirect(url_for('index'))
    
    # Fetch the logged-in user's MongoDB document using the session's id
    user = user_coll.find_one({"_id": ObjectId(session['id'])})
    print(user)
    
    if not user:
        return redirect(url_for('index'))

    # Get the list of workspace IDs associated with the user
    workspace_ids = user.get("workspaces", [])

    form = WorkspaceForm()

    if form.validate_on_submit():
        workspace = {
            "key": form.key.data,
            "members": [session['id'],],  # Associate with the logged-in user
        }
        result = work_coll.insert_one(workspace)
        inserted_id = result.inserted_id
        print(inserted_id)
        # inserted_doc = work_coll.find_one({"_id": inserted_id})
        # Add the workspace _id to the user's workspaces list
        user_coll.update_one(
            {"_id": ObjectId(session['id'])},  
            {"$push": {"workspaces": inserted_id}}  
        )

    workspaces = []
    # Query MongoDB for each workspace by its ObjectId
    for workspace_id in user.get("workspaces", []):
        # print(workspace_id)
        # print(work_coll.find_one({"_id": workspace_id}))
        workspaces.append(work_coll.find_one({"_id": workspace_id}))

    # print(workspace_id)

    
    return render_template('workspaces.html', name=user.get("name", "User"), workspaces=workspaces, form=form)

@app.route('/workspace/<workspace_id>/')
def workspace_view(workspace_id):
    if 'id' not in session:
        return redirect(url_for('index'))
    # Find the workspace by ID
    workspace = work_coll.find_one({"key": workspace_id})
    if not workspace:
        return redirect(url_for('workspaces'))  # Redirect if workspace not found
    # Find questions associated with the workspace
    questions = list(q_coll.find({"workspace_id": workspace_id}))
    for question in questions:
        question['id'] = str(question['_id'])  # Ensure question IDs are converted to strings

    # Ensure workspace ID is converted to string for consistency
    workspace['id'] = str(workspace['_id'])

    # Sample questions (Replace with DB query)
    # questions = [
    #     {"id": 1, "ques_txt": "What is O(n) complexity?"},
    #     {"id": 2, "ques_txt": "Explain binary search."},
    #     {"id": 3, "ques_txt": "Difference between list and tuple?"}
    # ]

    # workspace  = {'name':'csf111', 'members':['1234','5678']}
    return render_template('workspace_view.html', workspace=workspace, questions=questions)

# Add Question Page
@app.route('/workspace/<workspace_id>/add-question/', methods=['GET', 'POST'])
def add_question(workspace_id, methods=['GET','POST']):
    workspace  = {'name':'csf111', 'members':['1234','5678']}
    if 'id' not in session:
        return redirect(url_for('signin'))  # Redirect to sign-in if session is missing

    form = AddQForm()
    #if form.validate_on_submit():
        #{"id":"1235", "sol":form.sol.data, "tags":form.tags.data, "question_file":form.question_file.data, "practice":form.practice.data})


    return render_template('add_question.html', workspace=workspace, form=form)

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
        return redirect(url_for('workspace_view', workspace=workspace))  # Redirect after saving

    return render_template('create_qp.html', workspace=workspace, questions=questions)

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

    return render_template('preview_qp.html', workspace=workspace, question_paper=question_paper)

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


@app.route('/create_workspace', methods=['POST'])
def create_workspace():
    # Ensure the user is logged in
    if 'id' not in session:
        return redirect(url_for('index'))

    # Convert session ID to ObjectId
    user_id = ObjectId(session['id'])

    # Get the workspace name from the form
    workspace_name = request.form.get('workspace_name')

    if not workspace_name:
        return "Error: Workspace name is required!", 400
    # Insert the new workspace into the database
    workspace = {
        "name": workspace_name,
        "description": "Default description for workspace.",  # Optional description
        "user_id": user_id,  # Associate with the logged-in user
    }
    result = work_coll.insert_one(workspace)

    # Add the workspace _id to the user's workspaces list
    user_coll.update_one(
        {"_id": user_id},  # Match the logged-in user
        {"$push": {"workspaces": result.inserted_id}}  # Add the workspace ID
    )

    return redirect(url_for('workspaces'))


@app.route('/logout/')
def logout():
    session.clear()  # Clears all session data (logs out user)
    return redirect(url_for('index'))  # Redirects to homepage


if __name__ == '__main__':
    app.run(debug=True)
