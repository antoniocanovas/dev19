# CRM Business - Knowledge Document Page

Extiende [`crm_business`](../crm_business) añadiendo el campo **Procedimiento**
(`business_document_page_id`), un enlace a una página de documentación
(`document.page`) del módulo libre **OCA Document Page**
(`/Users/acanovas/pycharmprojects/19knowledge/document_page`) que describe el
procedimiento a seguir para esa línea de negocio.

Es la alternativa **sin dependencia Enterprise** a
[`crm_business_document`](../crm_business_document): mismo objetivo, mismo
patrón de campos, pero usando un módulo Community/OCA en lugar de la app
Documents de Odoo Enterprise.

## Funcionalidad

- `crm.business.business_document_page_id`: procedimiento asociado a la
  línea de negocio, editable desde su formulario.
- `crm.lead.business_document_page_id`: heredado (related, solo lectura) de
  la línea de negocio de la oportunidad, mostrado junto al resto de campos de
  línea de negocio en la pestaña **Notes**.
- `sale.order.business_document_page_id`: heredado de la oportunidad de
  origen.

El campo se etiqueta como "Procedimiento" en los formularios; el texto
"Document Page" (para distinguirlo de la variante `documents.document`,
cuando ambos módulos están instalados a la vez) aparece en la ayuda del
campo, no en la etiqueta visible.

## Dependencias

`crm_business`, `document_page` (OCA, módulo `knowledge`), sin ninguna
dependencia de Odoo Enterprise.

## Compatibilidad

Puede instalarse junto con `crm_business_document` sin conflicto: cada uno
añade su propio campo (`business_document_id` / `business_document_page_id`)
sin pisarse.
