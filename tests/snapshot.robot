*** Settings ***
Documentation    Geração e comparação com snapshots (baseline de pipes).
...              Permite congelar o estado de um pipe antes do deploy e comparar depois.

Resource         ../config/active.robot
Resource         ../resources/keywords/api_session.resource
Resource         ../resources/keywords/comparator.resource
Library          Collections
Library          OperatingSystem
Library          ../resources/libraries/ProgressLibrary.py

Suite Setup      Criar Sessao Pipefy


*** Variables ***
${SNAPSHOT_LABEL}    %{SNAPSHOT_LABEL=pipe_snapshot}
${SNAPSHOT_FILE}     %{SNAPSHOT_FILE=}


*** Test Cases ***
CT05: Gerar Snapshot Do Pipe
    [Documentation]    Extrai estrutura + automações de um pipe e salva como baseline JSON
    ...                em snapshots/{label}_{timestamp}.json.
    ...                Usar antes do deploy para congelar o estado aprovado.
    [Tags]             snapshot    gerar

    Limpar Progresso
    Iniciar Cronometro

    Atualizar Progresso    1    3    Extraindo estrutura do Pipe...    running
    Registrar Log    Consultando Pipe: ${PIPE_ORIGEM_UUID}
    ${pipe_data}=    Extrair Estrutura Do Pipe    ${PIPE_ORIGEM_UUID}
    Registrar Log    Pipe carregado: ${pipe_data}[name]
    Atualizar Progresso    1    3    Estrutura OK    done

    Atualizar Progresso    2    3    Extraindo automações...    running
    ${automacoes}=    Extrair Automacoes Do Pipe    ${PIPE_ORIGEM_REPO_ID}    ${ORGANIZATION_ID}
    ${qtd}=    Get Length    ${automacoes}
    Registrar Log    Automações extraídas: ${qtd}
    Atualizar Progresso    2    3    ${qtd} automação(ões)    done

    Atualizar Progresso    3    3    Salvando snapshot...    running
    ${filename}=    Gerar Snapshot    ${pipe_data}    ${automacoes}    ${SNAPSHOT_LABEL}
    ${tempo}=    Registrar Tempo Total
    Registrar Log    Snapshot gerado em ${tempo}: ${filename}
    Atualizar Progresso    3    3    Snapshot salvo    done

    # Gera validations.json pra o frontend reconhecer
    ${result}=    Create Dictionary
    ...    snapshot_generated=${True}
    ...    snapshot_file=${filename}
    ...    timestamp=${tempo}
    ...    pipe_name=${pipe_data}[name]
    ...    automacoes=${qtd}
    ${json_str}=    Evaluate
    ...    __import__('json').dumps($result, indent=2, ensure_ascii=False, default=str)
    Create File    results/validations.json    ${json_str}

    Log    \n✅ Snapshot salvo: ${filename}    console=True
    Log    Baseline capturado em ${tempo}. Use CT06 para comparar futuramente.    console=True


CT06: Comparar Pipe Contra Snapshot
    [Documentation]    Compara o estado atual de um pipe contra um snapshot salvo.
    ...                Requer variável SNAPSHOT_FILE apontando para o arquivo em snapshots/.
    [Tags]             snapshot    comparar

    Limpar Progresso
    Iniciar Cronometro

    # Valida que foi informado um snapshot
    IF    '${SNAPSHOT_FILE}' == ''
        Fail    Variável SNAPSHOT_FILE não informada. Use: robot --variable SNAPSHOT_FILE:snapshots/nome.json
    END

    # --- Carrega snapshot (baseline) ---
    Atualizar Progresso    1    5    Carregando snapshot baseline...    running
    Registrar Log    Carregando snapshot: ${SNAPSHOT_FILE}
    ${snapshot}=    Carregar Snapshot    ${SNAPSHOT_FILE}
    ${pipe_origem}=    Set Variable    ${snapshot}[pipe]
    ${auto_origem}=    Set Variable    ${snapshot}[automations]
    ${ts}=    Set Variable    ${snapshot}[metadata][timestamp]
    Registrar Log    Baseline capturado em: ${ts}
    Atualizar Progresso    1    5    Baseline carregado    done

    # --- Extrai ambiente atual ---
    Atualizar Progresso    2    5    Extraindo Pipe atual...    running
    ${pipe_destino}=    Extrair Estrutura Do Pipe    ${PIPE_DESTINO_UUID}
    Registrar Log    Pipe atual: ${pipe_destino}[name]
    Atualizar Progresso    2    5    Pipe atual OK    done

    Atualizar Progresso    3    5    Extraindo automações atuais...    running
    ${auto_destino}=    Extrair Automacoes Do Pipe    ${PIPE_DESTINO_REPO_ID}    ${ORGANIZATION_ID}
    ${qtd}=    Get Length    ${auto_destino}
    Registrar Log    Automações atuais: ${qtd}
    Atualizar Progresso    3    5    ${qtd} automação(ões)    done

    # --- Comparação ---
    Atualizar Progresso    4    5    Comparando baseline vs atual...    running
    Registrar Log    Iniciando comparação baseline vs estado atual
    ${divergencias}=    Comparar Estrutura Completa    ${pipe_origem}    ${pipe_destino}
    ${divergencias}=    Comparar Automacoes    ${auto_origem}    ${auto_destino}
    ...    ${pipe_origem}    ${pipe_destino}    ${divergencias}
    ${total}=    Get Length    ${divergencias}
    Registrar Log    Comparação concluída: ${total} divergência(s)
    Atualizar Progresso    4    5    ${total} divergência(s)    done

    # --- Relatório com metadata ---
    Atualizar Progresso    5    5    Gerando relatório...    running
    ${status}    ${total}=    Gerar Relatorio JSON
    ...    pipe_origem=${pipe_origem}
    ...    pipe_destino=${pipe_destino}
    ...    divergencias=${divergencias}
    ...    origem_source=snapshot:${SNAPSHOT_FILE}
    ...    destino_source=live
    ${tempo}=    Registrar Tempo Total
    Registrar Log    Execução finalizada em ${tempo}
    Atualizar Progresso    5    5    Concluído em ${tempo}    done

    Logar Resultado Final    ${status}    ${total}    ${divergencias}
