from pathlib import Path
from pypdf import PdfReader, PdfWriter


def combinar_pdfs(
    arquivos_pdf: list[Path],
    arquivo_saida: Path,
    max_paginas_por_resposta: int = 5,
) -> list[int]:
    """Combina exatamente 3 PDFs, validando o limite de páginas de cada resposta.

    Retorna a quantidade de páginas de cada PDF na ordem recebida.
    """
    if len(arquivos_pdf) != 3:
        raise ValueError(
            f"A prova bônus deve conter exatamente 3 respostas. "
            f"Foram recebidos {len(arquivos_pdf)} PDFs."
        )

    writer = PdfWriter()
    paginas_por_resposta: list[int] = []

    for numero, arquivo in enumerate(arquivos_pdf, start=1):
        arquivo = Path(arquivo)

        if not arquivo.exists():
            raise FileNotFoundError(
                f"PDF da Questão {numero} não encontrado: {arquivo}"
            )

        if arquivo.suffix.lower() != ".pdf":
            raise ValueError(
                f"A resposta da Questão {numero} não é um PDF: {arquivo}"
            )

        reader = PdfReader(str(arquivo))
        numero_paginas = len(reader.pages)

        if numero_paginas == 0:
            raise ValueError(
                f"O PDF da Questão {numero} está vazio: {arquivo}"
            )

        if numero_paginas > max_paginas_por_resposta:
            raise ValueError(
                f"A resposta da Questão {numero} possui {numero_paginas} páginas, "
                f"mas o limite é {max_paginas_por_resposta}."
            )

        paginas_por_resposta.append(numero_paginas)

        for pagina in reader.pages:
            writer.add_page(pagina)

    arquivo_saida = Path(arquivo_saida)
    arquivo_saida.parent.mkdir(parents=True, exist_ok=True)

    with arquivo_saida.open("wb") as arquivo:
        writer.write(arquivo)

    # Validação final do arquivo consolidado.
    reader_final = PdfReader(str(arquivo_saida))
    paginas_esperadas = sum(paginas_por_resposta)
    paginas_obtidas = len(reader_final.pages)

    if paginas_obtidas != paginas_esperadas:
        raise RuntimeError(
            "O PDF consolidado foi criado, mas o número de páginas não confere: "
            f"esperadas={paginas_esperadas}, obtidas={paginas_obtidas}."
        )

    return paginas_por_resposta
