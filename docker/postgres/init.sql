-- ===========================================
-- SoluPark - PostgreSQL Initialization
-- ===========================================

-- Crear extensiones útiles
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Configuraciones de rendimiento para la sesión
SET timezone = 'America/Bogota';
