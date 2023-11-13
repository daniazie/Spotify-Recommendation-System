from flask import Flask, render_template, request, redirect, session, make_response
from rec_sys import recommend
import pandas as pd
pd.options.mode.chained_assignment = None  # default='warn'

app = Flask(__name__)
app.config.from_pyfile('config.py')

@app.route('/auth')
def auth():
    return redirect(recommend.AUTH_URL)

@app.route('/callback/')
def callback():
    auth_token = request.args['code']
    auth_header = recommend.authorize(auth_token)
    session['auth_header'] = auth_header
    return profile()


def valid_token(resp):
    return resp is not None and not 'error' in resp

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/go', methods=['GET','POST'])
def go():
    session.clear()
    session['num_tracks'] = '50'
    session['time_range'] = 'short_term'
    base_url = recommend.AUTH_URL
    response = make_response(redirect(base_url),302)
    return response

@app.route('/profile')
def profile():
    if 'auth_header' in session:
        auth_header = session['auth_header']
        top_tracks_df = recommend.get_users_top_tracks(auth_header)
        if "failed" not in top_tracks_df:
            tracks_vector, nontop_tracks_df = recommend.generate_track_vector(top_tracks_df, 1.2)
            top15 = recommend.generate_recommendation(tracks_vector, nontop_tracks_df)
            tracks_list = recommend.gen_recs_list(top15)
            track_ids = recommend.get_id_list(tracks_list)
            print("yes")
            try:
                for i in range(15):
                    tracks_list[i]['track_url'] = recommend.get_track_url(auth_header, track_ids[i])
                msg = 'succeed'
                print("yes")
            except:
                msg = 'failed'
                print("no")
            session['tracks_list'] = tracks_list
            status = "success"
            return render_template("done.html", tracks_list = tracks_list, status = status, msg = msg)
        else:
            print("didn't work")
            status = "failure"
            msg = 'failed'
            return render_template("done.html", status = status, msg = msg)
    return render_template('done.html')

@app.route('/create', methods = ['POST'])
def create():
    if 'auth_header' in session:
        auth_header = session['auth_header']
        user_id = recommend.get_user_profile(auth_header)
        tracks_list = session.get('tracks_list')
        uri_dict = recommend.gen_uri_dict(tracks_list)

        if request.method == 'POST':
            try:
                playlist_id = recommend.create_playlist(auth_header,user_id)
                recommend.add_tracks_to_playlist(auth_header, playlist_id, uri_dict)
                msg = 'succeed'
                message = "Playlist created."
                status = 'success'
                return render_template("done.html", tracks_list = tracks_list, uri_dict = uri_dict, message = message, msg = msg, status = status)
            except:
                message = "Failed to create playlist."
                msg = 'failed'
                status = 'failure'
                return render_template("done.html", tracks_list = tracks_list, message = message, msg = msg, status = status)
    return render_template("done.html")

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')




if __name__ == "__main__":
    app.run(debug=False)