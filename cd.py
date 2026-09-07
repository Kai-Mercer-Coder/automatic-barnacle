import cv2
import imutils
import time
import threading
import winsound
import urllib.parse
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import collections

class SecurityApp:
    def __init__(self, window):
        self.window = window
        self.window.title("CP Plus Advanced Security Monitor")
        self.window.geometry("1100x700")
        self.window.minsize(900, 600)
        self.window.configure(bg="#1a1a2e")
        
        # --- Default Settings ---
        self.camera_ip = "192.168.31.203"
        self.camera_port = "554"
        self.camera_user = "admin"
        self.camera_pass = "admin@123"
        
        self.sensitivity = 2000
        self.cooldown_seconds = 2.0
        self.last_beep_time = 0
        
        # ROI percentages
        self.roi_x1, self.roi_x2 = 0.25, 0.90
        self.roi_y1, self.roi_y2 = 0.20, 0.85
        
        # Threading state
        self.is_running = False
        self.camera = None
        self.baseline_frame = None
        self.fps = 0
        self.detection_count = 0
        self.current_image = None
        
        # Performance - FPS tracking
        self.last_fps_time = time.time()
        self.fps_frame_count = 0
        
        # Performance - Frame queue for smooth display
        self.frame_queue = collections.deque(maxlen=2)
        self.display_lock = threading.Lock()
        
        # Performance settings
        self.target_fps = 30
        self.process_width = 480  # Reduced from 600 for faster processing
        
        self.setup_ui()
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        main_frame = tk.Frame(self.window, bg="#1a1a2e")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left Panel - Controls
        control_panel = tk.Frame(main_frame, bg="#16213e", width=280, padx=15, pady=15)
        control_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        control_panel.pack_propagate(False)
        
        title_label = tk.Label(control_panel, text="SECURITY MONITOR", 
                              font=('Segoe UI', 12, 'bold'), fg="#e94560", bg="#16213e")
        title_label.pack(anchor=tk.W, pady=(0, 15))
        
        # Camera Configuration
        section_label = tk.Label(control_panel, text="CAMERA CONFIGURATION", 
                                font=('Segoe UI', 9, 'bold'), fg="#a0a0a0", bg="#16213e")
        section_label.pack(anchor=tk.W, pady=(0, 5))
        
        tk.Label(control_panel, text="Camera IP:", fg="#ffffff", bg="#16213e", 
                font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 2))
        self.ip_entry = tk.Entry(control_panel, font=('Segoe UI', 10), bg="#0f3460", 
                                fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT)
        self.ip_entry.insert(0, self.camera_ip)
        self.ip_entry.pack(fill=tk.X, pady=(0, 5), ipady=4)
        
        tk.Label(control_panel, text="Port (554 or 25001):", fg="#ffffff", bg="#16213e",
                font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 2))
        self.port_entry = tk.Entry(control_panel, font=('Segoe UI', 10), bg="#0f3460",
                                  fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT)
        self.port_entry.insert(0, self.camera_port)
        self.port_entry.pack(fill=tk.X, pady=(0, 5), ipady=4)
        
        tk.Label(control_panel, text="Username:", fg="#ffffff", bg="#16213e",
                font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 2))
        self.user_entry = tk.Entry(control_panel, font=('Segoe UI', 10), bg="#0f3460",
                                  fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT)
        self.user_entry.insert(0, self.camera_user)
        self.user_entry.pack(fill=tk.X, pady=(0, 5), ipady=4)
        
        tk.Label(control_panel, text="Password:", fg="#ffffff", bg="#16213e",
                font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 2))
        self.pass_entry = tk.Entry(control_panel, show="*", font=('Segoe UI', 10), bg="#0f3460",
                                  fg="#ffffff", insertbackground="#ffffff", relief=tk.FLAT)
        self.pass_entry.insert(0, self.camera_pass)
        self.pass_entry.pack(fill=tk.X, pady=(0, 5), ipady=4)
        
        tk.Frame(control_panel, height=2, bg="#e94560").pack(fill=tk.X, pady=10)
        
        # Performance Settings
        section_perf = tk.Label(control_panel, text="PERFORMANCE", 
                               font=('Segoe UI', 9, 'bold'), fg="#a0a0a0", bg="#16213e")
        section_perf.pack(anchor=tk.W, pady=(0, 5))
        
        tk.Label(control_panel, text="Target FPS:", fg="#ffffff", bg="#16213e",
                font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 2))
        self.fps_slider = tk.Scale(control_panel, from_=15, to=60, orient=tk.HORIZONTAL,
                                  bg="#16213e", fg="#ffffff", troughcolor="#0f3460",
                                  highlightthickness=0, activebackground="#e94560",
                                  sliderrelief=tk.FLAT, bd=0, showvalue=True)
        self.fps_slider.set(30)
        self.fps_slider.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(control_panel, text="Process Width:", fg="#ffffff", bg="#16213e",
                font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 2))
        self.width_slider = tk.Scale(control_panel, from_=320, to=800, orient=tk.HORIZONTAL,
                                    bg="#16213e", fg="#ffffff", troughcolor="#0f3460",
                                    highlightthickness=0, activebackground="#e94560",
                                    sliderrelief=tk.FLAT, bd=0, showvalue=True)
        self.width_slider.set(self.process_width)
        self.width_slider.pack(fill=tk.X, pady=(0, 5))
        
        tk.Frame(control_panel, height=2, bg="#e94560").pack(fill=tk.X, pady=10)
        
        # Detection Tuning
        section_label2 = tk.Label(control_panel, text="DETECTION TUNING", 
                                 font=('Segoe UI', 9, 'bold'), fg="#a0a0a0", bg="#16213e")
        section_label2.pack(anchor=tk.W, pady=(0, 5))
        
        tk.Label(control_panel, text="Sensitivity:", fg="#ffffff", bg="#16213e",
                font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 2))
        self.sens_slider = tk.Scale(control_panel, from_=500, to=15000, orient=tk.HORIZONTAL,
                                   bg="#16213e", fg="#ffffff", troughcolor="#0f3460",
                                   highlightthickness=0, activebackground="#e94560",
                                   sliderrelief=tk.FLAT, bd=0, showvalue=True)
        self.sens_slider.set(self.sensitivity)
        self.sens_slider.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(control_panel, text="Alert Cooldown (sec):", fg="#ffffff", bg="#16213e",
                font=('Segoe UI', 9)).pack(anchor=tk.W, pady=(5, 2))
        self.cooldown_slider = tk.Scale(control_panel, from_=0.5, to=10.0, resolution=0.5,
                                       orient=tk.HORIZONTAL, bg="#16213e", fg="#ffffff",
                                       troughcolor="#0f3460", highlightthickness=0,
                                       activebackground="#e94560", sliderrelief=tk.FLAT, bd=0,
                                       showvalue=True)
        self.cooldown_slider.set(self.cooldown_seconds)
        self.cooldown_slider.pack(fill=tk.X, pady=(0, 5))
        
        tk.Frame(control_panel, height=2, bg="#e94560").pack(fill=tk.X, pady=10)
        
        # Control Buttons
        btn_frame = tk.Frame(control_panel, bg="#16213e")
        btn_frame.pack(fill=tk.X, pady=5)
        
        self.start_btn = tk.Button(btn_frame, text="START MONITOR", command=self.start_monitoring,
                                  bg="#00b4d8", fg="#ffffff", font=('Segoe UI', 10, 'bold'),
                                  activebackground="#0096c7", activeforeground="#ffffff",
                                  relief=tk.FLAT, cursor="hand2", pady=8)
        self.start_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.stop_btn = tk.Button(btn_frame, text="STOP MONITOR", command=self.stop_monitoring,
                                 bg="#e94560", fg="#ffffff", font=('Segoe UI', 10, 'bold'),
                                 activebackground="#c73e54", activeforeground="#ffffff",
                                 relief=tk.FLAT, cursor="hand2", state=tk.DISABLED, pady=8)
        self.stop_btn.pack(fill=tk.X)
        
        # Stats Panel
        stats_frame = tk.Frame(control_panel, bg="#0f3460", padx=10, pady=10)
        stats_frame.pack(fill=tk.X, pady=(15, 0))
        
        self.status_lbl = tk.Label(stats_frame, text="DISCONNECTED", fg="#a0a0a0",
                                  bg="#0f3460", font=('Segoe UI', 10, 'bold'))
        self.status_lbl.pack(anchor=tk.W, pady=(0, 5))
        
        self.fps_lbl = tk.Label(stats_frame, text="FPS: 0", fg="#00ff88", bg="#0f3460",
                               font=('Segoe UI', 9))
        self.fps_lbl.pack(anchor=tk.W, pady=(0, 3))
        
        self.detection_lbl = tk.Label(stats_frame, text="Detections: 0", fg="#ffcc00", 
                                     bg="#0f3460", font=('Segoe UI', 9))
        self.detection_lbl.pack(anchor=tk.W)
        
        self.latency_lbl = tk.Label(stats_frame, text="Latency: 0ms", fg="#00ccff", 
                                   bg="#0f3460", font=('Segoe UI', 9))
        self.latency_lbl.pack(anchor=tk.W, pady=(3, 0))
        
        # Right Panel - Video
        video_panel = tk.Frame(main_frame, bg="#0a0a15")
        video_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(video_panel, bg="#0a0a15", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

    def async_beep(self):
        try:
            winsound.Beep(1200, 100)
        except Exception:
            pass

    def start_monitoring(self):
        self.camera_ip = self.ip_entry.get().strip()
        self.camera_port = self.port_entry.get().strip()
        self.camera_user = self.user_entry.get().strip()
        self.camera_pass = self.pass_entry.get().strip()
        
        if not self.camera_ip or not self.camera_port:
            self.status_lbl.config(text="ERROR: IP/Port required", fg="#ff6b6b")
            return
        
        encoded_pass = urllib.parse.quote_plus(self.camera_pass)
        self.rtsp_url = f"rtsp://{self.camera_user}:{encoded_pass}@{self.camera_ip}:{self.camera_port}/cam/realmonitor?channel=1&subtype=0"
        
        self.is_running = True
        self.detection_count = 0
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.status_lbl.config(text="CONNECTING...", fg="#ffd93d")
        
        self.worker_thread = threading.Thread(target=self.video_loop, daemon=True)
        self.worker_thread.start()

    def stop_monitoring(self):
        self.is_running = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_lbl.config(text="STOPPED", fg="#a0a0a0")
        if self.camera:
            self.camera.release()
        self.baseline_frame = None
        self.canvas.delete("all")
        self.fps_lbl.config(text="FPS: 0")
        self.detection_lbl.config(text="Detections: 0")
        self.latency_lbl.config(text="Latency: 0ms")

    def video_loop(self):
        # Use optimized GStreamer pipeline for lower latency
        gst_pipeline = (
            f"rtspsrc location={self.rtsp_url} latency=0 ! "
            "rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! "
            "video/x-raw,format=BGR ! appsink drop=true"
        )
        
        # Try GStreamer first, fallback to standard OpenCV
        try:
            self.camera = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
            if not self.camera.isOpened():
                raise Exception("GStreamer failed")
        except:
            # Optimized OpenCV fallback
            self.camera = cv2.VideoCapture(self.rtsp_url)
            self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimal buffer
            self.camera.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
            self.camera.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        
        time.sleep(1.0)
        
        if not self.camera.isOpened():
            self.window.after(0, lambda: self.status_lbl.config(text="CONNECTION FAILED", fg="#ff6b6b"))
            self.window.after(0, self.stop_monitoring)
            return

        self.window.after(0, lambda: self.status_lbl.config(text="LIVE", fg="#00ff88"))
        self.last_fps_time = time.time()
        self.fps_frame_count = 0
        
        while self.is_running:
            loop_start = time.time()
            
            # Skip frames to reduce lag - grab latest frame
            grabbed = False
            frame = None
            for _ in range(3):  # Skip up to 3 buffered frames
                grabbed, frame = self.camera.read()
                if not grabbed:
                    break
            
            if not grabbed or frame is None:
                print("[ERROR] Dropped stream frame.")
                break
            
            current_sensitivity = self.sens_slider.get()
            current_cooldown = self.cooldown_slider.get()
            self.process_width = self.width_slider.get()
            self.target_fps = self.fps_slider.get()

            full_frame = frame
            
            # Optimize: single resize operation
            frame_resized = cv2.resize(full_frame, (self.process_width, 0), fx=0, fy=0, interpolation=cv2.INTER_LINEAR)
            if frame_resized.size == 0:
                frame_resized = imutils.resize(full_frame, width=self.process_width)
            
            gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
            # Smaller kernel for faster blur
            gray = cv2.GaussianBlur(gray, (11, 11), 0)

            h, w = gray.shape
            x_start, x_end = int(w * self.roi_x1), int(w * self.roi_x2)
            y_start, y_end = int(h * self.roi_y1), int(h * self.roi_y2)
            roi_gray = gray[y_start:y_end, x_start:x_end]

            full_h, full_w = full_frame.shape[:2]
            fx_start, fx_end = int(full_w * self.roi_x1), int(full_w * self.roi_x2)
            fy_start, fy_end = int(full_h * self.roi_y1), int(full_h * self.roi_y2)
            
            cv2.rectangle(full_frame, (fx_start, fy_start), (fx_end, fy_end), (0, 255, 255), 2)

            if self.baseline_frame is None or self.baseline_frame.shape != roi_gray.shape:
                self.baseline_frame = roi_gray
                continue

            frame_delta = cv2.absdiff(self.baseline_frame, roi_gray)
            thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)

            contours = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = imutils.grab_contours(contours)

            motion_detected = False
            scale_x = (fx_end - fx_start) / max(1, (x_end - x_start))
            scale_y = (fy_end - fy_start) / max(1, (y_end - y_start))
            
            for contour in contours:
                if cv2.contourArea(contour) < current_sensitivity:
                    continue
                motion_detected = True
                
                x, y, w_box, h_box = cv2.boundingRect(contour)
                actual_x = fx_start + int(x * scale_x)
                actual_y = fy_start + int(y * scale_y)
                actual_w = int(w_box * scale_x)
                actual_h = int(h_box * scale_y)
                cv2.rectangle(full_frame, (actual_x, actual_y), 
                             (actual_x + actual_w, actual_y + actual_h), (0, 0, 255), 3)

            if motion_detected:
                cv2.putText(full_frame, "ALERT: INTRUSION", (30, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
                current_time = time.time()
                if current_time - self.last_beep_time > current_cooldown:
                    self.last_beep_time = current_time
                    self.detection_count += 1
                    self.window.after(0, lambda: self.detection_lbl.config(
                        text=f"Detections: {self.detection_count}"))
                    threading.Thread(target=self.async_beep, daemon=True).start()
            else:
                cv2.putText(full_frame, "MONITORING ACTIVE", (30, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

            # Optimized frame conversion
            cv2_image = cv2.cvtColor(full_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(cv2_image)
            
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            if canvas_w > 10 and canvas_h > 10:
                # Use faster interpolation for display
                img_pil = img_pil.resize((canvas_w, canvas_h), Image.Resampling.NEAREST)
                
            img_tk = ImageTk.PhotoImage(image=img_pil)
            
            # Queue frame for display
            with self.display_lock:
                self.frame_queue.append(img_tk)
            
            self.window.after(0, self.update_canvas)
            
            # Calculate latency
            latency_ms = (time.time() - loop_start) * 1000
            
            # FPS calculation
            self.fps_frame_count += 1
            current_time = time.time()
            elapsed = current_time - self.last_fps_time
            if elapsed >= 1.0:
                self.fps = self.fps_frame_count / elapsed
                self.fps_frame_count = 0
                self.last_fps_time = current_time
                self.window.after(0, lambda f=self.fps, l=latency_ms: 
                    (self.fps_lbl.config(text=f"FPS: {f:.1f}"),
                     self.latency_lbl.config(text=f"Latency: {l:.0f}ms")))
            
            # Precise frame pacing
            elapsed_loop = time.time() - loop_start
            sleep_time = max(0, (1/self.target_fps) - elapsed_loop)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def update_canvas(self):
        with self.display_lock:
            if self.frame_queue:
                img_tk = self.frame_queue[-1]  # Get latest frame
            else:
                return
        
        self.current_image = img_tk
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)

    def on_close(self):
        self.stop_monitoring()
        self.window.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = SecurityApp(root)
    root.mainloop()
