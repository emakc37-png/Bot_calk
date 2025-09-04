import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Токен вашего бота
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

DOCTOR_ID = os.getenv("DOCTOR_ID")
if not DOCTOR_ID:
    raise ValueError("DOCTOR_ID не найден в переменных окружения")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# Состояния FSM
class BMIStates(StatesGroup):
    waiting_for_weight = State()
    waiting_for_height = State()


# Клавиатура для начала измерения
def get_start_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Измерить ИМТ", callback_data="measure_bmi")]
    ])
    return keyboard


# Клавиатура для подтверждения
def get_ok_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="OK", callback_data="ok")]
    ])
    return keyboard


# Функция расчета ИМТ и определения категории
def calculate_bmi(weight, height):
    # Преобразуем рост из см в метры
    height_m = height / 100
    bmi = weight / (height_m ** 2)

    # Определяем категорию
    if bmi < 16:
        category = "Выраженный дефицит массы тела"
    elif 16 <= bmi < 18.5:
        category = "Недостаточная масса тела"
    elif 18.5 <= bmi < 25:
        category = "Нормальная масса тела"
    elif 25 <= bmi < 30:
        category = "Избыточная масса тела"
    elif 30 <= bmi < 35:
        category = "Ожирение 1 степени"
    elif 35 <= bmi < 40:
        category = "Ожирение 2 степени"
    else:
        category = "Ожирение 3 степени"

    return round(bmi, 2), category


def calculate_weight_plan(current_weight, height):
    # Расчет идеального веса на основе целевого ИМТ = 25
    # ИМТ = вес / (рост в метрах)^2
    # Целевой вес = 25 * (рост в метрах)^2
    height_m = height / 100  # конвертируем см в метры
    ideal_weight = 25 * (height_m ** 2)

    # Избыток веса
    excess_weight = current_weight - ideal_weight

    # Планируемое снижение веса после операции (60-80% от избытка)
    min_weight_loss = excess_weight * 0.6
    max_weight_loss = excess_weight * 0.8

    return ideal_weight, excess_weight, min_weight_loss, max_weight_loss

# Обработчик команды /start
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    welcome_text = (
        "👋 Добро пожаловать в бот для расчета Индекса Массы Тела (ИМТ)!\n\n"
        "📊 <b>Что такое ИМТ?</b>\n"
        "ИМТ - это показатель соответствия веса и роста человека, "
        "который помогает оценить, является ли масса тела недостаточной, "
        "нормальной или избыточной.\n\n"
        "💡 <b>Как это работает?</b>\n"
        "1. Нажмите кнопку 'Измерить ИМТ'\n"
        "2. Введите свой вес в килограммах\n"
        "3. Введите свой рост в сантиметрах\n"
        "4. Получите результат с интерпретацией\n\n"
        "🚀 <b>Начните сейчас!</b>"
    )
    await message.answer(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )


# Обработчик нажатия на кнопку "Измерить ИМТ"
@dp.callback_query(lambda c: c.data == "measure_bmi")
async def process_measure_bmi(callback_query: types.CallbackQuery, state: FSMContext):
    # Убираем кнопку из приветственного сообщения
    await callback_query.message.edit_reply_markup(reply_markup=None)

    # Отправляем новое сообщение с запросом веса
    await callback_query.message.answer(
        "Введите ваш вес в килограммах (например: 65):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
        ])
    )
    await state.set_state(BMIStates.waiting_for_weight)
    await callback_query.answer()

# Обработчик отмены
@dp.callback_query(lambda c: c.data == "cancel")
async def process_cancel(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    # Редактируем текущее сообщение с запросом веса/роста
    await callback_query.message.edit_text(
        "Измерение отменено. Вы можете начать заново:",
        reply_markup=get_start_keyboard()
    )
    await callback_query.answer()

# Обработчик ввода веса
@dp.message(BMIStates.waiting_for_weight)
async def process_weight(message: types.Message, state: FSMContext):
    try:
        weight = float(message.text.replace(',', '.'))
        if weight <= 0 or weight > 300:
            await message.answer("Пожалуйста, введите корректный вес (от 1 до 300 кг):")
            return

        await state.update_data(weight=weight)
        await message.answer("Теперь введите ваш рост в сантиметрах (например: 175):")
        await state.set_state(BMIStates.waiting_for_height)

    except ValueError:
        await message.answer("Пожалуйста, введите вес числом (например: 65 или 65.5):")


# Обработчик ввода роста
@dp.message(BMIStates.waiting_for_height)
async def process_height(message: types.Message, state: FSMContext):
    try:
        height = float(message.text.replace(',', '.'))
        if height <= 0 or height > 250:
            await message.answer("Пожалуйста, введите корректный рост (от 1 до 250 см):")
            return

        user_data = await state.get_data()
        weight = user_data['weight']

        # Расчет ИМТ
        bmi, category = calculate_bmi(weight, height)

        result_text = (
            f"📊 <b>Результаты расчета ИМТ:</b>\n\n"
            f"⚖️ Вес: {weight} кг\n"
            f"📏 Рост: {height} см\n"
            f"🔢 ИМТ: {bmi}\n"
            f"📈 Категория: {category}\n\n"
        )

        # Расчет плана снижения веса только для ожирения
        if bmi >= 30:
            ideal_weight, excess_weight, min_weight_loss, max_weight_loss = calculate_weight_plan(weight, height)

            result_text += (
                f"🎯 <b>Идеальный вес:</b> {ideal_weight:.1f} кг\n"
                f"📊 <b>Избыток веса:</b> {excess_weight:.1f} кг\n\n"
                f"📋 <b>Планируемое снижение веса после операции:</b> "
                f"{min_weight_loss:.1f} - {max_weight_loss:.1f} кг\n"
                f"<i>(60-80% от избыточного веса)</i>\n\n"
                f"💡 <b>Рекомендации:</b>\n"
                f'Рекомендуется проконсультироваться с <a href="tg://user?id={DOCTOR_ID}">врачом</a> о программе снижения веса.'
            )
        else:
            # Объединенные рекомендации для всех остальных категорий
            result_text += "💡 <b>Рекомендации:</b>\n"

            if bmi < 18.5:
                result_text += 'Рекомендуется проконсультироваться с <a href="tg://user?id={DOCTOR_ID}">врачом</a> о наборе веса.'
            elif 18.5 <= bmi < 25:
                result_text += "Отличный результат! Поддерживайте текущий вес."
            elif 25 <= bmi < 30:
                result_text += 'Избыточная масса тела. Вам необходимо проконсультироваться с <a href="tg://user?id={DOCTOR_ID}">эндокринологом нашей команды.</a>'

        await message.answer(
            result_text,
            parse_mode="HTML",
            reply_markup=get_ok_keyboard()
        )

        await state.clear()

    except ValueError:
        await message.answer("Пожалуйста, введите рост числом (например: 175 или 175.5):")

# Обработчик кнопки OK
@dp.callback_query(lambda c: c.data == "ok")
async def process_ok(callback_query: types.CallbackQuery):
    await callback_query.message.answer(
        "Измерение завершено. Хотите измерить ИМТ снова?",
        reply_markup=get_start_keyboard()
    )
    await callback_query.answer()


# Запуск бота
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())