{
    "name": "CRM Partner Profile",
    "version": "19.0.1.0.0",
    "summary": "Catalog client sector, revenue, headcount, interests and current products/services",
    "author": "Antonio Cánovas",
    "license": "LGPL-3",
    "category": "Sales/CRM",
    "depends": [
        "crm",
        "contacts",
        "sale",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/crm_partner_attribute_data.xml",
        "views/crm_partner_attribute_views.xml",
        "views/product_template_views.xml",
        "views/res_partner_views.xml",
        "views/crm_partner_report_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
