-- ============================================================
-- Migración: Añadir TIPO_PRECIO a la tabla OFERTAS
-- Ejecutar en Snowflake como ACCOUNTADMIN
-- ============================================================

USE DATABASE OFERTAS_DB;
USE SCHEMA APP;

-- Añadir columna TIPO_PRECIO para distinguir CON/SIN Scrap
ALTER TABLE OFERTAS ADD COLUMN IF NOT EXISTS TIPO_PRECIO VARCHAR(50) DEFAULT 'PRECIO CON Scrap';

-- Actualizar ofertas existentes que no tienen tipo_precio
UPDATE OFERTAS SET TIPO_PRECIO = 'PRECIO CON Scrap' WHERE TIPO_PRECIO IS NULL;
