# Account Due Date Calendar

Añade una vista de calendario por fecha de vencimiento a las facturas/reembolsos, los asientos y los apuntes contables de Odoo 19 Community.

## Funcionalidades

### Calendario de facturas y reembolsos

Añade la vista **Calendario** (basada en `invoice_date_due`, la fecha de vencimiento de la factura) a las acciones estándar de Odoo. Cada tipo de documento tiene, en el propio Odoo, dos ids de acción distintos que muestran lo mismo pero los usa cada menú por separado — hay que cubrir ambos para que el calendario aparezca tanto en Facturación > Clientes/Proveedores como en cualquier otro módulo que reutilice el id "legacy" (p. ej. Mercas):

- Facturas de cliente: `account.action_move_out_invoice` (menú nativo Facturación > Clientes > Facturas) y `account.action_move_out_invoice_type` (legacy)
- Facturas rectificativas de cliente: `account.action_move_out_refund_type_non_legacy` (menú nativo) y `account.action_move_out_refund_type` (legacy)
- Facturas de proveedor: `account.action_move_in_invoice` (menú nativo) y `account.action_move_in_invoice_type` (legacy)
- Reembolsos de proveedor: `account.action_move_in_refund_type` (el mismo id en ambos sitios)

Al reutilizar el mismo id de acción que usa el propio Odoo, la pestaña Calendario aparece en cualquier menú que use estas acciones — tanto en Contabilidad/Facturación como en cualquier otro módulo que las reutilice (p. ej. Mercas).

Cada evento del calendario muestra el contacto, el importe pendiente (`amount_residual`) y el estado de pago, coloreado por contacto. No permite alta rápida (`quick_create`): al crear desde el calendario se abre el formulario completo, porque una factura tiene demasiados campos obligatorios para un alta rápida.

Se añade también, reutilizando la misma vista, a la acción estándar **Asientos contables** (`account.action_move_journal_line`), que muestra `account.move` sin filtrar por tipo. Los asientos que no sean factura (tipo "entry") no tienen `invoice_date_due` relleno y simplemente no aparecen en el calendario.

### Calendario de apuntes contables

Añade la misma vista Calendario a la acción estándar **Apuntes contables** (`account.action_account_moves_all`), basada en `date_maturity` — el vencimiento propio de cada apunte, no el de la factura. Es más fino que el calendario de facturas cuando una factura tiene varios plazos de pago (varias cuotas, cada una con su propia fecha de vencimiento).

No permite crear apuntes contables desde el calendario, igual que la lista estándar de apuntes contables.

## Dependencias

### Odoo
- `account`

## Compatibilidad

Odoo **19.0 Community**
