# Developer Guide

## Overview

This guide explains how to work with the Fragmento codebase as it grows from a simple timeslice engine into a larger application.

The main goals are to preserve separation between:

- domain logic
- application workflows
- infrastructure concerns
- interfaces

Why? Because with these separation of concerns, the project will remain easy to extend, test and refactor.

## So you want to add a feature

first ask:

Is this a new domain rule, a new workflow, an infrastructure concern, or an interface concern?

Use this rule of thumb:

- If it changes what a timeslice means, it belongs in the domain.
- If it changes how a use case is executed, it belongs in the application layer.
- If it changes file I/O, image reading, or persistence, it belongs in infrastructure.
- If it changes CLI arguments or the public API, it belongs in the interface layer.

## Recommended Project Structure

```text
fragmento_engine/
  domain/
    models.py
    planner.py
    compositor.py

  application/
    services.py

  infrastructure/
    image_loader.py
    image_writer.py

  interface/
    cli.py
```

## Layer Responsibilities

### Domain

The domain layer contains the business meaning of the application.

Examples:

- `TimesliceSpec`
- `TimeslicePlan`
- slice planning rules
- compositing logic
- validation around timeslice behavior

### Application

The application layer coordinates workflows.

Examples:

- render a timeslice from a folder
- generate a preview
- batch render multiple folders
- save metadata next to the output

The application layer should use the domain rather than replace it.

### Infrastructure

The infrastructure layer handles external dependencies and I/O.

Examples:

- reading images from disk
- resizing and cropping input images
- writing output images
- exporting metadata files

### Interface

The interface layer is how users interact with the system.

Examples:

- CLI commands
- API endpoints

The interface should stay thin and call into application services.

## Working with Services

A service should represent one clear use case.

Good examples:

- `RenderTimesliceService`
- `PreviewTimesliceService`
- `BatchRenderService`

A service should:

- accept structured input
- call the domain layer
- use infrastructure adapters
- return structured output

## Service Pattern

Use request and response objects when a workflow has more than one or two parameters.

Example:

```python
from dataclasses import dataclass
from pathlib import Path

from fragmento_engine.domain.models import CompositeResult, TimesliceSpec


@dataclass(frozen=True)
class RenderRequest:
    input_folder: Path
    spec: TimesliceSpec
    resize_mode: str = "crop"


@dataclass(frozen=True)
class RenderResponse:
    result: CompositeResult
    input_paths: list[Path]
    output_file: Path | None = None
    slice_counts: list[int] | None = None
```

This keeps service APIs clean and easy to evolve.

## Testing Strategy

### Domain tests

Focus on correctness of image logic.

Examples:

- slice boundaries
- frame selection
- reverse-time behavior
- vertical vs horizontal slicing

### Application tests

Focus on workflow correctness.

Examples:

- correct loader calls
- correct propagation of request values
- handling empty folders
- correct output writing flow

### Infrastructure tests

Focus on adapters.

Examples:

- image loading
- resize behavior
- output writing
- metadata file generation

## Practical Examples (Mapping feature to layers)

### Feature: reverse-time support

Belongs to the domain because it changes how frames are selected across time.

### Feature: preview command

Belongs to the application layer because it is a new workflow built on top of the same domain logic.

### Feature: EXIF orientation fix

Belongs to infrastructure or preprocessing because it changes how input images are normalized.

### Feature: new CLI flag

Belongs to the interface layer because it changes how the user invokes the program.
