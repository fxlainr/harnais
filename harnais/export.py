"""Export du coffre en archive zip, chiffrable avec `age`."""

import shutil
import subprocess
import zipfile
from datetime import date
from pathlib import Path

from harnais.vault import Coffre

EXCLUS = {".git", "index.sqlite"}


def exporter(
    coffre: Coffre, destination: Path, destinataire_age: str | None = None
) -> Path:
    destination = Path(destination).expanduser()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / f"harnais-coffre_{date.today()}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(coffre.racine.rglob("*")):
            rel = f.relative_to(coffre.racine)
            if f.is_dir() or EXCLUS & set(rel.parts):
                continue
            z.write(f, rel.as_posix())
    if destinataire_age:
        age = shutil.which("age")
        if not age:
            raise RuntimeError(
                "`age` n'est pas installé (brew install age). L'archive non chiffrée est conservée."
            )
        chiffre = archive.with_suffix(".zip.age")
        subprocess.run(
            [age, "-r", destinataire_age, "-o", str(chiffre), str(archive)], check=True
        )
        archive.unlink()
        return chiffre
    return archive
