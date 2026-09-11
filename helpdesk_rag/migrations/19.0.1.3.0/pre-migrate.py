"""Quita el prefijo rag_ de los campos de equipo del ticket.

Se hace en pre-migración, antes de que Odoo cargue los modelos, para que el
registro vea los nombres nuevos ya puestos. Si se dejara para después, Odoo
encontraría tres campos que ya no declara nadie, borraría sus filas de
ir_model_fields y con ellas —en cascada— la configuración del bridge, que
apunta a los campos por id: el flujo dejaría de recibir el equipo del ticket
sin dar ningún error.

El many2many no necesita tocarse: su tabla de relación se llama por los dos
modelos (helpdesk_rag_model_helpdesk_ticket_rel), no por el campo.
"""

RENOMBRES = [
    ("rag_manufacturer_id", "manufacturer_id", True),
    ("rag_model_ids", "model_ids", False),
    # Calculado sin store: no tiene columna que renombrar.
    ("rag_model_names", "model_names", False),
]


def migrate(cr, version):
    if not version:
        return
    for viejo, nuevo, tiene_columna in RENOMBRES:
        cr.execute(
            "SELECT id FROM ir_model_fields "
            "WHERE model = 'helpdesk.ticket' AND name = %s",
            (viejo,),
        )
        if not cr.fetchone():
            continue

        if tiene_columna:
            cr.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = 'helpdesk_ticket' AND column_name = %s",
                (viejo,),
            )
            if cr.fetchone():
                cr.execute(
                    "ALTER TABLE helpdesk_ticket RENAME COLUMN %s TO %s"
                    % (viejo, nuevo)
                )

        cr.execute(
            "UPDATE ir_model_fields SET name = %s "
            "WHERE model = 'helpdesk.ticket' AND name = %s",
            (nuevo, viejo),
        )
        cr.execute(
            "UPDATE ir_model_data SET name = %s "
            "WHERE module = 'helpdesk_rag' AND model = 'ir.model.fields' "
            "AND name = %s",
            (
                "field_helpdesk_ticket__%s" % nuevo,
                "field_helpdesk_ticket__%s" % viejo,
            ),
        )
