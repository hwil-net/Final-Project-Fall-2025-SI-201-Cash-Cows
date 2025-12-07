# Name: Dezmond Blair
# Student ID: 7083 2724
# Email: dezb@umich.edu
# List any AI tool (e.g. ChatGPT, GitHub Copilot): Claude assistance with auth logic and access token retrieval

from flask import Flask, request
import requests
from config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

app = Flask(__name__)

@app.route("/") 
def callback():
    code = request.args.get("code")
    if code:
        resp = requests.post("https://accounts.stockx.com/oauth/token", json={
            "grant_type": "authorization_code", "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET, "code": code, "redirect_uri": REDIRECT_URI})
        token = resp.json().get("access_token")
    return f'<a href="https://accounts.stockx.com/authorize?response_type=code&client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&scope=offline_access%20openid&audience=gateway.stockx.com&state=xyz">Click to Login</a>'

if __name__ == "__main__":
    app.run(port=5000)