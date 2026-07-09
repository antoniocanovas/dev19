# CRM Business

Añade **líneas de negocio** al CRM de Odoo para poder clasificar, filtrar y
medir oportunidades y presupuestos por área de negocio (línea comercial),
además de restringir el flujo de etapas de cada oportunidad a las etapas
propias de su línea de negocio.

No depende de ningún módulo Enterprise. Es el módulo base sobre el que se
apoyan `crm_business_document` (Documents, Enterprise) y `crm_business_knowledge`
(Document Page, OCA) para añadir el campo "Procedimiento".

## Funcionalidad

### Modelo `crm.business` (Línea de negocio)

Nuevo modelo con:

- **Nombre** (obligatorio).
- **Departamento** (`hr.department`).
- **Jefe de departamento**: usuario relacionado (de solo lectura) a través del
  responsable (`manager_id`) del departamento seleccionado.
- **Preventa**: usuario responsable por defecto.
- **Validador**: usuario con rol de manager de compras
  (`purchase.group_purchase_manager`) que valida el presupuesto una vez
  aceptado por el cliente.
- **Objetivo anual**: importe monetario.
- **Etapas** (`crm_business_stage_ids`): las etapas del CRM (`crm.stage`)
  permitidas para esta línea de negocio (`many2many`, widget de tags).

Nuevo menú **CRM > Ventas > Business Areas**, con vistas kanban, lista y
formulario.

### Etapas del CRM (`crm.stage`)

Se añade el campo inverso `crm_business_ids` (las líneas de negocio que usan
cada etapa), visible como `many2many_tags` en el formulario de etapas, junto
al campo de equipos de venta.

### Oportunidades (`crm.lead`)

Nuevos campos:

- `crm_business_id`: línea de negocio de la oportunidad.
- `presale_user_id` / `controller_user_id`: se copian por defecto desde la
  línea de negocio al seleccionarla, pero siguen siendo editables.
- `manager_user_id`, `hr_department_id`, `crm_business_stage_ids`: derivados
  (related, de solo lectura) de la línea de negocio.

Comportamiento:

- El **selector de etapas** (statusbar) sólo permite moverse a las etapas
  incluidas en `crm_business_stage_ids` de la línea de negocio asignada; si
  la línea de negocio no restringe etapas, se permiten todas. Se aplica
  también como constraint en base de datos.
- Al crear la oportunidad o al (re)asignar preventa/jefe de departamento/
  validador, esos usuarios se añaden automáticamente como **seguidores**.
  También se refuerza la suscripción cada vez que la oportunidad sale de su
  primera etapa.
- Todos los campos de línea de negocio se muestran agrupados en dos columnas
  en la pestaña **Notes** del formulario, y en el kanban de quick-create y en
  el kanban normal del pipeline (icono, avatares de preventa/validador junto
  al del comercial).
- Nueva regla de acceso: cualquier usuario que sea **seguidor** de una
  oportunidad puede verla, aunque no sea el comercial asignado.

### Presupuestos (`sale.order`)

- `crm_business_id`: se copia automáticamente desde la oportunidad
  (`opportunity_id`) cuando el presupuesto está vinculado a una; si no hay
  oportunidad asociada, es libremente editable. Se muestra justo debajo del
  cliente en el formulario.
- `presale_user_id`, `manager_user_id`, `controller_user_id`,
  `hr_department_id`, `crm_business_stage_ids`: heredados de la oportunidad,
  filtrables y agrupables desde la vista de búsqueda de presupuestos.

## Dependencias

`crm`, `sale_crm`, `hr`, `purchase`, `sale_margin` (todas Community).

## Módulos relacionados

- [`crm_business_document`](../crm_business_document): añade el campo
  "Procedimiento" usando el módulo Enterprise `documents`.
- [`crm_business_knowledge`](../crm_business_knowledge): añade el mismo
  campo "Procedimiento" pero usando el módulo libre OCA `document_page`, sin
  dependencia Enterprise. Ambos pueden convivir instalados a la vez.
