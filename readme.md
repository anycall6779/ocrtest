# 🚗 주차 단속 시스템 (Parking Enforcement System)

> 주차 단속 현장 사진에서 **차량 번호판을 자동으로 인식(OCR)**하고, 단속 내역을 **Excel 파일로 자동 저장**하는 웹 기반 시스템

[![Build and Release](https://github.com/hohofught/ocrtest/actions/workflows/build-release.yml/badge.svg)](https://github.com/hohofught/ocrtest/actions/workflows/build-release.yml)

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| **번호판 자동 인식** | YOLOv8 + OneOCR 기반 고정밀 OCR |
| **웹 기반 인터페이스** | PC/모바일 브라우저에서 사진 업로드 |
| **GUI 모드** | Tkinter 기반 데스크톱 앱으로 직접 실행 가능 |
| **Excel 자동 저장** | 단속 내역을 날짜별 엑셀 파일로 저장 |
| **외부 접속** | Cloudflare Tunnel로 외부 접속 URL 자동 생성 |
| **Discord 알림** | 서버 시작 시 Discord 웹훅 알림 지원 |
| **자동 DLL 추출** | Windows 앱에서 OCR 엔진 자동 추출 |

---

## 📥 다운로드 및 설치

### 방법 1: 릴리즈에서 EXE 다운로드 (권장)

1. [Releases](https://github.com/hohofught/ocrtest/releases) 페이지에서 최신 `주차단속시스템.exe` 다운로드
2. 더블클릭으로 실행
3. GUI 앱이 열리면 바로 사용 시작

> ⚠️ 첫 실행 시 Windows Defender가 검사할 수 있습니다 (1~2분 소요)

### 방법 2: 소스코드에서 직접 실행

```bash
# 저장소 클론
git clone https://github.com/hohofught/ocrtest.git
cd ocrtest

# 의존성 설치
pip install -r requirements.txt

# GUI 모드 실행
python ocr.py

# 서버 모드 실행
python ocr.py --server
```

---

## 🚀 실행 모드

| 모드 | 명령어 | 설명 |
|------|--------|------|
| **GUI 모드** (기본) | `python ocr.py` 또는 EXE 더블클릭 | 데스크톱 앱으로 실행, 이미지 직접 선택 |
| **서버 모드** | `python ocr.py --server` | 웹 서버만 실행, 브라우저로 접속 |

### 접속 주소 (서버 모드)

- **로컬 접속**: `http://127.0.0.1:5000`  
- **외부 접속**: 콘솔에 표시되는 `https://xxx.trycloudflare.com`

---

## ⚙️ 설정 변경

`ocr.py` 파일 상단에서 설정 변경 가능:

```python
# 🔒 보안 비밀번호 (빈 문자열 = 비밀번호 없음)
SYSTEM_PASSWORD = ""

# 📍 단속 위치 목록
LOCATIONS = ["1동", "2동", "3동", "4동", "5동", ...]

# 📋 단속 사유 목록
REASONS = ["주차선 외 위반", "장애인 구역 위반", ...]

# 🔔 Discord 웹훅 URL (선택사항)
DISCORD_WEBHOOK_URL = ""

# 🌐 고정 도메인 Cloudflare Tunnel (선택사항)
CLOUDFLARE_TUNNEL_TOKEN = ""
CLOUDFLARE_TUNNEL_DOMAIN = "parking.example.com"
```

---

## 📦 직접 빌드하기

### 로컬 빌드

```bash
build.bat
```

빌드 완료 후 `dist/주차단속시스템.exe` 생성됨 (약 200~400MB)

### GitHub Actions 자동 빌드

태그를 푸시하면 자동으로 빌드 및 릴리즈됩니다:

```bash
git tag v2.0.0
git push origin v2.0.0
```

자동으로 OCR DLL 다운로드 → PyInstaller 빌드 → GitHub Release 생성

---

## 📂 폴더 구조

```
ocrtest/
├── ocr.py               # 메인 서버 코드
├── gui.py               # GUI 인터페이스
├── dll_extractor.py     # DLL 자동 추출 모듈
├── settings_manager.py  # 설정 관리
├── requirements.txt     # Python 의존성
├── build.spec           # PyInstaller 빌드 설정
├── build.bat            # 빌드 스크립트
├── best.pt              # YOLO 모델 (번호판 탐지)
├── dlls/                # [자동생성] OCR 엔진 DLL
├── templates/           # HTML 템플릿
├── static/              # 정적 리소스
├── uploads/             # [자동생성] 업로드된 이미지
│
└── .github/workflows/   # GitHub Actions 설정
    └── build-release.yml
```

---

## ⚠️ 트러블슈팅

### "oneocr.dll을 찾을 수 없습니다" 오류

1. **Snipping Tool 설치 확인**: Microsoft Store에서 'Snipping Tool' 앱 설치
2. **DLL 수동 추출**: `python dll_extractor.py --force` 실행
3. **수동 다운로드**: [oneocr.zip](https://github.com/killkimno/MORT_VERSION/releases/download/oneocr/oneocr.zip) 다운로드 후 `dlls/` 폴더에 압축 해제

### OCR 인식률이 낮은 경우

- `best.pt` 파일이 있는지 확인
- 이미지가 너무 어둡거나 흐리면 인식률이 떨어집니다

### Excel 저장 실패

- 해당 Excel 파일이 다른 프로그램에서 열려있는지 확인
- `backup/` 폴더에 자동 백업됩니다

### Cloudflare Tunnel 실패

- 인터넷 연결 상태 확인
- 방화벽에서 `cloudflared.exe` 허용 필요

---

## 🔧 기술 스택

| 구성요소 | 기술 |
|----------|------|
| **백엔드** | Python 3.8+, Flask, Waitress |
| **OCR 엔진** | OneOCR DLL (Windows 내장 OCR 기반) |
| **객체 탐지** | YOLOv8 (Ultralytics) |
| **이미지 처리** | OpenCV, Pillow, NumPy |
| **데이터 처리** | Pandas, Openpyxl |
| **GUI** | Tkinter |
| **터널링** | Cloudflare Tunnel |

---

## 📝 사용된 오픈소스

| 구성요소 | 출처 |
|----------|------|
| YOLO 모델 (`best.pt`) | [MuhammadMoinFaisal/Computervisionprojects](https://github.com/MuhammadMoinFaisal/Computervisionprojects/tree/main/ANPR_YOLOv10/weights) |
| OCR 엔진 | [killkimno/MORT_VERSION](https://github.com/killkimno/MORT_VERSION/releases/download/oneocr/oneocr.zip) |

---

## 📜 라이선스

이 프로젝트는 교육 및 내부 사용 목적으로 제작되었습니다.