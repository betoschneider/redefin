import logging
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Optional

import bcrypt
import pyotp
import requests
from alembic import command
from alembic.config import Config
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import insights, investments, models, profile, transactions
from app.auth import criar_sessao, encerrar_sessao, verificar_autenticacao
from app.config import Base, engine, get_db, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
from app.models import User
from app.transactions import get_user_by_username


logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Limite de taxa (em memória, janela deslizante) ---------------------
# Suficiente para uma aplicação de poucos usuários. Para múltiplas instâncias,
# usar Redis (ex.: slowapi/fastapi-limiter).
_limite_taxa_por_chave = defaultdict(deque)
_LIMITE_MAX_CHAVES = 10000


def _ip_do_cliente(request: Request) -> str:
    return request.client.host if request.client else "desconhecido"


def _verificar_limite_taxa(chave: str, max_attempts: int, janela_segundos: int) -> None:
    agora = time.monotonic()
    fila = _limite_taxa_por_chave[chave]
    while fila and agora - fila[0] > janela_segundos:
        fila.popleft()
    if len(fila) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas. Tente novamente mais tarde.",
        )
    fila.append(agora)
    # Poda ocasional para evitar crescimento infinito do dict
    if len(_limite_taxa_por_chave) > _LIMITE_MAX_CHAVES:
        _limite_taxa_por_chave.clear()


# --- Cookie de sessão ----------------------------------------------------
# COOKIE_SECURE=auto (padrão): Secure apenas sobre HTTPS; defina
# COOKIE_SECURE=1 quando o app rodar atrás de um proxy que termina o TLS
# (o uvicorn não enxerga o esquema original sem --proxy-headers).
COOKIE_SECURE_MODE = os.getenv("COOKIE_SECURE", "auto").lower()


def _cookie_secure(request: Request) -> bool:
    if COOKIE_SECURE_MODE == "auto":
        return request.url.scheme == "https"
    return COOKIE_SECURE_MODE in ("1", "true", "yes")


def _definir_cookie_sessao(request: Request, response: Response, session_token: str) -> None:
    response.set_cookie(
        key="session_token",
        value=session_token,
        max_age=7200,
        httponly=True,   # impede leitura via JS (mitiga roubo de sessão via XSS)
        secure=_cookie_secure(request),
        samesite="lax",  # mitiga CSRF cross-site
        path="/",
    )


# Origens permitidas para o redirect_uri do OAuth Google. Nunca derivar o
# redirect_uri de input do usuário (evita roubo do authorization code).
# O default cobre os domínios conhecidos; adicione mais via ALLOWED_ORIGINS
# (lista separada por vírgula), ex.: ALLOWED_ORIGINS=https://fin.btoplay.com
_ORIGENS_PADRAO = {
    "https://betoschneider.com",
    "https://financeiro.betoschneider.com",
    "http://localhost:8520",
}


def _origens_permitidas() -> set[str]:
    origens = set(_ORIGENS_PADRAO)
    for item in os.getenv("ALLOWED_ORIGINS", "").split(","):
        item = item.strip().rstrip("/")
        if item:
            origens.add(item)
    return origens


def _stamp_se_necessario(cfg: Config) -> None:
    """Bancos antigos criados por create_all (sem versão do alembic) já estão
    com o schema completo: marca a head para o upgrade não tentar recriar
    tabelas existentes."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    tabelas = set(insp.get_table_names())
    if not tabelas:
        return  # banco novo: o upgrade cria tudo do zero

    tem_versao = "alembic_version" in tabelas
    if tem_versao:
        with engine.connect() as conn:
            tem_versao = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).fetchone() is not None
    if tem_versao:
        return

    # Banco não versionado: só marca a head se tiver o schema completo
    # (equivalente ao que o create_all produzia); caso contrário, o upgrade
    # roda as migrations normalmente (banco vazio/incompleto).
    tabelas_modelo = {
        "users", "transacoes", "investment_assets", "investment_metrics",
        "investment_transactions", "categorias", "tipos",
        "financial_insights", "investment_insights",
    }
    if tabelas_modelo.issubset(tabelas):
        command.stamp(cfg, "head")


def _sincronizar_esquema() -> None:
    """Bancos legados (criados por create_all e sem migrations) podem não ter
    tabelas/colunas mais recentes do modelo: completa o que faltar.

    As colunas adicionadas são sempre nullable (equivalentes às que as
    migrations adicionam). Chamado depois do upgrade para cobrir o caso de
    bancos não versionados que foram marcados (stamped) na head.
    """
    from sqlalchemy import inspect, text

    # Cria tabelas que faltam (checkfirst=True por padrão, seguro)
    Base.metadata.create_all(bind=engine)

    insp = inspect(engine)
    with engine.begin() as conn:
        for tabela in Base.metadata.sorted_tables:
            if tabela.name not in insp.get_table_names():
                continue
            existentes = {c["name"] for c in insp.get_columns(tabela.name)}
            for col in tabela.columns:
                if col.name in existentes or col.nullable is False:
                    continue
                tipo = col.type.compile(engine.dialect)
                conn.execute(
                    text(f"ALTER TABLE {tabela.name} ADD COLUMN {col.name} {tipo}")
                )


def rodar_migrations() -> None:
    """Cria/atualiza o banco aplicando as migrations do alembic.

    Garante que um banco criado do zero passe por todas as migrations
    (schema sempre versionado), em vez de usar create_all.
    """
    cfg = Config(str(BASE_DIR / "alembic.ini"))
    _stamp_se_necessario(cfg)
    command.upgrade(cfg, "head")
    # Bancos antigos não versionados podem ter schema desatualizado: completa
    _sincronizar_esquema()


rodar_migrations()


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def count_users(db: Session) -> int:
    return db.query(User).count()


def create_user(db: Session, username: str, password: str) -> User:
    db_user = User(
        username=username.strip(),
        password_hash=hash_password(password),
        totp_secret=pyotp.random_base32(),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def create_user_google(db: Session, username: str) -> User:
    random_pw = bcrypt.gensalt()
    hashed = bcrypt.hashpw(random_pw, bcrypt.gensalt()).decode("utf-8")
    db_user = User(
        username=username.strip(),
        password_hash=hashed,
        totp_secret=pyotp.random_base32(),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def reset_user_password(db: Session, user: User, new_password: str) -> User:
    user.password_hash = hash_password(new_password)
    db.commit()
    db.refresh(user)
    return user


app = FastAPI(title="Controle Financeiro")

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_origens_permitidas()),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserCreate(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    totp_secret: str
    totp_uri: str


class LoginStep1Request(BaseModel):
    username: str
    password: str


class LoginStep2Request(BaseModel):
    username: str
    code: str


class ResetPasswordRequest(BaseModel):
    username: str
    code: str
    new_password: str


@app.post("/api/auth/register", response_model=UserResponse)
def register(
    user_in: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    _verificar_limite_taxa(f"register:{_ip_do_cliente(request)}", 5, 3600)

    username = user_in.username.strip()
    if len(user_in.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A senha deve ter no mínimo 8 caracteres.",
        )

    existing_user = get_user_by_username(db, username)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nome de usuário já cadastrado.",
        )

    try:
        quota = int(os.getenv("ACCOUNT_QUOTA", "0"))
    except Exception:
        quota = 0
    if quota > 0 and count_users(db) >= quota:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Limite de contas atingido."
        )

    user = create_user(db, username, user_in.password)
    totp = pyotp.TOTP(user.totp_secret)
    totp_uri = totp.provisioning_uri(
        name=user.username, issuer_name="ControleFinanceiro"
    )
    return UserResponse(
        id=user.id,
        username=user.username,
        totp_secret=user.totp_secret,
        totp_uri=totp_uri,
    )


@app.post("/api/auth/login/step1")
def login_step1(
    auth_req: LoginStep1Request,
    request: Request,
    db: Session = Depends(get_db),
):
    # Limite de taxa evita ataques de força bruta e enumeração de usuários.
    _verificar_limite_taxa(f"login1:{_ip_do_cliente(request)}", 10, 900)
    user = get_user_by_username(db, auth_req.username)
    if not user or not verify_password(auth_req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos.",
        )
    return {
        "success": True,
        "message": "Senha válida. Prossiga para a autenticação em duas etapas.",
    }


@app.post("/api/auth/login/step2")
def login_step2(
    auth_req: LoginStep2Request,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    _verificar_limite_taxa(f"login2:{_ip_do_cliente(request)}", 10, 900)
    user = get_user_by_username(db, auth_req.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado."
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(auth_req.code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Código de autenticação inválido.",
        )

    session_token = criar_sessao(user.username)
    _definir_cookie_sessao(request, response, session_token)
    return {
        "success": True,
        "message": "Autenticado com sucesso.",
        "session_token": session_token,
    }


@app.post("/api/auth/reset-password")
def reset_password(
    req: ResetPasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _verificar_limite_taxa(f"reset:{_ip_do_cliente(request)}", 5, 900)
    user = get_user_by_username(db, req.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário não encontrado."
        )

    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(req.code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de autenticação inválido para redefinição.",
        )

    if len(req.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A nova senha deve ter no mínimo 8 caracteres.",
        )

    reset_user_password(db, user, req.new_password)
    return {"success": True, "message": "Senha redefinida com sucesso."}


@app.post("/api/auth/logout")
def logout(response: Response, session_token: Optional[str] = Cookie(None)):
    encerrar_sessao(session_token)
    response.delete_cookie("session_token", path="/")
    return {"message": "Sessão encerrada."}


@app.get("/api/auth/status")
def auth_status(session_token: Optional[str] = Cookie(None)):
    """Indica se o cookie de sessão atual é válido.

    Com o cookie HttpOnly, o JavaScript não consegue mais ler o token;
    este endpoint substitui essa verificação no frontend.
    """
    try:
        # authorization=None explícito: o default Header(None) é um objeto,
        # não None — passar explícito evita AttributeError fora do DI do FastAPI.
        verificar_autenticacao(authorization=None, session_token=session_token)
        return {"authenticated": True}
    except HTTPException:
        return {"authenticated": False}


class GoogleLoginRequest(BaseModel):
    code: str
    state: str


@app.post("/api/auth/login/google")
def login_google(
    payload: GoogleLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth não configurado. Configure GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET.",
        )

    _verificar_limite_taxa(f"google:{_ip_do_cliente(request)}", 10, 900)

    # O redirect_uri nunca deve ser derivado de input arbitrário: valida a
    # origem informada (state) contra uma allowlist fixa antes de montar a URL.
    origin = payload.state.rstrip("/") if payload.state else ""
    if origin not in _origens_permitidas():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Origem de redirecionamento inválida.",
        )
    redirect_uri = f"{origin}/google_oauth_callback.html"

    # Troca o authorization code por tokens (requer client_secret)
    try:
        token_resp = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": payload.code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Falha na troca do código de autorização.",
            )
        token_data = token_resp.json()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Falha na troca do código Google")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro na troca do código Google.",
        )

    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="id_token ausente na resposta do Google.",
        )

    # Valida o id_token junto ao Google (assinatura, expiração, emissor e
    # audience) via tokeninfo — sem depender de biblioteca cripto local.
    try:
        info_resp = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
            timeout=10,
        )
        if info_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="id_token inválido ou expirado.",
            )
        info = info_resp.json()
    except HTTPException:
        raise
    except Exception:
        logger.exception("Falha ao validar id_token do Google")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Falha ao validar o token do Google.",
        )

    # Valida claims: audience, emissor e expiração
    if info.get("aud") != GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: audience não corresponde.",
        )
    if info.get("iss") not in ("https://accounts.google.com", "accounts.google.com"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: emissor não corresponde.",
        )
    try:
        exp = int(info.get("exp") or 0)
        if exp and exp < int(time.time()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado.",
            )
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido: expiração ausente.",
        )

    email = info.get("email")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Google inválido: sem email",
        )

    user = get_user_by_username(db, email)
    if not user:
        try:
            quota = int(os.getenv("ACCOUNT_QUOTA", "0"))
        except Exception:
            quota = 0
        if quota > 0 and count_users(db) >= quota:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Limite de contas atingido.",
            )
        user = create_user_google(db, email)

    session_token = criar_sessao(user.username)
    _definir_cookie_sessao(request, response, session_token)
    return {
        "success": True,
        "message": "Autenticado via Google.",
        "session_token": session_token,
    }


app.include_router(transactions.router)
app.include_router(transactions.settings_router)
app.include_router(investments.router)
app.include_router(insights.router)
app.include_router(profile.router)

app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
