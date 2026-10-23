# Propuesta: impresión y correo en mercas_touch

Estado: **pendiente de decidir**, sin desarrollar. Recomendaciones del 23/10/2026 para retomar después.

## Situación actual

Tras *Vender y entregar* (F1), la pantalla de resultado ofrece botones para el **albarán**, las **etiquetas de caja** y, después de facturar, la **factura**. Tras *Comprar y recibir* (F2), solo las etiquetas. No se imprime ni se envía nada automáticamente (`get_print_action` en `models/mercas_touch.py`).

## Recomendación

- **Correo:** automático y en segundo plano, según la configuración del cliente y de la compañía.
- **Impresión:** manual por defecto, a un toque. Automática solo en los puestos con impresión silenciosa.
- **Etiquetas tras comprar:** abrir siempre el asistente.

### Impresión: manual, a un toque

- **Odoo no imprime en silencio por sí mismo.** Un informe abre el PDF y el navegador muestra su diálogo de impresión. "Automático" sin preparar la impresión solo significa que el diálogo aparece solo, y más pestañas abiertas.
- **La impresión silenciosa necesita una de estas opciones:**
  - Chrome con `--kiosk-printing` en el puesto del mostrador: imprime directamente en la impresora predeterminada.
  - Una IoT Box (solo Enterprise).
- **Con eso preparado, que sea configurable por puesto,** guardado en el navegador y no por compañía. Por ejemplo: "tras vender, imprimir el albarán automáticamente" (sí/no). Cada puesto tiene impresoras distintas (A4 o etiquetas) y costumbres distintas.
- **No todas las ventas necesitan papel,** por ejemplo un cliente habitual que recibe la factura por correo. Conviene una preferencia por cliente: albarán en papel, sí o no.

| Documento | Cuándo | Recomendación |
|---|---|---|
| Albarán | Tras *Vender y entregar* | Automático en los puestos con impresión silenciosa; botón a un toque en el resto |
| Etiquetas de caja | Tras *Comprar y recibir* | Abrir automáticamente el asistente de etiquetas: siempre se necesitan |
| Factura | Tras *Facturar* | Manual, o por correo (ver abajo) |
| Pedido de compra | — | No imprimirlo: el proveedor trae su propio albarán |

### Correo: automático, en segundo plano, con lo estándar

El vendedor no debería tener que decidir si se envía algo ni esperar al servidor de correo.

- **Albarán:** Inventario › Ajustes › *Confirmación por correo*. Envía un correo al validar una entrega de salida. Es estándar, sin código.
- **Factura:** al facturar desde touch, enviarla según el *método de envío de facturas* del cliente (`invoice_sending_method`, estándar desde v18): por correo si lo tiene, nada si no. Requiere un cambio pequeño en mercas_touch: llamar al proceso de envío estándar después de publicar la factura.
- **Confirmación del pedido:** normalmente no hace falta en el mostrador, porque vender y entregar van juntos. Se descarta.
- **Compras:** no enviar correo al proveedor; la compra se hace en el momento.
- **Aviso en pantalla:** el resultado debe mostrar "Factura enviada a x@y", o un aviso si el cliente no tiene correo, para que nadie tenga que comprobar si salió.

## Pendiente de decidir antes de desarrollar

1. ¿Los puestos del mostrador pueden usar Chrome en modo quiosco (`--kiosk-printing`)?
2. ¿Preferencia "albarán en papel" por cliente, o basta la configuración por puesto?
3. ¿Activar la confirmación por correo de los albaranes en la compañía?

## Alcance del desarrollo (cuando se decida)

- Opciones por puesto (almacenadas en el navegador): imprimir el albarán tras vender, abrir las etiquetas tras comprar.
- Envío de la factura en segundo plano al facturar, según `invoice_sending_method`, con el resultado en pantalla.
- Hacerlo en las dos versiones: dev19 (Odoo 19) y dev20 (Odoo 20).
