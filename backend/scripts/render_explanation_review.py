"""Render captured explanations as an offline human-review page."""

import argparse
import hashlib
import html
import json
from pathlib import Path
from typing import Any


def _text(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _case_html(case: dict[str, Any], capture: dict[str, Any] | None) -> str:
    case_id = _text(case["id"])
    digest = (
        hashlib.sha256(json.dumps(capture, sort_keys=True).encode()).hexdigest()
        if capture is not None
        else ""
    )
    header = (
        f"<details class='case' data-id='{case_id}' data-digest='{digest}'>"
        f"<summary><strong>{case_id}</strong> · {_text(case['kind'])} · "
        f"{_text(case['prompt'])}</summary>"
        f"<p>Expected outcome: {_text(case['expected_outcome'])}</p>"
    )
    if capture is None:
        return header + "<p>Awaiting live answer capture.</p></details>"
    if "error" in capture:
        return header + f"<p>Capture error: {_text(capture['error'])}</p></details>"
    parts = [header]
    withheld_answerable = bool(case.get("expected_paths")) and any(
        turn.get("answer", {}).get("outcome") not in {"completed", "partial_evidence"}
        for turn in capture.get("turns", [])
    )
    if withheld_answerable:
        parts.append(
            "<p>At least one required explanation was withheld. "
            "Mark this case unsupported and record any useful notes.</p>"
        )
    for index, turn in enumerate(capture.get("turns", []), start=1):
        answer = turn.get("answer") or {}
        parts.append(
            f"<h3>Turn {index}: {_text(turn['question'])}</h3>"
            f"<p>Outcome: {_text(answer.get('outcome', 'missing'))}</p>"
        )
        if answer.get("notice"):
            parts.append(f"<p>Notice: {_text(answer['notice'])}</p>")
        for block in answer.get("blocks") or []:
            citations = ", ".join(block.get("evidence_ids") or [])
            parts.append(
                f"<blockquote>{_text(block.get('text', ''))}"
                f"<small>Evidence: {_text(citations)}</small></blockquote>"
            )
        if answer.get("missing_facts"):
            parts.append(
                "<p>Missing facts: "
                + _text("; ".join(answer["missing_facts"]))
                + "</p>"
            )
        parts.append("<details class='sources'><summary>Official evidence</summary>")
        for item in answer.get("evidence") or []:
            parts.append(
                f"<h4>{_text(item.get('evidence_id', ''))}: "
                f"{_text(item.get('citation', ''))}</h4>"
                f"<p>{_text(item.get('edition_label', ''))} · "
                f"{_text(item.get('legal_status', ''))} · "
                f"{_text(item.get('source_title', ''))}</p>"
                f"<pre>{_text(item.get('authoritative_text', ''))}</pre>"
            )
        parts.append("</details>")
    yes_option = (
        "<option value='true' disabled>Yes</option>"
        if withheld_answerable
        else "<option value='true'>Yes</option>"
    )
    parts.append(
        "<fieldset><legend>Human judgment for all turns in this case</legend>"
        "<label>Supported answer or justified abstention? "
        "<select data-field='supported'><option value=''>Choose</option>"
        + yes_option
        + "<option value='false'>No</option>"
        "</select></label>"
        "<label>Critical legal-status error? "
        "<select data-field='critical_status_error'><option value=''>Choose</option>"
        "<option value='false'>No</option><option value='true'>Yes</option>"
        "</select></label>"
        "<label>Notes <textarea data-field='notes' rows='2'></textarea></label>"
        "</fieldset></details>"
    )
    return "".join(parts)


_SHELL = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Constitution explanation review</title>
<style>
body{font:16px/1.5 system-ui,sans-serif;color:#17212b;background:#f7f8fa;max-width:1050px;margin:auto;padding:1.5rem}
h1{line-height:1.2}.toolbar{position:sticky;top:0;background:#f7f8fa;padding:.75rem 0;border-bottom:1px solid #ccd3da;z-index:2}
button,select,textarea{font:inherit}button{padding:.4rem .8rem}.case{background:white;border:1px solid #ccd3da;border-radius:.5rem;margin:1rem 0;padding:1rem}
summary{cursor:pointer}blockquote{border-left:4px solid #7897b4;margin:1rem 0;padding:.4rem 1rem;background:#f2f6fa}
small{display:block;color:#485767;margin-top:.5rem}.sources{margin:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f7f8fa;padding:1rem}
fieldset{display:grid;gap:.8rem}label{display:grid;gap:.25rem}textarea{width:100%;box-sizing:border-box}
</style></head><body>
<h1>Constitution explanation review</h1>
<p>Read each response against its official evidence. Mark supported only if every substantive claim follows from its cited text and preserves qualifications, or if the response correctly abstains because the source is missing or unsupported. Mark an answerable case with a withheld explanation unsupported. Mark a critical status error if the answer treats historical/source wording as certified current law or misstates its legal status. Cases without a live capture cannot be judged.</p>
<div class="toolbar"><span id="progress"></span> <button id="export" type="button">Export judgments JSONL</button></div>
__CASES__
<script>
const key="law-padi-review-__VERSION__";
const cases=[...document.querySelectorAll(".case:has(fieldset)")];
let saved={};try{saved=JSON.parse(localStorage.getItem(key)||"{}")}catch{}
function update(){
  let done=0;
  for(const card of cases){
    const id=card.dataset.id, row=saved[id]||{};
    if(row.supported!==undefined&&row.critical_status_error!==undefined)done++;
  }
  document.getElementById("progress").textContent=`${done} of ${cases.length} captured cases judged`;
}
for(const card of cases){
  const id=card.dataset.id;
  if(saved[id]?.answer_digest!==card.dataset.digest)saved[id]={};
  if(card.querySelector("option[value='true'][disabled]")&&saved[id]?.supported===true){
    saved[id].supported=undefined;localStorage.setItem(key,JSON.stringify(saved));
  }
  const prior=saved[id]||{};
  for(const input of card.querySelectorAll("[data-field]")){
    const field=input.dataset.field;
    if(prior[field]!==undefined)input.value=String(prior[field]);
    input.addEventListener("change",()=>{
      const row=saved[id]||{answer_digest:card.dataset.digest};
      row[field]=input.value===""?undefined:(field==="notes"?input.value:input.value==="true");
      saved[id]=row;localStorage.setItem(key,JSON.stringify(saved));update();
    });
  }
}
document.getElementById("export").addEventListener("click",()=>{
  const rows=cases.map(card=>({id:card.dataset.id,...(saved[card.dataset.id]||{})}));
  const blob=new Blob([rows.map(row=>JSON.stringify(row)).join("\\n")+"\\n"],{type:"application/x-ndjson"});
  const link=document.createElement("a");link.href=URL.createObjectURL(blob);
  link.download="constitution-explanation-judgments.jsonl";link.click();
  setTimeout(()=>URL.revokeObjectURL(link.href),1000);
});
update();
</script></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--captures", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dataset = json.loads(args.dataset.read_text())
    captures = (
        {
            row["id"]: row
            for line in args.captures.read_text().splitlines()
            if (row := json.loads(line.strip()))
        }
        if args.captures
        else {}
    )
    cases = "\n".join(
        _case_html(case, captures.get(case["id"])) for case in dataset["cases"]
    )
    page = _SHELL.replace("__CASES__", cases).replace(
        "__VERSION__", _text(dataset["version"])
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page)
    print(f"Wrote {len(dataset['cases'])} cases to {args.output}")  # noqa: T201


if __name__ == "__main__":
    main()
