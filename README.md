# 🧠 Syntia.ai

![Version V2.01 BETA](https://img.shields.io/badge/Version-V2.01%20BETA-blueviolet?style=for-the-badge)
![Python](https://img.shields.io/badge/Made%20with-Python-blue?style=for-the-badge&logo=python&logoColor=white)
![AI](https://img.shields.io/badge/Powered%20by-Llama%203.1-orange?style=for-the-badge)
![Website V4.0 STABLE](https://img.shields.io/badge/Website-V4.0%20STABLE-success?style=for-the-badge)

> **L'alliance ultime entre Business, Gaming et Intelligence Artificielle.**

🌐 **Site Web & Documentation :** [https://syntia-ai.drt-hbr.sbs](https://syntia-ai.drt-hbr.sbs)

---

## 📜 À propos

**Syntia** est un écosystème centré autour d'un **Bot Discord intelligent** et d'une communauté active. Le projet vise à fusionner les mondes du business et du jeu vidéo à travers une infrastructure sécurisée et une IA conversationnelle avancée.

Actuellement en version **v2.01 (Beta)**, Syntia propose une gestion de serveur automatisée, des logs avancés et se prépare à déployer des capacités conversationnelles neuronales.

## ✨ Fonctionnalités

### 🚀 Actuellement Déployé
- **Infinity Panel (v40)** : Architecture centrale du bot. Gestion des rôles, logs avancés et "sécurité neuronale" pour protéger le serveur.
- **Bot Discord** : Structure IA complete avec chatbot intégré
- **Système de Logs** : Suivi des événements du serveur en temps réel.
- **Keep Alive** : Script pour maintenir le bot actif 24/7 (via Uptime Robot).

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
├── bot_gestion.py      # Scripts de gestion / pannel de gestion de bot
├── panel.py            # Interface du panneau de contrôle (Infinity Panel)
├── feed.json           # Données/Configuration des fichier RSS (flux d'actualité [totalement personalisable])
├── keep_alive.py       # Serveur web léger pour le maintien en ligne (Ping)
└── requirements.txt    # Liste des dépendances Python
```

🔒 Confidentialité & Sécurité
La protection des données est primordiale chez Syntia :

Données Techniques : Seuls les ID (Serveur, Channel, Admin) sont stockés pour le fonctionnement. (prochainement introduction du stockage de ces valeurs directement via l'hebergeur) 

Pas de Logs de Conversation : Syntia n'enregistre aucune conversation, tout est traité en RAM.

Sécurité API : Les clés (Groq, Llama) sont chiffrées dans les variables d'environnement (ex: Render Cloud).

## 👤 Auteur & Team

**DRT-HBR** | **Team :** drt-hbr, Amaury (Directeur)
* GitHub: [@hugobrt](https://github.com/hugobrt)
* Site Web: [Syntia.ai](https://hugobrt.github.io/syntia.ai/)

© 2026 Syntia.ai - Tous droits réservés.
