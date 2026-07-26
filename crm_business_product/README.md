# CRM Business Product

Depende de [`crm_business`](../crm_business) y añade la posibilidad de asociar
un **producto** (`product.template`) a la oportunidad, además de su línea de
negocio.

El seguimiento de encuestas ligadas al tipo de producto vive en el módulo
separado [`crm_business_survey`](../crm_business_survey).

## Funcionalidad

### Oportunidades (`crm.lead`)

- Nuevo campo `product_template_id` (Producto), junto al campo de línea de
  negocio. Si el producto no existe, se puede crear a mano directamente desde
  el propio selector (creación rápida/`Crear y editar`).
- Nuevo botón **Nuevo producto** (rojo, para destacarlo) en la cabecera del
  formulario, que abre un asistente para crear el producto sin salir de la
  oportunidad. Sólo es visible mientras la oportunidad no tenga ya un
  producto asignado.
- En el **kanban** del pipeline, debajo de la línea de negocio se muestra
  también el producto (`product_template_id`), sólo si está cumplimentado.

### Asistente de creación de producto

Pide:

- **Tipo de producto** (`type_id`): referencia al nuevo modelo
  `crm.business.product.type`. Cualquier usuario interno puede consultarlo,
  pero sólo los responsables de ventas (`sales_team.group_sale_manager`)
  pueden crear/editar tipos.
- **Nombre** del producto.
- Si es un **bien** o un **servicio** (mapeado al campo estándar `type` de
  `product.template`).
- **Categoría** (`categ_id`, `product.category`).
- **Atributos**: en cuanto se selecciona el tipo de producto, el asistente
  añade una línea por cada atributo (`product.attribute`) definido en ese
  tipo, para indicar sus valores (`product.attribute.value`). El atributo de
  cada línea es fijo (no se puede cambiar ni borrar la línea, sólo elegir o
  crear sus valores). Sólo se crean líneas de atributo
  (`product.template.attribute.line`) para las filas a las que se les haya
  indicado algún valor.

Al pulsar "Crear" se genera el `product.template` con esos datos (guardando
también el tipo de producto en el nuevo campo
`product_template.crm_business_product_type_id`) y se asigna automáticamente
a la oportunidad.

### Tipos de producto (`crm.business.product.type`)

Nuevo modelo y menú **CRM > Configuración > Productos > Tipos de producto**, con:

- **Nombre**.
- **Atributos** (`attribute_ids`, `product.attribute`): atributos que se
  ofrecerán a rellenar en el asistente al elegir este tipo.

`crm_business_survey` añade a este mismo modelo el campo **Encuestas**.

### Variantes de producto

Como los productos creados pueden llevar variantes, este módulo habilita por
defecto la opción estándar de Odoo **Variantes de producto**
(`product.group_product_variant`), igual que si se marcara la casilla
correspondiente en Ajustes.

## Dependencias

`crm_business`, `product` (ambas Community).
