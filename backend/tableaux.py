# ============================================================
# 1. Import des bibliothèques
# ============================================================

import json
from pathlib import Path

import pdfplumber

from metadata import FIELD_NAMES, clean_cell, extract_metadata


# ============================================================
# 2. Configuration des chemins
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"
OUTPUT_FILE = PROJECT_ROOT / "data" / "tableaux.json"


# ============================================================
# 3. Identification des tableaux de métadonnées
# ============================================================

def is_metadata_table(rows: list) -> bool:
    """Reconnaître un tableau de présentation par ses intitulés."""
    labels = {
        clean_cell(row[0])
        for row in rows
        if len(row) == 2
    }

    return set(FIELD_NAMES).issubset(labels)


# ============================================================
# 4. Transformation des lignes d'un tableau en texte
# ============================================================

def serialize_table(rows: list) -> list[dict]:
    """Associer chaque cellule à son en-tête de colonne."""
    if len(rows) < 2:
        return []

    # Les tableaux de contenu du corpus ont leurs en-têtes
    # dans la première ligne.
    headers = [clean_cell(cell) for cell in rows[0]]

    if any(not header for header in headers):
        raise ValueError("Tableau avec un en-tête vide : vérifier le PDF.")

    results = []

    for row_number, row in enumerate(rows[1:], start=1):
        values = [clean_cell(cell) for cell in row]

        # Ignorer uniquement les lignes entièrement vides.
        if not any(values):
            continue

        if len(values) != len(headers):
            raise ValueError(
                "Le nombre de cellules ne correspond pas aux en-têtes."
            )

        # Conserver aussi les cellules sous forme structurée.
        # Une cellule vide reste vide : aucune valeur n'est inventée.
        cells = [
            {"header": header, "value": value}
            for header, value in zip(headers, values)
        ]

        text = " — ".join(
            f"{cell['header']} : {cell['value']}"
            for cell in cells
            if cell["value"]
        )

        results.append({
            "row": row_number,
            "cells": cells,
            "text": text,
        })

    return results


# ============================================================
# 5. Extraction des tableaux d'un document
# ============================================================

def extract_tables(pdf_path: Path) -> tuple[list[dict], int]:
    """Extraire les lignes avec leurs métadonnées et leur page."""
    metadata = extract_metadata(pdf_path).model_dump(mode="json")
    results = []
    table_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            for table_number, table in enumerate(
                page.find_tables(), start=1
            ):
                rows = table.extract()

                if is_metadata_table(rows):
                    continue

                table_count += 1

                for row in serialize_table(rows):
                    results.append({
                        **metadata,
                        "page": page_number,
                        "table": table_number,
                        # Position du tableau : utile pour éviter ensuite
                        # de conserver également son texte brut.
                        "bbox": list(table.bbox),
                        **row,
                    })

    return results, table_count


# ============================================================
# 6. Traitement du corpus et sauvegarde
# ============================================================

def main() -> None:
    pdf_files = sorted(CORPUS_DIR.glob("*.pdf"))

    if len(pdf_files) != 7:
        raise ValueError(
            f"Le corpus doit contenir 7 PDF ; {len(pdf_files)} trouvé(s)."
        )

    all_rows = []
    total_tables = 0

    for pdf_path in pdf_files:
        rows, table_count = extract_tables(pdf_path)
        all_rows.extend(rows)
        total_tables += table_count

        print(
            f"{pdf_path.name} : "
            f"{table_count} tableau(x), {len(rows)} ligne(s)"
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nTotal : {total_tables} tableaux, {len(all_rows)} lignes.")
    print(f"Résultat : {OUTPUT_FILE}")


# ============================================================
# 7. Point d'entrée du script
# ============================================================

if __name__ == "__main__":
    main()