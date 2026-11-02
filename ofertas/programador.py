"""Programa la revisión automática de alertas en el sistema operativo.

- Windows: Programador de tareas (schtasks), una tarea diaria por horario.
- Mac / Linux: crontab, con líneas marcadas "# ofertas-super".
"""
from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

MARCA = "# ofertas-super"
PREFIJO_TAREA = "OfertasSuper"


def _python() -> str:
    exe = Path(sys.executable)
    if platform.system() == "Windows":
        sin_ventana = exe.with_name("pythonw.exe")  # evita que se abra una ventana negra
        if sin_ventana.exists():
            return str(sin_ventana)
    return str(exe)


def comando_alertas() -> str:
    return f'"{_python()}" -m ofertas.cli alertas'


def _validar(horas: list[int]) -> list[int]:
    horas = sorted(set(horas))
    if not horas or any(h < 0 or h > 23 for h in horas):
        raise ValueError("Las horas deben estar entre 0 y 23.")
    return horas


# ---------- Windows ----------
def comandos_windows(horas: list[int]) -> list[list[str]]:
    return [["schtasks", "/Create", "/F", "/SC", "DAILY", "/TN", f"{PREFIJO_TAREA}-{h:02d}",
             "/TR", comando_alertas(), "/ST", f"{h:02d}:00"] for h in _validar(horas)]


def _tareas_windows() -> list[str]:
    r = subprocess.run(["schtasks", "/Query", "/FO", "CSV", "/NH"], capture_output=True, text=True)
    return sorted({linea.split(",")[0].strip('"\\') for linea in r.stdout.splitlines()
                   if PREFIJO_TAREA in linea})


# ---------- Mac / Linux ----------
def lineas_cron(horas: list[int]) -> list[str]:
    return [f"0 {h} * * * {comando_alertas()} {MARCA}" for h in _validar(horas)]


def fusionar_cron(actual: str, nuevas: list[str]) -> str:
    conservar = [l for l in actual.splitlines() if MARCA not in l and l.strip()]
    return "\n".join(conservar + nuevas) + "\n"


def _leer_cron() -> str:
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def _escribir_cron(texto: str) -> None:
    subprocess.run(["crontab", "-"], input=texto, text=True, check=True)


# ---------- API común ----------
def programar(horas: list[int]) -> str:
    horas = _validar(horas)
    if platform.system() == "Windows":
        quitar()
        for cmd in comandos_windows(horas):
            subprocess.run(cmd, check=True, capture_output=True, text=True)
    else:
        if not shutil.which("crontab"):
            raise RuntimeError("No encontré 'crontab' en este equipo.")
        _escribir_cron(fusionar_cron(_leer_cron(), lineas_cron(horas)))
    return "Revisión programada diario a las " + ", ".join(f"{h:02d}:00" for h in horas) + "."


def quitar() -> str:
    if platform.system() == "Windows":
        for t in _tareas_windows():
            subprocess.run(["schtasks", "/Delete", "/F", "/TN", t], capture_output=True)
    elif shutil.which("crontab"):
        _escribir_cron(fusionar_cron(_leer_cron(), []))
    return "Revisión automática desactivada."


def estado() -> list[str]:
    """Horarios programados actualmente (texto legible)."""
    try:
        if platform.system() == "Windows":
            return [t.split("-")[-1] + ":00" for t in _tareas_windows()]
        return [f"{int(l.split()[1]):02d}:00" for l in _leer_cron().splitlines() if MARCA in l]
    except (OSError, ValueError, IndexError):
        return []
