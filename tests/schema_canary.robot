*** Settings ***
Documentation    Schema Canary — Detecta mudanças na API GraphQL do Pipefy.
...              Roda uma introspecção e compara contra o schema baseline da ferramenta.
...              Se o Pipefy deprecia, renomeia ou muda tipo de campo, alerta antes
...              que a comparação de ambientes retorne falsos positivos/negativos.

Resource         ../config/active.robot
Resource         ../resources/keywords/api_session.resource
Resource         ../resources/keywords/comparator.resource
Library          Collections
Library          ../resources/libraries/ProgressLibrary.py

Suite Setup      Criar Sessao Pipefy


*** Test Cases ***
CT07: Schema Canary - Verificar API Pipefy
    [Documentation]    Valida que a API GraphQL do Pipefy continua compatível
    ...                com os campos que a ferramenta consome. Falha se houver
    ...                mudanças de schema não-refletidas no baseline.
    [Tags]             canary    schema    smoke

    Limpar Progresso
    Iniciar Cronometro

    Atualizar Progresso    1    2    Executando introspecção da API...    running
    Registrar Log    Consultando schema GraphQL do Pipefy
    ${alertas}=    Validar Schema Canary
    Atualizar Progresso    1    2    Schema verificado    done

    Atualizar Progresso    2    2    Avaliando resultado...    running
    ${total}=    Get Length    ${alertas}
    ${tempo}=    Registrar Tempo Total

    IF    ${total} == 0
        Registrar Log    Schema compatível — nenhuma mudança detectada
        Atualizar Progresso    2    2    API compatível    done
        Log    \n✅ Schema Canary PASSOU em ${tempo}. API do Pipefy compatível.    console=True
    ELSE
        Registrar Log    ${total} incompatibilidade(s) de schema detectada(s)
        Atualizar Progresso    2    2    ${total} alerta(s) de schema    done
        Log    \n⚠️ Schema Canary detectou ${total} mudança(s) na API:    console=True
        FOR    ${a}    IN    @{alertas}
            Log    → ${a}    console=True
        END
        Fail    Schema do Pipefy mudou. Revisar ferramenta antes de confiar em comparações. Alertas: ${total}
    END
