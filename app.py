from flask import Flask, render_template, request, redirect, url_for, session
import random
import string
import time
import threading

from baralho import Baralho


app = Flask(__name__)
app.secret_key = "jogo-cartas-dev-2026"


salas = {}

estado_lock = threading.RLock()


TEMPO_NORMAL = 15
TEMPO_EXTRA = 5
TEMPO_TOTAL = TEMPO_NORMAL + TEMPO_EXTRA


# =========================================================
# ORDEM DAS CARTAS NA MÃO
# =========================================================

ORDEM_NAIPES = {
    "Copas": 0,
    "Ouros": 1,
    "Espadas": 2,
    "Paus": 3
}


# =========================================================
# FUNÇÕES GERAIS
# =========================================================

def gerar_codigo():

    while True:

        codigo = "".join(
            random.choices(
                string.ascii_uppercase + string.digits,
                k=4
            )
        )

        if codigo not in salas:
            return codigo


def ordem_a_partir_de(jogadores, indice_inicial):

    return (
        jogadores[indice_inicial:]
        + jogadores[:indice_inicial]
    )


def ordenar_mao(mao):

    mao.sort(
        key=lambda carta: (
            ORDEM_NAIPES[carta["naipe"]],
            carta["forca"]
        )
    )


# =========================================================
# RELÓGIO / ASTERISCOS
# =========================================================

def iniciar_relogio_turno(partida):

    partida["turno_iniciado_em"] = time.time()
    partida["asterisco_turno_aplicado"] = False


def limpar_relogio_turno(partida):

    partida["turno_iniciado_em"] = None
    partida["asterisco_turno_aplicado"] = False


def calcular_tempo_restante(partida):

    if (
        partida["fase"] != "jogando"
        or partida["turno_iniciado_em"] is None
    ):
        return None

    decorrido = (
        time.time()
        - partida["turno_iniciado_em"]
    )

    return max(
        0,
        TEMPO_TOTAL - decorrido
    )


def adicionar_asterisco(partida, jogador):

    partida["asteriscos"][jogador] += 1
    partida["total_asteriscos"][jogador] += 1

    if partida["asteriscos"][jogador] >= 3:

        partida["pontos"][jogador] -= 3
        partida["asteriscos"][jogador] = 0


# =========================================================
# CRIAÇÃO DA PARTIDA
# =========================================================

def criar_partida(sala):

    jogadores = sala["jogadores"]
    quantidade_jogadores = len(jogadores)

    max_cartas = 52 // quantidade_jogadores

    subida = list(
        range(
            3,
            max_cartas + 1
        )
    )

    descida = list(
        range(
            max_cartas - 1,
            2,
            -1
        )
    )

    sequencia_maos = subida + descida

    partida = {
        "jogadores": list(jogadores),

        "sequencia_maos": sequencia_maos,
        "indice_mao": 0,
        "max_cartas": max_cartas,

        "jogador_inicial": random.randrange(
            quantidade_jogadores
        ),

        "pontos": {
            jogador: 0
            for jogador in jogadores
        },

        "asteriscos": {
            jogador: 0
            for jogador in jogadores
        },

        "total_asteriscos": {
            jogador: 0
            for jogador in jogadores
        },

        "resultado_final": None,

        "turno_iniciado_em": None,
        "asterisco_turno_aplicado": False
    }

    sala["partida"] = partida

    preparar_mao(sala)


def preparar_mao(sala):

    partida = sala["partida"]
    jogadores = sala["jogadores"]

    cartas_por_jogador = (
        partida["sequencia_maos"][
            partida["indice_mao"]
        ]
    )

    baralho = Baralho()
    baralho.embaralhar()

    maos = {
        jogador: []
        for jogador in jogadores
    }

    # Distribuição das cartas.
    for _ in range(cartas_por_jogador):

        for jogador in jogadores:

            carta = baralho.comprar()

            maos[jogador].append(
                carta.to_dict()
            )

    # =====================================================
    # ORGANIZAÇÃO AUTOMÁTICA DAS MÃOS
    # =====================================================
    #
    # Primeiro organiza por naipe:
    #
    # Copas -> Ouros -> Espadas -> Paus
    #
    # Depois organiza cada naipe pela força:
    #
    # 2 -> 3 -> ... -> 10 -> J -> Q -> K -> A
    #
    # A própria lista usada pelo servidor é organizada.
    # Portanto, os índices das cartas continuam corretos
    # quando o jogador clica nelas.
    #
    # =====================================================

    for jogador in jogadores:

        ordenar_mao(
            maos[jogador]
        )

    # No topo não existe trunfo.
    if cartas_por_jogador == partida["max_cartas"]:

        carta_virada = None
        trunfo = None

    else:

        carta_virada = (
            baralho.comprar().to_dict()
        )

        trunfo = carta_virada["naipe"]

    partida["cartas_por_jogador"] = (
        cartas_por_jogador
    )

    partida["maos"] = maos

    partida["carta_virada"] = carta_virada
    partida["trunfo"] = trunfo

    partida["fase"] = "pedidas"

    partida["ordem_pedidas"] = ordem_a_partir_de(
        jogadores,
        partida["jogador_inicial"]
    )

    partida["indice_pedida_atual"] = 0

    partida["pedidas"] = {}

    partida["vazas"] = {
        jogador: 0
        for jogador in jogadores
    }

    partida["ordem_jogada"] = []

    partida["indice_jogada_atual"] = 0

    partida["mesa_atual"] = []

    partida["naipe_puxado"] = None

    partida["numero_vaza"] = 1

    partida["vencedor_ultima_vaza"] = None

    partida["momento_transicao_vaza"] = None

    partida["momento_transicao_mao"] = None

    partida["resultado_mao"] = {}

    limpar_relogio_turno(
        partida
    )


# =========================================================
# PEDIDAS
# =========================================================

def informacoes_pedida(partida):

    if partida["fase"] != "pedidas":
        return None, None

    ordem = partida["ordem_pedidas"]

    indice = partida[
        "indice_pedida_atual"
    ]

    if indice >= len(ordem):
        return None, None

    jogador_da_vez = ordem[indice]

    pedido_proibido = None

    ultimo_jogador = (
        indice == len(ordem) - 1
    )

    if ultimo_jogador:

        soma_anteriores = sum(
            partida["pedidas"].values()
        )

        possivel_proibido = (
            partida["cartas_por_jogador"]
            - soma_anteriores
        )

        if (
            0
            <= possivel_proibido
            <= partida["cartas_por_jogador"]
        ):

            pedido_proibido = (
                possivel_proibido
            )

    return (
        jogador_da_vez,
        pedido_proibido
    )


def iniciar_vazas(partida):

    jogadores = partida["jogadores"]

    partida["fase"] = "jogando"

    partida["ordem_jogada"] = (
        ordem_a_partir_de(
            jogadores,
            partida["jogador_inicial"]
        )
    )

    partida["indice_jogada_atual"] = 0

    partida["mesa_atual"] = []

    partida["naipe_puxado"] = None

    partida["numero_vaza"] = 1

    iniciar_relogio_turno(
        partida
    )


# =========================================================
# CARTAS VÁLIDAS
# =========================================================

def indices_cartas_validas(partida, jogador):

    mao = partida["maos"][jogador]

    if not mao:
        return []

    # Se ninguém jogou ainda,
    # qualquer carta é válida.
    if not partida["mesa_atual"]:

        return list(
            range(
                len(mao)
            )
        )

    naipe_puxado = partida[
        "naipe_puxado"
    ]

    indices_mesmo_naipe = [
        indice

        for indice, carta
        in enumerate(mao)

        if carta["naipe"] == naipe_puxado
    ]

    # Se possui o naipe puxado,
    # é obrigado a seguir.
    if indices_mesmo_naipe:

        return indices_mesmo_naipe

    # Caso contrário,
    # qualquer carta pode ser jogada.
    return list(
        range(
            len(mao)
        )
    )


# =========================================================
# VENCEDOR DA RODADA
# =========================================================

def determinar_vencedor_vaza(partida):

    mesa = partida["mesa_atual"]

    naipe_puxado = partida[
        "naipe_puxado"
    ]

    trunfo = partida["trunfo"]

    candidatos_trunfo = []

    # Se existe trunfo,
    # procura cartas do trunfo.
    if trunfo is not None:

        candidatos_trunfo = [

            jogada

            for jogada in mesa

            if (
                jogada["carta"]["naipe"]
                == trunfo
            )
        ]

    # Se alguém jogou trunfo,
    # maior trunfo vence.
    if candidatos_trunfo:

        vencedora = max(
            candidatos_trunfo,

            key=lambda jogada:
                jogada["carta"]["forca"]
        )

        return vencedora["jogador"]

    # Caso contrário,
    # maior carta do naipe puxado vence.
    candidatos_puxado = [

        jogada

        for jogada in mesa

        if (
            jogada["carta"]["naipe"]
            == naipe_puxado
        )
    ]

    vencedora = max(
        candidatos_puxado,

        key=lambda jogada:
            jogada["carta"]["forca"]
    )

    return vencedora["jogador"]


# =========================================================
# EXECUTAR JOGADA
# =========================================================

def executar_jogada(
    sala,
    jogador,
    indice,
    automatica=False
):

    partida = sala["partida"]

    if partida["fase"] != "jogando":

        return (
            False,
            "Não é hora de jogar."
        )

    ordem = partida["ordem_jogada"]

    indice_atual = partida[
        "indice_jogada_atual"
    ]

    if indice_atual >= len(ordem):

        return (
            False,
            "Jogada inválida."
        )

    jogador_da_vez = ordem[
        indice_atual
    ]

    if jogador != jogador_da_vez:

        return (
            False,
            "Não é a sua vez."
        )

    mao = partida["maos"][jogador]

    if (
        indice < 0
        or indice >= len(mao)
    ):

        return (
            False,
            "Carta inválida."
        )

    validos = indices_cartas_validas(
        partida,
        jogador
    )

    if indice not in validos:

        return (
            False,
            "Você deve seguir o naipe puxado."
        )

    carta = mao.pop(
        indice
    )

    # Primeira carta da rodada
    # define o naipe puxado.
    if not partida["mesa_atual"]:

        partida["naipe_puxado"] = (
            carta["naipe"]
        )

    partida["mesa_atual"].append(
        {
            "jogador": jogador,
            "carta": carta
        }
    )

    # Todos já jogaram.
    if (
        len(partida["mesa_atual"])
        == len(partida["jogadores"])
    ):

        vencedor = (
            determinar_vencedor_vaza(
                partida
            )
        )

        partida["vazas"][vencedor] += 1

        partida[
            "vencedor_ultima_vaza"
        ] = vencedor

        partida["fase"] = "entre_vazas"

        partida[
            "momento_transicao_vaza"
        ] = time.time()

        limpar_relogio_turno(
            partida
        )

    else:

        partida[
            "indice_jogada_atual"
        ] += 1

        iniciar_relogio_turno(
            partida
        )

    return True, None


# =========================================================
# TEMPO AUTOMÁTICO
# =========================================================

def atualizar_tempo_turno(sala):

    partida = sala["partida"]

    if partida["fase"] != "jogando":
        return

    if partida["turno_iniciado_em"] is None:

        iniciar_relogio_turno(
            partida
        )

        return

    agora = time.time()

    decorrido = (
        agora
        - partida["turno_iniciado_em"]
    )

    ordem = partida["ordem_jogada"]

    if (
        partida["indice_jogada_atual"]
        >= len(ordem)
    ):
        return

    jogador_da_vez = (
        ordem[
            partida[
                "indice_jogada_atual"
            ]
        ]
    )

    # Após 15 segundos:
    # adiciona asterisco.
    if (
        decorrido >= TEMPO_NORMAL

        and not partida[
            "asterisco_turno_aplicado"
        ]
    ):

        adicionar_asterisco(
            partida,
            jogador_da_vez
        )

        partida[
            "asterisco_turno_aplicado"
        ] = True

    # Após 20 segundos totais:
    # carta válida aleatória.
    if decorrido >= TEMPO_TOTAL:

        validos = (
            indices_cartas_validas(
                partida,
                jogador_da_vez
            )
        )

        if not validos:
            return

        indice_aleatorio = (
            random.choice(
                validos
            )
        )

        executar_jogada(
            sala,
            jogador_da_vez,
            indice_aleatorio,
            automatica=True
        )


# =========================================================
# RESULTADO DA MÃO
# =========================================================

def calcular_resultado_mao(partida):

    resultado = {}

    for jogador in partida["jogadores"]:

        pedido = partida[
            "pedidas"
        ][jogador]

        feitas = partida[
            "vazas"
        ][jogador]

        # Acertou exatamente.
        if pedido == feitas:

            variacao = 5 + pedido

        else:

            variacao = -abs(
                pedido - feitas
            )

        partida[
            "pontos"
        ][jogador] += variacao

        resultado[jogador] = {

            "pedido": pedido,

            "feitas": feitas,

            "variacao": variacao,

            "total": partida[
                "pontos"
            ][jogador]
        }

    partida["resultado_mao"] = (
        resultado
    )


# =========================================================
# RESULTADO FINAL
# =========================================================

def finalizar_partida(partida):

    ranking = []

    for jogador in partida["jogadores"]:

        ranking.append(
            {
                "nome": jogador,

                "pontos": partida[
                    "pontos"
                ][jogador],

                "asteriscos": partida[
                    "total_asteriscos"
                ][jogador]
            }
        )

    ranking.sort(
        key=lambda jogador: (
            -jogador["pontos"],
            jogador["asteriscos"],
            jogador["nome"].lower()
        )
    )

    melhor_pontuacao = ranking[
        0
    ]["pontos"]

    menor_asterisco_entre_lideres = min(

        jogador["asteriscos"]

        for jogador in ranking

        if (
            jogador["pontos"]
            == melhor_pontuacao
        )
    )

    vencedores = [

        jogador["nome"]

        for jogador in ranking

        if (
            jogador["pontos"]
            == melhor_pontuacao

            and jogador["asteriscos"]
            == menor_asterisco_entre_lideres
        )
    ]

    partida["resultado_final"] = {

        "ranking": ranking,

        "vencedores": vencedores
    }

    partida["fase"] = "fim_partida"

    limpar_relogio_turno(
        partida
    )


# =========================================================
# TRANSIÇÃO ENTRE RODADAS
# =========================================================

def atualizar_transicao_vaza(sala):

    partida = sala["partida"]

    if partida["fase"] != "entre_vazas":
        return

    momento = partida[
        "momento_transicao_vaza"
    ]

    if momento is None:
        return

    if (
        time.time() - momento
        < 2.5
    ):
        return

    terminou_mao = (
        partida["numero_vaza"]
        >= partida["cartas_por_jogador"]
    )

    # Última rodada da mão.
    if terminou_mao:

        calcular_resultado_mao(
            partida
        )

        partida["fase"] = "fim_mao"

        partida[
            "momento_transicao_mao"
        ] = time.time()

        partida["mesa_atual"] = []

        partida["naipe_puxado"] = None

        limpar_relogio_turno(
            partida
        )

        return

    # Próxima rodada começa
    # com o vencedor da anterior.
    vencedor = partida[
        "vencedor_ultima_vaza"
    ]

    indice_vencedor = (
        partida["jogadores"].index(
            vencedor
        )
    )

    partida["numero_vaza"] += 1

    partida["mesa_atual"] = []

    partida["naipe_puxado"] = None

    partida["ordem_jogada"] = (
        ordem_a_partir_de(
            partida["jogadores"],
            indice_vencedor
        )
    )

    partida["indice_jogada_atual"] = 0

    partida["fase"] = "jogando"

    partida[
        "momento_transicao_vaza"
    ] = None

    iniciar_relogio_turno(
        partida
    )


# =========================================================
# TRANSIÇÃO ENTRE MÃOS
# =========================================================

def atualizar_transicao_mao(sala):

    partida = sala["partida"]

    if partida["fase"] != "fim_mao":
        return

    momento = partida[
        "momento_transicao_mao"
    ]

    if momento is None:
        return

    if (
        time.time() - momento
        < 4
    ):
        return

    ultima_mao = (
        partida["indice_mao"]
        >= (
            len(
                partida[
                    "sequencia_maos"
                ]
            )
            - 1
        )
    )

    if ultima_mao:

        finalizar_partida(
            partida
        )

        return

    partida["indice_mao"] += 1

    # Passa o jogador inicial
    # uma posição no sentido da mesa.
    partida["jogador_inicial"] = (
        (
            partida["jogador_inicial"]
            + 1
        )
        % len(partida["jogadores"])
    )

    preparar_mao(
        sala
    )


# =========================================================
# ATUALIZAÇÃO GERAL
# =========================================================

def atualizar_estado_partida(sala):

    partida = sala["partida"]

    if partida is None:
        return

    atualizar_transicao_vaza(
        sala
    )

    atualizar_transicao_mao(
        sala
    )

    atualizar_tempo_turno(
        sala
    )


# =========================================================
# ASSINATURA DO ESTADO
# =========================================================

def gerar_assinatura_estado(sala):

    partida = sala["partida"]
    jogadores = sala["jogadores"]

    pedidos = [

        partida["pedidas"].get(
            jogador,
            None
        )

        for jogador in jogadores
    ]

    vazas = [

        partida["vazas"].get(
            jogador,
            0
        )

        for jogador in jogadores
    ]

    pontos = [

        partida["pontos"][jogador]

        for jogador in jogadores
    ]

    asteriscos = [

        partida[
            "asteriscos"
        ][jogador]

        for jogador in jogadores
    ]

    mesa = [

        [
            jogada["jogador"],
            jogada["carta"]["valor"],
            jogada["carta"]["naipe"]
        ]

        for jogada
        in partida["mesa_atual"]
    ]

    tamanhos_maos = [

        len(
            partida[
                "maos"
            ].get(
                jogador,
                []
            )
        )

        for jogador in jogadores
    ]

    return [

        partida["fase"],

        partida["indice_mao"],

        partida[
            "cartas_por_jogador"
        ],

        partida["numero_vaza"],

        partida[
            "indice_pedida_atual"
        ],

        partida[
            "indice_jogada_atual"
        ],

        pedidos,

        vazas,

        pontos,

        asteriscos,

        mesa,

        tamanhos_maos
    ]


# =========================================================
# PÁGINA INICIAL
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# =========================================================
# CRIAR SALA
# =========================================================

@app.route(
    "/criar-sala",
    methods=["POST"]
)
def criar_sala():

    nome = request.form.get(
        "nome",
        ""
    ).strip()

    try:

        numero_jogadores = int(
            request.form.get(
                "numero_jogadores",
                0
            )
        )

    except (
        TypeError,
        ValueError
    ):

        numero_jogadores = 0

    if not nome:

        return (
            "Nome inválido.",
            400
        )

    if numero_jogadores not in [
        4,
        5,
        6,
        7
    ]:

        return (
            "Quantidade de jogadores inválida.",
            400
        )

    with estado_lock:

        codigo = gerar_codigo()

        salas[codigo] = {

            "max_jogadores":
                numero_jogadores,

            "jogadores": [
                nome
            ],

            "anfitriao":
                nome,

            "iniciado":
                False,

            "partida":
                None
        }

    session["nome"] = nome

    session["codigo"] = codigo

    return redirect(
        url_for(
            "sala",
            codigo=codigo
        )
    )


# =========================================================
# ENTRAR NA SALA
# =========================================================

@app.route(
    "/entrar-sala",
    methods=["POST"]
)
def entrar_sala():

    nome = request.form.get(
        "nome",
        ""
    ).strip()

    codigo = request.form.get(
        "codigo",
        ""
    ).strip().upper()

    if not nome:

        return (
            "Nome inválido.",
            400
        )

    with estado_lock:

        if codigo not in salas:

            return (
                "Sala não encontrada.",
                404
            )

        sala_atual = salas[codigo]

        if sala_atual["iniciado"]:

            return (
                "A partida já começou.",
                400
            )

        if (
            nome
            in sala_atual["jogadores"]
        ):

            return (
                "Esse nome já está sendo usado na sala.",
                400
            )

        if (
            len(
                sala_atual["jogadores"]
            )
            >= sala_atual[
                "max_jogadores"
            ]
        ):

            return (
                "Sala cheia.",
                400
            )

        sala_atual[
            "jogadores"
        ].append(
            nome
        )

    session["nome"] = nome

    session["codigo"] = codigo

    return redirect(
        url_for(
            "sala",
            codigo=codigo
        )
    )


# =========================================================
# SALA
# =========================================================

@app.route(
    "/sala/<codigo>"
)
def sala(codigo):

    codigo = codigo.upper()

    with estado_lock:

        if codigo not in salas:

            return (
                "Sala não encontrada.",
                404
            )

        sala_atual = salas[codigo]

        nome = session.get(
            "nome"
        )

        if (
            session.get("codigo")
            != codigo

            or nome
            not in sala_atual[
                "jogadores"
            ]
        ):

            return redirect(
                url_for(
                    "index"
                )
            )

        if sala_atual["iniciado"]:

            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )

        return render_template(
            "sala.html",

            codigo=codigo,

            sala=sala_atual,

            nome=nome
        )


# =========================================================
# ESTADO DA SALA
# =========================================================

@app.route(
    "/estado-sala/<codigo>"
)
def estado_sala(codigo):

    codigo = codigo.upper()

    with estado_lock:

        if codigo not in salas:

            return {
                "erro":
                    "Sala não encontrada."
            }, 404

        sala_atual = salas[codigo]

        return {

            "jogadores":
                sala_atual["jogadores"],

            "max_jogadores":
                sala_atual[
                    "max_jogadores"
                ],

            "anfitriao":
                sala_atual["anfitriao"],

            "iniciado":
                sala_atual["iniciado"],

            "completa": (
                len(
                    sala_atual[
                        "jogadores"
                    ]
                )
                == sala_atual[
                    "max_jogadores"
                ]
            )
        }


# =========================================================
# INICIAR PARTIDA
# =========================================================

@app.route(
    "/iniciar-partida/<codigo>",
    methods=["POST"]
)
def iniciar_partida(codigo):

    codigo = codigo.upper()

    with estado_lock:

        if codigo not in salas:

            return (
                "Sala não encontrada.",
                404
            )

        sala_atual = salas[codigo]

        nome = session.get(
            "nome"
        )

        if (
            nome
            != sala_atual[
                "anfitriao"
            ]
        ):

            return (
                "Somente o dono da sala pode iniciar.",
                403
            )

        if sala_atual["iniciado"]:

            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )

        if (
            len(
                sala_atual[
                    "jogadores"
                ]
            )
            != sala_atual[
                "max_jogadores"
            ]
        ):

            return (
                "A sala ainda não está completa.",
                400
            )

        sala_atual["iniciado"] = True

        criar_partida(
            sala_atual
        )

    return redirect(
        url_for(
            "jogo",
            codigo=codigo
        )
    )


# =========================================================
# ESTADO DO JOGO
# =========================================================

@app.route(
    "/estado-jogo/<codigo>"
)
def estado_jogo(codigo):

    codigo = codigo.upper()

    with estado_lock:

        if codigo not in salas:

            return {
                "erro":
                    "Sala não encontrada."
            }, 404

        sala_atual = salas[codigo]

        nome = session.get(
            "nome"
        )

        if (
            session.get("codigo")
            != codigo

            or nome
            not in sala_atual[
                "jogadores"
            ]
        ):

            return {
                "erro":
                    "Jogador inválido."
            }, 403

        if not sala_atual[
            "iniciado"
        ]:

            return {
                "erro":
                    "Partida não iniciada."
            }, 400

        atualizar_estado_partida(
            sala_atual
        )

        partida = sala_atual[
            "partida"
        ]

        return {

            "assinatura":
                gerar_assinatura_estado(
                    sala_atual
                ),

            "tempo_restante":
                calcular_tempo_restante(
                    partida
                )
        }


# =========================================================
# JOGO
# =========================================================

@app.route(
    "/jogo/<codigo>"
)
def jogo(codigo):

    codigo = codigo.upper()

    with estado_lock:

        if codigo not in salas:

            return (
                "Sala não encontrada.",
                404
            )

        sala_atual = salas[codigo]

        nome = session.get(
            "nome"
        )

        if (
            session.get("codigo")
            != codigo

            or nome
            not in sala_atual[
                "jogadores"
            ]
        ):

            return redirect(
                url_for(
                    "index"
                )
            )

        if not sala_atual[
            "iniciado"
        ]:

            return redirect(
                url_for(
                    "sala",
                    codigo=codigo
                )
            )

        atualizar_estado_partida(
            sala_atual
        )

        partida = sala_atual[
            "partida"
        ]

        minha_mao = (
            partida[
                "maos"
            ].get(
                nome,
                []
            )
        )

        jogador_da_vez_pedido = None

        pedido_proibido = None

        jogador_da_vez_jogada = None

        indices_validos = []

        erro_pedido = session.pop(
            "erro_pedido",
            None
        )

        erro_jogada = session.pop(
            "erro_jogada",
            None
        )

        if (
            partida["fase"]
            == "pedidas"
        ):

            (
                jogador_da_vez_pedido,
                pedido_proibido
            ) = informacoes_pedida(
                partida
            )

        elif (
            partida["fase"]
            == "jogando"
        ):

            ordem = partida[
                "ordem_jogada"
            ]

            if (
                partida[
                    "indice_jogada_atual"
                ]
                < len(ordem)
            ):

                jogador_da_vez_jogada = (
                    ordem[
                        partida[
                            "indice_jogada_atual"
                        ]
                    ]
                )

            if (
                jogador_da_vez_jogada
                == nome
            ):

                indices_validos = (
                    indices_cartas_validas(
                        partida,
                        nome
                    )
                )

        tempo_total_restante = (
            calcular_tempo_restante(
                partida
            )
        )

        assinatura_estado = (
            gerar_assinatura_estado(
                sala_atual
            )
        )

        return render_template(
            "jogo.html",

            codigo=codigo,

            sala=sala_atual,

            nome=nome,

            partida=partida,

            minha_mao=minha_mao,

            jogador_da_vez_pedido=(
                jogador_da_vez_pedido
            ),

            pedido_proibido=(
                pedido_proibido
            ),

            jogador_da_vez_jogada=(
                jogador_da_vez_jogada
            ),

            indices_validos=(
                indices_validos
            ),

            erro_pedido=erro_pedido,

            erro_jogada=erro_jogada,

            tempo_total_restante=(
                tempo_total_restante
            ),

            assinatura_estado=(
                assinatura_estado
            )
        )


# =========================================================
# FAZER PEDIDO
# =========================================================

@app.route(
    "/fazer-pedido/<codigo>",
    methods=["POST"]
)
def fazer_pedido(codigo):

    codigo = codigo.upper()

    with estado_lock:

        if codigo not in salas:

            return (
                "Sala não encontrada.",
                404
            )

        sala_atual = salas[codigo]

        nome = session.get(
            "nome"
        )

        if (
            session.get("codigo")
            != codigo

            or nome
            not in sala_atual[
                "jogadores"
            ]
        ):

            return redirect(
                url_for(
                    "index"
                )
            )

        partida = sala_atual[
            "partida"
        ]

        atualizar_estado_partida(
            sala_atual
        )

        if (
            partida["fase"]
            != "pedidas"
        ):

            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )

        (
            jogador_da_vez,
            pedido_proibido
        ) = informacoes_pedida(
            partida
        )

        if jogador_da_vez != nome:

            session[
                "erro_pedido"
            ] = (
                "Não é a sua vez de pedir."
            )

            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )

        try:

            pedido = int(
                request.form.get(
                    "pedido"
                )
            )

        except (
            TypeError,
            ValueError
        ):

            session[
                "erro_pedido"
            ] = (
                "Pedido inválido."
            )

            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )

        if not (
            0
            <= pedido
            <= partida[
                "cartas_por_jogador"
            ]
        ):

            session[
                "erro_pedido"
            ] = (
                "Pedido inválido."
            )

            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )

        if (
            pedido_proibido
            is not None

            and pedido
            == pedido_proibido
        ):

            session[
                "erro_pedido"
            ] = (
                "Esse pedido faria a soma "
                "ser igual ao número de rodadas."
            )

            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )

        partida[
            "pedidas"
        ][nome] = pedido

        terminou_pedidas = (
            partida[
                "indice_pedida_atual"
            ]
            >= (
                len(
                    partida[
                        "ordem_pedidas"
                    ]
                )
                - 1
            )
        )

        if terminou_pedidas:

            iniciar_vazas(
                partida
            )

        else:

            partida[
                "indice_pedida_atual"
            ] += 1

    return redirect(
        url_for(
            "jogo",
            codigo=codigo
        )
    )


# =========================================================
# JOGAR CARTA
# =========================================================

@app.route(
    "/jogar-carta/<codigo>",
    methods=["POST"]
)
def jogar_carta(codigo):

    codigo = codigo.upper()

    with estado_lock:

        if codigo not in salas:

            return (
                "Sala não encontrada.",
                404
            )

        sala_atual = salas[codigo]

        nome = session.get(
            "nome"
        )

        if (
            session.get("codigo")
            != codigo

            or nome
            not in sala_atual[
                "jogadores"
            ]
        ):

            return redirect(
                url_for(
                    "index"
                )
            )

        atualizar_estado_partida(
            sala_atual
        )

        try:

            indice = int(
                request.form.get(
                    "indice_carta"
                )
            )

        except (
            TypeError,
            ValueError
        ):

            session[
                "erro_jogada"
            ] = (
                "Carta inválida."
            )

            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )

        sucesso, erro = (
            executar_jogada(
                sala_atual,
                nome,
                indice
            )
        )

        if not sucesso:

            session[
                "erro_jogada"
            ] = erro

    return redirect(
        url_for(
            "jogo",
            codigo=codigo
        )
    )


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=False,
        threaded=True
    )
