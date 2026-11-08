import os
import sys
import threading
import time
import requests
import telebot

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
if not BOT_TOKEN or not CHAT_ID:
    sys.exit("Задайте переменные окружения BOT_TOKEN и CHAT_ID")

URL = "https://pro-api.coinmarketcap.com/public-api/v3/fear-and-greed/latest"
DB_FILE = os.path.join(os.environ.get("STATE_DIR", "."), "last_value.txt")

bot = telebot.TeleBot(BOT_TOKEN)
_cache = {"t": 0, "data": None}


def fetch_index():
    if _cache["data"] and time.time() - _cache["t"] < 60:
        return _cache["data"]
    last_err = None
    for attempt in range(3):
        try:
            r = requests.get(URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            d = r.json()["data"]
            _cache["data"] = (int(d["value"]), d["value_classification"])
            _cache["t"] = time.time()
            return _cache["data"]
        except Exception as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise last_err


def load_last_value():
    try:
        with open(DB_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return None


def save_last_value(value):
    try:
        with open(DB_FILE, "w") as f:
            f.write(str(value))
    except Exception as e:
        print(f"Не удалось сохранить состояние: {e}", flush=True)


def get_recommendation(value):
    if value < 20:
        return "🚨 *ЭКСТРЕМАЛЬНЫЙ СТРАХ!* Возможная зона покупки. 🚀"
    elif value <= 30:
        return "😨 *СТРАХ!* Можно присмотреться к покупке. 🛒"
    elif value > 80:
        return "🚨 *ЭКСТРЕМАЛЬНАЯ ЖАДНОСТЬ!* Возможная зона фиксации прибыли. 💰"
    elif value >= 60:
        return "🤑 *ЖАДНОСТЬ!* Подумайте о фиксации прибыли. 📈"
    return "😐 *Рынок в неопределенности.* Сигналов нет."


def index_text(value, status):
    return (
        "📊 *Индекс страха и жадности (CoinMarketCap)*\n\n"
        f"📌 Значение: `{value}`\n"
        f"📈 Статус: {status}\n\n"
        f"📢 *Сигнал:*\n{get_recommendation(value)}"
    )


def check_and_send_index():
    last_value = load_last_value()
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        value, status = fetch_index()
        if value == last_value:
            print(f"[{now}] Индекс не изменился ({value})", flush=True)
            return
        bot.send_message(CHAT_ID, index_text(value, status), parse_mode="Markdown")
        save_last_value(value)
        print(f"[{now}] Отправлено: {value}", flush=True)
    except Exception as e:
        print(f"[{now}] Ошибка: {e}", flush=True)


@bot.message_handler(commands=["start", "index"])
def on_command(message):
    try:
        value, status = fetch_index()
        bot.reply_to(message, index_text(value, status), parse_mode="Markdown")
    except Exception as e:
        print(f"Ошибка ответа на команду: {e}", flush=True)
        bot.reply_to(message, "Не удалось получить индекс, попробуйте через минуту.")


def hourly_loop():
    while True:
        check_and_send_index()
        time.sleep(3600)


if __name__ == "__main__":
    threading.Thread(target=hourly_loop, daemon=True).start()
    bot.infinity_polling(skip_pending=True)
