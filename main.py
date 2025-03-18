from flask import Flask, render_template, url_for, redirect, request, session, send_from_directory, jsonify

# Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'FLASK_SECKEY'


@app.route('/', methods=['GET','POST'])
def index():
    # if session.get('key') != None:
    #     return redirect(url_for('dash'))
    return render_template('landing.html')

@app.route('/signin/', methods=['GET','POST'])
def signin():

    session['id'] = '123'
    session['email'] = 'kunalm2345@gmail.com'
    session['name'] = 'Kunal'
    session['workspace'] = ['csf111',]
    return redirect(url_for('workspaces'))

@app.route('/workspaces/')
def workspaces():
    if session.get('id') == None:
        return redirect(url_for('index'))
    return render_template('workspaces.html')

# @app.errorhandler(404)
# def not_found(e):
#   return render_template("404.html")

if __name__ == '__main__':
    app.run(debug=True)
