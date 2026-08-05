from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    source = target.read_text(encoding="utf-8")
    if new in source:
        return
    if old not in source:
        raise RuntimeError(f"Expected text not found in {path}: {old[:120]!r}")
    target.write_text(source.replace(old, new, 1), encoding="utf-8")


replace_once(
    "app_numlock_compat.py",
    "NUMLOCK_INJECTION_TAG = 0x4E4C4341\n",
    """NUMLOCK_INJECTION_TAG = 0x4E4C4341

# The navigation cluster and the numeric keypad share logical Windows key
# names when NumLock is off.  keyboard.add_hotkey therefore cannot distinguish
# dedicated PageDown from NumPad 3, Home from NumPad 7, and so on.
KEYPAD_NAVIGATION_ALIASES = frozenset(
    {
        "insert",
        "delete",
        "home",
        "end",
        "page up",
        "page down",
        "left",
        "right",
        "up",
        "down",
    }
)
MODIFIER_EVENT_NAMES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "left ctrl": "ctrl",
    "right ctrl": "ctrl",
    "left control": "ctrl",
    "right control": "ctrl",
    "alt": "alt",
    "left alt": "alt",
    "right alt": "alt",
    "shift": "shift",
    "left shift": "shift",
    "right shift": "shift",
    "windows": "windows",
    "win": "windows",
    "left windows": "windows",
    "right windows": "windows",
    "left win": "windows",
    "right win": "windows",
}
""",
)

replace_once(
    "app_numlock_compat.py",
    """    def restore_numlock_after_toggle(_delay: float = 0.0) -> None:
        \"\"\"Compatibility entry point retained for existing tests/callers.\"\"\"

        start_blink_cycle(True)
""",
    """    def canonical_hotkey_event_name(event: Any) -> str:
        \"\"\"Normalize a keyboard event without losing its keypad identity.\"\"\"

        name = \" \".join(
            str(getattr(event, \"name\", \"\") or \"\")
            .strip()
            .lower()
            .replace(\"_\", \" \")
            .split()
        )
        aliases = {
            \"pageup\": \"page up\",
            \"pagedown\": \"page down\",
            \"arrow left\": \"left\",
            \"arrow right\": \"right\",
            \"arrow up\": \"up\",
            \"arrow down\": \"down\",
        }
        return aliases.get(name, name)

    def register_physical_navigation_hotkey(
        keyboard_module: Any,
        hotkey: str,
    ) -> Any:
        \"\"\"Register a navigation hotkey while excluding keypad aliases.\"\"\"

        parts = tuple(part.strip() for part in hotkey.split(\"+\") if part.strip())
        required_modifiers = frozenset(parts[:-1])
        main_key = parts[-1]
        pressed_modifiers: set[str] = set()
        active = False

        def handle_event(event: Any) -> bool:
            nonlocal active

            event_type = str(getattr(event, \"event_type\", \"\") or \"\").lower()
            name = canonical_hotkey_event_name(event)
            modifier = MODIFIER_EVENT_NAMES.get(name)
            if modifier:
                if event_type == \"down\":
                    pressed_modifiers.add(modifier)
                elif event_type == \"up\":
                    pressed_modifiers.discard(modifier)
                return True

            if name != main_key:
                return True

            # This is the essential distinction: NumPad 3 can be reported as
            # PageDown, but keyboard marks it as a keypad event.
            if bool(getattr(event, \"is_keypad\", False)):
                return True

            if event_type == \"down\":
                if pressed_modifiers == required_modifiers:
                    active = True
                    return False
                return True

            if event_type == \"up\" and active:
                active = False
                on_global_hotkey()
                return False
            return True

        return keyboard_module.hook(handle_event, suppress=True)

    def restore_numlock_after_toggle(_delay: float = 0.0) -> None:
        \"\"\"Compatibility entry point retained for existing tests/callers.\"\"\"

        start_blink_cycle(True)
""",
)

replace_once(
    "app_numlock_compat.py",
    """        else:
            try:
                app._global_hotkey_handle = keyboard.add_hotkey(
                    validation.hotkey,
                    on_global_hotkey,
                    suppress=True,
                    trigger_on_release=True,
                )
                registered = True
            except Exception as error:
                app._hotkey_registration_error = (
                    f\"Не удалось зарегистрировать {validation.display}: {error}\"
                )
""",
    """        else:
            try:
                main_key = validation.hotkey.rsplit(\"+\", 1)[-1]
                if os.name == \"nt\" and main_key in KEYPAD_NAVIGATION_ALIASES:
                    app._global_hotkey_handle = register_physical_navigation_hotkey(
                        keyboard,
                        validation.hotkey,
                    )
                else:
                    app._global_hotkey_handle = keyboard.add_hotkey(
                        validation.hotkey,
                        on_global_hotkey,
                        suppress=True,
                        trigger_on_release=True,
                    )
                registered = True
            except Exception as error:
                app._hotkey_registration_error = (
                    f\"Не удалось зарегистрировать {validation.display}: {error}\"
                )
""",
)

replace_once(
    "app_numlock_compat.py",
    """    app.register_numlock_hook = register_native_hook
    app.stop_numlock_hook = stop_native_hook
    app.register_hotkeys = register_hotkeys
""",
    """    app.register_numlock_hook = register_native_hook
    app.stop_numlock_hook = stop_native_hook
    app.canonical_hotkey_event_name = canonical_hotkey_event_name
    app.register_physical_navigation_hotkey = register_physical_navigation_hotkey
    app.register_hotkeys = register_hotkeys
""",
)

replace_once(
    "renderer/app-shell-v2.hotkey.js",
    """  function browserHotkeyKey(event) {
""",
    """  const KEYPAD_NAVIGATION_ALIASES = new Set([
    'Insert', 'Delete', 'Home', 'End', 'PageUp', 'PageDown',
    'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
  ]);

  function isKeypadNavigationAlias(event) {
    return Number(event.location) === 3 && KEYPAD_NAVIGATION_ALIASES.has(String(event.key || ''));
  }

  function browserHotkeyKey(event) {
""",
)

replace_once(
    "renderer/app-shell-v2.hotkey.js",
    """      const next = hotkeyFromEvent(event);
""",
    """      if (isKeypadNavigationAlias(event)) {
        setStatus('Клавиша цифрового блока не может заменять отдельную навигационную клавишу', 'error');
        return;
      }
      const next = hotkeyFromEvent(event);
""",
)

replace_once(
    "tests/test_hotkey.py",
    """    def test_api_persists_only_after_successful_registration(self):
""",
    """    def test_navigation_hotkey_ignores_keypad_alias(self):
        calls = []
        hooks = []
        toggles = []

        class Event:
            def __init__(self, event_type, name, is_keypad):
                self.event_type = event_type
                self.name = name
                self.is_keypad = is_keypad

        class ImmediateThread:
            def __init__(self, target, args=(), kwargs=None, **_options):
                self.target = target
                self.args = args
                self.kwargs = kwargs or {}

            def start(self):
                self.target(*self.args, **self.kwargs)

        class FakeKeyboard:
            @staticmethod
            def hook(callback, suppress=False):
                hooks.append((callback, suppress))
                return callback

            @staticmethod
            def add_hotkey(key, callback, **kwargs):
                calls.append(('hotkey', key, callback, kwargs))
                return f'handle:{key}'

            @staticmethod
            def unhook_all():
                calls.append(('unhook',))

        app._global_hotkey = 'page down'
        app._quitting = False
        with (
            patch.object(app_numlock_compat.os, 'name', 'nt'),
            patch.object(app_numlock_compat.threading, 'Thread', ImmediateThread),
            patch.object(app, 'toggle_window', lambda: toggles.append('toggle')),
            patch.dict(sys.modules, {'keyboard': FakeKeyboard}),
        ):
            app.register_hotkeys()
            try:
                self.assertTrue(app._hotkey_registration_ok)
                self.assertEqual(len(hooks), 1)
                handler, suppress = hooks[0]
                self.assertTrue(suppress)

                self.assertTrue(handler(Event('down', 'page down', True)))
                self.assertTrue(handler(Event('up', 'page down', True)))
                self.assertEqual(toggles, [])

                self.assertFalse(handler(Event('down', 'page down', False)))
                self.assertFalse(handler(Event('up', 'page down', False)))
                self.assertEqual(toggles, ['toggle'])
            finally:
                app.unregister_hotkeys()

    def test_api_persists_only_after_successful_registration(self):
""",
)

replace_once(
    "tests/test_hotkey.py",
    """        self.assertIn('set_global_hotkey', html)
""",
    """        self.assertIn('set_global_hotkey', html)
        self.assertIn('KEYPAD_NAVIGATION_ALIASES', html)
        self.assertIn('Number(event.location) === 3', html)
""",
)

replace_once(
    "CHANGELOG.md",
    """- хвостовые нули после округления больше не показываются;
""",
    """- хвостовые нули после округления больше не показываются;
- собственные навигационные хоткеи различают отдельные клавиши и их NumPad-двойники;
""",
)

print("Applied physical navigation hotkey fix")
