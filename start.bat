@echo off
chcp 65001 > nul
TITLE 주차 단속 시스템

:: 현재 디렉토리로 이동
cd /d %~dp0

echo ============================================
echo   주차 단속 시스템 시작
echo ============================================
echo.

:: 기존 프로세스 정리
echo [1/3] 기존 프로세스 정리 중...
taskkill /f /im cloudflared.exe >nul 2>&1
echo 완료

:: 서버 시작
echo [2/3] 서버 시작 중...
echo.
python ocr.py --server

:: 서버 종료 후 정리
echo.
echo [3/3] 정리 중...
taskkill /f /im cloudflared.exe >nul 2>&1
echo.
echo ============================================
echo   서버가 종료되었습니다.
echo ============================================
pause
