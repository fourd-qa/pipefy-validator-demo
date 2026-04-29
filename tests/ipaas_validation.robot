*** Settings ***
Documentation    Validação iPaaS: compara flows do Activepieces entre ambientes.
...              Self-check: mesmo projeto vs mesmo projeto = 0 divergências.

Resource         ../config/ipaas_fourd.robot
Resource         ../resources/keywords/ipaas_session.resource
Resource         ../resources/keywords/ipaas_comparator.resource
Library          Collections
Library          ../resources/libraries/ProgressLibrary.py

Suite Setup      Criar Sessao iPaaS


*** Variables ***
${IPAAS_SNAPSHOT_LABEL}     ipaas_snapshot
${IPAAS_SNAPSHOT_FILE}      ${EMPTY}


*** Test Cases ***
CT-IPAAS-01: Self-Check iPaaS
    [Documentation]    Extrai flows do mesmo projeto duas vezes e compara.
    ...                Deve dar 0 divergências (self-check).
    [Tags]             ipaas    selfcheck

    Limpar Progresso
    Iniciar Cronometro

    # Extrai flows (duas chamadas ao mesmo projeto)
    Atualizar Progresso    1    4    Extraindo flows (chamada 1)...    running
    ${flows_origem}=    Extrair Flows Do Projeto    ${IPAAS_PROJECT_ID}
    ${total}=    Get Length    ${flows_origem}
    Registrar Log    Origem: ${total} flow(s) extraidos

    Atualizar Progresso    2    4    Extraindo flows (chamada 2)...    running
    ${flows_destino}=    Extrair Flows Do Projeto    ${IPAAS_PROJECT_ID}
    Registrar Log    Destino: ${total} flow(s) extraidos

    # Compara
    Atualizar Progresso    3    4    Comparando flows...    running
    ${divergencias}=    Comparar Flows iPaaS    ${flows_origem}    ${flows_destino}

    # Relatorio
    ${relatorio}=    Gerar Relatorio iPaaS JSON    ${divergencias}    ${flows_origem}    ${flows_destino}
    ${total_div}=    Get Length    ${divergencias}

    ${tempo}=    Registrar Tempo Total
    Atualizar Progresso    4    4    Concluido em ${tempo}!    done

    # Resumo
    Log    \n==================================================    console=True
    Log    iPaaS SELF-CHECK CONCLUIDO em ${tempo}    console=True
    Log    Flows: ${total} | Divergencias: ${total_div}    console=True
    Log    ==================================================    console=True

    IF    ${total_div} > 0
        FOR    ${d}    IN    @{divergencias}
            Log    -> ${d}    console=True
        END
        Fail    iPaaS self-check falhou: ${total_div} divergencia(s). Verifique results/ipaas_validations.json
    ELSE
        Log    ✅ iPaaS SELF-CHECK: 0 divergencias, ${total} flows validados    console=True
    END


CT-IPAAS-02: Inventario De Flows
    [Documentation]    Lista todos os flows com status e trigger.
    ...                Util pra auditoria e documentacao.
    [Tags]             ipaas    inventario

    Limpar Progresso
    Iniciar Cronometro

    Atualizar Progresso    1    2    Extraindo flows...    running
    ${flows}=    Extrair Flows Do Projeto    ${IPAAS_PROJECT_ID}
    ${total}=    Get Length    ${flows}

    Atualizar Progresso    2    2    Gerando inventario...    done

    ${tempo}=    Registrar Tempo Total

    Log    \n==================================================    console=True
    Log    iPaaS INVENTARIO - ${total} flow(s) em ${tempo}    console=True
    Log    ==================================================    console=True
    FOR    ${f}    IN    @{flows}
        ${steps}=    Set Variable    ${f}[steps]
        ${n_steps}=    Get Length    ${steps}
        ${icon}=    Set Variable If    '${f}[status]' == 'ENABLED'    ✅    ❌
        Log    ${icon} ${f}[displayName] | ${f}[status] | trigger=${f}[trigger_name] | ${n_steps} steps    console=True
    END
    Log    ==================================================    console=True

    # Salva inventario como JSON
    ${timestamp}=    Evaluate    __import__('datetime').datetime.now().isoformat()
    ${inventario}=    Create Dictionary
    ...    total_flows=${total}
    ...    timestamp=${timestamp}
    ...    flows=${flows}
    ${json_str}=    Evaluate
    ...    __import__('json').dumps($inventario, indent=2, ensure_ascii=False, default=str)
    Create File    results/ipaas_inventario.json    ${json_str}
    Log    Inventario salvo em: results/ipaas_inventario.json    console=True

    # Gera resultado pro frontend
    ${empty_list}=    Create List
    ${result}=    Create Dictionary
    ...    status=IDENTICOS
    ...    total_divergencias=${0}
    ...    total_flows_origem=${total}
    ...    total_flows_destino=${total}
    ...    divergencias=${empty_list}
    ...    inventario=${True}
    ...    metadata=${{ {"timestamp": "${timestamp}", "mode": "ipaas_inventario"} }}
    ${result_json}=    Evaluate
    ...    __import__('json').dumps($result, indent=2, ensure_ascii=False, default=str)
    Create File    results/ipaas_validations.json    ${result_json}


CT-IPAAS-03: Gerar Snapshot iPaaS
    [Documentation]    Congela o estado atual dos flows como baseline.
    ...                Uso: --variable IPAAS_SNAPSHOT_LABEL:pre_deploy
    [Tags]             ipaas    snapshot

    Limpar Progresso
    Iniciar Cronometro

    Atualizar Progresso    1    3    Extraindo flows...    running
    ${flows}=    Extrair Flows Do Projeto    ${IPAAS_PROJECT_ID}
    ${total}=    Get Length    ${flows}
    Registrar Log    ${total} flow(s) extraidos

    Atualizar Progresso    2    3    Gerando snapshot...    running
    ${filepath}=    Gerar Snapshot iPaaS    ${flows}    ${IPAAS_SNAPSHOT_LABEL}

    ${tempo}=    Registrar Tempo Total
    Atualizar Progresso    3    3    Snapshot salvo em ${tempo}!    done

    # Gera resultado pra o frontend reconhecer
    ${result}=    Create Dictionary
    ...    snapshot_generated=${True}
    ...    snapshot_file=${filepath}
    ...    timestamp=${tempo}
    ...    total_flows=${total}
    ${json_str}=    Evaluate
    ...    __import__('json').dumps($result, indent=2, ensure_ascii=False, default=str)
    Create File    results/ipaas_validations.json    ${json_str}

    Log    \n==================================================    console=True
    Log    iPaaS SNAPSHOT GERADO em ${tempo}    console=True
    Log    Arquivo: ${filepath}    console=True
    Log    Flows: ${total}    console=True
    Log    ==================================================    console=True


CT-IPAAS-04: Comparar vs Snapshot iPaaS
    [Documentation]    Compara o estado atual dos flows contra um baseline salvo.
    ...                Uso: --variable IPAAS_SNAPSHOT_FILE:snapshots/ipaas_snapshot_20260422.json
    [Tags]             ipaas    snapshot

    Limpar Progresso
    Iniciar Cronometro

    Should Not Be Empty    ${IPAAS_SNAPSHOT_FILE}
    ...    Informe o arquivo de baseline com --variable IPAAS_SNAPSHOT_FILE:snapshots/arquivo.json

    # Carrega baseline
    Atualizar Progresso    1    4    Carregando baseline...    running
    ${flows_baseline}=    Carregar Snapshot iPaaS    ${IPAAS_SNAPSHOT_FILE}
    ${total_base}=    Get Length    ${flows_baseline}
    Registrar Log    Baseline: ${total_base} flow(s) carregados de ${IPAAS_SNAPSHOT_FILE}

    # Extrai estado atual
    Atualizar Progresso    2    4    Extraindo flows atuais...    running
    ${flows_atual}=    Extrair Flows Do Projeto    ${IPAAS_PROJECT_ID}
    ${total_atual}=    Get Length    ${flows_atual}
    Registrar Log    Atual: ${total_atual} flow(s) extraidos

    # Compara
    Atualizar Progresso    3    4    Comparando...    running
    ${divergencias}=    Comparar Flows iPaaS    ${flows_baseline}    ${flows_atual}

    # Relatorio
    ${relatorio}=    Gerar Relatorio iPaaS JSON    ${divergencias}    ${flows_baseline}    ${flows_atual}
    ${total_div}=    Get Length    ${divergencias}

    ${tempo}=    Registrar Tempo Total
    Atualizar Progresso    4    4    Concluido em ${tempo}!    done

    Log    \n==================================================    console=True
    Log    iPaaS SNAPSHOT COMPARISON em ${tempo}    console=True
    Log    Baseline: ${total_base} flows | Atual: ${total_atual} flows    console=True
    Log    Divergencias: ${total_div}    console=True
    Log    ==================================================    console=True

    IF    ${total_div} > 0
        FOR    ${d}    IN    @{divergencias}
            Log    -> ${d}    console=True
        END
        Fail    iPaaS snapshot: ${total_div} divergencia(s). Verifique results/ipaas_validations.json
    ELSE
        Log    ✅ iPaaS: 0 divergencias vs baseline    console=True
    END
