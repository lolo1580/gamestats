"""Tests des fonctions pures de l'agent Windows."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import tracker


def write_games(tmp_path: Path, games: list[dict]) -> Path:
    path = tmp_path / "games.json"
    path.write_text(json.dumps({"games": games}), encoding="utf-8")
    return path


def mapping(
    name: str,
    processes: list[str] | None = None,
    window_titles: list[str] | None = None,
    steam_app_id: int | None = None,
) -> dict:
    entry: dict = {"name": name, "processes": processes or []}
    if window_titles:
        entry["window_titles"] = window_titles
    if steam_app_id:
        entry["steam_app_id"] = steam_app_id
    return entry


class TestLoadGameMappings:
    def test_normalizes_process_paths_and_duplicates(self, tmp_path):
        path = write_games(
            tmp_path,
            [
                {
                    "name": "Game",
                    "processes": ["C:\\Games\\Game.EXE", "game.exe", " other.exe "],
                    "steam_app_id": 730,
                }
            ],
        )

        assert tracker.load_game_mappings(path) == [
            {
                "name": "Game",
                "processes": ["game.exe", "other.exe"],
                "window_titles": [],
                "steam_app_id": 730,
            }
        ]

    def test_accepts_numeric_string_steam_app_id(self, tmp_path):
        path = write_games(
            tmp_path, [{"name": "Game", "processes": ["g.exe"], "steam_app_id": " 730 "}]
        )

        assert tracker.load_game_mappings(path)[0]["steam_app_id"] == 730

    def test_ignores_invalid_steam_app_id(self, tmp_path, caplog):
        path = write_games(
            tmp_path, [{"name": "Game", "processes": ["g.exe"], "steam_app_id": "abc"}]
        )

        mappings = tracker.load_game_mappings(path)

        assert "steam_app_id" not in mappings[0]
        assert "steam_app_id ignoré" in caplog.text

    def test_accepts_window_only_entry(self, tmp_path):
        path = write_games(
            tmp_path, [{"name": "Minecraft", "window_titles": ["Minecraft*"]}]
        )

        assert tracker.load_game_mappings(path) == [
            {
                "name": "Minecraft",
                "processes": [],
                "window_titles": ["minecraft*"],
            }
        ]

    def test_skips_entry_without_process_or_window(self, tmp_path, caplog):
        path = write_games(
            tmp_path,
            [
                {"name": "Broken"},
                {"name": "Valid", "processes": ["ok.exe"]},
            ],
        )

        mappings = tracker.load_game_mappings(path)

        assert [item["name"] for item in mappings] == ["Valid"]
        assert "aucun processus ni titre" in caplog.text

    def test_skips_entry_without_name(self, tmp_path, caplog):
        path = write_games(
            tmp_path, [{"name": "", "processes": ["g.exe"]}, {"name": "Ok"}]
        )

        with pytest.raises(ValueError, match="Aucun jeu valide"):
            tracker.load_game_mappings(path)
        assert "obligatoires" in caplog.text

    def test_warns_when_window_titles_is_not_a_list(self, tmp_path, caplog):
        path = write_games(
            tmp_path, [{"name": "Game", "processes": ["g.exe"], "window_titles": "*"}]
        )

        assert tracker.load_game_mappings(path)[0]["window_titles"] == []
        assert "window_titles ignoré" in caplog.text

    def test_raises_without_valid_entry(self, tmp_path):
        path = write_games(tmp_path, [{"name": "Broken"}])

        with pytest.raises(ValueError, match="Aucun jeu valide"):
            tracker.load_game_mappings(path)

    def test_raises_when_file_is_missing(self, tmp_path):
        with pytest.raises(ValueError, match="introuvable"):
            tracker.load_game_mappings(tmp_path / "missing.json")

    def test_raises_on_invalid_json(self, tmp_path):
        path = tmp_path / "games.json"
        path.write_text("{not json", encoding="utf-8")

        with pytest.raises(ValueError, match="JSON invalide"):
            tracker.load_game_mappings(path)

    def test_accepts_a_bare_list_of_games(self, tmp_path):
        path = tmp_path / "games.json"
        path.write_text(
            json.dumps([{"name": "Game", "processes": ["g.exe"]}]), encoding="utf-8"
        )

        assert tracker.load_game_mappings(path)[0]["name"] == "Game"


class TestDetectGames:
    def test_matches_running_process(self):
        games = [mapping("Game", ["game.exe"], steam_app_id=730)]

        assert tracker.detect_games(games, {"game.exe"}) == [
            {"name": "Game", "process": "game.exe", "steam_app_id": 730}
        ]

    def test_matches_window_title(self):
        games = [mapping("Minecraft", window_titles=["minecraft*"])]

        assert tracker.detect_games(games, set(), "Minecraft 1.21 - Java") == [
            {"name": "Minecraft"}
        ]

    def test_window_match_is_case_insensitive_and_exact_for_plain_titles(self):
        games = [mapping("Terraria", window_titles=["terraria"])]

        assert tracker.detect_games(games, set(), "Terraria") == [
            {"name": "Terraria"}
        ]
        assert tracker.detect_games(games, set(), "Terraria - Modding") == []

    def test_ignores_window_title_without_patterns(self):
        games = [mapping("Game", ["game.exe"])]

        assert tracker.detect_games(games, set(), "game.exe") == []

    def test_returns_each_game_once(self):
        games = [
            mapping("Game", ["a.exe", "b.exe"], window_titles=["game*"]),
        ]

        assert tracker.detect_games(games, {"a.exe", "b.exe"}, "Game") == [
            {"name": "Game", "process": "a.exe"}
        ]

    def test_combines_process_and_window_matches(self):
        games = [
            mapping("Process Game", ["a.exe"]),
            mapping("Window Game", window_titles=["game*"]),
        ]

        detected = tracker.detect_games(games, {"a.exe"}, "Game window")

        assert [game["name"] for game in detected] == ["Process Game", "Window Game"]


class TestHelpers:
    @pytest.mark.parametrize(
        ("server", "expected"),
        [
            ("http://host:8091", "http://host:8091/api/heartbeat"),
            ("http://host:8091/", "http://host:8091/api/heartbeat"),
            ("http://host:8091/api", "http://host:8091/api/heartbeat"),
            (
                "http://host:8091/api/heartbeat",
                "http://host:8091/api/heartbeat",
            ),
        ],
    )
    def test_heartbeat_endpoint(self, server, expected):
        assert tracker.heartbeat_endpoint(server) == expected

    def test_matches_window_requires_title_and_patterns(self):
        assert not tracker.matches_window(["game*"], "")
        assert not tracker.matches_window([], "Game")

    def test_format_process_list_flags_watched_processes(self):
        games = [mapping("Game", ["game.exe"])]

        text = tracker.format_process_list(games, {"game.exe", "code.exe"})

        assert "2 processus en cours, 1 surveillé(s)" in text
        assert "* game.exe" in text
        assert "\n  code.exe" in text

    def test_games_file_mtime_is_none_when_missing(self, tmp_path):
        assert tracker.games_file_mtime(tmp_path / "missing.json") is None

    def test_games_file_mtime_tracks_changes(self, tmp_path):
        path = write_games(tmp_path, [{"name": "Game", "processes": ["g.exe"]}])
        first = tracker.games_file_mtime(path)
        assert first is not None

        os.utime(path, (first + 10, first + 10))

        assert tracker.games_file_mtime(path) == pytest.approx(first + 10)

    def test_active_window_title_returns_a_string(self):
        assert isinstance(tracker.active_window_title(), str)
