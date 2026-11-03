Industrial062 constructor/checker adapters are retained unchanged from MontrealAI/AGI-Alpha-Invention-Flywheel-Lab commit91220d0793d1c9d6e21d5d2c8213d662d29db4de.

Public benchmark inputs and client checker code originate from NineAbyss/OR-License commit2bda4b8d6ddd4bd1cb62b89acee0c7c2f1914d47 (Apache License2.0, supplied alongside). They are retrieved transiently using the checksum-pinned industrial062/fetch_inputs.py; no large dataset is redistributed here.

scripts/materialize_industrial064.py documents the exact modifications: baseline reserialization and a deliberately authored +5% demand sensitivity with upward integer rounding. These are one historical manufacturer's two planning requests, not additional real customers or observed future demand.
