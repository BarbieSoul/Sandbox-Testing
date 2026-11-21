"""
Flappy - un juego estilo Flappy Bird con gráficos simples (pygame).

Controles:
    ESPACIO / clic / flecha arriba  -> aletear
    ESC                             -> salir
"""
import random
import sys

import pygame

# --- Configuración ---------------------------------------------------------
ANCHO, ALTO = 400, 600
FPS = 60

GRAVEDAD = 0.45
IMPULSO = -8.0
VEL_MAX_CAIDA = 10

VEL_TUBOS = 3
ANCHO_TUBO = 70
HUECO = 160               # espacio vertical entre tubo superior e inferior
DISTANCIA_TUBOS = 220     # separación horizontal entre pares de tubos
ALTO_SUELO = 80

# Colores
CIELO = (112, 197, 206)
VERDE = (94, 186, 60)
VERDE_OSCURO = (60, 130, 40)
SUELO = (222, 216, 149)
SUELO_BORDE = (150, 120, 60)
AMARILLO = (250, 210, 50)
NARANJA = (240, 120, 40)
BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)
NUBE = (240, 250, 255)


class Pajaro:
    RADIO = 16

    def __init__(self):
        self.x = ANCHO // 3
        self.y = ALTO // 2
        self.vel = 0.0
        self.aleteo = 0  # temporizador para animar el ala

    def aletear(self):
        self.vel = IMPULSO
        self.aleteo = 8

    def actualizar(self):
        self.vel = min(self.vel + GRAVEDAD, VEL_MAX_CAIDA)
        self.y += self.vel
        if self.aleteo > 0:
            self.aleteo -= 1

    def rect(self):
        r = self.RADIO - 3  # caja de colisión algo más pequeña: más justo
        return pygame.Rect(self.x - r, self.y - r, r * 2, r * 2)

    def dibujar(self, pantalla):
        # Dibuja en una superficie aparte para poder rotarlo según la velocidad
        tam = self.RADIO * 3
        s = pygame.Surface((tam, tam), pygame.SRCALPHA)
        c = tam // 2
        pygame.draw.circle(s, AMARILLO, (c, c), self.RADIO)
        pygame.draw.circle(s, NEGRO, (c, c), self.RADIO, 2)
        # ala
        ala_y = c - 2 if self.aleteo > 0 else c + 4
        pygame.draw.ellipse(s, BLANCO, (c - 14, ala_y - 4, 14, 9))
        pygame.draw.ellipse(s, NEGRO, (c - 14, ala_y - 4, 14, 9), 1)
        # ojo
        pygame.draw.circle(s, BLANCO, (c + 6, c - 5), 6)
        pygame.draw.circle(s, NEGRO, (c + 8, c - 5), 3)
        # pico
        pygame.draw.polygon(s, NARANJA, [(c + 12, c), (c + 24, c + 3), (c + 12, c + 7)])

        angulo = max(-30, min(60, self.vel * 6))
        rot = pygame.transform.rotate(s, -angulo)
        pantalla.blit(rot, rot.get_rect(center=(self.x, int(self.y))))


class ParTubos:
    def __init__(self, x):
        self.x = x
        margen = 60
        self.hueco_y = random.randint(margen + HUECO // 2,
                                      ALTO - ALTO_SUELO - margen - HUECO // 2)
        self.contado = False

    def actualizar(self):
        self.x -= VEL_TUBOS

    def rects(self):
        arriba = pygame.Rect(self.x, 0, ANCHO_TUBO, self.hueco_y - HUECO // 2)
        abajo_y = self.hueco_y + HUECO // 2
        abajo = pygame.Rect(self.x, abajo_y, ANCHO_TUBO, ALTO - ALTO_SUELO - abajo_y)
        return arriba, abajo

    def dibujar(self, pantalla):
        arriba, abajo = self.rects()
        for r, boca_arriba in ((arriba, False), (abajo, True)):
            pygame.draw.rect(pantalla, VERDE, r)
            pygame.draw.rect(pantalla, VERDE_OSCURO, r, 3)
            # "boca" del tubo
            boca = pygame.Rect(r.x - 5, r.top if boca_arriba else r.bottom - 24,
                               ANCHO_TUBO + 10, 24)
            pygame.draw.rect(pantalla, VERDE, boca)
            pygame.draw.rect(pantalla, VERDE_OSCURO, boca, 3)

    def fuera(self):
        return self.x + ANCHO_TUBO < 0


def dibujar_nubes(pantalla, nubes):
    for (x, y, t) in nubes:
        for dx, dy, r in ((0, 0, 20), (22, -8, 24), (46, 0, 20)):
            pygame.draw.circle(pantalla, NUBE, (int(x + dx * t), int(y + dy * t)), int(r * t))


def dibujar_suelo(pantalla, desplazamiento):
    y = ALTO - ALTO_SUELO
    pygame.draw.rect(pantalla, SUELO, (0, y, ANCHO, ALTO_SUELO))
    pygame.draw.rect(pantalla, VERDE, (0, y, ANCHO, 14))
    # rayas diagonales que se desplazan para dar sensación de movimiento
    for i in range(-1, ANCHO // 20 + 2):
        x = i * 20 - desplazamiento
        pygame.draw.line(pantalla, VERDE_OSCURO, (x, y + 14), (x + 10, y), 3)
    pygame.draw.line(pantalla, SUELO_BORDE, (0, y), (ANCHO, y), 3)


def texto(pantalla, fuente, msg, centro, color=BLANCO):
    # texto con contorno negro para que se lea sobre cualquier fondo
    for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        s = fuente.render(msg, True, NEGRO)
        pantalla.blit(s, s.get_rect(center=(centro[0] + dx, centro[1] + dy)))
    s = fuente.render(msg, True, color)
    pantalla.blit(s, s.get_rect(center=centro))


def main():
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Flappy")
    reloj = pygame.time.Clock()
    fuente_grande = pygame.font.SysFont("arial", 52, bold=True)
    fuente = pygame.font.SysFont("arial", 24, bold=True)

    record = 0
    nubes = [[random.randint(0, ANCHO), random.randint(40, 250), random.uniform(0.6, 1.2)]
             for _ in range(4)]

    def reiniciar():
        return Pajaro(), [ParTubos(ANCHO + 100)], 0

    pajaro, tubos, puntos = reiniciar()
    estado = "inicio"  # "inicio" | "jugando" | "fin"
    suelo_x = 0

    while True:
        # --- Eventos ---
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            accion = (e.type == pygame.MOUSEBUTTONDOWN or
                      (e.type == pygame.KEYDOWN and e.key in (pygame.K_SPACE, pygame.K_UP)))
            if accion:
                if estado == "inicio":
                    estado = "jugando"
                    pajaro.aletear()
                elif estado == "jugando":
                    pajaro.aletear()
                elif estado == "fin" and pajaro.y >= ALTO - ALTO_SUELO - Pajaro.RADIO:
                    pajaro, tubos, puntos = reiniciar()
                    estado = "inicio"

        # --- Lógica ---
        if estado != "fin":
            suelo_x = (suelo_x + VEL_TUBOS) % 20
            for n in nubes:
                n[0] -= 0.5 * n[2]
                if n[0] < -80:
                    n[0] = ANCHO + 20
                    n[1] = random.randint(40, 250)

        if estado == "inicio":
            # el pájaro flota suavemente
            pajaro.y = ALTO // 2 + 8 * pygame.math.Vector2(1, 0).rotate(
                pygame.time.get_ticks() / 4).y

        elif estado == "jugando":
            pajaro.actualizar()
            for t in tubos:
                t.actualizar()
                if not t.contado and t.x + ANCHO_TUBO < pajaro.x:
                    t.contado = True
                    puntos += 1
            if tubos[-1].x < ANCHO - DISTANCIA_TUBOS:
                tubos.append(ParTubos(ANCHO))
            tubos = [t for t in tubos if not t.fuera()]

            # colisiones
            r = pajaro.rect()
            choca_tubo = any(r.colliderect(x) for t in tubos for x in t.rects())
            if choca_tubo or pajaro.y + Pajaro.RADIO >= ALTO - ALTO_SUELO or pajaro.y < -50:
                estado = "fin"
                record = max(record, puntos)

        elif estado == "fin":
            # el pájaro cae hasta el suelo
            if pajaro.y < ALTO - ALTO_SUELO - Pajaro.RADIO:
                pajaro.actualizar()
            pajaro.y = min(pajaro.y, ALTO - ALTO_SUELO - Pajaro.RADIO)

        # --- Dibujo ---
        pantalla.fill(CIELO)
        dibujar_nubes(pantalla, nubes)
        for t in tubos:
            t.dibujar(pantalla)
        dibujar_suelo(pantalla, suelo_x)
        pajaro.dibujar(pantalla)

        if estado == "inicio":
            texto(pantalla, fuente_grande, "FLAPPY", (ANCHO // 2, 130))
            texto(pantalla, fuente, "ESPACIO o clic para volar", (ANCHO // 2, 400))
            if record:
                texto(pantalla, fuente, f"Récord: {record}", (ANCHO // 2, 440))
        elif estado == "jugando":
            texto(pantalla, fuente_grande, str(puntos), (ANCHO // 2, 70))
        else:
            texto(pantalla, fuente_grande, "GAME OVER", (ANCHO // 2, 160), NARANJA)
            texto(pantalla, fuente, f"Puntos: {puntos}", (ANCHO // 2, 240))
            texto(pantalla, fuente, f"Récord: {record}", (ANCHO // 2, 275))
            if pajaro.y >= ALTO - ALTO_SUELO - Pajaro.RADIO:
                texto(pantalla, fuente, "Clic o ESPACIO para reintentar", (ANCHO // 2, 360))

        pygame.display.flip()
        reloj.tick(FPS)


if __name__ == "__main__":
    main()
