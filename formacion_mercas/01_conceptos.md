# 01 · Conceptos básicos

Antes de tocar la pantalla conviene tener claras siete ideas. Todo el Mostrador gira alrededor de ellas.

## Lote

Cada compra que entra crea un **lote** por producto: un número como `0000001`. El lote guarda de quién es la mercancía, cuándo llegó, de dónde viene (país y provincia) y cuánto queda.

- Al vender **siempre se elige el lote**: así se sabe qué proveedor ha vendido qué.
- El número de lote va impreso en la **etiqueta de caja**. Escanear la etiqueta abre directamente ese lote.

## Caja (envase) y tara

Las cajas son productos aparte (por ejemplo `[E204] CAJAS MARI PILI`) y cada tipo tiene su **peso**, que es la **tara**.

- Las cajas **se cuentan**: el sistema sabe cuántas cajas nuestras tiene cada cliente y cuántas tenemos nosotros de cada proveedor.
- En la venta, las cajas aparecen como líneas del pedido y **se cobran** (su importe se devuelve cuando el cliente las trae de vuelta).

## Bruto, tara y neto

Es **lo más importante** para la báscula:

```
NETO = BRUTO − (número de cajas × peso de la caja)
```

| | Ejemplo |
|---|---|
| Bruto (lo que marca la báscula) | 50 kg |
| Cajas | 5 × CAJAS MARI PILI (2,2 kg) = 11 kg de tara |
| **Neto (lo que se cobra)** | **39 kg** |

En el Mostrador se escribe **el bruto** y el neto se calcula solo. Si después se cambian las cajas o el tipo de caja, el neto se recalcula.

## Facturación firme o liquidación por venta

Es el trato con el **proveedor** y se decide en cada línea de compra (por defecto, el que tenga el proveedor):

| | **Firme** | **Liquidación por venta** |
|---|---|---|
| Qué se le paga | Todo lo recibido, al precio de compra. | Lo que se vende, menos nuestro margen. |
| Desechos | Los pagamos nosotros. | No se pagan al proveedor. |
| Cómo se factura | *Crear factura de proveedor* o *Factura firme*. | *Facturar adelanto* (con stock) o *Liquidar* (lote agotado). |
| En pantalla | Etiqueta azul **Firme** en el lote. | Sin etiqueta. |

## Presupuesto, pedido y albarán

- Mientras se está preparando, la venta es un **presupuesto** que se guarda solo con cada cambio. Se puede dejar a medias y seguir después, en este u otro puesto.
- **Vender y entregar** lo convierte en **pedido** y valida el **albarán** (la salida de la mercancía) en un solo paso.
- La **factura** es un paso aparte: en el momento (contado) o a fin de mes.

## Saldo a favor del cliente

Cuando un cliente devuelve cajas, su importe puede quedarse como **saldo a favor**. Ese saldo aparece en **Cobros (F5)** y se descuenta de la siguiente factura.

## Contado o fin de mes

- **Cliente de albarán (fin de mes):** se lleva solo el albarán. El encargado le factura y le cobra a final de mes.
- **Cliente de contado:** se factura y se cobra en el momento, con tarjeta o en efectivo.

El plazo de pago de cada cliente está en su ficha (*Plazos de pago*). Por ejemplo, Cliente1 tiene «fin del mes siguiente».
