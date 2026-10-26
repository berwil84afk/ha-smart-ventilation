"""Status- und Benachrichtigungstexte in Deutsch und Englisch.

Die Sprache folgt der Systemsprache von Home Assistant; alles außer Deutsch
bekommt die englischen Texte.
"""

from __future__ import annotations

TEXTS: dict[str, dict[str, str]] = {
    "de": {
        "init": "Initialisierung …",
        "error": "❗ Fehler beim Schalten des Lüfters",
        "fan_unavailable": "⚪ Lüfter nicht verfügbar",
        "disabled": "⚪ Automatik deaktiviert",
        "disabled_manual": "⚪ Automatik deaktiviert – Lüfter läuft (manuell)",
        "night": "😴 Inaktiv – Nachtruhe bis {end} Uhr",
        "night_message": "🌙 {title}: Lüfter wegen Nachtruhe ausgeschaltet (bis {end} Uhr)",
        "max_runtime": "⏸️ Inaktiv – Pause nach Maximallaufzeit ({max_runtime} min)",
        "max_runtime_message": (
            "⏸️ {title}: Lüfter nach {max_runtime} min Laufzeit pausiert (mind. {pause} min Pause)"
        ),
        "invalid": "⚪ Inaktiv – ungültige Sensorwerte",
        "invalid_running": "⚠️ Ungültige Sensorwerte – Lüfter läuft weiter",
        "reason_min_humidity": "Mindestfeuchte unterschritten",
        "reason_buffer_off": "AH-Puffer unterschritten",
        "reason_condensation": "Kondensationsgefahr",
        "running": "🟢 Aktiv – Lüftung läuft (Diff {diff:.1f} g/m³)",
        "off": "🔴 Inaktiv – {reason}",
        "off_message": "💨 🔴 {title}: Lüfter ausgeschaltet\n{values}\nGrund: {reason}",
        "pause": "⏸️ Inaktiv – Zwangspause bis {until} Uhr",
        "min_humidity": "🔴 Inaktiv – Feuchte innen < {min_rh:.0f} % ({rh:.1f} %)",
        "difference_low": "🔴 Inaktiv – AH-Differenz zu gering ({diff:.1f} g/m³)",
        "condensation_detail": (
            "Taupunkt außen {dew_point:.1f} °C, Wand {wall:.1f} °C, Diff {diff:.1f} g/m³"
        ),
        "condensation": "⚠️ Inaktiv – Kondensationsgefahr ({detail})",
        "condensation_message": "⚠️ {title}: Lüften wäre sinnvoll, aber Kondensationsgefahr ({detail})",
        "on_message": "💨 🟢 {title}: Lüfter eingeschaltet\n{values}",
        "values": (
            "Innen: {in_t:.1f} °C / {in_rh:.1f} % → {in_ah:.2f} g/m³\n"
            "Außen: {out_t:.1f} °C / {out_rh:.1f} % → {out_ah:.2f} g/m³\n"
            "Differenz: {diff:.2f} g/m³\n"
            "Taupunkt außen: {dew_point:.1f} °C"
        ),
    },
    "en": {
        "init": "Initializing …",
        "error": "❗ Error switching the fan",
        "fan_unavailable": "⚪ Fan unavailable",
        "disabled": "⚪ Automatic mode disabled",
        "disabled_manual": "⚪ Automatic mode disabled – fan running (manual)",
        "night": "😴 Inactive – quiet hours until {end}",
        "night_message": "🌙 {title}: fan turned off for quiet hours (until {end})",
        "max_runtime": "⏸️ Inactive – pause after maximum runtime ({max_runtime} min)",
        "max_runtime_message": (
            "⏸️ {title}: fan paused after {max_runtime} min runtime (at least {pause} min pause)"
        ),
        "invalid": "⚪ Inactive – invalid sensor values",
        "invalid_running": "⚠️ Invalid sensor values – fan keeps running",
        "reason_min_humidity": "below minimum humidity",
        "reason_buffer_off": "below turn-off buffer",
        "reason_condensation": "condensation risk",
        "running": "🟢 Active – ventilating (diff {diff:.1f} g/m³)",
        "off": "🔴 Inactive – {reason}",
        "off_message": "💨 🔴 {title}: fan turned off\n{values}\nReason: {reason}",
        "pause": "⏸️ Inactive – forced pause until {until}",
        "min_humidity": "🔴 Inactive – indoor humidity < {min_rh:.0f} % ({rh:.1f} %)",
        "difference_low": "🔴 Inactive – humidity difference too small ({diff:.1f} g/m³)",
        "condensation_detail": (
            "outdoor dew point {dew_point:.1f} °C, wall {wall:.1f} °C, diff {diff:.1f} g/m³"
        ),
        "condensation": "⚠️ Inactive – condensation risk ({detail})",
        "condensation_message": (
            "⚠️ {title}: ventilating would help, but there is a condensation risk ({detail})"
        ),
        "on_message": "💨 🟢 {title}: fan turned on\n{values}",
        "values": (
            "Indoor: {in_t:.1f} °C / {in_rh:.1f} % → {in_ah:.2f} g/m³\n"
            "Outdoor: {out_t:.1f} °C / {out_rh:.1f} % → {out_ah:.2f} g/m³\n"
            "Difference: {diff:.2f} g/m³\n"
            "Outdoor dew point: {dew_point:.1f} °C"
        ),
    },
}


def get_texts(language: str | None) -> dict[str, str]:
    """Texte für die Systemsprache, z. B. "de", "de-CH" oder "en-GB"."""
    if language and language.split("-")[0].lower() == "de":
        return TEXTS["de"]
    return TEXTS["en"]
