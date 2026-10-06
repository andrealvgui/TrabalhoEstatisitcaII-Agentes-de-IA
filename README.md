# Estatística 2 - AI Agents

Projeto desenvolvido para a resolução do problema extra de Estatística II
utilizando uma arquitetura de agentes de IA.

O sistema foi desenvolvido para consultar os materiais da disciplina,
resolver questões com rigor matemático, revisar as soluções e gerar
respostas finais em formato PDF.

# Agentes

O projeto é dividido em agentes com funções específicas:

## Líder

Responsável por coordenar a resolução das questões.

O Líder:

- identifica o problema e o que está sendo solicitado;
- consulta os materiais da disciplina;
- utiliza os especialistas quando necessário;
- resolve as questões passo a passo;
- verifica as hipóteses dos teoremas utilizados;
- mantém, sempre que possível, a notação e a abordagem das Lecture
  Notes de Marcelo Moreira;
- incorpora as correções apontadas pelo Revisor;
- produz a solução final.

Quando uma questão está contida em um PDF de prova, o PDF é tratado como
a fonte canônica do enunciado e de sua numeração.

## Especialistas

São agentes consultivos responsáveis por áreas específicas do conteúdo
da disciplina.

### Probabilidade e Assintótica

Responsável por questões envolvendo, entre outros:

- LLN;
- CLT;
- Lindeberg-Feller;
- Lyapunov;
- Slutsky;
- convergência;
- consistência;
- normalidade assintótica.

### Econometria

Responsável por questões envolvendo, entre outros:

- OLS;
- CLS;
- GLS;
- NLS;
- máxima verossimilhança;
- GMM;
- consistência de estimadores;
- normalidade assintótica;
- testes;
- matrizes de variância-covariância.

### Álgebra Linear

Responsável por questões envolvendo, entre outros:

- operações matriciais;
- posto;
- inversas;
- autovalores;
- autovetores;
- formas quadráticas;
- projeções;
- ortogonalidade;
- matrizes positivas definidas ou semidefinidas.

Os especialistas não produzem necessariamente a resposta final.
Eles fornecem pareceres técnicos que são utilizados pelo Líder.

## Revisor

Responsável por revisar tecnicamente a solução produzida pelo Líder.

O Revisor verifica, entre outros pontos:

- correção matemática;
- álgebra e sinais;
- dimensões e operações matriciais;
- aplicação dos teoremas;
- hipóteses necessárias;
- argumentos assintóticos;
- fidelidade ao enunciado;
- numeração das questões e subitens;
- independência entre as questões;
- referências aos materiais.

O Revisor também diferencia problemas encontrados na solução,
problemas presentes no próprio enunciado e situações que não puderam
ser verificadas.

Após a revisão, o Líder produz a versão final da resposta.

# Fluxo do projeto

O fluxo principal do sistema é:

```text
PDF / pergunta do usuário
          ↓
        Líder
          ↓
    Especialistas
          ↓
      Rascunho
          ↓
       Revisor
          ↓
   Líder + correções
          ↓
     Solução final
          ↓
   Gerador de relatório
          ↓
       LaTeX
          ↓
      Compilação
          ↓
         PDF
