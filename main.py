from flask import Flask, render_template, url_for, redirect, request, session, jsonify, flash, send_file
from wtforms import SelectMultipleField, SubmitField, FileField, BooleanField, TextAreaField, StringField
from wtforms.validators import DataRequired
from flask_wtf import FlaskForm
import cloudinary
import cloudinary.uploader
import requests
from bson import ObjectId  # For handling MongoDB ObjectId
from pymongo import MongoClient

from functions import add_to_vectordb, vectordb_exists, search_vectordb

# Cloudinary configuration (replace with your credentials)
cloudinary.config(
    cloud_name="dy0q5cx5j",
    api_key="212258678217944",
    api_secret="xK3KvwLdOe-RaAl2o_c9LkMfMUQ"
)
from functions import retrieve_similar_images
import io
import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors


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


# class AddQForm(FlaskForm):
#     question_file = FileField('Upload Question', validators=[DataRequired()])
#     question_text = TextAreaField('Question Text', validators=[DataRequired()])
#     tags = StringField('Tags', validators=[DataRequired()])
#     sol = TextAreaField('Solution', validators=[DataRequired()])
#     practice = BooleanField('Set this as a practice question')
#     submit = SubmitField('Save')

# First form - only for image upload
class ImageUploadForm(FlaskForm):
    question_file = FileField('Upload Question Image', validators=[DataRequired()])
    workspace_id = StringField('Workspace ID', validators=[DataRequired()])
    submit = SubmitField('Upload Image')

# Second form - modified AddQForm with file_src instead of question_file
class AddQForm(FlaskForm):
    file_src = StringField('Image URL')  # New field to store image URL
    question_text = TextAreaField('Question Text', validators=[DataRequired()])
    tags = StringField('Tags', validators=[DataRequired()])
    sol = TextAreaField('Solution', validators=[DataRequired()])
    practice = BooleanField('Set this as a practice question')
    submit = SubmitField('Save Question')

class WorkspaceForm(FlaskForm):
    key = StringField('Workspace Key', validators=[DataRequired()])
    submit = SubmitField('Create Workspace')

class SearchForm(FlaskForm):
    query = StringField('Search', validators=[DataRequired()], 
                       render_kw={"placeholder": "Enter search query..."})
    submit = SubmitField('Search')

# Cloudinary setup - add near the top of your application
import cloudinary
import cloudinary.uploader
import cloudinary.api
from werkzeug.utils import secure_filename
import json
import datetime  # For timestamping uploads

# Initialize Cloudinary
cloudinary.config(
    cloud_name = "dvsbq6nfs",
    api_key = "415791229877485",
    api_secret = "8-qnUFb2YXotAXgsnMU_t1BPusE"
)

@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    if 'question_file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['question_file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Get the workspace_id from the form
    workspace_id = request.form.get('workspace_id')
    if not workspace_id:
        return jsonify({'error': 'Missing workspace_id'}), 400
    
    # Check file type
    allowed_extensions = {'png', 'jpg', 'jpeg'}
    filename = secure_filename(file.filename)
    file_ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'File type not allowed'}), 400
    
    try:
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(file, 
                                                  folder=f"workspace_{workspace_id}",
                                                  resource_type="image")
        file_url = upload_result.get('secure_url')

        # Process with genAI
        result = None
        try:
            import llm
            ai_response = llm.process_image_url_with_genai(
                file_url, 
                "Respond it in python dictionary type object with three fields: ques_txt (str), tags (list of str), solution (str). DO NOT write any other text before or after this. ques_txt should be the transcription of the question tags should be a list of 1-3 keyword from the question that can help a model to know what its related to. solution should be the solution of the question", 
                llm.api_key, 
                model_name="gemini-2.0-flash"
            )
            result_str = ai_response.lstrip('```python').rstrip('```').lstrip('```json').lstrip('```javascript')
            result = eval(result_str)
        except Exception as e:
            print(f"Error processing image with AI: {str(e)}")
            # Continue even if AI processing fails
        
        # Return JSON with file URL and AI results
        return jsonify({
            'success': True,
            'file_url': file_url,
            'result': result
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        }
        result = user_coll.insert_one(new_user)
        user_id = result.inserted_id
    else:
        user_id = user["_id"]

    # Set session variables
    session['id'] = str(user_id)
    session['email'] = user.get("email")
    session['name'] = user.get("name")
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

        workspace_key = workspace.get("key")
        existing_workspace = work_coll.find_one({"key": workspace_key})
        if existing_workspace:
            flash("Error: Workspace key already exists!", "danger")
            return redirect(url_for("workspaces"))
        
        result = work_coll.insert_one(workspace)
        inserted_id = result.inserted_id
        print(inserted_id)
        # inserted_doc = work_coll.find_one({"_id": inserted_id})
        # Add the workspace _id to the user's workspaces list
        user_coll.update_one(
            {"_id": ObjectId(session['id'])},  
            {"$push": {"workspaces": inserted_id}}  
        )
        flash("Workspace created successfully!", "success")
        return redirect(url_for("workspaces"))

    workspaces = []
    # Query MongoDB for each workspace by its ObjectId
    for workspace_id in user.get("workspaces", []):
        # print(workspace_id)
        # print(work_coll.find_one({"_id": workspace_id}))
        workspaces.append(work_coll.find_one({"_id": workspace_id}))

    # print(workspace_id)

    
    return render_template('workspaces.html', name=user.get("name", "User"), workspaces=workspaces, form=form)

@app.route('/workspace/<workspace_key>/', methods=['GET', 'POST'])
def workspace_view(workspace_key):
    if 'id' not in session:
        return redirect(url_for('index'))
    
    # Create search form
    form = SearchForm()

    # Find the workspace by key
    workspace = work_coll.find_one({"key": workspace_key})
    if not workspace:
        return redirect(url_for('workspaces'))  # Redirect if workspace not found
    
    # Get MongoDB _id of the workspace
    mongo_id = workspace.get("_id")
    
    # Default to showing all questions
    questions = list(q_coll.find({"workspace_id": mongo_id}))
    for question in questions:
        question['id'] = str(question['_id'])  # Ensure question IDs are converted to strings

    # Ensure workspace ID is converted to string for consistency
    workspace['id'] = str(workspace['_id'])

    # Initialize search status
    is_search = False
    search_query = None

    # Handle search form submission
    if form.validate_on_submit():
        is_search = True
        search_query = form.query.data
        print(f"Processing search for: {search_query}")
        
        # Check if vectordb exists for this workspace
        if vectordb_exists(workspace_key):
            try:
                # Search vectordb for similar questions
                search_results = search_vectordb(workspace_key, search_query, top_k=3)
                print(f"Search results: {search_results}")
                
                # Get unique image paths from the search results
                image_paths = [result["image_path"] for result in search_results]
                
                if image_paths:
                    # Find questions with these image paths
                    search_questions = list(q_coll.find({"file_src": {"$in": image_paths}}))
                    for question in search_questions:
                        question['id'] = str(question['_id'])
                        
                        # Add relevance score to questions
                        for result in search_results:
                            if result["image_path"] == question["file_src"]:
                                question["relevance_score"] = result["score"]
                                question["matching_tag"] = result["tag"]
                                break
                    
                    # Sort questions by relevance score if available
                    if all("relevance_score" in q for q in search_questions):
                        search_questions.sort(key=lambda q: q.get("relevance_score", float('inf')))
                    
                    questions = search_questions
                    print(f"Found {len(questions)} matching questions")
                else:
                    # No search results, return empty list
                    questions = []
                    print("No matching questions found")
            except Exception as e:
                print(f"Error searching vectordb: {e}")
                import traceback
                traceback.print_exc()
                # Continue with default questions list

    return render_template('workspace_view.html', 
                           workspace=workspace, 
                           questions=questions, 
                           form=form,
                           is_search=is_search,
                           search_query=search_query)


@app.route('/workspace/<workspace_id>/add-question/', methods=['GET', 'POST'])
def add_question(workspace_id):
    # Verify workspace exists
    workspace = work_coll.find_one({"key": workspace_id})
    if not workspace:
        return redirect(url_for('workspaces'))
    
    if 'id' not in session:
        return redirect(url_for('signin'))
    
    # Create form
    question_form = AddQForm()
    
    # Get file_url from query parameter if available
    file_url = request.args.get('file_url')
    
    # Handle form submission
    if request.method == 'POST' and question_form.validate_on_submit():
        # Parse tags from JSON string
        try:
            tags_list = json.loads(question_form.tags.data)
        except:
            tags_list = []  # Default to empty list if parsing fails
        
        # Save question to database
        question = {
            "workspace_id": workspace.get("_id"),
            "file_src": question_form.file_src.data,
            "ques_txt": question_form.question_text.data,
            "tags": tags_list,
            "solutions": question_form.sol.data,
            "practice": question_form.practice.data,
        }
        q_coll.insert_one(question)
        
        # Add the image and tags to the vectordb (with error handling)
        file_src = question_form.file_src.data
        
        try:
            # Process each tag separately for better retrieval
            for tag in tags_list:
                add_to_vectordb(workspace_id, tag, file_src)
        except Exception as e:
            # Log the error but continue - don't prevent question from being added
            print(f"Error updating vectordb: {e}")
            # You might want to add proper logging here
        
        return redirect(url_for('workspace_view', workspace_key=workspace_id))
    
    return render_template(
        'add_question.html',
        workspace=workspace,
        question_form=question_form,
        file_url=file_url
    )


# Create Question Paper Page
# Replace your existing create_qp route with this updated version
@app.route('/workspace/<workspace_key>/create-qp/', methods=['GET', 'POST'])
def create_qp(workspace_key):
    if 'id' not in session:
        return redirect(url_for('signin'))  # Redirect to sign-in if session is missing

    # Find the workspace by ID
    workspace = work_coll.find_one({"key": workspace_key})
    if not workspace:
        return redirect(url_for('workspaces'))  # Redirect if workspace not found
    
    # Convert ObjectId to string for the template
    workspace['id'] = str(workspace['_id'])
    
    # Get all available questions for this workspace
    all_questions = list(q_coll.find({"workspace_id": workspace['_id']}))
    
    # Convert ObjectIds to strings for the template
    for question in all_questions:
        question['id'] = str(question['_id'])
    
    # Get the list of questions already in the temp list
    temp_question_ids = []
    if 'temp_questions' in session and session['temp_questions']:
        temp_question_ids = [q['id'] for q in session['temp_questions']]
    
    # Filter out questions that are already in the temp list
    available_questions = [q for q in all_questions if q['id'] not in temp_question_ids]
    
    # Handle question paper creation form submission
    if request.method == 'POST':
        selected_questions = request.form.getlist('selected_questions')
        
        # Create a list to store the question paper
        question_paper = []
        
        # Add selected questions
        for q_id in selected_questions:
            question = q_coll.find_one({"_id": ObjectId(q_id)})
            if question:
                question_paper.append({
                    'id': str(question['_id']),
                    'text': question['ques_txt'],
                    'marks': 1  # Default marks
                })
        
        # Add temp questions if they exist
        if 'temp_questions' in session:
            for temp_q in session['temp_questions']:
                # Check if this question is already in selected_questions
                if temp_q['id'] not in selected_questions:
                    question_paper.append(temp_q)
        
        # Store the question paper in session
        if 'question_paper' not in session:
            session['question_paper'] = {}
        
        session['question_paper'][workspace_key] = question_paper
        session.modified = True
        
        # Clear temp questions after creating the paper
        if 'temp_questions' in session:
            session.pop('temp_questions')
            session.modified = True
        
        # Redirect to preview
        return redirect(url_for('preview_qp', workspace_id=str(workspace['_id'])))

    # Pass filtered available questions to the template
    return render_template('create_qp.html', workspace=workspace, questions=available_questions)
    
@app.route('/workspace/<workspace_key>/add_question_to_temp', methods=['POST'])
@app.route('/workspace/<workspace_key>/add_question_to_temp', methods=['POST'])
def add_question_to_temp(workspace_key):
    if 'id' not in session:
        return redirect(url_for('signin'))
    
    # Find the workspace by key
    workspace = work_coll.find_one({"key": workspace_key})
    if not workspace:
        return redirect(url_for('workspaces'))
    
    # Get form data
    question_id = request.form.get('question_id')
    
    # Parse marks as integer, with fallback to 1
    try:
        marks = int(request.form.get('marks', 1))
        # Ensure marks is at least 1
        marks = max(1, marks)
    except:
        marks = 1
    
    # Get the question from database
    question = q_coll.find_one({"_id": ObjectId(question_id)})
    
    if question:
        # Initialize session temp_questions if it doesn't exist
        if 'temp_questions' not in session:
            session['temp_questions'] = []
        
        # Check if question is already in the temp list
        existing_q_ids = [q['id'] for q in session['temp_questions']]
        if question_id not in existing_q_ids:
            # Add question to temp list with specified marks
            temp_question = {
                'id': question_id,
                'text': question['ques_txt'],
                'marks': marks
            }
            
            # Append to session list
            temp_questions = session['temp_questions']
            temp_questions.append(temp_question)
            session['temp_questions'] = temp_questions
            session.modified = True  # Important for session to save changes
            
        # Debug info to console
        print(f"Temp questions: {session['temp_questions']}")
        print(f"Total marks: {sum(q['marks'] for q in session['temp_questions'])}")
    
    # Redirect back to create question paper page
    return redirect(url_for('create_qp', workspace_key=workspace_key))

@app.route('/workspace/<workspace_key>/remove_question_from_temp')
def remove_question_from_temp(workspace_key):
    if 'id' not in session:
        return redirect(url_for('signin'))
    
    # Get question id from query parameters
    question_id = request.args.get('question_id')
    
    # Remove from session if exists
    if 'temp_questions' in session:
        temp_questions = [q for q in session['temp_questions'] if q['id'] != question_id]
        session['temp_questions'] = temp_questions
        session.modified = True  # Important for session to save changes
    
    # Redirect back to create question paper page
    return redirect(url_for('create_qp', workspace_key=workspace_key))

# Update your preview_qp route to match the template
@app.route('/workspace/<workspace_id>/question-paper/', methods=['GET', 'POST'])
def preview_qp(workspace_id):
    if 'id' not in session:
        return redirect(url_for('signin'))

    # Find the workspace by ID
    workspace = work_coll.find_one({"_id": ObjectId(workspace_id)})
    if not workspace:
        return redirect(url_for('workspaces'))
    
    # Make sure id and key are available
    workspace['id'] = str(workspace['_id'])
    workspace_key = workspace.get('key')
    
    # Retrieve selected questions from session
    question_paper = []
    if 'question_paper' in session and workspace_key in session['question_paper']:
        question_paper = session['question_paper'][workspace_key]
    
    # Handle question removal
    if request.method == 'POST' and 'delete_question' in request.form:
        question_id = request.form['delete_question']
        question_paper = [q for q in question_paper if q["id"] != question_id]
        
        if 'question_paper' not in session:
            session['question_paper'] = {}
        
        session['question_paper'][workspace_key] = question_paper
        session.modified = True
        
        # Redirect to avoid form resubmission
        return redirect(url_for('preview_qp', workspace_id=workspace_id))
    
    # Get question paper metadata
    qp_metadata = {}
    if 'qp_metadata' in session and workspace_key in session['qp_metadata']:
        qp_metadata = session['qp_metadata'][workspace_key]
    
    # Calculate total marks
    total_marks = sum(q.get('marks', 0) for q in question_paper)
    
    return render_template('preview_qp.html', 
                          workspace=workspace, 
                          question_paper=question_paper,
                          total_marks=total_marks,
                          qp_metadata=qp_metadata)

# Add a route to update question marks
@app.route('/workspace/<workspace_id>/update-question-marks', methods=['POST'])
def update_question_marks(workspace_id):
    if 'id' not in session:
        return redirect(url_for('signin'))
    
    # Find the workspace
    workspace = work_coll.find_one({"_id": ObjectId(workspace_id)})
    if not workspace:
        return redirect(url_for('workspaces'))
    
    workspace_key = workspace.get('key')
    
    # Get form data
    question_id = request.form.get('question_id')
    try:
        marks = int(request.form.get('marks', 1))
        marks = max(1, marks)  # Ensure marks is at least 1
    except:
        marks = 1
    
    # Update the question marks in the session
    if 'question_paper' in session and workspace_key in session['question_paper']:
        question_paper = session['question_paper'][workspace_key]
        for question in question_paper:
            if question['id'] == question_id:
                question['marks'] = marks
                break
        
        session['question_paper'][workspace_key] = question_paper
        session.modified = True
    
    return redirect(url_for('preview_qp', workspace_id=workspace_id))

# Add a route to update question paper metadata
@app.route('/workspace/<workspace_id>/update-qp-metadata', methods=['POST'])
def update_qp_metadata(workspace_id):
    if 'id' not in session:
        return redirect(url_for('signin'))
    
    # Find the workspace
    workspace = work_coll.find_one({"_id": ObjectId(workspace_id)})
    if not workspace:
        return redirect(url_for('workspaces'))
    
    workspace_key = workspace.get('key')
    
    # Get form data
    title = request.form.get('title', 'Untitled Question Paper')
    try:
        duration = int(request.form.get('duration', 60))
    except:
        duration = 60
    
    # Update metadata in session
    if 'qp_metadata' not in session:
        session['qp_metadata'] = {}
    
    session['qp_metadata'][workspace_key] = {
        'title': title,
        'duration': duration
    }
    session.modified = True
    
    return redirect(url_for('preview_qp', workspace_id=workspace_id))

# Add a route to save question paper to database
@app.route('/workspace/<workspace_id>/save-qp-to-db', methods=['POST'])
def save_qp_to_db(workspace_id):
    if 'id' not in session:
        return redirect(url_for('signin'))
    
    # Find the workspace
    workspace = work_coll.find_one({"_id": ObjectId(workspace_id)})
    if not workspace:
        return redirect(url_for('workspaces'))
    
    workspace_key = workspace.get('key')
    
    # Get question paper data from session
    question_paper = []
    if 'question_paper' in session and workspace_key in session['question_paper']:
        question_paper = session['question_paper'][workspace_key]
    else:
        flash("Cannot save empty question paper", "danger")
        return redirect(url_for('preview_qp', workspace_id=workspace_id))
    
    # Get metadata
    qp_metadata = {}
    if 'qp_metadata' in session and workspace_key in session['qp_metadata']:
        qp_metadata = session['qp_metadata'][workspace_key]
    
    # Prepare question paper document for MongoDB
    qp_document = {
        "docTitle": qp_metadata.get('title', 'Untitled Question Paper'),
        "ques": [
            {
                "question_id": ObjectId(q['id']),
                "marks": q['marks']
            } for q in question_paper
        ],
        "maxMarks": sum(q.get('marks', 0) for q in question_paper),
        "maxTime": qp_metadata.get('duration', 60),
        "workspace_id": ObjectId(workspace_id),
        "created_at": datetime.datetime.now(),
        "created_by": ObjectId(session['id'])
    }
    
    try:
        # Save to database
        result = qp_coll.insert_one(qp_document)
        
        if result.inserted_id:
            # Clear session data for this question paper
            if 'question_paper' in session and workspace_key in session['question_paper']:
                del session['question_paper'][workspace_key]
            
            if 'qp_metadata' in session and workspace_key in session['qp_metadata']:
                del session['qp_metadata'][workspace_key]
            
            session.modified = True
            
            flash("Question paper saved successfully!", "success")
        else:
            flash("Error saving question paper. Please try again.", "danger")
    except Exception as e:
        print(f"Error saving question paper to database: {e}")
        flash(f"Error saving question paper: {str(e)}", "danger")
    
    # Redirect to workspace view
    return redirect(url_for('workspace_view', workspace_key=workspace_key))

# Add download routes
@app.route('/workspace/<workspace_id>/download-qp/')
def download_qp(workspace_id):
    if 'id' not in session:
        return redirect(url_for('signin'))
    
    # Find the workspace
    workspace = work_coll.find_one({"_id": ObjectId(workspace_id)})
    if not workspace:
        return redirect(url_for('workspaces'))
    
    workspace_key = workspace.get('key')
    
    # Get question paper data
    question_paper = []
    if 'question_paper' in session and workspace_key in session['question_paper']:
        question_paper = session['question_paper'][workspace_key]
    
    # Get metadata
    qp_metadata = {}
    if 'qp_metadata' in session and workspace_key in session['qp_metadata']:
        qp_metadata = session['qp_metadata'][workspace_key]
    
    # Create PDF document
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Set title and metadata
    title = qp_metadata.get('title', 'Question Paper')
    duration = qp_metadata.get('duration', 60)
    total_marks = sum(q.get('marks', 0) for q in question_paper)
    
    # Add title
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width/2, height - 50, title)
    
    # Add metadata
    pdf.setFont("Helvetica", 12)
    metadata_text = f"Duration: {duration} minutes | Total Marks: {total_marks}"
    pdf.drawCentredString(width/2, height - 70, metadata_text)
    
    # Add each question
    y_position = height - 100
    for i, question in enumerate(question_paper, 1):
        # Question number and marks
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_position, f"Q{i}. ({question.get('marks', 0)} marks)")
        y_position -= 20
        
        # Question text
        pdf.setFont("Helvetica", 10)
        text = question.get('text', '')
        
        # Handle text wrapping (simple implementation)
        words = text.split()
        line = ""
        for word in words:
            test_line = line + " " + word if line else word
            if pdf.stringWidth(test_line, "Helvetica", 10) < width - 100:
                line = test_line
            else:
                pdf.drawString(60, y_position, line)
                y_position -= 15
                line = word
        
        if line:
            pdf.drawString(60, y_position, line)
            y_position -= 15
        
        # Add spacing between questions
        y_position -= 20
        
        # Check if need new page
        if y_position < 100:
            pdf.showPage()
            y_position = height - 50
    
    pdf.save()
    
    # Return the PDF as a downloadable file
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{title.replace(' ', '_')}.pdf",
        mimetype='application/pdf'
    )

@app.route('/workspace/<workspace_id>/download-ans-key/')
def download_ans_key(workspace_id):
    if 'id' not in session:
        return redirect(url_for('signin'))
    
    # Find the workspace
    workspace = work_coll.find_one({"_id": ObjectId(workspace_id)})
    if not workspace:
        return redirect(url_for('workspaces'))
    
    workspace_key = workspace.get('key')
    
    # Get question paper data
    question_paper = []
    if 'question_paper' in session and workspace_key in session['question_paper']:
        question_paper = session['question_paper'][workspace_key]
    
    # Get metadata
    qp_metadata = {}
    if 'qp_metadata' in session and workspace_key in session['qp_metadata']:
        qp_metadata = session['qp_metadata'][workspace_key]
    
    # Create PDF document
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Set title and metadata
    title = f"Answer Key: {qp_metadata.get('title', 'Question Paper')}"
    
    # Add title
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width/2, height - 50, title)
    
    # Add each question with solution
    y_position = height - 80
    for i, question in enumerate(question_paper, 1):
        # Get question details from database to access solution
        try:
            db_question = q_coll.find_one({"_id": ObjectId(question['id'])})
        except:
            db_question = None
        
        if not db_question:
            continue
        
        # Question number
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(50, y_position, f"Q{i}. ({question.get('marks', 0)} marks)")
        y_position -= 20
        
        # Question text
        pdf.setFont("Helvetica", 10)
        text = question.get('text', '')
        
        # Handle text wrapping
        words = text.split()
        line = ""
        for word in words:
            test_line = line + " " + word if line else word
            if pdf.stringWidth(test_line, "Helvetica", 10) < width - 100:
                line = test_line
            else:
                pdf.drawString(60, y_position, line)
                y_position -= 15
                line = word
        
        if line:
            pdf.drawString(60, y_position, line)
            y_position -= 15
        
        # Add solution heading
        y_position -= 10
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(60, y_position, "Solution:")
        y_position -= 15
        
        # Add solution text
        pdf.setFont("Helvetica", 10)
        solution_text = db_question.get('solutions', 'No solution available')
        
        # Handle solution text wrapping
        words = solution_text.split()
        line = ""
        for word in words:
            test_line = line + " " + word if line else word
            if pdf.stringWidth(test_line, "Helvetica", 10) < width - 120:
                line = test_line
            else:
                pdf.drawString(70, y_position, line)
                y_position -= 15
                line = word
        
        if line:
            pdf.drawString(70, y_position, line)
            y_position -= 15
        
        # Add spacing between questions
        y_position -= 30
        
        # Check if need new page
        if y_position < 100:
            pdf.showPage()
            y_position = height - 50
    
    pdf.save()
    
    # Return the PDF as a downloadable file
    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"Answer_Key_{qp_metadata.get('title', 'Question_Paper').replace(' ', '_')}.pdf",
        mimetype='application/pdf'
    )


# Practice Questions Page
@app.route('/workspace/<workspace_id>/practice/', methods=['GET', 'POST'])
def practice_questions(workspace_id):
    # Check if the user is logged in
    if 'id' not in session:
        return redirect(url_for('index'))
    
    # Find the workspace by ID
    workspace = work_coll.find_one({"key": workspace_id})
    if not workspace:
        return redirect(url_for('workspaces'))  # Redirect if workspace not found
    
    # Convert ObjectId to string for the template
    workspace['id'] = str(workspace['_id'])
    
    # Initialize the search form
    form = SearchForm()
    
    # Initialize questions list
    questions = []
    
    # Handle form submission
    if form.validate_on_submit():
        # Get the search query from the form
        search_query = form.query.data

        # Get practice questions for this workspace
        practice_questions_query = {
            "workspace_id": ObjectId(workspace_id),
            "isPractice": True
        }
        all_practice_questions = list(q_coll.find(practice_questions_query))

        # If there's a search query, use FAISS to find similar questions
        if search_query:
            # Get the IDs of practice questions in this workspace
            question_ids = [str(q["_id"]) for q in all_practice_questions]
            
            # Use the FAISS search function to find similar questions
            similar_ids = retrieve_similar_images(search_query, question_ids)
            
            # Filter the questions to only include those found by FAISS
            questions = [q for q in all_practice_questions if str(q["_id"]) in similar_ids]
        else:
            # If no search query, return all practice questions
            questions = all_practice_questions
    else:
        # On initial page load, show all practice questions
        questions = list(q_coll.find({
            "workspace_id": ObjectId(workspace['id']),
            "isPractice": True
        }))
        
    # Convert ObjectIds to strings for the template
    for question in questions:
        question['id'] = str(question['_id'])

    return render_template('practice_questions.html', 
                            workspace=workspace, 
                            questions=questions,
                            form=form)

# Edit Question Page
@app.route('/workspace/<workspace_id>/edit/<question_id>/')
def edit_question(workspace_id, question_id):
    return f"Edit question {question_id} in {workspace_id}"  # Replace with actual functionality


@app.route('/create_workspace/', methods=['POST'])
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
