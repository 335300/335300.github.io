"""Pure calculation layer.

These modules take model objects (and, where time matters, a ``today`` date)
and return plain dictionaries. They perform no I/O, hold no state and never
read the clock, which makes every figure the UI shows
directly unit-testable.
"""
