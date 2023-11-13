from __future__ import print_function
import base64
import json
import requests

from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics.pairwise import cosine_similarity
import pandas as pd

try:
    import urllib.request, urllib.error
    import urllib.parse as urllibparse
except ImportError:
    import urllib as urllibparse


# Set up Spotify API base URL
SPOTIFY_API_BASE_URL = 'http://api.spotify.com'
API_VERSION = 'v1'
SPOTIFY_API_URL = "{}/{}".format(SPOTIFY_API_BASE_URL, API_VERSION)

# Set up authorization URL
SPOTIFY_AUTH_BASE_URL = 'https://accounts.spotify.com/{}'
SPOTIFY_AUTH_URL = SPOTIFY_AUTH_BASE_URL.format('authorize')
SPOTIFY_TOKEN_URL = SPOTIFY_AUTH_BASE_URL.format('api/token')

# Client keys
CLIENT = json.load(open('./conf.json', 'r+'))
CLIENT_ID = CLIENT['id']
CLIENT_SECRET = CLIENT['secret']

# Server side parameters
REDIRECT_URI = "http://localhost:5000/callback/"
SCOPE = 'user-top-read playlist-modify-public playlist-modify-private'
STATE = ""
SHOW_DIALOG_bool = True
SHOW_DIALOG_str = str(SHOW_DIALOG_bool).lower()

auth_query_parameters = {
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPE,
    "client_id": CLIENT_ID
}



URL_ARGS = "&".join(["{}={}".format(key, urllibparse.quote(val))
                     for key, val in list(auth_query_parameters.items())])
AUTH_URL = "{}/?{}".format(SPOTIFY_AUTH_URL, URL_ARGS)

def authorize(auth_token):
    code_payload = {
        "grant_type": "authorization_code",
        "code": str(auth_token),
        "redirect_uri": REDIRECT_URI
    }

    base64encoded = base64.b64encode(("{}:{}".format(CLIENT_ID, CLIENT_SECRET)).encode())
    headers = {"Authorization": "Basic {}".format(base64encoded.decode())}

    post_request = requests.post(SPOTIFY_TOKEN_URL, data=code_payload, headers=headers)

    response_data = json.loads(post_request.text)
    access_token = response_data["access_token"]

    auth_header = {"Content-Type": "application/json", "Authorization": "Bearer {}".format(access_token)}
    return auth_header

def get_dataset(spotify_data):
    spotify_data = pd.read_parquet('tracks.parquet')
    spotify_data = spotify_data.rename(columns={'id': 'track_id', 'id_artists':'artist_ids'})
    spotify_data = spotify_data.reset_index()
    return spotify_data

spotify_data = pd.DataFrame()
spotify_data = get_dataset(spotify_data)

def get_features_df(df):
    df = spotify_data

    # discarding categorical and unnecessary feautures
    df = df.drop('artists',axis=1)
    df = df.drop('artist_ids',axis=1)
    df = df.drop('name',axis=1)
    df = df.drop('time_signature',axis=1)
    df = df.drop('release_date',axis=1)
    df = df.drop('popularity',axis=1)
    df = df.drop('explicit',axis=1)
    df = df.drop('duration_ms',axis=1)
    df = df.drop('mode',axis=1)

    return df

def scale_features(df):

    scaled_features = MinMaxScaler().fit_transform([
    df['acousticness'].values,
    df['danceability'].values,
    df['energy'].values,
    df['instrumentalness'].values,
    df['liveness'].values,
    df['loudness'].values,
    df['speechiness'].values,
    df['tempo'].values,
    df['valence'].values,
    df['key'].values,

])

    df[['acousticness','danceability','energy',
        'instrumentalness','liveness','loudness','speechiness',
        'tempo','valence', 'key']]=scaled_features.T

    return df

features_df = pd.DataFrame()
features_df = get_features_df(features_df)
features_df = scale_features(features_df)


SPOTIFY_GET_PROFILE_URL = 'https://api.spotify.com/v1/me'

def get_user_profile(auth_header):
    response = requests.get(
        SPOTIFY_GET_PROFILE_URL,
        headers = auth_header
    )
    response.json()
    return response.json()['id']

def get_users_top_tracks(auth_header):
    try:
        try:
            SPOTIFY_GET_TOP_TRACKS_URL = 'https://api.spotify.com/v1/me/top/tracks?time_range=short_term&limit=50'
            response = requests.get(SPOTIFY_GET_TOP_TRACKS_URL, headers = auth_header)
            resp_json = response.json()

        except:
            try:
                SPOTIFY_GET_TOP_TRACKS_URL = 'https://api.spotify.com/v1/me/top/tracks?time_range=medium_term&limit=50'
                response = requests.get(SPOTIFY_GET_TOP_TRACKS_URL, headers = auth_header)
                resp_json = response.json()

            except:
                try:
                    SPOTIFY_GET_TOP_TRACKS_URL = 'https://api.spotify.com/v1/me/top/tracks?time_range=medium_term&limit=20'
                    response = requests.get(SPOTIFY_GET_TOP_TRACKS_URL, headers = auth_header)
                    resp_json = response.json()

                except:
                    try:
                        SPOTIFY_GET_TOP_TRACKS_URL = 'https://api.spotify.com/v1/me/top/tracks?time_range=long_term&limit=20'
                        response = requests.get(SPOTIFY_GET_TOP_TRACKS_URL, headers = auth_header)
                        resp_json = response.json()

                    except:
                        SPOTIFY_GET_TOP_TRACKS_URL = 'https://api.spotify.com/v1/me/top/tracks?time_range=long_term&limit=50'
                        response = requests.get(SPOTIFY_GET_TOP_TRACKS_URL, headers = auth_header)
                        resp_json = response.json()

    except:
        print(response.status_code)
        return "failed"

    else:
        df = pd.DataFrame(columns=[
                "track_id",
                "track_name",
                "artists_name"
            ])

        top_tracks = []

        for tracks in resp_json['items']:
            track_id = tracks['id']
            track_name = tracks['name']
            artists = tracks['artists']
            artists_name = ', '.join(
                [artist['name'] for artist in artists]
            )

            top_tracks_dict = {
                'track_id': track_id,
                'track_name': track_name,
                'artists_name': artists_name
            }

            top_tracks.append(top_tracks_dict)

            df = pd.concat([df, pd.DataFrame([top_tracks_dict], columns = df.columns)],
                                      ignore_index=True)

            df['index'] = range(1, len(df) + 1)

        return df

def generate_track_vector(df, weight_factor):
    features_top_tracks = features_df[features_df['track_id'].isin(df['track_id'].values)]
    features_top_tracks = features_top_tracks.merge(df[['track_id']], on = 'track_id', how = 'inner')

    features_non_top = features_df[~features_df['track_id'].isin(df['track_id'].values)]

    features_tracks_set = features_top_tracks.sort_values('index', ascending=True)

    ranking = features_tracks_set.iloc[0,-1]

    for ix, row in features_tracks_set.iterrows():
        features_tracks_set.loc[ix,'rank'] = int(ranking-row.iloc[-1])

    features_tracks_set['weight'] =features_tracks_set['rank'].apply(lambda x: weight_factor ** (-x))

    features_tracks_set_weighted = features_tracks_set.copy()

    features_tracks_set_weighted.update(features_tracks_set_weighted.iloc[:,:-2].mul(features_tracks_set_weighted.weight.astype(int),0))

    features_tracks_set_weighted_final = features_tracks_set_weighted.iloc[:,:-2].drop(columns = ['track_id', 'index'])

    print(features_tracks_set)

    return features_tracks_set_weighted_final.sum(axis=0), features_non_top

def generate_recommendation(tracks_vector, nontop_tracks_df):
    nontop_tracks = spotify_data[spotify_data['track_id'].isin(nontop_tracks_df['track_id'].values)]
    nontop_tracks['sim'] = cosine_similarity(nontop_tracks_df.drop(['track_id', 'index'],axis=1).values,tracks_vector.values.reshape(1,-1))[:,0]
    nontop_tracks_top15 = nontop_tracks.sort_values('sim',ascending=False).head(15)

    return nontop_tracks_top15

def gen_recs_list(df):
    lst = []
    for i in range(15):
        dict = {
            'track_id': df['track_id'].values[i],
            'name': df['name'].values[i],
            'artists': df['artists'].str[2:-2].values[i]
        }

        lst.append(dict)
    return lst

def get_id_list(lst):
    id_lst = []
    for i in range(15):
        id = lst[i]['track_id']
        id_lst.append(id)
    return id_lst

def gen_uri_dict(lst):
    uri_list = []
    for i in range(15):
        uri = "spotify:track:"+lst[i]['track_id']
        uri_list.append(uri)

    dic = {'uris': uri_list}
    return dic

def create_playlist(auth_header, user_id):
    response = requests.post(
        'https://api.spotify.com/v1/users/'+user_id+'/playlists',
        headers = auth_header,
        json = {
            "name": "Top 15 Recommendations",
            "public": "false"
        }
    )

    return response.json()['id']

def add_tracks_to_playlist(auth_header, playlist_id, dic):
    response = requests.post(
        'https://api.spotify.com/v1/playlists/'+playlist_id+'/tracks',
        headers = auth_header,
        json = dic
    )
    return response.json()

def get_track_url(auth_header, track_id):
    response = requests.get(
        'https://api.spotify.com/v1/tracks/'+track_id,
        headers = auth_header
    )
    return response.json()['preview_url']




