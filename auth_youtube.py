# auth_youtube.py — ejecutar UNA VEZ para autorizar
# python auth_youtube.py

from publishers.youtube import _get_service

print("Iniciando autorización YouTube...")
service = _get_service()
channel = service.channels().list(part="snippet", mine=True).execute()
name = channel["items"][0]["snippet"]["title"]
print(f"Autorizado correctamente. Canal: {name}")
