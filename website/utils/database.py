import os
import re
from pymongo import MongoClient
from flask import session
from keys import *
from .spotify import get_current_user
from .misc import format_duration
from flask import session, url_for

MONGO_URI = os.getenv("MONGO_URI")
MONGO_NAME = os.getenv("MONGO_NAME")
DB_CLIENT = MongoClient(MONGO_URI)
DB = DB_CLIENT[MONGO_NAME]

def delete_song_from_playlist(playlist_name, song_url):
    user_id = int(session.get('user_id'))
    result = DB.playlists.update_one(
        {"_id": user_id, "playlists.name": {"$regex": f"^{re.escape(playlist_name)}$", "$options": "i"}},
        {"$pull": {"playlists.$.songs": song_url}}
    )
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
    
async def get_spotify_info(user_id):
    data = DB.spotifyOauth.find_one({"_id": user_id})
    if data:
        spotify_info, token = await get_current_user(user_id, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
        spotify_access_token = token
        user_profile_pic = spotify_info.get('images', [{'url': url_for('static', filename='default_profile_picture.png')}])[0]['url']
        profile_link = spotify_info['external_urls']['spotify']
        user_username = spotify_info['display_name']
        return spotify_access_token, user_profile_pic, profile_link, user_username
    return "", "{{ url_for('static', filename='default_profile_picture.png') }}", "", ""

def get_user_statistics(user_id):
    data = DB.music_stats.find_one({"_id": user_id})
    if data:
        song_stats = data['stats']['songsPlayed']
        listen_stats = format_duration(data['stats']['timeListened'])
        return song_stats, listen_stats
    return 0, "00:00:00"

def get_user_playlists(user_id):
    playlists_data = DB.playlists.find_one({"_id": user_id})
    user_playlists_data_bool = False
    user_playlists_data = None
    playlists_created = 0
    if playlists_data:
        user_playlists_data = playlists_data
        user_playlists_data_bool = True
        playlists_created = len(playlists_data['playlists'])
        user_playlists = playlists_data['playlists']
    return user_playlists_data_bool, user_playlists, playlists_created, user_playlists_data

def get_collaborative_playlists(user_id):
    collab_playlists = False
    collab_data = DB.collaborative_playlists.find({
        "$or": [
            {"creator_id": user_id},
            {"allowed_users": user_id}
        ]
    })
    if collab_data:
        collab_playlists = True
        user_playlists_data_bool = True
        collab_data = list(collab_data)
        for doc in collab_data:
            doc['creator_id'] = str(doc['creator_id'])
            doc['allowed_users'] = [str(user_id) for user_id in doc['allowed_users']]
    return collab_playlists, collab_data

def get_liked_songs(user_id):
    liked_songs = 0
    liked_data = DB.liked.find_one({"_id": user_id})
    if liked_data:
        liked_songs = len(liked_data['songs'])
    return liked_songs