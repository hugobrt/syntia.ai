from flask import Flask, jsonify, request
from flask_cors import CORS
from threading import Thread
import logging

app = Flask('')
CORS(app)

# On cache les logs techniques
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- MÉMOIRE PARTAGÉE ---
bot_stats = {
    "status": "DÉMARRAGE...",
    "members": 0,
    "ping": 0,
    "ai_requests": 0,
    "revenue": "0"
}
bot_logs = []

# --- LA BOÎTE AUX LETTRES (COMMANDES) ---
# Le site web écrit ici, le bot lit ici.
command_queue = [] 

# --- ROUTE UPTIMEROBOT (INDISPENSABLE) ---
@app.route('/')
def home():
    return "I'm alive! Syntia Core running."

# --- API STATS ---
@app.route('/api/stats')
def api_stats():
    return jsonify(bot_stats)

# --- API LOGS ---
@app.route('/api/logs')
def api_logs():
    return jsonify(bot_logs[-20:])

# --- API RÉCEPTION D'ORDRES (DU SITE) ---
@app.route('/api/execute', methods=['POST'])
def api_execute():
    try:
        data = request.json
        command_queue.append(data) # On met l'ordre dans la file
        bot_logs.append(f"[WEB] Commande reçue : {data.get('action')}")
        return jsonify({"status": "Ordre reçu"})
    except:
        return jsonify({"status": "Erreur"}), 400

# --- API SHUTDOWN ---
@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    command_queue.append({"action": "shutdown"})
    return jsonify({"status": "Signal reçu"})

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
