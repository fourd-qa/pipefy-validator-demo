*** Settings ***
Documentation    Validação técnica: compara estrutura de dois Pipes no Pipefy via GraphQL.
...              Garante que fases, campos, labels, start form e automações são idênticos
...              entre o Pipe Origem e o Pipe Destino após instalação/deploy.

Resource         ../config/active.robot
Resource         ../resources/keywords/api_session.resource
Resource         ../resources/keywords/comparator.resource
Library          Collections
Library          ../resources/libraries/ProgressLibrary.py

Suite Setup      Criar Sessao Pipefy


*** Test Cases ***
CT01: Comparação Estrutural Completa
    [Documentation]    Extrai a estrutura dos dois Pipes e compara fases, campos,
    ...                labels, start form e automações. Falha se houver qualquer divergência.
    [Tags]             structural    completo    smoke

    Limpar Progresso
    Iniciar Cronometro

    # --- Extração Estrutura ---
    Atualizar Progresso    1    7    Extraindo Pipe Origem...    running
    Registrar Log    Consultando Pipe Origem: ${PIPE_ORIGEM_UUID}
    ${pipe_origem}=    Extrair Estrutura Do Pipe    ${PIPE_ORIGEM_UUID}
    Registrar Log    Pipe Origem carregado: ${pipe_origem}[name]
    Atualizar Progresso    1    7    Pipe Origem OK    done

    Atualizar Progresso    2    7    Extraindo Pipe Destino...    running
    Registrar Log    Consultando Pipe Destino: ${PIPE_DESTINO_UUID}
    ${pipe_destino}=    Extrair Estrutura Do Pipe    ${PIPE_DESTINO_UUID}
    Registrar Log    Pipe Destino carregado: ${pipe_destino}[name]
    Atualizar Progresso    2    7    Pipe Destino OK    done

    # --- Extração Automações ---
    Atualizar Progresso    3    7    Extraindo automações Origem...    running
    Registrar Log    Consultando automações do Pipe Origem: ${PIPE_ORIGEM_REPO_ID}
    ${auto_origem}=    Extrair Automacoes Do Pipe    ${PIPE_ORIGEM_REPO_ID}    ${ORGANIZATION_ID}
    ${qtd_orig}=    Get Length    ${auto_origem}
    Registrar Log    Automações Origem: ${qtd_orig}
    Atualizar Progresso    3    7    ${qtd_orig} automação(ões) Origem    done

    Atualizar Progresso    4    7    Extraindo automações Destino...    running
    Registrar Log    Consultando automações do Pipe Destino: ${PIPE_DESTINO_REPO_ID}
    ${auto_destino}=    Extrair Automacoes Do Pipe    ${PIPE_DESTINO_REPO_ID}    ${ORGANIZATION_ID}
    ${qtd_dest}=    Get Length    ${auto_destino}
    Registrar Log    Automações Destino: ${qtd_dest}
    Atualizar Progresso    4    7    ${qtd_dest} automação(ões) Destino    done

    # --- Comparação ---
    Atualizar Progresso    5    7    Comparando estruturas...    running
    Registrar Log    Iniciando comparação estrutural completa
    ${divergencias}=    Comparar Estrutura Completa    ${pipe_origem}    ${pipe_destino}

    Registrar Log    Iniciando comparação de automações
    ${divergencias}=    Comparar Automacoes    ${auto_origem}    ${auto_destino}
    ...    ${pipe_origem}    ${pipe_destino}    ${divergencias}

    ${total}=    Get Length    ${divergencias}
    Registrar Log    Comparação concluída: ${total} divergência(s)
    Atualizar Progresso    5    7    ${total} divergência(s)    done

    # --- Relatório ---
    Atualizar Progresso    6    7    Gerando relatório...    running
    ${status}    ${total}=    Gerar Relatorio JSON
    ...    pipe_origem=${pipe_origem}
    ...    pipe_destino=${pipe_destino}
    ...    divergencias=${divergencias}
    Atualizar Progresso    6    7    Relatório salvo    done

    # --- Resultado ---
    Atualizar Progresso    7    7    Finalizando...    running
    ${tempo}=    Registrar Tempo Total
    Registrar Log    Execução finalizada em ${tempo}
    Atualizar Progresso    7    7    Concluído em ${tempo}    done

    Logar Resultado Final    ${status}    ${total}    ${divergencias}


CT02: Sanity Check — Apenas Nomes das Fases
    [Documentation]    Valida somente os nomes das fases. Validação rápida.
    [Tags]             sanity    rapido

    ${pipe_origem}=    Extrair Estrutura Do Pipe    ${PIPE_ORIGEM_UUID}
    ${pipe_destino}=    Extrair Estrutura Do Pipe    ${PIPE_DESTINO_UUID}

    ${fases_origem}=    Create List
    FOR    ${fase}    IN    @{pipe_origem}[phases]
        Append To List    ${fases_origem}    ${fase}[name]
    END

    ${fases_destino}=    Create List
    FOR    ${fase}    IN    @{pipe_destino}[phases]
        Append To List    ${fases_destino}    ${fase}[name]
    END

    Log    Fases Origem : ${fases_origem}    console=True
    Log    Fases Destino: ${fases_destino}    console=True
    Lists Should Be Equal    ${fases_origem}    ${fases_destino}
    ...    msg=Fases diferem entre Origem e Destino!
    Log    ✅ Fases idênticas nos dois Pipes.    console=True


CT03: Validar Apenas Start Form
    [Documentation]    Compara somente os campos do formulário inicial.
    [Tags]             start_form    rapido

    ${pipe_origem}=    Extrair Estrutura Do Pipe    ${PIPE_ORIGEM_UUID}
    ${pipe_destino}=    Extrair Estrutura Do Pipe    ${PIPE_DESTINO_UUID}

    ${divergencias}=    Create List
    ${divergencias}=    Comparar Start Form
    ...    ${pipe_origem}[start_form_fields]
    ...    ${pipe_destino}[start_form_fields]
    ...    ${divergencias}

    ${total}=    Get Length    ${divergencias}
    IF    ${total} == 0
        Log    ✅ Start Form idêntico nos dois Pipes.    console=True
    ELSE
        FOR    ${div}    IN    @{divergencias}
            Log    → ${div}    console=True
        END
        Fail    Start Form diverge: ${total} diferença(s).
    END


CT04: Validar Apenas Automações
    [Documentation]    Compara somente as automações entre Origem e Destino.
    ...                Valida nome, status, gatilho, ação, condições e parâmetros.
    [Tags]             automations    rapido

    # Extrai nomes dos pipes (necessário para normalizar nomes das automações)
    ${pipe_origem}=    Extrair Estrutura Do Pipe    ${PIPE_ORIGEM_UUID}
    ${pipe_destino}=    Extrair Estrutura Do Pipe    ${PIPE_DESTINO_UUID}

    ${auto_origem}=    Extrair Automacoes Do Pipe    ${PIPE_ORIGEM_REPO_ID}    ${ORGANIZATION_ID}
    ${auto_destino}=    Extrair Automacoes Do Pipe    ${PIPE_DESTINO_REPO_ID}    ${ORGANIZATION_ID}

    ${qtd_orig}=    Get Length    ${auto_origem}
    ${qtd_dest}=    Get Length    ${auto_destino}
    Log    Automações Origem: ${qtd_orig} | Destino: ${qtd_dest}    console=True

    ${divergencias}=    Create List
    ${divergencias}=    Comparar Automacoes    ${auto_origem}    ${auto_destino}
    ...    ${pipe_origem}    ${pipe_destino}    ${divergencias}

    ${total}=    Get Length    ${divergencias}
    IF    ${total} == 0
        Log    ✅ Automações idênticas nos dois Pipes.    console=True
    ELSE
        FOR    ${div}    IN    @{divergencias}
            Log    → ${div}    console=True
        END
        Fail    Automações divergem: ${total} diferença(s).
    END
