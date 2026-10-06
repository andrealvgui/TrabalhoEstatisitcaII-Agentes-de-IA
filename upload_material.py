from adiciona_vector_store import upload_file


arquivos = [
    "materiais/gabaritos/gabarito_lecture_notes.pdf",
]


if __name__ == "__main__":
    for arquivo in arquivos:
        upload_file(arquivo)
