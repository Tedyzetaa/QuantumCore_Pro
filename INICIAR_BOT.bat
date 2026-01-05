@echo off
title QUANTUM CORE v15 - INSTITUTIONAL LAUNCHER
color 0A
cls

echo ==================================================
echo      QUANTUM CORE - SISTEMA DE TRADING PRO
echo ==================================================
echo.

:: 1. Tenta ativar o ambiente virtual (R2)
:: O script assume que a pasta 'Scripts' está um nível acima, baseado no seu caminho c:\R1\bottrade6\
if exist "..\Scripts\activate.bat" (
    echo [BOOT] Ativando ambiente virtual (R2)...
    call "..\Scripts\activate.bat"
) else (
    echo [AVISO] Ambiente virtual nao encontrado no caminho padrao.
    echo [INFO] Tentando usar o Python global...
)

:: 2. Verifica se o CustomTkinter esta instalado
python -c "import customtkinter" 2>NUL
if %errorlevel% neq 0 (
    echo [SETUP] Bibliotecas visuais faltando. Instalando agora...
    pip install customtkinter packaging pillow matplotlib mplfinance pandas ccxt requests
    echo [SETUP] Instalacao concluida!
)

:: 3. Inicia o Bot
echo [BOOT] Inicializando Interface e Motor de Trading...
echo.
python main.py

:: 4. Se o bot fechar por erro, mantem a tela aberta
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo ==================================================
    echo [ERRO CRITICO] O sistema parou inesperadamente.
    echo Verifique a mensagem de erro acima.
    echo ==================================================
    pause..
)