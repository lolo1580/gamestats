import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from settings_service import get_agent_api_key


def require_agent_key(
    x_agent_key: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> None:
    expected = get_agent_api_key(db)
    if not x_agent_key or not hmac.compare_digest(x_agent_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé agent invalide ou manquante (en-tête X-Agent-Key).",
        )
