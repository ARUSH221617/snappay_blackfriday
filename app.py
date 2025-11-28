from flask import Flask, render_template, request, jsonify, Response
import threading
import queue
import time
import json
from main import SnappBot
import os

app = Flask(__name__)

# --- Global State ---
class BotManager:
    def __init__(self):
        self.bot = None
        self.log_queue = queue.Queue()
        self.input_queue = queue.Queue()
        self.input_needed = False
        self.input_prompt = ""
        self.is_running = False
        self.thread = None

    def log_handler(self, message):
        print(f"[BOT] {message}")
        self.log_queue.put(message)

    def input_handler(self, prompt):
        self.input_needed = True
        self.input_prompt = prompt
        self.log_handler(f"WAITING FOR INPUT: {prompt}")

        # Block until input is received
        user_input = self.input_queue.get()

        self.input_needed = False
        self.input_prompt = ""
        self.log_handler(f"INPUT RECEIVED: {user_input}")
        return user_input

    def start_bot(self):
        if self.is_running:
            return False

        self.is_running = True
        self.bot = SnappBot(input_handler=self.input_handler, log_handler=self.log_handler)

        def run_wrapper():
            try:
                self.bot.run()
            except Exception as e:
                self.log_handler(f"CRITICAL ERROR: {e}")
            finally:
                self.is_running = False
                self.log_handler("Bot execution finished.")

        self.thread = threading.Thread(target=run_wrapper)
        self.thread.start()
        return True

    def send_input(self, value):
        if self.input_needed:
            self.input_queue.put(value)
            return True
        return False

    def get_logs(self):
        logs = []
        while not self.log_queue.empty():
            logs.append(self.log_queue.get())
        return logs

bot_manager = BotManager()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start():
    if bot_manager.start_bot():
        return jsonify({"status": "started"})
    return jsonify({"status": "already_running"}), 400

@app.route('/api/input', methods=['POST'])
def send_input():
    data = request.json
    value = data.get('value')
    if bot_manager.send_input(value):
        return jsonify({"status": "input_sent"})
    return jsonify({"status": "not_waiting_for_input"}), 400

@app.route('/api/status')
def status():
    return jsonify({
        "running": bot_manager.is_running,
        "waiting_for_input": bot_manager.input_needed,
        "input_prompt": bot_manager.input_prompt
    })

@app.route('/api/logs')
def logs():
    return jsonify({"logs": bot_manager.get_logs()})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
