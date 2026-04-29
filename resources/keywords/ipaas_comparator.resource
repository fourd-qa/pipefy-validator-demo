*** Settings ***
Library    Collections
Library    OperatingSystem
Library    JSONLibrary


*** Variables ***
# CSV de categorias iPaaS ativas (IF, IT, IS). Vazio = todas.
${CATEGORIES_FILTER}    ${EMPTY}


*** Keywords ***
Categoria iPaaS Habilitada
    [Documentation]    Retorna True se a categoria iPaaS está em CATEGORIES_FILTER.
    ...                Filtro vazio = roda todas. Tags válidas: IF, IT, IS.
    [Arguments]    ${cat}
    IF    '${CATEGORIES_FILTER}' == '${EMPTY}' or '${CATEGORIES_FILTER}' == ''
        RETURN    ${True}
    END
    ${found}=    Evaluate    '${cat}' in '${CATEGORIES_FILTER}'.split(',')
    RETURN    ${found}


Comparar Flows iPaaS
    [Documentation]    Compara flows do iPaaS entre Origem e Destino.
    ...                Retorna lista de divergencias no mesmo formato do Pipefy Validator.
    ...                Respeita CATEGORIES_FILTER pra IF/IT/IS.
    [Arguments]    ${flows_origem}    ${flows_destino}

    ${divergencias}=    Create List

    # Mapa por displayName
    ${map_orig}=    Create Dictionary
    FOR    ${f}    IN    @{flows_origem}
        Set To Dictionary    ${map_orig}    ${f}[displayName]=${f}
    END

    ${map_dest}=    Create Dictionary
    FOR    ${f}    IN    @{flows_destino}
        Set To Dictionary    ${map_dest}    ${f}[displayName]=${f}
    END

    # 1. Inventário (categoria IF) — flows ausentes e extras
    ${run_if}=    Categoria iPaaS Habilitada    IF
    IF    ${run_if}
        FOR    ${f}    IN    @{flows_origem}
            ${existe}=    Run Keyword And Return Status
            ...    Dictionary Should Contain Key    ${map_dest}    ${f}[displayName]
            IF    not ${existe}
                Append To List    ${divergencias}
                ...    [IPAAS FLOW AUSENTE] "${f}[displayName]" existe na Origem mas NAO no Destino
            END
        END

        FOR    ${f}    IN    @{flows_destino}
            ${existe}=    Run Keyword And Return Status
            ...    Dictionary Should Contain Key    ${map_orig}    ${f}[displayName]
            IF    not ${existe}
                Append To List    ${divergencias}
                ...    [IPAAS FLOW EXTRA] "${f}[displayName]" existe no Destino mas NAO na Origem
            END
        END
    END

    # 2. Compara cada flow pareado
    FOR    ${f_orig}    IN    @{flows_origem}
        ${existe}=    Run Keyword And Return Status
        ...    Dictionary Should Contain Key    ${map_dest}    ${f_orig}[displayName]
        IF    ${existe}
            ${f_dest}=    Get From Dictionary    ${map_dest}    ${f_orig}[displayName]
            ${divergencias}=    Comparar Flow Individual    ${f_orig}    ${f_dest}    ${divergencias}
        END
    END

    RETURN    ${divergencias}


Comparar Flow Individual
    [Documentation]    Compara dois flows pareados (mesmo displayName).
    [Arguments]    ${orig}    ${dest}    ${divergencias}

    ${nome}=    Set Variable    ${orig}[displayName]

    # IF — Status do flow (parte de "Inventário/existência")
    ${run_if}=    Categoria iPaaS Habilitada    IF
    IF    ${run_if} and $orig['status'] != $dest['status']
        Append To List    ${divergencias}
        ...    [IPAAS FLOW STATUS] "${nome}": Origem="${orig}[status]" | Destino="${dest}[status]"
    END

    # IT — Trigger
    ${run_it}=    Categoria iPaaS Habilitada    IT
    IF    ${run_it}
        ${divergencias}=    Comparar Trigger iPaaS    ${orig}    ${dest}    ${divergencias}
    END

    # IS — Steps
    ${run_is}=    Categoria iPaaS Habilitada    IS
    IF    ${run_is}
        ${divergencias}=    Comparar Steps iPaaS    ${orig}    ${dest}    ${divergencias}
    END

    RETURN    ${divergencias}


Comparar Trigger iPaaS
    [Documentation]    Compara configuracao do trigger entre dois flows.
    [Arguments]    ${orig}    ${dest}    ${divergencias}

    ${nome}=    Set Variable    ${orig}[displayName]

    # Tipo do trigger
    IF    $orig['trigger_name'] != $dest['trigger_name']
        Append To List    ${divergencias}
        ...    [IPAAS TRIGGER TIPO] "${nome}": Origem="${orig}[trigger_name]" | Destino="${dest}[trigger_name]"
    END

    # Piece do trigger
    IF    $orig['trigger_piece'] != $dest['trigger_piece']
        Append To List    ${divergencias}
        ...    [IPAAS TRIGGER PIECE] "${nome}": Origem="${orig}[trigger_piece]" | Destino="${dest}[trigger_piece]"
    END

    # Campos que podem conter listas -- usar $ syntax pra avaliar como Python
    ${pipe_o}=    Evaluate    str($orig.get('trigger_pipeId', ''))
    ${pipe_d}=    Evaluate    str($dest.get('trigger_pipeId', ''))
    IF    $pipe_o != $pipe_d and ($pipe_o != '' or $pipe_d != '')
        Append To List    ${divergencias}
        ...    [IPAAS TRIGGER PIPE] "${nome}": PipeId Origem="${pipe_o}" | Destino="${pipe_d}"
    END

    ${phase_o}=    Evaluate    str($orig.get('trigger_toPhaseId', ''))
    ${phase_d}=    Evaluate    str($dest.get('trigger_toPhaseId', ''))
    IF    $phase_o != $phase_d and ($phase_o != '' or $phase_d != '')
        Append To List    ${divergencias}
        ...    [IPAAS TRIGGER FASE] "${nome}": toPhaseId Origem="${phase_o}" | Destino="${phase_d}"
    END

    ${fields_o}=    Evaluate    str($orig.get('trigger_fieldIds', ''))
    ${fields_d}=    Evaluate    str($dest.get('trigger_fieldIds', ''))
    IF    $fields_o != $fields_d and ($fields_o != '' or $fields_d != '')
        Append To List    ${divergencias}
        ...    [IPAAS TRIGGER CAMPOS] "${nome}": fieldIds Origem="${fields_o}" | Destino="${fields_d}"
    END

    ${org_o}=    Evaluate    str($orig.get('trigger_orgId', ''))
    ${org_d}=    Evaluate    str($dest.get('trigger_orgId', ''))
    IF    $org_o != $org_d and ($org_o != '' or $org_d != '')
        Append To List    ${divergencias}
        ...    [IPAAS TRIGGER ORG] "${nome}": orgId Origem="${org_o}" | Destino="${org_d}"
    END

    RETURN    ${divergencias}


Comparar Steps iPaaS
    [Documentation]    Compara a cadeia de steps entre dois flows.
    [Arguments]    ${orig}    ${dest}    ${divergencias}

    ${nome}=    Set Variable    ${orig}[displayName]
    ${steps_orig}=    Set Variable    ${orig}[steps]
    ${steps_dest}=    Set Variable    ${dest}[steps]

    ${count_orig}=    Get Length    ${steps_orig}
    ${count_dest}=    Get Length    ${steps_dest}

    # Quantidade de steps diferente
    IF    ${count_orig} != ${count_dest}
        Append To List    ${divergencias}
        ...    [IPAAS STEP COUNT] "${nome}": Origem=${count_orig} steps | Destino=${count_dest} steps
    END

    # Compara step a step (pelo indice, pois a ordem importa)
    ${min_count}=    Evaluate    min(${count_orig}, ${count_dest})
    FOR    ${i}    IN RANGE    ${min_count}
        ${s_orig}=    Evaluate    $steps_orig[${i}]
        ${s_dest}=    Evaluate    $steps_dest[${i}]
        ${step_name}=    Evaluate    $s_orig.get('displayName', $s_orig.get('name', 'step_${i}'))

        # Tipo do step
        ${t_orig}=    Evaluate    $s_orig.get('type', '')
        ${t_dest}=    Evaluate    $s_dest.get('type', '')
        IF    $t_orig != $t_dest
            Append To List    ${divergencias}
            ...    [IPAAS STEP TIPO] "${nome}" > "${step_name}": Tipo Origem="${t_orig}" | Destino="${t_dest}"
        END

        # Acao (actionName)
        ${a_orig}=    Evaluate    $s_orig.get('actionName', '')
        ${a_dest}=    Evaluate    $s_dest.get('actionName', '')
        IF    $a_orig != $a_dest
            Append To List    ${divergencias}
            ...    [IPAAS STEP ACAO] "${nome}" > "${step_name}": Acao Origem="${a_orig}" | Destino="${a_dest}"
        END

        # Piece (pieceName)
        ${p_orig}=    Evaluate    $s_orig.get('pieceName', '')
        ${p_dest}=    Evaluate    $s_dest.get('pieceName', '')
        IF    $p_orig != $p_dest
            Append To List    ${divergencias}
            ...    [IPAAS STEP PIECE] "${nome}" > "${step_name}": Piece Origem="${p_orig}" | Destino="${p_dest}"
        END

        # URL
        ${u_orig}=    Evaluate    $s_orig.get('url', '')
        ${u_dest}=    Evaluate    $s_dest.get('url', '')
        IF    $u_orig != $u_dest and ($u_orig != '' or $u_dest != '')
            Append To List    ${divergencias}
            ...    [IPAAS STEP URL] "${nome}" > "${step_name}": URL Origem="${u_orig}" | Destino="${u_dest}"
        END

        # Skip (step desabilitado)
        ${sk_orig}=    Evaluate    $s_orig.get('skip', False)
        ${sk_dest}=    Evaluate    $s_dest.get('skip', False)
        IF    $sk_orig != $sk_dest
            Append To List    ${divergencias}
            ...    [IPAAS STEP SKIP] "${nome}" > "${step_name}": Skip Origem=${sk_orig} | Destino=${sk_dest}
        END

        # Codigo fonte (hash MD5 pra detectar mudancas sem mostrar o code inteiro)
        ${h_orig}=    Evaluate    $s_orig.get('code_hash', '')
        ${h_dest}=    Evaluate    $s_dest.get('code_hash', '')
        IF    $h_orig != $h_dest and ($h_orig != '' or $h_dest != '')
            Append To List    ${divergencias}
            ...    [IPAAS CODE DIFF] "${nome}" > "${step_name}": Codigo fonte diferente entre Origem e Destino
        END

        # Input keys (mapeamento de campos diferente)
        ${ik_orig}=    Evaluate    str($s_orig.get('input_keys', []))
        ${ik_dest}=    Evaluate    str($s_dest.get('input_keys', []))
        IF    $ik_orig != $ik_dest
            Append To List    ${divergencias}
            ...    [IPAAS STEP MAPPING] "${nome}" > "${step_name}": Campos mapeados diferem. Origem=${ik_orig} | Destino=${ik_dest}
        END

        # Router conditions (branches)
        ${br_orig}=    Evaluate    $s_orig.get('branches', [])
        ${br_dest}=    Evaluate    $s_dest.get('branches', [])
        ${br_orig_str}=    Evaluate    str($br_orig) if $br_orig else ''
        ${br_dest_str}=    Evaluate    str($br_dest) if $br_dest else ''
        IF    $br_orig_str != $br_dest_str and ($br_orig_str != '' or $br_dest_str != '')
            Append To List    ${divergencias}
            ...    [IPAAS ROUTER CONDITION] "${nome}" > "${step_name}": Conditions do Router diferem entre Origem e Destino
        END
    END

    RETURN    ${divergencias}


Gerar Relatorio iPaaS JSON
    [Documentation]    Gera relatorio JSON no mesmo formato do Pipefy Validator.
    [Arguments]    ${divergencias}    ${flows_origem}    ${flows_destino}    ${output_path}=results/ipaas_validations.json

    ${total}=    Get Length    ${divergencias}
    ${total_flows_orig}=    Get Length    ${flows_origem}
    ${total_flows_dest}=    Get Length    ${flows_destino}
    ${timestamp}=    Evaluate    __import__('datetime').datetime.now().isoformat()

    ${relatorio}=    Create Dictionary
    ...    status=${{ 'IDENTICOS' if ${total} == 0 else 'DIVERGENCIAS_ENCONTRADAS' }}
    ...    total_divergencias=${total}
    ...    total_flows_origem=${total_flows_orig}
    ...    total_flows_destino=${total_flows_dest}
    ...    divergencias=${divergencias}
    ...    metadata=${{ {"timestamp": "${timestamp}", "mode": "ipaas", "tool_version": "1.0"} }}

    ${json_str}=    Evaluate
    ...    __import__('json').dumps($relatorio, indent=2, ensure_ascii=False, default=str)
    Create File    ${output_path}    ${json_str}
    Log    Relatorio iPaaS salvo em: ${output_path}    console=True

    RETURN    ${relatorio}


Gerar Snapshot iPaaS
    [Documentation]    Salva o estado atual dos flows como baseline JSON.
    [Arguments]    ${flows}    ${label}=ipaas_snapshot

    ${timestamp}=    Evaluate    __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    ${filename}=    Set Variable    snapshots/${label}_${timestamp}.json

    ${total}=    Get Length    ${flows}
    ${snapshot}=    Create Dictionary
    ...    label=${label}
    ...    timestamp=${timestamp}
    ...    total_flows=${total}
    ...    flows=${flows}

    ${json_str}=    Evaluate
    ...    __import__('json').dumps($snapshot, indent=2, ensure_ascii=False, default=str)
    Create File    ${filename}    ${json_str}
    Log    Snapshot iPaaS salvo em: ${filename}    console=True

    RETURN    ${filename}


Carregar Snapshot iPaaS
    [Documentation]    Carrega um snapshot iPaaS salvo anteriormente.
    [Arguments]    ${filepath}

    ${raw}=    Get File    ${filepath}
    ${data}=    Evaluate    __import__('json').loads($raw)
    ${flows}=    Set Variable    ${data}[flows]
    ${total}=    Get Length    ${flows}
    Log    Snapshot iPaaS carregado: ${filepath} (${total} flows)    console=True

    RETURN    ${flows}
