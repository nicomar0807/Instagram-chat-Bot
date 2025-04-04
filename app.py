import os
import json
from flask import Flask, request
import requests
import gspread
from google.oauth2.service_account import Credentials
import random
from google.cloud import vision

app = Flask(__name__)

# 👉 Crear archivo de credenciales desde variable de entorno en Render
cred_string = os.getenv("CREDENTIALS_JSON")
if cred_string is None:
    raise Exception("❌ Variable de entorno CREDENTIALS_JSON no encontrada.")

try:
    credenciales_dict = json.loads(cred_string)
except json.JSONDecodeError:
    raise Exception("❌ Error al parsear CREDENTIALS_JSON. Asegúrate de que esté bien formateado.")

# Guardar el archivo (opcional si lo necesitas para otras librerías que lo requieren en disco)
with open("credenciales.json", "w") as f:
    json.dump(credenciales_dict, f)

# 👉 Usar credenciales desde el diccionario
try:
    creds = Credentials.from_service_account_info(
        credenciales_dict,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    vision_client = vision.ImageAnnotatorClient.from_service_account_info(credenciales_dict)
except Exception as e:
    raise Exception(f"❌ Error al cargar las credenciales: {str(e)}")

# Inicializar cliente de Google Sheets
client = gspread.authorize(creds)
sheet = client.open_by_key("1_ZSk0z7Lp81rT-bBz4fmSJj0eyGjVWvrUZm432QzgoM").sheet1

# Configuración de Messenger
VERIFY_TOKEN = "mi_token_secreto"
ACCESS_TOKEN = "EAAItRKRWhG4BO45HxR38ZAxlhuLd7HEPUY1CW16Vc1nR9ES8cKm3l1eJRtMAtk6rlxHmzZAuE1QLJZCyFkY7GkmOGaGXDwC3jRsZBOnq6NzcdxxsE21waMbBH8S4B01mjts8FHhCXlEXbfl2tYNiZCtQfUIE0PzuVma5ruSs26CBERQMN3wVw7DSW2w6bEXB2JT0uTene98zHeZBWPhf6Ngx9vvOcZD"
usuarios = {}
retos = [
    "Tómate una foto con un anciano de tu iglesia.",
    "Tómate una foto con un niño pequeño.",
    "Tómate una foto con un amigo nuevo.",
    "Tómate una foto con el pastor.",
    "Tómate una foto con alguien de otra ciudad.",
    "Tómate una foto con un grupo de al menos 5 personas.",
    "Tómate una foto en la entrada de la iglesia.",
]

def registrar_participante(nombre, iglesia, sender_id):
    sheet.append_row([nombre, iglesia, sender_id])
    send_message(sender_id, "🎉 ¡Te has registrado exitosamente! Pronto recibirás tu primer reto.")

def send_message(recipient_id, message_text):
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    headers = {"Content-Type": "application/json"}
    requests.post(
        f"https://graph.facebook.com/v17.0/me/messages?access_token={ACCESS_TOKEN}",
        headers=headers,
        json=payload
    )

def handle_message(sender_id, text):
    if "mi nombre es" in text.lower():
        nombre = text.split("mi nombre es")[-1].strip()
        usuarios[sender_id] = {"nombre": nombre}
        send_message(sender_id, "Gracias. ¿A qué iglesia perteneces?")
    elif "mi iglesia es" in text.lower():
        if sender_id in usuarios and "nombre" in usuarios[sender_id]:
            iglesia = text.split("mi iglesia es")[-1].strip()
            usuarios[sender_id]["iglesia"] = iglesia
            registrar_participante(usuarios[sender_id]["nombre"], iglesia, sender_id)
        else:
            send_message(sender_id, "Primero dime tu nombre.")
    else:
        send_message(sender_id, "No entendí tu mensaje. Intenta de nuevo.")

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if token == VERIFY_TOKEN:
            return challenge, 200
        return "Token inválido", 403

    elif request.method == "POST":
        data = request.get_json()
        print("📩 Mensaje recibido:", json.dumps(data, indent=2))

        if data.get("entry"):
            for entry in data["entry"]:
                # ✅ Messenger clásico
                for messaging_event in entry.get("messaging", []):
                    sender_id = messaging_event["sender"]["id"]
                    if "message" in messaging_event:
                        text = messaging_event["message"].get("text")
                        if text:
                            handle_message(sender_id, text)

                # ✅ Instagram / WhatsApp moderno
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    if change.get("field") == "messages":
                        messages = value.get("messages", [])
                        for msg in messages:
                            sender_id = msg.get("from")
                            text = msg.get("text", {}).get("body")
                            if sender_id and text:
                                handle_message(sender_id, text)

        return "EVENT_RECEIVED", 200

if __name__ == "__main__":
    app.run(port=5000, debug=True)
