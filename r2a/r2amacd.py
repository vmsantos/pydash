import time
from statistics import mean, harmonic_mean

from player.parser import *
from r2a.ir2a import IR2A

RED = "\033[1;31m"
BLUE = "\033[1;34m"
CYAN = "\033[1;36m"
GREEN = "\033[0;32m"
RESET = "\033[0;0m"
BOLD = "\033[;1m"
REVERSE = "\033[;7m"


def ema(arr):
    # Inicializa variáveis
    moving_averages = []
    i = 0

    # Alpha, como definido na eq. 3
    x = 2 / (len(arr) + 1)
    # x = 0.5

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


class r2amacd(IR2A):

    def __init__(self, id):
        IR2A.__init__(self, id)
        self.throughputs = []
        self.request_time = 0
        self.qi = []
        self.selected_index = 10
        self.buffer_increase_time = 0

    def handle_xml_request(self, msg):
        # Salva momento da requisição pra calcular a vazão
        self.request_time = time.perf_counter()

        # Repassa a mensamge pro Connection Handler
        self.send_down(msg)

    def handle_xml_response(self, msg):
        # Obtém as qualidades disponíveis
        parsed_mpd = parse_mpd(msg.get_payload())
        self.qi = parsed_mpd.get_qi()

        # Calcula a vazão
        t = time.perf_counter() - self.request_time
        self.throughputs.append(msg.get_bit_length() / t)

        # Repassa a mensagem para o player
        self.send_up(msg)

    def handle_segment_size_request(self, msg):
        # Desenvolvimento
        print(BLUE+"------------- NOVA REQUISIÇÃO -------------"+RESET)

        # Salva tempo em que foi feita a requisição
        self.request_time = time.perf_counter()

        # Target na tabela - Tamanho de buffer desejado
        T = 60

        # Inicializa as variáveis
  #      buffering_time = 0
        differential_buffering_time = 0
  #      buffer = 0

        # Evita possíveis acessos indevidos no vetor
        if len(self.whiteboard.get_playback_segment_size_time_at_buffer()) > 0:
            # Buffering time - tempo que o último seguimento recebido aguarda no buffer até ser reproduzido
            buffering_time = self.whiteboard.get_playback_segment_size_time_at_buffer()[-1]

            # Calcula differential buffering time
            if len(self.whiteboard.get_playback_segment_size_time_at_buffer()) > 1:
                # Obtém o penúltimo buffering time
                last_buffering_time = self.whiteboard.get_playback_segment_size_time_at_buffer()[-2]

                # DeltaTi - diferença entre o último buffering time do anterior
                differential_buffering_time = buffering_time - last_buffering_time

            # Fatores da saída
            [N2, N1, Z, P1, P2] = [0.25, 0.5, 1, 1.5, 2]

            # Definindo short, close, long
#            short = 0
#            close = 0
#            long = 0

            # Definindo short, close, long
            if (buffering_time <= (2 / 3) * T):
                short = 1
                close = 0
                long = 0
            elif ((2 / 3) * T < buffering_time <= T):
                short = 3 - (3 / T) * buffering_time
                close = (3 / T) * buffering_time
                long = 0
            elif (T < buffering_time <= 4 * T):
                short = 0
                close = (4 / 3) - (1 / (3 * T)) * buffering_time
                long = -(1 / 3) + (1 / (3 * T)) * buffering_time
            else:
                short = 0
                close = 0
                long = 1

            # Definindo das tendências Falling, Steady, Rising
#            falling = 0
#            steady = 0
 #           rising = 0

            # Definindo falling, steady e rising
            if (differential_buffering_time <= (-2 / 3) * T):
                falling = 1
                steady = 0
                rising = 0
            elif ((-2 / 3) * T < differential_buffering_time <= 0):
                falling = -(3 / (2 * T)) * differential_buffering_time
                steady = 1 - (3 / (2 * T)) * differential_buffering_time
                rising = 0
            elif (0 < differential_buffering_time <= 4 * T):
                falling = 0
                steady = 1 - (1 / (4 * T)) * differential_buffering_time
                rising = (1 / (4 * T)) * differential_buffering_time
            else:
                falling = 0
                steady = 0
                rising = 1

            # Calcula r1, r2 etc.
            r1 = min(short, falling)
            r2 = min(close, falling)
            r3 = min(long, falling)
            r4 = min(short, steady)
            r5 = min(close, steady)
            r6 = min(long, steady)
            r7 = min(short, rising)
            r8 = min(close, rising)
            r9 = min(long, rising)

            # Calcula variações
            I = (r9 ** 2) ** (1 / 2)
            SI = (r6 ** 2 + r8 ** 2) ** (1 / 2)
            NC = (r3 ** 2 + r5 ** 2 + r7 ** 2) ** (1 / 2)
            SR = (r2 ** 2 + r4 ** 2) ** (1 / 2)
            R = (r1 ** 2) ** (1 / 2)

            # Calcula f
            f = N2 * R + N1 * SR + Z * NC + P1 * SI + P2 * I / (SR + R + NC + SI + I)

            # Tempo avaliado para média da vazão e para a estimativa.
            moving_average_size = 5

            # Normaliza o tamanho da média.
            moving_average_size = min(len(self.throughputs), moving_average_size)

            # Seleciona os últimos k elementos da lista.
            moving_average_throughput = mean(self.throughputs[-moving_average_size:])

            # Salva os índices e a qualidade antiga.
            last_index = self.selected_index
            last_qi = self.qi[last_index]

            # Estima a próxima qualidade
            next_qi = f * moving_average_throughput

            # Inicializa índice selecionado
            self.selected_index = 0
            # Seleciona o maior índice da qualidade
            for index in range(len(self.qi)):
                if next_qi > self.qi[index]:
                    self.selected_index = index

            # Seleciona a qualidade
            next_qi = self.qi[self.selected_index]

            # Limitação da variação da qualidade
            # Quanto tempo é observado no futuro
            est_time = 20

            # Pega o tamanho do buffer
            buffer = self.whiteboard.get_playback_buffer_size()[-1][1]
            print("BUFFER ->>>>>>> ", buffer)

            # Cálcula o tempo de buffer previsto
            predicted_buffer_new_qi = buffer + (((moving_average_throughput) / next_qi) - 1) * est_time
            predicted_buffer_old_qi = buffer + (((moving_average_throughput) / last_qi) - 1) * est_time

            # Se o tempo previsto for menor que o target buffer não aumenta a qualidade
            if next_qi > last_qi and predicted_buffer_new_qi < T:
                self.selected_index = last_index
                # print(RED+"\n------- Impediu aumento --------"+RESET)

            # Se o tempo previsto anterior for maior que o target buffer
            # não diminui a qualidade
            elif next_qi < last_qi:
                if (predicted_buffer_old_qi > T):
                    self.selected_index = last_index
                    # print(GREEN+"\n------- Impediu diminuição --------\n"+RESET)

            # Impede que os aumentos sejam superiores a 2
            if self.selected_index > (last_index + 2):
                self.selected_index = last_index + 2

            # Impede que os diminuições sejam superiores a 2
            if self.selected_index < (last_index - 2):
                self.selected_index = last_index - 2

            # Limita a quantidade de subidas em um intervalo de tempo
            increase_block_time = 5
            if (
                    self.selected_index > last_index and time.perf_counter() > self.buffer_increase_time + increase_block_time):
                self.buffer_increase_time = time.perf_counter()
                # print(CYAN+"Subiu nessa"+RESET)
            elif (
                    self.selected_index > last_index and time.perf_counter() < self.buffer_increase_time + increase_block_time):
                self.selected_index = last_index
                # print(CYAN+"Não sobe nessa"+RESET)

        # Usando o valor que ele obteve
        msg.add_quality_id(self.qi[self.selected_index])

        # Passa a mensagem pra fazer o request
        self.send_down(msg)

        # Desenvolvimento
        # print(BLUE+"------------- FINAL REQUISIÇÃO ------------"+RESET)

    def handle_segment_size_response(self, msg):
        t = time.perf_counter() - self.request_time
        self.throughputs.append(msg.get_bit_length() / t)
        self.send_up(msg)

    def initialize(self):
        pass

    def finalization(self):
        pass
