# CRM Partner Profile

Permite catalogar el cliente (sector, actividad, facturación, empleados,
intereses y productos/servicios actuales) de forma rápida desde su propia
ficha, sin depender de encuestas ni de campos libres. Es la base de datos
sobre la que trabaja `crm_opportunity_rules` para proponer oportunidades de
negocio automáticamente.

Deliberadamente genérico: "productos y servicios actuales" (en vez de
"tecnologías") para que sirva igual a una empresa de software que a una que
solo quiere registrar con qué proveedores o soluciones no técnicas trabaja
ya un cliente.

## Objetivos

- Que el comercial pueda **catalogar un cliente en un par de minutos**,
  marcando tags en vez de rellenar formularios largos.
- Que el catálogo de tipos de clasificación (sector, interés, ...) sea
  **ampliable sin desarrollo**: dar de alta un tipo nuevo y sus valores no
  requiere tocar código ni vistas.
- Que los **productos y servicios actuales** del cliente queden registrados
  con su estado (de "vigente y ok" a "obsoleto", pasando por "a cambiar") y
  quién los provee (nosotros, la competencia...), porque son el disparador
  típico de una oportunidad de cambio.
- Que esos productos/servicios sean **el propio catálogo de productos de
  Odoo** (marcados con un simple check), no un catálogo paralelo que haya
  que mantener duplicado.
- Servir de **fuente de verdad** para las condiciones del motor de reglas de
  `crm_opportunity_rules` (que se apoya en estos mismos campos del cliente).
- Poder **agrupar y analizar entre clientes** (no solo ficha a ficha) qué
  tipos de clasificación o qué productos/servicios son más comunes, o cuáles
  están obsoletos, desde un par de vistas de informe.

## Funcionalidad

### Modelo `crm.partner.attribute` (tipo de clasificación)

Catálogo de "tipos" (Sector, Actividad, Interés, y cualquier otro que se
necesite en el futuro). Cada tipo tiene:

- **Selección**: Única o Múltiple — controla cuántos valores puede marcar un
  cliente de este tipo.
- **Valores** (`crm.partner.attribute.value`): editables en línea dentro del
  propio tipo, igual que un catálogo de atributos de producto.

Menú: **CRM > Configuración > Clientes > Clasificación de clientes**.

Nota: "Productos y servicios actuales" **no** es un tipo de este catálogo —
tiene su propio modelo (ver abajo), independiente de atributos/valores.

### Modelo `crm.partner.profile.line`

Una línea por (cliente, tipo de clasificación), con los valores marcados
como `many2many_tags` filtrados por tipo. Restringe a un único valor cuando
el tipo es de selección "Única" (p. ej. Sector).

### Modelo `crm.partner.current_product`

Una línea por (cliente, producto/servicio actual), independiente del
catálogo de atributos: apunta directamente a `product.template`
(`product_tmpl_id`), con:

- **Estado**: un único campo que combina vigencia y "motivo de oportunidad"
  en una escala de mejor a peor — Vigente - Ok / Vigente - A evolucionar /
  Vigente - A cambiar / Parado o sin uso / Obsoleto. Antes eran dos campos
  (Estado + Satisfacción); se fusionaron en uno solo porque en la práctica
  siempre se leían juntos ("vigente pero insatisfecho" era en realidad un
  único concepto: "a cambiar").
- **Proveedor**: Interno / Nosotros / Competencia / Varios — quién provee
  hoy ese producto/servicio al cliente. Es una dimensión independiente del
  Estado (se puede cruzar "Competencia" × "A cambiar" en el pivote para ver
  justo dónde hay una oportunidad de desplazar a la competencia).
- **Nota** libre.

Esto es lo que permite luego filtrar "productos/servicios a cambiar,
parados u obsoletos" (o "en manos de la competencia") como disparador de
una oportunidad de cambio.

`product_tmpl_id` solo permite elegir productos marcados con el nuevo campo
**"Negocio en CRM"** (`crm_business`, casilla en la pestaña **Ventas** de la
ficha del producto) — así el selector no se llena con todo el catálogo
(embalajes, materias primas, etc.), solo con lo que de verdad tiene sentido
registrar como "lo que el cliente ya tiene".

Si al escribir el nombre de un producto que no existe se usa "Crear y
editar...", se abre el **formulario estándar completo del producto** (con
todas sus pestañas) — antes había aquí un formulario reducido solo con el
nombre y la casilla, pero no se correspondía con el estándar de creación de
producto de Odoo, así que se quitó. La casilla "Negocio en CRM" sigue
viniendo **premarcada por defecto** (`context={'default_crm_business':
True}`) tanto aquí como desde `product_template_id` en
`crm.opportunity.rule` (`crm_opportunity_rules`), el otro sitio del que se
selecciona un producto en este mismo grupo de módulos.

### Ficha de cliente (`res.partner`)

Nueva pestaña **Perfil comercial** con:

- Tabla de clasificación (sector, actividad, intereses, facturación,
  empleados...).
- Tabla de productos y servicios actuales.

En ambas tablas, al añadir una línea nueva no se ofrecen los tipos de
clasificación (o, en la tabla de productos/servicios, los productos) que el
cliente ya tiene en otra línea — se calcula con un campo `partner_used_*_ids`
que excluye lo ya usado por el resto de líneas del mismo cliente.

### Informes: agrupar/analizar entre clientes

Estos datos viven en líneas (One2many) del cliente, así que no se pueden
agrupar directamente en el listado de Contactos (Odoo agrupa por campos del
propio modelo que se lista, no por campos dentro de líneas hijas). En su
lugar, se exponen dos vistas de lista/pivote independientes, bajo
**CRM > Informes**:

- **Clasificación de clientes**: agrupable por Cliente, Tipo (`attribute_id`)
  o Valor (`value_ids`). Responde a "¿cuántos clientes tienen Sector =
  Calzado?" y, al vivir Sector/Actividad/Interés/Facturación/Empleados en el
  mismo modelo, también permite cruzar dimensiones entre sí en el propio
  pivote (p. ej. Facturación × Sector) abriendo una segunda fila/columna.
- **Productos y servicios actuales**: agrupable por Cliente, Producto/
  servicio, Estado o Proveedor, con filtros rápidos por cada estado ("A
  evolucionar", "A cambiar", "Parados", "Obsoletos") y "En competencia".
  Responde a "¿cuántos clientes tienen este producto marcado como
  obsoleto?" o "¿dónde tenemos un producto en competencia marcado como a
  cambiar?" — el pivote por defecto cruza producto × estado.

Son de solo lectura (`create="false"`) porque la edición real sigue
haciéndose desde la ficha del cliente, donde funciona la exclusión de
valores/productos ya usados.

## Datos precargados

Se cargan **18 tipos de clasificación genéricos**, válidos para cualquier
empresa (no específicos de un sector), pensados para no solapar con
"Productos y servicios actuales" — describen **quién es el cliente**, no
**qué tiene contratado**:

- **Estructura y tamaño**: Sector, Actividad, Empleados (con el tramo "1
  (autónomo)" separado de "2 - 10"), Facturación, EBITDA/margen, Forma
  jurídica, Año de constitución, Grupo empresarial, Modelo de
  propiedad.
- **Geografía**: Alcance geográfico (Local/Regional, Nacional, Internacional
  UE/global) — no duplica país/provincia, que ya están en la ficha estándar
  del contacto.
- **Organización interna**: Departamentos (múltiple), Ciclo de decisión de
  compra.
- **Contexto comercial**: Interés, Canal de venta del cliente,
  Estacionalidad del negocio, Presupuesto en tecnología/servicios, Nivel de
  digitalización.
- **Cumplimiento**: Normativas que le aplican (RGPD, NIS2, ISO 27001,
  PCI-DSS, SII) — pensado explícitamente para disparar reglas de
  oportunidad tipo el ejemplo de NIS2.

Deliberadamente **no** se incluye un tipo de "solvencia/riesgo financiero":
`mercas_base` ya integra `sale_financial_risk`/`account_financial_risk` (el
aviso de riesgo al confirmar pedidos); duplicarlo como clasificación manual
crearía dos fuentes de verdad que podrían desincronizarse.

**"Año de constitución" usa periodos de calendario fijos** (Antes de 2000,
2000-2010, 2011-2020, 2021 en adelante), no tramos relativos tipo "menos de
3 años" — un tramo relativo a "hoy" deja de ser cierto con el tiempo sin que
la situación real del cliente haya cambiado, y habría que ir
reclasificando clientes solo porque pasan los años. Con periodos de
calendario, una empresa fundada en 2015 siempre cae en "2011 - 2020": la
clasificación no caduca nunca.

Se cargan como datos normales (no de demostración) y con `noupdate="1"`:
tanto los tipos como sus valores se crean una vez al instalar el módulo y
**no vuelven a tocarse en actualizaciones futuras**, para no pisar renombres
o archivados que haya hecho el negocio. Cada empresa archiva los tipos que
no le apliquen (p. ej. una empresa que no vende a particulares puede
archivar los valores B2C del Canal de venta) sin miedo a que una
actualización del módulo los reactive o los deshaga.

No se precargan productos ni valores de "Productos y servicios actuales"
— eso ya forma parte del catálogo real de ventas de cada negocio.

Los tramos de Facturación y Empleados llevan `sequence` explícita en cada
valor para conservar su orden natural (0-500k, 500k-2M, 2M-10M, +10M) en
listas, desplegables y agrupados.

## Decisiones de diseño (para no repetir la discusión)

- Se descartó un modelo "perfil" intermedio 1:1 con `res.partner`: los
  campos y tablas cuelgan directamente del partner porque así se editan
  inline en su propia ficha (objetivo "rápido y sencillo") y porque el motor
  de reglas puede usar el editor de dominios estándar de Odoo apuntando
  directamente a `res.partner`, sin un modelo satélite intermedio.
- Sector, Actividad, Interés, Facturación y Empleados comparten el mismo
  mecanismo genérico (`crm.partner.profile.line`); Productos y servicios
  actuales **no** lo usa: primero porque necesita columnas adicionales
  (estado, proveedor) que el mecanismo genérico no contempla, y después
  porque se independizó del todo del catálogo de atributos para apuntar
  directamente al catálogo real de productos (`product.template`), evitando
  mantener un catálogo de "productos" duplicado y desincronizado del real.
- Facturación y Empleados empezaron siendo campos `Selection` fijos en
  `res.partner`, fuera del mecanismo genérico (más seguros en tipo y en
  orden que un catálogo abierto). Se revirtió esa decisión: al vivir en un
  modelo distinto al del resto de la clasificación, quedaban fuera del
  pivote de informes y era imposible cruzarlos con Sector/Actividad en una
  misma vista sin duplicar campos related en `res.partner`. El riesgo que
  motivaba mantenerlos aparte (que alguien desordene o corrompa los tramos)
  ya está cubierto por el control de acceso que **ya existía** para todo el
  catálogo de valores (`crm.partner.attribute.value`): solo
  `sales_team.group_sale_manager` puede crear o editar valores; el resto
  solo puede leerlos y marcarlos. No hizo falta un grupo de permisos nuevo.
- Al independizar Productos y servicios actuales del catálogo de atributos,
  el campo `code` (código reservado) de `crm.partner.attribute` dejó de
  tener consumidores — se eliminó del modelo en vez de dejarlo sin uso.
- El concepto se llamó primero "Tecnologías en producción" y se generalizó a
  "Productos y servicios actuales" (modelo, campos y catálogo renombrados en
  bloque) para que la solución sirviera a cualquier tipo de empresa, no solo
  a las que venden tecnología.

## Dependencias

`crm`, `contacts`, `sale` (necesario para la pestaña Ventas del producto
donde vive el check `crm_business`); todas Community.

## Módulos relacionados

- [`crm_opportunity_rules`](../crm_opportunity_rules): motor de reglas que
  consume este perfil para proponer oportunidades de negocio.
