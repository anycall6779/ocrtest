@echo off
chcp 65001 > nul
TITLE 주차 단속 시스템 빌더 (DLL OCR 버전 2.0)

echo ============================================
echo   주차 단속 시스템 - EXE 빌드 스크립트
echo   (DLL OCR 버전 2.0 - 자동 추출 지원)
echo ============================================
echo.

:: 현재 디렉토리로 이동
cd /d %~dp0

:: 1. 기본 필수 파일 확인
echo [1/5] 기본 파일 확인 중...
if not exist "ocr.py" (
    echo ❌ 오류: ocr.py 파일을 찾을 수 없습니다.
    pause
    exit /b 1
)
if not exist "dll_extractor.py" (
    echo ❌ 오류: dll_extractor.py 파일을 찾을 수 없습니다.
    pause
    exit /b 1
)
if not exist "best.pt" (
    echo ⚠️  경고: best.pt 파일이 없습니다. 기본 YOLO 모델이 사용됩니다.
)
if not exist "templates" (
    echo ❌ 오류: templates 폴더를 찾을 수 없습니다.
    pause
    exit /b 1
)
echo ✅ 기본 파일 확인 완료
echo.

:: 2. DLL 자동 추출 (없는 경우)
echo [2/5] OCR DLL 확인 및 추출 중...
if not exist "dlls\oneocr.dll" (
    echo    DLL이 없습니다. 자동 추출을 시작합니다...
    python dll_extractor.py
    if errorlevel 1 (
        echo ❌ 오류: DLL 추출 실패
        echo    Snipping Tool 또는 Windows Photos 앱이 설치되어 있는지 확인하세요.
        echo    또는 수동으로 DLL을 dlls 폴더에 복사하세요.
        pause
        exit /b 1
    )
) else (
    echo ✅ DLL 파일이 이미 존재합니다.
)
echo ✅ DLL 준비 완료
echo.

:: 3. 의존성 패키지 설치
echo [3/5] 의존성 패키지 설치 중...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ❌ 오류: 패키지 설치 실패
    pause
    exit /b 1
)
pip install pyinstaller -q
echo ✅ 의존성 설치 완료
echo.

:: 4. 이전 빌드 정리
echo [4/5] 이전 빌드 정리 중...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build
echo ✅ 정리 완료
echo.

:: 5. PyInstaller 빌드 실행
echo [5/5] EXE 빌드 중... (시간이 다소 소요됩니다)
echo.
python -m PyInstaller build.spec --noconfirm
if errorlevel 1 (
    echo.
    echo ❌ 빌드 실패! 오류 메시지를 확인하세요.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   ✅ 빌드 완료!
echo ============================================
echo.
echo   실행 파일 위치: dist\주차단속시스템.exe
echo.
echo   [주의사항]
echo   - EXE 파일에 모든 DLL과 모델이 포함되어 있습니다.
echo   - 첫 실행 시 Windows Defender가 검사할 수 있습니다.
echo.
pause
