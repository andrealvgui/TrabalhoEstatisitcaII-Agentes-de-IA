import asyncio

from agents import Runner

from agentes.lider import lider
from agentes.revisor import revisor


PERGUNTA = """
Derive a distribuição assintótica do OLS, mostrando exatamente onde
o resultado do CLT é utilizado e verificando as dimensões matriciais.
""".strip()


# ============================================================
# RASCUNHO DELIBERADAMENTE ERRADO
# ============================================================

RASCUNHO_ERRADO = r"""
Considere o modelo

y_i = x_i' beta + u_i,

com (x_i,u_i) iid, E[x_i u_i] = 0 e
Q = E[x_i x_i'] positiva definida.

O estimador OLS satisfaz

beta_hat - beta
=
(X'X)^{-1} X'u.

Logo,

sqrt(n)(beta_hat-beta)
=
(X'X/n)^{-1}
(1/n) sum_{i=1}^n x_i u_i.

Pela Lei dos Grandes Números,

X'X/n -> Q.

Para o segundo termo, pelo Teorema Central do Limite,

(1/n) sum_{i=1}^n x_i u_i
-> N(0, Omega),

onde

Omega = E[x_i x_i' u_i^2].

Portanto, pelo teorema de Slutsky,

sqrt(n)(beta_hat-beta)
-> N(0, Q^{-1} Omega Q^{-1}).

As dimensões são:

X: n x k
X'X: k x k
X'u: k x 1
beta_hat: k x 1
""".strip()


async def main():

    # ========================================================
    # ETAPA 1 — REVIEWER
    # ========================================================

    print("=" * 80)
    print("TESTE 1 — REVIEWER")
    print("=" * 80)

    prompt_revisao = f"""
Faça a revisão técnica do rascunho abaixo.

IMPORTANTE:
- A pergunta original está entre <<< >>>.
- O rascunho está entre [[[ ]]].
- Não produza uma solução nova.
- Apenas revise o rascunho.
- Identifique erros matemáticos, estatísticos, econométricos,
  problemas de hipóteses, normalização, dimensões e aplicação
  de teoremas.

PERGUNTA ORIGINAL:
<<<
{PERGUNTA}
>>>

RASCUNHO:
[[[
{RASCUNHO_ERRADO}
]]]

Produza apenas o parecer de revisão.
"""

    resultado_revisao = await Runner.run(
        revisor,
        prompt_revisao,
    )

    revisao = resultado_revisao.final_output

    print("\nPARECER DO REVIEWER:\n")
    print(revisao)

    # ========================================================
    # ETAPA 2 — LÍDER CORRIGE
    # ========================================================

    print("\n" + "=" * 80)
    print("TESTE 2 — LÍDER INCORPORANDO A REVISÃO")
    print("=" * 80)

    prompt_final = f"""
Produza a resposta FINAL ao aluno.

Você recebeu:
1. a pergunta original;
2. um rascunho;
3. o parecer de um Reviewer.

O rascunho pode conter erros.

Use o parecer do Reviewer como uma etapa obrigatória de correção.

Para cada problema apontado:
- corrija o problema;
- não repita a afirmação incorreta;
- verifique a matemática;
- verifique as hipóteses;
- verifique as dimensões;
- consulte os materiais do projeto quando necessário.

Não mencione o Reviewer.
Não mencione o rascunho.
Não explique o processo interno de revisão.

PERGUNTA ORIGINAL:
<<<
{PERGUNTA}
>>>

RASCUNHO:
[[[
{RASCUNHO_ERRADO}
]]]

PARECER DO REVIEWER:
[[[
{revisao}
]]]

Agora produza somente a resposta final ao aluno.
"""

    resultado_final = await Runner.run(
        lider,
        prompt_final,
    )

    resposta_final = resultado_final.final_output

    print("\nRESPOSTA FINAL DO LÍDER:\n")
    print(resposta_final)


if __name__ == "__main__":
    asyncio.run(main())