import os
import re
from dotenv import load_dotenv
from pymongo import MongoClient
from requests_oauthlib import OAuth2Session
from requests.auth import HTTPBasicAuth
from utils.spotify import get_current_user, format_duration
from flask import Flask, render_template, redirect, request, session, jsonify

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# MongoDB configuration
MONGO_URI = os.getenv("MONGO_URI")
MONGO_NAME = os.getenv("MONGO_NAME")
DB_CLIENT = MongoClient(MONGO_URI)
DB = DB_CLIENT[MONGO_NAME]

# Discord OAuth configuration
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_API_URL = "https://discord.com/api"

# Spotify OAuth configuration
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SPOTIFY_BASE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SCOPE = [
    "playlist-read-collaborative",
    "user-read-recently-played",
    "playlist-read-private",
    "user-library-read",
    "user-top-read"
]

# OAuth2Session setup
discord_oauth = OAuth2Session(
    client_id=DISCORD_CLIENT_ID,
    redirect_uri=DISCORD_REDIRECT_URI,
    scope=["identify", "guilds", "guilds.join", "email"]
)

spotify_oauth = OAuth2Session(
    client_id=SPOTIFY_CLIENT_ID,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=SPOTIFY_SCOPE
)

# Flask route for home
# Flask route for home
@app.route('/')
async def home():
    # Retrieve user ID and avatar URL from the session
    user_id = session.get('user_id')
    discord_avatar_url = session.get('discord_avatar_url')

    # Render the template with the user's avatar URL
    return render_template('home.html', logged_in=user_id is not None, discord_avatar_url=discord_avatar_url)

# Flask route for dashboard
@app.route('/dashboard')
async def dashboard():
    # Retrieve user ID and Discord avatar URL from the session
    user_id = int(session.get('user_id'))
    discord_avatar_url = session.get('discord_avatar_url')

    # Check if the user's Spotify account is linked
    spotify_linked = False
    user_username = ""
    user_profile_pic = ""
    profile_link = ""
    spotify_access_token = ""
    user_playlists = ""

    if user_id:
        data = DB.spotifyOauth.find_one({"_id": user_id})
        if data:
            spotify_linked = True
            spotify_info, token = await get_current_user(user_id)
            spotify_access_token = token

            if 'images' in spotify_info and spotify_info['images']:
                user_profile_pic = spotify_info['images'][0]['url']
            else:
                user_profile_pic = "{{ url_for('static', filename='default_profile_picture.png') }}"

            profile_link = spotify_info['external_urls']['spotify']
            user_username = spotify_info['display_name']

    song_stats = 0
    listen_stats = "00:00:00"
    data = DB.music_stats.find_one({"_id": user_id})
    if data:
        song_stats = data['stats']['songsPlayed']
        listen_stats = format_duration(data['stats']['timeListened'])

    liked_songs = 0
    playlists_created = 0

    liked_data = DB.liked.find_one({"_id": user_id})
    if liked_data:
        liked_songs = len(liked_data['songs'])

    user_playlists_data_bool = False
    user_playlists_data = None
    playlists_data = DB.playlists.find_one({"_id": user_id})
    if playlists_data:
        user_playlists_data = playlists_data
        user_playlists_data_bool = True
        playlists_created = len(playlists_data['playlists'])
        user_playlists = playlists_data['playlists']

    collab_playlists = False
    collab_data = list(DB.collaborative_playlists.find({
        "$or": [
            {"creator_id": user_id},
            {"allowed_users": user_id}
        ]
    }))
    if collab_data:
        collab_playlists = True
        user_playlists_data_bool = True
        collab_data = list(collab_data)
        print(collab_data)

    # Render the dashboard template with Spotify account status and Discord avatar
    return render_template('dashboard.html', logged_in=user_id, spotify_linked=spotify_linked, profile_link=profile_link,
                           user_username=user_username, user_profile_pic=user_profile_pic,
                           discord_avatar_url=discord_avatar_url,
                           spotify_logo_url="{{ url_for('static', filename='spotify_logo.png') }}", spotify_access_token=spotify_access_token,
                           song_stats=song_stats, listen_stats=listen_stats, liked_songs=liked_songs,
                           user_playlists_data_bool=user_playlists_data_bool, user_playlists=user_playlists, playlists_created=playlists_created,
                           user_playlists_data=user_playlists_data, collab_playlists=collab_playlists, collab_data=collab_data)


# function to delete a song from the playlist in the database
def delete_song_from_playlist(playlist_name, song_url):
    print(playlist_name, song_url)
    user_id = int(session.get('user_id'))

    # Print user_id for debugging
    print("user_id:", user_id)

    # Retrieve the current playlists data for debugging
    playlists_data_before = DB.playlists.find_one({"_id": user_id})

    # Print playlists_data_before for debugging
    print("Before update:", playlists_data_before)

    # Use $pull to remove the song from the playlist directly in the database
    result = DB.playlists.update_one(
        {"_id": user_id, "playlists.name": {"$regex": f"^{re.escape(playlist_name)}$", "$options": "i"}},
        {"$pull": {"playlists.$.songs": song_url}}
    )

    # Retrieve the updated playlists data for debugging
    playlists_data_after = DB.playlists.find_one({"_id": user_id})

    # Print playlists_data_after for debugging
    print("After update:", playlists_data_after)

    if result.modified_count > 0:
        return {'success': True, 'message': 'Song deleted successfully'}
    else:
        return {'success': False, 'error': 'Song not found in the playlist or playlist not found'}


def delete_song_from_collaborative(playlist_name, song_url):
    user_id = int(session.get('user_id'))

    # Find the collaborative playlist by name
    playlist_data = DB.collaborative_playlists.find_one({"name": playlist_name})

    if playlist_data:
        creator_id = playlist_data.get("creator_id")
        allowed_users = playlist_data.get("allowed_users", [])

        # Check if the user is the creator or an allowed user
        if user_id == creator_id or user_id in allowed_users:
            # Remove song_url from songs
            songs = playlist_data.get("songs", [])
            if song_url in songs:
                songs.remove(song_url)

                # Update the collaborative playlist in the database
                result = DB.collaborative_playlists.update_one(
                    {"name": playlist_name},
                    {"$set": {"songs": songs}}
                )

                if result.modified_count > 0:
                    return {'success': True, 'message': 'Song deleted successfully'}
                else:
                    return {'success': False, 'error': 'Failed to update collaborative playlist'}
            else:
                return {'success': False, 'error': 'Song not found in the playlist'}
        else:
            return {'success': False, 'error': 'Permission denied: You are not the creator or an allowed user'}
    else:
        return {'success': False, 'error': 'Collaborative playlist not found'}

@app.route('/delete-song', methods=['POST'])
def delete_song():
    try:
        data = request.get_json()
        playlist_name = data.get('playlist_name')
        song_url = data.get('song_url')
        is_collaborative = data.get('is_collaborative', False)
        if is_collaborative:
            delete_song_from_collaborative(playlist_name, song_url)
        else:
            delete_song_from_playlist(playlist_name, song_url)

        return jsonify({'success': True, 'message': 'Song deleted successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Flask route for Discord authorization
@app.route('/discord-login')
async def discord_login():
    authorization_url, _ = discord_oauth.authorization_url(f'{DISCORD_API_URL}/oauth2/authorize')
    return redirect(authorization_url)

# Flask route for Discord callback
@app.route('/callback')
async def discord_callback():
    # Fetch the token directly without calling token_url
    token = discord_oauth.fetch_token(
        f'{DISCORD_API_URL}/oauth2/token',
        authorization_response=request.url,
        client_secret=DISCORD_CLIENT_SECRET
    )

    # Use the access token to make a request to the Discord API to get user info
    user_info_response = discord_oauth.get(f'{DISCORD_API_URL}/users/@me')
    user_info = user_info_response.json()

    # Get user ID, name, and avatar URL from the user info
    user_id = user_info.get('id')
    user_name = user_info.get('username')
    avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{user_info.get('avatar')}.png"

    # Store user ID and avatar URL in session for later use
    session['user_id'] = user_id
    session['discord_avatar_url'] = avatar_url

    # Redirect to the home page
    return redirect('/')

# Flask route for Spotify login
@app.route('/spotify-login')
async def spotify_login():
    # Retrieve user ID from the session
    user_id = session.get('user_id')

    # Redirect to Spotify authorization URL
    authorization_url, _ = spotify_oauth.authorization_url(SPOTIFY_BASE_URL)
    return redirect(authorization_url)

# Flask route for Spotify callback
@app.route('/spotify-callback')
async def spotify_callback():
    # Retrieve user ID from the session
    user_id = int(session.get('user_id'))

    auth = HTTPBasicAuth(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    oauthData = spotify_oauth.fetch_token(SPOTIFY_TOKEN_URL, auth=auth, authorization_response=request.url)
    if oauthData['access_token'] is not None:
        data = DB.spotifyOauth.find_one({"_id": user_id})
        if data is None:
            DB.spotifyOauth.insert_one({"_id": user_id, "oauthData": oauthData})

        try:
            # Fetch Spotify user info after connecting
            spotify_info = await get_current_user(user_id)

            # Store necessary information in session for rendering the dashboard
            session['spotify_linked'] = True
            session['profile_link'] = spotify_info['external_urls']['spotify']
            session['user_username'] = spotify_info['display_name']

            if 'images' in spotify_info and spotify_info['images']:
                # Use the first available profile picture
                session['user_profile_pic'] = spotify_info['images'][0]['url']
            else:
                # Use default profile picture
                session['user_profile_pic'] = "{{ url_for('static', filename='default_profile_picture.png') }}"

            # Redirect to the dashboard after successfully connecting Spotify account
            return redirect('/dashboard')
        except Exception as e:
            # Render the error page for failed Spotify account connection
            print(f"Error fetching Spotify user info: {e}")
            return render_template('error.html')
    else:
        # Render the error page for failed Spotify account connection
        return render_template('error.html')

@app.route('/discord-logout')
async def logout():
    session.clear()
    return redirect('/')

# Flask route for handling 404 errors
@app.errorhandler(404)
def page_not_found(error):
    user_id = session.get('user_id')
    discord_avatar_url = session.get('discord_avatar_url')

    return render_template('404.html', logged_in=user_id is not None, discord_avatar_url=discord_avatar_url)

if __name__ == '__main__':
    import os
    from gunicorn.app.base import BaseApplication

    class StandaloneApplication(BaseApplication):
        def __init__(self, app, options=None):
            self.options = options or {}
            self.application = app
            super().__init__()

        def load_config(self):
            config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
            for key, value in config.items():
                self.cfg.set(key.lower(), value)

        def load(self):
            return self.application

    # Set up Gunicorn options
    options = {
        'bind': '0.0.0.0:5000',
        'workers': int(os.environ.get('GUNICORN_WORKERS', '4')),
        'certfile': '/etc/letsencrypt/live/itzjxnny.com/fullchain.pem',
        'keyfile': '/etc/letsencrypt/live/itzjxnny.com/privkey.pem',
        'worker-class': 'gevent',  # Use 'gevent' worker class for better performance
    }

    # Run the application with Gunicorn
    StandaloneApplication(app, options).run()