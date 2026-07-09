# CRM Business - Document

Extiende [`crm_business`](../crm_business) añadiendo el campo **Procedimiento**
(`business_document_id`), un enlace al documento (`documents.document`) del
módulo Enterprise **Documents** que describe el procedimiento a seguir para
esa línea de negocio.

## Requisitos

Requiere el módulo Enterprise `documents`. Si no dispones de Enterprise, usa
en su lugar [`crm_business_knowledge`](../crm_business_knowledge), que ofrece
el mismo campo apoyado en el módulo libre OCA `document_page`.

## Funcionalidad

- `crm.business.business_document_id`: procedimiento asociado a la línea de
  negocio, editable desde su formulario.
- `crm.lead.business_document_id`: heredado (related, solo lectura) de la
  línea de negocio de la oportunidad, mostrado junto al resto de campos de
  línea de negocio en la pestaña **Notes**.
- `sale.order.business_document_id`: heredado de la oportunidad de origen.

El campo se etiqueta como "Procedimiento (Documents)" para distinguirlo de la
variante `document_page` cuando ambos módulos están instalados a la vez.

## Dependencias

`crm_business`, `documents` (Enterprise).

## Compatibilidad

Puede instalarse junto con `crm_business_knowledge` sin conflicto: cada uno
añade su propio campo (`business_document_id` / `business_document_page_id`)
sin pisarse.
