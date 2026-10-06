import shutil
import subprocess
from pathlib import Path


def compilar_latex(
    arquivo_tex: str,
    pasta_saida: str,
) -> Path:

    tex_path = Path(arquivo_tex).resolve()
    output_dir = Path(pasta_saida).resolve()

    if not tex_path.exists():
        raise FileNotFoundError(
            f"Arquivo LaTeX não encontrado: {tex_path}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdflatex = shutil.which("pdflatex")

    if pdflatex is None:
        raise RuntimeError(
            "pdflatex não foi encontrado no PATH. "
            "Instale uma distribuição LaTeX, como MiKTeX ou TeX Live."
        )

    # Usa apenas o nome do arquivo como entrada para o LaTeX.
    # Isso evita que "\" do caminho do Windows seja interpretado
    # como comando TeX.
    nome_arquivo = tex_path.name

    comando = [
        pdflatex,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-output-directory",
        output_dir.as_posix(),
        nome_arquivo,
    ]

    # Executa a partir da pasta onde está o .tex.
    # Assim, o pdflatex recebe apenas "relatorio_xxx.tex".
    resultado = subprocess.run(
        comando,
        cwd=tex_path.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if resultado.returncode != 0:
        raise RuntimeError(
            "Erro ao compilar LaTeX:\n\n"
            + resultado.stdout
            + "\n"
            + resultado.stderr
        )

    # Segunda compilação para referências e elementos que possam
    # depender de mais de uma passagem.
    resultado = subprocess.run(
        comando,
        cwd=tex_path.parent,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if resultado.returncode != 0:
        raise RuntimeError(
            "Erro na segunda compilação LaTeX:\n\n"
            + resultado.stdout
            + "\n"
            + resultado.stderr
        )

    pdf_path = output_dir / f"{tex_path.stem}.pdf"

    if not pdf_path.exists():
        raise RuntimeError(
            f"LaTeX terminou sem gerar o PDF: {pdf_path}"
        )

    return pdf_path