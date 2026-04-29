*** Settings ***
Documentation    Smoke tests dos endpoints HTTP do Pipefy Validator.
...              Roda contra Flask local em http://localhost:8080. Não dispara o Robot
...              de verdade (só lê endpoints idempotentes). Útil pra validar deploys
...              e checar contratos da API após mudanças.
...
...              Pré-condição: container subido com docker-compose up -d.
...              Comando: robot tests/smoke_api.robot

Library          RequestsLibrary
Library          Collections
Library          String

Suite Setup      Criar Sessao Local

*** Variables ***
${BASE_URL}      http://localhost:8080
${ALIAS}         api


*** Keywords ***
Criar Sessao Local
    Create Session    ${ALIAS}    ${BASE_URL}    verify=${False}
    ...    disable_warnings=1


*** Test Cases ***
HC-01: Tela de Configuração responde 200
    [Tags]    smoke    pages
    ${resp}=    GET On Session    ${ALIAS}    /v2/configuracao
    Status Should Be    200    ${resp}
    Should Contain    ${resp.text}    Pipefy Validator


HC-02: Redirect da raiz vai pra /v2/configuracao
    [Tags]    smoke    pages
    ${resp}=    GET On Session    ${ALIAS}    /    expected_status=any    allow_redirects=${False}
    Should Be Equal As Integers    ${resp.status_code}    302
    Should Contain    ${resp.headers}[Location]    /v2/configuracao


HC-03: Documentação responde 200 e tem conteúdo
    [Tags]    smoke    pages
    ${resp}=    GET On Session    ${ALIAS}    /v2/docs
    Status Should Be    200    ${resp}
    Should Contain    ${resp.text}    Documentação
    Should Contain    ${resp.text}    Roadmap


HC-04: Página de ajuda responde 200
    [Tags]    smoke    pages
    ${resp}=    GET On Session    ${ALIAS}    /v2/help
    Status Should Be    200    ${resp}
    ${lower}=    Convert To Lower Case    ${resp.text}
    Should Contain    ${lower}    atalho


HC-05: /healthz responde 200 sem auth
    [Tags]    smoke    pages
    ${resp}=    GET On Session    ${ALIAS}    /healthz
    Status Should Be    200    ${resp}
    ${json}=    Set Variable    ${resp.json()}
    Dictionary Should Contain Key    ${json}    ok


HC-06: /api/configs retorna lista vazia (deprecated)
    [Tags]    smoke    api
    ${resp}=    GET On Session    ${ALIAS}    /api/configs
    Status Should Be    200    ${resp}
    ${json}=    Set Variable    ${resp.json()}
    Dictionary Should Contain Key    ${json}    single
    Dictionary Should Contain Key    ${json}    cross


HC-07: /api/v2/environments retorna 410 (deprecated)
    [Tags]    smoke    api    security
    ${resp}=    GET On Session    ${ALIAS}    /api/v2/environments    expected_status=any
    Should Be Equal As Integers    ${resp.status_code}    410


HC-08: /api/environments retorna 410 (deprecated)
    [Tags]    smoke    api    security
    ${resp}=    GET On Session    ${ALIAS}    /api/environments    expected_status=any
    Should Be Equal As Integers    ${resp.status_code}    410


HC-09: /api/snapshots retorna lista
    [Tags]    smoke    api
    ${resp}=    GET On Session    ${ALIAS}    /api/snapshots
    Status Should Be    200    ${resp}
    ${data}=    Set Variable    ${resp.json()}
    Should Be True    isinstance($data, list)


HC-10: /api/batch retorna pipes com env_id
    [Tags]    smoke    api
    ${resp}=    GET On Session    ${ALIAS}    /api/batch
    Status Should Be    200    ${resp}
    ${json}=    Set Variable    ${resp.json()}
    Dictionary Should Contain Key    ${json}    pipes
    # Cada pipe configurado deve ter env_id definido (após o fix do batch multi-org)
    FOR    ${pipe}    IN    @{json}[pipes]
        Dictionary Should Contain Key    ${pipe}    env_id    msg=batch_pipes.json sem env_id em ${pipe}
        Dictionary Should Contain Key    ${pipe}    uuid_origem
        Dictionary Should Contain Key    ${pipe}    repo_origem
    END


HC-11: /api/results retorna null ou objeto válido
    [Tags]    smoke    api
    ${resp}=    GET On Session    ${ALIAS}    /api/results
    Status Should Be    200    ${resp}
    ${data}=    Set Variable    ${resp.json()}
    # Aceita null (sem run anterior) ou dict com status
    ${is_valid}=    Evaluate    $data is None or isinstance($data, dict)
    Should Be True    ${is_valid}


HC-12: /api/status sempre retorna estrutura conhecida
    [Tags]    smoke    api
    ${resp}=    GET On Session    ${ALIAS}    /api/status
    Status Should Be    200    ${resp}
    ${json}=    Set Variable    ${resp.json()}
    Dictionary Should Contain Key    ${json}    running
    Dictionary Should Contain Key    ${json}    finished
    Dictionary Should Contain Key    ${json}    logs


HC-13: POST /api/run com body inválido NÃO retorna 500
    [Tags]    smoke    api
    # Manda string ao invés de objeto JSON: server.py deve tratar defensivamente
    ${headers}=    Create Dictionary    Content-Type=application/json
    ${resp}=    POST On Session    ${ALIAS}    /api/run    data="not_a_dict"
    ...    headers=${headers}    expected_status=any
    # Aceita 400 (sem token), 409 (já em execução). Nunca 500.
    Should Be True    ${resp.status_code} != 500    msg=Server crashou com payload inválido (status=${resp.status_code})


HC-15: POST /api/run sem token retorna 400
    [Tags]    smoke    api    security
    ${headers}=    Create Dictionary    Content-Type=application/json
    ${resp}=    POST On Session    ${ALIAS}    /api/run    json={"mode":"single"}
    ...    headers=${headers}    expected_status=any
    # Sem token client-side, backend deve rejeitar 400 (a menos que outro run já em curso)
    Should Be True    ${resp.status_code} in [400, 409]    msg=esperava 400/409, veio ${resp.status_code}


HC-14: /v2/assets serve CSS sem cache
    [Tags]    smoke    pages    cache
    ${resp}=    GET On Session    ${ALIAS}    /v2/assets/tela_configuracao_v1.css
    Status Should Be    200    ${resp}
    Should Contain    ${resp.headers}[Cache-Control]    no-store
