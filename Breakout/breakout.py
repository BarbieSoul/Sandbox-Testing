"""
Breakout - juego de romper ladrillos con gráficos simples (pygame).

Controles:
    Flechas izquierda/derecha o A/D  -> mover la paleta
    Mouse                            -> también mueve la paleta
    ESPACIO / clic                   -> lanzar la pelota / reiniciar
    P                                -> pausa
    ESC                              -> salir
"""
import math
import random
import sys

import pygame

# --- Configuración ---------------------------------------------------------
ANCHO, ALTO = 640, 720
FPS = 60

ANCHO_PALETA, ALTO_PALETA = 100, 14
VEL_PALETA = 8

RADIO_PELOTA = 8
VEL_PELOTA_INICIAL = 6.0
VEL_PELOTA_MAX = 11.0
AUMENTO_VEL = 0.15          # cuánto acelera la pelota con cada ladrillo roto

FILAS, COLUMNAS = 6, 10
ALTO_LADRILLO = 24
SEPARACION = 4
MARGEN_SUPERIOR = 80

VIDAS_INICIALES = 3

# Colores
FONDO = (20, 24, 40)
BLANCO = (240, 240, 240)
GRIS = (130, 140, 160)
PALETA_COLOR = (90, 200, 250)
PELOTA_COLOR = (255, 255, 255)
# Un color por fila; las filas de arriba valen más puntos
COLORES_FILAS = [
    (235, 80, 80),
    (240, 150, 60),
    (240, 210, 70),
    (110, 200, 90),
    (80, 160, 230),
    (160, 110, 220),
]


class Paleta:
    """La barra que controla el jugador en la parte inferior."""

    def __init__(self):
        """Crea la paleta centrada horizontalmente cerca del borde inferior."""
        self.rect = pygame.Rect(0, 0, ANCHO_PALETA, ALTO_PALETA)
        self.rect.midbottom = (ANCHO // 2, ALTO - 40)

    def mover(self, teclas, mouse_x):
        """Mueve la paleta con el teclado o, si se movió el mouse, la sigue.

        `mouse_x` es None cuando el mouse no se movió en este frame, así el
        teclado y el mouse no se pelean entre sí.
        """
        if mouse_x is not None:
            self.rect.centerx = mouse_x
        if teclas[pygame.K_LEFT] or teclas[pygame.K_a]:
            self.rect.x -= VEL_PALETA
        if teclas[pygame.K_RIGHT] or teclas[pygame.K_d]:
            self.rect.x += VEL_PALETA
        # No dejar que la paleta salga de la pantalla
        self.rect.clamp_ip(pygame.Rect(0, 0, ANCHO, ALTO))

    def dibujar(self, pantalla):
        """Dibuja la paleta como un rectángulo con bordes redondeados."""
        pygame.draw.rect(pantalla, PALETA_COLOR, self.rect, border_radius=7)


class Pelota:
    """La pelota que rebota contra paredes, paleta y ladrillos."""

    def __init__(self, paleta):
        """Crea la pelota apoyada sobre la paleta, esperando ser lanzada."""
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.velocidad = VEL_PELOTA_INICIAL
        self.pegada = True  # True mientras está sobre la paleta sin lanzar
        self.seguir_paleta(paleta)

    def seguir_paleta(self, paleta):
        """Coloca la pelota justo encima del centro de la paleta."""
        self.x = paleta.rect.centerx
        self.y = paleta.rect.top - RADIO_PELOTA - 1

    def lanzar(self):
        """Lanza la pelota hacia arriba con un ángulo un poco aleatorio."""
        if self.pegada:
            angulo = math.radians(random.uniform(-30, 30))
            self.vx = self.velocidad * math.sin(angulo)
            self.vy = -self.velocidad * math.cos(angulo)
            self.pegada = False

    def rect(self):
        """Devuelve el rectángulo que envuelve a la pelota (para colisiones)."""
        return pygame.Rect(int(self.x - RADIO_PELOTA), int(self.y - RADIO_PELOTA),
                           RADIO_PELOTA * 2, RADIO_PELOTA * 2)

    def acelerar(self):
        """Aumenta un poco la velocidad, manteniendo la dirección actual."""
        self.velocidad = min(self.velocidad + AUMENTO_VEL, VEL_PELOTA_MAX)
        actual = math.hypot(self.vx, self.vy)
        if actual:
            self.vx *= self.velocidad / actual
            self.vy *= self.velocidad / actual

    def rebotar_en_paleta(self, paleta):
        """Rebota en la paleta; el ángulo depende de dónde pegó la pelota.

        Si pega en el centro sale casi vertical; si pega cerca de un extremo
        sale más inclinada hacia ese lado. Así el jugador puede apuntar.
        """
        # Posición relativa del impacto: -1 (extremo izq.) a 1 (extremo der.)
        relativo = (self.x - paleta.rect.centerx) / (paleta.rect.width / 2)
        relativo = max(-1.0, min(1.0, relativo))
        angulo = math.radians(relativo * 60)  # hasta 60° de inclinación
        self.vx = self.velocidad * math.sin(angulo)
        self.vy = -self.velocidad * math.cos(angulo)
        self.y = paleta.rect.top - RADIO_PELOTA - 1  # evita que quede "dentro"

    def mover(self):
        """Avanza la pelota y la hace rebotar en las paredes laterales y el techo.

        Devuelve True si la pelota cayó por debajo de la pantalla (se pierde una vida).
        """
        self.x += self.vx
        self.y += self.vy

        if self.x - RADIO_PELOTA <= 0:
            self.x = RADIO_PELOTA
            self.vx = abs(self.vx)
        elif self.x + RADIO_PELOTA >= ANCHO:
            self.x = ANCHO - RADIO_PELOTA
            self.vx = -abs(self.vx)
        if self.y - RADIO_PELOTA <= 0:
            self.y = RADIO_PELOTA
            self.vy = abs(self.vy)

        return self.y - RADIO_PELOTA > ALTO

    def dibujar(self, pantalla):
        """Dibuja la pelota como un círculo."""
        pygame.draw.circle(pantalla, PELOTA_COLOR, (int(self.x), int(self.y)), RADIO_PELOTA)


class Ladrillo:
    """Un ladrillo que desaparece al ser golpeado por la pelota."""

    def __init__(self, x, y, ancho, fila):
        """Crea un ladrillo en (x, y); su color y puntaje dependen de la fila."""
        self.rect = pygame.Rect(x, y, ancho, ALTO_LADRILLO)
        self.color = COLORES_FILAS[fila % len(COLORES_FILAS)]
        self.puntos = (FILAS - fila) * 10  # fila de arriba = más puntos

    def dibujar(self, pantalla):
        """Dibuja el ladrillo con un borde más claro arriba para dar relieve."""
        pygame.draw.rect(pantalla, self.color, self.rect, border_radius=3)
        claro = tuple(min(255, c + 50) for c in self.color)
        pygame.draw.line(pantalla, claro, (self.rect.left + 3, self.rect.top + 2),
                         (self.rect.right - 4, self.rect.top + 2), 2)


def crear_ladrillos():
    """Genera la grilla completa de ladrillos centrada en la pantalla."""
    ancho = (ANCHO - SEPARACION * (COLUMNAS + 1)) // COLUMNAS
    # Centrar la grilla si la división no es exacta
    sobrante = ANCHO - (ancho * COLUMNAS + SEPARACION * (COLUMNAS + 1))
    inicio_x = SEPARACION + sobrante // 2
    ladrillos = []
    for fila in range(FILAS):
        for col in range(COLUMNAS):
            x = inicio_x + col * (ancho + SEPARACION)
            y = MARGEN_SUPERIOR + fila * (ALTO_LADRILLO + SEPARACION)
            ladrillos.append(Ladrillo(x, y, ancho, fila))
    return ladrillos


def colision_ladrillos(pelota, ladrillos):
    """Detecta si la pelota golpeó un ladrillo, lo rompe y hace rebotar la pelota.

    Para saber hacia dónde rebotar compara cuánto se "metió" la pelota en el
    ladrillo por cada lado: si el solapamiento horizontal es menor, el golpe
    fue de costado (se invierte vx); si no, fue de arriba/abajo (se invierte vy).
    Devuelve los puntos ganados (0 si no golpeó nada).
    """
    r = pelota.rect()
    indice = r.collidelist([l.rect for l in ladrillos])
    if indice == -1:
        return 0

    ladrillo = ladrillos.pop(indice)
    lr = ladrillo.rect
    solape_x = min(r.right, lr.right) - max(r.left, lr.left)
    solape_y = min(r.bottom, lr.bottom) - max(r.top, lr.top)
    if solape_x < solape_y:
        pelota.vx = -pelota.vx
    else:
        pelota.vy = -pelota.vy
    pelota.acelerar()
    return ladrillo.puntos


def texto(pantalla, fuente, msg, centro, color=BLANCO):
    """Escribe un texto centrado en la posición `centro`."""
    s = fuente.render(msg, True, color)
    pantalla.blit(s, s.get_rect(center=centro))


def dibujar_hud(pantalla, fuente, puntos, vidas, nivel):
    """Dibuja la barra superior con puntaje, nivel y vidas restantes."""
    pantalla.blit(fuente.render(f"Puntos: {puntos}", True, BLANCO), (14, 14))
    s = fuente.render(f"Nivel {nivel}", True, GRIS)
    pantalla.blit(s, s.get_rect(midtop=(ANCHO // 2, 14)))
    # Una pelotita por cada vida
    for i in range(vidas):
        pygame.draw.circle(pantalla, PALETA_COLOR, (ANCHO - 24 - i * 22, 26), 7)
    pygame.draw.line(pantalla, GRIS, (0, 50), (ANCHO, 50), 1)


def main():
    """Bucle principal: inicializa pygame, procesa eventos, actualiza y dibuja.

    El juego tiene cuatro estados:
        "listo"   -> la pelota espera sobre la paleta a ser lanzada
        "jugando" -> la pelota está en movimiento
        "pausa"   -> el juego está detenido
        "fin"     -> se ganó o se perdió; se espera para reiniciar
    """
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Breakout")
    reloj = pygame.time.Clock()
    fuente = pygame.font.SysFont("arial", 22, bold=True)
    fuente_grande = pygame.font.SysFont("arial", 56, bold=True)

    def nueva_partida():
        """Devuelve todo lo necesario para empezar una partida desde cero."""
        p = Paleta()
        return p, Pelota(p), crear_ladrillos(), 0, VIDAS_INICIALES, 1

    paleta, pelota, ladrillos, puntos, vidas, nivel = nueva_partida()
    estado = "listo"
    gano = False

    while True:
        # --- Eventos ---
        mouse_x = None
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if e.type == pygame.MOUSEMOTION:
                mouse_x = e.pos[0]
            if e.type == pygame.KEYDOWN and e.key == pygame.K_p and estado in ("jugando", "pausa"):
                estado = "pausa" if estado == "jugando" else "jugando"
            accion = (e.type == pygame.MOUSEBUTTONDOWN or
                      (e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE))
            if accion:
                if estado == "listo":
                    pelota.lanzar()
                    estado = "jugando"
                elif estado == "fin":
                    paleta, pelota, ladrillos, puntos, vidas, nivel = nueva_partida()
                    estado = "listo"

        # --- Lógica ---
        if estado in ("listo", "jugando"):
            paleta.mover(pygame.key.get_pressed(), mouse_x)

        if estado == "listo":
            pelota.seguir_paleta(paleta)

        elif estado == "jugando":
            if pelota.mover():
                # La pelota se cayó: perder una vida
                vidas -= 1
                if vidas == 0:
                    estado, gano = "fin", False
                else:
                    pelota = Pelota(paleta)
                    estado = "listo"
            else:
                # Rebote en la paleta (solo si la pelota va hacia abajo)
                if pelota.vy > 0 and pelota.rect().colliderect(paleta.rect):
                    pelota.rebotar_en_paleta(paleta)
                puntos += colision_ladrillos(pelota, ladrillos)

                # Si no quedan ladrillos, pasar al siguiente nivel
                if not ladrillos:
                    nivel += 1
                    if nivel > 3:
                        estado, gano = "fin", True
                    else:
                        ladrillos = crear_ladrillos()
                        velocidad = pelota.velocidad
                        pelota = Pelota(paleta)
                        pelota.velocidad = velocidad  # mantener la dificultad
                        estado = "listo"

        # --- Dibujo ---
        pantalla.fill(FONDO)
        for l in ladrillos:
            l.dibujar(pantalla)
        paleta.dibujar(pantalla)
        if estado != "fin":
            pelota.dibujar(pantalla)
        dibujar_hud(pantalla, fuente, puntos, vidas, nivel if nivel <= 3 else 3)

        if estado == "listo":
            texto(pantalla, fuente, "ESPACIO o clic para lanzar", (ANCHO // 2, ALTO // 2 + 80))
        elif estado == "pausa":
            texto(pantalla, fuente_grande, "PAUSA", (ANCHO // 2, ALTO // 2))
        elif estado == "fin":
            titulo = "¡GANASTE!" if gano else "GAME OVER"
            color = (110, 220, 110) if gano else (235, 80, 80)
            texto(pantalla, fuente_grande, titulo, (ANCHO // 2, ALTO // 2 - 30), color)
            texto(pantalla, fuente, f"Puntos: {puntos}", (ANCHO // 2, ALTO // 2 + 30))
            texto(pantalla, fuente, "ESPACIO o clic para jugar de nuevo", (ANCHO // 2, ALTO // 2 + 70))

        pygame.display.flip()
        reloj.tick(FPS)


if __name__ == "__main__":
    main()
