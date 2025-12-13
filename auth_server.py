# Name: Dezmond Blair
# Student ID: 7083 2724
# Email: dezb@umich.edu
# List any AI tool (e.g. ChatGPT, GitHub Copilot): Claude assistance with auth logic and access token retrieval

from flask import Flask, request
import requests
from config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

import html


app = Flask(__name__)

@app.route("/") 
def callback():
    code = request.args.get("code")
    token = None
    if code:
        resp = requests.post("https://accounts.stockx.com/oauth/token", json={
            "grant_type": "authorization_code", "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET, "code": code, "redirect_uri": REDIRECT_URI
        })
        try:
            payload = resp.json()
        except ValueError:
            payload = {}
        token = payload.get("access_token")
        # save token to file and print to console for convenience
        if token:
            try:
                with open("access_token.txt", "w", encoding="utf-8") as f:
                    f.write(token)
            except IOError:
                pass
            print("Retrieved access token:", token)

    auth_url = (
        f"https://accounts.stockx.com/authorize?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}&scope=offline_access%20openid&audience=gateway.stockx.com&state=xyz"
    )

    if token:
        # show token and link back
        safe_token = html.escape(token)
        return (
            f"<p>Access token retrieved and saved to <strong>access_token.txt</strong>.</p>"
            f"<p>Paste this value into your <code>config.py</code> as `ACCESS_TOKEN` if desired.</p>"
            f"<pre style='word-break:break-all;background:#f6f8fa;padding:8px;border-radius:4px;'>{safe_token}</pre>"
            f"<p><a href=\"{auth_url}\">Re-run login</a></p>"
        )

    return f'<a href="{auth_url}">Click to Login</a>'

if __name__ == "__main__":
    app.run(port=8080)