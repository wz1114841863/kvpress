import requests
from transformers import pipeline
from kvpress import KVzapPress, DMSPress

model = "Qwen/Qwen3-8B"
pipe = pipeline("kv-press-text-generation", model=model, device_map="auto", dtype="auto")
press = DMSPress(KVzapPress(model_type="mlp"), threshold=-4)
print("load successfully.")

# Prefilling compression only, thinking disabled
press.decoding = False
context = """
    This is an example article about machine learning. Machine learning is a subset of artificial intelligence
    that focuses on building systems that learn from data. Recent advances in deep learning have revolutionized
    many fields including computer vision, natural language processing, and speech recognition.
    Transformer models like BERT and GPT have shown remarkable performance on various NLP tasks.
    The field continues to evolve with new architectures and training techniques being developed regularly.

    In this paper, we introduce a novel approach to attention mechanisms that improves efficiency
    while maintaining performance. Our method reduces computational complexity from O(n^2) to O(n log n)
    for sequence length n. Experiments on benchmark datasets show competitive results with
    state-of-the-art models while using significantly less memory and computation time.
"""
question = "\n What is this article about in 2 sentences ?"
answer = pipe(context, question=question, press=press)["answer"]
print(f"Compression ratio: {press.compression_ratio:.2%}\nAnswer: {answer}")

# Prefilling and decoding compression, thinking enabled
press.decoding = True
prompt = "What is the best hardware to run LLMs and why ?"
answer = pipe(prompt, press=press, enable_thinking=True, max_new_tokens=2000)["answer"]
print(f"Compression ratio: {press.compression_ratio:.2%}\nAnswer: {answer}")
