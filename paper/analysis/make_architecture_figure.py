#!/usr/bin/env python3
"""Generate the AWS architecture figure for the paper (Task 11).

Guardrail 6: figures regenerate from a script, never hand-drawn-and-forgotten.
Source of truth is documentation/ARCHITECTURE.md; keep this in sync with it.

Renders vector PDF (what the paper embeds) plus PNG (for review). Flat
filenames, because Task 13 flattens everything to the tarball root.

    python paper/analysis/make_architecture_figure.py
"""
import pathlib
from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.storage import S3
from diagrams.aws.database import Aurora
from diagrams.aws.integration import StepFunctions
from diagrams.aws.ml import Textract, Bedrock
from diagrams.programming.language import Python

OUT = pathlib.Path(__file__).resolve().parents[1] / "figures" / "fig_architecture"

GRAPH_ATTR = {
    "fontsize": "13",
    "labelloc": "t",
    "pad": "0.35",
    "nodesep": "0.45",
    "ranksep": "0.75",
    "splines": "ortho",
    "bgcolor": "white",
}
NODE_ATTR = {"fontsize": "11"}
EDGE_ATTR = {"fontsize": "10", "color": "#444444"}


def build(fmt):
    """Each Bedrock model sits INSIDE the cluster that calls it.

    An earlier version grouped all three models into one far-away cluster,
    which produced three edges crossing the entire figure and a 2.4:1 aspect
    ratio full of whitespace -- unusable at column width. Co-locating them also
    reads truer: the model assignment is a property of the stage.
    """
    with Diagram(
        "",                       # no title: the LaTeX caption carries it
        filename=str(OUT),
        outformat=fmt,
        show=False,
        direction="LR",
        graph_attr=GRAPH_ATTR,
        node_attr=NODE_ATTR,
        edge_attr=EDGE_ATTR,
    ):
        sfn = StepFunctions("Step Functions\n(orchestration)")

        with Cluster("1-2  Ingest and extract"):
            ingest = Lambda("ingestion")
            extract = Lambda("extraction")
            textract = Textract("Textract\nlayout + OCR")
            # Extraction is HYBRID: Textract supplies layout/geometry, but its
            # OCR fuses adjacent words. PyMuPDF reads the PDF's own text layer
            # as a spacing oracle and only whitespace is ever changed.
            pymupdf = Python("PyMuPDF\ntext-layer spacing oracle")
            extract >> Edge(style="dashed", color="#7B61FF", constraint="false") >> textract
            extract >> Edge(style="dashed", color="#7B61FF", constraint="false",
                            label="word-boundary repair") >> pymupdf

        s3 = S3("S3\nevery stage boundary is an\nS3 write + read")

        with Cluster("3-4  Detection (batched)"):
            det_prep = Lambda("prepare\n<=5 chunks/batch")
            det_map = StepFunctions("Map\n<=3 concurrent")
            det_batch = Lambda("detect batch x N")
            det_merge = Lambda("merge + dedup")
            # Declared pass-2-first because graphviz stacks the later-declared
            # node lower; this makes pass 1 read above pass 2.
            b_det = Bedrock("pass 2: detection\nOpus 4.6")
            b_depth = Bedrock("pass 1: depth map\nHaiku 4.5")
            det_prep >> det_map >> det_batch >> det_merge
            det_prep >> Edge(style="dashed", color="#7B61FF", constraint="false") >> b_depth
            det_batch >> Edge(style="dashed", color="#7B61FF", constraint="false") >> b_det

        with Cluster("5-6  Parsing (batched)"):
            par_prep = Lambda("prepare\n<=3 domains/batch")
            par_map = StepFunctions("Map\n<=3 concurrent")
            par_batch = Lambda("parse batch x N")
            par_merge = Lambda("merge")
            b_par = Bedrock("parsing\nSonnet 4.6")
            par_prep >> par_map >> par_batch >> par_merge
            par_batch >> Edge(style="dashed", color="#7B61FF", constraint="false") >> b_par

        with Cluster("7-8  Validate and persist"):
            validate = Lambda("validation\n+ code-shape guard")
            persist = Lambda("persistence")
            aurora = Aurora("Aurora PostgreSQL\nServerless v2")
            validate >> Edge(label="valid only") >> persist >> aurora

        # EVERY stage boundary goes through S3 -- verified against
        # handlers.py, which pairs a save_json_to_s3 with the next stage's
        # load_json_from_s3 at each step (extraction:194, detection:252/292,
        # parsing:353/407, validation:526/560/597) and persister.py, which
        # reads the validation summary and each canonical record.
        # An earlier revision drew only the two merge writes, which wrongly
        # implied those stages were special and that nothing read back.

        sfn >> Edge(style="dotted", color="#999999") >> ingest
        ingest >> Edge(label="PDF") >> extract
        extract >> Edge(label="text blocks") >> det_prep
        det_merge >> Edge(label="elements") >> par_prep
        par_merge >> Edge(label="standards") >> validate
        # writes (one per stage that produces an intermediate artifact).
        # The FIRST edge is left constrained so graphviz ranks S3 next to the
        # pipeline instead of parking it at the far left, which produced five
        # full-width edges; the rest are unconstrained so they do not distort
        # the main row.
        extract >> Edge(style="dotted", color="#999999") >> s3
        # No labels on these three: they are long unconstrained edges, and
        # graphviz strands their labels at the bottom of the canvas far from the
        # edge they belong to. The S3 node's own caption carries the point.
        for producer in (det_merge, par_merge, validate):
            producer >> Edge(style="dotted", color="#999999",
                             constraint="false") >> s3
        # the one read worth drawing: persistence has no upstream data edge of
        # its own, so without this its input is unexplained
        s3 >> Edge(style="dotted", color="#999999", constraint="false") >> persist


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    for fmt in ("pdf", "png"):
        build(fmt)
        print(f"wrote {OUT}.{fmt}")
