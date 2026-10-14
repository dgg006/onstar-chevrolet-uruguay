"""Check tracked public files for forbidden captures and JWT credentials."""
from pathlib import Path
import re
import ast
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
try:
    files = subprocess.check_output(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], cwd=ROOT, stderr=subprocess.DEVNULL).decode().split('\0')
    # Source archives may be outside a Git checkout.
    if not files or files == ['']:
        raise ValueError()
except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
    files = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
             if p.is_file() and not any(part in {'.git', '__pycache__'} for part in p.parts)]

failures = []
for filename in files:
    if not filename:
        continue
    path = ROOT / filename
    if not path.is_file():
        continue
    if path.name == 'app_client.json':
        import json
        configuration = json.loads(path.read_text(encoding='utf-8'))
        if set(configuration) != {'client_id', 'client_secret', 'app_version'}:
            failures.append(filename)
    if any(part in {'work', 'private', '.storage'} for part in path.relative_to(ROOT).parts):
        failures.append(filename)
        continue
    if path.suffix in {'.har', '.apk', '.log', '.pem', '.key', '.db'} or path.name in {'secrets.yaml', '.env', 'onstar_uy_private.json'}:
        failures.append(filename)
        continue
    if path.suffix == '.py' and 'tests' not in path.relative_to(ROOT).parts:
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(t, ast.Name) and t.id == 'APP_CLIENT_SECRET' for t in targets):
                    if isinstance(node.value, ast.Constant) and node.value.value:
                        failures.append(filename)
    if path.suffix != '.png' and re.search(rb'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', path.read_bytes()):
        failures.append(filename)
if failures:
    print('Public file check failed; inspect these paths without posting their contents:')
    print('\n'.join(failures))
    sys.exit(1)
print('Public file checks passed. Review changes for other private values before publishing.')
