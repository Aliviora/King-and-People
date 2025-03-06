import json
import sqlite3
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, ContextTypes, \
    CallbackQueryHandler
import random
from answer_new import *

conn = sqlite3.connect("user_progres.db")
cursor = conn.cursor()

# Создание таблицы
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_progres (
    user_id INTEGER PRIMARY KEY,
    days INTEGER,
    answers TEXT,
    quest TEXT,
    gold INTEGER,
    stocks INTEGER,
    contentment INTEGER
)
''')
conn.commit()


def get_form(number, forms):
    if number % 10 == 1 and number % 100 != 11:
        return forms[0]

    elif 2 <= number % 10 <= 4 and (number % 100 < 10 or number % 100 >= 20):
        return forms[1]

    else:
        return forms[2]


def format_time(days):
    # Константы для перевода
    days_in_week = 7
    days_in_month = 30
    days_in_year = 365

    # Перевод дней в недели, месяцы и годы
    years = days // days_in_year
    days %= days_in_year

    months = days // days_in_month
    days %= days_in_month

    weeks = days // days_in_week
    days %= days_in_week

    # Форматирование вывода
    result = []
    if years > 0:
        result.append(f"{years} {get_form(years, ('год', 'года', 'лет'))}")
    if months:
        result.append(f"{months} {get_form(months, ('месяц', 'месеца', 'месяцев'))}")
    if weeks:
        result.append(f"{weeks} {get_form(weeks, ('неделя', 'недели', 'недель'))}")
    if days:
        result.append(f"{days} {get_form(days, ('день', 'дня', 'дней'))}")

    return ' и '.join(result)


def save_user_progres(user_id, progres):
    # Преобразуем список answers в строку JSON
    answers_str = json.dumps(progres['answers'])
    quest_str = json.dumps(progres['quest'])

    # Вставляем или обновляем данные пользователя
    cursor.execute('''
    INSERT OR REPLACE INTO user_progres (user_id, days, answers, quest, gold, stocks, contentment)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, progres['days'], answers_str, quest_str, progres['gold'], progres['stocks'],
          progres['contentment']))

    conn.commit()


def get_user_progres(user_id):
    cursor.execute(
        'SELECT days, answers, quest, gold, stocks, contentment FROM user_progres WHERE user_id = ?',
        (user_id,))
    result = cursor.fetchone()

    if result:
        try:
            # Преобразуем строку JSON обратно в список
            answers = json.loads(result[1])
            quest = json.loads(result[2])
            return {
                'days': result[0],
                'answers': answers,
                'quest': quest,
                'gold': result[3],
                'stocks': result[4],
                'contentment': result[5],
            }
        except json.JSONDecodeError as e:
            print(f"Ошибка декодирования {e}")
            return None
        except sqlite3.Error as e:
            print(f"Ошибка базы данных {e}")
            return None
    else:
        return None


def get_question(user_id, work):
    progres = get_user_progres(user_id)
    if not progres:
        progres = {
            "days": 0,
            "answers": None,
            "quest": None,
            "gold": 50,
            "stocks": 50,
            "contentment": 81,
        }
        save_user_progres(user_id, progres)

    global question_answers, question_index
    if work:
        if progres["gold"] < progres["stocks"] and progres["gold"] < \
                progres["contentment"]:
            rand = random.choice((0, 1))
            if rand:
                question_answers = questions_gold
            else:
                question_answers = random.choice(list_questions_answers)
        elif progres["stocks"] < progres["gold"] and progres["stocks"] < \
                progres["contentment"]:
            rand = random.choice((0, 1))
            if rand:
                question_answers = questions_stocks
            else:
                question_answers = random.choice(list_questions_answers)
        else:
            rand = random.choice((0, 1))
            if rand:
                question_answers = questions_contentment
            else:
                question_answers = random.choice(list_questions_answers)
        question_index = random.randrange(len(question_answers))
        list_questions_answers_index = list_questions_answers.index(question_answers)
        progres["quest"] = list(list_consequences[list_questions_answers_index].items())[question_index]
        progres["answers"] = list(question_answers.keys())[question_index]
        save_user_progres(user_id, progres)
        return list(question_answers.keys())[question_index]
    else:
        question_answers = random.choice(list_weekend_event)
        question_index = random.randrange(len(question_answers))
        list_questions_answers_index = list_weekend_event.index(question_answers)
        progres["quest"] = list(list_consequences_weekend_event[list_questions_answers_index].items())[question_index]
        progres["answers"] = list(question_answers.keys())[question_index]
        save_user_progres(user_id, progres)
        return list(question_answers.keys())[question_index]


async def echo(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text(f"Вы написали: {update.message.text}")


async def start(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    user = update.effective_user
    if not user:
        await message.reply_text("Не удалось определить пользователя")
        return
    user_id = user.id
    current_question = get_question(user_id, True)
    progres = get_user_progres(user_id)
    if not progres:
        await message.reply_text("Прогрес не найден, начинаем с начала")
    await message.reply_text(
        text=f"золото: {progres['gold']} | запасы: {progres['stocks']} | одобрение: {progres['contentment']}"
    )
    answer = question_answers[current_question]
    keyboard = [[InlineKeyboardButton(ans, callback_data=ans)] for ans in answer]
    await message.reply_text(current_question,
                             reply_markup=InlineKeyboardMarkup(keyboard))


async def restart(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    await message.reply_text(text=f"Действительно ли вы хотите сбросить прогресс игры")
    keyboard = [
        [InlineKeyboardButton("Да", callback_data="restart_yes"),
         InlineKeyboardButton("Нет", callback_data="restart_no")]
    ]
    await message.reply_text(
        "Хотите начать игру занова?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


def reset_progres(user_id):
    progres = {
        "days": 0,
        "answers": None,
        "quest": None,
        "gold": 50,
        "stocks": 50,
        "contentment": 81,
    }
    save_user_progres(user_id, progres)


async def button_handler(update: Update, context: CallbackContext) -> None:
    message = update.effective_message
    query = update.callback_query
    user_id = query.from_user.id
    progres = get_user_progres(user_id)
    await query.answer()
    if not progres:
        await query.message.reply_text("Прогрес не найден, начните с помощью /start")
        return
    if query.data == "restart_yes":
        reset_progres(user_id)
        await start(update, context)
        return
    elif query.data == 'restart_no':
        await query.message.reply_text("Спасибо за игру, возвращайтесь снова!")
        return
    select_answer = query.data
    consequence_index = progres["quest"][-1]
    if select_answer in consequence_index:
        consequence = consequence_index[select_answer][0]
        progres["gold"] += consequence_index[select_answer][1]
        progres["stocks"] += consequence_index[select_answer][2]
        progres["contentment"] += consequence_index[select_answer][3]
    else:
        consequence = "Что-то пошло не так..."
    if progres["gold"] <= 0:
        await query.message.reply_text(text="Закончилось золото! ")
        await query.message.reply_text(text="GAME OVER! ")
        await restart(update, context)
        return
    elif progres["stocks"] <= 0:
        await query.message.reply_text(text="Закончились припасы! ")
        await query.message.reply_text(text="GAME OVER! ")
        await restart(update, context)
        return
    elif progres["contentment"] <= 0:
        await query.message.reply_text(text="Недовольство населения стало слишком высоким! ")
        await query.message.reply_text(text="GAME OVER! ")
        await restart(update, context)
        return
    progres["days"] += 1
    save_user_progres(user_id, progres)
    if progres["days"] % 7 == 0 and progres["days"] != 0:
        set_time = format_time(progres['days'])
        await query.message.reply_text(text=f'<b>* Прошло {set_time} *</b>', parse_mode='HTML')
        next_question = get_question(user_id, False)
    else:
        await query.edit_message_text(text=f"Вы выбрали: {select_answer}\n\n{consequence}")
        next_question = get_question(user_id, True)
    answer = question_answers[next_question]
    keyboard = [[InlineKeyboardButton(ans, callback_data=ans)] for ans in answer]
    await query.message.reply_text(
        text=f"золото: {progres['gold']} | запасы: {progres['stocks']} | одобрение: {progres['contentment']}")
    await query.message.reply_text(text=next_question,
                                   reply_markup=InlineKeyboardMarkup(keyboard))


async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Команды:\n /start\n /help")


def main():
    application = Application.builder().token("7047500798:AAH9z5qWjfLZRr5skwbLorxE4mtnjz1wPb4").build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.run_polling()


if __name__ == "__main__":
    main()
