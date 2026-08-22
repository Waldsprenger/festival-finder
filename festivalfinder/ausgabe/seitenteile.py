"""Welche Dateien die Seite lädt — aus der Seite selbst gelesen.

Drei Stellen brauchen dieselbe Liste in derselben Reihenfolge: der Service
Worker (was er offline vorhalten muss), die gebündelte Einzelseite (was sie
einbetten muss) und die Seite selbst. Standen sie getrennt da, blieb eine
zurück — beim Aufteilen von `app.js` in Module wäre genau das passiert.

Gelesen wird deshalb `index.html`. Sie ist die Wahrheit; alles andere folgt.
"""

import re

from ..pfade import SITE


def skripte() -> list[str]:
    """Die <script src>-Dateien in der Reihenfolge, in der sie geladen werden."""
    html = (SITE / "index.html").read_text(encoding="utf-8")
    return re.findall(r'<script[^>]+src="([^"]+)"', html)


def stile() -> list[str]:
    """Die eingebundenen Stylesheets, in ihrer Reihenfolge."""
    html = (SITE / "index.html").read_text(encoding="utf-8")
    return re.findall(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"', html)


def vorrat() -> list[str]:
    """Was der Service Worker beim ersten Besuch ablegen soll.

    Die Seite selbst, ihre Stile, ihre Skripte, die Rechtstexte und das
    Manifest. Nicht dabei: `orte.js` — das große Verzeichnis wird nur
    nachgeladen, wenn jemand einen Ort sucht, den die kleine Liste nicht kennt.
    """
    dateien = ["./", "./index.html"]
    dateien += [f"./{d}" for d in stile()]
    dateien += [f"./{d}" for d in skripte() if d != "orte.js"]
    dateien += ["./impressum.html", "./datenschutz.html", "./manifest.webmanifest"]
    # Reihenfolge behalten, Doppelte entfernen
    return list(dict.fromkeys(dateien))
