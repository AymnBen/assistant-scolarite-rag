# ============================================================
# 1. Import des bibliothèques
# ============================================================

import pytest

from backend.decoupage import create_fixed_chunks, split_fixed


# ============================================================
# 2. Vérification du chevauchement et de la couverture du texte
# ============================================================

def test_fixed_overlap():
    """Vérifier les fenêtres et la conservation de tout le texte."""
    text = "ABCDEFGHIJKLM"

    fragments = split_fixed(text, size=6, overlap=2)

    assert fragments == ["ABCDEF", "EFGHIJ", "IJKLM"]

    # Les deux derniers caractères d'un fragment sont repris.
    assert fragments[0][-2:] == fragments[1][:2]
    assert fragments[1][-2:] == fragments[2][:2]

    # Reconstituer le texte sans compter deux fois le chevauchement.
    rebuilt = fragments[0] + "".join(
        fragment[2:] for fragment in fragments[1:]
    )
    assert rebuilt == text


# ============================================================
# 3. Vérification des textes courts et vides
# ============================================================

def test_short_text():
    """Un texte plus court que la taille reste entier."""
    assert split_fixed("Bonjour", size=500, overlap=100) == ["Bonjour"]


def test_empty_text():
    """Un texte vide ou composé d'espaces ne crée aucun fragment."""
    assert split_fixed("") == []
    assert split_fixed("   \n  ") == []


# ============================================================
# 4. Vérification des paramètres invalides
# ============================================================

@pytest.mark.parametrize(
    "size, overlap",
    [
        (0, 0),
        (-10, 0),
        (100, -1),
        (100, 100),
        (100, 150),
    ],
)
def test_invalid_parameters(size, overlap):
    """Refuser les paramètres qui empêchent un découpage correct."""
    with pytest.raises(ValueError):
        split_fixed("Texte de test", size=size, overlap=overlap)


# ============================================================
# 5. Vérification de la fin du texte
# ============================================================

def test_exact_size():
    """Ne pas créer un fragment supplémentaire de chevauchement."""
    assert split_fixed("ABCDEF", size=6, overlap=2) == ["ABCDEF"]


# ============================================================
# 6. Vérification des identifiants et des métadonnées
# ============================================================

def test_chunk_identity_and_metadata():
    """Conserver la provenance et produire des identifiants stables."""
    pages = [{
        "file": "document_test.pdf",
        "reference": "TEST-001",
        "type": "Document de test",
        "date": "2026-01-01",
        "version": "1.0",
        "status": "Test uniquement",
        "page": 2,
        "blocks": [
            {"kind": "text", "text": "Article 1 — Objet"},
            {"kind": "text", "text": "Ce texte sert à tester le découpage."},
        ],
    }]

    first_run = create_fixed_chunks(pages, size=30, overlap=5)
    second_run = create_fixed_chunks(pages, size=30, overlap=5)

    assert first_run
    assert first_run == second_run
    assert len({chunk["id"] for chunk in first_run}) == len(first_run)

    for chunk in first_run:
        assert chunk["file"] == "document_test.pdf"
        assert chunk["reference"] == "TEST-001"
        assert chunk["page"] == 2
        assert chunk["section"] == "Article 1 — Objet"
        assert len(chunk["text"]) <= 30

    # Une modification du contenu doit modifier son identifiant.
    pages[0]["blocks"][1]["text"] = "Un contenu différent."
    modified_run = create_fixed_chunks(pages, size=30, overlap=5)

    assert [c["id"] for c in first_run] != [
        c["id"] for c in modified_run
    ]