# Podcast «Primer día en el puesto»: guion

**Duración estimada:** 8–9 minutos leído con naturalidad (unas 1.450 palabras); el borrador sintético dura 6,5 minutos.
**Voces:**
- **LUCÍA**: encargada del puesto, lleva años con el Mostrador.
- **ANDRÉS**: empieza mañana en la báscula.

Para generar el audio:
- **NotebookLM** (recomendado): sube este guion y los capítulos `.md`, y usa *Audio Overview* en español.
- **Borrador local:** `podcast/borrador_podcast.m4a`, generado con las voces de macOS (Mónica y Reed). Sirve para revisar el texto, no para publicar.

---

**[Sintonía corta]**

**LUCÍA:** Bienvenido, Andrés. Mañana empiezas en la báscula y hoy te voy a contar, en un rato, todo lo que necesitas para no perderte con el Mostrador.

**ANDRÉS:** Gracias. Te confieso que me imponen un poco tantas teclas.

**LUCÍA:** Son seis, y tú vas a usar sobre todo tres. El Mostrador es la pantalla táctil del puesto. Cada tarea tiene su tecla: F1 para vender, F2 para comprar, F3 para las cajas, F4 para los lotes, F5 para cobrar y F6 para reponer una etiqueta estropeada. Las compras y los lotes son cosa mía. Tú vivirás en F1, F3 y F5.

**ANDRÉS:** Vale. ¿Y qué es lo primero que tengo que entender?

**LUCÍA:** El lote. Cada mañana, cuando llega la mercancía, yo la doy de alta en F2 y el sistema crea un lote por producto, con un número como 0000001. Ese lote sabe de qué proveedor es, cuándo llegó, de dónde viene y cuántos kilos quedan. Imprimo una etiqueta por caja con ese número.

**ANDRÉS:** O sea, que cuando yo vendo tomate…

**LUCÍA:** …eliges de qué lote sale. El Mostrador te enseña los lotes con stock, el más antiguo primero, para que salga antes lo que lleva más tiempo. Y lo más rápido: si escaneas la etiqueta de la caja, te abre directamente su lote.

**[Pausa]**

**ANDRÉS:** Ahora la báscula. ¿Qué peso apunto?

**LUCÍA:** Esta es la pregunta del millón, así que apúntatela: **en la báscula se escribe siempre el bruto.** El bruto es lo que marca la báscula, fruta y cajas juntas. El neto, que es lo que se cobra, lo calcula el Mostrador: bruto menos el número de cajas por el peso de cada caja.

**ANDRÉS:** ¿Un ejemplo?

**LUCÍA:** Cliente1 se lleva tomate en cinco cajas nuestras, las MARI PILI, que pesan dos kilos y dos cada una. La báscula marca cincuenta. Cinco por dos con dos son once kilos de tara. Neto: treinta y nueve. Tú escribes cincuenta en «Bruto», pones cinco cajas, eliges el tipo MARI PILI, y el neto sale solo: treinta y nueve. Al lado verás escrito «tara 11».

**ANDRÉS:** ¿Y si me equivoco y escribo los cincuenta en el neto?

**LUCÍA:** Pues le cobras al cliente once kilos de plástico a precio de tomate. Por eso te digo la regla de oro: si hay cajas, al lado del neto tiene que verse la palabra «tara». Si no la ves, algo está mal.

**ANDRÉS:** Entendido. ¿Y el tipo de caja importa tanto?

**LUCÍA:** Mucho, por dos motivos. Primero, cada caja pesa distinto: la nuestra, dos con dos, y la del proveedor ASCOY, uno y medio. Si te equivocas de tipo, el neto sale mal. Segundo, el sistema lleva la cuenta de cuántas cajas de cada tipo tiene cada cliente, y luego nos las tiene que devolver. Así que si la pera sale en las mismas cajas en que la compramos, eliges ASCOY. Si la reenvasas en las nuestras, MARI PILI.

**ANDRÉS:** ¿Y si el cliente se lleva dos pesadas?

**LUCÍA:** El teclado de la pantalla tiene calculadora. Escribes «24,4 por 2», o «24,4 más 23,9», pulsas igual y listo. Nada de sumar de cabeza.

**[Pausa]**

**ANDRÉS:** Ya tengo la línea. ¿Y luego?

**LUCÍA:** Pulsas «Añadir» y la línea pasa al ticket de la derecha. Repites con cada producto. Y fíjate en una cosa: arriba del ticket pone «Guardado». Todo se guarda solo. Si te llaman a mitad de una venta, sales con la flecha y luego la retomas desde la lista «En curso».

**ANDRÉS:** ¿Y si el cliente regatea el precio?

**LUCÍA:** En el ticket, el precio de cada línea es un botón. Lo tocas, escribes el precio nuevo y el subtotal cambia al momento. Con «Siguiente» pasas a la línea de abajo. Es como en una caja registradora: la primera tecla sustituye el precio.

**ANDRÉS:** Y para terminar, «Vender y entregar».

**LUCÍA:** Exacto. Un solo botón: confirma el pedido y da por entregada la mercancía. Te fijarás en que el total es algo más alto que la suma de la fruta: lleva el IVA y además las cajas, que se cobran como envase. Cuando el cliente nos las devuelve, se le abonan.

**[Pausa]**

**ANDRÉS:** Aquí viene lo que me lía: unos clientes pagan y otros no.

**LUCÍA:** Tenemos dos tipos. Los de fin de mes, como Cliente1, se llevan solo el albarán: después de «Vender y entregar» le das a «Imprimir», sale el albarán y se acabó. A fin de mes yo les hago la factura de todo lo que se han llevado y se la cobro.

**ANDRÉS:** ¿Y los de contado?

**LUCÍA:** Como Cliente2. Después de «Vender y entregar» le das a «Facturar». La factura se crea en el momento. Luego, «Cobrar»: se abre la pantalla de cobros con la factura ya marcada y el importe puesto. Eliges «Tarjeta» o «Efectivo» y le das a «Cobrar».

**ANDRÉS:** ¿Algún truco?

**LUCÍA:** Uno importante: el Mostrador recuerda el último medio de pago que usaste. Si el anterior pagó con tarjeta y este paga en efectivo, cambia el botón antes de cobrar. Si no, la caja no te cuadrará por la noche.

**[Pausa]**

**ANDRÉS:** Hablemos de las cajas que devuelven.

**LUCÍA:** Para eso está F3. Eliges el cliente y ves cuántas cajas nuestras tiene de cada tipo; las que tiene salen las primeras. Pones con el más cuántas te devuelve. Y abajo del todo eliges qué hacemos con el dinero de esas cajas: «Saldo para próximas facturas» o «Pagar ahora».

**ANDRÉS:** ¿Cuál uso?

**LUCÍA:** Con los clientes de fin de mes, casi siempre saldo. El importe queda a su favor y, cuando yo le cobre la factura, aparece debajo como «Saldo a favor del cliente». Lo marco y se descuenta solo: si la factura son unos ciento cuatro euros y el saldo seis, se cobran noventa y ocho. «Pagar ahora» es para cuando el cliente quiere su dinero en el momento.

**ANDRÉS:** ¿Y si no le doy a ninguna?

**LUCÍA:** El botón «Recibir y abonar» no se activa hasta que eliges una. No te puedes equivocar por despiste.

**[Pausa]**

**ANDRÉS:** Has dicho F6 para etiquetas.

**LUCÍA:** Si se moja o se rompe una etiqueta, en F6 escaneas lo que se pueda leer o escribes el número de lote, y te salen sus etiquetas. Ojo: te propone tantas como cajas se compraron, diez por ejemplo. Si solo se ha roto una, cambia el número a uno antes de imprimir, o gastarás un rollo entero.

**ANDRÉS:** ¿Y F4, los lotes?

**LUCÍA:** Eso es mío, pero te lo cuento para que lo entiendas. Ahí veo cada lote con una barra: verde lo vendido, rojo lo que se ha tirado, azul lo que queda. Si algo se pudre, lo desecho desde ahí. Y desde ahí pago a los proveedores.

**ANDRÉS:** ¿No se les paga a todos igual?

**LUCÍA:** No. Unos van en firme: les pagamos todo lo que nos traen, al precio pactado, vendamos o no. Otros van en liquidación por venta: les pagamos lo que vendemos menos nuestro margen, y lo que se tira no lo cobran. En la tarjeta del lote, los firmes llevan una etiqueta azul que dice «Firme».

**ANDRÉS:** ¿Y cómo se les paga a los de liquidación?

**LUCÍA:** Si el lote ya se ha acabado, «Liquidar». Si aún queda género pero el proveedor quiere cobrar algo, «Facturar adelanto». Y una cosa que confunde: si le das a «Liquidar» a un lote que todavía tiene stock, sale «No hay lotes que facturar». No es un error del programa: ese lote no está terminado.

**[Pausa]**

**ANDRÉS:** Resumiendo, para que me quede…

**LUCÍA:** Venga, cinco frases. Una: en la báscula, el bruto, siempre. Dos: el tipo de caja, el de verdad, el de la compra o el nuestro. Tres: si el cliente es de contado, facturar y cobrar, mirando bien si es tarjeta o efectivo. Cuatro: si devuelve cajas y paga a fin de mes, saldo. Y cinco: si te equivocas o te interrumpen, tranquilo, que todo queda guardado en «En curso».

**ANDRÉS:** Pues mañana a la báscula.

**LUCÍA:** Y si tienes dudas, en la carpeta de formación tienes cada paso con capturas y un ejercicio de un día completo para practicar en la base de pruebas. Suerte, Andrés.

**[Sintonía de cierre]**
