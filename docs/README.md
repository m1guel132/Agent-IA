# 📚 Documentación Técnica de Agent IA

Este directorio contiene toda la especificación formal y el manual operativo del sistema **Agent IA**:

---

## 🗂️ Estructura del Directorio

```
docs/
├── manual_usuario/                     # Manual de Usuario y Operación
│   ├── manual_usuario.pdf              # Documento PDF compilado (8 páginas)
│   ├── manual_usuario.tex              # Código fuente LaTeX editable
│   └── MANUAL_USUARIO.md               # Versión ligera en formato Markdown
│
└── srs/                                # Especificación de Requerimientos (SRS)
    ├── srs_especificacion.pdf          # Documento formal SRS compilado
    └── srs_especificacion.tex          # Código fuente LaTeX formal
```

---

## 📖 Contenido de los Documentos

### 1. [Manual de Usuario](manual_usuario/)
* **PDF Oficial:** [`manual_usuario/manual_usuario.pdf`](manual_usuario/manual_usuario.pdf)
* **Código Fuente LaTeX:** [`manual_usuario/manual_usuario.tex`](manual_usuario/manual_usuario.tex)
* **Temas tratados:**
  * Arquitectura Hexagonal y Flota de Agentes (**Hermes**, **Curador**, **Plan**, **Estudio**, **Sync**).
  * Preparación del entorno y configuración en `.env` (Modo Híbrido, Ollama, Gemini Flash).
  * Guía de comandos conversacionales y flujos de revisión *Human-in-the-Loop*.
  * Sistema de sanitización y ofuscación local de datos personales (`DataMasker`).
  * Matriz de resolución de problemas y tabla de comandos CLI.

### 2. [SRS (Software Requirements Specification)](srs/)
* **PDF Oficial:** [`srs/srs_especificacion.pdf`](srs/srs_especificacion.pdf)
* **Código Fuente LaTeX:** [`srs/srs_especificacion.tex`](srs/srs_especificacion.tex)
* **Temas tratados:**
  * Metodología de requerimientos de 3 niveles (Negocio, Usuario, Software).
  * Priorización DINO (Deseable, Importante, No implementable, Obligatorio).
  * Requerimientos funcionales (RF1–RF6) y no funcionales (RNF1–RNF5).
  * Diagramas de paquetes, casos de uso y modelos de dominio.

---

## ⚙️ Cómo Recompilar los Documentos LaTeX

Si realizas modificaciones en los archivos `.tex`, puedes recompilarlos usando `pdflatex`:

```bash
# Compilar el Manual de Usuario
cd docs/manual_usuario
pdflatex -interaction=nonstopmode manual_usuario.tex

# Compilar el SRS
cd ../srs
pdflatex -interaction=nonstopmode srs_especificacion.tex
```
