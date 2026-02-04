from flask import Flask, jsonify
from flask_cors import CORS
from threading import Thread
import logging

app = Flask('')
CORS(app) # Autorise ton site Admin à lire les données

# On cache les logs techniques dans la console
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- LE COFFRE-FORT (Données partagées) ---
# Le bot viendra écrire ici, et le site viendra lire ici.
bot_stats = {
    "status": "DÉMARRAGE...",
    "members": 0,
    "ping": 0,
    "ai_requests": 0,
    "revenue": "0"
}
bot_logs = []

# --- ROUTE 1 : Pour UptimeRobot (Touche pas à ça !) ---
@app.route('/')
def home():
    return "I'm alive! Syntia is running."

# --- ROUTE 2 : Pour ton Panel (Stats) ---
@app.route('/api/stats')
def api_stats():
    return jsonify(bot_stats)

# --- ROUTE 3 : Pour ton Panel (Logs) ---
@app.route('/api/logs')
def api_logs():
    return jsonify(bot_logs[-20:]) # Renvoie les 20 derniers logs

# --- ROUTE 4 : Commande d'arrêt ---
@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    # On ajoute un log pour dire qu'on a reçu l'ordre
    bot_logs.append("[PANEL] Demande d'arrêt d'urgence reçue.")
    return jsonify({"status": "Signal reçu"})

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
