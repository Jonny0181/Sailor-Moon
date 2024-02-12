import requests

def get_user_info(user_id, DISCORD_BOT_TOKEN, DISCORD_API_URL):
    headers = {
        'Authorization': f'Bot {DISCORD_BOT_TOKEN}',
        'Content-Type': 'application/json',
    }
    
    user_info_response = requests.get(f'{DISCORD_API_URL}/users/{user_id}', headers=headers)

    try:
        user_info_response.raise_for_status()
        user_info = user_info_response.json()
        if 'id' in user_info:
            return {'success': True, 'user_info': user_info}
        else:
            return {'success': False, 'error': 'User information not found.'}
    except requests.HTTPError as e:
        return {'success': False, 'error': f'HTTP error: {e}', 'status_code': user_info_response.status_code}
    except Exception as e:
        return {'success': False, 'error': f'Unexpected error: {e}'}
    
def format_duration(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"