# Screener ASH — contexto del proyecto

Este archivo es el traspaso completo del proyecto. Leelo entero antes de tocar
código: hay varias decisiones que parecen arbitrarias y no lo son, y hay cinco o
seis trampas que ya se pisaron una vez.

---

## 1. Qué es y para qué

Un screener de acciones tipo Finviz, pero con indicadores propios que Finviz no
tiene, en particular el **ASH** (Absolute Strength Histogram). Lo usa una sola
persona, un trader argentino que opera CEDEARs y ADRs.

El objetivo central: **filtrar y ordenar ~465 papeles por la señal del ASH**,
cruzando eso con tendencia (las nubes Paragon), momentum (RSI, ADR, ADX), liquidez y fuerza
relativa de la industria. El resultado se mira todos los días después del cierre
de Nueva York.

Lo que **no** es: no es un backtester, no es tiempo real, no ejecuta órdenes.

### El usuario

Escribe en español rioplatense, es técnico, itera mucho. Pide auditorías y espera
que se le diga cuando algo está mal, incluso si el error es propio. Ya pasó dos
veces que se entregó algo sin verificar y salió mal; **verificá siempre antes de
decir que algo funciona**. Prefiere que se le expliquen los límites reales de una
solución antes que promesas.

---

## 2. Arquitectura: tres formas de usar lo mismo

El mismo motor de cálculo corre en tres contextos. Es importante entender por qué
existen los tres, porque un cambio en `plantilla.html` los afecta a todos.

### A. Sitio publicado (GitHub Pages) — el modo principal

```
GitHub Actions (cron nocturno)
  └─ python generar_sitio.py
       ├─ baja precios de Yahoo con yfinance
       └─ escribe sitio/index.html (~83 KB) + sitio/datos.json (~8 MB)
  └─ peaceiris/actions-gh-pages publica en la rama gh-pages
        └─ GitHub Pages sirve https://USUARIO.github.io/REPO/
```

La página llega sin datos adentro y busca `datos.json` al lado (mismo origen, sin
CORS). Se lee en streaming para mostrar barra de progreso.

**Hay dos crones, no uno.** `actualizar.yml` corre de noche y baja los 3 años de
historial. `intradia.yml` corre **una vez por hora mientras Nueva York opera** y
adentro se refresca cada 10 minutos durante 5 h 30,
agarra el `datos.json` que ya está publicado, le pide a Yahoo sólo el último mes
de cada símbolo y le pega las barras nuevas encima (`actualizar_rapido.py`). Por
eso, cuando abrís el link, lo publicado tiene menos de una hora sin que el
navegador tenga que hablar con nadie.

La página *además* intenta pedirle la rueda del día a Yahoo por su cuenta, pero
eso es un extra: **Yahoo no manda CORS y el navegador lo bloquea con un "Failed
to fetch"** (verificado con el usuario, 13/8/2026). Cuando falla no pasa nada
grave y **no se muestra ninguna alarma**, porque lo publicado ya está fresco.

### B. Servidor local (`servidor.py`)

Para cuando se quieren precios del momento sin esperar al cron. Levanta un HTTP
en `127.0.0.1:8765`, sirve `plantilla.html` y expone tres endpoints:

- `GET /api/estado` — progreso de la descarga, para la barra
- `GET /api/datos` — el payload, pre-comprimido en memoria y en disco
- `POST /api/actualizar?periodo=&fund=&completo=` — dispara la descarga

**Para qué sigue existiendo, ahora que la página le pide precios a Yahoo sola:**
porque este camino no depende de CORS. El navegador sólo puede leer la respuesta
de Yahoo si Yahoo manda la cabecera que lo permite, y eso Yahoo lo cambia cuando
quiere; `servidor.py` baja los precios desde Python, fuera del navegador, así que
anda siempre. Es la red de seguridad del modo A, no un reemplazo.

### C. Archivo suelto (`screener.html`)

`generar_html.py` mete los datos dentro del HTML. Doble clic, funciona sin Python
y sin internet. Sirve para llevárselo a otra máquina. Pesa ~12 MB.

**La página detecta sola en cuál de los tres está**, en la función `arrancar()`:
prueba `api/estado` (servidor), después `datos.json` (sitio), y si no, usa los
datos incrustados.

---

## 3. Los archivos

### Python

| Archivo | Rol |
|---|---|
| `screener.py` | **La librería.** Indicadores, descarga con reintentos, detección de atrasos, cuarentena, mapeo de CEDEARs, caché en disco. Todo lo demás importa de acá. |
| `generar_html.py` | Arma el payload (`armar_payload`) y escribe el archivo suelto. |
| `generar_sitio.py` | Escribe `sitio/` (página + datos separados) para publicar. |
| `servidor.py` | Servidor local con progreso, cuarentena y actualización a pedido. |
| `verificar.py` | Imprime OHLC e indicadores de UN símbolo, para comparar a ojo contra TradingView. |
| `diagnostico.py` | Lee un `datos.json` y reporta qué símbolos vienen con precios atrasados. |
| `actualizar_rapido.py` | **La actualización intradía.** Toma el `datos.json` publicado, pide sólo el último mes y fusiona. Barato: es lo que corre cada 10 minutos. |
| `bonos.py` | **La renta fija argentina.** Precios de los soberanos, los dos dólares implícitos, el canje de leyes, TIR/TNA/paridad/duration/DV01 sobre el cronograma, y las obligaciones negociables. Ver la sección 7b. |
| `futuros.py` | **Los futuros de dólar** (A3/Matba Rofex). Deduce el vencimiento del símbolo, descarta los vencidos y despeja el spot. Ver la sección 7b. |
| `armar_universo.py` | Compara `cedears.csv` contra el panel vivo de BYMA y reporta las diferencias. Sólo reporta, no escribe. |
| `cloudflare-worker.js` | Proxy de una línea, opcional. Sólo hace falta si Yahoo deja de mandar CORS. |

### Datos y configuración

| Archivo | Contenido |
|---|---|
| `universo.csv` | `ticker,grupo[,subyacente]` — 465 símbolos. |
| `cedears.csv` | `local,subyacente` — 400 mapeos del panel oficial de BYMA del 12/6/2026. |
| `bonos_cronograma.csv` | `bono,fecha,cupon_anual,amortiza,verificado` — los once soberanos del canje 2020, completos desde la emisión. **La cabecera documenta de dónde sale cada dato y cómo se verificó**; leerla antes de tocar una línea. |
| `plantilla.html` | **Todo el frontend**: motor de indicadores en JS, interfaz, gráfico, panorama, renta fija. |
| `requirements.txt` | pandas, numpy, yfinance. El servidor usa sólo la stdlib. |
| `.github/workflows/actualizar.yml` | El cron nocturno: historial completo. |
| `.github/workflows/intradia.yml` | Durante la rueda: los precios del día **y los bonos**, en la misma corrida. |
| `.github/workflows/bonos.yml` | A mano. Corre `pruebas/renta_fija.py` y después arma el payload con datos de verdad y lo imprime entero. Es lo que hay que mirar cuando se toca `bonos.py` o el cronograma. |
| `pruebas/` | La batería completa. `cd pruebas && ./correr.sh`. |

### Generados (no se commitean, están en `.gitignore`)

`cache_precios.pkl`, `cache_datos.json.gz`, `cache_fundamentales.json`,
`sin_datos.json`, `sitio/`, `screener.html`, `pruebas/tmp/`, `estado/ons.json`.

---

## 4. El ASH: lo más importante del proyecto

El indicador es una traducción **línea por línea** del Pine v4 *"Absolute Strength
Histogram v2 | jh"* (original de alexgrover). El usuario lo usa en TradingView y
espera que los números coincidan.

Está implementado **dos veces**: en `screener.py` (`calc_ash`) y en el JS de
`plantilla.html` (`calcAsh`). **Las dos implementaciones están verificadas entre
sí**: `pruebas/paridad.py` compara las 18 combinaciones modo × media más RSI,
ATR, ADX y ADR% sobre las mismas series. Error máximo medido: **6,7e-14**.

> Si tocás una, tocá la otra y volvé a correr `pruebas/paridad.py`. Es el
> invariante más importante del proyecto.

**Cómo se mide el error, que no es obvio:** el histograma es una resta de dos
números casi iguales, así que donde cruza el cero el error *relativo punto a
punto* explota aunque el absoluto sea 1e-16. Por eso la comparación se hace
contra la **escala** de cada serie, no punto a punto. Si alguna vez ves un
"desvío" de 1e-11 en el `hist` y de 1e-16 en `bulls` y `bears`, es esto y no un
error de traducción.

### Configuración que usa el usuario

```
Period of Evaluation: 16    Period of Smoothing: 4
Indicator Method: RSI       MV: EMA
ALMA offset 0.85, sigma 6
```

### Tres detalles del Pine original que se respetaron a propósito

1. **El modo STOCHASTIC usa el cierre**, no el máximo y el mínimo de la barra. En
   el Pine es `lowest(Price1, Length)` donde `Price1 = sma(src,1)` = el cierre.
   Parece un bug del original, pero se replica para que coincida con el gráfico.
2. **La SMMA del Pine no es recursiva.** Usa `w[1]` (la WMA anterior), no se
   referencia a sí misma. No la "arregles" a la SMMA de Wilder.
3. **`Price1 = sma(src,1)` es el source a secas.** La media de período 1 no hace
   nada; está por la estructura del código original.

### La única diferencia deliberada

El Pine platea `abs(SmthBulls - SmthBears)` y le pone el signo por color. En una
columna eso no sirve, así que se guarda la **diferencia con signo**:

```
ash_d = SmthBulls - SmthBears     > 0 = verde por encima de roja
```

### Columnas derivadas

- `ash_d_norm` = `(bulls - bears) / (bulls + bears)`, acotado a [-1, 1]. **Existe
  porque el ASH crudo está en unidades de precio**: un papel de USD 500 muestra
  números más grandes que uno de USD 20 aunque la fuerza sea igual. Para filtrar
  por signo se usa el crudo; para *ordenar el universo*, el normalizado.
- `ash_tend` / `ash_w_tend` — cuatro estados en un número ordenable:
  `2` alcista y separándose, `1` alcista pero cerrándose, `-1` bajista cediendo,
  `-2` bajista y separándose.
- `ash_d_cruce` — barras desde el último cambio de signo.

### El semanal

Se arma resampleando las diarias a `W-FRI`, con la semana en curso como barra
parcial (igual que TradingView). Necesita `length + smooth + 8` barras semanales
o devuelve NaN — **eso es correcto, no lo rellenes con un valor inventado**.
`ash_w_crece` arranca en `false` y no en `undefined`: si queda sin definir, el
filtro "ASH semanal creciendo" deja pasar a los que ni siquiera tienen semanal.

---

## 4b. Paragon: las medias que reemplazaron a las EMAs 20/50

Reconstrucción por ingeniería inversa de los dos indicadores privados de DocXBT
(The Paragon Group). **Los dos son el mismo par 100/200**; lo único que cambia
es el timeframe de anclaje. No es un error de tipeo:

- **Conjunto W** — "Paragon Weekly": EMA 100/200 ancladas a **1D**
- **Conjunto D** — "Paragon Daily": EMA 100/200 ancladas a **4h**
- **rVWAP 365d** — línea suelta, VWAP rolling sobre 365 velas diarias

### La EMA es la de Pine, y NO es la que usa el ASH

`ema_pine()` / `emaPine()`: semilla = **SMA de los primeros L**, `NaN` durante
las L−1 primeras velas, y de ahí la recursión. **No** es `ewm(adjust=True)` ni
`ewm(adjust=False)`.

> **No unifiques las dos EMAs.** La `ema()` de más arriba siembra con el primer
> precio, y eso es exactamente lo que sostiene la paridad de 6,7e-14 del ASH.
> Son dos medias distintas a propósito. `pruebas/paragon.py` verifica que
> `ema_pine` difiera de las dos variantes de `ewm`.

### Conversión de longitudes: multiplicativa, no lineal

Lo que se conserva es la tasa de decaimiento por unidad de tiempo calendario:

```
a_destino = 1 − (1 − a_ancla)^k          L_destino = 2/a_destino − 1
```

Con **k=6** (cripto) da **17 y 33**, que son exactamente los números que
documenta el Pine original. Ésa es la comprobación de que la fórmula está bien,
y está en `pruebas/paragon.py`. Con **k=2** (una rueda de 6,5 h son dos velas de
4 h) el par 100/200 de 4h equivale a **50/100** en diario.

### El warmup sale del ANCLA, no de la longitud convertida

La longitud convertida gobierna la *forma* de la curva; cuándo puede existir lo
gobierna el ancla. Para imprimir hacen falta `largo` velas del ancla, o sea
`ceil(largo/k)` de la serie.

> Con k=6 la EMA 200 de 4h necesita 200/6 = 33,33 días, así que **la primera
> vela diaria que las completa es la 34** — no la 33, que es donde imprimiría
> una EMA(33) suelta. Ese uno de diferencia es el dato que identifica al
> indicador de Doc, y es lo que pidió verificar el usuario. Está en
> `pruebas/paragon.py`.

### Qué es exacto y qué es aproximado

| | Ancla | Estado |
|---|---|---|
| Conjunto W | 1D | **Exacto**: el proyecto ya baja velas diarias |
| Conjunto D | 4h | **Aproximado**: no hay velas de 4h en el pipeline |

`interval="1d"` está fijo en `_descargar()`, y Yahoo ni siquiera tiene intervalo
de 4h (el máximo es `1h`, sólo 730 días). El conjunto D usa la conversión
multiplicativa con `k` configurable y **cada fila queda marcada con `≈`**.

> **`k` no está medido, está asumido.** El usuario pidió medir empíricamente la
> mediana de velas intradiarias por sesión y no hardcodear nada. Desde el
> entorno de desarrollo no hay salida a Yahoo, así que k=2 es una deducción
> (rueda de 6,5 h → dos velas de 4 h), no una medición. Si algún día se agrega
> data intradiaria, medilo y ajustá el default.

### rVWAP: ventana expansiva

`rvwap[t] = Σ(precio·volumen) / Σ(volumen)` sobre las últimas `min(t+1, 365)`
velas. El `min()` es deliberado: hasta el día 365 es un VWAP anclado al inicio
del historial y de ahí pasa a ser la ventana móvil, **sin salto**. Las filas con
la ventana incompleta se marcan con `*`. Fuente `hl2` por defecto (la del Pine
del usuario), configurable a `hlc3` o `close`.

### Columnas derivadas

Por conjunto: sesgo, posición del precio (arriba/adentro/abajo), ancho, distancia
al borde más cercano en % y en ATR(14), velas desde el cruce, y cruce fresco.
Más `vs_rvwap`, `rv_llena` y **`regimen`** — los dos sesgos cruzados en cuatro
estados (`D+ W+`, `D− W+`, `D+ W−`, `D− W−`), que es la columna con la que se
filtra el universo. Se ordena por `regimen_ord` (0 a 3), no alfabéticamente:
para eso `COLS` acepta ahora un campo `ord` con el nombre del campo alternativo.

Los que no llegan al warmup **no se descartan en silencio**: van con `NaN` y con
`sin_historial`, que se puede filtrar desde el panel.

## 4c. Consolidación: la caja

Encontrar lo que se mueve en un mismo rango. Lo pidió el usuario con una captura,
y después lo hizo afinar señalando **PLTR**, que es el caso que rompió la primera
versión.

### El largo de la caja se BUSCA, no se asume

**Ésta es la parte que estaba mal.** La primera versión usaba una ventana fija de
20 ruedas. Sobre PLTR al 26/08/2026 esa ventana llegaba hasta el 30/07 —*antes*
del salto del 04/08 (+29,45%)— así que medía una caja de **35,4% de alto** y no
detectaba nada. El rango de verdad eran **13 ruedas desde el 10/08, con 7,9%**.

Ahora se prueban todos los largos y gana **el que minimiza la estrechez**.
Funciona porque la curva tiene un mínimo nítido justo donde arranca el rango: en
PLTR baja parejo hasta L=13 (0,55) y salta a 0,79 en L=14, que es la barra
anterior al rango. La caja termina donde agregar una barra más empieza a doler.

`_mejor_caja()` / `mejorCaja()` es O(maxL): techo y piso corridos, y el ADR de
una suma acumulada. No recalcula la media en cada vuelta.

### El alto se mide contra el ADR del propio papel

Un rango "chico" no significa nada en abstracto: 6% en un mes es quieto para un
papel que se mueve 3% por día y es un temblor para uno de 0,4%. Si el precio
fuera una caminata al azar con paso diario igual a su ADR, en L ruedas recorrería
del orden de `ADR·√L`:

```
estrechez = alto_de_la_caja / (ADR · √L)
```

Menor que 1 = se movió **menos de lo que le corresponde por su propia
volatilidad**. Comparable entre AAPL y una minera chica.

### Los estados

| Estado | Cuándo |
|---|---|
| `Rompió ↑` / `Rompió ↓` | la caja de ayer era buena y hoy el cierre quedó afuera |
| `Cajón` | `estrechez ≤ 0,62`, `L ≥ 10` |
| `Se aprieta` | `contracción < 0,40` y `estrechez ≤ 0,72` |
| `Rango` | `estrechez ≤ 0,72` |

Todos exigen además `alto ≤ tope` (18% por defecto, editable).

**En las rupturas se reporta la caja de la que SALIÓ**, no la de hoy: la de hoy ya
incluye la barra de la ruptura, así que sale más alta y no es la que el ojo (ni
el gráfico) llama "el rango que rompió". La posición pasa de 100%.

**La contracción se mide contra lo que vino ANTES de la caja**, no contra su
propia mitad. Ahora que el largo se elige minimizando la estrechez, la caja es
uniforme por construcción y comparar sus mitades daba 1,00 siempre.

### Los umbrales están calibrados contra datos reales

No son inventados: se midieron sobre los **447 papeles del `datos.json`
publicado**. Con los cortes de la primera versión (pensados para ventana fija),
`Rango` marcaba al **54% del universo** — media tabla en verde no sirve de filtro.
Y `Se aprieta` con corte 0,60 marcaba 17%, más que `Rango`, que es al revés de lo
que sirve.

Hoy: sin caja 75,6% · Rango 11,4% · Cajón 6,9% · Se aprieta 3,4% · rupturas 2,7%.

> **El tope de alto hace falta.** BIOX daba estrechez 0,57 con una caja del 44%
> en 59 ruedas. Relativo a SU volatilidad es quieto, pero una caja del 44% no es
> un rango para nadie.

> **Si volvés a tocar los umbrales, medí primero.** `pruebas/` no tiene internet,
> pero el `datos.json` publicado se baja de `raw.githubusercontent.com` y tiene
> 400 barras reales de cada papel. Calibrar a ojo sobre series sintéticas fue
> justamente lo que dejó los cortes mal la primera vez.

### El caso PLTR es un test fijo

`pruebas/pltr.json` tiene las 70 barras reales, guardadas del sitio publicado
(sin internet no se pueden volver a bajar). `pruebas/consolidacion.py` verifica la
secuencia completa: **Se aprieta** del 18 al 24/08 (contracción 0,22 contra el
tramo explosivo), **Cajón** el 25 y 26, **Rompió ↑** el 27, y la caja anclada al
**10/08** en todos los cortes.

La caja se dibuja en el gráfico: rectángulo desde donde arrancó, techo y piso
punteados, color según el estado, y `estado · alto% · ruedas` en la esquina.

> **Bug que ya se cometió una vez:** en el JS, `adrPct()` devuelve la **serie**,
> no el último valor. Escribir `adrPct(b,n)/100` da `NaN` siempre y la caja no se
> marca nunca — una función muerta que parece andar. Va `ultimo(adrPct(...))`.
> Lo agarró `pruebas/paridad.py`.

## 5. CEDEARs: la regla que no se negocia

**Nunca se descarga el precio del CEDEAR.** El precio en pesos mezcla el
movimiento del papel con el tipo de cambio implícito, y eso contamina el ASH, el
RSI y el ADR con movimientos de FX que no tienen nada que ver con el activo.

El flujo: en `universo.csv` se escribe el código BYMA con `.BA`, y
`cargar_mapa_cedears()` lo resuelve al subyacente usando `cedears.csv`.

```
AAPL.BA  -> AAPL        DISN.BA -> DIS         BA.C.BA -> BAC
TEN.BA   -> TS          UN.BA   -> NU          ADGO.BA -> AGRO
BRKB.BA  -> BRK-B       TXR.BA  -> TX          BAS.BA  -> BAS.DE
```

Ojo con los que no son obvios: en BYMA `BA` es **Boeing** y `BA.C` es **Bank of
America**. `TEN` es Tenaris (cotiza como TS). `UN` es Nu Holdings. `ADGO` es
Adecoagro (en NYSE: AGRO).

**Si un `.BA` no está mapeado, se saltea y se avisa.** Bajar el CEDEAR daría
indicadores equivocados, que es peor que no tenerlos. No cambies eso por un
fallback.

**Una línea rota de `cedears.csv` se saltea, no rompe el archivo entero.** Antes
una línea sin subyacente arrastraba la clave de la línea anterior y la mapeaba a
un valor vacío (o directamente reventaba con `IndexError`).

La tabla muestra `Ticker` (lo que se analizó) y `CEDEAR` (lo que se compra).
Hay además una columna `Mon` con la moneda del subyacente: hoy 446 en USD, 9 en
BRL, 7 en EUR, 1 JPY, 1 TWD. **Cero en pesos argentinos, y así debe quedar.**

---

## 6. Rendimiento: cómo está optimizado y por qué

Con 465 símbolos × 400 barras, el recálculo completo son **3-35 ms** medidos con
jsdom (más en un navegador real con pintura, pero el orden es ése). Está partido
en tres capas para que mover un parámetro no rehaga todo:

1. **`cacheBase`** — RSI, ADR, ATR, ADX, nubes Paragon, rVWAP, volúmenes,
   performances, máximos de 52 semanas. Se invalida sólo si cambian esos
   períodos o los parámetros de Paragon.
2. **`cacheSem`** — las barras semanales resampleadas. Nunca se invalida.
3. **`memoAsh`** — un Map por configuración de ASH, guarda las últimas 4. Volver
   de 9/4 a 16/4 tarda **3 ms** en vez de recalcular todo.

**Los filtros no recalculan nada**: filtran sobre lo ya calculado. El orden
tampoco. Sólo `recalcular()` toca el motor; `aplicar()` filtra y `render()` pinta.

> **Bug ya corregido, no lo reintroduzcas:** el debounce de los controles es un
> único temporizador compartido. Antes, tocar el ASH y enseguida un filtro
> cancelaba el recálculo y la tabla se quedaba con el ASH viejo hasta el próximo
> cambio. Ahora hay una bandera `pendientePesado` que sobrevive al `clearTimeout`.

Otras decisiones de peso:

- El sitio se genera con **400 barras**, no 600. Alcanzan para la EMA 200 del
  conjunto B (200), el
  máximo de 52 semanas (252) y ~80 semanas de ASH. Un tercio menos de peso.
- **Página y datos separados** en el sitio publicado: el navegador cachea el HTML
  aparte y las visitas siguientes sólo bajan los precios.
- El payload del servidor se guarda **pre-comprimido** en `cache_datos.json.gz`
  (2,8 MB contra 8,2 MB en crudo). Antes se recomprimía en cada pedido.
- Si el gráfico está oculto, `dibujar()` sale en la primera línea sin calcular.

---

## 7. La interfaz

### Vista Panorama (tarjetas)

Tarjetas con mini-gráfico de velas para mirar el mercado **de arriba hacia
abajo**: primero los índices, después los sectores, y recién después un papel.
Ese es el orden en que se decide y la tabla sola no lo mostraba. Se abre con el
chip `Panorama` o con la tecla `P`.

Seis paneles: Índices · Sectores · Temáticos · Commodities · Mundo · Favoritos.
**Las listas son fijas** (`PANELES`), no se deducen del sector que informa
Yahoo: a un ETF de semiconductores lo clasifica como *Technology*, igual que a
Apple.

Cada tarjeta trae precio, variación con signo, mini-velas de 60 ruedas, **RS**,
el estado del **ASH diario y semanal** (▲/▼), la figura si la hay, el volumen en
dólares y la etiqueta `PRE`/`AH` cuando hay precio fuera de hora.

**El mini-gráfico está en porcentaje, no en precio.** La línea punteada es el
cierre previo (el 0%) y a la derecha van tres números: el techo del rango, el 0%
y el piso. Sin eso no se sabe si la forma que se ve es un movimiento de 0,3% o
de 12%, que es la diferencia entre mirar y no mirar. La variación del día va en
una etiqueta pegada a la última vela, que es el número que se busca primero.

Arriba: encabezado con el título grande, el **estado del mercado** (Abierto /
Pre-market / After-hours / Cerrado, calculado con la hora de Nueva York y no la
del navegador), cuándo se actualizó, un buscador que —a diferencia del panel—
busca en **todo el universo**, y la barra de amplitud con cuántos suben, cuántos
bajan y las puntas.

### Pre-market y after-hours

**De dónde salen:** del mismo endpoint de gráficos de Yahoo, pero con intervalo
intradía (5m) y `includePrePost=1`. yfinance lo expone como `prepost=True`.

**Cómo se separan las sesiones:** Yahoo no marca cada barra, así que se mira la
hora local del mercado — antes de 9:30 es pre, de 16:00 en adelante es after.
yfinance devuelve el índice en la zona del mercado, así que no hay que adivinar
husos.

**Contra qué se compara:** el pre-market contra el cierre del día **anterior**,
el after-hours contra el cierre de **hoy**. Cualquier otra referencia da
porcentajes que no significan nada.

**Sólo para Estados Unidos.** La ventana 9:30-16:00 es la de Nueva York;
aplicársela a Tokio o a São Paulo da cualquier cosa. En la primera corrida real
los dos únicos «pre-market» que salieron fueron `6701.T` y `2317.TW`, justamente
por eso. `bajar_extendido` saltea todo lo que tenga sufijo de mercado.

**Lo que no se puede prometer:** fuera de horario el volumen es una fracción del
de la rueda. Por eso viaja también `exv` (volumen extendido): sirve para saber
cuánto creerle. En un papel líquido el dato es útil; en uno que no lo es, una
sola operación suelta mueve el precio 4%.

`intradia.yml` pide un disparo por hora, 8:00-23:00 UTC, para cubrir las tres
sesiones.

### Dónde vive cada control (cambió, y por un motivo)

Hay tres alturas y no se mezclan:

1. **Navegación (columna izquierda, arriba)** — Tabla · Panorama · Argentina.
   Es *dónde estoy parado*.
2. **Ajustes de la vista tabla (barra, con icono)** — **Filtros**,
   **Indicadores**, **Columnas**. Se abren como desplegables desde la barra,
   que es donde se los busca mientras se mira la tabla.
3. **Ajustes de la página (columna izquierda, al pie, tras el ⚙)** — tamaño de
   letra, alto de fila, de dónde bajan los datos, respaldo, CSV. No es de
   ninguna vista: es de la página.

**Los filtros y los indicadores salieron de la columna izquierda.** Estaban
siempre abiertos ocupando media pantalla, y mezclados con "Datos" y "Respaldo",
que son cosas de otro rango.

**El chip de Sectores/Industrias se fue de la barra.** El *ranking* ya está en
Panorama y repetirlo era ruido; lo que sí servía —elegir un sector para
filtrar— se mudó adentro del panel de Filtros, que es donde vive un filtro.

**El grupo entero se esconde fuera de la tabla.** Los filtros son de la renta
variable: en Panorama no hay tabla que filtrar y en la curva de bonos un "RSI
mayor que" no quiere decir nada. Dejarlos a la vista invita a tocarlos y después
a no entender por qué no pasa nada. Cambiar de vista además los cierra.

**La barra dice cuántos filtros hay puestos.** Con los filtros detrás de un
icono, ese número es lo único que avisa que la tabla **no** está mostrando todo.

> **Trampa que costó once pruebas y hay que no repetir:** el cableado de los
> controles decía `$$('aside input, aside select')`, o sea que dependía de
> **dónde** estaba cada control en el HTML. Al mudarlos a los desplegables,
> **todos quedaron desconectados en silencio** — no guardaban la sesión ni
> disparaban el recálculo — y la página seguía cargando igual, con la tabla
> perfecta. Ahora es `.ctrl-host input, .ctrl-host select`: **si agregás un
> contenedor con controles, ponele la clase `ctrl-host`.** `pruebas/menus.js`
> verifica que ninguno quede huérfano.

### Barra superior
Pastilla de **frescura** · desplegable de filtros guardados · tres cápsulas de
chips · nada más.

**La firma dice sólo la fecha de cierre** (más el aviso rojo si el archivo
quedó viejo de verdad). Antes repetía la configuración del ASH y la cantidad de
símbolos: la configuración ya está en el panel de Indicadores, que es donde se
la toca, y la cantidad está en los KPIs. Repetirlas arriba de todo era ruido
permanente en la línea que más se mira. **No las devuelvas.** La prueba del
debounce comparaba el texto de la firma para saber si había recalculado; ahora
compara el contenido de la tabla, que es lo que de verdad importa.

La pastilla es lo primero que se mira y por eso está antes que todo lo demás:
**verde** = se actualizó hace menos de 75 minutos, **ámbar** = es el cierre de la
última rueda (lo correcto con el mercado cerrado), **rojo** = el archivo quedó
viejo de verdad, dos ruedas o más.

**Los chips van en tres cápsulas, no en una, y cada una tiene su propio
"encendido".** Es la corrección de un error de lectura real: con los cinco chips
juntos y el mismo resaltado, `Panorama` y `★ favoritos` prendidos a la vez se
veían como dos opciones elegidas del mismo control, que no existe.

| Cápsula | Qué es | Cómo se ve el `.on` |
|---|---|---|
| `.seg` — `Tabla` / `Panorama` | una elección entre dos, **siempre hay exactamente una encendida** | hundida, con sombra |
| `.inter` — `★ favoritos`, `Gráfico` | interruptores que van y vienen | ámbar |
| `.menus` — `Sectores ▾`, `Columnas ▾` | abren un desplegable | apenas aclarada |

`verPanorama()` prende una y apaga la otra en la misma línea; no hay forma de
que las dos queden encendidas. `pruebas/panorama.js` lo verifica prendiendo
favoritos **y** Panorama a la vez, que es el caso de la captura del usuario.

### Pantallas angostas

El screener se abre desde un link, así que tarde o temprano se abre desde el
teléfono. Abajo de 860 px el panel deja de robarle ancho a la tabla y pasa a ser
un **cajón** que se abre encima, con un velo detrás que lo cierra al tocarlo. El
estado plegado del escritorio no abre el cajón solo al entrar desde el teléfono.
`matchMedia` está guardado con un `innerWidth` de respaldo porque jsdom no lo
trae y reventaba las pruebas.

### KPIs
En el universo · Pasan el filtro · ASH diario + · ASH semanal + · Los dos + ·
Cruce ≤ 5 ruedas · **⚠ Precio atrasado** (se puede tocar: esconde y muestra los
desactualizados).

### Barra de búsqueda
Buscar (ticker, nombre o código CEDEAR) · `Copiar tickers` · `Guardar estos
filtros` · `Copiar vista`.

### Panel izquierdo (ocultable con `[`)
ASH · Otros indicadores · Filtros · Grupos · Filtros guardados · Respaldo de la
configuración · Datos.

### Persistencia — hay cuatro niveles, y esto importa

1. **`localStorage`** — sesión, favoritos, perfiles, estado del panel y del
   gráfico. Se guarda con debounce de 400 ms y **se fuerza el guardado en
   `pagehide` y en `visibilitychange`**, porque si no el último cambio se perdía
   al cerrar la pestaña.
2. **URL con hash** (`#v=base64`) — el botón **Copiar vista** serializa todo el
   estado en la dirección. **Existe porque el usuario tuvo el caso de que el
   navegador le borraba los datos al cerrar.** Sobrevive a incógnito, a borrados
   y a cambio de máquina. Al arrancar, **la URL tiene prioridad** sobre la sesión,
   pero **se consume**: se aplica, se graba como sesión propia y el hash se
   limpia con `replaceState`. El enlace copiado no se toca.
3. **Respaldo `.json`** — exporta e importa perfiles + favoritos + sesión. Al
   importar se **fusiona**, no se pisa: restaurar no te borra lo que ya tenías.
4. **Detección de almacenamiento bloqueado** — `hayAlmacen` prueba escribir; si
   falla, se usa un objeto en memoria y se avisa en el panel.

> **Bug ya corregido, y es el que más confundió:** `copiarVista()` escribía el
> `#v=` **en la barra del que apretaba el botón**, no sólo en el enlace copiado.
> Ese hash quedaba pegado, y como la URL le gana a la sesión al arrancar, desde
> esa apretada en adelante *cada recarga restauraba esa foto vieja*. El usuario
> apagaba columnas, se guardaban bien en `localStorage`, y al volver estaban
> prendidas otra vez: se leía como "falla el guardado" cuando en realidad se
> guardaba y se pisaba.
>
> Dos mitades del arreglo, y hacen falta las dos:
> 1. El `#v=` se planta en tu barra **sólo si el portapapeles falló** — el único
>    caso donde sirve, para copiarlo a mano.
> 2. Una vista que llega por URL se usa **una vez**: se aplica, se graba como
>    sesión y se limpia el hash. Sin esto, el que abre un enlace compartido
>    queda con el mismo problema.
>
> `pruebas/columnas.js` cubre las dos mitades, incluido el caso del portapapeles
> roto. Si alguna vez volvés a escribir el hash siempre, esto reaparece.

> **Trampa conocida:** `localStorage` no está disponible en orígenes opacos
> (`file://` en algunos navegadores). Una vez esto rompió la página entera al
> arrancar. Todo acceso pasa por `leerLS`/`escribirLS`, que atrapan la excepción.
> No uses `localStorage` directo.

**Qué se guarda y qué se guardaba mal.** El estado incluye ahora la búsqueda, la
industria seleccionada y el perfil elegido en el desplegable, además de los
filtros, los grupos, las columnas y el orden. Los chips de
grupos **no llamaban a `guardarSesion()`**: los elegías, recargabas y volvía todo
al default. Era la queja más concreta sobre "la memoria".

### Estado neutro
`NEUTRO` + `NEUTRO_CHECK` son **la única** definición de "sin filtros". La usan el
botón de limpiar, la opción `— sin filtros —` del desplegable y los presets. Antes
la lista estaba duplicada dentro del botón y se olvidaba de los controles nuevos.

### No hay filtros predeterminados

Había diecisiete armados de fábrica en una constante `PRESETS` y **el usuario los
mandó sacar** (4/9/2026). El desplegable lleva ahora `Sin filtros` (valor `'0'`,
que limpia todo) y los perfiles que uno se guarda, nada más. Si alguna vez hace
falta una lista fija, se guarda como perfil y se exporta con el respaldo `.json`,
que es el mecanismo que ya existe para eso — **no vuelvas a meter una constante
de presets**.

Dos detalles de la pantalla vacía, que es el caso nuevo: sin ningún perfil
guardado el desplegable tendría **una sola opción**, y eso se lee como roto. Por
eso la raya que separa `Sin filtros` del resto sólo se dibuja **si hay resto**
(`nodo.nextElementSibling`), y la lista se marca con `sin-perfiles`, que pinta un
`::after` explicando cómo se llena.

> Ese cartel es **contenido generado por CSS**, así que jsdom no puede verlo
> nunca: no aplica hojas de estilo. En `interfaz.js` se verifica la *clase*; el
> *texto* se verifica en `vista.js`, preguntándole al navegador. Es el mismo
> reparto que el de `[hidden]`.

Las pruebas usaban los presets como vehículo para verificar otras cosas (que
elegir del desplegable no te cambie las columnas, que te saque de Panorama y de
Bonos, que encienda el selector). Todas siguen, pero **se guardan su propio
perfil** en vez de apoyarse en uno de fábrica.

**Elegir cualquier cosa del desplegable sale solo de Panorama.** Antes, estando
en las tarjetas, apretabas `Sin filtros` y no pasaba nada visible: el resultado
se ve en la tabla y había que apretar `Tabla` a mano para verlo. Ahora
`elegirPerfil()` y `limpiarFiltros()` llaman a `salirDePanorama()`, y **mover
cualquier perilla del panel de filtros hace lo mismo** — el listener compara
contra `ES_FILTRO`, que sale de `NEUTRO` + `NEUTRO_CHECK` para no tener dos
definiciones de "qué es un filtro". Las perillas del **ASH** no salen de
Panorama a propósito: ésas sí cambian las tarjetas, porque el verde de cada
sector se calcula con el ASH.

### El filtro del cruce: cuatro lecturas

`fCruceDir` × `fCruceMax` reemplazan al viejo "cruce alcista ≤ N ruedas", que
era **una sola** de las cuatro combinaciones posibles y no dejaba pedir lo
contrario: los papeles que llevan rato en rojo, que es donde se buscan los pisos.

```
'1'   alcista, hace poco   ash_d > 0  y  ash_d_cruce <= N
'1+'  alcista, hace rato   ash_d > 0  y  ash_d_cruce >= N
'0'   bajista, hace poco   ash_d < 0  y  ash_d_cruce <= N
'0+'  bajista, hace rato   ash_d < 0  y  ash_d_cruce >= N
```

Vive en `pasaCruce()`, dentro del motor y exportada para las pruebas. Dos
detalles que no son obvios:

- **`N = 0` sigue queriendo decir "sin filtro"**, como todas las perillas. Por
  eso `fCruceDir` arranca en `'1'` y los perfiles viejos, que sólo guardaban
  `fCruceMax`, siguen leyéndose igual que antes.
- **La dirección viaja en `null` cuando `N` es cero.** Si viajara siempre con
  valor, la cuenta de "filtros puestos" nunca bajaría a cero y la pastilla nunca
  diría `sin filtros`. Ya rompió una prueba de la interfaz.

La etiqueta dice la lectura entera (`≤ 8 ruedas` / `≥ 8 ruedas`): el número solo
no distingue los dos sentidos.

### Columnas

**La columna CEDEAR sólo se muestra cuando difiere del ticker.** En 347 de 448
papeles el código BYMA es idéntico (MU/MU, AMAT/AMAT), así que repetirlo era una
columna entera de ruido. Los 36 que sí difieren son justo los que hay que mirar
(DISN→DIS, BA.C→BAC, BRKB→BRK-B, AOCA→ACH). Los demás muestran un `·`.

**Se fijan dos columnas al desplazar, no una.** Con sólo la estrella fija, al
correr la tabla a la derecha se perdía el ticker y no se sabía de qué fila era
cada número. La estrella mide 30 px y el ticker se ancla ahí.

Sector, industria y nombre llevan `corto:1`: se cortan con puntos suspensivos y
el texto entero queda en el `title`. Sin eso estiraban la tabla a lo ancho.

> **Trampa que ya mordió:** cuando se agrega una columna al set por defecto, el
> que ya tenía una selección guardada **nunca la ve**, porque su lista pisa la
> nueva. Pasó de verdad: se agregaron las tres columnas de líneas de tendencia y
> en pantalla seguían apareciendo las 16 de antes, así que la función entera era
> invisible. Ahora la sesión guarda en `_colsVistas` qué columnas existían al
> guardarla, y `fusionarColumnas()` agrega las de `def:1` que no estaban
> entonces; lo que el usuario apagó a propósito queda apagado, porque eso sí lo
> conocía. `COLS_AGREGADAS` cubre las sesiones viejas que no traen la lista.
>
> **Y ahora se avisa.** Que aparezcan columnas nuevas sin explicación se lee
> como "se me borró la configuración", que es justo lo contrario de lo que pasó.
> `fusionarColumnas()` deja en `colsNuevas` las que agregó y el desplegable
> `Columnas ▾` lo dice arriba de todo; el aviso se va apenas tocás cualquier
> columna. Sólo pasa en el deploy donde se agrega la columna, no en cada uno.

**El orden lo elige el usuario** (`ordenCols`, una lista de claves). Se reordena
de dos formas: **arrastrando el encabezado en la tabla misma**, o desde la lista
del desplegable `Columnas ▾`.

> **Trampa del encabezado:** un `th` hace dos cosas — al hacer clic ordena, al
> arrastrar mueve la columna. Para que soltar el arrastre no dispare también el
> ordenamiento se usa una **marca de tiempo** (`ultimoArrastre`) y **no una
> bandera**: con una bandera, si el navegador no manda el `dragend` (pasa al
> cancelar con Escape o al soltar afuera) quedaba trabada en `true` y el
> encabezado no ordenaba nunca más. Una marca de tiempo se cura sola.

Las columnas de EMAs se expanden en la tabla (`vs_ema20`, `vs_ema50`) pero en el
orden viajan como una sola entrada (`__emas`); `claveReal()` hace la traducción.
 Lo que no
esté en la lista se agrega al final en el orden de `COLS`, así una columna nueva
aparece igual sin tener que tocar nada. Se reordena arrastrando o con las
flechas ↑↓ del desplegable `Columnas ▾` — **las flechas no son un adorno**: el
arrastre no anda con el dedo en el teléfono ni con el teclado.

**★ y Ticker no se mueven.** Son las dos que quedan fijas al desplazar a lo
ancho y el CSS las ancla por posición (`nth-child(1)` y `(2)`); si se pudieran
correr, la tabla se rompe.

> **Bug ya corregido:** al apagar una columna se llamaba sólo a `render()`, así
> que la columna apagada seguía figurando en la lista de orden. Hay que rearmar
> el desplegable entero (`montarColumnas()`).

**El CSV baja lo que se ve, en el orden en que se ve.** Antes salían las ~60
claves internas en orden alfabético y después había que reordenar el archivo a
mano.

### Tamaño de letra y alto de fila

Dos variables en `:root` que multiplican todo: `--escala` (tipografía de la
tabla y de los KPI) y `--aire` (padding y `line-height` de las filas). Se manejan
desde *Datos → Cómo se ve* y se guardan aparte de la sesión, porque son de la
pantalla y no del filtro. La misma tabla se mira en un monitor de 27" y en un
portátil de 13".

**Nada de fuentes de internet**: el screener tiene que abrir sin conexión. La
pila arranca en `ui-monospace` / `ui-sans-serif`, que en cada sistema cae en la
mejor cara que tenga (SF Mono en Mac, Cascadia en Windows 11).

`COLS` define las columnas; las que tienen `def:1` son el set por defecto.
`nosel:1` marca las que no se pueden apagar (★ y Ticker). El desplegable las
agrupa según `GRUPOS_COL`. La selección viaja en la sesión, en la URL y dentro de
los perfiles guardados.

### Una sola convención decimal: coma

La interfaz escribe en **es-AR**, o sea con coma decimal y punto de miles. Los
números sueltos ya salían así (`bnum` usa `toLocaleString`), pero los
porcentajes salían con `toFixed`, que **siempre** pone punto. Resultado: la
misma fila mostraba `54,31` al lado de `7.76%`, y en la tabla de futuros la
columna **A3** —la única que usa `bnum`— quedaba con `17,57%` pegada a `17.94%`
de la columna de al lado. Dos convenciones decimales en columnas contiguas de
la misma tabla.

`bpc` y `bsig` pasan ahora por `bnum`, y lo mismo los **textos** del gráfico
(los rótulos de cada punto, el globito, el spread entre las dos líneas). **Las
coordenadas SVG siguen con `toFixed` y tienen que seguir así**: un `cx="1,5"`
no es un número para el navegador. Por eso la prueba mira los `<text>` y no los
atributos.

`pruebas/bonos.js` lo verifica pestaña por pestaña buscando `\.\d{1,2}%`, que
sirve de detección porque en es-AR el punto separa miles y los miles van de a
tres: `1.234%` no matchea, `7.76%` sí.

### Escapado

Los nombres, sectores e industrias vienen de Yahoo y se insertan como HTML.
Alcanza con un `&` o un `<` en la razón social para romper la fila, y una comilla
en el nombre de la industria rompía el `data-ind` del panel. **Todo texto de
Yahoo pasa por `esc()`.**

> **Trampa:** dentro de `dibujar()` hay una función `escY()` que mapea valor →
> coordenada Y. Se llamaba `esc` y **tapaba a la global `esc()`** por TDZ, lo que
> rompía el panel del detalle con un `Cannot access 'esc' before initialization`.
> No la vuelvas a llamar `esc`.

### Sectores e industrias

`agregarPorGrupo()` calcula, por industria y por sector:
- **RS** — percentil 1-99 de la mediana de rendimiento a 3 meses del grupo.
- **breadth** — qué fracción del grupo tiene el ASH diario positivo.

Sólo se rankean grupos con ≥2 miembros.

**El panel agrupa por SECTOR, no por industria** (`campoGrupo`, con un chip para
cambiar). Medido sobre los datos reales: 11 sectores contra 95 industrias, y
**31 de esas industrias tienen un solo papel**, así que ni siquiera se pueden
rankear. Sumado a que la clasificación de Yahoo es mediocre (el caso `ACH`), la
industria sirve para afinar pero no para decidir. Cambiar de campo **suelta la
selección**: si no, quedaba filtrando por «Semiconductors» con la lista de
sectores en pantalla y no se entendía por qué la tabla mostraba veinte papeles.

El buscador también matchea sector e industria, así que escribir `energy` deja
el sector entero sin abrir el desplegable.

### Líneas de tendencia (soporte y resistencia)

Es lo que dibuja Finviz. **No es una regresión sobre los cierres**: una
regresión común pasa por el medio del precio y no sirve ni de soporte ni de
resistencia. El método, en `tendencias()`:

1. **Pivotes**: un máximo es una barra cuyo `High` domina las `k` barras a cada
   lado (`tlPivote`, por defecto 5).
2. **Regresión envolvente**: se ajusta una recta sobre esos pivotes, se tiran
   los que quedaron del lado de adentro y se vuelve a ajustar. Tres vueltas.
   Así la recta queda *apoyada* sobre los extremos en vez de partirlos al medio.
3. **Toques**: cuántos pivotes caen dentro de la tolerancia. La tolerancia sale
   del **rango de la ventana** (3,5%), no de un porcentaje fijo del precio: un
   papel que se movió 5% en el trimestre y otro que se movió 80% no se pueden
   medir con la misma vara.

Los últimos `k` bares nunca pueden ser pivote, así que la recta se **extrapola**
hasta la última barra. Eso es lo correcto: la resistencia de hoy sale de los
máximos de antes.

La figura se clasifica con las dos pendientes normalizadas a **% por mes**
(21 ruedas), con un umbral de 1,5%/mes para considerar una recta plana: Canal
alcista, Canal bajista, Triángulo asc., Triángulo desc., Cuña / triángulo,
Rango, Se abre. Hace falta un mínimo de 2 toques en cada recta o no se
clasifica.

Cuesta **6-17 ms** para los 465 símbolos, y viaja en `cacheBase`: `tlBarras` y
`tlPivote` entran en `claveBase`, así que cambiarlos invalida el caché.

`pruebas/tendencias.js` verifica contra figuras **construidas a mano**, donde la
respuesta se conoce de antemano. Es la única forma seria de probar esto sin ojo
humano: con series reales no hay contra qué comparar.

> **Trampa:** `mostrarTL` no puede inicializarse con `leerLS()` en la
> declaración — `leerLS` es un `const` de más abajo y ahí está en la zona muerta
> temporal, lo que rompía la página entera al arrancar. Es el mismo error que ya
> había pasado con `esc`/`escY`. Se lee dentro de `iniciar()`.

### AVWAP anclado al último máximo fractal

Es la línea naranja del gráfico de referencia, y es la metodología de Brian
Shannon: en vez del VWAP del día, un VWAP que **arranca en un punto que
significa algo**. Anclado al último máximo contesta una pregunta concreta: *el
precio promedio que pagó todo el que compró desde ese máximo, cuánto es*. Si el
precio está por debajo, todos esos compradores están perdiendo; cuando lo
recupera, dejan de estarlo, y eso cambia la oferta.

**Cuál es «el último máximo fractal».** Un pivote de máximos cualquiera puede
ser un micro-pico sin importancia. El que sirve es el **último pivote que
todavía no fue superado**: ése es el techo con el que el precio está peleando.
Si el papel viene haciendo máximos nuevos no queda ninguno sin superar y se usa
el último pivote a secas. Si no hay ningún pivote (una recta perfecta hacia
arriba) **no se inventa un ancla**: un papel sin techo reciente no tiene este
patrón, y decirlo es más útil que dibujar una línea cualquiera.

El ancla usa la misma ventana y el mismo pivote que las líneas de tendencia
(`tlBarras`, `tlPivote`), para no multiplicar controles.

Cuatro estados: `Recuperado` (arriba y cruzó hace ≤10 ruedas), `Encima`,
`Perdido` (abajo y cruzó hace ≤10), `Debajo`. El filtro «a ≤ X% del AVWAP» toma
**los dos lados**: el patrón es el precio *volviendo* a la línea, y puede llegar
desde arriba o desde abajo.

> **Ojo con el volumen:** los precios vienen ajustados por dividendos y el
> volumen no. Sobre una ventana de tres meses la diferencia es despreciable,
> pero no uses esto sobre varios años sin pensarlo.

### El panel de filtros

> **Bug ya corregido:** `aside .interior` medía **lo mismo** que el panel, así
> que la barra de desplazamiento se montaba encima de los controles y los
> sliders quedaban cortados contra el borde. Ahora el interior es
> `calc(var(--panel-ancho) - var(--barra-sc))`, y las dos medidas salen de la
> misma variable para que no se desincronicen. No se puede usar `width:100%`
> porque al plegar el panel (`width:0`) se aplastaría todo el contenido.

Los deslizadores están dibujados a mano (riel de 4 px, perilla de 13). Los que
vienen por defecto son enormes y con `accent-color` cada navegador dibuja otra
cosa. Los filtros van agrupados con subtítulos (`.subt`): veinte controles
seguidos son una lista infinita donde no se encuentra nada.

### Gráfico

Canvas propio. Velas + las dos nubes Paragon + rVWAP arriba, ASH abajo (bulls, bears,
histograma). Crosshair con OHLC. Selector diario/semanal.

> **Bug ya corregido, no lo reintroduzcas:** la escala del panel del ASH **debe
> incluir el cero** (`a=Math.min(a,0); z=Math.max(z,0)`) y el dibujo del
> histograma va dentro de un `clip()`. Sin eso, las barras se salían del panel y
> tapaban las fechas. `pruebas/grafico.js` verifica que nada se dibuje fuera del
> canvas.

---

## 7b. Renta fija argentina: bonos soberanos y obligaciones negociables

La segunda pata del proyecto. El screener sirve para elegir acciones; esta
sección sirve para elegir bonos, que es el otro pedido concreto: *"para que la
página pueda ser utilizada por asesores para buscar las acciones o bonos que más
se adapten a sus clientes"*.

Vive en `bonos.py` (payload) + la vista `#bonos` de `plantilla.html`. Viaja en
un archivo aparte, `bonos.json`, que se baja **la primera vez que se entra a la
vista**: el que nunca mira bonos no paga la descarga.

### De dónde sale cada cosa

| Dato | Fuente |
|---|---|
| Precios de los soberanos (pesos / MEP / cable) | `data912.com/live/arg_bonds`. Cada bono cotiza en tres especies: `AL30`, `AL30D`, `AL30C`. |
| Cupones del canje 2020 | `bonistas.com/api/bonds`, campo `description`: enumera el step-up cupón por cupón. |
| Amortización | Texto del prospecto que publica **Rava** en `/perfil/<TICKER>`, citando la Resolución 381/2020. |
| Obligaciones negociables | `bonistas.com/api/bonds`, familias `ONS` y `ONS-CABLE`. |

**Lo que se probó y NO sirve, para que nadie lo reintente:** data912 no tiene
cronogramas (se leyó su `openapi.json` entero: 16 endpoints, todos precios u
OHLC). Open BYMA tampoco — hay que pedirle con **POST** y cuerpo
`{"excludeZeroPxAndQty":true,"T1":true}` (con `T2` devuelve el sobre paginado
vacío, y el `405` de antes era el método, no una negativa); así contestan
`cedears`, `public-bonds`, `leading-equity` y `general-equity`, pero
`government-bonds`, `corporate-bonds` y `negotiable-obligations` dan **401**, y
ninguno trae flujos. Ministerio de Economía, `datos.gob.ar`, IAMC y Bolsar:
nada. **CAFCI (fondos comunes) devuelve 403** — por eso no hay sección de FCI:
no es que falte hacerla, es que no hay de dónde.

### Cómo se verificaron los cronogramas (tres cruces, no memoria)

Esto importa más que el código. `bonos_cronograma.csv` tiene los once soberanos
completos desde la emisión, y la cabecera del archivo documenta cada cruce:

1. **El importe del próximo cupón.** El campo `coupon` de bonistas **no es la
   tasa**: es la plata que paga el próximo cupón por cada 100 de nominal
   original, o sea `cupón_anual/2 × residual/100`. Ata la tasa **y** el residual
   a la vez. Da exacto en los nueve bonos donde bonistas lo publica. Es lo que
   fijó el cronograma del **GD46**, que no tenía otra referencia: su `coupon` de
   1,875 con cupón 4,125% obliga a un residual de 90,909 = 40/44, o sea 44
   cuotas de 2,2727% con cuatro pagadas → la primera fue el 9/1/2025.
2. **TIR, paridad, duration y DV01** contra la pantalla de referencia del
   usuario (1/9/2026). La **duration coincide hasta la centésima en los cinco**
   bonos con referencia, y la duration es justamente lo que el cronograma
   decide. Las centésimas de diferencia en la TIR son del *precio*, que se
   reconstruyó de un DV01 redondeado a cuatro decimales.
3. **Los gemelos.** GD29/GD30/GD35/GD38/GD41 tienen el mismo flujo que su par de
   ley argentina; lo único que cambia es el tribunal.

> **La trampa del step-up, que ya costó una vuelta:** el cupón que se **cobra**
> en una fecha es el que rigió el semestre **anterior**, no el que empieza ese
> día. Aplicarlo un pago antes daba 8,91% de TIR en el AL30 contra 8,65% de
> referencia — **con la paridad y la duration ya coincidiendo**, que es lo que
> señalaba que el error estaba en el importe y no en las fechas.

> **La otra trampa:** el **residual es lo que queda por amortizar**, no "100
> menos lo ya pagado". La primera versión restaba de 100 las amortizaciones
> pasadas del CSV y daba 92 cuando lo que faltaba sumaba 60.

> **Los intereses corridos van con días reales, y el prospecto dice 30/360.**
> Es cierto, y **está medido: no cambia nada**. La diferencia en el valor
> técnico es de 0,001 a 0,011 sobre ~100, y en la paridad **como mucho 0,01
> puntos porcentuales** en los once bonos — la pantalla muestra la paridad con
> un decimal, así que es invisible. Cambiarlo sería tocar algo verificado contra
> una referencia externa para ganar cero. Queda anotado para que no se
> "arregle" dos veces.

La columna `verificado` en `1` quiere decir que ese bono pasó los cruces. Si
alguna vez se agrega uno sin verificar se pone `0`, y la pantalla muestra su TIR
con una pastilla **prov.** al lado.

### Qué muestra la pantalla

Cuatro pestañas dentro de la vista Argentina: **Soberanos**, **Pesos**,
**Futuros** y **Corporativos**.

**Soberanos:** curva de rendimientos (TIR contra **duration**, no contra año de
vencimiento — un bono que amortiza temprano devuelve la plata mucho antes de lo
que su vencimiento sugiere; una línea por ley, y **la distancia vertical entre
las dos ES el canje**, dibujado); tabla por ley con TIR, TNA, paridad, duration,
DV01, residual vivo y próximo pago; y **tocar una fila abre su cronograma** —
cada pago con renta, amortización, total y cuánto queda vivo después, más qué
fracción de lo que se cobra es renta y cuánta es devolución de capital propio
(un bono que paga casi todo capital no "rinde" como un plazo fijo, te está
devolviendo lo tuyo).

**Obligaciones negociables:** una tabla **plana**, ordenable por cualquier
columna y con buscador. Estuvo agrupada por emisor y el usuario pidió lo
contrario: al comparar una ON contra otra el emisor es una columna más, no una
carpeta que hay que abrir. El agrupado por emisor sigue viajando en el payload
(`emisores`) porque el diagnóstico de consola lo usa.

> **La TIR, la duration y la paridad de las ONs las calcula bonistas, no este
> programa, y la pantalla lo dice.** Para los soberanos el cronograma está
> cargado y verificado acá; para las ONs son cientos de emisiones y no hay
> fuente pública con los flujos. **No se usa el campo de amortización de
> bonistas**: dice "bullet" hasta para los soberanos del canje, que amortizan en
> cuotas desde 2024. Si está mal en los que se pueden verificar, no se usa en
> los que no. **Tampoco hay calificación de riesgo** en ninguna fuente abierta,
> y la pantalla lo dice en vez de omitirlo en silencio.

### Curvas en pesos, futuros de dólar, y por qué nada de eso se mantiene a mano

La pestaña **Argentina** tiene cuatro pantallas: **Soberanos USD**, **Pesos**,
**Futuros** y **Corporativos**.

> **El pedido explícito fue que no haya que tocar código cuando vence un
> contrato o una letra.** Todo lo de abajo está diseñado alrededor de eso, y es
> el criterio con el que hay que juzgar cualquier cambio futuro: si te encontrás
> agregando un ticker o una fecha a una lista, parate y buscá el campo de la
> fuente que ya te lo dice.

#### Cómo se mantienen solas

| Qué | Cómo se resuelve | Qué NO se hace |
|---|---|---|
| Qué instrumentos entran | El campo `bond_family` de bonistas | Una lista de tickers |
| En qué curva va cada uno | Su campo `index` | Una tabla de tickers → curva |
| Cómo se llama una curva nueva | Su `bond_family_label` | Que desaparezca en silencio |
| Qué contratos de futuros hay | Los que devuelve A3 | Una lista de vencimientos |
| Cuándo vence un futuro | Se **deduce del símbolo**: `DLR092026` → último día hábil de septiembre 2026 | Anotarlo |
| Qué está vencido | Se compara contra hoy y se cae solo | Limpiarlo a mano |
| Qué rueda usar | Se pide un **rango** y se toma la más nueva de cada contrato | Pedir "hoy", que falla todo feriado, sábado y antes del cierre |

Verificado con datos reales: en la primera corrida aparecieron solas **cuatro**
curvas que no estaban declaradas en ningún lado — Badlar, Bonos CER, Bonos
Capitalizables y Bonos TAMAR — cada una con el nombre que le pone la fuente.

#### Dos campos, dos trabajos distintos — costó dos vueltas

`bond_family` y `index` parecen redundantes y no lo son:

- **`bond_family` decide QUÉ ENTRA.** Separa la letra en pesos **S30S6** de su
  gemela en dólares **SS6D** (`LETRAS-FIJO` contra `LETRAS-FIJO-USD`) y marca
  las patas sintéticas. Agrupar sólo por `index` metía las dos en la misma
  curva: dos puntos al mismo plazo con rendimientos muy distintos (**TO26
  25,6%** contra **TO26D 46,5%**).
- **`index` decide EN QUÉ CURVA VA.** Una LECAP (`LETRAS-FIJO`) y un BONCAP
  (`BONO-CAPITALIZABLE`) son familias distintas y la **misma** curva de tasa
  fija, y quien opera las mira juntas. Agrupar sólo por familia las partía en
  **nueve curvas donde el mercado ve cinco**.

Filtrar por familia y **después** agrupar por índice da las dos cosas bien. Las
familias que terminan en `-USD` se excluyen por el sufijo de la familia, no por
una lista de tickers.

#### Las dos convenciones de tasa que se pueden hacer mal

Verificado contra cuatro contratos de la pantalla de referencia del usuario, y
**dan exacto**:

| Contrato | Precio | Días | TNA calculada | TNA referencia | TEM calculada | TEM ref |
|---|---|---|---|---|---|---|
| SEP26 | 1.536,50 | 30 | 22,58% | 22,58% | 1,86% | 1,86% |
| OCT26 | 1.562,50 | 60 | 21,78% | 21,78% | 1,77% | 1,77% |
| DIC26 | 1.619,50 | 121 | 22,20% | 22,20% | 1,78% | 1,78% |
| JUL27 | 1.834,00 | 333 | 23,65% | 23,65% | 1,78% | 1,78% |

Las dos que se prestan a error:

- **La TNA anualiza en DÍAS**: `directa × 365/días`. No en meses.
- **La TEM CAPITALIZA**: `(1+directa)^(30/días) − 1`. **No** es la directa
  dividida por los meses — con 7,36% en 121 días, dividir daría 1,84% y
  capitalizar da 1,78%.

`pruebas/renta_fija.py` fija las dos contra esa tabla: si alguien las cambia por
"lo que parece razonable", se pone en rojo.

#### El spot de los futuros: se deduce, no se adivina

La tasa directa es `precio_futuro / spot − 1`, así que un spot malo corrompe
**todas** las tasas. El orden es:

1. **A3500 del BCRA**, que es contra lo que liquidan estos contratos.
2. Si el BCRA no contesta: **se despeja de las tasas implícitas que publica A3**.
   Si un contrato vale P, vence en D días y A3 dice que rinde R, el spot que usó
   A3 es `P / (1 + R/100 × D/365)`. Se despeja de varios y se toma la mediana.
3. Último recurso: el contrato más corto.

> **Por qué importa:** la primera versión saltaba directo al paso 3, que suena
> razonable y no lo es. En datos reales el contrato más corto quedó en **1534,5**
> contra un A3500 de **1509,5** — 1,7% que se le sumaba a la tasa de *todos* los
> contratos. La deducción del paso 2 dio **1510,11**, a 0,04% del real.

El payload lleva `spot_fuente` y **la pantalla dice cuál de las tres se usó**.

#### Cómo se dibuja una curva (contra el informe de referencia)

El usuario mandó el **informe diario de renta fija de IEB** como referencia.
Sus gráficos tienen tres cosas que acá se hacían distinto, y las tres importan:

**1. El eje X es la DURATION, no los días al vencimiento.** No es una cuestión
de gusto. Con días, el `TY30P` a 1365 estiraba el eje cinco veces y dejaba a los
otros diez papeles de tasa fija apilados contra el margen izquierdo, con los
tickers encimados hasta ser ilegibles (`S3N0O6E7` en la captura del usuario). En
duration ese mismo papel está en **2,05 contra 0,64** del `T30J7` —tres veces,
no cinco— y la nube se abre sola. Y además es lo correcto: un bono que amortiza
temprano devuelve la plata mucho antes de lo que su vencimiento sugiere. **Los
días siguen en la tabla**, que es donde se los busca.

**2. Es una NUBE con una tendencia punteada, no una quebrada.** `cvAjuste()`
ajusta `y = a + b·ln(x)` por mínimos cuadrados, que es la forma de una curva de
rendimientos: sube rápido en el tramo corto y se aplana en el largo. Unir punto
a punto daba un zigzag que se lee **como si el mercado tuviera saltos donde sólo
hay dispersión** entre papeles parecidos. Con menos de tres puntos no se ajusta
nada —una recta por dos puntos no es una tendencia, es la recta que los une— y
**no se extrapola** fuera del tramo que los papeles cubren.

**3. El gráfico va al COSTADO de la tabla, y la tabla primero.** Apilados, una
familia sola ocupaba dos pantallas y había que subir y bajar entre la curva y
los números del mismo papel. Abajo de 1100 px se apilan, porque en un teléfono
lado a lado no entra ninguno de los dos.

> El `minmax(0,…)` del grid **es necesario**: sin él la tabla ancha estira su
> columna y le come el ancho al gráfico en vez de desplazarse ella.

#### Los rótulos de la curva no se pisan nunca

Era la queja concreta sobre una captura de producción. Se colocan uno por uno
llevando la lista de los que ya se pusieron, probando **cuatro lugares por
punto** —arriba, abajo, derecha, izquierda— con aire alrededor. Si no entra en
ninguno **no se dibuja**: un ticker pisado es peor que ausente, se lee mal y se
confunde con otro; el punto queda igual, con su nombre en el globito y en la
tabla de al lado.

> **La prueba usa los ONCE papeles REALES de la captura, no la fixtura**, que
> tiene pocos por curva y no reproduce el amontonamiento. Y mide teniendo en
> cuenta el **ancla** de cada rótulo: uno con `text-anchor="start"` crece hacia
> la derecha de su `x`, no alrededor, y medirlos todos como centrados daba
> choques que no existían —me pasó, y me hizo perseguir un bug que no estaba—.
> Hoy: once de once rotulados, cero superpuestos.

#### Un punto muy lejos del resto no se dibuja (pero sí se lista)

Había un dólar linked cotizando con **139% de TIR** — una cotización vieja de
algo que no opera — que estiraba el eje y dejaba a los otros diecinueve
aplastados en una línea. `cvSinRaros()` los saca **del dibujo**, nunca de la
tabla, con un corte contra la mediana y el rango intercuartil (que no se mueven
por tener un outlier adentro, un promedio sí), y **la tarjeta dice cuántos y
cuáles quedaron afuera**.

#### La tira de tipos de cambio y la tasa sintética

Las dos salen de datos que **ya se bajaban**; no agregan ninguna fuente.

**La tira** (oficial, MEP, cable, brecha, canje) va arriba de las pestañas
porque vale para las cuatro. El MEP y el cable ya salían bono por bono —comprar
en pesos y vender en dólares— y el oficial es el mismo spot que usan los
futuros. Se usa la **mediana**, no el promedio: un soberano con la punta vieja
corre el promedio de todo el mercado. Verificado contra el informe del
01/09/2026 (oficial 1512,7 / MEP 1532,7 / CCL 1594,9): brecha = promedio de
`MEP/oficial−1` y `CCL/oficial−1` = **3,38%**, canje = `CCL/MEP−1` = **4,06%**,
las dos exactas.

#### Las dos sintéticas: las dos mitades del mismo triángulo

Son pesos, dólares y el futuro que los une, mirados desde los dos lados. Las dos
viven en **Futuros** y las dos salen de datos que ya se bajaban.

| | se arma con | queda una tasa en |
|---|---|---|
| `sinteticos` | letra de tasa fija + **comprar** futuro | **dólares** |
| `sinteticos_dl` | dólar linked + **vender** futuro | **pesos** |

```
LETRA + FUTURO      entra = precio/spot      sale = cobro/futuro
                    efectiva = sale/entra − 1

DÓLAR LINKED        tc_bono = precio/100     (los pesos por dólar que pagás hoy)
                    usd = 100·spot/precio − 1        (sale sola, sin futuro)
                    ars = 100·futuro/precio − 1      (cubierta con el futuro)
```

Verificado contra las seis filas del informe: la efectiva da idéntica en las
seis. Vale además la identidad `(1+tasa_pesos) = (1+dólares)(1+devaluación)`,
que es cómo se lee la tabla: tasa en pesos menos lo que se lleva el dólar.

**El dólar linked ya ES un instrumento en dólares** —paga 100 dólares al A3500
del vencimiento—, así que su tasa en dólares sale sin futuro. El futuro entra
por dos lados: como **referencia del mismo dólar** (si `tc_bono` está por debajo
del futuro, el bono compra dólares más barato, y esa es la señal sin pasar por
ninguna tasa), y como **cobertura** (vendiéndolo se cancela la exposición al
A3500 y queda un cobro cierto en pesos, o sea una tasa fija sintética, que es
contra la curva de LECAPs que hay que compararla). Esa curva se **interpola** al
plazo del bono y **no se extrapola**.

##### Tres errores de conocimiento financiero que tenía esta tabla

**1. Decía «sin riesgo de tipo de cambio», y para casi cualquiera es falso.** El
futuro de A3 **liquida contra el A3500**, o sea contra el oficial. La tasa queda
cerrada sólo para quien entra *y sale* por el oficial. El que pone dólares
**MEP** cobra pesos cubiertos contra el oficial y para volver a sus dólares
necesita el MEP del vencimiento, que no lo fija ningún futuro: lo que le queda
abierto es la **brecha**. Con la brecha en ~2,7% y un sintético de 23 días, eso
son más de 40% anualizado —**varias veces** la tasa que muestra la tabla—. La
tarjeta lo dice ahora con el número del día.

**2. El descalce se medía entre PLAZOS y hay que medirlo entre FECHAS.** Los
días del bono se cuentan desde la **liquidación** (24hs = hábil siguiente) y los
del futuro desde hoy. Restarlos metía el desfasaje de la liquidación adentro:
un viernes daba **tres días de descalce en pares que vencen el mismo día**
—seis de los diez del panel del 4/9— y de paso tapaba los de verdad (el S13N6
decía 11 cuando eran 14). Ahora se restan las dos fechas.

**3. Se publicaba una tasa donde no había cobertura.** Entre que cobra el bono y
liquida el futuro quedás descubierto, y ahí corre la diferencia entre la tasa en
pesos y la de dólares: ~22 puntos anuales, o sea **0,06% por día**. El S15S6
salía publicado con una TNA de **−21%**: 8 días de operación con 15 de descalce,
más descalce que operación. Con `FRACCION_DESCALCE = 0.25`, si el descalce se
come un cuarto del plazo la fila va **sin tasa y con el motivo escrito** —queda
en la tabla, con el descalce a la vista—. No es un umbral de gusto: en un
sintético de 42 días cuyo margen entero son 0,3%, once días de descubierto se
comen el negocio.

**Y una mejora, no un error:** se publican **TNA y TEA**. La TIR de un soberano
es efectiva, así que compararla contra una TNA lineal está sesgado. La tarjeta
dice que la comparación va por TEA.

> **El dólar de cada pata va en la tabla** (`tc_entrada`/`tc_salida` en una,
> `tc_bono`/`tc_futuro` en la otra). Lo pidió el usuario y tiene razón: sin esos
> dos números a la vista la tasa sale de la nada y no hay cómo auditarla.

#### `coupon` es la RENTA, no lo que se cobra

Salió publicado mal y en el papel más operado del panel: el `S30S6` mostraba
**17,54** cuando al vencimiento entran **117,54**. Faltaba el capital.

Cuando el pago es el **último** de una letra que **capitaliza** —no amortiza,
devuelve todo junto— lo que se cobra es renta **más los 100 de residual**.
Verificado contra el informe en los **diez** papeles de tasa fija: `100+cupón`
da su «Pago final» exacto en los diez.

> **Donde no se puede afirmar, no se afirma.** Si el instrumento amortiza, el
> residual no es 100 y sin cronograma no hay forma de saberlo: ahí se sigue
> mostrando el número de la fuente, que es la renta. Y un pago intermedio nunca
> devuelve capital, sea la familia que sea.

Lo encontré armando los sintéticos, porque esa tabla pide el cobro al
vencimiento y el mío daba 100 menos.

##### Y quién decide si ese 100 corresponde: el PRECIO, no la familia

Esto se resolvía con una lista a mano, `FAMILIAS_CAPITALIZAN`, y **la lista se
equivocó de las dos maneras posibles, las dos publicadas**:

- **De más.** `LETRAS-CER` estaba adentro, y el capital de un CER **no es 100**:
  es 100 ajustado por inflación. El `X30S6` decía que cobrabas **100** cuando se
  cobran **~115,8**, y había **ocho** letras CER así. La TIR de un CER es una
  tasa **real**, en unidades de CER; mezclarla con un cobro en pesos nominales
  es un error de categoría, no de redondeo.
- **De menos.** Los duales no estaban, así que **siete** papeles que capitalizan
  y pagan todo junto —igual que una LECAP— mostraban la columna vacía sin
  motivo.

Ahora **no se le pregunta a la familia, se le pregunta al precio**: el cobro
candidato (`monto + 100`) tiene que **reproducir el precio** al descontarlo a la
TIR que publica la fuente, con 1% de tolerancia. La cuenta contesta, en el
fondo, si esa TIR está expresada en pesos nominales:

| | ¿cierra? | por qué |
|---|---|---|
| tasa fija, TAMAR, BADLAR, duales | **sí**, al 0,05% | su TIR es nominal en pesos |
| CER | no, por 13% o más | su TIR es **real**, en unidades de CER |
| dólar linked | no | su TIR es en **dólares**; el capital son 100 USD al A3500 del vencimiento, que hoy no se sabe |

Los dos últimos no son un error de la fuente: son instrumentos cuyo cobro final
**no se puede afirmar hoy**, y ahí la columna queda vacía. La ventaja de
preguntarle al precio es que **no hay lista que envejezca**: cuando el Tesoro
emita una familia nueva, entra sola si la cuenta cierra.

> **El riesgo de esto** es que si la fuente cambiara cómo expresa la TIR, la
> columna se vaciaría **en silencio**. Por eso el diagnóstico de `bonos.yml`
> imprime, por curva, cuántos últimos pagos afirman su cobro: `Tasa fija 10/10`,
> `CER 0/17`. Si una curva que siempre afirmó deja de hacerlo de un día para el
> otro, es esto y no el mercado.

#### El próximo pago: lo único del cronograma que publica la fuente

El pedido fue «que todo lo que sea renta fija me aparezca cuáles son sus pagos,
también en las ONs». Los soberanos ya lo tenían —cronograma completo, cargado y
verificado en `bonos_cronograma.csv`—; los pesos y las ONs no.

Una sonda al panel de bonistas (909 filas, todas las claves con su conteo)
encontró dos campos que no se estaban usando y que están en **881 de 909**:

- **`days_to_coupon`** — días hasta el próximo servicio.
- **`coupon`** — su **importe** cada 100 nominales. **Es un importe, no una
  tasa**: es la misma confusión que ya se pagó cara con los soberanos. El TO26
  paga 15,50% anual sobre 100 de residual y el campo trae **7,75**.

No hay ningún array de flujos: **el cronograma completo sigue sin existir en
ninguna fuente abierta**, y eso ya está verificado (§ *Fuentes*).

**La distinción que hace útil a esto, y que no es cosmética:** cuando
`days_to_coupon` **coincide** con `days_to_finish` no queda ningún servicio
entre ese pago y el vencimiento, o sea que **ES EL ÚLTIMO**. Una letra que
capitaliza y paga todo junto queda entonces con su **cronograma completo, de
una sola línea**, y eso es un dato firme. Cuando difieren, lo que se muestra es
un cobro parcial y el importe lleva un **`+`** al lado: los que siguen no los
publica nadie gratis, y mostrar un cupón suelto como si fuera todo lo que queda
por cobrar sería peor que no mostrarlo. La tarjeta lo dice con todas las letras.

Verificado en los dos sentidos con datos reales: el `S15S6` da 12 = 12 → último;
el `TY30P` da 88 contra 1365, su próximo pago cae el **30/11/2026** —que es su
cupón— y **no** se marca como último.

> **Cuando es el último, la fecha se toma del vencimiento de la MISMA fila**, no
> se reconstruye desde los días. Derivándolas por caminos separados, las
> columnas «vence» y «próximo pago» podían decir días distintos del mismo evento.

#### La fecha del panel es la MAYORITARIA (esto salió publicado mal)

Al pasar a calcular los plazos acá en vez de leerlos de la fuente, se empezó a
necesitar una «fecha de hoy». Se tomó del campo `estimation_date` **de la
primera fila** del panel, y eso salió publicado: las ONs mostraban su próximo
pago el **27/07/2026 estando a 2/9** —una fecha que ya había pasado— y el
`CAC7O` daba **412 días** al vencimiento en vez de 369. Alcanza con que **una**
fila venga rancia para correr los plazos de los novecientos instrumentos.

Ahora se toma la fecha **más frecuente**, que es el mismo criterio que el
proyecto ya usa para los atrasos de precios (§8): unos pocos papeles sin
actualizar no pueden mover el día de referencia de todos. A igual frecuencia
gana la más nueva. Y se resuelve **una sola vez** para las ONs y para las curvas
en pesos: si cada una la resolviera por su cuenta podrían quedar en días
distintos.

> **Por qué no lo cazaron las pruebas y sí el workflow:** en la pantalla un
> plazo corrido **no se ve**, porque las fechas siguen pareciendo plausibles.
> Por eso el payload publica ahora `dias_fuente` —los días que dice la fuente—
> al lado de los nuestros, y el diagnóstico de `bonos.yml` los compara especie
> por especie.

**Unas pocas que difieren por dos o tres días no son un error.** Cada fila trae
su propio `estimation_date` y algunas la fuente las valuó antes; contra la
compra de hoy el número bueno es el nuestro. En la corrida del 2/9 difieren 5 de
260, todas de IRSA, por 2-3 días. El diagnóstico sólo grita cuando la
divergencia es **sistemática** (más del 10% de las especies) o **grande** (más
de 7 días), que es la firma de la fecha del panel corrida.

#### Los días NO estaban mal, aunque lo parecían

Vale la pena dejarlo escrito porque la evidencia era convincente y la conclusión
era falsa. Contra el informe de cierre del 01/09/2026, nuestros días daban **uno
menos en los once papeles de tasa fija, sin una sola excepción** — la pinta
clásica de un error de convención.

No lo era. **Ese informe es el cierre del 01-09 y liquida el 02-09; nuestro dato
es del 02-09 y liquida el 03-09.** Un día más fresco, no un día mal contado.

Verificado contra los datos crudos: para las tres formas —24hs sobre día hábil,
contado inmediato, y un vencimiento que cae sábado— el `days_to_finish` que
publica la fuente es **exactamente** el vencimiento hábil menos la liquidación
de ese plazo. Ya cuenta desde la liquidación y ya corre los fines de semana.
`pruebas/renta_fija.py` lo deja clavado con las filas crudas, **para que nadie
vuelva a "arreglar" un día que no está roto**.

**Lo que sí estaba mal era la FECHA.** La fuente publica el vencimiento
*nominal*: el `TO26` figura venciendo el **17/10/2026, que es sábado**, cuando
lo que se cobra —y contra lo que ella misma descuenta— es el lunes 19/10. Ahora
`vencimiento_y_dias()` corrige la fecha al hábil siguiente, así la columna dice
lo mismo que la cuenta.

> **La fecha del panel sale de `estimation_date`, no del reloj.** El workflow
> corre en UTC y a las 02:00 UTC ya es otro día que en Buenos Aires, así que
> `date.today()` correría todos los plazos una vez por noche.

#### Los que distorsionaban la curva no eran falsos: no habían operado

Es la causa de fondo del punto anterior, y el corte por outlier era el síntoma.
Medido sobre el panel del **2/9/2026**: de 54 papeles en pesos, **15 tenían
volumen exactamente 0**. Cuatro de los seis dólar linked estaban en ese grupo,
y por eso esa familia salía con rendimientos de 0,8% y 10,8% mezclados sin nada
en el medio — no era el mercado, eran cotizaciones rancias. La fuente publica
la última punta aunque sea de hace días, sin decir que lo es.

`marcar_operados()` en `bonos.py` le pone un campo `opero` a cada fila. **Las
dos condiciones son relativas a propósito, para que no quede un umbral que
envejezca** cuando cambien los volúmenes del mercado:

1. que haya operado algo (`volumen > 0`), que no necesita umbral ninguno; y
2. que ese algo no sea una miga contra **la mediana de su propia curva**
   (`FRACCION_MEDIANA = 0.01`). Ésta es la que saca al `TY30P`: negoció 0,01
   contra una mediana de 7,72 y él solo estiraba el eje de 300 a 1365 días,
   aplastando contra el margen izquierdo a los diez papeles que sí se operan.

Tres detalles que ya se pisaron:

- **La segunda condición no se aplica con menos de 5 papeles**
  (`MINIMO_PARA_RELATIVO`). Con dos, la "mediana" *es* el más grande y el otro
  quedaba afuera por nada.
- **Si la fuente no manda `volume` para ninguna fila de la curva, pasan todas.**
  Callarse media curva por un campo que no vino sería peor que el problema.
- **Un papel poco operado no es lo mismo que uno sin operar.** El `TO26` negoció
  1,13 contra una mediana de 7,72 y entra: el filtro apunta a las puntas
  rancias, no a los papeles flacos.

Nada de esto borra nada: **los papeles siguen en la tabla**, en gris y en
bastardilla, y la tarjeta dice cuántos dejó afuera y por qué. Si de una familia
no operó ninguno (la BADLAR del panel real, un solo papel con volumen 0) no se
dibuja una curva de un punto: se dice que no operó ninguno.

> La regla vive **sólo en `bonos.py`**. El frontend lee `opero` y no vuelve a
> decidir, así el diagnóstico de `bonos.yml` (que imprime una columna `dib`) y
> la página dicen exactamente lo mismo. Si alguna vez discrepan, es que alguien
> duplicó la regla en el JS.

#### Las patas sintéticas de los duales no son especies

`TXMJ8_CER`, `TTS26_CAP`, `BPOA8_PUT`: son la descomposición que hace bonistas
para valuar la opción de un bono dual, no algo que se pueda comprar. Vienen con
precio 0 o TIR absurda — el `TTS26_CAP` daba **−95%** — y en una tabla se leen
como oportunidades que no existen. Se filtran por las dos marcas que usa la
fuente: guion bajo en el ticker, o familia terminada en `-LEG`.

#### Corporativos: plana, no agrupada

La primera versión agrupaba por emisor, con el argumento de que el que arma una
cartera decide primero *a quién le presta*. El pedido fue el contrario y tiene
razón para este caso: agrupadas no se pueden ordenar por rendimiento ni comparar
dos emisores al mismo plazo sin abrir y cerrar. Ahora es una tabla sola,
ordenable por cualquier columna, con buscador, y el emisor como columna.

#### Fuentes

| Qué | De dónde |
|---|---|
| Curvas en pesos y ONs | `bonistas.com/api/bonds` — **un solo pedido para las dos cosas** |
| Futuros | `apicem.matbarofex.com.ar/api/v2/closing-prices` (A3, público) |
| A3500 | `api.bcra.gob.ar` (dos endpoints, se prueban los dos) |

**Ninguna de las tres puede tirar abajo al resto**: si una falla, su sección sale
vacía con su explicación y todo lo demás se publica igual.

---

### Educación con la fuente y tolerancia a fallos

El panel de ONs pesa 1,6 MB e `intradia.yml` publica cada diez minutos. Por eso
`--cache-ons` con TTL de 30 minutos: cada publicación sale **completa** —no se
cae la sección en las vueltas intermedias— y los pedidos bajan a dos por hora.

**Si bonistas o data912 no contestan, los soberanos igual salen y el screener ni
se entera.** La renta fija no puede tirar abajo las acciones.

`data912` y `bonistas` son servicios de terceros sin acuerdo de nivel de
servicio; data912 se describe a sí misma como una API educativa. Para uso
profesional con clientes eso hay que decirlo, y la pantalla de ONs lo dice.

---

## 8. Yahoo Finance: todo lo que se aprendió a los golpes

### Los fallos vienen en rachas, no por símbolo

Un lote de 60 puede volver entero vacío aunque los papeles estén vivos. En un log
real fallaron BK (Bank of New York Mellon) y MMC (Marsh & McLennan) — dos
empresas perfectamente cotizantes.

**Por eso `bajar_precios()` reintenta en tres vueltas:** el lote completo (50),
después de a 5, después de a 1, con pausas crecientes. `pruebas/reintentos.py`
simula el comportamiento en rachas y verifica que recupera **todos** los vivos y
deja afuera sólo los muertos.

> Esta función es **compartida** por `servidor.py` y `generar_sitio.py`. Estuvo
> duplicada y sólo el servidor reintentaba; por eso al sitio le faltaban papeles.
> No la vuelvas a duplicar.

**Cortafuegos:** si la primera vuelta no trae *un solo símbolo*, no es una racha,
es que Yahoo no está contestando. Se corta ahí. Sin esto, 465 reintentos de a uno
con pausas de 3 s son 25 minutos tirados y se come el timeout del workflow. Y la
tercera vuelta tiene tope (`MAX_INDIVIDUALES = 150`) por la misma razón.

### Precios atrasados — el problema más molesto

No es que falte un papel: es que **un papel aparezca con el precio y la variación
de hace tres días sin avisar**. Pasa porque Yahoo, cuando lo apuran, devuelve la
serie recortada en vez de un error.

Cómo se ataca, en este orden:

1. `atrasos(precios)` compara cada símbolo contra la última rueda de **su
   mercado** (por sufijo: `.SA`, `.DE`, sin sufijo = EE.UU.), y usa la fecha más
   **frecuente** de ese mercado, no la máxima. Comparar todo contra Nueva York
   marcaría como rotos a 20 papeles sanos cada vez que Europa tiene feriado.
2. `repescar_atrasados()` vuelve a pedir de a uno los que quedaron atrasados.
   Cuando un lote grande viene recortado, pedir el símbolo solo casi siempre
   devuelve la serie completa.
3. Lo que sigue atrasado viaja al navegador en el campo `at` de cada símbolo. La
   tabla lo marca con `⚠` ámbar junto al ticker, la variación queda atenuada con
   subrayado punteado, hay columnas `Atraso` y `Última barra`, un KPI que se puede
   tocar para esconderlos y un filtro en el panel.
4. `diagnostico.py` audita un `datos.json` desde la consola.
5. El workflow **no publica** si más del 40% viene atrasado.

**Un día de atraso fuera de EE.UU. es normal**: Brasil, Europa y Asia tienen
feriados propios. Dos ruedas o más en un papel de Nueva York es Yahoo devolviendo
la serie recortada.

Aparte, si **todo** el archivo quedó viejo (el cron falló tres noches, la pestaña
está abierta desde el jueves) la firma del encabezado lo grita en rojo. Es un
problema distinto del de un símbolo suelto atrasado.

### Series sucias

`limpiar_barras()` corre sobre todo lo que baja: ordena el índice, saca fechas
duplicadas, saca la zona horaria (si no, después no se puede comparar con otro
índice sin ella), tira las filas sin `Close` y **completa `Open`/`High`/`Low` con
el cierre** en vez de tirar la barra, porque perder una barra corre todas las
ventanas móviles. Un `null` en `High` viajando al navegador se lleva puesto el
ADR, el ATR y el gráfico del símbolo.

### Pedirle precios a Yahoo desde el navegador

El sitio publicado se arma de noche. Si el usuario abre el link a media mañana,
el historial ya está pero falta la rueda de hoy, que son pocas barras. Por eso al
abrir se piden sólo las últimas semanas de cada símbolo a
`query1.finance.yahoo.com/v8/finance/chart/SIMBOLO` y se fusionan con lo que ya
había (`fusionarBarras`), con 6 pedidos en paralelo y barra de progreso.

Tres cosas que no son obvias:

1. **Hay que reajustar por dividendos.** El historial se baja con
   `auto_adjust=True`, así que las barras nuevas se escalan por
   `adjclose/close`. Sin eso un dividendo mete un escalón falso en el ASH.
2. **La fecha sale de `meta.gmtoffset`**, no del epoch a secas. Una barra de
   Tokio o de São Paulo caería en el día equivocado.
3. **La última barra guardada se reemplaza siempre**, porque pudo haberse
   guardado a mitad de rueda.

Después de fusionar se recalcula el atraso en JS con la misma regla que Python
(la fecha más frecuente de cada mercado), así el `⚠` queda correcto.

> **Esto NO funciona, y ya está comprobado.** El usuario probó el link el
> 13/8/2026 y le dio `Failed to fetch`: Yahoo no manda la cabecera CORS, así que
> el navegador descarta la respuesta. No se arregla desde este código.
>
> **Por eso la solución de verdad es `intradia.yml`**, que refresca el sitio
> cada diez minutos del lado del servidor y no depende de CORS para nada. El
> intento desde el navegador quedó como extra por si algún día Yahoo lo permite,
> pero **cuando falla no se muestra ninguna alarma**: sería ruido sobre algo que
> ya está resuelto. La banda roja quedó reservada para lo único que sí es un
> problema real: que los datos publicados tengan 2 ruedas o más de atraso.
>
> Si alguna vez hace falta que el navegador sí pueda, están `cloudflare-worker.js`
> (proxy propio, se pega la dirección en *Datos → Si Yahoo no contesta*) y
> `servidor.py`.

Si Yahoo contesta 429 se corta enseguida en vez de insistir 465 veces.

### Símbolos muertos de verdad

`WBA` (Walgreens, comprada por Sycamore en agosto 2025), `TTM`, `LFC`, `HNP`,
`PCRFY`, `YZCHY`. Estos no vuelven.

### Nada de datos de prueba

**El proyecto no tiene modo demo y no hay que devolvérselo.** Había un `--demo`
en `generar_sitio.py` y en `generar_html.py` que llenaba la tabla con caminatas
aleatorias: velas creíbles, variaciones creíbles, cruces del ASH creíbles y todo
falso. Al usuario lo confundía y con una bandera mal puesta se podía publicar.
Las series sintéticas viven ahora en `pruebas/fixtura.py` y no salen de ahí.

El screener, hoy, o muestra precios de Yahoo o no muestra nada.

### Cuarentena

Lo que falla 3 veces seguidas queda anotado en `sin_datos.json` y no se pide por
7 días. Pasada la semana se reintenta solo: los deslistados reinciden y los que
fallaron por una racha vuelven a entrar. **La usan los dos**, `servidor.py` y
`generar_sitio.py`. El botón "Rehacer todo el historial" del servidor perdona la
cuarentena a propósito: si el usuario lo aprieta es porque sospecha de los datos.

### El cron de GitHub no se cumple, y por eso el workflow tiene un bucle adentro

**Medido sobre este repo**, con `0,30 8-23 * * 1-5` pedido (32 corridas al día):

| Día | Corridas reales |
|---|---|
| 21/08 | 23 |
| 24/08 | 21 |
| 25/08 | 19 |
| 26/08 | 10 |
| 27/08 | **2** |
| 28/08 | **1** (a las 02:25 UTC, ninguna con el mercado abierto) |

El 28/08 el usuario abrió el link a las 14:46 UTC —una hora larga después de la
apertura— y vio los precios del cierre anterior. No era el navegador ni la
caché: **el cron simplemente no se ejecutó**. Los cron de Actions son "mejor
esfuerzo" y a los repos que piden mucha frecuencia se les saltean corridas.

**La salida no es pedir más corridas**, que empeora el estrangulamiento, sino
que cada corrida cubra un rato: se pide **una por hora** y adentro se refresca
cada 10 minutos.

**Con 50 minutos de bucle no alcanzó.** El 4/9/2026 el usuario volvió a reportar
lo mismo: se pidieron 8 disparos y GitHub largó **uno**, a las 12:18 UTC, así que
la única corrida del día terminó **27 minutos antes** de que abriera Nueva York.
A las 15:18 lo publicado tenía 2 h 15 y era de antes de la apertura. Por eso el
bucle pasó de 50 minutos a **5 h 30** (`MINUTOS=330`, `timeout-minutes: 350`; el
tope duro de un job son 6 horas): un solo disparo que caiga en la mañana cubre
casi toda la rueda.

**El ritmo no cambia y esto es lo importante:** sigue siendo un refresco cada 10
minutos y el grupo de concurrencia deja **una sola corrida viva**, así que Yahoo
no recibe ni un pedido más por unidad de tiempo por más disparos que larguen.
Lo único que se achica son los huecos.

**El bucle se corta a las 00:30 UTC** aunque le sobre tiempo. El after-hours
cierra a las 00:00 y la corrida pesada (`actualizar.yml`) arranca 01:30: si las
dos le pegan a Yahoo a la vez aparecen las descargas parciales, que es
justamente lo que la nocturna no se puede permitir.

Detalles que importan:

- El publicado va **con `git` a mano**, no con `peaceiris/actions-gh-pages`: una
  action no se puede llamar dentro de un bucle de bash. Se replica `force_orphan`
  haciendo `git init` en cada vuelta, así `gh-pages` sigue teniendo **un solo
  commit** y no 2 GB de historial al año.
- **Una vuelta que falla no corta la corrida.** Yahoo tiene rachas malas y la de
  dentro de diez minutos puede andar perfecto. Sólo se devuelve error si no
  publicó ninguna.
- El grupo de concurrencia es **`intradia`**, distinto del `screener` de la
  nocturna, así la nocturna nunca se cancela por esto. Entre corridas de este
  workflow sí se cancela la vieja: si GitHub larga dos juntas tras una demora,
  la que vale es la nueva.

> El botón `⟳` de la página **no arregla esto**: vuelve a bajar el `datos.json`
> publicado, que es tan fresco como la última corrida del workflow. Cuando el
> cron no corre, no hay nada más fresco que traer.

### Yahoo bloquea más a los servidores

Las IPs de GitHub Actions reciben más cortes que una conexión hogareña. El
workflow reintenta 3 veces con pausas de 90 s y, antes de publicar, verifica:

- que hayan entrado **al menos 300 símbolos**
- que **no más del 40% venga con la barra atrasada**

Si alguna falla, **no publica** y deja el sitio anterior en pie. Esto es
deliberado: mejor datos de ayer que un sitio roto.

El workflow además **cachea `cache_fundamentales.json` y `sin_datos.json`** entre
corridas con `actions/cache`. Sin eso se vuelven a pedir los 465 `get_info()`
todas las noches, que es lentísimo y es lo que más hace enojar a Yahoo — o sea,
lo que causa las descargas parciales.

### Doble listado — confusión frecuente

Varios papeles cotizan en NASDAQ/NYSE y también en Toronto con el mismo ticker
(SHOP, AEM, KGC, HL, NG, PAAS, B). Si un precio no cierra por un factor de ~1,40,
es el dólar canadiense. Ya pasó una vez: el usuario comparó contra `TSX:SHOP` en
vez de `NASDAQ:SHOP` y pensó que los datos estaban mal. Está anotado arriba de
`verificar.py`, que es donde se va a mirar cuando un precio no cierre.

### Fundamentales

`get_info()` de yfinance trae sector, industria, país, float y market cap. Se
cachea 7 días en `cache_fundamentales.json`. **La calidad es mediocre**: se
detectó `ACH` (Aluminum Corp of China) clasificado como *Healthcare* cuando es
Basic Materials. No rompe cálculos técnicos pero ensucia las métricas de
industria.

---

## 8b. De dónde salen los precios, y por qué de ahí

Medido el 2/9/2026 desde el runner de Actions (`sonda_velocidad.py`, borrada
después de contestar). Los números son de esa corrida, no estimaciones.

| Fuente | Pedidos | Tiempo | Cubre del universo | Moneda |
|---|---|---|---|---|
| **Yahoo** (`v8/finance/chart`, de a uno) | **465** | ~70 s | 465/465 | la de origen |
| **data912** `/live/usa_stocks` | **1** | 1,0 s | 3.155 símbolos | **USD** |
| **data912** `/live/usa_adrs` | **1** | 0,5 s | 205 símbolos | **USD** |
| data912 `/live/arg_cedears` | 1 | 0,8 s | 967 símbolos | **pesos — inservible** |
| BYMA `cedears` (POST) | 1 | 1,5 s | 1.168 símbolos | **pesos — inservible** |

**Los dos endpoints de data912 juntos cubren 374 de los 465 en dólares, con dos
pedidos.** Los 91 que faltan son ETFs (`TLT HYG LQD EWZ` y la familia `EW*`),
listados fuera de EE.UU. (`.DE .PA .SA .T .TW .IL`), los seis muertos conocidos
(`WBA TTM LFC HNP PCRFY YZCHY`) y los dos que esperan confirmación de renombre
(`BK MMC`).

### Lo que esto cambia y lo que no

**El cuello de botella no es la CPU, es la cantidad de pedidos.** Yahoo tarda
0,150 s por símbolo y corta cuando lo apuran, que es exactamente por qué los
precios llegan tarde. Bajar de 465 pedidos a ~87 (374 por data912 en dos, más
los ~85 vivos que faltan por Yahoo) es **un 81% menos de pedidos** contra la
única fuente que rate-limitea.

**El historial sigue en Yahoo y no hay alternativa.** Ninguna fuente sirve OHLC
en bloque: `/historical/...` de data912 es de a un símbolo, y el de CEDEARs
viene en pesos, o sea que rompe el invariante 2. La corrida nocturna
—400 barras × 465 símbolos— no se puede mudar.

> **Nunca uses `arg_cedears` ni el panel de BYMA para precios.** Están en pesos
> y mezclan el movimiento del papel con el tipo de cambio implícito: un CEDEAR
> puede subir 4% un día que el papel no se movió. Sirven para la sección
> Argentina, no para el screener.

### Sobre reescribir en C++ (se preguntó, se midió)

**No serviría de nada.** El tiempo se va esperando la red, no calculando:

- El recálculo completo del motor —465 símbolos × 400 barras, ASH, Paragon,
  RSI, ADX, líneas de tendencia— tarda **3-35 ms en JavaScript**.
- La descarga tarda **~70 s**, y es todo espera de red y pausas deliberadas
  entre reintentos.

C++ haría los 30 ms un poco más rápidos y no tocaría los 70 segundos. A cambio
se perderían `yfinance` y `pandas`, aparecería un paso de compilación, y el HTML
dejaría de ser un archivo suelto que anda sin internet ni dependencias
(invariante 7). **La palanca real es pedir menos veces, no calcular más rápido.**

---

## 9. Cómo testear (no hay navegador)

```
cd pruebas && ./correr.sh
```

Arma un sitio con datos sintéticos, le inyecta atrasos y sectores de mentira, y
corre todo. Hoy: **paridad OK (6,7e-14) + 36/36 de interfaz + gráfico + estrés**.

| Archivo | Qué prueba |
|---|---|
| `atrasos.py` | detección de atrasos por mercado, `limpiar_barras`, `cedears.csv` roto (termina en `ATRASOS OK`) |
| `reintentos.py` | las tres vueltas con Yahoo fallando en rachas, y la cuarentena |
| `repesca.py` | que la repesca arregle los recortados y no invente los muertos |
| `paridad.py` + `paridad_js.js` | Python ↔ JS, 18 combinaciones + RSI/ATR/ADX/ADR |
| `interfaz.js` | carga, filtros, orden, persistencia, URL, respaldo, teclas |
| `grafico.js` | que nada se dibuje fuera del canvas y que el escapado funcione |
| `estres.js` | períodos extremos, k de Paragon, sin columnas, industrias, CSV |
| `paragon.py` | EMA de Pine, conversión de longitudes, warmup del ancla, rVWAP |
| `consolidacion.py` | la caja: largo elegido, ADR propio, y el caso real de PLTR |
| `teclado.js` | saltos en la tabla, hoja de atajos, y que no dispare escribiendo |
| `columnas_globales.js` | que elegir un filtro NO te cambie las columnas |
| `persistencia.js` | los nueve flujos del guardado de columnas, dos pestañas incluidas |
| `yahoo.js` | parseo, ajuste por dividendos, husos, fusión, CORS bloqueado, 429 |
| `movil.js` | el panel como cajón en pantallas angostas y la pastilla de frescura |
| `rapido.py` | la fusión intradía: sin duplicar fechas, sin perder historial |
| `renta_fija.py` | **la cuenta contra casos analíticos** (un bono a la par rinde su cupón, la duration de un cupón cero es su plazo) **y los cronogramas contra la referencia externa**. Separados a propósito: si falla lo primero está mal el programa, si falla lo segundo está mal el CSV. |
| `bonos.js` | la vista de bonos: que lo que el payload trae llegue a la pantalla, la curva, el cronograma que se abre, las ONs por emisor |
| `menus.js` | los desplegables de la barra, el engranaje, y **que ningún control quede huérfano al mudarse de contenedor** |

Los de renta fija cubren además **lo que se mantiene solo**: que una familia
desconocida aparezca con su nombre en vez de desaparecer, que un papel vencido
se caiga, que las patas sintéticas de los duales no se cuelen, que el
vencimiento de un futuro salga del símbolo, y que el spot se despeje de las
tasas de A3 en vez de aproximarse con el contrato más corto.
| `fixtura.py` | arma `tmp/sitio` con series sintéticas. **El único lugar con datos falsos.** |
| `vista.js` | **en un navegador de verdad**: que la curva se vea, con color y con texto legible |

**Casi todo se prueba con jsdom** desde Node, con el canvas stubbeado entero.
Sirve para contar filas y columnas, leer KPIs, disparar clics y eventos `input`,
probar teclas, verificar persistencia (con un `localStorage` falso compartido
entre dos aperturas) y medir el recálculo.

### SÍ hay navegador, y hace falta

> Durante mucho tiempo acá decía «no hay Chrome en el entorno de desarrollo» y
> **era falso**: `/opt/pw-browsers` trae Chromium y Playwright lo maneja. Esa
> creencia costó cara.

jsdom **no aplica CSS ni calcula layout**. Dos bugs pasaron por delante de 811
pruebas sin que ninguna los viera, y los dos eran del mismo tipo —el DOM
perfecto y la pantalla no—:

1. **La línea de tendencia se dibujaba con `stroke:none`.** El `<path>` estaba
   ahí, con su `d` bien calculada, y en pantalla **no había ninguna línea**: las
   reglas de color apuntaban a `.cv-linea` y la clase había pasado a ser
   `.cv-ajuste`. Para jsdom estaba todo bien.
2. **El gráfico tenía un `viewBox` de 1000 y se pintaba en una columna de 636**,
   así que todo salía al 64% y los rótulos de 13 px quedaban en **8,3 px**. El
   usuario reportó «faltan las curvas»: estaban, pero se leían como una mancha.

`pruebas/vista.js` levanta el sitio en un servidor local —por `http` y no por
`file://`, que con origen opaco ni carga— y verifica **lo medible, no lo
estético**: que lo que tiene que tener color lo tenga, que el texto llegue a la
pantalla con al menos 11 px reales, que el gráfico tenga ancho y alto mayores
que cero y un tamaño comparable al de su tabla, y que ninguna pestaña tire una
excepción. **Nada de comparar imágenes.** Se saltea sola si faltan Playwright o
Chromium, para que la batería siga corriendo en cualquier máquina.

> Y para mirar de verdad: una captura con `page.screenshot()` sobre
> `.bo-tarjeta` alcanza para ver el problema en dos segundos. Cuando algo «se ve
> mal» y las pruebas están en verde, **sacá la foto antes de teorizar** — yo
> perdí un rato largo razonando sobre grid y `min-width` cuando la respuesta
> estaba en `getComputedStyle(...).stroke`.

**Ojo con las pruebas que dependen de la fecha:** `yahoo.js` dispara la descarga
a mano en vez de esperar el refresco automático. Cuando dependía del automático,
pasaba o fallaba según con qué fecha se hubiera armado la fixtura, y al cruzar la
medianoche empezó a fallar sola.

**Ojo con el debounce en los tests:** el guardado de sesión tiene 400 ms. Si el
test lee `localStorage` antes de eso, ve `undefined` y parece un bug que no lo es.

**Los precios de las pruebas son sintéticos.** Se prueba la maquinaria, no los
números de mercado. Para los números están `verificar.py` y `diagnostico.py`, que
necesitan internet.

---

## 10. Invariantes: cosas que no se rompen

1. **Paridad Python ↔ JS del ASH.** Si tocás uno, tocá el otro y corré
   `pruebas/paridad.py`.
2. **Nunca descargar el precio del CEDEAR.** Siempre el subyacente.
3. **Los tres modos de uso siguen funcionando.** Un cambio en `plantilla.html`
   tiene que andar en el sitio, en el servidor y en el archivo suelto.
4. **`localStorage` siempre vía `leerLS`/`escribirLS`.**
5. **El workflow no publica datos incompletos.** No aflojes los umbrales de 300
   símbolos y 40% de atraso.
6. **La `ema()` del ASH y la `ema_pine()` de Paragon son dos medias distintas.**
   No las unifiques: la primera siembra con el primer precio y es lo que
   sostiene la paridad del ASH.
7. **Los tres quirks del Pine se respetan** (STOCHASTIC con cierre, SMMA no
   recursiva, `sma(src,1)`).
8. **Nada de dependencias externas en runtime.** El HTML no carga scripts de CDN;
   funciona sin internet.
9. **La escala del panel del ASH incluye el cero y el histograma va clippeado.**
10. **`bajar_precios` es una sola.** No la dupliques entre servidor y sitio.
11. **Todo texto que venga de Yahoo pasa por `esc()`** antes de entrar al HTML.
12. **Nunca datos inventados.** Sin modo demo, sin rellenos, sin precios de
    mentira. Si no hay datos, la página lo dice.
13. **Una pestaña sólo graba la sesión si el usuario tocó algo en ella.** Si no,
    una pestaña vieja en segundo plano te revierte la configuración.
14. **Todo control de estado cuelga de un `.ctrl-host`.** El cableado no puede
    volver a depender de en qué contenedor del HTML está el control: así se
    desconectaron todos, en silencio, al mudarlos a los desplegables.
15. **Un rendimiento calculado acá se muestra como propio; uno de un tercero se
    muestra atribuido.** Los soberanos tienen su cronograma cargado y
    verificado, así que su TIR es auditable. La de las ONs la calcula bonistas
    y la pantalla lo dice. Nunca al revés.
16. **La renta fija no puede tirar abajo las acciones.** Si `data912` o
    `bonistas` no contestan, `bonos.py` avisa y sigue.
17. **`bonos_cronograma.csv` no se toca de memoria.** Cada línea tiene que pasar
    los cruces documentados en la cabecera, y `pruebas/renta_fija.py` los corre.
18. **Nunca el precio del CEDEAR, tampoco de `arg_cedears` ni de BYMA.** Están
    en pesos y mezclan el papel con el tipo de cambio implícito. Para el
    screener sólo sirven las fuentes en la moneda de origen.
19. **Nada de la sección Argentina lleva una lista de tickers ni de
    vencimientos.** Si te encontrás agregando uno, parate: hay un campo de la
    fuente que ya lo dice (`bond_family`, el símbolo del contrato). Era el
    pedido explícito del usuario y es lo que hace que la sección no se pudra
    sola cuando vence algo.
20. **Un instrumento sin dato no se dibuja con un dato inventado.** Sin precio o
    sin rendimiento, no entra a la curva. Muy lejos del resto, sale del dibujo
    pero **no de la tabla**, y la tarjeta dice cuál y por qué.

---

## 11. Trabajo pendiente, en orden de valor

### Alto

1. **Lightweight Charts (TradingView, Apache 2.0, ~45 KB)** para reemplazar el
   canvas propio: zoom, arrastre, escala log, ejes de tiempo adaptativos,
   crosshair nativo. Incrustar el bundle en el HTML, no CDN. **Nunca se pudo
   verificar visualmente desde el entorno de desarrollo** — si lo hacés, pedile
   al usuario que confirme cómo se ve.
2. **Web Worker para el motor.** Hoy el cálculo corre en el hilo de la UI. Con
   400 barras son pocos ms, pero con 600 y el universo creciendo la interfaz se
   va a congelar.
3. **Tabla de correcciones manuales de sector/industria**, para pisar los errores
   de Yahoo (el caso `ACH`). Un CSV `correcciones.csv` que se aplique después de
   `bajar_fundamentales`.
4. **Pedirle los precios del día a data912 en vez de a Yahoo.** Medido: cubre
   **374 de los 465 en dólares con dos pedidos** contra los 465 de Yahoo (ver la
   sección 8b). Es un 81% menos de pedidos contra la única fuente que
   rate-limitea, y es la causa real de que los precios lleguen tarde. Yahoo
   queda para los ~85 que faltan y para todo el historial, que no se puede mudar.
5. **Cargar los CEDEARs nuevos.** `armar_universo.py` ya compara contra el panel
   vivo y reporta las diferencias, pero **todavía no se aplicaron**. Se mapean
   solos: `BNG BNY CLS EMBJ MRSH NU SPCE SPCX`. Los brasileños van a mano:
   `ABEV3 BBDC3 CSNA3 ITUB3 PETR3 SBSP3 SUZB3 TIMS3 VALE3 VIVT3`. **Dos son
   renombres y hay que confirmarlos antes de tocarlos**: `BK`→`BNY` y
   `MMC`→`MRSH`, que hoy fallan en silencio en el universo.
6. **Sección Global**: bonos del Tesoro (`^TNX`, `^TYX`), commodities (`CL=F`,
   `GC=F`, `ZS=F`) e índices — verificado que Yahoo los devuelve.
7. **Portafolios.** El usuario los pidió y eligió **local ahora, backend
   después**: guardar en `localStorage` detrás de una capa fina. Cuentas y login
   son **imposibles** en GitHub Pages, que es estático; eso hay que decirlo
   cuando se retome.
8. **Acciones argentinas.** `data912` las publica en `/live/arg_stocks`; falta
   el parser y la pantalla. Ahí los filtros del screener vuelven a tener sentido
   y se muestran de nuevo (hoy sólo aparecen en la vista Tabla).
9. **FCI**: sin fuente. CAFCI devuelve 403 y no se encontró otra. No es que
   falte hacerlo, es que no hay de dónde.
10. **Calificación de riesgo de las ONs**: tampoco hay fuente abierta. La
    pantalla lo dice en vez de omitirlo.
11. **El A3500 del BCRA no contestó en ninguna corrida.** Hoy el spot de los
    futuros se despeja de las tasas implícitas de A3, que da a 0,3% del oficial,
    pero conviene encontrar el endpoint bueno: la tasa directa es
    `precio/spot − 1`, así que el spot decide todas las tasas de esa tabla.

### Medio

5. **Formato binario para los precios**: Float32 en base64 en vez de JSON. De
   ~8 MB a ~3 MB y parseo casi instantáneo.
6. **`optimizar_ash.py`** — banco de pruebas de parámetros con separación
   in-sample / out-of-sample (ver la sección 13).
7. **Virtualización de la tabla** si el universo crece más allá de ~2.000
   símbolos. Hoy con 465 el DOM plano rinde bien y no hace falta.

### Bajo

8. Sincronización de configuración entre dispositivos (requiere backend y
   cuentas; hoy se resuelve con **Copiar vista** y el respaldo `.json`).
9. Mudanza a Cloudflare Pages, que permitiría repo privado y subdominio elegido.

---

## 12. Cosas que ya se descartaron, con su motivo

- **Pine Screener de TradingView** — requiere plan pago y sólo escanea
  watchlists.
- **Excel como motor de cálculo** — inmanejable con ventanas móviles sobre 465
  series. Excel quedó como salida opcional, no como motor.
- **Streamlit** — el usuario quería un archivo/URL, no prender un servidor con
  Python cada vez. (El servidor local quedó igual, pero como opción secundaria.)
- **Librerías de indicadores tipo `technicalindicators`** — no traen el ASH y
  siembran RSI/ADX distinto que Pine. Se perdería la fidelidad, que es el punto.
- **AG Grid / TanStack Table** — cientos de KB para resolver un problema que no
  existe con 465 filas.
- **API paga con CORS** (Twelve Data, EODHD) — costo real y la clave quedaría
  expuesta en un HTML público.

---

## 13. Sobre el ASH como señal: honestidad estadística

Cuando se barren parámetros con separación in-sample / out-of-sample, sin
lookahead (la señal usa el ASH de `t-1`) y con costo por cambio de posición, hay
que ordenar por lo que le saca a comprar y esperar, no por el retorno a secas.

Corriendo el mismo barrido sobre **random walks puros** —donde no hay señal
posible— igual aparece una "mejor" configuración con 9,4% anual fuera de muestra,
que rinde 5 puntos *menos* que comprar y esperar y acierta 50,7%. **Esa es la vara
del autoengaño.**

Si el usuario pide optimizar parámetros, recordale: elegir una **meseta** (que los
vecinos rindan parecido), nunca un pico aislado. Y que **timing y screening son
problemas distintos**: que el ASH no le gane a comprar y esperar como señal de
entrada no lo invalida como columna para ordenar cuáles mirar.

---

## 14. Publicación en GitHub Pages

Repo **público** (Pages con repos privados requiere plan pago). Dos ramas:

- `main` — el proyecto. Lo sube el usuario.
- `gh-pages` — el sitio armado. **La crea el workflow**, con `force_orphan: true`
  para que guarde un solo commit (sin eso serían >2 GB al año).

Settings → Actions → General → **Read and write permissions**, o el workflow no
puede publicar.

El cron corre de martes a sábado 01:30 UTC = lunes a viernes 22:30 hora
argentina, después del cierre de Nueva York.

---

## 15. Estilo de código

- **Comentarios en español**, y que expliquen *por qué*, no *qué*. Los comentarios
  valiosos de este proyecto son los que documentan las trampas de Yahoo, los
  quirks del Pine y las razones de las decisiones de caché.
- Python: sin dependencias más allá de pandas/numpy/yfinance. El servidor usa sólo
  la stdlib.
- JS: sin frameworks, sin build step, sin CDN. Todo en `plantilla.html`.
- Nombres de variables e interfaz en español.
- El usuario prefiere **etiquetas automáticas sobre toggles manuales** cuando se
  puede inferir el estado.
