@echo off
:: --- SOLICITAR ADMINISTRADOR ---
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    goto UACPrompt
) else ( goto gotAdmin )

:UACPrompt
    echo Set UAC = CreateObject^("Shell.Application"^) > "%temp%\getadmin.vbs"
    echo UAC.ShellExecute "%~s0", "", "", "runas", 1 >> "%temp%\getadmin.vbs"
    "%temp%\getadmin.vbs"
    exit /B

:gotAdmin
    if exist "%temp%\getadmin.vbs" ( del "%temp%\getadmin.vbs" )
    :: Define a pasta do script como diretório de trabalho
    cd /d "%~dp0"

:: --- CONFIGURAÇÃO E EXECUÇÃO ---
TITLE QuantumCore Pro - ADMIN MODE
SET CONDA_PATH=C:\ProgramData\miniconda3
SET ENV_NAME=r2

echo 🚀 Ativando ambiente Conda (%ENV_NAME%)...
call %CONDA_PATH%\Scripts\activate.bat %CONDA_PATH%
call conda activate %ENV_NAME%

echo 🤖 Iniciando o QuantumCore Pro...
python main.py

pause