import random

from carta import Carta


class Baralho:

    def __init__(self):

        valores = [
            "2", "3", "4", "5", "6", "7",
            "8", "9", "10", "J", "Q", "K", "A"
        ]

        naipes = [
            "Copas",
            "Ouros",
            "Espadas",
            "Paus"
        ]

        self.cartas = []

        for naipe in naipes:

            for valor in valores:

                self.cartas.append(
                    Carta(valor, naipe)
                )

    def embaralhar(self):
        random.shuffle(self.cartas)

    def comprar(self):
        return self.cartas.pop()