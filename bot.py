import logging
import sqlite3
import os
from datetime import datetime
import asyncio

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties
from aiogram.filters.callback_data import CallbackData
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")
EXPERT_ID = int(os.getenv("EXPERT_ID"))

logging.basicConfig(
    filename='bot.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

DB_FILE = "applications.db"

# Инициализация БД
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

# Сохранение заявки
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

# Состояния пользователя
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

# Состояния эксперта
class ExpertForm(StatesGroup):
    summa = State()

# Callback для кнопки ответа
class ReplyCallback(CallbackData, prefix="reply"):
    app_number: int
    user_id: int

# Промпты для фото
PHOTO_PROMPTS = {
    "Автографы": "Сфотографируй общий вид предмета и отдельно крупно сам автограф.",
    "Боны": "Сфотографируй бону с двух сторон.",
    "Декоративно-прикладное искусство": "Сфотографируй предмет со всех сторон, снизу, клеймо или подпись (если есть) и все дефекты.",
    "Живопись": "Сделай общее фото картины, фото обратной стороны и крупно подпись (если она есть).",
    "Книги": "Сделай общие фото книги, титульный лист, страницы с надписями и дефектами.",
    "Марки": "Сфотографируй марки крупно с двух сторон. Если они в альбоме — пришли фото страниц.",
    "Медали": "Сфотографируй медаль с двух сторон.",
    "Монеты": "Сфотографируй монету с двух сторон и отдельно ребро (если там есть надписи).",
    "Открытки": "Сфотографируй открытку с двух сторон.",
    "Фотографии": "Сфотографируй фотографию с двух сторон."
}

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
        one_time_keyboard=False,
        input_field_placeholder="Пришли фото или нажми кнопку"
    )

def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

# Команды меню
async def set_commands():
    commands = [
        BotCommand(command="start", description="Начать новую заявку на оценку"),
        BotCommand(command="cancel", description="Отменить текущую заявку")
    ]
    await bot.set_my_commands(commands)

# Старт
@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Привет! 😊 Я помогу тебе отправить один предмет на оценку нашему эксперту по антиквариату.\n\n"
        "Это займёт всего 2–3 минуты, и ты получишь предварительную оценку бесплатно.\n\n"
        "Для начала выбери категорию предмета:",
        reply_markup=category_keyboard()
    )
    await state.set_state(Form.category)

# Отмена
@dp.message(F.text == "Отмена")
@dp.message(Command("cancel"))
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Заявка отменена. Чтобы начать новую — нажми /start 😊",
        reply_markup=ReplyKeyboardRemove()
    )

# Выбор категории
@dp.message(Form.category)
async def handle_category(message: types.Message, state: FSMContext):
    if message.text == "Отмена":
        return await cancel(message, state)

    category = message.text.strip()
    if category not in PHOTO_PROMPTS:
        await message.answer("Выбери категорию из предложенных ниже 👇", reply_markup=category_keyboard())
        return

    await state.update_data(category=category, photos=[])
    photo_prompt = (
        "📸 Чтобы эксперт мог дать точную оценку, пришли фото в хорошем качестве "
        "и при дневном освещении (без вспышки).\n\n" +
        PHOTO_PROMPTS.get(category, "") +
        "\n\nПрисылай фото. Когда закончишь — нажми «Продолжить»."
    )
    await message.answer(photo_prompt, reply_markup=photo_keyboard())
    await state.set_state(Form.photos)

# Лимит фото
MAX_PHOTOS = 15

# Обработка альбома (медиагруппы)
@dp.message(Form.photos, F.media_group_id)
async def handle_album(message: types.Message, state: FSMContext, album: list[types.Message]):
    data = await state.get_data()
    photos = data.get("photos", [])
    added = 0

    for msg in album:
        if msg.photo and len(photos) < MAX_PHOTOS:
            photos.append(msg.photo[-1].file_id)
            added += 1

    if added > 0:
        await state.update_data(photos=photos)
        await message.answer(
            f"Получен альбом: +{added} фото. Всего: {len(photos)} 📸\n"
            "Присылай ещё или нажми «Продолжить».",
            reply_markup=photo_keyboard()
        )

    if len(photos) >= MAX_PHOTOS:
        await message.answer(f"Достигнут лимит {MAX_PHOTOS} фото. Нажми «Продолжить».")

# Обработка одиночного фото
@dp.message(Form.photos, F.photo)
async def handle_single_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    if len(photos) >= MAX_PHOTOS:
        await message.answer(f"Достигнут лимит {MAX_PHOTOS} фото. Нажми «Продолжить».", reply_markup=photo_keyboard())
        return

    photos.append(message.photo[-1].file_id)
    await state.update_data(photos=photos)
    await message.answer(
        f"Получено +1 фото. Всего: {len(photos)} 📸\nПрисылай ещё или нажми «Продолжить».",
        reply_markup=photo_keyboard()
    )

# Кнопка "Отправить ещё фото"
@dp.message(Form.photos, F.text == "Отправить ещё фото")
async def send_more_photos(message: types.Message):
    await message.answer("Хорошо, присылай ещё фото.", reply_markup=photo_keyboard())

# Кнопка "Продолжить" после фото
@dp.message(Form.photos, F.text == "Продолжить")
async def photos_continue(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    if len(photos) == 0:
        await message.answer("Пришли хотя бы одно фото, пожалуйста.", reply_markup=photo_keyboard())
        return

    category = data["category"]

    if category in ["Автографы", "Марки", "Медали", "Открытки", "Фотографии"]:
        await message.answer("Расскажи всё, что знаешь о предмете (страна, год, автор, состояние и т.д.).", reply_markup=cancel_keyboard())
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

# Дальнейшие вопросы (оставлены без изменений, кроме переходов)
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
        await message.answer("Расскажи подробнее: страна, автор, происхождение, другая известная информация.", reply_markup=cancel_keyboard())
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

# Обработчик нажатия на inline-кнопку "Ответить"
@dp.callback_query(ReplyCallback.filter())
async def handle_reply_callback(callback: types.CallbackQuery, callback_data: ReplyCallback, state: FSMContext):
    await callback.answer("Готовлю ответ...")
    await bot.send_message(
        callback.from_user.id,
        "Введите предварительную оценку (например: «500–700 USD», «бесценно», «нужны дополнительные фото» и т.д.):"
    )
    await state.set_state(ExpertForm.summa)
    await state.update_data(app_number=callback_data.app_number, user_id=callback_data.user_id)

# Ввод оценки экспертом
@dp.message(ExpertForm.summa, F.from_user.id == EXPERT_ID)
async def handle_expert_summa(message: types.Message, state: FSMContext):
    data = await state.get_data()
    app_number = data.get("app_number")
    user_id = data.get("user_id")

    if not app_number or not user_id:
        await message.answer("Ошибка: данные заявки не найдены.")
        await state.clear()
        return

    summa = message.text.strip()

    formatted_text = (
        "✉️ <b>Ответ эксперта по вашей заявке №{app_number}</b>\n\n"
        "🔍 <b>Предварительная оценка:</b>\n"
        f"<i>{summa}</i>\n\n"
        "📝 Эксперт изучил предоставленные фотографии и информацию.\n"
        "Это ориентировочная стоимость на текущий момент.\n\n"
        "Если у вас есть дополнительные вопросы или вы хотите обсудить продажу/покупку — напишите эксперту напрямую.\n\n"
        "Спасибо, что обратились к нам! 🙏\n"
        "Желаем удачи с вашим антиквариатом! ✨"
    ).format(app_number=app_number)

    try:
        await bot.send_message(user_id, formatted_text, parse_mode="HTML")
        await message.answer(f"✅ Оценка отправлена пользователю:\n\n{summa}")
        logging.info(f"Эксперт оценил заявку №{app_number} для пользователя {user_id}: {summa}")
    except Exception as e:
        await message.answer("❌ Ошибка при отправке оценки.")
        logging.error(f"Ошибка отправки оценки заявки №{app_number}: {e}")

    await state.clear()

# Финализация заявки
async def finalize_case(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if not data.get("category"):
        await message.answer("Ошибка: данные неполные. Начните заново.")
        await state.clear()
        return

    photos = data.get("photos", [])
    info_dict = {}
    if "country_year" in data:
        info_dict["Страна и год"] = data["country_year"]
    if "technique" in data:
        info_dict["Техника"] = data["technique"]
    if "size" in data:
        info_dict["Размер"] = data["size"]
    if "detailed_info" in data:
        info_dict["Подробно"] = data["detailed_info"]
    if "material_weight" in data:
        info_dict["Материал и вес"] = data["material_weight"]
    if "book_info" in data:
        info_dict["Книга"] = data["book_info"]
    if "additional_info" in data:
        info_dict["Дополнительно"] = data["additional_info"]

    app_number = save_application(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        category=data["category"],
        photos=photos,
        info_dict=info_dict
    )

    text = f"Новая заявка №{app_number}\n\n"
    text += f"Категория: {data['category']}\n"
    text += f"Пользователь: {message.from_user.full_name} (@{message.from_user.username or 'нет'})\n"
    text += f"ID: {message.from_user.id}\n\n"
    for key, value in info_dict.items():
        text += f"{key}: {value}\n"

    # Inline-кнопка для эксперта
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Ответить на заявку",
            callback_data=ReplyCallback(app_number=app_number, user_id=message.from_user.id).pack()
        )]
    ])

    try:
        await bot.send_message(EXPERT_ID, text, reply_markup=kb)

        if photos:
            media_group = [types.InputMediaPhoto(media=file_id) for file_id in photos]
            media_group[0].caption = f"Заявка №{app_number} | Фото"
            await bot.send_media_group(EXPERT_ID, media_group)

        logging.info(f"Заявка №{app_number} отправлена эксперту от {message.from_user.id}")
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

# Некорректный ввод в состоянии фото
@dp.message(Form.photos)
async def invalid_in_photos(message: types.Message):
    if not message.photo and message.text not in ["Отправить ещё фото", "Продолжить", "Отмена"]:
        await message.answer("Присылай фото или используй кнопки ниже.", reply_markup=photo_keyboard())

# Запуск
async def main():
    await set_commands()
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Критическая ошибка бота: {e}")

if __name__ == "__main__":
    asyncio.run(main())
