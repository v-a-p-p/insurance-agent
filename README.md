### Sobre o desenvolvimento deste projeto, seguindo Spec-Driven Development

O primeiro passo foi criar o arquivo AGENTS.md e popular /.agents com rules e skills, para desenvolver o projeto de forma agêntica utilizando OpenCode e DeepSeek V4 Pro.

O passo posterior foi, em conjunto com o agente (em plan mode), criar os constitutional files: /specs/mission.md, /specs/roadmap.md, e /specs/tech-stack.md, que são a base para todo o desenvolvimento sobre o projeto. Estes, e principalmente o roadmap.md, podem ser alterados ao longo do projeto.

Depois, para cada fase descrita no roadmap, se discute com o agente (em plan mode) os arquivos que darão base ao desenvolvimento daquela fase (plan.md, requirements.md, e validation.md), e adicionados a pasta daquela fase (por exemplo, em /specs/4-resilience/ para a fase 4). Uma vez criados, pede-se ao agente (agora em build mode) para escrever os arquivos de código daquela fase. Ao terminar a implementação, a fase é marcada como "done" no roadmap, e a pasta é movida para /specs/done/ afim de arquivar todas as "source of truth" das implementações.

Como pode ser verificado em /specs/roadmap.md, e nas pastas existentes em /specs, o próximo passo seria o desenvolvimento da fase 4.

### Como executar os evals

Pré-requisitos: tenha o Python 3.14+ e o uv instalados, e uma API Key do OpenRouter definida no .env como OPENROUTER_API_KEY.

uv run pytest -m eval -s

### Para executar os unit tests

Pré-requisitos: tenha o Python 3.14+ e o uv instalados.

uv run pytest -m "not eval"

### Mapa do projeto

```
.
├── .agents/                  # Configuração de agentes de IA (regras + skills)
│   ├── rules/                # Regras de código (FastAPI best practices)
│   └── skills/               # Skills para LangChain, LangGraph, FastAPI (14 skills)
├── .env.example              # Exemplo de variáveis de ambiente
├── .gitignore
├── .python-version           # Python 3.14+
├── AGENTS.md                 # Instruções para agentes de IA (OpenCode)
├── ai-logs/                  # Logs de conversas com IAs (exigência do desafio)
├── eval/                     # Framework de avaliação do agente (LLM-as-judge)
│   ├── sample/               # 10 conversas do dataset anotadas para avaliação
│   ├── results/              # Resultados das execuções de avaliação (.jsonl)
│   ├── judge.py              # Juiz LLM com rubrica 4D (relevância, tom, precisão, PII)
│   ├── runner.py             # Replay de conversas pelo agente, capturando respostas
│   ├── report.py             # Relatório agregado com pass rate e médias por dimensão
│   ├── conftest.py           # Fixtures de avaliação (mock quote client, loader)
│   └── test_eval.py          # Testes do framework de avaliação
├── namastex-fde-challenge/   # Assets do desafio (NÃO EDITAR)
├── pyproject.toml            # Dependências (uv), configuração do pytest
├── specs/                    # Spec-Driven Development: documentos constitucionais
│   ├── mission.md            # Missão, critérios de sucesso, north star
│   ├── roadmap.md            # Roadmap de 8 fases (fases 1-3 concluídas)
│   ├── tech-stack.md         # Stack tecnológica e justificativas
│   ├── 4-resilience/         # Specs da fase atual (plan, requirements, validation)
│   └── done/                 # Specs arquivadas das fases concluídas (1, 2, 3)
├── src/                      # Código fonte da aplicação
│   ├── main.py               # Entry point FastAPI: lifespan, rotas, /health
│   ├── config.py             # Settings via Pydantic (env vars + defaults)
│   ├── chat/                 # Módulo do agente conversacional
│   ├── quote/                # Integração com o serviço de cotação
│   └── dataset/              # Carregador do dataset de conversas
├── tests/                    # Testes unitários (pytest)
└── uv.lock                   # Lockfile de dependências (uv)
```
