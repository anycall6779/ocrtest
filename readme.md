# 📸 주차 단속 시스템 (Parking Enforcement OCR)

주차 단속 현장 사진에서 **차량 번호판을 자동으로 인식(OCR)**하고, 단속 내역을 **Excel 파일로 자동 저장**하는 웹 기반 시스템입니다.

## 📌 주요 기능

1. **웹 기반 인터페이스**: PC 및 모바일 브라우저에서 사진 업로드 및 관리
2. **자동 번호판 인식**:
   - YOLO 모델을 통한 차량/번호판 영역 검출
   - 이미지 전처리(Grayscale, CLAHE, Threshold) 후 OCR 수행
   - 오인식 방지 로직 (번호판 패턴 정규식 필터링)
3. **데이터 관리**:
   - 단속 위치, 사유, 시간대별 자동 폴더 분류
   - Excel 자동 저장 (`주차단속내역_YYYY-MM-DD.xlsx`)
   - 백업 시스템으로 데이터 유실 방지
4. **네트워크 접근성**:
   - Cloudflare Tunnel 자동 연동으로 외부 접속 URL 생성
   - 로컬/외부 접속 구분 보안 기능

---

## 📂 버전 비교

이 프로젝트는 **세 가지 버전**을 제공합니다 (Windows, 2.0V, Linux):

| 구분 | Windows 버전 | 2.0V 버전 |
|------|--------------|-----------|
| **위치** | `Windows/` 폴더 | `2.0V/` 폴더 |
| **OCR 엔진** | Windows SDK (`winsdk`) | 전용 DLL (`oneocr.dll`) |
| **장점** | 추가 파일 불필요 | 더 빠른 인식 속도 |
| **단점** | Windows 10+ 필요 | DLL 파일 필요 |
| **추가 기능** | - | Discord 알림, 스마트 로그인 |

### 어떤 버전을 사용해야 할까요?

- **Windows 10 이상** + **간편한 설치** → `Windows/` 버전 권장
- **빠른 인식 속도** + **추가 기능** → `2.0V/` 버전 권장

---

## 🛠 설치 및 실행

### 공통 요구사항
- **운영체제**: Windows 10 이상
- **Python**: 3.8 이상 ([다운로드](https://www.python.org/downloads/))

### 설치 방법
```bash
# 원하는 버전 폴더로 이동
cd Windows   # 또는 cd 2.0V

# 의존성 설치
pip install -r requirements.txt

# 실행
python ocr.py
```

또는 각 폴더의 `start.bat` 파일을 더블클릭하세요.

---

## 🚀 자동 빌드 및 릴리즈 (GitHub Actions)

이 저장소에는 **자동 빌드 및 릴리즈 시스템**이 구축되어 있습니다.
GitHub에 새로운 태그(`v*`)를 푸시하면 자동으로 Windows용 EXE 파일을 빌드하고 Release를 생성합니다.

### 사용 방법

1. **태그 생성 및 푸시**:
   버전 태그(예: `v1.0.0`)를 생성하고 GitHub에 푸시합니다.
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **자동 빌드 시작**:
   GitHub Actions 탭에서 빌드 진행 상황을 확인할 수 있습니다.
   - `Build Windows Version`: Windows 버전 빌드
   - `Build 2.0V Version`: 2.0V 버전 빌드

3. **결과물 다운로드**:
   빌드가 완료되면 [Releases](https://github.com/USERNAME/REPOSITORY/releases) 페이지에 자동으로 새 릴리즈가 생성되고, 다음 파일들이 첨부됩니다:
   - `ParkingEnforcement-Windows.exe`
   - `ParkingEnforcement-2.0V.exe`

---

## 📦 독립 실행 파일 (EXE) 빌드

Python 없이 실행 가능한 단일 EXE 파일을 생성할 수 있습니다.

### 빌드 방법
```bash
# 원하는 버전 폴더로 이동
cd Windows   # 또는 cd 2.0V

# 빌드 실행
build.bat
```

### 빌드 결과
- **생성 위치**: `dist/주차단속시스템.exe`
- **파일 크기**: 약 200~400MB (모든 의존성 포함)

---

## 📂 폴더 구조

```
ocrtest-main/
│
├── readme.md           # 이 파일 (전체 프로젝트 설명)
│
├── Windows/            # Windows OCR 버전
│   ├── ocr.py          # 메인 서버 코드
│   ├── requirements.txt
│   ├── build.spec      # PyInstaller 설정
│   ├── build.bat       # EXE 빌드 스크립트
│   ├── start.bat       # 서버 시작 스크립트
│   ├── best.pt         # YOLO 모델
│   ├── templates/      # HTML 템플릿
│   └── static/         # 정적 리소스
│
└── 2.0V/               # DLL OCR 버전
    ├── ocr.py          # 메인 서버 코드
    ├── requirements.txt
    ├── build.spec      # PyInstaller 설정
    ├── build.bat       # EXE 빌드 스크립트
    ├── start.bat       # 서버 시작 스크립트
    ├── best.pt         # YOLO 모델
    ├── oneocr.dll      # OCR 엔진 DLL
    ├── oneocr.onemodel # OCR 모델 데이터
    ├── onnxruntime.dll # ONNX 런타임
    ├── templates/      # HTML 템플릿
    └── static/         # 정적 리소스
```

---

## ⚙️ 설정 방법

각 버전의 `ocr.py` 파일 상단에서 설정을 변경할 수 있습니다:

```python
# 보안 비밀번호 (빈 문자열 = 비밀번호 없음)
SYSTEM_PASSWORD = "1234"

# 단속 위치 목록
LOCATIONS = ["1동", "2동", "3동", ...]

# 단속 사유 목록
REASONS = ["주차선 외 위반", "장애인 구역 위반", ...]
```

---

## ⚠️ 트러블슈팅

### OCR 인식률이 낮은 경우
- `best.pt` 파일이 있는지 확인하세요
- 이미지가 너무 어둡거나 흐리면 인식률이 떨어집니다

### Excel 저장 실패
- 해당 Excel 파일이 다른 프로그램에서 열려있는지 확인하세요
- `backup/` 폴더에서 백업 파일을 확인할 수 있습니다

### Cloudflare Tunnel 실패
- 인터넷 연결 상태를 확인하세요
- 방화벽이 `cloudflared.exe` 실행을 차단하고 있는지 확인하세요

---

## 📝 사용된 오픈소스

| 구성요소 | 출처 |
|----------|------|
| YOLO 모델 (`best.pt`) | [MuhammadMoinFaisal/Computervisionprojects](https://github.com/MuhammadMoinFaisal/Computervisionprojects/tree/main/ANPR_YOLOv10/weights) |
| OCR 엔진 (2.0V용) | [killkimno/MORT_VERSION](https://github.com/killkimno/MORT_VERSION/releases/download/oneocr/oneocr.zip) |

---

## 📜 라이선스

이 프로젝트는 교육 및 내부 사용 목적으로 제작되었습니다.