import subprocess, sys
r = subprocess.run(
    ["python3", "-m", "pytest", "test_db.py", "-v"],
    cwd="/home/doo/f42bbs",
    capture_output=True, text=True
)
print(r.stdout)
print(r.stderr)
sys.exit(r.returncode)
