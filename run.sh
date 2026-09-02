#!/usr/bin/env bash
# 本地启动脚本：自动读取 .env（如有）再启动应用
set -e
cd "$(dirname "$0")"
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi
exec mvn spring-boot:run
