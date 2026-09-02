"""Persistencia local opcional das credenciais OAuth.

No Windows, o Client Secret e protegido com DPAPI e so pode ser recuperado pelo
mesmo usuario. Em outros sistemas, as credenciais nao sao gravadas; nesses
casos, a interface e a CLI ainda podem recebe-las manualmente ou por variaveis
de ambiente.
"""
import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


APP_NAME = "osu-mp-link-miner"
CRYPTPROTECT_UI_FORBIDDEN = 0x01


def can_store_credentials():
    """Indica se ha armazenamento seguro implementado neste sistema."""
    return os.name == "nt"


class DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def config_path():
    base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / APP_NAME / "credentials.json"


def _input_blob(data):
    buffer = ctypes.create_string_buffer(data)
    blob = DataBlob(
        len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))
    )
    return blob, buffer


def _protect(value):
    if os.name != "nt":
        raise OSError("A protecao de credenciais requer o Windows.")
    source, source_buffer = _input_blob(value.encode("utf-8"))
    result = DataBlob()
    success = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), APP_NAME, None, None, None,
        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(result),
    )
    del source_buffer
    if not success:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)


def _unprotect(value):
    if os.name != "nt":
        raise OSError("A protecao de credenciais requer o Windows.")
    source, source_buffer = _input_blob(value)
    result = DataBlob()
    success = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None,
        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(result),
    )
    del source_buffer
    if not success:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)


def save_credentials(client_id, client_secret, path=None):
    """Salva o ID e o secret criptografado para o usuario atual do Windows."""
    if not can_store_credentials():
        raise OSError("O armazenamento seguro de credenciais requer o Windows.")
    target = Path(path) if path else config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    protected = base64.b64encode(_protect(client_secret)).decode("ascii")
    payload = {"client_id": client_id, "client_secret_dpapi": protected}
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary, target)


def load_credentials(path=None):
    """Retorna credenciais salvas ou strings vazias se ainda nao existirem."""
    if not can_store_credentials():
        return "", ""
    target = Path(path) if path else config_path()
    if not target.exists():
        return "", ""
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        protected = base64.b64decode(
            payload.get("client_secret_dpapi", ""), validate=True
        )
        secret = _unprotect(protected)
        return str(payload.get("client_id", "")), secret
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return "", ""


def delete_credentials(path=None):
    """Remove as credenciais locais, caso existam."""
    target = Path(path) if path else config_path()
    try:
        target.unlink()
    except FileNotFoundError:
        pass
