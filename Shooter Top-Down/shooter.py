"""
Shooter top-down con ventana creciente (pygame-ce).

Una pequeña nave apunta hacia el mouse y dispara sola sin parar, mientras
naves enemigas entran sin descanso por los costados de la pantalla.
Lo especial: la ventana de Windows arranca chiquita y va creciendo cuanto
más dura la partida. Crece hacia todos lados desde su centro, así que lo
que ya está en pantalla no se mueve; solo aparece más espacio alrededor.

Controles:
    W A S D        -> mover la nave
    Mouse          -> apuntar (los disparos son automáticos)
    P              -> pausa
    ESPACIO / clic -> reiniciar después de perder
    ESC            -> salir
"""
import random
import sys

import pygame

# --- Configuración ---------------------------------------------------------
FPS = 60
TAM_INICIAL = (400, 300)       # resolución con la que arranca la ventana (4:3)
CRECIMIENTO = 6.0              # píxeles de ancho que gana la ventana por segundo
PASO_MINIMO = 4                # solo se redimensiona cuando la diferencia llega a esto
PROPORCION_MAX = 0.88          # tamaño máximo como fracción del escritorio

VEL_JUGADOR = 4.5
VIDAS = 5
INVULNERABLE = 90              # frames sin recibir daño después de un golpe
CADENCIA = 8                   # frames entre disparo y disparo
VEL_BALA = 11
RADIO_BALA = 3

INTERVALO_INICIAL = 1.2        # segundos entre enemigos al empezar
INTERVALO_MINIMO = 0.25
ACELERACION_SPAWN = 0.006      # cuánto se acorta el intervalo por segundo jugado

DENSIDAD_ESTRELLAS = 1 / 2500  # estrellas por píxel cuadrado de ventana

# tipo: (radio, velocidad, vida, puntos, color, segundo desde el que aparece, peso)
ENEMIGOS = {
    "normal": (13, 1.8, 1, 10, (235, 80, 80), 0, 60),
    "rapido": (9, 3.2, 1, 15, (240, 160, 60), 25, 25),
    "tanque": (22, 1.0, 5, 50, (170, 110, 230), 50, 15),
}

# Colores
FONDO = (10, 12, 24)
BLANCO = (240, 240, 240)
GRIS = (130, 140, 160)
JUGADOR_COLOR = (90, 200, 250)
BALA_COLOR = (255, 240, 140)
VIDA_COLOR = (110, 220, 110)


def rotar_puntos(puntos, angulo, centro):
    """Rota una lista de puntos (relativos al origen) y los traslada a `centro`."""
    return [centro + pygame.Vector2(p).rotate(angulo) for p in puntos]


class Jugador:
    """La nave del jugador: se mueve con WASD y mira siempre hacia el mouse."""

    FORMA = [(16, 0), (-10, -10), (-5, 0), (-10, 10)]  # triángulo con muesca atrás
    RADIO = 10

    def __init__(self, centro):
        """Crea la nave en `centro` con todas sus vidas."""
        self.pos = pygame.Vector2(centro)
        self.vel = pygame.Vector2()
        self.angulo = 0.0
        self.vidas = VIDAS
        self.invulnerable = 0
        self.enfriamiento = 0

    def actualizar(self, teclas, mouse, tam):
        """Mueve la nave según WASD, la orienta hacia el mouse y la mantiene en pantalla."""
        direccion = pygame.Vector2(
            (teclas[pygame.K_d] - teclas[pygame.K_a]),
            (teclas[pygame.K_s] - teclas[pygame.K_w]),
        )
        if direccion.length_squared():
            direccion.scale_to_length(VEL_JUGADOR)
        # Interpolar la velocidad da un movimiento suave, con algo de inercia
        self.vel += (direccion - self.vel) * 0.25
        self.pos += self.vel
        self.pos.x = max(self.RADIO, min(tam[0] - self.RADIO, self.pos.x))
        self.pos.y = max(self.RADIO, min(tam[1] - self.RADIO, self.pos.y))

        hacia_mouse = pygame.Vector2(mouse) - self.pos
        if hacia_mouse.length_squared() > 1:
            self.angulo = hacia_mouse.as_polar()[1]

        if self.invulnerable:
            self.invulnerable -= 1
        if self.enfriamiento:
            self.enfriamiento -= 1

    def disparar(self):
        """Devuelve una bala nueva si ya pasó la cadencia de disparo, o None."""
        if self.enfriamiento:
            return None
        self.enfriamiento = CADENCIA
        direccion = pygame.Vector2(1, 0).rotate(self.angulo)
        return Bala(self.pos + direccion * 16, direccion * VEL_BALA)

    def recibir_golpe(self):
        """Resta una vida si no está en período de invulnerabilidad. Devuelve True si dañó."""
        if self.invulnerable:
            return False
        self.vidas -= 1
        self.invulnerable = INVULNERABLE
        return True

    def dibujar(self, pantalla):
        """Dibuja la nave; parpadea mientras es invulnerable."""
        if self.invulnerable and (self.invulnerable // 5) % 2:
            return
        puntos = rotar_puntos(self.FORMA, self.angulo, self.pos)
        pygame.draw.polygon(pantalla, JUGADOR_COLOR, puntos)
        pygame.draw.polygon(pantalla, BLANCO, puntos, 1)


class Bala:
    """Disparo de la nave del jugador; viaja en línea recta."""

    def __init__(self, pos, vel):
        """Crea la bala en `pos` con velocidad `vel`."""
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)

    def actualizar(self, tam):
        """Avanza la bala. Devuelve True si salió de la pantalla (hay que borrarla)."""
        self.pos += self.vel
        return not (-10 < self.pos.x < tam[0] + 10 and -10 < self.pos.y < tam[1] + 10)

    def dibujar(self, pantalla):
        """Dibuja la bala como un pequeño trazo en la dirección en que viaja."""
        cola = self.pos - self.vel * 0.6
        pygame.draw.line(pantalla, BALA_COLOR, cola, self.pos, RADIO_BALA)


class Enemigo:
    """Nave enemiga que entra por un costado y persigue al jugador."""

    def __init__(self, tipo, pos):
        """Crea un enemigo del tipo indicado en `pos` (fuera de la pantalla)."""
        self.tipo = tipo
        self.radio, self.velocidad, self.vida, self.puntos, self.color, _, _ = ENEMIGOS[tipo]
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2()
        self.destello = 0  # frames que se ve blanco tras recibir un disparo

    def actualizar(self, objetivo):
        """Gira de a poco hacia el jugador y avanza; el giro gradual permite esquivarlo."""
        deseada = pygame.Vector2(objetivo) - self.pos
        if deseada.length_squared() > 0.01:  # evita escalar un vector casi nulo
            deseada.scale_to_length(self.velocidad)
        self.vel += (deseada - self.vel) * 0.04
        self.pos += self.vel
        if self.destello:
            self.destello -= 1

    def recibir_disparo(self):
        """Resta vida al enemigo. Devuelve True si quedó destruido."""
        self.vida -= 1
        self.destello = 4
        return self.vida <= 0

    def dibujar(self, pantalla):
        """Dibuja el enemigo como un rombo orientado hacia donde se mueve."""
        angulo = self.vel.as_polar()[1] if self.vel.length_squared() else 0
        r = self.radio
        forma = [(r, 0), (0, -r * 0.8), (-r * 0.6, 0), (0, r * 0.8)]
        puntos = rotar_puntos(forma, angulo, self.pos)
        pygame.draw.polygon(pantalla, BLANCO if self.destello else self.color, puntos)
        pygame.draw.polygon(pantalla, FONDO, puntos, 1)


class Particula:
    """Chispa de una explosión que se desvanece con el tiempo."""

    def __init__(self, pos, color):
        """Crea una chispa con dirección y velocidad aleatorias."""
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(random.uniform(1, 4), 0).rotate(random.uniform(0, 360))
        self.vida = random.randint(15, 30)
        self.color = color

    def actualizar(self):
        """Mueve y frena la chispa. Devuelve True cuando se apagó."""
        self.pos += self.vel
        self.vel *= 0.92
        self.vida -= 1
        return self.vida <= 0

    def dibujar(self, pantalla):
        """Dibuja la chispa, cada vez más chica."""
        pygame.draw.circle(pantalla, self.color, self.pos, max(1, self.vida // 8))


class Juego:
    """Maneja la ventana (y su crecimiento), las entidades y las reglas.

    Estados posibles: "jugando", "pausa" y "fin".
    """

    def __init__(self):
        """Crea la ventana chica centrada en el escritorio y empieza una partida."""
        ancho_esc, alto_esc = pygame.display.get_desktop_sizes()[0]
        # Tamaño máximo en 4:3 que entra en el escritorio
        alto_max = min(alto_esc * PROPORCION_MAX, ancho_esc * PROPORCION_MAX * 3 / 4)
        self.ancho_max = int(alto_max * 4 / 3)

        self.ventana = pygame.Window("Shooter - ventana creciente", TAM_INICIAL)
        self.ventana.position = pygame.WINDOWPOS_CENTERED
        self.pantalla = self.ventana.get_surface()
        self.fuente = pygame.font.SysFont("arial", 18, bold=True)
        self.fuente_grande = pygame.font.SysFont("arial", 40, bold=True)
        self.reiniciar()

    @property
    def tam(self):
        """Tamaño actual de la ventana (ancho, alto)."""
        return self.ventana.size

    def reiniciar(self):
        """Vuelve la ventana al tamaño inicial y arranca una partida desde cero."""
        self.ventana.size = TAM_INICIAL
        self.ventana.position = pygame.WINDOWPOS_CENTERED
        self.pantalla = self.ventana.get_surface()
        self.jugador = Jugador((TAM_INICIAL[0] / 2, TAM_INICIAL[1] / 2))
        self.balas, self.enemigos, self.particulas = [], [], []
        self.estrellas = []
        self.agregar_estrellas((0, 0), TAM_INICIAL)
        self.puntos = 0
        self.tiempo = 0.0           # segundos jugados (no cuenta la pausa)
        self.proximo_enemigo = 1.0  # segundos hasta el próximo enemigo
        self.tam_maximo_alcanzado = TAM_INICIAL
        self.estado = "jugando"

    def agregar_estrellas(self, tam_viejo, tam_nuevo):
        """Agrega estrellas de fondo solo en la franja nueva que ganó la ventana.

        `tam_viejo` es el rectángulo que ya tenía estrellas, ya centrado dentro
        del tamaño nuevo; así el cielo mantiene la misma densidad al crecer.
        """
        ancho, alto = tam_nuevo
        viejo = pygame.Rect((0, 0), tam_viejo)
        viejo.center = (ancho // 2, alto // 2)
        cantidad = int((ancho * alto - viejo.width * viejo.height) * DENSIDAD_ESTRELLAS)
        while cantidad > 0:
            p = (random.uniform(0, ancho), random.uniform(0, alto))
            if not viejo.collidepoint(p):
                self.estrellas.append([pygame.Vector2(p), random.randint(60, 200)])
                cantidad -= 1

    def crecer_ventana(self):
        """Agranda la ventana según el tiempo jugado, manteniéndola centrada.

        Todas las entidades se desplazan la mitad de lo que crece la ventana,
        así quedan quietas respecto del monitor y el espacio nuevo aparece
        alrededor, por los cuatro lados.
        """
        ancho_objetivo = min(TAM_INICIAL[0] + CRECIMIENTO * self.tiempo, self.ancho_max)
        ancho_actual, alto_actual = self.tam
        if ancho_objetivo - ancho_actual < PASO_MINIMO:
            return
        nuevo = (int(ancho_objetivo), round(ancho_objetivo * 3 / 4))

        self.ventana.size = nuevo
        self.ventana.position = pygame.WINDOWPOS_CENTERED
        self.pantalla = self.ventana.get_surface()  # la superficie anterior deja de ser válida

        desplazamiento = pygame.Vector2(nuevo[0] - ancho_actual, nuevo[1] - alto_actual) / 2
        self.jugador.pos += desplazamiento
        for grupo in (self.balas, self.enemigos, self.particulas):
            for cosa in grupo:
                cosa.pos += desplazamiento
        for estrella in self.estrellas:
            estrella[0] += desplazamiento
        self.agregar_estrellas((ancho_actual, alto_actual), nuevo)
        self.tam_maximo_alcanzado = nuevo

    def generar_enemigo(self):
        """Crea un enemigo justo afuera del borde izquierdo o derecho, a una altura al azar.

        Los tipos más difíciles solo aparecen después de cierto tiempo de partida.
        """
        disponibles = [t for t, datos in ENEMIGOS.items() if self.tiempo >= datos[5]]
        tipo = random.choices(disponibles, weights=[ENEMIGOS[t][6] for t in disponibles])[0]
        radio = ENEMIGOS[tipo][0]
        ancho, alto = self.tam
        x = -radio * 2 if random.random() < 0.5 else ancho + radio * 2
        y = random.uniform(radio, alto - radio)
        self.enemigos.append(Enemigo(tipo, (x, y)))

    def explotar(self, pos, color, cantidad=14):
        """Genera chispas en `pos` para mostrar una explosión."""
        self.particulas += [Particula(pos, color) for _ in range(cantidad)]

    def actualizar(self):
        """Avanza un frame: ventana, jugador, disparos, enemigos, choques y partículas."""
        self.particulas = [p for p in self.particulas if not p.actualizar()]
        if self.estado != "jugando":
            return

        self.tiempo += 1 / FPS
        self.crecer_ventana()
        tam = self.tam

        self.jugador.actualizar(pygame.key.get_pressed(), pygame.mouse.get_pos(), tam)
        bala = self.jugador.disparar()  # disparo automático y constante
        if bala:
            self.balas.append(bala)
        self.balas = [b for b in self.balas if not b.actualizar(tam)]

        # Aparición de enemigos: cada vez más seguido
        self.proximo_enemigo -= 1 / FPS
        if self.proximo_enemigo <= 0:
            self.generar_enemigo()
            self.proximo_enemigo = max(INTERVALO_MINIMO,
                                       INTERVALO_INICIAL - self.tiempo * ACELERACION_SPAWN)

        for e in self.enemigos:
            e.actualizar(self.jugador.pos)

        # Balas contra enemigos
        for b in self.balas[:]:
            for e in self.enemigos:
                if b.pos.distance_to(e.pos) < e.radio + RADIO_BALA:
                    self.balas.remove(b)
                    if e.recibir_disparo():
                        self.puntos += e.puntos
                        self.explotar(e.pos, e.color)
                    break
        self.enemigos = [e for e in self.enemigos if e.vida > 0]

        # Enemigos contra el jugador: el enemigo explota y el jugador pierde una vida
        for e in self.enemigos[:]:
            if e.pos.distance_to(self.jugador.pos) < e.radio + Jugador.RADIO:
                if self.jugador.recibir_golpe():
                    self.enemigos.remove(e)
                    self.explotar(e.pos, e.color)
                    self.explotar(self.jugador.pos, JUGADOR_COLOR, 8)
        if self.jugador.vidas <= 0:
            self.explotar(self.jugador.pos, JUGADOR_COLOR, 40)
            self.estado = "fin"

    def dibujar(self):
        """Dibuja el fondo, las entidades, la interfaz y los carteles según el estado."""
        p = self.pantalla
        p.fill(FONDO)
        for pos, brillo in self.estrellas:
            p.set_at((int(pos.x), int(pos.y)), (brillo, brillo, brillo))
        for b in self.balas:
            b.dibujar(p)
        for e in self.enemigos:
            e.dibujar(p)
        for part in self.particulas:
            part.dibujar(p)
        if self.estado != "fin":
            self.jugador.dibujar(p)
        self.dibujar_hud()

        centro = (self.tam[0] // 2, self.tam[1] // 2)
        if self.estado == "pausa":
            self.texto("PAUSA", centro, self.fuente_grande)
        elif self.estado == "fin":
            ancho, alto = self.tam_maximo_alcanzado
            self.texto("GAME OVER", (centro[0], centro[1] - 50), self.fuente_grande, (235, 80, 80))
            self.texto(f"Puntos: {self.puntos}   Tiempo: {self.formato_tiempo()}",
                       (centro[0], centro[1]))
            self.texto(f"Ventana máxima: {ancho}x{alto}", (centro[0], centro[1] + 28))
            self.texto("ESPACIO o clic para reiniciar", (centro[0], centro[1] + 64), color=GRIS)
        self.ventana.flip()

    def dibujar_hud(self):
        """Dibuja puntos, tiempo, vidas y la resolución actual de la ventana."""
        p = self.pantalla
        ancho, alto = self.tam
        p.blit(self.fuente.render(f"Puntos: {self.puntos}", True, BLANCO), (10, 8))
        s = self.fuente.render(self.formato_tiempo(), True, GRIS)
        p.blit(s, s.get_rect(midtop=(ancho // 2, 8)))
        for i in range(self.jugador.vidas):
            pygame.draw.rect(p, VIDA_COLOR, (ancho - 20 - i * 16, 12, 10, 14), border_radius=2)
        maximo = " (máx.)" if ancho >= self.ancho_max - PASO_MINIMO else ""
        s = self.fuente.render(f"{ancho}x{alto}{maximo}", True, GRIS)
        p.blit(s, (10, alto - s.get_height() - 6))

    def formato_tiempo(self):
        """Devuelve el tiempo jugado como mm:ss."""
        segundos = int(self.tiempo)
        return f"{segundos // 60:02d}:{segundos % 60:02d}"

    def texto(self, msg, centro, fuente=None, color=BLANCO):
        """Escribe un texto centrado en `centro`."""
        s = (fuente or self.fuente).render(msg, True, color)
        self.pantalla.blit(s, s.get_rect(center=centro))


def main():
    """Bucle principal: procesa eventos, actualiza el juego y lo dibuja a 60 FPS."""
    pygame.init()
    juego = Juego()
    reloj = pygame.time.Clock()

    while True:
        for e in pygame.event.get():
            if e.type in (pygame.QUIT, pygame.WINDOWCLOSE) or (
                    e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_p and juego.estado != "fin":
                juego.estado = "pausa" if juego.estado == "jugando" else "jugando"
            reinicio = (e.type == pygame.MOUSEBUTTONDOWN or
                        (e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE))
            if reinicio and juego.estado == "fin":
                juego.reiniciar()

        juego.actualizar()
        juego.dibujar()
        reloj.tick(FPS)


if __name__ == "__main__":
    main()
