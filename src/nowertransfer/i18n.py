"""Two-language user interface.

A dict of dicts rather than gettext: the catalogue is small, it needs no
build step, and it survives being frozen into a single .exe without extra
data files. The test suite asserts that every key exists in every language.
"""

from __future__ import annotations

import locale
import os
import sys
from contextlib import suppress

DEFAULT_LANGUAGE = "en"

#: Language code -> name as speakers of that language write it.
LANGUAGES: dict[str, str] = {"en": "English", "de": "Deutsch"}

CATALOG: dict[str, dict[str, str]] = {
    # -- chrome -------------------------------------------------------
    "app.tagline": {
        "en": "Direct file transfer over your own relay",
        "de": "Direkte Dateiübertragung über dein eigenes Relay",
    },
    "app.footer": {
        "en": "v{version} · Relay: {relay}",
        "de": "v{version} · Relay: {relay}",
    },
    "nav.back": {"en": "←  Back", "de": "←  Zurück"},
    "nav.settings": {"en": "Settings", "de": "Einstellungen"},
    # -- home ---------------------------------------------------------
    "home.send.title": {"en": "Send", "de": "Senden"},
    "home.send.body": {
        "en": "Share files\nor a folder",
        "de": "Dateien oder\nOrdner verschicken",
    },
    "home.receive.title": {"en": "Receive", "de": "Empfangen"},
    "home.receive.body": {
        "en": "Fetch with\na code phrase",
        "de": "Mit Code-Phrase\nabholen",
    },
    "home.resume": {
        "en": "Resume last transfer  ({code})",
        "de": "Letzte Übertragung fortsetzen  ({code})",
    },
    # -- first run / missing pieces -----------------------------------
    "croc.missing.title": {
        "en": "croc was not found",
        "de": "croc wurde nicht gefunden",
    },
    "croc.missing.body": {
        "en": (
            "NowerTransfer uses the croc command line tool for the actual "
            "transfer.\n\nPut the croc binary next to this program, or build "
            "the app with scripts/build.py, which bundles it automatically."
        ),
        "de": (
            "NowerTransfer nutzt das Kommandozeilen-Werkzeug croc für die "
            "eigentliche Übertragung.\n\nLege die croc-Datei neben dieses "
            "Programm oder baue die App mit scripts/build.py – dort wird croc "
            "automatisch mit eingepackt."
        ),
    },
    "setup.title": {"en": "One thing first", "de": "Eine Sache noch"},
    "setup.body": {
        "en": (
            "No relay is configured yet. Enter the address of your croc relay "
            "below and you are ready to go."
        ),
        "de": (
            "Es ist noch kein Relay eingetragen. Trage unten die Adresse "
            "deines croc-Relays ein, dann kann es losgehen."
        ),
    },
    # -- send ---------------------------------------------------------
    "send.subtitle": {
        "en": "Send — pick your files, pass on the code",
        "de": "Senden — Dateien auswählen, Code weitergeben",
    },
    "send.choose_folder": {"en": "Choose folder", "de": "Ordner wählen"},
    "send.choose_files": {"en": "Choose files", "de": "Dateien wählen"},
    "send.folder_dialog": {"en": "Which folder?", "de": "Welchen Ordner senden?"},
    "send.files_dialog": {"en": "Which files?", "de": "Welche Dateien senden?"},
    "send.nothing_selected": {
        "en": "Nothing selected yet.",
        "de": "Noch nichts ausgewählt.",
    },
    "send.many_selected": {
        "en": "{count} items selected",
        "de": "{count} Einträge ausgewählt",
    },
    "send.code_label": {
        "en": "CODE PHRASE — send this to the recipient",
        "de": "CODE-PHRASE — dem Empfänger schicken",
    },
    "send.copy": {"en": "Copy", "de": "Kopieren"},
    "send.copied": {
        "en": "Code copied — send it to the recipient now.",
        "de": "Code kopiert — jetzt an den Empfänger schicken.",
    },
    "send.regenerate": {"en": "New code", "de": "Neuer Code"},
    "send.start": {"en": "Start transfer", "de": "Übertragung starten"},
    "send.need_selection": {
        "en": "Pick a folder or some files first.",
        "de": "Bitte zuerst einen Ordner oder Dateien wählen.",
    },
    "send.connecting": {
        "en": "Connected to the relay, waiting for the recipient …",
        "de": "Mit dem Relay verbunden, warte auf den Empfänger …",
    },
    # -- receive ------------------------------------------------------
    "receive.subtitle": {
        "en": "Receive — enter the code and collect",
        "de": "Empfangen — Code eingeben und abholen",
    },
    "receive.code_label": {
        "en": "CODE PHRASE — from the sender",
        "de": "CODE-PHRASE — vom Absender",
    },
    "receive.code_placeholder": {
        "en": "e.g. falke-wolke-tiger-nebel-quarz-83",
        "de": "z. B. falke-wolke-tiger-nebel-quarz-83",
    },
    "receive.choose_target": {"en": "Choose folder", "de": "Zielordner wählen"},
    "receive.target_dialog": {
        "en": "Where should the files go?",
        "de": "Wohin sollen die Dateien?",
    },
    "receive.start": {"en": "Start receiving", "de": "Empfang starten"},
    "receive.need_code": {
        "en": "Enter the code phrase you were given.",
        "de": "Bitte die Code-Phrase vom Absender eingeben.",
    },
    "receive.connecting": {
        "en": "Connected to the relay, looking for the sender …",
        "de": "Mit dem Relay verbunden, suche den Absender …",
    },
    # -- transfer status ----------------------------------------------
    "status.ready": {"en": "Ready.", "de": "Bereit."},
    "status.cancel": {"en": "Cancel", "de": "Abbrechen"},
    "status.cancelling": {"en": "Cancelling …", "de": "Wird abgebrochen …"},
    "status.cancelled": {
        "en": "Cancelled. Start again with the same code phrase whenever you like.",
        "de": "Abgebrochen. Mit derselben Code-Phrase jederzeit neu starten.",
    },
    "status.retry": {
        "en": "Connection lost — trying again in {seconds} s.",
        "de": "Verbindung unterbrochen — neuer Versuch in {seconds} s.",
    },
    "status.finished": {
        "en": "Done. Everything arrived.",
        "de": "Fertig. Alles ist angekommen.",
    },
    "status.finished_button": {"en": "Done!", "de": "Fertig!"},
    "status.fell_back": {
        "en": (
            "Your relay is not answering — continuing over croc's public "
            "relay. Contents stay encrypted; who sends what to whom does not."
        ),
        "de": (
            "Dein Relay antwortet nicht — es geht über das öffentliche "
            "croc-Relay weiter. Inhalte bleiben verschlüsselt, wer wem was "
            "schickt nicht."
        ),
    },
    "status.wrong_code": {
        "en": "Wrong code phrase — please check it.",
        "de": "Falsche Code-Phrase — bitte prüfen.",
    },
    # -- errors -------------------------------------------------------
    "error.relay_unreachable": {
        "en": (
            "Cannot reach the relay. Is it running? Are host, port and relay "
            "password correct, and are ports 9009–9013 open in the firewall?"
        ),
        "de": (
            "Das Relay ist nicht erreichbar. Läuft es? Stimmen Adresse, Port "
            "und Relay-Passwort, und sind die Ports 9009–9013 in der Firewall "
            "offen?"
        ),
    },
    "error.version_mismatch": {
        "en": (
            "The other side is running an older version of this app. Both "
            "of you need the same one - the transfer protocol changed."
        ),
        "de": (
            "Die Gegenseite nutzt eine ältere Version dieser App. Ihr "
            "braucht beide dieselbe – das Übertragungsprotokoll hat sich "
            "geändert."
        ),
    },
    "error.croc_start_failed": {
        "en": "croc could not be started.",
        "de": "croc konnte nicht gestartet werden.",
    },
    "error.no_relay": {
        "en": "No relay configured — open the settings first.",
        "de": "Kein Relay eingetragen — bitte zuerst die Einstellungen öffnen.",
    },
    # -- settings -----------------------------------------------------
    "settings.title": {"en": "Settings", "de": "Einstellungen"},
    "settings.relay_host": {"en": "Relay address", "de": "Relay-Adresse"},
    "settings.relay_host_hint": {
        "en": "Host name or IP of your croc relay. Port 9009 is assumed.",
        "de": "Hostname oder IP deines croc-Relays. Port 9009 wird ergänzt.",
    },
    "settings.relay_host_placeholder": {
        "en": "relay.example.com",
        "de": "relay.example.com",
    },
    "settings.relay_password": {"en": "Relay password", "de": "Relay-Passwort"},
    "settings.relay_password_hint": {
        "en": (
            "Optional. Keeps strangers off your relay; it does not protect "
            "the files, which croc encrypts end to end either way."
        ),
        "de": (
            "Optional. Hält Fremde vom Relay fern; die Dateien schützt es "
            "nicht – die verschlüsselt croc ohnehin Ende-zu-Ende."
        ),
    },
    "settings.relay_password_placeholder": {
        "en": "leave empty for croc's default",
        "de": "leer lassen für croc-Standard",
    },
    "settings.show_password": {"en": "Show", "de": "Zeigen"},
    "settings.relay_mode": {"en": "Which relay to use", "de": "Welches Relay"},
    "settings.relay_mode.own": {"en": "Only mine", "de": "Nur meins"},
    "settings.relay_mode.fallback": {
        "en": "Mine, then public",
        "de": "Meins, sonst öffentlich",
    },
    "settings.relay_mode.public": {"en": "Public", "de": "Öffentlich"},
    "settings.relay_mode_hint": {
        "en": (
            "croc's public relay is run by someone else. File contents stay "
            "end-to-end encrypted either way, but it can see who transfers "
            "to whom, when and how much."
        ),
        "de": (
            "Das öffentliche croc-Relay betreibt jemand anderes. Die Inhalte "
            "bleiben in jedem Fall Ende-zu-Ende verschlüsselt, aber wer wann "
            "wie viel an wen überträgt, ist dort sichtbar."
        ),
    },
    "relay.public": {"en": "croc public relay", "de": "öffentliches croc-Relay"},
    "settings.save": {"en": "Save", "de": "Speichern"},
    "settings.saved": {"en": "Saved to {path}", "de": "Gespeichert unter {path}"},
    "settings.invalid_host": {
        "en": "Please enter a relay address.",
        "de": "Bitte eine Relay-Adresse eintragen.",
    },
    "settings.source": {
        "en": "currently from: {source}",
        "de": "aktuell aus: {source}",
    },
    # -- config sources -----------------------------------------------
    "source.default": {"en": "default", "de": "Standard"},
    "source.build": {"en": "built into this app", "de": "in die App eingebaut"},
    "source.portable": {"en": "file next to the app", "de": "Datei neben der App"},
    "source.user": {"en": "your settings", "de": "deine Einstellungen"},
    "source.environment": {
        "en": "environment variable",
        "de": "Umgebungsvariable",
    },
}


def detect_language() -> str:
    """Best guess at the user's language, falling back to English."""
    candidates: list[str | None] = [
        os.environ.get(name) for name in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE")
    ]
    with suppress(ValueError, TypeError):
        candidates.append(locale.getlocale()[0])
    if sys.platform == "win32":
        with suppress(AttributeError, OSError, KeyError):
            import ctypes

            lcid = ctypes.windll.kernel32.GetUserDefaultUILanguage()  # type: ignore[attr-defined]
            candidates.append(locale.windows_locale.get(lcid))

    for candidate in candidates:
        if not candidate:
            continue
        code = candidate.replace("-", "_").split("_", 1)[0].lower()
        if code in LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


class Translator:
    """Looks up UI strings for one language."""

    def __init__(self, language: str | None = None) -> None:
        self.language = language if language in LANGUAGES else DEFAULT_LANGUAGE

    def __call__(self, key: str, **fields: object) -> str:
        entry = CATALOG.get(key)
        if entry is None:
            # A missing key is a bug, but a half-drawn window helps nobody.
            return key
        text = entry.get(self.language) or entry[DEFAULT_LANGUAGE]
        return text.format(**fields) if fields else text
