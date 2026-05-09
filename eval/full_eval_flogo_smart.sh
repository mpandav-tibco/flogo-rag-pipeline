#!/bin/bash
# full_eval_flogo_smart.sh — clean-slate ingest + 50-query eval for the
# Docling-Markdown + heading-chunk smart pipeline.
#
# Pipeline: PDF → Docling /v0/markdown (full MD, tables intact)
#               → Flogo /rag/weaviate/ingest/smart (heading-strategy chunks)
#               → Weaviate (FlogoSmartDocs)
#               → Flogo /rag/weaviate/query/generate (RAGQueryGenerate, LLM)
# Rageval events fired automatically by SendRagevalEvent activity.

set -euo pipefail
cd "$(dirname "$0")"

PDF_DIR="${1:-./test-data}"
INGEST_URL=http://localhost:9191/rag/weaviate/ingest/smart
RAGDB=/Users/milindpandav/git/rageval/rageval.db
COLLECTION=FlogoSmartDocs

# (filename | interface_id | owner | document_type)
DOCS=(
  "Functional_Specs.pdf|17486|Tome,Mario|Functional_Spec"
  "Technical_Spec.pdf|17486|Tome,Mario|Technical_Spec"
  "1020882549_ce6d0ee4689b471f8599e943addef2f2-300426-1425-354.pdf|9469|Martin Saal|Interface_Assessment"
  "1064248810_c409c6ad5fc146528dc2c80a8288edda-300426-1424-348.pdf|9469|Martin Saal|Technical_Spec"
  "988748864_7865bb38f4b848a5b604598bb8cbb0bf-300426-1424-352.pdf|9469|Martin Saal|Interface_Request"
  "988748864_f8ca4515068e44aabf580012c48cbd4a-300426-1428-356.pdf|9469|Martin Saal|Interface_Request"
)

echo "============================================================"
echo " STEP 1 — Wipe Weaviate collection: $COLLECTION"
echo "============================================================"
curl -s -X DELETE "http://localhost:18080/v1/schema/$COLLECTION" \
  && echo "  Collection wiped" || echo "  (collection did not exist)"

echo ""
echo "============================================================"
echo " STEP 2 — Wipe rageval rows for $COLLECTION"
echo "============================================================"
python3 - <<PYEOF
import sqlite3
conn = sqlite3.connect("$RAGDB")
cur = conn.cursor()
cur.execute("DELETE FROM eval_results WHERE collection='$COLLECTION'")
print(f"  Deleted {cur.rowcount} rows from eval_results")
conn.commit(); conn.close()
PYEOF

echo ""
echo "============================================================"
echo " STEP 3 — Ingest ${#DOCS[@]} PDFs via smart endpoint"
echo "============================================================"
for entry in "${DOCS[@]}"; do
  IFS='|' read -r fname iid owner dtype <<< "$entry"
  printf "  → %s ... " "$fname"
  resp=$(curl -s -w "HTTP_%{http_code}" -X POST "$INGEST_URL" \
    -F "file=@${PDF_DIR}/${fname}" \
    -F "filename=${fname}" \
    -F "collection=${COLLECTION}" \
    -F "interface_id=${iid}" \
    -F "owner=${owner}" \
    -F "document_type=${dtype}")
  code="${resp##*HTTP_}"
  body="${resp%HTTP_*}"
  if [ "$code" = "200" ]; then
    chunks=$(python3 -c "import json,sys; print(json.loads('''$body''').get('chunks_embedded','?'))" 2>/dev/null || echo "?")
    dur=$(python3    -c "import json,sys; print(json.loads('''$body''').get('processing_time','?'))" 2>/dev/null || echo "?")
    echo "OK  chunks=$chunks  dur=$dur"
  else
    echo "FAILED ($code)"
    echo "    $body" | head -c 400
    echo
  fi
done

echo ""
echo "============================================================"
echo " STEP 4 — Run 50 queries through /rag/weaviate/query/generate"
echo "============================================================"
COLLECTION="$COLLECTION" python3 run_queries_flogo_smart.py
