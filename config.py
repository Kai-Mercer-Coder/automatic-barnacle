class Config:
    def __init__(self):
        # Camera
        self.camera_ip = "192.168.31.203"
        self.camera_port = "554"
        self.camera_user = "admin"
        self.camera_pass = "admin@123"
        
        # ROI (normalized 0.0 - 1.0) - percentages of frame
        self.roi_left = 25    # % from left edge
        self.roi_right = 90   # % from left edge (so right edge is at 90%)
        self.roi_top = 20     # % from top edge
        self.roi_bottom = 85  # % from top edge
        self.roi_mode = "custom"
        
        # Detection
        self.sensitivity = 500
        self.cooldown_seconds = 2.0
        self.blur_kernel = 7
        self.threshold = 15
        
        # Detection box drawing
        self.box_color = "red"       # red, green, yellow, cyan
        self.box_thickness = 3
        self.show_roi_outline = True
        
        # Performance
        self.target_fps = 30
        self.process_width = 480
        self.buffer_size = 1
        self.skip_frames = 3
        self.resize_interp = "nearest"
        
        # Stealth alert
        self.stealth_enabled = True
        self.stealth_title = "Untitled"
        self.stealth_beep = True
        self.stealth_screenshot = True
        self.screenshot_dir = "screenshots"
        
    @property
    def roi_x1(self):
        return self.roi_left / 100.0
    
    @property
    def roi_x2(self):
        return self.roi_right / 100.0
    
    @property
    def roi_y1(self):
        return self.roi_top / 100.0
    
    @property
    def roi_y2(self):
        return self.roi_bottom / 100.0
    
    def set_roi_from_edges(self, left, right, top, bottom):
        self.roi_left = max(0, min(99, left))
        self.roi_right = max(self.roi_left + 1, min(100, right))
        self.roi_top = max(0, min(99, top))
        self.roi_bottom = max(self.roi_top + 1, min(100, bottom))
        self.roi_mode = "custom"
    
    def set_roi_from_normalized(self, x1, y1, x2, y2):
        self.roi_left = round(x1 * 100, 1)
        self.roi_right = round(x2 * 100, 1)
        self.roi_top = round(y1 * 100, 1)
        self.roi_bottom = round(y2 * 100, 1)
        self.roi_mode = "custom"

    def get_roi_preset(self, preset):
        presets = {
            "full":       (0, 100, 0, 100),
            "center":     (20, 80, 20, 80),
            "top-half":   (0, 100, 0, 50),
            "bottom-half": (0, 100, 50, 100),
            "left-half":  (0, 50, 0, 100),
            "right-half": (50, 100, 0, 100),
            "top-left":   (0, 50, 0, 50),
            "top-right":  (50, 100, 0, 50),
            "bottom-left": (0, 50, 50, 100),
            "bottom-right": (50, 100, 50, 100),
        }
        return presets.get(preset, (25, 90, 20, 85))
