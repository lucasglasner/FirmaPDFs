---
title: Firmador de PDFs
emoji: ✍
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Firmador de PDFs

Herramienta web liviana para colocar una firma (imagen JPG/PNG) en PDFs de forma visual y automática.

## Problema que resuelve

Firmar planos u otros PDFs manualmente es tedioso: hay que encontrar las coordenadas exactas donde colocar la imagen, ajustar el tamaño, y repetir el proceso para decenas de archivos. Esta app permite posicionar la firma arrastrándola con el mouse sobre el PDF, y luego aplicarla en lote a todos los archivos de una vez.

## Demo rápida

1. Sube un PDF de referencia y tu firma (JPG/PNG)
2. Arrastra la firma hasta la posición deseada y ajusta el tamaño
3. Confirma la posición y sube todos los PDFs a firmar
4. Descarga un ZIP con todos los PDFs firmados

## Funcionalidades

- **Posicionamiento visual** — la firma se muestra como overlay arrastrable sobre el PDF
- **Zoom** — niveles 100% / 125% / 150% / 175% / 200% con botones y rueda del mouse
- **Ratio fijo** — al cambiar el tamaño, el alto/ancho de la firma se mantiene proporcional
- **Coordenadas manuales** — campos X / Y / Ancho / Alto editables en puntos PDF
- **Vista previa** — render real del PDF firmado antes de procesar en lote
- **Firma en lote** — firma múltiples PDFs de una vez, con opción de aplicar en todas las páginas, solo la primera o solo la última
- **Descarga ZIP** — todos los PDFs firmados en un solo archivo
- **Drag & drop** — arrastra los archivos directamente a la interfaz
- **Interfaz en español**

## Stack

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI + Uvicorn |
| Procesamiento PDF | PyMuPDF (fitz) |
| Procesamiento imagen | Pillow |
| Frontend | HTML / CSS / JS vanilla (sin frameworks) |

## Instalación local

**Requisitos:** Python 3.10+

```bash
git clone https://github.com/tu-usuario/FirmaPlanos.git
cd FirmaPlanos
pip install -r requirements.txt
python app.py
```

Abrí el navegador en [http://localhost:8000](http://localhost:8000).

## Docker

```bash
docker compose up -d --build
```

La app queda disponible en [http://localhost:8000](http://localhost:8000).

Para detenerla:

```bash
docker compose down
```

## Estructura del proyecto

```
FirmaPlanos/
├── app.py              # Backend FastAPI (todos los endpoints)
├── static/
│   └── index.html      # Frontend (SPA, sin dependencias externas)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── SPEC.md             # Especificación técnica detallada
```

## API

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/upload-pdf` | Sube un PDF de referencia |
| `GET`  | `/api/page-image/{id}/{page}` | Devuelve una página rasterizada (PNG) |
| `POST` | `/api/upload-signature` | Sube la imagen de firma |
| `GET`  | `/api/signature/{id}` | Sirve la imagen de firma |
| `POST` | `/api/preview` | Renderiza una página con la firma aplicada |
| `POST` | `/api/batch-sign` | Firma múltiples PDFs, devuelve ZIP |

## Licencia

MIT
