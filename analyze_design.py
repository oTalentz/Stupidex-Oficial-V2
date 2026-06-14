import sys

sys.path.insert(0, "src")

# Compare HTML structures
with open("design-ref/Page_1.html", "r", encoding="utf-8", errors="ignore") as f:
    design = f.read()
with open("src/stupidex/static/index.html", "r", encoding="utf-8") as f:
    current = f.read()

# Check key differences
print("=== ANALYSIS ===")
print()

# 1. Check if design-ref has interactive elements
if "onclick" in design:
    print("Design-ref has onclick handlers (static/demo)")
if "data-" in design:
    print("Design-ref has data attributes (static/demo)")

# 2. Check for Puter.js (design-ref has it)
if "puter" in design.lower():
    print("Design-ref uses Puter.js SDK")
if "puter" in current.lower():
    print("Current uses Puter.js SDK")
else:
    print("Current does NOT use Puter.js SDK")

# 3. Check for phosphor icons
if "phosphor" in design:
    print("Design-ref uses Phosphor Icons")
if "phosphor" in current:
    print("Current uses Phosphor Icons")

# 4. Check structure
print()
print("=== STRUCTURE CHECK ===")

# Current has auth screen and app div
if '<div id="auth-screen"' in current:
    print("Current has auth-screen (REQUIRED for login)")
if '<div id="app"' in current:
    print("Current has main app div")

# Check for required elements
required_ids = [
    "auth-screen",
    "app",
    "session-list",
    "workspace-list",
    "composer",
    "messages",
]
print()
print("=== REQUIRED IDS ===")
for rid in required_ids:
    in_current = 'id="' + rid + '"' in current
    in_design = 'id="' + rid + '"' in design
    print(rid + ": current=" + str(in_current) + ", design=" + str(in_design))
