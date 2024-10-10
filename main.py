import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Union, List, Tuple
import deezer
import deezer.client
import deezer.pagination
import deezer.resources
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


def connect_to_deezer(access_token: str | None) -> Tuple[deezer.Client, deezer.User]:

    if not access_token:
        print("Error: No ACCESS_TOKEN found. Please provide a valid Deezer access token with 'offline_access'.")
        sys.exit(1)

    client: deezer.Client = deezer.Client(access_token)
    try:
        user: deezer.User = safe_deezer_request(
            client, "get_user", user_id='me')
        print("Successfully connected to Deezer!")
    except Exception as e:
        print(f"Failed to connect with provided token: {e}")
        sys.exit(1)
    return client, user


def get_new_releases_from_followed_artists(user: deezer.User, days: int) -> List[int]:
    print("Fetching new releases from followed artists...")
    followed_artists: deezer.pagination.PaginatedList | deezer.Artist | None = safe_deezer_request(
        user, "get_artists")
    if not followed_artists:
        return []

    new_tracks = []
    total_artists = len(followed_artists)
    today = datetime.today().date()
    progress_step = max(1, total_artists // 100)
    with tqdm(total=100, desc="Progress") as pbar:
        for index, artist in enumerate(followed_artists):
            # on détermine le type de variable que contient la variable artist.

            albums: deezer.pagination.PaginatedList | deezer.Album | None = safe_deezer_request(
                artist, "get_albums")
            if albums is None or albums == deezer.Album:
                continue

            for album in albums:
                release_date = album.release_date
                if release_date == today or release_date == (today - timedelta(days=1)):
                    tracks: deezer.pagination.PaginatedList | deezer.Track | None = safe_deezer_request(
                        album, "get_tracks")
                    if tracks is None or tracks == deezer.Track:
                        continue

                    for track in tracks:
                        track_released = track.release_date
                        if today - timedelta(days=days) <= track_released <= today:
                            new_tracks.append(track.id)

            if (index + 1) % progress_step == 0:
                pbar.update(1)

    return new_tracks


def get_tracks_listened_last_hours(access_token: str, user: deezer.User, days: int = 2) -> List[int]:
    user_id = user.id
    url = f"https://api.deezer.com/user/{user_id}/history?access_token={access_token}"

    listened_tracks = []
    time_limit = datetime.now() - timedelta(days=days)

    while url:
        limiter.add_request()
        response = requests.get(url)
        if response.status_code != 200:
            print(f"History retrieval failed: {response.status_code}")
            break

        history_data: list[dict] = response.json().get('data', [])
        for entry in history_data:
            track_timestamp = datetime.fromtimestamp(entry['timestamp'])
            if track_timestamp >= time_limit:
                listened_tracks.append(entry['id'])
                listened_tracks: list[int]
            else:
                return listened_tracks

        url = str(response.json().get('next'))

    return listened_tracks


def find_or_create_playlist(playlist_name: str, user: deezer.User) -> str:
    search_query = f"{playlist_name} {user.name}"
    playlists: deezer.pagination.PaginatedList | deezer.Playlist | None = safe_deezer_request(
        user, "search_playlists", query=search_query)
    if not playlists:
        print(f"Playlist not found for user. Creation of a new playlist.")
        return create_playlist(playlist_name)
    playlists: deezer.Playlist | deezer.pagination.PaginatedList
    for playlist in playlists:
        playlist: deezer.Playlist
        if playlist.title.lower() == playlist_name.lower() and playlist.creator.id == user.id:
            return str(playlist.id)


def create_playlist(playlist_name: str) -> str:
    try:
        playlist_id = str(safe_deezer_request(
            "create_playlist", playlist_name))
        print("Playlist created successfully.")
        return playlist_id
    except Exception as e:
        print(f"Failed to create playlist: {e}")
        sys.exit(1)


def get_all_tracks_from_playlist(playlist_id: str) -> list[int]:
    all_tracks = []
    url = f"https://api.deezer.com/playlist/{playlist_id}/tracks"
    while url:
        limiter.add_request()
        response = requests.get(url)
        if response.status_code != 200:
            print(f"Error when retrieving titles : {response.status_code}")
            break

        data: dict = response.json()
        for track in data['data']:
            all_tracks.append(track['id'])
        url: str = data.get('next')
    all_tracks: list[int]
    return all_tracks


def update_daily_playlist(client: deezer.Client, access_token: str, user: deezer.User, playlist_name: str, playlist_id: str | None, days: int = 2) -> None:
    try:
        if not playlist_id:
            raise ValueError("You did not provide a playlist ID at all.")
        playlist_id: str
        limiter.add_request()
        response = requests.get(
            f"https://api.deezer.com/playlist/{playlist_id}")
        response.raise_for_status()
        playlist_data = response.json()

        if 'error' in playlist_data and playlist_data['error']['code'] == 800:
            print("Invalid Playlist ID. Deleted?")
            raise ValueError("Invalid playlist ID")
    except (requests.exceptions.HTTPError, ValueError):
        print("Creating a new one.")
        playlist_id = find_or_create_playlist(playlist_name, user)
        dotenv.set_key(dotenv.find_dotenv(), f"PLAYLIST_ID_{name}",
                       playlist_id)
        dotenv.load_dotenv()

    new_tracks = get_new_releases_from_followed_artists(user, days)
    listened_tracks = get_tracks_listened_last_hours(access_token, user, days)
    playlist_tracks_ids = get_all_tracks_from_playlist(playlist_id)
    new_tracks_ids = list(
        set(new_tracks) - set(playlist_tracks_ids) - set(listened_tracks))
    listened_tracks_in_playlist = list(
        set(listened_tracks) & set(playlist_tracks_ids))

    if new_tracks_ids:

        safe_deezer_request(safe_deezer_request(
            client, "get_playlist", playlist_id), "add_tracks", new_tracks_ids)
        print(f"Added {len(new_tracks_ids)} new tracks to the playlist.")
    else:
        print("No new titles to add to the playlist.")

    if listened_tracks_in_playlist:
        safe_deezer_request(safe_deezer_request(
            client, "get_playlist", playlist_id), "delete_tracks", listened_tracks_in_playlist)
        print(
            f"Removed {len(listened_tracks_in_playlist)} listened tracks from the playlist.")
    else:
        print("No tracks to remove from the playlist.")


def safe_deezer_request(
    obj: Union[deezer.Client, deezer.Playlist, deezer.User, deezer.Artist, deezer.Album, deezer.Track],
    method: str,
    *args,
    **kwargs,
) -> Union[bool, deezer.pagination.PaginatedList, deezer.Playlist, deezer.User, deezer.Artist, deezer.Album, deezer.Track, None]:
    max_retries = 5
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"Attempt {attempt + 1}/{max_retries}")
        try:
            limiter.add_request()
            return getattr(obj, method)(*args, **kwargs)
        except deezer.exceptions.DeezerForbiddenError:
            print(f"Error: Forbidden. Please check your Rate Limit.")
            time.sleep(5)
            continue
        except deezer.exceptions.DeezerRetryableHTTPError:
            print("Temporary issue, retrying...")
            time.sleep(5)
        except deezer.exceptions.DeezerNotFoundError:
            print("Resource not found.")
            return None
        except deezer.exceptions.DeezerErrorResponse as deezer_error:
            error = deezer_error.json_data["error"]
            print(f"Deezer error: {error}")
            if "code" in error and error["code"] == 500 and "This song already exists in this playlist" in error["message"]:
                print("Some tracks already exist in the playlist, skipping those.")
                return None
            print(f"An error occurred: {error}")
            return None
        except deezer.exceptions.DeezerHTTPError as http_error:
            print('Here was the error, 5')
            print(f"HTTP error: {http_error}")
            return None
        except Exception as e:
            print('Here was the error, 6')
            print(f"Unexpected error: {e}")
            raise e
    print("Max retries reached. Request failed.")
    return None


def main(access_token: str | None, playlist_id: str | None) -> None:

    client, user = connect_to_deezer(access_token)
    access_token: str = access_token
    print("Updating playlist...")
    update_daily_playlist(client, access_token, user,
                          "Deezer News 🎶", playlist_id, days=2)


if __name__ == "__main__":
    try:
        # 45 requests every 5 seconds, 50 max requests per 5 seconds
        limiter = RateLimiter(max_requests=50, period=5)
        dotenv.load_dotenv()
        names: str | None = os.getenv("NAMES")
        if not names:
            print(
                "Error: No NAMES found. Please provide a list of names separated by commas.")
            sys.exit(1)
        names = names[1:-1].split(", ")  # split the string into a list
        names = [name[1:-1] for name in names]  # remove the quotes
        for name in names:
            access_token: str | None = os.getenv(f"ACCESS_TOKEN_{name}")
            playlist_id: str | None = os.getenv(f"PLAYLIST_ID_{name}")
            main(access_token, playlist_id)
        print("Finished !")
    except KeyboardInterrupt:
        print("Interrupted by user.")
