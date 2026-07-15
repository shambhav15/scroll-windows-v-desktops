from pynput import mouse
from pynput.keyboard import Key, Controller
import json
import ctypes
from ctypes import wintypes
import sys
import os
import traceback
import threading
import winreg

# Enable DPI awareness to make sure cursor coordinates and WindowFromPoint are pixel-perfect
try:
  ctypes.windll.shcore.SetProcessDpiAwareness(2) # Per-Monitor DPI Aware V2
except Exception:
  try:
    ctypes.windll.user32.SetProcessDPIAware() # Fallback for older Windows
  except Exception:
    pass

if getattr(sys, 'frozen', False):
  script_dir = os.path.dirname(sys.executable)
else:
  script_dir = os.path.dirname(os.path.abspath(__file__))

log_path = os.path.join(script_dir, 'error_log.txt')

def log_message(msg):
  try:
    with open(log_path, 'a') as f:
      f.write(msg + '\n')
  except Exception:
    pass

def custom_excepthook(args):
  log_message("Thread exception:")
  log_message("".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)))

threading.excepthook = custom_excepthook

class POINT(ctypes.Structure):
  _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

def set_startup(enabled=True):
  key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
  try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE)
    if enabled:
      exe_path = f'"{os.path.abspath(sys.executable)}" --startup'
      winreg.SetValueEx(key, "VirtualDesktopScrollSwitcher", 0, winreg.REG_SZ, exe_path)
    else:
      try:
        winreg.DeleteValue(key, "VirtualDesktopScrollSwitcher")
      except FileNotFoundError:
        pass
    winreg.CloseKey(key)
    return True
  except Exception as e:
    log_message(f"Registry error: {e}")
    return False

def is_startup_enabled():
  key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
  try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
    value, regtype = winreg.QueryValueEx(key, "VirtualDesktopScrollSwitcher")
    winreg.CloseKey(key)
    expected = f'"{os.path.abspath(sys.executable)}" --startup'
    return value == expected
  except FileNotFoundError:
    return False
  except Exception as e:
    log_message(f"Registry check error: {e}")
    return False

try:
  try:
    config_path = os.path.join(script_dir, 'config.json')
    with open(config_path, 'r') as f:
      config = json.load(f)
  except Exception:
    config = {}

  use_taskbar = config.get("useTaskbar", True)

  xMin = config.get("xMin", 0)
  xMax = config.get("xMax", 0)
  yMin = config.get("yMin", 0)
  yMax = config.get("yMax", 0)

  keyboard = Controller()

  # Handle Autostart Dialogs
  is_frozen = getattr(sys, 'frozen', False)
  is_startup_run = "--startup" in sys.argv

  if is_frozen and not is_startup_run:
    if is_startup_enabled():
      # Already enabled. Ask if they want to disable it.
      res = ctypes.windll.user32.MessageBoxW(
        0,
        "Virtual Desktop Scroll Switcher is running in the background!\n\nAutostart on boot is currently ENABLED.\n\nWould you like to DISABLE autostart on Windows boot?",
        "Virtual Desktop Switcher",
        0x04 | 0x40 # MB_YESNO | MB_ICONINFORMATION
      )
      if res == 6: # IDYES
        set_startup(False)
        ctypes.windll.user32.MessageBoxW(
          0,
          "Autostart has been disabled.",
          "Virtual Desktop Switcher",
          0x40 # MB_ICONINFORMATION
        )
    else:
      # Not enabled yet. Ask if they want to enable it.
      res = ctypes.windll.user32.MessageBoxW(
        0,
        "Virtual Desktop Scroll Switcher is now running in the background!\n\nScroll your mouse wheel over the Windows Taskbar to switch desktops.\n\nWould you like this utility to start automatically when your computer boots?",
        "Virtual Desktop Switcher",
        0x04 | 0x20 # MB_YESNO | MB_ICONQUESTION
      )
      if res == 6: # IDYES
        set_startup(True)
        ctypes.windll.user32.MessageBoxW(
          0,
          "Autostart has been enabled! The app will start automatically on boot.",
          "Virtual Desktop Switcher",
          0x40 # MB_ICONINFORMATION
        )
      else:
        # User clicked No. Just notify that it's running manually.
        ctypes.windll.user32.MessageBoxW(
          0,
          "Running manually for this session only.\n\n(It will not start on boot.)",
          "Virtual Desktop Switcher",
          0x40 # MB_ICONINFORMATION
        )

  def is_cursor_over_taskbar():
    pt = POINT()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
      return False
    hwnd = ctypes.windll.user32.WindowFromPoint(pt)
    if not hwnd:
      return False
    root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, 2)
    if not root_hwnd:
      root_hwnd = hwnd
    class_name = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetClassNameW(root_hwnd, class_name, 256)
    return class_name.value in ("Shell_TrayWnd", "SecondaryTrayWnd")

  def on_scroll(x, y, dx, dy):
    should_switch = False
    if use_taskbar:
      should_switch = is_cursor_over_taskbar()
    else:
      should_switch = (x > xMin and x < xMax and y > yMin and y < yMax)

    if should_switch:
      keyboard.press(Key.cmd)
      keyboard.press(Key.ctrl)
      if dy < 0:
        keyboard.press(Key.right)
      else:
        keyboard.press(Key.left)
        
      keyboard.release(Key.cmd)
      keyboard.release(Key.ctrl)
      if dy < 0:
        keyboard.release(Key.right)
      else:
        keyboard.release(Key.left)

    if (config.get('printPosition', False) == True):
      print('Scrolled {0} at {1}'.format(
        'down' if dy < 0 else 'up',
        (x, y)))

  with mouse.Listener(
      on_scroll=on_scroll) as listener:
    listener.join()

except Exception as e:
  log_message("Unhandled exception on startup:")
  log_message(traceback.format_exc())
  sys.exit(1)