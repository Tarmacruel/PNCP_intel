# PNCP_intel

Busca de contratos de fornecedores na base publica do PNCP com interface Streamlit.

## Requisitos

- Python 3.12+

## Como rodar

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py --server.port=8501 --server.address=127.0.0.1
```

## Funcionalidades

- Validacao de CNPJ
- Busca paginada no PNCP
- Dashboard com graficos interativos
- Filtros dinamicos
- Exportacao para Excel e CSV
