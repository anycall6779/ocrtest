# 📸 주차 단속 시스템 (DLL OCR 버전 2.0)

차량 번호판을 자동으로 인식하여 단속 내역을 Excel 파일로 저장하는 웹 기반 시스템입니다.

## 📌 특징

- **전용 OCR 엔진 사용**: `oneocr.dll` 기반의 고성능 OCR 엔진
- **YOLOv8 객체 탐지**: 이미지에서 번호판 영역을 자동 검출
- **웹 기반 인터페이스**: PC 및 모바일 브라우저에서 접속 가능
- **Cloudflare Tunnel**: 외부에서도 접속 가능한 공개 URL 자동 생성
- **Discord 알림**: 서버 시작 시 Discord 웹훅으로 알림 전송 (선택)
- **자동 백업**: Excel 파일 저장 실패 시 자동 백업

## 🛠 설치 방법

### 1. Python 설치
Python 3.8 이상이 필요합니다.  
[Python 공식 다운로드](https://www.python.org/downloads/)

### 2. 의존성 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 필수 파일 확인
| 파일명 | 설명 | 필수 여부 |
|--------|------|-----------|
| `ocr.py` | 메인 서버 코드 | ✅ 필수 |
| `dll_extractor.py` | DLL 자동 추출 모듈 | ✅ 필수 |
| `best.pt` | YOLO 번호판 탐지 모델 | ⚠️ 권장 |
| `templates/` | 웹 페이지 HTML 파일들 | ✅ 필수 |
| `static/` | 정적 리소스 | ✅ 필수 |

### 4. OCR 엔진 (자동 추출)

> **⚡ 버전 2.0부터 OCR DLL이 자동으로 추출됩니다!**

프로그램 첫 실행 시 Windows에 설치된 **Snipping Tool** 또는 **Windows Photos** 앱에서 OCR 엔진을 자동으로 추출합니다.

**자동 추출 원리** (MORT 프로젝트 방식):
1. `Microsoft.ScreenSketch` (Snipping Tool) 검색
2. 없으면 `Microsoft.Windows.Photos` 검색  
3. 앱에서 `oneocr.dll`, `oneocr.onemodel`, `onnxruntime.dll` 복사

**수동 설치가 필요한 경우** (앱이 없는 경우):
- Microsoft Store에서 'Snipping Tool' 앱 설치
- 또는 [oneocr.zip](https://github.com/killkimno/MORT_VERSION/releases/download/oneocr/oneocr.zip) 다운로드 후 `dlls/` 폴더에 압축 해제

## 🚀 실행 방법

### 방법 1: start.bat 실행 (권장)
`start.bat` 파일을 더블클릭하세요.

### 방법 2: 직접 실행
```bash
python ocr.py
```

### 접속 주소
- **로컬**: `http://127.0.0.1:5000` (비밀번호 없이 자동 로그인)
- **외부**: 콘솔에 표시되는 `https://xxx.trycloudflare.com` 주소

### 🖥️ 실행 모드

| 모드 | 설명 | 실행 방법 |
|------|------|-----------|
| **GUI 모드** | 데스크톱 앱 (기본) | `python ocr.py` 또는 EXE 더블클릭 |
| **서버 모드** | 웹 서버 | `python ocr.py --server` |

GUI 모드에서는 브라우저 없이 직접 이미지를 선택하고 번호판을 인식할 수 있습니다.

## 📦 EXE 빌드 (독립 실행 파일 생성)

Python 없이 실행 가능한 단일 EXE 파일을 생성합니다.

### 빌드 방법
```bash
build.bat
```
또는
```bash
pyinstaller build.spec --noconfirm
```

### 빌드 결과
- 생성 위치: `dist/주차단속시스템.exe`
- 모든 DLL과 모델이 EXE 파일에 포함됨

### 주의사항
- 빌드 시간: 약 3~5분 소요
- 파일 크기: 약 200~400MB
- 첫 실행 시 Windows Defender 검사가 발생할 수 있음

## ⚙️ 설정

`ocr.py` 파일 상단에서 설정 변경 가능:

```python
# 보안 비밀번호 (빈 문자열이면 비밀번호 없음)
SYSTEM_PASSWORD = ""

# Discord 웹훅 URL (서버 시작 알림)
DISCORD_WEBHOOK_URL = ""

# 고정 도메인 Cloudflare Tunnel (선택사항)
# Cloudflare Zero Trust에서 터널 생성 후 토큰 복사
CLOUDFLARE_TUNNEL_TOKEN = ""
CLOUDFLARE_TUNNEL_DOMAIN = "parking.example.com"

# 단속 위치 목록
LOCATIONS = ["1동", "2동", "3동", ...]

# 단속 사유 목록
REASONS = ["주차선 외 위반", "장애인 구역 위반", ...]
```

### 고정 도메인 터널 설정 방법
1. [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) 접속
2. Networks → Tunnels → Create a tunnel
3. 터널 이름 입력 후 토큰 복사
4. Public Hostname 설정 (예: parking.example.com → http://localhost:5000)
5. `ocr.py`의 `CLOUDFLARE_TUNNEL_TOKEN`과 `CLOUDFLARE_TUNNEL_DOMAIN`에 값 입력

## 📂 폴더 구조

```
2.0V/
├── ocr.py              # 메인 서버 코드
├── dll_extractor.py    # DLL 자동 추출 모듈
├── dlls/               # [자동생성] OCR 엔진 폴더
│   ├── oneocr.dll         # (자동 추출됨)
│   ├── oneocr.onemodel    # (자동 추출됨)
│   └── onnxruntime.dll    # (자동 추출됨)
├── best.pt             # YOLO 모델 (번호판 탐지)
├── requirements.txt    # Python 의존성 목록
├── build.spec          # PyInstaller 빌드 설정
├── build.bat           # EXE 빌드 스크립트
├── start.bat           # 서버 시작 스크립트
├── templates/          # HTML 템플릿
├── static/             # 정적 리소스
├── uploads/            # [자동생성] 업로드된 이미지
├── backup/             # [자동생성] 백업 파일
└── dist/               # [빌드 후 생성] EXE 파일
```

## ⚠️ 트러블슈팅

### "oneocr.dll을 찾을 수 없습니다" 오류
1. **Snipping Tool 앱 설치 확인**: Microsoft Store에서 'Snipping Tool' 또는 'Windows Photos' 앱이 설치되어 있는지 확인
2. **DLL 수동 추출 시도**: `python dll_extractor.py --force` 실행
3. **수동 다운로드**: [oneocr.zip](https://github.com/killkimno/MORT_VERSION/releases/download/oneocr/oneocr.zip) 다운로드 후 `dlls/` 폴더에 압축 해제

### OCR 인식률이 낮은 경우
- `best.pt` 파일이 있는지 확인하세요
- 이미지가 너무 어둡거나 흐리면 인식률이 떨어집니다

### Excel 저장 실패
- 해당 Excel 파일이 다른 프로그램에서 열려있는지 확인하세요
- `backup/` 폴더에 자동 백업됩니다

## 📝 라이선스

이 프로젝트는 교육 및 내부 사용 목적으로 제작되었습니다.

### 사용된 오픈소스
- **YOLO best.pt**: [MuhammadMoinFaisal/Computervisionprojects](https://github.com/MuhammadMoinFaisal/Computervisionprojects/tree/main/ANPR_YOLOv10/weights)
- **OCR 엔진**: [killkimno/MORT_VERSION](https://github.com/killkimno/MORT_VERSION/releases/download/oneocr/oneocr.zip)
