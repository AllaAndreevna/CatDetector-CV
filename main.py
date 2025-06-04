import cv2
import numpy as np
import time
import csv
from datetime import datetime
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command
from datetime import datetime
from pytz import timezone


CONFIDENCE_THRESHOLD = 0.3
INPUT_WIDTH = 320
INPUT_HEIGHT = 320
DETECTION_COOLDOWN = 5  
CAT_CLASS_ID = 15  
TRAP_ID = "001"  

SAVE_DIR = "detections"
CSV_FILE = os.path.join(SAVE_DIR, "detections_log.csv")
MODEL_PATH = "models/yolo11n.onnx"
WIFI_FILE = "wifi_config.txt"

os.makedirs(SAVE_DIR, exist_ok=True)

API_TOKEN = "7387365516:AAEEgkdcQWaCwMeLNwZ6qo-kGBVv2FRSqsE"
USER_ID = 1310738709  

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Состояния для конфигурации Wi-Fi
user_states = {}

# главное меню
def get_main_menu():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📊 Статус системы")],
            [KeyboardButton(text="📶 Настройки Wi-Fi"), KeyboardButton(text="📸 Информация о камере")],
            [KeyboardButton(text="🔧 Настройки детекции"), KeyboardButton(text="📋 Журнал обнаружений")],
            [KeyboardButton(text="❌ Выключить фотоловушку")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    return keyboard

# сохранение/чтение конфигурации Wi-Fi 
def save_wifi_config(ssid, password):
    try:
        with open(WIFI_FILE, "w", encoding='utf-8') as f:
            f.write(f"{ssid}\n{password}")
        print(f"✅ Wi-Fi данные сохранены: SSID={ssid}")
        return True
    except Exception as e:
        print(f"❌ Ошибка сохранения Wi-Fi: {e}")
        return False

def load_wifi_config():
    if os.path.exists(WIFI_FILE):
        try:
            with open(WIFI_FILE, encoding='utf-8') as f:
                lines = f.read().splitlines()
                if len(lines) >= 2:
                    print(f"📶 Загружены Wi-Fi данные: SSID={lines[0]}")
                    return lines[0], lines[1]
        except Exception as e:
            print(f"❌ Ошибка чтения Wi-Fi конфига: {e}")
    return "", ""

def apply_wifi_config():
    """Применение Wi-Fi настроек (заглушка для реализации на плате)"""
    ssid, password = load_wifi_config()
    if ssid and password:
        print(f"🔄 Попытка подключения к Wi-Fi: {ssid}")
        # Здесь будет код для подключения к Wi-Fi на плате
        # import subprocess
        # subprocess.run(['nmcli', 'dev', 'wifi', 'connect', ssid, 'password', password])
        return True
    return False

async def send_error_alert(message):
    try:
        await bot.send_message(chat_id=USER_ID, text=f"❗ Ошибка фотоловушки {TRAP_ID}: {message}")
    except Exception as e:
        print(f"Ошибка отправки сообщения: {e}")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = f"""👋 Добро пожаловать в систему управления фотоловушкой {TRAP_ID}!

🎯 Система автоматического обнаружения котов
📱 Управление через Telegram
📊 Полная статистика и журнал

Выберите действие из меню ниже:"""
    
    await message.answer(welcome_text, reply_markup=get_main_menu())

@dp.message(lambda message: message.text == "📊 Статус системы")
async def status_handler(message: types.Message):
    ssid, _ = load_wifi_config()
    wifi_status = f"📶 Wi-Fi: {ssid if ssid else 'Не настроен'}"
    
    # Проверка файлов
    model_exists = "✅" if os.path.exists(MODEL_PATH) else "❌"
    csv_exists = "✅" if os.path.exists(CSV_FILE) else "❌"
    
    status_text = f"""📊 Статус фотоловушки {TRAP_ID}:

{wifi_status}
YOLO модель: {model_exists}
Журнал: {csv_exists}
Порог детекции: {CONFIDENCE_THRESHOLD}
Кулдаун: {DETECTION_COOLDOWN}с
Класс: {CAT_CLASS_ID} (кот)

🔧 ID устройства: {TRAP_ID}"""
    
    await message.answer(status_text, reply_markup=get_main_menu())

@dp.message(lambda message: message.text == "📶 Настройки Wi-Fi")
async def wifi_settings_handler(message: types.Message):
    ssid, _ = load_wifi_config()
    current_wifi = f"Текущий SSID: {ssid}" if ssid else "Wi-Fi не настроен"
    
    text = f"""📶 Настройки Wi-Fi фотоловушки {TRAP_ID}

{current_wifi}

Отправьте данные в формате:
SSID пароль

Например: MyWiFi mypassword123"""
    
    user_states[message.from_user.id] = "waiting_wifi"
    await message.answer(text, reply_markup=ReplyKeyboardRemove())

@dp.message(lambda message: message.text == "📸 Информация о камере")
async def camera_info_handler(message: types.Message):
    text = f"""📸 Информация о камере фотоловушки {TRAP_ID}:

Разрешение входа: {INPUT_WIDTH}x{INPUT_HEIGHT}
Детекция: YOLO11n
Порог уверенности: {CONFIDENCE_THRESHOLD}
Кулдаун между срабатываниями: {DETECTION_COOLDOWN}с
Папка сохранения: {SAVE_DIR}/"""
    
    await message.answer(text, reply_markup=get_main_menu())

@dp.message(lambda message: message.text == "🔧 Настройки детекции")
async def detection_settings_handler(message: types.Message):
    text = f"""🔧 Настройки детекции фотоловушки {TRAP_ID}:

Порог уверенности: {CONFIDENCE_THRESHOLD}
Кулдаун: {DETECTION_COOLDOWN} секунд
ID класса 'кот': {CAT_CLASS_ID}
Размер входа: {INPUT_WIDTH}x{INPUT_HEIGHT}

Для изменения настроек обратитесь к администратору."""
    
    await message.answer(text, reply_markup=get_main_menu())

@dp.message(lambda message: message.text == "📋 Журнал обнаружений")
async def log_handler(message: types.Message):
    try:
        if os.path.exists(CSV_FILE):
            with open(CSV_FILE, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                total = len(lines) - 1  # -1 для заголовка
                recent = lines[-6:-1] if len(lines) > 6 else lines[1:]  # последние 5
                
                text = f"📋 Журнал обнаружений фотоловушки {TRAP_ID}:\n\n"
                text += f"📊 Всего обнаружений: {total}\n\n"
                
                if recent:
                    text += "🕒 Последние обнаружения:\n"
                    for line in reversed(recent):
                        parts = line.strip().split(',')
                        if len(parts) >= 2:
                            text += f"• {parts[0]} - {parts[1]}\n"
                else:
                    text += "Обнаружений пока нет"
        else:
            text = f"📋 Журнал фотоловушки {TRAP_ID} пуст"
            
    except Exception as e:
        text = f"❌ Ошибка чтения журнала: {e}"
    
    await message.answer(text, reply_markup=get_main_menu())

@dp.message(lambda message: message.text == "❌ Выключить фотоловушку")
async def shutdown_handler(message: types.Message):
    await message.answer(f"🔌 Выключение фотоловушки {TRAP_ID}...", reply_markup=ReplyKeyboardRemove())
    print(f"❌ Выключение фотоловушки {TRAP_ID}")
    # Здесь можно добавить код для graceful shutdown
    os._exit(0)

# Обработка Wi-Fi данных
@dp.message(lambda message: user_states.get(message.from_user.id) == "waiting_wifi")
async def process_wifi_data(message: types.Message):
    try:
        parts = message.text.strip().split()
        if len(parts) >= 2:
            ssid = parts[0]
            password = " ".join(parts[1:])  # пароль может содержать пробелы
            
            if save_wifi_config(ssid, password):
                await message.answer(f"✅ Wi-Fi данные сохранены!\nSSID: {ssid}\n\n🔄 Применение настроек...", reply_markup=get_main_menu())
                
                # попытка применить настройки
                if apply_wifi_config():
                    await message.answer(f"✅ Подключение к Wi-Fi {ssid} выполнено!")
                else:
                    await message.answer("⚠️ Не удалось применить настройки Wi-Fi")
            else:
                await message.answer("❌ Ошибка сохранения Wi-Fi данных", reply_markup=get_main_menu())
        else:
            await message.answer("⚠️ Неверный формат!\nИспользуйте: SSID пароль", reply_markup=get_main_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=get_main_menu())
    finally:
        user_states.pop(message.from_user.id, None)

# обработка неизвестных команд
@dp.message()
async def unknown_handler(message: types.Message):
    await message.answer("❓ Неизвестная команда. Используйте меню ниже:", reply_markup=get_main_menu())

async def send_cat_found_alert(image_path, location_info):
    try:
        photo = FSInputFile(image_path)
        now = datetime.now(timezone("Europe/Moscow")).strftime("%Y-%m-%d %H:%M:%S")
        caption = f"🐱 Фотоловушка {TRAP_ID}: Обнаружен кот!\n📍 Место: {location_info}\n🕒 Время: {now}"
        await bot.send_photo(chat_id=USER_ID, photo=photo, caption=caption)
        print(f"Уведомление отправлено: кот обнаружен в {now}")
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
    
    print(f"Инициализация фотоловушки {TRAP_ID}...")
    
    # проверка Wi-Fi настроек
    ssid, password = load_wifi_config()
    if ssid:
        print(f"Wi-Fi настроен: {ssid}")
        apply_wifi_config()
    else:
        print("⚠️ Wi-Fi не настроен")
    
    # инициализация камеры
    print("Подключение к камере...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        error_msg = "Камера не найдена"
        print(f"❌ {error_msg}")
        await send_error_alert(error_msg)
        return
    print("Камера подключена")
    
    # загрузка модели
    print("Загрузка YOLO модели...")
    if not os.path.exists(MODEL_PATH):
        error_msg = f"Модель не найдена: {MODEL_PATH}"
        print(f"❌ {error_msg}")
        await send_error_alert(error_msg)
        cap.release()
        return
    
    net = cv2.dnn.readNet(MODEL_PATH)
    print("Модель загружена")
    
    # инициализация CSV
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(["Date/Time", "Image name"])
        print("Создан файл журнала")
    
    # отправка уведомления о готовности
    ready_msg = f"Фотоловушка {TRAP_ID} готова к работе"
    print(f"✅ {ready_msg}")
    await bot.send_message(chat_id=USER_ID, text=ready_msg)
    
    print(f"Начало мониторинга (порог: {CONFIDENCE_THRESHOLD}, кулдаун: {DETECTION_COOLDOWN}с)")
    
    try:
        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                print("⚠️ Потеря кадра с камеры")
                continue

            # обработка каждого кадра
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
                    filename = f"cat_{TRAP_ID}_{timestamp}.jpg"
                    filepath = os.path.join(SAVE_DIR, filename)
                    cv2.imwrite(filepath, snapshot)

                    with open(CSV_FILE, 'a', newline='', encoding='utf-8') as f:
                        csv.writer(f).writerow([timestamp, filename])

                    print(f"🐱 [{timestamp}] Кот обнаружен! Уверенность: {conf:.2f}, файл: {filename}")
                    await send_cat_found_alert(filepath, f"Камера {TRAP_ID}")
                    last_detection_time = now
            
            # показать статус каждые 1000 кадров (в консоли)
            frame_count += 1
            if frame_count % 1000 == 0:
                print(f"📊 Обработано кадров: {frame_count}")
                
            await asyncio.sleep(0.1)
    finally:
        cap.release()
        print("Камера отключена")

last_detection_time = 0

async def main():   
    try:
        print(f"🚀 Запуск системы фотоловушки {TRAP_ID}")
        
        startup_message = f"""🤖 Фотоловушка {TRAP_ID} запущена!

Отправьте любое сообщение для начала работы
или используйте команду /start

🎯 Система готова к настройке и мониторингу"""
        
        await bot.send_message(chat_id=USER_ID, text=startup_message)
        
        # запускаем задачи параллельно
        await asyncio.gather(
            main_loop(),
            dp.start_polling(bot)
        )
    except KeyboardInterrupt:
        print(f"⚠️ Получен сигнал остановки фотоловушки {TRAP_ID}")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        await send_error_alert(f"Критическая ошибка: {e}")
    finally:
        await bot.session.close()
        print(f"Фотоловушка {TRAP_ID} отключена")

if __name__ == "__main__":
    asyncio.run(main())