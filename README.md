# Hydrus React — nova stack (FastAPI + Next.js)

Rebuild da plataforma AgroHydrus com a física preservada e UI reativa.
O app Gradio em `../Hydrus` segue como **referência/gabarito de paridade**.

## Estrutura

```
Hydrus-react/
├── packages/hydrus-core/   # física 1D (pip install -e .) — fonte única
│   └── hydrus_core/        # Richards + ADE + Feddes + laudos + gráficos
├── backend/                # FastAPI fina sobre o hydrus-core
│   ├── app/{main,schemas,service}.py
│   └── Dockerfile
├── frontend/               # Next.js 14 (App Router) + fetch na API
└── docker-compose.yml      # dev local: api + web
```

## Rodar local

```bash
# 1. núcleo + backend
cd packages/hydrus-core && pip install -e .
cd ../../backend && pip install -r requirements.txt
uvicorn app.main:app --port 8001   # http://127.0.0.1:8001/docs

# 2. frontend
cd ../frontend && npm install
HYDRUS_API_URL=http://127.0.0.1:8001 npm run dev   # http://127.0.0.1:3000

# ou tudo via compose:
docker compose up --build
```

## API (fase 1, síncrona)

- `GET /health`, `GET /soils`, `GET /crops`
- `POST /simulate` → balanço em 3 vias (retido 0–raiz / abaixo no perfil /
  fundo + absorvido) + PNG do perfil em base64

Limites atuais: chuva uniforme no período (série diária na fase 2),
casos curtos (séries anuais vão para fila + progresso na fase 2).

## Roadmap

- [x] Fase 0 — scaffold: pacote, API mínima, página funcional
- [x] Fase 1 — jobs assíncronos (`POST /jobs` + polling) e wizard (solo/cultura,
  tabela de solutos, lâmina uniforme ou série diária colável)
- [ ] Fase 2 — Plotly interativo, fertirrigação/liberação controlada na API,
  ET0 por série, Excel para download
- [ ] Fase 3 — paridade numérica com Gradio (bateria de comparação) + PDF
- [ ] Fase 4 — deploy Fly.io gru (SP) + auth
