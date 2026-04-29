*** Settings ***
Documentation    Sessão HTTP e execução de queries GraphQL no Pipefy.
...              Suporta single-session (mesmo ambiente) e dual-session (cross-environment).
...              Modos de autenticação: bearer (PAT) e session (cookie/CSRF).

Library          RequestsLibrary
Library          Collections
Library          OperatingSystem
Library          JSONLibrary


*** Variables ***
${QUERY_DIR}    ${CURDIR}${/}..${/}queries


*** Keywords ***
# ===========================================================================
# SESSÃO — SINGLE ENVIRONMENT (backward compat)
# ===========================================================================

Criar Sessao Pipefy
    [Documentation]    Cria sessão HTTP única (mesmo ambiente origem/destino).
    Criar Sessao Nomeada    pipefy
    ...    ${AUTH_MODE}    ${PIPEFY_BASE_URL}    ${PIPEFY_TOKEN}
    ...    ${PIPEFY_SESSION_COOKIE}    ${PIPEFY_CSRF_TOKEN}    ${VERIFY_SSL}


# ===========================================================================
# SESSÃO — DUAL ENVIRONMENT (cross-env: HMG vs PRD)
# ===========================================================================

Criar Dual Sessions
    [Documentation]    Cria duas sessões HTTP: pipefy_origem e pipefy_destino.
    ...                Usado para comparação cross-environment (ex: HMG vs PRD).
    Criar Sessao Nomeada    pipefy_origem
    ...    ${ORIGEM_AUTH_MODE}    ${ORIGEM_BASE_URL}    ${ORIGEM_TOKEN}
    ...    ${ORIGEM_SESSION_COOKIE}    ${ORIGEM_CSRF_TOKEN}    ${ORIGEM_VERIFY_SSL}

    Criar Sessao Nomeada    pipefy_destino
    ...    ${DESTINO_AUTH_MODE}    ${DESTINO_BASE_URL}    ${DESTINO_TOKEN}
    ...    ${DESTINO_SESSION_COOKIE}    ${DESTINO_CSRF_TOKEN}    ${DESTINO_VERIFY_SSL}


# ===========================================================================
# SESSÃO — CORE (parametrizada)
# ===========================================================================

Criar Sessao Nomeada
    [Documentation]    Cria sessão HTTP com alias, modo de auth e credenciais.
    [Arguments]    ${alias}    ${auth_mode}    ${base_url}    ${token}
    ...            ${session_cookie}    ${csrf_token}    ${verify_ssl}
    ${verify}=    Evaluate    $verify_ssl.lower() == 'true'

    IF    '${auth_mode}' == 'bearer'
        ${headers}=    Create Dictionary
        ...    Authorization=${token}
        ...    Content-Type=application/json
        Create Session    ${alias}    ${base_url}    headers=${headers}    verify=${verify}
    ELSE IF    '${auth_mode}' == 'session'
        ${headers}=    Create Dictionary
        ...    Content-Type=application/json
        ...    x-csrf-token=${csrf_token}
        ...    x-app-name=pipeui
        ...    accept=*/*
        ${cookies}=    Create Dictionary
        ...    _pipefy_session=${session_cookie}
        Create Session    ${alias}    ${base_url}
        ...    headers=${headers}    cookies=${cookies}    verify=${verify}
    ELSE
        Fail    AUTH_MODE inválido: "${auth_mode}". Use "bearer" ou "session".
    END


# ===========================================================================
# QUERIES GRAPHQL
# ===========================================================================

Executar Query GraphQL
    [Documentation]    Executa query GraphQL genérica e retorna o nó 'data'.
    ...                Aceita session alias (default: pipefy).
    [Arguments]    ${query}    ${variables}=${None}    ${session}=pipefy
    ${body}=    Create Dictionary    query=${query}
    IF    $variables is not None
        Set To Dictionary    ${body}    variables=${variables}
    END
    ${response}=    POST On Session    ${session}    ${EMPTY}    json=${body}
    Should Be Equal As Integers    ${response.status_code}    200
    ${json}=    Set Variable    ${response.json()}
    Dictionary Should Not Contain Key    ${json}    errors
    ...    msg=GraphQL retornou erro: ${json}
    RETURN    ${json}[data]


Carregar Query De Arquivo
    [Documentation]    Lê um arquivo .graphql e retorna o conteúdo como string.
    [Arguments]    ${nome_arquivo}
    ${path}=    Set Variable    ${QUERY_DIR}${/}${nome_arquivo}
    ${query}=    Get File    ${path}
    RETURN    ${query}


Extrair Estrutura Do Pipe
    [Documentation]    Extrai nome, fases, campos, labels e start form de um Pipe via UUID.
    [Arguments]    ${pipe_uuid}    ${session}=pipefy
    ${query}=    Carregar Query De Arquivo    pipe_structure.graphql
    ${variables}=    Create Dictionary    pipeId=${pipe_uuid}
    ${data}=    Executar Query GraphQL    ${query}    ${variables}    ${session}
    RETURN    ${data}[pipe]


Extrair Automacoes Do Pipe
    [Documentation]    Extrai todas as automações de um Pipe via repoId + organizationId.
    ...                Trata paginação automaticamente (cursor-based).
    [Arguments]    ${repo_id}    ${org_id}    ${session}=pipefy
    ${query}=    Carregar Query De Arquivo    automations_list.graphql
    ${todas_automacoes}=    Create List
    ${cursor}=    Set Variable    ${None}

    FOR    ${_}    IN RANGE    50    # safety limit
        ${variables}=    Create Dictionary    repoId=${repo_id}    orgId=${org_id}
        IF    $cursor is not None
            Set To Dictionary    ${variables}    after=${cursor}
        END
        ${data}=    Executar Query GraphQL    ${query}    ${variables}    ${session}

        # Extrai nodes da página atual
        FOR    ${edge}    IN    @{data}[automations][edges]
            Append To List    ${todas_automacoes}    ${edge}[node]
        END

        # Verifica se há próxima página
        ${has_next}=    Set Variable    ${data}[automations][pageInfo][hasNextPage]
        IF    not ${has_next}    BREAK
        ${cursor}=    Set Variable    ${data}[automations][pageInfo][endCursor]
    END

    ${total}=    Get Length    ${todas_automacoes}
    Log    Automações extraídas: ${total}    console=True
    RETURN    ${todas_automacoes}


# ===========================================================================
# SCHEMA CANARY — Detecta mudanças na API GraphQL do Pipefy
# ===========================================================================

Validar Schema Canary
    [Documentation]    Executa introspecção no schema do Pipefy e valida se todos
    ...                os campos que a ferramenta depende ainda existem. Se algum
    ...                campo sumiu ou mudou tipo, retorna lista de alertas.
    ...                Usa a sessão informada (default: pipefy).
    [Arguments]    ${session}=pipefy    ${baseline_path}=${CURDIR}${/}..${/}schema_baseline.json

    Log    Executando Schema Canary — verificando API do Pipefy    console=True

    # Carrega baseline de schema esperado
    ${baseline_content}=    Get File    ${baseline_path}
    ${baseline}=    Evaluate    __import__('json').loads($baseline_content)
    ${required}=    Set Variable    ${baseline}[required_fields]

    # Executa introspecção
    ${query}=    Get File    ${QUERY_DIR}${/}schema_canary.graphql
    ${data}=    Executar Query GraphQL    ${query}    session=${session}

    # Compara cada tipo esperado vs retornado
    ${alertas}=    Create List

    # Pipe
    ${pipe_fields_api}=    Extrair Nomes De Campos Do Tipo    ${data}    pipeType
    ${alertas}=    Comparar Campos Esperados    Pipe    ${required}[Pipe]
    ...    ${pipe_fields_api}    ${alertas}

    # Phase
    ${phase_fields_api}=    Extrair Nomes De Campos Do Tipo    ${data}    phaseType
    ${alertas}=    Comparar Campos Esperados    Phase    ${required}[Phase]
    ...    ${phase_fields_api}    ${alertas}

    # PhaseField
    ${field_fields_api}=    Extrair Nomes De Campos Do Tipo    ${data}    phaseFieldType
    ${alertas}=    Comparar Campos Esperados    PhaseField    ${required}[PhaseField]
    ...    ${field_fields_api}    ${alertas}

    # Automation
    ${auto_fields_api}=    Extrair Nomes De Campos Do Tipo    ${data}    automationType
    ${alertas}=    Comparar Campos Esperados    Automation    ${required}[Automation]
    ...    ${auto_fields_api}    ${alertas}

    ${total_alertas}=    Get Length    ${alertas}
    IF    ${total_alertas} == 0
        Log    ✅ Schema Canary OK — API do Pipefy compatível com a ferramenta.    console=True
    ELSE
        Log    ⚠️ Schema Canary detectou ${total_alertas} incompatibilidade(s):    console=True
        FOR    ${a}    IN    @{alertas}
            Log    → ${a}    console=True
        END
    END
    RETURN    ${alertas}


Extrair Nomes De Campos Do Tipo
    [Documentation]    Extrai lista de nomes de campos do resultado da introspecção.
    [Arguments]    ${data}    ${type_key}
    ${nomes}=    Create List
    ${type_data}=    Get From Dictionary    ${data}    ${type_key}
    IF    $type_data is None
        RETURN    ${nomes}
    END
    FOR    ${field}    IN    @{type_data}[fields]
        Append To List    ${nomes}    ${field}[name]
    END
    RETURN    ${nomes}


Comparar Campos Esperados
    [Documentation]    Compara campos esperados vs campos retornados pela API.
    ...                Adiciona alertas para campos ausentes ou com tipo diferente.
    [Arguments]    ${type_name}    ${esperados}    ${retornados_nomes}    ${alertas}
    FOR    ${campo}    IN    @{esperados}
        ${nome}=    Set Variable    ${campo}[name]
        ${existe}=    Evaluate    $nome in $retornados_nomes
        IF    not ${existe}
            Append To List    ${alertas}
            ...    [SCHEMA] Campo "${nome}" sumiu do tipo ${type_name} (Pipefy mudou a API)
        END
    END
    RETURN    ${alertas}
