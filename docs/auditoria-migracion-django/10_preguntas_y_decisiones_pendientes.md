# 10. Preguntas Bloqueantes y Decisiones Pendientes
## Cuestionario Técnico-Operativo para la Dirección y el Equipo de Desarrollo

---

## 1. Introducción
Para avanzar con el diseño final de los modelos ORM en Django y la ejecución del plan de migración de datos, existen **decisiones clave de negocio y arquitectura** que deben ser definidas formalmente por la dirección de **JC Distribuciones**.

---

## 2. Cuestionario de Decisiones por Área

### 2.1 Modelo Comercial y Módulos a Incorporar en el MVP Django

1. **Gestión de Cuenta Corriente y Cobranzas**:
   - *Antecedente*: Producción posee el módulo de Cta. Cte. (`MovimientoCtaCte`), pero el desarrollo .NET lo omitió. La consigna indica que el MVP de Django no tendrá cobranzas ni Cta. Cte. inicialmente.
   - **Pregunta Bloqueante 1.1**: ¿Cómo se gestionará en el MVP la venta a clientes con condición de pago "Cuenta Corriente"? ¿Se registrarán las facturas en estado `PENDIENTE_PAGO` sin libro mayor, o se migrará el histórico de deudas de producción como saldo inicial?

2. **Flujo de Pedidos y Pre-Ventas**:
   - *Antecedente*: En producción existen los pedidos pre-venta de los vendedores. En Django, el portal de clientes permitirá ingresar pedidos.
   - **Pregunta Bloqueante 1.2**: ¿Todos los pedidos ingresados por clientes en el portal requerirán aprobación manual por parte de un vendedor/administrador antes de pasar a preparación y facturación?

3. **Políticas de Stock e Inventario**:
   - *Antecedente*: La consigna indica que el control de stock estará deshabilitado inicialmente, y cuando se habilite, permitirá continuar con advertencia ante saldo insuficiente.
   - **Pregunta Bloqueante 1.3**: ¿Se desea que el sistema descuente stock al emitir el Remito, al emitir la Factura, o al cambiar el pedido a estado `PREPARADO`? ¿Cómo se resolverá el caso actual de producción donde remito y factura descuentan doblemente?

---

### 2.2 Tratamiento de Datos Históricos y Limpieza de Producción

4. **Consolidación de Tablas Clonadas**:
   - *Antecedente*: Producción contiene las tablas fragmentadas `articulo1`, `articulo2`, `comprobante1`, `comprobante2`, etc.
   - **Pregunta Bloqueante 2.1**: ¿Se autoriza la unificación masiva (`UNION ALL` y deduplicación) de estas tablas históricas en PostgreSQL, o existe algún motivo operativo por el cual deban permanecer aisladas?

5. **Blanqueo de Contraseñas de Usuarios**:
   - *Antecedente*: Las contraseñas actuales están en texto plano en la base de datos de producción.
   - **Pregunta Bloqueante 2.2**: ¿Se aprueba forzar el blanqueo y reseteo obligatorio de contraseña para todos los usuarios/vendedores en su primer acceso al nuevo sistema web Django?

6. **Tratamiento de Comprobantes Huérfanos**:
   - *Antecedente*: Existen comprobantes en producción cuya referencia a `id_cliente` apunta a registros inexistentes o borrados.
   - **Pregunta Bloqueante 2.3**: ¿Se aprueba imputar dichos comprobantes huérfanos a un cliente genérico de auditoría llamado `CONSUMIDOR FINAL HISTÓRICO (MIGRACIÓN)`?

---

### 2.3 Reglas Fiscales e Integración AFIP / ARCA

7. **Estrategia de Facturación Electrónica**:
   - *Antecedente*: El desarrollo .NET posee un microservicio simulado (`src/webafip`). Producción emite comprobantes locales.
   - **Pregunta Bloqueante 3.1**: ¿En la primera fase de salida a producción con Django, el sistema emitirá comprobantes locales (Factura/Remito interno) y la integración directa con AFIP (obtención de CAE vía WSFEv1) se habilitará en una fase posterior?

8. **Discriminación de IVA por Producto**:
   - *Antecedente*: El desarrollo .NET calcula el IVA aplicando un 21% global sobre el total del comprobante.
   - **Pregunta Bloqueante 3.2**: ¿Existen en el catálogo actual productos con alícuotas diferenciadas del 10.5% o 27% que requieran discriminación renglón por renglón en las Facturas A?

---

### 2.4 Infraestructura y Despliegue

9. **Infraestructura de Servidores**:
   - **Pregunta Bloqueante 4.1**: ¿Se cuenta con servidor propio (On-Premise) o infraestructura en la nube (AWS / DigitalOcean / Hertzner) para el despliegue de PostgreSQL, Django, Redis y Celery?

---

## 3. Matriz de Priorización de Decisiones

| ID Decision | Asunto / Tema | Impacto Técnico | Prioridad | Responsable Requerido |
| :--- | :--- | :--- | :--- | :--- |
| **D-01** | Consolidación de tablas clonadas en ETL | Estructura de BD PostgreSQL | **ALTA** | Dirección / IT |
| **D-02** | Blanqueo de contraseñas de usuarios | Seguridad / Autenticación | **ALTA** | Seguridad / IT |
| **D-03** | Definición del momento de descuento de stock | Lógica del Dominio Stock | **ALTA** | Operaciones |
| **D-04** | Salida inicial sin AFIP (Factura Local) | Alcance de Salida a Producción | **MEDIA** | Administración |
