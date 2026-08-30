#!/bin/sh
set -e

# Garante que /app/data exista e pertença ao usuário app (UID 1000).
#
# Com o bind mount (./data:/app/data), a pasta do host pode pertencer a
# outro UID (ou ser criada como root pelo Docker num clone novo). Este passo
# roda enquanto o container ainda é root e desce para o usuário app via
# su-exec, então o banco SQLite é gravável em qualquer host — sem passos
# manuais de chown.
if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/data
    chown -R app:app /app/data
    exec su-exec app "$@"
fi

# Já executando como app (ou fora do container): roda direto.
exec "$@"
