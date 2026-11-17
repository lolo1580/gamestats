# GameStats Agent (Windows)

Agent léger qui détecte les jeux lancés sur le PC et envoie un heartbeat au
backend GameStats. Il ne capture ni écran, ni fichiers, ni données de jeu.

## Installateur

Le build produit deux fichiers dans `agent-windows/dist/` :

- `GameStatsAgentSetup.exe` — installateur Windows (recommandé) ;
- `GameStatsAgent-portable.zip` — version portable sans installation.

L’installateur demande :

- l’adresse du backend, par exemple `http://192.168.30.21:8091` ;
- la clé agent disponible dans **GameStats → Paramètres → Général → Clé agent**.

Il installe l’agent dans `%LOCALAPPDATA%\Programs\GameStats Agent`, crée un
raccourci dans le menu Démarrer et, par défaut, un démarrage automatique à
l’ouverture de session. Aucun droit administrateur n’est nécessaire.

Après l’installation, l’installateur peut lancer un test de connexion. Le
résultat s’affiche dans une boîte de dialogue.

## Fichiers de configuration

| Fichier | Emplacement |
|---|---|
| Configuration | `%APPDATA%\GameStats\agent.json` |
| Liste des jeux | `%APPDATA%\GameStats\games.json` |
| Logs | `%APPDATA%\GameStats\agent.log` |

Exemple de `agent.json` :

```json
{
  "server": "http://192.168.30.21:8091",
  "api_key": "votre-cle-agent",
  "interval": 30,
  "games_file": "games.json",
  "log_file": "agent.log"
}
```

Les chemins relatifs sont résolus par rapport au dossier de `agent.json`.

Pour ajouter un jeu, modifiez `games.json` : associez le nom du jeu aux
exécutables détectés par le gestionnaire de tâches. Exemple :

```json
{
  "games": [
    {
      "name": "Elden Ring",
      "steam_app_id": 1245620,
      "processes": ["eldenring.exe"]
    }
  ]
}
```

Relancez l’agent après modification de la liste.

## Diagnostic

Pour connaître le nom exact d’un exécutable, lancez l’agent avec
`--list-processes` : il affiche les processus en cours et marque d’un `*` ceux
déjà surveillés.

```powershell
py tracker.py --list-processes
```

Avec l’exécutable installé, le résultat s’affiche dans une boîte de dialogue :

```powershell
& "$env:LOCALAPPDATA\Programs\GameStats Agent\GameStatsAgent.exe" --list-processes
```

Si le backend est injoignable, l’agent ne s’arrête pas : il réessaie avec un
délai progressif (30 s, 60 s, 120 s… jusqu’à 5 minutes) et reprend le rythme
normal dès qu’une réponse revient. Une erreur inattendue pendant un cycle est
journalisée et l’agent continue.

Les entrées invalides de `games.json` (nom manquant, liste de processus vide,
`steam_app_id` non numérique) sont ignorées et signalées dans `agent.log`. Ce
fichier est limité à 1 Mo et conservé en trois archives (`agent.log.1` à
`agent.log.3`).

## Construire l’installateur

### Sur Windows

Prérequis :

- Python 3.11 ou plus récent ;
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) pour générer l’installateur.

Depuis `agent-windows/` :

```powershell
.\build.ps1
```

Le script crée un environnement virtuel, installe PyInstaller, construit
`GameStatsAgent.exe`, puis `GameStatsAgentSetup.exe` dans `dist/`. Il copie aussi
automatiquement l’installateur et l’archive portable dans `../downloads/` pour
les rendre disponibles depuis le serveur GameStats local.

Pour ne construire que l’exécutable :

```powershell
.\build.ps1 -SkipInstaller
```

### Via GitHub Actions

Le workflow `.github/workflows/agent-windows.yml` construit automatiquement
l’exécutable et l’installateur sur `windows-latest`. Lancez-le manuellement
depuis l’onglet **Actions** du dépôt, ou poussez un tag `agent-v1.1.0` pour
attacher les fichiers à une release GitHub.

## Publication sur le serveur local

Le backend monte le dossier `downloads/` du dépôt en lecture seule sur
`/downloads`. Placez-y les fichiers suivants :

- `GameStatsAgentSetup.exe`
- `GameStatsAgent-portable.zip` (optionnel)

Ils sont alors téléchargeables depuis **GameStats → Paramètres → Général →
Agent Windows**. `build.ps1` effectue cette copie automatiquement après chaque
build. Les binaires sont ignorés par Git.

## Exécution en développement

```powershell
py -m pip install -r requirements.txt

# Test unique avec les paramètres en ligne de commande
py tracker.py `
  --server http://192.168.30.21:8091 `
  --key "VOTRE_CLE_AGENT" `
  --once
```

L’exécutable installé n’ouvre pas de console : les erreurs sont écrites dans
`agent.log` et, pour les erreurs de démarrage ou le test `--once`, affichées
dans une boîte de dialogue Windows.

## Désinstallation

Utilisez **Paramètres Windows → Applications → GameStats Agent**, ou le
raccourci de désinstallation du menu Démarrer. La configuration, la liste des
jeux et les logs dans `%APPDATA%\GameStats` sont conservés. Supprimez ce dossier
manuellement si vous voulez aussi effacer les données locales.

## Signature

L’exécutable et l’installateur ne sont pas signés par défaut. Windows SmartScreen
peut donc afficher un avertissement au premier lancement. Pour une distribution
large, signez `GameStatsAgent.exe` et `GameStatsAgentSetup.exe` avec un
certificat de signature de code.
