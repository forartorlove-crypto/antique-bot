import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, BotCommand
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os
from datetime import datetime
import asyncio

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
EXPERT_ID = int(os.getenv("EXPERT_ID"))

logging.basicConfig(filename='bot.log', level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

DB_FILE = "applications.db"

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            category TEXT,
            photos TEXT,
            info TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Сохранить заявку в БД и вернуть номер
def save_application(user_id, username, full_name, category, photos, info_dict):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    photos_str = ','.join(photos) if photos else ''
    info_str = str(info_dict)
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M")
    c.execute('''
        INSERT INTO applications (user_id, username, full_name, category, photos, info, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username or "нет", full_name, category, photos_str, info_str, timestamp))
    conn.commit()
    app_id = c.lastrowid
    conn.close()
    return app_id

# Состояния
class Form(StatesGroup):
    category = State()
    photos = State()
    info = State()
    technique = State()
    size = State()
    material_weight = State()
    country_year = State()
    book_info = State()
    detailed_info = State()

# Клавиатуры
def category_keyboard():
    buttons = [
        ["Автографы", "Боны"],
        ["Декоративно-прикладное искусство", "Живопись"],
        ["Книги", "Марки"],
        ["Медали", "Монеты"],
        ["Открытки", "Фотографии"]
    ]
    kb = [[KeyboardButton(text=text) for text in row] for row in buttons]
    kb.append([KeyboardButton(text="Отмена")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True)

def photo_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить ещё фото"), KeyboardButton(text="Продолжить")],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False  # Оставляем, чтобы пользователь мог повторять
    )

def cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отмена")]], resize_keyboard=True, one_time_keyboard=True)

# Установка кнопки меню справа
async def set_commands():
    commands = [
        BotCommand(command="start", description="Начать новую заявку на оценку")
    ]
    await bot.set_my_commands(commands)

# Старт
@dp.message(Command(commands=["start"]))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! 😊 Я помогу тебе отправить один предмет на оценку нашему эксперту по антиквариату.\n\n"
        "Это займёт всего 2–3 минуты, и ты получишь предварительную оценку бесплатно.\n\n"
        "Для начала выбери категорию предмета:",
        reply_markup=category_keyboard()
    )
    await state.set_state(Form.category)

# Общая отмена
@dp.message(F.text == "Отмена")
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Заявка отменена. Чтобы начать новую — нажми кнопку меню справа и выбери /start 😊", reply_markup=ReplyKeyboardRemove())

# Выбор категории
@dp.message(Form.category)
async def handle_category(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        return await cancel(message, state)

    category = message.text.strip()
    valid_categories = [
        "Автографы", "Боны", "Декоративно-прикладное искусство", "Живопись",
        "Книги", "Марки", "Медали", "Монеты", "Открытки", "Фотографии"
    ]
    if category not in valid_categories:
        await message.answer("Выбери, пожалуйста, категорию из предложенных ниже 👇", reply_markup=category_keyboard())
        return

    await state.update_data(category=category, photos=[], last_media_group_id=None, photo_count_in_group=0)

    photo_prompt = "📸 Чтобы эксперт мог дать точную оценку, пришли фото в хорошем качестве и при дневном освещении (без вспышки).\n\n"

    if category == "Автографы":
        photo_prompt += "Сфотографируй общий вид предмета и отдельно крупно сам автограф."
    elif category == "Боны":
        photo_prompt += "Сфотографируй бону с двух сторон."
    elif category == "Живопись":
        photo_prompt += "Сделай общее фото картины, фото обратной стороны и крупно подпись (если она есть)."
    elif category == "Марки":
        photo_prompt += "Сфотографируй марки крупно с двух сторон. Если они в альбоме — пришли фото страниц."
    elif category == "Монеты":
        photo_prompt += "Сфотографируй монету с двух сторон и отдельно ребро (если там есть надписи)."
    elif category == "Декоративно-прикладное искусство":
        photo_prompt += "Сфотографируй предмет со всех сторон, снизу, клеймо или подпись (если есть) и все дефекты."
    elif category == "Книги":
        photo_prompt += "Сделай общие фото книги, титульный лист, страницы с надписями и дефектами."
    elif category == "Медали":
        photo_prompt += "Сфотографируй медаль с двух сторон."
    elif category == "Открытки":
        photo_prompt += "Сфотографируй открытку с двух сторон."
    elif category == "Фотографии":
        photo_prompt += "Сфотографируй фотографию с двух сторон."

    await message.answer(photo_prompt + "\n\nПрисылай фото. Когда закончишь — нажми «Продолжить».", reply_markup=photo_keyboard())
    await state.set_state(Form.photos)

# Сбор фото с улучшенной обработкой групп
@dp.message(Form.photos, F.photo)
async def handle_photos(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    last_media_group_id = data.get("last_media_group_id")
    photo_count_in_group = data.get("photo_count_in_group", 0)

    photos.append(message.photo[-1].file_id)
    added_count = 1

    if message.media_group_id:
        if message.media_group_id == last_media_group_id:
            photo_count_in_group += 1
            added_count = photo_count_in_group
            # Не отправляем сообщение сразу, ждём конца группы (workaround: задержка)
            await asyncio.sleep(0.5)  # Ждём, чтобы убедиться, что группа закончилась
        else:
            photo_count_in_group = 1
            added_count = 1
        await state.update_data(last_media_group_id=message.media_group_id, photo_count_in_group=photo_count_in_group)

    await state.update_data(photos=photos)

    # Отправляем сообщение только если это не группа или конец группы
    if not message.media_group_id or added_count > 1:  # Простой хак: если >1, предполагаем конец
        await message.answer(f"Получено {len(photos)} фото всего! 📸 Присылай ещё или нажми «Продолжить».", reply_markup=photo_keyboard())

@dp.message(Form.photos, F.text == "Отправить ещё фото")
async def send_more_photos(message: types.Message):
    await message.answer("Хорошо, присылай ещё фото в хорошем качестве.", reply_markup=photo_keyboard())

@dp.message(Form.photos, F.text == "Продолжить")
async def photos_continue(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    if len(photos) == 0:
        await message.answer("Пожалуйста, пришли хотя бы одно фото, чтобы эксперт мог оценить предмет.", reply_markup=photo_keyboard())
        return

    total_photos = len(photos)
    await message.answer(f"Получено {total_photos} фото. Отлично! Теперь перейдём к вопросам.", reply_markup=cancel_keyboard())

    category = data["category"]

    if category in ["Автографы", "Марки", "Медали", "Открытки", "Фотографии"]:
        await message.answer("Расскажи, пожалуйста, всё, что знаешь о предмете (страна, год, автор, состояние и т.д.).", reply_markup=cancel_keyboard())
        await state.set_state(Form.info)

    elif category == "Боны":
        await message.answer("Укажи страну и год выпуска, если знаешь.", reply_markup=cancel_keyboard())
        await state.set_state(Form.country_year)

    elif category == "Живопись":
        await message.answer("Какая техника исполнения (масло, акварель, гуашь и т.д.)?", reply_markup=cancel_keyboard())
        await state.set_state(Form.technique)

    elif category == "Монеты":
        await message.answer("Из какого материала монета и какой вес (если знаешь)?", reply_markup=cancel_keyboard())
        await state.set_state(Form.material_weight)

    elif category == "Декоративно-прикладное искусство":
        await message.answer("Какой размер предмета и из какого материала он сделан?", reply_markup=cancel_keyboard())
        await state.set_state(Form.size)

    elif category == "Книги":
        await message.answer("Название книги, автор и год издания?", reply_markup=cancel_keyboard())
        await state.set_state(Form.book_info)

# Обработка вопросов (унифицировал на "additional_info" вместо "simple_info")
@dp.message(Form.info)
async def handle_info(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        return await cancel(message, state)
    await state.update_data(additional_info=message.text)
    await finalize_case(message, state)

@dp.message(Form.country_year)
async def handle_country_year(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        return await cancel(message, state)
    await state.update_data(country_year=message.text)
    await message.answer("Есть ещё какая-то информация о боне?", reply_markup=cancel_keyboard())
    await state.set_state(Form.info)

@dp.message(Form.technique)
async def handle_technique(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        return await cancel(message, state)
    await state.update_data(technique=message.text)
    await message.answer("Какой размер картины (в сантиметрах)?", reply_markup=cancel_keyboard())
    await state.set_state(Form.size)

@dp.message(Form.size)
async def handle_size(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        return await cancel(message, state)
    await state.update_data(size=message.text)
    category = (await state.get_data())["category"]
    if category == "Живопись":
        await message.answer("Расскажи подробнее: страна, автор, как картина к тебе попала, другая известная информация.", reply_markup=cancel_keyboard())
        await state.set_state(Form.detailed_info)
    else:
        await message.answer("Есть ещё какая-то информация о предмете?", reply_markup=cancel_keyboard())
        await state.set_state(Form.info)

@dp.message(Form.detailed_info)
async def handle_detailed_info(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        return await cancel(message, state)
    await state.update_data(detailed_info=message.text)
    await finalize_case(message, state)

@dp.message(Form.material_weight)
async def handle_material_weight(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        return await cancel(message, state)
    await state.update_data(material_weight=message.text)
    await message.answer("Есть ещё какая-то информация о монете?", reply_markup=cancel_keyboard())
    await state.set_state(Form.info)

@dp.message(Form.book_info)
async def handle_book_info(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        return await cancel(message, state)
    await state.update_data(book_info=message.text)
    await finalize_case(message, state)

# Функция ответа эксперта (исправлен парсинг)
@dp.message(F.from_user.id == EXPERT_ID, F.reply_to_message)
async def expert_reply(message: types.Message):
    if message.reply_to_message:
        try:
            text = message.reply_to_message.text
            user_id_line = [line for line in text.split('\n') if 'ID:' in line][0]
            user_id = int(user_id_line.split('ID:')[1].strip())  # Исправлено: split по 'ID:', strip для очистки
            await bot.send_message(user_id, message.text)
            await message.answer("Ответ отправлен пользователю.")
            logging.info(f"Эксперт ответил пользователю {user_id}")
        except IndexError:
            await message.answer("Ошибка: не удалось найти строку с ID.")
            logging.error("Ошибка: строка с ID не найдена в сообщении.")
        except ValueError:
            await message.answer("Ошибка: ID не является числом.")
            logging.error("Ошибка: неверный формат ID.")
        except Exception as e:
            await message.answer("Ошибка: не удалось отправить ответ.")
            logging.error(f"Ошибка ответа эксперта: {e}")

# Финализация с БД (унифицировал ключи в info_dict)
async def finalize_case(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("category"):  # Валидация
        await message.answer("Ошибка: данные неполные. Начните заново.")
        await state.clear()
        return

    photos = data.get("photos", [])

    info_dict = {}
    if "country_year" in data:
        info_dict["Страна и год"] = data['country_year']
    if "technique" in data:
        info_dict["Техника"] = data['technique']
    if "size" in data:
        info_dict["Размер"] = data['size']
    if "detailed_info" in data:
        info_dict["Подробно"] = data['detailed_info']
    if "material_weight" in data:
        info_dict["Материал и вес"] = data['material_weight']
    if "book_info" in data:
        info_dict["Книга"] = data['book_info']
    if "additional_info" in data:
        info_dict["Дополнительно"] = data['additional_info']

    app_number = save_application(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        category=data.get('category'),
        photos=photos,
        info_dict=info_dict
    )

    text = f"Новая заявка №{app_number}\n\n"
    text += f"Категория: {data.get('category')}\n"
    text += f"Пользователь: {message.from_user.full_name} (@{message.from_user.username or 'нет'})\n"
    text += f"ID: {message.from_user.id}\n\n"

    for key, value in info_dict.items():
        text += f"{key}: {value}\n"

    try:
        await bot.send_message(EXPERT_ID, text)
        if photos:
            media_group = [types.InputMediaPhoto(media=file_id) for file_id in photos]
            media_group[0].caption = f"Заявка №{app_number} | Фото"
            await bot.send_media_group(EXPERT_ID, media_group)
        logging.info(f"Заявка №{app_number} отправлена эксперту от пользователя {message.from_user.id}")
    except Exception as e:
        logging.error(f"Ошибка отправки эксперту: {e}")
        await message.answer("Ошибка при отправке заявки. Попробуйте позже.")

    await message.answer(
        "Спасибо большое! 🙏 Твоя заявка отправлена эксперту.\n"
        "Он изучит фото и информацию и скоро напишет тебе ответ.\n"
        "Хорошего дня! ☀️",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

# Общий обработчик для invalid input в состояниях (опционально, но полезно)
@dp.message(Form.photos)  # Для не-фото в photos
async def invalid_in_photos(message: types.Message):
    if not message.photo and message.text not in ["Отправить ещё фото", "Продолжить", "Отмена"]:
        await message.answer("Пожалуйста, присылай фото или используй кнопки ниже.", reply_markup=photo_keyboard())

# Запуск
async def main():
    await set_commands()
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Критическая ошибка бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())
