class Carta:

    ORDEM = {
        "2": 2,
        "3": 3,
        "4": 4,
        "5": 5,
        "6": 6,
        "7": 7,
        "8": 8,
        "9": 9,
        "10": 10,
        "J": 11,
        "Q": 12,
        "K": 13,
        "A": 14
    }

    SIMBOLOS = {
        "Copas": "♥",
        "Ouros": "♦",
        "Espadas": "♠",
        "Paus": "♣"
    }

    def __init__(self, valor, naipe):
        self.valor = valor
        self.naipe = naipe

    def __str__(self):
        return f"{self.valor} de {self.naipe}"

    def to_dict(self):
        return {
            "valor": self.valor,
            "naipe": self.naipe,
            "simbolo": self.SIMBOLOS[self.naipe],
            "forca": self.ORDEM[self.valor]
        }