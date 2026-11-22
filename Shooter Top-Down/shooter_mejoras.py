"""
Shooter top-down con mejoras (pygame-ce).

Una pequeña nave apunta hacia el mouse y dispara sola, mientras naves
enemigas entran sin descanso por los costados. Con el tiempo los enemigos
aparecen más seguido, tienen más vida y algunos disparan.
El objetivo es sobrevivir el mayor tiempo posible: el contador de tiempo es el puntaje.

Cada minuto aparece un jefe verde, grande y lento. Mientras esté vivo el
cronómetro se detiene y cada enemigo eliminado da un 75% menos de experiencia,
así que conviene derribarlo rápido.

Al salir de una pausa (o de elegir una mejora) hay una cuenta regresiva de
3 segundos antes de que el juego siga.

Cada enemigo destruido da experiencia. Al llenar la barra de experiencia el
juego se pausa y se elige una mejora entre 3 opciones:

    Cadencia +    -> disparar más rápido
    Multidisparo  -> un disparo simultáneo más (en abanico)
    Ventana +     -> la ventana de Windows se agranda
    Vida extra    -> +1 vida                         (rara: 10% de aparecer)
    Escudo        -> bloquea un golpe y al romperse  (rara: 25% de aparecer)
                     explota dañando a todos los enemigos en pantalla;
                     se acumula hasta 3 capas

La ventana arranca chiquita y SOLO crece con la mejora "Ventana +".

Controles:
    W A S D             -> mover la nave
    Mouse               -> apuntar (los disparos son automáticos)
    Clic o teclas 1-2-3 -> elegir mejora
    P                   -> pausa
    ESPACIO / clic      -> reiniciar después de perder
    ESC                 -> salir
"""
import random
import sys

import pygame

# --- Configuración ---------------------------------------------------------
FPS = 60
CUENTA_REGRESIVA = 3 * FPS     # frames de cuenta regresiva al despausar
TAM_INICIAL = (400, 300)       # resolución con la que arranca la ventana (4:3)
INCREMENTO_VENTANA = 110       # píxeles de ancho que suma cada mejora "Ventana +"
VEL_ANIM_VENTANA = 8           # píxeles de ancho por frame mientras la ventana crece
PROPORCION_MAX = 0.88          # tamaño máximo como fracción del escritorio

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

XP_BASE = 10                   # experiencia para pasar del nivel 1 al 2
XP_POR_NIVEL = 10              # cuánto más se necesita en cada nivel siguiente

INTERVALO_JEFE = 60            # cada cuántos segundos de cronómetro aparece un jefe
PENALIZACION_XP_JEFE = 0.25    # multiplicador de experiencia mientras el jefe vive (-75%)
XP_TIRADOR = 2                 # experiencia extra por destruir un enemigo que dispara

DENSIDAD_ESTRELLAS = 1 / 2500  # estrellas por píxel cuadrado de ventana

ENEMIGOS = {
    "normal": dict(radio=13, velocidad=1.8, vida=1, xp=1,
                   color=(235, 80, 80), desde=0, peso=60),
    "rapido": dict(radio=9, velocidad=3.2, vida=1, xp=2,
                   color=(240, 160, 60), desde=25, peso=25),
    "tanque": dict(radio=22, velocidad=1.0, vida=4, xp=5,
                   color=(170, 110, 230), desde=50, peso=15),
    # El jefe tiene peso 0: nunca sale al azar, solo cada INTERVALO_JEFE segundos
    "jefe":   dict(radio=36, velocidad=0.7, vida=30, xp=15,
                   color=(60, 200, 90), desde=0, peso=0),
}

# clave: (título de la tarjeta, descripción, probabilidad de aparecer)
# Las comunes (probabilidad None) llenan los lugares que dejan libres las raras.
# Cada rara se sortea en cada subida de nivel con su propia probabilidad.
MEJORAS = {
    "cadencia": ("Cadencia +", "Disparás un 25% más rápido", None),
    "multidisparo": ("Multidisparo", "+1 disparo simultáneo", None),
    "ventana": ("Ventana +", "La ventana se agranda", None),
    "vida": ("Vida extra", "+1 vida", 0.10),
    "escudo": ("Escudo", "Para 1 golpe y explota: 3 de daño a todos", 0.25),
}

# Colores
FONDO = (10, 12, 24)
BLANCO = (240, 240, 240)
GRIS = (130, 140, 160)
JUGADOR_COLOR = (90, 200, 250)
BALA_COLOR = (255, 240, 140)
BALA_ENEMIGA_COLOR = (255, 90, 160)
VIDA_COLOR = (110, 220, 110)
XP_COLOR = (90, 200, 250)
JEFE_COLOR = ENEMIGOS["jefe"]["color"]
ESCUDO_COLOR = (130, 255, 220)
RARA_COLOR = (240, 200, 80)
TARJETA = (30, 36, 60)
TARJETA_HOVER = (50, 60, 100)


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
        self.cadencia = float(CADENCIA_INICIAL)  # frames entre disparos (baja con mejoras)
        self.disparos = 1                        # disparos simultáneos (sube con mejoras)
        self.escudo = 0                          # capas de escudo (mejora "Escudo")
        self.enfriamiento = 0.0

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
        self.enfriamiento -= 1

    def disparar(self):
        """Devuelve la lista de balas de esta ráfaga (vacía si todavía está recargando).

        Con varios disparos simultáneos, las balas salen en abanico, centradas
        en la dirección en la que apunta la nave.
        """
        if self.enfriamiento > 0:
            return []
        self.enfriamiento += self.cadencia
        balas = []
        inicio = -ABANICO * (self.disparos - 1) / 2
        for i in range(self.disparos):
            direccion = pygame.Vector2(1, 0).rotate(self.angulo + inicio + i * ABANICO)
            balas.append(Bala(self.pos + direccion * 16, direccion * VEL_BALA,
                              BALA_COLOR, RADIO_BALA))
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

    def dibujar(self, pantalla):
        """Dibuja la nave con un anillo por capa de escudo; parpadea si es invulnerable."""
        for i in range(self.escudo):
            pygame.draw.circle(pantalla, ESCUDO_COLOR, self.pos, 17 + i * 5, 2)
        if self.invulnerable and (self.invulnerable // 5) % 2:
            return
        puntos = rotar_puntos(self.FORMA, self.angulo, self.pos)
        pygame.draw.polygon(pantalla, JUGADOR_COLOR, puntos)
        pygame.draw.polygon(pantalla, BLANCO, puntos, 1)


class Bala:
    """Un disparo en línea recta; lo usan tanto el jugador como los enemigos."""

    def __init__(self, pos, vel, color, radio):
        """Crea la bala en `pos` con velocidad `vel`, color y radio dados."""
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.color = color
        self.radio = radio

    def actualizar(self, tam):
        """Avanza la bala. Devuelve True si salió de la pantalla (hay que borrarla)."""
        self.pos += self.vel
        return not (-10 < self.pos.x < tam[0] + 10 and -10 < self.pos.y < tam[1] + 10)

    def dibujar(self, pantalla):
        """Las balas del jugador son trazos; las enemigas, bolitas (más fáciles de ver)."""
        if self.color == BALA_COLOR:
            pygame.draw.line(pantalla, self.color, self.pos - self.vel * 0.6, self.pos, self.radio)
        else:
            pygame.draw.circle(pantalla, self.color, self.pos, self.radio)
            pygame.draw.circle(pantalla, BLANCO, self.pos, self.radio, 1)


class Enemigo:
    """Nave enemiga que entra por un costado, persigue al jugador y quizás dispara."""

    def __init__(self, tipo, pos, fuerza, dispara):
        """Crea un enemigo del tipo indicado en `pos` (fuera de la pantalla).

        `fuerza` multiplica su vida (crece con el tiempo de partida) y
        `dispara` indica si es un tirador.
        """
        datos = ENEMIGOS[tipo]
        self.tipo = tipo
        self.jefe = tipo == "jefe"
        self.radio = datos["radio"]
        self.color = datos["color"]
        self.vida_max = max(1, int(datos["vida"] * fuerza + 0.5))
        self.vida = self.vida_max
        self.xp = datos["xp"] + (XP_TIRADOR if dispara else 0)
        self.velocidad = datos["velocidad"]
        self.dispara = dispara
        self.recarga = random.randint(60, 180)  # el primer disparo llega antes
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

    def intentar_disparo(self, objetivo, tam):
        """Si es tirador, está dentro de la pantalla y ya recargó, dispara al jugador.

        Devuelve la bala disparada o None.
        """
        if not self.dispara or not (0 < self.pos.x < tam[0] and 0 < self.pos.y < tam[1]):
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

    def recibir_disparo(self, danio=1):
        """Resta `danio` de vida al enemigo. Devuelve True si quedó destruido."""
        self.vida -= danio
        self.destello = 4
        return self.vida <= 0

    def dibujar(self, pantalla):
        """Dibuja el enemigo como un rombo orientado hacia donde se mueve.

        Los tiradores llevan un núcleo rosa y los que tienen más de 1 de vida
        muestran una barrita de vida encima.
        """
        angulo = self.vel.as_polar()[1] if self.vel.length_squared() else 0
        r = self.radio
        forma = [(r, 0), (0, -r * 0.8), (-r * 0.6, 0), (0, r * 0.8)]
        puntos = rotar_puntos(forma, angulo, self.pos)
        pygame.draw.polygon(pantalla, BLANCO if self.destello else self.color, puntos)
        pygame.draw.polygon(pantalla, FONDO, puntos, 1)
        if self.dispara:
            pygame.draw.circle(pantalla, BALA_ENEMIGA_COLOR, self.pos, max(3, r // 3))
        if self.jefe:
            pygame.draw.circle(pantalla, BLANCO, self.pos, r // 4, 2)  # "ojo" del jefe
        elif self.vida_max > 1:  # el jefe usa la barra grande del HUD
            ancho = r * 2
            x, y = self.pos.x - r, self.pos.y - r - 7
            pygame.draw.rect(pantalla, (60, 20, 30), (x, y, ancho, 3))
            pygame.draw.rect(pantalla, VIDA_COLOR, (x, y, ancho * self.vida / self.vida_max, 3))


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


class Onda:
    """Anillo que se expande desde la nave cuando explota una capa de escudo (solo visual)."""

    DURACION = 28

    def __init__(self, pos, radio_max):
        """Crea la onda en `pos`; crece hasta `radio_max` y se desvanece."""
        self.pos = pygame.Vector2(pos)
        self.radio_max = radio_max
        self.vida = self.DURACION

    def actualizar(self):
        """Avanza la animación. Devuelve True cuando terminó."""
        self.vida -= 1
        return self.vida <= 0

    def dibujar(self, pantalla):
        """Dibuja el anillo, más grande y más fino a medida que avanza."""
        avance = 1 - self.vida / self.DURACION
        radio = 20 + (self.radio_max - 20) * avance
        grosor = max(1, int(8 * (1 - avance)))
        pygame.draw.circle(pantalla, ESCUDO_COLOR, self.pos, radio, grosor)


class Juego:
    """Maneja la ventana, las entidades, la experiencia, las mejoras y las reglas.

    Estados posibles: "jugando", "pausa", "mejora" (eligiendo mejora),
    "cuenta" (cuenta regresiva antes de seguir jugando) y "fin".
    """

    def __init__(self):
        """Crea la ventana chica centrada en el escritorio y empieza una partida."""
        ancho_esc, alto_esc = pygame.display.get_desktop_sizes()[0]
        # Tamaño máximo en 4:3 que entra en el escritorio
        alto_max = min(alto_esc * PROPORCION_MAX, ancho_esc * PROPORCION_MAX * 3 / 4)
        self.ancho_max = int(alto_max * 4 / 3)

        self.ventana = pygame.Window("Shooter - mejoras", TAM_INICIAL)
        self.ventana.position = pygame.WINDOWPOS_CENTERED
        self.pantalla = self.ventana.get_surface()
        self.fuente = pygame.font.SysFont("arial", 18, bold=True)
        self.fuente_chica = pygame.font.SysFont("arial", 13)
        self.fuente_grande = pygame.font.SysFont("arial", 34, bold=True)
        self.fuente_enorme = pygame.font.SysFont("arial", 90, bold=True)
        self.mejor_tiempo = 0.0  # récord de la sesión (se mantiene entre partidas)
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
        self.ancho_objetivo = TAM_INICIAL[0]  # hacia dónde crece la ventana
        self.jugador = Jugador((TAM_INICIAL[0] / 2, TAM_INICIAL[1] / 2))
        self.balas, self.balas_enemigas = [], []
        self.enemigos, self.particulas, self.ondas = [], [], []
        self.xp_pendiente = 0.0     # experiencia ganada en el frame actual
        self.estrellas = []
        self.agregar_estrellas((0, 0), TAM_INICIAL)
        self.tiempo = 0.0           # segundos sobrevividos = puntaje (no cuenta pausas,
                                    # mejoras, cuenta regresiva ni el tiempo con jefe vivo)
        self.proximo_jefe = INTERVALO_JEFE
        self.cuenta = 0             # frames que le quedan a la cuenta regresiva
        self.nuevo_record = False
        self.proximo_enemigo = 1.0  # segundos hasta el próximo enemigo
        self.nivel = 1
        self.xp = 0
        self.opciones = []          # mejoras ofrecidas mientras el estado es "mejora"
        self.estado = "jugando"

    # --- Ventana -----------------------------------------------------------

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
        """Si la ventana es más chica que `ancho_objetivo`, la agranda un poco (animación).

        La ventana se mantiene centrada y todas las entidades se desplazan la
        mitad de lo que crece, así quedan quietas respecto del monitor y el
        espacio nuevo aparece alrededor, por los cuatro lados.
        """
        ancho_actual, alto_actual = self.tam
        if ancho_actual >= self.ancho_objetivo:
            return
        ancho = min(ancho_actual + VEL_ANIM_VENTANA, self.ancho_objetivo)
        nuevo = (ancho, round(ancho * 3 / 4))

        self.ventana.size = nuevo
        self.ventana.position = pygame.WINDOWPOS_CENTERED
        self.pantalla = self.ventana.get_surface()  # la superficie anterior deja de ser válida

        desplazamiento = pygame.Vector2(nuevo[0] - ancho_actual, nuevo[1] - alto_actual) / 2
        self.jugador.pos += desplazamiento
        for grupo in (self.balas, self.balas_enemigas, self.enemigos, self.particulas, self.ondas):
            for cosa in grupo:
                cosa.pos += desplazamiento
        for estrella in self.estrellas:
            estrella[0] += desplazamiento
        self.agregar_estrellas((ancho_actual, alto_actual), nuevo)

    # --- Experiencia y mejoras -------------------------------------------------

    def xp_necesaria(self):
        """Experiencia que hace falta para pasar del nivel actual al siguiente."""
        return XP_BASE + (self.nivel - 1) * XP_POR_NIVEL

    def ganar_xp(self, cantidad):
        """Suma experiencia y, si se llena la barra, sube de nivel y ofrece mejoras."""
        self.xp += cantidad
        if self.estado == "jugando":
            self.revisar_subida_nivel()

    def revisar_subida_nivel(self):
        """Si la barra está llena, sube de nivel, pausa el juego y elige las opciones.

        Primero se sortea cada mejora rara con su probabilidad (por ejemplo,
        "Vida extra" sale el 10% de las veces); las que salen ocupan un lugar.
        Los lugares que quedan, hasta 3, se llenan con mejoras comunes al azar.
        Solo se ofrecen mejoras que todavía no llegaron a su tope; si no queda
        ninguna, solo se sube de nivel.
        """
        if self.xp < self.xp_necesaria():
            return
        self.xp -= self.xp_necesaria()
        self.nivel += 1
        disponibles = [m for m in MEJORAS if self.mejora_disponible(m)]
        raras = [m for m in disponibles
                 if MEJORAS[m][2] is not None and random.random() < MEJORAS[m][2]]
        comunes = [m for m in disponibles if MEJORAS[m][2] is None]
        self.opciones = raras[:3]
        self.opciones += random.sample(comunes, k=min(3 - len(self.opciones), len(comunes)))
        random.shuffle(self.opciones)  # que la rara no salga siempre en el mismo lugar
        if self.opciones:
            self.estado = "mejora"

    def mejora_disponible(self, mejora):
        """Indica si una mejora todavía se puede elegir (no llegó a su tope)."""
        if mejora == "cadencia":
            return self.jugador.cadencia > CADENCIA_MINIMA
        if mejora == "multidisparo":
            return self.jugador.disparos < DISPAROS_MAX
        if mejora == "ventana":
            return self.ancho_objetivo < self.ancho_max
        if mejora == "vida":
            return self.jugador.vidas < VIDAS_MAX
        if mejora == "escudo":
            return self.jugador.escudo < ESCUDO_MAX
        return False

    def describir_estado(self, mejora):
        """Texto corto con el valor actual y el que tendría tras elegir la mejora."""
        j = self.jugador
        if mejora == "cadencia":
            nueva = max(CADENCIA_MINIMA, j.cadencia * FACTOR_CADENCIA)
            return f"{FPS / j.cadencia:.1f} -> {FPS / nueva:.1f} tiros/s"
        if mejora == "multidisparo":
            return f"{j.disparos} -> {j.disparos + 1} disparos"
        if mejora == "vida":
            return f"{j.vidas} -> {j.vidas + 1} vidas"
        if mejora == "escudo":
            return f"{j.escudo} -> {j.escudo + 1} capas"
        ancho = min(self.ancho_objetivo + INCREMENTO_VENTANA, self.ancho_max)
        return f"-> {ancho}x{round(ancho * 3 / 4)}"

    def aplicar_mejora(self, mejora):
        """Aplica la mejora elegida y vuelve al juego (o encadena otra subida de nivel)."""
        if mejora == "cadencia":
            self.jugador.cadencia = max(CADENCIA_MINIMA, self.jugador.cadencia * FACTOR_CADENCIA)
        elif mejora == "multidisparo":
            self.jugador.disparos += 1
        elif mejora == "ventana":
            self.ancho_objetivo = min(self.ancho_objetivo + INCREMENTO_VENTANA, self.ancho_max)
        elif mejora == "vida":
            self.jugador.vidas = min(self.jugador.vidas + 1, VIDAS_MAX)
        elif mejora == "escudo":
            self.jugador.escudo = min(self.jugador.escudo + 1, ESCUDO_MAX)
        self.opciones = []
        self.estado = "jugando"
        self.revisar_subida_nivel()  # por si se juntó experiencia para otro nivel
        if self.estado == "jugando":
            self.iniciar_cuenta()

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

    def rects_tarjetas(self):
        """Calcula los rectángulos de las tarjetas de mejora, centradas en la ventana."""
        ancho_v, alto_v = self.tam
        n = len(self.opciones)
        separacion = 10
        ancho = min(170, (ancho_v - 20 - separacion * (n - 1)) // n)
        alto = 130
        x = (ancho_v - (ancho * n + separacion * (n - 1))) // 2
        y = alto_v // 2 - alto // 2 + 10
        return [pygame.Rect(x + i * (ancho + separacion), y, ancho, alto) for i in range(n)]

    def elegir_con_clic(self, pos):
        """Aplica la mejora de la tarjeta clickeada, si se hizo clic sobre alguna."""
        for rect, mejora in zip(self.rects_tarjetas(), self.opciones):
            if rect.collidepoint(pos):
                self.aplicar_mejora(mejora)
                return

    # --- Partida ---------------------------------------------------------------

    @property
    def jefe_vivo(self):
        """True si hay un jefe verde con vida en pantalla."""
        return any(e.jefe and e.vida > 0 for e in self.enemigos)

    def generar_enemigo(self, tipo=None):
        """Crea un enemigo justo afuera del borde izquierdo o derecho, a una altura al azar.

        Sin `tipo`, se elige uno al azar según los pesos (nunca el jefe).
        Cuanto más dura la partida: aparecen tipos más difíciles, tienen más
        vida y velocidad, y es más probable que sean tiradores. El jefe no dispara.
        """
        if tipo is None:
            disponibles = [t for t, d in ENEMIGOS.items()
                           if d["peso"] > 0 and self.tiempo >= d["desde"]]
            tipo = random.choices(disponibles,
                                  weights=[ENEMIGOS[t]["peso"] for t in disponibles])[0]
        fuerza = 1 + self.tiempo / ESCALADO_VIDA
        if tipo == "jefe" or self.tiempo < TIRADORES_DESDE:
            prob_tirador = 0.0
        else:
            avance = min(1.0, (self.tiempo - TIRADORES_DESDE) / TIRADORES_RAMPA)
            prob_tirador = TIRADORES_PROB_INICIAL + (TIRADORES_PROB_MAX - TIRADORES_PROB_INICIAL) * avance
        dispara = random.random() < prob_tirador

        radio = ENEMIGOS[tipo]["radio"]
        ancho, alto = self.tam
        x = -radio * 2 if random.random() < 0.5 else ancho + radio * 2
        y = random.uniform(radio, alto - radio)
        enemigo = Enemigo(tipo, (x, y), fuerza, dispara)
        enemigo.velocidad *= 1 + min(ESCALADO_VEL_MAX, ESCALADO_VEL * self.tiempo / 60)
        self.enemigos.append(enemigo)

    def explotar(self, pos, color, cantidad=14):
        """Genera chispas en `pos` para mostrar una explosión."""
        self.particulas += [Particula(pos, color) for _ in range(cantidad)]

    def destruir_enemigo(self, e):
        """Registra la muerte de un enemigo: experiencia y explosión.

        Mientras el jefe vive, el resto de los enemigos da 75% menos de
        experiencia; el propio jefe da su experiencia completa.
        """
        penalizado = not e.jefe and self.jefe_vivo
        self.xp_pendiente += e.xp * (PENALIZACION_XP_JEFE if penalizado else 1)
        self.explotar(e.pos, e.color, 60 if e.jefe else 14)

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
        """Explosión de una capa de escudo: daña a TODOS los enemigos en pantalla.

        Cada enemigo visible (aunque sea en parte) recibe el daño de
        DANIO_ESCUDO disparos, el jefe incluido.
        """
        ancho, alto = self.tam
        for e in self.enemigos:
            visible = -e.radio < e.pos.x < ancho + e.radio and -e.radio < e.pos.y < alto + e.radio
            if e.vida > 0 and visible and e.recibir_disparo(DANIO_ESCUDO):
                self.destruir_enemigo(e)
        self.ondas.append(Onda(self.jugador.pos, max(ancho, alto)))
        self.explotar(self.jugador.pos, ESCUDO_COLOR, 24)

    def actualizar(self):
        """Avanza un frame: ventana, jugador, disparos, enemigos, choques y partículas."""
        self.crecer_ventana()
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
        tam = self.tam
        jugador = self.jugador

        jugador.actualizar(pygame.key.get_pressed(), pygame.mouse.get_pos(), tam)
        self.balas += jugador.disparar()  # disparo automático y constante
        self.balas = [b for b in self.balas if not b.actualizar(tam)]
        self.balas_enemigas = [b for b in self.balas_enemigas if not b.actualizar(tam)]

        # Aparición de enemigos: cada vez más seguido
        self.proximo_enemigo -= 1 / FPS
        if self.proximo_enemigo <= 0:
            self.generar_enemigo()
            self.proximo_enemigo = max(INTERVALO_MINIMO,
                                       INTERVALO_INICIAL - self.tiempo * ACELERACION_SPAWN)

        for e in self.enemigos:
            e.actualizar(jugador.pos)
            bala = e.intentar_disparo(jugador.pos, tam)
            if bala:
                self.balas_enemigas.append(bala)

        # Balas del jugador contra enemigos
        for b in self.balas[:]:
            for e in self.enemigos:
                if e.vida > 0 and b.pos.distance_to(e.pos) < e.radio + b.radio:
                    self.balas.remove(b)
                    if e.recibir_disparo():
                        self.destruir_enemigo(e)
                    break

        # Enemigos y balas enemigas contra el jugador
        # (un enemigo común explota al chocar, sin dar experiencia; el jefe sobrevive)
        for e in self.enemigos:
            if e.vida > 0 and e.pos.distance_to(jugador.pos) < e.radio + Jugador.RADIO:
                if self.golpear_jugador() and not e.jefe and e.vida > 0:
                    e.vida = 0
                    self.explotar(e.pos, e.color)
        for b in self.balas_enemigas[:]:
            if b.pos.distance_to(jugador.pos) < b.radio + Jugador.RADIO:
                self.balas_enemigas.remove(b)
                self.golpear_jugador()
        self.enemigos = [e for e in self.enemigos if e.vida > 0]

        if jugador.vidas <= 0:
            self.explotar(jugador.pos, JUGADOR_COLOR, 40)
            self.estado = "fin"
            self.nuevo_record = self.tiempo > self.mejor_tiempo
            self.mejor_tiempo = max(self.mejor_tiempo, self.tiempo)
        elif self.xp_pendiente:
            self.ganar_xp(self.xp_pendiente)

    # --- Dibujo ----------------------------------------------------------------

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
        for b in self.balas_enemigas:
            b.dibujar(p)
        for part in self.particulas:
            part.dibujar(p)
        for onda in self.ondas:
            onda.dibujar(p)
        if self.estado != "fin":
            self.jugador.dibujar(p)
        self.dibujar_hud()

        centro = (self.tam[0] // 2, self.tam[1] // 2)
        if self.estado == "pausa":
            self.oscurecer()
            self.texto("PAUSA", centro, self.fuente_grande)
            self.texto("P para continuar", (centro[0], centro[1] + 34), color=GRIS)
        elif self.estado == "cuenta":
            numero = (self.cuenta + FPS - 1) // FPS  # 3, 2, 1
            self.texto(str(numero), centro, self.fuente_enorme, XP_COLOR)
            self.texto("¡Preparate!", (centro[0], centro[1] + 60), color=GRIS)
        elif self.estado == "mejora":
            self.dibujar_mejoras()
        elif self.estado == "fin":
            self.oscurecer()
            self.texto("GAME OVER", (centro[0], centro[1] - 60), self.fuente_grande, (235, 80, 80))
            self.texto(f"Sobreviviste {self.formato_tiempo(self.tiempo)}", (centro[0], centro[1] - 18))
            if self.nuevo_record:
                self.texto("¡Nuevo récord!", (centro[0], centro[1] + 8), color=VIDA_COLOR)
            else:
                self.texto(f"Récord: {self.formato_tiempo(self.mejor_tiempo)}",
                           (centro[0], centro[1] + 8), color=GRIS)
            self.texto(f"Nivel {self.nivel}   Ventana {self.tam[0]}x{self.tam[1]}",
                       (centro[0], centro[1] + 32), self.fuente_chica)
            self.texto("ESPACIO o clic para reiniciar", (centro[0], centro[1] + 62), color=GRIS)
        self.ventana.flip()

    def dibujar_mejoras(self):
        """Oscurece el juego y dibuja las tarjetas de mejora; la del mouse se resalta."""
        p = self.pantalla
        self.oscurecer()

        rects = self.rects_tarjetas()
        self.texto(f"¡NIVEL {self.nivel}!", (self.tam[0] // 2, rects[0].top - 38),
                   self.fuente_grande, XP_COLOR)
        mouse = pygame.mouse.get_pos()
        for i, (rect, mejora) in enumerate(zip(rects, self.opciones)):
            titulo, descripcion, probabilidad = MEJORAS[mejora]
            rara = probabilidad is not None
            color = TARJETA_HOVER if rect.collidepoint(mouse) else TARJETA
            pygame.draw.rect(p, color, rect, border_radius=8)
            # Las mejoras raras llevan borde dorado y la etiqueta "RARA"
            pygame.draw.rect(p, RARA_COLOR if rara else XP_COLOR, rect, 2, border_radius=8)
            etiqueta = f"[{i + 1}] RARA" if rara else f"[{i + 1}]"
            self.texto(etiqueta, (rect.centerx, rect.top + 14), self.fuente_chica,
                       RARA_COLOR if rara else GRIS)
            self.texto(titulo, (rect.centerx, rect.top + 36))
            y = rect.top + 62
            for linea in partir_texto(self.fuente_chica, descripcion, rect.width - 12):
                self.texto(linea, (rect.centerx, y), self.fuente_chica)
                y += 16
            self.texto(self.describir_estado(mejora), (rect.centerx, rect.bottom - 16),
                       self.fuente_chica, VIDA_COLOR)
        self.texto("Clic o 1-2-3 para elegir", (self.tam[0] // 2, rects[0].bottom + 18),
                   self.fuente_chica, GRIS)

    def dibujar_hud(self):
        """Dibuja el contador de tiempo, nivel, vidas, resolución y la barra de experiencia."""
        p = self.pantalla
        ancho, alto = self.tam
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
            relleno.width = int(barra.width * jefe.vida / jefe.vida_max)
            pygame.draw.rect(p, JEFE_COLOR, relleno)
            pygame.draw.rect(p, BLANCO, barra, 1)
        for i in range(self.jugador.vidas):
            pygame.draw.rect(p, VIDA_COLOR, (ancho - 20 - i * 16, 12, 10, 14), border_radius=2)
        # Capas de escudo: un anillo por capa, debajo de las vidas
        for i in range(self.jugador.escudo):
            pygame.draw.circle(p, ESCUDO_COLOR, (ancho - 15 - i * 16, 36), 5, 2)

        maximo = " (máx.)" if ancho >= self.ancho_max else ""
        s = self.fuente_chica.render(f"{ancho}x{alto}{maximo}", True, GRIS)
        p.blit(s, (8, alto - s.get_height() - 12))

        # Barra de experiencia a lo ancho del borde inferior (gris si está penalizada)
        pygame.draw.rect(p, (30, 40, 60), (0, alto - 7, ancho, 7))
        lleno = min(1.0, self.xp / self.xp_necesaria())
        pygame.draw.rect(p, GRIS if jefe else XP_COLOR, (0, alto - 7, ancho * lleno, 7))
        if jefe:
            s = self.fuente_chica.render("XP -75%", True, JEFE_COLOR)
            p.blit(s, (ancho - s.get_width() - 8, alto - s.get_height() - 12))

    def oscurecer(self):
        """Cubre la pantalla con un velo negro semitransparente para resaltar un cartel."""
        velo = pygame.Surface(self.tam, pygame.SRCALPHA)
        velo.fill((0, 0, 0, 160))
        self.pantalla.blit(velo, (0, 0))

    @staticmethod
    def formato_tiempo(segundos):
        """Devuelve un tiempo en segundos como mm:ss.d (con décimas, como un cronómetro)."""
        minutos, resto = divmod(segundos, 60)
        return f"{int(minutos):02d}:{resto:04.1f}"

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
            if e.type == pygame.KEYDOWN and e.key == pygame.K_p:
                juego.alternar_pausa()

            if juego.estado == "mejora":
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    juego.elegir_con_clic(e.pos)
                elif e.type == pygame.KEYDOWN and pygame.K_1 <= e.key <= pygame.K_3:
                    indice = e.key - pygame.K_1
                    if indice < len(juego.opciones):
                        juego.aplicar_mejora(juego.opciones[indice])
            elif juego.estado == "fin":
                if e.type == pygame.MOUSEBUTTONDOWN or (
                        e.type == pygame.KEYDOWN and e.key == pygame.K_SPACE):
                    juego.reiniciar()

        juego.actualizar()
        juego.dibujar()
        reloj.tick(FPS)


if __name__ == "__main__":
    main()
