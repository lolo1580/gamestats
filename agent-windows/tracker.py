#!/usr/bin/env python3
"""Agent GameStats pour Windows.

Détecte les processus de jeux déclarés dans games.json et envoie un heartbeat
au backend. Aucune donnée de jeu n'est envoyée au-delà du nom du jeu et des
processus détectés.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil
import requests

LOGGER = logging.getLogger("gamestats-agent")
APP_NAME = "GameStats"
AGENT_VERSION = "1.1.0"


def user_data_dir() -> Path:
    if os.name == "nt":
        base = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.getenv("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


def default_settings_path() -> Path:
    return user_data_dir() / "agent.json"


def default_games_path() -> Path:
    if not getattr(sys, "frozen", False):
        beside = Path(__file__).resolve().with_name("games.json")
        if beside.exists():
            return beside
    return user_data_dir() / "games.json"


def load_settings_file(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise ValueError(f"Configuration illisible ({path}) : {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide dans {path} : {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} doit contenir un objet JSON.")
    return data


def resolve_setting_path(value: Any, base: Path) -> Path | None:
    if value is None or not str(value).strip():
        return None
    path = Path(str(value)).expanduser()
    return path if path.is_absolute() else base / path


def env_or_setting(name: str, setting: Any, fallback: Any) -> Any:
    value = os.getenv(name)
    if value not in (None, ""):
        return value
    if setting not in (None, ""):
        return setting
    return fallback


def int_setting(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument(
        "--settings",
        type=Path,
        default=Path(
            os.getenv("GAMESTATS_SETTINGS", str(default_settings_path()))
        ),
    )
    known, _ = bootstrap.parse_known_args(argv)
    settings_path = known.settings.expanduser()
    settings = load_settings_file(settings_path)
    base = settings_path.parent

    env_games = os.getenv("GAMESTATS_CONFIG")
    if env_games:
        games_default = Path(env_games).expanduser()
    else:
        games_default = resolve_setting_path(settings.get("games_file"), base)
        if games_default is None:
            games_default = default_games_path()

    env_log = os.getenv("GAMESTATS_LOG_FILE")
    if env_log:
        log_default: Path | None = Path(env_log).expanduser()
    else:
        log_default = resolve_setting_path(settings.get("log_file"), base)
        if log_default is None and (
            getattr(sys, "frozen", False) or settings_path.exists()
        ):
            log_default = user_data_dir() / "agent.log"

    parser = argparse.ArgumentParser(
        description="Envoie au backend GameStats les jeux actuellement lancés sur ce PC.",
    )
    parser.add_argument(
        "--settings",
        type=Path,
        default=settings_path,
        help="Fichier de configuration JSON (défaut : %(default)s).",
    )
    parser.add_argument(
        "--server",
        default=str(
            env_or_setting(
                "GAMESTATS_URL", settings.get("server"), "http://localhost:8091"
            )
        ),
        help="URL du backend, par ex. http://192.168.1.20:8091 (défaut : %(default)s)",
    )
    parser.add_argument(
        "--key",
        default=str(
            env_or_setting("GAMESTATS_API_KEY", settings.get("api_key"), "")
        ),
        help="Clé partagée AGENT_API_KEY (ou variable GAMESTATS_API_KEY).",
    )
    parser.add_argument(
        "--agent-id",
        default=str(
            env_or_setting(
                "GAMESTATS_AGENT_ID", settings.get("agent_id"), ""
            )
        )
        or None,
        help="Identifiant stable du PC (généré automatiquement sinon).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int_setting(
            env_or_setting(
                "GAMESTATS_INTERVAL", settings.get("interval"), 30
            ),
            30,
        ),
        help="Intervalle entre deux heartbeats, en secondes (défaut : 30).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=games_default,
        help="Fichier JSON des jeux à surveiller (défaut : %(default)s).",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=log_default,
        help="Fichier de log optionnel (utile en arrière-plan).",
    )
    parser.add_argument(
        "--log-level",
        default=str(
            env_or_setting(
                "GAMESTATS_LOG_LEVEL", settings.get("log_level"), "INFO"
            )
        ),
        help="Niveau de log : DEBUG, INFO, WARNING…",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"GameStats Agent {AGENT_VERSION}",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Envoie un seul heartbeat puis quitte (test de configuration).",
    )
    return parser.parse_args(argv)


def setup_logging(level: str, log_file: Path | None) -> None:
    handlers: list[logging.Handler] = []
    if not getattr(sys, "frozen", False) or sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except OSError:
            pass
    if not handlers:
        handlers.append(logging.NullHandler())
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


def notify(message: str, *, error: bool = False) -> None:
    if getattr(sys, "frozen", False) and os.name == "nt":
        try:
            import ctypes

            flags = 0x10 if error else 0x40
            ctypes.windll.user32.MessageBoxW(
                None, message, "GameStats Agent", flags
            )
            return
        except Exception:
            pass
    stream = sys.stderr if error else sys.stdout
    if stream is not None:
        print(message, file=stream)


_MUTEX_HANDLE: Any = None


def acquire_single_instance() -> bool:
    global _MUTEX_HANDLE
    if os.name != "nt":
        return True
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        _MUTEX_HANDLE = kernel32.CreateMutexW(
            None, False, "GameStatsAgentMutex"
        )
        return kernel32.GetLastError() != 183
    except Exception:
        return True


def default_agent_id() -> str:
    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            if machine_guid:
                clean = str(machine_guid).strip().replace("{", "").replace("}", "")
                return f"pc-{clean[:12].lower()}"
        except OSError:
            pass

    return f"pc-{uuid.getnode():012x}"


def heartbeat_endpoint(server: str) -> str:
    value = server.strip().rstrip("/")
    if value.endswith("/api/heartbeat"):
        return value
    if value.endswith("/api"):
        return f"{value}/heartbeat"
    return f"{value}/api/heartbeat"


def load_game_mappings(path: Path) -> list[dict[str, Any]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Fichier de configuration introuvable : {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide dans {path} : {exc}") from exc

    entries = raw.get("games") if isinstance(raw, dict) else raw
    if not isinstance(entries, list):
        raise ValueError(f"{path} doit contenir une liste 'games'.")

    mappings: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name", "")).strip()
        processes = entry.get("processes") or entry.get("match") or []
        if not name or not isinstance(processes, list):
            continue

        normalized = sorted(
            {
                Path(str(process).strip()).name.casefold()
                for process in processes
                if str(process).strip()
            }
        )
        if not normalized:
            continue

        mapping: dict[str, Any] = {"name": name, "processes": normalized}
        steam_app_id = entry.get("steam_app_id")
        if isinstance(steam_app_id, int) and steam_app_id > 0:
            mapping["steam_app_id"] = steam_app_id
        mappings.append(mapping)

    if not mappings:
        raise ValueError(f"Aucun jeu valide dans {path}.")
    return mappings


def running_process_names() -> set[str]:
    names: set[str] = set()
    for process in psutil.process_iter(["name", "exe"]):
        try:
            info = process.info
            for value in (info.get("name"), info.get("exe")):
                if value:
                    names.add(Path(str(value)).name.casefold())
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return names


def detect_games(
    mappings: list[dict[str, Any]], running: set[str]
) -> list[dict[str, Any]]:
    detected: list[dict[str, Any]] = []
    seen: set[str] = set()

    for mapping in mappings:
        key = mapping["name"].casefold()
        if key in seen:
            continue
        for process in mapping["processes"]:
            if process in running:
                game: dict[str, Any] = {"name": mapping["name"], "process": process}
                if mapping.get("steam_app_id"):
                    game["steam_app_id"] = mapping["steam_app_id"]
                detected.append(game)
                seen.add(key)
                break

    return detected


def send_heartbeat(
    http: requests.Session,
    endpoint: str,
    api_key: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    response = http.post(
        endpoint,
        json=payload,
        headers={
            "X-Agent-Key": api_key,
            "User-Agent": "GameStats-Agent/1.0",
        },
        timeout=10,
    )
    if response.status_code >= 400:
        detail = " ".join(response.text.split())[:200]
        raise requests.HTTPError(
            f"HTTP {response.status_code} — {detail}", response=response
        )
    try:
        return response.json()
    except ValueError:
        return {}


def main() -> int:
    try:
        args = parse_args()
    except ValueError as exc:
        notify(f"Configuration invalide : {exc}", error=True)
        return 2
    setup_logging(args.log_level, args.log_file)

    if not args.key:
        message = (
            "Clé API manquante. Utilisez --key, la variable GAMESTATS_API_KEY "
            "ou le fichier agent.json (même valeur que AGENT_API_KEY côté backend)."
        )
        LOGGER.error(message)
        notify(message, error=True)
        return 2

    if not acquire_single_instance():
        message = "GameStats Agent est déjà en cours d'exécution."
        LOGGER.info(message)
        notify(message)
        return 0

    try:
        mappings = load_game_mappings(args.config)
    except ValueError as exc:
        LOGGER.error("%s", exc)
        notify(str(exc), error=True)
        return 2

    interval = max(10, args.interval)
    endpoint = heartbeat_endpoint(args.server)
    agent_id = args.agent_id or default_agent_id()
    hostname = socket.gethostname()
    http = requests.Session()

    LOGGER.info("Agent %s (%s) → %s", agent_id, hostname, endpoint)
    LOGGER.info("%s jeu(x) surveillé(s), heartbeat toutes les %ss.", len(mappings), interval)

    last_signature: tuple[str, ...] | None = None
    exit_code = 0

    try:
        while True:
            started = time.monotonic()
            running = running_process_names()
            detected = detect_games(mappings, running)

            payload = {
                "agent_id": agent_id,
                "hostname": hostname,
                "games": detected,
                "captured_at": datetime.now(timezone.utc).isoformat(),
            }

            try:
                response = send_heartbeat(http, endpoint, args.key, payload)
                signature = tuple(sorted(game["name"] for game in detected))
                if signature != last_signature:
                    if detected:
                        LOGGER.info(
                            "Jeux détectés : %s",
                            ", ".join(game["name"] for game in detected),
                        )
                    else:
                        LOGGER.info("Aucun jeu détecté — heartbeat envoyé.")
                    last_signature = signature
                else:
                    active = len(response.get("active_sessions") or [])
                    LOGGER.debug("Heartbeat OK (%s session(s) active(s)).", active)
                if args.once:
                    active = len(response.get("active_sessions") or [])
                    notify(
                        "Connexion réussie au serveur GameStats.\n"
                        f"{len(detected)} jeu(x) détecté(s), "
                        f"{active} session(s) active(s)."
                    )
            except requests.RequestException as exc:
                LOGGER.warning(
                    "Heartbeat impossible (%s). Nouvel essai dans %ss.", exc, interval
                )
                if args.once:
                    notify(
                        "Connexion impossible au serveur GameStats.\n"
                        f"{exc}",
                        error=True,
                    )
                    exit_code = 1

            if args.once:
                break

            elapsed = time.monotonic() - started
            time.sleep(max(1.0, interval - elapsed))
    except KeyboardInterrupt:
        LOGGER.info("Arrêt de l'agent.")
    finally:
        http.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
