"""
OneOCR DLL 자동 추출 모듈
Windows Snipping Tool 또는 Windows Photos 앱에서 OCR DLL을 자동으로 추출합니다.

참고: MORT 프로젝트 (https://github.com/killkimno/MORT) 구현 기반
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# Windows 콘솔 UTF-8 출력 설정
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, OSError):
        pass  # Python 3.7 미만 또는 reconfigure 불가능한 경우

# 필요한 파일 목록
REQUIRED_FILES = [
    'oneocr.dll',
    'oneocr.onemodel', 
    'onnxruntime.dll'
]

# UWP 앱 이름 (우선순위 순)
UWP_APPS = [
    ('Microsoft.ScreenSketch', 'SnippingTool'),  # Snipping Tool (하위 폴더에 있음)
    ('Microsoft.Windows.Photos', ''),             # Windows Photos (루트에 있음)
]


def get_install_location(app_name: str) -> Optional[str]:
    """
    PowerShell을 사용하여 UWP 앱의 설치 경로를 조회합니다.
    
    Args:
        app_name: UWP 앱 패키지 이름 (예: Microsoft.ScreenSketch)
    
    Returns:
        설치 경로 또는 None (앱이 설치되지 않은 경우)
    """
    cmd = f'(Get-AppxPackage -Name {app_name}).InstallLocation'
    
    try:
        result = subprocess.run(
            ['powershell.exe', '-NoProfile', '-Command', cmd],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0,
            timeout=30
        )
        
        if result.returncode != 0:
            return None
        
        path = result.stdout.strip()
        return path if path else None
        
    except subprocess.TimeoutExpired:
        print(f"⚠️ [{app_name}] 경로 조회 시간 초과")
        return None
    except Exception as e:
        print(f"⚠️ [{app_name}] 경로 조회 실패: {e}")
        return None


def find_dll_source() -> Optional[Tuple[Path, str]]:
    """
    DLL 파일이 존재하는 Windows 앱 경로를 찾습니다.
    
    Returns:
        (DLL 경로, 앱 이름) 튜플 또는 None
    """
    for app_name, subfolder in UWP_APPS:
        print(f"🔍 [{app_name}] 검색 중...")
        
        install_path = get_install_location(app_name)
        if not install_path:
            print(f"   ❌ 설치되지 않음")
            continue
        
        # 하위 폴더가 있는 경우 (Snipping Tool)
        if subfolder:
            dll_dir = Path(install_path) / subfolder
        else:
            dll_dir = Path(install_path)
        
        # oneocr.dll 존재 확인
        dll_file = dll_dir / 'oneocr.dll'
        if dll_file.exists():
            print(f"   ✅ DLL 발견: {dll_dir}")
            return dll_dir, app_name
        else:
            print(f"   ❌ {dll_dir}에 oneocr.dll 없음")
    
    return None


def copy_dll_files(source_dir: Path, dest_dir: Path) -> bool:
    """
    DLL 파일들을 소스 경로에서 대상 경로로 복사합니다.
    
    Args:
        source_dir: Windows 앱의 DLL 경로
        dest_dir: 복사할 대상 경로 (예: ./dlls)
    
    Returns:
        성공 여부
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    copied_files = []
    missing_files = []
    
    for filename in REQUIRED_FILES:
        src_file = source_dir / filename
        dst_file = dest_dir / filename
        
        if not src_file.exists():
            missing_files.append(filename)
            continue
        
        try:
            # 이미 존재하는 경우 덮어쓰기
            shutil.copy2(src_file, dst_file)
            copied_files.append(filename)
            print(f"   📄 복사 완료: {filename}")
        except PermissionError:
            print(f"   ⚠️ 권한 오류: {filename} (관리자 권한 필요)")
            return False
        except Exception as e:
            print(f"   ❌ 복사 실패: {filename} - {e}")
            return False
    
    if missing_files:
        print(f"   ⚠️ 찾을 수 없는 파일: {', '.join(missing_files)}")
        return False
    
    return len(copied_files) == len(REQUIRED_FILES)


def check_existing_dlls(dll_dir: Path) -> bool:
    """
    DLL 파일들이 이미 존재하는지 확인합니다.
    
    Args:
        dll_dir: DLL 폴더 경로
    
    Returns:
        모든 필요한 파일이 존재하면 True
    """
    for filename in REQUIRED_FILES:
        if not (dll_dir / filename).exists():
            return False
    return True


def extract_oneocr_dlls(dest_dir: Optional[str] = None, force: bool = False) -> bool:
    """
    Windows Snipping Tool 또는 Photos 앱에서 OneOCR DLL을 추출합니다.
    
    MORT 프로젝트의 구현 방식을 따릅니다:
    1. Snipping Tool (Microsoft.ScreenSketch)에서 우선 시도
    2. 없으면 Windows Photos (Microsoft.Windows.Photos)에서 시도
    
    Args:
        dest_dir: DLL을 저장할 폴더 경로 (기본값: ./dlls)
        force: True이면 기존 파일이 있어도 덮어쓰기
    
    Returns:
        추출 성공 여부
    """
    print("\n" + "="*50)
    print("🔧 OneOCR DLL 자동 추출 시작")
    print("="*50)
    
    # 대상 폴더 설정
    if dest_dir is None:
        base_dir = Path(__file__).parent
        dest_dir = base_dir / 'dlls'
    else:
        dest_dir = Path(dest_dir)
    
    print(f"📁 대상 폴더: {dest_dir}")
    
    # 이미 존재하는지 확인
    if not force and check_existing_dlls(dest_dir):
        print("✅ DLL 파일이 이미 존재합니다. 추출을 건너뜁니다.")
        print("   (강제 재추출: force=True 옵션 사용)")
        return True
    
    # Windows 앱에서 DLL 소스 찾기
    result = find_dll_source()
    if result is None:
        print("\n❌ DLL 추출 실패!")
        print("   Snipping Tool 또는 Windows Photos 앱이 설치되어 있지 않습니다.")
        print("\n💡 해결 방법:")
        print("   1. Microsoft Store에서 'Snipping Tool' 또는 'Windows Photos' 설치")
        print("   2. 또는 수동으로 DLL 파일을 dlls 폴더에 복사")
        print(f"   필요한 파일: {', '.join(REQUIRED_FILES)}")
        return False
    
    source_dir, app_name = result
    print(f"\n📦 [{app_name}]에서 DLL 추출 중...")
    
    # 파일 복사
    if copy_dll_files(source_dir, dest_dir):
        print("\n" + "="*50)
        print("✅ DLL 추출 완료!")
        print(f"   저장 위치: {dest_dir}")
        print("="*50 + "\n")
        return True
    else:
        print("\n❌ DLL 복사 중 오류가 발생했습니다.")
        print("   관리자 권한으로 실행하거나, 수동으로 파일을 복사하세요.")
        return False


def get_dll_info() -> dict:
    """
    현재 DLL 상태 정보를 반환합니다.
    
    Returns:
        상태 정보 딕셔너리
    """
    base_dir = Path(__file__).parent
    dll_dir = base_dir / 'dlls'
    
    info = {
        'dll_dir': str(dll_dir),
        'files': {},
        'all_present': True
    }
    
    for filename in REQUIRED_FILES:
        file_path = dll_dir / filename
        exists = file_path.exists()
        info['files'][filename] = {
            'exists': exists,
            'size': file_path.stat().st_size if exists else 0
        }
        if not exists:
            info['all_present'] = False
    
    return info


# 메인 실행 (독립 실행 시)
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='OneOCR DLL 자동 추출')
    parser.add_argument('--force', '-f', action='store_true', 
                        help='기존 파일이 있어도 덮어쓰기')
    parser.add_argument('--dest', '-d', type=str, default=None,
                        help='DLL을 저장할 폴더 경로')
    parser.add_argument('--info', '-i', action='store_true',
                        help='현재 DLL 상태 정보 출력')
    
    args = parser.parse_args()
    
    if args.info:
        info = get_dll_info()
        print(f"\n📊 DLL 상태 정보")
        print(f"   폴더: {info['dll_dir']}")
        print(f"   파일:")
        for name, data in info['files'].items():
            status = "✅" if data['exists'] else "❌"
            size = f"({data['size']:,} bytes)" if data['exists'] else ""
            print(f"     {status} {name} {size}")
        sys.exit(0)
    
    success = extract_oneocr_dlls(dest_dir=args.dest, force=args.force)
    sys.exit(0 if success else 1)
