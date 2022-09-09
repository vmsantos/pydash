import time

from player.player import Player
from player.parser import *
from r2a.ir2a import IR2A
from numpy import mean

def ema(arr):
    # Inicializa variáveis
    moving_averages = []
    i = 0

    # Alpha, como definido na eq. 3
    x = 2 / (len(arr) + 1)
    #x = 0.5

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

    return ema(shortarr)[len(shortarr) - 1] - ema(longarr)[len(longarr) - 1]


class R2Amacd2(IR2A):

    def __init__(self, id):
        IR2A.__init__(self, id)
        self.throughputs = []
        self.request_time = 0
        self.qi = []
        self.m = 9

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
        macd1 = macd(self.throughputs, 3, 19) > 0
        macd2 = macd(self.throughputs, 12, 26) > 0
        macd3 = macd(self.throughputs, 13, 21) > 0
        macd4 = macd(self.throughputs, 5, 35) > 0
        macd5 = macd(self.throughputs, 3, 30) > 0
        macd6 = macd(self.throughputs, 8, 34) > 0
        macd7 = macd(self.throughputs, 20, 60) > 0
        macd8 = macd(self.throughputs, 1, 100) > 0
        macdaverage = (macd(self.throughputs, 3, 19) +
                        macd(self.throughputs, 12, 26) +
                        macd(self.throughputs, 3, 30) +
                        macd(self.throughputs, 5, 35) +
                        macd(self.throughputs, 13, 21) +
                        macd(self.throughputs, 20, 60) +
                        macd(self.throughputs, 1, 100) +
                        macd(self.throughputs, 8, 34))/8
        macdP = [macd1, macd2, macd3, macd4, macd5, macd6, macd7, macd8].count(True)
        macdN = [macd1, macd2, macd3, macd4, macd5, macd6, macd7, macd8].count(False)

        buffer = self.

        print(buffer)

        if macdP > macdN and macd3 > macdaverage:  # Tendência de alta
            if self.m < 19:
                self.m += 1
            selected_qi = self.qi[self.m]

        elif macdP < macdN and macd3 < macdaverage:  # Tendência de baixa
            if self.m > 0:
                self.m -= 1
            selected_qi = self.qi[self.m]

        else:  # Tendência estável
            selected_qi = self.qi[self.m]

        print("----------------\n", macdP, macdN, macdaverage)

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
