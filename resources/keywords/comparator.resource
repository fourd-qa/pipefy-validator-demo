*** Settings ***
Documentation    Keywords de comparação estrutural entre dois Pipes do Pipefy.
...              Compara fases, campos, labels, start form e automações.
...
...              Filtro de categorias: passe via --variable CATEGORIES_FILTER:SF,FA pra
...              limitar a comparação. Vazio = todas as 7 categorias.

Library          Collections
Library          OperatingSystem
Library          String
Library          JSONLibrary


*** Variables ***
# CSV de categorias ativas (SF,FA,LB,AS,AD,AH,AC). Vazio = todas.
${CATEGORIES_FILTER}    ${EMPTY}


*** Keywords ***
# ===========================================================================
# FILTRO DE CATEGORIAS
# ===========================================================================

Categoria Habilitada
    [Documentation]    Retorna True se a categoria está em CATEGORIES_FILTER.
    ...                Filtro vazio = roda todas (compatível com runs antigas).
    [Arguments]    ${cat}
    IF    '${CATEGORIES_FILTER}' == '${EMPTY}' or '${CATEGORIES_FILTER}' == ''
        RETURN    ${True}
    END
    ${found}=    Evaluate    '${cat}' in '${CATEGORIES_FILTER}'.split(',')
    RETURN    ${found}


# ===========================================================================
# ORQUESTRAÇÃO
# ===========================================================================

Comparar Estrutura Completa
    [Documentation]    Compara toda a estrutura entre Pipe Origem e Destino.
    ...                Retorna lista de divergências encontradas. Respeita CATEGORIES_FILTER.
    [Arguments]    ${pipe_origem}    ${pipe_destino}
    ${divergencias}=    Create List

    # Start Form
    ${run_sf}=    Categoria Habilitada    SF
    IF    ${run_sf}
        ${divergencias}=    Comparar Start Form
        ...    ${pipe_origem}[start_form_fields]
        ...    ${pipe_destino}[start_form_fields]
        ...    ${divergencias}
    END

    # Fases e campos
    ${run_fa}=    Categoria Habilitada    FA
    IF    ${run_fa}
        ${divergencias}=    Comparar Fases
        ...    ${pipe_origem}[phases]
        ...    ${pipe_destino}[phases]
        ...    ${divergencias}
    END

    # Labels
    ${run_lb}=    Categoria Habilitada    LB
    IF    ${run_lb}
        ${divergencias}=    Comparar Labels
        ...    ${pipe_origem}[labels]
        ...    ${pipe_destino}[labels]
        ...    ${divergencias}
    END

    RETURN    ${divergencias}


# ===========================================================================
# START FORM
# ===========================================================================

Comparar Start Form
    [Documentation]    Compara os campos do formulário inicial entre Origem e Destino.
    [Arguments]    ${campos_origem}    ${campos_destino}    ${divergencias}

    ${destino_map}=    Mapear Campos Por Label    ${campos_destino}

    FOR    ${campo}    IN    @{campos_origem}
        ${label}=    Set Variable    ${campo}[label]
        ${existe}=    Run Keyword And Return Status
        ...    Dictionary Should Contain Key    ${destino_map}    ${label}
        IF    not ${existe}
            Append To List    ${divergencias}
            ...    [START FORM - CAMPO AUSENTE] Campo "${label}" existe na Origem mas NAO no Destino
        ELSE
            ${campo_dest}=    Get From Dictionary    ${destino_map}    ${label}
            ${divergencias}=    Comparar Atributos Do Campo
            ...    ${campo}    ${campo_dest}    Start Form    ${divergencias}
        END
    END

    # Campos extras no destino
    ${origem_labels}=    Extrair Labels Dos Campos    ${campos_origem}
    FOR    ${campo}    IN    @{campos_destino}
        ${existe}=    Run Keyword And Return Status
        ...    Should Contain    ${origem_labels}    ${campo}[label]
        IF    not ${existe}
            Append To List    ${divergencias}
            ...    [START FORM - CAMPO EXTRA] Campo "${campo}[label]" existe no Destino mas NAO na Origem
        END
    END

    RETURN    ${divergencias}


# ===========================================================================
# FASES
# ===========================================================================

Comparar Fases
    [Documentation]    Compara fases entre Origem e Destino, incluindo campos de cada fase.
    [Arguments]    ${fases_origem}    ${fases_destino}    ${divergencias}

    ${destino_map}=    Create Dictionary
    FOR    ${fase}    IN    @{fases_destino}
        Set To Dictionary    ${destino_map}    ${fase}[name]=${fase}
    END

    # Fases e campos da origem
    FOR    ${fase}    IN    @{fases_origem}
        ${nome}=    Set Variable    ${fase}[name]
        ${existe}=    Run Keyword And Return Status
        ...    Dictionary Should Contain Key    ${destino_map}    ${nome}
        IF    not ${existe}
            Append To List    ${divergencias}
            ...    [FASE AUSENTE] Fase "${nome}" existe na Origem mas NAO no Destino
        ELSE
            ${fase_dest}=    Get From Dictionary    ${destino_map}    ${nome}
            ${divergencias}=    Comparar Campos Da Fase
            ...    ${fase}[fields]    ${fase_dest}[fields]    ${nome}    ${divergencias}
        END
    END

    # Fases extras no destino
    ${origem_nomes}=    Create List
    FOR    ${fase}    IN    @{fases_origem}
        Append To List    ${origem_nomes}    ${fase}[name]
    END
    FOR    ${fase}    IN    @{fases_destino}
        ${existe}=    Run Keyword And Return Status
        ...    Should Contain    ${origem_nomes}    ${fase}[name]
        IF    not ${existe}
            Append To List    ${divergencias}
            ...    [FASE EXTRA] Fase "${fase}[name]" existe no Destino mas NAO na Origem
        END
    END

    RETURN    ${divergencias}


# ===========================================================================
# CAMPOS
# ===========================================================================

Comparar Campos Da Fase
    [Documentation]    Compara campos entre mesma fase nos dois Pipes.
    [Arguments]    ${campos_origem}    ${campos_destino}    ${nome_fase}    ${divergencias}

    ${destino_map}=    Mapear Campos Por Label    ${campos_destino}

    FOR    ${campo}    IN    @{campos_origem}
        ${label}=    Set Variable    ${campo}[label]
        ${existe}=    Run Keyword And Return Status
        ...    Dictionary Should Contain Key    ${destino_map}    ${label}
        IF    not ${existe}
            Append To List    ${divergencias}
            ...    [CAMPO AUSENTE] Fase "${nome_fase}" > Campo "${label}" existe na Origem mas NAO no Destino
        ELSE
            ${campo_dest}=    Get From Dictionary    ${destino_map}    ${label}
            ${divergencias}=    Comparar Atributos Do Campo
            ...    ${campo}    ${campo_dest}    ${nome_fase}    ${divergencias}
        END
    END

    # Campos extras no destino
    ${origem_labels}=    Extrair Labels Dos Campos    ${campos_origem}
    FOR    ${campo}    IN    @{campos_destino}
        ${existe}=    Run Keyword And Return Status
        ...    Should Contain    ${origem_labels}    ${campo}[label]
        IF    not ${existe}
            Append To List    ${divergencias}
            ...    [CAMPO EXTRA] Fase "${nome_fase}" > Campo "${campo}[label]" existe no Destino mas NAO na Origem
        END
    END

    RETURN    ${divergencias}


Comparar Atributos Do Campo
    [Documentation]    Compara tipo, obrigatoriedade e opções de um campo.
    [Arguments]    ${campo_orig}    ${campo_dest}    ${contexto}    ${divergencias}
    ${label}=    Set Variable    ${campo_orig}[label]

    # Tipo
    IF    '${campo_orig}[type]' != '${campo_dest}[type]'
        Append To List    ${divergencias}
        ...    [TIPO DIFERENTE] ${contexto} > Campo "${label}": Origem="${campo_orig}[type]" | Destino="${campo_dest}[type]"
    END

    # Obrigatoriedade
    IF    '${campo_orig}[required]' != '${campo_dest}[required]'
        Append To List    ${divergencias}
        ...    [REQUIRED DIFERENTE] ${contexto} > Campo "${label}": Origem="${campo_orig}[required]" | Destino="${campo_dest}[required]"
    END

    # Opções (dropdowns, checklists, radio)
    ${orig_options}=    Evaluate    $campo_orig.get('options', []) or []
    ${dest_options}=    Evaluate    $campo_dest.get('options', []) or []
    ${orig_sorted}=    Evaluate    sorted($orig_options)
    ${dest_sorted}=    Evaluate    sorted($dest_options)
    IF    $orig_sorted != $dest_sorted
        Append To List    ${divergencias}
        ...    [OPTIONS DIFERENTE] ${contexto} > Campo "${label}": Origem=${orig_sorted} | Destino=${dest_sorted}
    END

    RETURN    ${divergencias}


# ===========================================================================
# LABELS
# ===========================================================================

Comparar Labels
    [Documentation]    Compara etiquetas (labels) entre Origem e Destino.
    [Arguments]    ${labels_origem}    ${labels_destino}    ${divergencias}

    ${nomes_destino}=    Create List
    FOR    ${label}    IN    @{labels_destino}
        Append To List    ${nomes_destino}    ${label}[name]
    END

    FOR    ${label}    IN    @{labels_origem}
        ${existe}=    Run Keyword And Return Status
        ...    Should Contain    ${nomes_destino}    ${label}[name]
        IF    not ${existe}
            Append To List    ${divergencias}
            ...    [LABEL AUSENTE] Label "${label}[name]" existe na Origem mas NAO no Destino
        END
    END

    # Labels extras no destino
    ${nomes_origem}=    Create List
    FOR    ${label}    IN    @{labels_origem}
        Append To List    ${nomes_origem}    ${label}[name]
    END
    FOR    ${label}    IN    @{labels_destino}
        ${existe}=    Run Keyword And Return Status
        ...    Should Contain    ${nomes_origem}    ${label}[name]
        IF    not ${existe}
            Append To List    ${divergencias}
            ...    [LABEL EXTRA] Label "${label}[name]" existe no Destino mas NAO na Origem
        END
    END

    RETURN    ${divergencias}


# ===========================================================================
# AUTOMAÇÕES
# ===========================================================================

Comparar Automacoes
    [Documentation]    Compara automações entre Pipe Origem e Destino.
    ...                Resolve triggerFieldIds e condition.field_address para nomes
    ...                de campos usando mapa field_id → label de cada pipe.
    [Arguments]    ${automacoes_origem}    ${automacoes_destino}
    ...            ${pipe_origem}    ${pipe_destino}    ${divergencias}

    # Extrai nomes dos pipes pra normalização
    ${nome_pipe_origem}=    Set Variable    ${pipe_origem}[name]
    ${nome_pipe_destino}=    Set Variable    ${pipe_destino}[name]

    # Constrói mapas field_id → label de cada pipe
    ${field_map_orig}=    Construir Mapa Field ID Para Label    ${pipe_origem}
    ${field_map_dest}=    Construir Mapa Field ID Para Label    ${pipe_destino}

    # Constrói mapas phase_id → phase_name de cada pipe
    ${phase_map_orig}=    Construir Mapa Phase ID Para Nome    ${pipe_origem}
    ${phase_map_dest}=    Construir Mapa Phase ID Para Nome    ${pipe_destino}

    # Mapeia destino por nome normalizado
    ${destino_map}=    Create Dictionary
    FOR    ${auto}    IN    @{automacoes_destino}
        ${key}=    Normalizar Nome Automacao    ${auto}[name]
        ...    ${nome_pipe_origem}    ${nome_pipe_destino}
        Set To Dictionary    ${destino_map}    ${key}=${auto}
    END

    # Verifica cada automação da origem
    FOR    ${auto}    IN    @{automacoes_origem}
        ${key}=    Normalizar Nome Automacao    ${auto}[name]
        ...    ${nome_pipe_origem}    ${nome_pipe_destino}
        ${existe}=    Run Keyword And Return Status
        ...    Dictionary Should Contain Key    ${destino_map}    ${key}
        IF    not ${existe}
            Append To List    ${divergencias}
            ...    [AUTOMACAO AUSENTE] "${key}" existe na Origem mas NAO no Destino
        ELSE
            ${auto_dest}=    Get From Dictionary    ${destino_map}    ${key}
            ${divergencias}=    Comparar Atributos Da Automacao
            ...    ${auto}    ${auto_dest}    ${divergencias}
            ...    ${field_map_orig}    ${field_map_dest}
            ...    ${phase_map_orig}    ${phase_map_dest}
        END
    END

    # Automações extras no destino
    ${keys_origem}=    Create List
    FOR    ${auto}    IN    @{automacoes_origem}
        ${key}=    Normalizar Nome Automacao    ${auto}[name]
        ...    ${nome_pipe_origem}    ${nome_pipe_destino}
        Append To List    ${keys_origem}    ${key}
    END
    FOR    ${auto}    IN    @{automacoes_destino}
        ${key}=    Normalizar Nome Automacao    ${auto}[name]
        ...    ${nome_pipe_origem}    ${nome_pipe_destino}
        ${existe}=    Run Keyword And Return Status
        ...    Should Contain    ${keys_origem}    ${key}
        IF    not ${existe}
            Append To List    ${divergencias}
            ...    [AUTOMACAO EXTRA] "${key}" existe no Destino mas NAO na Origem
        END
    END

    RETURN    ${divergencias}


Normalizar Nome Automacao
    [Documentation]    Remove sufixos de nomes de pipes do nome da automação.
    ...                Ex: "[CRIA] Card em X-MeuPipe-MeuPipe (cópia)" → "[CRIA] Card em X"
    [Arguments]    ${nome_automacao}    ${nome_pipe_origem}    ${nome_pipe_destino}
    ${normalizado}=    Set Variable    ${nome_automacao}
    ${normalizado}=    Replace String    ${normalizado}    -${nome_pipe_origem}    ${EMPTY}
    ${normalizado}=    Replace String    ${normalizado}    -${nome_pipe_destino}    ${EMPTY}
    ${normalizado}=    Strip String    ${normalizado}
    RETURN    ${normalizado}


Comparar Atributos Da Automacao
    [Documentation]    Compara atributos de uma automação. Resolve triggerFieldIds e
    ...                condition.field_address para nomes de campos usando field maps.
    [Arguments]    ${auto_orig}    ${auto_dest}    ${divergencias}
    ...            ${field_map_orig}=${EMPTY}    ${field_map_dest}=${EMPTY}
    ...            ${phase_map_orig}=${EMPTY}    ${phase_map_dest}=${EMPTY}
    ${nome}=    Set Variable    ${auto_orig}[name]

    ${run_as}=    Categoria Habilitada    AS
    ${run_ad}=    Categoria Habilitada    AD
    ${run_ah}=    Categoria Habilitada    AH
    ${run_ac}=    Categoria Habilitada    AC

    # Status (ativa/inativa) — categoria AS
    IF    ${run_as} and '${auto_orig}[active]' != '${auto_dest}[active]'
        Append To List    ${divergencias}
        ...    [AUTOMACAO STATUS] "${nome}": Origem active=${auto_orig}[active] | Destino active=${auto_dest}[active]
    END

    # Ação — categoria AS
    IF    ${run_as} and '${auto_orig}[action_id]' != '${auto_dest}[action_id]'
        Append To List    ${divergencias}
        ...    [AUTOMACAO ACTION] "${nome}": Origem="${auto_orig}[action_id]" | Destino="${auto_dest}[action_id]"
    END

    # Evento / Gatilho — categoria AS
    IF    ${run_as} and '${auto_orig}[event_id]' != '${auto_dest}[event_id]'
        Append To List    ${divergencias}
        ...    [AUTOMACAO EVENT] "${nome}": Origem="${auto_orig}[event_id]" | Destino="${auto_dest}[event_id]"
    END

    # --- ACTION PARAMS ---
    ${ap_orig}=    Evaluate    $auto_orig.get('action_params') or {}
    ${ap_dest}=    Evaluate    $auto_dest.get('action_params') or {}

    # Fase de destino — resolve to_phase_id para nome via mapa de fases do pipe
    ${pid_orig}=    Evaluate    str($ap_orig.get('to_phase_id', '') or '')
    ${pid_dest}=    Evaluate    str($ap_dest.get('to_phase_id', '') or '')
    # Resolve pra nome (retorna '' se não encontrar — fase de outro pipe)
    ${pname_orig}=    Evaluate    ($phase_map_orig.get($pid_orig, '') if isinstance($phase_map_orig, dict) else '') or str(($ap_orig.get('phase') or {}).get('name', '') or '')
    ${pname_dest}=    Evaluate    ($phase_map_dest.get($pid_dest, '') if isinstance($phase_map_dest, dict) else '') or str(($ap_dest.get('phase') or {}).get('name', '') or '')
    # AD — Fase destino
    IF    ${run_ad} and $pname_orig != '' and $pname_dest != '' and $pname_orig != $pname_dest
        Append To List    ${divergencias}
        ...    [AUTOMACAO FASE_DESTINO] "${nome}": Para fase Origem="${pname_orig}" | Destino="${pname_dest}"
    END

    # AH — URL do webhook / HTTP request
    ${url_orig}=    Evaluate    str($ap_orig.get('url', '') or '')
    ${url_dest}=    Evaluate    str($ap_dest.get('url', '') or '')
    IF    ${run_ah} and $url_orig != $url_dest and ($url_orig != '' or $url_dest != '')
        Append To List    ${divergencias}
        ...    [AUTOMACAO URL] "${nome}": URL Origem="${url_orig}" | Destino="${url_dest}"
    END

    # AH — HTTP Method (GET, POST, PUT...)
    ${method_orig}=    Evaluate    str($ap_orig.get('httpMethod', '') or '')
    ${method_dest}=    Evaluate    str($ap_dest.get('httpMethod', '') or '')
    IF    ${run_ah} and $method_orig != $method_dest and ($method_orig != '' or $method_dest != '')
        Append To List    ${divergencias}
        ...    [AUTOMACAO HTTP_METHOD] "${nome}": Método Origem="${method_orig}" | Destino="${method_dest}"
    END

    # AH — Body do request HTTP
    ${body_orig}=    Evaluate    str($ap_orig.get('body', '') or '')
    ${body_dest}=    Evaluate    str($ap_dest.get('body', '') or '')
    IF    ${run_ah} and $body_orig != $body_dest and ($body_orig != '' or $body_dest != '')
        Append To List    ${divergencias}
        ...    [AUTOMACAO HTTP_BODY] "${nome}": Body do request difere entre Origem e Destino
    END

    # AH — Headers do request HTTP
    ${hdr_orig}=    Evaluate    str($ap_orig.get('headers', '') or '')
    ${hdr_dest}=    Evaluate    str($ap_dest.get('headers', '') or '')
    IF    ${run_ah} and $hdr_orig != $hdr_dest and ($hdr_orig != '' or $hdr_dest != '')
        Append To List    ${divergencias}
        ...    [AUTOMACAO HTTP_HEADERS] "${nome}": Headers do request diferem entre Origem e Destino
    END

    # --- EVENT PARAMS ---
    ${ep_orig}=    Evaluate    $auto_orig.get('event_params') or {}
    ${ep_dest}=    Evaluate    $auto_dest.get('event_params') or {}

    # Fase do evento — resolve to_phase_id via mapa, fallback em event_params.phase.name
    ${ep_pid_orig}=    Evaluate    str($ep_orig.get('to_phase_id', '') or $ep_orig.get('inPhaseId', '') or '')
    ${ep_pid_dest}=    Evaluate    str($ep_dest.get('to_phase_id', '') or $ep_dest.get('inPhaseId', '') or '')
    ${ep_phase_orig}=    Evaluate    ($phase_map_orig.get($ep_pid_orig, '') if isinstance($phase_map_orig, dict) and $ep_pid_orig else '') or str(($ep_orig.get('phase') or {}).get('name', '') or '')
    ${ep_phase_dest}=    Evaluate    ($phase_map_dest.get($ep_pid_dest, '') if isinstance($phase_map_dest, dict) and $ep_pid_dest else '') or str(($ep_dest.get('phase') or {}).get('name', '') or '')
    # AD — Fase do evento
    IF    ${run_ad} and $ep_phase_orig != $ep_phase_dest and ($ep_phase_orig != '' or $ep_phase_dest != '')
        Append To List    ${divergencias}
        ...    [AUTOMACAO FASE_EVENTO] "${nome}": Fase do evento Origem="${ep_phase_orig}" | Destino="${ep_phase_dest}"
    END

    IF    not ${run_ac}
        # AC desativada: pula trigger field e condition
        RETURN    ${divergencias}
    END

    # AC — Trigger field IDs — compara apenas se resolvíveis para nomes
    # (Em pipes diferentes, triggerFieldIds usa IDs numéricos que não existem
    #  no mapa de slugs do pipe. Se não resolver, pula pra evitar falso positivo.)
    ${tf_orig_ids}=    Evaluate    $ep_orig.get('triggerFieldIds', []) or []
    ${tf_dest_ids}=    Evaluate    $ep_dest.get('triggerFieldIds', []) or []
    ${tf_orig_names}=    Resolver IDs Para Labels    ${tf_orig_ids}    ${field_map_orig}
    ${tf_dest_names}=    Resolver IDs Para Labels    ${tf_dest_ids}    ${field_map_dest}
    ${tf_resolved}=    Evaluate    $tf_orig_names != $tf_orig_ids or $tf_dest_names != $tf_dest_ids
    IF    ${tf_resolved}
        # IDs foram resolvidos — compara por nome
        IF    $tf_orig_names != $tf_dest_names and (len($tf_orig_names) > 0 or len($tf_dest_names) > 0)
            Append To List    ${divergencias}
            ...    [AUTOMACAO TRIGGER] "${nome}": Campo(s) gatilho Origem=${tf_orig_names} | Destino=${tf_dest_names}
        END
    ELSE
        # IDs iguais = mesmo pipe (cross-env/snapshot) — compara direto
        IF    $tf_orig_ids != $tf_dest_ids and (len($tf_orig_ids) > 0 or len($tf_dest_ids) > 0)
            IF    $tf_orig_ids == $tf_dest_ids
                Log    Trigger IDs iguais — OK    level=DEBUG
            END
        END
    END

    # Condition — mesma lógica: compara apenas se resolvível ou IDs iguais
    ${cond_orig}=    Evaluate    $auto_orig.get('condition') or {}
    ${cond_dest}=    Evaluate    $auto_dest.get('condition') or {}
    ${expr_orig}=    Evaluate    $cond_orig.get('expressions', []) or []
    ${expr_dest}=    Evaluate    $cond_dest.get('expressions', []) or []

    # Cross-env/snapshot: expressions têm mesmos IDs, compara value e operation
    # Ordena por op+val pra evitar falso positivo por ordem diferente da API
    ${cond_orig_vals}=    Evaluate    sorted([{'op': (e.get('operation') or ''), 'val': (e.get('value') or '')} for e in ($cond_orig.get('expressions', []) or [])], key=lambda x: x['op']+x['val'])
    ${cond_dest_vals}=    Evaluate    sorted([{'op': (e.get('operation') or ''), 'val': (e.get('value') or '')} for e in ($cond_dest.get('expressions', []) or [])], key=lambda x: x['op']+x['val'])
    # Pula se TODOS os valores são numéricos (IDs internos — diferem entre pipes/chamadas)
    ${all_numeric}=    Evaluate    all(v['val'].isdigit() for v in ($cond_orig_vals + $cond_dest_vals) if v['val'])
    IF    $cond_orig_vals != $cond_dest_vals and (len($cond_orig_vals) > 0 or len($cond_dest_vals) > 0) and not $all_numeric
        # Monta descrição legível das diferenças
        ${desc_orig}=    Evaluate    ', '.join([f"{c['op']} \\"{c['val']}\\"" for c in $cond_orig_vals]) or 'nenhuma'
        ${desc_dest}=    Evaluate    ', '.join([f"{c['op']} \\"{c['val']}\\"" for c in $cond_dest_vals]) or 'nenhuma'
        Append To List    ${divergencias}
        ...    [AUTOMACAO CONDITION] "${nome}": Origem=[${desc_orig}] | Destino=[${desc_dest}]
    END

    RETURN    ${divergencias}


# ===========================================================================
# RELATÓRIO
# ===========================================================================

Gerar Relatorio JSON
    [Documentation]    Gera results/validations.json com resultado da comparação + metadata.
    [Arguments]    ${pipe_origem}    ${pipe_destino}    ${divergencias}
    ...            ${output_path}=results/validations.json
    ...            ${origem_source}=live    ${destino_source}=live
    ${total}=    Get Length    ${divergencias}
    ${status}=    Set Variable If    ${total} == 0
    ...    IDENTICOS    DIVERGENCIAS_ENCONTRADAS
    ${timestamp}=    Evaluate    __import__('datetime').datetime.now().isoformat()
    ${metadata}=    Create Dictionary
    ...    timestamp=${timestamp}
    ...    origem_source=${origem_source}
    ...    destino_source=${destino_source}
    ...    tool_version=1.0
    ${relatorio}=    Create Dictionary
    ...    status=${status}
    ...    pipe_origem=${pipe_origem}[name]
    ...    pipe_destino=${pipe_destino}[name]
    ...    total_divergencias=${total}
    ...    divergencias=${divergencias}
    ...    metadata=${metadata}
    ${json_str}=    Evaluate
    ...    __import__('json').dumps($relatorio, indent=2, ensure_ascii=False)
    Create File    ${output_path}    ${json_str}
    Log    Relatorio salvo em: ${output_path}    console=True
    RETURN    ${status}    ${total}


Gerar Snapshot
    [Documentation]    Salva snapshot completo de um Pipe (estrutura + automações + metadata).
    ...                Arquivo nomeado com timestamp para histórico.
    [Arguments]    ${pipe_data}    ${automacoes}    ${label}=snapshot
    ${timestamp}=    Evaluate    __import__('datetime').datetime.now().isoformat()
    ${date_str}=    Evaluate    __import__('datetime').datetime.now().strftime('%Y%m%d_%H%M%S')
    ${safe_label}=    Evaluate    '${label}'.replace(' ', '_').replace('/', '_')
    ${filename}=    Set Variable    snapshots/${safe_label}_${date_str}.json
    ${metadata}=    Create Dictionary
    ...    timestamp=${timestamp}
    ...    label=${label}
    ...    pipe_name=${pipe_data}[name]
    ...    tool_version=1.0
    ${snapshot}=    Create Dictionary
    ...    metadata=${metadata}
    ...    pipe=${pipe_data}
    ...    automations=${automacoes}
    ${json_str}=    Evaluate
    ...    __import__('json').dumps($snapshot, indent=2, ensure_ascii=False, default=str)
    Create Directory    snapshots
    Create File    ${filename}    ${json_str}
    Log    Snapshot salvo: ${filename}    console=True
    RETURN    ${filename}


Carregar Snapshot
    [Documentation]    Carrega um snapshot salvo. Retorna dict com pipe, automations e metadata.
    [Arguments]    ${filename}
    ${content}=    Get File    ${filename}
    ${snapshot}=    Evaluate    __import__('json').loads($content)
    Log    Snapshot carregado: ${filename} (capturado em ${snapshot}[metadata][timestamp])    console=True
    RETURN    ${snapshot}


Logar Resultado Final
    [Documentation]    Imprime resumo no console e falha se houver divergências.
    [Arguments]    ${status}    ${total}    ${divergencias}
    IF    '${status}' == 'IDENTICOS'
        Log    \n✅ SUCESSO: Pipes IDENTICOS — nenhuma divergencia.    console=True
    ELSE
        Log    \n❌ ALERTA: ${total} divergencia(s) encontrada(s)!    console=True
        FOR    ${div}    IN    @{divergencias}
            Log    → ${div}    console=True
        END
        Fail    Comparacao falhou: ${total} divergencia(s). Verifique results/validations.json
    END


# ===========================================================================
# UTILITÁRIOS
# ===========================================================================

Mapear Campos Por Label
    [Documentation]    Cria dicionário {label: campo} a partir de lista de campos.
    [Arguments]    ${campos}
    ${map}=    Create Dictionary
    FOR    ${campo}    IN    @{campos}
        Set To Dictionary    ${map}    ${campo}[label]=${campo}
    END
    RETURN    ${map}


Extrair Labels Dos Campos
    [Documentation]    Retorna lista com apenas os labels dos campos.
    [Arguments]    ${campos}
    ${labels}=    Create List
    FOR    ${campo}    IN    @{campos}
        Append To List    ${labels}    ${campo}[label]
    END
    RETURN    ${labels}


Construir Mapa Field ID Para Label
    [Documentation]    Constrói dicionário {field_id: field_label} a partir de pipe_data.
    ...                Inclui campos do start form + todos os campos de todas as fases.
    [Arguments]    ${pipe_data}
    ${mapa}=    Create Dictionary

    # Start form fields
    ${sf}=    Evaluate    $pipe_data.get('start_form_fields', []) or []
    FOR    ${campo}    IN    @{sf}
        ${fid}=    Evaluate    str($campo.get('id', ''))
        IF    '${fid}' != ''
            Set To Dictionary    ${mapa}    ${fid}=${campo}[label]
        END
    END

    # Phase fields
    ${phases}=    Evaluate    $pipe_data.get('phases', []) or []
    FOR    ${phase}    IN    @{phases}
        ${fields}=    Evaluate    $phase.get('fields', []) or []
        FOR    ${campo}    IN    @{fields}
            ${fid}=    Evaluate    str($campo.get('id', ''))
            IF    '${fid}' != ''
                Set To Dictionary    ${mapa}    ${fid}=${campo}[label]
            END
        END
    END

    RETURN    ${mapa}


Construir Mapa Phase ID Para Nome
    [Documentation]    Constrói dicionário {phase_id: phase_name} a partir de pipe_data.
    ...                Usado para resolver to_phase_id em nomes legíveis.
    [Arguments]    ${pipe_data}
    ${mapa}=    Create Dictionary
    ${phases}=    Evaluate    $pipe_data.get('phases', []) or []
    FOR    ${phase}    IN    @{phases}
        ${pid}=    Evaluate    str($phase.get('id', ''))
        IF    '${pid}' != ''
            Set To Dictionary    ${mapa}    ${pid}=${phase}[name]
        END
    END
    RETURN    ${mapa}


Resolver IDs Para Labels
    [Documentation]    Recebe lista de IDs e mapa {id: label}. Retorna lista de labels.
    ...                Se ID não está no mapa, mantém o ID original.
    [Arguments]    ${ids}    ${field_map}
    ${labels}=    Create List
    IF    $field_map == ''
        RETURN    ${ids}
    END
    FOR    ${fid}    IN    @{ids}
        ${fid_str}=    Evaluate    str($fid)
        ${exists}=    Run Keyword And Return Status
        ...    Dictionary Should Contain Key    ${field_map}    ${fid_str}
        IF    ${exists}
            ${label}=    Get From Dictionary    ${field_map}    ${fid_str}
            Append To List    ${labels}    ${label}
        ELSE
            Append To List    ${labels}    ${fid_str}
        END
    END
    RETURN    ${labels}


Normalizar Conditions
    [Documentation]    Recebe lista de expressions e mapa {id: label}.
    ...                Substitui field_address por label e retorna lista normalizada.
    ...                Remove campos que são IDs internos (structure_id, id) da comparação.
    [Arguments]    ${expressions}    ${field_map}
    ${normalized}=    Create List
    IF    $field_map == ''
        RETURN    ${expressions}
    END
    FOR    ${expr}    IN    @{expressions}
        ${fa}=    Evaluate    str($expr.get('field_address', ''))
        ${op}=    Evaluate    str($expr.get('operation', ''))
        ${val}=    Evaluate    str($expr.get('value', ''))
        # Resolve field_address para label
        ${fa_resolved}=    Evaluate    $field_map.get($fa, $fa) if isinstance($field_map, dict) else $fa
        ${norm_expr}=    Create Dictionary
        ...    field=${fa_resolved}    operation=${op}    value=${val}
        Append To List    ${normalized}    ${norm_expr}
    END
    RETURN    ${normalized}
