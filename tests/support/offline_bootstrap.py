"""Session-scoped isolation installed BEFORE application imports during collection.

This is test infrastructure, not an alternate implementation of system.config.
Real-LLM opt-in keeps its historical environment switch; default tests cannot use
developer configuration, home-directory state, dotenv credentials or sockets.
"""
from __future__ import annotations

import inspect
import os
from pathlib import Path
import socket
import tempfile

import pytest


class OfflineBootstrap:
    def __init__(self):
        self.patch = pytest.MonkeyPatch()
        self.attempts: list[str] = []
        self.directory: tempfile.TemporaryDirectory | None = None

    def install(self):
        if os.environ.get("NAGA_ENABLE_REAL_LLM_TESTS") == "1":
            return
        self.directory = tempfile.TemporaryDirectory(prefix="naga-pytest-", ignore_cleanup_errors=True)
        sandbox = Path(self.directory.name)
        self.patch.setattr(Path, "home", classmethod(lambda cls: sandbox))
        self.patch.setenv("APPDATA", str(sandbox))
        self.patch.setenv("LITELLM_LOCAL_MODEL_COST_MAP", "True")
        self.patch.setenv("OTEL_SDK_DISABLED", "true")

        # Preserve get_config_path's real precedence logic. Hide ONLY the real
        # developer config; upstream path-precedence tests use their own tmp paths.
        developer_config = Path(__file__).resolve().parents[2] / "config.json"
        original_is_file = Path.is_file
        self.patch.setattr(Path, "is_file", lambda path: False if path == developer_config else original_is_file(path))

        import dotenv
        self.patch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
        for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL",
                    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"):
            self.patch.delenv(key, raising=False)

        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex

        def self_pipe():
            # Windows asyncio creates a private socketpair through loopback TCP.
            return any(frame.function == "socketpair" and Path(frame.filename).name == "socket.py"
                       for frame in inspect.stack())

        def forbidden(target):
            self.attempts.append(repr(target))
            raise RuntimeError(f"external connection forbidden in offline tests: {target!r}")

        def connect(sock, target):
            return original_connect(sock, target) if self_pipe() else forbidden(target)

        def connect_ex(sock, target):
            return original_connect_ex(sock, target) if self_pipe() else forbidden(target)

        self.patch.setattr(socket.socket, "connect", connect)
        self.patch.setattr(socket.socket, "connect_ex", connect_ex)
        self.patch.setattr(socket, "create_connection", lambda target, *a, **kw: forbidden(target))

    def close(self):
        self.patch.undo()
        # App log handlers can keep sandbox files open on Windows. The temporary
        # directory is deliberately retained if cleanup cannot close those files.
        if self.directory is not None:
            self.directory.cleanup()
