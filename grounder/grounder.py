import torch
from pathlib import Path
from collections import defaultdict

def ground_file(txt_path: Path, out_path: Path):
    entity_to_id = {}
    next_id = 0
    batch_size = 10000

    binary_preds = defaultdict(list)
    unary_preds = defaultdict(list)

    def get_entity_id(name):
        nonlocal next_id
        if name not in entity_to_id:
            entity_to_id[name] = next_id
            next_id += 1
        return entity_to_id[name]


    with open(txt_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.strip().split()
            arity = parts[0].upper()

            if arity == "UNARY":
                if len(parts) < 3:
                    continue # bad form
                p = parts[1]
                ent = " ".join(parts[2:])
                eid = get_entity_id(ent)
                unary_preds[p].appends(eid)
            elif arity == "BINARY":
                if len(parts) < 4:
                    continue # bad form
                p = parts[1]
                s = parts[2]
                o = " ".join(parts[3:])
                sid = get_entity_id(s)
                oid = get_entity_id(o)
                binary_preds[p].append((sid,oid))

            else:
                continue

    # to tensors (SPARSE)
    tensor_batches = []
    for pred, pairs in binary_preds.items():
        for i in range(0, len(pairs),batch_size):
            batch = pairs[i:i+batch_size]
            subj_ids = torch.tensor([x[0] for x in batch], dtype=torch.long)
            obj_ids = torch.tensor([x[1] for x in batch], dtype=torch.long)
            tensor_batches.append((pred, subj_ids, obj_ids))

    # Save tensors safely
    torch.save({
        "entities": entity_to_id,
        "binary": tensor_batches,
        "unary": dict(unary_preds)
    }, out_path)
    print(f"[OK] Grounded {txt_path} -> {out_path}")

def main():
    base = Path(__file__).parent
    # in_dir = base / "../data/run2/nlm"
    # out_dir = base / "../data/run2/grounded"
    in_dir = base / "../data/ir"
    out_dir = base / "../data/ir/grounded"

    out_dir.mkdir(parents=True, exist_ok=True)
    
    files = list(in_dir.glob("*.txt"))
    if not files:
        print("No files found in", in_dir)
        return

    for txt in files:
        out_file = out_dir / (txt.stem + ".pt")
        try:
            ground_file(txt, out_file)
        except Exception as e:
            print(f"[ERROR] Failed to ground {txt}: {e}");


if __name__ == "__main__":
    main()

