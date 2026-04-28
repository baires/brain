from pathlib import Path

VALID_EXTENSIONS = {".md", ".txt"}


def collect_files(path: str) -> list[str]:
    files = []
    p = Path(path)
    if p.is_file():
        if p.suffix in VALID_EXTENSIONS:
            files.append(str(p))
    elif p.is_dir():
        for f in p.rglob("*"):
            if f.is_file() and f.suffix in VALID_EXTENSIONS:
                files.append(str(f))
    return files


def read_file(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")
