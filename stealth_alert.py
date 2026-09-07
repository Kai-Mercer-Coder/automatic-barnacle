import ctypes
import ctypes.wintypes
import threading
import time

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Set proper 64-bit signatures
user32.DefWindowProcW.restype = ctypes.c_longlong
user32.DefWindowProcW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT,
                                  ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
user32.ShowWindow.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
user32.SendMessageW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.UINT,
                                ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]
user32.SetWindowTextW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPCWSTR]
user32.GetWindowLongW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.argtypes = [ctypes.wintypes.HWND, ctypes.c_int, ctypes.c_long]
user32.SetWindowLongW.restype = ctypes.c_long
user32.LoadIconW.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.LPCWSTR]
user32.LoadIconW.restype = ctypes.wintypes.HANDLE
user32.LoadCursorW.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.LPCWSTR]
user32.LoadCursorW.restype = ctypes.wintypes.HANDLE


def load_standard_icon():
    """Load IDI_APPLICATION (32512) by casting the resource ID"""
    return user32.LoadIconW(None, ctypes.wintypes.LPCWSTR(32512))


def load_standard_cursor():
    """Load IDC_ARROW (32512) by casting the resource ID"""
    return user32.LoadCursorW(None, ctypes.wintypes.LPCWSTR(32512))

GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
WS_OVERLAPPEDWINDOW = 0x00CF0000
SW_SHOW = 5
SW_HIDE = 0
SW_SHOWNORMAL = 1
WM_CLOSE = 0x0010
WM_SETICON = 0x0080
IDI_APPLICATION = 32512


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("style", ctypes.c_uint),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.wintypes.HINSTANCE),
        ("hIcon", ctypes.wintypes.HANDLE),
        ("hCursor", ctypes.wintypes.HANDLE),
        ("hbrBackground", ctypes.wintypes.HANDLE),
        ("lpszMenuName", ctypes.wintypes.LPCWSTR),
        ("lpszClassName", ctypes.wintypes.LPCWSTR),
        ("hIconSm", ctypes.wintypes.HANDLE),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.wintypes.HWND),
        ("message", ctypes.wintypes.UINT),
        ("wParam", ctypes.wintypes.WPARAM),
        ("lParam", ctypes.wintypes.LPARAM),
        ("time", ctypes.wintypes.DWORD),
        ("pt", ctypes.wintypes.POINT),
    ]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.wintypes.HWND,
                               ctypes.wintypes.UINT, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)


class StealthAlert:
    def __init__(self, title="Untitled"):
        self.title_text = title
        self.visible = False
        self._hwnd = None
        self._thread = None
        self._running = False
        self._wndproc = None
        self._class_atom = None
        print("[STEALTH] Initialized")

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == WM_CLOSE:
            user32.DestroyWindow(hwnd)
            return 0
        if msg == 0x0002:  # WM_DESTROY
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _create_win32_window(self):
        print("[STEALTH] Creating Win32 window in thread...")

        self._wndproc = WNDPROC(self._wnd_proc)

        wc = WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
        wc.lpfnWndProc = ctypes.cast(self._wndproc, ctypes.c_void_p).value
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "StealthMonitorAlert"
        wc.hbrBackground = ctypes.windll.user32.GetSysColorBrush(15)  # COLOR_BTNFACE
        wc.hCursor = load_standard_cursor()
        wc.hIcon = load_standard_icon()
        wc.hIconSm = load_standard_icon()

        self._class_atom = user32.RegisterClassExW(ctypes.byref(wc))
        if not self._class_atom:
            err = kernel32.GetLastError()
            print(f"[STEALTH] RegisterClassExW failed: {err}")
            return

        print(f"[STEALTH] Class registered, atom={self._class_atom}")

        hwnd = user32.CreateWindowExW(
            0,
            "StealthMonitorAlert",
            self.title_text,
            WS_OVERLAPPEDWINDOW,
            400, 400, 280, 80,
            None, None, wc.hInstance, None
        )

        if not hwnd:
            err = kernel32.GetLastError()
            print(f"[STEALTH] CreateWindowExW failed: {err}")
            return

        self._hwnd = hwnd
        print(f"[STEALTH] HWND: {hwnd:#x}")

        # Set icon
        icon = load_standard_icon()
        user32.SendMessageW(hwnd, WM_SETICON, 0, icon)
        user32.SendMessageW(hwnd, WM_SETICON, 1, icon)
        print("[STEALTH] Icons set")

        # Force taskbar entry
        ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        new_ex = (ex_style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_ex)
        print(f"[STEALTH] ExStyle: {ex_style:#x} -> {new_ex:#x}")

        # Show and enter message loop
        user32.ShowWindow(hwnd, SW_SHOWNORMAL)
        user32.UpdateWindow(hwnd)
        print("[STEALTH] Window created, entering message loop")

        msg = MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

        print("[STEALTH] Message loop exited")
        self._hwnd = None

    def create(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._create_win32_window, daemon=True)
        self._thread.start()
        for _ in range(50):
            if self._hwnd is not None:
                time.sleep(0.05)
                print("[STEALTH] Window ready")
                return
            time.sleep(0.05)
        print("[STEALTH] WARNING: Window creation timed out")

    def show(self):
        if not self._hwnd:
            print("[STEALTH] No HWND, cannot show")
            return
        print(f"[STEALTH] show() hwnd={self._hwnd:#x}")
        user32.ShowWindow(self._hwnd, SW_SHOWNORMAL)
        user32.SetForegroundWindow(self._hwnd)
        user32.UpdateWindow(self._hwnd)
        self.visible = True

    def hide(self):
        if not self._hwnd:
            return
        print(f"[STEALTH] hide() hwnd={self._hwnd:#x}")
        user32.ShowWindow(self._hwnd, SW_HIDE)
        self.visible = False

    def show_timed(self, duration_sec):
        print(f"[STEALTH] show_timed({duration_sec}s)")
        self.show()
        threading.Timer(duration_sec, self.hide).start()

    def update_title(self, title):
        self.title_text = title
        if self._hwnd:
            user32.SetWindowTextW(self._hwnd, title)

    def cleanup(self):
        print("[STEALTH] cleanup()")
        if self._hwnd:
            user32.SendMessageW(self._hwnd, WM_CLOSE, 0, 0)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._hwnd = None
        self.visible = False
        self._running = False
