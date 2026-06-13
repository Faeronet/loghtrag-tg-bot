#!/bin/sh
set -e

DATA_DIR="/var/lib/telegram-bot-api"
TEMP_DIR="${DATA_DIR}/temp"

mkdir -p "${TEMP_DIR}"

set -- telegram-bot-api \
  --local \
  --http-port=8081 \
  --http-stat-port=8082 \
  --dir="${DATA_DIR}" \
  --temp-dir="${TEMP_DIR}"

if [ -n "${TELEGRAM_PROXY_HOST}" ] && [ -n "${TELEGRAM_PROXY_PORT}" ]; then
  set -- "$@" \
    "--tdlib-proxy-type=${TELEGRAM_PROXY_TYPE:-socks5}" \
    "--proxy-server=${TELEGRAM_PROXY_HOST}" \
    "--proxy-port=${TELEGRAM_PROXY_PORT}"
  if [ -n "${TELEGRAM_PROXY_LOGIN}" ]; then
    set -- "$@" "--proxy-login=${TELEGRAM_PROXY_LOGIN}"
  fi
  if [ -n "${TELEGRAM_PROXY_PASSWORD}" ]; then
    set -- "$@" "--proxy-password=${TELEGRAM_PROXY_PASSWORD}"
  fi
fi

exec "$@"
