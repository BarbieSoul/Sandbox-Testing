"""
Breakout con modificadores - versión arcade con cápsulas de poder (pygame).

Al romper un ladrillo hay una probabilidad (PROB_MODIFICADOR) de que caiga
una cápsula. Si la paleta la atrapa, se activa su efecto:

    E  Expandir   -> paleta más ancha (temporal)
    R  Reducir    -> paleta más angosta (temporal, negativo)
    M  Multibola  -> cada pelota se divide en tres
    L  Lenta      -> las pelotas van más despacio
    F  Rápida     -> las pelotas van más rápido (negativo)
    X  Láser      -> la paleta dispara manteniendo ESPACIO o clic (temporal)
    P  Pegajosa   -> la pelota se pega a la paleta; se relanza con ESPACIO (temporal)
    +  Vida       -> una vida extra (poco frecuente)

Además, la fila superior es de ladrillos metálicos que necesitan dos golpes.

Controles:
    Flechas izquierda/derecha o A/D  -> mover la paleta
    Mouse                            -> también mueve la paleta
    ESPACIO / clic                   -> lanzar la pelota / disparar láser / reiniciar
    P                                -> pausa
    ESC                              -> salir
"""
import copy
import math
import random
import sys

import pygame

# --- Configuración ---------------------------------------------------------
ANCHO, ALTO = 640, 720
FPS = 60

ANCHO_PALETA, ALTO_PALETA = 100, 14
ANCHO_PALETA_GRANDE = 160
ANCHO_PALETA_CHICA = 60
VEL_PALETA = 8

RADIO_PELOTA = 8
VEL_PELOTA_INICIAL = 6.0
VEL_PELOTA_MIN = 4.0
VEL_PELOTA_MAX = 11.0
AUMENTO_VEL = 0.15          # cuánto acelera la pelota con cada ladrillo golpeado
MAX_PELOTAS = 9

FILAS, COLUMNAS = 6, 10
ALTO_LADRILLO = 24
SEPARACION = 4
MARGEN_SUPERIOR = 80

VIDAS_INICIALES = 3
VIDAS_MAX = 6
NIVELES = 3

# --- Modificadores ---------------------------------------------------------
PROB_MODIFICADOR = 0.20     # probabilidad de que un ladrillo roto suelte una cápsula
MAX_CAPSULAS = 3            # cápsulas cayendo a la vez, como máximo
VEL_CAPSULA = 3
DURACION_EFECTO = 12 * FPS  # duración de los efectos temporales (en frames)
VEL_LASER = 10
CADENCIA_LASER = 15         # frames entre disparo y disparo

# tipo: (nombre visible, letra de la cápsula, color, peso)
# El peso es relativo: como suman 100, equivale al % de cada tipo entre las cápsulas.
MODIFICADORES = {
    "expandir":  ("Expandir",  "E", (80, 160, 230), 20),
    "reducir":   ("Reducir",   "R", (120, 120, 130), 10),
    "multibola": ("Multibola", "M", (240, 210, 70), 15),
    "lenta":     ("Lenta",     "L", (240, 150, 60), 15),
    "rapida":    ("Rápida",    "F", (220, 70, 150), 10),
    "laser":     ("Láser",     "X", (235, 80, 80), 12),
    "pegajosa":  ("Pegajosa",  "P", (110, 200, 90), 13),
    "vida":      ("Vida extra", "+", (160, 110, 220), 5),
}

# Colores
FONDO = (20, 24, 40)
BLANCO = (240, 240, 240)
NEGRO = (0, 0, 0)
GRIS = (130, 140, 160)
METAL = (190, 195, 210)
PALETA_COLOR = (90, 200, 250)
PALETA_PEGAJOSA = (110, 200, 90)
LASER_COLOR = (255, 90, 90)
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


def elegir_modificador():
    """Elige al azar un tipo de modificador respetando los pesos de MODIFICADORES."""
    tipos = list(MODIFICADORES)
    pesos = [MODIFICADORES[t][3] for t in tipos]
    return random.choices(tipos, weights=pesos)[0]


class Paleta:
    """La barra que controla el jugador en la parte inferior."""

    def __init__(self):
        """Crea la paleta centrada horizontalmente cerca del borde inferior."""
        self.rect = pygame.Rect(0, 0, ANCHO_PALETA, ALTO_PALETA)
        self.rect.midbottom = (ANCHO // 2, ALTO - 40)

    def cambiar_ancho(self, ancho):
        """Cambia el ancho de la paleta manteniendo su centro (Expandir/Reducir)."""
        centro = self.rect.centerx
        self.rect.width = ancho
        self.rect.centerx = centro
        self.rect.clamp_ip(pygame.Rect(0, 0, ANCHO, ALTO))

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

    def dibujar(self, pantalla, con_laser, pegajosa):
        """Dibuja la paleta; cambia de color si es pegajosa y muestra cañones si tiene láser."""
        color = PALETA_PEGAJOSA if pegajosa else PALETA_COLOR
        pygame.draw.rect(pantalla, color, self.rect, border_radius=7)
        if con_laser:
            for x in (self.rect.left + 6, self.rect.right - 12):
                pygame.draw.rect(pantalla, LASER_COLOR, (x, self.rect.top - 6, 6, 8))


class Pelota:
    """La pelota que rebota contra paredes, paleta y ladrillos."""

    def __init__(self, paleta, velocidad=VEL_PELOTA_INICIAL):
        """Crea la pelota apoyada sobre la paleta, esperando ser lanzada."""
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.velocidad = velocidad
        self.pegada = True  # True mientras está sobre la paleta sin lanzar
        self.offset_x = 0   # distancia al centro de la paleta mientras está pegada
        self.seguir_paleta(paleta)

    def seguir_paleta(self, paleta):
        """Coloca la pelota encima de la paleta, en su punto de apoyo."""
        self.x = paleta.rect.centerx + self.offset_x
        self.y = paleta.rect.top - RADIO_PELOTA - 1

    def pegar(self, paleta):
        """Deja la pelota pegada a la paleta donde la tocó (modificador Pegajosa)."""
        mitad = paleta.rect.width / 2
        self.offset_x = max(-mitad, min(mitad, self.x - paleta.rect.centerx))
        self.pegada = True
        self.seguir_paleta(paleta)

    def lanzar(self, paleta):
        """Lanza la pelota si está pegada a la paleta.

        En el saque inicial sale con un ángulo aleatorio. Si la atrapó la
        paleta pegajosa, sale con el ángulo que le corresponde al punto donde
        quedó apoyada, igual que si hubiese rebotado ahí.
        """
        if not self.pegada:
            return
        self.pegada = False
        if self.offset_x:
            self.rebotar_en_paleta(paleta)
        else:
            angulo = math.radians(random.uniform(-30, 30))
            self.vx = self.velocidad * math.sin(angulo)
            self.vy = -self.velocidad * math.cos(angulo)
        self.offset_x = 0

    def rect(self):
        """Devuelve el rectángulo que envuelve a la pelota (para colisiones)."""
        return pygame.Rect(int(self.x - RADIO_PELOTA), int(self.y - RADIO_PELOTA),
                           RADIO_PELOTA * 2, RADIO_PELOTA * 2)

    def fijar_velocidad(self, nueva):
        """Cambia la velocidad (dentro de los límites) manteniendo la dirección."""
        self.velocidad = max(VEL_PELOTA_MIN, min(nueva, VEL_PELOTA_MAX))
        actual = math.hypot(self.vx, self.vy)
        if actual:
            self.vx *= self.velocidad / actual
            self.vy *= self.velocidad / actual

    def acelerar(self):
        """Aumenta un poco la velocidad tras golpear un ladrillo."""
        self.fijar_velocidad(self.velocidad + AUMENTO_VEL)

    def clonar(self, grados):
        """Devuelve una copia de la pelota con su dirección girada `grados` (Multibola)."""
        nueva = copy.copy(self)
        v = pygame.math.Vector2(self.vx, self.vy).rotate(grados)
        nueva.vx, nueva.vy = v.x, v.y
        return nueva

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

        Devuelve True si la pelota cayó por debajo de la pantalla.
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
    """Un ladrillo que desaparece al ser golpeado; los metálicos aguantan dos golpes."""

    def __init__(self, x, y, ancho, fila):
        """Crea un ladrillo en (x, y); su color, resistencia y puntaje dependen de la fila."""
        self.rect = pygame.Rect(x, y, ancho, ALTO_LADRILLO)
        self.metalico = fila == 0
        self.golpes = 2 if self.metalico else 1
        self.color = METAL if self.metalico else COLORES_FILAS[fila % len(COLORES_FILAS)]
        self.puntos = (FILAS - fila) * 10  # fila de arriba = más puntos

    def golpear(self):
        """Resta un golpe al ladrillo. Devuelve True si quedó destruido."""
        self.golpes -= 1
        return self.golpes <= 0

    def dibujar(self, pantalla):
        """Dibuja el ladrillo con relieve; los metálicos intactos llevan un marco oscuro."""
        pygame.draw.rect(pantalla, self.color, self.rect, border_radius=3)
        claro = tuple(min(255, c + 50) for c in self.color)
        pygame.draw.line(pantalla, claro, (self.rect.left + 3, self.rect.top + 2),
                         (self.rect.right - 4, self.rect.top + 2), 2)
        if self.metalico and self.golpes > 1:
            pygame.draw.rect(pantalla, GRIS, self.rect.inflate(-8, -8), 2, border_radius=2)


class Capsula:
    """Cápsula de modificador que cae desde un ladrillo roto."""

    def __init__(self, tipo, centro):
        """Crea una cápsula del tipo indicado centrada donde estaba el ladrillo."""
        self.tipo = tipo
        _, self.letra, self.color, _ = MODIFICADORES[tipo]
        self.rect = pygame.Rect(0, 0, 36, 16)
        self.rect.center = centro

    def mover(self):
        """Hace caer la cápsula. Devuelve True si salió por abajo de la pantalla."""
        self.rect.y += VEL_CAPSULA
        return self.rect.top > ALTO

    def dibujar(self, pantalla, fuente):
        """Dibuja la cápsula como una píldora de color con su letra en el centro."""
        pygame.draw.rect(pantalla, self.color, self.rect, border_radius=8)
        pygame.draw.rect(pantalla, BLANCO, self.rect, 1, border_radius=8)
        s = fuente.render(self.letra, True, NEGRO)
        pantalla.blit(s, s.get_rect(center=self.rect.center))


class Laser:
    """Disparo de la paleta con el modificador Láser; rompe el primer ladrillo que toca."""

    def __init__(self, x, y):
        """Crea un disparo que sale desde (x, y) hacia arriba."""
        self.rect = pygame.Rect(x - 2, y - 12, 4, 12)

    def mover(self):
        """Sube el disparo. Devuelve True si salió por arriba de la pantalla."""
        self.rect.y -= VEL_LASER
        return self.rect.bottom < 0

    def dibujar(self, pantalla):
        """Dibuja el disparo como una línea roja."""
        pygame.draw.rect(pantalla, LASER_COLOR, self.rect)


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
    """Detecta si la pelota golpeó un ladrillo y la hace rebotar.

    Para saber hacia dónde rebotar compara cuánto se "metió" la pelota en el
    ladrillo por cada lado: si el solapamiento horizontal es menor, el golpe
    fue de costado (se invierte vx); si no, fue de arriba/abajo (se invierte vy).
    Devuelve el ladrillo si quedó destruido (se saca de la lista), o None.
    """
    r = pelota.rect()
    indice = r.collidelist([l.rect for l in ladrillos])
    if indice == -1:
        return None

    ladrillo = ladrillos[indice]
    lr = ladrillo.rect
    solape_x = min(r.right, lr.right) - max(r.left, lr.left)
    solape_y = min(r.bottom, lr.bottom) - max(r.top, lr.top)
    if solape_x < solape_y:
        pelota.vx = -pelota.vx
    else:
        pelota.vy = -pelota.vy
    pelota.acelerar()
    if ladrillo.golpear():
        ladrillos.pop(indice)
        return ladrillo
    return None


class Juego:
    """Guarda el estado de la partida y aplica las reglas en cada frame.

    Estados posibles:
        "listo"   -> la pelota espera sobre la paleta a ser lanzada
        "jugando" -> la pelota está en movimiento
        "pausa"   -> el juego está detenido
        "fin"     -> se ganó o se perdió; se espera para reiniciar
    """

    def __init__(self):
        """Crea el juego y empieza una partida nueva."""
        self.nueva_partida()

    def nueva_partida(self):
        """Reinicia puntaje, vidas, nivel y ladrillos."""
        self.puntos = 0
        self.vidas = VIDAS_INICIALES
        self.nivel = 1
        self.gano = False
        self.paleta = Paleta()
        self.ladrillos = crear_ladrillos()
        self.mensaje, self.frames_mensaje = "", 0
        self.preparar_saque(VEL_PELOTA_INICIAL)

    def preparar_saque(self, velocidad):
        """Deja una sola pelota sobre la paleta y borra cápsulas, disparos y efectos."""
        self.paleta.cambiar_ancho(ANCHO_PALETA)
        self.pelotas = [Pelota(self.paleta, velocidad)]
        self.capsulas = []
        self.lasers = []
        self.efectos = {}  # tipo de efecto temporal -> frames que le quedan
        self.enfriamiento_laser = 0
        self.estado = "listo"

    def mostrar_mensaje(self, texto):
        """Muestra un aviso breve en pantalla (por ejemplo, el modificador atrapado)."""
        self.mensaje, self.frames_mensaje = texto, int(1.5 * FPS)

    def lanzar_pelotas(self):
        """Lanza todas las pelotas que estén pegadas a la paleta."""
        for p in self.pelotas:
            p.lanzar(self.paleta)

    def romper_ladrillo(self, ladrillo):
        """Suma los puntos del ladrillo roto y, con cierta probabilidad, suelta una cápsula."""
        self.puntos += ladrillo.puntos
        if random.random() < PROB_MODIFICADOR and len(self.capsulas) < MAX_CAPSULAS:
            self.capsulas.append(Capsula(elegir_modificador(), ladrillo.rect.center))

    def aplicar_modificador(self, tipo):
        """Activa el efecto de una cápsula atrapada por la paleta."""
        if tipo == "expandir":
            self.efectos.pop("reducir", None)  # Expandir y Reducir se anulan entre sí
            self.efectos[tipo] = DURACION_EFECTO
            self.paleta.cambiar_ancho(ANCHO_PALETA_GRANDE)
        elif tipo == "reducir":
            self.efectos.pop("expandir", None)
            self.efectos[tipo] = DURACION_EFECTO
            self.paleta.cambiar_ancho(ANCHO_PALETA_CHICA)
        elif tipo == "multibola":
            self.lanzar_pelotas()  # las pelotas pegadas se sueltan para poder dividirse
            nuevas = []
            for p in self.pelotas:
                nuevas += [p.clonar(-20), p.clonar(20)]
            self.pelotas += nuevas[:MAX_PELOTAS - len(self.pelotas)]
        elif tipo == "lenta":
            for p in self.pelotas:
                p.fijar_velocidad(p.velocidad * 0.7)
        elif tipo == "rapida":
            for p in self.pelotas:
                p.fijar_velocidad(p.velocidad * 1.3)
        elif tipo in ("laser", "pegajosa"):
            self.efectos[tipo] = DURACION_EFECTO
        elif tipo == "vida":
            self.vidas = min(self.vidas + 1, VIDAS_MAX)
        self.mostrar_mensaje(MODIFICADORES[tipo][0] + "!")

    def actualizar_efectos(self):
        """Descuenta el tiempo de los efectos temporales y deshace los que terminan."""
        for tipo in list(self.efectos):
            self.efectos[tipo] -= 1
            if self.efectos[tipo] <= 0:
                del self.efectos[tipo]
                if tipo in ("expandir", "reducir"):
                    self.paleta.cambiar_ancho(ANCHO_PALETA)
                elif tipo == "pegajosa":
                    self.lanzar_pelotas()  # al terminar el efecto, se sueltan solas

    def disparar(self):
        """Dispara dos láseres desde los extremos de la paleta, respetando la cadencia."""
        if self.enfriamiento_laser == 0:
            p = self.paleta.rect
            self.lasers += [Laser(p.left + 9, p.top - 6), Laser(p.right - 9, p.top - 6)]
            self.enfriamiento_laser = CADENCIA_LASER

    def perder_vida(self):
        """Resta una vida; si no quedan, termina la partida."""
        self.vidas -= 1
        if self.vidas == 0:
            self.estado, self.gano = "fin", False
        else:
            self.preparar_saque(VEL_PELOTA_INICIAL)

    def actualizar(self, disparando):
        """Avanza un frame de juego: pelotas, disparos, cápsulas, efectos y nivel.

        `disparando` indica si el jugador mantiene apretado ESPACIO o el clic.
        """
        if self.frames_mensaje:
            self.frames_mensaje -= 1
        if self.estado != "jugando":
            return

        # Pelotas
        vivas = []
        for p in self.pelotas:
            if p.pegada:
                p.seguir_paleta(self.paleta)
                vivas.append(p)
                continue
            if p.mover():
                continue  # esta pelota se cayó
            if p.vy > 0 and p.rect().colliderect(self.paleta.rect):
                if "pegajosa" in self.efectos:
                    p.pegar(self.paleta)
                else:
                    p.rebotar_en_paleta(self.paleta)
            roto = colision_ladrillos(p, self.ladrillos)
            if roto:
                self.romper_ladrillo(roto)
            vivas.append(p)
        self.pelotas = vivas
        if not self.pelotas:
            self.perder_vida()  # solo se pierde una vida cuando caen TODAS las pelotas
            return

        # Láser
        if self.enfriamiento_laser:
            self.enfriamiento_laser -= 1
        if disparando and "laser" in self.efectos:
            self.disparar()
        restantes = []
        for l in self.lasers:
            if l.mover():
                continue
            indice = l.rect.collidelist([b.rect for b in self.ladrillos])
            if indice == -1:
                restantes.append(l)
            elif self.ladrillos[indice].golpear():
                self.romper_ladrillo(self.ladrillos.pop(indice))
        self.lasers = restantes

        # Cápsulas: se activan si las atrapa la paleta, se pierden si caen
        cayendo = []
        for c in self.capsulas:
            if c.rect.colliderect(self.paleta.rect):
                self.aplicar_modificador(c.tipo)
            elif not c.mover():
                cayendo.append(c)
        self.capsulas = cayendo

        self.actualizar_efectos()

        # Si no quedan ladrillos, pasar al siguiente nivel (o ganar)
        if not self.ladrillos:
            self.nivel += 1
            if self.nivel > NIVELES:
                self.estado, self.gano = "fin", True
            else:
                velocidad = max(p.velocidad for p in self.pelotas)
                self.ladrillos = crear_ladrillos()
                self.preparar_saque(velocidad)  # mantener la dificultad

    def dibujar(self, pantalla, fuente, fuente_chica, fuente_grande):
        """Dibuja todos los elementos del juego y los textos según el estado."""
        pantalla.fill(FONDO)
        for b in self.ladrillos:
            b.dibujar(pantalla)
        for c in self.capsulas:
            c.dibujar(pantalla, fuente_chica)
        for l in self.lasers:
            l.dibujar(pantalla)
        self.paleta.dibujar(pantalla, "laser" in self.efectos, "pegajosa" in self.efectos)
        if self.estado != "fin":
            for p in self.pelotas:
                p.dibujar(pantalla)
        dibujar_hud(pantalla, fuente, fuente_chica, self)

        centro_x, centro_y = ANCHO // 2, ALTO // 2
        if self.frames_mensaje and self.estado != "fin":
            texto(pantalla, fuente, self.mensaje, (centro_x, centro_y + 130))
        if self.estado == "listo":
            texto(pantalla, fuente, "ESPACIO o clic para lanzar", (centro_x, centro_y + 80))
        elif self.estado == "pausa":
            texto(pantalla, fuente_grande, "PAUSA", (centro_x, centro_y))
        elif self.estado == "fin":
            titulo = "¡GANASTE!" if self.gano else "GAME OVER"
            color = (110, 220, 110) if self.gano else (235, 80, 80)
            texto(pantalla, fuente_grande, titulo, (centro_x, centro_y - 30), color)
            texto(pantalla, fuente, f"Puntos: {self.puntos}", (centro_x, centro_y + 30))
            texto(pantalla, fuente, "ESPACIO o clic para jugar de nuevo", (centro_x, centro_y + 70))


def texto(pantalla, fuente, msg, centro, color=BLANCO):
    """Escribe un texto centrado en la posición `centro`."""
    s = fuente.render(msg, True, color)
    pantalla.blit(s, s.get_rect(center=centro))


def dibujar_hud(pantalla, fuente, fuente_chica, juego):
    """Dibuja la barra superior (puntos, nivel, vidas) y los efectos activos abajo."""
    pantalla.blit(fuente.render(f"Puntos: {juego.puntos}", True, BLANCO), (14, 14))
    s = fuente.render(f"Nivel {min(juego.nivel, NIVELES)}", True, GRIS)
    pantalla.blit(s, s.get_rect(midtop=(ANCHO // 2, 14)))
    # Una pelotita por cada vida
    for i in range(juego.vidas):
        pygame.draw.circle(pantalla, PALETA_COLOR, (ANCHO - 24 - i * 22, 26), 7)
    pygame.draw.line(pantalla, GRIS, (0, 50), (ANCHO, 50), 1)

    # Efectos temporales activos con los segundos que les quedan
    x = 14
    for tipo, frames in juego.efectos.items():
        nombre, _, color, _ = MODIFICADORES[tipo]
        s = fuente_chica.render(f"{nombre} {math.ceil(frames / FPS)}s", True, color)
        pantalla.blit(s, (x, ALTO - 24))
        x += s.get_width() + 16


def main():
    """Bucle principal: inicializa pygame, procesa eventos, actualiza y dibuja."""
    pygame.init()
    pantalla = pygame.display.set_mode((ANCHO, ALTO))
    pygame.display.set_caption("Breakout con modificadores")
    reloj = pygame.time.Clock()
    fuente = pygame.font.SysFont("arial", 22, bold=True)
    fuente_chica = pygame.font.SysFont("arial", 15, bold=True)
    fuente_grande = pygame.font.SysFont("arial", 56, bold=True)

    juego = Juego()

    while True:
        # --- Eventos ---
        mouse_x = None
        for e in pygame.event.get():
            if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if e.type == pygame.MOUSEMOTION:
                mouse_x = e.pos[0]
            if e.type == pygame.KEYDOWN and e.key == pygame.K_p and juego.estado in ("jugando", "pausa"):
                juego.estado = "pausa" if juego.estado == "jugando" else "jugando"
            accion = (e.type == pygame.MOUSEBUTTONDOWN or
                      (e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE))
            if accion:
                if juego.estado == "listo":
                    juego.lanzar_pelotas()
                    juego.estado = "jugando"
                elif juego.estado == "jugando":
                    juego.lanzar_pelotas()  # suelta las pelotas atrapadas por Pegajosa
                elif juego.estado == "fin":
                    juego.nueva_partida()

        # --- Lógica ---
        teclas = pygame.key.get_pressed()
        if juego.estado in ("listo", "jugando"):
            juego.paleta.mover(teclas, mouse_x)
        if juego.estado == "listo":
            for p in juego.pelotas:
                p.seguir_paleta(juego.paleta)
        disparando = teclas[pygame.K_SPACE] or pygame.mouse.get_pressed()[0]
        juego.actualizar(disparando)

        # --- Dibujo ---
        juego.dibujar(pantalla, fuente, fuente_chica, fuente_grande)
        pygame.display.flip()
        reloj.tick(FPS)


if __name__ == "__main__":
    main()
