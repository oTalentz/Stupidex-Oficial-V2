import sys

sys.path.insert(0, "src")
from stupidex.web import app

# Final comprehensive test
tests = []
with app.test_client() as client:
    # Test 1: Index loads
    r = client.get("/")
    tests.append(("GET /", r.status_code == 200))

    # Test 2: Health check
    r = client.get("/api/health")
    tests.append(
        ("GET /api/health", r.status_code == 200 and r.json["database"] == "ok")
    )

    # Test 3: Static JS loads
    r = client.get("/static/app.js")
    tests.append(("GET /static/app.js", r.status_code == 200))

    # Test 4: Static HTML loads
    r = client.get("/static/index.html")
    tests.append(("GET /static/index.html", r.status_code == 200))

print("=== FINAL TEST RESULTS ===")
for name, passed in tests:
    status = "PASS" if passed else "FAIL"
    print(status + ": " + name)

all_passed = all(t[1] for t in tests)
print("\nAll tests: " + ("PASSED" if all_passed else "FAILED"))
