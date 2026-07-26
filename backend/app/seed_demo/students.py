"""Demo students: Brazilian names, @demo.certai.app emails, fixed profile assignment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DemoStudent:
    email: str
    name: str
    profile: str


# Order is fixed: profiles are assigned by slice so the seed is stable.
# Counts: destaque 7, consistente 11, irregular 11, dificuldade 7,
# pouco_engajado 7, atrasado 2, pendente_avaliacao 3 → 48.
_RAW: list[tuple[str, str, str]] = [
    # destaque (7)
    ("ana.beatriz.souza", "Ana Beatriz Souza", "destaque"),
    ("rafael.monteiro", "Rafael Monteiro", "destaque"),
    ("larissa.figueiredo", "Larissa Figueiredo", "destaque"),
    ("thiago.barbosa", "Thiago Barbosa", "destaque"),
    ("isabela.nogueira", "Isabela Nogueira", "destaque"),
    ("gabriel.pires", "Gabriel Pires", "destaque"),
    ("maria.eduarda.ramos", "Maria Eduarda Ramos", "destaque"),
    # consistente (11)
    ("joao.pedro.santos", "João Pedro Santos", "consistente"),
    ("beatriz.almeida", "Beatriz Almeida", "consistente"),
    ("felipe.castro", "Felipe Castro", "consistente"),
    ("carolina.vieira", "Carolina Vieira", "consistente"),
    ("andre.ribeiro", "André Ribeiro", "consistente"),
    ("patricia.gomes", "Patrícia Gomes", "consistente"),
    ("rodrigo.melo", "Rodrigo Melo", "consistente"),
    ("amanda.cardoso", "Amanda Cardoso", "consistente"),
    ("vinicius.teixeira", "Vinícius Teixeira", "consistente"),
    ("juliana.freitas", "Juliana Freitas", "consistente"),
    ("diego.araujo", "Diego Araújo", "consistente"),
    # irregular (11)
    ("camila.batista", "Camila Batista", "irregular"),
    ("lucas.moura", "Lucas Moura", "irregular"),
    ("helena.correia", "Helena Correia", "irregular"),
    ("matheus.duarte", "Matheus Duarte", "irregular"),
    ("sofia.martins", "Sofia Martins", "irregular"),
    ("bruno.farias", "Bruno Farias", "irregular"),
    ("laura.campos", "Laura Campos", "irregular"),
    ("pedro.henrique.dias", "Pedro Henrique Dias", "irregular"),
    ("giovanna.reis", "Giovanna Reis", "irregular"),
    ("gustavo.nunes", "Gustavo Nunes", "irregular"),
    ("manuela.lopes", "Manuela Lopes", "irregular"),
    # dificuldade (7)
    ("renata.oliveira", "Renata Oliveira", "dificuldade"),
    ("caio.fernandes", "Caio Fernandes", "dificuldade"),
    ("tatiane.moreira", "Tatiane Moreira", "dificuldade"),
    ("wesley.silva", "Wesley Silva", "dificuldade"),
    ("priscila.andrade", "Priscila Andrade", "dificuldade"),
    ("alexandre.costa", "Alexandre Costa", "dificuldade"),
    ("danielle.rocha", "Danielle Rocha", "dificuldade"),
    # pouco_engajado (7)
    ("igor.machado", "Igor Machado", "pouco_engajado"),
    ("bruna.azevedo", "Bruna Azevedo", "pouco_engajado"),
    ("samuel.pinto", "Samuel Pinto", "pouco_engajado"),
    ("leticia.barros", "Letícia Barros", "pouco_engajado"),
    ("henrique.cavalcanti", "Henrique Cavalcanti", "pouco_engajado"),
    ("natalia.souza", "Natália Souza", "pouco_engajado"),
    ("eduardo.guimaraes", "Eduardo Guimarães", "pouco_engajado"),
    # atrasado (2)
    ("yago.pereira", "Yago Pereira", "atrasado"),
    ("marina.tavares", "Marina Tavares", "atrasado"),
    # pendente_avaliacao (3): extras beyond the 45 profiles
    ("otavio.lins", "Otávio Lins", "pendente_avaliacao"),
    ("clara.mendes", "Clara Mendes", "pendente_avaliacao"),
    ("ricardo.vale", "Ricardo Vale", "pendente_avaliacao"),
]


def build_demo_students() -> list[DemoStudent]:
    students = [
        DemoStudent(
            email=f"{slug}@demo.certai.app",
            name=name,
            profile=profile,
        )
        for slug, name, profile in _RAW
    ]
    assert len(students) == 48
    counts = {
        "destaque": 7,
        "consistente": 11,
        "irregular": 11,
        "dificuldade": 7,
        "pouco_engajado": 7,
        "atrasado": 2,
        "pendente_avaliacao": 3,
    }
    for profile, expected in counts.items():
        actual = sum(1 for s in students if s.profile == profile)
        assert actual == expected, f"{profile}: {actual} != {expected}"
    return students
