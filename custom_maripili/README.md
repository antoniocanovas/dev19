# custom_maripili

Lo propio de Maripili sobre Mercas: impresión y otras particularidades del cliente. Lo que sirve a cualquier cliente va en `mercas_base` / `mercas_touch`, no aquí.

## Etiquetas de caja 70 x 50 (Citizen CL-S700)

- Añade el formato **70 x 50 (etiquetadora)** al asistente de etiquetas de caja de `mercas_base` (`mercas.label.print.wizard`), con `selection_add` sobre `print_format` y `_get_report_xmlid` para elegir su informe. Los demás formatos (Dymo, hojas A4) siguen con los informes de `mercas_base`.
- Una etiqueta por página, papel `paperformat_label_70x50` (70 x 50 mm, sin márgenes).
- Los datos (producto, lote, caducidad, origen, código de barras del lote) son los del informe de `mercas_base` (`report.mercas_base.report_mercas_box_label`), de modo que vale para las compras, las ventas y la reimpresión desde los lotes, también desde mercas_touch.
- **El diseño es propio:** `box_label_70x50_content` en `report/box_label_70x50.xml`. Los cambios de diseño se hacen ahí, no en `mercas_base`.
- **Impresión:** PDF por el driver de Citizen del sistema operativo del puesto, con la etiqueta de 70 x 50 mm configurada y escala al 100 % (sin "ajustar a página"). La impresión directa sin diálogo (servidor en la nube, impresora en red) está pendiente de decidir: ver `mercas_touch/PROPUESTA_IMPRESION_CORREO.md`.

## Tests

`--test-tags /custom_maripili` sobre una base con el módulo instalado (por ejemplo `test_mercas_touch19`).
