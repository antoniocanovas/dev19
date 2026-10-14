# Mercas — siguientes pasos

Propuesta para llevar la solución Mercas a pantallas táctiles, con el mismo criterio que los módulos de Odoo 20 *Despiece cárnico* (`meat_cutting`) y *Ruta de venta* (`sale_route_offline`) de `dev20`. Incluye la revisión de las dependencias de OCA de cara a una migración a Odoo 20.

*Revisado el 14/10/2026.*

---

## 1. Punto de partida

- **`mercas_base`** ya tiene la lógica difícil, y funciona desde los formularios estándar:
  - *Vender y Entregar*, y *Comprar y Recibir* con lotes automáticos;
  - cajas por línea, y devolución o entrega de envases;
  - etiquetas, origen y liquidación de lotes;
  - aviso de edición concurrente por bus.
- **`mercas_keys`** es una pantalla con F1-F4 que abre dentro las listas y formularios estándar. Para ir rápido, manipula el DOM: `addLineAndFocusProduct` pulsa *Añadir línea* y luego la celda de producto. Es la parte más frágil y donde más se gana.

## 2. Propuesta: pantalla táctil por modos

Una acción cliente Owl propia, como `RouteScreen` o despiece cárnico, con un modo por tarea en lugar de vistas embebidas. Las teclas F1-F5 se conservan como atajos de cada modo. Los formularios estándar quedan para los casos excepcionales.

### F1 — Venta en mostrador

1. **Cliente**, en tarjetas o buscando, con su **riesgo y deuda** visibles, como la ficha del cliente de la ruta.
2. **Producto**, en tarjetas por familia. Al tocarlo aparecen **los lotes disponibles como tarjetas**: proveedor, origen, kg en almacén, fecha y caja por defecto. Así se elige el lote sin abrir el desplegable de `sale_order_lot_selection`.
3. **Teclado numérico** para kg, nº de cajas y tipo de caja. Una báscula USB HID, o de etiqueta con código de barras, escribe directamente en el campo de kg.
4. **Lector de códigos.** Escanear la etiqueta de caja añade la línea con su producto y lote. Requiere que la etiqueta lleve el lote en el código de barras.
5. **Nota por línea**, que queda en la descripción bajo el producto.
6. **Revisar** y luego **Vender y Entregar**:
   - Un único método de servidor, tipo `sell_from_screen(vals)`, reutiliza el flujo actual de `mercas_base`: lote obligatorio, riesgo, confirmar y validar el albarán.
   - Después, imprimir etiquetas o el albarán.

### F2 — Recepción de compra

- Proveedor, después producto y luego kg, cajas, país o provincia de origen (solo los marcados como *Origen Mercas*) y *Facturación firme*.
- **Comprar y Recibir** en una sola llamada: crea el lote automáticamente e imprime las etiquetas al momento.

### F3 — Cajas

- Saldo de cajas por cliente o proveedor, en tarjetas por tipo de caja.
- Devolución o entrega rápida con +/−. Por debajo genera la compra o venta de envases y su *Recibir y facturar*.

### F4 — Lotes

- Tarjetas de lote con una barra de recibido, vendido, desechado y en almacén. Es lo más parecido a la vista de líneas y lotes de despiece cárnico.
- Acciones táctiles: **desecho rápido**, cambio de lote, y marcar para *Liquidar*, *Facturar adelanto* o *Factura firme*.

### F5 — Cobros

- Igual que en la ruta: facturas pendientes del cliente, importe y diario.
- Pago estándar, conciliado con las facturas elegidas al confirmarlo.

## 3. Criterios que se reutilizan de dev20

- **Una llamada para cargar los datos de la pantalla y una por acción.** Cada acción es un método de servidor que valida lo que recibe (cantidades, lotes, permisos) y no depende de onchanges ni del DOM.
- **Idempotencia con `uuid`** en cada venta o recepción, con una restricción UNIQUE. Una pulsación doble o un reintento no duplican pedidos.
- **Concurrencia:** la notificación por bus que ya tiene `mercas_base` se aplica al **stock de los lotes**. Si otro puesto vende del mismo lote, la tarjeta se actualiza.
- **Presentación:**
  - aplicación con su propio icono y menú;
  - cuadrícula para volver al inicio de Odoo;
  - instalación como PWA en la tablet;
  - insignias legibles en modo oscuro (`text-bg-300/info/success/warning`, nunca `text-bg-light`).
- **Tests de servidor y de hoot** para cada flujo.

## 4. Diferencias por ser Odoo 19

- **Owl 2:** no hay `proxy`, signals ni `useProps`. Se programa con `useState` y `onWillStart`, como en `mercas_keys`. Hay que adaptar el código, pero el patrón es el mismo.
- **Sin conexión:** creo que el modo sin conexión de `web` que usa `sale_route_offline` (`OfflinePlugin`, `scheduleORM`) es de Odoo 20 y no existe en 19, aunque no lo he comprobado en el código de 19. En un mercado tampoco conviene: el stock de los lotes tiene que ser el real en ese momento, así que la pantalla trabaja **solo con conexión**.

## 5. Orden recomendado

1. **Venta en mostrador con lotes (F1).** Es la operación más frecuente y la que más se nota.
2. Recepción (F2).
3. Cajas (F3).
4. Lotes y liquidación (F4).
5. Cobros (F5).

`mercas_base` no se modifica: la pantalla solo llama a sus métodos. Propuesta: un módulo nuevo, por ejemplo `mercas_touch`, que sustituya a `mercas_keys` con los mismos atajos F1-F5.

---

## 6. Dependencias de OCA y su migración a Odoo 20

### Qué módulos de OCA usa Mercas

| Módulo OCA | Repositorio | Lo usa | Tipo de dependencia |
|---|---|---|---|
| `purchase_lot` | purchase-workflow | `mercas_base` | En el manifiesto |
| `sale_order_lot_selection` | sale-workflow | `mercas_base` | En el manifiesto |
| `stock_restrict_lot` | stock-logistics-workflow | `purchase_lot`, `sale_order_lot_selection` y el asistente de cambio de lote de `mercas_base` (`restrict_lot_id`) | Indirecta, imprescindible |
| `account_financial_risk` | credit-control | `mercas_base` (*Vender y Entregar*) | Opcional: se detecta con `hasattr(..., "evaluate_risk_message")` |
| `sale_financial_risk` | credit-control | `mercas_base` (*Vender y Entregar*) | Opcional, igual que la anterior |

Fuera de OCA:

- **`mercas_ai`** depende de `odoo_mcp_manager`, de Cybrosys (en `19cybro`), y de `chat_ai`, que es propio.
  - `odoo_mcp_manager` **ya está disponible para Odoo 20** en [CybroOdoo/CybroAddons, rama 20.0](https://github.com/CybroOdoo/CybroAddons/tree/20.0) (versión `20.0.1.0.1`, depende de `base`, `mail` y `web`).
  - Para migrar `mercas_ai` falta adaptar `chat_ai` y el propio `mercas_ai`.
- **`mercas_keys`** y **`mercas_demo`** solo dependen de módulos del núcleo, aparte de `mercas_base`.

### Estado en OCA (consultado en GitHub el 14/10/2026)

En los cuatro repositorios ya existe la rama `20.0`, pero está prácticamente vacía: solo `sale-workflow` tiene un módulo (`sale_order_type`). **Ninguno de los cinco módulos está migrado a 20.0, y no hay ningún PR de migración abierto.**

Además:

- **`purchase_lot` no está publicado ni en 19.0:** la copia de dev19 sale del PR abierto [OCA/purchase-workflow#3071](https://github.com/OCA/purchase-workflow/pull/3071) (`[19.0][MIG]`).
- **`sale_order_lot_selection` de dev19 es una variante propia.** No coincide con la 19.0 de OCA:
  - añade el selector de varios lotes en el popover de stock (`static/src`, `get_available_lots_for_line`) y su informe;
  - le faltan cosas que OCA ha añadido después (ajustes de compañía, `sale_order.py`, `stock_move.py`, informes, seguridad y demo).
- **`stock_restrict_lot`, `account_financial_risk` y `sale_financial_risk`** coinciden con la 19.0 de OCA.

### Dificultad de migrar cada uno a Odoo 20

Comparando con el código de `20odoo`, los métodos del núcleo que sobrescriben siguen existiendo con la misma firma. Están en `stock.move`, `stock.quant`, `stock.rule`, `purchase.order.line`, `sale.order.line`, `account.move._post`, `payment.transaction` y `res.partner._commercial_fields`. Las vistas que heredan también siguen existiendo con el mismo id.

| Módulo | Tamaño | Dificultad | Motivo |
|---|---|---|---|
| `stock_restrict_lot` | ~260 líneas Python, sin JS, ~400 de tests | **Media** | Toca la reserva de stock (`_update_reserved_quantity`, `_get_available_quantity`, `_prepare_move_line_vals`, `_split`, `_action_done`). Las firmas no cambian, pero es el código más delicado del stock: hay que pasar sus tests y probar a fondo reservas y entregas con lote. Es la base de los otros dos, así que va primero. |
| `purchase_lot` | Pequeño, sin JS | **Baja** | 4 sobrescrituras de `purchase_stock` (`_get_procurements_to_merge_groupby`, `_prepare_purchase_order_line_from_procurement`, `_prepare_stock_move_vals`, `_find_candidate`), todas con la misma firma en 20. Conviene partir del PR de 19.0. |
| `sale_order_lot_selection` | Pequeño en Python, ~100 líneas de JS | **Media** | El Python es sencillo (`_prepare_procurement_values`, `_compute_lot_id`). El JS es un parche de `QtyAtDatePopover` de `sale_stock`, que sigue existiendo en 20 pero hay que pasar a Owl 3 (`useState` → `proxy`). Además hay que decidir si se sigue con la variante propia o se vuelve a la de OCA y el selector de varios lotes se pasa a un módulo propio. Si se hace la pantalla táctil, el selector de lotes pasa a ella y este módulo queda solo para el backend. |
| `account_financial_risk` | ~850 líneas Python, ~420 XML | **Baja-media** | Mucho código, pero sobre todo campos calculados y vistas. Sus sobrescrituras (`_post`, `_commercial_fields`) siguen igual en 20. Lo más laborioso son las vistas de ajustes y de contacto y los tests. |
| `sale_financial_risk` | Pequeño | **Baja** | Depende de `account_financial_risk`. Toca `payment.transaction` (`_set_authorized`, `_post_process`) y el cálculo de lo pendiente de facturar, que siguen igual en 20. Como es opcional para Mercas, puede esperar. |

### Recomendación

1. **Imprescindibles para Mercas en Odoo 20:** `stock_restrict_lot`, `purchase_lot` y `sale_order_lot_selection`, en ese orden. Aproximadamente **3-5 días** en total, incluidos tests.
2. **El riesgo financiero es opcional.** `mercas_base` funciona sin él, solo deja de avisar en *Vender y Entregar*. Se puede migrar después (**1-2 días**), o esperar a que lo haga OCA (Tecnativa suele migrar `credit-control` pronto).
3. Antes de migrar `sale_order_lot_selection`, separar lo propio (selector de varios lotes e informe) en un módulo `mercas_*`. Así el módulo de OCA se puede seguir actualizando desde upstream.
4. Si se hace la migración, conviene hacerla **en OCA** (PR `[20.0][MIG]`), para no mantener copias propias.
