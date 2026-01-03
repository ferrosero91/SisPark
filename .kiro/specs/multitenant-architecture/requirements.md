# Requirements Document

## Introduction

Este documento define los requisitos para transformar el sistema de estacionamiento SoluPark en una plataforma multitenant completa. La reforma incluye: arquitectura multitenant con panel de superadministrador, gestión de terceros y mensualidades, control de acceso granular por módulos, mejoras de seguridad, y rediseño de la interfaz de usuario.

## Glossary

- **Tenant**: Organización/parqueadero individual que opera de forma aislada dentro de la plataforma
- **SuperAdmin**: Usuario con acceso global a todos los tenants y configuración de la plataforma
- **ParkingLot**: Entidad que representa un parqueadero específico (tenant)
- **Third_Party**: Cliente o tercero registrado que puede tener contratos mensuales
- **Monthly_Contract**: Contrato de mensualidad asociado a un tercero y vehículo
- **Module**: Funcionalidad específica del sistema (ej: Ingresos, Reportes, Caja)
- **Access_Control**: Sistema que determina qué módulos puede ver/usar cada usuario
- **User_Profile**: Perfil extendido del usuario con permisos y tenant asociado

---

## Requirements

### Requirement 1: Arquitectura Multitenant Base

**User Story:** Como propietario de la plataforma, quiero que múltiples parqueaderos operen de forma independiente en el mismo sistema, para poder ofrecer el servicio a diferentes clientes.

#### Acceptance Criteria

1. THE System SHALL aislar completamente los datos de cada tenant (parqueadero)
2. WHEN un usuario inicia sesión, THE System SHALL cargar automáticamente el contexto de su tenant
3. THE System SHALL garantizar que ningún usuario pueda acceder a datos de otro tenant
4. WHEN se realizan consultas a la base de datos, THE System SHALL filtrar automáticamente por tenant activo
5. THE System SHALL soportar subdominios o rutas para identificar cada tenant (ej: parking1.solupark.shop o solupark.shop/parking1)
6. IF un usuario intenta acceder a recursos de otro tenant, THEN THE System SHALL denegar el acceso y registrar el intento

---

### Requirement 2: Panel de SuperAdmin

**User Story:** Como superadministrador, quiero un panel centralizado para gestionar todos los parqueaderos de la plataforma, para poder administrar el negocio de forma eficiente.

#### Acceptance Criteria

1. THE SuperAdmin_Panel SHALL permitir crear nuevos parqueaderos (tenants)
2. THE SuperAdmin_Panel SHALL permitir editar información de parqueaderos existentes
3. THE SuperAdmin_Panel SHALL permitir activar/desactivar parqueaderos
4. WHEN un parqueadero es desactivado, THE System SHALL impedir el acceso de todos sus usuarios mostrando mensaje de cuenta suspendida
5. THE SuperAdmin_Panel SHALL permitir eliminar parqueaderos permanentemente con confirmación
6. WHEN se elimina un parqueadero, THE System SHALL eliminar todos los datos asociados (usuarios, tickets, terceros, contratos)
7. THE SuperAdmin_Panel SHALL permitir cambiar la contraseña del administrador de cualquier parqueadero
8. THE SuperAdmin_Panel SHALL mostrar estadísticas globales de todos los parqueaderos
9. WHEN el superadmin crea un parqueadero, THE System SHALL generar automáticamente un usuario administrador para ese tenant
10. THE SuperAdmin_Panel SHALL permitir acceder a cualquier parqueadero en modo visualización (impersonar)
11. THE SuperAdmin_Panel SHALL mostrar un dashboard con métricas de uso por tenant
12. THE SuperAdmin_Panel SHALL permitir configurar planes y límites por tenant
13. THE SuperAdmin_Panel SHALL mostrar estado de pago/suscripción de cada parqueadero
14. THE SuperAdmin_Panel SHALL permitir enviar notificaciones a administradores de parqueaderos
15. THE SuperAdmin_Panel SHALL registrar todas las acciones del superadmin en log de auditoría

---

### Requirement 3: Gestión de Seguridad

**User Story:** Como administrador del sistema, quiero que las credenciales y datos sensibles estén protegidos adecuadamente, para cumplir con estándares de seguridad.

#### Acceptance Criteria

1. THE System SHALL almacenar todas las credenciales en variables de entorno
2. THE System SHALL generar SECRET_KEY única por instalación
3. THE System SHALL implementar rate limiting en endpoints de autenticación
4. THE System SHALL registrar todos los intentos de acceso fallidos
5. THE System SHALL forzar HTTPS en producción
6. THE System SHALL implementar tokens CSRF en todos los formularios
7. THE System SHALL sanitizar todas las entradas de usuario
8. WHEN un usuario falla 5 intentos de login, THEN THE System SHALL bloquear temporalmente la cuenta
9. THE System SHALL implementar headers de seguridad (X-Frame-Options, CSP, etc.)

---

### Requirement 4: Módulo de Terceros (Clientes)

**User Story:** Como administrador de parqueadero, quiero registrar clientes/terceros con sus datos completos, para poder gestionar contratos mensuales y mantener un historial.

#### Acceptance Criteria

1. THE Third_Party_Module SHALL permitir crear terceros con: nombre, documento, teléfono, email, dirección
2. THE Third_Party_Module SHALL validar unicidad del documento dentro del tenant
3. THE Third_Party_Module SHALL permitir asociar múltiples vehículos a un tercero
4. THE Third_Party_Module SHALL mostrar historial de visitas y pagos del tercero
5. THE Third_Party_Module SHALL permitir buscar terceros por nombre, documento o placa
6. WHEN se registra un vehículo de entrada, THE System SHALL sugerir terceros existentes si la placa coincide
7. THE Third_Party_Module SHALL permitir exportar listado de terceros a Excel/CSV

---

### Requirement 5: Módulo de Mensualidades

**User Story:** Como administrador de parqueadero, quiero gestionar contratos mensuales con clientes, para automatizar cobros y controlar accesos de vehículos con mensualidad.

#### Acceptance Criteria

1. THE Monthly_Contract_Module SHALL permitir crear contratos asociados a un tercero y vehículo
2. THE Monthly_Contract_Module SHALL definir fecha de inicio, fecha de vencimiento y tarifa
3. THE Monthly_Contract_Module SHALL mostrar estado del contrato (Vigente, Por vencer, Vencido)
4. WHEN un contrato está por vencer (5 días), THE System SHALL mostrar alerta visual
5. WHEN un vehículo con mensualidad vigente ingresa, THE System SHALL registrar entrada sin cobro
6. WHEN un vehículo con mensualidad vencida ingresa, THE System SHALL alertar y permitir cobro normal
7. THE Monthly_Contract_Module SHALL generar reporte de contratos por vencer
8. THE Monthly_Contract_Module SHALL permitir renovar contratos existentes
9. THE Monthly_Contract_Module SHALL registrar historial de pagos de mensualidad

---

### Requirement 6: Sistema de Usuarios y Control de Acceso

**User Story:** Como administrador de parqueadero, quiero crear usuarios con acceso específico a ciertos módulos, para controlar qué puede hacer cada empleado.

#### Acceptance Criteria

1. THE User_Module SHALL permitir crear usuarios asociados al tenant
2. THE User_Module SHALL permitir definir qué módulos puede acceder cada usuario
3. THE Access_Control SHALL verificar permisos antes de mostrar cada módulo en el menú
4. THE Access_Control SHALL verificar permisos antes de permitir acceso a cada vista
5. WHEN un usuario sin permiso intenta acceder a un módulo, THEN THE System SHALL redirigir al dashboard con mensaje de error
6. THE User_Module SHALL permitir definir roles predefinidos (Administrador, Cajero, Consulta)
7. THE User_Module SHALL permitir crear roles personalizados con permisos específicos
8. THE User_Module SHALL mostrar log de actividad por usuario
9. THE System SHALL permitir al administrador del tenant resetear contraseñas de sus usuarios

---

### Requirement 7: Mejora de Reportes

**User Story:** Como administrador de parqueadero, quiero reportes detallados y exportables, para analizar el rendimiento del negocio.

#### Acceptance Criteria

1. THE Report_Module SHALL generar reporte de ingresos por período con filtros
2. THE Report_Module SHALL generar reporte de ocupación por hora del día
3. THE Report_Module SHALL generar reporte de vehículos frecuentes
4. THE Report_Module SHALL generar reporte de mensualidades activas y por vencer
5. THE Report_Module SHALL generar reporte de cuadre de caja diario
6. THE Report_Module SHALL permitir exportar todos los reportes a PDF y Excel
7. THE Report_Module SHALL mostrar gráficos interactivos con Chart.js
8. THE Report_Module SHALL permitir comparar períodos (este mes vs mes anterior)
9. THE Report_Module SHALL calcular métricas: ticket promedio, tiempo promedio, ocupación promedio

---

### Requirement 8: Rediseño de Interfaz de Usuario

**User Story:** Como usuario del sistema, quiero una interfaz moderna, intuitiva y profesional, para trabajar de forma eficiente y agradable.

#### Acceptance Criteria

1. THE UI SHALL seguir un sistema de diseño consistente con paleta de colores definida
2. THE UI SHALL ser completamente responsive (móvil, tablet, desktop)
3. THE UI SHALL cargar en menos de 3 segundos en conexión estándar
4. THE UI SHALL mostrar feedback visual inmediato en todas las acciones
5. THE UI SHALL usar tipografía legible y jerarquía visual clara
6. THE UI SHALL implementar modo oscuro opcional
7. THE UI SHALL mostrar breadcrumbs para navegación
8. THE UI SHALL usar iconografía consistente (Font Awesome o similar)
9. THE UI SHALL evitar patrones visuales genéricos de frameworks CSS
10. THE UI SHALL implementar animaciones sutiles para transiciones

---

### Requirement 9: Mejoras al Flujo de Entrada/Salida

**User Story:** Como operador de parqueadero, quiero un flujo de entrada/salida rápido y con menos clics, para atender más vehículos en menos tiempo.

#### Acceptance Criteria

1. WHEN se escanea código de barras en salida, THE System SHALL mostrar automáticamente el resumen de cobro
2. THE Entry_Form SHALL recordar la última categoría seleccionada
3. THE Entry_Form SHALL autocompletar datos si la placa ya existe en el sistema
4. THE Exit_Form SHALL calcular vuelto automáticamente al ingresar monto recibido
5. THE System SHALL permitir imprimir ticket con un solo clic después del pago
6. THE System SHALL soportar atajos de teclado para operaciones frecuentes
7. WHEN hay error de impresión, THE System SHALL permitir reimprimir sin recargar página

---

### Requirement 10: Auditoría y Logs

**User Story:** Como administrador, quiero un registro completo de todas las operaciones del sistema, para poder auditar y resolver disputas.

#### Acceptance Criteria

1. THE Audit_System SHALL registrar todas las operaciones CRUD en modelos críticos
2. THE Audit_System SHALL registrar usuario, fecha, hora, IP y acción realizada
3. THE Audit_System SHALL registrar valores anteriores y nuevos en modificaciones
4. THE Audit_System SHALL permitir filtrar logs por usuario, fecha, tipo de acción
5. THE Audit_System SHALL retener logs por mínimo 1 año
6. THE Audit_System SHALL ser accesible solo para administradores del tenant
7. IF se detecta actividad sospechosa, THEN THE System SHALL notificar al administrador
