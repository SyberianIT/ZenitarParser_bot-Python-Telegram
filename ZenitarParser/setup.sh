#!/bin/bash

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}========================================${NC}"
echo -e "${GREEN}🚀 Установка ZenitarParser${NC}"
echo -e "${YELLOW}========================================${NC}"

# Переходим в папку ZenitarParser
cd /home/serj/Документы/ZenitarParser || {
    echo -e "${RED}❌ Папка не найдена!${NC}"
    exit 1
}

echo -e "${GREEN}📁 Папка: $(pwd)${NC}"

# Удаляем старое виртуальное окружение если есть
if [ -d "venv" ]; then
    echo -e "${YELLOW}🗑 Удаляем старое виртуальное окружение...${NC}"
    deactivate 2>/dev/null
    rm -rf venv
fi

# Создаем новое виртуальное окружение
echo -e "${GREEN}🔨 Создаем виртуальное окружение...${NC}"
python3 -m venv venv

# Активируем виртуальное окружение
echo -e "${GREEN}✅ Активируем виртуальное окружение...${NC}"
source venv/bin/activate

# Обновляем pip
echo -e "${GREEN}📦 Обновляем pip...${NC}"
pip install --upgrade pip

# Устанавливаем зависимости
echo -e "${GREEN}📦 Устанавливаем зависимости...${NC}"

# Проверяем есть ли requirements.txt
if [ -f "requirements.txt" ]; then
    echo -e "${GREEN}📄 Найден requirements.txt, устанавливаем...${NC}"
    pip install -r requirements.txt
else
    echo -e "${YELLOW}⚠️ requirements.txt не найден, устанавливаем вручную...${NC}"
    pip install aiogram==3.10.0
    pip install pyrogram==2.0.106
    pip install tgcrypto==1.2.5
    pip install aiohttp==3.9.1
fi

# Проверяем установку
echo -e "${YELLOW}========================================${NC}"
echo -e "${GREEN}📋 Установленные пакеты:${NC}"
pip list
echo -e "${YELLOW}========================================${NC}"

# Создаем requirements.txt с текущими версиями
echo -e "${GREEN}📄 Создаем requirements.txt с текущими версиями...${NC}"
pip freeze > requirements.txt

# Проверяем папку sessions
if [ ! -d "sessions" ]; then
    echo -e "${GREEN}📁 Создаем папку sessions...${NC}"
    mkdir sessions
fi

# Проверяем config.py
if [ ! -f "config.py" ]; then
    echo -e "${YELLOW}⚠️ config.py не найден!${NC}"
    echo -e "${YELLOW}📝 Создаем шаблон config.py...${NC}"
    cat > config.py << EOF
# Конфигурация бота
API_ID = 1234567  # Замени на свой API ID
API_HASH = "ваш_api_hash"  # Замени на свой API HASH
BOT_TOKEN = "ваш_токен_бота"  # Замени на токен от @BotFather
ADMIN_ID = 123456789  # Замени на свой Telegram ID
EOF
    echo -e "${RED}⚠️ НЕ ЗАБУДЬ ЗАПОЛНИТЬ config.py!${NC}"
fi

echo -e "${YELLOW}========================================${NC}"
echo -e "${GREEN}✅ Установка завершена!${NC}"
echo -e "${GREEN}📌 Чтобы активировать окружение:${NC}"
echo -e "   ${YELLOW}source venv/bin/activate${NC}"
echo -e "${GREEN}📌 Чтобы запустить бота:${NC}"
echo -e "   ${YELLOW}python app.py${NC}"
echo -e "${GREEN}📌 Чтобы создать сессию:${NC}"
echo -e "   ${YELLOW}python create_session.py${NC}"
echo -e "${YELLOW}========================================${NC}"

# Деактивируем
deactivate 2>/dev/null