# auth_instagram.py — ejecutar UNA VEZ para autorizar Instagram
# python auth_instagram.py
#
# Requisitos:
# 1. Crear app en https://developers.facebook.com/
# 2. Añadir producto "Instagram"
# 3. Configurar permisos: instagram_basic, instagram_content_publish
# 4. Obtener IG Business/Creator account vinculada a página de Facebook
#
# Este script obtiene un long-lived token (60 días) y lo guarda.

import os
import json
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.environ.get("INSTAGRAM_APP_ID", "")
APP_SECRET = os.environ.get("INSTAGRAM_APP_SECRET", "")
REDIRECT_URI = "http://localhost:8082/callback"
TOKEN_FILE = "credentials/instagram_token.json"

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
    if not APP_ID or not APP_SECRET:
        print("Configura INSTAGRAM_APP_ID e INSTAGRAM_APP_SECRET en .env")
        return

    scopes = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"

    # 1. Abrir navegador
    auth_url = (
        f"https://www.facebook.com/v21.0/dialog/oauth"
        f"?client_id={APP_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={scopes}"
        f"&response_type=code"
    )

    print("Abriendo navegador para autorizar Instagram via Facebook...")
    webbrowser.open(auth_url)

    # 2. Escuchar callback
    server = HTTPServer(("localhost", 8082), CallbackHandler)
    server.handle_request()

    if not auth_code:
        print("Error: no se recibió código de autorización")
        return

    # 3. Obtener short-lived token
    resp = requests.get(
        "https://graph.facebook.com/v21.0/oauth/access_token",
        params={
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": auth_code,
        },
    )
    resp.raise_for_status()
    short_token = resp.json()["access_token"]

    # 4. Intercambiar por long-lived token (60 días)
    resp = requests.get(
        "https://graph.facebook.com/v21.0/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "fb_exchange_token": short_token,
        },
    )
    resp.raise_for_status()
    long_token = resp.json()["access_token"]

    # 5. Obtener Instagram User ID
    # Primero obtener páginas de Facebook
    resp = requests.get(
        "https://graph.facebook.com/v21.0/me/accounts",
        params={"access_token": long_token},
    )
    resp.raise_for_status()
    pages = resp.json()["data"]

    if not pages:
        print("Error: no se encontraron páginas de Facebook vinculadas")
        return

    page = pages[0]  # Usar primera página
    page_token = page["access_token"]

    # Obtener IG user ID desde la página
    resp = requests.get(
        f"https://graph.facebook.com/v21.0/{page['id']}",
        params={"fields": "instagram_business_account", "access_token": page_token},
    )
    resp.raise_for_status()
    ig_data = resp.json()

    ig_user_id = ig_data.get("instagram_business_account", {}).get("id")
    if not ig_user_id:
        print("Error: la página no tiene cuenta de Instagram Business/Creator vinculada")
        return

    # 6. Guardar
    os.makedirs("credentials", exist_ok=True)
    token_data = {
        "access_token": long_token,
        "ig_user_id": ig_user_id,
        "page_id": page["id"],
        "page_name": page["name"],
    }
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

    print(f"Autorizado. Token guardado en {TOKEN_FILE}")
    print(f"Instagram User ID: {ig_user_id}")
    print(f"Página Facebook: {page['name']}")
    print(f"Token expira en ~60 días. Volver a ejecutar para renovar.")


if __name__ == "__main__":
    main()
