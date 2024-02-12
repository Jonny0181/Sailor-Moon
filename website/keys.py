import os
from dotenv import load_dotenv
from pymongo import MongoClient
from requests_oauthlib import OAuth2Session

load_dotenv()

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_NAME = os.getenv("MONGO_NAME")
DB_CLIENT = MongoClient(MONGO_URI)
DB = DB_CLIENT[MONGO_NAME]
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")
DISCORD_API_URL = 'https://discord.com/api/v10'
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SPOTIFY_BASE_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SCOPE = ["playlist-read-collaborative", "user-read-recently-played", "playlist-read-private", "user-library-read", "user-top-read"]

discord_oauth = OAuth2Session(client_id=DISCORD_CLIENT_ID, redirect_uri=DISCORD_REDIRECT_URI, scope=["identify", "guilds", "guilds.join", "email"])
spotify_oauth = OAuth2Session(client_id=SPOTIFY_CLIENT_ID, redirect_uri=SPOTIFY_REDIRECT_URI, scope=SPOTIFY_SCOPE)