*** Settings ***
Documentation    Health Check: valida que todos os modulos estao operacionais.
...              Executa testes rapidos de cada fluxo e gera relatorio consolidado.

Resource         ../config/active.robot
Resource         ../resources/keywords/api_session.resource
Resource         ../resources/keywords/comparator.resource
Resource         ../resources/keywords/ipaas_session.resource
Resource         ../resources/keywords/ipaas_comparator.resource
Library          Collections
Library          OperatingSystem
Library          ../resources/libraries/ProgressLibrary.py

Suite Setup      Setup Health Check
Suite Teardown   Gerar Resultado Health Check


*** Variables ***
${HC_IPAAS_ENABLED}     false
# Defaults iPaaS (resolve parse-time, sobrescritos pelo Import Resource no setup)
${IPAAS_BASE_URL}       https://ipaas.pipefy.com/api/v1
${IPAAS_TOKEN}          NONE
${IPAAS_PROJECT_ID}     NONE


*** Keywords ***
Setup Health Check
    [Documentation]    Inicializa sessoes. Carrega iPaaS config se existir.
    Limpar Progresso
    Iniciar Cronometro
    Registrar Log    Iniciando Health Check...
    Criar Sessao Pipefy

    # Tenta carregar iPaaS config dinamicamente
    ${ipaas_cfg}=    Set Variable    ${CURDIR}/../config/ipaas_fourd.robot
    ${exists}=    Run Keyword And Return Status    File Should Exist    ${ipaas_cfg}
    IF    ${exists}
        Import Resource    ${ipaas_cfg}
        Set Suite Variable    ${HC_IPAAS_ENABLED}    true
        Criar Sessao iPaaS
        Registrar Log    iPaaS habilitado
    ELSE
        Registrar Log    iPaaS desabilitado (config nao encontrada)
    END


Gerar Resultado Health Check
    [Documentation]    Gera JSON com resultado do healthcheck para o frontend.
    ${timestamp}=    Evaluate    __import__('datetime').datetime.now().isoformat()
    ${result}=    Create Dictionary
    ...    healthcheck=${True}
    ...    timestamp=${timestamp}
    ...    status=COMPLETED
    ${json_str}=    Evaluate
    ...    __import__('json').dumps($result, indent=2, ensure_ascii=False, default=str)
    Create File    results/validations.json    ${json_str}


*** Test Cases ***
HC-01: Pipefy API Disponivel
    [Documentation]    Verifica se a API do Pipefy responde e retorna dados do pipe.
    [Tags]    healthcheck    pipefy
    ${pipe}=    Extrair Estrutura Do Pipe    ${PIPE_ORIGEM_UUID}
    Should Not Be Empty    ${pipe}[name]
    ${fases}=    Get Length    ${pipe}[phases]
    Should Be True    ${fases} > 0
    Registrar Log    HC-01 OK: Pipe "${pipe}[name]" com ${fases} fases
    Set Test Message    Conectou na API GraphQL do Pipefy e extraiu o pipe "${pipe}[name]" com ${fases} fases e todos os campos. API respondendo normalmente.


HC-02: Automacoes Acessiveis
    [Documentation]    Verifica se a API de automacoes responde com dados.
    [Tags]    healthcheck    pipefy
    ${autos}=    Extrair Automacoes Do Pipe    ${PIPE_ORIGEM_REPO_ID}    ${ORGANIZATION_ID}
    ${total}=    Get Length    ${autos}
    Should Be True    ${total} > 0
    Registrar Log    HC-02 OK: ${total} automacao(oes) extraidas
    Set Test Message    Extraiu ${total} automacao(oes) do pipe via repoId + organizationId com paginacao cursor-based. Permissoes de leitura OK.


HC-03: Comparacao Estrutural Funcional
    [Documentation]    Self-check estrutural (mesmo pipe vs mesmo pipe = 0 div).
    [Tags]    healthcheck    pipefy
    ${pipe}=    Extrair Estrutura Do Pipe    ${PIPE_ORIGEM_UUID}
    ${divergencias}=    Comparar Estrutura Completa    ${pipe}    ${pipe}
    ${total}=    Get Length    ${divergencias}
    Should Be Equal As Integers    ${total}    0
    Registrar Log    HC-03 OK: Self-check estrutural 0 divergencias
    Set Test Message    Comparou fases, campos (tipo, obrigatoriedade, opcoes), labels e start form do mesmo pipe contra si mesmo. Resultado: 0 divergencias. Motor de comparacao estrutural operacional.


HC-04: Comparacao Automacoes Funcional
    [Documentation]    Self-check automacoes (mesmo pipe vs mesmo pipe = 0 div).
    [Tags]    healthcheck    pipefy
    ${autos}=    Extrair Automacoes Do Pipe    ${PIPE_ORIGEM_REPO_ID}    ${ORGANIZATION_ID}
    ${pipe}=    Extrair Estrutura Do Pipe    ${PIPE_ORIGEM_UUID}
    ${divergencias}=    Create List
    ${divergencias}=    Comparar Automacoes    ${autos}    ${autos}    ${pipe}    ${pipe}    ${divergencias}
    ${total}=    Get Length    ${divergencias}
    Should Be Equal As Integers    ${total}    0
    Registrar Log    HC-04 OK: Self-check automacoes 0 divergencias
    Set Test Message    Comparou automacoes (status, acao, evento, fase destino, conditions, URL/HTTP) do mesmo pipe contra si mesmo. Resultado: 0 divergencias. Normalizacao de nomes e resolucao de fase destino por nome funcionando.


HC-05: Snapshot Gerar e Carregar
    [Documentation]    Gera snapshot temporario e valida que pode ser carregado.
    [Tags]    healthcheck    snapshot
    ${pipe}=    Extrair Estrutura Do Pipe    ${PIPE_ORIGEM_UUID}
    ${autos}=    Extrair Automacoes Do Pipe    ${PIPE_ORIGEM_REPO_ID}    ${ORGANIZATION_ID}
    ${filename}=    Gerar Snapshot    ${pipe}    ${autos}    healthcheck_temp
    File Should Exist    ${filename}
    ${snapshot}=    Carregar Snapshot    ${filename}
    Should Not Be Empty    ${snapshot}[pipe][name]
    Remove File    ${filename}
    Registrar Log    HC-05 OK: Snapshot gerado e carregado
    Set Test Message    Gerou snapshot temporario com estrutura completa (fases, campos, automacoes), salvou em JSON, recarregou e validou integridade dos dados. Ciclo completo de snapshot funcional.


HC-06: Relatorio JSON Funcional
    [Documentation]    Gera relatorio JSON e valida formato.
    [Tags]    healthcheck    report
    ${pipe}=    Extrair Estrutura Do Pipe    ${PIPE_ORIGEM_UUID}
    ${divs}=    Create List
    ${status}    ${total}=    Gerar Relatorio JSON
    ...    pipe_origem=${pipe}    pipe_destino=${pipe}    divergencias=${divs}
    Should Be Equal    ${status}    IDENTICOS
    Should Be Equal As Integers    ${total}    0
    Registrar Log    HC-06 OK: Relatorio JSON gerado
    Set Test Message    Gerou relatorio validations.json com status IDENTICOS e 0 divergencias. Formato JSON valido e pronto para consumo pelo dashboard.


HC-07: iPaaS API Disponivel
    [Documentation]    Verifica se a API do Activepieces responde.
    [Tags]    healthcheck    ipaas
    Skip If    '${HC_IPAAS_ENABLED}' != 'true'    iPaaS desabilitado
    ${flows}=    Extrair Flows Do Projeto    ${IPAAS_PROJECT_ID}
    ${total}=    Get Length    ${flows}
    Should Be True    ${total} > 0
    Registrar Log    HC-07 OK: iPaaS ${total} flow(s)
    Set Test Message    Conectou na API REST do Activepieces (iPaaS) e extraiu ${total} flow(s) do projeto. Token Bearer valido e API respondendo.


HC-08: iPaaS Self-Check Funcional
    [Documentation]    Compara flows do iPaaS contra si mesmos.
    [Tags]    healthcheck    ipaas
    Skip If    '${HC_IPAAS_ENABLED}' != 'true'    iPaaS desabilitado
    ${flows}=    Extrair Flows Do Projeto    ${IPAAS_PROJECT_ID}
    ${divergencias}=    Comparar Flows iPaaS    ${flows}    ${flows}
    ${total}=    Get Length    ${divergencias}
    Should Be Equal As Integers    ${total}    0
    Registrar Log    HC-08 OK: iPaaS self-check 0 div
    Set Test Message    Comparou triggers, steps (tipo, acao, URL), codigo fonte (hash MD5), router conditions e mapeamento de campos de todos os flows contra si mesmos. Resultado: 0 divergencias.


HC-09: iPaaS Snapshot Funcional
    [Documentation]    Gera snapshot iPaaS temporario e valida carregamento.
    [Tags]    healthcheck    ipaas
    Skip If    '${HC_IPAAS_ENABLED}' != 'true'    iPaaS desabilitado
    ${flows}=    Extrair Flows Do Projeto    ${IPAAS_PROJECT_ID}
    ${filename}=    Gerar Snapshot iPaaS    ${flows}    healthcheck_ipaas_temp
    File Should Exist    ${filename}
    ${loaded}=    Carregar Snapshot iPaaS    ${filename}
    ${total}=    Get Length    ${loaded}
    Should Be True    ${total} > 0
    Remove File    ${filename}
    Registrar Log    HC-09 OK: iPaaS snapshot ok
    Set Test Message    Gerou snapshot temporario de ${total} flows do iPaaS com triggers, steps e codigo fonte. Recarregou e validou integridade. Ciclo completo de snapshot iPaaS funcional.
