import os

for root, dirs, files in os.walk("."):
    for f in files:
        if not f.endswith(".py"):
            continue
        if f == "_fix_unicode.py":
            continue
        path = os.path.join(root, f)
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()
        original = content
        content = content.replace("\u2192", "->")
        content = content.replace("\u2550", "=")
        content = content.replace("\u2502", "|")
        content = content.replace("\u26a0", "[!]")
        if content != original:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content)
            print("Fixed:", path)
print("Done")
