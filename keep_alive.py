from flask import Flask, jsonify, request
from flask_cors import CORS # Indispensable pour le site
from threading import Thread
import logging

app = Flask('')
CORS(app)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- MÉMOIRE ---
bot_stats = { "status": "DÉMARRAGE...", "members": 0, "ping": 0, "ai_requests": 0, "revenue": "0" }

# C'EST ÇA QU'IL TE MANQUAIT : La liste vide pour les salons et membres
bot_data = {
    "channels": [],
    "members": []
}

bot_logs = []
command_queue = [] 

@app.route('/')
def home(): return "I'm alive!"

@app.route('/api/stats')
def api_stats(): return jsonify(bot_stats)

@app.route('/api/logs')
def api_logs(): return jsonify(bot_logs[-20:])

# C'EST ÇA QU'IL TE MANQUAIT : La route pour que le site récupère les listes
@app.route('/api/lists')
def api_lists():
    return jsonify(bot_data)

@app.route('/api/execute', methods=['POST'])
def api_execute():
    try:
        data = request.json
        command_queue.append(data)
        bot_logs.append(f"[WEB] Commande reçue : {data.get('action')}")
        return jsonify({"status": "OK"})
    except: return jsonify({"status": "Erreur"}), 400

def run(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): t = Thread(target=run); t.start()
