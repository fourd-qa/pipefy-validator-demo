*** Settings ***
Library    RequestsLibrary
Library    JSONLibrary
Library    Collections
Library    OperatingSystem


*** Keywords ***
Criar Sessao iPaaS
    [Documentation]    Cria sessao HTTP para a API REST do Activepieces (iPaaS).
    [Arguments]    ${alias}=ipaas    ${base_url}=${IPAAS_BASE_URL}    ${token}=${IPAAS_TOKEN}

    ${headers}=    Create Dictionary
    ...    Authorization=${token}
    ...    Content-Type=application/json
    ...    accept=application/json
    Create Session    ${alias}    ${base_url}    headers=${headers}    verify=${False}
    Log    Sessao iPaaS criada: ${alias} -> ${base_url}    console=True


Extrair Flows Do Projeto
    [Documentation]    Lista todos os flows de um projeto no Activepieces.
    ...                Retorna lista de dicts com id, displayName, status, trigger, steps.
    [Arguments]    ${project_id}=${IPAAS_PROJECT_ID}    ${alias}=ipaas

    ${params}=    Create Dictionary
    ...    projectId=${project_id}
    ...    folderId=NULL
    ...    limit=1000
    ${resp}=    GET On Session    ${alias}    /flows    params=${params}
    Status Should Be    200    ${resp}

    ${flows_raw}=    Set Variable    ${resp.json()}[data]
    ${total}=    Get Length    ${flows_raw}
    Log    iPaaS: ${total} flow(s) extraidos do projeto ${project_id}    console=True

    # Normaliza cada flow pra estrutura comparavel
    ${flows}=    Create List
    FOR    ${f}    IN    @{flows_raw}
        ${flow_norm}=    Normalizar Flow    ${f}
        Append To List    ${flows}    ${flow_norm}
    END

    RETURN    ${flows}


Normalizar Flow
    [Documentation]    Transforma o JSON aninhado do Activepieces em estrutura plana comparavel.
    ...                Extrai: id, nome, status, trigger config, lista de steps achatada.
    [Arguments]    ${flow_raw}

    ${version}=    Evaluate    $flow_raw.get('version') or {}
    ${trigger}=    Evaluate    ($version.get('trigger') or {})
    ${trigger_settings}=    Evaluate    ($trigger.get('settings') or {})
    ${trigger_input}=    Evaluate    ($trigger_settings.get('input') or {})

    # Extrai lista achatada de steps (percorre a cadeia nextAction)
    ${steps}=    Extrair Cadeia De Steps    ${trigger}

    # Monta estrutura normalizada
    ${flow}=    Create Dictionary
    ...    id=${flow_raw}[id]
    ...    displayName=${{ ($version.get('displayName') or '').strip() }}
    ...    status=${flow_raw}[status]
    ...    trigger_name=${{ $trigger_settings.get('triggerName', '') or '' }}
    ...    trigger_piece=${{ $trigger_settings.get('pieceName', '') or '' }}
    ...    trigger_pipeId=${{ str($trigger_input.get('pipeId', '') or '') }}
    ...    trigger_toPhaseId=${{ str($trigger_input.get('toPhaseId', '') or '') }}
    ...    trigger_fromPhaseId=${{ str($trigger_input.get('fromPhaseId', '') or '') }}
    ...    trigger_fieldIds=${{ str($trigger_input.get('fieldIds', '') or '') }}
    ...    trigger_orgId=${{ str($trigger_input.get('organizationId', '') or '') }}
    ...    steps=${steps}
    ...    connectionIds=${{ ($version.get('connectionIds') or []) }}
    ...    state=${{ $version.get('state', '') or '' }}

    RETURN    ${flow}


Extrair Cadeia De Steps
    [Documentation]    Percorre a cadeia trigger.nextAction -> nextAction -> ...
    ...                Retorna lista plana de steps com nome, tipo, acao, URL, inputs.
    [Arguments]    ${trigger}

    ${steps}=    Create List
    ${current}=    Evaluate    ($trigger.get('nextAction') or None)

    FOR    ${i}    IN RANGE    50
        ${is_none}=    Evaluate    $current is None
        IF    ${is_none}    BREAK

        ${step}=    Extrair Info Do Step    ${current}
        Append To List    ${steps}    ${step}

        # Steps tipo ROUTER tem children (branches)
        ${tipo}=    Evaluate    ($current.get('type') or '')
        IF    '${tipo}' == 'ROUTER'
            ${children}=    Evaluate    ($current.get('children') or [])
            FOR    ${child}    IN    @{children}
                ${child_none}=    Evaluate    $child is None
                IF    not ${child_none}
                    ${child_step}=    Extrair Info Do Step    ${child}
                    Append To List    ${steps}    ${child_step}
                END
            END
        END

        ${current}=    Evaluate    ($current.get('nextAction') or None)
    END

    RETURN    ${steps}


Extrair Info Do Step
    [Documentation]    Extrai informacoes comparaveis de um step individual.
    [Arguments]    ${step}

    ${settings}=    Evaluate    ($step.get('settings') or {})
    ${input}=    Evaluate    ($settings.get('input') or {})
    ${source}=    Evaluate    ($settings.get('sourceCode') or {})

    # Extrai URL se houver (steps HTTP)
    ${url}=    Evaluate    str($input.get('url', '') or '')

    # Extrai codigo fonte se step tipo CODE
    ${code}=    Evaluate    ($source.get('code', '') or '')

    # Extrai conditions se ROUTER
    ${branches}=    Evaluate    ($settings.get('branches') or [])

    ${info}=    Create Dictionary
    ...    name=${{ $step.get('name', '') or '' }}
    ...    displayName=${{ $step.get('displayName', '') or '' }}
    ...    type=${{ $step.get('type', '') or '' }}
    ...    skip=${{ $step.get('skip', False) }}
    ...    pieceName=${{ $settings.get('pieceName', '') or '' }}
    ...    actionName=${{ $settings.get('actionName', '') or '' }}
    ...    url=${url}
    ...    code_hash=${{ __import__('hashlib').md5(($source.get('code', '') or '').encode()).hexdigest() if ($source.get('code', '') or '') else '' }}
    ...    code_preview=${{ ($source.get('code', '') or '')[:200] }}
    ...    input_keys=${{ sorted($input.keys()) if isinstance($input, dict) else [] }}
    ...    branches=${branches}

    RETURN    ${info}
