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
cruzando eso con tendencia (EMAs), momentum (RSI, ADR, ADX), liquidez y fuerza
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
historial. `intradia.yml` corre **cada media hora mientras Nueva York opera**,
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
| `actualizar_rapido.py` | **La actualización intradía.** Toma el `datos.json` publicado, pide sólo el último mes y fusiona. Barato: es lo que corre cada media hora. |
| `cloudflare-worker.js` | Proxy de una línea, opcional. Sólo hace falta si Yahoo deja de mandar CORS. |

### Datos y configuración

| Archivo | Contenido |
|---|---|
| `universo.csv` | `ticker,grupo[,subyacente]` — 465 símbolos. |
| `cedears.csv` | `local,subyacente` — 400 mapeos del panel oficial de BYMA del 12/6/2026. |
| `plantilla.html` | **Todo el frontend**: motor de indicadores en JS, interfaz, gráfico. ~83 KB. |
| `requirements.txt` | pandas, numpy, yfinance. El servidor usa sólo la stdlib. |
| `.github/workflows/actualizar.yml` | El cron nocturno: historial completo. |
| `.github/workflows/intradia.yml` | Cada media hora durante la rueda: sólo los precios del día. |
| `pruebas/` | La batería completa. `cd pruebas && ./correr.sh`. |

### Generados (no se commitean, están en `.gitignore`)

`cache_precios.pkl`, `cache_datos.json.gz`, `cache_fundamentales.json`,
`sin_datos.json`, `sitio/`, `screener.html`, `pruebas/tmp/`.

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

1. **`cacheBase`** — RSI, ADR, ATR, ADX, EMAs, volúmenes, performances, máximos
   de 52 semanas. Se invalida sólo si cambian *esos* períodos o las EMAs.
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

- El sitio se genera con **400 barras**, no 600. Alcanzan para EMA 200 (200), el
  máximo de 52 semanas (252) y ~80 semanas de ASH. Un tercio menos de peso.
- **Página y datos separados** en el sitio publicado: el navegador cachea el HTML
  aparte y las visitas siguientes sólo bajan los precios.
- El payload del servidor se guarda **pre-comprimido** en `cache_datos.json.gz`
  (2,8 MB contra 8,2 MB en crudo). Antes se recomprimía en cada pedido.
- Si el gráfico está oculto, `dibujar()` sale en la primera línea sin calcular.

---

## 7. La interfaz

### Barra superior
Pastilla de **frescura** · `★ favoritos` · `Gráfico` · `Industrias ▾` ·
`Columnas N ▾` · desplegable de filtros guardados.

La pastilla es lo primero que se mira y por eso está antes que todo lo demás:
**verde** = se actualizó hace menos de 75 minutos, **ámbar** = es el cierre de la
última rueda (lo correcto con el mercado cerrado), **rojo** = el archivo quedó
viejo de verdad, dos ruedas o más.

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
   y a cambio de máquina. Al arrancar, **la URL tiene prioridad** sobre la sesión.
3. **Respaldo `.json`** — exporta e importa perfiles + favoritos + sesión. Al
   importar se **fusiona**, no se pisa: restaurar no te borra lo que ya tenías.
4. **Detección de almacenamiento bloqueado** — `hayAlmacen` prueba escribir; si
   falla, se usa un objeto en memoria y se avisa en el panel.

> **Trampa conocida:** `localStorage` no está disponible en orígenes opacos
> (`file://` en algunos navegadores). Una vez esto rompió la página entera al
> arrancar. Todo acceso pasa por `leerLS`/`escribirLS`, que atrapan la excepción.
> No uses `localStorage` directo.

**Qué se guarda y qué se guardaba mal.** El estado incluye ahora la búsqueda, la
industria seleccionada y el perfil elegido en el desplegable, además de los
filtros, las EMAs, los grupos, las columnas y el orden. Los chips de EMAs y de
grupos **no llamaban a `guardarSesion()`**: los elegías, recargabas y volvía todo
al default. Era la queja más concreta sobre "la memoria".

### Estado neutro
`NEUTRO` + `NEUTRO_CHECK` son **la única** definición de "sin filtros". La usan el
botón de limpiar, la opción `— sin filtros —` del desplegable y los presets. Antes
la lista estaba duplicada dentro del botón y se olvidaba de los controles nuevos.

### Presets de filtros

Cinco vienen armados en la constante `PRESETS`: Tendencia limpia, Cruce fresco de
ASH, Pullback en tendencia, Se mueve y es líquido, Fuerza relativa top. La primera
opción del desplegable es `— sin filtros —` (valor `'0'`), que limpia todo.

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

`COLS` define las columnas; las que tienen `def:1` son el set por defecto.
`nosel:1` marca las que no se pueden apagar (★ y Ticker). El desplegable las
agrupa según `GRUPOS_COL`. La selección viaja en la sesión, en la URL y dentro de
los perfiles guardados.

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

### Gráfico

Canvas propio, ~120 líneas. Velas + EMAs arriba, ASH abajo (bulls, bears,
histograma). Crosshair con OHLC. Selector diario/semanal.

> **Bug ya corregido, no lo reintroduzcas:** la escala del panel del ASH **debe
> incluir el cero** (`a=Math.min(a,0); z=Math.max(z,0)`) y el dibujo del
> histograma va dentro de un `clip()`. Sin eso, las barras se salían del panel y
> tapaban las fechas. `pruebas/grafico.js` verifica que nada se dibuje fuera del
> canvas.

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
> cada media hora del lado del servidor y no depende de CORS para nada. El
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

## 9. Cómo testear (no hay navegador)

```
cd pruebas && ./correr.sh
```

Arma un sitio con datos sintéticos, le inyecta atrasos y sectores de mentira, y
corre todo. Hoy: **paridad OK (6,7e-14) + 36/36 de interfaz + gráfico + estrés**.

| Archivo | Qué prueba |
|---|---|
| `atrasos.py` | detección de atrasos por mercado, `limpiar_barras`, `cedears.csv` roto |
| `reintentos.py` | las tres vueltas con Yahoo fallando en rachas, y la cuarentena |
| `repesca.py` | que la repesca arregle los recortados y no invente los muertos |
| `paridad.py` + `paridad_js.js` | Python ↔ JS, 18 combinaciones + RSI/ATR/ADX/ADR |
| `interfaz.js` | carga, filtros, orden, persistencia, URL, respaldo, teclas |
| `grafico.js` | que nada se dibuje fuera del canvas y que el escapado funcione |
| `estres.js` | períodos extremos, sin EMAs, sin columnas, industrias, CSV |
| `yahoo.js` | parseo, ajuste por dividendos, husos, fusión, CORS bloqueado, 429 |
| `movil.js` | el panel como cajón en pantallas angostas y la pastilla de frescura |
| `rapido.py` | la fusión intradía: sin duplicar fechas, sin perder historial |
| `fixtura.py` | arma `tmp/sitio` con series sintéticas. **El único lugar con datos falsos.** |

**No hay Chrome en el entorno de desarrollo.** Se usa **jsdom** desde Node, con el
canvas stubbeado entero. Sirve para contar filas y columnas, leer KPIs, disparar
clics y eventos `input`, probar teclas, verificar persistencia (con un
`localStorage` falso compartido entre dos aperturas) y medir el recálculo.

**No sirve para**: nada visual. El gráfico no se puede verificar así — lo único
comprobable es que no lance excepciones y que las coordenadas caigan dentro del
canvas (se hace capturando las llamadas a `fillRect`).

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
6. **Los tres quirks del Pine se respetan** (STOCHASTIC con cierre, SMMA no
   recursiva, `sma(src,1)`).
7. **Nada de dependencias externas en runtime.** El HTML no carga scripts de CDN;
   funciona sin internet.
8. **La escala del panel del ASH incluye el cero y el histograma va clippeado.**
9. **`bajar_precios` es una sola.** No la dupliques entre servidor y sitio.
10. **Todo texto que venga de Yahoo pasa por `esc()`** antes de entrar al HTML.
11. **Nunca datos inventados.** Sin modo demo, sin rellenos, sin precios de
    mentira. Si no hay datos, la página lo dice.

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
4. **`armar_universo.py`** — regenerar `universo.csv` y `cedears.csv` desde el
   panel de BYMA. Hoy `cedears.csv` es del 12/6/2026 y se actualiza a mano.

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
