*** Settings ***
Documentation    Validação batch: compara múltiplos pares de pipes de uma vez.
...              Lê pares de config/batch_pipes.json e gera relatório consolidado.

Resource         ../config/active.robot
Resource         ../resources/keywords/api_session.resource
Resource         ../resources/keywords/comparator.resource
Library          Collections
Library          OperatingSystem
Library          ../resources/libraries/ProgressLibrary.py

Suite Setup      Criar Sessao Pipefy


*** Variables ***
${BATCH_ENV}         ${EMPTY}
${BATCH_SELECTED}    ${EMPTY}


*** Test Cases ***
CT-BATCH-01: Validação Batch De Múltiplos Pipes
    [Documentation]    Compara todos os pares de pipes listados em config/batch_pipes.json.
    ...                Gera relatório consolidado com total de divergências por pipe.
    [Tags]             batch    completo

    Limpar Progresso
    Iniciar Cronometro

    # Carrega config batch
    ${config_raw}=    Get File    config/batch_pipes.json
    ${config}=    Evaluate    __import__('json').loads($config_raw)
    ${all_pipes}=    Set Variable    ${config}[pipes]

    # Filtra pipes por BATCH_ENV (enviado via --variable pelo backend).
    # Cada pipe tem env_id; só roda os que batem com o ambiente ativo.
    # Isso evita PERMISSION_DENIED ao rodar pipes de outra organização.
    IF    '${BATCH_ENV}' == ''
        ${pipes}=    Set Variable    ${all_pipes}
        Log    BATCH_ENV não definido, rodando todos os ${{len($all_pipes)}} pipes    console=True
    ELSE
        ${pipes}=    Evaluate    [p for p in $all_pipes if p.get('env_id') == '${BATCH_ENV}']
        Log    Filtro BATCH_ENV=${BATCH_ENV}: ${{len($pipes)}} de ${{len($all_pipes)}} pipes    console=True
    END

    # Filtro adicional por seleção da UI (lista de UUIDs origem em CSV)
    IF    '${BATCH_SELECTED}' != ''
        ${selected_uuids}=    Evaluate    set('${BATCH_SELECTED}'.split(','))
        ${pipes}=    Evaluate    [p for p in $pipes if p.get('uuid_origem') in $selected_uuids]
        Log    Filtro BATCH_SELECTED: ${{len($pipes)}} pipes selecionados na UI    console=True
    END

    ${total_pipes}=    Get Length    ${pipes}
    IF    ${total_pipes} == 0
        Fail    Nenhum pipe configurado para o ambiente '${batch_env}' em config/batch_pipes.json.
    END
    Log    Batch: ${total_pipes} par(es) de pipes para validar    console=True

    # Resultado consolidado
    ${resultados}=    Create List
    ${total_divergencias_geral}=    Set Variable    ${0}

    # Loop por cada par
    FOR    ${idx}    ${par}    IN ENUMERATE    @{pipes}
        ${num}=    Evaluate    ${idx} + 1
        ${nome_par}=    Set Variable    ${par}[nome]
        Log    \n━━━ [${num}/${total_pipes}] ${nome_par} ━━━    console=True
        Registrar Log    Validando pipe ${num}/${total_pipes}: ${nome_par}

        # Extrai estrutura
        Atualizar Progresso    ${num}    ${total_pipes}    Extraindo ${nome_par}...    running
        ${pipe_orig}=    Extrair Estrutura Do Pipe    ${par}[uuid_origem]
        ${pipe_dest}=    Extrair Estrutura Do Pipe    ${par}[uuid_destino]
        Log    Origem: ${pipe_orig}[name] | Destino: ${pipe_dest}[name]    console=True

        # Extrai automações
        ${auto_orig}=    Extrair Automacoes Do Pipe    ${par}[repo_origem]    ${ORGANIZATION_ID}
        ${auto_dest}=    Extrair Automacoes Do Pipe    ${par}[repo_destino]    ${ORGANIZATION_ID}

        # Compara
        ${divergencias}=    Comparar Estrutura Completa    ${pipe_orig}    ${pipe_dest}
        ${divergencias}=    Comparar Automacoes    ${auto_orig}    ${auto_dest}
        ...    ${pipe_orig}    ${pipe_dest}    ${divergencias}

        ${total_div}=    Get Length    ${divergencias}
        ${total_divergencias_geral}=    Evaluate    ${total_divergencias_geral} + ${total_div}

        # Coleta resultado do par
        ${resultado_par}=    Create Dictionary
        ...    nome=${nome_par}
        ...    pipe_origem=${pipe_orig}[name]
        ...    pipe_destino=${pipe_dest}[name]
        ...    total_divergencias=${total_div}
        ...    divergencias=${divergencias}
        Append To List    ${resultados}    ${resultado_par}

        IF    ${total_div} == 0
            Log    ✅ ${nome_par}: 0 divergências    console=True
        ELSE
            Log    ❌ ${nome_par}: ${total_div} divergência(s)    console=True
        END

        Atualizar Progresso    ${num}    ${total_pipes}    ${nome_par}: ${total_div} div.    done
    END

    # Gera relatório consolidado
    ${timestamp}=    Evaluate    __import__('datetime').datetime.now().isoformat()
    ${relatorio}=    Create Dictionary
    ...    status=${{ 'IDENTICOS' if ${total_divergencias_geral} == 0 else 'DIVERGENCIAS_ENCONTRADAS' }}
    ...    total_divergencias=${total_divergencias_geral}
    ...    total_pipes=${total_pipes}
    ...    pipes=${resultados}
    ...    metadata=${{ {"timestamp": "${timestamp}", "mode": "batch", "tool_version": "1.0"} }}
    ${json_str}=    Evaluate
    ...    __import__('json').dumps($relatorio, indent=2, ensure_ascii=False, default=str)
    Create File    results/validations.json    ${json_str}

    ${tempo}=    Registrar Tempo Total
    Registrar Log    Batch concluído em ${tempo}: ${total_pipes} pipe(s), ${total_divergencias_geral} divergência(s) total

    # Resumo final
    Log    \n==================================================    console=True
    Log    BATCH CONCLUÍDO em ${tempo}    console=True
    Log    ==================================================    console=True
    FOR    ${r}    IN    @{resultados}
        ${icon}=    Set Variable If    ${r}[total_divergencias] == 0    ✅    ❌
        Log    ${icon} ${r}[nome]: ${r}[total_divergencias] divergência(s)    console=True
    END
    Log    TOTAL: ${total_divergencias_geral} divergência(s) em ${total_pipes} pipe(s)    console=True
    Log    ==================================================    console=True

    IF    ${total_divergencias_geral} > 0
        Fail    Batch: ${total_divergencias_geral} divergência(s) encontrada(s) em ${total_pipes} pipe(s).
    END
