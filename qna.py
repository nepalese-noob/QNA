from flask import Flask, request
import telebot
import re
import threading
import time
import random
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_TOKEN = os.getenv('API_TOKEN')  # Ensure to set API_TOKEN in your Render environment
QA_FILE = 'qa.txt'
CHAT_ID = int(os.getenv('CHAT_ID', -1001597616235))  # Your group chat ID from environment or fallback
bot = telebot.TeleBot(API_TOKEN, parse_mode='MarkdownV2')

# Flask App
app = Flask(__name__)

# File I/O for Q&A
def read_qa_pairs():
    try:
        with open(QA_FILE, 'r', encoding='utf-8') as f:
            return [(q.strip(), a.strip()) for line in f if '=' in line for q, a in [line.split('=', 1)]]
    except FileNotFoundError:
        return []

def save_qa_pairs(qa_pairs):
    existing_pairs = read_qa_pairs()
    unique_pairs = [pair for pair in qa_pairs if pair not in existing_pairs]
    with open(QA_FILE, 'a', encoding='utf-8') as f:
        for question, answer in unique_pairs:
            f.write(f'{question} = {answer}\n')

def delete_qa_pair(question):
    qa_pairs = read_qa_pairs()
    qa_pairs = [(q, a) for q, a in qa_pairs if q != question.strip()]
    with open(QA_FILE, 'w', encoding='utf-8') as f:
        for q, a in qa_pairs:
            f.write(f'{q} = {a}\n')

# Parse Q&A from messages
def parse_qa_message(message):
    qa_pattern = re.compile(r'(.+?)[👉=⇒→÷>](.+)')
    return [(match.group(1).strip(), match.group(2).strip()) for line in message.split('\n') if (match := qa_pattern.search(line))]

# Markdown Escaping
def escape_markdown_v2(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# Q&A Thread Logic
stop_thread = False
qa_frequency = 1200  # Default frequency

def send_qa_pairs():
    global stop_thread
    while not stop_thread:
        try:
            qa_pairs = read_qa_pairs()
            if qa_pairs and CHAT_ID:
                question, answer = random.choice(qa_pairs)
                bot.send_message(CHAT_ID, f'{escape_markdown_v2(question)} 👉 ||{escape_markdown_v2(answer)}||')
            time.sleep(qa_frequency)  # Use the updated frequency
        except Exception as e:
            print(f"Error in Q&A thread: {e}")
            time.sleep(5)  # Prevent rapid retries if an error occurs

def restart_qa_thread():
    global stop_thread, qa_thread
    stop_thread = True
    if qa_thread.is_alive():
        qa_thread.join()  # Wait for the current thread to finish
    stop_thread = False
    qa_thread = threading.Thread(target=send_qa_pairs)
    qa_thread.start()

# Function to ignore YouTube and Facebook links
def contains_links(message):
    urls = ['youtube', 'youtu.be', 'facebook.com', 'fb.com']
    return any(url in message for url in urls)

# Bot Handlers
@bot.message_handler(func=lambda message: not message.text.startswith('/') and not contains_links(message.text))
def handle_message(message):
    qa_pairs = parse_qa_message(message.text)
    if qa_pairs:
        save_qa_pairs(qa_pairs)
        bot.reply_to(message, escape_markdown_v2("Q&A pairs saved."))
    else:
        bot.reply_to(message, escape_markdown_v2("No Q&A pairs found."))

@bot.message_handler(commands=['delete'])
def handle_delete(message):
    try:
        _, question = message.text.split(' ', 1)
        delete_qa_pair(question)
        bot.reply_to(message, escape_markdown_v2("Q&A pair deleted if it existed."))
    except ValueError:
        bot.reply_to(message, escape_markdown_v2("Please provide the question to delete."))

@bot.message_handler(commands=['frequency'])
def handle_frequency(message):
    global qa_frequency
    try:
        _, frequency = message.text.split(' ', 1)
        qa_frequency = int(frequency.strip())
        restart_qa_thread()  # Restart the thread with the new frequency
        bot.reply_to(message, escape_markdown_v2(f"Frequency set to {qa_frequency} seconds."))
    except ValueError:
        bot.reply_to(message, escape_markdown_v2("Please provide a valid number."))

@bot.message_handler(commands=['stop'])
def handle_stop(message):
    global stop_thread
    stop_thread = True
    bot.reply_to(message, escape_markdown_v2("Q&A thread stopped."))

@bot.message_handler(commands=['start'])
def handle_start(message):
    global stop_thread, qa_thread
    if not qa_thread.is_alive():
        stop_thread = False
        qa_thread = threading.Thread(target=send_qa_pairs)
        qa_thread.start()
        bot.reply_to(message, escape_markdown_v2("Q&A thread started."))
    else:
        bot.reply_to(message, escape_markdown_v2("Q&A thread is already running."))

# Flask Webhook Routes
@app.route('/')
def home():
    return "Q&A Bot is running!"

@app.route(f'/{API_TOKEN}', methods=['POST'])
def telegram_webhook():
    json_update = request.get_json()
    update = telebot.types.Update.de_json(json_update)
    bot.process_new_updates([update])
    return "OK", 200

# Main App Entry Point
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
    
