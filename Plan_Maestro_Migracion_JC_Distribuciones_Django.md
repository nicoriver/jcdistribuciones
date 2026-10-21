# Plan maestro de migración a Django

## Sistema comercial mayorista — JC Distribuciones

**Estado:** Línea base inicial para validación  
**Estrategia:** MVP rápido con mejoras posteriores  
**Destino:** Aplicación web Django + PostgreSQL en VPS Hostinger

---

## 1. Objetivo del proyecto

Reemplazar la aplicación de escritorio actualmente utilizada en producción por una aplicación web responsive, accesible desde computadoras, celulares y futuras tablets. La solución se alojará en el VPS existente y permitirá la operación interna de JC Distribuciones y el ingreso de pedidos por parte de sus clientes mayoristas.

El desarrollo .NET de escritorio analizado no es el sistema productivo: es un reemplazo en desarrollo que reproduce fielmente la operación actual. Se utilizarán su código y documentación como especificación funcional. La migración histórica se realizará desde la base de datos del sistema productivo.

## 2. Principios de diseño acordados

1. Construir inicialmente para JC Distribuciones, pero separar módulos y reglas para facilitar su reutilización futura en otras empresas.
2. Desarrollar el sistema interno y el portal de clientes como partes de la primera versión.
3. Migrar todo el historial necesario para que cada cliente conserve sus ventas anteriores.
4. Priorizar trazabilidad, integridad de cantidades e importes y auditoría de cambios.
5. Implementar un MVP utilizable sin esperar la integración con ARCA.
6. Mantener la lógica comercial parametrizable y evitar reglas rígidas en las pantallas.
7. Separar el movimiento físico de mercadería, los documentos comerciales y los comprobantes fiscales.

## 3. Sistemas involucrados

| Sistema | Situación | Uso en el proyecto |
|---|---|---|
| Aplicación .NET productiva | En producción y con operaciones diarias | Fuente de los datos históricos para la migración final |
| Desarrollo .NET equivalente | En desarrollo, con base propia equivalente | Fuente funcional principal y referencia de reglas, pantallas y cálculos |
| Nuevo sistema Django | A construir | Reemplazo web definitivo |

## 4. Alcance funcional del MVP

### 4.1 Administración y seguridad

- Inicio de sesión de clientes mediante CUIT.
- Usuarios internos con usuario y contraseña propios del sistema.
- Recuperación segura de acceso.
- Contraseñas almacenadas mediante hash seguro con sal.
- Sin segundo factor en el MVP.
- Perfiles internos:
  - Administrador.
  - Vendedor.
  - Facturación.
  - Preparación o depósito.
  - Consulta y reportes.
- Cada vendedor consulta solamente sus clientes y sus pedidos.
- Registro de auditoría para altas, modificaciones, cambios de estado, precios, descuentos y emisión/anulación de comprobantes.

### 4.2 Clientes

- Alta administrativa de cuentas.
- Autorregistro del cliente sujeto a aprobación interna.
- Un usuario y una dirección por cliente en el MVP.
- Asignación de vendedor, zona, día de reparto y lista de precios.
- Conservación del historial de operaciones migradas.

### 4.3 Proveedores y costos

- Administración de proveedores.
- Registro y actualización de costos de artículos.
- No se implementará todavía el circuito completo de compras, recepción y cuentas a pagar.
- El modelo quedará preparado para incorporar compras y actualización de stock en una fase posterior.

### 4.4 Artículos y catálogo

- Código interno y código de barras, cuando corresponda.
- Nombre, descripción, marca y categoría.
- Imagen de producto.
- IVA asociado.
- Estado activo/inactivo.
- Catálogo común para todos los clientes activos.
- Presentaciones múltiples:
  - Unidad.
  - Pack o paquete.
  - Caja o bulto.
  - Peso o cantidad fraccionada.
- Equivalencias entre presentación y unidad base.
- Disponibilidad mostrada de forma informativa.

### 4.5 Listas, precios y descuentos

- Cada cliente tendrá una lista de precios asignada.
- El precio de lista se almacenará como valor neto sin IVA.
- Las reglas generales podrán combinar cliente, artículo y lista.
- El vendedor podrá aplicar un descuento adicional por renglón durante la preparación comercial y antes de la facturación.
- El descuento deberá quedar visible en el remito.
- Los precios y descuentos aplicados se copiarán al pedido para conservar la condición vigente al momento del envío.
- Un cambio posterior de lista no modificará pedidos ya enviados.
- Condiciones configurables de pedido mayorista:
  - Monto mínimo total.
  - Cantidad mínima por artículo o presentación.

### 4.6 Portal de clientes

- Catálogo responsive con imágenes, marca, categoría, presentaciones, precio y disponibilidad.
- Búsqueda y filtros.
- Favoritos.
- Repetición de pedidos anteriores.
- Carga rápida mediante código y cantidad.
- Carrito o borrador editable hasta el envío.
- Al enviarse, el pedido queda bloqueado para el cliente y pasa a revisión interna.
- Se permite solicitar cantidades superiores a la disponibilidad, indicando que quedan sujetas a confirmación.
- Estados visibles para el cliente:
  - Enviado.
  - En revisión.
  - Aprobado.
  - Rechazado.
- Notificaciones dentro del portal y por correo electrónico.
- Descarga de pedidos y remitos.
- Facturas y notas de crédito no se expondrán inicialmente en el portal.

### 4.7 Pedidos y aprobación

- Todos los pedidos requieren aprobación interna.
- El cliente puede modificar o cancelar únicamente antes de enviarlos.
- El vendedor revisa artículos, cantidades, condiciones mínimas y descuentos.
- Los pedidos conservan una fotografía de precios, descuentos, IVA y presentaciones aplicadas.
- Una factura puede agrupar uno o varios pedidos según decisión del vendedor.
- Se admite más de un remito por pedido en casos excepcionales.

### 4.8 Remitos

- Emisión en hoja A4.
- Diseño lo más fiel posible al comprobante actual.
- No discrimina IVA visualmente.
- Debe mostrar el descuento aplicado en cada artículo.
- Reparto propio organizado por zonas y días fijos.
- El costo del reparto está incluido en los precios.
- No se incorporará en el MVP firma, fotografía, geolocalización ni confirmación de recepción.

### 4.9 Facturas y notas de crédito

- El MVP puede publicarse inicialmente con pedidos y remitos, sin integración fiscal completa.
- La integración posterior con ARCA deberá contemplar:
  - Factura A.
  - Factura B.
  - Nota de Crédito A.
  - Nota de Crédito B.
- El módulo ARCA existente en .NET será auditado; no se lo considerará reutilizable sin evaluación.
- Las notas de crédito conservarán dos clasificaciones:
  - Tipo fiscal ARCA: NCA o NCB.
  - Motivo interno: devolución (NC) o faltante (NCF).
- Frente a una falla de ARCA, el comprobante quedará pendiente. Se permitirán reintentos manuales controlados y una decisión posterior del usuario, sin reintentos automáticos indefinidos.

### 4.10 Faltantes y devoluciones

- Operación habitual de faltantes:
  1. Se factura el pedido.
  2. Se retira o prepara físicamente la mercadería.
  3. Se identifican cantidades faltantes.
  4. Se genera la nota de crédito fiscal correspondiente con motivo interno NCF.
- Las devoluciones posteriores generan una nota de crédito con motivo interno NC.
- Cada devolución se imputa manualmente a uno o varios renglones de comprobantes originales.
- El sistema debe impedir devolver más cantidad que la vendida menos devoluciones anteriores.
- Facturas y remitos pueden representar cantidades vendidas separadas.
- El vendedor decide si el artículo devuelto vuelve al stock disponible.

### 4.11 Stock

- El control de stock estará deshabilitado inicialmente.
- Existirá una configuración general para habilitarlo.
- Con el control general activo, cada artículo podrá activar o desactivar individualmente su control.
- Un comprobante que deje stock negativo mostrará una advertencia, pero permitirá continuar.
- Facturas y remitos que representen ventas separadas generan movimientos separados.
- Todo movimiento debe registrar documento origen, artículo, presentación, cantidad, usuario, fecha y motivo.
- La devolución puede reincorporar stock solo por decisión explícita del vendedor.
- Debe evitarse que factura y remito descuenten dos veces cuando documenten la misma operación; esta condición se validará en el diseño detallado y las pruebas de migración.

### 4.12 Reportes y paneles

Reportes prioritarios:

- Ventas por período, cliente y vendedor.
- Ventas por artículo, marca y categoría.
- Pedidos aprobados, rechazados y pendientes.
- Remitos, devoluciones y faltantes.

Indicadores del panel:

- Ventas y pedidos del día y del mes.
- Productos más vendidos.
- Clientes con mayor volumen de compra.
- Faltantes y devoluciones.

Formatos:

- Consulta en pantalla.
- Excel.
- PDF.
- Impresión directa.

## 5. Fuera del MVP

- Integración completa con ARCA, salvo que se priorice durante el desarrollo.
- Cobranzas y medios de pago.
- Cuenta corriente, crédito, límites y deuda vencida.
- Compras, pedidos a proveedores y recepción de mercadería.
- Prueba digital de entrega.
- Varios usuarios o varias sucursales por cliente.
- Multiempresa completo.
- Segundo factor de autenticación.
- Aplicación móvil nativa.

## 6. Arquitectura propuesta

### 6.1 Componentes

- Django como aplicación principal.
- PostgreSQL como base de datos.
- Interfaz web responsive renderizada por Django, evitando una SPA innecesaria para el MVP.
- Tareas en segundo plano solo donde aporten valor: correos, generación pesada de reportes y futuras comunicaciones con ARCA.
- Nginx como proxy inverso.
- Gunicorn como servidor de aplicación.
- Archivos estáticos y multimedia administrados fuera del repositorio.
- Certificado HTTPS obligatorio.

### 6.2 Organización modular sugerida

- `accounts`: usuarios, roles, permisos y auditoría.
- `customers`: clientes, vendedores, zonas y días de reparto.
- `suppliers`: proveedores y costos.
- `catalog`: artículos, marcas, categorías, imágenes y presentaciones.
- `pricing`: listas, precios, descuentos, vigencias e IVA.
- `orders`: borradores, pedidos, aprobación y estados.
- `documents`: remitos y relaciones entre comprobantes.
- `returns`: devoluciones, faltantes e imputaciones.
- `inventory`: configuración y libro de movimientos de stock.
- `reports`: consultas, exportaciones y paneles.
- `notifications`: avisos internos y correo.
- `fiscal`: futura integración con ARCA.
- `migration_legacy`: procesos repetibles de migración y conciliación.

### 6.3 Criterios técnicos

- Servicios de dominio para cálculos y cambios de estado importantes.
- Transacciones de base de datos para operaciones con múltiples tablas.
- Estados explícitos; no inferir procesos críticos a partir de campos dispersos.
- Historial inmutable de precios y condiciones aplicadas en cada pedido.
- Libro de movimientos de stock en lugar de modificar existencias sin trazabilidad.
- Numeración de documentos protegida frente a concurrencia.
- Importes monetarios con tipo decimal; nunca punto flotante.
- Fechas almacenadas con zona horaria y mostradas en horario de Argentina.

## 7. Estrategia de migración de datos

La migración se realizará desde la base productiva hacia PostgreSQL. El desarrollo .NET y su base equivalente servirán para comprender el modelo destino, pero no reemplazarán la fuente productiva.

### 7.1 Etapas

1. Inventario de tablas, claves, procedimientos y volúmenes de la base productiva.
2. Perfilado de calidad: duplicados, CUIT inválidos, referencias huérfanas, fechas e importes inconsistentes.
3. Diccionario de correspondencia origen-destino.
4. Scripts de extracción, transformación y carga repetibles.
5. Migración de ensayo en el ambiente de pruebas.
6. Conciliación por cantidades, totales, clientes, artículos y documentos.
7. Corrección de reglas y nueva ejecución completa.
8. Ensayo general de corte.
9. Congelamiento de escritura del sistema productivo.
10. Copia final, migración, conciliación y habilitación web.
11. Conservación del respaldo previo al corte y plan de reversión.

### 7.2 Controles mínimos de conciliación

- Cantidad de clientes, proveedores y artículos.
- Cantidad de documentos por tipo y año.
- Totales monetarios por mes y tipo de comprobante.
- Cantidades vendidas y devueltas por artículo.
- Relaciones entre cabecera y detalle.
- Historial por cliente.
- Muestras funcionales revisadas manualmente.

## 8. Infraestructura y operación

- VPS Hostinger existente.
- Subdominio de `cognitivalabs.ar` para producción.
- Subdominio separado para pruebas.
- Base PostgreSQL independiente para cada ambiente.
- Hasta 50 clientes y 10 usuarios internos durante el primer año.
- Correo saliente mediante Gmail o Google Workspace.
- Aplicación y base alojadas en el VPS.
- Respaldo automático diario enviado a Google Drive.

### 8.1 Política de respaldo

Cada respaldo incluirá:

- Volcado consistente de PostgreSQL.
- Imágenes y demás archivos subidos.
- Configuración necesaria para restaurar, excluyendo la exposición de secretos en texto plano.

Retención:

- Copias diarias durante 30 días.
- Copias mensuales durante 12 meses.
- Verificación periódica mediante restauración de prueba.

## 9. Plan de ejecución incremental

### Fase 0 — Auditoría y línea base

- Inspeccionar código y base del desarrollo .NET.
- Inspeccionar estructura y muestras anonimizadas de la base productiva.
- Comparar documentación con comportamiento real.
- Cerrar diccionario de datos y reglas de precio.
- Capturar el diseño A4 del remito actual.

### Fase 1 — Fundación técnica

- Repositorio, configuración por ambientes y calidad de código.
- Proyecto Django y PostgreSQL.
- Usuarios internos, perfiles, permisos y auditoría.
- Despliegue inicial en ambiente de pruebas.
- Backups automatizados y prueba de restauración.

### Fase 2 — Maestros comerciales

- Clientes, vendedores, zonas y reparto.
- Proveedores y costos.
- Artículos, marcas, categorías, imágenes y presentaciones.
- Listas de precios, IVA y descuentos.

### Fase 3 — Portal y pedidos

- Acceso de clientes por CUIT.
- Registro y aprobación de cuentas.
- Catálogo, filtros, favoritos y repetición.
- Borrador, mínimos, envío y estados.
- Revisión y aprobación interna.
- Notificaciones web y por correo.

### Fase 4 — Remitos, faltantes y devoluciones

- Preparación comercial y descuento por renglón.
- Remito A4 fiel al actual.
- Entregas parciales excepcionales.
- NC y NCF internas con imputación a documentos originales.
- Libro opcional de movimientos de stock.

### Fase 5 — Migración histórica

- Construir y ejecutar el proceso de migración.
- Conciliar resultados.
- Probar consultas históricas por cliente.
- Realizar al menos un ensayo completo de corte.

### Fase 6 — Reportes y estabilización

- Panel e indicadores.
- Reportes operativos.
- Exportación a Excel y PDF.
- Pruebas de rendimiento, permisos, concurrencia e impresión.
- Correcciones surgidas de validación personal.

### Fase 7 — Puesta en producción

- Respaldo previo.
- Congelamiento del sistema anterior.
- Migración final.
- Conciliación.
- Cambio de subdominio o habilitación productiva.
- Monitoreo intensivo y plan de reversión.

### Fase 8 — Integración ARCA

- Auditoría del módulo .NET existente.
- Revisión de requisitos fiscales actuales.
- Homologación.
- Emisión de A/B y NCA/NCB.
- Manejo de pendientes y reintentos manuales.
- Trazabilidad entre pedido, factura, remito y NC/NCF.

## 10. Criterios de aceptación del MVP

El MVP estará listo cuando:

1. Un cliente aprobado pueda ingresar por CUIT, consultar catálogo, armar y enviar un pedido.
2. El pedido conserve precios y condiciones del momento del envío.
3. Un vendedor pueda revisar y aprobar o rechazar únicamente pedidos de sus clientes.
4. El personal pueda preparar el pedido, aplicar descuentos autorizados y emitir el remito A4.
5. Puedan registrarse faltantes y devoluciones vinculados a documentos originales.
6. Los movimientos de stock sean opcionales, auditables y no se dupliquen.
7. El cliente pueda consultar estados iniciales y descargar pedidos y remitos.
8. Los reportes principales concilien con la información histórica migrada.
9. Los permisos impidan accesos indebidos entre vendedores y perfiles.
10. La copia automática y una restauración de prueba hayan sido verificadas.
11. La migración de ensayo y la final superen los controles de conciliación.
12. El responsable del proyecto valide personalmente los circuitos críticos.

## 11. Riesgos principales y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Diferencias entre la base productiva y la base del desarrollo equivalente | Auditar ambas estructuras y construir un diccionario de correspondencia explícito |
| Migración incompleta o totales inconsistentes | Scripts repetibles, conciliación automática y ensayos completos antes del corte |
| Doble descuento de stock entre factura y remito | Libro de movimientos con documento origen e idempotencia por operación |
| Fórmulas de precios ambiguas | Casos de prueba con ejemplos reales aprobados antes de programar |
| Descuentos posteriores a la facturación | Cerrar precio y descuento antes de emitir el comprobante fiscal |
| Faltantes y devoluciones superiores a lo vendido | Saldo devolvible por renglón y validaciones transaccionales |
| Caída o lentitud de ARCA | Estado pendiente, reintento manual y registro de cada intento |
| Pérdida de información en el VPS | Respaldo externo diario, retención y restauraciones de prueba |
| Cambios directos en producción | Ambiente de pruebas separado y procedimiento de despliegue reproducible |
| Exceso de alcance | Mantener fuera del MVP cobranzas, compras completas, multiempresa y logística avanzada |

## 12. Próximo paso recomendado

Realizar la **Fase 0 — Auditoría y línea base**. El primer entregable técnico debe contener:

1. Inventario real del repositorio .NET de desarrollo.
2. Diagrama y diccionario de su base equivalente.
3. Inventario de la base productiva.
4. Comparación de entidades y campos entre ambas bases.
5. Diez casos comerciales reales con valores esperados de precios, descuentos, IVA, remitos, faltantes y devoluciones.
6. Propuesta definitiva de modelo Django/PostgreSQL.
7. Backlog del MVP dividido en entregas pequeñas.

No se recomienda comenzar programando pantallas antes de completar esta auditoría, porque la migración histórica y las reglas de documentos condicionan el modelo de datos.
