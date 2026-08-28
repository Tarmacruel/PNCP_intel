# PNCP Intelligence

Painel analítico para consultar e interpretar dados públicos do Portal Nacional de Contratações Públicas (PNCP), por fornecedor ou órgão público.

## O que a aplicação entrega

- Consulta por CNPJ de fornecedor, com busca paginada, validação amostral e recorte opcional por período.
- Consulta por CNPJ de órgão, com faixa anual, contratos, compras/licitações e atas consolidados.
- Filtros operacionais, gráficos interativos, tabelas paginadas e links para conferência no PNCP.
- Relatórios com contexto do recorte, cobertura, filtros efetivos, identificador rastreável e data de geração em BRT.
- Base integral em CSV ou Excel formatado; PDF executivo e PDF detalhado com amostra claramente identificada.

## Executar localmente

Requer Python 3.10 ou superior.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m streamlit run app.py --server.port=8501 --server.address=127.0.0.1
```

Abra `http://127.0.0.1:8501` no navegador.

## Implantação no Streamlit Community Cloud

O arquivo [`.streamlit/config.toml`](.streamlit/config.toml) desativa a observação de arquivos no servidor. Isso evita a falha de inicialização por limite compartilhado de instâncias `inotify` no ambiente hospedado.

Para publicar, conecte o repositório ao Streamlit Community Cloud e use:

- arquivo principal: `app.py`
- dependências: `requirements.txt`

## Relatórios e limites de uso

Os dados permanecem públicos e são obtidos dos endpoints do PNCP. A exportação registra a cobertura retornada pelo portal; se ela for parcial, o relatório apresenta esse aviso. O PDF detalhado contém uma amostra de até 100 registros para manter legibilidade e desempenho — use Excel ou CSV para a base integral e para auditorias extensas.
