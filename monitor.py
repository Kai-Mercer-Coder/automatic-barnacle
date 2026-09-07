import cv2
import imutils
import time
import os
import threading
import winsound
import urllib.parse
import collections
import tkinter as tk
from PIL import Image, ImageTk
from stealth_alert import StealthAlert

class SecurityMonitor:
    def __init__(self, config, status_callback):
        self.config = config
        self.status_callback = status_callback
        
        self.is_running = False
        self.camera = None
        self.baseline_frame = None
        self.detection_count = 0
        self.last_beep_time = 0
        self.current_image = None
        self.processed_count = 0
        
        self.fps = 0
        self.last_fps_time = time.time()
        self.fps_frame_count = 0
        
        self.frame_queue = collections.deque(maxlen=2)
        self.display_lock = threading.Lock()
        self.canvas = None
        self.stealth_alert = None
        
        self._color_map = {
            "red": (0, 0, 255),
            "green": (0, 255, 0),
            "yellow": (0, 255, 255),
            "cyan": (255, 255, 0),
        }

    def reset_baseline(self):
        self.baseline_frame = None

    def async_beep(self):
        try:
            winsound.Beep(1200, 100)
        except Exception:
            pass

    def _save_screenshot(self, frame):
        try:
            ts = time.strftime("%Y%m%d_%H%M%S")
            path = os.path.join(self.config.screenshot_dir, f"det_{ts}.jpg")
            cv2.imwrite(path, frame)
        except Exception:
            pass

    def _trigger_alert(self, frame):
        if self.config.stealth_enabled and self.stealth_alert:
            try:
                self.stealth_alert.show_timed(self.config.cooldown_seconds)
            except Exception as e:
                print(f"[MONITOR] Stealth alert trigger failed: {e}")
        if self.config.stealth_beep:
            threading.Thread(target=self.async_beep, daemon=True).start()
        if self.config.stealth_screenshot:
            threading.Thread(target=self._save_screenshot, args=(frame,), daemon=True).start()

    def start(self, canvas):
        self.canvas = canvas
        self.is_running = True
        self.detection_count = 0
        self.processed_count = 0
        
        if self.config.stealth_enabled:
            self.stealth_alert = StealthAlert(title=self.config.stealth_title)
            self.stealth_alert.create()
        
        os.makedirs(self.config.screenshot_dir, exist_ok=True)
        
        self.status_callback("status", "CONNECTING")
        
        self.worker_thread = threading.Thread(target=self.video_loop, daemon=True)
        self.worker_thread.start()

    def stop(self):
        self.is_running = False
        if self.camera:
            self.camera.release()
            self.camera = None
        self.baseline_frame = None
        if self.stealth_alert:
            self.stealth_alert.cleanup()
            self.stealth_alert = None

    def build_rtsp_url(self):
        encoded_pass = urllib.parse.quote_plus(self.config.camera_pass)
        return f"rtsp://{self.config.camera_user}:{encoded_pass}@{self.config.camera_ip}:{self.config.camera_port}/cam/realmonitor?channel=1&subtype=0"

    def _get_resize_method(self):
        methods = {
            "nearest": Image.Resampling.NEAREST,
            "bilinear": Image.Resampling.BILINEAR,
            "cubic": Image.Resampling.BICUBIC,
        }
        return methods.get(self.config.resize_interp, Image.Resampling.NEAREST)

    def video_loop(self):
        rtsp_url = self.build_rtsp_url()
        
        self.camera = cv2.VideoCapture(rtsp_url)
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, self.config.buffer_size)
        self.camera.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 5000)
        self.camera.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        
        time.sleep(1.0)
        
        if not self.camera.isOpened():
            self.status_callback("status", "ERROR")
            self.is_running = False
            return

        self.status_callback("status", "LIVE")
        self.last_fps_time = time.time()
        self.fps_frame_count = 0
        resize_method = self._get_resize_method()
        
        while self.is_running:
            loop_start = time.time()
            
            # Skip buffered frames (configurable)
            skip = self.config.skip_frames
            grabbed = False
            frame = None
            for _ in range(skip + 1):
                g, f = self.camera.read()
                if g:
                    grabbed = True
                    frame = f
            
            if not grabbed or frame is None:
                print("[ERROR] Dropped stream frame.")
                break
            
            full_frame = frame
            
            # Resize using configured method
            interp_flag = {
                "nearest": cv2.INTER_NEAREST,
                "bilinear": cv2.INTER_LINEAR,
                "cubic": cv2.INTER_CUBIC,
            }.get(self.config.resize_interp, cv2.INTER_NEAREST)
            ratio = self.config.process_width / full_frame.shape[1]
            new_h = int(full_frame.shape[0] * ratio)
            frame_resized = cv2.resize(full_frame, (self.config.process_width, new_h), 
                                       interpolation=interp_flag)
            
            gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
            
            # Use configured blur kernel (must be odd)
            k = self.config.blur_kernel
            if k % 2 == 0:
                k += 1
            gray = cv2.GaussianBlur(gray, (k, k), 0)

            h, w = gray.shape
            x_start = int(w * self.config.roi_x1)
            x_end = int(w * self.config.roi_x2)
            y_start = int(h * self.config.roi_y1)
            y_end = int(h * self.config.roi_y2)
            roi_gray = gray[y_start:y_end, x_start:x_end]

            full_h, full_w = full_frame.shape[:2]
            fx_start = int(full_w * self.config.roi_x1)
            fx_end = int(full_w * self.config.roi_x2)
            fy_start = int(full_h * self.config.roi_y1)
            fy_end = int(full_h * self.config.roi_y2)
            
            if self.config.show_roi_outline:
                cv2.rectangle(full_frame, (fx_start, fy_start), (fx_end, fy_end), (0, 255, 255), 2)

            if self.baseline_frame is None or self.baseline_frame.shape != roi_gray.shape:
                self.baseline_frame = roi_gray
                continue

            frame_delta = cv2.absdiff(self.baseline_frame, roi_gray)
            thresh = cv2.threshold(frame_delta, self.config.threshold, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)

            contours = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            contours = imutils.grab_contours(contours)

            motion_detected = False
            scale_x = (fx_end - fx_start) / max(1, (x_end - x_start))
            scale_y = (fy_end - fy_start) / max(1, (y_end - y_start))
            box_color = self._color_map.get(self.config.box_color, (0, 0, 255))
            
            for contour in contours:
                if cv2.contourArea(contour) < self.config.sensitivity:
                    continue
                motion_detected = True
                
                x, y, w_box, h_box = cv2.boundingRect(contour)
                actual_x = fx_start + int(x * scale_x)
                actual_y = fy_start + int(y * scale_y)
                actual_w = int(w_box * scale_x)
                actual_h = int(h_box * scale_y)
                cv2.rectangle(full_frame, (actual_x, actual_y), 
                             (actual_x + actual_w, actual_y + actual_h), box_color, self.config.box_thickness)

            if motion_detected:
                cv2.putText(full_frame, "ALERT: INTRUSION", (30, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
                current_time = time.time()
                if current_time - self.last_beep_time > self.config.cooldown_seconds:
                    self.last_beep_time = current_time
                    self.detection_count += 1
                    self.status_callback("detections", self.detection_count)
                    self._trigger_alert(full_frame)
            else:
                cv2.putText(full_frame, "MONITORING ACTIVE", (30, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

            self.processed_count += 1
            if self.processed_count % 30 == 0:
                self.status_callback("processed", self.processed_count)

            cv2_image = cv2.cvtColor(full_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(cv2_image)
            
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()
            if canvas_w > 10 and canvas_h > 10:
                img_pil = img_pil.resize((canvas_w, canvas_h), resize_method)
                
            img_tk = ImageTk.PhotoImage(image=img_pil)
            
            with self.display_lock:
                self.frame_queue.append(img_tk)
            
            self.canvas.after(0, self.update_canvas)
            
            latency_ms = (time.time() - loop_start) * 1000
            
            self.fps_frame_count += 1
            current_time = time.time()
            elapsed = current_time - self.last_fps_time
            if elapsed >= 1.0:
                self.fps = self.fps_frame_count / elapsed
                self.fps_frame_count = 0
                self.last_fps_time = current_time
                self.status_callback("fps", self.fps)
                self.status_callback("latency", latency_ms)
            
            elapsed_loop = time.time() - loop_start
            sleep_time = max(0, (1 / self.config.target_fps) - elapsed_loop)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def update_canvas(self):
        with self.display_lock:
            if self.frame_queue:
                img_tk = self.frame_queue[-1]
            else:
                return
        
        self.current_image = img_tk
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)
