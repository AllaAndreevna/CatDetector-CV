import cv2
import numpy as np
import time
import csv
from datetime import datetime
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile
from aiogram.filters import Command
from datetime import datetime
from pytz import timezone


CONFIDENCE_THRESHOLD = 0.3
INPUT_WIDTH = 320
INPUT_HEIGHT = 320
DETECTION_COOLDOWN = 5  
CAT_CLASS_ID = 15  


SAVE_DIR = "detections"
CSV_FILE = os.path.join(SAVE_DIR, "detections_log.csv")
MODEL_PATH = "models/yolo11n.onnx"
WIFI_FILE = "wifi_config.txt"

os.makedirs(SAVE_DIR, exist_ok=True)


API_TOKEN = "7387365516:AAEEgkdcQWaCwMeLNwZ6qo-kGBVv2FRSqsE"
USER_ID = 1310738709  


bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Сохранение/чтение конфигурации Wi-Fi 
def save_wifi_config(ssid, password):
    with open(WIFI_FILE, "w") as f:
        f.write(f"{ssid}\n{password}")
    print("Wi-Fi данные сохранены")

def load_wifi_config():
    if os.path.exists(WIFI_FILE):
        with open(WIFI_FILE) as f:
            lines = f.read().splitlines()
            return lines if len(lines) == 2 else ("", "")
    return ("", "")

async def send_error_alert(message):
    try:
        await bot.send_message(chat_id=USER_ID, text=f"❗ Ошибка: {message}")
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👋 Привет! Я фотоловушка.\n\nДоступные команды:\n📶 /wifi SSID PASSWORD\n❌ /off — выключить ловушку")

@dp.message(Command("wifi"))
async def cmd_wifi(message: types.Message):
    try:
        _, ssid, password = message.text.strip().split()
        save_wifi_config(ssid, password)
        await message.answer("✅ Wi-Fi данные сохранены")
    except ValueError:
        await message.answer("⚠️ Используй формат: /wifi SSID PASSWORD")


@dp.message(Command("off"))
async def cmd_off(message: types.Message):
    print("❌ Выключение фотоловушки...")
    await message.answer("🔌 Фотоловушка отключена.")
    os._exit(0)

async def send_cat_found_alert(image_path, location_info):
    try:
        photo = FSInputFile(image_path)
        now = datetime.now(timezone("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
        caption = f"🐱 Обнаружен кот!\n📍 Место: {location_info}\n🕒 Время: {now}"
        await bot.send_photo(chat_id=USER_ID, photo=photo, caption=caption)
    except Exception as e:
        print(f"Ошибка отправки Telegram-сообщения: {e}")


def detect_cat_and_get_box(outs, frame):
    h, w = frame.shape[:2]
    x_scale = w / INPUT_WIDTH
    y_scale = h / INPUT_HEIGHT
    output = outs[0].squeeze(0).T
    for i in range(output.shape[0]):
        row = output[i]
        scores = row[4:]
        class_id = np.argmax(scores)
        confidence = scores[class_id]
        if class_id == CAT_CLASS_ID and confidence > CONFIDENCE_THRESHOLD:
            cx, cy, bw, bh = row[:4]
            cx *= x_scale
            cy *= y_scale
            bw *= x_scale
            bh *= y_scale
            x1, y1 = int(cx - bw / 2), int(cy - bh / 2)
            x2, y2 = int(cx + bw / 2), int(cy + bh / 2)
            return True, (x1, y1, x2, y2), confidence
    return False, None, None


async def main_loop():
    global last_detection_time
    
    # Инициализация камеры и модели
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Не удалось открыть камеру")
        await send_error_alert("Камера не найдена")
        return
    
    net = cv2.dnn.readNet(MODEL_PATH)
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            csv.writer(f).writerow(["Date/Time", "Image name"])
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                continue

            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (INPUT_WIDTH, INPUT_HEIGHT), swapRB=True)
            net.setInput(blob)
            outs = net.forward(net.getUnconnectedOutLayersNames())

            detected, box, conf = detect_cat_and_get_box(outs, frame)
            if detected:
                now = time.time()
                if now - last_detection_time > DETECTION_COOLDOWN:
                    x1, y1, x2, y2 = box
                    snapshot = frame.copy()
                    cv2.rectangle(snapshot, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(snapshot, f"Cat {conf:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                    timestamp = datetime.now(timezone("Europe/Moscow")).strftime("%Y-%m-%d_%H-%M-%S")
                    filename = f"cat_{timestamp}.jpg"
                    filepath = os.path.join(SAVE_DIR, filename)
                    cv2.imwrite(filepath, snapshot)

                    with open(CSV_FILE, 'a', newline='') as f:
                        csv.writer(f).writerow([timestamp, filename])

                    print(f"[{timestamp}] {filename}")
                    await send_cat_found_alert(filepath, "Камера №1")
                    last_detection_time = now
            await asyncio.sleep(0.1)
    finally:
        cap.release()


last_detection_time = 0

async def main():   
    try:
        print("✅ Фотоловушка готова к работе")
        await bot.send_message(chat_id=USER_ID, text="📸 Фотоловушка готова к работе")

        # Запускаем задачи параллельно
        await asyncio.gather(
            main_loop(),
            dp.start_polling(bot)
        )
    except KeyboardInterrupt:
        print("Получен сигнал остановки")
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())