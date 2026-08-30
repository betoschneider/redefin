FROM ghcr.io/astral-sh/uv:python3.12-alpine

# Cria usuário não-root (UID 1000) para rodar a aplicação.
# O volume ./data do docker-compose deve ser gravável por este UID no host.
RUN adduser -D -u 1000 -h /app app

# su-exec permite ao entrypoint corrigir as permissões de /app/data (como
# root, para o bind mount ./data do host) e descer para o usuário app
# antes de rodar o app. O processo da aplicação nunca roda como root.
RUN apk add --no-cache su-exec

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Cria diretório data/ para o banco SQLite
RUN mkdir -p /app/data

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/
COPY entrypoint.sh ./entrypoint.sh

# Garante que os arquivos da aplicação, migrations e data pertencem ao usuário app
RUN chown -R app:app /app/app /app/data /app/alembic /app/alembic.ini /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

# Sem USER app fixo: o entrypoint roda como root só para garantir as
# permissões de /app/data e desce para o usuário app via su-exec.
EXPOSE 8520

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8520"]
