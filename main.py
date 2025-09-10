import os
import time

from dotenv import load_dotenv
import telebot
from flask import Flask, request
from telebot import types


server = Flask(__name__)

load_dotenv()

# WEBHOOK_URL_BASE = os.getenv("WEBHOOK_URL_BASE")
# if not WEBHOOK_URL_BASE:
#     raise ValueError("WEBHOOK_URL_BASE не найден в переменных окружения")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

DOCTOR_ID = os.getenv("DOCTOR_ID")
if not DOCTOR_ID:
    raise ValueError("DOCTOR_ID не найден в переменных окружения")

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Вместо FSM будем использовать простые переменные
user_data = {}


# Клавиатуры
def get_start_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Измерить ИМТ", callback_data="measure_bmi"))
    return keyboard


def get_ok_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="OK", callback_data="ok"))
    return keyboard


def get_cancel_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(text="Отмена", callback_data="cancel"))
    return keyboard


# Функции расчета (остаются без изменений)
def calculate_bmi(weight, height):
    height_m = height / 100
    bmi = weight / (height_m ** 2)

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
    height_m = height / 100
    ideal_weight = 24 * (height_m ** 2)
    excess_weight = current_weight - ideal_weight
    min_weight_loss = excess_weight * 0.6
    max_weight_loss = excess_weight * 0.8
    return ideal_weight, excess_weight, min_weight_loss, max_weight_loss


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def cmd_start(message):
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
    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode='HTML',
        reply_markup=get_start_keyboard()
    )


# Обработчик нажатия на кнопку "Измерить ИМТ"
@bot.callback_query_handler(func=lambda call: call.data == 'measure_bmi')
def process_measure_bmi(call):
    try:
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
    except:
        pass

    # Сохраняем состояние пользователя
    user_data[call.from_user.id] = {'state': 'waiting_weight'}

    bot.send_message(
        call.message.chat.id,
        "Введите ваш вес в килограммах (например: 65):",
        reply_markup=get_cancel_keyboard()
    )
    bot.answer_callback_query(call.id)


# Обработчик отмены
@bot.callback_query_handler(func=lambda call: call.data == 'cancel')
def process_cancel(call):
    if call.from_user.id in user_data:
        del user_data[call.from_user.id]

    try:
        bot.edit_message_text(
            "Измерение отменено. Вы можете начать заново:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=get_start_keyboard()
        )
    except:
        bot.send_message(
            call.message.chat.id,
            "Измерение отменено. Вы можете начать заново:",
            reply_markup=get_start_keyboard()
        )
    bot.answer_callback_query(call.id)


# Обработчик ввода веса
@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get('state') == 'waiting_weight')
def process_weight(message):
    try:
        weight = float(message.text.replace(',', '.'))
        if weight <= 0 or weight > 300:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректный вес (от 1 до 300 кг):")
            return

        # Сохраняем вес и меняем состояние
        user_data[message.from_user.id] = {
            'state': 'waiting_height',
            'weight': weight
        }

        bot.send_message(
            message.chat.id,
            "Теперь введите ваш рост в сантиметрах (например: 175):",
            reply_markup=get_cancel_keyboard()
        )

    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите вес числом (например: 65 или 65.5):")


# Обработчик ввода роста
@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get('state') == 'waiting_height')
def process_height(message):
    try:
        height = float(message.text.replace(',', '.'))
        if height <= 0 or height > 250:
            bot.send_message(message.chat.id, "Пожалуйста, введите корректный рост (от 1 до 250 см):")
            return

        # Получаем сохраненные данные
        user_info = user_data.get(message.from_user.id, {})
        weight = user_info.get('weight')

        if not weight:
            bot.send_message(message.chat.id, "Ошибка: данные о весе не найдены. Начните заново.")
            del user_data[message.from_user.id]
            return

        # Расчет ИМТ
        bmi, category = calculate_bmi(weight, height)

        result_text = (
            f"📊 <b>Результаты расчета ИМТ:</b>\n\n"
            f"⚖️ Вес: {weight} кг\n"
            f"📏 Рост: {height} см\n"
            f"🔢 ИМТ: {bmi}\n"
            f"📈 Категория: {category}\n\n"
        )

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
            result_text += "💡 <b>Рекомендации:</b>\n"
            if bmi < 18.5:
                result_text += f'Рекомендуется проконсультироваться с <a href="tg://user?id={DOCTOR_ID}">врачом</a> о наборе веса.'
            elif 18.5 <= bmi < 25:
                result_text += "Отличный результат! Поддерживайте текущий вес."
            elif 25 <= bmi < 30:
                result_text += f'Избыточная масса тела. Вам необходимо проконсультироваться с <a href="tg://user?id={DOCTOR_ID}">эндокринологом нашей команды.</a>'

        # Отправляем результат
        bot.send_message(
            message.chat.id,
            result_text,
            parse_mode='HTML',
            reply_markup=get_ok_keyboard()
        )

        # Очищаем состояние пользователя
        del user_data[message.from_user.id]

    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, введите рост числом (например: 175 или 175.5):")


# Обработчик кнопки OK
@bot.callback_query_handler(func=lambda call: call.data == 'ok')
def process_ok(call):
    bot.send_message(
        call.message.chat.id,
        "Измерение завершено. Хотите измерить ИМТ снова?",
        reply_markup=get_start_keyboard()
    )
    bot.answer_callback_query(call.id)

# @server.route('/' + BOT_TOKEN, methods=['POST'])
# def getMessage():
#     json_string = request.get_data().decode('utf-8')
#     update = telebot.types.Update.de_json(json_string)
#     bot.process_new_updates([update])
#     return "!", 200

@server.route('/healthcheck',  methods=['GET'])
def healthcheck():
    return {"status": "alive"}, 200

# bot.remove_webhook()
#
# time.sleep(1)
#
# # Set webhook
# bot.set_webhook(url=f"{WEBHOOK_URL_BASE}/{BOT_TOKEN}")

# Запуск бота
if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))