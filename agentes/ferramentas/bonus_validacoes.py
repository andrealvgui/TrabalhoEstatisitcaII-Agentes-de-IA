from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader


@dataclass(frozen=True)
class MembroGrupo:
    nome: str
    id_epge: str


@dataclass(frozen=True)
class DadosGrupo:
    identificador: str
    membros: tuple[MembroGrupo, MembroGrupo, MembroGrupo]


def ler_campo_obrigatorio(prompt: str) -> str:
    """Lê um campo textual e impede entrada vazia."""
    while True:
        valor = input(prompt).strip()
        if valor:
            return valor
        print("Este campo é obrigatório. Digite um valor.\n")


def ler_dados_grupo() -> DadosGrupo:
    """Coleta os dados do grupo exigidos pela prova bônus."""
    print("\n" + "=" * 70)
    print("DADOS DO GRUPO")
    print("=" * 70)

    identificador = ler_campo_obrigatorio("Identificador do grupo: ")

    membros = []
    for numero in range(1, 4):
        print(f"\nMembro {numero}")
        nome = ler_campo_obrigatorio("Nome completo: ")
        id_epge = ler_campo_obrigatorio("FGV/EPGE ID: ")
        membros.append(MembroGrupo(nome=nome, id_epge=id_epge))

    return DadosGrupo(
        identificador=identificador,
        membros=tuple(membros),
    )


def validar_pdf_resposta(
    arquivo_pdf: Path,
    numero_questao: int,
    max_paginas: int = 5,
) -> int:
    """Valida existência, formato e número máximo de páginas de uma resposta."""
    arquivo_pdf = Path(arquivo_pdf)

    if not arquivo_pdf.exists():
        raise FileNotFoundError(
            f"PDF da Questão {numero_questao} não foi encontrado: {arquivo_pdf}"
        )

    if arquivo_pdf.suffix.lower() != ".pdf":
        raise ValueError(
            f"O arquivo da Questão {numero_questao} não possui extensão .pdf: {arquivo_pdf}"
        )

    reader = PdfReader(str(arquivo_pdf))
    paginas = len(reader.pages)

    if paginas == 0:
        raise ValueError(
            f"O PDF da Questão {numero_questao} está vazio: {arquivo_pdf}"
        )

    if paginas > max_paginas:
        raise ValueError(
            f"A Questão {numero_questao} possui {paginas} páginas; "
            f"o limite é {max_paginas}."
        )

    return paginas


def validar_saida_bonus(
    arquivos_pdf: Iterable[Path],
    arquivo_final: Path,
    max_paginas_por_resposta: int = 5,
) -> list[int]:
    """Validação final antes da entrega do PDF consolidado."""
    arquivos = [Path(a) for a in arquivos_pdf]

    if len(arquivos) != 3:
        raise ValueError(
            f"A prova bônus exige 3 PDFs individuais; foram encontrados {len(arquivos)}."
        )

    paginas = [
        validar_pdf_resposta(
            arquivo_pdf=arquivo,
            numero_questao=numero,
            max_paginas=max_paginas_por_resposta,
        )
        for numero, arquivo in enumerate(arquivos, start=1)
    ]

    arquivo_final = Path(arquivo_final)
    if not arquivo_final.exists():
        raise FileNotFoundError(
            f"PDF final consolidado não foi encontrado: {arquivo_final}"
        )

    reader_final = PdfReader(str(arquivo_final))
    paginas_finais = len(reader_final.pages)
    paginas_esperadas = sum(paginas)

    if paginas_finais != paginas_esperadas:
        raise RuntimeError(
            "O PDF final não contém a quantidade esperada de páginas: "
            f"esperadas={paginas_esperadas}, obtidas={paginas_finais}."
        )

    return paginas
