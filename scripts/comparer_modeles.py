"""Compare des modèles LM Studio sur le taggage de vraies sessions. Rien n'est écrit dans le coffre.

    uv run python scripts/comparer_modeles.py --sessions 8 qwen/qwen3.5-9b google/gemma-4-e4b

Produit un tableau Markdown (JSON valide, temps moyen, posture et résumé par session) à juger à l'œil.
"""

import argparse
import os
import time
from pathlib import Path

from harnais import config, llm, lmstudio, transcript
from harnais.agents import tagueur
from harnais.vault import Coffre


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("modeles", nargs="+")
    p.add_argument("--sessions", type=int, default=8)
    p.add_argument("--sortie", default="comparaison-modeles.md")
    a = p.parse_args()

    coffre = Coffre(config.chemin_coffre())
    fichiers = sorted(
        config.chemin_transcripts().glob("*/*.jsonl"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    sessions = []
    for f in fichiers:
        s = transcript.lire(f)
        if len(s.messages) >= 2 and "(sous-agent)" not in s.projet:
            sessions.append(s)
        if len(sessions) == a.sessions:
            break

    ids = [i["id"] for i in tagueur.memoire.intentions_resumees(coffre)]
    systeme = (tagueur.PROMPTS / "tagueur.md").read_text(encoding="utf-8")
    resultats: dict[str, list] = {}
    for modele in a.modeles:
        os.environ["LMSTUDIO_MODEL"] = modele
        charge = lmstudio.preparer(modele)
        resultats[modele] = []
        for s in sessions:
            debut = time.monotonic()
            try:
                r = llm.appeler(
                    "tagueur",
                    systeme,
                    tagueur.message(coffre, s),
                    schema=tagueur.schema(ids),
                    max_tokens=1200,
                )
                ok = bool(r.donnees and r.donnees.get("resume"))
                resultats[modele].append(
                    (ok, time.monotonic() - debut, r.donnees or {})
                )
            except Exception as e:
                resultats[modele].append(
                    (False, time.monotonic() - debut, {"resume": f"ERREUR {e}"})
                )
        if charge:
            lmstudio.liberer(modele)

    L = [
        "# Comparaison des modèles de taggage",
        "",
        "| Modèle | JSON valide | Temps moyen |",
        "|---|---|---|",
    ]
    for m, rs in resultats.items():
        L.append(
            f"| {m} | {sum(r[0] for r in rs)}/{len(rs)} | {sum(r[1] for r in rs) / len(rs):.1f} s |"
        )
    for n, s in enumerate(sessions):
        L += [
            "",
            f"## Session {n + 1} · {s.projet} · {s.duree_min} min · {s.titre}",
            "",
        ]
        for m, rs in resultats.items():
            d = rs[n][2]
            L.append(
                f"**{m}** ({d.get('posture', '?')}, confiance {d.get('confiance', '?')}) : {d.get('resume', '')}"
            )
            L.append("")
    Path(a.sortie).write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L[: 3 + len(resultats) + 1]))
    print(f"\nDétail : {a.sortie}")


if __name__ == "__main__":
    main()
