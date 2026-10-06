from pathlib import Path

from agents import function_tool
from pypdf import PdfReader


PASTA_MATERIAIS = Path("materiais")


def localizar_arquivo(nome_arquivo: str) -> Path:
    """
    Procura um arquivo pelo nome dentro de materiais/,
    ignorando diferenças entre maiúsculas e minúsculas.
    """

    nome_arquivo = nome_arquivo.strip().lower()

    candidatos = [
        caminho
        for caminho in PASTA_MATERIAIS.rglob("*")
        if caminho.is_file()
        and caminho.name.lower() == nome_arquivo
    ]

    if not candidatos:
        raise FileNotFoundError(
            f"Arquivo '{nome_arquivo}' não foi encontrado "
            f"dentro de {PASTA_MATERIAIS.resolve()}."
        )

    if len(candidatos) > 1:
        caminhos = "\n".join(
            f"- {caminho}"
            for caminho in candidatos
        )

        raise RuntimeError(
            "Mais de um arquivo com esse nome foi encontrado:\n"
            + caminhos
        )

    return candidatos[0]


@function_tool
def ler_documento_completo(nome_arquivo: str) -> str:
    """
    Lê integralmente um PDF local, página por página,
    preservando a ordem do documento.
    """

    caminho = localizar_arquivo(nome_arquivo)

    print(f"Arquivo encontrado: {caminho}")

    try:
        leitor = PdfReader(str(caminho))
    except Exception as erro:
        raise RuntimeError(
            f"Não foi possível abrir o PDF '{caminho}': {erro}"
        ) from erro

    numero_paginas = len(leitor.pages)

    print(
        f"Número de páginas: {numero_paginas}"
    )

    partes = []

    partes.append(
        f"DOCUMENTO: {caminho.name}"
    )

    partes.append(
        f"CAMINHO: {caminho}"
    )

    partes.append(
        f"NÚMERO DE PÁGINAS: {numero_paginas}"
    )

    partes.append("")

    for numero_pagina, pagina in enumerate(
        leitor.pages,
        start=1,
    ):

        try:
            texto = pagina.extract_text()
        except Exception as erro:
            texto = ""

            print(
                f"Aviso: erro ao extrair "
                f"a página {numero_pagina}: {erro}"
            )

        if texto is None:
            texto = ""

        texto = texto.strip()

        partes.append(
            "=" * 60
        )

        partes.append(
            f"PÁGINA {numero_pagina} DE {numero_paginas}"
        )

        partes.append(
            "=" * 60
        )

        if texto:
            partes.append(texto)
        else:
            partes.append(
                "[Nenhum texto foi extraído desta página.]"
            )

        partes.append("")

    resultado = "\n".join(partes)

    print(
        f"Texto extraído: {len(resultado)} caracteres"
    )

    return resultado