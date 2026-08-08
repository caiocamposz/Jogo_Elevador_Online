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


def iniciar_relogio_turno(partida):

    partida["turno_iniciado_em"] = time.time()

    partida["asterisco_turno_aplicado"] = False


def calcular_tempo_restante(partida):

    if (
        partida["fase"] != "jogando"
        or partida["turno_iniciado_em"] is None
    ):
        return None

    tempo_passado = (
        time.time()
        - partida["turno_iniciado_em"]
    )

    return max(
        0.0,
        TEMPO_TOTAL - tempo_passado
    )


# =========================================================
# ASTERISCOS
# =========================================================

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


    # Primeiro jogador totalmente aleatório

    jogador_inicial = random.randrange(
        quantidade_jogadores
    )


    sala["partida"] = {

        "sequencia_maos":
            sequencia_maos,

        "indice_mao":
            0,

        "max_cartas":
            max_cartas,

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

        "resultado_final":
            None,

        "turno_iniciado_em":
            None,

        "asterisco_turno_aplicado":
            False,

        "ultima_jogada_automatica":
            None
    }


    preparar_mao(
        sala,
        indice_mao=0,
        jogador_inicial=jogador_inicial
    )


# =========================================================
# PREPARAR NOVA MÃO
# =========================================================

def preparar_mao(
    sala,
    indice_mao,
    jogador_inicial
):

    partida = sala["partida"]

    jogadores = sala["jogadores"]


    cartas_por_jogador = (
        partida[
            "sequencia_maos"
        ][indice_mao]
    )


    baralho = Baralho()

    baralho.embaralhar()


    maos = {
        jogador: []
        for jogador in jogadores
    }


    for _ in range(
        cartas_por_jogador
    ):

        for jogador in jogadores:

            carta = baralho.comprar()

            maos[jogador].append(
                carta.to_dict()
            )


    topo = (
        cartas_por_jogador
        == partida["max_cartas"]
    )


    if topo:

        carta_virada = None

        trunfo = None

    else:

        carta = baralho.comprar()

        carta_virada = carta.to_dict()

        trunfo = carta.naipe


    ordem_pedidas = (
        ordem_a_partir_de(
            jogadores,
            jogador_inicial
        )
    )


    partida.update({

        "indice_mao":
            indice_mao,

        "cartas_por_jogador":
            cartas_por_jogador,

        "maos":
            maos,

        "carta_virada":
            carta_virada,

        "trunfo":
            trunfo,

        "jogador_inicial":
            jogador_inicial,

        "jogador_inicial_nome":
            jogadores[jogador_inicial],

        "fase":
            "pedidas",

        "ordem_pedidas":
            ordem_pedidas,

        "indice_pedida_atual":
            0,

        "pedidas":
            {},

        "vazas": {
            jogador: 0
            for jogador in jogadores
        },

        "ordem_jogada":
            [],

        "indice_jogada_atual":
            0,

        "mesa_atual":
            [],

        "naipe_puxado":
            None,

        "numero_vaza":
            1,

        "vencedor_ultima_vaza":
            None,

        "fim_vaza_em":
            None,

        "resultado_mao":
            None,

        "fim_mao_em":
            None,

        "turno_iniciado_em":
            None,

        "asterisco_turno_aplicado":
            False,

        "ultima_jogada_automatica":
            None
    })


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
            partida[
                "pedidas"
            ].values()
        )


        possivel_proibido = (
            partida[
                "cartas_por_jogador"
            ]
            - soma_anteriores
        )


        if (
            0
            <= possivel_proibido
            <= partida[
                "cartas_por_jogador"
            ]
        ):

            pedido_proibido = (
                possivel_proibido
            )


    return (
        jogador_da_vez,
        pedido_proibido
    )


# =========================================================
# COMEÇAR VAZAS
# =========================================================

def iniciar_vazas(sala):

    partida = sala["partida"]

    jogadores = sala["jogadores"]


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

    partida["fase"] = "jogando"

    partida["ultima_jogada_automatica"] = None


    iniciar_relogio_turno(
        partida
    )


# =========================================================
# CARTAS VÁLIDAS
# =========================================================

def indices_cartas_validas(
    partida,
    jogador
):

    mao = partida["maos"][jogador]

    naipe_puxado = partida[
        "naipe_puxado"
    ]


    if naipe_puxado is None:

        return list(
            range(len(mao))
        )


    indices_do_naipe = [

        indice

        for indice, carta
        in enumerate(mao)

        if carta["naipe"]
        == naipe_puxado
    ]


    if indices_do_naipe:

        return indices_do_naipe


    return list(
        range(len(mao))
    )


# =========================================================
# VENCEDOR DA VAZA
# =========================================================

def determinar_vencedor_vaza(
    partida
):

    mesa = partida["mesa_atual"]

    trunfo = partida["trunfo"]

    naipe_puxado = partida[
        "naipe_puxado"
    ]


    cartas_trunfo = [

        jogada

        for jogada in mesa

        if (
            trunfo is not None
            and
            jogada["carta"]["naipe"]
            == trunfo
        )
    ]


    if cartas_trunfo:

        candidatas = cartas_trunfo

    else:

        candidatas = [

            jogada

            for jogada in mesa

            if (
                jogada["carta"]["naipe"]
                == naipe_puxado
            )
        ]


    vencedora = max(

        candidatas,

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
    indice_carta,
    automatica=False
):

    partida = sala["partida"]

    mao = partida["maos"][jogador]


    carta = mao.pop(
        indice_carta
    )


    if partida[
        "naipe_puxado"
    ] is None:

        partida[
            "naipe_puxado"
        ] = carta["naipe"]


    partida[
        "mesa_atual"
    ].append({

        "jogador":
            jogador,

        "carta":
            carta
    })


    if automatica:

        partida[
            "ultima_jogada_automatica"
        ] = {

            "jogador":
                jogador,

            "carta":
                carta
        }

    else:

        partida[
            "ultima_jogada_automatica"
        ] = None


    partida[
        "indice_jogada_atual"
    ] += 1


    # Todos jogaram na vaza

    if (
        partida[
            "indice_jogada_atual"
        ]
        >= len(
            sala["jogadores"]
        )
    ):

        vencedor = (
            determinar_vencedor_vaza(
                partida
            )
        )


        partida[
            "vazas"
        ][vencedor] += 1


        partida[
            "vencedor_ultima_vaza"
        ] = vencedor


        partida["fase"] = (
            "entre_vazas"
        )


        partida["fim_vaza_em"] = (
            time.time()
        )


        partida[
            "turno_iniciado_em"
        ] = None


        partida[
            "asterisco_turno_aplicado"
        ] = False


    else:

        iniciar_relogio_turno(
            partida
        )


# =========================================================
# CONTROLE DO TEMPO
# =========================================================

def atualizar_tempo_turno(sala):

    partida = sala["partida"]


    if partida["fase"] != "jogando":

        return


    if (
        partida[
            "turno_iniciado_em"
        ]
        is None
    ):

        iniciar_relogio_turno(
            partida
        )


    indice = partida[
        "indice_jogada_atual"
    ]


    if indice >= len(
        partida["ordem_jogada"]
    ):

        return


    jogador = (
        partida[
            "ordem_jogada"
        ][indice]
    )


    tempo_passado = (

        time.time()

        - partida[
            "turno_iniciado_em"
        ]
    )


    # 15 segundos:
    # recebe 1 asterisco

    if (
        tempo_passado >= TEMPO_NORMAL
        and
        not partida[
            "asterisco_turno_aplicado"
        ]
    ):

        adicionar_asterisco(
            partida,
            jogador
        )


        partida[
            "asterisco_turno_aplicado"
        ] = True


    # 20 segundos:
    # joga aleatoriamente uma carta válida

    if tempo_passado >= TEMPO_TOTAL:

        validas = (
            indices_cartas_validas(
                partida,
                jogador
            )
        )


        if not validas:

            return


        indice_aleatorio = (
            random.choice(validas)
        )


        executar_jogada(

            sala,

            jogador,

            indice_aleatorio,

            automatica=True
        )


# =========================================================
# PONTUAÇÃO
# =========================================================

def calcular_resultado_mao(
    partida
):

    resultado = {}


    for jogador in partida[
        "pedidas"
    ]:

        pedido = partida[
            "pedidas"
        ][jogador]


        feitas = partida[
            "vazas"
        ][jogador]


        if pedido == feitas:

            variacao = (
                5 + pedido
            )

        else:

            variacao = (
                -abs(
                    pedido - feitas
                )
            )


        partida[
            "pontos"
        ][jogador] += variacao


        resultado[jogador] = {

            "pedido":
                pedido,

            "feitas":
                feitas,

            "variacao":
                variacao,

            "total":
                partida[
                    "pontos"
                ][jogador]
        }


    partida[
        "resultado_mao"
    ] = resultado


# =========================================================
# FINAL DA PARTIDA
# =========================================================

def finalizar_partida(sala):

    partida = sala["partida"]

    jogadores = sala["jogadores"]


    ranking = sorted(

        jogadores,

        key=lambda jogador: (

            -partida[
                "pontos"
            ][jogador],

            partida[
                "total_asteriscos"
            ][jogador],

            jogador.lower()
        )
    )


    maior_pontuacao = (
        partida[
            "pontos"
        ][ranking[0]]
    )


    empatados_pontos = [

        jogador

        for jogador in ranking

        if (
            partida[
                "pontos"
            ][jogador]
            == maior_pontuacao
        )
    ]


    menor_asterisco = min(

        partida[
            "total_asteriscos"
        ][jogador]

        for jogador
        in empatados_pontos
    )


    vencedores = [

        jogador

        for jogador
        in empatados_pontos

        if (
            partida[
                "total_asteriscos"
            ][jogador]
            == menor_asterisco
        )
    ]


    ranking_detalhado = []


    for jogador in ranking:

        ranking_detalhado.append({

            "nome":
                jogador,

            "pontos":
                partida[
                    "pontos"
                ][jogador],

            "asteriscos":
                partida[
                    "total_asteriscos"
                ][jogador]
        })


    partida[
        "resultado_final"
    ] = {

        "ranking":
            ranking_detalhado,

        "vencedores":
            vencedores
    }


    partida["fase"] = (
        "fim_partida"
    )


# =========================================================
# TRANSIÇÃO ENTRE VAZAS
# =========================================================

def atualizar_transicao_vaza(
    sala
):

    partida = sala["partida"]


    if (
        partida["fase"]
        != "entre_vazas"
    ):

        return


    if (
        partida[
            "fim_vaza_em"
        ]
        is None
    ):

        return


    tempo_passado = (

        time.time()

        - partida[
            "fim_vaza_em"
        ]
    )


    if tempo_passado < 2.5:

        return


    # Última vaza da mão

    if (
        partida[
            "numero_vaza"
        ]
        >=
        partida[
            "cartas_por_jogador"
        ]
    ):

        calcular_resultado_mao(
            partida
        )


        partida["fase"] = (
            "fim_mao"
        )


        partida[
            "fim_mao_em"
        ] = time.time()


        return


    # Próxima vaza

    partida[
        "numero_vaza"
    ] += 1


    vencedor = partida[
        "vencedor_ultima_vaza"
    ]


    jogadores = sala[
        "jogadores"
    ]


    indice_vencedor = (
        jogadores.index(
            vencedor
        )
    )


    partida[
        "ordem_jogada"
    ] = ordem_a_partir_de(

        jogadores,

        indice_vencedor
    )


    partida[
        "indice_jogada_atual"
    ] = 0


    partida[
        "mesa_atual"
    ] = []


    partida[
        "naipe_puxado"
    ] = None


    partida[
        "fim_vaza_em"
    ] = None


    partida["fase"] = (
        "jogando"
    )


    partida[
        "ultima_jogada_automatica"
    ] = None


    iniciar_relogio_turno(
        partida
    )


# =========================================================
# TRANSIÇÃO ENTRE MÃOS
# =========================================================

def atualizar_transicao_mao(
    sala
):

    partida = sala["partida"]


    if (
        partida["fase"]
        != "fim_mao"
    ):

        return


    if (
        partida[
            "fim_mao_em"
        ]
        is None
    ):

        return


    tempo_passado = (

        time.time()

        - partida[
            "fim_mao_em"
        ]
    )


    if tempo_passado < 4:

        return


    proximo_indice = (
        partida[
            "indice_mao"
        ]
        + 1
    )


    if (
        proximo_indice
        >= len(
            partida[
                "sequencia_maos"
            ]
        )
    ):

        finalizar_partida(
            sala
        )

        return


    jogadores = sala[
        "jogadores"
    ]


    proximo_inicial = (

        partida[
            "jogador_inicial"
        ]
        + 1

    ) % len(jogadores)


    preparar_mao(

        sala,

        indice_mao=
            proximo_indice,

        jogador_inicial=
            proximo_inicial
    )


# =========================================================
# ATUALIZAR ESTADO
# =========================================================

def atualizar_estado_partida(
    sala
):

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
#
# É ISSO QUE SUBSTITUI O F5 INFINITO.
# O NAVEGADOR SÓ RECARREGA SE ALGO REALMENTE MUDOU.
# =========================================================

def gerar_assinatura_estado(
    sala
):

    partida = sala["partida"]

    jogadores = sala["jogadores"]


    pedidos = [

        partida[
            "pedidas"
        ].get(
            jogador,
            None
        )

        for jogador
        in jogadores
    ]


    vazas = [

        partida[
            "vazas"
        ].get(
            jogador,
            0
        )

        for jogador
        in jogadores
    ]


    pontos = [

        partida[
            "pontos"
        ][jogador]

        for jogador
        in jogadores
    ]


    asteriscos = [

        partida[
            "asteriscos"
        ][jogador]

        for jogador
        in jogadores
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

        for jogador
        in jogadores
    ]


    return [

        partida["fase"],

        partida["indice_mao"],

        partida[
            "cartas_por_jogador"
        ],

        partida[
            "numero_vaza"
        ],

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
def inicio():

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

    nome = request.form[
        "nome"
    ].strip()


    try:

        numero_jogadores = int(
            request.form[
                "numero_jogadores"
            ]
        )

    except (
        ValueError,
        TypeError,
        KeyError
    ):

        return (
            "Número de jogadores inválido."
        )


    if not nome:

        return "Nome inválido."


    if (
        numero_jogadores < 4
        or
        numero_jogadores > 7
    ):

        return (
            "Número de jogadores inválido."
        )


    codigo = gerar_codigo()


    salas[codigo] = {

        "max_jogadores":
            numero_jogadores,

        "jogadores":
            [nome],

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

    nome = request.form[
        "nome"
    ].strip()


    codigo = (
        request.form[
            "codigo"
        ]
        .strip()
        .upper()
    )


    if not nome:

        return "Nome inválido."


    if codigo not in salas:

        return (
            "Essa sala não existe."
        )


    sala_encontrada = salas[
        codigo
    ]


    if sala_encontrada[
        "iniciado"
    ]:

        return (
            "Essa partida já começou."
        )


    if (
        len(
            sala_encontrada[
                "jogadores"
            ]
        )
        >=
        sala_encontrada[
            "max_jogadores"
        ]
    ):

        return (
            "Essa sala já está cheia."
        )


    nomes_minusculos = [

        jogador.lower()

        for jogador
        in sala_encontrada[
            "jogadores"
        ]
    ]


    if (
        nome.lower()
        in nomes_minusculos
    ):

        return (
            "Já existe um jogador "
            "com esse nome."
        )


    sala_encontrada[
        "jogadores"
    ].append(nome)


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


    if codigo not in salas:

        return (
            "Sala não encontrada."
        )


    nome = session.get(
        "nome"
    )


    if (
        session.get(
            "codigo"
        )
        != codigo

        or

        nome not in salas[
            codigo
        ][
            "jogadores"
        ]
    ):

        return redirect(
            url_for(
                "inicio"
            )
        )


    if salas[
        codigo
    ][
        "iniciado"
    ]:

        return redirect(
            url_for(
                "jogo",
                codigo=codigo
            )
        )


    return render_template(

        "sala.html",

        codigo=codigo,

        sala=salas[codigo],

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


    if codigo not in salas:

        return {
            "erro":
                "Sala não encontrada."
        }, 404


    sala_atual = salas[codigo]


    return {

        "codigo":
            codigo,

        "jogadores":
            sala_atual[
                "jogadores"
            ],

        "max_jogadores":
            sala_atual[
                "max_jogadores"
            ],

        "anfitriao":
            sala_atual[
                "anfitriao"
            ],

        "iniciado":
            sala_atual[
                "iniciado"
            ],

        "completa":
            len(
                sala_atual[
                    "jogadores"
                ]
            )
            ==
            sala_atual[
                "max_jogadores"
            ]
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
                "Sala não encontrada."
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
                "Somente o dono da sala "
                "pode iniciar."
            )


        if (
            len(
                sala_atual[
                    "jogadores"
                ]
            )
            !=
            sala_atual[
                "max_jogadores"
            ]
        ):

            return (
                "A sala ainda não "
                "está completa."
            )


        if not sala_atual[
            "iniciado"
        ]:

            criar_partida(
                sala_atual
            )

            sala_atual[
                "iniciado"
            ] = True


    return redirect(
        url_for(
            "jogo",
            codigo=codigo
        )
    )


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
                "Sala não encontrada."
            )


        sala_atual = salas[codigo]

        nome = session.get(
            "nome"
        )


        if (
            session.get(
                "codigo"
            )
            != codigo

            or

            nome not in sala_atual[
                "jogadores"
            ]
        ):

            return redirect(
                url_for(
                    "inicio"
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


        if (
            partida["fase"]
            == "jogando"
        ):

            jogador_da_vez_jogada = (

                partida[
                    "ordem_jogada"
                ][
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


        erro_pedido = session.pop(
            "erro_pedido",
            None
        )


        erro_jogada = session.pop(
            "erro_jogada",
            None
        )


        return render_template(

            "jogo.html",

            codigo=codigo,

            nome=nome,

            sala=sala_atual,

            partida=partida,

            minha_mao=minha_mao,

            jogador_da_vez_pedido=
                jogador_da_vez_pedido,

            pedido_proibido=
                pedido_proibido,

            jogador_da_vez_jogada=
                jogador_da_vez_jogada,

            indices_validos=
                indices_validos,

            erro_pedido=
                erro_pedido,

            erro_jogada=
                erro_jogada,

            tempo_total_restante=
                tempo_total_restante,

            assinatura_estado=
                assinatura_estado
        )


# =========================================================
# ESTADO DO JOGO
#
# NÃO RECARREGA A PÁGINA.
# SÓ DEVOLVE INFORMAÇÕES PARA O JAVASCRIPT.
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
            session.get(
                "codigo"
            )
            != codigo

            or

            nome not in sala_atual[
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
                "Sala não encontrada."
            )


        sala_atual = salas[codigo]

        partida = sala_atual[
            "partida"
        ]

        nome = session.get(
            "nome"
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


        if (
            nome
            != jogador_da_vez
        ):

            session[
                "erro_pedido"
            ] = (
                "Ainda não é sua vez."
            )


            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )


        try:

            pedido = int(
                request.form[
                    "pedido"
                ]
            )

        except (
            ValueError,
            TypeError,
            KeyError
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


        maximo = partida[
            "cartas_por_jogador"
        ]


        if (
            pedido < 0
            or
            pedido > maximo
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

            and

            pedido
            == pedido_proibido
        ):

            session[
                "erro_pedido"
            ] = (
                f"Você não pode pedir "
                f"{pedido}."
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


        partida[
            "indice_pedida_atual"
        ] += 1


        if (
            partida[
                "indice_pedida_atual"
            ]
            >=
            len(
                partida[
                    "ordem_pedidas"
                ]
            )
        ):

            iniciar_vazas(
                sala_atual
            )


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
                "Sala não encontrada."
            )


        sala_atual = salas[codigo]


        atualizar_estado_partida(
            sala_atual
        )


        partida = sala_atual[
            "partida"
        ]


        nome = session.get(
            "nome"
        )


        if (
            partida["fase"]
            != "jogando"
        ):

            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )


        jogador_da_vez = (

            partida[
                "ordem_jogada"
            ][
                partida[
                    "indice_jogada_atual"
                ]
            ]
        )


        if (
            nome
            != jogador_da_vez
        ):

            session[
                "erro_jogada"
            ] = (
                "Ainda não é sua vez."
            )


            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )


        try:

            indice_carta = int(
                request.form[
                    "indice_carta"
                ]
            )

        except (
            ValueError,
            TypeError,
            KeyError
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


        mao = partida[
            "maos"
        ][nome]


        if (
            indice_carta < 0

            or

            indice_carta
            >= len(mao)
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


        validas = (
            indices_cartas_validas(
                partida,
                nome
            )
        )


        if (
            indice_carta
            not in validas
        ):

            session[
                "erro_jogada"
            ] = (
                "Você é obrigado a seguir "
                "o naipe puxado."
            )


            return redirect(
                url_for(
                    "jogo",
                    codigo=codigo
                )
            )


        executar_jogada(

            sala_atual,

            nome,

            indice_carta,

            automatica=False
        )


    return redirect(
        url_for(
            "jogo",
            codigo=codigo
        )
    )


# =========================================================
# EXECUTAR
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True,
        threaded=True
    )