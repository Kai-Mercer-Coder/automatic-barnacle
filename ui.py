import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from config import Config
from monitor import SecurityMonitor


class RoundedButton(tk.Canvas):
    """Canvas-based button with actual rounded corners."""

    def __init__(self, master, text, command, bg="#00ff88", fg="#000000",
                 active_bg=None, font=('Segoe UI', 10, 'bold'), radius=14,
                 height=40, disabled_bg="#1c1c1c", disabled_fg="#555555"):
        self._master_bg = master["bg"]
        super().__init__(master, bg=self._master_bg, highlightthickness=0,
                         bd=0, cursor="hand2", height=height)
        self._command = command
        self._bg = bg
        self._fg = fg
        self._active_bg = active_bg or bg
        self._font = font
        self._radius = radius
        self._height = height
        self._disabled_bg = disabled_bg
        self._disabled_fg = disabled_fg
        self._text = text
        self._enabled = True
        self._hover = False

        # Auto-size width to fit the text
        f = tkfont.Font(font=self._font)
        self.configure(width=f.measure(text) + 32)

        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Configure>", lambda e: self._draw())
        self._draw()

    def _round_rect_points(self, w, h, r):
        return [
            r, 0, w - r, 0, w, 0, w, r,
            w, h - r, w, h, w - r, h, r, h,
            0, h, 0, h - r, 0, r, 0, 0,
        ]

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return
        if self._enabled:
            color = self._active_bg if self._hover else self._bg
            text_color = self._fg
        else:
            color = self._disabled_bg
            text_color = self._disabled_fg
        r = min(self._radius, w // 2, h // 2)
        pts = self._round_rect_points(w, h, r)
        self.create_polygon(pts, smooth=True, fill=color, outline=color)
        self.create_text(w // 2, h // 2, text=self._text,
                         fill=text_color, font=self._font)

    def _on_enter(self, _):
        self._hover = True
        self._draw()

    def _on_leave(self, _):
        self._hover = False
        self._draw()

    def _on_click(self, _):
        if self._enabled and self._command:
            self._command()

    def set_text(self, text):
        self._text = text
        self._draw()

    def config_button(self, state=None):
        if state is not None:
            self._enabled = state != tk.DISABLED
            self.configure(cursor="hand2" if self._enabled else "arrow")
            self._draw()

    # Mirror the tk.Button API used elsewhere
    def config(self, state=None, text=None, **kwargs):
        if state is not None:
            self.config_button(state=state)
        if text is not None:
            self.set_text(text)

class SecurityApp:
    def __init__(self, window):
        self.window = window
        self.window.title("Security Monitor")
        self.window.geometry("1200x750")
        self.window.minsize(900, 600)
        self.window.configure(bg="#0a0a0a")
        
        self.config = Config()
        self.monitor = SecurityMonitor(self.config, self.on_status_update)
        
        # ROI dragging state
        self.roi_drawing = False
        self.roi_start = None
        self.roi_rect = None
        self.roi_preview = None
        
        self.setup_ui()
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        main_frame = tk.Frame(self.window, bg="#0a0a0a")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        
        # RIGHT PANEL - Video (create canvas first so controls can reference it)
        video_panel = tk.Frame(main_frame, bg="#0a0a0a")
        video_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(video_panel, bg="#000000", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # LEFT PANEL
        control_panel = tk.Frame(main_frame, bg="#111111", width=320, padx=12, pady=12)
        control_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 8))
        control_panel.pack_propagate(False)
        
        ctrl_canvas = tk.Canvas(control_panel, bg="#111111", highlightthickness=0)
        ctrl_scrollbar = ttk.Scrollbar(control_panel, orient="vertical", command=ctrl_canvas.yview)
        self.scrollable_frame = tk.Frame(ctrl_canvas, bg="#111111")
        
        self.scrollable_frame.bind("<Configure>", lambda e: ctrl_canvas.configure(scrollregion=ctrl_canvas.bbox("all")))
        ctrl_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        ctrl_canvas.configure(yscrollcommand=ctrl_scrollbar.set)
        
        def _on_mousewheel(event):
            ctrl_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        ctrl_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        ctrl_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        ctrl_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self._build_controls(self.scrollable_frame)
        
        # ROI drawing bindings (after canvas exists)
        self.canvas.bind("<ButtonPress-1>", self.roi_mouse_down)
        self.canvas.bind("<B1-Motion>", self.roi_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.roi_mouse_up)

    def _build_controls(self, p):
        # -- CAMERA --
        self._section(p, "CAMERA")
        
        self.ip_entry = self._entry(p, "IP", self.config.camera_ip)
        self.port_entry = self._entry(p, "Port", self.config.camera_port)
        self.user_entry = self._entry(p, "User", self.config.camera_user)
        self.pass_entry = self._entry(p, "Pass", self.config.camera_pass, show="*")
        
        # -- ROI (drag on video or set below) --
        self._section(p, "DETECTION BOX (drag on video)")
        
        # Preset dropdown
        roi_frame = tk.Frame(p, bg="#111111")
        roi_frame.pack(fill=tk.X, pady=(0, 3))
        
        presets = ["custom", "full", "center", "top-half", "bottom-half",
                   "left-half", "right-half", "top-left", "top-right",
                   "bottom-left", "bottom-right"]
        self.roi_preset_var = tk.StringVar(value=self.config.roi_mode)
        roi_menu = tk.OptionMenu(roi_frame, self.roi_preset_var, *presets, command=self.apply_roi_preset)
        roi_menu.config(bg="#1a1a1a", fg="#ffffff", activebackground="#222222", activeforeground="#ffffff",
                       highlightthickness=0, relief=tk.FLAT, font=('Segoe UI', 9))
        roi_menu["menu"].config(bg="#1a1a1a", fg="#ffffff", activebackground="#333333")
        roi_menu.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        self.roi_reset_btn = RoundedButton(roi_frame, text="Reset", command=self.reset_roi,
                                          bg="#1a1a1a", fg="#777777", active_bg="#2a2a2a",
                                          font=('Segoe UI', 8), radius=10, height=26)
        self.roi_reset_btn.pack(side=tk.RIGHT, padx=(4, 0))
        
        # Per-edge inputs (percentages)
        edges_frame = tk.Frame(p, bg="#111111")
        edges_frame.pack(fill=tk.X, pady=(5, 3))
        
        # Left / Right
        lr_frame = tk.Frame(edges_frame, bg="#111111")
        lr_frame.pack(fill=tk.X, pady=2)
        
        tk.Label(lr_frame, text="Left:", fg="#666666", bg="#111111", font=('Segoe UI', 8)).pack(side=tk.LEFT)
        self.roi_left_var = tk.StringVar(value=str(int(self.config.roi_left)))
        self.roi_left_entry = tk.Entry(lr_frame, textvariable=self.roi_left_var, width=5,
                                       font=('Consolas', 9), bg="#1a1a1a", fg="#ffffff",
                                       insertbackground="#ffffff", relief=tk.FLAT)
        self.roi_left_entry.pack(side=tk.LEFT, padx=(2, 0), ipady=2)
        tk.Label(lr_frame, text="%", fg="#444444", bg="#111111", font=('Segoe UI', 7)).pack(side=tk.LEFT)
        
        tk.Label(lr_frame, text="Right:", fg="#666666", bg="#111111", font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=(10, 0))
        self.roi_right_var = tk.StringVar(value=str(int(self.config.roi_right)))
        self.roi_right_entry = tk.Entry(lr_frame, textvariable=self.roi_right_var, width=5,
                                        font=('Consolas', 9), bg="#1a1a1a", fg="#ffffff",
                                        insertbackground="#ffffff", relief=tk.FLAT)
        self.roi_right_entry.pack(side=tk.LEFT, padx=(2, 0), ipady=2)
        tk.Label(lr_frame, text="%", fg="#444444", bg="#111111", font=('Segoe UI', 7)).pack(side=tk.LEFT)
        
        # Top / Bottom
        tb_frame = tk.Frame(edges_frame, bg="#111111")
        tb_frame.pack(fill=tk.X, pady=2)
        
        tk.Label(tb_frame, text="Top:", fg="#666666", bg="#111111", font=('Segoe UI', 8)).pack(side=tk.LEFT)
        self.roi_top_var = tk.StringVar(value=str(int(self.config.roi_top)))
        self.roi_top_entry = tk.Entry(tb_frame, textvariable=self.roi_top_var, width=5,
                                      font=('Consolas', 9), bg="#1a1a1a", fg="#ffffff",
                                      insertbackground="#ffffff", relief=tk.FLAT)
        self.roi_top_entry.pack(side=tk.LEFT, padx=(2, 0), ipady=2)
        tk.Label(tb_frame, text="%", fg="#444444", bg="#111111", font=('Segoe UI', 7)).pack(side=tk.LEFT)
        
        tk.Label(tb_frame, text="Bottom:", fg="#666666", bg="#111111", font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=(10, 0))
        self.roi_bottom_var = tk.StringVar(value=str(int(self.config.roi_bottom)))
        self.roi_bottom_entry = tk.Entry(tb_frame, textvariable=self.roi_bottom_var, width=5,
                                         font=('Consolas', 9), bg="#1a1a1a", fg="#ffffff",
                                         insertbackground="#ffffff", relief=tk.FLAT)
        self.roi_bottom_entry.pack(side=tk.LEFT, padx=(2, 0), ipady=2)
        tk.Label(tb_frame, text="%", fg="#444444", bg="#111111", font=('Segoe UI', 7)).pack(side=tk.LEFT)
        
        # Apply button + pixel preview
        apply_frame = tk.Frame(p, bg="#111111")
        apply_frame.pack(fill=tk.X, pady=(3, 3))
        
        self.roi_apply_btn = RoundedButton(apply_frame, text="Apply", command=self.apply_roi_manual,
                                          bg="#00ff88", fg="#000000", active_bg="#00cc66",
                                          font=('Segoe UI', 8, 'bold'), radius=10, height=26)
        self.roi_apply_btn.pack(side=tk.LEFT)
        
        self.roi_pixel_lbl = tk.Label(apply_frame, text="", fg="#444444", bg="#111111",
                                      font=('Consolas', 7))
        self.roi_pixel_lbl.pack(side=tk.LEFT, padx=(8, 0))
        self._update_roi_pixel_label()
        
        self.roi_lbl = tk.Label(p, text="", fg="#555555", bg="#111111", font=('Consolas', 8))
        self.roi_lbl.pack(anchor=tk.W, pady=(0, 5))
        self._update_roi_label()
        
        # -- BOX STYLE --
        self._section(p, "BOX STYLE")
        
        color_frame = tk.Frame(p, bg="#111111")
        color_frame.pack(fill=tk.X, pady=(0, 3))
        tk.Label(color_frame, text="Color:", fg="#666666", bg="#111111", font=('Segoe UI', 8)).pack(side=tk.LEFT)
        self.box_color_var = tk.StringVar(value=self.config.box_color)
        for color in ["red", "green", "yellow", "cyan"]:
            rb = tk.Radiobutton(color_frame, text=color, variable=self.box_color_var, value=color,
                               bg="#111111", fg="#888888", selectcolor="#1a1a1a",
                               activebackground="#111111", activeforeground="#ffffff",
                               font=('Segoe UI', 8), highlightthickness=0)
            rb.pack(side=tk.LEFT, padx=(4, 0))
        
        self.box_thickness_slider = self._slider(p, "Box Thickness", 1, 6, self.config.box_thickness)
        
        self.show_roi_var = tk.BooleanVar(value=self.config.show_roi_outline)
        tk.Checkbutton(p, text="Show ROI outline", variable=self.show_roi_var,
                      bg="#111111", fg="#666666", selectcolor="#1a1a1a",
                      activebackground="#111111", activeforeground="#ffffff",
                      font=('Segoe UI', 8), highlightthickness=0).pack(anchor=tk.W, pady=(3, 5))
        
        # -- DETECTION --
        self._section(p, "DETECTION")
        
        self.sens_slider = self._slider(p, "Sensitivity", 500, 15000, self.config.sensitivity)
        self.cooldown_slider = self._slider(p, "Cooldown", 0.5, 10.0, self.config.cooldown_seconds, res=0.5)
        self.blur_slider = self._slider(p, "Blur Kernel", 3, 31, self.config.blur_kernel, res=2)
        self.threshold_slider = self._slider(p, "Threshold", 5, 100, self.config.threshold)
        self.adapt_slider = self._slider(p, "Adapt After (s)", 1, 60, self.config.baseline_reset_seconds, res=1)
        self.maxbeep_slider = self._slider(p, "Max Beep (s)", 1, 60, self.config.alert_max_seconds, res=1)
        
        # -- PERFORMANCE --
        self._section(p, "PERFORMANCE")
        
        self.fps_slider = self._slider(p, "Target FPS", 15, 60, self.config.target_fps)
        self.width_slider = self._slider(p, "Process Width", 320, 960, self.config.process_width, res=32)
        self.skip_slider = self._slider(p, "Skip Frames", 0, 5, self.config.skip_frames)
        self.buffer_slider = self._slider(p, "Buffer Size", 1, 5, self.config.buffer_size)
        
        # Resize method
        res_frame = tk.Frame(p, bg="#111111")
        res_frame.pack(fill=tk.X, pady=(5, 5))
        tk.Label(res_frame, text="Resize:", fg="#666666", bg="#111111", font=('Segoe UI', 8)).pack(side=tk.LEFT)
        self.resize_var = tk.StringVar(value=self.config.resize_interp)
        for mode in ["nearest", "bilinear", "cubic"]:
            rb = tk.Radiobutton(res_frame, text=mode, variable=self.resize_var, value=mode,
                               bg="#111111", fg="#888888", selectcolor="#1a1a1a",
                               activebackground="#111111", activeforeground="#ffffff",
                               font=('Segoe UI', 8), highlightthickness=0)
            rb.pack(side=tk.LEFT, padx=(6, 0))
        
        # -- SOUND ALERT --
        self._section(p, "SOUND ALERT")
        
        self.sound_alert_var = tk.BooleanVar(value=True)
        tk.Checkbutton(p, text="Enable beep on detection", variable=self.sound_alert_var,
                      bg="#111111", fg="#666666", selectcolor="#1a1a1a",
                      activebackground="#111111", activeforeground="#ffffff",
                      font=('Segoe UI', 8), highlightthickness=0).pack(anchor=tk.W, pady=(3, 2))
        
        # -- BUTTONS --
        tk.Frame(p, height=1, bg="#222222").pack(fill=tk.X, pady=10)
        
        self.start_btn = RoundedButton(p, text="START", command=self.start_monitoring,
                                      bg="#00ff88", fg="#000000", active_bg="#00cc66",
                                      font=('Segoe UI', 10, 'bold'), radius=16, height=44)
        self.start_btn.pack(fill=tk.X, pady=(0, 5))
        
        self.stop_btn = RoundedButton(p, text="STOP", command=self.stop_monitoring,
                                     bg="#ff3333", fg="#ffffff", active_bg="#cc0000",
                                     font=('Segoe UI', 10, 'bold'), radius=16, height=44,
                                     disabled_bg="#1c1c1c", disabled_fg="#555555")
        self.stop_btn.config_button(state=tk.DISABLED)
        self.stop_btn.pack(fill=tk.X)
        
        # -- STATS --
        stats_frame = tk.Frame(p, bg="#0d0d0d", padx=8, pady=8)
        stats_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_lbl = tk.Label(stats_frame, text="OFFLINE", fg="#444444",
                                  bg="#0d0d0d", font=('Consolas', 10, 'bold'))
        self.status_lbl.pack(anchor=tk.W, pady=(0, 3))
        
        self.fps_lbl = tk.Label(stats_frame, text="FPS: --", fg="#00ff88", bg="#0d0d0d",
                               font=('Consolas', 9))
        self.fps_lbl.pack(anchor=tk.W, pady=(0, 2))
        
        self.detection_lbl = tk.Label(stats_frame, text="Detections: 0", fg="#ffcc00", 
                                     bg="#0d0d0d", font=('Consolas', 9))
        self.detection_lbl.pack(anchor=tk.W, pady=(0, 2))
        
        self.latency_lbl = tk.Label(stats_frame, text="Latency: --ms", fg="#00ccff", 
                                   bg="#0d0d0d", font=('Consolas', 9))
        self.latency_lbl.pack(anchor=tk.W)
        
        self.processed_lbl = tk.Label(stats_frame, text="Processed: 0", fg="#888888",
                                     bg="#0d0d0d", font=('Consolas', 8))
        self.processed_lbl.pack(anchor=tk.W, pady=(3, 0))

    def _section(self, parent, title):
        row = tk.Frame(parent, bg="#111111")
        row.pack(fill=tk.X, pady=(12, 4))
        tk.Frame(row, bg="#e94560", width=3, height=11).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(row, text=title, fg="#8a8a8a", bg="#111111",
                font=('Segoe UI', 8, 'bold')).pack(side=tk.LEFT)

    def _entry(self, parent, label, default, show=None):
        tk.Label(parent, text=label, fg="#666666", bg="#111111",
                font=('Segoe UI', 8)).pack(anchor=tk.W, pady=(4, 1))
        entry = tk.Entry(parent, font=('Consolas', 9), bg="#1a1a1a", fg="#ffffff",
                        insertbackground="#ffffff", relief=tk.FLAT, show=show or "")
        entry.insert(0, default)
        entry.pack(fill=tk.X, pady=(0, 3), ipady=3)
        return entry

    def _slider(self, parent, label, from_, to_, default, res=None):
        tk.Label(parent, text=label, fg="#666666", bg="#111111",
                font=('Segoe UI', 8)).pack(anchor=tk.W, pady=(4, 1))
        slider = tk.Scale(parent, from_=from_, to_=to_, orient=tk.HORIZONTAL, resolution=res,
                         bg="#111111", fg="#888888", troughcolor="#1a1a1a",
                         highlightthickness=0, activebackground="#ffffff",
                         sliderrelief=tk.FLAT, bd=0, showvalue=True,
                         font=('Consolas', 7), length=180)
        slider.set(default)
        slider.pack(fill=tk.X, pady=(0, 3))
        return slider

    # ROI Drawing
    def roi_mouse_down(self, event):
        if not self.monitor.is_running:
            return
        self.roi_drawing = True
        self.roi_start = (event.x, event.y)
        if self.roi_rect:
            self.canvas.delete(self.roi_rect)
        self.roi_rect = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#00ff88", width=2, dash=(4, 4))

    def roi_mouse_drag(self, event):
        if self.roi_drawing and self.roi_rect:
            self.canvas.coords(self.roi_rect, self.roi_start[0], self.roi_start[1], event.x, event.y)

    def roi_mouse_up(self, event):
        if not self.roi_drawing:
            return
        self.roi_drawing = False
        
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w < 10 or canvas_h < 10:
            return
        
        x1 = min(self.roi_start[0], event.x) / canvas_w
        y1 = min(self.roi_start[1], event.y) / canvas_h
        x2 = max(self.roi_start[0], event.x) / canvas_w
        y2 = max(self.roi_start[1], event.y) / canvas_h
        
        x1 = max(0, min(1, x1))
        y1 = max(0, min(1, y1))
        x2 = max(0, min(1, x2))
        y2 = max(0, min(1, y2))
        
        if (x2 - x1) > 0.05 and (y2 - y1) > 0.05:
            self.config.set_roi_from_normalized(x1, y1, x2, y2)
            self.roi_preset_var.set("custom")
            self.monitor.reset_baseline()
            self._sync_roi_entries()
            self._update_roi_label()
            self._update_roi_pixel_label()

    def apply_roi_preset(self, preset):
        if preset == "custom":
            return
        left, right, top, bottom = self.config.get_roi_preset(preset)
        self.config.set_roi_from_edges(left, right, top, bottom)
        self.monitor.reset_baseline()
        self._sync_roi_entries()
        self._update_roi_label()
        self._update_roi_pixel_label()

    def apply_roi_manual(self):
        try:
            left = float(self.roi_left_var.get())
            right = float(self.roi_right_var.get())
            top = float(self.roi_top_var.get())
            bottom = float(self.roi_bottom_var.get())
        except ValueError:
            return
        self.config.set_roi_from_edges(left, right, top, bottom)
        self.roi_preset_var.set("custom")
        self.monitor.reset_baseline()
        self._update_roi_label()
        self._update_roi_pixel_label()

    def reset_roi(self):
        self.config.set_roi_from_edges(25, 90, 20, 85)
        self.roi_preset_var.set("custom")
        self.monitor.reset_baseline()
        self._sync_roi_entries()
        self._update_roi_label()
        self._update_roi_pixel_label()

    def _sync_roi_entries(self):
        self.roi_left_var.set(str(int(self.config.roi_left)))
        self.roi_right_var.set(str(int(self.config.roi_right)))
        self.roi_top_var.set(str(int(self.config.roi_top)))
        self.roi_bottom_var.set(str(int(self.config.roi_bottom)))

    def _update_roi_label(self):
        self.roi_lbl.config(
            text=f"ROI: L{self.config.roi_left:.0f}% R{self.config.roi_right:.0f}% T{self.config.roi_top:.0f}% B{self.config.roi_bottom:.0f}%")

    def _update_roi_pixel_label(self):
        canvas_w = 1920
        canvas_h = 1080
        try:
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            if cw > 10 and ch > 10:
                canvas_w, canvas_h = cw, ch
        except AttributeError:
            pass
        lx = int(canvas_w * self.config.roi_x1)
        rx = int(canvas_w * self.config.roi_x2)
        ty = int(canvas_h * self.config.roi_y1)
        by = int(canvas_h * self.config.roi_y2)
        w = rx - lx
        h = by - ty
        self.roi_pixel_lbl.config(text=f"{w}x{h}px @ ({lx},{ty})")

    def on_status_update(self, status_type, value):
        self.window.after(0, lambda: self._update_status(status_type, value))
    
    def _update_status(self, status_type, value):
        if status_type == "status":
            colors = {"CONNECTING": "#ffcc00", "LIVE": "#00ff88", "STOPPED": "#444444", "ERROR": "#ff3333"}
            self.status_lbl.config(text=value, fg=colors.get(value, "#444444"))
        elif status_type == "fps":
            self.fps_lbl.config(text=f"FPS: {value:.1f}")
        elif status_type == "detections":
            self.detection_lbl.config(text=f"Detections: {value}")
        elif status_type == "latency":
            self.latency_lbl.config(text=f"Latency: {value:.0f}ms")
        elif status_type == "processed":
            self.processed_lbl.config(text=f"Processed: {value}")

    def start_monitoring(self):
        self.config.camera_ip = self.ip_entry.get().strip()
        self.config.camera_port = self.port_entry.get().strip()
        self.config.camera_user = self.user_entry.get().strip()
        self.config.camera_pass = self.pass_entry.get().strip()
        self.config.target_fps = self.fps_slider.get()
        self.config.process_width = self.width_slider.get()
        self.config.sensitivity = self.sens_slider.get()
        self.config.cooldown_seconds = self.cooldown_slider.get()
        self.config.blur_kernel = self.blur_slider.get()
        if self.config.blur_kernel % 2 == 0:
            self.config.blur_kernel += 1
        self.config.threshold = self.threshold_slider.get()
        self.config.baseline_reset_seconds = self.adapt_slider.get()
        self.config.alert_max_seconds = self.maxbeep_slider.get()
        self.config.skip_frames = self.skip_slider.get()
        self.config.buffer_size = self.buffer_slider.get()
        self.config.resize_interp = self.resize_var.get()
        self.config.box_color = self.box_color_var.get()
        self.config.box_thickness = self.box_thickness_slider.get()
        self.config.show_roi_outline = self.show_roi_var.get()
        self.config.sound_alert = self.sound_alert_var.get()
        
        if not self.config.camera_ip or not self.config.camera_port:
            self._update_status("status", "ERROR")
            return
        
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.monitor.start(self.canvas)

    def stop_monitoring(self):
        self.monitor.stop()
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.canvas.delete("all")
        self._update_status("status", "OFFLINE")
        self.fps_lbl.config(text="FPS: --")
        self.latency_lbl.config(text="Latency: --ms")
        self.processed_lbl.config(text="Processed: 0")

    def on_close(self):
        self.monitor.stop()
        self.window.destroy()
