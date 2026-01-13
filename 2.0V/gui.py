# -*- coding: utf-8 -*-
"""
주차 단속 시스템 - 로컬 GUI 모드
Tkinter 기반 데스크톱 애플리케이션
"""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
from PIL import Image, ImageTk
import pandas as pd

# OCR 엔진 및 처리 함수 import (ocr.py에서)
try:
    from ocr import (
        detect_best_plate, global_ocr, model,
        LOCATIONS, REASONS, BASE_DIR, BACKUP_DIR
    )
    OCR_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ OCR 모듈 로드 실패: {e}")
    OCR_AVAILABLE = False


class ParkingEnforcementGUI:
    """주차 단속 GUI 애플리케이션"""
    
    def __init__(self, root, start_server=False):
        self.root = root
        self.root.title("🚘 주차 단속 시스템 (로컬 모드)")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # 다크 테마 설정
        self.setup_theme()
        
        # 데이터 저장소
        self.image_files = []
        self.results = []
        self.current_index = 0
        self.processing = False
        
        # 서버 관련
        self.server_thread = None
        self.server_running = False
        self.server_url = None
        
        # UI 구성
        self.create_widgets()
        
        # 창 닫기 핸들러 등록 (서버 정리)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 하이브리드 모드: 서버 자동 시작
        if start_server:
            self.root.after(500, self.toggle_server)
        
        # 상태 표시
        self.update_status("준비됨" if OCR_AVAILABLE else "⚠️ OCR 모듈 로드 실패")
    
    def on_closing(self):
        """프로그램 종료 시 정리"""
        import subprocess
        
        # 서버 중지
        if self.server_running:
            self.stop_background_server()
        
        # Cloudflare 프로세스 종료
        try:
            subprocess.run(
                ["taskkill", "/f", "/im", "cloudflared.exe"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except:
            pass
        
        self.root.destroy()
    
    def setup_theme(self):
        """다크 테마 설정"""
        self.bg_color = "#1e1e1e"
        self.fg_color = "#ffffff"
        self.accent_color = "#0078d4"
        self.entry_bg = "#2d2d2d"
        self.button_bg = "#3c3c3c"
        self.success_color = "#107c10"
        
        self.root.configure(bg=self.bg_color)
        
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(".", background=self.bg_color, foreground=self.fg_color)
        style.configure("TFrame", background=self.bg_color)
        style.configure("TLabel", background=self.bg_color, foreground=self.fg_color, font=("맑은 고딕", 10))
        style.configure("TButton", background=self.button_bg, foreground=self.fg_color, font=("맑은 고딕", 10), padding=8)
        style.map("TButton", background=[("active", self.accent_color)])
        style.configure("Accent.TButton", background=self.accent_color, foreground=self.fg_color)
        style.configure("Success.TButton", background=self.success_color, foreground=self.fg_color)
        style.configure("TEntry", fieldbackground=self.entry_bg, foreground=self.fg_color)
        style.configure("TCombobox", fieldbackground=self.entry_bg, foreground=self.fg_color)
        style.configure("Horizontal.TProgressbar", background=self.accent_color, troughcolor=self.entry_bg)
    
    def create_widgets(self):
        """UI 위젯 생성"""
        # 상단 툴바
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Button(toolbar, text="📁 폴더 선택", command=self.select_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="📄 파일 선택", command=self.select_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="▶️ 분석 시작", command=self.start_processing, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="⏹️ 중지", command=self.stop_processing).pack(side=tk.LEFT, padx=5)
        
        # 서버 토글 버튼
        self.server_btn = ttk.Button(toolbar, text="🌐 서버 시작", command=self.toggle_server)
        self.server_btn.pack(side=tk.RIGHT, padx=5)
        
        # 주소 복사 버튼
        self.copy_url_btn = ttk.Button(toolbar, text="📋 주소 복사", command=self.copy_server_url, state=tk.DISABLED)
        self.copy_url_btn.pack(side=tk.RIGHT, padx=5)
        
        self.server_status_label = ttk.Label(toolbar, text="")
        self.server_status_label.pack(side=tk.RIGHT, padx=5)
        
        # 설정 영역
        settings_frame = ttk.Frame(self.root)
        settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(settings_frame, text="위치:").pack(side=tk.LEFT, padx=5)
        self.location_var = tk.StringVar(value=LOCATIONS[0] if OCR_AVAILABLE else "")
        location_combo = ttk.Combobox(settings_frame, textvariable=self.location_var, 
                                       values=LOCATIONS if OCR_AVAILABLE else [], width=15)
        location_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(settings_frame, text="사유:").pack(side=tk.LEFT, padx=5)
        self.reason_var = tk.StringVar(value=REASONS[0] if OCR_AVAILABLE else "")
        reason_combo = ttk.Combobox(settings_frame, textvariable=self.reason_var,
                                     values=REASONS if OCR_AVAILABLE else [], width=25)
        reason_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(settings_frame, text="시간대:").pack(side=tk.LEFT, padx=5)
        self.ampm_var = tk.StringVar(value="오전" if datetime.now().hour < 12 else "오후")
        ttk.Combobox(settings_frame, textvariable=self.ampm_var, 
                     values=["오전", "오후"], width=8).pack(side=tk.LEFT, padx=5)
        
        # 메인 컨텐츠 영역
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # 왼쪽: 이미지 미리보기
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.image_label = tk.Label(left_frame, bg=self.entry_bg, text="이미지를 선택하세요",
                                     fg=self.fg_color, font=("맑은 고딕", 12))
        self.image_label.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 이미지 네비게이션
        nav_frame = ttk.Frame(left_frame)
        nav_frame.pack(fill=tk.X, pady=5)
        ttk.Button(nav_frame, text="◀ 이전", command=self.prev_image).pack(side=tk.LEFT, padx=5)
        self.nav_label = ttk.Label(nav_frame, text="0 / 0")
        self.nav_label.pack(side=tk.LEFT, expand=True)
        ttk.Button(nav_frame, text="다음 ▶", command=self.next_image).pack(side=tk.RIGHT, padx=5)
        
        # 오른쪽: 결과 목록
        right_frame = ttk.Frame(main_frame, width=350)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=5)
        right_frame.pack_propagate(False)
        
        ttk.Label(right_frame, text="📋 인식 결과", font=("맑은 고딕", 12, "bold")).pack(pady=5)
        
        # 결과 리스트박스
        list_frame = ttk.Frame(right_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.result_listbox = tk.Listbox(list_frame, bg=self.entry_bg, fg=self.fg_color,
                                          font=("Consolas", 10), selectmode=tk.SINGLE,
                                          yscrollcommand=scrollbar.set)
        self.result_listbox.pack(fill=tk.BOTH, expand=True)
        self.result_listbox.bind('<<ListboxSelect>>', self.on_result_select)
        scrollbar.config(command=self.result_listbox.yview)
        
        # 수정 영역
        edit_frame = ttk.Frame(right_frame)
        edit_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(edit_frame, text="번호판:").pack(side=tk.LEFT, padx=5)
        self.plate_entry = ttk.Entry(edit_frame, font=("맑은 고딕", 12), width=15)
        self.plate_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(edit_frame, text="수정", command=self.update_plate).pack(side=tk.LEFT, padx=5)
        
        # 하단 상태 및 진행률
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(bottom_frame, variable=self.progress_var, 
                                             maximum=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        status_frame = ttk.Frame(bottom_frame)
        status_frame.pack(fill=tk.X)
        
        self.status_label = ttk.Label(status_frame, text="준비됨")
        self.status_label.pack(side=tk.LEFT)
        
        ttk.Button(status_frame, text="💾 Excel 저장", command=self.save_to_excel, 
                   style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(status_frame, text="🔄 초기화", command=self.reset_all).pack(side=tk.RIGHT, padx=5)
    
    def select_folder(self):
        """폴더 선택"""
        folder = filedialog.askdirectory(title="이미지 폴더 선택")
        if folder:
            self.image_files = []
            for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
                import glob
                self.image_files.extend(glob.glob(os.path.join(folder, ext)))
                self.image_files.extend(glob.glob(os.path.join(folder, ext.upper())))
            
            self.image_files.sort()
            self.results = [{"filename": os.path.basename(f), "path": f, "plate": ""} 
                           for f in self.image_files]
            self.current_index = 0
            self.update_result_list()
            self.show_current_image()
            self.update_status(f"{len(self.image_files)}개 이미지 로드됨")
    
    def select_files(self):
        """파일 선택"""
        files = filedialog.askopenfilenames(
            title="이미지 파일 선택",
            filetypes=[("이미지 파일", "*.jpg *.jpeg *.png *.bmp"), ("모든 파일", "*.*")]
        )
        if files:
            self.image_files = list(files)
            self.results = [{"filename": os.path.basename(f), "path": f, "plate": ""} 
                           for f in self.image_files]
            self.current_index = 0
            self.update_result_list()
            self.show_current_image()
            self.update_status(f"{len(self.image_files)}개 이미지 로드됨")
    
    def show_current_image(self):
        """현재 이미지 표시"""
        if not self.image_files or self.current_index >= len(self.image_files):
            return
        
        try:
            img_path = self.image_files[self.current_index]
            img = Image.open(img_path)
            
            # 이미지 크기 조정
            max_size = (450, 400)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(img)
            self.image_label.configure(image=photo, text="")
            self.image_label.image = photo
            
            self.nav_label.configure(text=f"{self.current_index + 1} / {len(self.image_files)}")
            
            # 현재 결과의 번호판 표시
            if self.results:
                self.plate_entry.delete(0, tk.END)
                self.plate_entry.insert(0, self.results[self.current_index].get("plate", ""))
        except Exception as e:
            self.image_label.configure(image="", text=f"이미지 로드 실패: {e}")
    
    def prev_image(self):
        """이전 이미지"""
        if self.current_index > 0:
            self.current_index -= 1
            self.show_current_image()
            self.result_listbox.selection_clear(0, tk.END)
            self.result_listbox.selection_set(self.current_index)
            self.result_listbox.see(self.current_index)
    
    def next_image(self):
        """다음 이미지"""
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.show_current_image()
            self.result_listbox.selection_clear(0, tk.END)
            self.result_listbox.selection_set(self.current_index)
            self.result_listbox.see(self.current_index)
    
    def update_result_list(self):
        """결과 목록 업데이트"""
        self.result_listbox.delete(0, tk.END)
        for i, result in enumerate(self.results):
            plate = result.get("plate", "")
            status = "✅" if plate else "⏳"
            self.result_listbox.insert(tk.END, f"{status} {result['filename']}: {plate}")
    
    def on_result_select(self, event):
        """결과 항목 선택"""
        selection = self.result_listbox.curselection()
        if selection:
            self.current_index = selection[0]
            self.show_current_image()
    
    def update_plate(self):
        """번호판 수정"""
        if self.results and self.current_index < len(self.results):
            new_plate = self.plate_entry.get().strip()
            self.results[self.current_index]["plate"] = new_plate
            self.update_result_list()
            self.result_listbox.selection_set(self.current_index)
            self.update_status(f"번호판 수정됨: {new_plate}")
    
    def start_processing(self):
        """분석 시작"""
        if not OCR_AVAILABLE:
            messagebox.showerror("오류", "OCR 모듈이 로드되지 않았습니다.")
            return
        
        if not self.image_files:
            messagebox.showwarning("경고", "먼저 이미지를 선택해주세요.")
            return
        
        if self.processing:
            return
        
        self.processing = True
        threading.Thread(target=self._process_images, daemon=True).start()
    
    def _process_images(self):
        """이미지 처리 (백그라운드 스레드)"""
        total = len(self.image_files)
        
        for i, img_path in enumerate(self.image_files):
            if not self.processing:
                break
            
            try:
                plate, _ = detect_best_plate(img_path)
                self.results[i]["plate"] = plate if plate else ""
            except Exception as e:
                self.results[i]["plate"] = ""
            
            # UI 업데이트 (메인 스레드에서)
            progress = ((i + 1) / total) * 100
            self.root.after(0, lambda p=progress, idx=i: self._update_progress(p, idx))
        
        self.processing = False
        self.root.after(0, lambda: self.update_status("분석 완료!"))
    
    def _update_progress(self, progress, index):
        """진행률 업데이트"""
        self.progress_var.set(progress)
        self.update_result_list()
        self.result_listbox.see(index)
        self.update_status(f"분석 중... {index + 1}/{len(self.image_files)}")
    
    def stop_processing(self):
        """분석 중지"""
        self.processing = False
        self.update_status("분석 중지됨")
    
    def save_to_excel(self):
        """Excel 저장"""
        if not self.results:
            messagebox.showwarning("경고", "저장할 데이터가 없습니다.")
            return
        
        # 유효한 번호판만 필터링
        valid_results = [r for r in self.results if r.get("plate")]
        
        if not valid_results:
            messagebox.showwarning("경고", "인식된 번호판이 없습니다.")
            return
        
        # DataFrame 생성
        entries = []
        for r in valid_results:
            entries.append({
                "날짜": datetime.now().strftime('%Y-%m-%d'),
                "시간대": self.ampm_var.get(),
                "단속위치": self.location_var.get(),
                "사유": self.reason_var.get(),
                "차량번호": r["plate"]
            })
        
        df = pd.DataFrame(entries)
        
        # 파일 저장 대화상자
        filename = f"주차단속내역_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.xlsx"
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel 파일", "*.xlsx")],
            initialfile=filename
        )
        
        if filepath:
            try:
                df.to_excel(filepath, index=False)
                messagebox.showinfo("성공", f"저장 완료: {filepath}\n총 {len(entries)}건")
                self.update_status(f"Excel 저장 완료: {len(entries)}건")
            except Exception as e:
                messagebox.showerror("오류", f"저장 실패: {e}")
    
    def reset_all(self):
        """초기화"""
        self.image_files = []
        self.results = []
        self.current_index = 0
        self.progress_var.set(0)
        self.result_listbox.delete(0, tk.END)
        self.plate_entry.delete(0, tk.END)
        self.image_label.configure(image="", text="이미지를 선택하세요")
        self.nav_label.configure(text="0 / 0")
        self.update_status("초기화됨")
    
    def update_status(self, text):
        """상태 업데이트"""
        self.status_label.configure(text=text)
    
    def copy_server_url(self):
        """서버 URL을 클립보드에 복사"""
        if self.server_url:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.server_url)
            self.root.update()  # 클립보드 업데이트 강제
            self.update_status(f"✅ 주소 복사됨: {self.server_url}")
            messagebox.showinfo("복사 완료", f"서버 주소가 복사되었습니다:\n{self.server_url}")
        else:
            self.update_status("⚠️ 서버가 실행되지 않았습니다")
    
    def toggle_server(self):
        """웹 서버 시작/중지 토글"""
        if self.server_running:
            # 서버 중지
            self.stop_background_server()
        else:
            # 서버 시작
            self.start_background_server()
    
    def stop_background_server(self):
        """백그라운드 웹 서버 중지"""
        import subprocess
        
        # Cloudflare 프로세스 종료
        try:
            subprocess.run(
                ["taskkill", "/f", "/im", "cloudflared.exe"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except:
            pass
        
        self.server_running = False
        self.server_btn.configure(text="🌐 서버 시작")
        self.copy_url_btn.configure(state=tk.DISABLED)
        self.server_status_label.configure(text="")
        self.server_url = None
        self.update_status("서버 중지됨 (다시 시작 버튼 클릭)")

    def start_background_server(self):
        """백그라운드 웹 서버 시작"""
        import socket
        import subprocess
        
        # 기존 cloudflared 프로세스 정리
        try:
            subprocess.run(
                ["taskkill", "/f", "/im", "cloudflared.exe"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except:
            pass
        
        # 포트 사용 확인
        port = 5000
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('127.0.0.1', port))
            sock.close()
        except OSError:
            messagebox.showerror("오류", f"포트 {port}가 이미 사용 중입니다.\n다른 서버가 실행 중인지 확인하세요.")
            return
        
        def run_server():
            try:
                from ocr import app, init_cloudflare_tunnel, send_discord_webhook
                from waitress import serve
                
                # Cloudflare Tunnel 시도
                public_url = init_cloudflare_tunnel(port)
                
                if public_url:
                    self.server_url = public_url
                    self.root.after(0, lambda: self.server_status_label.configure(
                        text=f"🌐 {public_url[:30]}..."))
                    # Discord 알림
                    try:
                        send_discord_webhook(public_url)
                    except:
                        pass
                else:
                    self.server_url = f"http://127.0.0.1:{port}"
                    self.root.after(0, lambda: self.server_status_label.configure(
                        text=f"🏠 로컬만"))
                
                serve(app, host='0.0.0.0', port=port, threads=10, channel_timeout=3000)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("서버 오류", str(e)))
                self.root.after(0, lambda: self.stop_background_server())
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        self.server_running = True
        self.server_btn.configure(text="🔴 서버 중지")
        self.copy_url_btn.configure(state=tk.NORMAL)
        self.server_url = f"http://127.0.0.1:{port}"
        self.update_status("웹 서버 시작 중...")


def main(start_server=False):
    """GUI 애플리케이션 실행"""
    # PIL 설치 확인
    try:
        from PIL import Image, ImageTk
    except ImportError:
        print("❌ Pillow 라이브러리가 필요합니다: pip install Pillow")
        sys.exit(1)
    
    root = tk.Tk()
    app = ParkingEnforcementGUI(root, start_server=start_server)
    root.mainloop()


if __name__ == "__main__":
    main()

