"""Just show the output."""
import os
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth

load_dotenv()

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST", "https://us.cloud.langfuse.com")

trace_id = "9c753193506fa292377cb261acdc0287"

trace_url = f"{host}/api/public/traces/{trace_id}"
auth = HTTPBasicAuth(public_key, secret_key)

response = requests.get(trace_url, auth=auth, timeout=30)
response.raise_for_status()

trace = response.json()

trace_output = trace.get('output')
if isinstance(trace_output, dict):
    output_content = trace_output.get('content', '')
    print(output_content[:2000])  # First 2000 chars
elif isinstance(trace_output, str):
    print(trace_output[:2000])
