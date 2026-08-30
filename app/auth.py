import os
import secrets
import time
from typing import Dict, Optional, Tuple

from fastapi import Cookie, HTTPException, status

# Sessões em memória com expiração (TTL deslizante). Para múltiplas instâncias
# ou restart sem perda de sessão, migrar para Redis/PostgreSQL.
SESSION_TTL_SECONDS = 7200  # 2h — alinhado ao max_age do cookie

# token -> (username, expires_at)
ACTIVE_SESSIONS: Dict[str, Tuple[str, float]] = {}


def eh_admin(username: str) -> bool:
    """Decide se um usuário tem papel de administrador (gerência de tipos).

    Decisão de modelo (ISSUE 2): a tabela `tipos` é compartilhada entre todos
    os usuários (categorias já são por usuário). Para impedir que um usuário
    renomeie/exclua um tipo usado por outro (as transações guardam o nome como
    string), a criação/edição/remoção de tipos fica restrita a administradores
    definidos pela variável de ambiente `ADMIN_USERNAMES` (lista separada por
    vírgula). Sem a variável, nenhum usuário gerencia tipos — os padrão
    (Receita/Despesa) já existem via seed.
    """
    admins = {
        a.strip().lower()
        for a in os.getenv("ADMIN_USERNAMES", "").split(",")
        if a.strip()
    }
    return username.strip().lower() in admins


def _limpar_expiradas() -> None:
    agora = time.time()
    expiradas = [t for t, (_, exp) in ACTIVE_SESSIONS.items() if exp <= agora]
    for t in expiradas:
        del ACTIVE_SESSIONS[t]


def verificar_autenticacao(session_token: Optional[str] = Cookie(None)) -> str:
    """Valida a sessão via cookie HttpOnly (único mecanismo suportado).

    O header `Authorization: Bearer` foi removido (decisão documentada no
    README): o frontend usa apenas cookie, e com HttpOnly + SameSite=Lax o
    token não é legível via JS nem enviado em navegações cross-site — reduz a
    superfície caso um token vaze para logs/referrers.
    """
    _limpar_expiradas()

    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso inválido ou ausente.",
        )

    sessao = ACTIVE_SESSIONS.get(session_token)
    if not sessao:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso inválido ou ausente.",
        )

    username, expires_at = sessao
    if expires_at <= time.time():
        del ACTIVE_SESSIONS[session_token]
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão expirada.",
        )

    # Renovação deslizante: cada requisição autenticada estende a sessão
    ACTIVE_SESSIONS[session_token] = (username, time.time() + SESSION_TTL_SECONDS)
    return username


def criar_sessao(username: str) -> str:
    session_token = secrets.token_hex(32)
    ACTIVE_SESSIONS[session_token] = (username, time.time() + SESSION_TTL_SECONDS)
    return session_token


def encerrar_sessao(session_token: Optional[str]) -> None:
    if session_token:
        ACTIVE_SESSIONS.pop(session_token, None)
