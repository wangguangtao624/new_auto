from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

root = Path.cwd()
version = (root / "VERSION").read_text(encoding="ascii").strip()
out_dir = root / "dist"
out_dir.mkdir(exist_ok=True)
out = out_dir / f"new_auto-{version}-windows-x64.zip"
include = ["app", "bin", "configs", "fw", "modules", "scripts", "tests"]
files = [root / x for x in ("README.md", "REPORT.md", "DEPLOYMENT.md", "RELEASE_NOTES.md", "VERSION", "requirements.txt", "run_new_auto.bat", "config.json", "pixelide.ini")]
with ZipFile(out, "w", ZIP_DEFLATED, compresslevel=6) as z:
    prefix = f"new_auto-{version}"
    for item in include:
        for path in (root / item).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.name != "agent_key.local":
                z.write(path, f"{prefix}/{path.relative_to(root).as_posix()}")
    for path in files:
        z.write(path, f"{prefix}/{path.name}")
print(out)
