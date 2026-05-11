import torch
from safetensors import safe_open

adapters = ["./models/task1/model1",
            "./models/task1/model2",
            "./models/task1/model3"]
merged   = "./models/task1/wag_merged"
key_substr = "score"  # narrow to whatever key showed up above

def load_score(p):
    with safe_open(f"{p}/adapter_model.safetensors", framework="pt") as f:
        hits = [k for k in f.keys() if key_substr in k and "lora" not in k]
        assert hits, f"no full score tensor in {p}"
        return {k: f.get_tensor(k) for k in hits}

src = [load_score(a) for a in adapters]
mrg = load_score(merged)

for k in mrg:
    avg = torch.stack([s[k] for s in src]).mean(0)
    diff = (avg - mrg[k]).norm().item()
    print(f"{k}: ||avg - merged|| = {diff:.3e}  (should be ~0)")