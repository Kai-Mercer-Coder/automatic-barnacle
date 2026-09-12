import itertools


class Camera:
    _id_gen = itertools.count(1)

    def __init__(self, name="Cam 1", ip="192.168.31.203", port="554",
                 user="admin", passwd="admin@123", enabled=True):
        self.uid = next(Camera._id_gen)
        self.name = name
        self.ip = ip
        self.port = port
        self.user = user
        self.passwd = passwd
        self.enabled = enabled


class Config:
    def __init__(self):
        self.cameras = [Camera()]

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
        self.sound_alert = True
        self.baseline_reset_seconds = 10   # Adapt baseline after this many quiet seconds
        self.alert_max_seconds = 10        # Cap continuous beeping, then re-adapt scene

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

        # Grid layout
        self.grid_cols = 2

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

    def add_camera(self, camera=None):
        cam = camera or Camera()
        self.cameras.append(cam)
        return cam

    def remove_camera(self, uid):
        self.cameras = [c for c in self.cameras if c.uid != uid]

    def get_camera(self, uid):
        for c in self.cameras:
            if c.uid == uid:
                return c
        return None

    def get_enabled_cameras(self):
        return [c for c in self.cameras if c.enabled]