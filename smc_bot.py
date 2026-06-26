import time
import requests
from datetime import datetime

TELEGRAM_TOKEN = "8651170126:AAEWaMCIvL0Ur0OUMhBKWgV1uXiPtvSUeqo"
TELEGRAM_CHAT_ID = "6736058409"
SYMBOLS = ["EURUSD", "GBPUSD", "XAUUSD"]
CHECK_EVERY = 300

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

def main():
    send_telegram("SMC Bot запущен!")
    while True:
        print("Сканирую...")
        time.sleep(CHECK_EVERY)

if __name__ == "__main__":
    main()
