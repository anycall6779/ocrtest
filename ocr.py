import os
import sys
import shutil
import re
import threading
import urllib.parse
import cv2
import numpy as np
import uuid
import gc
import time
import socket
import requests
import subprocess
import ctypes
import pandas as pd
from datetime import datetime
from functools import wraps
from collections import Counter
from ctypes import Structure, byref, POINTER, c_int64, c_int32, c_float, c_ubyte, c_char, c_char_p
from contextlib import contextmanager

from ultralytics import YOLO
from flask import Flask, render_template, request, send_from_directory, jsonify, redirect, url_for, session
from waitress import serve

# 설정 관리자 import
from settings_manager import get_settings, init_settings
from archive_manager import archive_expired_files
from plate_rules import (
    PlateHistoryIndex,
    choose_best_candidate,
    extract_plate_candidates,
    is_valid_plate,
    normalize_plate_candidate,
)

# ==========================================
# 1. 시스템 설정 및 라이브러리 로드
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 설정 관리자 초기화
_app_settings = init_settings()

# 동적 폴더 경로 (설정 파일에서 로드, 없으면 기본값)
def get_upload_dir():
    custom = _app_settings.get("input_folder", "")
    return custom if custom else os.path.join(BASE_DIR, 'uploads')

def get_backup_dir():
    custom = _app_settings.get("output_folder", "")
    return custom if custom else os.path.join(BASE_DIR, 'backup')

def get_excel_dir():
    custom = _app_settings.get("excel_save_folder", "")
    return custom if custom else BASE_DIR


_plate_history_index = None
_plate_history_lock = threading.Lock()


def _history_workbooks():
    """누적 백업 중 날짜/시간대별 최종 스냅샷만 선택한다."""
    search_roots = {
        os.path.abspath(get_excel_dir()),
        os.path.abspath(os.path.join(BASE_DIR, "excel")),
        os.path.abspath(get_backup_dir()),
    }
    grouped = {}
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for current_root, _, files in os.walk(root):
            for filename in files:
                if not filename.lower().endswith(".xlsx") or filename.startswith("~$"):
                    continue
                path = os.path.join(current_root, filename)
                date_match = re.search(r"\d{4}-\d{2}-\d{2}", filename) or re.search(r"\d{4}-\d{2}-\d{2}", current_root)
                date_key = date_match.group(0) if date_match else os.path.dirname(path)
                shift = "오후" if "오후" in filename else "오전" if "오전" in filename else "기타"
                key = (date_key, shift)
                # 메인 누적 파일을 우선하고, 같은 종류에서는 가장 최근 파일을 사용한다.
                priority = (1 if filename.startswith("주차단속내역_") else 0, os.path.getmtime(path))
                if key not in grouped or priority > grouped[key][0]:
                    grouped[key] = (priority, path)
    return [item[1] for item in grouped.values()]


def get_plate_history_index():
    """기존 Excel의 사용자 확인 결과를 한 번만 읽어 OCR 사전확률로 사용한다."""
    global _plate_history_index
    if _plate_history_index is not None:
        return _plate_history_index
    with _plate_history_lock:
        if _plate_history_index is not None:
            return _plate_history_index
        plates = []
        seen_rows = set()
        for path in _history_workbooks():
            try:
                frame = pd.read_excel(path, dtype=str)
                if "차량번호" not in frame.columns:
                    continue
                for _, row in frame.fillna("").iterrows():
                    plate = str(row.get("차량번호", "")).replace(" ", "")
                    record_key = (
                        str(row.get("날짜", "")), str(row.get("시간대", "")),
                        str(row.get("단속위치", "")), str(row.get("사유", "")), plate,
                    )
                    if record_key not in seen_rows:
                        seen_rows.add(record_key)
                        plates.append(plate)
            except Exception as exc:
                print(f"⚠️ 번호판 이력 읽기 실패: {os.path.basename(path)} ({exc})")
        _plate_history_index = PlateHistoryIndex.from_plates(plates)
        print(f"📚 번호판 이력 인덱스: {len(plates)}건 / {len(_plate_history_index.counts)}개 숫자 패턴")
        return _plate_history_index

# 기본 폴더 (이전 버전 호환용)
UPLOAD_DIR = get_upload_dir()
BACKUP_DIR = get_backup_dir()

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# ==========================================
# 오래된 Excel/이미지 자동 보관
# ==========================================
_archive_maintenance_started = False
_archive_maintenance_lock = threading.Lock()


def run_archive_maintenance():
    result = archive_expired_files(
        base_dir=BASE_DIR,
        upload_dir=UPLOAD_DIR,
        retention_days=2,
    )
    if result.excel_moved or result.images_moved or result.errors:
        print(
            f"🗄️ 자동 보관: Excel {result.excel_moved}개, "
            f"이미지 {result.images_moved}개 이동, 오류 {result.errors}개"
        )
    return result


def _archive_maintenance_worker():
    while True:
        try:
            run_archive_maintenance()
        except Exception as exc:
            print(f"⚠️ 자동 보관 작업 실패: {exc}")
        # 서버/GUI 장기 실행 중에도 6시간마다 다시 확인한다.
        time.sleep(6 * 60 * 60)


def start_archive_maintenance():
    global _archive_maintenance_started
    with _archive_maintenance_lock:
        if _archive_maintenance_started:
            return
        _archive_maintenance_started = True
        thread = threading.Thread(target=_archive_maintenance_worker, daemon=True, name="archive-maintenance")
        thread.start()


start_archive_maintenance()

# OCR 설정 (DLL 및 모델 파일명)
MODEL_NAME = 'oneocr.onemodel'
DLL_NAME = 'oneocr.dll'
MODEL_KEY = b"kj)TGtrK>f]b[Piow.gU+nC@s\"\"\"\"\"\"4"

# ==========================================
# [보안 설정 & 디스코드 알림] - 설정 파일에서 동적 로드
# ==========================================
SYSTEM_PASSWORD = ""  
SECRET_KEY = "super_secret_security_key_change_this"

# 동적 설정 (설정 파일에서 로드)
def get_discord_webhook_url():
    return _app_settings.get("discord_webhook_url", "")

def get_cloudflare_tunnel_token():
    return _app_settings.get("cloudflare_tunnel_token", "")

def get_cloudflare_tunnel_domain():
    return _app_settings.get("cloudflare_tunnel_domain", "")

# 이전 버전 호환용 상수 (빈 문자열로 유지, 실제로는 함수 사용)
DISCORD_WEBHOOK_URL = ""
CLOUDFLARE_TUNNEL_TOKEN = ""
CLOUDFLARE_TUNNEL_DOMAIN = ""

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB 최대 업로드

# 전역 변수
excel_lock = threading.Lock()
tasks = {}

# ==========================================
# 2. Ctypes 구조체 및 DLL 정의 (OCR)
# ==========================================
c_int64_p = POINTER(c_int64)
c_float_p = POINTER(c_float)
c_ubyte_p = POINTER(c_ubyte)

class ImageStructure(Structure):
    _fields_ = [
        ('type', c_int32),
        ('width', c_int32),
        ('height', c_int32),
        ('_reserved', c_int32),
        ('step_size', c_int64),
        ('data_ptr', c_ubyte_p)
    ]

class BoundingBox(Structure):
    _fields_ = [
        ('x1', c_float), ('y1', c_float), ('x2', c_float), ('y2', c_float),
        ('x3', c_float), ('y3', c_float), ('x4', c_float), ('y4', c_float)
    ]

DLL_FUNCTIONS = [
    ('CreateOcrInitOptions', [c_int64_p], c_int64),
    ('OcrInitOptionsSetUseModelDelayLoad', [c_int64, c_char], c_int64),
    ('CreateOcrPipeline', [c_char_p, c_char_p, c_int64, c_int64_p], c_int64),
    ('CreateOcrProcessOptions', [c_int64_p], c_int64),
    ('OcrProcessOptionsSetMaxRecognitionLineCount', [c_int64, c_int64], c_int64),
    ('RunOcrPipeline', [c_int64, POINTER(ImageStructure), c_int64, c_int64_p], c_int64),
    ('GetOcrLineCount', [c_int64, c_int64_p], c_int64),
    ('GetOcrLine', [c_int64, c_int64, c_int64_p], c_int64),
    ('GetOcrLineContent', [c_int64, POINTER(c_char_p)], c_int64),
    ('ReleaseOcrResult', [c_int64], None),
    ('ReleaseOcrInitOptions', [c_int64], None),
    ('ReleaseOcrPipeline', [c_int64], None),
    ('ReleaseOcrProcessOptions', [c_int64], None)
]

# ==========================================
# DLL 자동 추출 및 로드
# ==========================================
# MORT 프로젝트 방식: Windows Snipping Tool/Photos 앱에서 DLL 자동 추출
from pathlib import Path

# PyInstaller 번들 환경 감지
def is_pyinstaller_bundle():
    """PyInstaller로 빌드된 EXE인지 확인"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

ocr_dll = None
try:
    # 1. DLL 폴더 경로 설정 (PyInstaller 환경 고려)
    if is_pyinstaller_bundle():
        # EXE로 실행 중: 번들된 DLL 사용
        dll_dir = os.path.join(sys._MEIPASS, 'dlls')
        print(f"📦 EXE 모드: 번들된 DLL 사용")
    else:
        # 소스로 실행 중: dlls 폴더 사용
        dll_dir = os.path.join(BASE_DIR, 'dlls')
    
    dll_dir_path = Path(dll_dir)
    
    # 2. DLL이 없으면 자동 추출 시도 (소스 실행 시에만)
    if not is_pyinstaller_bundle():
        from dll_extractor import extract_oneocr_dlls, check_existing_dlls
        
        if not check_existing_dlls(dll_dir_path):
            print("\n📦 DLL 파일이 없습니다. 자동 추출을 시도합니다...")
            if not extract_oneocr_dlls(dest_dir=dll_dir):
                print("\n💡 DLL 수동 설치 방법:")
                print("   1. Microsoft Store에서 'Snipping Tool' 앱 설치")
                print("   2. 또는 아래 경로에서 수동으로 파일 복사:")
                print("      C:\\Program Files\\WindowsApps\\Microsoft.ScreenSketch_*\\SnippingTool\\")
                print(f"   3. 필요한 파일: oneocr.dll, oneocr.onemodel, onnxruntime.dll")
                print(f"   4. 대상 폴더: {dll_dir}")
                sys.exit(1)
    
    # 3. DLL 경로 결정
    dll_path = os.path.join(dll_dir, DLL_NAME)
    model_path_full = os.path.join(dll_dir, MODEL_NAME)

    # 4. PATH 환경변수에 DLL 폴더 추가 (의존성 문제 해결)
    if os.path.exists(dll_dir):
        os.add_dll_directory(dll_dir)
        os.environ['PATH'] = dll_dir + ';' + os.environ['PATH']

    if not os.path.exists(dll_path):
        print(f"❌ 오류: {DLL_NAME} 파일을 찾을 수 없습니다.")
        print(f"   탐색 경로: {dll_dir}")
        sys.exit(1)
        
    ocr_dll = ctypes.WinDLL(dll_path)
    for name, argtypes, restype in DLL_FUNCTIONS:
        if hasattr(ocr_dll, name):
            func = getattr(ocr_dll, name)
            func.argtypes = argtypes
            func.restype = restype
        else:
            print(f"⚠️ 경고: DLL 함수 '{name}'를 찾을 수 없습니다.")
    print(f"✅ Custom OCR DLL 로드 성공")
except Exception as e:
    print(f"❌ DLL 초기화 실패: {e}")
    sys.exit(1)

# ==========================================
# 3. OcrEngine 클래스
# ==========================================
@contextmanager
def suppress_output():
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        old_stdout = os.dup(1)
        old_stderr = os.dup(2)
        os.dup2(devnull, 1)
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(old_stdout, 1)
        os.dup2(old_stderr, 2)
        os.close(devnull)

class OcrEngine:
    """OCR 엔진 래퍼 클래스 - 싱글톤 패턴으로 사용"""
    
    def __init__(self):
        self.init_opts = c_int64()
        self._check(ocr_dll.CreateOcrInitOptions(byref(self.init_opts)), "InitOptions 생성 실패")
        self._check(ocr_dll.OcrInitOptionsSetUseModelDelayLoad(self.init_opts, 0), "DelayLoad 설정 실패")
        
        model_path = model_path_full.encode()
        self.pipeline = c_int64()
        
        with suppress_output():
            self._check(ocr_dll.CreateOcrPipeline(
                model_path, 
                ctypes.create_string_buffer(MODEL_KEY), 
                self.init_opts, 
                byref(self.pipeline)
            ), "파이프라인 생성 실패 (모델 파일 확인 필요)")

        self.proc_opts = c_int64()
        self._check(ocr_dll.CreateOcrProcessOptions(byref(self.proc_opts)), "ProcessOptions 생성 실패")
        ocr_dll.OcrProcessOptionsSetMaxRecognitionLineCount(self.proc_opts, 1000)
        
        # 리소스 관리 플래그
        self._initialized = True

    def __del__(self):
        """리소스 정리 - 메모리 누수 방지"""
        if hasattr(self, '_initialized') and self._initialized:
            try:
                if self.proc_opts.value:
                    ocr_dll.ReleaseOcrProcessOptions(self.proc_opts)
                if self.pipeline.value:
                    ocr_dll.ReleaseOcrPipeline(self.pipeline)
                if self.init_opts.value:
                    ocr_dll.ReleaseOcrInitOptions(self.init_opts)
            except:
                pass
            self._initialized = False

    def _check(self, code, msg):
        if code != 0:
            raise RuntimeError(f"{msg} (Code: {code})")

    def recognize_numpy(self, img_np):
        if img_np is None or img_np.size == 0:
            return ""

        if len(img_np.shape) == 2:
            img_bgra = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGRA)
        elif len(img_np.shape) == 3:
            img_bgra = cv2.cvtColor(img_np, cv2.COLOR_BGR2BGRA)
        else:
            return ""

        h, w = img_bgra.shape[:2]
        step = w * 4
        
        img_struct = ImageStructure(
            type=3, width=w, height=h, _reserved=0, step_size=step,
            data_ptr=img_bgra.ctypes.data_as(c_ubyte_p)
        )

        res_handle = c_int64()
        if ocr_dll.RunOcrPipeline(self.pipeline, byref(img_struct), self.proc_opts, byref(res_handle)) != 0:
            return ""

        line_count = c_int64()
        ocr_dll.GetOcrLineCount(res_handle, byref(line_count))
        
        full_text = []
        for i in range(line_count.value):
            l_handle = c_int64()
            ocr_dll.GetOcrLine(res_handle, i, byref(l_handle))
            content = c_char_p()
            ocr_dll.GetOcrLineContent(l_handle, byref(content))
            if content.value:
                try:
                    text = content.value.decode('utf-8', errors='ignore')
                    full_text.append(text)
                except:
                    pass
        
        ocr_dll.ReleaseOcrResult(res_handle)
        return " ".join(full_text)

try:
    global_ocr = OcrEngine()
    print(f"✅ OCR 엔진 초기화 완료")
except Exception as e:
    print(f"❌ OCR 엔진 초기화 실패: {e}")
    sys.exit(1)

# YOLO 모델 로드
YOLO_MODEL_PATH = os.path.join(BASE_DIR, 'best.pt')
if os.path.exists(YOLO_MODEL_PATH):
    print(f"✅ YOLO 모델 로드: {YOLO_MODEL_PATH}")
    model = YOLO(YOLO_MODEL_PATH)
else:
    print("⚠️ 기본 모델(yolov8n.pt) 로드. 인식률이 낮을 수 있습니다.")
    model = YOLO('yolov8n.pt')

LOCATIONS = [
    "1동", "2동", "3동", "4동", "5동", "6동", "7동", "8동", "9동", "10동",
    "11동", "12동", "13동", "14동", "15동", "중앙동", "민원동", "2청사", "2동 옥외",
    "7동 옥외", "8동 옥외", "9동 옥외", "10동 옥외", "10동 임시1", "10동 임시2",
    "11동 옥외", "13-1 옥외", "13-2 옥외", "14-1 임시", "14-2 임시", "15-1 옥외",
    "15-2 옥외", "15-3 옥외", "문화관", "중앙동 임시", "C26,C27"
]
REASONS = [
    "주차선 외 위반", "경차 구역 위반", "임산부 구역 위반",
    "방문객 전용 구역 위반", "전기차 구역 위반", "지하주차장 통로, 통행, 방해주차 위반",
    "장애인 구역 위반, 지정주차 구역(업무용포함)", "소방차 전용구역 위반", "주차금지구역위반 (필로티 등)", "2,5부제 위반"
]

# ==========================================
# 4. 이미지 처리 및 유틸리티
# ==========================================

# [스마트 로그인] 로컬/Cloudflare 접속 구분
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not SYSTEM_PASSWORD:
            session['logged_in'] = True
            return f(*args, **kwargs)

        if session.get('logged_in'):
            return f(*args, **kwargs)
        
        is_localhost = request.remote_addr == '127.0.0.1'
        is_cloudflare = request.headers.get('CF-Ray') is not None
        
        if is_localhost and not is_cloudflare:
            session['logged_in'] = True 
            return f(*args, **kwargs)

        return redirect(url_for('login'))
        
    return decorated_function

def add_padding(img, pad_size=20, color=(255, 255, 255)):
    return cv2.copyMakeBorder(img, pad_size, pad_size, pad_size, pad_size, cv2.BORDER_CONSTANT, value=color)

def apply_clahe(gray_img):
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray_img)

def apply_threshold(gray_img):
    blurred = cv2.GaussianBlur(gray_img, (5, 5), 0)
    return cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

def apply_otsu(gray_img):
    blurred = cv2.GaussianBlur(gray_img, (3, 3), 0)
    return cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

def apply_unsharp(gray_img):
    blurred = cv2.GaussianBlur(gray_img, (0, 0), 1.2)
    return cv2.addWeighted(gray_img, 1.8, blurred, -0.8, 0)

def fix_common_errors(text):
    text = text.upper()
    text = text.replace('O', '0').replace('o', '0')
    text = text.replace('I', '1').replace('l', '1').replace('|', '1')
    text = text.replace('S', '5').replace('s', '5')
    text = text.replace('B', '8')
    text = text.replace('G', '6')
    text = text.replace('Z', '2')
    return text

def clean_text(text):
    text = fix_common_errors(text)
    return re.sub(r'[^0-9가-힣]', '', text)

def find_plate_pattern(text):
    candidates = extract_plate_candidates(text, get_plate_history_index())
    return candidates[0] if candidates else None

def mask_side_regions(img, ratio=0.1):
    h, w = img.shape[:2]
    w_cut = int(w * ratio)
    masked = img.copy()
    cv2.rectangle(masked, (0, 0), (w_cut, h), (255, 255, 255), -1)
    cv2.rectangle(masked, (w - w_cut, 0), (w, h), (255, 255, 255), -1)
    return masked

def smart_plate_filter(text):
    candidates = extract_plate_candidates(fix_common_errors(text), get_plate_history_index())
    return candidates[0] if candidates else None

def stitch_broken_plate(raw_text):
    text = fix_common_errors(raw_text)
    fronts = re.findall(r'\d{2,3}[가-힣]', text)
    backs = re.findall(r'\d{4}', text)
    for f in fronts:
        for b in backs:
            combined = normalize_plate_candidate(f + b, get_plate_history_index())
            if combined:
                return combined
    return None

def process_and_ocr(crop_img, start_time, timeout=5.0, is_full_image=False):
    """이미지에서 번호판 텍스트 추출 (최적화 버전)"""
    if crop_img.ndim == 3:
        gray = cv2.cvtColor(crop_img, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop_img

    if not is_full_image:
        gray = mask_side_regions(gray, ratio=0.03)

    # 필터를 미리 전부 만들지 않고 실제 OCR 시도 직전에 생성한다.
    # 앞쪽 시도에서 번호판이 확정되면 무거운 이진화/팽창 연산을 완전히 생략할 수 있다.
    filter_factories = [
        ("CLAHE", lambda: add_padding(apply_clahe(gray), pad_size=15)),
        ("Gray+Pad", lambda: add_padding(gray, pad_size=15)),
        ("Otsu", lambda: add_padding(apply_otsu(gray), pad_size=15)),
        ("Unsharp", lambda: add_padding(apply_unsharp(gray), pad_size=15)),
        ("Thresh", lambda: add_padding(apply_threshold(gray), pad_size=15)),
    ]
    if not is_full_image:
        filter_factories.append((
            "Dilate",
            lambda: add_padding(
                cv2.dilate(apply_threshold(gray), np.ones((2, 2), np.uint8), iterations=1),
                pad_size=15,
            ),
        ))

    # 1.5배가 속도/인식률 균형이 가장 좋아 먼저 시도한다.
    scales = [1.0] if is_full_image else [1.5, 2.0, 1.0]

    candidates = []
    history = get_plate_history_index()

    processed_cache = {}
    for scale in scales:
        for filter_name, factory in filter_factories:
            if time.time() - start_time > timeout:
                break
            
            try:
                if filter_name not in processed_cache:
                    processed_cache[filter_name] = factory()
                processed_img = processed_cache[filter_name]
                if scale != 1.0:
                    target_img = cv2.resize(processed_img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
                else:
                    target_img = processed_img

                raw_text = global_ocr.recognize_numpy(target_img)
                found = extract_plate_candidates(fix_common_errors(raw_text), history)

                if found:
                    candidates.extend(found)
                    best_so_far = choose_best_candidate(candidates, history)
                    # 서로 다른 전처리에서 두 번 일치하면 남은 고비용 필터를 생략한다.
                    if best_so_far and candidates.count(best_so_far) >= 2:
                        return [best_so_far]
                elif is_full_image:
                    stitched = stitch_broken_plate(raw_text)
                    if stitched:
                        candidates.append(stitched)

            except Exception:
                pass
        
        if time.time() - start_time > timeout:
            break

    if candidates:
        best = choose_best_candidate(candidates, history)
        return [best] if best else []
    
    return []

def detect_best_plate(img_path):
    # 최초 1회 Excel 이력 로딩 시간은 이미지 OCR 제한 시간에 포함하지 않는다.
    get_plate_history_index()
    start_time = time.time()
    # 속도보다 정확도를 우선한다. YOLO와 여러 OCR 전처리의 총 허용 시간.
    timeout = 5.0
    log_lines = []
    best_plate = ""

    original_img = cv2.imread(img_path)
    if original_img is None:
        return "읽기실패", []

    h, w, _ = original_img.shape
    candidates_boxes = []

    if model:
        try:
            results = model.predict(original_img, conf=0.25, imgsz=640, max_det=5, verbose=False)
            for r in results:
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    box_w = max(1, x2 - x1)
                    box_h = max(1, y2 - y1)
                    pad_x = int(box_w * 0.10) 
                    pad_y = int(box_h * 0.12)
                    crop = original_img[max(0, y1 - pad_y):min(h, y2 + pad_y), max(0, x1 - pad_x):min(w, x2 + pad_x)]
                    if crop.size > 0:
                        candidates_boxes.append({'y2': y2, 'crop': crop, 'is_full': False})
            del results
        except Exception as e:
            log_lines.append(f"YOLO Error: {e}")

    # YOLO가 실패했을 때의 전체 이미지 OCR은 장축을 1600px로 제한해 처리량을 줄인다.
    full_scan_img = original_img
    max_side = max(h, w)
    if max_side > 1600:
        resize_ratio = 1600.0 / max_side
        full_scan_img = cv2.resize(
            original_img,
            (max(1, int(w * resize_ratio)), max(1, int(h * resize_ratio))),
            interpolation=cv2.INTER_AREA,
        )
    candidates_boxes.append({'y2': h, 'crop': full_scan_img, 'is_full': True})
    candidates_boxes.sort(key=lambda x: (x['is_full'], -x['y2']))

    plate_found = False
    for item in candidates_boxes:
        if time.time() - start_time > timeout:
            log_lines.append(" ⚠️ [Timeout] 시간 초과")
            break

        is_full = item['is_full']
        label = "전체 스캔" if is_full else f"박스(y2:{item['y2']})"
        found_plates = process_and_ocr(item['crop'], start_time, timeout, is_full_image=is_full)
        
        if found_plates:
            best_plate = found_plates[0]
            log_lines.append(f" ✅ [인식 성공] {best_plate} - {label}")
            plate_found = True
            break 

    if not plate_found:
        log_lines.append(" ❌ 최종 인식 실패")

    del original_img
    return best_plate, log_lines

def background_processing(task_id, file_paths, location, reason, ampm):
    print(f"🚀 [Task {task_id}] 작업 시작 (총 {len(file_paths)}장)")
    results_list = []
    total = len(file_paths)

    try:
        for idx, path in enumerate(file_paths):
            filename = os.path.basename(path)
            tasks[task_id]['current'] = idx + 1
            tasks[task_id]['last_processed'] = filename
            print(f"  ↳ Processing [{idx+1}/{total}]: {filename} ... ", end='', flush=True)

            try:
                plate, _ = detect_best_plate(path)
            except Exception as e:
                print(f"Error: {e}")
                plate = ""
            
            print(f"Done ({plate if plate else '인식실패'})")
            
            web_url = "/uploads/" + urllib.parse.quote(os.path.relpath(path, UPLOAD_DIR).replace('\\', '/'))
            results_list.append({'filename': filename, 'plate': plate, 'image_url': web_url})
            # 매 이미지마다 강제 GC를 실행하면 배치 처리량이 크게 떨어진다.
            if (idx + 1) % 10 == 0:
                gc.collect()

        tasks[task_id]['results'] = results_list
        tasks[task_id]['report_text'] = f"{location} {reason} ({ampm}) - 총 {total}건"
        tasks[task_id]['status'] = 'done'
        print(f"🏁 [Task {task_id}] 작업 완료.\n")

    except Exception as e:
        print(f"🔥 [Task {task_id}] 오류: {e}")
        tasks[task_id]['status'] = 'error'

# ==========================================
# 5. Flask 라우트 정의
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if not SYSTEM_PASSWORD:
        session['logged_in'] = True
        return redirect(url_for('index'))

    if request.method == 'POST':
        if request.form['password'] == SYSTEM_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error="❌ 비밀번호가 올바르지 않습니다.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html', locations=LOCATIONS, reasons=REASONS)

# 분할 업로드 세션 저장소
upload_sessions = {}

@app.route('/upload/start_session', methods=['POST'])
@login_required
def start_upload_session():
    """분할 업로드 세션 시작"""
    session_id = str(uuid.uuid4())
    data = request.get_json()
    
    loc = data.get('location', '위치 미지정')
    reason = data.get('reason', '사유 미지정')
    ampm = data.get('ampm', '오전')
    total_files = data.get('total_files', 0)
    
    save_path = os.path.join(UPLOAD_DIR, datetime.now().strftime('%Y.%m.%d'), loc, ampm, reason)
    os.makedirs(save_path, exist_ok=True)
    
    upload_sessions[session_id] = {
        'location': loc,
        'reason': reason,
        'ampm': ampm,
        'save_path': save_path,
        'total_files': total_files,
        'uploaded_files': [],
        'uploaded_count': 0,
        'status': 'uploading'
    }
    
    return jsonify({'session_id': session_id, 'status': 'started'})

@app.route('/upload/add_batch/<session_id>', methods=['POST'])
@login_required
def add_batch_to_session(session_id):
    """세션에 파일 배치 추가"""
    if session_id not in upload_sessions:
        return jsonify({'error': 'Invalid session'}), 404
    
    session = upload_sessions[session_id]
    save_path = session['save_path']
    
    files = request.files.getlist('photos')
    saved_count = 0
    
    for f in files:
        if f.filename:
            safe_name = os.path.basename(f.filename)
            # 파일명 중복 방지
            base, ext = os.path.splitext(safe_name)
            counter = 1
            final_path = os.path.join(save_path, safe_name)
            while os.path.exists(final_path):
                final_path = os.path.join(save_path, f"{base}_{counter}{ext}")
                counter += 1
            
            try:
                f.save(final_path)
                session['uploaded_files'].append(final_path)
                saved_count += 1
            except OSError as e:
                if e.errno == 28:
                    return jsonify({'error': '디스크 용량이 가득 찼습니다!'}), 507
                raise
    
    session['uploaded_count'] += saved_count
    
    return jsonify({
        'status': 'ok',
        'batch_saved': saved_count,
        'total_uploaded': session['uploaded_count']
    })

@app.route('/upload/finish/<session_id>', methods=['POST'])
@login_required
def finish_upload_session(session_id):
    """업로드 세션 완료 및 OCR 처리 시작"""
    if session_id not in upload_sessions:
        return jsonify({'error': 'Invalid session'}), 404
    
    session = upload_sessions[session_id]
    saved_files = session['uploaded_files']
    
    if not saved_files:
        del upload_sessions[session_id]
        return jsonify({'error': '업로드된 파일이 없습니다.'}), 400
    
    # OCR 처리 태스크 생성
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'total': len(saved_files), 'current': 0, 'status': 'processing',
        'last_processed': '', 'results': [], 
        'location': session['location'], 'reason': session['reason']
    }
    
    # 백그라운드 처리 시작
    thread = threading.Thread(
        target=background_processing, 
        args=(task_id, saved_files, session['location'], session['reason'], session['ampm'])
    )
    thread.daemon = True
    thread.start()
    
    # 세션 정리
    del upload_sessions[session_id]
    
    return jsonify({
        'status': 'processing',
        'task_id': task_id,
        'total_files': len(saved_files)
    })

@app.route('/changelog')
@login_required
def changelog():
    return render_template('changelog.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    loc = request.form.get('location', "위치 미지정")
    reason = request.form.get('reason', "사유 미지정")
    ampm = request.form.get('ampm', "오전")
    
    save_path = os.path.join(UPLOAD_DIR, datetime.now().strftime('%Y.%m.%d'), loc, ampm, reason)
    
    try:
        os.makedirs(save_path, exist_ok=True)
    except OSError as e:
        if e.errno == 28:  # No space left on device
            return "<h3>❌ 업로드 실패</h3><p><b>디스크 용량이 가득 찼습니다!</b></p><p>서버 저장 공간을 확보한 후 다시 시도해주세요.</p><a href='/'>메인으로</a>", 507
        raise

    saved_files = []
    files = request.files.getlist('photos')
    
    for f in files:
        if f.filename:
            safe_name = os.path.basename(f.filename)
            path = os.path.join(save_path, safe_name)
            try:
                f.save(path)
                saved_files.append(path)
            except OSError as e:
                # 디스크 용량 부족 (errno 28: ENOSPC)
                if e.errno == 28 or "No space" in str(e) or "disk" in str(e).lower():
                    # 이미 저장된 파일 정리
                    for saved_path in saved_files:
                        try:
                            os.remove(saved_path)
                        except:
                            pass
                    return "<h3>❌ 업로드 실패</h3><p><b>디스크 용량이 가득 찼습니다!</b></p><p>서버 저장 공간을 확보한 후 다시 시도해주세요.</p><a href='/'>메인으로</a>", 507
                raise

    if not saved_files:
        return "파일이 업로드되지 않았습니다.", 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'total': len(saved_files), 'current': 0, 'status': 'processing',
        'last_processed': '', 'results': [], 'location': loc, 'reason': reason
    }

    thread = threading.Thread(target=background_processing, args=(task_id, saved_files, loc, reason, ampm))
    thread.daemon = True
    thread.start()

    return render_template('progress.html', task_id=task_id, total=len(saved_files))

@app.route('/status/<task_id>')
@login_required
def check_status(task_id):
    if task_id not in tasks: return jsonify({'error': 'Unknown task'}), 404
    return jsonify({
        'status': tasks[task_id]['status'],
        'current': tasks[task_id]['current'],
        'total': tasks[task_id]['total'],
        'last_processed': tasks[task_id]['last_processed']
    })

@app.route('/result_view/<task_id>')
@login_required
def result_view(task_id):
    if task_id not in tasks: return f"<h3>❌ 작업을 찾을 수 없습니다.</h3><a href='/'>메인으로</a>", 404
    task = tasks[task_id]
    if task['status'] == 'error': return f"<h3>🔥 오류 발생</h3><a href='/'>메인으로</a>", 500
    if task['status'] == 'processing':
        # progress.html 템플릿을 렌더링하여 진행률 바 표시
        return render_template('progress.html', task_id=task_id, total=task['total'])
    return render_template('result.html', results=task['results'], report_text=task['report_text'], location=task['location'], reason=task['reason'])

@app.route('/save', methods=['POST'])
@login_required
def save():
    entries = []
    loc = request.form.get('location', '')
    reason = request.form.get('reason', '')
    report_text = request.form.get('report_text', '')
    
    if '(오후)' in report_text:
        time_suffix = "오후"
    elif '(오전)' in report_text:
        time_suffix = "오전"
    else:
        time_suffix = "오전" if datetime.now().hour < 12 else "오후"

    for k, v in request.form.items():
        if k.startswith('plate_') and v and v.lower() != 's':
            entries.append({
                "날짜": datetime.now().strftime('%Y-%m-%d'),
                "시간대": time_suffix,
                "단속위치": loc,
                "사유": reason,
                "차량번호": v
            })

    if not entries:
        return "저장할 데이터가 없습니다.", 400

    today_str = datetime.now().strftime('%Y-%m-%d')
    timestamp = datetime.now().strftime('%H시%M분%S초')
    
    root_filename = f"주차단속내역_{today_str}_{time_suffix}.xlsx"
    root_path = os.path.join(BASE_DIR, root_filename)

    backup_folder = os.path.join(BACKUP_DIR, today_str)
    os.makedirs(backup_folder, exist_ok=True)
    backup_filename = f"단속내역_{time_suffix}_{timestamp}.xlsx"
    backup_path = os.path.join(backup_folder, backup_filename)

    messages = []

    with excel_lock:
        try:
            # 1. 메인 엑셀 파일 로드 (없으면 생성)
            if os.path.exists(root_path):
                try:
                    df = pd.read_excel(root_path)
                except Exception:
                    df = pd.DataFrame(columns=["날짜", "시간대", "단속위치", "사유", "차량번호"])
            else:
                df = pd.DataFrame(columns=["날짜", "시간대", "단속위치", "사유", "차량번호"])
            
            new_df = pd.DataFrame(entries)
            final_df = pd.concat([df, new_df], ignore_index=True)

            # 2. [중요] 백업 파일 우선 저장
            final_df.to_excel(backup_path, index=False)
            messages.append(f"✅ <b>데이터 안전 저장됨 (Backup):</b> {today_str}/{backup_filename}")

            # 3. 메인 파일 덮어쓰기 시도
            try:
                shutil.copy2(backup_path, root_path)
                messages.append(f"✅ <b>메인 파일 업데이트됨:</b> {root_filename}")
                main_status = "성공"
            except PermissionError:
                messages.append(
                    f"<br>⚠️ <b>[주의] 메인 엑셀 파일이 열려있어 업데이트하지 못했습니다.</b><br>"
                    f"하지만 데이터는 <b>backup 폴더</b>에 안전하게 저장되었습니다.<br>"
                    f"최신 내용을 보려면 엑셀을 닫고 다시 저장하거나 backup 폴더를 확인하세요."
                )
                main_status = "실패"

        except Exception as e:
            return f"<h3>❌ 치명적 저장 오류</h3><p>{str(e)}</p>", 500
    
    backup_relative_path = os.path.join('backup', today_str, backup_filename)

    return render_template(
        'success.html', 
        count=len(entries), 
        excel_file=root_filename if main_status == "성공" else backup_relative_path,
        report_text=report_text,
        extra_message="<br>".join(messages)
    )

@app.route('/download/<path:filename>')
@login_required
def download_file(filename):
    try:
        return send_from_directory(BASE_DIR, filename, as_attachment=True)
    except:
        return "파일을 찾을 수 없습니다.", 404

@app.route('/uploads/<path:path>')
@login_required
def uploads(path):
    return send_from_directory(UPLOAD_DIR, path)

@app.route('/help')
@login_required
def help_page():
    return render_template('help.html') if os.path.exists(os.path.join(BASE_DIR, 'templates', 'help.html')) else "<h3>도움말 준비 중</h3><a href='/'>홈으로</a>"

@app.route('/report')
@login_required
def report_page():
    files = [f for f in os.listdir(BASE_DIR) if f.endswith('.xlsx') and '주차단속내역' in f]
    files.sort(reverse=True)
    file_list = "".join([f'<li><a href="/download/{f}">{f}</a></li>' for f in files])
    
    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>단속 리포트</title>
        <style>
            body {{ font-family: sans-serif; padding: 20px; max-width: 600px; margin: auto; }}
            h2 {{ color: #2c3e50; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ margin: 10px 0; padding: 10px; background: #f9f9f9; border-bottom: 1px solid #ddd; }}
            a {{ text-decoration: none; color: #007bff; font-weight: bold; }}
            .btn {{ display:inline-block; margin-top:20px; padding:10px 20px; background:#6c757d; color:white; text-decoration:none; border-radius:5px; }}
        </style>
    </head>
    <body>
        <h2>📊 주차 단속 엑셀 파일 목록</h2>
        <ul>
            {file_list if files else "<li>저장된 내역이 없습니다.</li>"}
        </ul>
        <hr>
        <p>※ 파일이 열려있어 저장이 안 된 경우, <b>backup</b> 폴더를 확인하세요.</p>
        <a href="/" class="btn">🏠 홈으로 돌아가기</a>
    </body>
    </html>
    """

# ==========================================
# 6. 서버 실행 및 터널링
# ==========================================

# [추가됨] 디스코드 웹훅 전송 함수
def send_discord_webhook(tunnel_url):
    webhook_url = get_discord_webhook_url()
    if not webhook_url:
        return
    
    data = {
        "username": "OCR Server Bot",
        "embeds": [{
            "title": "🚀 단속 서버가 시작되었습니다.",
            "description": "외부에서 접속 가능한 링크가 생성되었습니다.",
            "color": 65280, # Green color
            "fields": [
                {"name": "🌍 외부 접속 URL", "value": tunnel_url, "inline": False},
                {"name": "🏠 로컬 URL", "value": f"http://127.0.0.1:5000", "inline": False},
                {"name": "🔒 보안 모드", "value": "활성화" if SYSTEM_PASSWORD else "비활성화 (공개)", "inline": True}
            ],
            "footer": {"text": f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
        }]
    }

    try:
        requests.post(webhook_url, json=data)
        print("📨 [Discord] 웹훅 전송 완료")
    except Exception as e:
        print(f"⚠️ [Discord] 웹훅 전송 실패: {e}")

def init_cloudflare_tunnel(port):
    """
    Cloudflare Tunnel 초기화
    우선순위:
    1. 이미 cloudflared가 실행 중이면 기존 터널 사용
    2. config.yml + credentials-file 방식 (로컬 관리 터널)
    3. 토큰 기반 방식 (원격 관리 터널)
    4. Quick Tunnel (임시 trycloudflare.com URL)
    """
    import glob
    
    cf_filename = "cloudflared.exe"
    cf_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    
    tunnel_domain = get_cloudflare_tunnel_domain()
    
    # 이미 cloudflared가 실행 중인지 확인
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq cloudflared.exe"],
            capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW
        )
        if "cloudflared.exe" in result.stdout:
            print("✅ cloudflared가 이미 실행 중 - 기존 터널 사용")
            if tunnel_domain:
                return f"https://{tunnel_domain}"
            else:
                return "[외부 터널 사용 중 - 도메인 설정에서 확인]"
    except:
        pass

    # cloudflared 다운로드
    if not os.path.exists(cf_filename):
        print(f"⬇️ Cloudflare 다운로드 중...")
        try:
            with requests.get(cf_url, stream=True) as r:
                r.raise_for_status()
                with open(cf_filename, 'wb') as f:
                    shutil.copyfileobj(r.raw, f)
        except Exception:
            return None

    # 기존 프로세스 종료 (새로 시작할 때만)
    os.system("taskkill /f /im cloudflared.exe >nul 2>&1")
    
    # Windows에서 콘솔 창 숨기기
    creation_flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
    
    # 방법 1: config.yml 파일이 있는 경우 (로컬 관리 터널)
    config_path = os.path.join(BASE_DIR, "config.yml")
    if os.path.exists(config_path):
        print("🔗 설정 파일(config.yml)로 터널 시작 중...")
        
        # credentials 파일 찾기
        creds_files = [f for f in glob.glob(os.path.join(BASE_DIR, "*.json")) 
                       if "package" not in os.path.basename(f).lower()]
        
        if creds_files:
            creds_file = creds_files[0]
            print(f"   인증 파일: {os.path.basename(creds_file)}")
            cmd = [cf_filename, "tunnel", "--config", config_path, "--credentials-file", creds_file, "run"]
            process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding='utf-8', errors='replace',
                creationflags=creation_flags
            )
            
            # 터널 시작 대기
            start_time = time.time()
            while time.time() - start_time < 15:
                line = process.stderr.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                if "Registered tunnel connection" in line or "connIndex" in line:
                    if tunnel_domain:
                        return f"https://{tunnel_domain}"
                    else:
                        return "[설정 파일 터널 - 도메인 설정에서 확인]"
            
            print("⚠️ 설정 파일 터널 연결 시간 초과...")
    
    # 방법 2: 토큰 기반 (원격 관리 터널)
    tunnel_token = get_cloudflare_tunnel_token()
    
    if tunnel_token:
        print("🔗 토큰으로 터널 시작 중...")
        cmd = [cf_filename, "tunnel", "run", "--token", tunnel_token]
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding='utf-8', errors='replace',
            creationflags=creation_flags
        )
        
        start_time = time.time()
        while time.time() - start_time < 15:
            line = process.stderr.readline()
            if not line:
                time.sleep(0.5)
                continue
            if "Registered tunnel connection" in line or "connIndex" in line:
                if tunnel_domain:
                    return f"https://{tunnel_domain}"
                else:
                    return "[토큰 터널 - 도메인 설정에서 확인]"
        
        print("⚠️ 토큰 터널 연결 시간 초과, Quick Tunnel로 전환...")

    # 방법 3: Quick Tunnel (임시 URL)
    print("🌐 Quick Tunnel 시작 중...")
    cmd = [cf_filename, "tunnel", "--url", f"http://localhost:{port}"]
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
        text=True, encoding='utf-8', errors='replace',
        creationflags=creation_flags
    )

    tunnel_url = None
    start_time = time.time()
    while time.time() - start_time < 15:
        line = process.stderr.readline()
        if not line: break
        match = re.search(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', line)
        if match:
            tunnel_url = match.group(0)
            break
    return tunnel_url

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='주차 단속 시스템')
    parser.add_argument('--gui', action='store_true', help='GUI 모드로 실행')
    parser.add_argument('--server', action='store_true', help='웹 서버 모드로 실행')
    parser.add_argument('--hybrid', action='store_true', help='하이브리드 모드 (GUI + 백그라운드 서버)')
    parser.add_argument('--port', type=int, default=5000, help='웹 서버 포트 (기본: 5000)')
    args = parser.parse_args()
    
    # 기본값: 인수 없이 실행하면 GUI 모드 (EXE 더블클릭 시)
    if not args.gui and not args.server and not args.hybrid:
        args.gui = True
    
    if args.gui or args.hybrid:
        # GUI 모드 또는 하이브리드 모드 실행
        try:
            from gui import main as gui_main
            mode_name = "하이브리드" if args.hybrid else "GUI"
            print(f"🖥️ {mode_name} 모드로 시작합니다...")
            gui_main(start_server=args.hybrid)  # 하이브리드면 서버도 시작
        except ImportError as e:
            print(f"❌ GUI 모듈 로드 실패: {e}")
            print("   --server 옵션으로 웹 서버 모드를 사용하세요.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ GUI 실행 실패: {e}")
            sys.exit(1)
    else:
        # 서버 모드 실행
        PORT = args.port
        HOST_IP = '127.0.0.1' 
        
        print("=" * 60)
        print(f"🚀 [서버 시작] 보안 모드 (v2.2 - GUI 지원)")
        if SYSTEM_PASSWORD:
            print(f"🔑 외부 접속 비밀번호: {SYSTEM_PASSWORD}")
        else:
            print(f"🔓 비밀번호 미설정 (누구나 접속 가능)")
            
        print(f"📂 백업 폴더: {BACKUP_DIR}")

        public_url = init_cloudflare_tunnel(PORT)
        print("-" * 60)
        if public_url:
            print(f"🌍 [외부 접속 주소] : {public_url}")
            send_discord_webhook(public_url)
        else:
            print("❌ Cloudflare 터널 실패 (로컬 접속만 가능)")

        print("-" * 60)
        print(f"🏠 [로컬 접속 주소] : http://{HOST_IP}:{PORT}")
        print("   (로컬 접속 시 비밀번호 없이 자동 로그인됩니다)")
        print("=" * 60)
        print("   서버를 종료하려면 Ctrl+C를 누르세요.")
        print("=" * 60)

        # 종료 시 정리 함수
        def cleanup():
            print("\n🛑 서버 종료 중...")
            # Cloudflare 프로세스 종료
            os.system("taskkill /f /im cloudflared.exe >nul 2>&1")
            print("✅ 정리 완료")
        
        # 종료 핸들러 등록
        import atexit
        import signal
        
        atexit.register(cleanup)
        
        def signal_handler(signum, frame):
            cleanup()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # 종료 신호
        
        try:
            # Windows에서 콘솔 창 닫기 이벤트 처리
            if sys.platform == 'win32':
                signal.signal(signal.SIGBREAK, signal_handler)
        except (AttributeError, ValueError):
            pass  # SIGBREAK가 없는 환경
        
        try:
            serve(app, host=HOST_IP, port=PORT, threads=10, channel_timeout=3000)
        except KeyboardInterrupt:
            cleanup()
        except Exception as e:
            print(f"❌ 서버 오류: {e}")
            cleanup()
