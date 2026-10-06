import os

from agents import function_tool
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

client = OpenAI()

VECTOR_STORE_ID = os.environ["MOREIRA_VECTOR_STORE_ID"]


def texto_resultado(resultado) -> str:
    partes = []

    for parte in resultado.content:

        if getattr(parte, "type", None) == "text":
            partes.append(parte.text)

    return "\n".join(partes)


@function_tool
def buscar_documento(nome_arquivo: str) -> str:
    """
    Recupera trechos de um documento específico do Vector Store.

    Usado quando o usuário fornece o nome de um arquivo,
    e não uma referência de exercício.
    """

    nome_arquivo = nome_arquivo.strip()

    consultas = [
        nome_arquivo,
        f'"{nome_arquivo}"',
        "Statistics II P2",
        "Statistics II exam",
        "Question 1 Question 2 Question 3",
    ]

    resultados = {}

    for consulta in consultas:

        print(
            f"\nRealizando busca de documento: {consulta}"
        )

        busca = client.vector_stores.search(
            vector_store_id=VECTOR_STORE_ID,
            query=consulta,
            max_num_results=20,
            rewrite_query=False,
        )

        for resultado in busca.data:

            filename = (
                getattr(resultado, "filename", "")
                or ""
            )

            if filename.lower() != nome_arquivo.lower():
                continue

            texto = texto_resultado(resultado)

            chave = (
                resultado.file_id,
                texto[:1000],
            )

            if chave not in resultados:
                resultados[chave] = resultado

    resultados_ordenados = sorted(
        resultados.values(),
        key=lambda r: r.score,
        reverse=True,
    )

    resposta = []

    resposta.append(
        f"DOCUMENTO SOLICITADO: {nome_arquivo}"
    )

    resposta.append("")

    if not resultados_ordenados:

        resposta.append(
            "Nenhum trecho do documento solicitado "
            "foi recuperado."
        )

        return "\n".join(resposta)

    resposta.append(
        f"Foram recuperados "
        f"{len(resultados_ordenados)} trechos."
    )

    resposta.append("")

    for i, resultado in enumerate(
        resultados_ordenados,
        start=1,
    ):

        resposta.extend([
            f"--- TRECHO {i} ---",
            f"Arquivo: {resultado.filename}",
            f"Score: {resultado.score:.4f}",
            "",
            texto_resultado(resultado),
            "",
        ])

    return "\n".join(resposta)