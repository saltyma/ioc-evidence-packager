# UI tests

UI tests cover view models and a small number of offscreen PySide6 workflows. They verify that widgets call application services, remain responsive during jobs, display escaped evidence, expose coverage reasons, and leave correct state after cancel/failure.

Evidence matching, coverage calculation, persistence, and export semantics belong in headless tests rather than being retested only through widgets.
