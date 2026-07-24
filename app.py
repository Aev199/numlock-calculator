"""
NumLock Calculator — Python/WebView Portable Launcher
=====================================================
Заменяет Electron: окно на pywebview + глобальный хук NumLock.

Сборка: pyinstaller --onefile --windowed --add-data "renderer;renderer" app.py
"""

import os
import sys
import json
import threading
import webview

# ── Пути (учитываем PyInstaller bundle) ──────────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    DATA_FILE = os.path.join(os.path.dirname(sys.executable), 'numlock-calc-data.json')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_FILE = os.path.join(BASE_DIR, 'numlock-calc-data.json')

RENDERER_DIR = os.path.join(BASE_DIR, 'renderer')


# ── Persistent storage (замена localStorage) ─────────────────────────
class Storage:
    """Класс-мост между JS (localStorage) и Python (JSON-файл).
    Методы getItem/setItem/removeItem вызываются из JS через
    window.pywebview.api.getItem(...) и т.д.
    """

    def __init__(self, filepath):
        self._filepath = filepath
        self._data = {}
        self._load()

    def _load(self):
        if os.path.exists(self._filepath):
            try:
                with open(self._filepath, 'r', encoding='utf-8') as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self):
        try:
            with open(self._filepath, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False)
        except Exception:
            pass

    def getItem(self, key):
        return self._data.get(key)

    def setItem(self, key, value):
        self._data[key] = value
        self._save()

    def removeItem(self, key):
        self._data.pop(key, None)
        self._save()


# ── Сборка HTML (инлайн CSS + JS + localStorage-полифилл) ────────────
def build_html():
    with open(os.path.join(RENDERER_DIR, 'index.html'), 'r', encoding='utf-8') as f:
        html = f.read()
    with open(os.path.join(RENDERER_DIR, 'style.css'), 'r', encoding='utf-8') as f:
        css = f.read()
    with open(os.path.join(RENDERER_DIR, 'script.js'), 'r', encoding='utf-8') as f:
        js = f.read()

    # Инлайн CSS
    html = html.replace(
        '<link rel="stylesheet" href="style.css">',
        f'<style>\n{css}\n</style>'
    )
    # Инлайн JS
    html = html.replace(
        '<script src="script.js"></script>',
        f'<script>\n{js}\n</script>'
    )

    # Полифилл: подменяем localStorage на Python-мост (до загрузки body)
    polyfill = '''<script>
(function() {
    var _cache = {};
    window._lsReady = false;
    try {
        _cache.nlcalc_history = window.pywebview.api.getItem('nlcalc_history');
        _cache.nlcalc_theme = window.pywebview.api.getItem('nlcalc_theme');
        window._lsReady = true;
    } catch(e) {}

    var fakeLS = {
        getItem: function(k) { return _cache[k] || null; },
        setItem: function(k, v) {
            _cache[k] = v;
            try { window.pywebview.api.setItem(k, v); } catch(e) {}
        },
        removeItem: function(k) {
            delete _cache[k];
            try { window.pywebview.api.removeItem(k); } catch(e) {}
        },
        clear: function() { _cache = {}; }
    };

    Object.defineProperty(window, 'localStorage', {
        value: fakeLS, writable: false, configurable: false
    });
})();
</script>
'''
    html = html.replace('<body', polyfill + '\n<body', 1)

    return html


# ── Глобальное состояние ─────────────────────────────────────────────
_win = None          # pywebview window
_visible = True      # отслеживаем видимость
_quitting = False    # флаг выхода
_storage = Storage(DATA_FILE)


def toggle_window():
    """Показать/скрыть окно (вызывается из потока-хука keyboard)."""
    global _win, _visible
    if _win is None:
        return
    try:
        if _visible:
            _win.hide()
            _visible = False
        else:
            _win.show()
            _win.restore()
            _visible = True
    except Exception:
        pass


def on_closing():
    """Закрытие окна: прячем вместо выхода."""
    global _visible, _quitting
    if not _quitting:
        _visible = False
        return False  # блокируем закрытие
    return True


def on_shown():
    global _visible
    _visible = True


def quit_app():
    """Полный выход из приложения."""
    global _quitting, _win
    _quitting = True
    if _win:
        try:
            _win.destroy()
        except Exception:
            pass
    os._exit(0)


# ── Точка входа ──────────────────────────────────────────────────────
def main():
    global _win

    html = build_html()

    _win = webview.create_window(
        title='NumLock Calc',
        html=html,
        width=480,
        height=680,
        min_size=(380, 550),
        js_api=_storage,
        resizable=True,
        easy_drag=False,
        confirm_close=False,
    )

    # События окна
    _win.events.closing += on_closing
    _win.events.shown += on_shown

    # Глобальный хук NumLock
    try:
        import keyboard
        keyboard.add_hotkey('num lock', toggle_window, suppress=False)
        # Ctrl+Shift+Q для полного выхода
        keyboard.add_hotkey('ctrl+shift+q', quit_app, suppress=False)
        print('[NumLock] Hotkeys registered: NumLock=toggle, Ctrl+Shift+Q=quit')
    except Exception as e:
        print(f'[NumLock] Hotkey error: {e}')

    # Старт
    webview.start(private_mode=True)


if __name__ == '__main__':
    main()

