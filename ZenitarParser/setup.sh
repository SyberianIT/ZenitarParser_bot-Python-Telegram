#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}======================================${NC}"
echo -e "${GREEN}  ZenitarParser Pro — Установка${NC}"
echo -e "${YELLOW}======================================${NC}"

# Создаём venv
python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip -q
pip install -r requirements.txt -q

# Папки
mkdir -p sessions exports

# .env шаблон
if [ ! -f .env ]; then
cat > .env << 'ENVEOF'
# https://my.telegram.org → API_ID и API_HASH
API_ID=0
API_HASH=your_api_hash_here

# Токен от @BotFather
BOT_TOKEN=your_bot_token_here

# Telegram ID администратора (узнать у @userinfobot)
# Несколько: 123456,789012
ADMIN_IDS=123456789
ENVEOF
    echo -e "${RED}⚠️  Создан .env — заполните его перед запуском!${NC}"
fi

echo ""
echo -e "${GREEN}✅ Установка завершена!${NC}"
echo ""
echo "  Заполните .env файл, затем:"
echo -e "  ${YELLOW}source venv/bin/activate && python main.py${NC}"
echo ""
echo "  Добавление аккаунтов для парсинга:"
echo "  В боте → 👥 Аккаунты → ➕ Добавить аккаунт"
echo -e "${YELLOW}======================================${NC}"