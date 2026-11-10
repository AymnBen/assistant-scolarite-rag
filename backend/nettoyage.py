# ============================================================
# 1. Import des bibliothèques
# ============================================================

import json
import re
from collections import Counter, defaultdict
from pathlib import Path


# ============================================================
# 2. Configuration des chemins
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

PAGES_FILE = DATA_DIR / "pages_brutes.json"
METADATA_FILE = DATA_DIR / "documents.json"
OUTPUT_FILE = DATA_DIR / "pages_nettoyees.json"


# ============================================================
# 3. Normalisation pour comparer les lignes
# ============================================================

def normalize_margin(text: str) -> str:
    """Uniformiser les espaces et neutraliser le numéro de page."""
    text = " ".join(text.split())

    # Les pieds de page sont identiques sauf leur pagination.
    # Exemple : "Guide — page 1" devient "Guide — page #".
    return re.sub(
        r"\bpage\s+\d+\b",
        "page #",
        text,
        flags=re.IGNORECASE,
    )


def nonempty_lines(text: str) -> list[str]:
    """Récupérer les lignes non vides sans modifier leurs espaces."""
    return [line for line in text.splitlines() if line.strip()]


# ============================================================
# 4. Nettoyage des pages d'un document
# ============================================================

def clean_document(pages: list[dict]) -> tuple[list[dict], int]:
    """Retirer les premières et dernières lignes répétées."""
    lines_by_page = [
        nonempty_lines(page["text"])
        for page in pages
    ]

    # Compter séparément les lignes du haut et celles du bas.
    headers = Counter(
        normalize_margin(lines[0])
        for lines in lines_by_page
        if lines
    )

    footers = Counter(
        normalize_margin(lines[-1])
        for lines in lines_by_page
        if lines
    )

    cleaned_pages = []
    removed_count = 0

    for page, lines in zip(pages, lines_by_page):
        positions_to_remove = set()

        if lines:
            # Une ligne doit apparaître sur au moins deux pages.
            if headers[normalize_margin(lines[0])] >= 2:
                positions_to_remove.add(0)

            if footers[normalize_margin(lines[-1])] >= 2:
                positions_to_remove.add(len(lines) - 1)

        kept_lines = [
            line
            for index, line in enumerate(lines)
            if index not in positions_to_remove
        ]

        removed_count += len(positions_to_remove)

        cleaned_pages.append({
            **page,
            "text": "\n".join(kept_lines).strip(),
        })

    return cleaned_pages, removed_count


# ============================================================
# 5. Chargement des pages et des métadonnées
# ============================================================

def main() -> None:
    pages = json.loads(PAGES_FILE.read_text(encoding="utf-8"))
    documents = json.loads(METADATA_FILE.read_text(encoding="utf-8"))

    metadata_by_file = {
        document["file"]: document
        for document in documents
    }

    # Regrouper les pages pour comparer uniquement celles
    # qui appartiennent au même document.
    pages_by_file = defaultdict(list)

    for page in pages:
        pages_by_file[page["file"]].append(page)

    if set(pages_by_file) != set(metadata_by_file):
        raise ValueError(
            "Les fichiers des pages et des métadonnées ne correspondent pas. "
            "Relancez extraction.py et metadata.py."
        )

    all_cleaned_pages = []
    total_removed = 0


    # ========================================================
    # 6. Nettoyage et ajout des métadonnées à chaque page
    # ========================================================

    for filename, document_pages in pages_by_file.items():
        cleaned_pages, removed = clean_document(document_pages)

        for page in cleaned_pages:
            all_cleaned_pages.append({
                **metadata_by_file[filename],
                **page,
            })

        total_removed += removed

        print(
            f"{filename} : "
            f"{len(cleaned_pages)} pages, "
            f"{removed} lignes répétées supprimées"
        )


    # ========================================================
    # 7. Sauvegarde des résultats
    # ========================================================

    OUTPUT_FILE.write_text(
        json.dumps(all_cleaned_pages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nTotal : {len(all_cleaned_pages)} pages nettoyées.")
    print(f"Lignes supprimées : {total_removed}")
    print(f"Résultat : {OUTPUT_FILE}")


# ============================================================
# 8. Point d'entrée du script
# ============================================================

if __name__ == "__main__":
    main()