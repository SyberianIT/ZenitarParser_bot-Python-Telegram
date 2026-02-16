Write-Host "========================================" -ForegroundColor Yellow
Write-Host "🚀 Установка ZenitarParser" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Yellow

# Переходим в папку
Set-Location -Path "C:\Users\serj\Documents\ZenitarParser" -ErrorAction Stop

Write-Host "📁 Папка: $(Get-Location)" -ForegroundColor Green

# Удаляем старое виртуальное окружение
if (Test-Path "venv") {
    Write-Host "🗑 Удаляем старое виртуальное окружение..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force "venv"
}

# Создаем виртуальное окружение
Write-Host "🔨 Создаем виртуальное окружение..." -ForegroundColor Green
python -m venv venv

# Активируем
Write-Host "✅ Активируем виртуальное окружение..." -ForegroundColor Green
& .\venv\Scripts\Activate.ps1

# Обновляем pip
Write-Host "📦 Обновляем pip..." -ForegroundColor Green
python -m pip install --upgrade pip

# Устанавливаем зависимости
Write-Host "📦 Устанавливаем зависимости..." -ForegroundColor Green
pip install aiogram==3.10.0 pyrogram==2.0.106 tgcrypto==1.2.5 aiohttp==3.9.1

# Показываем установленные пакеты
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "📋 Установленные пакеты:" -ForegroundColor Green
pip list
Write-Host "========================================" -ForegroundColor Yellow

# Создаем папку sessions
if (-not (Test-Path "sessions")) {
    Write-Host "📁 Создаем папку sessions..." -ForegroundColor Green
    New-Item -ItemType Directory -Path "sessions"
}

Write-Host "========================================" -ForegroundColor Yellow
Write-Host "✅ Установка завершена!" -ForegroundColor Green
Write-Host "📌 Чтобы активировать окружение:" -ForegroundColor Green
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Yellow
Write-Host "📌 Чтобы запустить бота:" -ForegroundColor Green
Write-Host "   python app.py" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow

deactivate