# GameStats

Dashboard auto-hébergé de suivi du temps de jeu : un agent Windows détecte les
jeux lancés en temps réel, le backend synchronise aussi la bibliothèque Steam
(temps de jeu, succès) et enrichit les fiches avec IGDB (jaquettes HD, genres).

## Fonctionnalités

- **Sessions en temps réel** — l'agent Windows envoie un heartbeat toutes les
  30 s ; le backend ouvre, prolonge et clôture automatiquement les sessions.
- **Heatmap annuelle** — temps de jeu par jour de la semaine et par heure, dans
  le fuseau configuré (`Europe/Paris` par défaut).
- **Top jeux** — classement des 30 derniers jours, temps suivi et temps total
  Steam.
- **Bibliothèque Steam** — synchronisation de la bibliothèque toutes les
  15 minutes, temps de jeu, derniers lancements, succès débloqués.
- **Jaquettes & genres IGDB** — enrichissement automatique des jeux sans
  visuel, sans bloquer le reste de l'application.
- **Interface sombre responsive** — thème sombre par défaut et thème clair
  commutable depuis l'en-tête, préférence conservée dans le navigateur.

## Démarrage rapide

```bash
cp .env.example .env
# Éditez .env : au minimum AGENT_API_KEY.
docker compose up -d --build
```

| Service     | URL                            |
| ----------- | ------------------------------ |
| Dashboard   | http://localhost:8090          |
| API / docs  | http://localhost:8091/docs     |
| Healthcheck | http://localhost:8091/api/health |

Les ports hôtes sont configurables via `FRONTEND_PORT` et `BACKEND_PORT` dans
`.env` (8090 et 8091 par défaut, pour éviter les ports 8080/8000 souvent
occupés). Le port backend doit rester joignable depuis le PC Windows de
l'agent.

Les données SQLite sont conservées dans `./data/gamestats.db` (volume monté
dans le conteneur backend).

### Configuration minimale

```dotenv
AGENT_API_KEY=une-clé-longue-et-aléatoire
TIMEZONE=Europe/Paris
```

Générez une clé avec `openssl rand -hex 24` (ou équivalent PowerShell). La
valeur doit être **identique** dans `.env` et dans la configuration de l'agent.

### Steam (optionnel)

1. Créez une clé API sur https://steamcommunity.com/dev/apikey.
2. Récupérez votre SteamID64 sur https://steamid.io/.
3. Vérifiez que **Profil public** et **Détails de jeu publics** sont activés.
4. Renseignez `STEAM_API_KEY` et `STEAM_ID`, puis `docker compose up -d`.

Sans Steam, l'application fonctionne uniquement avec les sessions de l'agent.
Le premier import Steam ne crée pas de fausses sessions : il enregistre un
instantané de référence. Les synchronisations suivantes transforment les
deltas de temps de jeu en sessions approximatives, sauf si l'agent a déjà
couvert la même période (pour éviter le double comptage).

### IGDB (optionnel)

1. Créez une application sur https://dev.twitch.tv/console/apps.
2. Renseignez `IGDB_CLIENT_ID` et `IGDB_CLIENT_SECRET`.
3. Redémarrez : les jeux sans jaquette sont enrichis par lots (8/heure par
   défaut).

Les succès Steam sont récupérés pour les jeux les plus récemment joués, avec
un rafraîchissement au plus toutes les 6 heures.

## Agent Windows

Prérequis : Python 3.10+ et un PC Windows sur le même réseau que le backend.

```powershell
cd agent-windows
py -m pip install -r requirements.txt

# Test unique (le backend doit être joignable)
py tracker.py `
  --server http://192.168.1.20:8091 `
  --key "LA_MEME_CLE_QUE_AGENT_API_KEY" `
  --once

# Exécution continue
py tracker.py `
  --server http://192.168.1.20:8091 `
  --key "LA_MEME_CLE_QUE_AGENT_API_KEY"
```

L'agent peut aussi lire `GAMESTATS_URL`, `GAMESTATS_API_KEY`,
`GAMESTATS_AGENT_ID`, `GAMESTATS_INTERVAL` et `GAMESTATS_LOG_FILE`.

### Ajouter un jeu

Éditez `agent-windows/games.json` et associez un titre à ses exécutables :

```json
{
  "name": "Mon Jeu",
  "steam_app_id": 123456,
  "processes": ["monjeu.exe", "monjeu_dx12.exe"]
}
```

Le `steam_app_id` est facultatif mais recommandé : il permet de fusionner
automatiquement la fiche agent avec la fiche Steam. Redémarrez ensuite l'agent.
Pour trouver le nom exact du processus : `Get-Process | Select-Object Name`.

### Démarrage automatique

Avec le Planificateur de tâches Windows, créez une tâche **Au démarrage de
session**, programme = le chemin de `pythonw.exe`, arguments :

```
"C:\GameStats\agent-windows\tracker.py" --server http://192.168.1.20:8091 --key "VOTRE_CLE" --log-file "C:\GameStats\agent.log"
```

Lancez la tâche avec le compte de l'utilisateur (et non SYSTEM), sinon les
processus des jeux ne seront pas visibles. Vérifiez le résultat avec le
fichier de log.

## Architecture

```
agent-windows/tracker.py ── POST /api/heartbeat ──► backend FastAPI
                                                        │
                                   ┌────────────────────┼───────────────────┐
                                   ▼                    ▼                   ▼
                              SQLite /data        APScheduler          Steam Web API
                                                  (15 min)            + IGDB
                                                        │
frontend React (nginx) ◄──────── GET /api/stats/* ──────┘
```

- **Agent** : analyse `psutil` toutes les 30 s, envoie la liste des jeux
  détectés. Aucune capture d'écran, aucun contenu de jeu.
- **Backend** : sessions agent gérées par présence ; une session sans heartbeat
  depuis 180 s est clôturée automatiquement.
- **Planificateur** : clôture des sessions inactives chaque minute, import
  Steam toutes les 15 min, enrichissement IGDB toutes les 60 min. Un seul
  worker uvicorn est utilisé pour éviter les planificateurs en double.
- **Frontend** : React/Vite servi par nginx, proxy `/api` vers le backend.

## API

| Méthode | Route                     | Description                                |
| ------- | ------------------------- | ------------------------------------------ |
| `POST`  | `/api/heartbeat`          | Heartbeat agent (header `X-Agent-Key`)      |
| `GET`   | `/api/stats/summary`      | Cartes du dashboard                        |
| `GET`   | `/api/stats/heatmap`      | Heatmap 7 × 24 (`?days=365`)               |
| `GET`   | `/api/stats/daily`        | Totaux par jour (`?days=14`)               |
| `GET`   | `/api/stats/top-games`    | Top jeux (`?days=30&limit=8`)              |
| `GET`   | `/api/sessions`           | Sessions récentes (`?limit=15`)            |
| `GET`   | `/api/games`              | Bibliothèque (`?search=&sort=playtime`)    |
| `GET`   | `/api/agents`             | État des agents                            |
| `GET`   | `/api/health`             | Santé du backend                           |
| `POST`  | `/api/admin/sync/steam`   | Sync Steam manuelle (`X-Agent-Key`)        |
| `POST`  | `/api/admin/enrich/igdb`  | Enrichissement IGDB manuel (`X-Agent-Key`) |

Exemple de synchronisation forcée :

```bash
curl -X POST -H "X-Agent-Key: $AGENT_API_KEY" \
  http://localhost:8091/api/admin/sync/steam
```

Les routes de lecture ne sont pas authentifiées. N'exposez pas le port backend
(8091 par défaut) directement sur Internet : gardez l'ensemble derrière un
reverse proxy authentifié, ou limitez l'accès au réseau local.

## Développement

### Backend

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend
uvicorn main:app --reload --port 8000
```

Variables d'environnement utiles : `DATABASE_URL` (par défaut
`sqlite:///./data/gamestats.db`), `AGENT_API_KEY`, `TIMEZONE`,
`SCHEDULER_ENABLED=false` pour désactiver les tâches de fond.

Tests :

```bash
cd backend
pytest -q
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxy /api vers :8000
```

Build de production : `npm run build` (typecheck TypeScript inclus).

## Dépannage

- **401 sur le heartbeat** : `AGENT_API_KEY` et `--key` ne correspondent pas.
- **Bibliothèque Steam vide** : profil privé, clé invalide, ou `STEAM_ID` qui
  n'est pas un SteamID64. Consultez `docker compose logs -f backend`.
- **Pas de jaquettes** : identifiants IGDB absents ou quota atteint ; l'erreur
  apparaît dans les logs et les jeux seront retentés au prochain passage.
- **Session bloquée « en cours »** : l'agent ne répond plus ; elle est fermée
  après `AGENT_STALE_SECONDS` (180 s par défaut).
- **Heures décalées** : corrigez `TIMEZONE`, redémarrez le backend (les
  sessions sont stockées en UTC).
- **Agent ne détecte pas un jeu** : vérifiez le nom exact du processus dans
  `games.json`. Les jeux Java (Minecraft Java) passent souvent par
  `javaw.exe` : ajoutez une règle dédiée si nécessaire.

## Limites connues

- Les deltas Steam sont approximatifs : le temps joué hors ligne est rattaché
  à la fenêtre de synchronisation qui détecte l'augmentation.
- Le schéma SQLite est créé automatiquement, sans migrations Alembic. Pour
  repartir de zéro : `docker compose down`, puis supprimez le dossier `data`
  (les fichiers créés par le conteneur appartiennent à root : `sudo rm -rf data`
  peut être nécessaire).
- Un seul agent est prévu pour l'instant ; plusieurs agents créeraient des
  sessions distinctes pour un même jeu.
