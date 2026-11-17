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
DEFAULT_CONFIG = Path(__file__).resolve().with_name("games.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Envoie au backend GameStats les jeux actuellement lancés sur ce PC.",
    )
    parser.add_argument(
        "--server",
        default=os.getenv("GAMESTATS_URL", "http://localhost:8091"),
        help="URL du backend, par ex. http://192.168.1.20:8000 (défaut : %(default)s)",
    )
    parser.add_argument(
        "--key",
        default=os.getenv("GAMESTATS_API_KEY", ""),
        help="Clé partagée AGENT_API_KEY (ou variable GAMESTATS_API_KEY).",
    )
    parser.add_argument(
        "--agent-id",
        default=os.getenv("GAMESTATS_AGENT_ID"),
        help="Identifiant stable du PC (généré automatiquement sinon).",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("GAMESTATS_INTERVAL", "30")),
        help="Intervalle entre deux heartbeats, en secondes (défaut : 30).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(os.getenv("GAMESTATS_CONFIG", str(DEFAULT_CONFIG))),
        help="Fichier JSON des jeux à surveiller (défaut : games.json).",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path(os.environ["GAMESTATS_LOG_FILE"]) if os.getenv("GAMESTATS_LOG_FILE") else None,
        help="Fichier de log optionnel (utile en arrière-plan avec pythonw).",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("GAMESTATS_LOG_LEVEL", "INFO"),
        help="Niveau de log : DEBUG, INFO, WARNING…",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Envoie un seul heartbeat puis quitte (test de configuration).",
    )
    return parser.parse_args()


def setup_logging(level: str, log_file: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
    )


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
    args = parse_args()
    setup_logging(args.log_level, args.log_file)

    if not args.key:
        LOGGER.error(
            "Clé API manquante. Utilisez --key ou la variable GAMESTATS_API_KEY "
            "(même valeur que AGENT_API_KEY côté backend)."
        )
        return 2

    try:
        mappings = load_game_mappings(args.config)
    except ValueError as exc:
        LOGGER.error("%s", exc)
        return 2

    interval = max(10, args.interval)
    endpoint = heartbeat_endpoint(args.server)
    agent_id = args.agent_id or default_agent_id()
    hostname = socket.gethostname()
    http = requests.Session()

    LOGGER.info("Agent %s (%s) → %s", agent_id, hostname, endpoint)
    LOGGER.info("%s jeu(x) surveillé(s), heartbeat toutes les %ss.", len(mappings), interval)

    last_signature: tuple[str, ...] | None = None

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
            except requests.RequestException as exc:
                LOGGER.warning(
                    "Heartbeat impossible (%s). Nouvel essai dans %ss.", exc, interval
                )

            if args.once:
                break

            elapsed = time.monotonic() - started
            time.sleep(max(1.0, interval - elapsed))
    except KeyboardInterrupt:
        LOGGER.info("Arrêt de l'agent.")
    finally:
        http.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
