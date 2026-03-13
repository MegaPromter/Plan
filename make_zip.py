import zipfile
import os
import fnmatch

exclude_patterns = [
    '__pycache__',
    '*.pyc', '*.pyo', '*.pyd',
    'venv', 'venv311', 'env', '.venv',
    '.env', '.env.local',
    '*.log', 'db.sqlite3', 'staticfiles',
    '.idea', '.vscode',
    '.pytest_cache', '.coverage', 'htmlcov',
    '*.orig',
    'mig_err.txt', 'mig_err2.txt', 'mig_out.txt', 'mig_out2.txt',
    'ntc_simulator',
    '.claude',
    '*.docx',
    'media',
    'list_users.py', 'test_render.py', 'test_templates2.py',
    'make_zip.py',
    'planning_system_report.md',
]

def should_exclude(rel_path):
    parts = rel_path.replace('\\', '/').split('/')
    for part in parts:
        for pat in exclude_patterns:
            if fnmatch.fnmatch(part, pat):
                return True
    return False

base = os.path.dirname(os.path.abspath(__file__))
out = os.path.join(os.path.dirname(base), 'planapp_django_prod.zip')

count = 0
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
    for root, dirs, files in os.walk(base):
        rel_root = os.path.relpath(root, base)
        dirs[:] = [d for d in dirs if not should_exclude(os.path.join(rel_root, d))]
        for file in files:
            rel_path = os.path.join(rel_root, file)
            if not should_exclude(rel_path):
                full = os.path.join(root, file)
                zinfo = zipfile.ZipInfo(rel_path, date_time=(2024, 1, 1, 0, 0, 0))
                zinfo.compress_type = zipfile.ZIP_DEFLATED
                with open(full, 'rb') as f:
                    zf.writestr(zinfo, f.read())
                count += 1

size = os.path.getsize(out)
print(f'Готово: {count} файлов -> {out}')
print(f'Размер: {size/1024/1024:.1f} MB')
