# 🚗 주차 단속 시스템 v1.0 (Windows SDK OCR 버전)

이 프로젝트는 **Windows 기반 PC**에서 동작하는 웹 기반 차량 번호판 인식 시스템입니다. 사용자가 촬영한 주차 위반 차량 사진을 업로드하면, AI(YOLO)가 번호판을 찾고 Windows OCR 엔진이 번호를 판독하여 엑셀 리포트로 자동 변환해 줍니다.

> ⚠️ **참고**: 이 버전은 유지보수 상태입니다. 최신 기능은 [2.0V 버전](../2.0V/)을 사용하세요.

---

## ✨ 주요 기능

| 기능 | 설명 |
|------|------|
| **웹 기반 인터페이스** | 별도 설치 없이 브라우저(PC/모바일)로 사진 업로드 |
| **YOLOv8 객체 탐지** | 이미지 내에서 차량 번호판 위치를 정확하게 탐지 |
| **Windows Media OCR** | 로컬 Windows 엔진으로 빠르고 정확한 한글/숫자 인식 |
| **이미지 전처리** | CLAHE(대비 향상), 이진화, 노이즈 제거로 인식률 향상 |
| **자동 보정** | OCR 오인식 문자 자동 변환 (`O`→`0`, `S`→`5`, `I`→`1`) |
| **번호판 패턴 검증** | 대한민국 번호판 정규식(`12가3456` 등) 매칭 및 검증 |
| **보고서 자동화** | 인식 결과를 날짜/시간/사유별로 Excel(.xlsx)로 저장 |
| **외부 접속** | Cloudflare Tunnel로 포트포워딩 없이 외부 접속 가능 |
| **멀티스레딩** | 대량 이미지를 백그라운드에서 비동기 처리 |

---

## 🛠 기술 스택

| 구성요소 | 기술 |
|----------|------|
| **언어** | Python 3.8+ |
| **웹 프레임워크** | Flask, Waitress (Production Server) |
| **AI/CV** | Ultralytics YOLOv8, OpenCV, NumPy |
| **OCR** | Windows SDK (`winsdk.windows.media.ocr`) |
| **데이터** | Pandas, OpenPyXL |
| **네트워크** | Cloudflare Tunnel (`cloudflared`) |

---

## 💻 설치 및 실행 가이드

### 1. 필수 요구 사항

> ⚠️ **중요**: 이 시스템은 **Windows 10 또는 Windows 11** 운영체제에서만 작동합니다. (Windows 내장 OCR 엔진 사용)

- Python 3.8+ 설치 (3.12 권장)
- Microsoft VS C++ Redistributable 설치

### 2. 라이브러리 설치

```bash
pip install flask waitress opencv-python numpy pandas ultralytics winsdk requests openpyxl
```

> **참고**: `winsdk` 설치 시 에러가 발생하면, Visual Studio C++ Build Tools가 설치되어 있는지 확인하세요.

### 3. YOLO 모델 파일 준비

- 사용자 학습된 모델(`best.pt`)이 있다면 프로젝트 루트 폴더에 위치시킵니다.
- 파일이 없으면 실행 시 자동으로 기본 모델(`yolov8n.pt`)을 다운로드하여 사용하지만, 번호판 인식률이 다소 떨어질 수 있습니다.

### 4. 서버 실행

```bash
python ocr.py
```

실행하면 콘솔에 다음과 같은 정보가 출력됩니다:

- 로컬 접속 주소: `http://127.0.0.1:5000`
- 외부 접속 주소: `https://[랜덤문자열].trycloudflare.com` (Cloudflare 터널 성공 시)

---

## 📖 사용 방법

1. **로그인**:
   - 브라우저로 접속 주소에 들어갑니다.
   - 초기 비밀번호 `1234`를 입력합니다. (코드 내 `SYSTEM_PASSWORD` 변수에서 변경 가능)

2. **이미지 업로드**:
   - 단속 위치(동/호수)와 위반 사유를 선택합니다.
   - `파일 선택` 버튼을 눌러 번호판이 찍힌 사진들을 선택하고 `분석 시작`을 클릭합니다.

3. **결과 확인 및 수정**:
   - 분석이 완료되면 번호판 인식 결과가 표시됩니다.
   - 인식이 잘못된 경우 수동으로 번호를 수정할 수 있습니다.

4. **저장**:
   - `결과 저장` 버튼을 누르면 서버의 `Excel` 파일에 내용이 누적 저장됩니다.
   - `리포트` 메뉴에서 저장된 엑셀 파일을 다운로드할 수 있습니다.

---

## 📂 프로젝트 구조

```
Windows/
├── ocr.py               # 메인 서버 코드
├── best.pt              # (권장) 번호판 학습된 YOLO 모델
├── yolov8n.pt           # (자동다운) 기본 YOLO 모델
├── cloudflared.exe      # (자동다운) 외부 접속용 터널 프로그램
├── templates/           # Flask HTML 템플릿
│   ├── index.html
│   └── result.html
├── uploads/             # 업로드된 원본 이미지 (날짜/위치별)
└── 주차단속내역_xxxx.xlsx  # 생성된 결과 엑셀 파일
```

---

## ⚙️ 환경 설정 (Configuration)

`ocr.py` 파일 상단의 설정 구역을 수정하여 커스터마이징할 수 있습니다.

```python
# ==========================================
# 🔒 [보안 설정 구역]
# ==========================================
SYSTEM_PASSWORD = "1234"  # 로그인 비밀번호 변경
app.secret_key = "..."    # 세션 암호화 키 (임의 변경 권장)

# --- [YOLO 모델 경로] ---
YOLO_MODEL_PATH = os.path.join(BASE_DIR, 'best.pt') # 모델 파일명 변경 시 수정
```

---

## 🔍 문제 해결 (Troubleshooting)

**Q. `ModuleNotFoundError: No module named 'winsdk'` 오류가 납니다.**

- A. `pip install winsdk`를 실행하세요. 이 라이브러리는 Windows OS에서만 설치 가능합니다.

**Q. 외부 접속 URL이 생성되지 않습니다.**

- A. 처음 실행 시 `cloudflared.exe`를 다운로드하는 데 시간이 걸릴 수 있습니다. 인터넷 연결을 확인하고 방화벽이 차단하지 않는지 확인하세요.

**Q. OCR 인식률이 너무 낮습니다.**

- A.
  1. 사진 촬영 시 번호판이 너무 작거나 흐리지 않게 찍어주세요.
  2. `best.pt` 모델이 번호판 영역만 정확히 자르도록 학습된 모델인지 확인하세요.
  3. 코드 내 `process_and_ocr` 함수의 전처리 필터 순서를 조정해 볼 수 있습니다.

**Q. WinSDK 설치 오류**

- A. Python 버전을 확인하세요. 3.12 버전 권장입니다.

---

## 📝 라이선스 및 저작권

이 프로젝트는 교육 및 내부 사용 목적으로 제작되었습니다.

### 사용된 오픈소스

| 구성요소 | 출처 |
|----------|------|
| YOLO best.pt | [MuhammadMoinFaisal/Computervisionprojects](https://github.com/MuhammadMoinFaisal/Computervisionprojects/tree/main/ANPR_YOLOv10/weights) |
