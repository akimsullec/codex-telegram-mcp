"""Windows user-scoped DPAPI vault. No plaintext credentials/session on disk."""

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


def initial_state():
    return {
        "version": 1,
        "history_enabled": False,
        "chats": {},
        "requests": {},
        "file_roots": [],
        "credentials": None,
        "session": None,
    }


class Vault:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.path = self.directory / "telegram.dpapi"

    @contextmanager
    def locked(self):
        import msvcrt

        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / "vault.lock").open("a+b") as handle:
            if handle.seek(0, 2) == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError(
                    "Telegram занят другим запросом. Повторите позже."
                ) from None
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

    def load(self):
        if not self.path.exists():
            return initial_state()
        import win32crypt

        _, data = win32crypt.CryptUnprotectData(
            self.path.read_bytes(), None, None, None, 1
        )
        state = json.loads(data.decode("utf-8"))
        if state.get("version") != 1:
            raise RuntimeError("Неизвестная версия хранилища Telegram.")
        return state

    def save(self, state):
        import win32crypt

        data = json.dumps(state, ensure_ascii=False).encode("utf-8")
        encrypted = win32crypt.CryptProtectData(
            data, "Telegram Local", None, None, None, 1
        )
        self.directory.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(dir=self.directory, suffix=".dpapi.tmp")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        finally:
            Path(temp_path).unlink(missing_ok=True)
