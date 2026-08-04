import json
import re
from datetime import datetime
from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


def transcribe_audio(voice_path):
    """Распознает голосовое сообщение через Whisper"""
    with open(voice_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
    return transcript.text


def parse_call_summary(text):
    """Анализирует текст звонка через GPT"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    system_prompt = f"""Ты — AI-ассистент для CRM. Проанализируй текст звонка с клиентом и извлеки структурированную информацию.

Ответь СТРОГО в формате JSON:
{{
    "client_name": "Имя клиента или компании",
    "phone": "Телефон если есть, иначе null",
    "company": "Название компании если есть, иначе null",
    "summary": "Краткое содержание разговора (2-3 предложения)",
    "agreements": "О чем договорились",
    "next_action": "Что нужно сделать дальше",
    "call_back_date": "Дата следующего звонка в формате YYYY-MM-DD или null",
    "call_back_time": "Время звонка в формате HH:MM или null",
    "notes": "Дополнительные заметки или null"
}}

Если дата не указана явно (например 'завтра', 'через неделю', 'в понедельник'), вычисли реальную дату относительно сегодня.
Сегодня: {today}
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        temperature=0.3
    )
    
    content = response.choices[0].message.content
    json_match = re.search(r'\{{.*\}}', content, re.DOTALL)
    
    if json_match:
        return json.loads(json_match.group())
    return None


def generate_call_script(client_name, last_agreements):
    """Генерирует скрипт для следующего звонка"""
    prompt = f"""Подготовь краткий скрипт для звонка клиенту {client_name}.
Последние договоренности: {last_agreements}

Напиши 3-4 пункта: с чего начать разговор, о чем напомнить, какие вопросы задать."""
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Ты — помощник по продажам. Пиши кратко и по делу."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    
    return response.choices[0].message.content


def format_report(client_name, summary, agreements, next_action, reminder_date):
    report = f"""
📞 *Отчет о звонке*

👤 *Клиент:* {client_name}

📝 *О чем говорили:*
{summary}

🤝 *Договоренности:*
{agreements}

➡️ *Следующий шаг:*
{next_action}
"""
    if reminder_date:
        report += f"\n⏰ *Напоминание:* {reminder_date}"
    return report