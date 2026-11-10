# ============================================================
# 1. Import des bibliothèques
# ============================================================

import argparse
import hashlib
import json
import re
from pathlib import Path


# ============================================================
# 2. Configuration des chemins et reconnaissance des titres
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "data" / "pages_preparees.json"

# Reconnaître les articles, titres, sections numérotées et questions.
# Les lignes de tableaux sont exclues de cette détection.
SECTION_PATTERN = re.compile(
    r"^(?:"
    r"Article\s+\d+\b|"
    r"Titre\s+[IVXLCDM]+\b|"
    r"\d+(?:\.\d+)*\.?\s+\S|"
    r"Q\d+\.\s+"
    r")",
    flags=re.IGNORECASE,
)

METADATA_FIELDS = (
    "file",
    "reference",
    "type",
    "date",
    "version",
    "status",
    "page",
)


# ============================================================
# 3. Découpage fixe avec chevauchement
# ============================================================

def split_fixed(
    text: str,
    size: int = 500,
    overlap: int = 100,
) -> list[str]:
    """Découper un texte en fenêtres de caractères."""
    if size <= 0:
        raise ValueError("La taille doit être strictement positive.")

    if overlap < 0 or overlap >= size:
        raise ValueError(
            "Le chevauchement doit être positif ou nul "
            "et strictement inférieur à la taille."
        )

    if not text.strip():
        return []

    fragments = []
    start = 0

    while start < len(text):
        end = min(start + size, len(text))
        fragment = text[start:end]

        if fragment.strip():
            fragments.append(fragment)

        # Éviter un dernier fragment contenant uniquement
        # le chevauchement déjà présent dans le précédent.
        if end == len(text):
            break

        start = end - overlap

    return fragments


# ============================================================
# 4. Regroupement des blocs par section et par page
# ============================================================

def group_sections(pages: list[dict]) -> list[dict]:
    """Conserver la section courante, même à travers les pages."""
    groups = []
    current_file = None
    current_section = "Introduction"

    for page in sorted(
        pages,
        key=lambda item: (item["file"], item["page"]),
    ):
        # Réinitialiser la section au changement de document.
        if page["file"] != current_file:
            current_file = page["file"]
            current_section = "Introduction"

        pending_blocks = []

        def save_group():
            """Enregistrer les blocs accumulés pour cette section."""
            if pending_blocks:
                groups.append({
                    **{key: page[key] for key in METADATA_FIELDS},
                    "section": current_section,
                    "blocks": list(pending_blocks),
                    "text": "\n".join(
                        block["text"] for block in pending_blocks
                    ),
                })

        for block in page["blocks"]:
            text = block["text"].strip()

            if not text:
                continue

            is_heading = (
                block["kind"] == "text"
                and SECTION_PATTERN.match(text) is not None
            )

            if is_heading:
                save_group()
                pending_blocks = []
                current_section = text

            pending_blocks.append(block)

        # Fermer le groupe en fin de page pour conserver
        # un numéro de page précis pour chaque fragment.
        save_group()

    return groups


# ============================================================
# 5. Création des fragments fixes avec identifiants stables
# ============================================================

def create_fixed_chunks(
    pages: list[dict],
    size: int,
    overlap: int,
) -> list[dict]:
    """Associer chaque fragment fixe à sa source et ses paramètres."""
    chunks = []

    for group_index, group in enumerate(group_sections(pages)):
        fragments = split_fixed(group["text"], size, overlap)

        for fragment_index, text in enumerate(fragments):
            chunk = {
                **{key: group[key] for key in METADATA_FIELDS},
                "section": group["section"],
                "strategy": "fixed",
                "size": size,
                "overlap": overlap,
                "text": text,
            }

            # Même contenu, même position et mêmes paramètres :
            # le calcul redonne le même identifiant.
            identity = json.dumps(
                {
                    **chunk,
                    "group_index": group_index,
                    "fragment_index": fragment_index,
                },
                ensure_ascii=False,
                sort_keys=True,
            )

            chunk["id"] = hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()

            chunks.append(chunk)

    return chunks


# ============================================================
# 6. Création des fragments structurels
# ============================================================

def create_structural_chunks(
    pages: list[dict],
    size: int = 500,
) -> list[dict]:
    """Assembler les blocs par section et page, sans les couper."""
    if size <= 0:
        raise ValueError("La taille doit être strictement positive.")

    chunks = []

    for group_index, group in enumerate(group_sections(pages)):
        fragments = []
        pending = []
        current_length = 0

        for block in group["blocks"]:
            text = block["text"]

            if not text.strip():
                continue

            # Prévoir le retour à la ligne entre deux blocs.
            added_length = len(text) + (1 if pending else 0)

            # Fermer le fragment si l'ajout du bloc dépasserait
            # la taille cible. Le bloc lui-même n'est jamais coupé.
            if pending and current_length + added_length > size:
                fragments.append("\n".join(pending))
                pending = []
                current_length = 0

            if pending:
                current_length += 1

            pending.append(text)
            current_length += len(text)

        # Enregistrer le dernier fragment du groupe.
        if pending:
            fragments.append("\n".join(pending))

        for fragment_index, text in enumerate(fragments):
            chunk = {
                **{key: group[key] for key in METADATA_FIELDS},
                "section": group["section"],
                "strategy": "structural",
                "size": size,
                "overlap": 0,
                "text": text,
            }

            identity = json.dumps(
                {
                    **chunk,
                    "group_index": group_index,
                    "fragment_index": fragment_index,
                },
                ensure_ascii=False,
                sort_keys=True,
            )

            chunk["id"] = hashlib.sha256(
                identity.encode("utf-8")
            ).hexdigest()

            chunks.append(chunk)

    return chunks


# ============================================================
# 7. Paramètres de lancement et sauvegarde
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Découpage fixe ou structurel du corpus."
    )

    parser.add_argument(
        "--strategy",
        choices=["fixed", "structural"],
        default="fixed",
        help="Stratégie de découpage : fixed ou structural.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=500,
        help="Taille maximale en fixe ; taille cible en structurel.",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=None,
        help="Chevauchement : 100 par défaut en fixe, 0 en structurel.",
    )

    args = parser.parse_args()

    if args.size <= 0:
        parser.error("La taille doit être strictement positive.")

    # Valider les paramètres avant de lire les données.
    if args.strategy == "fixed":
        overlap = 100 if args.overlap is None else args.overlap

        if not 0 <= overlap < args.size:
            parser.error("Il faut : 0 <= overlap < size.")

    else:
        if args.overlap not in (None, 0):
            parser.error(
                "La stratégie structurelle utilise un chevauchement de 0."
            )

        overlap = 0

    pages = json.loads(INPUT_FILE.read_text(encoding="utf-8"))

    if args.strategy == "fixed":
        chunks = create_fixed_chunks(pages, args.size, overlap)
        filename = f"fragments_fixed_{args.size}_{overlap}.json"

    else:
        chunks = create_structural_chunks(pages, args.size)
        filename = f"fragments_structural_{args.size}.json"

    output_file = PROJECT_ROOT / "data" / filename
    output_file.parent.mkdir(parents=True, exist_ok=True)

    output_file.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    max_length = max(
        (len(chunk["text"]) for chunk in chunks),
        default=0,
    )

    oversized = sum(
        len(chunk["text"]) > args.size
        for chunk in chunks
    )

    print(f"Stratégie : {args.strategy}")
    print(f"Taille demandée : {args.size} caractères")
    print(f"Chevauchement : {overlap} caractères")
    print(f"Fragments créés : {len(chunks)}")
    print(f"Identifiants uniques : {len({c['id'] for c in chunks})}")
    print(f"Longueur maximale : {max_length} caractères")
    print(f"Fragments dépassant la taille cible : {oversized}")
    print(f"Résultat : {output_file}")


# ============================================================
# 8. Point d'entrée du script
# ============================================================

if __name__ == "__main__":
    main()