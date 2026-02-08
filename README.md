# 🧠 Syntia.ai

![Version](https://img.shields.io/badge/version-4.0%20BETA-blueviolet?style=for-the-badge)
![Python](https://img.shields.io/badge/Made%20with-Python-blue?style=for-the-badge&logo=python&logoColor=white)
![AI](https://img.shields.io/badge/Powered%20by-Llama%203.1-orange?style=for-the-badge)

> **L'alliance ultime entre Business, Gaming et Intelligence Artificielle.**

🌐 **Site Web & Documentation :** [https://hugobrt.github.io/syntia.ai/](https://hugobrt.github.io/syntia.ai/)

---

## 📜 À propos

**Syntia** est un écosystème centré autour d'un **Bot Discord intelligent** et d'une communauté active. Le projet vise à fusionner les mondes du business et du jeu vidéo à travers une infrastructure sécurisée et une IA conversationnelle avancée.

Actuellement en version **v4.0 (Beta)**, Syntia propose une gestion de serveur automatisée, des logs avancés et se prépare à déployer des capacités conversationnelles neuronales.

## ✨ Fonctionnalités

### 🚀 Actuellement Déployé
- **Infinity Panel (v4.0)** : Architecture centrale du bot. Gestion des rôles, logs avancés et "sécurité neuronale" pour protéger le serveur.
- **Bot Discord** : Structure complète et configuration du serveur communautaire.
- **Système de Logs** : Suivi des événements du serveur en temps réel.
- **Keep Alive** : Script pour maintenir le bot actif 24/7 (via Render/Uptime).

### 🛠 En Développement (Roadmap)
- [x] **Chat Bot IA (80%)** : Intégration de **Llama 3.1** (via Groq) pour une IA conversationnelle ultra-rapide.
- [ ] **Web Dashboard (30%)** : Interface web pour gérer les paramètres du bot sans ligne de commande.
- [ ] **Auto Convert Devise (10%)** : Module financier pour la conversion de devises en temps réel.
- [ ] **Panel Modo** : Outils de modération avancés (accès restreint).

## 📂 Structure du Projet

Voici un aperçu des fichiers clés du repository :

```bash
syntia.ai/
├── bot2.py             # Cœur du bot Discord (Main Logic)
├── bot_gestion.py      # Scripts de gestion et commandes administratives
├── panel.py            # Interface du panneau de contrôle (Infinity Panel)
├── feed.json           # Données/Configuration dynamiques
├── keep_alive.py       # Serveur web léger pour le maintien en ligne (Ping)
└── requirements.txt    # Liste des dépendances Python
