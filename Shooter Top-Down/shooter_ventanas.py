"""
Shooter top-down multiventana (pygame-ce).

El escenario es TODO el monitor. Cada ventana del juego es un "agujero" por
el que se ve una parte de ese escenario. Al principio hay una sola ventana;
la mejora "Ventana extra" abre otra cerca de la ventana principal.

La nave, los enemigos y las balas se mueven libremente por todo el monitor,
también por el vacío entre ventanas, donde son invisibles. Cuando la nave
está en el vacío, unas flechas en el borde de cada ventana indican dónde está.
Como el mouse se lee en coordenadas del escritorio, se puede apuntar (y
disparar) a enemigos que se ven en otra ventana.

El objetivo es sobrevivir el mayor tiempo posible: el contador de tiempo es el puntaje.
Cada minuto aparece un jefe verde; mientras vive, el cronómetro se detiene y
los enemigos dan 75% menos de experiencia. Desde el 5º jefe, lo acompañan
escoltas que lo orbitan. Después de derrotar al primer jefe, los enemigos
también entran por arriba y por abajo de las ventanas.

Enemigos:
    Normal, Rápido, Tanque  -> persiguen a la nave (algunos disparan)
    Kamikaze                -> al acercarse fija tu posición, acelera y explota
    Divisor                 -> al morir se parte en 2 enemigos más chicos
    Francotirador           -> mantiene distancia, marca una línea y dispara rápido
    Escolta                 -> orbita al jefe y absorbe muchas balas
    Élite (10%)             -> cualquier tipo común con aura dorada: más vida y experiencia

Mejoras (al llenar la barra de experiencia se elige 1 de 3). Rarezas:
    Común (azul)        -> rellenan los lugares que dejan libres las demás
    Rara (dorada)       -> 30% de aparecer en cada sorteo
    Legendaria (morada) -> 15%
    Mítica (roja)       -> 5%

    Comunes:      Cadencia +, Multidisparo, Perforación, Crítico
    Raras:        Escudo, Rebote, Reacción en cadena, Velocidad +
    Legendarias:  Vida extra, Recarga de escudo,
                  División (solo si ya tenés Perforación y Rebote)
    Ventana extra sube de rareza cada 2 veces que se elige
    (común, rara, legendaria y, desde la 7ª, mítica para siempre).

Controles:
    W A S D             -> mover la nave
    Mouse               -> apuntar (los disparos son automáticos)
    Clic o teclas 1-2-3 -> elegir mejora (las tarjetas salen en la ventana principal)
    P                   -> pausa
    ESPACIO / clic      -> reiniciar después de perder
    ESC                 -> salir
"""
import collections
import math
import random
import sys

import pygame

# --- Configuración ---------------------------------------------------------
FPS = 60
CUENTA_REGRESIVA = 3 * FPS     # frames de cuenta regresiva al despausar
FRAMES_SIN_FOCO = 10           # frames sin foco antes de pausar solo (evita falsas alarmas)

TAM_PRINCIPAL = (480, 360)     # tamaño de la ventana principal
TAM_EXTRA = (320, 240)         # tamaño de cada ventana extra
VENTANAS_MAX = 9               # ventanas en total (principal + extras)
MARGEN_VENTANAS = 24           # separación mínima entre ventanas
MARGEN_TITULO = 32             # alto aproximado de la barra de título de la principal
MARGEN_INFERIOR = 60           # espacio reservado para la barra de tareas de Windows
PASO_GRILLA = 16               # precisión (en píxeles) al buscar lugar para una ventana extra
CERCANIA = 60                  # una ventana extra se abre a lo sumo esto más lejos que el lugar libre más cercano
DURACION_NUEVA = 3 * FPS       # frames que una ventana nueva se ve resaltada

VEL_JUGADOR = 4.5
VIDAS = 5
VIDAS_MAX = 8                  # tope de vidas con la mejora "Vida extra"
ESCUDO_MAX = 3                 # capas de escudo acumulables
DANIO_ESCUDO = 3               # daño (en disparos) de la explosión al romperse una capa
INVULNERABLE = 90              # frames sin recibir daño después de un golpe
CADENCIA_INICIAL = 26          # frames entre disparo y disparo (~2,3 por segundo)
CADENCIA_MINIMA = 4
FACTOR_CADENCIA = 0.8          # cada mejora "Cadencia +" multiplica la cadencia por esto
DISPAROS_MAX = 7
ABANICO = 9                    # grados entre disparos simultáneos
VEL_BALA = 11
RADIO_BALA = 3
MAX_BALAS = 500                # tope de balas del jugador (la División puede multiplicarlas)

# Mejoras nuevas
REBOTE_ALCANCE = 350           # distancia máxima para que una bala rebote a otro enemigo
DIVISIONES = 2                 # veces que se divide una bala (se reinicia si mata)
DIVISION_ANGULO = 12           # grados de separación entre las dos balas divididas
CRITICO_POR_NIVEL = 0.10       # chance de crítico (doble daño) por nivel de la mejora
REACCION_RADIO = 55            # radio de la explosión de "Reacción en cadena" en nivel 1...
REACCION_RADIO_NIVEL = 20      # ...y cuánto crece por nivel; el daño es igual al nivel
RECARGA_ESCUDO_SEG = (30, 20, 12)  # segundos para recuperar 1 capa, según el nivel
VELOCIDAD_POR_NIVEL = 0.15     # +15% de velocidad de movimiento por nivel

INTERVALO_INICIAL = 0.9        # segundos entre enemigos al empezar
INTERVALO_MINIMO = 0.18
ACELERACION_SPAWN = 0.008      # cuánto se acorta el intervalo por segundo jugado

ESCALADO_VIDA = 75             # cada tantos segundos los enemigos ganan +100% de vida
ESCALADO_VEL = 0.10            # +10% de velocidad por minuto...
ESCALADO_VEL_MAX = 0.5         # ...hasta un +50%
TIRADORES_DESDE = 20           # segundo desde el que aparecen enemigos que disparan
TIRADORES_PROB_INICIAL = 0.15  # probabilidad de que un enemigo dispare al llegar a ese segundo...
TIRADORES_RAMPA = 120          # ...que sube hasta el máximo en estos segundos
TIRADORES_PROB_MAX = 0.65      # probabilidad máxima de que un enemigo dispare
VEL_BALA_ENEMIGA = 2.6
RADIO_BALA_ENEMIGA = 4
RECARGA_ENEMIGA = (180, 260)   # frames entre disparos enemigos (rango al azar)

KAMIKAZE_DISTANCIA = 170       # a esta distancia fija tu posición y se lanza
KAMIKAZE_VENTANAS_MIN = 3      # ventanas abiertas (contando la principal) para que aparezcan
KAMIKAZE_ROJO = (255, 25, 25)  # color del titileo
KAMIKAZE_MECHA = 50           # frames desde que se lanza hasta que explota
KAMIKAZE_VEL_MAX = 8
KAMIKAZE_ACELERACION = 0.35
KAMIKAZE_RADIO = 60            # radio de su explosión

FRANCO_DISTANCIA = (260, 340)  # distancia que intenta mantener con la nave
FRANCO_APUNTE = 70             # frames que muestra la línea antes de disparar...
FRANCO_FIJA = 20               # ...los últimos, con la dirección ya fija (para poder esquivar)
FRANCO_VEL_BALA = 9
FRANCO_RECARGA = (160, 240)

ESCOLTAS_DESDE_JEFE = 5        # el jefe número 5 (minuto 5) y los siguientes traen escoltas
ESCOLTAS_BASE = 3              # escoltas del 5º jefe; +1 por cada jefe siguiente...
ESCOLTAS_MAX = 6               # ...hasta este máximo

ELITE_PROB = 0.10              # chance de que un enemigo común sea élite
ELITE_VIDA = 3                 # multiplicador de vida de los élite
ELITE_XP = 3                   # multiplicador de experiencia de los élite

XP_BASE = 10                   # experiencia para pasar del nivel 1 al 2
XP_POR_NIVEL = 10              # cuánto más se necesita en cada nivel siguiente

INTERVALO_JEFE = 60            # cada cuántos segundos de cronómetro aparece un jefe
PENALIZACION_XP_JEFE = 0.25    # multiplicador de experiencia mientras el jefe vive (-75%)
XP_TIRADOR = 2                 # experiencia extra por destruir un enemigo que dispara

DENSIDAD_ESTRELLAS = 1 / 2500  # estrellas por píxel cuadrado del monitor

# peso 0 = nunca sale al azar (aparece por otra regla); tirador = puede salir
# como tirador; elite = puede salir como élite
ENEMIGOS = {
    "normal":        dict(radio=13, velocidad=1.8, vida=1, xp=1, color=(235, 80, 80),
                          desde=0, peso=50, tirador=True, elite=True),
    "rapido":        dict(radio=9, velocidad=3.2, vida=1, xp=2, color=(240, 160, 60),
                          desde=25, peso=20, tirador=True, elite=True),
    "tanque":        dict(radio=22, velocidad=1.0, vida=4, xp=5, color=(170, 110, 230),
                          desde=50, peso=12, tirador=True, elite=True),
    "kamikaze":      dict(radio=11, velocidad=2.2, vida=1, xp=2, color=(255, 120, 40),
                          desde=35, peso=12, tirador=False, elite=True),
    "divisor":       dict(radio=17, velocidad=1.5, vida=3, xp=3, color=(60, 200, 200),
                          desde=45, peso=10, tirador=True, elite=True),
    "divisor_chico": dict(radio=9, velocidad=2.6, vida=1, xp=1, color=(60, 200, 200),
                          desde=0, peso=0, tirador=False, elite=False),
    "francotirador": dict(radio=12, velocidad=1.3, vida=2, xp=4, color=(200, 220, 255),
                          desde=70, peso=8, tirador=False, elite=True),
    "escolta":       dict(radio=14, velocidad=1.6, vida=12, xp=4, color=(150, 170, 190),
                          desde=0, peso=0, tirador=False, elite=False),
    "jefe":          dict(radio=36, velocidad=0.7, vida=30, xp=15, color=(60, 200, 90),
                          desde=0, peso=0, tirador=False, elite=False),
}

# Rarezas, de menor a mayor. prob = chance de que una mejora de esa rareza
# aparezca en cada sorteo (las comunes no se sortean: rellenan).
ORDEN_RAREZAS = ["comun", "rara", "legendaria", "mitica"]
RAREZAS = {
    "comun":      dict(nombre="COMÚN", prob=None, color=(90, 160, 250)),
    "rara":       dict(nombre="RARA", prob=0.30, color=(240, 200, 80)),
    "legendaria": dict(nombre="LEGENDARIA", prob=0.15, color=(185, 110, 245)),
    "mitica":     dict(nombre="MÍTICA", prob=0.05, color=(245, 70, 70)),
}

# maximo = nivel tope (las que no lo tienen se limitan por otra regla)
MEJORAS = {
    "cadencia":     dict(titulo="Cadencia +", desc="Disparás un 25% más rápido", rareza="comun"),
    "multidisparo": dict(titulo="Multidisparo", desc="+1 disparo simultáneo", rareza="comun"),
    "perforacion":  dict(titulo="Perforación", desc="Las balas atraviesan 1 enemigo más",
                         rareza="comun", maximo=5),
    "critico":      dict(titulo="Crítico", desc="+10% de chance de hacer doble daño",
                         rareza="comun", maximo=5),
    "ventana":      dict(titulo="Ventana extra", desc="Otra ventana cerca de la principal",
                         rareza="comun"),  # su rareza real sube con el uso (ver Juego.rareza)
    "escudo":       dict(titulo="Escudo", desc="Para 1 golpe y explota: 3 de daño a todos",
                         rareza="rara"),
    "rebote":       dict(titulo="Rebote", desc="Tras impactar, la bala salta a otro enemigo",
                         rareza="rara", maximo=5),
    "reaccion":     dict(titulo="Reacción en cadena", desc="Los enemigos explotan al morir",
                         rareza="rara", maximo=5),
    "velocidad":    dict(titulo="Velocidad +", desc="Te movés un 15% más rápido",
                         rareza="rara", maximo=4),
    "vida":         dict(titulo="Vida extra", desc="+1 vida", rareza="legendaria"),
    "recarga":      dict(titulo="Recarga de escudo", desc="Recuperás capas de escudo con el tiempo",
                         rareza="legendaria", maximo=3),
    "division":     dict(titulo="División", desc="Al impactar, la bala se divide en 2",
                         rareza="legendaria", maximo=1),
}
# Abreviaturas para la lista de mejoras del HUD
ABREVIATURAS = {"perforacion": "Perf", "critico": "Crit", "rebote": "Reb", "reaccion": "Cadena",
                "velocidad": "Vel", "recarga": "Recarga", "division": "Div"}

# Colores
FONDO = (10, 12, 24)
BLANCO = (240, 240, 240)
GRIS = (130, 140, 160)
JUGADOR_COLOR = (90, 200, 250)
BALA_COLOR = (255, 240, 140)
BALA_ENEMIGA_COLOR = (255, 90, 160)
BALA_FRANCO_COLOR = (255, 255, 255)
LINEA_FRANCO_COLOR = (255, 70, 70)
VIDA_COLOR = (110, 220, 110)
XP_COLOR = (90, 200, 250)
JEFE_COLOR = ENEMIGOS["jefe"]["color"]
ESCUDO_COLOR = (130, 255, 220)
ELITE_COLOR = (255, 210, 60)
CRITICO_COLOR = (255, 230, 90)
REACCION_COLOR = (255, 150, 60)
KAMIKAZE_EXPLOSION = (255, 90, 40)
TARJETA = (30, 36, 60)
TARJETA_HOVER = (50, 60, 100)
BORDE_VENTANA = (45, 55, 85)


def rotar_puntos(puntos, angulo, centro):
    """Rota una lista de puntos (relativos al origen) y los traslada a `centro`."""
    return [centro + pygame.Vector2(p).rotate(angulo) for p in puntos]


def partir_texto(fuente, texto, ancho):
    """Divide `texto` en líneas que entren en `ancho` píxeles con esa fuente."""
    lineas, actual = [], ""
    for palabra in texto.split():
        prueba = f"{actual} {palabra}".strip()
        if fuente.size(prueba)[0] <= ancho or not actual:
            actual = prueba
        else:
            lineas.append(actual)
            actual = palabra
    return lineas + [actual] if actual else lineas


# Todas las posiciones del juego están en coordenadas del ESCRITORIO (el
# "mundo"). Para dibujar en una ventana se les resta `o`, la esquina superior
# izquierda de esa ventana en el escritorio.


class Jugador:
    """La nave del jugador: se mueve con WASD, mira hacia el mouse y dispara sola."""

    FORMA = [(16, 0), (-10, -10), (-5, 0), (-10, 10)]  # triángulo con muesca atrás
    RADIO = 10

    def __init__(self, centro):
        """Crea la nave en `centro` con todas sus vidas y sin mejoras."""
        self.pos = pygame.Vector2(centro)
        self.vel = pygame.Vector2()
        self.angulo = 0.0
        self.vidas = VIDAS
        self.invulnerable = 0
        self.velocidad = VEL_JUGADOR
        self.cadencia = float(CADENCIA_INICIAL)  # frames entre disparos (baja con mejoras)
        self.disparos = 1                        # disparos simultáneos
        self.perforacion = 0                     # enemigos que atraviesa cada bala
        self.rebotes = 0                         # saltos a otro enemigo tras impactar
        self.division = False                    # las balas se dividen al impactar
        self.escudo = 0                          # capas de escudo
        self.enfriamiento = 0.0

    def actualizar(self, teclas, mouse, limites):
        """Mueve la nave según WASD, la orienta hacia el mouse y la mantiene en el monitor.

        `limites` es el rectángulo del monitor: la nave puede ir a cualquier
        lado, también al vacío entre ventanas.
        """
        direccion = pygame.Vector2(
            (teclas[pygame.K_d] - teclas[pygame.K_a]),
            (teclas[pygame.K_s] - teclas[pygame.K_w]),
        )
        if direccion.length_squared():
            direccion.scale_to_length(self.velocidad)
        # Interpolar la velocidad da un movimiento suave, con algo de inercia
        self.vel += (direccion - self.vel) * 0.25
        self.pos += self.vel
        self.pos.x = max(limites.left + self.RADIO, min(limites.right - self.RADIO, self.pos.x))
        self.pos.y = max(limites.top + self.RADIO, min(limites.bottom - self.RADIO, self.pos.y))

        hacia_mouse = pygame.Vector2(mouse) - self.pos
        if hacia_mouse.length_squared() > 1:
            self.angulo = hacia_mouse.as_polar()[1]

        if self.invulnerable:
            self.invulnerable -= 1
        self.enfriamiento -= 1

    def disparar(self):
        """Devuelve la lista de balas de esta ráfaga (vacía si todavía está recargando).

        Con varios disparos simultáneos, las balas salen en abanico, centradas
        en la dirección en la que apunta la nave. Cada bala lleva las mejoras
        de perforación, rebote y división que tenga la nave.
        """
        if self.enfriamiento > 0:
            return []
        self.enfriamiento += self.cadencia
        balas = []
        inicio = -ABANICO * (self.disparos - 1) / 2
        for i in range(self.disparos):
            direccion = pygame.Vector2(1, 0).rotate(self.angulo + inicio + i * ABANICO)
            balas.append(Bala(self.pos + direccion * 16, direccion * VEL_BALA, BALA_COLOR, RADIO_BALA,
                              perforaciones=self.perforacion, rebotes=self.rebotes,
                              divisiones=DIVISIONES if self.division else 0))
        return balas

    def recibir_golpe(self):
        """Procesa un golpe: primero lo absorbe una capa de escudo, si no hay, cuesta una vida.

        Devuelve "escudo" si se rompió una capa, "vida" si se perdió una vida,
        o None si la nave era invulnerable y no pasó nada.
        """
        if self.invulnerable:
            return None
        self.invulnerable = INVULNERABLE
        if self.escudo:
            self.escudo -= 1
            return "escudo"
        self.vidas -= 1
        return "vida"

    def dibujar(self, pantalla, o):
        """Dibuja la nave con un anillo por capa de escudo; parpadea si es invulnerable."""
        centro = self.pos - o
        for i in range(self.escudo):
            pygame.draw.circle(pantalla, ESCUDO_COLOR, centro, 17 + i * 5, 2)
        if self.invulnerable and (self.invulnerable // 5) % 2:
            return
        puntos = rotar_puntos(self.FORMA, self.angulo, centro)
        pygame.draw.polygon(pantalla, JUGADOR_COLOR, puntos)
        pygame.draw.polygon(pantalla, BLANCO, puntos, 1)


class Bala:
    """Un disparo en línea recta; lo usan tanto el jugador como los enemigos.

    Las balas del jugador además pueden perforar, rebotar y dividirse; para
    eso recuerdan a qué enemigos ya golpearon (así no los golpean dos veces).
    """

    def __init__(self, pos, vel, color, radio, perforaciones=0, rebotes=0, divisiones=0):
        """Crea la bala en `pos` con velocidad `vel`, color, radio y mejoras dadas."""
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.color = color
        self.radio = radio
        self.perforaciones = perforaciones
        self.rebotes = rebotes
        self.divisiones = divisiones
        self.golpeados = set()

    def actualizar(self, limites):
        """Avanza la bala. Devuelve True si salió del monitor (hay que borrarla)."""
        self.pos += self.vel
        return not limites.inflate(20, 20).collidepoint(self.pos)

    def dibujar(self, pantalla, o):
        """Las balas del jugador son trazos; las enemigas, bolitas (más fáciles de ver)."""
        pos = self.pos - o
        if self.color == BALA_COLOR:
            pygame.draw.line(pantalla, self.color, pos - self.vel * 0.6, pos, self.radio)
        elif self.color == BALA_FRANCO_COLOR:
            pygame.draw.line(pantalla, LINEA_FRANCO_COLOR, pos - self.vel * 1.5, pos, 2)
            pygame.draw.circle(pantalla, self.color, pos, self.radio)
        else:
            pygame.draw.circle(pantalla, self.color, pos, self.radio)
            pygame.draw.circle(pantalla, BLANCO, pos, self.radio, 1)


class Enemigo:
    """Nave enemiga. Su comportamiento depende del tipo (ver ENEMIGOS)."""

    def __init__(self, tipo, pos, fuerza, dispara, elite=False):
        """Crea un enemigo del tipo indicado en `pos`.

        `fuerza` multiplica su vida (crece con el tiempo de partida),
        `dispara` indica si es un tirador y `elite` si es la variante dorada,
        con más vida y experiencia.
        """
        datos = ENEMIGOS[tipo]
        self.tipo = tipo
        self.jefe = tipo == "jefe"
        self.elite = elite
        self.radio = datos["radio"]
        self.color = datos["color"]
        vida = datos["vida"] * fuerza * (ELITE_VIDA if elite else 1)
        self.vida_max = max(1, int(vida + 0.5))
        self.vida = self.vida_max
        self.xp = (datos["xp"] + (XP_TIRADOR if dispara else 0)) * (ELITE_XP if elite else 1)
        self.velocidad = datos["velocidad"]
        self.resiste_choque = tipo in ("jefe", "escolta")  # no explotan al chocar con la nave
        self.dispara = dispara
        self.recarga = random.randint(60, 180)  # el primer disparo llega antes
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2()
        self.destello = 0  # frames que se ve blanco tras recibir un disparo
        # Kamikaze: frames hasta explotar desde que se lanzó (None = todavía persigue)
        # y punto fijado al lanzarse (donde estaba la nave en ese momento)
        self.mecha = None
        self.destino = None
        # Francotirador: frames que le quedan apuntando y dirección del disparo
        self.apuntando = 0
        self.dir_apunte = pygame.Vector2(1, 0)
        # Escolta: jefe al que protege, radio y ángulo de su órbita, y velocidad de giro
        self.protege = None
        self.orbita = 0.0
        self.angulo = 0.0
        self.giro = 0.0

    def dirigir(self, deseada):
        """Gira de a poco hacia la velocidad `deseada` y avanza (el giro gradual permite esquivarlo)."""
        if deseada.length_squared() > 0.01:  # evita escalar un vector casi nulo
            deseada.scale_to_length(self.velocidad)
        self.vel += (deseada - self.vel) * 0.04
        self.pos += self.vel

    def actualizar(self, objetivo):
        """Mueve al enemigo según su tipo. Devuelve True si un kamikaze debe explotar."""
        if self.destello:
            self.destello -= 1
        objetivo = pygame.Vector2(objetivo)
        hacia = objetivo - self.pos

        if self.tipo == "kamikaze":
            return self.actualizar_kamikaze(hacia)
        if self.tipo == "escolta" and self.protege is not None and self.protege.vida > 0:
            # Orbita al jefe; si el jefe muere, pasa a perseguir como cualquier otro
            self.angulo += self.giro
            nueva = self.protege.pos + pygame.Vector2(self.orbita, 0).rotate_rad(self.angulo)
            self.vel = nueva - self.pos
            self.pos = nueva
            return False
        if self.tipo == "francotirador":
            # Se queda quieto mientras apunta; si no, mantiene la distancia
            distancia = hacia.length()
            if self.apuntando:
                deseada = pygame.Vector2()
            elif distancia > FRANCO_DISTANCIA[1]:
                deseada = hacia
            elif distancia < FRANCO_DISTANCIA[0]:
                deseada = -hacia
            else:
                deseada = hacia.rotate(90) * 0.5  # se mueve de costado
            self.dirigir(deseada)
            return False
        self.dirigir(hacia)
        return False

    def actualizar_kamikaze(self, hacia):
        """Persigue; al estar cerca fija tu posición actual, acelera hacia ella y explota.

        Una vez lanzado ya no corrige el rumbo: si te movés, lo esquivás.
        Explota al llegar al punto fijado o cuando se termina la mecha, lo
        que pase primero. Devuelve True cuando hay que hacerlo explotar.
        """
        if self.mecha is None:
            if hacia.length() < KAMIKAZE_DISTANCIA and hacia.length_squared() > 0.01:
                self.destino = self.pos + hacia
                self.vel = hacia.normalize() * max(self.vel.length(), self.velocidad)
                self.mecha = KAMIKAZE_MECHA
            else:
                self.dirigir(hacia)
                return False
        if self.vel.length_squared() > 0.01:
            self.vel.scale_to_length(min(KAMIKAZE_VEL_MAX, self.vel.length() + KAMIKAZE_ACELERACION))
        self.pos += self.vel
        self.mecha -= 1
        llego = (self.destino - self.pos).dot(self.vel) <= 0  # ya pasó (o alcanzó) el punto
        return llego or self.mecha <= 0

    def intentar_disparo(self, objetivo, visible):
        """Si puede disparar y se ve en alguna ventana, dispara al jugador.

        Los enemigos que están en el vacío entre ventanas no disparan, para
        que nunca te ataque algo que no podés ver. Devuelve la bala o None.
        """
        if self.tipo == "francotirador":
            return self.disparo_francotirador(objetivo, visible)
        if not self.dispara or not visible:
            return None
        self.recarga -= 1
        if self.recarga > 0:
            return None
        self.recarga = random.randint(*RECARGA_ENEMIGA)
        direccion = pygame.Vector2(objetivo) - self.pos
        if direccion.length_squared() < 0.01:
            return None
        direccion.scale_to_length(VEL_BALA_ENEMIGA)
        return Bala(self.pos, direccion, BALA_ENEMIGA_COLOR, RADIO_BALA_ENEMIGA)

    def disparo_francotirador(self, objetivo, visible):
        """Ciclo del francotirador: recarga, apunta mostrando una línea y dispara rápido.

        La línea sigue a la nave hasta que faltan FRANCO_FIJA frames; ahí se
        congela, así el jugador tiene un momento para salir de la trayectoria.
        Si deja de verse en las ventanas, cancela el disparo.
        """
        if not visible:
            self.apuntando = 0
            return None
        if self.apuntando:
            self.apuntando -= 1
            if self.apuntando > FRANCO_FIJA:
                direccion = pygame.Vector2(objetivo) - self.pos
                if direccion.length_squared() > 0.01:
                    self.dir_apunte = direccion.normalize()
            if self.apuntando == 0:
                self.recarga = random.randint(*FRANCO_RECARGA)
                return Bala(self.pos + self.dir_apunte * self.radio,
                            self.dir_apunte * FRANCO_VEL_BALA, BALA_FRANCO_COLOR, 3)
            return None
        self.recarga -= 1
        if self.recarga <= 0:
            self.apuntando = FRANCO_APUNTE
        return None

    def recibir_disparo(self, danio=1):
        """Resta `danio` de vida al enemigo. Devuelve True si quedó destruido."""
        self.vida -= danio
        self.destello = 4
        return self.vida <= 0

    def forma(self):
        """Puntos del polígono del enemigo (sin rotar), según su tipo."""
        r = self.radio
        if self.tipo == "kamikaze":
            return [(r, 0), (-r, -r * 0.7), (-r * 0.4, 0), (-r, r * 0.7)]  # punta de flecha
        if self.tipo == "francotirador":
            return [(r * 1.4, 0), (-r * 0.6, -r * 0.5), (-r * 0.3, 0), (-r * 0.6, r * 0.5)]
        if self.tipo == "escolta":
            return [(r, r), (r, -r), (-r, -r), (-r, r)]  # bloque cuadrado
        return [(r, 0), (0, -r * 0.8), (-r * 0.6, 0), (0, r * 0.8)]  # rombo

    def dibujar_linea_apunte(self, pantalla, o):
        """Línea roja del francotirador mientras apunta; parpadea cuando ya está fija."""
        if not self.apuntando:
            return
        fija = self.apuntando <= FRANCO_FIJA
        if fija and (self.apuntando // 3) % 2:
            return
        inicio = self.pos - o
        pygame.draw.line(pantalla, LINEA_FRANCO_COLOR, inicio, inicio + self.dir_apunte * 2500,
                         2 if fija else 1)

    def dibujar(self, pantalla, o):
        """Dibuja el enemigo orientado hacia donde se mueve, con sus marcas de tipo.

        Élite: aura dorada. Tirador: núcleo rosa. Kamikaze lanzado: parpadea.
        Los que tienen más de 1 de vida muestran una barrita encima.
        """
        centro = self.pos - o
        r = self.radio
        if self.elite:
            pulso = 2 * math.sin(pygame.time.get_ticks() / 120)
            pygame.draw.circle(pantalla, ELITE_COLOR, centro, r + 7 + pulso, 2)

        color = self.color
        if self.tipo == "kamikaze":
            # Titila en rojo intenso siempre; mucho más rápido cuando ya se lanzó
            periodo = 60 if self.mecha is not None else 160
            if (pygame.time.get_ticks() // periodo) % 2:
                color = KAMIKAZE_ROJO
                pygame.draw.circle(pantalla, KAMIKAZE_ROJO, centro, r + 5, 2)
        if self.destello:
            color = BLANCO
        if self.tipo in ("divisor", "divisor_chico"):
            # Círculo con una raya: se ve "partible"
            pygame.draw.circle(pantalla, color, centro, r)
            pygame.draw.line(pantalla, FONDO, centro - (0, r), centro + (0, r), 2)
        else:
            angulo = self.vel.as_polar()[1] if self.vel.length_squared() else 0
            puntos = rotar_puntos(self.forma(), angulo, centro)
            pygame.draw.polygon(pantalla, color, puntos)
            pygame.draw.polygon(pantalla, FONDO, puntos, 1)

        if self.dispara:
            pygame.draw.circle(pantalla, BALA_ENEMIGA_COLOR, centro, max(3, r // 3))
        if self.jefe:
            pygame.draw.circle(pantalla, BLANCO, centro, r // 4, 2)  # "ojo" del jefe
        elif self.vida_max > 1:  # el jefe usa la barra grande del HUD
            ancho = r * 2
            x, y = centro.x - r, centro.y - r - 8
            pygame.draw.rect(pantalla, (60, 20, 30), (x, y, ancho, 3))
            pygame.draw.rect(pantalla, VIDA_COLOR, (x, y, ancho * max(0, self.vida) / self.vida_max, 3))


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

    def dibujar(self, pantalla, o):
        """Dibuja la chispa, cada vez más chica."""
        pygame.draw.circle(pantalla, self.color, self.pos - o, max(1, self.vida // 8))


class Onda:
    """Anillo que se expande y se desvanece (escudo, reacción en cadena, kamikaze). Solo visual."""

    def __init__(self, pos, radio_max, color=ESCUDO_COLOR, duracion=28, radio_inicial=20):
        """Crea la onda en `pos`; crece de `radio_inicial` a `radio_max` en `duracion` frames."""
        self.pos = pygame.Vector2(pos)
        self.radio_max = radio_max
        self.radio_inicial = radio_inicial
        self.color = color
        self.duracion = duracion
        self.vida = duracion

    def actualizar(self):
        """Avanza la animación. Devuelve True cuando terminó."""
        self.vida -= 1
        return self.vida <= 0

    def dibujar(self, pantalla, o):
        """Dibuja el anillo, más grande y más fino a medida que avanza."""
        avance = 1 - self.vida / self.duracion
        radio = self.radio_inicial + (self.radio_max - self.radio_inicial) * avance
        grosor = max(1, int(8 * (1 - avance)))
        pygame.draw.circle(pantalla, self.color, self.pos - o, radio, grosor)


class Vista:
    """Una ventana de Windows que muestra la parte del escenario que tiene detrás.

    La principal tiene barra de título (para poder cerrarla). Las extra no
    tienen bordes y quedan siempre visibles por encima de otros programas,
    así no se pueden mover ni tapar por accidente.
    """

    def __init__(self, titulo, tam, pos, principal):
        """Abre la ventana con el tamaño y la posición (en el escritorio) indicados."""
        extras = {} if principal else {"borderless": True, "always_on_top": True}
        self.ventana = pygame.Window(titulo, tam, position=pos, **extras)
        self.principal = principal
        self.nueva = 0 if principal else DURACION_NUEVA  # frames de resaltado al aparecer

    @property
    def rect(self):
        """Rectángulo de la ventana en coordenadas del escritorio.

        Se lee en cada frame: si el jugador arrastra la ventana principal, la
        vista simplemente pasa a mostrar otra parte del escenario.
        """
        return pygame.Rect(self.ventana.position, self.ventana.size)

    def cerrar(self):
        """Cierra la ventana."""
        self.ventana.destroy()


class Juego:
    """Maneja las ventanas, las entidades, la experiencia, las mejoras y las reglas.

    Estados posibles: "jugando", "pausa", "mejora" (eligiendo mejora),
    "cuenta" (cuenta regresiva antes de seguir jugando) y "fin".
    """

    def __init__(self):
        """Prepara el escenario (el monitor), las fuentes y empieza una partida."""
        ancho_esc, alto_esc = pygame.display.get_desktop_sizes()[0]
        self.mundo = pygame.Rect(0, 0, ancho_esc, alto_esc)
        # Zona donde se pueden abrir ventanas (sin tapar la barra de tareas)
        self.area_ventanas = pygame.Rect(0, 0, ancho_esc, alto_esc - MARGEN_INFERIOR)

        self.fuente = pygame.font.SysFont("arial", 18, bold=True)
        self.fuente_media = pygame.font.SysFont("arial", 14, bold=True)
        self.fuente_chica = pygame.font.SysFont("arial", 13)
        self.fuente_grande = pygame.font.SysFont("arial", 34, bold=True)
        self.fuente_enorme = pygame.font.SysFont("arial", 90, bold=True)

        # Las estrellas cubren todo el monitor: cada ventana muestra las suyas
        cantidad = int(ancho_esc * alto_esc * DENSIDAD_ESTRELLAS)
        self.estrellas = [(pygame.Vector2(random.uniform(0, ancho_esc), random.uniform(0, alto_esc)),
                           random.randint(60, 200)) for _ in range(cantidad)]

        pos = ((ancho_esc - TAM_PRINCIPAL[0]) // 2, (alto_esc - TAM_PRINCIPAL[1]) // 2)
        self.vistas = [Vista("Shooter - ventanas", TAM_PRINCIPAL, pos, principal=True)]
        self.mejor_tiempo = 0.0  # récord de la sesión (se mantiene entre partidas)
        self.sin_foco = 0
        self.reiniciar()

    @property
    def principal(self):
        """La ventana principal (la primera)."""
        return self.vistas[0]

    def reiniciar(self):
        """Cierra las ventanas extra y arranca una partida desde cero."""
        for vista in self.vistas[1:]:
            vista.cerrar()
        self.vistas = self.vistas[:1]
        self.jugador = Jugador(self.principal.rect.center)
        self.niveles = collections.Counter()  # veces que se eligió cada mejora
        self.balas, self.balas_enemigas = [], []
        self.enemigos, self.particulas, self.ondas = [], [], []
        self.explosiones = []       # explosiones de "Reacción en cadena" pendientes
        self.xp_pendiente = 0.0     # experiencia ganada en el frame actual
        self.tiempo = 0.0           # segundos sobrevividos = puntaje (no cuenta pausas,
                                    # mejoras, cuenta regresiva ni el tiempo con jefe vivo)
        self.proximo_enemigo = 1.0  # segundos hasta el próximo enemigo
        self.proximo_jefe = INTERVALO_JEFE
        self.jefes_aparecidos = 0
        self.jefes_derrotados = 0
        self.progreso_recarga = 0   # frames acumulados hacia la próxima capa de escudo
        self.cuenta = 0             # frames que le quedan a la cuenta regresiva
        self.nuevo_record = False
        self.nivel = 1
        self.xp = 0
        self.opciones = []          # mejoras ofrecidas mientras el estado es "mejora"
        self.estado = "jugando"

    # --- Ventanas ----------------------------------------------------------------

    def visible(self, pos, margen=0):
        """True si el punto `pos` se ve en alguna ventana (con `margen` píxeles de tolerancia)."""
        return any(v.rect.inflate(margen * 2, margen * 2).collidepoint(pos) for v in self.vistas)

    def posicion_libre(self, tam):
        """Busca un lugar CERCA de la ventana principal donde una ventana de `tam` no toque a otras.

        Recorre el monitor en una grilla, se queda con los lugares libres y
        elige uno al azar entre los más cercanos a la principal (hasta
        CERCANIA píxeles más lejos que el mejor). Así queda cerca, pero no
        siempre en el mismo lugar. Devuelve la esquina superior izquierda,
        o None si no hay lugar.
        """
        ocupados = []
        for v in self.vistas:
            r = v.rect.inflate(MARGEN_VENTANAS * 2, MARGEN_VENTANAS * 2)
            if v.principal:  # dejar libre también su barra de título
                r.top -= MARGEN_TITULO
                r.height += MARGEN_TITULO
            ocupados.append(r)
        principal = self.principal.rect
        area = self.area_ventanas
        candidatos = []
        for x in range(area.left, area.right - tam[0] + 1, PASO_GRILLA):
            for y in range(area.top, area.bottom - tam[1] + 1, PASO_GRILLA):
                r = pygame.Rect((x, y), tam)
                if r.collidelist(ocupados) == -1:
                    # distancia entre los bordes de esta ventana y la principal
                    dx = max(principal.left - r.right, r.left - principal.right, 0)
                    dy = max(principal.top - r.bottom, r.top - principal.bottom, 0)
                    candidatos.append((math.hypot(dx, dy), (x, y)))
        if not candidatos:
            return None
        mejor = min(d for d, _ in candidatos)
        return random.choice([pos for d, pos in candidatos if d <= mejor + CERCANIA])

    def agregar_ventana(self):
        """Abre una ventana extra en un lugar libre cerca de la principal (si hay lugar)."""
        pos = self.posicion_libre(TAM_EXTRA)
        if pos is not None:
            self.vistas.append(Vista("Shooter - ventana extra", TAM_EXTRA, pos, principal=False))

    def revisar_foco(self):
        """Pausa solo si el juego perdió el foco del teclado durante varios frames seguidos.

        Pasa, por ejemplo, al hacer clic en el escritorio o en otro programa.
        Cambiar de una ventana del juego a otra no cuenta como perder el foco.
        """
        if pygame.key.get_focused():
            self.sin_foco = 0
            return
        self.sin_foco += 1
        if self.sin_foco >= FRAMES_SIN_FOCO and self.estado in ("jugando", "cuenta"):
            self.estado = "pausa"

    # --- Experiencia y mejoras -------------------------------------------------

    def xp_necesaria(self):
        """Experiencia que hace falta para pasar del nivel actual al siguiente."""
        return XP_BASE + (self.nivel - 1) * XP_POR_NIVEL

    def ganar_xp(self, cantidad):
        """Suma experiencia y, si se llena la barra, sube de nivel y ofrece mejoras."""
        self.xp += cantidad
        if self.estado == "jugando":
            self.revisar_subida_nivel()

    def rareza(self, mejora):
        """Rareza actual de una mejora.

        "Ventana extra" sube un escalón cada 2 veces que se elige y se queda
        en mítica para siempre; las demás tienen rareza fija.
        """
        if mejora == "ventana":
            return ORDEN_RAREZAS[min(self.niveles["ventana"] // 2, len(ORDEN_RAREZAS) - 1)]
        return MEJORAS[mejora]["rareza"]

    def revisar_subida_nivel(self):
        """Si la barra está llena, sube de nivel, pausa el juego y sortea las opciones.

        Cada mejora no común se sortea con la chance de su rareza (rara 30%,
        legendaria 15%, mítica 5%); las que salen ocupan un lugar. Los lugares
        que quedan, hasta 3, se rellenan con mejoras comunes al azar (y si no
        quedan comunes disponibles, con cualquier otra). Solo se ofrecen
        mejoras que todavía no llegaron a su tope.
        """
        if self.xp < self.xp_necesaria():
            return
        self.xp -= self.xp_necesaria()
        self.nivel += 1
        disponibles = [m for m in MEJORAS if self.mejora_disponible(m)]
        sorteadas = [m for m in disponibles if self.rareza(m) != "comun"
                     and random.random() < RAREZAS[self.rareza(m)]["prob"]]
        random.shuffle(sorteadas)
        self.opciones = sorteadas[:3]
        comunes = [m for m in disponibles if self.rareza(m) == "comun"]
        self.opciones += random.sample(comunes, k=min(3 - len(self.opciones), len(comunes)))
        resto = [m for m in disponibles if m not in self.opciones]
        self.opciones += random.sample(resto, k=min(3 - len(self.opciones), len(resto)))
        random.shuffle(self.opciones)
        if self.opciones:
            self.estado = "mejora"

    def mejora_disponible(self, mejora):
        """Indica si una mejora todavía se puede elegir (no llegó a su tope ni le faltan requisitos)."""
        j = self.jugador
        if mejora == "cadencia":
            return j.cadencia > CADENCIA_MINIMA
        if mejora == "multidisparo":
            return j.disparos < DISPAROS_MAX
        if mejora == "ventana":  # también hace falta que quede lugar libre en el monitor
            return len(self.vistas) < VENTANAS_MAX and self.posicion_libre(TAM_EXTRA) is not None
        if mejora == "vida":
            return j.vidas < VIDAS_MAX
        if mejora == "escudo":
            return j.escudo < ESCUDO_MAX
        if mejora == "division":  # evolución: requiere Perforación y Rebote
            if not (self.niveles["perforacion"] and self.niveles["rebote"]):
                return False
        return self.niveles[mejora] < MEJORAS[mejora].get("maximo", 1)

    def radio_reaccion(self, nivel=None):
        """Radio de la explosión de "Reacción en cadena" para un nivel (por defecto, el actual)."""
        nivel = self.niveles["reaccion"] if nivel is None else nivel
        return REACCION_RADIO + REACCION_RADIO_NIVEL * (nivel - 1)

    def describir_estado(self, mejora):
        """Texto corto con el valor actual y el que tendría tras elegir la mejora."""
        j = self.jugador
        n = self.niveles[mejora]
        if mejora == "cadencia":
            nueva = max(CADENCIA_MINIMA, j.cadencia * FACTOR_CADENCIA)
            return f"{FPS / j.cadencia:.1f} -> {FPS / nueva:.1f} tiros/s"
        if mejora == "multidisparo":
            return f"{j.disparos} -> {j.disparos + 1} disparos"
        if mejora == "vida":
            return f"{j.vidas} -> {j.vidas + 1} vidas"
        if mejora == "escudo":
            return f"{j.escudo} -> {j.escudo + 1} capas"
        if mejora == "ventana":
            return f"{len(self.vistas)} -> {len(self.vistas) + 1} ventanas"
        if mejora == "perforacion":
            return f"atraviesa {n} -> {n + 1}"
        if mejora == "critico":
            return f"{n * 10}% -> {(n + 1) * 10}% crítico"
        if mejora == "rebote":
            return f"{n} -> {n + 1} rebotes"
        if mejora == "reaccion":
            return f"radio {self.radio_reaccion(n + 1)}, daño {n + 1}"
        if mejora == "velocidad":
            return f"+{n * 15}% -> +{(n + 1) * 15}%"
        if mejora == "recarga":
            return f"1 capa cada {RECARGA_ESCUDO_SEG[n]}s"
        return f"{DIVISIONES} divisiones por bala"  # división

    def aplicar_mejora(self, mejora):
        """Aplica la mejora elegida y vuelve al juego (o encadena otra subida de nivel)."""
        j = self.jugador
        self.niveles[mejora] += 1
        if mejora == "cadencia":
            j.cadencia = max(CADENCIA_MINIMA, j.cadencia * FACTOR_CADENCIA)
        elif mejora == "multidisparo":
            j.disparos += 1
        elif mejora == "ventana":
            self.agregar_ventana()
        elif mejora == "vida":
            j.vidas = min(j.vidas + 1, VIDAS_MAX)
        elif mejora == "escudo":
            j.escudo = min(j.escudo + 1, ESCUDO_MAX)
        elif mejora == "perforacion":
            j.perforacion += 1
        elif mejora == "rebote":
            j.rebotes += 1
        elif mejora == "division":
            j.division = True
        elif mejora == "velocidad":
            j.velocidad = VEL_JUGADOR * (1 + VELOCIDAD_POR_NIVEL * self.niveles["velocidad"])
        elif mejora == "recarga":
            self.progreso_recarga = 0
        # "critico" y "reaccion" se leen directamente de self.niveles
        self.opciones = []
        self.estado = "jugando"
        self.revisar_subida_nivel()  # por si se juntó experiencia para otro nivel
        if self.estado == "jugando":
            self.iniciar_cuenta()

    def mouse_en_principal(self):
        """Posición del mouse relativa a la ventana principal (para las tarjetas)."""
        x, y = pygame.mouse.get_pos(desktop=True)
        px, py = self.principal.ventana.position
        return (x - px, y - py)

    def rects_tarjetas(self):
        """Calcula los rectángulos de las tarjetas de mejora, centradas en la ventana principal."""
        ancho_v, alto_v = self.principal.ventana.size
        n = len(self.opciones)
        separacion = 10
        ancho = min(170, (ancho_v - 20 - separacion * (n - 1)) // n)
        alto = 140
        x = (ancho_v - (ancho * n + separacion * (n - 1))) // 2
        y = alto_v // 2 - alto // 2 + 10
        return [pygame.Rect(x + i * (ancho + separacion), y, ancho, alto) for i in range(n)]

    def elegir_con_clic(self):
        """Aplica la mejora de la tarjeta bajo el mouse, si hay alguna."""
        pos = self.mouse_en_principal()
        for rect, mejora in zip(self.rects_tarjetas(), self.opciones):
            if rect.collidepoint(pos):
                self.aplicar_mejora(mejora)
                return

    # --- Pausa y cuenta regresiva ----------------------------------------------

    def iniciar_cuenta(self):
        """Arranca la cuenta regresiva de 3 segundos antes de volver a jugar."""
        self.cuenta = CUENTA_REGRESIVA
        self.estado = "cuenta"

    def alternar_pausa(self):
        """Pausa el juego, o si ya estaba pausado arranca la cuenta regresiva para seguir."""
        if self.estado in ("jugando", "cuenta"):
            self.estado = "pausa"
        elif self.estado == "pausa":
            self.iniciar_cuenta()

    # --- Enemigos ----------------------------------------------------------------

    @property
    def jefe_vivo(self):
        """True si hay un jefe verde con vida."""
        return any(e.jefe and e.vida > 0 for e in self.enemigos)

    def fuerza(self):
        """Multiplicador de vida de los enemigos nuevos según el tiempo de partida."""
        return 1 + self.tiempo / ESCALADO_VIDA

    def factor_velocidad(self):
        """Multiplicador de velocidad de los enemigos nuevos según el tiempo de partida."""
        return 1 + min(ESCALADO_VEL_MAX, ESCALADO_VEL * self.tiempo / 60)

    def posicion_entrada(self, radio):
        """Punto justo afuera del borde de una ventana al azar por donde entra un enemigo.

        Al principio solo por los costados; después de derrotar al primer
        jefe, también por arriba y por abajo.
        """
        r = random.choice(self.vistas).rect
        lados = ["izquierda", "derecha"]
        if self.jefes_derrotados:
            lados += ["arriba", "abajo"]
        lado = random.choice(lados)
        if lado == "izquierda":
            return (r.left - radio * 2, random.uniform(r.top + radio, r.bottom - radio))
        if lado == "derecha":
            return (r.right + radio * 2, random.uniform(r.top + radio, r.bottom - radio))
        x = random.uniform(r.left + radio, r.right - radio)
        return (x, r.top - radio * 2) if lado == "arriba" else (x, r.bottom + radio * 2)

    def generar_enemigo(self, tipo=None):
        """Crea un enemigo afuera del borde de una ventana al azar y lo devuelve.

        Sin `tipo`, se elige uno al azar según los pesos. Cuanto más dura la
        partida: aparecen tipos más difíciles, tienen más vida y velocidad, y
        es más probable que sean tiradores. Algunos tipos pueden salir élite.
        """
        if tipo is None:
            disponibles = [t for t, d in ENEMIGOS.items()
                           if d["peso"] > 0 and self.tiempo >= d["desde"]
                           and (t != "kamikaze" or len(self.vistas) >= KAMIKAZE_VENTANAS_MIN)]
            tipo = random.choices(disponibles,
                                  weights=[ENEMIGOS[t]["peso"] for t in disponibles])[0]
        datos = ENEMIGOS[tipo]
        if not datos["tirador"] or self.tiempo < TIRADORES_DESDE:
            prob_tirador = 0.0
        else:
            avance = min(1.0, (self.tiempo - TIRADORES_DESDE) / TIRADORES_RAMPA)
            prob_tirador = TIRADORES_PROB_INICIAL + (TIRADORES_PROB_MAX - TIRADORES_PROB_INICIAL) * avance
        dispara = random.random() < prob_tirador
        elite = datos["elite"] and random.random() < ELITE_PROB

        enemigo = Enemigo(tipo, self.posicion_entrada(datos["radio"]), self.fuerza(), dispara, elite)
        enemigo.velocidad *= self.factor_velocidad()
        self.enemigos.append(enemigo)
        if tipo == "jefe":
            self.jefes_aparecidos += 1
            if self.jefes_aparecidos >= ESCOLTAS_DESDE_JEFE:
                self.generar_escoltas(enemigo)
        return enemigo

    def generar_escoltas(self, jefe):
        """Crea las escoltas del jefe: orbitan a distintas distancias, en sentidos alternados."""
        cantidad = min(ESCOLTAS_MAX, ESCOLTAS_BASE + self.jefes_aparecidos - ESCOLTAS_DESDE_JEFE)
        for i in range(cantidad):
            escolta = Enemigo("escolta", jefe.pos, self.fuerza(), False)
            escolta.protege = jefe
            escolta.orbita = jefe.radio + 30 + i * 26
            escolta.angulo = 2 * math.pi * i / cantidad
            escolta.giro = (0.03 - i * 0.003) * (1 if i % 2 == 0 else -1)
            escolta.pos = jefe.pos + pygame.Vector2(escolta.orbita, 0).rotate_rad(escolta.angulo)
            escolta.velocidad *= self.factor_velocidad()
            self.enemigos.append(escolta)

    def enemigo_cercano(self, pos, excluir=(), alcance=None):
        """El enemigo vivo más cercano a `pos` que no esté en `excluir` (o None)."""
        mejor, mejor_dist = None, alcance if alcance is not None else float("inf")
        for e in self.enemigos:
            if e.vida > 0 and e not in excluir:
                d = e.pos.distance_to(pos)
                if d < mejor_dist:
                    mejor, mejor_dist = e, d
        return mejor

    def explotar(self, pos, color, cantidad=14):
        """Genera chispas en `pos` para mostrar una explosión."""
        self.particulas += [Particula(pos, color) for _ in range(cantidad)]

    def destruir_enemigo(self, e):
        """Registra la muerte de un enemigo: experiencia, explosión y efectos al morir.

        Mientras el jefe vive, el resto de los enemigos da 75% menos de
        experiencia. El divisor se parte en dos; con "Reacción en cadena", el
        enemigo deja una explosión pendiente.
        """
        penalizado = not e.jefe and self.jefe_vivo
        self.xp_pendiente += e.xp * (PENALIZACION_XP_JEFE if penalizado else 1)
        self.explotar(e.pos, ELITE_COLOR if e.elite else e.color, 60 if e.jefe else 14)
        if e.jefe:
            self.jefes_derrotados += 1
        if e.tipo == "divisor":
            costado = (e.vel.rotate(90).normalize() if e.vel.length_squared() > 0.01
                       else pygame.Vector2(0, 1))
            for signo in (-1, 1):
                hijo = Enemigo("divisor_chico", e.pos + costado * signo * 10, self.fuerza(), False)
                hijo.vel = costado * signo * 3
                hijo.velocidad *= self.factor_velocidad()
                self.enemigos.append(hijo)
        if self.niveles["reaccion"]:
            self.explosiones.append(pygame.Vector2(e.pos))

    def procesar_reacciones(self):
        """Resuelve las explosiones de "Reacción en cadena" (pueden encadenarse).

        Cada explosión daña a los enemigos dentro de su radio; si alguno muere,
        agrega su propia explosión a la cola.
        """
        nivel = self.niveles["reaccion"]
        radio = self.radio_reaccion()
        while self.explosiones:
            pos = self.explosiones.pop()
            self.ondas.append(Onda(pos, radio, REACCION_COLOR, duracion=16, radio_inicial=6))
            for e in list(self.enemigos):
                if e.vida > 0 and e.pos.distance_to(pos) < radio + e.radio:
                    if e.recibir_disparo(nivel):
                        self.destruir_enemigo(e)

    def explotar_kamikaze(self, e):
        """Explosión de un kamikaze: daña a la nave si está dentro del radio."""
        e.vida = 0
        self.ondas.append(Onda(e.pos, KAMIKAZE_RADIO, KAMIKAZE_EXPLOSION, duracion=18, radio_inicial=8))
        self.explotar(e.pos, e.color, 20)
        if e.pos.distance_to(self.jugador.pos) < KAMIKAZE_RADIO + Jugador.RADIO:
            self.golpear_jugador()

    # --- Golpes ----------------------------------------------------------------

    def impacto(self, b, e):
        """Resuelve el golpe de una bala del jugador contra un enemigo.

        Orden: daño (con posible crítico), división (crea 2 balas nuevas hacia
        el enemigo más cercano), y después la bala original perfora, rebota
        hacia otro enemigo o se destruye. Devuelve True si la bala sigue viva.
        """
        danio = 1
        if random.random() < CRITICO_POR_NIVEL * self.niveles["critico"]:
            danio = 2
            self.explotar(b.pos, CRITICO_COLOR, 5)
        mato = e.recibir_disparo(danio)
        if mato:
            self.destruir_enemigo(e)
        b.golpeados.add(e)

        # División: si la bala mató, las nuevas balas recuperan todas sus divisiones
        if b.divisiones > 0 and len(self.balas) < MAX_BALAS:
            restantes = DIVISIONES if mato else b.divisiones - 1
            objetivo = self.enemigo_cercano(b.pos, excluir=b.golpeados)
            direccion = (objetivo.pos - b.pos) if objetivo else pygame.Vector2(b.vel)
            if direccion.length_squared() > 0.01:
                direccion = direccion.normalize()
                for angulo in (-DIVISION_ANGULO, DIVISION_ANGULO):
                    hija = Bala(b.pos, direccion.rotate(angulo) * VEL_BALA, BALA_COLOR, RADIO_BALA,
                                divisiones=restantes)
                    hija.golpeados = set(b.golpeados)
                    self.balas.append(hija)

        if b.perforaciones > 0:
            b.perforaciones -= 1
            return True
        if b.rebotes > 0:
            objetivo = self.enemigo_cercano(b.pos, excluir=b.golpeados, alcance=REBOTE_ALCANCE)
            if objetivo is not None:
                b.rebotes -= 1
                direccion = objetivo.pos - b.pos
                if direccion.length_squared() > 0.01:
                    b.vel = direccion.normalize() * VEL_BALA
                    return True
        return False

    def golpear_jugador(self):
        """Aplica un golpe a la nave. Si rompe una capa de escudo, dispara su explosión.

        Devuelve True si el golpe contó (la nave no era invulnerable).
        """
        resultado = self.jugador.recibir_golpe()
        if resultado == "escudo":
            self.explosion_escudo()
        elif resultado == "vida":
            self.explotar(self.jugador.pos, JUGADOR_COLOR, 8)
        return resultado is not None

    def explosion_escudo(self):
        """Explosión de una capa de escudo: daña a TODOS los enemigos visibles.

        Cada enemigo que se vea (aunque sea en parte) en cualquier ventana
        recibe el daño de DANIO_ESCUDO disparos, el jefe incluido. Los que
        están en el vacío entre ventanas no reciben daño.
        """
        for e in list(self.enemigos):
            if e.vida > 0 and self.visible(e.pos, e.radio) and e.recibir_disparo(DANIO_ESCUDO):
                self.destruir_enemigo(e)
        alcance = max(max(v.rect.width, v.rect.height) for v in self.vistas)
        self.ondas.append(Onda(self.jugador.pos, alcance))
        self.explotar(self.jugador.pos, ESCUDO_COLOR, 24)

    # --- Frame -----------------------------------------------------------------

    def actualizar(self):
        """Avanza un frame: jugador, disparos, enemigos, choques, partículas y ventanas."""
        for vista in self.vistas:
            if vista.nueva:
                vista.nueva -= 1
        if self.estado == "cuenta":
            self.cuenta -= 1
            if self.cuenta <= 0:
                self.estado = "jugando"
            return  # durante la cuenta regresiva todo queda congelado
        self.particulas = [p for p in self.particulas if not p.actualizar()]
        self.ondas = [o for o in self.ondas if not o.actualizar()]
        if self.estado != "jugando":
            return
        self.xp_pendiente = 0.0

        # El cronómetro solo avanza si no hay un jefe vivo
        if not self.jefe_vivo:
            self.tiempo += 1 / FPS
            if self.tiempo >= self.proximo_jefe:
                self.generar_enemigo("jefe")
                self.proximo_jefe += INTERVALO_JEFE
        jugador = self.jugador
        self.actualizar_recarga_escudo()

        mouse = pygame.mouse.get_pos(desktop=True)  # en coordenadas del escritorio
        jugador.actualizar(pygame.key.get_pressed(), mouse, self.mundo)
        if len(self.balas) < MAX_BALAS:
            self.balas += jugador.disparar()  # disparo automático y constante
        self.balas = [b for b in self.balas if not b.actualizar(self.mundo)]
        self.balas_enemigas = [b for b in self.balas_enemigas if not b.actualizar(self.mundo)]

        # Aparición de enemigos: cada vez más seguido
        self.proximo_enemigo -= 1 / FPS
        if self.proximo_enemigo <= 0:
            self.generar_enemigo()
            self.proximo_enemigo = max(INTERVALO_MINIMO,
                                       INTERVALO_INICIAL - self.tiempo * ACELERACION_SPAWN)

        for e in list(self.enemigos):
            if e.vida <= 0:
                continue
            if e.actualizar(jugador.pos):  # un kamikaze terminó su mecha
                self.explotar_kamikaze(e)
                continue
            bala = e.intentar_disparo(jugador.pos, self.visible(e.pos))
            if bala:
                self.balas_enemigas.append(bala)

        # Balas del jugador contra enemigos (también en el vacío entre ventanas)
        for b in list(self.balas):
            for e in self.enemigos:
                if e.vida > 0 and e not in b.golpeados and b.pos.distance_to(e.pos) < e.radio + b.radio:
                    if not self.impacto(b, e):
                        self.balas.remove(b)
                    break
        self.procesar_reacciones()

        # Enemigos y balas enemigas contra el jugador
        # (los comunes explotan al chocar, sin dar experiencia; jefe y escoltas sobreviven)
        for e in self.enemigos:
            if e.vida > 0 and e.pos.distance_to(jugador.pos) < e.radio + Jugador.RADIO:
                if self.golpear_jugador() and not e.resiste_choque and e.vida > 0:
                    e.vida = 0
                    self.explotar(e.pos, e.color)
        for b in self.balas_enemigas[:]:
            if b.pos.distance_to(jugador.pos) < b.radio + Jugador.RADIO:
                self.balas_enemigas.remove(b)
                self.golpear_jugador()
        self.procesar_reacciones()  # por si la explosión de un escudo mató enemigos
        self.enemigos = [e for e in self.enemigos if e.vida > 0]

        if jugador.vidas <= 0:
            self.explotar(jugador.pos, JUGADOR_COLOR, 40)
            self.estado = "fin"
            self.nuevo_record = self.tiempo > self.mejor_tiempo
            self.mejor_tiempo = max(self.mejor_tiempo, self.tiempo)
        elif self.xp_pendiente:
            self.ganar_xp(self.xp_pendiente)

    def actualizar_recarga_escudo(self):
        """Con "Recarga de escudo", recupera 1 capa cada cierto tiempo (si no está completo)."""
        nivel = self.niveles["recarga"]
        if not nivel or self.jugador.escudo >= ESCUDO_MAX:
            self.progreso_recarga = 0
            return
        self.progreso_recarga += 1
        if self.progreso_recarga >= RECARGA_ESCUDO_SEG[nivel - 1] * FPS:
            self.progreso_recarga = 0
            self.jugador.escudo += 1
            self.explotar(self.jugador.pos, ESCUDO_COLOR, 10)

    # --- Dibujo ----------------------------------------------------------------

    def dibujar(self):
        """Dibuja cada ventana con la parte del escenario que le toca, más HUD y carteles."""
        nave_visible = self.visible(self.jugador.pos)
        francotiradores = [e for e in self.enemigos if e.apuntando]
        for vista in self.vistas:
            p = vista.ventana.get_surface()
            rect = vista.rect
            o = pygame.Vector2(rect.topleft)
            zona = rect.inflate(80, 80)  # solo se dibuja lo que está cerca de esta ventana

            p.fill(FONDO)
            for pos, brillo in self.estrellas:
                if rect.collidepoint(pos):
                    p.set_at((int(pos.x - o.x), int(pos.y - o.y)), (brillo, brillo, brillo))
            # Las líneas de apunte cruzan ventanas, así que se dibujan aunque el
            # francotirador esté lejos de esta ventana
            for e in francotiradores:
                e.dibujar_linea_apunte(p, o)
            for grupo in (self.balas, self.enemigos, self.balas_enemigas, self.particulas):
                for cosa in grupo:
                    if zona.collidepoint(cosa.pos):
                        cosa.dibujar(p, o)
            for onda in self.ondas:
                onda.dibujar(p, o)
            if self.estado != "fin":
                self.jugador.dibujar(p, o)
                if not nave_visible:
                    self.dibujar_indicador(p, rect)

            # Borde: resaltado mientras la ventana es nueva, discreto el resto del tiempo
            if vista.nueva and (vista.nueva // 10) % 2:
                pygame.draw.rect(p, XP_COLOR, p.get_rect(), 4)
            else:
                pygame.draw.rect(p, BORDE_VENTANA, p.get_rect(), 1)

            if vista.principal:
                self.dibujar_hud(p)
            self.dibujar_carteles(p, vista.principal)
            vista.ventana.flip()

    def dibujar_indicador(self, p, rect):
        """Flecha en el borde de la ventana que apunta hacia la nave cuando está en el vacío."""
        centro = pygame.Vector2(rect.center)
        direccion = self.jugador.pos - centro
        if direccion.length_squared() < 1:
            return
        # Escalar la dirección hasta tocar el borde (con un margen)
        mitad_x, mitad_y = rect.width / 2 - 16, rect.height / 2 - 16
        t = min(mitad_x / abs(direccion.x) if direccion.x else float("inf"),
                mitad_y / abs(direccion.y) if direccion.y else float("inf"))
        punta = centro + direccion * t - pygame.Vector2(rect.topleft)
        angulo = direccion.as_polar()[1]
        puntos = rotar_puntos([(10, 0), (-8, -8), (-8, 8)], angulo, punta)
        pygame.draw.polygon(p, JUGADOR_COLOR, puntos)
        pygame.draw.polygon(p, BLANCO, puntos, 1)

    def dibujar_carteles(self, p, es_principal):
        """Dibuja pausa, cuenta regresiva, mejoras y game over según el estado.

        Las tarjetas de mejora y el resumen del game over van en la ventana
        principal; las demás solo se oscurecen.
        """
        centro = (p.get_width() // 2, p.get_height() // 2)
        if self.estado == "pausa":
            self.oscurecer(p)
            self.texto(p, "PAUSA", centro, self.fuente_grande)
            self.texto(p, "P para continuar", (centro[0], centro[1] + 34), color=GRIS)
        elif self.estado == "cuenta":
            numero = (self.cuenta + FPS - 1) // FPS  # 3, 2, 1
            self.texto(p, str(numero), centro, self.fuente_enorme, XP_COLOR)
            self.texto(p, "¡Preparate!", (centro[0], centro[1] + 60), color=GRIS)
        elif self.estado == "mejora":
            self.oscurecer(p)
            if es_principal:
                self.dibujar_mejoras(p)
        elif self.estado == "fin":
            self.oscurecer(p)
            if not es_principal:
                return
            self.texto(p, "GAME OVER", (centro[0], centro[1] - 60), self.fuente_grande, (235, 80, 80))
            self.texto(p, f"Sobreviviste {self.formato_tiempo(self.tiempo)}", (centro[0], centro[1] - 18))
            if self.nuevo_record:
                self.texto(p, "¡Nuevo récord!", (centro[0], centro[1] + 8), color=VIDA_COLOR)
            else:
                self.texto(p, f"Récord: {self.formato_tiempo(self.mejor_tiempo)}",
                           (centro[0], centro[1] + 8), color=GRIS)
            self.texto(p, f"Nivel {self.nivel}   Ventanas {len(self.vistas)}",
                       (centro[0], centro[1] + 32), self.fuente_chica)
            self.texto(p, "ESPACIO o clic para reiniciar", (centro[0], centro[1] + 62), color=GRIS)

    def dibujar_mejoras(self, p):
        """Dibuja las tarjetas de mejora con el color de su rareza; la del mouse se resalta."""
        rects = self.rects_tarjetas()
        self.texto(p, f"¡NIVEL {self.nivel}!", (p.get_width() // 2, rects[0].top - 34),
                   self.fuente_grande, XP_COLOR)
        mouse = self.mouse_en_principal()
        for i, (rect, mejora) in enumerate(zip(rects, self.opciones)):
            rareza = RAREZAS[self.rareza(mejora)]
            color = TARJETA_HOVER if rect.collidepoint(mouse) else TARJETA
            pygame.draw.rect(p, color, rect, border_radius=8)
            pygame.draw.rect(p, rareza["color"], rect, 2, border_radius=8)
            self.texto(p, f"[{i + 1}] {rareza['nombre']}", (rect.centerx, rect.top + 14),
                       self.fuente_chica, rareza["color"])
            # Si el título no entra con la fuente normal, se usa una más chica
            titulo = MEJORAS[mejora]["titulo"]
            fuente = self.fuente if self.fuente.size(titulo)[0] <= rect.width - 10 else self.fuente_media
            self.texto(p, titulo, (rect.centerx, rect.top + 36), fuente)
            y = rect.top + 60
            for linea in partir_texto(self.fuente_chica, MEJORAS[mejora]["desc"], rect.width - 12):
                self.texto(p, linea, (rect.centerx, y), self.fuente_chica)
                y += 16
            self.texto(p, self.describir_estado(mejora), (rect.centerx, rect.bottom - 16),
                       self.fuente_chica, VIDA_COLOR)
        self.texto(p, "Clic o 1-2-3 para elegir", (p.get_width() // 2, rects[0].bottom + 16),
                   self.fuente_chica, GRIS)

    def dibujar_hud(self, p):
        """Dibuja en la ventana principal: cronómetro, nivel, vidas, escudo, mejoras y experiencia."""
        ancho, alto = p.get_size()
        jefe = next((e for e in self.enemigos if e.jefe and e.vida > 0), None)

        # Con el jefe vivo el cronómetro se ve verde y con la marca de detenido
        color_tiempo = JEFE_COLOR if jefe else BLANCO
        s = self.fuente.render(self.formato_tiempo(self.tiempo), True, color_tiempo)
        p.blit(s, (10, 8))
        if jefe:
            p.blit(self.fuente_chica.render("detenido", True, JEFE_COLOR), (10, 30))
        s = self.fuente.render(f"Nv {self.nivel}", True, GRIS)
        p.blit(s, s.get_rect(midtop=(ancho // 2, 8)))

        # Barra de vida del jefe debajo de la línea superior
        if jefe:
            barra = pygame.Rect(0, 0, int(ancho * 0.5), 8)
            barra.midtop = (ancho // 2, 34)
            pygame.draw.rect(p, (20, 60, 30), barra)
            relleno = barra.copy()
            relleno.width = int(barra.width * max(0, jefe.vida) / jefe.vida_max)
            pygame.draw.rect(p, JEFE_COLOR, relleno)
            pygame.draw.rect(p, BLANCO, barra, 1)

        for i in range(self.jugador.vidas):
            pygame.draw.rect(p, VIDA_COLOR, (ancho - 20 - i * 16, 12, 10, 14), border_radius=2)
        # Capas de escudo: un anillo por capa, debajo de las vidas
        for i in range(self.jugador.escudo):
            pygame.draw.circle(p, ESCUDO_COLOR, (ancho - 15 - i * 16, 36), 5, 2)
        # Progreso de la "Recarga de escudo"
        if self.niveles["recarga"] and self.jugador.escudo < ESCUDO_MAX:
            total = RECARGA_ESCUDO_SEG[self.niveles["recarga"] - 1] * FPS
            pygame.draw.rect(p, (30, 50, 50), (ancho - 58, 46, 48, 3))
            pygame.draw.rect(p, ESCUDO_COLOR, (ancho - 58, 46, 48 * self.progreso_recarga / total, 3))

        # Mejoras especiales obtenidas, con su nivel
        partes = [f"{ABREVIATURAS[m]} {n}" if MEJORAS[m].get("maximo", 1) > 1 else ABREVIATURAS[m]
                  for m, n in self.niveles.items() if m in ABREVIATURAS and n]
        if partes:
            s = self.fuente_chica.render("  ".join(partes), True, GRIS)
            p.blit(s, (8, alto - s.get_height() - 28))
        s = self.fuente_chica.render(f"Ventanas {len(self.vistas)}/{VENTANAS_MAX}", True, GRIS)
        p.blit(s, (8, alto - s.get_height() - 12))

        # Barra de experiencia a lo ancho del borde inferior (gris si está penalizada)
        pygame.draw.rect(p, (30, 40, 60), (0, alto - 7, ancho, 7))
        lleno = min(1.0, self.xp / self.xp_necesaria())
        pygame.draw.rect(p, GRIS if jefe else XP_COLOR, (0, alto - 7, ancho * lleno, 7))
        if jefe:
            s = self.fuente_chica.render("XP -75%", True, JEFE_COLOR)
            p.blit(s, (ancho - s.get_width() - 8, alto - s.get_height() - 12))

    @staticmethod
    def oscurecer(p):
        """Cubre la superficie con un velo negro semitransparente para resaltar un cartel."""
        velo = pygame.Surface(p.get_size(), pygame.SRCALPHA)
        velo.fill((0, 0, 0, 160))
        p.blit(velo, (0, 0))

    @staticmethod
    def formato_tiempo(segundos):
        """Devuelve un tiempo en segundos como mm:ss.d (con décimas, como un cronómetro)."""
        minutos, resto = divmod(segundos, 60)
        return f"{int(minutos):02d}:{resto:04.1f}"

    def texto(self, p, msg, centro, fuente=None, color=BLANCO):
        """Escribe un texto centrado en `centro` sobre la superficie `p`."""
        s = (fuente or self.fuente).render(msg, True, color)
        p.blit(s, s.get_rect(center=centro))


def main():
    """Bucle principal: procesa eventos, actualiza el juego y dibuja todas las ventanas."""
    pygame.init()
    juego = Juego()
    reloj = pygame.time.Clock()

    while True:
        for e in pygame.event.get():
            if e.type in (pygame.QUIT, pygame.WINDOWCLOSE) or (
                    e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                pygame.quit()
                sys.exit()
            if e.type == pygame.KEYDOWN and e.key == pygame.K_p:
                juego.alternar_pausa()

            if juego.estado == "mejora":
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    juego.elegir_con_clic()
                elif e.type == pygame.KEYDOWN and pygame.K_1 <= e.key <= pygame.K_3:
                    indice = e.key - pygame.K_1
                    if indice < len(juego.opciones):
                        juego.aplicar_mejora(juego.opciones[indice])
            elif juego.estado == "fin":
                if e.type == pygame.MOUSEBUTTONDOWN or (
                        e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE):
                    juego.reiniciar()

        juego.revisar_foco()
        juego.actualizar()
        juego.dibujar()
        reloj.tick(FPS)


if __name__ == "__main__":
    main()
