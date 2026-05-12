# Analysis2
Portable LUBM-oriented rewrite of the original analysis tooling.
## Why this exists
The original `Analysis` tooling was tightly coupled to:
- fixed repository-relative paths
- hardcoded output locations
- OWL declaration counting that does not fit LUBM instance-heavy RDF/XML very well
This rewrite is designed to work directly on LUBM university ontologies and department modules.
## What it measures
For each `.owl` file, the analyzer counts distinct LUBM vocabulary symbols used in RDF/XML:
- **classes**: distinct LUBM elements used as typed resources
- **properties**: distinct LUBM elements used as predicates / child relation elements
- **combined**: `classes + properties`
This is a better fit for generated LUBM university files and split department modules, where the files mainly contain instance data rather than explicit class/property declarations.
## Folder layout
- `analysis2/analyzer.py` — parsing, counting, summaries, export helpers
- `analysis2/cli.py` — command-line entrypoint
- `run_analysis.py` — tiny runner for direct execution
- `tests/test_analysis2.py` — regression tests with synthetic RDF/XML samples
- `requirements.txt` — dependency manifest (standard library only)
## Quick start
From `GLaMoR-DataPipeline`:
```bash
python Analysis2/run_analysis.py   --ontologies-root /media/nvme7n1/lniederberger/models/GLaMoR/GLaMoR-DataPipeline/data/lubm_c   --modules-root /media/nvme7n1/lniederberger/models/GLaMoR/GLaMoR-DataPipeline/data/ont_modules   --output-dir /media/nvme7n1/lniederberger/models/GLaMoR/GLaMoR-DataPipeline/Analysis2/output
```
## Outputs
The tool writes:
- `ontologies_counts.csv`
- `modules_counts.csv`
- `summary.json`
- `lubm_table_rows.tex`
The LaTeX file contains rows ready to paste into a table of the form:
```tex
\multirow{2}{*}{LUBM100} & Ontologies & <median> & <average> & <sd> \
                         & Modules    & <median> & <average> & <sd> \
```
These values are based on the **combined** class + property counts.
## Run tests
```bash
python -m unittest Analysis2.tests.test_analysis2 -v
```
