# Tableros de Mercas (`mercas_dashboard`)

Los tableros de la dirección de Mercas en la aplicación **Tableros** de Odoo (*Tableros › Tableros*), en su propio grupo **Mercas**, junto a *Ventas* y *Finanzas*. Sustituyen a la antigua pantalla *Dirección*: muestran las mismas cifras que el resumen que se envía por correo cada tarde, con filtros, periodos y la posibilidad de abrir el detalle.

Se instala solo (`auto_install`) cuando están `mercas_base` y `spreadsheet_dashboard` (Tableros). Los ven los usuarios del grupo **Mercas: Dirección** (`mercas_base.group_mercas_management`), que tienen los administradores de ventas y de facturación; a los demás no les aparece el grupo.

## Tableros

Importes sin impuestos y kg netos, sin las cajas, como el resumen por correo. Las ventas y compras confirmadas cuentan en la fecha del pedido; las mermas, en la fecha en que se hicieron.

### Ventas

- **Cómo vamos, hasta hoy:** tarjetas de hoy, la semana, el mes y el año frente al mismo periodo de hace un año, y una tabla con las ventas, la variación frente al periodo anterior y frente a hace un año, los kg netos, el precio/kg, los pedidos y las cajas.
  - El día se compara con ayer y con el mismo día de la semana de hace un año (52 semanas antes).
  - La semana, el mes y el año, con el periodo anterior hasta el mismo día y con el mismo periodo de hace un año (la semana, con la semana entera de hace 52 semanas).
- **Ritmo:** el mes y el año hasta hoy, hace un año hasta el mismo día y en total, y la previsión de cierre al ritmo de los días transcurridos.
- **Ventas hasta hoy:** la semana día a día (esta, la anterior y la de hace un año), el mes acumulado (este, el anterior y el de hace un año) y el año acumulado por meses (este y el anterior).
- **En el periodo** (el del filtro *Periodo*, por defecto el mes hasta la fecha): ventas, kg, precio/kg y pedidos frente al periodo anterior; las ventas por día; los mejores clientes, productos y categorías.
- **Filtros:** periodo, cliente, producto, categoría y comercial. Todas las cifras siguen los filtros; las de *hasta hoy* no dependen del periodo, porque hacen sus propios periodos.

### Compras y mermas

Lo mismo para las compras (sin el gráfico del año), con los **kg de merma** y el **% de merma** (kg desechados sobre los kg comprados) de cada periodo; los proveedores, los productos comprados y las mermas por producto del periodo; y los **lotes por liquidar**: vendidos del todo, en liquidación por venta y aún sin liquidar al proveedor. Filtros: periodo, proveedor, producto y categoría.

### Deuda y cobros

Lo que se debe **hoy**: lo que nos deben los clientes y cuánto está vencido, lo que debemos a proveedores y lo pendiente de facturar; la deuda de los clientes por días de retraso (sin vencer, 1-30, 31-60, 61-90 y más de 90 días) en un gráfico y por cliente; lo pendiente de facturar por cliente y lo que debemos a cada proveedor. Y los **cobros** del periodo del filtro frente al anterior, los de hoy, por día y por diario. Filtros: periodo de cobros y contacto.

## Datos

Las hojas leen tres informes (vistas SQL, solo lectura, para el grupo *Mercas: Dirección*):

| Modelo | Contenido |
|---|---|
| `mercas.report.goods` | Una fila por línea de venta o compra confirmada de mercancía (sin cajas) y por merma hecha: tipo, fecha, contacto (la empresa), producto, categoría, lote, comercial/comprador, pedido, importe, kg netos y cajas. Los kg se calculan como `product.product._mercas_net_weight`: la cantidad convertida si la unidad es de peso, o por el peso del producto si no. |
| `mercas.report.balance` | Los apuntes de clientes y proveedores publicados y sin conciliar (lo pendiente, con los días de retraso y su antigüedad) y las líneas de venta confirmadas con importe pendiente de facturar. |
| `mercas.report.payment` | Los cobros de clientes en proceso o pagados: fecha, cliente, diario e importe. |

Las cifras coinciden con las del resumen por correo de `mercas_base` (`mercas.management.dashboard`); los tests lo comprueban.

## Cambiar los tableros

Las hojas (`data/files/*.json`) se generan con `tools/build_dashboards.py`, que es la fuente: tras un cambio, se ejecuta y se actualiza el módulo.

```
python3 mercas_dashboard/tools/build_dashboards.py
```

Cada tablero tiene una hoja visible, *Dashboard*, y otra oculta, *Data*, con las cifras de cada periodo: una tabla dinámica de las ventas (o compras, o cobros) de cada día, sobre la que se suman los periodos con `SUMIFS`. Las tablas dinámicas del periodo del filtro usan el desplazamiento de fecha de Odoo (`offset: -1`) para el periodo anterior.

Con **OCA spreadsheet** (`spreadsheet_oca` y `spreadsheet_dashboard_oca`, repositorio `19spreadsheet`) se pueden editar los tableros en Odoo, pero el cambio se queda en esa base de datos: para conservarlo, hay que llevarlo al generador.

Los textos van en inglés con `_t()` en las celdas, y su traducción al español en `i18n/es.po`. Los nombres de las tablas dinámicas, que Odoo no traduce, se escriben en español en el generador.

## Tests

Los informes dan las cifras del resumen (importe y kg de ventas y compras, sin cajas, en gramos y por unidades; mermas; deuda por antigüedad; cobros), y las hojas usan modelos y campos que existen y solo las ve la dirección.
