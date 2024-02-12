import os
import traceback
from keys import *
from requests.auth import HTTPBasicAuth
from utils.misc import get_user_info
from utils.spotify import get_current_user
from flask import Flask, render_template, redirect, request, session, jsonify, url_for
from utils.database import ( delete_song_from_collaborative, delete_song_from_playlist, get_spotify_info,
                            get_user_statistics, get_user_playlists, get_collaborative_playlists, get_liked_songs )

app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

@app.route('/')
async def home():
    user_id = session.get('user_id')
    discord_avatar_url = session.get('discord_avatar_url')
    return render_template('home.html', logged_in=user_id is not None, discord_avatar_url=discord_avatar_url)


@app.route('/dashboard')
async def dashboard():
    user_id = int(session.get('user_id'))
    discord_avatar_url = session.get('discord_avatar_url')

    spotify_linked = False
    user_username = ""
    user_profile_pic = ""
    profile_link = ""
    spotify_access_token = ""
    user_playlists = ""

    if user_id:
        spotify_access_token, user_profile_pic, profile_link, user_username = await get_spotify_info(user_id)
        if spotify_access_token:
            spotify_linked = True

    song_stats, listen_stats = get_user_statistics(user_id)
    liked_songs = get_liked_songs(user_id)
    user_playlists_data_bool, user_playlists, playlists_created, user_playlists_data = get_user_playlists(user_id)
    collab_playlists, collab_data = get_collaborative_playlists(user_id)

    return render_template('dashboard.html', DISCORD_BOT_TOKEN=DISCORD_BOT_TOKEN, logged_in=str(user_id), spotify_linked=spotify_linked, profile_link=profile_link,
                           user_username=user_username, user_profile_pic=user_profile_pic,
                           discord_avatar_url=discord_avatar_url,
                           spotify_logo_url="{{ url_for('static', filename='spotify_logo.png') }}", spotify_access_token=spotify_access_token,
                           song_stats=song_stats, listen_stats=listen_stats, liked_songs=liked_songs,
                           user_playlists_data_bool=user_playlists_data_bool, user_playlists=user_playlists, playlists_created=playlists_created,
                           user_playlists_data=user_playlists_data, collab_playlists=collab_playlists, collab_data=collab_data)

@app.route('/delete-song', methods=['POST'])
async def delete_song():
    try:
        user_id = int(session.get('user_id'))
        data = request.get_json()
        playlist_name = data.get('playlist_name')
        song_url = data.get('song_url')
        is_collaborative = data.get('is_collaborative', False)
        if is_collaborative:
            delete_song_from_collaborative(playlist_name, song_url)
        else:
            delete_song_from_playlist(playlist_name, song_url)

        user_playlists = None
        playlists_data = DB.playlists.find_one({"_id": user_id})
        if playlists_data:
            user_playlists = playlists_data['playlists']

        collab_data = DB.collaborative_playlists.find({
            "$or": [
                {"creator_id": user_id},
                {"allowed_users": user_id}
            ]
        })
        if collab_data:
            collab_data = list(collab_data)
            for doc in collab_data:
                doc['creator_id'] = str(doc['creator_id'])
                doc['allowed_users'] = [str(user_id) for user_id in doc['allowed_users']]

        return jsonify({
            'user_playlists': user_playlists,
            'collab_data': collab_data,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    

@app.route('/remove-user', methods=['POST'])
async def remove_user():
    try:
        data = request.get_json()
        playlist = data.get('playlist')
        userToRemove = int(data.get('userId'))
        user_id = int(session.get('user_id'))

        collab_playlist = DB.collaborative_playlists.find_one({'_id': playlist, 'name': str(playlist).split("_")[0], 'creator_id': int(str(playlist).split("_")[1])})
        if collab_playlist:
            if userToRemove in collab_playlist['allowed_users']:
                DB.collaborative_playlists.update_one(
                    {'_id': playlist, 'name': str(playlist).split("_")[0], 'creator_id': int(str(playlist).split("_")[1])},
                    {'$pull': {'allowed_users': userToRemove}}
                )

                user_playlists = None
                playlists_data = DB.playlists.find_one({"_id": user_id})
                if playlists_data:
                    user_playlists = playlists_data['playlists']

                collab_data = DB.collaborative_playlists.find({
                    "$or": [
                        {"creator_id": user_id},
                        {"allowed_users": user_id}
                    ]
                })
                if collab_data:
                    collab_data = list(collab_data)
                    for doc in collab_data:
                        doc['creator_id'] = str(doc['creator_id'])
                        doc['allowed_users'] = [str(user_id) for user_id in doc['allowed_users']]

                return jsonify({'success': True, 'error': 'User removed from allowed list.', 'user_playlists': user_playlists, 'collab_data': collab_data})
            else:
                return jsonify({'success': False, 'error': 'Playlist not found or user info not available.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/add-user', methods=['POST'])
async def add_user():
    try:
        data = request.get_json()
        user_id = int(session.get('user_id'))
        new_user_id = int(data.get('userID'))
        playlist_id = data.get('currentPlaylist')
        playlist_name, creator_id = playlist_id.split('_')
        creator_id = int(creator_id)
        user_id = int(session.get('user_id'))

        playlist = DB.collaborative_playlists.find_one({'_id': playlist_id, 'name': playlist_name, 'creator_id': creator_id})

        if playlist:
            if new_user_id in playlist['allowed_users']:
                return jsonify({'success': True, 'error': 'User already in allowed list.'})

            DB.collaborative_playlists.update_one(
                {'_id': playlist_id, 'name': playlist_name, 'creator_id': creator_id},
                {'$push': {'allowed_users': new_user_id}}
            )

            user_playlists = None
            playlists_data = DB.playlists.find_one({"_id": user_id})
            if playlists_data:
                user_playlists = playlists_data['playlists']

            collab_data = DB.collaborative_playlists.find({
                "$or": [
                    {"creator_id": user_id},
                    {"allowed_users": user_id}
                ]
            })
            if collab_data:
                collab_data = list(collab_data)
                for doc in collab_data:
                    doc['creator_id'] = str(doc['creator_id'])
                    doc['allowed_users'] = [str(user_id) for user_id in doc['allowed_users']]
                    
            return jsonify({'success': True, 'error': 'User added to allowed list.', 'user_playlists': user_playlists, 'collab_data': collab_data,})
        else:
            return jsonify({'success': False, 'error': 'Playlist not found or user info not available.'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/get-user-info', methods=['POST'])
async def get_user_info_route():
    try:
        data = request.json
        user_id = str(data.get('user_id')) 
        user_info = get_user_info(user_id, DISCORD_BOT_TOKEN, DISCORD_API_URL)
        return jsonify(user_info)
    except Exception as e:
        print(f'Error in get_user_info: {str(e)}')
        return jsonify({'success': False, 'message': f'Unexpected error: {str(e)}'})

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

@app.route('/spotify-login')
async def spotify_login():
    authorization_url, _ = spotify_oauth.authorization_url(SPOTIFY_BASE_URL)
    return redirect(authorization_url)

@app.route('/spotify-disconnect', methods=['POST'])
async def spotify_disconnect():
    user_id = int(session.get('user_id'))
    try:
        DB.spotifyOauth.find_one_and_delete({"_id": user_id})
        return {'success': True, 'message': f'Account disconnected.'}
    except Exception as e:
        return {'success': False, 'message': f'Unexpected error: {e}'}

# Flask route for Spotify callback
@app.route('/spotify-callback')
async def spotify_callback():
    user_id = int(session.get('user_id'))

    auth = HTTPBasicAuth(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    oauthData = spotify_oauth.fetch_token(SPOTIFY_TOKEN_URL, auth=auth, authorization_response=request.url)
    if oauthData['access_token'] is not None:
        data = DB.spotifyOauth.find_one({"_id": user_id})
        if data is None:
            DB.spotifyOauth.insert_one({"_id": user_id, "oauthData": oauthData})

        try:
            spotify_info = await get_current_user(user_id, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
            spotify_info = spotify_info[0]
            session['spotify_linked'] = True
            session['profile_link'] = spotify_info['external_urls']['spotify']
            session['user_username'] = spotify_info.get('display_name', 'Unknown')

            if 'images' in spotify_info and spotify_info['images']:
                session['user_profile_pic'] = spotify_info['images'][0].get('url', url_for('static', filename='default_profile_picture.png'))  # Handling if URL is not available
            else:
                session['user_profile_pic'] = url_for('static', filename='default_profile_picture.png')
            return redirect('/dashboard')
        except Exception:
            traceback.print_exc()
            return render_template('error.html')
    else:
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