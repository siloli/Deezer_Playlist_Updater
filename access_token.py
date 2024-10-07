import os
import sys
import requests
import dotenv
import deezer
import json
import unicodedata
from typing import Tuple
from http.server import BaseHTTPRequestHandler, HTTPServer

# Load environment variables from the .env file
dotenv.load_dotenv()

# Global variable to store the authorization code
authorization_code = None


class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global authorization_code
        path = self.path
        if "/oauth/return" in path and "code=" in path:
            authorization_code = path.split("code=")[1]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Authorization code received. You can close this window.")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress log output to avoid cluttering the console
        pass


def start_local_server(port=8080) -> str:
    server_address = ('', port)
    httpd = HTTPServer(server_address, OAuthHandler)
    httpd.handle_request()  # Block until the first request is received
    return authorization_code


def connect_to_deezer(name: str) -> Tuple[str, str]:
    access_token = os.getenv(f"API_TOKEN_{name}")
    if not access_token:
        print(f"Error: No API_TOKEN found for {name}. Please provide a valid Deezer access token with 'offline_access'.")
        sys.exit(1)
    
    client = deezer.Client(access_token=access_token)
    try:
        user = client.get_user(user_id='me')
        print(f"Successfully connected to Deezer for {name}!")
        return access_token, user
    except Exception as e:
        print(f"Failed to connect with provided token: {e}")
        sys.exit(1)


def generate_oauth_url() -> str:
    DEEZER_APP_ID = os.getenv('DEEZER_APP_ID')
    DEEZER_SECRET_TOKEN = os.getenv('DEEZER_SECRET_TOKEN')

    if not DEEZER_APP_ID or not DEEZER_SECRET_TOKEN:
        print("Error: Missing Deezer credentials in environment variables.")
        sys.exit(1)

    return (
        f"https://connect.deezer.com/oauth/auth.php?app_id={DEEZER_APP_ID}"
        f"&redirect_uri=http://localhost:8080/oauth/return"
        f"&perms=basic_access,email,manage_library,manage_community,delete_library,"
        f"listening_history,offline_access"
    )


def get_access_token(code: str) -> str:
    DEEZER_APP_ID = os.getenv('DEEZER_APP_ID')
    DEEZER_SECRET_TOKEN = os.getenv('DEEZER_SECRET_TOKEN')

    if not DEEZER_APP_ID or not DEEZER_SECRET_TOKEN:
        print("Error: Missing Deezer credentials in environment variables.")
        sys.exit(1)

    token_url = (
        f"https://connect.deezer.com/oauth/access_token.php?app_id={DEEZER_APP_ID}"
        f"&secret={DEEZER_SECRET_TOKEN}&code={code}&output=json"
    )
    response = requests.get(token_url)
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data.get("access_token")
        if access_token:
            print(f"New Access Token: {access_token}")
            return access_token
        else:
            print("Failed to retrieve access token.")
            sys.exit(1)
    else:
        print(f"Error fetching access token: {response.status_code}")
        sys.exit(1)


def save_access_token(name: str, token: str, yml_file: str = ".github/workflows/main.yml") -> None:
    """
    Adds or updates an environment variable in the .env file and ensures it is correctly referenced
    in the GitHub Actions workflow file (yml). If not, the function adds it under the env block.
    
    :param name: The name of the user, e.g., "GEORGE"
    :param token: The API token associated with this user
    :param yml_file: Path to the GitHub Actions workflow yml file
    """

    # Load the .env file
    dotenv_file = dotenv.find_dotenv()
    dotenv.load_dotenv(dotenv_file)

    # Update the variable in the .env file
    API_Token_name = f"API_TOKEN_{name}"
    Playlist_ID_name = f"PLAYLIST_ID_{name}"
    dotenv.set_key(dotenv_file, API_Token_name, token)
    dotenv.set_key(dotenv_file, Playlist_ID_name, "")  # Initialize the playlist ID to an empty string
    dotenv.load_dotenv(dotenv_file)
    print(f"Environment variable {API_Token_name} updated in the .env file.")

    # Check and update the yml file
    if not os.path.exists(yml_file):
        print(f"Error: The file {yml_file} does not exist.")
        return

    # Read the yml file
    with open(yml_file, "r") as file:
        lines = file.readlines()

    # Prepare the secret strings to add
    token_secret = f"        API_TOKEN_{name}: ${{{{ secrets.API_TOKEN_{name} }}}}\n"
    playlist_secret = f"        PLAYLIST_ID_{name}: ${{{{ secrets.PLAYLIST_ID_{name} }}}}\n"

    # Find the correct 'env' block under 'Run the script to update the playlist'
    found_env = False
    new_lines = []
    for line in lines:
        new_lines.append(line)

        # Find the 'env:' line in the correct job
        if "- name: Run the script to update the playlist" in line:
            found_env = True
        elif found_env and "env:" in line:
            # Insert the new secrets after the existing 'env:' section
            new_lines.append(token_secret)
            new_lines.append(playlist_secret)
            found_env = False  # Reset flag after insertion

    # Write the modified content back to the yml file
    with open(yml_file, "w") as file:
        file.write("".join(new_lines))

    print(f"Secrets for {name} added to the file {yml_file}.")



def update_names_in_env(new_name: str) -> None:
    dotenv_file = dotenv.find_dotenv()
    dotenv.load_dotenv(dotenv_file)

    names_str = os.getenv("NAMES", '[]')
    names_list = json.loads(names_str)

    if new_name not in names_list:
        names_list.append(new_name)

    updated_names_str = json.dumps(names_list)
    dotenv.set_key(dotenv_file, "NAMES", updated_names_str)


def remove_accents(input_str: str) -> str:
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def main():
    name = remove_accents(input("Enter the name of the user: ")).upper()

    access_token = os.getenv(f"API_TOKEN_{name}")

    if access_token:
        print(f"An access token for {name} already exists. Trying to connect...")
        connect_to_deezer(name)
    else:
        print("No access token found. Starting OAuth process...")

        oauth_url = generate_oauth_url()
        print(f"Please go to the following URL to authorize the application:\n{oauth_url}")

        authorization_code = start_local_server()

        access_token = get_access_token(authorization_code)

        save_access_token(name, access_token)

        connect_to_deezer(name)

    update_names_in_env(name)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nProcess interrupted.")
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)
