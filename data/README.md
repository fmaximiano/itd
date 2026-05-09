**Arquitetura de Dados — Serviços MG**

Data base: 25/02/2026  
Status: Em implementação (API validada localmente; Excel loader e GitHub Actions em estruturação)

---

**1\. Visão Geral**

Este repositório implementa uma arquitetura de dados simples, auditável e historicamente consistente para acompanhamento de serviços públicos do Estado de Minas Gerais.

A solução é baseada em três pilares:

-   **Excel histórico (imutável)** → representa o passado.
-   **API oficial (/servicos\_etapas)** → representa presente e futuro.
-   **BigQuery append-only** → armazena snapshots brutos (RAW) e fornece uma **view canônica única** para o Power BI.

O objetivo central é garantir:

-   Série histórica contínua.
-   Nenhuma coluna “origem/tipo\_registro” no BI.
-   Rastreabilidade total via RAW.
-   Captura integral do payload da API (mesmo que não usado no BI).

---

**2\. Princípios Arquiteturais (Obrigatórios)**

**2.1 Append-Only**

No BigQuery é **proibido**:

-   UPDATE
-   MERGE
-   DELETE
-   TRUNCATE
-   OVERWRITE

Cada execução gera um novo snapshot.

O histórico nunca é alterado.

---

**2.2 Separação clara entre RAW e Modelagem**

| Camada | Função | Alteração permitida? |
| --- | --- | --- |
| RAW | Armazenamento bruto, auditável | ❌ Nunca |
| Views | Padronização, modelagem | ✅ Sim |
| BI | Consumo final | ❌ Não distingue origem |

---

**2.3 Continuidade temporal no BI**

O Power BI consome **uma única entidade**:

dataset\_servicos.vw\_mapacompleto

O campo de tempo oficial é:

DATA = data\_ref

Regras:

-   Excel → data\_ref vem da coluna DATA (com regra de preenchimento de blocos).
-   API → data\_ref = DATE(dt\_carga).

---

**2.4 Chave Universal Estável**

Cada registro (Excel ou API) recebe:

id\_interno = SHA256(  
  orgao\_norm | servico\_norm | num\_etapa\_norm | nome\_etapa\_norm  
)

Normalização mínima aplicada antes do hash:

-   trim
-   colapsar múltiplos espaços
-   minúsculo
-   substituir “–/—” por “-”
-   **não remover acentos**

Essa chave é:

-   Estável no tempo
-   Independente de nid/nid\_1
-   Usada para continuidade histórica

---

**3\. Estrutura do BigQuery**

**Dataset**

dataset\_servicos

---

**3.1 Tabela RAW — Excel Histórico**

dataset\_servicos.raw\_excel\_hist

Colunas:

-   dt\_carga TIMESTAMP REQUIRED
-   exec\_ref STRING REQUIRED
-   data\_ref DATE REQUIRED (PARTITION)
-   id\_interno STRING REQUIRED (CLUSTER)
-   payload\_excel JSON REQUIRED

Características:

-   require\_partition\_filter = TRUE
-   Append-only
-   Payload completo armazenado como JSON

---

**3.2 Tabela RAW — API**

dataset\_servicos.raw\_servicos\_etapas

Colunas:

-   dt\_carga TIMESTAMP REQUIRED
-   exec\_ref STRING REQUIRED
-   data\_ref DATE REQUIRED (PARTITION)
-   id\_interno STRING REQUIRED (CLUSTER)
-   nid STRING NULLABLE
-   nid\_1 STRING NULLABLE
-   payload\_api JSON REQUIRED

Regra obrigatória:

payload\_api deve conter TODOS os campos retornados pela API.

Mesmo que o BI não utilize.

---

**3.3 View Canônica**

dataset\_servicos.vw\_mapacompleto

Função:

-   Unificar Excel + API
-   Expor colunas estáveis
-   Eliminar qualquer distinção de origem

Observação importante:

Campos do Excel com caracteres especiais exigem JSONPath com aspas:

JSON\_VALUE(payload\_excel, '$."Título/Serviço"')

---

**4\. Estrutura do Repositório**

digital-transformation-map/  
  scripts/  
    api/  
      load\_servicos\_etapas.py  
    excel/  
      load\_excel\_hist.py  
    common/  
      bq.py  
      normalize.py  
      hash\_id.py  
      logging\_setup.py  
      config.py  
  sql/  
    views/  
      vw\_mapacompleto.sql  
  .github/  
    workflows/  
  requirements.txt  
  .env.example  
  .gitignore  
  README.md

---

**5\. Loader da API**

**Status**

✔ Testado localmente✔ Inseriu 200 registros (uma execução)  
✔ Batch load via WRITE\_APPEND✔ Schema alinhado ao DDL

**Fluxo**

1.  Lê .env
2.  Autentica via header key: <API\_KEY>
3.  Consome endpoint:

https://www.mg.gov.br/api/v4/servicos\_etapas

4.  Calcula id\_interno
5.  Define:

data\_ref = DATE(dt\_carga)

6.  Grava via load\_table\_from\_json

---

**6\. Loader do Excel (Planejado)**

Regras obrigatórias:

-   Remover linhas totalmente vazias.
-   Preencher blocos de DATA:

-   Se a última data válida acima for igual à primeira válida abaixo → preencher intervalo.

-   Gerar id\_interno padrão.
-   Armazenar linha completa em payload\_excel (JSON).
-   Append-only.

---

**7\. GitHub Actions (Planejado)**

Será criado workflow para:

-   Executar loader da API
-   Periodicidade definida no YAML
-   Ambiente controlado via secrets

Sem execução ainda nesta fase.

---

**8\. Como Executar Localmente**

**8.1 Criar ambiente virtual**

python -m venv .venv  
.venv\\Scripts\\activate

**8.2 Instalar dependências**

pip install -r requirements.txt

**8.3 Criar .env**

Baseado em .env.example.

---

**8.4 Rodar loader da API**

python -m scripts.api.load\_servicos\_etapas

---

**9\. Validação no BigQuery**

**Contagem do dia**

SELECT COUNT(\*)  
FROM \`dataset\_servicos.raw\_servicos\_etapas\`  
WHERE data\_ref = CURRENT\_DATE();

---

**Amostra**

SELECT dt\_carga, exec\_ref, data\_ref, id\_interno, nid\_1  
FROM \`dataset\_servicos.raw\_servicos\_etapas\`  
WHERE data\_ref = CURRENT\_DATE()  
ORDER BY dt\_carga DESC  
LIMIT 20;

---

**10\. Estratégia de Evolução**

Ordem recomendada:

**P0**

-   Consolidar loader API
-   Implementar loader Excel completo
-   Ajustar vw\_mapacompleto (colunas base apenas)

**P1**

-   Configurar GitHub Actions
-   Definir estratégia final do Excel histórico

**P2**

-   Criar camada de cálculos (views adicionais)
-   Reproduzir fórmulas do Excel no BigQuery

---

**11\. Filosofia do Projeto**

Este projeto adota um modelo:

-   Simples
-   Determinístico
-   Auditável
-   Historicamente consistente

Nada é apagado.  
Nada é reescrito.  
Nada depende de lógica oculta no BI.

A verdade histórica está no RAW.  
A interpretação está nas Views.  
O consumo está no Power BI.

Separação clara.  
Responsabilidades claras.  
Evolução controlada.

---

**12\. Garantias Arquiteturais**

-   ✔ Série histórica contínua
-   ✔ Captura integral da API
-   ✔ Excel preservado como passado
-   ✔ Snapshot diário consistente
-   ✔ Independência do BI
-   ✔ Governança simples