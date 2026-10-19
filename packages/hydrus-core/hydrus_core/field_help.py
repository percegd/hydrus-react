"""Textos de ajuda por campo (botão "?" da UI).

Formato por campo: título, unidade, "O que é" (1 frase leiga) e "Na simulação"
(efeito prático, inclusive de errar o valor). Revisável sem tocar na UI.
"""

FIELD_HELP = {
    "theta_r": (
        "θr — Umidade residual",
        "[cm³/cm³]",
        "Água presa nos microporos que nem a planta nem a gravidade conseguem retirar; o “piso” da umidade do solo.",
        "Define o ponto de partida da curva de retenção; θr alto demais “achata” a drenagem e atrasa a frente de molhamento.",
    ),
    "theta_s": (
        "θs — Umidade de saturação",
        "[cm³/cm³]",
        "Umidade quando todos os poros estão cheios de água (≈ porosidade total).",
        "É o “teto” — controla quanta chuva o perfil consegue armazenar antes de drenar ou escoar; θs menor que a chuva acumulada vira drenagem direta no fundo.",
    ),
    "alpha": (
        "α — Alfa",
        "[1/cm]",
        "Inverso da pressão de entrada de ar; diz a que sucção os maiores poros começam a esvaziar.",
        "α alto = solo “solta” a água fácil (curva íngreme, drenagem rápida); α baixo = retém por mais tempo e segura o nutriente junto.",
    ),
    "n": (
        "n — Índice de forma",
        "[-]",
        "Uniformidade dos tamanhos de poro; quanto maior, mais “de uma vez” o solo drena.",
        "Controla a inclinação da curva; n próximo de 1 deixa a frente de molhamento lenta e difusa, e o pico do nutriente chega atrasado e espalhado.",
    ),
    "ks": (
        "Ks — Condutividade hidráulica saturada",
        "[cm/dia]",
        "Velocidade máxima da água quando o solo está encharcado.",
        "Governa drenagem profunda e escoamento; Ks baixo com chuva forte = encharco superficial no gráfico θ(z) e lixiviação subestimada no fundo.",
    ),
    "bulk_density": (
        "ρb — Densidade do solo",
        "[g/cm³]",
        "Massa de solo seco por volume; indica compactação.",
        "Entra no retardamento dos nutrientes — solo compactado retém mais o adubo e atrasa a chegada ao fundo.",
    ),
    "disp": (
        "λ — Dispersividade",
        "[cm]",
        "Espalhamento do soluto pelos poros, além do fluxo principal da água.",
        "λ maior alarga a mancha do nutriente no perfil e adianta a primeira chegada ao fundo, mesmo com a mesma dose.",
    ),
    "domain_depth": (
        "Profundidade do perfil simulado",
        "[cm]",
        "Até onde o solo é simulado — o fundo do domínio 1D.",
        "Define o tamanho da coluna: 200 cm acompanha lixiviação profunda; raso demais corta a frente do nutriente e subestima a perda.",
    ),
    "obs_depths": (
        "Nós de observação",
        "[cm]",
        "Profundidades onde o modelo registra a umidade e a concentração ao longo do tempo (as curvas θ(t) e C(t)).",
        "Viram as séries temporais dos gráficos; sem nó na zona da raiz, não há como ver quando o nutriente passa por ela.",
    ),
    "crop_name": (
        "Cultura agrícola",
        "",
        "Nome da cultura para identificar o cenário e puxar parâmetros prontos do banco (ou personalize os valores).",
        "Só organiza o cenário; a física usa os números abaixo (profundidade, Kc e limiares), não o nome.",
    ),
    "root_depth": (
        "Profundidade radicular",
        "[cm]",
        "Até onde as raízes buscam água e nutriente.",
        "Delimita a zona de absorção: o que passa dela conta como perdido (lixiviado) no balanço e no selo de risco.",
    ),
    "kc": (
        "Coeficiente de cultura (Kc)",
        "[-]",
        "Quanto a cultura transpira em relação à referência (ET0).",
        "Multiplica a ET0 para dar a transpiração — Kc alto seca o perfil mais rápido e concentra o nutriente na solução.",
    ),
    "fed_h1": (
        "Anaerobiose (encharcado)",
        "[cm c.a.]",
        "Sucção a partir da qual o solo fica tão molhado que falta ar para a raiz (próximo de zero).",
        "Acima desse ponto a absorção zera no modelo — raiz afogada não puxa água nem nutriente.",
    ),
    "fed_h2": (
        "Aeração ótima",
        "[cm c.a.]",
        "Fim da faixa de transição do encharcado para o ideal.",
        "Entre a anaerobiose e aqui a absorção sobe de 0 a 100%; abaixo daqui a planta trabalha a pleno.",
    ),
    "fed_h3": (
        "Início do estresse hídrico",
        "[cm c.a.]",
        "Sucção em que o solo começa a segurar água com força e a planta sente falta.",
        "Abaixo desse ponto a absorção cai progressivamente — é o gatilho do estresse no gráfico e no laudo.",
    ),
    "fed_h4": (
        "Murcha permanente",
        "[cm c.a.]",
        "Sucção em que a planta não consegue mais extrair água (≈ −8000 a −15000 cm).",
        "Limite final da absorção no modelo; além dele, transpiração e uptake zeram.",
    ),
    "dose_tab": (
        "Dose do nutriente",
        "[kg/ha]",
        "Quantidade de nutriente elementar aplicada por hectare (não é dose de produto comercial — a conversão é feita no botão de fertilizante).",
        "É a massa inicial do soluto na simulação; tudo no balanço (% retido, perdido, absorvido) é fração dela.",
    ),
    "kd_tab": (
        "Kd — Coeficiente de adsorção",
        "[cm³/g]",
        "Quanto do nutriente gruda nas partículas do solo em vez de ficar dissolvido na água.",
        "Vem da literatura pela textura; Kd alto = nutriente preso (lixivia pouco), Kd ≈ 0 (nitrato) = viaja com a água. Vale por soluto. O laudo e os cartões mostram o Kd efetivo usado no transporte quando a competição (Ca) ou Langmuir o altera.",
    ),
    "disp_tab": (
        "Dispersividade da coluna (λ)",
        "[cm]",
        "Espalhamento do soluto ao atravessar os poros; padrão 0,1 × profundidade.",
        "Alarga a frente do nutriente; ajuste com valor calibrado (STANMOD/CXTFIT) quando houver ensaio.",
    ),
    "res_tab": (
        "Teor residual inicial",
        "[mg/dm³]",
        "Quanto do nutriente já existe no solo antes da adubação (análise de solo).",
        "Entra no balanço como massa pré-existente: não conta como dose aplicada, mas aparece nos perfis e na lixiviação total.",
    ),
    "release_type": (
        "Liberação do fertilizante",
        "",
        "Convencional dissolve tudo na hora; controlada libera aos poucos.",
        "Controlada espalha a entrada do soluto no tempo — pico menor e mais tardio, menos perda em chuva forte logo após aplicar.",
    ),
    "release_days": (
        "Duração nominal da liberação",
        "[dias]",
        "Em quantos dias o fertilizante de liberação controlada termina de soltar o nutriente.",
        "Janela de injeção gradual do soluto no modelo; só vale para liberação controlada.",
    ),
    "placement_mode": (
        "Posicionamento do adubo",
        "",
        "Onde o fertilizante é colocado: superfície, sulco, profundidade escolhida ou via água de irrigação.",
        "Define a camada que recebe a massa inicial — a lanço concentra no topo (lixivia mais fácil), profundo aproxima da raiz.",
    ),
    "z_top": (
        "De (profundidade inicial)",
        "[cm]",
        "Topo da camada de aplicação no posicionamento personalizado.",
        "Junto com o 'Até', delimita onde a dose entra no perfil.",
    ),
    "z_bottom": (
        "Até (profundidade final)",
        "[cm]",
        "Base da camada de aplicação no posicionamento personalizado.",
        "Precisa ser maior que o 'De'; camada fora da zona radicular vira perda direta.",
    ),
    "fert_c0": (
        "Concentração da solução injetada (C₀)",
        "[mg/L]",
        "Concentração do nutriente na água de irrigação da fertirrigação.",
        "É a condição de contorno do topo durante a injeção: C₀ alto com muita lâmina empurra o nutriente fundo rápido.",
    ),
    "fert_pulse": (
        "Duração da injeção",
        "[dias]",
        "Por quantos dias a fertirrigação injeta solução (0 = contínua no período).",
        "Limita a janela de entrada via água; após o pulso, só resta o transporte do que já entrou.",
    ),
    "rain_mm": (
        "Lâmina de chuva / irrigação",
        "[mm]",
        "Quanta água entra de uma vez no ensaio de coluna (evento único).",
        "É o pulso que empurra o nutriente para baixo; lâmina grande em solo arenoso atravessa o fundo rápido.",
    ),
    "moisture": (
        "Umidade prévia do solo",
        "[% da capacidade de campo]",
        "Quão molhado o solo já está antes de começar.",
        "Solo já úmido conduz e lixivia mais rápido desde o dia 1; seco atrasa a frente de molhamento.",
    ),
    "total_days": (
        "Duração do ensaio",
        "[dias]",
        "Por quantos dias a coluna é simulada no modo lâmina.",
        "Define o horizonte: precisa cobrir a chegada do pico ao fundo, senão a lixiviação sai subestimada.",
    ),
    "et0": (
        "ET0 — Evapotranspiração de referência",
        "[mm/dia]",
        "Demanda atmosférica do período (Penman-Monteith / valor informado).",
        "Multiplicada pelo Kc vira transpiração + evaporação, que secam o perfil e concentram o nutriente.",
    ),
    "evap": (
        "Evaporação do solo",
        "[mm/dia]",
        "Água que sai direto do solo nu (0 = derivada de ET0).",
        "Compõe a saída de água no balanço; em solo nu é a principal perda junto da drenagem.",
    ),
    "transp": (
        "Transpiração",
        "[mm/dia]",
        "Água puxada pelas raízes (0 = ET0·Kc).",
        "É o motor do uptake: sem transpiração, a planta não absorve nutriente no modelo.",
    ),
    "app_day": (
        "Dia da aplicação do fertilizante",
        "[1–365]",
        "Em que dia do ano a adubação é feita na série climática.",
        "Troca o 'quando': chuva antes da data lava solo sem adubo; chuva depois move o nutriente recém-aplicado.",
    ),
    "print_days": (
        "Dias de leitura",
        "[dias]",
        "Dias em que o perfil completo é fotografado (snapshots da evolução).",
        "Viram as curvas da evolução temporal; precisam cobrir antes e depois da aplicação para contar a história toda.",
    ),
    "window_start": (
        "Início da janela de análise",
        "[dia do ano]",
        "Primeiro dia do trecho da série que será simulado.",
        "Recorta chuva e ET0 a partir daqui; dias de leitura e aplicação fora da janela são barrados.",
    ),
    "window_end": (
        "Fim da janela de análise",
        "[dia do ano]",
        "Último dia do trecho simulado.",
        "Fecha a janela; permite simular só uma semana (rápido) em vez do ano inteiro.",
    ),
    "water_source": (
        "Fonte de água",
        "",
        "De onde vem a água: série climática do polo, planilha própria (upload) ou lâmina única de chuva/irrigação.",
        "Define o regime inteiro: série distribui chuva real no tempo, lâmina aplica um pulso único no dia zero.",
    ),
    "water_series": (
        "Série climática do polo",
        "",
        "Chuva e ET0 diários reais (NASA POWER) do polo agrícola, com ano típico, seco ou super chuvoso.",
        "Gera os eventos de água dia a dia; o total anual aparece no balanço e puxa a lixiviação do ano.",
    ),
    "water_upload": (
        "Upload de série diária",
        "",
        "Sua própria planilha de chuva (e ET0 opcional) no lugar da série do polo.",
        "Mesma mecânica da série climática, mas com os dados da sua fazenda/estação.",
    ),
}


def render_help_store() -> str:
    """Todas as ajudas pré-renderizadas (#help-store) + vista vazia (#help-view).

    O JS copia o bloco data-key para a vista e exibe o overlay — sem roundtrip.
    """
    parts = ['<div id="help-store" style="display:none;">']
    for key in FIELD_HELP:
        title, unit, what, sim = FIELD_HELP[key]
        parts.append(
            f'<div class="help-entry" data-key="{key}">'
            '<div class="help-modal-head"><div class="help-modal-icon">?</div>'
            f"<div><h3 class=\"help-modal-title\">{title} <span class=\"help-modal-unit\">{unit}</span></h3></div></div>"
            '<div class="help-modal-body">'
            f"<p><b>O que é:</b> {what}</p>"
            f"<p><b>Na simulação:</b> {sim}</p>"
            "</div></div>"
        )
    parts.append('</div><div id="help-view"></div>')
    return "".join(parts)
