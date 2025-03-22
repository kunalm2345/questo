from flask import Flask, render_template, url_for, redirect, request, session
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


@app.route('/')
def index():
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
    session['email'] = userinfo.get("email")
    session['name'] = userinfo.get("name")

    return redirect(url_for('workspaces'))


from bson import ObjectId  # Ensure you import ObjectId for MongoDB object matching

@app.route('/workspaces/')
def workspaces():
    # Check if the user is logged in
    if 'id' not in session:
        return redirect(url_for('index'))
    
    # Fetch the logged-in user's MongoDB document using the session's id
    user = user_coll.find_one({"_id": ObjectId(session['id'])})
    
    if not user:
        return redirect(url_for('index'))
    
    # Get the list of workspace IDs associated with the user
    workspace_ids = user.get("workspaces", [])
    
    # Query MongoDB for each workspace by its ObjectId
    workspaces = [
        {
            "id": str(workspace["_id"]),
            "name": workspace["name"],
            "description": workspace.get("description", "No description available")
        }
        for workspace in work_coll.find({"_id": {"$in": [ObjectId(wid) for wid in workspace_ids]}})
    ]
    
    return render_template('workspaces.html', name=user.get("name", "User"), workspaces=workspaces)

@app.route('/workspace/<workspace_id>')
def workspace_view(workspace_id):
    if 'id' not in session:
        return redirect(url_for('index'))

    # Find the workspace by ID
    workspace = work_coll.find_one({"_id": ObjectId(workspace_id)})
    if not workspace:
        return "Error: Workspace not found!", 404

    # Find questions associated with the workspace
    questions = list(q_coll.find({"workspace_id": ObjectId(workspace_id)}))
    for question in questions:
        question['id'] = str(question['_id'])  # Ensure question IDs are converted to strings

    # Ensure workspace ID is converted to string for consistency
    workspace['id'] = str(workspace['_id'])

    return render_template('workspace_view.html', workspace=workspace, questions=questions)


@app.route('/workspace/<workspace_id>/add_question', methods=['POST'])
def add_question(workspace_id):
    if 'id' not in session:
        return redirect(url_for('index'))

    question_text = request.form.get('question_text')
    if not question_text:
        return "Error: Question text is required!", 400

    question = {
        "workspace_id": ObjectId(workspace_id),
        "text": question_text,
        "created_by": ObjectId(session['id']),
    }
    q_coll.insert_one(question)

    return redirect(url_for('workspace_view', workspace_id=workspace_id))


@app.route('/workspace/<workspace_id>/delete_question/<question_id>', methods=['POST'])
def delete_question(workspace_id, question_id):
    if 'id' not in session:
        return redirect(url_for('index'))

    q_coll.delete_one({"_id": ObjectId(question_id), "workspace_id": ObjectId(workspace_id)})
    return redirect(url_for('workspace_view', workspace_id=workspace_id))



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
