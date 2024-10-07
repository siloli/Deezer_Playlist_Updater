import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Union, List, Tuple
import deezer
import dotenv
import requests
from tqdm import tqdm


class RateLimiter:
	def __init__(self, max_requests: int, period: int) -> None:
		self.max_requests = max_requests
		self.period = period
		self.requests = []

	def wait(self) -> None:
		while len(self.requests) >= self.max_requests:
			if time.time() - self.requests[0] > self.period:
				self.requests.pop(0)
			else:
				time.sleep(self.period - (time.time() - self.requests[0]))

	def add_request(self) -> None:
		self.wait()
		self.requests.append(time.time())


def connect_to_deezer(access_token:int) -> Tuple[deezer.Client, deezer.User]:
	
	if not access_token:
		print("Error: No ACCESS_TOKEN found. Please provide a valid Deezer access token with 'offline_access'.")
		sys.exit(1)

	client = deezer.Client(access_token)

	try:
		user = client.get_user(user_id='me')
		print("Successfully connected to Deezer!")
	except Exception as e:
		print(f"Failed to connect with provided token: {e}")
		sys.exit(1)
	return client, user


def get_new_releases_from_followed_artists(client: deezer.Client, user: deezer.User, days: int) -> List[int]:
    print("Fetching new releases from followed artists...")
    followed_artists = safe_deezer_request(client, user, "get_artists")
    new_tracks = []
    total_artists = len(followed_artists)  # For progress bar calculation
    today = datetime.today().date()

    with tqdm(total=100, desc="Progress") as pbar:
        for index, artist in enumerate(followed_artists):
            albums = safe_deezer_request(client, artist, "get_albums")

            for album in albums:
                release_date = album.release_date
                if release_date == today or release_date == (today - timedelta(days=1)):
                    tracks = safe_deezer_request(client, album, "get_tracks")
                    for track in tracks:
                        track_released = track.release_date
                        if today - timedelta(days=days) <= track_released <= today:
                            new_tracks.append(track.id)
            
            # Update progress bar
            pbar.update(int((index + 1) / total_artists * 100) - pbar.n)

    return new_tracks


def get_tracks_listened_last_hours(access_token:str, user: deezer.User, days: int = 2) -> List[dict]:
	user_id = user.id
	url = f"https://api.deezer.com/user/{user_id}/history?access_token={access_token}"

	listened_tracks = []
	time_limit = datetime.now() - timedelta(days=days)

	while url:
		response = requests.get(url)
		if response.status_code != 200:
			print(f"History retrieval failed: {response.status_code}")
			break

		history_data = response.json().get('data', [])

		for entry in history_data:
			track_timestamp = datetime.fromtimestamp(entry['timestamp'])
			if track_timestamp >= time_limit:
				listened_tracks.append(entry)
			else:
				return listened_tracks

		url = response.json().get('next')

	return listened_tracks


def find_or_create_playlist(client: deezer.Client, playlist_name: str, user: deezer.User) -> int:
	search_query = f"{playlist_name} {user.name}"
	playlists = client.search_playlists(query=search_query)

	for playlist in playlists:
		if playlist.title.lower() == playlist_name.lower() and playlist.creator.id == user.id:
			return playlist.id

	print(f"Playlist not found for user. Creation of a new playlist.")
	return create_playlist(playlist_name, client)


def create_playlist(playlist_name: str, client: deezer.Client) -> Union[int, None]:
	try:
		deezer_playlist_id: int = safe_deezer_request(client, client, "create_playlist", playlist_name)
		print("Playlist created successfully.")
		return deezer_playlist_id
	except Exception as e:
		print(f"Failed to create playlist: {e}")
		return None


def get_all_tracks_from_playlist(playlist_id: int) -> List[dict]:
	all_tracks = []
	url = f"https://api.deezer.com/playlist/{playlist_id}/tracks"
	while url:
		response = requests.get(url)
		if response.status_code != 200:
			print(f"Error when retrieving titles : {response.status_code}")
			break

		data = response.json()
		all_tracks.extend(data['data'])

		url = data.get('next')

	return all_tracks


def update_daily_playlist(client: deezer.Client, access_token:str, user: deezer.User, playlist_name: str, playlist_id: int, days: int = 2) -> None:
	try:
		if not playlist_id:
			raise ValueError("Invalid playlist ID")

		response = requests.get(f"https://api.deezer.com/playlist/{playlist_id}")
		response.raise_for_status()
		playlist_data = response.json()

		if 'error' in playlist_data and playlist_data['error']['code'] == 800:
			raise ValueError("Invalid playlist ID")
	except (requests.exceptions.HTTPError, ValueError):
		print(f"Invalid playlist ID. Creating a new one")
		playlist_id = find_or_create_playlist(client, playlist_name, user)
		dotenv.set_key(dotenv.find_dotenv(), f"PLAYLIST_ID_{name}", str(playlist_id))  # Convert playlist_id to string
		dotenv.load_dotenv()

	new_tracks = get_new_releases_from_followed_artists(client, user, days)
	listened_tracks = get_tracks_listened_last_hours(access_token, user, days)
	all_playlist_tracks = get_all_tracks_from_playlist(playlist_id)
	playlist_tracks_ids = [track['id'] for track in all_playlist_tracks]

	new_tracks_ids = set(new_tracks) - set(playlist_tracks_ids) - set([track['id'] for track in listened_tracks])
	listened_tracks_in_playlist = list(set([track['id'] for track in listened_tracks]) & set(playlist_tracks_ids))

	if new_tracks_ids:
		safe_deezer_request(client, client.get_playlist(playlist_id), "add_tracks", new_tracks_ids)
		print(f"Added {len(new_tracks_ids)} new tracks to the playlist.")
	else:
		print("No new titles to add to the playlist.")

	if listened_tracks_in_playlist:
		safe_deezer_request(client, client.get_playlist(playlist_id), "delete_tracks", listened_tracks_in_playlist)
		print(f"Removed {len(listened_tracks_in_playlist)} listened tracks from the playlist.")
	else:
		print("No tracks to remove from the playlist.")

def safe_deezer_request(
	client: deezer.Client,
	obj: Union[deezer.Client, deezer.Playlist, deezer.User, Any],
	method: str,
	*args,
	**kwargs,
) -> Union[bool, List[Any], None]:
	try:
		limiter.add_request()
		return getattr(obj, method)(*args, **kwargs)
	except deezer.exceptions.DeezerForbiddenError:
		print("Forbidden access, retrying...")
		time.sleep(5)
	except deezer.exceptions.DeezerErrorResponse as deezer_error:
		error = deezer_error.args[0]["error"]
		print(f"Deezer error: {error}")
		if "code" in error and error["code"] == 500 and "This song already exists in this playlist" in error["message"]:
			print("Some tracks already exist in the playlist, skipping those.")
			return False
		print(f"An error occurred: {error}")
		return None
	except Exception as e:
		print(f"Unexpected error: {e}")
		raise e


def main(access_token:str,playlist_id:int) -> None:
	
	client, user = connect_to_deezer(access_token)
	print("Updating playlist...")
	update_daily_playlist(client, access_token, user, "Deezer News 🎶", playlist_id, days=2)
	


if __name__ == "__main__":
    try:
        limiter = RateLimiter(max_requests=50, period=5)
        dotenv.load_dotenv()
        names = os.getenv("NAMES")
        names = names[1:-1].split(", ") # split the string into a list
        names = [name[1:-1] for name in names] # remove the quotes
        for name in names:
            access_token = os.getenv(f"ACCESS_TOKEN_{name}")
            playlist_id = os.getenv(f"PLAYLIST_ID_{name}")
            main(access_token,playlist_id)
        print("Finished !")
    except KeyboardInterrupt:
        print("Interrupted by user.")