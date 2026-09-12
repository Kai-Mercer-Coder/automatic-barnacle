import math
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from config import Config, Camera
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
        self.monitors = {}
        self.is_monitoring = False
        self.cam_status = {}
        self._stats_cache = {}

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

        # RIGHT PANEL - Video grid
        video_panel = tk.Frame(main_frame, bg="#0a0a0a")
        video_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.grid_wrapper = tk.Frame(video_panel, bg="#0a0a0a")
        self.grid_wrapper.pack(fill=tk.BOTH, expand=True)
        self.tiles = {}
        self.tile_status = {}

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

    def _build_controls(self, p):
        # -- CAMERAS --
        self._section(p, "CAMERAS")

        top_row = tk.Frame(p, bg="#111111")
        top_row.pack(fill=tk.X, pady=(0, 4))

        self.add_cam_btn = RoundedButton(top_row, text="+ Add Camera", command=self.add_camera_dialog,
                                          bg="#00b4d8", fg="#ffffff", active_bg="#0d94bb",
                                          font=('Segoe UI', 8, 'bold'), radius=10, height=26)
        self.add_cam_btn.pack(side=tk.LEFT)

        tk.Label(top_row, text="Grid:", fg="#666666", bg="#111111",
                 font=('Segoe UI', 8)).pack(side=tk.LEFT, padx=(12, 3))
        self.grid_cols_var = tk.StringVar(value=str(self.config.grid_cols))
        grid_menu = tk.OptionMenu(top_row, self.grid_cols_var, "1", "2", "3", "4",
                                  command=self._on_grid_cols_change)
        grid_menu.config(bg="#1a1a1a", fg="#ffffff", activebackground="#222222",
                         activeforeground="#ffffff", highlightthickness=0,
                         relief=tk.FLAT, font=('Segoe UI', 9))
        grid_menu["menu"].config(bg="#1a1a1a", fg="#ffffff", activebackground="#333333")
        grid_menu.pack(side=tk.LEFT)

        self.cam_list_frame = tk.Frame(p, bg="#111111")
        self.cam_list_frame.pack(fill=tk.X)
        self._rebuild_camera_list()

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

        self.sound_alert_var = tk.BooleanVar(value=self.config.sound_alert)
        tk.Checkbutton(p, text="Enable beep on detection", variable=self.sound_alert_var,
                      bg="#111111", fg="#666666", selectcolor="#1a1a1a",
                      activebackground="#111111", activeforeground="#ffffff",
                      font=('Segoe UI', 8), highlightthickness=0).pack(anchor=tk.W, pady=(3, 2))

        # -- BUTTONS --
        tk.Frame(p, height=1, bg="#222222").pack(fill=tk.X, pady=10)

        self.start_btn = RoundedButton(p, text="START ALL", command=self.start_monitoring,
                                      bg="#00ff88", fg="#000000", active_bg="#00cc66",
                                      font=('Segoe UI', 10, 'bold'), radius=16, height=44)
        self.start_btn.pack(fill=tk.X, pady=(0, 5))

        self.stop_btn = RoundedButton(p, text="STOP ALL", command=self.stop_monitoring,
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

    # ---------------------------------------------------------------- cameras --
    def _rebuild_camera_list(self):
        for w in self.cam_list_frame.winfo_children():
            w.destroy()

        if not self.config.cameras:
            tk.Label(self.cam_list_frame, text="No cameras yet. Click 'Add Camera'.",
                     fg="#555555", bg="#111111", font=('Segoe UI', 8)).pack(anchor=tk.W, pady=4)
            return

        for cam in self.config.cameras:
            self._build_camera_row(cam)

    def _build_camera_row(self, cam):
        row = tk.Frame(self.cam_list_frame, bg="#1a1a1a")
        row.pack(fill=tk.X, pady=2)

        enabled_var = tk.BooleanVar(value=cam.enabled)
        cb = tk.Checkbutton(row, variable=enabled_var,
                            bg="#1a1a1a", fg="#aaaaaa", selectcolor="#2a2a2a",
                            activebackground="#1a1a1a", activeforeground="#ffffff",
                            highlightthickness=0,
                            command=lambda c=cam, v=enabled_var: self._toggle_camera(c, v))
        cb.pack(side=tk.LEFT, padx=(3, 0))

        info = tk.Frame(row, bg="#1a1a1a")
        info.pack(side=tk.LEFT, fill=tk.X, expand=True, anchor=tk.W, padx=(4, 0))

        tk.Label(info, text=cam.name, fg="#dddddd", bg="#1a1a1a",
                 font=('Segoe UI', 8, 'bold'), anchor=tk.W).pack(fill=tk.X)
        tk.Label(info, text=f"{cam.ip}:{cam.port}", fg="#666666", bg="#1a1a1a",
                 font=('Consolas', 7), anchor=tk.W).pack(fill=tk.X)

        edit_btn = RoundedButton(row, text="Edit", command=lambda c=cam: self.edit_camera_dialog(c),
                                 bg="#2a2a2a", fg="#aaaaaa", active_bg="#333333",
                                 font=('Segoe UI', 8), radius=9, height=24)
        edit_btn.pack(side=tk.LEFT, padx=(4, 0))

        del_btn = RoundedButton(row, text="\u2715", command=lambda c=cam: self._remove_camera(c),
                                bg="#2a2a2a", fg="#ff5555", active_bg="#3a2a2a",
                                font=('Segoe UI', 8, 'bold'), radius=9, height=24)
        del_btn.pack(side=tk.LEFT, padx=(2, 3))

    def _toggle_camera(self, cam, var):
        cam.enabled = bool(var.get())

    def _remove_camera(self, cam):
        self.config.remove_camera(cam.uid)
        if self.is_monitoring and cam.uid in self.monitors:
            self.monitors[cam.uid].stop()
            del self.monitors[cam.uid]
        if cam.uid in self.tiles:
            self.tiles[cam.uid].master.destroy()
            del self.tiles[cam.uid]
        if cam.uid in self.tile_status:
            del self.tile_status[cam.uid]
        if cam.uid in self.cam_status:
            del self.cam_status[cam.uid]
        self._rebuild_camera_list()
        self._update_global_status()

    def add_camera_dialog(self):
        self._camera_dialog(None)

    def edit_camera_dialog(self, cam):
        self._camera_dialog(cam)

    def _camera_dialog(self, cam):
        dialog = tk.Toplevel(self.window)
        dialog.title("Edit Camera" if cam else "Add Camera")
        dialog.configure(bg="#111111")
        dialog.resizable(False, False)
        dialog.transient(self.window)
        dialog.grab_set()

        pre = cam if cam else Camera()
        f = tk.Frame(dialog, bg="#111111", padx=16, pady=14)
        f.pack(fill=tk.BOTH, expand=True)

        f.columnconfigure(1, weight=1)

        self._dlg_values = []
        for label, default, show in [
            ("Name", pre.name, None),
            ("IP", pre.ip, None),
            ("Port", pre.port, None),
            ("User", pre.user, None),
            ("Pass", pre.passwd, "*"),
        ]:
            row = len(self._dlg_values)
            self._dlg_values.append(self._dlg_entry(f, label, default, row=row, show=show))

        enabled_var = tk.BooleanVar(value=pre.enabled)
        tk.Checkbutton(f, text="Enabled", variable=enabled_var,
                       bg="#111111", fg="#888888", selectcolor="#1a1a1a",
                       activebackground="#111111", activeforeground="#ffffff",
                       font=('Segoe UI', 9), highlightthickness=0).grid(row=5, column=0, columnspan=2,
                                                                         sticky=tk.W, pady=(6, 2))

        btns = tk.Frame(f, bg="#111111")
        btns.grid(row=6, column=0, columnspan=2, sticky=tk.EW, pady=(6, 0))
        btns.columnconfigure(0, weight=1)

        cancel_btn = RoundedButton(btns, text="Cancel", command=dialog.destroy,
                                   bg="#2a2a2a", fg="#999999", active_bg="#333333",
                                   font=('Segoe UI', 9), radius=10, height=30)
        cancel_btn.pack(side=tk.RIGHT, padx=(6, 0))

        def save():
            vals = [e.get() for e in self._dlg_values]
            new_cam = Camera() if cam is None else cam
            new_cam.name = vals[0]
            new_cam.ip = vals[1]
            new_cam.port = vals[2]
            new_cam.user = vals[3]
            new_cam.passwd = vals[4]
            new_cam.enabled = enabled_var.get()
            if cam is None:
                self.config.add_camera(new_cam)
            self._rebuild_camera_list()
            dialog.destroy()

        save_btn = RoundedButton(btns, text="Save", command=save,
                                 bg="#00ff88", fg="#000000", active_bg="#00cc66",
                                 font=('Segoe UI', 9, 'bold'), radius=10, height=30)
        save_btn.pack(side=tk.RIGHT)

    def _dlg_entry(self, parent, label, default, row, show=None):
        tk.Label(parent, text=label, fg="#888888", bg="#111111",
                 font=('Segoe UI', 9)).grid(row=row, column=0, sticky=tk.W, pady=3)
        entry = tk.Entry(parent, font=('Consolas', 10), bg="#1a1a1a", fg="#ffffff",
                         insertbackground="#ffffff", relief=tk.FLAT, show=show or "")
        entry.insert(0, default)
        entry.grid(row=row, column=1, sticky=tk.EW, padx=(10, 0), ipady=3)
        return entry

    # --------------------------------------------------------------- sections --
    def _section(self, parent, title):
        row = tk.Frame(parent, bg="#111111")
        row.pack(fill=tk.X, pady=(12, 4))
        tk.Frame(row, bg="#e94560", width=3, height=11).pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(row, text=title, fg="#8a8a8a", bg="#111111",
                font=('Segoe UI', 8, 'bold')).pack(side=tk.LEFT)

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

    # ------------------------------------------------------------------- grid --
    def _build_tiles(self):
        for w in self.grid_wrapper.winfo_children():
            w.destroy()
        self.tiles = {}
        self.tile_status = {}
        self.cam_status = {}

        cams = self.config.get_enabled_cameras()
        cols = self.config.grid_cols
        rows = max(1, math.ceil(len(cams) / cols)) if cams else 1

        for i, cam in enumerate(cams):
            tile = tk.Frame(self.grid_wrapper, bg="#000000")
            tile.grid(row=i // cols, column=i % cols, sticky="nsew", padx=2, pady=2)

            canvas = tk.Canvas(tile, bg="#000000", highlightthickness=0, cursor="crosshair")
            canvas.pack(fill=tk.BOTH, expand=True)
            self._bind_roi_events(canvas)

            status_lbl = tk.Label(tile, text=f"{cam.name}: OFFLINE", bg="#000000", fg="#444444",
                                  font=('Consolas', 8), anchor=tk.W)
            status_lbl.pack(fill=tk.X)

            self.tiles[cam.uid] = canvas
            self.tile_status[cam.uid] = status_lbl
            self._draw_placeholder(canvas, cam.name)

        for c in range(cols):
            self.grid_wrapper.columnconfigure(c, weight=1)
        for r in range(rows):
            self.grid_wrapper.rowconfigure(r, weight=1)

    def _draw_placeholder(self, canvas, name):
        canvas.delete("all")
        canvas.create_text(canvas.winfo_width() // 2, canvas.winfo_height() // 2,
                           text=name, fill="#333333",
                           font=('Segoe UI', int(max(10, canvas.winfo_width() * 0.04)), 'bold'))

    def _bind_roi_events(self, canvas):
        canvas.bind("<ButtonPress-1>", self.roi_mouse_down)
        canvas.bind("<B1-Motion>", self.roi_mouse_drag)
        canvas.bind("<ButtonRelease-1>", self.roi_mouse_up)

    def _on_grid_cols_change(self, value):
        self.config.grid_cols = int(value)
        if self.is_monitoring:
            self.restart_monitoring()

    # ------------------------------------------------------------------- ROI --
    def roi_mouse_down(self, event):
        if not self.is_monitoring:
            return
        self.roi_drawing = True
        self.roi_start = (event.x, event.y)
        c = event.widget
        if self.roi_rect:
            c.delete(self.roi_rect)
        self.roi_rect = c.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#00ff88", width=2, dash=(4, 4))

    def roi_mouse_drag(self, event):
        if self.roi_drawing and self.roi_rect:
            event.widget.coords(self.roi_rect, self.roi_start[0], self.roi_start[1], event.x, event.y)

    def roi_mouse_up(self, event):
        if not self.roi_drawing:
            return
        self.roi_drawing = False
        c = event.widget

        canvas_w = c.winfo_width()
        canvas_h = c.winfo_height()
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
            self._reset_all_baselines()
            self._sync_roi_entries()
            self._update_roi_label()
            self._update_roi_pixel_label()

    def apply_roi_preset(self, preset):
        if preset == "custom":
            return
        left, right, top, bottom = self.config.get_roi_preset(preset)
        self.config.set_roi_from_edges(left, right, top, bottom)
        self._reset_all_baselines()
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
        self._reset_all_baselines()
        self._update_roi_label()
        self._update_roi_pixel_label()

    def reset_roi(self):
        self.config.set_roi_from_edges(25, 90, 20, 85)
        self.roi_preset_var.set("custom")
        self._reset_all_baselines()
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
        for canvas in self.tiles.values():
            cw = canvas.winfo_width()
            ch = canvas.winfo_height()
            if cw > 10 and ch > 10:
                canvas_w, canvas_h = cw, ch
                break
        lx = int(canvas_w * self.config.roi_x1)
        rx = int(canvas_w * self.config.roi_x2)
        ty = int(canvas_h * self.config.roi_y1)
        by = int(canvas_h * self.config.roi_y2)
        w = rx - lx
        h = by - ty
        self.roi_pixel_lbl.config(text=f"{w}x{h}px @ ({lx},{ty})")

    def _reset_all_baselines(self):
        for mon in self.monitors.values():
            mon.reset_baseline()

    # ------------------------------------------------------------- callbacks --
    def on_status_update(self, uid, status_type, value):
        self.window.after(0, lambda: self._update_status(uid, status_type, value))

    def _update_status(self, uid, status_type, value):
        if status_type == "status":
            if uid in self.tile_status:
                colors = {"CONNECTING": "#ffcc00", "LIVE": "#00ff88", "ERROR": "#ff3333"}
                cam = self.config.get_camera(uid)
                name = cam.name if cam else "Cam"
                self.tile_status[uid].config(
                    text=f"{name}: {value}", fg=colors.get(value, "#444444"))
            self.cam_status[uid] = value
            self._update_global_status()
            return

        if uid is None:
            return
        self._stats_cache.setdefault(status_type, {})[uid] = value

        if status_type == "fps":
            vals = list(self._stats_cache["fps"].values())
            self.fps_lbl.config(text=f"FPS: {max(vals):.1f}")
        elif status_type == "latency":
            vals = list(self._stats_cache["latency"].values())
            self.latency_lbl.config(text=f"Latency: {sum(vals) / len(vals):.0f}ms")
        elif status_type == "detections":
            vals = list(self._stats_cache["detections"].values())
            self.detection_lbl.config(text=f"Detections: {sum(vals)}")
        elif status_type == "processed":
            vals = list(self._stats_cache["processed"].values())
            self.processed_lbl.config(text=f"Processed: {sum(vals)}")

    def _update_global_status(self):
        if not self.is_monitoring:
            self.status_lbl.config(text="OFFLINE", fg="#444444")
            return
        statuses = list(self.cam_status.values())
        if not statuses:
            self.status_lbl.config(text="IDLE", fg="#888888")
            return
        live = statuses.count("LIVE")
        connecting = statuses.count("CONNECTING")
        if live:
            self.status_lbl.config(text=f"LIVE ({live})", fg="#00ff88")
        elif connecting:
            self.status_lbl.config(text="CONNECTING", fg="#ffcc00")
        else:
            self.status_lbl.config(text="ERROR", fg="#ff3333")

    # ----------------------------------------------------------------- start --
    def _read_settings(self):
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

    def start_monitoring(self):
        self._read_settings()

        cams = self.config.get_enabled_cameras()
        if not cams:
            self._update_status(None, "status", "ERROR")
            self.status_lbl.config(text="NO CAMERAS", fg="#ff3333")
            return

        self._build_tiles()
        self.is_monitoring = True
        self._stats_cache = {}
        self.cam_status = {cam.uid: "CONNECTING" for cam in cams}

        self.start_btn.config_button(state=tk.DISABLED)
        self.stop_btn.config_button(state=tk.NORMAL)

        self.monitors = {}
        for cam in cams:
            mon = SecurityMonitor(self.config, cam, self.on_status_update)
            self.monitors[cam.uid] = mon
            mon.start(self.tiles[cam.uid])

    def stop_monitoring(self):
        self.is_monitoring = False
        for mon in self.monitors.values():
            mon.stop()
        self.monitors = {}
        self.cam_status = {}
        if hasattr(self, '_stats_cache'):
            self._stats_cache.clear()

        for w in self.grid_wrapper.winfo_children():
            w.destroy()
        self.tiles = {}
        self.tile_status = {}

        self.start_btn.config_button(state=tk.NORMAL)
        self.stop_btn.config_button(state=tk.DISABLED)
        self.status_lbl.config(text="OFFLINE", fg="#444444")
        self.fps_lbl.config(text="FPS: --")
        self.detection_lbl.config(text="Detections: 0")
        self.latency_lbl.config(text="Latency: --ms")
        self.processed_lbl.config(text="Processed: 0")

    def restart_monitoring(self):
        self.stop_monitoring()
        self.start_monitoring()

    def on_close(self):
        self.stop_monitoring()
        self.window.destroy()