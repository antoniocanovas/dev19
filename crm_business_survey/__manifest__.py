{
    "name": "CRM Business Survey",
    "version": "19.0.1.0.0",
    "summary": "Track and answer the surveys tied to the opportunity's product type",
    "author": "Antonio Cánovas",
    "license": "LGPL-3",
    "category": "Sales/CRM",
    "depends": [
        "crm_business_product",
        "survey",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/crm_business_product_type_views.xml",
        "views/crm_lead_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
