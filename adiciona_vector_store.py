import os
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()


PASTA_MATERIAIS = Path("materiais")

EXTENSOES_PERMITIDAS = {
    ".pdf",
    ".txt",
    ".md",
}


def obter_vector_store_id() -> str:
    vector_store_id = os.getenv("MOREIRA_VECTOR_STORE_ID")

    if not vector_store_id:
        raise ValueError(
            "MOREIRA_VECTOR_STORE_ID não foi encontrado no arquivo .env."
        )

    return vector_store_id


def encontrar_materiais() -> list[Path]:
    """
    Percorre recursivamente materiais/ e encontra
    todos os arquivos acadêmicos relevantes.
    """

    if not PASTA_MATERIAIS.exists():
        raise FileNotFoundError(
            f"A pasta {PASTA_MATERIAIS.resolve()} não existe."
        )

    arquivos = []

    for arquivo in PASTA_MATERIAIS.rglob("*"):

        if not arquivo.is_file():
            continue

        if arquivo.suffix.lower() not in EXTENSOES_PERMITIDAS:
            continue

        arquivos.append(arquivo)

    return sorted(arquivos)


def nome_normalizado(nome: str) -> str:
    """
    Normaliza o nome para comparação.

    Exemplo:
        aula_1.PDF -> aula_1.pdf
    """

    return nome.lower()


def arquivos_ja_no_vector_store(
    client: OpenAI,
    vector_store_id: str,
) -> set[str]:
    """
    Obtém os nomes dos arquivos que já estão
    no Vector Store, ignorando diferença entre
    maiúsculas e minúsculas.
    """

    existentes = set()

    pagina = client.vector_stores.files.list(
        vector_store_id=vector_store_id,
        limit=100,
    )

    for arquivo_vs in pagina.data:

        try:

            arquivo = client.files.retrieve(
                arquivo_vs.id
            )

            existentes.add(
                nome_normalizado(arquivo.filename)
            )

        except Exception as erro:

            print(
                f"Aviso: não foi possível identificar "
                f"o arquivo {arquivo_vs.id}: {erro}"
            )

    return existentes


def preparar_arquivo_para_upload(
    caminho: Path,
) -> tuple[Path, str | None]:

    """
    Se a extensão já estiver em minúsculo, usa
    o arquivo original.

    Se estiver em maiúsculo, cria uma cópia temporária
    com extensão minúscula.

    Retorna:
        caminho_para_upload
        diretorio_temporario
    """

    if caminho.suffix == caminho.suffix.lower():

        return caminho, None

    diretorio_temporario = tempfile.mkdtemp(
        prefix="moreira_upload_"
    )

    novo_nome = caminho.stem + caminho.suffix.lower()

    copia = Path(diretorio_temporario) / novo_nome

    shutil.copy2(
        caminho,
        copia,
    )

    return copia, diretorio_temporario


def enviar_arquivo(
    client: OpenAI,
    vector_store_id: str,
    caminho: Path,
) -> None:

    print("\n" + "=" * 70)
    print("ENVIANDO ARQUIVO")
    print("=" * 70)

    print(f"Arquivo original: {caminho}")

    caminho_upload, diretorio_temporario = (
        preparar_arquivo_para_upload(caminho)
    )

    try:

        print(
            f"Arquivo enviado:  {caminho_upload.name}"
        )

        with caminho_upload.open("rb") as arquivo:

            resultado = client.vector_stores.files.upload_and_poll(
                vector_store_id=vector_store_id,
                file=arquivo,
            )

        print(
            f"Status: {resultado.status}"
        )

        if resultado.status != "completed":

            print(
                f"Atenção: processamento terminou com "
                f"status {resultado.status}."
            )

    finally:

        if diretorio_temporario is not None:

            shutil.rmtree(
                diretorio_temporario,
                ignore_errors=True,
            )


def main():

    client = OpenAI()

    vector_store_id = obter_vector_store_id()

    print("=" * 70)
    print("BASE DE CONHECIMENTO — MOREIRA")
    print("=" * 70)

    # --------------------------------------------------
    # 1. Encontrar todos os materiais
    # --------------------------------------------------

    materiais = encontrar_materiais()

    print(
        f"\nTotal de arquivos encontrados em "
        f"materiais/: {len(materiais)}"
    )

    for arquivo in materiais:

        print(
            f"  - {arquivo.relative_to(PASTA_MATERIAIS)}"
        )

    # --------------------------------------------------
    # 2. Verificar arquivos existentes
    # --------------------------------------------------

    print(
        "\nVerificando arquivos já enviados..."
    )

    existentes = arquivos_ja_no_vector_store(
        client,
        vector_store_id,
    )

    print(
        f"Arquivos já presentes no Vector Store: "
        f"{len(existentes)}"
    )

    # --------------------------------------------------
    # 3. Selecionar arquivos novos
    # --------------------------------------------------

    novos = []

    for arquivo in materiais:

        nome = nome_normalizado(
            arquivo.name
        )

        if nome not in existentes:

            novos.append(arquivo)

    print(
        f"Arquivos novos a enviar: {len(novos)}"
    )

    # --------------------------------------------------
    # 4. Upload
    # --------------------------------------------------

    if not novos:

        print(
            "\nTodos os materiais encontrados "
            "já estão no Vector Store."
        )

        return

    sucessos = 0
    erros = 0

    for arquivo in novos:

        try:

            enviar_arquivo(
                client=client,
                vector_store_id=vector_store_id,
                caminho=arquivo,
            )

            sucessos += 1

        except Exception as erro:

            erros += 1

            print(
                "\nERRO AO ENVIAR"
            )

            print(
                f"Arquivo: {arquivo}"
            )

            print(
                f"Erro: {erro}"
            )

    # --------------------------------------------------
    # 5. Resumo
    # --------------------------------------------------

    print(
        "\n" + "=" * 70
    )

    print(
        "RESUMO"
    )

    print(
        "=" * 70
    )

    print(
        f"Encontrados: {len(materiais)}"
    )

    print(
        f"Enviados:    {sucessos}"
    )

    print(
        f"Erros:       {erros}"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()