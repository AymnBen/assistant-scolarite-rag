# ============================================================
# 1. Import des bibliothèques
# ============================================================

import json
from collections import Counter
from pathlib import Path

import pdfplumber

from metadata import extract_metadata
from nettoyage import normalize_margin
from tableaux import is_metadata_table, serialize_table


# ============================================================
# 2. Configuration des chemins
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"
OUTPUT_FILE = PROJECT_ROOT / "data" / "pages_preparees.json"


# ============================================================
# 3. Retrait du texte situé dans les tableaux
# ============================================================

def exclude_tables(page, tables):
    """Écarter les caractères des tableaux pour éviter les doublons."""
    boxes = [table.bbox for table in tables]

    def keep_object(obj):
        if obj.get("object_type") != "char":
            return True

        # Calculer le centre du caractère dans la page.
        x = (obj["x0"] + obj["x1"]) / 2
        y = (obj["top"] + obj["bottom"]) / 2

        # Conserver le caractère s'il est hors de tous les tableaux.
        return not any(
            left <= x <= right and top <= y <= bottom
            for left, top, right, bottom in boxes
        )

    return page.filter(keep_object)


# ============================================================
# 4. Préparation des pages d'un document
# ============================================================

def prepare_document(pdf_path: Path) -> list[dict]:
    """Assembler les lignes de texte et de tableaux dans leur ordre."""
    metadata = extract_metadata(pdf_path).model_dump(mode="json")
    prepared_pages = []

    with pdfplumber.open(pdf_path) as pdf:
        # Relever les lignes originales avant de retirer les tableaux.
        original_lines = [
            page.extract_text_lines()
            for page in pdf.pages
        ]

        headers = Counter(
            normalize_margin(lines[0]["text"])
            for lines in original_lines
            if lines
        )

        footers = Counter(
            normalize_margin(lines[-1]["text"])
            for lines in original_lines
            if lines
        )

        for page_number, (page, original) in enumerate(
            zip(pdf.pages, original_lines), start=1
        ):
            tables = page.find_tables()
            text_page = exclude_tables(page, tables)
            lines = text_page.extract_text_lines()

            # Retirer seulement les marges répétées identifiées
            # dans les pages originales du même document.
            if original and lines:
                first = normalize_margin(original[0]["text"])

                if (
                    headers[first] >= 2
                    and normalize_margin(lines[0]["text"]) == first
                ):
                    lines = lines[1:]

            if original and lines:
                last = normalize_margin(original[-1]["text"])

                if (
                    footers[last] >= 2
                    and normalize_margin(lines[-1]["text"]) == last
                ):
                    lines = lines[:-1]

            blocks = []

            # Conserver chaque ligne de texte et sa position verticale.
            for line in lines:
                blocks.append({
                    "kind": "text",
                    "top": line["top"],
                    "text": line["text"],
                })

            # Réintroduire les tableaux sous forme de lignes explicites.
            for table_number, table in enumerate(tables, start=1):
                rows = table.extract()

                # Les métadonnées figurent déjà dans chaque page :
                # leur tableau de présentation n'est pas réintroduit.
                if is_metadata_table(rows):
                    continue

                for row in serialize_table(rows):
                    blocks.append({
                        "kind": "table_row",
                        "top": table.rows[row["row"]].bbox[1],
                        "table": table_number,
                        "row": row["row"],
                        "cells": row["cells"],
                        "text": row["text"],
                    })

            # Retrouver l'ordre de lecture du haut vers le bas.
            blocks.sort(key=lambda block: block["top"])

            prepared_pages.append({
                **metadata,
                "page": page_number,
                "blocks": blocks,
                "text": "\n".join(block["text"] for block in blocks),
            })

    return prepared_pages


# ============================================================
# 5. Traitement du corpus et sauvegarde
# ============================================================

def main() -> None:
    pdf_files = sorted(CORPUS_DIR.glob("*.pdf"))

    if len(pdf_files) != 7:
        raise ValueError(
            f"Le corpus doit contenir 7 PDF ; {len(pdf_files)} trouvé(s)."
        )

    all_pages = []
    total_table_rows = 0

    for pdf_path in pdf_files:
        pages = prepare_document(pdf_path)

        table_rows = sum(
            block["kind"] == "table_row"
            for page in pages
            for block in page["blocks"]
        )

        all_pages.extend(pages)
        total_table_rows += table_rows

        print(
            f"{pdf_path.name} : {len(pages)} pages, "
            f"{table_rows} lignes de tableaux intégrées"
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(all_pages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nTotal : {len(all_pages)} pages préparées.")
    print(f"Lignes de tableaux intégrées : {total_table_rows}")
    print(f"Résultat : {OUTPUT_FILE}")


# ============================================================
# 6. Point d'entrée du script
# ============================================================

if __name__ == "__main__":
    main()