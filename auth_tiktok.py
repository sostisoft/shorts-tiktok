# auth_tiktok.py — ejecutar UNA VEZ para autorizar TikTok
# python auth_tiktok.py
#
# Requisitos:
# 1. Crear app en https://developers.tiktok.com/
# 2. Activar "Content Posting API"
# 3. Configurar TIKTOK_CLIENT_KEY y TIKTOK_CLIENT_SECRET en .env

import os
import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_KEY = os.environ["TIKTOK_CLIENT_KEY"]
CLIENT_SECRET = os.environ["TIKTOK_CLIENT_SECRET"]
REDIRECT_URI = "http://localhost:8081/callback"
SCOPES = "user.info.basic,video.publish,video.upload"
TOKEN_FILE = "credentials/tiktok_token.json"

auth_code = None


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        query = parse_qs(urlparse(self.path).query)
        auth_code = query.get("code", [None])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Autorizado. Puedes cerrar esta ventana.")

    def log_message(self, format, *args):
        pass


def main():
    # 1. Abrir navegador para autorizar
    auth_url = (
        f"https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={CLIENT_KEY}"
        f"&scope={SCOPES}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
    )

    print("Abriendo navegador para autorizar TikTok...")
    webbrowser.open(auth_url)

    # 2. Escuchar callback
    server = HTTPServer(("localhost", 8081), CallbackHandler)
    server.handle_request()

    if not auth_code:
        print("Error: no se recibió código de autorización")
        return

    # 3. Intercambiar código por token
    resp = requests.post(
        "https://open.tiktokapis.com/v2/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": CLIENT_KEY,
            "client_secret": CLIENT_SECRET,
            "code": auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
    )
    resp.raise_for_status()
    token_data = resp.json()

    # 4. Guardar token
    os.makedirs("credentials", exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"Autorizado. Token guardado en {TOKEN_FILE}")
    print(f"Open ID: {token_data.get('open_id')}")
    print(f"Expira en: {token_data.get('expires_in')} segundos")


if __name__ == "__main__":
    main()
