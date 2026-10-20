import json, os, re, sys

root, out = sys.argv[1], sys.argv[2]
link_re = re.compile(r"\[\[([^\]|#]+)")
notes = {}
for dp, dn, fn in os.walk(root):
    dn[:] = [d for d in dn if not d.startswith('.')]
    for f in fn:
        if f.endswith('.md'):
            rel = os.path.relpath(os.path.join(dp, f), root)
            folder = rel.split(os.sep)[0] if os.sep in rel else 'raiz'
            notes[f[:-3]] = {'folder': folder, 'path': os.path.join(dp, f)}

keys = {k.lower(): k for k in notes}
edges = set()
for name, n in notes.items():
    try:
        text = open(n['path'], encoding='utf-8', errors='ignore').read()
    except OSError:
        continue
    for m in link_re.findall(text):
        target = keys.get(os.path.basename(m.strip()).lower())
        if target and target != name:
            edges.add(tuple(sorted((name, target))))

names = sorted(notes)
idx = {k: i for i, k in enumerate(names)}
folders = sorted({notes[k]['folder'] for k in names})
data = {
    'folders': folders,
    'nodes': [[k, folders.index(notes[k]['folder'])] for k in names],
    'edges': [[idx[a], idx[b]] for a, b in sorted(edges)],
}
json.dump(data, open(out, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(len(names), 'notas', len(edges), 'conexoes', folders)
