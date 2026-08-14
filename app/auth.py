import secrets
import time
from typing import Dict, Optional, Tuple

from fastapi import Cookie, Header, HTTPException, status

# Sessões em memória com expiração (TTL deslizante). Para múltiplas instâncias
# ou restart sem perda de sessão, migrar para Redis/PostgreSQL.
SESSION_TTL_SECONDS = 7200  # 2h — alinhado ao max_age do cookie

# token -> (username, expires_at)
ACTIVE_SESSIONS: Dict[str, Tuple[str, float]] = {}


def _limpar_expiradas() -> None:
    agora = time.time()
    expiradas = [t for t, (_, exp) in ACTIVE_SESSIONS.items() if exp <= agora]
    for t in expiradas:
        del ACTIVE_SESSIONS[t]


def verificar_autenticacao(
    authorization: Optional[str] = Header(None),
    session_token: Optional[str] = Cookie(None),
) -> str:
    _limpar_expiradas()

    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
    elif session_token:
        token = session_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso inválido ou ausente.",
        )

    sessao = ACTIVE_SESSIONS.get(token)
    if not sessao:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso inválido ou ausente.",
        )

    username, expires_at = sessao
    if expires_at <= time.time():
        del ACTIVE_SESSIONS[token]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão expirada.",
        )

    # Renovação deslizante: cada requisição autenticada estende a sessão
    ACTIVE_SESSIONS[token] = (username, time.time() + SESSION_TTL_SECONDS)
    return username


def criar_sessao(username: str) -> str:
    session_token = secrets.token_hex(32)
    ACTIVE_SESSIONS[session_token] = (username, time.time() + SESSION_TTL_SECONDS)
    return session_token


def encerrar_sessao(session_token: Optional[str]) -> None:
    if session_token:
        ACTIVE_SESSIONS.pop(session_token, None)
