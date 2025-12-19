# bot.py
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
EXPERT_ID = int(os.getenv("EXPERT_ID"))

import asyncio

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
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def photo_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Отправить ещё фото"), KeyboardButton(text="Продолжить")],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True
    )

def cancel_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отмена")]], resize_keyboard=True)

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
        "Привет! 😊 Я помогу тебе отправить <b>один предмет</b> на оценку нашему эксперту по антиквариату.\n\n"
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

    await state.update_data(category=category, photos=[])

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

# Сбор фото (одиночное)
@dp.message(Form.photos, F.photo & ~F.media_group_id)
async def handle_single_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer("Фото получено! 📸 Присылай ещё или нажми «Продолжить».", reply_markup=photo_keyboard())

# Сбор группы фото (media group)
@dp.message(Form.photos, F.media_group_id)
async def handle_media_group(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    # Добавляем все фото из группы
    added_count = 0
    for media in message.media_group_id:  # aiogram не имеет media_group_id, это ошибка; используем handler для группы
        if media.content_type == 'photo':
            photos.append(media.photo[-1].file_id)
            added_count += 1

    await state.update_data(photos=photos)
    await message.answer(f"Получено {added_count} фото! 📸 Присылай ещё или нажми «Продолжить».", reply_markup=photo_keyboard())

# Обработчик для кнопок во время фото
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
        await message.answer("Какая техника исполнения (масло, акварель, гуашь и т.d.)?", reply_markup=cancel_keyboard())
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

# Обработка вопросов (без предпросмотра — сразу к финалу)
@dp.message(Form.info)
async def handle_simple_info(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        return await cancel(message, state)
    await state.update_data(simple_info=message.text)
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

# Финализация с БД
async def finalize_case(message: types.Message, state: FSMContext):
    data = await state.get_data()
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
    if "simple_info" in data:
        info_dict["Дополнительно"] = data['simple_info']

    app_number = save_application(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        category=data.get('category'),
        photos=photos,
        info_dict=info_dict
    )

    text = f"<b>Новая заявка №{app_number}</b>\n\n"
    text += f"<b>Категория:</b> {data.get('category')}\n"
    text += f"<b>Пользователь:</b> {message.from_user.full_name} (@{message.from_user.username or 'нет'})\n"
    text += f"<b>ID:</b> <code>{message.from_user.id}</code>\n\n"

    for key, value in info_dict.items():
        text += f"<b>{key}:</b> {value}\n"

    try:
        await bot.send_message(EXPERT_ID, text)
        if photos:
            for i, file_id in enumerate(photos):
                await bot.send_photo(EXPERT_ID, file_id, caption=f"Заявка №{app_number} | Фото {i+1}")
    except Exception as e:
        logging.error(f"Ошибка отправки эксперту: {e}")

    await message.answer(
        "Спасибо большое! 🙏 Твоя заявка отправлена эксперту.\n"
        "Он изучит фото и информацию и скоро напишет тебе ответ.\n"
        "Хорошего дня! ☀️",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()

# Запуск
async def main():
    await set_commands()
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Критическая ошибка бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())
