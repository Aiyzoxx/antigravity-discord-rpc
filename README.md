# Antigravity 2.0 - Discord Rich Presence (RPC)

Watcher autonome pour afficher en direct votre activité Antigravity 2.0 sur votre profil Discord.

## Fonctionnalités
- **Détection automatique** du processus Antigravity 2.0 (`Antigravity.exe`).
- **Affichage du projet** : extrait automatiquement le nom du workspace actif (`Projet: nom-projet`).
- **Statut en temps réel** :
  - Outil en cours d'exécution (terminal, édition de fichier, recherche web...).
  - Réflexion du modèle ("Réflexion Gemini...").
  - Statut en attente ("En attente d'instruction").
- **Nettoyage automatique** à la fermeture d'Antigravity.
- **Client ID et logos intégrés** : prêt à l'emploi (logo officiel Antigravity + badge robot).

## Lancement

### Mode console (pour tester) :
Double-clic sur `start_rpc.bat`.

### Mode silencieux (arrière-plan) :
Double-clic sur `start_rpc_background.vbs`.

### Arrêt du mode silencieux :
Double-clic sur `stop_rpc.bat`.

## Configuration (`config.json`)
- `client_id` : ID d'application Discord (par défaut configuré avec le logo Antigravity).
- `poll_interval` : Fréquence de rafraîchissement en secondes (par défaut `3`).
- `language` : Langue des statuts (`"fr"` ou `"en"`).
- `show_project` : Afficher le nom du workspace (`true` / `false`).
