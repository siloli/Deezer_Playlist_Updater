
# Deezer_Playlist_Updater 🎶

This project uses the [Deezer API](https://developers.deezer.com/api) to fetch new releases from followed artists and automatically updates a daily playlist. The script is set up to run with GitHub Actions, either on a scheduled basis or manually.

## Features

- **Followed Artists**: Fetches new releases from followed artists on Deezer.
- **Automatic Updates**: Adds new tracks to a personalized playlist and removes tracks that have already been listened to.
- **Automated Execution**: Utilizes GitHub Actions to execute the script daily.

## Requirements

1. **Deezer API Access**: You will need to create an application via the official [Deezer developers page](https://developers.deezer.com/myapps).
2. **Python**: Make sure you have Python 3.x installed on your machine.
3. **User Access Token**: You will need a Deezer access token with the `offline_access` permission for unlimited access (run `access_token.py` to generate this token).
4. **Dependencies**: The project uses several Python libraries, which can be installed via the `requirements.txt` file.

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/your-user/fresh-tracks-deezer.git
    cd fresh-tracks-deezer
    ```

2. Create and activate a virtual environment:
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3. Install the dependencies:
    ```bash
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    ```

4. Create a `.env` file at the root of the project and add your API credentials:
    ```bash
    DEEZER_APP_ID=your_app_id
    DEEZER_SECRET_TOKEN=your_secret_token
    API_TOKEN=your_deezer_access_token
    PLAYLIST_ID=your_playlist_id
    ```

## Running Locally

Once the environment is configured, you can manually run the script to update your playlist with the following command:

```bash
python main.py
```

## Forking and Using Your Own Private Repository

This public repository is designed to allow users to **fork** it and create their own private version to securely store their secrets.

### Steps for Forking

1. **Fork this repository**: Use the GitHub fork option to create your own version of this repository.
2. **Create a private repository**: After forking, set your fork to private to keep your secrets secure.
3. **Set up your secrets**: In your private repository, go to **Settings > Secrets and variables > Actions**, and add your own secrets for Deezer access.
    - Add secrets for:
        - `API_TOKEN_YOURNAME`
        - `PLAYLIST_ID_YOURNAME`
        - `NAMES`: The list of user names.

### Updating the GitHub Actions Workflow

After adding your secrets, make sure the workflow YAML file (in `.github/workflows/main.yml`) references your own secrets:

```yaml
    - name: Run the script to update the playlist
      run: |
        python main.py
      env:
        API_TOKEN_YOURNAME: ${{ secrets.API_TOKEN_YOURNAME }}
        PLAYLIST_ID_YOURNAME: ${{ secrets.PLAYLIST_ID_YOURNAME }}
        NAMES: ${{ secrets.NAMES }}
```

## Automating with GitHub Actions

This project is configured to run automatically using GitHub Actions. To make it work with your private repository, ensure that you've added your secrets as described above.

- GitHub Actions is set to run every day at 8 AM UTC. You can also trigger it manually via the GitHub Actions tab.

## Customization

Feel free to customize the Python scripts and workflows according to your needs. If you're managing multiple users, you can add their API tokens and playlist IDs as secrets and update the script to handle multiple people.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.
