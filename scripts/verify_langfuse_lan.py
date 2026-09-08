"""Explicit synthetic-only upload/readback probe for the saved LAN Langfuse .env.

Run: uv run --frozen python scripts/verify_langfuse_lan.py --confirm-synthetic-upload
Requires the test dependency group. It creates two synthetic traces, does not
delete data, and does not enable the independent real-LLM test profile.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-synthetic-upload', action='store_true')
    args = parser.parse_args()
    if not args.confirm_synthetic_upload:
        parser.error('Explicit --confirm-synthetic-upload is required; this writes synthetic LAN traces')
    root = Path(__file__).resolve().parents[1]
    output = root / 'tests/artifacts/upstream_migration/mig-5'
    output.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(NAGA_ENABLE_LANGFUSE_LAN_TESTS='1', NAGA_ENABLE_REAL_LLM_TESTS='0',
               PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONIOENCODING='utf-8')
    command = [sys.executable, '-m', 'pytest', '-p', 'pytest_asyncio.plugin',
               'tests/integration/observability/test_langfuse_chat_wiring.py::test_lan_synthetic_upload_and_readback',
               '-q', '--tb=short', '--junitxml=' + str(output / 'lan-probe.xml')]
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding='utf-8', errors='replace', timeout=180)
        log, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired:
        log, code = 'Synthetic LAN probe exceeded 180 seconds; delivery is not confirmed.', 124
    manifest = {}
    for pattern in ('apiserver/*langfuse*.py', 'apiserver/llm_service.py', 'apiserver/agentic_tool_loop.py',
                    'apiserver/routes/chat.py', 'apiserver/api_server.py', 'tests/support/offline_bootstrap.py',
                    'tests/integration/observability/*.py', 'tests/unit/test_langfuse*.py', 'pyproject.toml', 'uv.lock'):
        for path in root.glob(pattern):
            manifest[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'command': command, 'exit_code': code, 'seconds': round(time.monotonic() - started, 2),
              'revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              'source_sha256': manifest, 'external_write': 'synthetic LAN Langfuse traces only',
              'proof': 'lan-readback.json is acceptance evidence only when this run exits 0'}
    (output / 'lan-probe.log').write_text(log, encoding='utf-8')
    (output / 'lan-probe.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(log[-6000:])
    print('Probe exit code:', code, '| Evidence:', output)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
