# CRM Opportunity Rules

Motor de reglas que, a partir del perfil del cliente (`crm_partner_profile`),
propone oportunidades de negocio evitando propuestas repetidas, y permite
convertirlas en oportunidad (`crm.lead`) asignada al comercial habitual del
cliente con un clic.

## Objetivos

- Detectar automáticamente **combinaciones de perfil que justifican una
  oferta** (p. ej. "sector calzado" + "Fabricación" → "Vertical Odoo
  Calzado"), sin depender de que un comercial se acuerde de proponerla.
- **No repetir nunca** una propuesta ya hecha ni una solución ya vendida.
- Permitir **encadenar reglas** ("Vertical Mercas" + "SII" → "NIS2") sin
  código adicional, usando lo que el cliente ya tiene comprado (o quién se
  lo provee hoy) como condición de entrada de otras reglas — p. ej. proponer
  NIS2 solo si el SII actual es de la competencia o interno, pero no si el
  proveedor de ese SII ya somos nosotros.
- Que configurar una regla nueva sea trabajo de **administración, no de
  desarrollo**: se hace con el editor de dominios estándar de Odoo.
- Que pasar una sugerencia a oportunidad sea **un clic**, con el comercial
  correcto ya asignado.

## Funcionalidad

### Modelo `crm.opportunity.rule`

- **Condición** (`domain`): dominio estándar de Odoo evaluado contra
  `res.partner` (sector, actividad, productos y servicios actuales,
  facturación, empleados, soluciones ya vendidas...). Se edita con el mismo
  widget de filtros que cualquier vista de lista de Odoo — admite AND/OR sin
  necesidad de un editor de condiciones propio.
- **Solución propuesta** (`product_template_id`): el producto del catálogo
  que representa la solución/vertical (p. ej. un producto real "Vertical
  Odoo Calzado"). Es lo que se compara contra el histórico de ventas del
  cliente para no repetir la propuesta.
- **Línea de negocio** (`crm_business_id`, opcional): si se indica, la
  oportunidad generada hereda su preventa/validador/etapas, igual que
  cualquier otra oportunidad de `crm_business`.

Menú: **CRM > Configuración > Clientes > Reglas de oportunidad** (agrupado
junto con "Clasificación de clientes" bajo la clasificación de menú
"Clientes", definida en `crm_partner_profile`).

Dos botones en la cabecera del formulario:

- **Asistente de condición**: abre un asistente (`crm.opportunity.rule.wizard`)
  que construye el campo `domain` a partir de 4 preguntas, en vez de escribir
  el dominio a mano:
  1. Propiedades a cumplir del perfil de negocio (tags de
     `crm.partner.attribute.value` — Sector, Actividad, Interés,
     Facturación, Empleados).
  2. Propiedades excluyentes del perfil de negocio (mismos tags, en
     negativo).
  3. Productos/servicios que ha de tener el cliente, con Estado y Proveedor
     opcionales por línea (vacío = cualquiera).
  4. Productos/servicios que no ha de tener el cliente, igual con Estado y
     Proveedor opcionales.

  Todas las líneas de un mismo bloque se combinan en AND. Al confirmar,
  **sustituye por completo** la condición actual de la regla — no la
  fusiona ni relee el dominio existente para precargar el formulario (abrir
  el asistente siempre empieza en blanco). El campo `domain` sigue editable
  a mano después, por si hace falta afinar el resultado.
- **Generar sugerencias ahora**: ejecuta la regla en el momento (sin
  esperar al disparo en tiempo real ni al cron nocturno) y muestra cuántas
  sugerencias nuevas se han creado.

### Modelo `crm.opportunity.suggestion`

Una sugerencia por (cliente, regla) — nunca se genera dos veces la misma
(restricción única en base de datos). Estados:

- **Nueva**: al crearse.
- **Convertida**: significa "tiene una oportunidad (`lead_id`) asignada".
  El botón **Convertir en oportunidad** crea el `crm.lead` (tipo
  oportunidad, `partner_id`, `user_id` = comercial habitual del cliente,
  producto y, si la regla la define, línea de negocio con su primera etapa
  permitida) y enlaza la sugerencia con la oportunidad creada. Si esa
  oportunidad se **elimina**, la sugerencia vuelve automáticamente a Nueva
  (ver más abajo) — puede volver a convertirse.
- **Descartada**: al pulsar **Descartar**. A diferencia de Convertida, este
  estado sí es permanente (no hay ninguna acción que la reabra sola).

`crm.lead.lead_id` es `ondelete='set null'`: al borrar la oportunidad, la
base de datos limpia el campo directamente vía la restricción de clave
ajena, sin pasar por `write()` — así que el estado se quedaría clavado en
"Convertida" con `lead_id` vacío si no se hiciera nada más. Por eso
`crm_lead.py` sobrescribe `unlink()` en `crm.lead`: captura qué sugerencias
apuntan a las oportunidades que se van a borrar (antes de borrarlas) y, tras
el borrado, las devuelve a Nueva.

Menú: **CRM > Ventas > Recomendaciones de venta** (además del acceso desde la
propia ficha del cliente).

**Sugerencias que dejan de ser válidas**: cada vez que cambia el perfil de un
cliente (clasificación o productos/servicios actuales), además de generar
sugerencias nuevas se revisan las que ya tenía en estado **Nueva**: si la
condición de su regla ya no se cumple (`crm.opportunity.rule._partner_matches`),
la sugerencia se **elimina**. Ejemplo: un cliente tiene "ERP Odoo" y se le
sugiere "RRHH Odoo"; si luego se le añade "Factorial" como producto actual y
la regla excluye a quien ya tiene Factorial, la sugerencia de "RRHH Odoo"
desaparece sola. Se revisa en los mismos tres sitios que generan sugerencias:
al guardar el perfil (tiempo real), en el cron nocturno y al pulsar "Generar
sugerencias ahora". Aquí las sugerencias **Convertidas** nunca se tocan (ya
hay una oportunidad real de por medio) y las **Descartadas** tampoco.

**Cambiar la condición de una regla reevalúa TODO, sin importar el estado**
(`crm.opportunity.rule._reconcile_suggestions`, disparado desde `write()` al
tocar `domain`, `product_template_id` o `active` — así que aplica tanto si
se edita a mano como desde el Asistente de condición):

- **Nueva** o **Descartada** que ya no cumple → se borra sin más.
- **Convertida** que ya no cumple → se borra la sugerencia (pierde el
  vínculo con la regla) pero la oportunidad **no se toca**; en su lugar se
  le añade una nota en el chatter: *"Esta oportunidad se creó en base a la
  regla X que ha cambiado su parametrización y ahora no la cumple."*
- **Oportunidades ya existentes sin regla** (`crm.lead` tipo Oportunidad,
  con el producto de la regla, sin ninguna sugerencia asociada) cuyo
  cliente **ahora sí** cumple la condición nueva → se adoptan: se crea una
  sugerencia en estado Convertida enlazada a esa oportunidad, en vez de
  generarles una sugerencia nueva duplicada.
- El resto de clientes que ahora cumplen y no tenían nada → sugerencia
  nueva, como siempre.

### Ficha de cliente (`res.partner`)

- **Soluciones vendidas** (`crm_solution_ids`, calculado): productos de
  líneas de pedidos de venta confirmados de ese cliente. Es el campo que
  permite (a) no repetir una propuesta ya vendida y (b) encadenar reglas.
- Botón "Sugerencias" en la ficha del cliente (junto a los demás botones de
  estadística), con el número de sugerencias nuevas pendientes, que abre la
  lista de oportunidades sugeridas para ese cliente.

### Cuándo se evalúan las reglas

- **En tiempo real**, al guardar cambios de perfil en la ficha del cliente
  (clasificación, productos y servicios actuales, tramos de
  facturación/empleados): el
  comercial ve la sugerencia nueva al instante.
- **Cron nocturno** (`ir.cron` diario): reevalúa todo el catálogo de reglas
  contra todos los clientes. Cubre dos casos que el disparo en tiempo real
  no ve: una regla nueva que ya aplicaría a clientes cuyo perfil no ha
  cambiado, y el encadenamiento cuando lo que cambia es una **venta**
  confirmada (el campo `crm_solution_ids` se recalcula por la propia venta,
  no por una edición de la ficha del cliente).

## Decisiones de diseño (para no repetir la discusión)

- El "ya lo tiene" para no repetir una propuesta se basa en **ventas
  confirmadas** (`sale.order` en estado `sale`), no en cotizaciones en
  borrador ni en una etiqueta manual del perfil.
- Una sugerencia **descartada queda descartada de forma permanente** para
  ese (cliente, regla); no reaparece sola. Si hay que reabrirla, se cambia
  su estado a mano.
- El "producto o solución" de una regla es siempre un `product.template`
  real y concreto — no una categoría ni un conjunto de productos.
- El asistente de condición usa el operador de dominio `any`/`not any`
  (Odoo 19) para las líneas de producto, en vez de encadenar condiciones
  sueltas sobre `crm_current_product_ids.product_tmpl_id` /
  `crm_current_product_ids.state` / `crm_current_product_ids.provider` por
  separado. Con condiciones sueltas, un cliente con el Producto A vigente y
  el Producto B obsoleto haría coincidir por error "Producto A obsoleto"
  (cada condición se evalúa contra cualquier línea, no necesariamente la
  misma). `any`/`not any` obliga a que producto + estado + proveedor se
  cumplan **en la misma línea**. Verificado con un caso de prueba
  específico para este falso positivo.
- **Nunca uses una ruta con punto de dos saltos (`campo_o2m.subcampo`)
  combinada con un operador negativo (`!=`, `not in`)**: en Odoo 19 excluye
  por error también a los registros que **no tienen ninguna línea en
  absoluto** en `campo_o2m`, en vez de incluirlos (que es lo correcto: si no
  tienen ninguna línea, trivialmente no tienen el valor excluido). Se
  detectaron y corrigieron dos casos reales de este patrón:
  - `_get_matching_partners` / `_partner_matches`: excluir a quien ya tiene
    el producto de la regla como actual. Estaba escrito como
    `("crm_current_product_ids.product_tmpl_id", "not in", [id])` y excluía
    por error a los clientes sin ningún producto/servicio actual en su
    perfil. Corregido a
    `("crm_current_product_ids", "not any", [("product_tmpl_id", "=", id)])`.
  - Asistente de condición, `excluded_value_ids`: excluir a quien tiene una
    propiedad de perfil concreta. Estaba escrito como
    `("crm_profile_line_ids.value_ids", "!=", [id])` y excluía por error a
    los clientes sin ninguna línea de perfil rellenada. Corregido a
    `("crm_profile_line_ids", "not any", [("value_ids", "=", [id])])`.

  Las condiciones **positivas** (`=`, `in` con ruta de punto) no tienen este
  problema. Si en el futuro se añade otra condición negativa sobre un campo
  relacional, usar siempre `not any` en vez de una ruta con punto.

## Próximos pasos deliberadamente fuera de este primer alcance

- **Plantilla de oferta y plantilla de proyecto**: se decidió que la
  solución es directamente un producto del catálogo; de momento el
  comercial elige a mano la plantilla de presupuesto (`sale.order.template`,
  módulo `sale_management`) y de proyecto al crear la venta/proyecto desde
  la oportunidad convertida. Si se quiere automatizar esa selección, el
  siguiente paso natural es añadir un campo en `crm.opportunity.rule` (o en
  el propio `product.template`) que apunte a la plantilla por defecto.
- No hay todavía un evento inmediato al confirmar una venta que recalcule
  reglas en el acto (se apoya en el cron nocturno); si el encadenamiento
  necesita ser instantáneo, habría que enganchar `sale.order.action_confirm`.

## Dependencias

`crm_partner_profile`, `crm_business_product` (que a su vez trae `crm`,
`crm_business`, `sale_crm` y `product`).

## Módulos relacionados

- [`crm_partner_profile`](../crm_partner_profile): perfil del cliente que
  este módulo consume como condición de las reglas.
