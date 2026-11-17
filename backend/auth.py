import hmac
from typing import Annotated

from fastapi import Header, HTTPException, status

from config import get_settings


def require_agent_key(x_agent_key: Annotated[str | None, Header()] = None) -> None:
    """Vérifie la clé partagée envoyée par l'agent (ou pour les routes admin)."""

    expected = get_settings().agent_api_key
    if not x_agent_key or not hmac.compare_digest(x_agent_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé agent invalide ou manquante (en-tête X-Agent-Key).",
        )
