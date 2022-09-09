##  Vinícius de Melo Santos
### 17/0157849
####

import time

from player.parser import *
from r2a.ir2a import IR2A
from numpy import *


def ma(x, peso):
    return np.convolve(x, np.ones(w), 'valid') / peso


def ewma(arr, peso):
    # Inicializa variáveis
    moving_averages = []
    i = 0
    # Alpha
    # x = 2 / (len(arr) + 1)
    x = peso
    # Insert first exponential average in the list
    moving_averages.append(arr[0])
    # Loop through the array elements
    while i < len(arr):
        # Calculate the exponential
        # average by using the formula
        window_average = round((x * arr[i]) + (1 - x) * moving_averages[-1], 2)
        # Store the cumulative average of current window in moving average list.
        moving_averages.append(window_average)
        # Shift window to right by one position
        i += 1
    return moving_averages


def macd(arr, short, long):
    shortarr = arr[-short:]
    longarr = arr[-long:]
    x = 2 / (len(arr) + 1)
    return ewma(shortarr, x)[len(shortarr) - 1] - ewma(longarr, x)[len(longarr) - 1]


class R2Amacd1(IR2A):

    def __init__(self, id):
        IR2A.__init__(self, id)
        self.throughputs = []
        self.request_time = 0
        self.qi = []
        self.m = 12
        self.macds = []
        self.macd1mavg = 0

    def handle_xml_request(self, msg):
        self.request_time = time.perf_counter()
        self.send_down(msg)

    def handle_xml_response(self, msg):

        parsed_mpd = parse_mpd(msg.get_payload())
        self.qi = parsed_mpd.get_qi()

        t = time.perf_counter() - self.request_time
        self.throughputs.append(msg.get_bit_length() / t)

        self.send_up(msg)

    def handle_segment_size_request(self, msg):
        self.request_time = time.perf_counter()
        # Define os pesos usados em cada EWMA do MACD
        fast = 2
        slow = 5

        # Obtém lista com os MACDs já cálculados
        macd1 = macd(self.throughputs, fast, slow)

        macds = self.macds.append(macd1)

        # Número mágico escolhido é o inverso da razão áurea
        numero_magico = (1+sqrt(5))/2 - 1

        # Calculamos a média móvel exponencial dos MACDs anteriores
        self.macd1mavg = ewma(self.macds, numero_magico)[len(self.macds) - 1]

        # Usamos macd1mavg para obter os limites/filtros superior e inferior
        Thp = abs(self.macd1mavg)*10
        Thn = -1*Thp

        selected_qi = self.qi[self.m]

        if macd1 > Thp:  # Tendência de alta
            # print("Tend. de Alta")
            if self.m < 19:
                self.m += 1
                selected_qi = self.qi[self.m]
            else:
                self.m -= 2
                selected_qi = self.qi[self.m]

        elif macd1 < Thn:  # Tendência de baixa
            # print("Tend. de Baixa")
            if self.m > 0:
                self.m -= 1
                selected_qi = self.qi[self.m]
            else:
                self.m += 2
                selected_qi = self.qi[self.m]

        elif macd1 != 0:  # Tendência estável
            if self.m > 10:
                self.m -= 2
                selected_qi = self.qi[self.m]
                # print("m = ", self.m)
            elif self.m < 9:
                self.m += 2
                selected_qi = self.qi[self.m]
                # print("m = ", self.m)
            # print("Tend. horizontal")

        msg.add_quality_id(selected_qi)
        self.send_down(msg)

    def handle_segment_size_response(self, msg):
        t = time.perf_counter() - self.request_time
        self.throughputs.append(msg.get_bit_length() / t)
        self.send_up(msg)

    def initialize(self):
        pass

    def finalization(self):
        pass
