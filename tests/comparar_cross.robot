*** Settings ***
Documentation    Validação cross-environment: compara o MESMO pipe entre dois ambientes
...              (ex: HMG vs PRD) via GraphQL. Usa dual-session (duas conexões simultâneas).

Resource         ../config/active_cross.robot
Resource         ../resources/keywords/api_session.resource
Resource         ../resources/keywords/comparator.resource
Library          Collections
Library          ../resources/libraries/ProgressLibrary.py

Suite Setup      Criar Dual Sessions


*** Test Cases ***
CT-CROSS-01: Comparação Cross-Environment Completa
    [Documentation]    Compara estrutura + automações do mesmo pipe entre dois ambientes.
    ...                Origem e Destino apontam para endpoints/tokens diferentes.
    [Tags]             cross    completo    smoke

    Limpar Progresso
    Iniciar Cronometro

    # --- Extração Estrutura ---
    Atualizar Progresso    1    7    Extraindo Pipe Origem...    running
    Registrar Log    Pipe Origem: ${ORIGEM_PIPE_UUID} (${ORIGEM_BASE_URL})
    ${pipe_origem}=    Extrair Estrutura Do Pipe    ${ORIGEM_PIPE_UUID}    pipefy_origem
    Registrar Log    Pipe Origem carregado: ${pipe_origem}[name]
    Atualizar Progresso    1    7    Pipe Origem OK    done

    Atualizar Progresso    2    7    Extraindo Pipe Destino...    running
    Registrar Log    Pipe Destino: ${DESTINO_PIPE_UUID} (${DESTINO_BASE_URL})
    ${pipe_destino}=    Extrair Estrutura Do Pipe    ${DESTINO_PIPE_UUID}    pipefy_destino
    Registrar Log    Pipe Destino carregado: ${pipe_destino}[name]
    Atualizar Progresso    2    7    Pipe Destino OK    done

    # --- Extração Automações ---
    Atualizar Progresso    3    7    Extraindo automações Origem...    running
    ${auto_origem}=    Extrair Automacoes Do Pipe
    ...    ${ORIGEM_PIPE_REPO_ID}    ${ORIGEM_ORGANIZATION_ID}    pipefy_origem
    ${qtd_orig}=    Get Length    ${auto_origem}
    Registrar Log    Automações Origem: ${qtd_orig}
    Atualizar Progresso    3    7    ${qtd_orig} automação(ões) Origem    done

    Atualizar Progresso    4    7    Extraindo automações Destino...    running
    ${auto_destino}=    Extrair Automacoes Do Pipe
    ...    ${DESTINO_PIPE_REPO_ID}    ${DESTINO_ORGANIZATION_ID}    pipefy_destino
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
