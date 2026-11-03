# Ofertas Súper — CP 87130 (Cd. Victoria, Tamaulipas)

Compara precios de **Walmart, Bodega Aurrera, HEB, Chedraui, Soriana, Sam's Club, City Club y GranD**. El orden es por **precio unitario** (kilo, litro o pieza), guarda historial y te avisa solo de las ofertas que **de verdad** valen la pena.

## Qué hace

| Función | Detalle |
|---|---|
| Comparador | Busca en todas las tiendas al mismo tiempo y ordena por $/kg, $/l o $/pz, de modo que los "paquetes ahorro" no engañan. |
| Veredicto | Compara el precio de hoy con la mediana de los últimos 90 días: **excelente** (mínimo histórico), **buena** (≥15 % abajo), **normal** o **cara**. |
| Ofertas simuladas | Marca cuando el precio "antes" nunca existió o el "descuento" no baja del precio habitual, y guarda **evidencia fechada** en `~/.ofertas-super/evidencia/`. |
| Profeco QQP | Importa los datos abiertos de *Quién es Quién en los Precios* filtrados a Victoria, Tamaulipas, como referencia oficial. |
| GranD / HEB | GranD no tiene catálogo en línea y HEB bloquea consultas automatizadas. Sus precios se capturan del folleto semanal (Facebook/Instagram/Flipsnack), del anaquel o del ticket, en la página **Capturar precios** o con `ofertas capturar` (para HEB: `ofertas capturar 24.90 Leche Clavel 360 g --tienda heb`). Entran en la comparación por 14 días y alimentan el historial. |
| Alertas | Lista de vigilancia con precio objetivo opcional y avisos por **Telegram**, **correo** o consola. |

## Instalación (en tu computadora)

```bash
git clone <este repositorio> && cd ofertas-super
python -m venv .venv
# Windows: .venv\Scripts\activate    |   Mac/Linux: source .venv/bin/activate
pip install -e .
```

## Uso

```bash
ofertas web                         # abre http://127.0.0.1:5000
ofertas buscar aceite 1 l           # comparación en terminal
ofertas vigilar café nescafé 200 g --objetivo 120
ofertas alertas                     # revisa la vigilancia una vez
ofertas alertas --cada 360          # revisa cada 6 horas (déjalo corriendo)
ofertas capturar 35.90 Aceite Capullo 1 l --antes 42   # precio de GranD
ofertas importar-profeco QQP_2026.csv
ofertas config                      # crea ~/.ofertas-super/config.json para editar
```

### Alertas en tu Telegram (5 minutos)
**Desde la página:** abre `ofertas web` → **Ajustes** y sigue los 3 pasos (token de @BotFather, INICIAR el bot, «Detectar mi chat»).
**Desde la terminal:** `ofertas telegram` (te guía y envía un mensaje de prueba). Para comprobar después: `ofertas probar-alerta`.

### Revisión automática diaria
**Desde la página:** **Ajustes** → elige horarios → **Programar**.
**Desde la terminal:**
```bash
ofertas programar            # diario 08:00 y 19:00
ofertas programar 7 13 20    # tus horarios
ofertas programar --estado   # ver qué está programado
ofertas programar --quitar   # desactivar
```
- **Windows** crea tareas `OfertasSuper-HH` en el Programador de tareas, sin ventana visible.
- **Mac / Linux** agrega líneas a tu `crontab` marcadas con `# ofertas-super`; no toca tus otras tareas. En Mac, si macOS pide permiso para `cron`, acéptalo.
- La computadora debe estar encendida a esa hora. Cada revisión queda anotada en `~/.ofertas-super/alertas.log`, que también puedes ver en Ajustes.

## Configuración (`~/.ofertas-super/config.json`)
- `tiendas`: cuáles consultar.
- `umbral_oferta_pct` (15): qué tan abajo del precio habitual cuenta como oferta.
- `pausa_segundos` (2): pausa de cortesía entre consultas. No la bajes.
- `vtex_sc`: canal de ventas por tienda VTEX (HEB/Chedraui) si tu sucursal tiene precios propios, por ejemplo `{"heb": "1"}`.

## Limitaciones honestas
- **HEB, Walmart, Bodega Aurrera y Soriana bloquean las consultas automatizadas** con sistemas antibot; hoy sólo **Chedraui** responde en automático. Sam's Club y City Club se intentan; si bloquean, aplica lo mismo. En los clubes fíjate en el **precio por unidad**: el paquete grande no siempre es más barato, y requieren membresía. El programa lo detecta, lo reporta y **no intenta evadirlo**. Sus precios se capturan a mano en **Capturar precios** (de la app, el folleto o el anaquel) o se toman de los datos de Profeco. Una tienda que bloquea se omite por 24 h para no insistir (`ofertas desbloquear` para reintentar antes).
- Las tiendas **no ofrecen API pública**. Los adaptadores leen sus buscadores web y pueden fallar si cambian su sitio; la página web indica qué tienda no respondió. Soriana es **experimental**.
- El precio en línea puede diferir del de la sucursal física. El veredicto mejora con el historial: las primeras semanas casi todo saldrá "sin historial".
- Los términos de uso de los sitios restringen la extracción automatizada. El programa está pensado para **uso personal y moderado** (consultas espaciadas, sin reventa de datos).

## Marco legal útil (LFPC)
- **Art. 7 y 7 Bis**: el proveedor debe respetar el precio exhibido.
- **Arts. 46-48**: promociones y ofertas. Deben indicar condiciones y vigencia, y respetarse.
- **Arts. 32 y 43**: publicidad engañosa. Un precio "antes" inflado puede encuadrar aquí.
- Con la evidencia JSON (fecha, precio, precio "antes", historial) puedes presentar queja en **Concilianet** o en la oficina de Profeco en Cd. Victoria.

## Pruebas
```bash
pip install -e ".[dev]" && pytest
```
