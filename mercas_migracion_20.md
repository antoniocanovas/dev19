# Mercas — migración de Odoo 19 (dev19) a Odoo 20 (dev20)

Revisión del código portado en `dev20` frente a `dev19`, para retomar la migración más adelante. Complementa la sección 6 de `mercas_next.md`.

*Revisado el 20/10/2026 (apartados 1-7); ampliado el 22/10 (apartado 8), el 29/10 (apartado 9) y del 16/11 al 23/11/2026 (apartados 10-21).*

---

## 1. Conclusión

- **Se puede migrar.** Los módulos `mercas_*` y sus dependencias ya están portados a Odoo 20 en `dev20`, del commit `ab37d12` (*mercas20*) del 14/10/2026.
- **No cambia el modelo de datos propio:** no hay campos almacenados nuevos ni renombrados en los `mercas_*`, así que no hacen falta scripts `migrations/` propios.
- **No se pierde funcionalidad.** Todos los cambios son adaptaciones a la API de Odoo 20 o mejoras. Los tests de `mercas_base` son los mismos (6 + 9 + 5), y se añaden tours.
- **El control de crédito no necesita desarrollo nuevo.** Ver el apartado 4.
- **El paso pendiente es migrar la base de datos de 19 a 20.** Los cambios de datos del núcleo los resuelve la migración estándar (upgrade.odoo.com u OpenUpgrade 20), no los `mercas_*`.

## 2. Qué cambia en cada módulo

### `mercas_base` (19.0.1.0.0 → 20.0.1.0.0)

**Adaptaciones a Odoo 20:**

- **Permisos:** `security/ir.model.access.csv` pasa a `security/ir.access.csv`, con el formato nuevo `operation=crud`. En el manifiesto va al final de `data`.
- **Desechos:** en Odoo 20 desaparece `stock.scrap`; un desecho es un `stock.move` con `is_scrap`.
  - `stock.lot.scrap_line_ids` pasa de One2many a `stock.scrap` a un Many2many calculado y no almacenado sobre `stock.move` (`_compute_scrap_line_ids`).
  - `action_open_scrap` usa el `action_scrap()` estándar del lote, con `default_quantity=0`, la compañía y la ubicación con stock del lote.
  - En la pestaña *Scrap* del lote, las columnas pasan a `reference`, `quantity`, `uom_id` y `date`, y se añade `state`.
- **Unidad de medida:** `product_uom_id` pasa a `uom_id` en `stock.move.line`. Afecta a `stock_lot.py` y al asistente de cambio de lote.
- **Vistas:**
  - Los xpath de las líneas de pedido van ahora contra `column[@name='product_and_description']` en compras, `column[@name='sol_uom']` en ventas, y `widget[@name='section_state']` para el icono de fecha de cambio de cantidad.
  - Los iconos `fa-*` pasan a Material: `inventory_2`, `local_shipping`, `undo` y `shuffle`.
- **Informe de etiquetas:** desaparece `report_file`, y las variables del `t-call` de la Dymo se pasan con `.f`.
- **JavaScript (Owl 3):** `useProps`, `usePlugin(BusPlugin / NotificationPlugin)` y `useLayoutEffect`.

**Mejoras funcionales:**

- **`stock.picking._mercas_validate()` (nuevo `models/stock_picking.py`):** lo usan *Vender y Entregar*, *Comprar y Recibir* y las cajas.
  - Valida el albarán con `skip_immediate`, `skip_backorder` y, además, `skip_sms`, para la confirmación del SMS de `stock_sms`.
  - Si el albarán no queda hecho, da un error. Antes el pedido podía quedar como entregado sin estarlo.
- **Ubicaciones técnicas de cliente y proveedor:** se crean con `sudo()`, para que el flujo funcione con usuarios sin permisos de inventario.
- **Provincia de origen en las líneas de compra:** limitada al país de origen de la línea y, con `mercas_origin_filter`, a los países marcados como `mercas_origin` (las provincias ya no se marcan).

### `mercas_ai`

- **Permisos:** `ir.access.csv`, como en `mercas_base`.
- **Parámetros del sistema:** `get_param`/`set_param` pasan a `get_str`/`set_str` (`mercas_ai.custom_instructions`).
- **Informes de compras:** usan `uom_id` en `purchase.order.line`. Se añade el parámetro `uom_field` a `_line_product_detail`.
- **JavaScript:** el campo de historial del chat pasa a Owl 3.
- **Dependencias:** `chat_ai` está portado; solo cambian la firma de `_message_post_after_hook(message)` y `type="bytes"` en la imagen del bot. `odoo_mcp_manager` es la 20.0.1.0.1 de Cybrosys.

### `mercas_keys`

- **Owl 3 y nuevas vistas:** `useProps`, `t-out` e iconos `oi`.
- **Clic en el producto:** `addLineAndFocusProduct` pulsa ahora `td[name="product_and_description"]`. Sigue siendo la parte frágil, porque manipula el DOM.

### `mercas_demo`

- Se quita `company_type`, `tracking` pasa de `none` a `False`, y las imágenes usan `type="bytes"`.
- No se instala en producción.

### `mercas_touch` (nuevo, solo en dev20)

- Pantalla táctil con los modos F1-F5 que proponía `mercas_next.md`: venta con lotes, recepción, cajas, lotes y cobros.
- Depende de `mercas_base` y `barcodes`.
- **Pendiente decidir** si sustituye a `mercas_keys`. Si lo sustituye, `mercas_keys` se desinstala tras migrar.

## 3. Dependencias (todas presentes en dev20)

| Módulo | Origen en v19 | En dev20 | Cambios |
|---|---|---|---|
| `stock_restrict_lot` | OCA 19.0 (`19stock-logistics-workflow`) | 20.0.1.0.1 | `_prepare_move_default_values` pasa a `_prepare_return_move_default_values` (renombrado en el núcleo) |
| `purchase_lot` | PR OCA/purchase-workflow#3071 | 20.0.1.0.0 | xpath a `product_and_description`; `tracking == 'none'` pasa a `not tracking` |
| `sale_order_lot_selection` | Variante propia (selector de varios lotes) | 20.0.1.0.0 | Mantiene la variante propia. Popover en Owl 3, xpath de la vista y del informe (`line.label`) |
| `account_financial_risk` | OCA 19.0 (`19credit-control`) | 20.0.1.0.0 | Ver el apartado 4 |
| `sale_financial_risk` | OCA 19.0 (`19credit-control`) | 20.0.1.0.1 | Ver el apartado 4 |
| `chat_ai` | Propio | 20.0.1.0.0 | Firma de `_message_post_after_hook`. En dev19 hay una carpeta anidada `chat_ai/chat_ai` que no pasa a dev20 |
| `odoo_mcp_manager` | Cybrosys 19 | 20.0.1.0.1 | Versión 20.0 publicada por Cybrosys |
| `stock_picking_report_valued` | OCA 19.0 (`19stock-logistics-reporting`) | 20.0.1.0.0 | En la línea de albarán la unidad es `uom_id` (no `product_uom_id`) y se compara con `uom_id.compare` (la unidad ya no tiene `rounding`) |

Ninguna de las de OCA está publicada en la rama 20.0 de OCA (a 14/10/2026). Son ports propios: conviene subirlos como PR `[20.0][MIG]` para no mantener copias.

## 4. Control de crédito en Odoo 20

**No hay que añadir funcionalidad.** El port de `account_financial_risk` y `sale_financial_risk` es equivalente al de OCA 19.0:

- **`account_financial_risk`:**
  - El grupo `group_account_financial_risk_user` se declara directamente en `groups` de `credit_limit`, en lugar de añadirse en `_setup_complete`. El efecto es el mismo.
  - `get_param` + `str2bool` pasan a `get_bool`.
  - Portal: `t-call` con el parámetro `partner=`.
- **`sale_financial_risk`:** `get_bool` y el redondeo con `uom.round()`.
- **Sin cambios funcionales:**
  - mismos campos de riesgo;
  - mismo asistente `partner.risk.exceeded.wiz`;
  - mismas sobrescrituras de `_post`, `_commercial_fields` y `payment.transaction`.

Cómo lo usa Mercas en dev20:

- **`mercas_base` (*Vender y Entregar*):** igual que en v19. Si existe `evaluate_risk_message` y la compañía no permite confirmar con riesgo excedido, abre el asistente estándar de OCA. Al continuar, confirma con `bypass_risk`.
- **`mercas_touch`:**
  - Muestra el riesgo y la deuda del cliente: insignia *Risk exceeded* y aviso en el modo venta.
  - `sell()` llama a `button_sold_and_sent()`. Si se excede el riesgo, devuelve la acción del asistente estándar, y el pedido queda como presupuesto hasta que un responsable de riesgo lo acepta.
  - Tiene test (`test_sell_over_risk`).

Detalle menor: el port de `account_financial_risk/views/portal_templates.xml` perdió la cabecera de copyright y licencia AGPL de Tecnativa. Hay que restaurarla.

**Excepción:** el riesgo en las **facturas** que se publican automáticamente no se gestiona bien. Hay que corregirlo, y viene ya de v19. Ver el apartado 7.

## 5. Pasos para migrar

1. **Migración del núcleo:** elegir la herramienta y confirmar que cubre la edición de la base de dev19:
   - upgrade.odoo.com, que requiere suscripción;
   - u OpenUpgrade 20, comprobando que esté disponible para los módulos usados.
   - Debe convertir `stock.scrap` a `stock.move` con `is_scrap`, `ir.model.access` a `ir.access`, los `uom_id` de `stock.move.line` y `purchase.order.line`, `tracking` de `none` a `False` y `company_type`.
2. **Comprobar los módulos instalados en la base de 19:** que estén los mismos que en dev20: `stock_restrict_lot`, `purchase_lot`, `sale_order_lot_selection`, los de riesgo, `chat_ai` y `odoo_mcp_manager`.
3. **Migrar una copia de la base** y actualizar todos los `mercas_*` y sus dependencias.
4. **Comprobar en la copia:**
   - **Desechos de v19:** aparecen en la pestaña *Scrap* del lote, y `scrap_kg` cuadra.
   - **Permisos:** no hay accesos duplicados de los asistentes (xmlids `access_*` con el mismo nombre).
   - **`mercas_ai`:** se conserva el parámetro `mercas_ai.custom_instructions`.
   - **Riesgo:** se conservan los límites de crédito y los ajustes de la compañía, como `allow_overrisk_sale_confirmation`.
5. **Pasar los tests y tours:** los de los `mercas_*`, `stock_restrict_lot`, `sale_order_lot_selection`, `purchase_lot` y los de riesgo.
6. **Decidir entre `mercas_keys` y `mercas_touch`.**
7. **Restaurar la cabecera de licencia** en `account_financial_risk/views/portal_templates.xml`.

## 6. Mejoras de dev20 que se podrían llevar a dev19

Si se retrasa la migración, se pueden pasar a dev19 sin cambios:

- `_mercas_validate()`;
- el `sudo()` de las ubicaciones técnicas;
- el dominio de provincia de origen en compras.

`mercas_touch` habría que reescribirlo en Owl 2 (`useState`/`onWillStart`, sin `useProps`, `signal` ni `usePlugin`).

## 7. Riesgo financiero en las facturas automáticas

*Revisado el 20/10/2026. **Corregido en dev20 el mismo día**, sin commit; ver «Corrección aplicada en dev20» al final del apartado. **En dev19 sigue pendiente.***

### Cómo funciona el aviso de riesgo en las facturas de OCA

En `account_financial_risk`, `account.move.action_post()` no publica las facturas de cliente (`out_invoice`) de un cliente que supera el riesgo cuando se cumplen dos condiciones:

- la compañía tiene desactivado *Allow invoice validation over the risk* (`allow_overrisk_invoice_validation`);
- no hay `bypass_risk` en el contexto.

En ese caso **devuelve la acción del asistente** `partner.risk.exceeded.wiz` en vez de publicar. Si quien llama ignora lo que devuelve, la factura se queda en borrador sin que nadie se entere.

El riesgo de la **venta** (`allow_overrisk_sale_confirmation`) es otra opción distinta. Además, `bypass_risk` solo se pasa a `action_confirm()`, no a la factura, así que aunque un responsable acepte el riesgo en la venta, la factura se vuelve a comprobar.

### Puntos afectados

| Dónde | Flujo | Qué pasa si se excede el riesgo de factura | Desde |
|---|---|---|---|
| `mercas_base/models/sale_order.py`, `_mercas_box_delivery_confirm_flow` (`invoice.action_post()`) | Entrega de cajas a proveedor: botón *Entregar y facturar* | Ignora la acción del asistente. Abre la factura, que sigue **en borrador**, sin avisar | v19 |
| Mismo método, llamado desde `_mercas_sold_and_sent_execute` | *Vender y Entregar* de un pedido que solo tiene cajas, en el backend y en el modo **F3 Cajas** de `mercas_touch` (`move_boxes`, dirección `deliver`) | `_mercas_sold_and_sent_execute` no devuelve nada, así que se pierde también la acción que abre la factura. La factura queda **en borrador sin ningún aviso** | v19 |
| `mercas_touch/models/mercas_touch.py`, `invoice_sale` (`invoices...action_post()`) | Botón *Facturar* tras una venta en Mostrador, para cobrarla | Ignora la acción. La factura queda en borrador y la pantalla da un error engañoso: *There is nothing to invoice in S…* Al reintentar pasa lo mismo, porque el pedido ya cuenta como facturado con la factura en borrador. Solo se puede publicar desde el backend | dev20 (nuevo) |

**No están afectados**, porque el riesgo de OCA solo se comprueba en las facturas de cliente (`out_invoice`):

- las facturas de proveedor de *Comprar y Recibir* y de la devolución de cajas (`purchase_order.py`);
- la liquidación de lotes (`stock_lot.py`, `in_invoice`);
- la compensación (`account_move.py`, asiento `entry`).

### Corrección propuesta

1. **`mercas_base`:**
   - En `_mercas_box_delivery_confirm_flow`, guardar lo que devuelve `invoice.action_post()`. Si es una acción (el asistente de riesgo), devolverla en lugar de la acción que abre la factura.
   - Hacer que `_mercas_sold_and_sent_execute` devuelva lo que devuelve `_mercas_box_delivery_confirm_flow`, para que *Vender y Entregar* y `mercas_touch` lo reciban.
   - **Hay que decidir** si, cuando un responsable ya ha aceptado el riesgo de la venta (`continue_method` del asistente), la factura se publica con `bypass_risk` para no pedir la aprobación dos veces. Recomendación:
     - sí, cuando venga de aceptar el asistente;
     - no, cuando la venta se confirmó sin pasar por el asistente, porque la compañía permite el riesgo en ventas pero no en facturas.
2. **`mercas_touch`:**
   - **`invoice_sale`:** si `action_post()` devuelve una acción, devolver `{'action': ...}` sin dar error, y que la pantalla abra el asistente igual que en `sell()`. Al cerrarlo, refrescar la factura y el pedido.
   - **`move_boxes` (entrega):** ya devuelve la acción de `button_sold_and_sent()` cuando es un diccionario. Con el cambio de `mercas_base` recibirá también el asistente de la factura. El problema es que, sin riesgo, recibiría además la acción que abre la factura, y no debe abrirla en la pantalla. Solo hay que pasar la acción cuando sea el asistente (`res_model == 'partner.risk.exceeded.wiz'`).
3. **Tests**, con `allow_overrisk_invoice_validation = False` y un cliente por encima del límite:
   - entrega de cajas desde el backend: se devuelve el asistente y la factura queda en borrador hasta continuar;
   - `mercas_touch.invoice_sale`: devuelve `action` y no da error;
   - `mercas_touch.move_boxes` en entrega: devuelve `action`.

Se puede corregir en dev19 (solo la parte de `mercas_base`) y en dev20 (`mercas_base` y `mercas_touch`).

### Corrección aplicada en dev20 (20/10/2026)

Se aplicó con la recomendación anterior.

**`mercas_base/models/sale_order.py`:**

- **`_mercas_box_delivery_confirm_flow`:** si `action_post()` devuelve el asistente de riesgo, lo devuelve en lugar de la acción que abre la factura.
- **`_mercas_sold_and_sent_execute`:** devuelve solo el asistente de riesgo de la factura, nunca la acción que abre la factura. Así *Vender y Entregar* y Mostrador siguen sin abrir la factura cuando no hay riesgo.
- **Nuevo `_mercas_is_risk_action(action)`.**
- **Sin doble aviso:** cuando un responsable acepta el riesgo de la venta, el asistente de OCA llama a `_mercas_sold_and_sent_execute` con `bypass_risk`. Ese contexto llega a la factura, que se publica sin volver a preguntar. Por eso no hace falta código adicional para esto.

**`mercas_touch/models/mercas_touch.py`:**

- **`invoice_sale`:**
  - crea la factura si hace falta;
  - publica las facturas en borrador del pedido;
  - si sale el asistente, devuelve `{'action', 'order'}` en vez de dar error.
  - Al reintentar, vuelve a pedir la aprobación sobre la misma factura en borrador, sin crear otra.
- **`_get_order_states`:** añade `invoice_draft`, que indica si la venta tiene una factura de cliente en borrador. Nuevo método `_get_draft_invoices`.
- **`get_drafts`:** el filtro `to_invoice` de ventas incluye también las que tienen una factura de cliente en borrador.

**`mercas_touch/static/src/touch_screen/`:**

- **`touch_screen.js`:** `onInvoiceSale` abre el asistente y, al cerrarlo, refresca el resumen del pedido.
- **`touch_screen.xml`:** el botón *Create invoice* también aparece cuando hay una factura en borrador (`done.invoice_draft`).
- La entrega de cajas (`move_boxes`) no ha necesitado cambios: ya abría la acción que recibe.

**Tests nuevos:**

- En `mercas_base/tests/test_mercas_box_orders.py`:
  - `test_sale_action_deliver_and_invoice_over_risk`;
  - `test_sale_button_sold_and_sent_box_order_over_risk`;
  - `test_sale_button_sold_and_sent_box_order_risk_accepted`.
- En `mercas_touch/tests/test_mercas_touch.py`:
  - `test_invoice_sale_over_risk`;
  - `test_boxes_deliver_over_risk`.

Resultado sobre la base nueva `test_mercas_risk` (con `mercas_touch` y `sale_financial_risk`): **48 tests, 0 fallos**. Son las clases `TestMercasBoxOrders` y `TestMercasTouch`. No se pasaron los tours ni los tests JS de hoot.

Para dev19 basta con llevar la parte de `mercas_base`, que es idéntica, con sus tres tests.

## 8. Mejoras de dev20 traídas a dev19 (22/10/2026)

Se han llevado a dev19 las mejoras de dev20 posteriores al port (`1dc2c11`, `cd6cfc4`, `ee98377`, `bbfcd04`) y las del propio port que no eran adaptación a Odoo 20.

- **`mercas_base`:**
  - `_mercas_validate()` (nuevo `models/stock_picking.py`), el `sudo()` de las ubicaciones técnicas y el dominio de provincia de origen en compras (apartado 6).
  - Riesgo financiero de las facturas automáticas de cajas, con sus tres tests (apartado 7).
  - Albarán del proveedor (`supplier_ref`) en las recepciones y recepciones en el autocompletar de la factura de proveedor (`purchase.bill.union`).
  - Calidad y calibre (`mercas_role` en los atributos): análisis de ventas, pestaña *Ventas* del lote y desglose de la liquidación.
- **`mercas_demo`:** categorías *Frutas* y *Verduras*, atributos de calidad y calibre, *Manzana granel* y README.
- **`mercas_touch`:** portado a Odoo 19 (versión 19.0.1.0.0).
- **`mercas_ai` y `mercas_keys`:** sin cambios. En dev20 solo tienen adaptaciones a Odoo 20 y tours de humo.

Diferencias con dev20 por la versión de Odoo:

- **`sale.report`:** usa `_select_additional_fields` (en Odoo 20, `_select_dict`).
- **`purchase.bill.union`:** en Odoo 19 la vista se crea en `init()`, no con `_table_sql`. Se envuelve la vista estándar (`pg_get_viewdef`) para añadir `mercas_receipts`, y `_depends` vacía a la base los campos de los albaranes antes de leerla. La lista heredada es `purchase.view_purchase_bill_union_tree`.
- **`mercas_touch`:**
  - En la pantalla, Owl 2: `useState`, `static props`, `useExternalListener` y los servicios `barcode` y `bus_service`.
  - Iconos de Font Awesome en lugar de los Material de Odoo 20.
  - Desechos con `stock.scrap` (`action_validate`).
  - La unidad de las líneas de compra es `product_uom_id`.

Resultado sobre la base nueva `test_mercas_touch19` (con `mercas_touch` y `sale_financial_risk`): tests de `mercas_base` y `mercas_touch`, **0 fallos y 0 errores**, sin tests saltados. No se pasaron los tours de `mercas_touch` porque falta `websocket-client` en `venv312`.

## 9. Facturación de compras, autofacturación y DeCA, llevados a dev20 (29/10/2026)

Cambios de dev19 posteriores a `05eb6dd` (último commit trasladado a dev20): el commit `c430804` (*mercas_touch_inv*: DeCA, transportista por defecto) y los cambios de la sesión del 29/10, aún sin commitear en ninguno de los dos repositorios. Se trasladaron con un parche (`git diff 05eb6dd` más los ficheros nuevos) y `patch -p1`; los bloques que no encajaron se resolvieron a mano.

**`mercas_base`:**

- **Factura estándar del pedido y facturación por lote:** `purchase.order.line._mercas_is_invoiced_from_lot`; `action_create_invoice` y `_add_purchase_order_lines` dejan fuera esas líneas y las secciones vacías; los lotes firmes sin facturas desde el lote van en la factura estándar con `mercas_is_firm_line`.
- **Cajas:** la primera factura del lote (firme, adelanto o liquidación) incluye las cajas pendientes (`_mercas_pending_box_invoice_lines`).
- **Aviso de líneas vacías:** `account.move._get_alerts` no cuenta secciones ni notas (mismo código en Odoo 20).
- **Autofacturación:** casilla y fecha de acuerdo en el proveedor, diario de autofacturas por compañía creado al instalar/actualizar (`data/mercas_self_billing_data.xml` → `res.company._mercas_setup_self_billing_journal`), diario por defecto según el proveedor (`_search_default_journal` y onchange), bloqueo al publicar, referencia = número (`_set_next_sequence`, antes de las comprobaciones del SII) y bloque de emisor/destinatario en el PDF (`report/report_invoice.xml`; la mención va fuera de la fila: wkhtmltopdf no parte filas de más de 12 columnas).
- **Optimización sin cambio de funcionalidad:** mixin `mercas.box.order.mixin` para las secciones y cajas de ventas y compras; en `stock.lot`, `_mercas_posted_net`, `_mercas_sale_move_lines`, `_mercas_scrap_move_lines` y `_mercas_confirmed_purchase_lines`; `sale.order.line._mercas_net_price`; `grouped()` en lugar de diccionarios a mano.

**`mercas_touch`:**

- Botones de facturación de la compra según lo pendiente (*Liquidar*, *Facturar adelanto*, *Factura firme*, *Crear factura de proveedor*), lista *Facturas* (siempre desplegada, se recarga al cerrar el diálogo de la factura) con impresión de las publicadas y borrado de los borradores.
- DeCA (de `c430804`): depende de `l10n_es_deca_oca`.
- `_browse_order` y `are_record_ids` para las comprobaciones repetidas.

**Diferencias resueltas a mano en dev20:**

- Manifiestos: el XML de datos va antes de `security/ir.access.csv`; `l10n_es_deca_oca` en `depends` de `mercas_touch` (existe la 20.0.1.0.0 en dev20).
- Pantalla: iconos Material (`<i class="oi" data-icon="…"/>`: `receipt_long`, `description`, `print`, `delete`, `local_shipping`) en lugar de Font Awesome.
- `escape_psql` → `escape_like_value` en `mercas_touch` (obsoleto desde Odoo 20; ya estaba antes del traslado).
- No hacen falta permisos nuevos: el mixin es abstracto.

**Resultado:**

- dev19, base `test_mercas_touch19`: `mercas_base` + `mercas_touch`, 100 tests, 0 fallos.
- dev20, base `test_mercas_touch20` (con `venv312`; instala `l10n_es_deca_oca`): 101 tests, 0 fallos; tras el cambio de `escape_like_value`, `mercas_touch` 38 tests, 0 fallos.
- Tours sin pasar en ninguna de las dos (falta `websocket-client`).

**Pendiente:**

- Commitear en dev19 y dev20.
- Pasar los tours instalando `websocket-client` en los entornos.
- Comprobar en el servidor (Linux) que el PDF no pierde las negritas: en el Mac, wkhtmltopdf 0.12.6 las pierde al azar (1 de cada 5 aprox.), también lanzado a mano y sin Odoo.
- La insignia y el filtro *Para facturar* de las compras siguen el `invoice_status` estándar: en compras con lotes por liquidación no desaparece aunque los lotes estén facturados.
- `mercas_ai`, `mercas_demo` y `mercas_keys` no cambian en esta sesión.

## 10. Inventario del lote y detalle del lote en el táctil, llevados a dev20 (16/11/2026)

Commits `8a0e420` y siguiente de dev19, trasladados con `git show 8a0e420` + `patch -p1`.

- **`mercas_base`:** botón **Inventario** en el formulario del lote (asistente `stock.lot.inventory.wizard`, `stock.lot._mercas_apply_inventory`: ajuste de inventario estándar con `stock.quant` en modo inventario).
- **`mercas_touch`:** botón **Detalle** en las tarjetas de F4 (form del lote en diálogo) y aviso `lots_changed` tras un inventario (`models/stock_lot.py`).

Diferencias resueltas a mano en dev20:

- Permiso en `security/ir.access.csv` (formato de Odoo 20: `model_id` por nombre, `operation` = `crud`).
- `i18n/es.po` de `mercas_base`: entradas nuevas añadidas al final a mano (el final del fichero difiere).
- Icono Material `info` en lugar de `fa-info-circle`.
- Redondeo con `uom.is_zero`/`uom.compare` (Odoo 20 no tiene `uom.uom.rounding`); mismo código en dev19.

Resultado: `mercas_base` + `mercas_touch` en `test_mercas_touch19` (105 tests) y `test_mercas_touch20` (108 tests, base creada de nuevo): solo fallan los 6 de `TestSelfBilling`. Ocurre en bases recién creadas: el diario de autofacturas se crea al instalar `mercas_base`, antes de que Odoo cargue el plan contable. No tiene relación con este cambio.

## 11. Búsqueda de tipos de caja en el táctil, llevada a dev20 (16/11/2026)

Commit de dev19 posterior a `5e05b44` («mercas_touch: búsqueda de tipos de caja»), trasladado con `git diff -- mercas_touch` + `patch -p1`, sin rechazos.

- **Línea de venta/compra:** el `<select>` de la caja pasa a ser un buscador: se escribe para filtrar (referencia interna, nombre o código de barras) y se elige entre los resultados (máx. 50 a la vez). Escape cierra la lista; la «×» deja la línea sin caja.
- **Pestaña Cajas (F3):** buscador sobre las tarjetas; las cajas con cantidad puesta no se ocultan y las del saldo del cliente/proveedor van primero.
- **`get_screen_data`:** carga siempre todas las cajas, fuera del límite de `PRODUCT_LIMIT`.

Diferencias resueltas a mano en dev20: iconos Material `search` y `close` en lugar de `fa-search` y `fa-times`.

Resultado: `mercas_touch` en `test_mercas_touch19` y `test_mercas_touch20`: 39 tests, 0 fallos (tours saltados: falta `websocket-client`).

## 12. Aviso de líneas de compra facturadas desde su lote y extensión del asistente de etiquetas, llevados a dev20 (17/11/2026)

Commits `47c1ab3` y `648f7ee` de dev19, trasladados con `git diff 0edcea0 648f7ee -- mercas_base mercas_touch` + `patch -p1`, sin rechazos.

- **`mercas_base`:** `purchase.order._mercas_lot_settlement_lines()` y aviso `mercas_lot_settlement_lines` en `account.move._get_alerts` (factura de proveedor): las líneas con lote que la factura estándar deja fuera, con botón «Ver los lotes».
- **`mercas_touch`:** `settlement_lines` en el resultado de la compra y recuadro de aviso en la pantalla de resultado.
- **`mercas_base`:** `mercas.label.print.wizard._get_report_xmlid()`, para que un módulo de cliente añada formatos de etiqueta (p. ej. `custom_maripili`, que no se ha llevado a dev20).

Diferencias resueltas a mano en dev20:

- `purchase.order.line.uom_id` en lugar de `product_uom_id` (aviso de la factura y `settlement_lines`).
- `patch` dejó copias `.orig` y sobrescribió `mercas_touch/static/src/touch_screen/touch_screen.xml.orig`, que está versionado en dev20: restaurado con `git checkout`.

Resultado: `mercas_base` + `mercas_touch` en `test_mercas_touch19` y `test_mercas_touch20`: 106 tests, 0 fallos.

## 13. Precio propuesto estándar en el táctil, llevado a dev20 (18/11/2026)

Commit `e70e2c4` de dev19, trasladado con `git show e70e2c4 -- mercas_touch` + `patch -p1`.

- **`mercas_touch`:** `get_line_price(kind, partner_id, product_id, qty, attribute_value_ids)` calcula el precio de una línea de pedido nueva (`new()`) como el backend: en compras, tarifa del proveedor para la cantidad o, si no hay, coste; en ventas, tarifa del cliente con el extra de los atributos o, si no hay, precio de venta. Neto del descuento de la línea. La pantalla lo pide al abrir el producto y otra vez al añadir si han cambiado la cantidad o los atributos; el precio tecleado a mano se respeta. En compras, las tarjetas de producto ya no muestran el precio de venta.

Diferencias resueltas a mano en dev20:

- Importación de `float_round`: en dev20 la línea anterior importa `escape_like_value` en lugar de `escape_psql`.
- Tarjeta de producto: icono Material `barcode` en lugar de `fa-barcode`.

Resultado: `mercas_touch` en `test_mercas_touch19` y `test_mercas_touch20`: 45 tests, 0 fallos (tours saltados: falta `websocket-client`).

## 14. Facturación firme por defecto, comentarios de la venta y envío por correo, llevados a dev20 (18/11/2026)

Commits `0bc2c77`, `81bcb9f` y `0091113` de dev19, trasladados con `git diff a78c9fe 81bcb9f -- mercas_base mercas_touch` + `patch -p1` (y `0091113` a mano).

- **`mercas_base`:** opción *Facturación firme* en la compañía, valor por defecto de los contactos nuevos; `mercas_firm_negotiation` es campo comercial (oculto en contactos hijos y sincronizado con su empresa, también desmarcado); la línea de compra toma el valor de la empresa del proveedor. Migración que alinea los contactos existentes.
- **`mercas_base`:** campo *Comentarios* del pedido de venta (`mercas_comment`), impreso en pedido, albarán y factura (`report/report_comment.xml`); `account.move.mercas_comment` calculado desde los pedidos facturados; bloqueado cuando una factura se ha enviado o tiene su PDF guardado.
- **`mercas_touch`:** comentarios en la pantalla de la venta (`set_sale_comment`) y *Enviar por correo* (`send_sale_documents`): factura al contacto de facturación con el envío estándar; albarán y DeCA al de entrega con la plantilla `mail_template_delivery_documents`; un solo correo si coinciden las direcciones.

Diferencias resueltas a mano en dev20:

- Versión `20.0.1.0.1` y migración en `migrations/20.0.1.0.1` (en dev19, `19.0.1.0.1`).
- Iconos Material `check`, `send` y `mail` en lugar de `fa-check`, `fa-paper-plane` y `fa-envelope`.
- `account.move.send._get_default_sending_settings` en Odoo 20 suma `sending_methods` con una lista: se pasan como lista (`['email']`), también en dev19 (`0091113`).

Resultado: `mercas_base` + `mercas_touch` en `test_mercas_touch19` (112 tests) y `test_mercas_touch20` (115 tests): 0 fallos. Plantilla de correo traducida al español en las dos.

## 15. Palets y packing list, impresión unificada, mercancía de mercado y sin migraciones, llevados a dev20 (19/11/2026)

Commits `fc4bfae` y `9978257` de dev19, trasladados con `git diff 0091113 9978257 -- mercas_base mercas_touch mercas_demo` + `patch -p1`.

- **`mercas_base`:** palets de la venta (`mercas.sale.pallet`/`mercas.sale.pallet.line`), cada palet como paquete del albarán al entregar y corrección después de vender (`stock.move.line._mercas_apply_pallets_to_move`); tipos de paquete con *Palet* y *Producto envase*; línea de europalets retornables; informe *Packing list* (venta y albarán); opción *Paquetes* activada al instalar; categoría *Mercancía de mercado* (`product.category.is_merca`).
- **`mercas_touch`:** botón *Palets* (rápido y gráfico, también tras vender); botón único *Imprimir* (albarán, DeCA, packing list y factura en un PDF, informe `action_report_sale_documents`); catálogo solo con las categorías de mercancía de mercado.
- **`mercas_demo`:** europalet, tipos de caja y palet, compra recibida con lotes y presupuesto *Demo palets*; *Envases* no es mercancía de mercado.
- **Sin migraciones:** se instala todo de nuevo, así que se quitan los `migrations/` de `mercas_base` (en dev20, `20.0.1.0.1`) y no se crean otros.

Diferencias resueltas a mano en dev20:

- Versiones `20.0.1.0.3` (`mercas_base`) y `20.0.1.0.1` (`mercas_demo`).
- Permisos de los palets en `security/ir.access.csv` (formato de Odoo 20).
- `stock.move.line.uom_id` en lugar de `product_uom_id` al repartir las líneas del albarán entre palets.
- Sin `report_file` en los informes nuevos (packing list y documentos de la venta).
- `tracking` `False` en lugar de `none` en el europalet de la demo.
- Pantalla táctil: botones *Imprimir* y *Palets* del resultado puestos a mano (rechazo del parche) e iconos Material (`grid_view`, `warning`, `add`, `remove`, `shuffle`, `delete`, `arrow_downward`, `check`, `print`) en lugar de los `fa-*`.

Resultado: `test_mercas_touch20` actualizada (151 tests): solo falla `test_packages_enabled`, porque *Paquetes* se activa al instalar y esa base venía de antes (activado a mano después). Instalación limpia de `mercas_demo` + `mercas_touch` en `test_mercas_pallet_demo20`: *Paquetes* activo, presupuesto *Demo palets* vendido con sus palets (`PAL0000001`, `PALD0000001`), documentos de impresión y packing list correctos; los 10 tests de palets, impresión y catálogo pasan.

## 16. Calculadora en el teclado numérico y operaciones en los campos decimales, llevados a dev20 (20/11/2026)

Commit de dev19 con el mismo título, trasladado con `git diff -- mercas_touch` (antes del commit) + `patch -p1`.

- **Teclado numérico:** columna de operadores (÷ × − +) y tecla `=`; el campo guarda la operación (`12,5×3`) y se calcula con `=` o al confirmar; multiplicación y división primero. Los operadores se desactivan (no se ocultan) en los campos de cajas, y en el teclado de palets no se muestran (`calculator="false"`). Cuatro columnas de 3,5 a 5 rem para no desbordar en pantallas estrechas.
- **Campos decimales** (cantidad y precio de la línea, precio del ticket, altura del palet, cantidad a desechar e importe a cobrar): una operación escrita con el teclado (`50*2-3`, `12,5x3`) se sustituye por su resultado al pulsar Intro o salir del campo; también se admite el `=` de Odoo (`=(2+3)^2`), que calcula el parser estándar (`parseFloat`).

Diferencias resueltas a mano en dev20:

- Props del teclado con `useProps` y `t.boolean().optional(true)` (Owl 3).
- Icono Material `backspace` en la tecla de borrar.
- `patch` sobrescribe los `touch_screen.js.orig`/`touch_screen.xml.orig` que están versionados en dev20: hay que restaurarlos con `git checkout HEAD --` después del parche.

Resultado: `mercas_touch` en `test_mercas_touch19` y `test_mercas_touch20`: 46 tests, 0 fallos (tours saltados: falta `websocket-client`). dev20 sin commit (junto con el apartado 15).

## 17. Pesos (bruto, tara, neto), envases aparte, facturar compras solo administradores y packing list del albarán, llevados a dev20 (20/11/2026)

Commit de dev19 con el mismo título, trasladado con `git diff HEAD -- mercas_base mercas_demo mercas_touch` (antes del commit, con los ficheros nuevos marcados con `git add -N`) + `patch -p1`.

- **Pesos por línea:** mixin `mercas.weighed.line.mixin` (tara = cajas × peso del producto envase, bruto con inverso que fija el neto) en las líneas de venta y compra; cajas y tara en la línea de factura; columnas Cajas · Bruto · Tara · Neto en factura, albarán (valorado, con totales y tara de palets), pedido de venta, pedido de compra y solicitud de presupuesto; envases en tabla aparte en factura y albarán. Campo **Bruto** en `mercas_touch`. En las listas de pedido, bruto y tara con `optional="hide"`.
- **Dependencias nuevas de `mercas_base`:** `sale_management` y `stock_picking_report_valued` (port propio a dev20, ver apartado 3).
- **Packing list del albarán:** nombre de informe propio (`report_mercas_packing_list_picking`); con el mismo que el del pedido, al imprimir desde el navegador se leían los ids de albarán como pedidos.
- **`mercas_touch`:** facturar las compras (crear factura, liquidar, adelanto, firme) solo para `account.group_account_manager`, en botones y en el servidor.
- **Demo:** peso en los envases (Caja1 0,5, Caja2 0,8, Europalet 25 kg); fuera los tipos de paquete de caja.

Diferencias resueltas a mano en dev20:

- Rechazos del parche: `report_name` del packing list del albarán (dev20 no tiene `report_file`) y el `t-if` de los botones de facturar de F4 (el botón *Etiquetas* lleva icono Material).
- La línea de compra tiene `uom_id` en vez de `product_uom_id`: el mixin de pesos lleva `_mercas_uom_field` (por defecto `product_uom_id`, `uom_id` en la compra).
- La línea de albarán también usa `uom_id`: `_mercas_delivery_weights` y el port de `stock_picking_report_valued`.
- Copias `.orig` sin versionar que deja `patch`, borradas; los `touch_screen.{js,xml}.orig` versionados, restaurados con `git checkout HEAD --`.

Resultado: dev19 `test_mercas_touch19`, 133 tests de `mercas_base` y `mercas_touch`, 0 fallos. dev20 `test_mercas_touch20`, 139 tests (con los de `stock_picking_report_valued`), 0 fallos. Tours saltados (falta `websocket-client`). Commiteado en dev20 como `a23eea7`, junto con los apartados 15 y 16.

## 18. Resolución especial para móvil, cajas y total en gris y pesos brutos en la demo, llevados a dev20 (23/11/2026)

Commit de dev19 `66d7f31`, trasladado con `git diff ad957a0 66d7f31 -- 'mercas_*'` + `patch -p1`.

- **`mercas_touch`:** con el ticket debajo de los productos (menos de 992 px, `ui.size < SIZES.LG`), barra fija al pie con *Ocultar / Ver productos*, cajas, total y los botones del pedido (plantilla `TouchScreenOrderActions`, con la etiqueta *Palets*); en el móvil (menos de 768 px, `ui.isSmall`), sin teclado numérico en pantalla y con el teclado del sistema en el precio rápido y en *Cajas a mover*. Cajas y total del ticket sobre gris (`o_mercas_touch_summary`) en todas las resoluciones. Todo marcado *Resolución especial para móvil*.
- **Demo:** pesos brutos de báscula en la compra y la venta de palets.

Diferencias resueltas a mano en dev20:

- Rechazos del parche: los botones del pedido (`TouchScreenOrderActions`) y el campo *Cajas a mover*, por los iconos Material; también los iconos nuevos (`visibility`, `visibility_off`, `add`).
- Owl 3: `proxy(useService("ui"))` en vez de `useState`; `SIZES` se importa de `@web/core/ui/ui_utils` (en 20 no hay `ui_service.js`).
- `touch_screen.{js,xml}.orig` versionados, restaurados con `git checkout HEAD --`.

Resultado: dev20 `test_mercas_touch20`, 48 tests de `mercas_touch`, 0 fallos (tours saltados). Demo reinstalada en dev19 (`test_mercas_demo_pesos19`) con los pesos esperados. Commiteado en dev20 como `7c192b1`.

## 19. Cajas devueltas como saldo a favor o pagadas, y saldo a favor en Cobros, llevados a dev20 (23/11/2026)

Commit de dev19 `0f90bff`, trasladado con `git diff 66d7f31 0f90bff -- mercas_touch` + `patch -p1` (sin rechazos).

- **`mercas_touch`:** al devolver cajas un cliente (F3) se elige *Saldo para próximas facturas* (`action_compensate` de `mercas_base`, con el diario de compensación de la compañía) o *Pagar ahora* (caja o banco); en Cobros (F5), el saldo a favor del cliente se aplica primero a las facturas marcadas y se cobra el resto.

Diferencias resueltas a mano en dev20: iconos Material en los botones nuevos (`swap_horiz`, `payments`, `account_balance`); copias `.orig` y `.rej` sin versionar que deja `patch`, borradas; `touch_screen.{js,xml}.orig` versionados, restaurados.

Resultado: dev19 y dev20, 50 tests de `mercas_touch` cada uno, 0 fallos (tours saltados). Commiteado en dev20 como `61fe9b0`.

## 20. Devolución de cajas compensada en la demo, llevada a dev20 (23/11/2026)

Commit de dev19 `dac7fc6`, trasladado con `git diff 0f90bff dac7fc6 -- mercas_demo` + `patch -p1` (sin rechazos ni cambios).

- **Demo:** venta **Demo cajas compensadas** de *Cliente2* (facturada, pendiente de cobro) y la devolución de sus 4 *Caja2* compensada: 2,00 € de saldo a favor para *Cobros* (F5). El diario de compensación, los impuestos y los dos pedidos de demo se crean tras cargar el plan contable (`registry._auto_install_template`, igual en 19 y 20): en una base de datos nueva el plan contable se carga después del hook.

Resultado: instalación desde cero en dev19 (`test_mercas_demo_pesos19`) y dev20 (`test_mercas_demo20`): factura de 44,35 € y saldo a favor de 2,00 € en las dos. Commiteado en dev20 como `b49b151`.

## 21. README de `mercas_base`, `mercas_touch` y `mercas_demo`, llevados a dev20 (23/11/2026)

Solo documentación. Cada commit de dev19 se trasladó con `git diff <commit>~1 <commit> -- <módulo>/README.md` + `patch -p1` (sin rechazos):

| Módulo | dev19 | dev20 | Qué se añade |
|---|---|---|---|
| `mercas_base` | `4e10b2c` | `b0cc248` | Bruto y tara como columnas opcionales ocultas; saldo de la devolución de envases (compensar o pagar); saldo a favor en *Cobros* del táctil; peso del producto caja como tara. |
| `mercas_touch` | `5907530` | `971e1a1` | Importe de las cajas y saldo a favor en el resumen de modos; F5 (y Ctrl/Mayús+F5) abre *Cobros* sin recargar; métodos del servidor y tests que faltaban. |
| `mercas_demo` | `52a75ca` | `4eeb6aa` | Tabla de precios; 2,00 € de saldo de las cajas compensadas; cuándo se crean los pedidos de demo. En dev20 dice «igual en Odoo 19» en lugar de «igual en Odoo 20». |

## 22. Resumen de un pedido sin factura, llevado a dev20 (23/11/2026)

Commit de dev19 `79f45c6` (solo la parte de `mercas_touch`; el borrado de `sale_order_lot_selection` del mismo commit no se lleva: dev20 tiene su propia versión portada), aplicado a mano en dev20 (dos líneas, mismo código en las dos versiones).

- **Táctil:** `_get_last_invoice` devuelve `False` cuando el pedido no tiene factura publicada. Antes devolvía un recordset vacío, que llegaba a la pantalla como `[]` (verdadero en JS): el resumen de una venta sin facturar mostraba «Factura : 0 € por cobrar» y el botón *Cobrar*.
- **Test:** `test_draft_filters_and_summary` exige `assertIs(summary['invoice'], False)`; el `assertFalse` anterior aceptaba el recordset vacío.

Resultado: 50 tests de `mercas_touch` en verde en dev19 (`test_mercas_touch19`) y dev20 (`test_mercas_touch20`). En las dos versiones, la primera ejecución sobre una base recién instalada (`-i`) da un fallo en `test_pallets` que no se repite al volver a pasar los tests con `-u`, y que no depende de este cambio. Commiteado en dev20 como `813b578`.

## 23. Cuadro de mandos del Mostrador y resumen de Dirección, llevados a dev20 (23/11/2026)

Commits de dev19 `11523fa`, `615e816` y `e90761c`, trasladados con `git diff 79f45c6 e90761c -- mercas_base mercas_touch` (sin `mercas_base.pot` ni `ir.model.access.csv`) + `patch -p1`. Los rechazos (versión del manifiesto, import de `html2plaintext`, botón y columnas del inicio) se resolvieron a mano. Cambios propios de Odoo 20:

| Qué | dev19 | dev20 |
|---|---|---|
| Unidad de la línea de compra | `product_uom_id` | `uom_id` |
| Mermas del resumen | `stock.scrap` (`scrap_qty`, `date_done`) | `stock.move` con `is_scrap` (`quantity`, `date`, `uom_id`) |
| Gráficos de Dirección | `useRef`/`useEffect` y `loadBundle` | `useChart` (`@web/core/utils/chart_hook`), `useProps`, `t-ref="this.<x>Chart.ref"` y `this.` en la plantilla |
| Barras del resumen (QWeb) | `t-call` con `t-set` dentro | `t-call` con los parámetros como atributos (la plantilla llamada no ve las variables de quien llama) |
| Iconos del panel del Mostrador | Font Awesome | Material (`oi` + `data-icon`) |
| Acceso del modelo | `ir.model.access.csv` | `security/ir.access.csv` |

Resultado: en dev20 (`test_mercas_touch20`), 151 tests de `mercas_base` y `mercas_touch` con solo 2 errores, los de las barras del resumen (`KeyError: 'bar_data'`). Tras arreglar el `t-call`, los 10 tests del resumen pasan; la batería completa no se ha vuelto a pasar. Gráficos y panel revisados en el navegador. Commiteado en dev20 como `31d245a`.

## 24. Panel del Mostrador en el móvil, llevado a dev20 (23/11/2026)

Commit de dev19 `a0a7636`, trasladado con `git diff a864b76 a0a7636 -- mercas_touch` + `patch -p1`. El hunk de la cabecera de Mensajes se rechazó (en dev20 el icono es Material) y se aplicó a mano.

- **Estilos:** las columnas del inicio llevan `min-width: 0`. Sin él, los textos recortados (`text-truncate`, sin salto de línea) fijaban el ancho mínimo del panel, que a ~375 px medía 423 px y se cortaba por los dos lados.
- **Plantilla:** la etiqueta de caducidad de los lotes no se encoge (`flex-shrink-0`) y la cabecera de Mensajes parte línea (`flex-wrap`).

Solo cambian CSS y plantilla, así que no se han pasado tests. Revisado en el navegador en dev19 a 375 y 320 px; en dev20 no se ha comprobado en el navegador. Commiteado en dev20 como `74e5ce6`.

## 25. Precio de venta del lote, origen del proveedor y teclado numérico por usuario, llevados a dev20 (24/11/2026)

Commit de dev19 `e4ac8d8`, trasladado con `git diff 0672011 e4ac8d8 -- mercas_base mercas_touch` + `patch -p1`. Un solo hunk rechazado (las cajas a mover entre palets, con iconos Material en dev20), aplicado a mano.

Qué trae: productos con lote para vender en el catálogo de venta; origen por defecto del proveedor en las compras; coma decimal en la tecla del bloque numérico; precio de venta del lote como base de la tarifa (compra, F4 · Lotes, precio propuesto); teclado numérico en pantalla según la preferencia del usuario, con ticket a media pantalla y líneas compactas sin él; y el arreglo de la impresión de los documentos de la venta desde el navegador.

| Qué | dev19 | dev20 |
|---|---|---|
| Preferencia que el usuario cambia de sí mismo | `SELF_READABLE_FIELDS` / `SELF_WRITEABLE_FIELDS` | `user_writeable=True` en el campo |
| `sale.order.line.lot_id` | `precompute=True` (módulo OCA) | La copia propia de `sale_order_lot_selection` no lo tenía: se añade. Sin él, el precio (que ahora depende del lote) no se precalcula y la línea se inserta con `price_unit` nulo |
| Reglas de tarifa en los tests | `percentage` (`percent_price`) y `formula` | `discount` (`price_discount`, con `price_surcharge`) |
| Icono del botón de precio en F4 | Font Awesome `fa-eur` | Material `euro` |

Resultado: en dev20 (`test_mercas_touch20`), 168 tests de `sale_order_lot_selection`, `mercas_base` y `mercas_touch` sin fallos (los tours se saltan: falta `websocket-client`); el bundle de JS y CSS compila. En dev19, 161 tests con los mismos 7 errores previos de `TestStockLotChangeWizard`, y los tours en verde. No revisado en el navegador en dev20. Commiteado en dev20 como `0dba18e`.

## 26. Tableros de Mercas (mercas_dashboard), llevados a dev20 (25/11/2026)

Commits de dev19 `b84b6f1` (menú de Dirección en Tableros) y `07f1c97` (módulo `mercas_dashboard` y retirada de la pantalla Dirección de `mercas_base`), trasladados con `git diff e4ac8d8 07f1c97 -- mercas_base mercas_dashboard` (sin `mercas_base.pot`) + `patch -p1`. Los únicos rechazos fueron los del widget de gráficos de Dirección, que en dev20 es distinto (Owl 3) y se borra entero. El borrado de las copias de OCA spreadsheet de dev19 (`6b02f09`) no se lleva: dev20 no las tiene y OCA aún no tiene rama 20.0.

| Qué | dev19 | dev20 |
|---|---|---|
| Vista SQL de los informes | `_table_query` | `_table_sql`, entre paréntesis |
| Mermas | `stock.scrap` (`scrap_qty`, `product_uom_id`, `date_done`, `lot_id`) | `stock.move` con `is_scrap` (`quantity`, `uom_id`, `date`; el lote, el de su primera línea) |
| Unidad de la línea de compra | `product_uom_id` | `uom_id` |
| Cobros | estados `in_process` y `paid` | `paid` y `reconciled` (no hay `in_process`); arreglado también el resumen por correo de dev20, que se dejaba los conciliados |
| Permisos | `ir.model.access.csv` | `security/ir.access.csv` (operación `r`) |
| Editar las hojas en Odoo | `spreadsheet_dashboard_oca` (repositorio `19spreadsheet`) | No hay: se cambian en el generador |

Las hojas JSON son las mismas (formato 18.5.10, que Odoo 20 actualiza al abrirlas). `mercas_base.pot` se regeneró en cada versión: con la plantilla vieja, Odoo descartaba al cargar las traducciones nuevas del `es.po`.

Resultado: en dev20 (`test_mercas_touch20`), 108 tests de `mercas_base` y `mercas_dashboard` sin fallos; los tres tableros se abren en el navegador sin errores (base de test, en inglés y sin datos). En dev19, 167 tests con los 7 errores previos de `TestStockLotChangeWizard`, y los tableros revisados en el navegador sobre una copia de `mercas` con 15 meses de historial de prueba. Commiteado en dev20 como `fad2744`.

## 27. Informes de Dirección solo de familias Mercancía de mercado, con las cajas aparte (25/11/2026)

Commit de dev19 `ba551f1`, trasladado con `git diff 376f97e ba551f1 -- mercas_base mercas_dashboard` + `patch -p1`. Rechazados y aplicados a mano: la consulta de `mercas.report.goods` (en dev20 con `_table_sql`, `uom_id` en la compra y las mermas en `stock.move`) y el filtro de familias en las mermas del resumen por correo (en dev20, `stock.move` con `is_scrap`).

Qué trae: los tableros y el resumen por correo cuentan solo los productos de familias *Mercancía de mercado* (`is_merca`, o sin familia); las cajas (`is_box`) van aparte, en tablas propias (vendidas o entregadas; compradas o devueltas); los productos de otras familias no entran. Nota en la cabecera de los tableros y del correo.

Resultado: dev20 (`test_mercas_touch20`), 108 tests de `mercas_base` y `mercas_dashboard` sin fallos; dev19, 167 tests con los 7 errores previos de `TestStockLotChangeWizard`, y revisado en el navegador sobre `mercas_dash`. Commiteado en dev20 como `35c51fc`.

## 28. Intro pasa al campo siguiente de la línea, llevado a dev20 (25/11/2026)

Commit de dev19 `fcbca71`, trasladado con `git diff 60afa07 fcbca71 -- mercas_touch` + `patch -p1`, sin rechazos (mismo código en las dos versiones).

Resultado: 61 tests de `mercas_touch` sin fallos en dev20 y dev19, pero **los tours no se ejecutan en ninguna de las dos**: ni `venv312` ni el `python3` del sistema tienen `websocket-client`, y Odoo los salta. Probado a mano en el navegador en dev19 (copia `mercas_dash`): bruto `5*2` → 10, neto, precio, cajas, Mayús+Intro vuelve, e Intro en las cajas añade la línea. En dev20 solo se ha comprobado que el bundle compila. Commiteado en dev20 como `28b0d23`.

## 29. Intro en las cajas pasa al tipo de caja, llevado a dev20 (25/11/2026)

Commit de dev19 `c23d1ea`, trasladado con su `git diff` + `patch -p1`, sin rechazos. 61 tests de `mercas_touch` sin fallos en las dos versiones (los tours, saltados: falta `websocket-client`). Probado a mano en el navegador en dev19. Commiteado en dev20 como `67a0427`.

## 30. Tours ejecutados por primera vez, arreglos llevados a dev20 (25/11/2026)

Instalado `websocket-client` en `venv312`: hasta ahora los tours se saltaban en 19 y en 20 (Odoo lo registra como *skipped*). En la base de test de 19 se desinstaló `export_delete_login_log` (19cybro): consultaba la IP en internet al iniciar sesión y los tests bloquean las peticiones externas.

Al ejecutarlos salieron: un error en consola al añadir la línea con Intro desde el tipo de caja y otro al cerrar con Intro el cambio rápido de precios; un salto a una venta nueva del cliente al volver a la lista tras facturar (`reloadPartner` tardío, visible en 20); y dos tours que dependían de que la base no tuviera otros pedidos o de la velocidad. dev19 `17f08a8` y `61d9784`, dev20 `d5bf0d0`.

Resultado: dev19 (`test_mercas_touch19`), 168 tests de `mercas_base`, `mercas_touch` y `mercas_dashboard`, tours incluidos, con solo los 7 errores previos de `TestStockLotChangeWizard` (en 20 pasan). dev20 (`test_mercas_touch20`), 175 tests de los mismos módulos y `sale_order_lot_selection`, sin fallos. Un fallo suelto de `test_to_invoice` en una ejecución completa de 19 no se repitió en tres ejecuciones más.
