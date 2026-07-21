# CRM Business Survey

Depende de [`crm_business_product`](../crm_business_product) y añade el
seguimiento de **encuestas** (`survey.survey`) asociadas al tipo de producto
de la oportunidad.

## Funcionalidad

### Tipos de producto (`crm.business.product.type`)

Añade el campo **Encuestas** (`survey_ids`, `survey.survey`, widget de tags)
al modelo y a las vistas definidas en `crm_business_product`.

### Oportunidades (`crm.lead`)

- Debajo del campo **Procedimiento**: un botón **Cumplimentar** por cada
  encuesta pendiente, en función de las encuestas definidas en el tipo de
  producto del producto elegido
  (`product_template_id.crm_business_product_type_id.survey_ids`). Las
  líneas se generan automáticamente (`crm.lead.survey.line`) cada vez que se
  asigna o cambia el producto de la oportunidad. La columna interna con la
  referencia al `survey.user_input` está oculta (`column_invisible`): sólo
  se usa como dato para los botones, no hace falta mostrarla.
- Al pulsar **Cumplimentar** se crea la respuesta (`survey.user_input`) y se
  abre la encuesta **en una pestaña nueva**; el botón desaparece y en su
  lugar aparece un botón **Ver / editar**.
- **Ver / editar** reabre la encuesta (también en pestaña nueva) para
  revisar o cambiar las respuestas ya dadas. Si la encuesta ya estaba
  completada, se reactiva (`state` a `in_progress`, `end_datetime` y
  `last_displayed_page_id` a vacío) para que el flujo se reanude desde la
  primera página en vez de mostrar la pantalla de "ya respondida" (o dar
  error). Si además la encuesta **no** tiene activada la opción "Los
  usuarios pueden retroceder" (`users_can_go_back`), también se borran las
  respuestas anteriores al reabrirla: Odoo no permite sobrescribir una
  respuesta ya guardada salvo que esa opción esté activada, así que sin
  vaciarlas la edición daría el error "Esta respuesta no se puede
  sobrescribir".

  > **Recomendación al diseñar las encuestas**: para poder editarlas después
  > sin perder las respuestas ya dadas, crea las encuestas con las preguntas
  > **sueltas** o **por secciones** (`questions_layout` = "Una pregunta por
  > página" o "Todas las preguntas de una sección por página"), **no** con
  > el diseño "Una página" — con ese diseño no existe el concepto de
  > "página anterior" y la opción de abajo ni siquiera aparece. Además, hay
  > que activar la casilla **"Permitir roaming"** (`users_can_go_back`; así
  > se llama el campo en la interfaz, aunque el nombre técnico es "Users can
  > go back"), en la propia encuesta, pestaña **Opciones** → grupo
  > **Preguntas**. Sin esas dos cosas, "Ver / editar" solo podrá reabrir la
  > encuesta borrando las respuestas anteriores para empezar de nuevo.
- Nueva pestaña **Respuestas de encuestas**, sólo visible si hay alguna
  encuesta ya completada, con un resumen en HTML de solo lectura (una
  tarjeta por encuesta, con sus preguntas y respuestas). Se muestra una
  tarjeta por cada encuesta en estado `done`, aunque no tenga líneas de
  respuesta (indicándolo con un mensaje), para que ninguna encuesta
  completada quede oculta del resumen.
  - Aviso: como la encuesta se rellena en una pestaña nueva, si se
    completa y se vuelve a la pestaña original de la oportunidad sin
    recargarla, ésta seguirá mostrando los datos de su última carga (Odoo
    no refresca automáticamente una pestaña distinta). Es una limitación
    aceptada conscientemente: implementarlo (sondeo periódico o
    notificaciones por el bus de Odoo) requeriría añadir JavaScript propio
    al módulo, que de momento es solo Python y vistas. Basta con recargar
    (F5) la oportunidad para ver el resumen al día.

## Seguridad

Los comerciales (`sales_team.group_sale_salesman`) pueden leer `survey.survey`
y `survey.user_input` (necesario para mostrar los campos en las vistas). La
creación real de las respuestas y la modificación de su estado se hacen
siempre vía `sudo()` dentro de acciones controladas por este módulo, sin
conceder acceso amplio al módulo de encuestas.

## Dependencias

`crm_business_product`, `survey` (ambas Community).
