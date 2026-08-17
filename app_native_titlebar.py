"""Enable WebView2 native non-client regions for the frameless titlebar."""

from __future__ import annotations

import logging
import os
from typing import Any


logger = logging.getLogger("numcalc.native_titlebar")
_PATCH_MARKER = "_numcalc_non_client_regions_patch"


def enable_non_client_region_support(settings: Any) -> bool:
    """Enable WebView2's native ``app-region`` handling on a settings object."""

    if settings is None:
        return False

    try:
        # pythonnet normally exposes .NET properties directly. Keep the explicit
        # setter fallback because pywebview itself uses both access styles.
        settings.IsNonClientRegionSupportEnabled = True
        return True
    except Exception:
        try:
            setter = getattr(settings, "set_IsNonClientRegionSupportEnabled", None)
            if not callable(setter):
                return False
            setter(True)
            return True
        except Exception:
            return False


def patch_edgechromium(edgechromium: Any) -> bool:
    """Enable native titlebar regions before pywebview's first navigation.

    pywebview registers ``EdgeChrome.on_webview_ready`` as the WebView2
    initialization callback. Its original callback performs the first
    NavigateToString/Source navigation, so wrapping that callback lets NumCalc
    enable non-client regions at exactly the point required by WebView2: after
    CoreWebView2 exists, but before the page is navigated.
    """

    edge_class = getattr(edgechromium, "EdgeChrome", None)
    original = getattr(edge_class, "on_webview_ready", None)
    if edge_class is None or not callable(original):
        return False
    if getattr(original, _PATCH_MARKER, False):
        return True

    def on_webview_ready(self: Any, sender: Any, args: Any) -> Any:
        if bool(getattr(args, "IsSuccess", False)):
            try:
                core = getattr(sender, "CoreWebView2", None)
                settings = getattr(core, "Settings", None)
                if not enable_non_client_region_support(settings):
                    logger.warning(
                        "WebView2 non-client region support is unavailable; "
                        "titlebar dragging will remain disabled"
                    )
            except Exception:
                logger.exception("Failed to enable WebView2 non-client regions")
        return original(self, sender, args)

    setattr(on_webview_ready, _PATCH_MARKER, True)
    setattr(on_webview_ready, "_numcalc_original", original)
    edge_class.on_webview_ready = on_webview_ready
    return True


def install(app: Any) -> None:
    """Install WebView2 native titlebar support before the desktop loop starts."""

    if getattr(app, "_native_titlebar_installed", False):
        return
    app._native_titlebar_installed = True
    app._native_titlebar_mode = "webview2-non-client-regions"

    if os.name != "nt":
        return

    try:
        from webview.platforms import edgechromium

        if not patch_edgechromium(edgechromium):
            logger.warning("Could not patch pywebview EdgeChromium titlebar support")
    except Exception:
        # Do not prevent NumCalc from starting if a machine cannot initialize
        # Edge/WebView2. The normal pywebview startup path owns that diagnostic.
        logger.exception("Could not install WebView2 native titlebar support")
