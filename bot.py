# bot.py
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv   # ← эта строка
import os                        # ← и эта

load_dotenv()                    # ← эти две строки
API_TOKEN = os.getenv("API_TOKEN")
EXPERT_ID = int(os.getenv("EXPERT_ID"))

import asyncio

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=API_TOKEN,             # ← используем переменную, а не строку с токеном
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# --- Состояния ---
class Form(StatesGroup):
    waiting_photos = State()       # Ожидание фото (в начале)
    category = State()             # Выбор категории
    # Автографы
    autograph_known = State()
    autograph_whose = State()
    # Боны
    bonds_type = State()
    # ДПИ
    material = State()
    size_dpi = State()
    marks = State()
    weight = State()
    # Живопись
    size_painting = State()
    technique_known = State()
    russian_author = State()
    clarification = State()
    dating = State()
    before_after_1917 = State()
    # Финал
    final = State()

# --- Клавиатуры ---
def category_keyboard():
    buttons = [
        ["Автографы", "Антикварное оружие"],
        ["Боны", "Декоративно прикладное искусство"],
        ["Живопись", "Книги"],
        ["Марки", "Медали"],
        ["Монеты", "Открытки"],
        ["Плакаты", "Фотографии"]
    ]
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=text) for text in row] for row in buttons],
                               resize_keyboard=True)

def yes_no_keyboard():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
                               resize_keyboard=True)

def material_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Фарфор"), KeyboardButton(text="Бронза")],
            [KeyboardButton(text="Серебро"), KeyboardButton(text="Дерево")],
            [KeyboardButton(text="Другое")]
        ],
        resize_keyboard=True
    )

# --- Старт ---
@dp.message(Command(commands=["start"]))
async def start(message: types.Message, state: FSMContext):
    await state.clear()  # На всякий случай
    await message.answer(
        "Привет! Этот бот поможет отправить заявку на оценку антиквариата.\n\n"
        "Пожалуйста, сначала пришлите <b>фото предмета</b> (можно несколько).",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Form.waiting_photos)

# --- Ожидание фото ---
@dp.message(Form.waiting_photos, F.photo)
async def handle_photos(message: types.Message, state: FSMContext):
    # Сохраняем фото
    photos = (await state.get_data()).get("photos", [])
    photos.append(message.photo[-1].file_id)  # Берем самое большое качество
    await state.update_data(photos=photos)

    await message.answer(f"Получено фото: {len(photos)}. Можно прислать ещё или выбрать категорию.",
                         reply_markup=category_keyboard())

    await state.set_state(Form.category)

@dp.message(Form.waiting_photos)
async def photos_reminder(message: types.Message):
    await message.answer("Пожалуйста, пришлите хотя бы одно фото предмета.")

# --- Выбор категории ---
@dp.message(Form.category)
async def handle_category(message: types.Message, state: FSMContext):
    # Список всех возможных категорий (точно как в кнопках)
    VALID_CATEGORIES = {
        "Автографы", "Антикварное оружие",
        "Боны", "Декоративно прикладное искусство",
        "Живопись", "Книги",
        "Марки", "Медали",
        "Монеты", "Открытки",
        "Плакаты", "Фотографии"
    }

    user_text = message.text.strip()

    if user_text not in VALID_CATEGORIES:
        await message.answer("Пожалуйста, выберите категорию, нажав на одну из кнопок ниже:", 
                             reply_markup=category_keyboard())
        return

    # Сохраняем категорию
    await state.update_data(category=user_text)

    # Теперь логика по категориям
    if user_text == "Автографы":
        await message.answer("Известен ли чей автограф?", reply_markup=yes_no_keyboard())
        await state.set_state(Form.autograph_known)

    elif user_text == "Антикварное оружие":
        await finalize_case(message, state)

    elif user_text == "Боны":
        await message.answer("Боны российские или иностранные?\n(напишите ответ текстом)", 
                             reply_markup=ReplyKeyboardRemove())
        await state.set_state(Form.bonds_type)

    elif user_text == "Декоративно прикладное искусство":
        await message.answer("Выберите материал:", reply_markup=material_keyboard())
        await state.set_state(Form.material)

    elif user_text == "Живопись":
        await message.answer("Введите размер картины (например: 50x70 см):", 
                             reply_markup=ReplyKeyboardRemove())
        await state.set_state(Form.size_painting)

    else:  # Все остальные категории — сразу отправляем эксперту
        await finalize_case(message, state)
# --- Автографы ---
@dp.message(Form.autograph_known)
async def autograph_known(message: types.Message, state: FSMContext):
    await state.update_data(autograph_known=message.text)
    if message.text == "Да":
        await message.answer("Чей автограф?")
        await state.set_state(Form.autograph_whose)
    else:
        await finalize_case(message, state)

@dp.message(Form.autograph_whose)
async def autograph_whose(message: types.Message, state: FSMContext):
    await state.update_data(autograph_whose=message.text)
    await finalize_case(message, state)

# --- Боны ---
@dp.message(Form.bonds_type)
async def bonds_type(message: types.Message, state: FSMContext):
    await state.update_data(bonds_type=message.text)
    await finalize_case(message, state)

# --- ДПИ ---
@dp.message(Form.material)
async def dpi_material(message: types.Message, state: FSMContext):
    await state.update_data(material=message.text)
    await message.answer("Введите размер предмета (например: высота 20 см):")
    await state.set_state(Form.size_dpi)

@dp.message(Form.size_dpi)
async def dpi_size(message: types.Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("Есть ли клейма, подписи, маркировки?", reply_markup=yes_no_keyboard())
    await state.set_state(Form.marks)

@dp.message(Form.marks)
async def dpi_marks(message: types.Message, state: FSMContext):
    await state.update_data(marks=message.text)
    data = await state.get_data()
    if data.get("material") == "Серебро":
        await message.answer("Укажите вес (в граммах):")
        await state.set_state(Form.weight)
    else:
        await finalize_case(message, state)

@dp.message(Form.weight)
async def dpi_weight(message: types.Message, state: FSMContext):
    await state.update_data(weight=message.text)
    await finalize_case(message, state)

# --- Живопись ---
@dp.message(Form.size_painting)
async def painting_size(message: types.Message, state: FSMContext):
    await state.update_data(size=message.text)
    await message.answer("Известна ли техника исполнения или автор?", reply_markup=yes_no_keyboard())
    await state.set_state(Form.technique_known)

@dp.message(Form.technique_known)
async def painting_technique(message: types.Message, state: FSMContext):
    await state.update_data(technique_known=message.text)
    await message.answer("Автор русский?", reply_markup=yes_no_keyboard())
    await state.set_state(Form.russian_author)

@dp.message(Form.russian_author)
async def painting_russian(message: types.Message, state: FSMContext):
    await state.update_data(russian_author=message.text)
    await message.answer("Уточнение по автору, технике, подписи и т.д.:")
    await state.set_state(Form.clarification)

@dp.message(Form.clarification)
async def painting_clarification(message: types.Message, state: FSMContext):
    await state.update_data(clarification=message.text)
    await message.answer("Датировка (если известна):")
    await state.set_state(Form.dating)

@dp.message(Form.dating)
async def painting_dating(message: types.Message, state: FSMContext):
    await state.update_data(dating=message.text)
    await message.answer("Работа до 1917 года или после?")
    await state.set_state(Form.before_after_1917)

@dp.message(Form.before_after_1917)
async def painting_period(message: types.Message, state: FSMContext):
    await state.update_data(before_after_1917=message.text)
    await finalize_case(message, state)

# --- Финализация и отправка эксперту ---
async def finalize_case(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])

    text = "<b>Новая заявка на оценку</b>\n\n"
    text += f"<b>Категория:</b> {data.get('category', 'Не указана')}\n"
    text += f"<b>От кого:</b> {message.from_user.full_name} (@{message.from_user.username or 'нет'})\n"
    text += f"<b>ID пользователя:</b> <code>{message.from_user.id}</code>\n\n"

    # Добавляем все ответы
    answers = {
        "Автограф известен": data.get("autograph_known"),
        "Чей автограф": data.get("autograph_whose"),
        "Тип бон": data.get("bonds_type"),
        "Материал": data.get("material"),
        "Размер": data.get("size"),
        "Клейма/подписи": data.get("marks"),
        "Вес": data.get("weight"),
        "Техника/автор известны": data.get("technique_known"),
        "Русский автор": data.get("russian_author"),
        "Уточнение": data.get("clarification"),
        "Датировка": data.get("dating"),
        "Период": data.get("before_after_1917"),
    }
    for key, value in answers.items():
        if value:
            text += f"<b>{key}:</b> {value}\n"

    # Отправляем эксперту
    await bot.send_message(EXPERT_ID, text)
    if photos:
        for i, file_id in enumerate(photos):
            await bot.send_photo(EXPERT_ID, file_id, caption="Фото предмета" if i == 0 else "")

    await message.answer("Спасибо! Ваша заявка отправлена эксперту. Ожидайте ответа в ближайшее время.", 
                         reply_markup=ReplyKeyboardRemove())
    await state.clear()

# --- Запуск ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
