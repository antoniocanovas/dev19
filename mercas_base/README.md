# Mercas Base

Módulo base para la gestión de mercados mayoristas de frutas y hortalizas en Odoo 19 Community.

## Funcionalidades

### Ventas — Vender y Entregar

El botón **Vender y Entregar** en el pedido de venta ejecuta en un solo clic:

1. Valida que todas las líneas de producto trazadas tengan lote asignado.
2. Comprueba el riesgo financiero del cliente (requiere `sale_financial_risk` / `account_financial_risk`). Si se supera el riesgo, muestra el aviso estándar de OCA; si el usuario acepta continuar, el flujo continúa automáticamente.
3. Confirma el pedido.
4. Valida el albarán de salida asignando la cantidad hecha igual a la demandada (sin pedir confirmación de retroactivos).

### Ventas — Cajas por línea de pedido

Cada línea de pedido tiene los campos **Cajas** (`box_qty`) y **Caja** (`box_product_id`). Al confirmar el pedido:

- Se inserta la sección **PRODUCTOS** antes de las líneas de producto.
- Se inserta la sección **Envases** al final.
- Por cada línea con `box_qty > 0` se crea automáticamente una línea de caja vinculada (`box_sale_line_id`) usando el producto indicado en `box_product_id` de la línea (que se inicializa desde la plantilla del producto y puede modificarse manualmente antes de confirmar).
- Si después de confirmar se modifica `box_qty`, `box_product_id` o el producto de una línea, la línea de caja se actualiza o elimina en consecuencia.

### Ventas — Ubicación por cliente

Al confirmar un pedido de venta se verifica si el cliente tiene una sub-ubicación propia bajo el **Almacén clientes** configurado en la empresa. Si no existe, se crea automáticamente con el nombre del partner y se asigna como `property_stock_customer` del cliente (campo dependiente de empresa).

### Compras — Comprar y Recibir

El botón **Comprar y Recibir** en el pedido de compra:

1. Confirma el pedido (con auto-creación de lotes si está activada).
2. Valida el albarán de entrada asignando cantidad hecha igual a la demandada.
3. Genera la factura de proveedor, le asigna la fecha de hoy y la valida.
4. Abre directamente la factura generada.

### Compras — Auto-creación de lotes

Cuando la opción **Purchase lot auto** está activa en la empresa, al confirmar cualquier pedido de compra se crea automáticamente un lote nuevo (usando la secuencia del producto) para cada línea trazada que no tenga lote asignado. El proveedor del pedido se asigna automáticamente al lote. Requiere el módulo OCA `purchase_lot`.

### Compras — Origen del producto

Las líneas de pedido de compra disponen de los campos **País origen** y **Provincia origen**. Su visibilidad en la vista de pedido se controla mediante los toggles **Columna país origen** y **Columna provincia origen** de la parametrización de empresa.

Cuando una línea tiene lote asignado, cualquier cambio en el país o provincia de origen se propaga automáticamente al lote correspondiente (`stock.lot`).

### Compras — Devolución de envases

El botón **Devolución cajas** en el pedido de venta abre un nuevo pedido de compra pre-relleno con el tipo de compra de envases configurado. Al confirmar este pedido:

1. Se verifica la ubicación de stock del cliente (igual que en ventas).
2. Se reciben las cajas desde la ubicación física del cliente (no desde el proveedor virtual).
3. Se genera y valida automáticamente la factura de proveedor (nota de crédito al cliente por el depósito).
4. Se abre la factura para revisión.

Los productos de un pedido de devolución de envases quedan restringidos a las **Categorías de cajas** configuradas en la empresa.

### Contabilidad — Compensación de facturas

El botón **Compensar** en facturas de proveedor (`in_invoice`) en estado publicado y pendiente de pago:

1. Crea un asiento de compensación en el **Diario de compensación** configurado en la empresa:
   - Debe a la cuenta a pagar de la factura de proveedor (salda la deuda con el proveedor).
   - Haber a la cuenta a cobrar del mismo partner (genera un crédito pendiente en sus facturas de cliente).
2. Valida y concilia el asiento con la línea a pagar de la factura de proveedor.
3. El crédito resultante aparece como **crédito pendiente** en las facturas de cliente del mismo partner y puede aplicarse directamente desde ellas.

### Maestros — País y Provincia de origen

Los modelos `res.country` y `res.country.state` disponen del campo booleano **Origen Mercas** (`mercas_origin`), visible en sus vistas de formulario y lista. Permite marcar los países y provincias habituales de origen de la mercancía para su uso futuro como filtro (controlado por **Filtro origen** en la empresa).

### Lotes de stock (`stock.lot`)

El módulo extiende el lote de stock con las siguientes capacidades:

#### Campos de trazabilidad

| Campo | Descripción |
|---|---|
| **Proveedor** (`partner_id`) | Partner proveedor del lote. Se asigna automáticamente al confirmar el pedido de compra y puede editarse manualmente. |
| **País origen** / **Provincia origen** | Origen geográfico del producto. Se propagan desde las líneas de compra. |

#### Pestaña General — Liquidación

| Campo | Descripción |
|---|---|
| **Kg comprados** | Suma de kg de las líneas de compra confirmadas. |
| **Kg vendidos** | Suma de kg entregados en albaranes de venta (`stock.move.line` completados). |
| **Kg desechados** | Desechos formales más ajustes de inventario negativos, menos ajustes positivos (neto). |
| **Kg en almacén** | Campo estándar `product_qty` de Odoo (stock disponible). |
| **Importe vendido** | Calculado desde los movimientos de salida: `qty × precio_unitario × (1 - descuento%)`. |
| **Margen (%)** | Margen aplicable al lote: del partner si está informado, o el general de la empresa. Se asigna al crear el lote y puede modificarse manualmente (requiere grupo Gestor de Ventas). |
| **Importe proveedor** | `Importe vendido × (1 - Margen%)` |
| **Precio/kg proveedor** | `Importe proveedor / Kg comprados` |
| **Margen importe** | `Importe vendido - Importe proveedor` |
| **Factura proveedor** | Factura de liquidación generada para este lote (solo lectura). |

#### Campo Completado

El campo booleano **Completado** (`completed`, almacenado) se activa automáticamente cuando `product_qty ≤ 0`. Permite filtrar lotes liquidados y es la condición de entrada para la facturación de lotes.

#### Pestañas de trazabilidad

El formulario incluye pestañas con las líneas de compra, venta, facturas de proveedor, facturas de cliente y desechos asociados al lote.

#### Facturación de lotes (liquidación a proveedores)

Desde la vista lista de lotes se puede invocar la acción **Crear facturas proveedor** sobre los lotes seleccionados. También está disponible el botón **Facturar lote** en el formulario individual.

El proceso:
1. Filtra los lotes seleccionados: `completed = True`, sin factura previa y con proveedor asignado.
2. Agrupa por proveedor y crea **una factura por proveedor** con:
   - Fecha: día actual.
   - Por cada lote: línea con producto, cantidad (`purchase_kg`), precio (`supplier_price_kg`) y descripción compuesta por el nombre del producto y, en segunda línea, `DD/MM/YYYY | Ref.pedido | Ref.proveedor | Núm.lote`.
3. Asigna la factura al campo `supplier_invoice_id` de cada lote.
4. Actualiza el coste (`purchase_price`) en las líneas de venta relacionadas, si el módulo `sale_margin` está instalado.
5. Confirma la factura automáticamente si **Confirmar factura proveedor automáticamente** está activo en la empresa.

Un smart button en el formulario del lote abre la factura de liquidación cuando ya está generada.

#### Vista lista y búsqueda de lotes

- Columnas adicionales: **Proveedor** y **Completado** (ambas opcionales).
- Filtros: **Completados no facturados** (activo por defecto en el menú Mercas), **Completado**.
- Agrupación por **Proveedor**.
- Búsqueda por **Proveedor** como primera opción en la barra de búsqueda.

## Parametrización (Empresa > pestaña Mercas)

### Almacén
| Campo | Descripción |
|---|---|
| **Almacén clientes** | Ubicación padre bajo la que se crean las sub-ubicaciones por cliente. Por defecto: `stock.stock_location_customers`. |

### Compras
| Campo | Descripción |
|---|---|
| **Purchase lot auto** | Activa la creación automática de lotes al confirmar pedidos de compra. |
| **Columna país origen** | Muestra la columna de país de origen en las líneas de pedido de compra. |
| **Columna provincia origen** | Muestra la columna de provincia de origen en las líneas de pedido de compra. |
| **Filtro origen** | Restringe la selección de país/provincia a los marcados como Origen Mercas. |

### Envases
| Campo | Descripción |
|---|---|
| **Tipo de compra envases** | Tipo de pedido de compra que identifica una devolución de envases (`purchase.order.type`). |
| **Categorías de cajas** | Familias de productos permitidas en pedidos de devolución de envases. |

### Contabilidad
| Campo | Descripción |
|---|---|
| **Diario de compensación** | Diario de tipo "Operaciones varias" para los asientos de compensación. |
| **Margen Mercas (%)** | Margen general aplicado a los lotes cuando el partner no tiene margen propio. |
| **Confirmar factura proveedor automáticamente** | Si está activo, las facturas de liquidación de lotes se confirman al generarse. |

## Dependencias

### Odoo
- `purchase`
- `stock`
- `account`
- `sale_stock`
- `contacts`

### OCA
- `purchase_order_type` — campo `order_type` en pedidos de compra
- `purchase_lot` — campo `lot_id` en líneas de pedido de compra
- `sale_order_lot_selection` — selección de lote en líneas de venta

### OCA opcionales
- `sale_financial_risk` — control de riesgo financiero en ventas
- `account_financial_risk` — cálculo de riesgo financiero por partner

### Odoo opcionales
- `sale_margin` — actualización del precio de coste en líneas de venta al generar facturas de lote

## Compatibilidad

Odoo **19.0 Community**
