"""AI data-collection pipeline (manual CLI: ``python -m app.pipeline``).

Mode 1: collect programs + tuition for a NEW field across the universities that
already exist in the dataset. Findings go to a staging file for human review;
an explicit ``apply`` step merges approved entries into ``data.real.json`` and
inserts them into the live database. Nothing writes to the dataset without the
review step, and every figure carries its own source URL + accessed date.
"""
