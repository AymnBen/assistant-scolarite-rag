# ============================================================
# 1. Imports
# ============================================================

import pytest

from backend.decoupage import create_structural_chunks


# ============================================================
# 2. Création de pages fictives pour les tests
# ============================================================

def make_page(blocks, page=1):
    """Construire une page de test avec ses métadonnées."""
    return {
        "file": "document_test.pdf",
        "reference": "TEST-001",
        "type": "Guide",
        "date": "2026-01-01",
        "version": "1.0",
        "status": "Test uniquement",
        "page": page,
        "blocks": blocks,
    }


# ============================================================
# 3. Conservation des blocs et de leur ordre
# ============================================================

def test_blocks_preserved():
    """Conserver chaque bloc, sans perte ni chevauchement."""
    pages = [make_page([
        {"kind": "text", "text": "AAAA"},
        {"kind": "text", "text": "BBBB"},
        {"kind": "text", "text": "CCCC"},
    ])]

    chunks = create_structural_chunks(pages, size=9)

    # Deux blocs de 4 caractères + un retour à la ligne = 9.
    assert [chunk["text"] for chunk in chunks] == [
        "AAAA\nBBBB",
        "CCCC",
    ]

    rebuilt = "\n".join(chunk["text"] for chunk in chunks)
    assert rebuilt == "AAAA\nBBBB\nCCCC"


# ============================================================
# 4. Conservation d'une longue ligne de tableau
# ============================================================

def test_long_table_row_preserved():
    """Ne pas couper une ligne de tableau dépassant la taille cible."""
    table_text = (
        "Date : 10 juin — Événement : Examen final — Public : 1A"
    )

    pages = [make_page([
        {"kind": "text", "text": "Avant"},
        {"kind": "table_row", "text": table_text},
        {"kind": "text", "text": "Après"},
    ])]

    chunks = create_structural_chunks(pages, size=20)

    assert [chunk["text"] for chunk in chunks] == [
        "Avant",
        table_text,
        "Après",
    ]
    assert len(chunks[1]["text"]) > 20


# ============================================================
# 5. Respect des limites de sections
# ============================================================

def test_sections_separated():
    """Ne pas mélanger deux articles dans un même fragment."""
    pages = [make_page([
        {"kind": "text", "text": "Article 1 — Objet"},
        {"kind": "text", "text": "Premier contenu."},
        {"kind": "text", "text": "Article 2 — Admission"},
        {"kind": "text", "text": "Deuxième contenu."},
    ])]

    chunks = create_structural_chunks(pages, size=500)

    assert len(chunks) == 2
    assert chunks[0]["section"] == "Article 1 — Objet"
    assert chunks[1]["section"] == "Article 2 — Admission"
    assert chunks[0]["text"] == "Article 1 — Objet\nPremier contenu."
    assert chunks[1]["text"] == (
        "Article 2 — Admission\nDeuxième contenu."
    )


# ============================================================
# 6. Conservation de la section sur la page suivante
# ============================================================

def test_section_continues_across_pages():
    """Conserver le nom de section et une provenance par page."""
    pages = [
        make_page([
            {"kind": "text", "text": "Article 1 — Objet"},
            {"kind": "text", "text": "Début du contenu."},
        ], page=1),
        make_page([
            {"kind": "text", "text": "Suite du contenu."},
        ], page=2),
    ]

    chunks = create_structural_chunks(pages, size=500)

    assert len(chunks) == 2
    assert [chunk["page"] for chunk in chunks] == [1, 2]
    assert all(
        chunk["section"] == "Article 1 — Objet"
        for chunk in chunks
    )
    assert chunks[1]["text"] == "Suite du contenu."


# ============================================================
# 7. Vérification des métadonnées et des identifiants
# ============================================================

def test_identity_and_metadata():
    """Produire des identifiants stables et conserver la source."""
    pages = [make_page([
        {"kind": "text", "text": "AAAA"},
        {"kind": "text", "text": "BBBB"},
    ])]

    first_run = create_structural_chunks(pages, size=4)
    second_run = create_structural_chunks(pages, size=4)

    assert len(first_run) == 2
    assert first_run == second_run
    assert len({chunk["id"] for chunk in first_run}) == 2

    for chunk in first_run:
        for field in (
            "file", "reference", "type", "date",
            "version", "status", "page",
        ):
            assert chunk[field] == pages[0][field]

        assert chunk["strategy"] == "structural"
        assert chunk["size"] == 4
        assert chunk["overlap"] == 0

    pages[0]["blocks"][0]["text"] = "ZZZZ"
    modified_run = create_structural_chunks(pages, size=4)

    assert first_run[0]["id"] != modified_run[0]["id"]


# ============================================================
# 8. Corpus vide et blocs vides
# ============================================================

def test_empty_content():
    """Ne pas produire de fragment sans contenu."""
    assert create_structural_chunks([], size=500) == []

    pages = [make_page([
        {"kind": "text", "text": "   \n  "},
    ])]

    assert create_structural_chunks(pages, size=500) == []


# ============================================================
# 9. Paramètres invalides
# ============================================================

@pytest.mark.parametrize("size", [0, -10])
def test_invalid_size(size):
    """Refuser une taille nulle ou négative."""
    with pytest.raises(ValueError):
        create_structural_chunks([], size=size)