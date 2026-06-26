# Análisis y diseño — Solución Mercas en Odoo 19

---

# PARTE 1 — OBJETIVOS

---

## 1. Necesidad y contexto

**Entorno:** mercado mayorista de frutas (mercas). El operario trabaja a alta velocidad con múltiples tipos de documento (ventas, compras, facturas, pagos) y necesita cambiar entre ellos con la mínima fricción.

**Requisitos principales:**

- Venta de fruta por kg con posibilidad de indicar el número de cajas que se lleva el cliente en la misma línea de venta.
- Cobro de una **fianza por caja** (p.ej. 1 €/caja, sin IVA) que se abona automáticamente cuando el cliente devuelve las cajas. Las devoluciones pueden ser parciales, mezcladas de distintos pedidos y sin límite superior.
- **Compras a proveedor** con asignación de lote en el momento de la recepción. Si no se indica lote, el sistema asigna uno automáticamente.
- Interfaz rápida: teclas de función o botones visibles para cambiar de modo sin pasar por los menús generales de Odoo.
- Los pagos son estándar Odoo (no requieren desarrollo).

**Dos soluciones planteadas:**

| Solución | Módulo | Descripción |
|---|---|---|
| Backend unificado | `mercas_unified_screen` | Pantalla única en el backend con F1-F5 para cambiar entre ventas, compras, facturas y pagos |
| TPV (POS) | `mercas_pos_purchase` + `mercas_box_deposit` | Flujo completo en el TPV, incluyendo compras con lotes y fianza de cajas mediante popup |

Ambas soluciones comparten el módulo de fianza de cajas (`mercas_box_deposit`).

## 2. Estimación global

| Módulo | Contenido | Estimación |
|---|---|---|
| `mercas_box_deposit` | Campos en `product.template` y `sale.order.line`, onchange, línea fianza automática, sección en factura, wizard devolución, integración TPV | 2 días |
| `mercas_unified_screen` | Componente OWL pantalla unificada, hotkeys F1-F5, modos con `<View>` embebida, breadcrumb de retorno | 1-2 días |
| `mercas_pos_purchase` | Pedido de compra desde TPV, lotes en recepción inmediata, auto-asignación de lote, validación albarán | 1 día |
| Pruebas y ajustes | Integración entre módulos, casos extremos | 1 día |
| **Total** | | **5-6 días** |

## 3. Odoo Community vs Enterprise para este proyecto

### Conclusión directa

**Odoo Community es suficiente para la totalidad del proyecto.** Ninguno de los tres módulos custom depende de código Enterprise y las funcionalidades Enterprise analizadas no forman parte de los requisitos.

### Los módulos base del proyecto son todos Community

| Módulo estándar | Edición | Uso en el proyecto |
|---|---|---|
| `point_of_sale` | Community | TPV base, lotes, sincronización entre terminales |
| `sale` | Community | Pedidos de venta, fianza de cajas en backend |
| `purchase` | Community | Pedidos de compra |
| `purchase_stock` | Community | Albarán de recepción al confirmar compra |
| `account` | Community | Facturas, pagos, notas de crédito |
| `stock` | Community | Lotes, movimientos de stock |

### El desarrollo custom no toca ninguna API Enterprise

Los tres módulos del proyecto (`mercas_box_deposit`, `mercas_unified_screen`, `mercas_pos_purchase`) extienden únicamente modelos y servicios de Community. Se pueden instalar, actualizar y mantener sin licencia Enterprise en ningún servidor.

### La pantalla unificada sustituye las funciones POS de Enterprise

El módulo Enterprise `pos_settle_due` añade al TPV la capacidad de cobrar facturas y deudas pendientes desde la pantalla de pago. Para este proyecto esa funcionalidad se cubre desde la **pantalla unificada backend** (modo F3 Facturas + F4 Pagos), con acceso a la misma información en una interfaz igualmente rápida. No hay necesidad de `pos_settle_due`.

Del mismo modo, la gestión de límite de crédito en el TPV (aviso naranja de `pos_settle_due`) no está entre los requisitos del proyecto.

### Ahorro de licencia con alto impacto relativo

En un entorno de mercas el número de usuarios simultáneos es bajo (2-5 terminales). El coste de Enterprise por usuario activo mensual convierte la licencia en el componente más caro del proyecto, por encima del propio desarrollo custom, sin añadir valor para los requisitos actuales.

### Única excepción potencial: básculas electrónicas conectadas vía IoT Box

La integración de básculas de precisión en red o por puerto serie requiere el módulo Enterprise `pos_iot` (OEEL). Community **sí soporta el campo `to_weight`** en el producto y el flujo de pesaje manual, pero la conexión física vía IoT Box de Odoo es Enterprise.

| Tipo de báscula | Community | Enterprise |
|---|---|---|
| Báscula independiente con impresión de etiqueta (código de barras con peso) | ✅ | ✅ |
| Báscula USB con emulación de teclado (HID) | ✅ | ✅ |
| Báscula en red o serie conectada a IoT Box de Odoo | ❌ | ✅ (`pos_iot`) |

**Recomendación:** verificar el modelo de báscula existente en el mercas antes de confirmar Community. Si usa una báscula con salida por código de barras o USB HID, Community cubre el 100% del proyecto. Si necesita IoT Box de Odoo, el coste de licencia se limita a los terminales TPV que usen la báscula.

---

---

# PARTE 2 — SOLUCIÓN BACKEND

---

## 3. Pantalla unificada: concepto

Una pantalla de gestión operativa en el **backend de Odoo** que centraliza ventas, compras, facturación y pagos en una única vista sin necesidad de navegar por los menús estándar. El operario cambia de modo con una tecla de función y trabaja sobre las vistas lista estándar de Odoo sin salir de la pantalla.

## 4. UX: teclas de función con botones visibles

La combinación óptima son **botones visibles que muestran su tecla de función asociada**:

```
┌──────────────────────────────────────────────────────────────────┐
│  [F1 Ventas]  [F2 Compras]  [F3 Facturas]  [F4 Pagos]  [F5 Nuevo] │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│   Vista lista estándar del modo activo                           │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

| Tecla | Acción |
|---|---|
| `F1` | Cambiar a modo Ventas |
| `F2` | Cambiar a modo Compras |
| `F3` | Cambiar a modo Facturación |
| `F4` | Cambiar a modo Pagos |
| `F5` | Crear documento nuevo del modo activo |
| `Enter` | Abrir registro seleccionado |
| `Esc` | Volver a la lista desde un formulario |

Los atajos se registran con el hook `useHotkey` de `@web/core/hotkeys/hotkey_hook`, disponible en Odoo 19 sin dependencias adicionales.

## 5. Arquitectura técnica

### Componente raíz: `ir.actions.client`

Un único componente OWL registrado como acción cliente que:
1. Gestiona el modo activo en estado local reactivo
2. Renderiza la barra superior con botones y hotkeys
3. Embebe la vista lista estándar mediante el componente `<View>` de Odoo

```
ClientAction (OWL)
├── TopBar
│   ├── ModeButton [F1] Ventas
│   ├── ModeButton [F2] Compras
│   ├── ModeButton [F3] Facturas
│   ├── ModeButton [F4] Pagos
│   └── NewButton  [F5] Nuevo
└── <View type="list" resModel="{modelo activo}" domain="..." />
```

### Por qué `<View>` y no `ActionManager`

El componente `<View>` (importable desde `@web/views/view`) renderiza directamente cualquier vista Odoo recibiendo `resModel`, `type` y `domain` como props. Mantiene el control dentro del componente raíz sin generar entradas en el historial de navegación del cliente — el cambio de modo es instantáneo y no requiere viaje al servidor.

### Modos y modelos

| Tecla | Modo | `resModel` | Dominio por defecto |
|---|---|---|---|
| F1 | Ventas | `sale.order` | `[['state', 'not in', ['cancel']]]` |
| F2 | Compras | `purchase.order` | `[['state', 'not in', ['cancel']]]` |
| F3 | Facturas | `account.move` | `[['move_type', 'in', ['out_invoice', 'in_invoice', 'out_refund']]]` |
| F4 | Pagos | `account.payment` | `[['state', '!=', 'cancel']]` |

### Creación de documentos (`F5 / Nuevo`)

`F5` llama a `actionService.doAction` con el formulario estándar del modelo activo. El formulario abre en el área principal con un breadcrumb "← Gestión" que devuelve a la pantalla unificada al guardar o descartar, sin pasar por ningún menú de Odoo.

## 6. Fianza de cajas en backend (`mercas_box_deposit`)

### Requisitos

- Cada producto de fruta tiene asignado un tipo de caja (producto independiente con su precio de fianza).
- Al introducir kg en una línea de venta, el sistema propone automáticamente el número de cajas según la ratio `qty_per_box` del producto.
- El operario confirma o ajusta el número de cajas en la misma línea.
- Se genera automáticamente una línea hermana con el producto caja, cantidad y precio de fianza (sin IVA).
- La línea de fianza aparece en la factura distinguible del producto de fruta.
- Las devoluciones son parciales, pueden mezclar pedidos y no tienen límite superior (se abona siempre lo que se devuelve).
- No se requiere seguimiento de lotes ni inventario de cajas.

### Modelo de datos

**Extensión de `product.template`:**
- `box_product_id`: Many2one a `product.product` — el producto caja asociado a esta fruta
- `qty_per_box`: Float — kg por caja (para calcular la propuesta automática)

**Producto caja** (`product.product` estándar):
- `type = 'service'` — sin movimiento de stock
- `taxes_id = []` — sin IVA
- `list_price` = importe de fianza (p.ej. 1,00 €)
- Un producto distinto por cada tipo de caja con su coste propio

**Extensión de `sale.order.line`:**
- `box_qty`: Integer — cajas que se lleva el cliente en esta línea
- `box_deposit_line_id`: Many2one a la línea hermana de fianza (gestionada automáticamente)

### Flujo en pedido de venta

```
Operario introduce 100 kg de naranjas
       ↓
onchange: producto tiene box_product_id → propone box_qty = round(100 / qty_per_box)
       ↓
Operario confirma o ajusta (p.ej. 23 cajas)
       ↓
Se crea/actualiza automáticamente la línea hermana:
   producto  = "Caja Naranja"   (servicio, sin IVA)
   cantidad  = 23
   precio    = 1,00 €
   total     = 23,00 €
```

Si se elimina o modifica la línea de fruta, la línea de fianza se recalcula o elimina automáticamente.

### Apariencia en factura

```
Naranjas Valencia    100,00 kg   0,80 €/kg    80,00 €
─── Depósito de envases ───────────────────────────     ← sección automática (display_type='line_section')
Caja Naranja          23,00 ud   1,00 €/ud    23,00 €   (sin IVA)
────────────────────────────────────────────────────
BASE IMPONIBLE                                80,00 €
IVA 10%                                        8,00 €
FIANZA ENVASES (sin IVA)                      23,00 €
TOTAL                                        111,00 €
```

### Devolución de cajas

Botón "Devolver cajas" accesible desde el modo Facturas o Ventas de la pantalla unificada. Abre un wizard ligero donde el operario indica tipo de caja y cantidad a devolver. El sistema genera una nota de crédito (`account.move` tipo `out_refund`). Sin validación contra histórico — si devuelve más de lo comprado, se abona igualmente.

## 7. Por qué no se pueden usar productos Combo

### Problema fundamental en backend

En `sale/models/sale_order.py` L957, las líneas hijas del combo se crean con:

```python
'product_uom_qty': line.product_uom_qty,  # siempre igual a la línea padre
```

Y cuando la cantidad del padre cambia (L988-991):

```python
combo_item_lines.update({
    'product_uom_qty': line.product_uom_qty,  # sincronización forzada
})
```

**Consecuencia:** si la línea padre es "100 kg de Naranjas", todas las líneas hijas heredan qty=100. No es posible configurar una cantidad absoluta e independiente.

### Problema persiste en TPV

En `pos_store.js` L1102 la cantidad de cada línea hija es:

```js
qty: comboItem.qty * values.qty   // qty seleccionada × qty del padre
```

Si el cajero pone 100 kg y selecciona 23 cajas en el configurador, la línea de cajas queda `23 × 100 = 2300`. El combo **multiplica**, nunca asigna valor absoluto.

### Tabla de incompatibilidades

| Requisito fianza de cajas | Combo estándar |
|---|---|
| Cantidad de cajas independiente de los kg | ❌ Siempre qty_padre × qty_elegida |
| Propuesta automática basada en kg/caja | ❌ No existe tal lógica |
| Opción de no cobrar fianza (0 cajas) | ❌ `qty_free ≥ 1` obliga a seleccionar algo |
| Compatible con el producto fruta existente | ❌ Requiere crear un nuevo producto padre de tipo combo |
| Precio de fianza sin IVA en línea separada | ❌ El precio del combo se prorratea entre ítems |

**Conclusión:** el combo de Odoo 19 está diseñado para el patrón "elige uno de entre estas opciones". No modela componentes con cantidad absoluta e independiente ligados a una línea de producto. Referencia: `product/models/product_combo_item.py` — el modelo no tiene campo `qty`.

---

---

# PARTE 3 — SOLUCIÓN TPV (POS)

---

## 8. Capacidades estándar del TPV relevantes para este proyecto

### Compras a proveedor

El módulo `point_of_sale` **no incluye compras**. Al cerrar la sesión se disparan las reglas de reorden (`stock.warehouse.orderpoint`) si el producto tiene ruta "Comprar" configurada, pero esto es automático y transparente al cajero. Las compras desde el TPV requieren desarrollo custom (`mercas_pos_purchase`).

### Facturas pendientes de cobro (`pos_settle_due`, Enterprise)

El módulo Enterprise `pos_settle_due` permite cobrar deudas y facturas pendientes desde el TPV. Accesible desde el menú desplegable de cada cliente:

- **Saldar pedidos** — cancela deuda de pedidos anteriores pagados con `pay_later`
- **Pagar facturas** — muestra facturas `account.move` en estado `posted` con `payment_state` en `not_paid` o `partial`
- **Depositar / saldar importe** — saldo genérico a favor o en contra del cliente

### Límites de crédito (Enterprise)

Con `pos_settle_due` el TPV muestra avisos visuales cuando un cliente supera su límite de crédito (botón naranja, icono ⚠️ en pantalla de pago). **Nunca bloquea la venta**, solo informa.

Los campos relevantes están en `account` Comunidad:
- `res.company.account_use_credit_limit`
- `res.partner.credit_limit`

## 9. Módulo custom: pedidos de compra desde el TPV (`mercas_pos_purchase`)

### Planteamiento

Botón "Crear pedido de compra" en el TPV que, con los mismos productos del carrito, genera un `purchase.order` confirmado con recepción inmediata. No pasa por `PaymentScreen`.

### Simplificaciones acordadas

- **Sin tarifas de proveedor:** se usan los precios del TPV tal cual (`price_unit` de la línea)
- **Sin selección de proveedor:** se reutiliza el `partner_id` del pedido. El campo `purchase.order.partner_id` no tiene restricción de `supplier_rank`, cualquier contacto es válido.
- **Sin pantalla de pago:** la orden no genera líneas de pago
- **Sin cambios en la carga de datos del frontend:** el pedido de compra se crea enteramente en el servidor

### Lógica Python del método principal

```python
def create_and_receive_purchase_order(self, lot_data):
    # 1. Crear y confirmar el pedido de compra
    po = self.env['purchase.order'].create({
        'partner_id': self.partner_id.id,
        'order_line': [(0, 0, {
            'product_id': line.product_id.id,
            'name':        line.product_id.name,
            'product_qty': line.qty,
            'price_unit':  line.price_unit,
            'product_uom': line.product_uom_id.id,
            'date_planned': fields.Datetime.now(),
        }) for line in self.lines],
    })
    po.button_confirm()  # genera el albarán de recepción

    # 2. Asignar lotes en las líneas del albarán
    picking = po.picking_ids[0]
    for move in picking.move_ids:
        if move.product_id.tracking == 'none':
            continue
        lot_names = lot_data.get(str(move.product_id.id), [])
        if not lot_names:
            # Sin lote indicado: auto-generar con secuencia
            lot_names = [
                self.env['ir.sequence'].next_by_code('stock.lot.serial')
                or f"REC-{po.name}-{move.product_id.default_code or move.product_id.id}"
            ]
        for lot_name in lot_names:
            lot = self.env['stock.lot'].create({
                'name':       lot_name,
                'product_id': move.product_id.id,
                'company_id': po.company_id.id,
            })
            move.move_line_ids[0].write({'lot_id': lot.id})

    # 3. Validar el albarán de forma silenciosa (sin asistentes)
    picking.with_context(
        skip_sanity_check=True,
        skip_backorder=True,
        cancel_backorder=True,
    ).button_validate()

    return po.id
```

## 10. Lotes en modo compra: entrada directa y auto-asignación

### Comportamiento esperado

Al recibir mercancía a través del TPV, el número de lote se introduce **directamente en la línea de compra** (campo visible en la línea del carrito en modo compra). Si el operario no introduce ningún lote, al confirmar el pedido el servidor genera uno automáticamente.

| | Modo venta (estándar) | Modo compra (custom) |
|---|---|---|
| Lotes disponibles | Solo con stock en ubicación TPV | Campo de texto libre |
| Crear lote nuevo | No permitido | Sí (o auto-generado) |
| Sin lote indicado | Error (lote obligatorio en venta) | Se auto-genera con secuencia |
| Dónde se asigna | Picking de salida | Recepción del pedido de compra |

### Problema con el diálogo estándar de lotes

El TPV configura el comportamiento de lotes según el tipo de operación de **salida**:
- `use_existing_lots = True` → solo muestra lotes con stock en la ubicación del TPV
- `use_create_lots = False` → no permite escribir nombres de lote nuevos

Esto es correcto para ventas pero no para recepciones de compra, donde los lotes llegan por primera vez. La solución: un campo booleano `is_purchase_mode` en la orden TPV que cambia el comportamiento del diálogo.

### Implementación en el frontend

En modo compra, el patch de `editLots` usa:

```js
customInput: true,  // permite escribir nombres de lote libremente
options: [],        // sin consultar stock existente
```

El lote introducido se incluye en `lot_data` al llamar al servidor. Si `lot_data` está vacío para un producto con tracking, el servidor auto-genera el lote (ver sección 9).

### Flujo completo

1. Cajero activa el modo compra (`is_purchase_mode = true`) **antes** de añadir productos
2. Al añadir un producto con seguimiento de lotes, el campo de lote en la línea permite escribir el número libremente (p.ej. el número de lote del fabricante impreso en el embalaje)
3. Si se deja en blanco, se continúa sin lote
4. Al pulsar "Crear pedido de compra":
   - Se crea y confirma el `purchase.order`
   - Se genera el albarán de recepción
   - Para cada línea con tracking: se asigna el lote indicado, o se auto-genera uno si no se indicó
   - Se valida el albarán con `skip_backorder=True, cancel_backorder=True`

## 11. Sincronización de pedidos entre terminales

El TPV usa **WebSocket** con el canal `SYNCHRONISATION`. Un terminal solo ve los pedidos de otro si están configurados como "de confianza" (`trusted_config_ids` en `pos.config`).

| Escenario | ¿Se replican los pedidos? |
|---|---|
| Mismo `pos.config`, varios dispositivos | ✅ Siempre |
| Distintos `pos.config` con `trusted_config_ids` | ✅ Sí |
| Distintos `pos.config` sin `trusted_config_ids` | ❌ No |

**Limitaciones:** solo pedidos en estado `draft`; sin control de concurrencia; la relación de confianza hay que activarla manualmente.

## 12. Fianza de cajas en TPV: popup post-adición (`BoxDepositPopup`)

### Por qué no un campo en la línea (como en backend)

En el TPV no hay un formulario de línea editable en tabla. La interacción con líneas es mediante popups modales. El patrón correcto es el mismo que usa `SelectLotPopup` (lotes al añadir producto) y `ComboConfiguratorPopup` (combo al añadir producto combo).

### Flujo UX

```
Cajero pulsa "Naranjas Valencia" (100 kg) en el catálogo
       ↓
Se añade la línea de naranjas
       ↓
POS detecta box_product_id en el producto → abre popup automáticamente
┌─────────────────────────────────────┐
│  Depósito de cajas                  │
│  Naranja Valencia                   │
│  Propuesta: 4 cajas                 │  ← round(100 / qty_per_box)
│  [  4  ]  ▲ ▼                      │
│  [Confirmar]        [Sin cajas]     │
└─────────────────────────────────────┘
       ↓
Se añade automáticamente línea hermana:
   producto = "Caja Naranja"  qty = 4  precio = 1,00 €  sin IVA
```

### Modelo de datos TPV (extensión de `pos.order.line`)

```python
# pos.order.line — campos adicionales
box_deposit_line_id = fields.Many2one('pos.order.line', ondelete='set null')
```

Los campos `box_product_id` y `qty_per_box` están en `product.template` (compartidos con backend, sección 6).

### Implementación JS — patch de `addLineToOrder`

```js
patch(PosStore.prototype, {
    async addLineToOrder(vals, order, opts = {}, configure = true) {
        const line = await super.addLineToOrder(...arguments);
        if (!line || !configure || vals._is_box_deposit) return line;

        const tmpl = line.product_id.product_tmpl_id;
        if (!tmpl.box_product_id) return line;

        const proposedQty = Math.round(line.qty / (tmpl.qty_per_box || 1));
        const boxQty = await makeAwaitable(this.dialog, BoxDepositPopup, {
            productName: tmpl.display_name,
            proposedQty,
        });
        if (boxQty) {
            const boxProduct = this.models["product.product"].get(tmpl.box_product_id);
            const boxLine = await this.addLineToOrder({
                product_id:      boxProduct,
                qty:             boxQty,
                price_unit:      boxProduct.lst_price,
                tax_ids:         [],
                _is_box_deposit: true,
            }, order, opts, false);
            line.box_deposit_line_id = boxLine;
        }
        return line;
    },
});
```

### Devolución de cajas en TPV

Línea de cantidad negativa sobre el producto caja usando el flujo de devolución estándar del TPV. Permite devoluciones parciales, mixtas y en exceso (se abona siempre lo que se devuelve).

---

---

# PARTE 4 — GUÍA DE IMPLEMENTACIÓN

---

## 13. Estructura de módulos y ficheros

```
mercas_box_deposit/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   ├── product_template.py      # box_product_id, qty_per_box
│   ├── sale_order_line.py       # box_qty, box_deposit_line_id, _sync_box_deposit_line
│   ├── sale_order.py            # override _create_invoices → sección factura
│   └── pos_order_line.py        # box_deposit_line_id + _load_pos_data_fields
├── views/
│   ├── product_template_views.xml   # campo box_product_id en ficha producto
│   └── sale_order_views.xml         # columna box_qty en líneas de pedido
├── security/
│   └── ir.model.access.csv          # vacío (sin modelos nuevos)
└── static/src/
    └── app/
        ├── models/
        │   └── pos_order_line.js    # campo box_deposit_line_id en modelo JS
        ├── services/
        │   └── pos_store.js         # patch addLineToOrder
        └── components/
            └── box_deposit_popup/
                ├── box_deposit_popup.js
                └── box_deposit_popup.xml

mercas_unified_screen/
├── __manifest__.py
├── __init__.py
├── views/
│   └── unified_screen_action.xml    # ir.actions.client
└── static/src/
    └── app/
        └── unified_screen/
            ├── unified_screen.js
            └── unified_screen.xml

mercas_pos_purchase/
├── __manifest__.py
├── __init__.py
├── models/
│   ├── __init__.py
│   └── pos_order.py                 # create_and_receive_purchase_order
└── static/src/
    └── app/
        ├── models/
        │   └── pos_order.js         # campo is_purchase_mode
        ├── services/
        │   └── pos_store.js         # patch editLots (modo compra)
        └── components/
            └── purchase_button/
                ├── purchase_button.js
                └── purchase_button.xml
```

## 14. Manifests con dependencias

### `mercas_box_deposit/__manifest__.py`

```python
{
    'name': 'Mercas - Fianza de Cajas',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'depends': ['sale', 'point_of_sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'mercas_box_deposit/static/src/**/*',
        ],
    },
    'license': 'LGPL-3',
}
```

### `mercas_unified_screen/__manifest__.py`

```python
{
    'name': 'Mercas - Pantalla Unificada',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'depends': ['sale', 'purchase', 'account', 'mercas_box_deposit'],
    'data': [
        'views/unified_screen_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mercas_unified_screen/static/src/**/*',
        ],
    },
    'license': 'LGPL-3',
}
```

### `mercas_pos_purchase/__manifest__.py`

```python
{
    'name': 'Mercas - Compras desde TPV',
    'version': '19.0.1.0.0',
    'category': 'Point of Sale',
    'depends': ['point_of_sale', 'purchase_stock'],
    'data': [],
    'assets': {
        'point_of_sale._assets_pos': [
            'mercas_pos_purchase/static/src/**/*',
        ],
    },
    'license': 'LGPL-3',
}
```

## 15. Carga de campos custom en el frontend del TPV (`pos.load.mixin`)

El TPV carga datos del servidor al arrancar la sesión. Para añadir campos custom hay que extender `_load_pos_data_fields` en los modelos correspondientes.

### `models/product_template.py`

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    box_product_id = fields.Many2one('product.product', string="Producto caja depósito")
    qty_per_box    = fields.Float(string="Kg por caja", default=1.0)

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        fields += ['box_product_id', 'qty_per_box']
        return fields
```

`box_product_id` se carga como ID entero. El frontend lo resuelve automáticamente al modelo `product.product` que ya está precargado en POS.

### `models/pos_order_line.py`

```python
class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    box_deposit_line_id = fields.Many2one('pos.order.line', ondelete='set null')

    @api.model
    def _load_pos_data_fields(self, config):
        fields = super()._load_pos_data_fields(config)
        fields += ['box_deposit_line_id']
        return fields
```

Sin este override, cuando el TPV cargue órdenes abiertas existentes no sabrá qué línea es la hermana de fianza y mostraría líneas duplicadas al volver a abrir una orden.

## 16. Python: ciclo de vida de la línea de fianza (`sale.order.line`)

```python
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    box_qty             = fields.Integer(string="Cajas", default=0)
    box_deposit_line_id = fields.Many2one('sale.order.line', ondelete='set null',
                                          string="Línea fianza")

    @api.onchange('product_uom_qty', 'product_id')
    def _onchange_propose_box_qty(self):
        if self.product_id.box_product_id and self.product_uom_qty:
            self.box_qty = round(self.product_uom_qty / (self.product_id.qty_per_box or 1))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.filtered(lambda l: l.box_qty > 0)._sync_box_deposit_line()
        return lines

    def write(self, vals):
        res = super().write(vals)
        if 'box_qty' in vals:
            self._sync_box_deposit_line()
        return res

    def unlink(self):
        self.mapped('box_deposit_line_id').unlink()
        return super().unlink()

    def _sync_box_deposit_line(self):
        for line in self:
            box_product = line.product_id.box_product_id
            if not box_product:
                continue
            if line.box_qty <= 0:
                if line.box_deposit_line_id:
                    line.box_deposit_line_id.unlink()
                    line.box_deposit_line_id = False
            elif line.box_deposit_line_id:
                line.box_deposit_line_id.product_uom_qty = line.box_qty
            else:
                deposit = self.create([{
                    'order_id':        line.order_id.id,
                    'product_id':      box_product.id,
                    'product_uom_qty': line.box_qty,
                    'price_unit':      box_product.lst_price,
                    'tax_id':          [Command.clear()],
                    'sequence':        line.sequence + 1,
                }])
                line.box_deposit_line_id = deposit
```

**Sin recursión:** `_sync_box_deposit_line` llama a `create` sin `box_qty`, por lo que la línea de fianza creada no vuelve a disparar el sync.

## 17. Separador de sección en factura

Patrón idéntico al de la sección de anticipos en `sale/models/sale_order.py` L1576-1585:

```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _create_invoices(self, grouped=False, final=False, date=None):
        invoices = super()._create_invoices(grouped=grouped, final=final, date=date)
        for invoice in invoices:
            deposit_sol_ids = set(
                invoice.invoice_line_ids.sale_line_ids
                .filtered('box_deposit_line_id')
                .mapped('box_deposit_line_id').ids
            )
            deposit_inv_lines = invoice.invoice_line_ids.filtered(
                lambda l: any(s.id in deposit_sol_ids for s in l.sale_line_ids)
            )
            if deposit_inv_lines:
                first_seq = min(deposit_inv_lines.mapped('sequence'))
                self.env['account.move.line'].with_context(
                    check_move_validity=False
                ).create({
                    'move_id':      invoice.id,
                    'display_type': 'line_section',
                    'name':         _('Depósito de envases'),
                    'sequence':     first_seq,
                })
                deposit_inv_lines.write({'sequence': first_seq + 1})
        return invoices
```

El contexto `check_move_validity=False` es necesario porque la factura aún no está publicada en este punto.

## 18. `BoxDepositPopup`: estructura OWL completa

### `box_deposit_popup.js`

```js
import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";

export class BoxDepositPopup extends Component {
    static template = "mercas_box_deposit.BoxDepositPopup";
    static components = { Dialog };
    static props = {
        productName: String,
        proposedQty: Number,
        getPayload: Function,
        close: Function,
    };

    setup() {
        this.state = useState({ qty: this.props.proposedQty });
    }

    confirm() {
        this.props.getPayload(this.state.qty);
        this.props.close();
    }

    skip() {
        this.props.getPayload(0);
        this.props.close();
    }
}
```

### `box_deposit_popup.xml`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<templates xml:space="preserve">
<t t-name="mercas_box_deposit.BoxDepositPopup">
    <Dialog title="'Depósito de cajas'">
        <p class="mb-1 fw-bold"><t t-esc="props.productName"/></p>
        <div class="d-flex align-items-center gap-2 my-3">
            <label>Cajas:</label>
            <input type="number" class="form-control w-auto"
                   t-model.number="state.qty" min="0" autofocus="autofocus"/>
        </div>
        <t t-set-slot="footer">
            <button class="btn btn-primary" t-on-click="confirm">Confirmar</button>
            <button class="btn btn-secondary" t-on-click="skip">Sin cajas</button>
        </t>
    </Dialog>
</t>
</templates>
```

## 19. Puntos de extensión críticos — resumen

| Qué | Dónde extender | Método |
|---|---|---|
| Añadir campos al frontend POS | `product.template` + `pos.order.line` | `_load_pos_data_fields` |
| Crear/actualizar/eliminar línea fianza | `sale.order.line` | `_sync_box_deposit_line` desde `create`, `write`, `unlink` |
| Insertar sección en factura | `sale.order` | `_create_invoices` (patrón down-payment L1576) |
| Popup cajas en TPV | `PosStore` | patch `addLineToOrder` |
| Botón compra en TPV | `PosStore` + componente `ActionPad` | patch + nuevo botón OWL |
| Lotes libres en modo compra | `PosStore` | patch `editLots` con `customInput: true, options: []` |
| Auto-asignación de lote si no se indica | `pos.order` Python | `create_and_receive_purchase_order` con `ir.sequence` |
| Validación silenciosa del albarán | `pos.order` Python | `button_validate` con `skip_backorder=True, cancel_backorder=True` |

## 20. Referencias de código estándar Odoo 19

| Funcionalidad | Ruta | Referencia |
|---|---|---|
| Campos `qty_max` / `qty_free` en combo (POS) | `point_of_sale/models/product_combo.py` | L11-12 |
| Cantidad hija igual al padre (backend) | `sale/models/sale_order.py` | L957 |
| Cantidad hija = elegida × padre (TPV) | `point_of_sale/static/src/app/services/pos_store.js` | L1102 |
| Popup combo configurator (patrón referencia) | `point_of_sale/static/src/app/components/popups/combo_configurator_popup/` | — |
| Lotes existentes en stock para TPV | `point_of_sale/models/pos_order.py` | L1655 `get_existing_lots` |
| Lógica del diálogo de lotes | `point_of_sale/static/src/app/services/pos_store.js` | L2439 `editLots` |
| Creación albarán desde pedido de compra | `purchase_stock/models/purchase_order.py` | L374 `_create_picking` |
| Validación albarán | `stock/models/stock_picking.py` | L1393 `button_validate` |
| Gancho pre-validación (asistentes) | `stock/models/stock_picking.py` | L1468 `_pre_action_done_hook` |
| Patrón sección factura (down-payment) | `sale/models/sale_order.py` | L1576-1585 `_create_invoices` |
| Sincronización WebSocket entre terminales | `point_of_sale/models/pos_config.py` | L222 `notify_synchronisation` |
| Campo terminales de confianza | `point_of_sale/models/pos_config.py` | L189 `trusted_config_ids` |
| Módulo saldar facturas/deudas (Enterprise) | `19enterprise/pos_settle_due/` | — |
| Límite de crédito por socio | `account/models/partner.py` | L515 `credit_limit` |
| Hook de atajos de teclado | `@web/core/hotkeys/hotkey_hook` | `useHotkey` |
| Componente vista embebida | `@web/views/view` | `<View>` |
| Servicio de acciones | `@web/core/action_service` | `actionService.doAction` |
