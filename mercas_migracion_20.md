# Mercas — migración de Odoo 19 (dev19) a Odoo 20 (dev20)

Revisión del código portado en `dev20` frente a `dev19`, para retomar la migración más adelante. Complementa la sección 6 de `mercas_next.md`.

*Revisado el 20/10/2026. No se ha ejecutado ninguna migración ni test: es una revisión del código.*

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
- **Provincia de origen en las líneas de compra:** dominio `mercas_origin` cuando el pedido tiene activo `mercas_origin_filter`.

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
