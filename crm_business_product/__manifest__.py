{
    "name": "CRM Business Product",
    "version": "19.0.1.0.0",
    "summary": "Select or create a product on the opportunity, with a configurable product type catalog",
    "author": "Antonio Cánovas",
    "license": "LGPL-3",
    "category": "Sales/CRM",
    "depends": [
        "crm_business",
        "product",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/res_groups_data.xml",
        "views/crm_business_product_type_views.xml",
        "views/crm_lead_views.xml",
        "views/product_template_views.xml",
        "wizard/crm_business_product_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}