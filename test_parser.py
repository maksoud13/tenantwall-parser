import requests
import json

# اقرا الـ SQL من الملف
with open("complex.sql", "r", encoding="utf-8") as f:
    sql = f.read()

# ابعت الطلب
response = requests.post(
    "http://localhost:8000/api/modify",
    json={
        "sql": sql,
        "column": "tenant_id",
        "value": "maksoud",
        "dialect": "oracle"  # ← Oracle، لأن فيه NVL
    },
    timeout=30
)

# اطبع النتيجة
data = response.json()
if data.get("success"):
    print("✅ SUCCESS\n")
    print(data["result"])
else:
    print("❌ FAILED")
    print(data.get("error"))