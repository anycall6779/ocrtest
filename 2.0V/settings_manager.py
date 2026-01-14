# -*- coding: utf-8 -*-
"""
설정 관리 모듈 - JSON 기반 설정 자동 저장/로드
"""

import os
import json
from typing import Any, Dict, Optional


class SettingsManager:
    """애플리케이션 설정을 관리하는 클래스"""
    
    # 기본 설정 값
    DEFAULT_SETTINGS = {
        # Cloudflare Tunnel 설정
        "cloudflare_tunnel_token": "",
        "cloudflare_tunnel_domain": "",
        
        # Discord 웹훅 설정
        "discord_webhook_url": "",
        
        # 폴더 경로 설정
        "input_folder": "",  # 빈 문자열이면 기본값 사용
        "output_folder": "",  # 백업 폴더
        "excel_save_folder": "",  # Excel 저장 위치
        
        # 마지막 선택 값 (UI 상태 유지)
        "last_location": "",
        "last_reason": "",
        "last_ampm": "",
        
        # 창 설정
        "window_geometry": "",  # 창 위치/크기 (예: "900x700+100+100")
    }
    
    def __init__(self, settings_file: Optional[str] = None):
        """
        설정 관리자 초기화
        
        Args:
            settings_file: 설정 파일 경로 (None이면 기본 경로 사용)
        """
        if settings_file is None:
            # 기본 경로: 실행 파일과 같은 폴더의 .settings 파일
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.settings_file = os.path.join(base_dir, ".settings")
        else:
            self.settings_file = settings_file
        
        # 현재 설정 (기본값으로 초기화)
        self._settings: Dict[str, Any] = dict(self.DEFAULT_SETTINGS)
        
        # 설정 파일 로드
        self.load()
    
    def load(self) -> bool:
        """
        설정 파일에서 설정 로드
        
        Returns:
            성공 여부
        """
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # 기본값에 로드된 값 덮어쓰기 (새 설정 항목 누락 방지)
                    for key, value in loaded.items():
                        if key in self._settings:
                            self._settings[key] = value
                return True
        except Exception as e:
            print(f"⚠️ 설정 로드 실패: {e}")
        return False
    
    def save(self) -> bool:
        """
        설정을 파일에 저장
        
        Returns:
            성공 여부
        """
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"⚠️ 설정 저장 실패: {e}")
        return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        설정 값 가져오기
        
        Args:
            key: 설정 키
            default: 기본값 (설정이 없을 경우)
            
        Returns:
            설정 값
        """
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """
        설정 값 저장
        
        Args:
            key: 설정 키
            value: 설정 값
        """
        self._settings[key] = value
    
    def get_all(self) -> Dict[str, Any]:
        """모든 설정 반환"""
        return dict(self._settings)
    
    def update(self, settings: Dict[str, Any]) -> None:
        """
        여러 설정 한번에 업데이트
        
        Args:
            settings: 업데이트할 설정 딕셔너리
        """
        for key, value in settings.items():
            if key in self._settings:
                self._settings[key] = value
    
    def reset(self) -> None:
        """모든 설정을 기본값으로 초기화"""
        self._settings = dict(self.DEFAULT_SETTINGS)
    
    # 편의 프로퍼티들
    @property
    def cloudflare_tunnel_token(self) -> str:
        return self.get("cloudflare_tunnel_token", "")
    
    @cloudflare_tunnel_token.setter
    def cloudflare_tunnel_token(self, value: str):
        self.set("cloudflare_tunnel_token", value)
    
    @property
    def cloudflare_tunnel_domain(self) -> str:
        return self.get("cloudflare_tunnel_domain", "")
    
    @cloudflare_tunnel_domain.setter
    def cloudflare_tunnel_domain(self, value: str):
        self.set("cloudflare_tunnel_domain", value)
    
    @property
    def discord_webhook_url(self) -> str:
        return self.get("discord_webhook_url", "")
    
    @discord_webhook_url.setter
    def discord_webhook_url(self, value: str):
        self.set("discord_webhook_url", value)
    
    @property
    def input_folder(self) -> str:
        return self.get("input_folder", "")
    
    @input_folder.setter
    def input_folder(self, value: str):
        self.set("input_folder", value)
    
    @property
    def output_folder(self) -> str:
        return self.get("output_folder", "")
    
    @output_folder.setter
    def output_folder(self, value: str):
        self.set("output_folder", value)
    
    @property
    def excel_save_folder(self) -> str:
        return self.get("excel_save_folder", "")
    
    @excel_save_folder.setter
    def excel_save_folder(self, value: str):
        self.set("excel_save_folder", value)


# 전역 설정 관리자 인스턴스 (싱글톤 패턴)
_settings_instance: Optional[SettingsManager] = None


def get_settings() -> SettingsManager:
    """전역 설정 관리자 인스턴스 반환"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = SettingsManager()
    return _settings_instance


def init_settings(settings_file: Optional[str] = None) -> SettingsManager:
    """
    설정 관리자 초기화 (앱 시작 시 호출)
    
    Args:
        settings_file: 설정 파일 경로
        
    Returns:
        SettingsManager 인스턴스
    """
    global _settings_instance
    _settings_instance = SettingsManager(settings_file)
    return _settings_instance
