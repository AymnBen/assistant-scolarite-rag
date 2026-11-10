# ============================================================
# 1. Import des bibliothèques
# ============================================================

import json
import re
from datetime import date
from pathlib import Path

import pdfplumber
from pydantic import BaseModel, Field


# ============================================================
# 2. Configuration des chemins et des champs recherchés
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus"
OUTPUT_FILE = PROJECT_ROOT / "data" / "documents.json"

# Associer les intitulés des PDF aux noms utilisés dans notre JSON.
FIELD_NAMES = {
    "Référence": "reference",
    "Type de document": "type",
    "Date de publication": "date",
    "Version": "version",
    "Statut": "status",
}

# Convertir les mois français sans dépendre de la langue de Windows.
MONTHS = {
    "janvier": 1,
    "février": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
}


# ============================================================
# 3. Modèle Pydantic des métadonnées
# ============================================================

class DocumentMetadata(BaseModel):
    """Décrire un document et vérifier ses champs obligatoires."""

    file: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    type: str = Field(min_length=1)
    date: date
    version: str = Field(min_length=1)
    status: str = Field(min_length=1)


# ============================================================
# 4. Nettoyage des cellules et conversion des dates
# ============================================================

def clean_cell(value: str | None) -> str:
    """Remplacer les retours à la ligne et espaces multiples."""
    return " ".join((value or "").split())


def parse_french_date(value: str) -> date:
    """Convertir '1er septembre 2026' en une date Python."""
    match = re.fullmatch(
        r"(\d{1,2})(?:er)?\s+(\w+)\s+(\d{4})",
        clean_cell(value).lower(),
    )

    if match is None:
        raise ValueError(f"Format de date non reconnu : {value}")

    day, month, year = match.groups()

    if month not in MONTHS:
        raise ValueError(f"Mois non reconnu : {month}")

    # date() vérifie aussi la validité du jour et du mois.
    return date(int(year), MONTHS[month], int(day))


# ============================================================
# 5. Extraction des métadonnées d'un PDF
# ============================================================

def extract_metadata(pdf_path: Path) -> DocumentMetadata:
    """Chercher le tableau contenant les cinq champs attendus."""
    candidates = []
    required_fields = set(FIELD_NAMES.values())

    with pdfplumber.open(pdf_path) as pdf:
        for table in pdf.pages[0].extract_tables():
            fields = {}

            for row in table:
                # Le tableau de présentation contient deux colonnes :
                # l'intitulé à gauche et sa valeur à droite.
                if len(row) != 2:
                    continue

                label = clean_cell(row[0])
                value = clean_cell(row[1])

                if label in FIELD_NAMES:
                    fields[FIELD_NAMES[label]] = value

            if required_fields.issubset(fields):
                candidates.append(fields)

    # Échouer explicitement plutôt que d'inventer une métadonnée.
    if len(candidates) != 1:
        raise ValueError(
            f"{pdf_path.name} : attendu un tableau de métadonnées "
            f"complet, trouvé {len(candidates)}."
        )

    fields = candidates[0]
    fields["date"] = parse_french_date(fields["date"])

    return DocumentMetadata(file=pdf_path.name, **fields)


# ============================================================
# 6. Traitement du corpus et sauvegarde en JSON
# ============================================================

def main() -> None:
    pdf_files = sorted(CORPUS_DIR.glob("*.pdf"))

    if len(pdf_files) != 7:
        raise ValueError(
            f"Le corpus doit contenir 7 PDF ; {len(pdf_files)} trouvé(s)."
        )

    documents = []

    for pdf_path in pdf_files:
        metadata = extract_metadata(pdf_path)
        documents.append(metadata.model_dump(mode="json"))

        print(
            f"{metadata.reference} | "
            f"{metadata.date.isoformat()} | "
            f"{metadata.type}"
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    OUTPUT_FILE.write_text(
        json.dumps(documents, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\n{len(documents)} documents traités.")
    print(f"Résultat : {OUTPUT_FILE}")


# ============================================================
# 7. Point d'entrée du script
# ============================================================

if __name__ == "__main__":
    main()