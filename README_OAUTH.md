# Gmail OAuth Setup

To use the "Sign in with Gmail" feature, you need a `credentials.json` file.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one).
3. Enable the **Gmail API**.
4. Go to **APIs & Services > Credentials**.
5. Click **Create Credentials** -> **OAuth client ID**.
6. Select **Desktop app**.
7. Download the JSON file and rename it to `credentials.json`.
8. Place `credentials.json` in this folder (next to the app executable).

## Note for Testing
If you are the developer, ensure your email is added to the "Test Users" list in the OAuth Consent Screen configuration if the app is not published.
