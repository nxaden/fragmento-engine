# Fragmento Core

Fragmento Core is the image processing engine behind Fragmento. It takes an ordered image sequence and a time-slice specification, then produces a composite time-slice image.

This repository focuses on deterministic, testable rendering logic. It does not define the final user interface.

## Scope

Fragmento Core is responsible for:

- discovering and validating input frames
- planning slice geometry
- extracting slices from source frames
- compositing slices into a final output image
- exporting the rendered result

It is not responsible for the final desktop UI, web UI, or project management experience.

## Pipeline

The render pipeline should be deterministic and testable:

1. Discover and sort input frames
2. Validate the sequence
3. Read metadata and determine canonical dimensions
4. Build a slice plan
5. Extract slices
6. Composite onto the output canvas
7. Export the final image

## Architecture

Fragmento Core is organized into layers with distinct responsibilities.

### Domain Layer

The domain layer defines the core concepts of the system, such as image sequences, time-slice specifications, slice geometry, and composition rules. It should not depend on UI concerns or file system details.

### Application Layer

The application layer coordinates workflows such as validation, preview generation, full-quality rendering, and export.

### Infrastructure Layer

The infrastructure layer handles concerns such as file I/O, JPG decoding, Pillow or OpenCV integration, caching, and output writing.

### Interface Layer

The interface layer exposes the core system to external consumers, such as a CLI, desktop application, or API layer.

## Core Business Logic

One of the main responsibilities of Fragmento Core is building a slice plan. This is where user intent is translated into concrete geometry for rendering.

For example, in a horizontal left-to-right time-slice, each slice is taken from a different frame and placed as a vertical strip in the final composite. With 10 slices and a 4000 px output width, each slice may occupy 400 px.

A slice plan should determine:

- which frame maps to each slice
- the source rectangle within the frame
- the destination rectangle within the output image
- how remainder pixels are handled when dimensions do not divide evenly.
