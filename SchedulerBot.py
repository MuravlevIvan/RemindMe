import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from datetime import datetime, timedelta
import re
from dotenv import load_dotenv
import os

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

# Хранилище напоминаний
reminders = {}
# Ожидание ввода времени от пользователя
waiting_for_time = set()

# Частота повторов (в секундах)
REPEAT_INTERVALS = {
    "10 секунд": 10,
    "30 секунд": 30,
    "1 минута": 60,
    "5 минут": 300,
    "10 минут": 600,
    "30 минут": 1800,
    "1 час": 3600,
    "Без повтора": 0
}

# Временные данные для каждого пользователя
user_temp_data = {}


@dp.message(Command('start'))
async def start_message(message: types.Message):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📝 Установить напоминание")],
        [KeyboardButton(text="📋 Показать список напоминаний")],
        [KeyboardButton(text="🗑 Удалить напоминание")],
        [KeyboardButton(text="🔄 Управление повторами")]
    ])
    await bot.send_message(message.chat.id,
                           'Привет! Я помогу тебе не забыть об важных делах\n\n'
                           '📌 Как установить напоминание:\n'
                           '1. Нажми "Установить напоминание"\n'
                           '2. Введи время в формате ЧЧ:ММ\n'
                           '3. Выбери частоту повтора\n'
                           '4. Напиши текст напоминания\n\n'
                           '🔄 Повторяющиеся напоминания начинают работу с указанного времени!\n\n'
                           '🗑 Для удаления напоминания нажми кнопку "Удалить" в самом уведомлении',
                           reply_markup=markup)
    #print(text)



@dp.message(lambda message: message.text == "📝 Установить напоминание")
async def set_reminder(message: types.Message):
    waiting_for_time.add(message.chat.id)
    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ])
    await bot.send_message(message.from_user.id,
                           "⏰ Введите время первого напоминания в формате **ЧЧ:ММ** (например, 14:30)\n\n"
                           "Или нажмите 'Отмена' для выхода",
                           reply_markup=markup,
                           parse_mode="Markdown")


@dp.message(lambda message: message.text == "❌ Отмена")
async def cancel_reminder(message: types.Message):
    if message.chat.id in waiting_for_time:
        waiting_for_time.remove(message.chat.id)
    if message.chat.id in user_temp_data:
        del user_temp_data[message.chat.id]

    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📝 Установить напоминание")],
        [KeyboardButton(text="📋 Показать список напоминаний")],
        [KeyboardButton(text="🗑 Удалить напоминание")],
        [KeyboardButton(text="🔄 Управление повторами")]
    ])
    await bot.send_message(message.from_user.id, "❌ Установка напоминания отменена", reply_markup=markup)


@dp.message(lambda message: message.text == "🔄 Управление повторами")
async def manage_repeats(message: types.Message):
    if message.chat.id not in reminders or not reminders[message.chat.id]:
        await bot.send_message(message.from_user.id, "📭 У вас нет активных напоминаний для управления повторами!")
        return

    # Показываем только напоминания с повтором
    repeat_reminders = [r for r in reminders[message.chat.id] if r.get('repeat_interval', 0) > 0]

    if not repeat_reminders:
        await bot.send_message(message.from_user.id, "📭 У вас нет повторяющихся напоминаний!")
        return

    keyboard = []
    for reminder in repeat_reminders:
        time_str = reminder['time'].strftime("%H:%M")
        button_text = f"{reminder['text'][:20]} - {time_str}"
        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"repeat_config_{reminder['id']}")])

    keyboard.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_repeat_menu")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await bot.send_message(message.from_user.id,
                           "🔄 **Управление повторами напоминаний**\n\nВыберите напоминание для настройки повтора:",
                           parse_mode="Markdown", reply_markup=markup)


@dp.callback_query(lambda call: call.data.startswith("repeat_config_"))
async def configure_repeat(call: types.CallbackQuery):
    reminder_id = int(call.data.split("_")[2])
    chat_id = call.message.chat.id

    user_temp_data[chat_id] = {'configuring_repeat': reminder_id}

    keyboard = []
    for interval_name, seconds in REPEAT_INTERVALS.items():
        keyboard.append([InlineKeyboardButton(text=interval_name, callback_data=f"set_interval_{seconds}")])
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_repeat_config")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await call.message.edit_text("🔄 **Выберите частоту повтора:**\n\n"
                                 "После выбора напоминание будет повторяться с указанным интервалом\n"
                                 "⚠️ Напоминания с повтором будут идти бесконечно, пока вы не удалите их!",
                                 parse_mode="Markdown", reply_markup=markup)
    await call.answer()


@dp.callback_query(lambda call: call.data.startswith("set_interval_"))
async def set_repeat_interval(call: types.CallbackQuery):
    interval_seconds = int(call.data.split("_")[2])
    chat_id = call.message.chat.id

    if chat_id not in user_temp_data or 'configuring_repeat' not in user_temp_data[chat_id]:
        await call.message.edit_text("❌ Ошибка! Попробуйте снова.")
        await call.answer()
        return

    reminder_id = user_temp_data[chat_id]['configuring_repeat']

    if chat_id in reminders:
        for reminder in reminders[chat_id]:
            if reminder['id'] == reminder_id:
                reminder['repeat_interval'] = interval_seconds

                if 'repeat_task' in reminder and reminder['repeat_task'] and not reminder['repeat_task'].done():
                    reminder['repeat_task'].cancel()

                if interval_seconds > 0:
                    # Запускаем повтор
                    reminder['repeat_task'] = asyncio.create_task(
                        repeat_reminder(chat_id, reminder['text'], interval_seconds, reminder_id)
                    )
                    interval_name = [name for name, sec in REPEAT_INTERVALS.items() if sec == interval_seconds][0]
                    await call.message.edit_text(f"✅ **Настройки повтора обновлены!**\n\n"
                                                 f"📝 Текст: {reminder['text']}\n"
                                                 f"🔄 Частота: {interval_name}\n\n"
                                                 f"Напоминание будет повторяться с указанным интервалом.",
                                                 parse_mode="Markdown")
                else:
                    if 'repeat_task' in reminder:
                        reminder['repeat_task'] = None
                    await call.message.edit_text(f"✅ **Повтор отключен!**\n\n"
                                                 f"📝 Текст: {reminder['text']}\n"
                                                 f"Теперь это одноразовое напоминание.",
                                                 parse_mode="Markdown")

                del user_temp_data[chat_id]
                await call.answer()
                return

    await call.message.edit_text("❌ Напоминание не найдено!")
    await call.answer()


@dp.callback_query(lambda call: call.data == "cancel_repeat_config")
async def cancel_repeat_config(call: types.CallbackQuery):
    chat_id = call.message.chat.id
    if chat_id in user_temp_data:
        del user_temp_data[chat_id]
    await call.message.edit_text("❌ Настройка повтора отменена")
    await call.answer()


@dp.callback_query(lambda call: call.data == "close_repeat_menu")
async def close_repeat_menu(call: types.CallbackQuery):
    await call.message.delete()
    await call.answer()


@dp.message(lambda message: message.chat.id in waiting_for_time)
async def get_reminder_time(message: types.Message):
    time_pattern = re.compile(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$')

    if not time_pattern.match(message.text.strip()):
        await bot.send_message(message.from_user.id,
                               "❌ Неверный формат времени!\n"
                               "Пожалуйста, введите время в формате **ЧЧ:ММ** (например, 14:30 или 09:00)",
                               parse_mode="Markdown")
        return

    reminder_time_str = message.text.strip()
    hours, minutes = map(int, reminder_time_str.split(':'))

    now = datetime.now()
    reminder_datetime = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)

    if reminder_datetime <= now:
        reminder_datetime += timedelta(days=1)
        day_text = "завтра"
    else:
        day_text = "сегодня"

    if message.chat.id not in user_temp_data:
        user_temp_data[message.chat.id] = {}
    user_temp_data[message.chat.id]['reminder_time'] = reminder_datetime
    user_temp_data[message.chat.id]['time_str'] = reminder_time_str
    user_temp_data[message.chat.id]['day_text'] = day_text

    waiting_for_time.remove(message.chat.id)

    keyboard = []
    for interval_name, seconds in REPEAT_INTERVALS.items():
        keyboard.append([InlineKeyboardButton(text=interval_name, callback_data=f"select_interval_{seconds}")])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await bot.send_message(message.from_user.id,
                           f"✅ Время установлено: {reminder_time_str} ({day_text})\n\n"
                           f"🔄 **Выберите частоту повтора:**",
                           parse_mode="Markdown",
                           reply_markup=markup)


@dp.callback_query(lambda call: call.data.startswith("select_interval_"))
async def select_repeat_interval(call: types.CallbackQuery):
    interval_seconds = int(call.data.split("_")[2])
    chat_id = call.message.chat.id

    if chat_id not in user_temp_data or 'reminder_time' not in user_temp_data[chat_id]:
        await call.answer("Ошибка! Попробуйте начать заново.")
        return

    user_temp_data[chat_id]['repeat_interval'] = interval_seconds

    interval_name = [name for name, sec in REPEAT_INTERVALS.items() if sec == interval_seconds][0]

    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="❌ Отмена")]
    ])

    await call.message.delete()
    await bot.send_message(chat_id,
                           f"✅ Время: {user_temp_data[chat_id]['time_str']} ({user_temp_data[chat_id]['day_text']})\n"
                           f"🔄 Частота: {interval_name}\n\n"
                           f"📝 Теперь напишите **текст напоминания**:",
                           parse_mode="Markdown",
                           reply_markup=markup)

    user_temp_data[chat_id]['waiting_for_text'] = True
    await call.answer()


@dp.message(
    lambda message: message.chat.id in user_temp_data and user_temp_data[message.chat.id].get('waiting_for_text',
                                                                                              False))
async def get_reminder_text(message: types.Message):
    reminder_text = message.text.strip()
    chat_id = message.chat.id

    if reminder_text == "❌ Отмена":
        if chat_id in user_temp_data:
            del user_temp_data[chat_id]
        markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
            [KeyboardButton(text="📝 Установить напоминание")],
            [KeyboardButton(text="📋 Показать список напоминаний")],
            [KeyboardButton(text="🗑 Удалить напоминание")],
            [KeyboardButton(text="🔄 Управление повторами")]
        ])
        await bot.send_message(chat_id, "❌ Создание напоминания отменено", reply_markup=markup)
        return

    if not reminder_text:
        await bot.send_message(chat_id, "❌ Текст не может быть пустым! Напишите текст напоминания:")
        return

    reminder_datetime = user_temp_data[chat_id].get('reminder_time')
    repeat_interval = user_temp_data[chat_id].get('repeat_interval', 0)
    time_str = user_temp_data[chat_id].get('time_str')
    day_text = user_temp_data[chat_id].get('day_text')

    if not reminder_datetime:
        await bot.send_message(chat_id, "❌ Ошибка! Попробуйте установить напоминание заново.")
        if chat_id in user_temp_data:
            del user_temp_data[chat_id]
        return

    # Создаем задачу для первого напоминания
    task = asyncio.create_task(send_scheduled_reminder(chat_id, reminder_datetime, reminder_text, repeat_interval))

    if chat_id not in reminders:
        reminders[chat_id] = []

    reminder_id = len(reminders[chat_id])

    reminder_info = {
        'id': reminder_id,
        'time': reminder_datetime,
        'text': reminder_text,
        'task': task,
        'repeat_interval': repeat_interval,
        'repeat_task': None,
        'repeat_active': repeat_interval > 0
    }

    # Запускаем повторяющуюся задачу если интервал > 0
    if repeat_interval > 0:
        reminder_info['repeat_task'] = asyncio.create_task(
            repeat_reminder(chat_id, reminder_text, repeat_interval, reminder_id, reminder_datetime)
        )

    reminders[chat_id].append(reminder_info)

    if chat_id in user_temp_data:
        del user_temp_data[chat_id]

    markup = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
        [KeyboardButton(text="📝 Установить напоминание")],
        [KeyboardButton(text="📋 Показать список напоминаний")],
        [KeyboardButton(text="🗑 Удалить напоминание")],
        [KeyboardButton(text="🔄 Управление повторами")]
    ])


    if repeat_interval > 0:
        interval_name = [name for name, sec in REPEAT_INTERVALS.items() if sec == repeat_interval][0]
        repeat_text = f"\n🔄 Повтор: каждые {interval_name} (бесконечно)"
    else:
        repeat_text = "\n🔄 Повтор: отсутствует (одноразовое)"

    await bot.send_message(chat_id,
                           f"✅ **Напоминание успешно установлено!**\n\n"
                           f"🕐 Время первого напоминания: {time_str} ({day_text})\n"
                           f"📝 Текст: {reminder_text}{repeat_text}\n\n"
                           f"⚠️ **Важно:** Чтобы удалить напоминание, нажмите кнопку 'Удалить' в самом уведомлении!",
                           parse_mode="Markdown",
                           reply_markup=markup)


async def repeat_reminder(chat_id, text, interval_seconds, reminder_id, first_time=None):
    """Функция для бесконечного повторения напоминания"""
    try:
        # Если указано время первого запуска, ждем его
        if first_time:
            now = datetime.now()
            wait_seconds = (first_time - now).total_seconds()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            # Проверяем, существует ли еще напоминание после ожидания
            if chat_id not in reminders:
                return

            reminder_exists = False
            for reminder in reminders[chat_id]:
                if reminder['id'] == reminder_id:
                    reminder_exists = True
                    break

            if not reminder_exists:
                return

        # Бесконечный цикл повторений
        while True:
            await asyncio.sleep(interval_seconds)

            # Проверяем, существует ли еще напоминание
            if chat_id not in reminders:
                break

            reminder_exists = False
            for reminder in reminders[chat_id]:
                if reminder['id'] == reminder_id:
                    reminder_exists = True
                    break

            if not reminder_exists:
                break

            # Отправляем повторяющееся напоминание только с кнопкой удаления
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🗑 Удалить напоминание", callback_data=f"delete_repeat_{reminder_id}")]
            ])

            await bot.send_message(
                chat_id=chat_id,
                text=f"🔄 **ПОВТОРЯЮЩЕЕСЯ НАПОМИНАНИЕ!** 🔄\n\n"
                     f"📝 {text}\n\n"
                     f"⏰ Интервал: {interval_seconds} секунд\n\n"
                     f"⚠️ Это напоминание будет повторяться, пока вы не удалите его!",
                parse_mode="Markdown",
                reply_markup=markup
            )


            print(text)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Ошибка в repeat_reminder: {e}")


async def send_scheduled_reminder(chat_id, reminder_time, text, repeat_interval=0):
    """Функция для отправки напоминания в заданное время"""
    now = datetime.now()
    wait_seconds = (reminder_time - now).total_seconds()

    if wait_seconds > 0:
        await asyncio.sleep(wait_seconds)

    try:
        reminder_id = None
        if chat_id in reminders:
            for reminder in reminders[chat_id]:
                if reminder['time'] == reminder_time and reminder['text'] == text:
                    reminder_id = reminder['id']
                    break

        # Создаем кнопку удаления
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить напоминание", callback_data=f"delete_{reminder_id}")]
        ])

        # Если это напоминание с повтором
        if repeat_interval > 0:
            interval_name = [name for name, sec in REPEAT_INTERVALS.items() if sec == repeat_interval][0]
            await bot.send_message(
                chat_id=chat_id,
                text=f"🔔 **НАПОМИНАНИЕ!** 🔔\n\n"
                     f"⏰ Время: {reminder_time.strftime('%H:%M')}\n"
                     f"📝 {text}\n\n"
                     f"🔄 Это напоминание будет повторяться каждые {interval_name}\n\n"
                     f"⚠️ Нажмите 'Удалить напоминание', чтобы остановить повторы!",
                parse_mode="Markdown",
                reply_markup=markup
            )

            print(text)

        else:
            # Одноразовое напоминание
            await bot.send_message(
                chat_id=chat_id,
                text=f"🔔 **НАПОМИНАНИЕ!** 🔔\n\n⏰ Время: {reminder_time.strftime('%H:%M')}\n📝 {text}",
                parse_mode="Markdown",
                reply_markup=markup
            )

            # Удаляем одноразовое напоминание после отправки
            if chat_id in reminders:
                for reminder in reminders[chat_id][:]:
                    if reminder['time'] == reminder_time and reminder['text'] == text and reminder.get(
                            'repeat_interval', 0) == 0:
                        if reminder['task'] and not reminder['task'].done():
                            reminder['task'].cancel()
                        reminders[chat_id].remove(reminder)
                        break

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Ошибка при отправке напоминания: {e}")


@dp.message(lambda message: message.text == "📋 Показать список напоминаний")
async def show_reminders(message: types.Message):
    if message.chat.id not in reminders or not reminders[message.chat.id]:
        await bot.send_message(message.from_user.id, "📭 У вас нет активных напоминаний!")
        return

    response = "📋 **Ваши активные напоминания:**\n\n"
    now = datetime.now()

    for reminder in reminders[message.chat.id]:
        time_str = reminder['time'].strftime("%H:%M")
        date_str = reminder['time'].strftime("%d.%m.%Y")
        if reminder['time'].date() == now.date():
            date_display = f"сегодня в {time_str}"
        else:
            date_display = f"{date_str} в {time_str}"

        repeat_info = ""
        if reminder.get('repeat_interval', 0) > 0:
            interval_name = [name for name, sec in REPEAT_INTERVALS.items() if sec == reminder['repeat_interval']][0]
            repeat_info = f"\n   🔄 Повтор: каждые {interval_name} (бесконечно)\n   📌 Первое напоминание: {date_display}"
            date_display = "будет повторяться"

        response += f"🆔 ID: {reminder['id']}\n   🕐 {date_display}\n   📝 {reminder['text']}{repeat_info}\n\n"

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_reminders")]
    ])

    await bot.send_message(message.from_user.id, response, parse_mode="Markdown", reply_markup=markup)


@dp.message(lambda message: message.text == "🗑 Удалить напоминание")
async def delete_reminder_menu(message: types.Message):
    if message.chat.id not in reminders or not reminders[message.chat.id]:
        await bot.send_message(message.from_user.id, "📭 У вас нет активных напоминаний для удаления!")
        return

    keyboard = []
    for reminder in reminders[message.chat.id]:
        time_str = reminder['time'].strftime("%H:%M")
        repeat_mark = "🔄" if reminder.get('repeat_interval', 0) > 0 else "🔔"
        button_text = f"{repeat_mark} {time_str} - {reminder['text'][:25]}"
        keyboard.append([InlineKeyboardButton(text=button_text, callback_data=f"del_{reminder['id']}")])

    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await bot.send_message(message.from_user.id, "🗑 Выберите напоминание для удаления:", reply_markup=markup)


@dp.callback_query(lambda call: call.data.startswith("del_"))
async def delete_specific_reminder(call: types.CallbackQuery):
    reminder_id = int(call.data.split("_")[1])
    chat_id = call.message.chat.id

    if chat_id in reminders:
        for reminder in reminders[chat_id]:
            if reminder['id'] == reminder_id:
                if reminder['task'] and not reminder['task'].done():
                    reminder['task'].cancel()

                if reminder.get('repeat_task') and reminder['repeat_task'] and not reminder['repeat_task'].done():
                    reminder['repeat_task'].cancel()

                reminders[chat_id].remove(reminder)

                repeat_text = "с повторением" if reminder.get('repeat_interval', 0) > 0 else "одноразовое"
                await call.message.edit_text(
                    f"✅ Напоминание ({repeat_text}) удалено!\n\n🕐 {reminder['time'].strftime('%H:%M')}\n📝 {reminder['text']}")
                await call.answer()

                if not reminders[chat_id]:
                    await call.message.answer("📭 Теперь у вас нет активных напоминаний.")
                return

    await call.message.edit_text("❌ Напоминание не найдено!")
    await call.answer()


@dp.callback_query(lambda call: call.data == "cancel_delete")
async def cancel_delete(call: types.CallbackQuery):
    await call.message.edit_text("❌ Удаление отменено")
    await call.answer()


@dp.callback_query(lambda call: call.data == "close_reminders")
async def close_reminders(call: types.CallbackQuery):
    await call.message.delete()
    await call.answer()


# Обработчик для кнопки "Удалить" из уведомлений (одноразовые)
@dp.callback_query(lambda call: call.data.startswith("delete_") and not call.data.startswith("delete_repeat_"))
async def delete_from_notification(call: types.CallbackQuery):
    reminder_id = int(call.data.split("_")[1])
    chat_id = call.message.chat.id

    if chat_id in reminders:
        for reminder in reminders[chat_id]:
            if reminder['id'] == reminder_id:
                if reminder['task'] and not reminder['task'].done():
                    reminder['task'].cancel()
                if reminder.get('repeat_task') and reminder['repeat_task'] and not reminder['repeat_task'].done():
                    reminder['repeat_task'].cancel()
                reminders[chat_id].remove(reminder)
                await call.message.edit_text("🗑 Напоминание удалено!", reply_markup=None)
                await call.answer()
                return

    await call.message.edit_text("❌ Напоминание уже было удалено", reply_markup=None)
    await call.answer()


# Обработчик для кнопки "Удалить" из уведомлений (повторяющиеся)
@dp.callback_query(lambda call: call.data.startswith("delete_repeat_"))
async def delete_repeat_from_notification(call: types.CallbackQuery):
    reminder_id = int(call.data.split("_")[2])
    chat_id = call.message.chat.id

    if chat_id in reminders:
        for reminder in reminders[chat_id]:
            if reminder['id'] == reminder_id:
                if reminder['task'] and not reminder['task'].done():
                    reminder['task'].cancel()
                if reminder.get('repeat_task') and reminder['repeat_task'] and not reminder['repeat_task'].done():
                    reminder['repeat_task'].cancel()
                reminders[chat_id].remove(reminder)
                await call.message.edit_text("✅ Повторяющееся напоминание полностью удалено!", reply_markup=None)
                await call.answer()
                return

    await call.message.edit_text("❌ Напоминание уже было удалено", reply_markup=None)
    await call.answer()


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':

    asyncio.run(main())