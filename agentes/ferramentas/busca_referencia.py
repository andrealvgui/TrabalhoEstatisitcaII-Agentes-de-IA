import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from agents import function_tool
from pypdf import PdfReader


load_dotenv()

client = OpenAI()

VECTOR_STORE_ID = os.environ["MOREIRA_VECTOR_STORE_ID"]

PASTA_MATERIAIS = Path("materiais")


# ============================================================
# PARSE DA REFERÊNCIA
# ============================================================

def extrair_referencia(referencia: str):
    """
    Converte referências como:

        7.11(b)
        7.11
        16.22(a)

    em:

        ("7.11", "b")
        ("7.11", None)
        ("16.22", "a")
    """

    referencia = referencia.strip()

    match = re.search(
        r"(?<!\d)(\d+)\.(\d+)"
        r"(?:\(\s*([a-zA-Z])\s*\))?",
        referencia,
    )

    if not match:
        return referencia, None

    secao, exercicio, subitem = match.groups()

    referencia_base = f"{secao}.{exercicio}"

    if subitem:
        return referencia_base, subitem.lower()

    return referencia_base, None


# ============================================================
# NORMALIZAÇÃO DE TEXTO
# ============================================================

def normalizar_texto(texto: str) -> str:
    """
    Normaliza espaços e alguns caracteres comuns de PDFs
    para facilitar a busca textual.
    """

    texto = texto.replace("\xa0", " ")

    texto = texto.replace(
        "\u00ad",
        "",
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


def normalizar_para_busca(texto: str) -> str:
    """
    Normalização mais agressiva para comparação.
    """

    texto = texto.lower()

    texto = texto.replace(
        "\u2212",
        "-",
    )

    texto = texto.replace(
        "–",
        "-",
    )

    texto = texto.replace(
        "—",
        "-",
    )

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto.strip()


# ============================================================
# EXTRAÇÃO DE TEXTO DE PDF
# ============================================================

def extrair_texto_pdf(caminho: Path) -> str:
    """
    Extrai o texto completo de um PDF.
    """

    leitor = PdfReader(str(caminho))

    partes = []

    for numero_pagina, pagina in enumerate(
        leitor.pages,
        start=1,
    ):

        texto = pagina.extract_text() or ""

        partes.append(
            f"\n--- PÁGINA {numero_pagina} ---\n"
        )

        partes.append(texto)

    return "\n".join(partes)


# ============================================================
# LOCALIZAÇÃO DOS PDFs
# ============================================================

def encontrar_pdfs() -> list[Path]:

    if not PASTA_MATERIAIS.exists():
        return []

    return sorted(
        [
            caminho
            for caminho in PASTA_MATERIAIS.rglob("*")
            if caminho.is_file()
            and caminho.suffix.lower() == ".pdf"
        ]
    )


# ============================================================
# IDENTIFICAÇÃO EXATA DE UM EXERCÍCIO
# ============================================================

def localizar_exercicio_no_texto(
    texto: str,
    referencia_base: str,
):
    """
    Tenta localizar uma questão usando diferentes formatos
    possíveis nos materiais.

    Exemplo:
        7.11
    pode aparecer como:
        7. [7, 11]
        7. [7,11]
        7. [7 , 11]
    """

    secao, exercicio = referencia_base.split(".")

    texto_busca = normalizar_para_busca(texto)

    padroes = [
        # Formato do Moreira:
        # 7. [7, 11]
        rf"\b{re.escape(secao)}\.\s*\[\s*"
        rf"{re.escape(secao)}\s*,\s*"
        rf"{re.escape(exercicio)}\s*\]",

        # Possível formato:
        # 7.11
        rf"\b{re.escape(referencia_base)}\b",
    ]

    for padrao in padroes:

        match = re.search(
            padrao,
            texto_busca,
        )

        if match:
            return match.start()

    return None


# ============================================================
# EXTRAÇÃO DE UM EXERCÍCIO COMPLETO
# ============================================================

def extrair_exercicio(
    texto: str,
    referencia_base: str,
):
    """
    Localiza o exercício solicitado e tenta extrair seu texto
    até o início do próximo exercício numerado.

    Importante:
    essa função não resolve o exercício.
    """

    texto_original = texto

    posicao = localizar_exercicio_no_texto(
        texto_original,
        referencia_base,
    )

    if posicao is None:
        return None

    resto = texto_original[posicao:]

    # Tentamos identificar o próximo exercício.
    #
    # Exemplos possíveis:
    # 8.
    # 9. [7, 14]
    #
    # Não usamos simplesmente qualquer número porque isso
    # poderia capturar números dentro das fórmulas.

    padrao_proximo_exercicio = re.compile(
        r"\n\s*\d+\.\s*(?:\[\s*\d+\s*,\s*\d+\s*\])?",
        flags=re.IGNORECASE,
    )

    matches = list(
        padrao_proximo_exercicio.finditer(
            resto[1:]
        )
    )

    if matches:

        fim = 1 + matches[0].start()

        bloco = resto[:fim]

    else:

        bloco = resto

    bloco = bloco.strip()

    return bloco


# ============================================================
# LOCALIZAR EXERCÍCIO COMPLETO NOS MATERIAIS
# ============================================================

def buscar_exercicio_local(
    referencia_base: str,
    nome_subitem: str | None,
):
    """
    Procura primeiro diretamente nos PDFs locais.

    Retorna uma lista de candidatos.
    """

    candidatos = []

    pdfs = encontrar_pdfs()

    print(
        f"\nDEBUG - PDFs locais encontrados: {len(pdfs)}"
    )

    for caminho in pdfs:

        try:

            texto = extrair_texto_pdf(caminho)

        except Exception as erro:

            print(
                f"Erro lendo {caminho}: {erro}"
            )

            continue

        exercicio = extrair_exercicio(
            texto,
            referencia_base,
        )

        if not exercicio:
            continue

        candidatos.append(
            {
                "arquivo": caminho.name,
                "caminho": str(caminho),
                "texto": exercicio,
            }
        )

    return candidatos


# ============================================================
# SELECIONAR SUBITEM
# ============================================================

def extrair_subitem(
    texto_exercicio: str,
    subitem: str,
):
    """
    Extrai o subitem solicitado de um exercício.

    Exemplo:

        (a) ...
        (b) ...
        (c) ...

    Se solicitado "b", retorna apenas o bloco de (b).
    """

    texto = texto_exercicio

    # Procura explicitamente:
    #
    # (b)
    # (b)
    # ( B )
    #
    padrao_inicio = re.compile(
        rf"\(\s*{re.escape(subitem)}\s*\)",
        flags=re.IGNORECASE,
    )

    match_inicio = padrao_inicio.search(
        texto
    )

    if match_inicio is None:
        return None

    inicio = match_inicio.start()

    resto = texto[inicio:]

    # Próximo subitem:
    #
    # (c)
    # (d)
    #
    padrao_proximo = re.compile(
        r"\(\s*[a-zA-Z]\s*\)"
    )

    match_proximo = padrao_proximo.search(
        resto[len(match_inicio.group()):]
    )

    if match_proximo is not None:

        deslocamento = (
            len(match_inicio.group())
            + match_proximo.start()
        )

        bloco = resto[:deslocamento]

    else:

        bloco = resto

    return bloco.strip()


# ============================================================
# TEXTO DO RESULTADO DO VECTOR STORE
# ============================================================

def texto_resultado(resultado) -> str:

    partes = []

    for parte in resultado.content:

        if getattr(parte, "type", None) == "text":

            partes.append(
                parte.text
            )

    return "\n".join(partes)


# ============================================================
# BUSCA NO VECTOR STORE
# ============================================================

def executar_busca(
    consultas,
    max_num_results=5,
):

    resultados = {}

    for consulta in consultas:

        print(
            f"\nRealizando busca: {consulta}"
        )

        try:

            busca = client.vector_stores.search(
                vector_store_id=VECTOR_STORE_ID,
                query=consulta,
                max_num_results=max_num_results,
                rewrite_query=False,
            )

        except Exception as erro:

            print(
                f"Erro na busca: {erro}"
            )

            continue

        for resultado in busca.data:

            texto = texto_resultado(
                resultado
            )

            chave = (
                resultado.file_id,
                texto[:500],
            )

            if chave not in resultados:

                resultados[chave] = resultado

    return sorted(
        resultados.values(),
        key=lambda r: r.score,
        reverse=True,
    )


# ============================================================
# FILTRAGEM POR SUBITEM
# ============================================================

def candidato_tem_subitem(
    texto: str,
    subitem: str,
) -> bool:

    padrao = re.compile(
        rf"\(\s*{re.escape(subitem)}\s*\)",
        flags=re.IGNORECASE,
    )

    return (
        padrao.search(texto)
        is not None
    )


# ============================================================
# TOOL PRINCIPAL
# ============================================================

@function_tool
def buscar_referencia(
    referencia: str,
) -> str:

    referencia_original = referencia

    referencia_base, subitem = (
        extrair_referencia(
            referencia
        )
    )

    print("\n" + "=" * 80)
    print("DEBUG - BUSCA DE REFERÊNCIA")
    print(
        f"Referência recebida: "
        f"'{referencia_original}'"
    )
    print(
        f"Referência base: "
        f"'{referencia_base}'"
    )
    print(
        f"Subitem solicitado: "
        f"'{subitem}'"
    )
    print("=" * 80)

    # ========================================================
    # 1. PRIMEIRA TENTATIVA:
    #    BUSCA DIRETA NOS PDFs LOCAIS
    # ========================================================

    candidatos_locais = (
        buscar_exercicio_local(
            referencia_base,
            subitem,
        )
    )

    candidatos_validos = []

    for candidato in candidatos_locais:

        texto_exercicio = candidato["texto"]

        if subitem is not None:

            texto_subitem = extrair_subitem(
                texto_exercicio,
                subitem,
            )

            if texto_subitem is None:

                continue

            candidato = {
                **candidato,
                "texto": texto_subitem,
            }

        candidatos_validos.append(
            candidato
        )

    # ========================================================
    # Se encontrou exatamente um candidato local
    # ========================================================

    if len(candidatos_validos) == 1:

        candidato = candidatos_validos[0]

        print(
            "\nDEBUG - EXERCÍCIO ENCONTRADO "
            "DIRETAMENTE NO PDF LOCAL"
        )

        print(
            f"Arquivo: {candidato['arquivo']}"
        )

        print(
            f"Referência: {referencia_base}"
            + (
                f"({subitem})"
                if subitem
                else ""
            )
        )

        return (
            "REFERÊNCIA IDENTIFICADA COM "
            "BUSCA DIRETA NO MATERIAL LOCAL\n\n"
            f"Referência: {referencia_base}"
            + (
                f"({subitem})"
                if subitem
                else ""
            )
            + "\n"
            f"Arquivo: {candidato['arquivo']}\n"
            f"Caminho: {candidato['caminho']}\n\n"
            "ENUNCIADO RECUPERADO:\n"
            "==================================================\n"
            f"{candidato['texto']}\n"
            "=================================================="
        )

    # ========================================================
    # Se encontrou vários candidatos locais
    # ========================================================

    if len(candidatos_validos) > 1:

        print(
            "\nDEBUG - MÚLTIPLOS CANDIDATOS "
            "ENCONTRADOS NO MATERIAL LOCAL"
        )

        partes = []

        for i, candidato in enumerate(
            candidatos_validos,
            start=1,
        ):

            partes.append(
                f"\nCANDIDATO {i}\n"
                f"Arquivo: {candidato['arquivo']}\n"
                f"Caminho: {candidato['caminho']}\n\n"
                f"{candidato['texto']}"
            )

        return (
            "Foram encontrados múltiplos candidatos "
            f"para a referência {referencia_base}"
            + (
                f"({subitem})"
                if subitem
                else ""
            )
            + ".\n\n"
            + "\n".join(partes)
            + "\n\n"
            "IMPORTANTE: não escolha arbitrariamente "
            "entre os candidatos."
        )

    # ========================================================
    # 2. FALLBACK:
    #    VECTOR STORE
    # ========================================================

    print(
        "\nDEBUG - BUSCA LOCAL NÃO FOI SUFICIENTE."
    )

    consultas_principais = [
        referencia_base,
        f"exercise {referencia_base}",
        f"problem {referencia_base}",
    ]

    if subitem is not None:

        consultas_principais.extend(
            [
                f"{referencia_base}({subitem})",
                f"{referencia_base} item {subitem}",
                f"exercise {referencia_base}({subitem})",
                f"problem {referencia_base}({subitem})",
            ]
        )

    candidatos_principais = executar_busca(
        consultas_principais,
        max_num_results=10,
    )

    # ========================================================
    # FILTRAGEM DOS RESULTADOS
    # ========================================================

    candidatos_filtrados = []

    for resultado in candidatos_principais:

        texto = texto_resultado(
            resultado
        )

        texto_normalizado = (
            normalizar_para_busca(texto)
        )

        referencia_normalizada = (
            normalizar_para_busca(
                referencia_base
            )
        )

        tem_referencia = (
            referencia_normalizada
            in texto_normalizado
        )

        if not tem_referencia:

            # O formato pode ser:
            # 7. [7, 11]
            secao, exercicio = (
                referencia_base.split(".")
            )

            padrao_moreira = (
                rf"\b{re.escape(secao)}\."
                rf"\s*\[\s*"
                rf"{re.escape(secao)}"
                rf"\s*,\s*"
                rf"{re.escape(exercicio)}"
                rf"\s*\]"
            )

            tem_referencia = (
                re.search(
                    padrao_moreira,
                    texto_normalizado,
                )
                is not None
            )

        if not tem_referencia:
            continue

        if subitem is not None:

            if not candidato_tem_subitem(
                texto,
                subitem,
            ):
                continue

        candidatos_filtrados.append(
            resultado
        )

    # ========================================================
    # 3. GABARITO
    # ========================================================

    consultas_gabarito = [
        f"gabarito {referencia_base}",
        f"solução {referencia_base}",
    ]

    if subitem is not None:

        consultas_gabarito.extend(
            [
                f"gabarito {referencia_base}({subitem})",
                f"solução {referencia_base}({subitem})",
            ]
        )

    candidatos_gabarito_brutos = (
        executar_busca(
            consultas_gabarito,
            max_num_results=10,
        )
    )

    candidatos_gabarito = []

    for resultado in candidatos_gabarito_brutos:

        filename = (
            getattr(
                resultado,
                "filename",
                ""
            )
            or ""
        )

        filename_lower = (
            filename.lower()
        )

        if "gabarito" not in filename_lower:
            continue

        texto = texto_resultado(
            resultado
        )

        if subitem is not None:

            if not candidato_tem_subitem(
                texto,
                subitem,
            ):
                continue

        candidatos_gabarito.append(
            resultado
        )

    # ========================================================
    # 4. CONSTRUÇÃO DO RESULTADO
    # ========================================================

    partes = []

    partes.append(
        "REFERÊNCIA SOLICITADA"
    )

    partes.append(
        "=================================================="
    )

    partes.append(
        f"Referência original: "
        f"{referencia_original}"
    )

    partes.append(
        f"Referência base: "
        f"{referencia_base}"
    )

    partes.append(
        "Subitem: "
        + (
            subitem
            if subitem
            else "nenhum"
        )
    )

    partes.append(
        "\nRESULTADOS DA BUSCA NO MATERIAL"
    )

    partes.append(
        "=================================================="
    )

    if not candidatos_filtrados:

        partes.append(
            "Nenhum resultado do Vector Store "
            "foi validado por referência exata."
        )

    else:

        for i, resultado in enumerate(
            candidatos_filtrados[:5],
            start=1,
        ):

            filename = (
                getattr(
                    resultado,
                    "filename",
                    ""
                )
                or ""
            )

            texto = texto_resultado(
                resultado
            )

            partes.append(
                f"\nRESULTADO {i}\n"
                f"Arquivo: {filename}\n"
                f"Score: {resultado.score}\n"
                "--------------------------------------------------\n"
                f"{texto}\n"
            )

    # ========================================================
    # GABARITO
    # ========================================================

    partes.append(
        "\nRESULTADOS DE GABARITO"
    )

    partes.append(
        "=================================================="
    )

    if not candidatos_gabarito:

        partes.append(
            "Nenhum gabarito específico foi "
            "validado para essa referência."
        )

    else:

        for i, resultado in enumerate(
            candidatos_gabarito[:3],
            start=1,
        ):

            filename = (
                getattr(
                    resultado,
                    "filename",
                    ""
                )
                or ""
            )

            texto = texto_resultado(
                resultado
            )

            partes.append(
                f"\nGABARITO {i}\n"
                f"Arquivo: {filename}\n"
                f"Score: {resultado.score}\n"
                "--------------------------------------------------\n"
                f"{texto}\n"
            )

    # ========================================================
    # INSTRUÇÃO ANTI-HALLUCINAÇÃO
    # ========================================================

    partes.append(
        """
==================================================
INSTRUÇÕES IMPORTANTES AO LÍDER
==================================================

A referência solicitada deve ser tratada como:

    """
        + referencia_base
        + (
            f"({subitem})"
            if subitem
            else ""
        )
        + """

Não confunda:

- número da questão;
- referência entre colchetes;
- número de página;
- número de seção;
- referências cruzadas;
- outro exercício semanticamente parecido.

Se foi solicitado um subitem específico, por exemplo (b),
utilize somente o subitem (b) da questão identificada.

Não invente ou reconstrua o enunciado a partir da memória.

Se os resultados recuperados forem insuficientes para confirmar
a questão ou o subitem solicitado, declare explicitamente que
a identificação não pôde ser confirmada.
"""
    )

    resultado_final = "\n".join(
        partes
    )

    print(
        "\nDEBUG - BUSCA FINALIZADA"
    )

    return resultado_final