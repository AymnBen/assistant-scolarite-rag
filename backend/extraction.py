import json
from pathlib import Path

import pdfplumber


# Racine du projet, quel que soit le dossier depuis lequel on lance le script.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"
OUTPUT_FILE = PROJECT_ROOT / "data" / "pages_brutes.json"


def extract_pages(pdf_path: Path) -> list[dict]:
    """Extrait le texte d'un PDF en conservant le fichier et la page."""
    pages = []

    with pdfplumber.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text(layout=True) or ""

            pages.append({
                "file": pdf_path.name,
                "page": page_number,
                "text": text.strip(),
            })

    return pages


def main() -> None:
    pdf_files = sorted(CORPUS_DIR.glob("*.pdf"))

    if len(pdf_files) != 7:
        raise ValueError(
            f"Le corpus doit contenir 7 PDF ; {len(pdf_files)} trouvé(s)."
        )

    all_pages = []

    for pdf_path in pdf_files:
        pages = extract_pages(pdf_path)
        all_pages.extend(pages)

        print(f"{pdf_path.name} : {len(pages)} page(s)")

        for page in pages:
            if not page["text"]:
                print(f"  Attention : page {page['page']} sans texte extrait.")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        json.dumps(all_pages, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nTotal : {len(all_pages)} pages extraites.")
    print(f"Résultat : {OUTPUT_FILE}")


if __name__ == "__main__":
    main()