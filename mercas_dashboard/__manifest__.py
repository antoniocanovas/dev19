{
    "name": "Mercas Dashboards",
    "version": "19.0.1.0.0",
    "summary": "Tableros de Mercas en Tableros: ventas, compras y mermas, deuda y cobros",
    "author": "Antonio Cánovas",
    "license": "LGPL-3",
    "category": "Productivity/Dashboard",
    "depends": [
        "mercas_base",
        "spreadsheet_dashboard",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/dashboards.xml",
    ],
    # The dashboards of the management of Mercas whenever Mercas and the Dashboards app are
    "auto_install": True,
}
