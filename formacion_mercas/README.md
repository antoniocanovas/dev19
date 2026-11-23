# Formación Mercas: el Mostrador paso a paso

Guía para aprender a trabajar con el **Mostrador** de Odoo (módulos `mercas_base` y `mercas_touch`) en un puesto de mercado mayorista de fruta y verdura.

Todas las capturas están hechas en la base de pruebas, a tamaño tablet, con datos de formación:

| Dato | Para qué sirve en la formación |
|---|---|
| **Cliente1** | Cliente que se lleva solo el **albarán** y paga **a fin de mes**. |
| **Cliente2** | Cliente de **contado**: se le factura y se le cobra en el momento (tarjeta o efectivo). |
| **Proveedor1** | Proveedor con **facturación firme**: se le paga todo lo comprado. |
| **Proveedor2** | Proveedor en **liquidación por venta**: se le paga según lo que se vende. |
| `[E204] CAJAS MARI PILI` | Nuestras cajas (tara 2,2 kg). |
| `[E180] CAJAS ASCOY` | Cajas del proveedor, que vienen con la compra (tara 1,5 kg). |

## ¿Quién hace qué?

| Puesto | Tareas | Capítulos |
|---|---|---|
| **Encargado** | Compra la mercancía, factura a los clientes de fin de mes, pone los precios especiales y liquida a los proveedores. Decide las promociones y las caducidades y sigue el resumen de Dirección. | 10 a 13 |
| **Báscula** | Vende: despacha a los clientes que vienen y prepara los pedidos, cobra a los de contado y recoge las cajas devueltas. | 20 a 24 |

Todos deberían leer primero los capítulos 01 y 02.

## Índice

1. [Conceptos básicos](01_conceptos.md): lote, caja, tara, bruto y neto, firme o liquidación, saldo a favor.
2. [El Mostrador](02_mostrador.md): pantalla de inicio y cuadro de mandos, teclas F1–F6, teclado numérico y calculadora.

**Encargado**

- [10 · Comprar y recibir (F2)](10_encargado_compras.md)
- [11 · Lotes: stock, desechos y liquidación al proveedor (F4)](11_encargado_lotes.md)
- [12 · Facturación de fin de mes y cobro con saldo a favor](12_encargado_facturacion.md)
- [13 · Cuadro de mandos: promociones, caducidades y Dirección](13_encargado_cuadro_de_mandos.md)

**Báscula**

- [20 · Vender y entregar (F1)](20_bascula_venta.md)
- [21 · Venta de contado: facturar y cobrar (F1 + F5)](21_bascula_contado.md)
- [22 · El cliente devuelve cajas (F3)](22_bascula_cajas.md)
- [23 · Etiqueta dañada (F6)](23_bascula_etiqueta.md)
- [24 · Palets, DeCA y envío por correo](24_bascula_palets_deca_correo.md)

**Para todos**

- [30 · Errores frecuentes](30_errores_frecuentes.md)
- [31 · Ejercicio: un día completo](31_ejercicio_dia_completo.md)
- [Glosario](glosario.md)
- [Guion del podcast](podcast/guion.md)

## Un día de trabajo, en resumen

```
  Mañana temprano             Durante el día                           Fin de mes
  ───────────────             ──────────────                           ──────────
  ENCARGADO                   BÁSCULA                                  ENCARGADO
  F2 Compra                   F1 Venta (bruto en báscula → neto)       F1 «Para facturar»
   └ lotes + etiquetas         ├ Cliente de albarán → solo albarán       └ Facturar
                               └ Cliente de contado → Facturar           └ F5 Cobrar (con saldo)
                                   └ Cobrar (tarjeta / efectivo)
                              F3 Cajas que devuelven los clientes      F4 Lotes
                              F6 Reponer una etiqueta                    └ Liquidar al proveedor
```
