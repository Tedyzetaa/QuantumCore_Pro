@echo off
TITLE Instalando Dependencias do Telegram
:: --- CONFIGURAÇÃO ---
SET CONDA_PATH=C:\ProgramData\miniconda3
SET ENV_NAME=r2

echo 🚀 Ativando ambiente Conda (%ENV_NAME%)...
call %CONDA_PATH%\Scripts\activate.bat %CONDA_PATH%
call conda activate %ENV_NAME%

echo 📦 Instalando python-telegram-bot...
pip install python-telegram-bot

echo.
echo ✅ Instalação concluída! Agora você pode rodar o INICIAR_BOT.bat.
pause