import requests
from config import TELEGRAM_API_KEY, TELEGRAM_CHAT_ID

"""A module to report messages to a telegram channel."""

url = "https://api.telegram.org/bot" + TELEGRAM_API_KEY

def send_message(msg: str) -> None:
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg}
    requests.post(url + "/sendMessage", json=payload)
