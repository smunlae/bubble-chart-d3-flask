import re
import requests
from typing import Any, Dict, List, Optional
from flask import Flask, jsonify, render_template

def run_datalens_query(page: int = 1) -> Optional[Dict[str, Any]]:
    url = "https://datalens.yandex/charts/api/run"
    headers = {"Content-Type": "application/json"}
    payload: Dict[str, Any] = {
        "id": "5jjsemsj8ssmr",
        "params": {},
        "responseOptions": {"includeConfig": True, "includeLogs": False}
    }
    if page > 1:
        payload["params"]["_page"] = str(page)
    try:
        resp = requests.post(url, json=payload, headers=headers)
        resp.raise_for_status()
    except requests.HTTPError as e:
        print(f"Ошибка запроса страницы {page}:", e)
        return None
    return resp.json()

def extract_nodes_by_type(node: Dict[str, Any], types: List[str]) -> List[str]:
    res: List[str] = []
    t = node.get("type"); content = node.get("content")
    if t == "text" and "text" in types and isinstance(content, str):
        res.append(content)
    elif t in ("bold", "color") and t in types:
        if isinstance(content, str):
            res.append(content)
        elif isinstance(content, dict) and content.get("type") == "text":
            res.append(content.get("content", ""))
    for child in node.get("children", []):
        res.extend(extract_nodes_by_type(child, types))
    return res

def process_datalens_response(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    head = resp["data"]["head"]
    rows = resp["data"]["rows"]
    idx_img     = 0
    idx_changes = next(i for i,h in enumerate(head) if h["name"] == "Changes")
    idx_price   = next(i for i,h in enumerate(head) if h["name"] == "Market price")

    out: List[Dict[str, Any]] = []
    for row in rows:
        cells = row["cells"]
        # 1) картинка
        img_val = cells[idx_img]["value"]
        img_src = img_val.get("src", "") if isinstance(img_val, dict) else ""

        # 2) имя и объем
        change_node = cells[idx_changes]["value"]
        name = extract_nodes_by_type(change_node, ["bold"])
        name = name[0] if name else ""
        texts = extract_nodes_by_type(change_node, ["text"])
        volume = next((v for v in reversed(texts) if v.isdigit()), "")

        # 3) цена и проценты
        price_node = cells[idx_price]["value"]
        floor = (extract_nodes_by_type(price_node, ["bold"]) or [""])[0].replace("💎","")
        colors = extract_nodes_by_type(price_node, ["color"])
        def fmt(x: str) -> str:
            return x.replace("▲","+").replace("▼","-").strip()
        raw_1d = fmt(colors[0]) if len(colors)>0 else ""
        # Преобразуем строку "+ 8.7%" → число 8.7
        try:
            change_1d = float(raw_1d.replace("%","").replace(" ",""))
        except:
            change_1d = 0.0

        out.append({
            "name":    name,
            "volume":  volume,
            "floorprice": floor,
            "change":  change_1d,
            "img_src": img_src
        })

    return out

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def get_data():
    all_items: List[Dict[str, Any]] = []
    for p in range(1, 8):
        r = run_datalens_query(page=p)
        if r:
            all_items.extend(process_datalens_response(r))
    return jsonify(all_items)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
