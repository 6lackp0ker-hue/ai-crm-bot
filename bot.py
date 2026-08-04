import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from config import TELEGRAM_BOT_TOKEN, DATABASE_NAME
from database import (
    init_db, add_client, get_client_by_name, get_client_by_id,
    get_all_clients, add_interaction, get_pending_reminders,
    mark_reminder_sent, get_client_history, get_statistics, get_last_interaction
)
from ai_helper import transcribe_audio, parse_call_summary, generate_call_script, format_report

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

ADMIN_CHAT_ID = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global ADMIN_CHAT_ID
    ADMIN_CHAT_ID = update.effective_chat.id

    welcome = """
🤖 *AI-Помощник для CRM*

Привет! Я помогу вести базу клиентов и напоминать о звонках.

*Как пользоваться:*
1. Отправь мне голосовое сообщение после звонка
2. Я сам извлеку всю информацию и сохраню в базу
3. Пришлю напоминание, когда нужно перезвонить

*Команды:*
📋 /clients — список клиентов
📊 /stats — статистика
🔍 /history [имя] — история по клиенту
⏰ /reminders — активные напоминания
❓ /help — помощь
"""
    await update.message.reply_text(welcome, parse_mode='Markdown')


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
*Команды:*

🎤 *Отправь голосовое* — сохраню отчет о звонке

📋 /clients — все клиенты
📊 /stats — статистика
🔍 /history Имя — история звонков
⏰ /reminders — активные напоминания
📝 /add Имя Телефон — добавить клиента
"""
    await update.message.reply_text(text, parse_mode='Markdown')


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎙️ Слушаю и распознаю...")

    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)

        voice_path = f"voice_{update.message.message_id}.ogg"
        await file.download_to_drive(voice_path)

        text = transcribe_audio(voice_path)
        os.remove(voice_path)

        await update.message.reply_text(f"📝 *Распознано:*\n_{text}_", parse_mode='Markdown')
        await update.message.reply_text("🧠 Анализирую...")

        parsed = parse_call_summary(text)

        if not parsed:
            await update.message.reply_text("❌ Не удалось распознать структуру. Попробуй написать текстом.")
            return

        clients = get_client_by_name(parsed['client_name'])
        if clients:
            client_id = clients[0][0]
        else:
            client_id = add_client(
                name=parsed['client_name'],
                phone=parsed.get('phone'),
                company=parsed.get('company'),
                notes=parsed.get('notes')
            )
            await update.message.reply_text(f"✅ Новый клиент: *{parsed['client_name']}*", parse_mode='Markdown')

        reminder_date = None
        if parsed.get('call_back_date'):
            time = parsed.get('call_back_time', '10:00')
            reminder_date = f"{parsed['call_back_date']} {time}:00"

        add_interaction(
            client_id=client_id,
            summary=parsed['summary'],
            agreements=parsed['agreements'],
            next_action=parsed['next_action'],
            reminder_date=reminder_date
        )

        report = format_report(
            parsed['client_name'],
            parsed['summary'],
            parsed['agreements'],
            parsed['next_action'],
            reminder_date
        )

        keyboard = [
            [InlineKeyboardButton("📞 Скрипт звонка", callback_data=f"script_{client_id}")],
            [InlineKeyboardButton("📋 История", callback_data=f"history_{client_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(report, parse_mode='Markdown', reply_markup=reply_markup)

        if reminder_date:
            await update.message.reply_text(
                f"⏰ Напомню позвонить *{parsed['client_name']}* {reminder_date}",
                parse_mode='Markdown'
            )

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}\n\nПопробуй отправить текстом.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith('/'):
        return

    await update.message.reply_text("🧠 Анализирую текст...")

    try:
        parsed = parse_call_summary(text)

        if not parsed:
            await update.message.reply_text("❌ Не распознал структуру. Уточни: с кем, о чем, когда перезвонить.")
            return

        clients = get_client_by_name(parsed['client_name'])
        if clients:
            client_id = clients[0][0]
        else:
            client_id = add_client(
                name=parsed['client_name'],
                phone=parsed.get('phone'),
                company=parsed.get('company')
            )
            await update.message.reply_text(f"✅ Новый клиент: *{parsed['client_name']}*", parse_mode='Markdown')

        reminder_date = None
        if parsed.get('call_back_date'):
            time = parsed.get('call_back_time', '10:00')
            reminder_date = f"{parsed['call_back_date']} {time}:00"

        add_interaction(
            client_id=client_id,
            summary=parsed['summary'],
            agreements=parsed['agreements'],
            next_action=parsed['next_action'],
            reminder_date=reminder_date
        )

        report = format_report(
            parsed['client_name'],
            parsed['summary'],
            parsed['agreements'],
            parsed['next_action'],
            reminder_date
        )

        keyboard = [
            [InlineKeyboardButton("📞 Скрипт звонка", callback_data=f"script_{client_id}")],
            [InlineKeyboardButton("📋 История", callback_data=f"history_{client_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(report, parse_mode='Markdown', reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def clients_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clients = get_all_clients()
    if not clients:
        await update.message.reply_text("📭 База пуста")
        return

    text = "📋 *Клиенты:*\n\n"
    for c in clients:
        text += f"👤 *{c[1]}*\n"
        if c[3]:
            text += f"   🏢 {c[3]}\n"
        if c[2]:
            text += f"   📞 {c[2]}\n"
        text += "\n"

    await update.message.reply_text(text, parse_mode='Markdown')


async def statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_statistics()
    text = f"""
📊 *Статистика*

👥 Клиентов: {stats['total_clients']}
📞 Звонков: {stats['total_interactions']}
⏰ Напоминаний: {stats['pending_reminders']}
"""
    await update.message.reply_text(text, parse_mode='Markdown')


async def client_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❓ Формат: /history Имя")
        return

    name = ' '.join(context.args)
    clients = get_client_by_name(name)

    if not clients:
        await update.message.reply_text(f"❌ Клиент '{name}' не найден")
        return

    client = clients[0]
    history = get_client_history(client[0])

    if not history:
        await update.message.reply_text(f"📭 История с {client[1]} пуста")
        return

    text = f"📋 *История с {client[1]}:*\n\n"
    for h in history:
        text += f"📅 {h[0]}\n📝 {h[1]}\n🤝 {h[2]}\n"
        if h[4]:
            text += f"⏰ {h[4]}\n"
        text += "\n"

    await update.message.reply_text(text, parse_mode='Markdown')


async def reminders_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reminders = get_pending_reminders()
    if not reminders:
        await update.message.reply_text("✅ Нет активных напоминаний")
        return

    text = "⏰ *Активные напоминания:*\n\n"
    for r in reminders:
        text += f"🔔 {r[3]}\n📅 {r[2]}\n📝 {r[1]}\n\n"

    await update.message.reply_text(text, parse_mode='Markdown')


async def add_client_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❓ Формат: /add Имя [Телефон]")
        return

    name = context.args[0]
    phone = context.args[1] if len(context.args) > 1 else None
    client_id = add_client(name=name, phone=phone)
    await update.message.reply_text(f"✅ Клиент *{name}* добавлен", parse_mode='Markdown')


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    action, id_val = data.split('_', 1)
    id_val = int(id_val)

    if action == "script":
        client = get_client_by_id(id_val)
        if client:
            last = get_last_interaction(id_val)
            script = generate_call_script(client[1], last or "Нет данных")
            await query.edit_message_text(f"📞 *Скрипт ({client[1]}):*\n\n{script}", parse_mode='Markdown')

    elif action == "history":
        client = get_client_by_id(id_val)
        if not client:
            return

        history = get_client_history(id_val)
        if not history:
            await query.edit_message_text(f"📭 История с {client[1]} пуста")
            return

        text = f"📋 *История с {client[1]}:*\n\n"
        for h in history:
            text += f"📅 {h[0]}\n📝 {h[1]}\n🤝 {h[2]}\n\n"

        await query.edit_message_text(text, parse_mode='Markdown')


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    global ADMIN_CHAT_ID
    if not ADMIN_CHAT_ID:
        return

    reminders = get_pending_reminders()
    for r in reminders:
        text = f"""
⏰ *НАПОМИНАНИЕ!*

🔔 {r[3]}
📝 {r[1]}
📅 {r[2]}

Не забудь позвонить!
"""
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode='Markdown')
            mark_reminder_sent(r[0])
        except Exception as e:
            logger.error(f"Ошибка напоминания: {e}")


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    global ADMIN_CHAT_ID
    if not ADMIN_CHAT_ID:
        return

    reminders = get_pending_reminders()
    for r in reminders:
        text = f"""
⏰ *НАПОМИНАНИЕ!*

🔔 {r[3]}
📝 {r[1]}
📅 {r[2]}

Не забудь позвонить!
"""
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text, parse_mode='Markdown')
            mark_reminder_sent(r[0])
        except Exception as e:
            logger.error(f"Ошибка напоминания: {e}")


def main():
    init_db()
    print("✅ База данных готова")

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("clients", clients_list))
    application.add_handler(CommandHandler("stats", statistics))
    application.add_handler(CommandHandler("history", client_history))
    application.add_handler(CommandHandler("reminders", reminders_list))
    application.add_handler(CommandHandler("add", add_client_manual))

    # Сообщения
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # Кнопки
    application.add_handler(CallbackQueryHandler(button_callback))

    # Напоминания каждые 5 минут
    job_queue = application.job_queue
    job_queue.run_repeating(check_reminders, interval=300, first=10)

    print("🤖 Бот запущен! Отправь /start в Telegram")
    application.run_polling()


if __name__ == '__main__':
    main()


if __name__ == '__main__':
    main()