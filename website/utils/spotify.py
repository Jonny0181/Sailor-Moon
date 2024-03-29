import time
import base64
import aiohttp
from pymongo import MongoClient

DB_URI = "mongodb+srv://sailormoon:9nlh6clJCkIMgD1v@sailormoon.clmbhrd.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "SailorMoon"
DB_CLIENT = MongoClient(DB_URI)
DB = DB_CLIENT[DB_NAME]

async def get_current_user(user_id, client_id, client_secret):
    token = await get_access_token(user_id, client_id, client_secret)
    if token != "Account not setup.":
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}"
        }
        url = "https://api.spotify.com/v1/me/"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                try:
                    json = await response.json()
                    return json, token
                except:
                    return "Failed"

async def get_access_token(user_id, client_id, client_secret):
    oauth_data = DB.spotifyOauth.find_one({"_id": user_id})
    if oauth_data is None:
        return "Account not setup."

    if (
        oauth_data['oauthData']['access_token']
        and not oauth_data['oauthData']["expires_at"] - int(time.time()) < 60
    ):
        return oauth_data['oauthData']['access_token']
    else:
        auth_header = base64.b64encode((f"{client_id}:{client_secret}").encode("ascii"))
        headers = {
            "Authorization": f"Basic {auth_header.decode('ascii')}",
            "grant_type": "refresh_token",
            "refresh_token": oauth_data['oauthData']['refresh_token'],
        }
        data = {"grant_type": "refresh_token", "refresh_token": oauth_data['oauthData']['refresh_token']}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                 "https://accounts.spotify.com/api/token", data=data, headers=headers
            ) as response:
                json = await response.json()
                oauth_data['oauthData']['access_token'] = json['access_token']
                oauth_data['oauthData']['expires_at'] = int(time.time()) + json["expires_in"]
                DB.spotifyOauth.update_one({"_id": user_id}, {"$set": oauth_data})
                return json['access_token']