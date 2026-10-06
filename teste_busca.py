import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI()

vector_store_id = os.environ["MOREIRA_VECTOR_STORE_ID"]

query = """
Definition 7.6
A sequence of random variables
converges in distribution
continuity points
F_X
F_Y
"""

results = client.vector_stores.search(
    vector_store_id=vector_store_id,
    query=query,
    max_num_results=50,
    rewrite_query=False,
)

for i, result in enumerate(results.data, start=1):
    print("\n" + "=" * 80)
    print(f"RESULTADO {i}")
    print(f"Arquivo: {result.filename}")
    print(f"Score: {result.score}")
    print("-" * 80)

    for content in result.content:
        if content.type == "text":
            print(content.text)