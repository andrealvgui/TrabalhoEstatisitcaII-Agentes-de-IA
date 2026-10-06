import asyncio
import re
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader
from agents import Runner

from agentes.lider import lider
from agentes.revisor import revisor
from agentes.relatorio import relatorio

from agentes.ferramentas.compilar_latex import (
    compilar_latex,
)

from agentes.ferramentas.combinar_pdfs import (
    combinar_pdfs,
)
from agentes.ferramentas.bonus_validacoes import (
    ler_dados_grupo as ler_dados_grupo_validado,
    validar_saida_bonus,
)


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def tarefa_e_apenas_identificacao(
    mensagem: str,
) -> bool:

    texto = mensagem.lower()

    palavras_identificacao = [
        "identifique",
        "identificar",
        "reproduza",
        "reproduzir",
        "liste",
        "listar",
        "estrutura",
        "enunciado",
    ]

    frases_nao_resolver = [
        "não resolva",
        "nao resolva",
        "não quero resolução",
        "nao quero resolucao",
        "não quero que resolva",
        "nao quero que resolva",
        "apenas identifique",
        "somente identifique",
        "não resolva nenhuma questão",
        "nao resolva nenhuma questao",
    ]

    tem_identificacao = any(
        palavra in texto
        for palavra in palavras_identificacao
    )

    tem_bloqueio = any(
        frase in texto
        for frase in frases_nao_resolver
    )

    return (
        tem_identificacao
        and tem_bloqueio
    )


def limitar_texto(
    texto: str,
    limite: int,
) -> str:

    if len(texto) <= limite:
        return texto

    return (
        texto[:limite]
        + "\n\n[CONTEÚDO TRUNCADO]"
    )


def ler_pergunta() -> str:

    print("Digite sua pergunta.")
    print(
        "Você pode usar várias linhas e linhas vazias."
    )
    print(
        "Quando terminar, digite /enviar e pressione Enter.\n"
    )

    linhas = []

    while True:

        linha = input()

        if linha.strip().lower() == "/enviar":
            break

        linhas.append(linha)

    pergunta = "\n".join(
        linhas
    ).strip()

    if not pergunta:
        raise ValueError(
            "A pergunta não pode estar vazia."
        )

    return pergunta


def ler_dados_grupo():
    """
    Coleta e valida os dados do grupo usando a ferramenta
    de validação específica da prova bônus.
    """
    dados = ler_dados_grupo_validado()

    # Mantemos o formato de dicionário utilizado pelo
    # restante deste arquivo.
    return {
        "grupo": dados.identificador,
        "membros": [
            {
                "nome": membro.nome,
                "fgv_id": membro.id_epge,
            }
            for membro in dados.membros
        ],
    }


def formatar_dados_grupo(
    dados_grupo,
) -> str:

    linhas = [
        f"Grupo: {dados_grupo['grupo']}",
        "",
        "Membros:",
    ]

    for membro in dados_grupo[
        "membros"
    ]:

        linhas.append(
            f"- {membro['nome']} "
            f"— FGV/EPGE ID: "
            f"{membro['fgv_id']}"
        )

    return "\n".join(
        linhas
    )


def parecer_exige_segunda_revisao(parecer: str) -> bool:
    """
    Determina se o parecer do primeiro Reviewer exige uma nova revisão.

    O teste prioriza a linha STATUS. Se o Reviewer usar uma variação
    inesperada do formato, há um fallback conservador para indicações
    explícitas de problemas.
    """
    texto = parecer.strip()

    match = re.search(
        r"STATUS\s*:\s*([^\n\r]+)",
        texto,
        flags=re.IGNORECASE,
    )

    if match:
        status = match.group(1).strip().upper()
        status_sem_acentos = (
            status
            .replace("Á", "A")
            .replace("À", "A")
            .replace("Ã", "A")
            .replace("Â", "A")
            .replace("É", "E")
            .replace("Ê", "E")
            .replace("Í", "I")
            .replace("Ó", "O")
            .replace("Ô", "O")
            .replace("Õ", "O")
            .replace("Ú", "U")
            .replace("Ç", "C")
        )

        if "SEM ERROS RELEVANTES" in status_sem_acentos:
            return False

        if (
            "REVISAO NECESSARIA" in status_sem_acentos
            or "REVISAR" in status_sem_acentos
            or "REVISAO" == status_sem_acentos
        ):
            return True

    # Fallback conservador: só aciona a segunda revisão quando houver
    # uma classificação explícita de problema no corpo do parecer.
    padroes_problema = [
        r"\[\s*CR[IÍ]TICO\s*\]",
        r"\[\s*IMPORTANTE\s*\]",
        r"\[\s*MENOR\s*\]",
        r"\bCR[IÍ]TICO\b",
        r"\bIMPORTANTE\b",
        r"\bMENOR\b",
    ]

    return any(
        re.search(padrao, texto, flags=re.IGNORECASE)
        for padrao in padroes_problema
    )


def arquivo_prova_existe(
    nome_arquivo: str,
) -> Path:

    pasta = Path(
        "materiais/provas"
    )

    caminho = pasta / nome_arquivo

    if caminho.suffix.lower() != ".pdf":
        raise ValueError(
            f"O arquivo informado não é um PDF: {caminho}"
        )

    if not caminho.exists():

        raise FileNotFoundError(
            f"O arquivo não foi encontrado:\n"
            f"{caminho}\n\n"
            f"Coloque o PDF da prova em "
            f"materiais/provas/"
        )

    return caminho


# ============================================================
# IDENTIFICAÇÃO
# ============================================================

async def modo_identificacao(
    pergunta: str,
):

    print(
        "\n[Identificando documento...]\n"
    )

    prompt_identificacao = f"""
Você é o Tutor Líder de Estatística II.

O usuário deseja SOMENTE identificar e reproduzir
o conteúdo do documento solicitado.

Não resolva nenhuma questão.

Não apresente:

- cálculos;
- provas;
- respostas aos itens;
- soluções;
- argumentos matemáticos.

Use obrigatoriamente a ferramenta
ler_documento_completo para ler o documento inteiro.

Depois de ler todas as páginas:

1. identifique o nome do documento;
2. identifique o número de páginas;
3. identifique todas as questões;
4. identifique todos os subitens;
5. conte corretamente o número total de itens;
6. reproduza os enunciados completos;
7. preserve exatamente a numeração do documento.

IMPORTANTE:

- Não confunda números de página com números de questões.
- Não confunda referências cruzadas com a numeração das questões.
- Leia todas as páginas antes de concluir que algo está ausente.
- Não use conhecimento externo.
- Não complete lacunas de memória.

Pergunta do usuário:

{pergunta}
"""

    resultado = await Runner.run(
        lider,
        prompt_identificacao,
    )

    print(
        "\nIdentificação da prova:\n"
    )

    print(
        resultado.final_output
    )


# ============================================================
# UMA QUESTÃO DO BÔNUS
# ============================================================

async def resolver_questao_bonus(
    numero_questao: int,
    nome_arquivo: str,
):

    # ========================================================
    # 1. LÍDER — RASCUNHO
    # ========================================================

    print(
        f"\n[Questão {numero_questao}] "
        f"[1/4] Líder elaborando solução..."
    )

    prompt_lider = f"""
Você é o Tutor Líder de Estatística II.

A prova está no arquivo:

    {nome_arquivo}

Use obrigatoriamente a ferramenta
ler_documento_completo para consultar o PDF.

Leia todas as páginas antes de resolver.

Sua tarefa nesta execução é resolver SOMENTE:

    QUESTÃO {numero_questao}

Não resolva as outras questões.

O enunciado do PDF é a fonte canônica da questão.

Preserve exatamente:

- a numeração;
- os subitens;
- a notação;
- as hipóteses do enunciado.

IMPORTANTE:

Cada questão é independente.

Não carregue hipóteses de outras questões.

Para a questão atual:

1. identifique as hipóteses explícitas;
2. identifique os teoremas utilizados;
3. verifique suas hipóteses;
4. desenvolva a solução passo a passo;
5. se o enunciado estiver incorreto ou incompleto,
   identifique isso explicitamente;
6. se uma conclusão depender de uma hipótese adicional,
   deixe isso claramente indicado;
7. não invente informações.

A resposta será utilizada em uma prova oral.
Portanto, a solução deve ser suficientemente clara para
que um aluno consiga explicar seu raciocínio.

Produza um rascunho completo SOMENTE da Questão
{numero_questao}.
"""

    resultado_rascunho = await Runner.run(
        lider,
        prompt_lider,
    )

    rascunho = (
        resultado_rascunho.final_output
    )

    # ========================================================
    # 2. REVIEWER
    # ========================================================

    print(
        f"[Questão {numero_questao}] "
        f"[2/4] Reviewer verificando..."
    )

    prompt_revisor = f"""
Faça uma revisão técnica da solução da
QUESTÃO {numero_questao}.

ARQUIVO DA PROVA:
{nome_arquivo}

Use ler_documento_completo para consultar o PDF
e verificar o enunciado exato da questão.

RASCUNHO:

==================================================
{limitar_texto(rascunho, 35000)}
==================================================

Verifique:

1. identificação correta da questão;
2. fidelidade ao enunciado;
3. numeração dos subitens;
4. hipóteses utilizadas;
5. teoremas e suas hipóteses;
6. álgebra;
7. dimensões matriciais;
8. argumentos assintóticos;
9. conclusões;
10. possíveis hipóteses adicionais.

IMPORTANTE:

As hipóteses das outras questões da prova
não podem ser utilizadas automaticamente.

Se houver erro no enunciado, identifique-o
como problema do enunciado.

Se a solução estiver correta apesar de uma
falha no enunciado, preserve isso.

Produza apenas o parecer.

Use exatamente:

STATUS:
...

PROBLEMAS:
...

VERIFICAÇÕES:
...

PONTOS CORRETOS:
...
"""

    resultado_revisor = await Runner.run(
        revisor,
        prompt_revisor,
    )

    parecer_revisor = (
        resultado_revisor.final_output
    )

    print(
        "\n" + "=" * 80
    )

    print(
        f"PARECER DO REVIEWER "
        f"— QUESTÃO {numero_questao}"
    )

    print(
        "=" * 80
    )

    print(
        parecer_revisor
    )

    print(
        "=" * 80
    )

    # ========================================================
    # SALVAR PARECER
    # ========================================================

    pasta_bonus = Path(
        "outputs/bonus"
    )

    pasta_bonus.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    arquivo_parecer = (
        pasta_bonus
        / f"reviewer_q{numero_questao}_{timestamp}.txt"
    )

    arquivo_parecer.write_text(
        parecer_revisor,
        encoding="utf-8",
    )

    # ========================================================
    # 3. LÍDER — VERSÃO FINAL
    # ========================================================

    print(
        f"[Questão {numero_questao}] "
        f"[3/4] Líder corrigindo..."
    )

    prompt_final = f"""
Você é o Tutor Líder de Estatística II.

Produza a versão final da QUESTÃO {numero_questao}.

ARQUIVO DA PROVA:
{nome_arquivo}

RASCUNHO:
==================================================
{limitar_texto(rascunho, 35000)}
==================================================

PARECER DO REVIEWER:
==================================================
{limitar_texto(parecer_revisor, 25000)}
==================================================

Corrija todos os problemas CRÍTICOS e IMPORTANTES.

Preserve argumentos corretos.

Não aceite uma crítica do Reviewer automaticamente
caso ela esteja matematicamente errada.

Se existir uma falha no enunciado:

- não a esconda;
- explique a resolução pretendida, quando possível;
- deixe clara a hipótese adicional necessária.

Não carregue hipóteses de outras questões.

Preserve a numeração original.

Não mencione o Reviewer.

Produza somente a solução final da Questão
{numero_questao}.
"""

    resultado_final = await Runner.run(
        lider,
        prompt_final,
    )

    solucao_final = (
        resultado_final.final_output
    )

    # ========================================================
    # 4. SEGUNDA REVISÃO CONDICIONAL
    # ========================================================

    parecer_segunda_revisao = ""

    if parecer_exige_segunda_revisao(parecer_revisor):

        print(
            f"[Questão {numero_questao}] "
            f"[4] Segunda revisão do Reviewer..."
        )

        prompt_segunda_revisao = f"""
Faça uma SEGUNDA revisão técnica da versão FINAL
da QUESTÃO {numero_questao}.

Esta segunda revisão foi solicitada porque o primeiro
parecer encontrou pelo menos um problema que exigiu
revisão da solução.

ARQUIVO DA PROVA:
{nome_arquivo}

Use ler_documento_completo para verificar novamente
o enunciado exato da questão.

PRIMEIRO PARECER:
==================================================
{limitar_texto(parecer_revisor, 25000)}
==================================================

VERSÃO FINAL APÓS A PRIMEIRA CORREÇÃO:
==================================================
{limitar_texto(solucao_final, 35000)}
==================================================

Verifique novamente, de forma independente:

1. identificação correta da questão;
2. fidelidade ao enunciado;
3. numeração dos subitens;
4. hipóteses utilizadas;
5. teoremas e suas hipóteses;
6. álgebra;
7. dimensões matriciais;
8. argumentos assintóticos;
9. conclusões;
10. hipóteses adicionais;
11. se a primeira correção introduziu algum novo erro.

Não aceite automaticamente a primeira solução nem
o primeiro parecer. Verifique a matemática novamente.

Questões diferentes continuam sendo independentes.
Não transfira hipóteses de outras questões.

Produza apenas o parecer, usando exatamente:

STATUS:
...

PROBLEMAS:
...

VERIFICAÇÕES:
...

PONTOS CORRETOS:
...
"""

        resultado_segunda_revisao = await Runner.run(
            revisor,
            prompt_segunda_revisao,
        )

        parecer_segunda_revisao = (
            resultado_segunda_revisao.final_output
        )

        print(
            "\n" + "=" * 80
        )
        print(
            f"SEGUNDA REVISÃO DO REVIEWER "
            f"— QUESTÃO {numero_questao}"
        )
        print(
            "=" * 80
        )
        print(
            parecer_segunda_revisao
        )
        print(
            "=" * 80
        )

        timestamp_segundo = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        arquivo_segunda_revisao = (
            pasta_bonus
            / f"reviewer_q{numero_questao}_segunda_"
            f"{timestamp_segundo}.txt"
        )
        arquivo_segunda_revisao.write_text(
            parecer_segunda_revisao,
            encoding="utf-8",
        )

        # Se a segunda revisão ainda identificar problemas,
        # pedimos uma última correção ao Líder antes do PDF.
        if parecer_exige_segunda_revisao(
            parecer_segunda_revisao
        ):

            print(
                f"[Questão {numero_questao}] "
                f"[5] Segunda correção do Líder..."
            )

            prompt_correcao_final = f"""
Produza a versão FINAL CORRIGIDA da QUESTÃO
{numero_questao}.

ARQUIVO DA PROVA:
{nome_arquivo}

SOLUÇÃO ATUAL:
==================================================
{limitar_texto(solucao_final, 35000)}
==================================================

SEGUNDO PARECER DO REVIEWER:
==================================================
{limitar_texto(parecer_segunda_revisao, 25000)}
==================================================

Corrija os problemas realmente identificados.
Preserve toda a matemática que estiver correta.
Não introduza hipóteses de outras questões.
Se houver problema no próprio enunciado, deixe isso
explicitamente indicado.

Produza somente a solução final da Questão
{numero_questao}.
"""

            resultado_correcao_final = await Runner.run(
                lider,
                prompt_correcao_final,
            )

            solucao_final = (
                resultado_correcao_final.final_output
            )

    return (
        solucao_final,
        parecer_revisor,
        parecer_segunda_revisao,
    )


# ============================================================
# RELATÓRIO DE UMA QUESTÃO
# ============================================================

async def gerar_relatorio_questao(
    numero_questao: int,
    solucao_final: str,
    dados_grupo,
    incluir_dados_grupo: bool,
    pasta_saida: Path,
):

    # ========================================================
    # DADOS DO GRUPO
    # ========================================================

    if incluir_dados_grupo:

        texto_grupo = formatar_dados_grupo(
            dados_grupo
        )

        bloco_grupo = f"""
DADOS DO GRUPO:

{texto_grupo}

Na primeira página, no topo do documento,
reproduza essas informações.
"""

        bloco_ferramentas = """
Na primeira resposta, inclua também uma linha breve:

Ferramentas utilizadas: OpenAI Agents SDK, Python,
materiais da disciplina e LaTeX.
"""

    else:

        bloco_grupo = ""
        bloco_ferramentas = ""

    # ========================================================
    # GERAÇÃO
    # ========================================================

    tentativa = 1

    while tentativa <= 2:

        print(
            f"[Questão {numero_questao}] "
            f"[4/4] Gerando relatório "
            f"(tentativa {tentativa})..."
        )

        instrucoes_paginas = ""

        if tentativa == 2:

            instrucoes_paginas = """
ATENÇÃO:

A versão anterior ultrapassou o limite de cinco páginas.

Produza uma versão MAIS CONCISA.

Reduza:
- explicações repetitivas;
- reprodução desnecessária do enunciado;
- texto verbal redundante;
- espaços excessivos.

NÃO remova:
- demonstrações necessárias;
- hipóteses;
- justificativas;
- equações essenciais;
- conclusões.

O documento final PRECISA ter no máximo cinco páginas.
"""

        prompt_relatorio = f"""
Você é o Gerador de Relatórios de Estatística II
do Mestrado em Economia da FGV EPGE.

Produza o relatório acadêmico da:

QUESTÃO {numero_questao}

SOLUÇÃO FINAL:
==================================================
{limitar_texto(solucao_final, 40000)}
==================================================

{bloco_grupo}

{bloco_ferramentas}

FORMATAÇÃO OBRIGATÓRIA
==================================================

Use EXATAMENTE:

\\documentclass[12pt,letterpaper]{{article}}

\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{babel}}
\\babelprovide[main,import]{{brazilian}}
\\usepackage{{amsmath}}
\\usepackage{{amssymb}}
\\usepackage{{mathtools}}
\\usepackage{{geometry}}

\\geometry{{margin=1in}}

Não use microtype.

Não crie capa.

Não crie folha de rosto.

A primeira página deve começar com a identificação
do grupo, quando solicitada, e em seguida a resposta.

A resposta deve ter NO MÁXIMO 5 PÁGINAS.

Não reproduza o enunciado inteiro.
Apresente apenas uma identificação breve do que é pedido.

Priorize:

- rigor matemático;
- clareza;
- concisão;
- justificativas;
- hipóteses;
- teoremas utilizados.

A resposta será lida pelo professor e também utilizada
na prova oral, portanto os passos essenciais devem permanecer.

As referências contam para o limite de páginas.

A resposta deve ser SOMENTE o código LaTeX completo.

Não utilize markdown fences.

Comece diretamente com:

\\documentclass

{instrucoes_paginas}
"""

        resultado_relatorio = await Runner.run(
            relatorio,
            prompt_relatorio,
        )

        codigo_latex = (
            resultado_relatorio.final_output.strip()
        )

        # ====================================================
        # LIMPEZA LATEX
        # ====================================================

        codigo_latex = codigo_latex.replace(
            r"\usepackage[portuguese]{babel}",
            r"\usepackage{babel}"
            r"\babelprovide[main,import]{brazilian}",
        )

        codigo_latex = codigo_latex.replace(
            r"\usepackage[brazil]{babel}",
            r"\usepackage{babel}"
            r"\babelprovide[main,import]{brazilian}",
        )

        codigo_latex = codigo_latex.replace(
            r"\usepackage[brazilian]{babel}",
            r"\usepackage{babel}"
            r"\babelprovide[main,import]{brazilian}",
        )

        codigo_latex = codigo_latex.replace(
            r"\usepackage{microtype}",
            "",
        )

        # Remove fences

        if codigo_latex.startswith(
            "```latex"
        ):

            codigo_latex = (
                codigo_latex[
                    len("```latex"):
                ].strip()
            )

        if codigo_latex.startswith(
            "```"
        ):

            codigo_latex = (
                codigo_latex[3:].strip()
            )

        if codigo_latex.endswith(
            "```"
        ):

            codigo_latex = (
                codigo_latex[:-3].strip()
            )

        # ====================================================
        # SALVAR TEX
        # ====================================================

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        arquivo_tex = (
            pasta_saida
            / f"questao_{numero_questao}_"
            f"{timestamp}.tex"
        )

        arquivo_tex.write_text(
            codigo_latex,
            encoding="utf-8",
        )

        # ====================================================
        # COMPILAR
        # ====================================================

        pdf_path = compilar_latex(
            str(arquivo_tex),
            str(pasta_saida),
        )

        # ====================================================
        # VERIFICAR PÁGINAS
        # ====================================================

        reader = PdfReader(
            str(pdf_path)
        )

        numero_paginas = len(
            reader.pages
        )

        print(
            f"Questão {numero_questao}: "
            f"{numero_paginas} página(s)"
        )

        if numero_paginas <= 5:

            return pdf_path

        # Se passou do limite

        print(
            f"Questão {numero_questao} "
            f"ultrapassou o limite de 5 páginas."
        )

        tentativa += 1

    raise RuntimeError(
        f"Não foi possível gerar a Questão "
        f"{numero_questao} dentro do limite de 5 páginas."
    )


# ============================================================
# MODO BÔNUS
# ============================================================

async def modo_bonus(
    pergunta: str,
):

    print(
        "\n" + "=" * 80
    )

    print(
        "TRABALHO BÔNUS — STATISTICS II"
    )

    print(
        "=" * 80
    )

    # ========================================================
    # ARQUIVO
    # ========================================================

    nome_arquivo = input(
        "\nNome do arquivo PDF da prova "
        "(ex.: bonus.pdf): "
    ).strip()

    arquivo_prova_existe(
        nome_arquivo
    )

    # ========================================================
    # GRUPO
    # ========================================================

    dados_grupo = ler_dados_grupo()

    pasta_bonus = Path(
        "outputs/bonus"
    )

    pasta_bonus.mkdir(
        parents=True,
        exist_ok=True,
    )

    pdfs_respostas = []

    # ========================================================
    # 3 QUESTÕES
    # ========================================================

    for numero_questao in range(
        1,
        4,
    ):

        (
            solucao_final,
            parecer,
            parecer_segunda_revisao,
        ) = await resolver_questao_bonus(
            numero_questao,
            nome_arquivo,
        )

        pdf_resposta = (
            await gerar_relatorio_questao(
                numero_questao,
                solucao_final,
                dados_grupo,
                numero_questao == 1,
                pasta_bonus,
            )
        )

        pdfs_respostas.append(
            pdf_resposta
        )

        # Salvar solução final em TXT

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        arquivo_solucao = (
            pasta_bonus
            / f"solucao_q{numero_questao}_"
            f"{timestamp}.txt"
        )

        arquivo_solucao.write_text(
            solucao_final,
            encoding="utf-8",
        )

        if parecer_segunda_revisao:
            arquivo_parecer_resumo = (
                pasta_bonus
                / f"resumo_revisoes_q{numero_questao}_"
                f"{timestamp}.txt"
            )
            arquivo_parecer_resumo.write_text(
                "PRIMEIRA REVISÃO:\n"
                + parecer
                + "\n\nSEGUNDA REVISÃO:\n"
                + parecer_segunda_revisao,
                encoding="utf-8",
            )

    # ========================================================
    # COMBINAR
    # ========================================================

    timestamp_final = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    arquivo_final = (
        pasta_bonus
        / f"bonus_final_{timestamp_final}.pdf"
    )

    print(
        "\n" + "=" * 80
    )

    print(
        "COMBINANDO AS TRÊS RESPOSTAS..."
    )

    print(
        "=" * 80
    )

    paginas = combinar_pdfs(
        pdfs_respostas,
        arquivo_final,
        max_paginas_por_resposta=5,
    )

    # Validação final independente do PDF consolidado.
    paginas_validadas = validar_saida_bonus(
        arquivos_pdf=pdfs_respostas,
        arquivo_final=arquivo_final,
        max_paginas_por_resposta=5,
    )

    if paginas_validadas != paginas:
        raise RuntimeError(
            "A validação final retornou uma contagem de páginas diferente "
            "daquela informada pela etapa de combinação."
        )

    total_paginas = sum(
        paginas
    )

    print(
        "\nVALIDAÇÃO FINAL: OK"
    )

    print(
        "Os 3 PDFs individuais existem, cada resposta respeita o limite "
        "de 5 páginas e o PDF consolidado possui o número esperado de páginas."
    )

    print(
        "\nPDF FINAL GERADO COM SUCESSO!"
    )

    print(
        f"Arquivo: {arquivo_final}"
    )

    print(
        f"Páginas por questão: {paginas}"
    )

    print(
        f"Total de páginas: {total_paginas}"
    )


# ============================================================
# MAIN
# ============================================================

async def main():

    pergunta = ler_pergunta()

    # ========================================================
    # IDENTIFICAÇÃO
    # ========================================================

    if tarefa_e_apenas_identificacao(
        pergunta
    ):

        await modo_identificacao(
            pergunta
        )

        return

    # ========================================================
    # MODO BÔNUS
    # ========================================================

    texto = pergunta.lower()

    if (
        "bônus" in texto
        or "bonus" in texto
    ) and (
        "3 questões" in texto
        or "três questões" in texto
        or "questões" in texto
    ):

        await modo_bonus(
            pergunta
        )

        return

    # ========================================================
    # MODO ANTIGO
    # ========================================================

    print(
        "\n[1/4] Líder elaborando a solução..."
    )

    mensagem_lider = f"""
PERGUNTA DO PROFESSOR:
<<<
{pergunta}
>>>

Resolva a questão seguindo rigorosamente
suas instruções.

Produza uma solução detalhada.
"""

    resultado_rascunho = await Runner.run(
        lider,
        mensagem_lider,
    )

    rascunho = (
        resultado_rascunho.final_output
    )

    # Reviewer

    print(
        "[2/4] Reviewer verificando a solução..."
    )

    prompt_revisao = f"""
Faça a revisão técnica da solução abaixo.

PERGUNTA ORIGINAL:
<<<
{pergunta}
>>>

RASCUNHO:
<<<
{limitar_texto(rascunho, 30000)}
>>>

Produza apenas o parecer de revisão.
"""

    resultado_revisao = await Runner.run(
        revisor,
        prompt_revisao,
    )

    parecer_revisor = (
        resultado_revisao.final_output
    )

    print(
        "\n" + "=" * 80
    )

    print(
        "PARECER DO REVIEWER"
    )

    print(
        "=" * 80
    )

    print(
        parecer_revisor
    )

    print(
        "=" * 80
    )

    # Líder final

    print(
        "[3/4] Líder corrigindo a solução..."
    )

    prompt_final = f"""
Você é o Tutor Líder de Estatística II.

PERGUNTA ORIGINAL:
==================================================
{pergunta}

RASCUNHO:
==================================================
{limitar_texto(rascunho, 30000)}

PARECER DO REVIEWER:
==================================================
{limitar_texto(parecer_revisor, 20000)}

Produza a solução final corrigida.

Preserve as partes corretas.

Corrija os problemas apontados.

Não mencione o Reviewer.

Produza somente a solução final.
"""

    resultado_final = await Runner.run(
        lider,
        prompt_final,
    )

    solucao_final = (
        resultado_final.final_output
    )

    print(
        "[4/4] Solução final produzida."
    )

    print(
        "\nSolução final:\n"
    )

    print(
        solucao_final
    )


if __name__ == "__main__":

    asyncio.run(main())